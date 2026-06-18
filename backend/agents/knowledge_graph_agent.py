"""
Knowledge Graph Agent
Answers cross-repository questions using:
1. Knowledge graph traversal (node/edge queries)
2. Cross-repository vector search
3. GPT-4o reasoning over combined context
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from langchain.schema import HumanMessage, SystemMessage
from models.models import KnowledgeNode, KnowledgeEdge, Repository
from rag.kg_rag_fusion import KGRAGFusionRetriever
from agents.model_router_agent import routed_invoke
import logging

logger = logging.getLogger(__name__)

KG_SYSTEM_PROMPT = """You are an expert software architect with deep knowledge of
multi-service, enterprise codebases.

You have access to:
1. A knowledge graph showing how services, modules, and libraries depend on each other
2. Actual source code retrieved via semantic + keyword + graph-traversal fusion search

When answering questions:
- Trace dependency chains clearly (A → B → C)
- Identify which repositories are involved
- Highlight shared libraries and common dependencies
- Flag circular dependencies if present
- Mention specific file paths when relevant
- Be precise about direction: "X depends on Y" vs "Y is used by X"
- For indirect dependencies, walk the full chain step by step
"""


class KnowledgeGraphAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def query(self, question: str, user_id: str) -> Dict[str, Any]:
        """Answer a cross-repository question using KG + RAG Fusion."""

        # 1. Get all indexed repos for this user
        result = await self.db.execute(
            select(Repository).where(
                Repository.owner_id == user_id,
                Repository.is_indexed == True,
            )
        )
        repos = result.scalars().all()
        if not repos:
            return {
                "answer": "No indexed repositories found. Please index at least one repository first.",
                "graph_context": {},
                "sources": [],
                "fusion_stats": {},
            }

        repo_ids = [str(r.id) for r in repos]
        repo_map = {str(r.id): r.full_name for r in repos}

        # 2. KG + RAG Fusion retrieval (Vector + BM25 + Graph traversal + Reranker)
        fusion = KGRAGFusionRetriever(self.db)
        fusion_result = await fusion.retrieve(
            query=question,
            repo_ids=repo_ids,
            top_k=12,
        )

        reranked_chunks = fusion_result["chunks"]
        kg_nodes        = fusion_result["kg_nodes"]
        kg_edges        = fusion_result["kg_edges"]
        fusion_stats    = fusion_result["fusion_stats"]

        # 3. Build graph context summary (for prompt)
        graph_context = await self._build_graph_context(question, repo_ids)

        # 4. Format context for LLM
        code_context = self._format_vector_context(reranked_chunks)
        graph_text   = self._format_graph_context(graph_context, repo_map)

        # Build traversal chain description
        chain_text = self._format_kg_traversal(kg_nodes, kg_edges)

        messages = [
            SystemMessage(content=KG_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Repositories in scope: {', '.join(r.full_name for r in repos)}\n\n"
                f"=== Knowledge Graph (Structural Context) ===\n{graph_text}\n\n"
                f"=== Graph Traversal Chain ===\n{chain_text}\n\n"
                f"=== Relevant Code (Fusion: Vector + BM25 + KG + Reranker) ===\n{code_context}\n\n"
                f"Question: {question}"
            )),
        ]

        result = await routed_invoke(
            task_type="knowledge_graph",
            messages=messages,
        )

        return {
            "answer": result["response"].content,
            "agent_type": "knowledge_graph_fusion",
            "repos_searched": [r.full_name for r in repos],
            "graph_context": graph_context,
            "kg_traversal": {"nodes": kg_nodes, "edges": kg_edges},
            "fusion_stats": fusion_stats,
            "sources": [
                {
                    "file_path": c["file_path"],
                    "chunk_name": c.get("chunk_name"),
                    "score": c.get("rerank_score") or c.get("score", 0),
                    "source": c.get("_source", "hybrid"),
                }
                for c in reranked_chunks[:8]
            ],
        }

    async def get_graph(self, user_id: str) -> Dict[str, Any]:
        """Return the full multi-repo knowledge graph for visualization."""
        result = await self.db.execute(
            select(Repository).where(
                Repository.owner_id == user_id,
                Repository.is_indexed == True,
            )
        )
        repos = result.scalars().all()
        repo_ids = [str(r.id) for r in repos]

        if not repo_ids:
            return {"nodes": [], "edges": []}

        # Fetch all nodes
        nodes_result = await self.db.execute(
            select(KnowledgeNode).where(KnowledgeNode.repo_id.in_(repo_ids))
        )
        nodes = nodes_result.scalars().all()
        node_ids = [n.id for n in nodes]

        # Fetch all edges between those nodes
        edges_result = await self.db.execute(
            select(KnowledgeEdge).where(
                KnowledgeEdge.source_node_id.in_(node_ids),
                KnowledgeEdge.target_node_id.in_(node_ids),
            )
        )
        edges = edges_result.scalars().all()

        return {
            "nodes": [
                {
                    "id": str(n.id),
                    "name": n.name,
                    "type": n.node_type,
                    "repo": n.repo_full_name,
                    "file_path": n.file_path,
                    "language": n.language,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "source": str(e.source_node_id),
                    "target": str(e.target_node_id),
                    "type": e.edge_type,
                    "weight": e.weight,
                }
                for e in edges
            ],
            "repos": [r.full_name for r in repos],
        }

    async def find_dependents(self, node_name: str, user_id: str) -> Dict[str, Any]:
        """
        Find all services/modules that depend on a given node.
        Example: 'Which services depend on UserService?'
        """
        result = await self.db.execute(
            select(Repository).where(
                Repository.owner_id == user_id,
                Repository.is_indexed == True,
            )
        )
        repos = result.scalars().all()
        repo_ids = [str(r.id) for r in repos]

        # Find target node by name (case-insensitive)
        node_result = await self.db.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.repo_id.in_(repo_ids),
                KnowledgeNode.name.ilike(f"%{node_name}%"),
            )
        )
        target_nodes = node_result.scalars().all()

        if not target_nodes:
            return {"dependents": [], "message": f"No node found matching '{node_name}'"}

        all_dependents = []
        for target in target_nodes:
            # Find all nodes with edges pointing TO this node
            edges_result = await self.db.execute(
                select(KnowledgeEdge, KnowledgeNode)
                .join(KnowledgeNode, KnowledgeEdge.source_node_id == KnowledgeNode.id)
                .where(KnowledgeEdge.target_node_id == target.id)
            )
            for edge, source_node in edges_result.fetchall():
                all_dependents.append({
                    "name": source_node.name,
                    "repo": source_node.repo_full_name,
                    "type": source_node.node_type,
                    "file_path": source_node.file_path,
                    "edge_type": edge.edge_type,
                    "weight": edge.weight,
                })

        return {
            "target": node_name,
            "dependents": all_dependents,
            "count": len(all_dependents),
        }

    async def _build_graph_context(self, question: str, repo_ids: List[str]) -> Dict:
        """Extract relevant subgraph based on keywords in the question."""
        words = [w for w in question.split() if len(w) > 3]
        if not words:
            return {}

        # Find nodes whose names match question keywords
        conditions = " OR ".join(f"n.name ILIKE :kw{i}" for i in range(len(words)))
        params: Dict = {"repo_ids": repo_ids}
        for i, w in enumerate(words[:5]):
            params[f"kw{i}"] = f"%{w}%"

        node_result = await self.db.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.repo_id.in_(repo_ids),
                KnowledgeNode.name.ilike(f"%{words[0]}%"),
            ).limit(10)
        )
        relevant_nodes = node_result.scalars().all()

        graph: Dict[str, List] = {}
        for node in relevant_nodes:
            # Get outgoing edges
            edges_result = await self.db.execute(
                select(KnowledgeEdge, KnowledgeNode)
                .join(KnowledgeNode, KnowledgeEdge.target_node_id == KnowledgeNode.id)
                .where(KnowledgeEdge.source_node_id == node.id)
                .limit(10)
            )
            deps = []
            for edge, target_node in edges_result.fetchall():
                deps.append(f"{target_node.name} ({target_node.repo_full_name})")

            # Get incoming edges
            in_edges_result = await self.db.execute(
                select(KnowledgeEdge, KnowledgeNode)
                .join(KnowledgeNode, KnowledgeEdge.source_node_id == KnowledgeNode.id)
                .where(KnowledgeEdge.target_node_id == node.id)
                .limit(10)
            )
            used_by = []
            for edge, source_node in in_edges_result.fetchall():
                used_by.append(f"{source_node.name} ({source_node.repo_full_name})")

            graph[f"{node.name} [{node.repo_full_name}]"] = {
                "type": node.node_type,
                "depends_on": deps,
                "used_by": used_by,
            }

        return graph

    def _format_kg_traversal(self, nodes: List[Dict], edges: List[Dict]) -> str:
        """Format the graph traversal chain for the LLM prompt."""
        if not nodes:
            return "No graph traversal nodes found."
        lines = []
        node_names = {n["id"]: n["name"] for n in nodes}
        lines.append(f"Nodes traversed ({len(nodes)}): " + ", ".join(n["name"] for n in nodes[:10]))
        if edges:
            lines.append(f"Edges found ({len(edges)}):")
            for e in edges[:15]:
                lines.append(f"  {e['source_name']} --[{e['edge_type']}]--> {e['target_name']} (weight={e['weight']})")
        return "\n".join(lines)

    def _format_graph_context(self, graph: Dict, repo_map: Dict) -> str:
        if not graph:
            return "No matching nodes found in knowledge graph."
        lines = []
        for node_label, info in graph.items():
            lines.append(f"Node: {node_label} (type: {info['type']})")
            if info["depends_on"]:
                lines.append(f"  → depends on: {', '.join(info['depends_on'])}")
            if info["used_by"]:
                lines.append(f"  ← used by: {', '.join(info['used_by'])}")
        return "\n".join(lines)

    def _format_vector_context(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "No relevant code found."
        parts = []
        for c in chunks[:8]:
            header = f"[{c['repo_full_name']}] {c['file_path']}"
            if c.get("chunk_name"):
                header += f" → {c['chunk_name']}"
            parts.append(f"{header}\n```\n{c['content'][:600]}\n```")
        return "\n\n---\n\n".join(parts)
