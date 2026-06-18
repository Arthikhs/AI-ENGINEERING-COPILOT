"""
KG + RAG Fusion Retriever
Upgrade over plain vector search:

  Query
    ├── Vector Search  (semantic recall via pgvector)
    ├── BM25 Search    (keyword recall)
    └── KG Traversal   (structural recall — follow import/call edges)
         ↓
    Merge + Deduplicate
         ↓
    Cross-Encoder Reranker (BGE)
         ↓
    Top-K enriched chunks → LLM

This answers questions like:
  "Which services indirectly depend on PaymentService?"
because the KG traversal surfaces files that are structurally
related, not just semantically similar.
"""
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from models.models import KnowledgeNode, KnowledgeEdge
from rag.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)

# Max graph hops for indirect dependency traversal
MAX_HOPS = 2


class KGRAGFusionRetriever:
    """
    Fuses three retrieval signals:
      1. Vector + BM25 (via HybridRetriever)
      2. Knowledge-graph traversal  (direct + indirect neighbours)
      3. Cross-encoder reranking over the merged candidate pool
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.hybrid = HybridRetriever(db)

    async def retrieve(
        self,
        query: str,
        repo_ids: List[str],
        top_k: int = 10,
        vector_candidates: int = 20,
        kg_candidates: int = 20,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            chunks:        List[Dict]   — reranked top-k chunks
            kg_nodes:      List[Dict]   — nodes found via graph traversal
            kg_edges:      List[Dict]   — edges between those nodes
            fusion_stats:  Dict         — how many came from each signal
          }
        """
        # ── 1. Hybrid (vector + BM25) over first repo (or all if cross-repo) ──
        hybrid_chunks: List[Dict] = []
        for repo_id in repo_ids:
            chunks = await self.hybrid.retrieve(
                query, repo_id,
                top_k=vector_candidates,
                bm25_candidates=vector_candidates,
                vector_candidates=vector_candidates,
            )
            hybrid_chunks.extend(chunks)

        # ── 2. KG traversal — find seed nodes, then walk edges ──────────────
        kg_chunks, kg_nodes, kg_edges = await self._kg_traverse(
            query, repo_ids, limit=kg_candidates
        )

        # ── 3. Merge + deduplicate by chunk id ───────────────────────────────
        seen: Dict[str, Dict] = {}
        for c in hybrid_chunks:
            seen[c["id"]] = {**c, "_source": "hybrid"}
        for c in kg_chunks:
            if c["id"] not in seen:
                seen[c["id"]] = {**c, "_source": "kg"}
            else:
                seen[c["id"]]["_source"] = "fusion"

        candidates = list(seen.values())

        # ── 4. Rerank the merged pool ────────────────────────────────────────
        reranked = self._rerank(query, candidates, top_k)

        stats = {
            "hybrid_candidates": len(hybrid_chunks),
            "kg_candidates": len(kg_chunks),
            "merged_before_rerank": len(candidates),
            "returned_after_rerank": len(reranked),
        }

        logger.info(
            f"[KGRAGFusion] query='{query[:60]}' stats={stats}"
        )

        return {
            "chunks": reranked,
            "kg_nodes": kg_nodes,
            "kg_edges": kg_edges,
            "fusion_stats": stats,
        }

    # ── KG traversal ──────────────────────────────────────────────────────────

    async def _kg_traverse(
        self, query: str, repo_ids: List[str], limit: int
    ) -> tuple[List[Dict], List[Dict], List[Dict]]:
        """
        1. Find seed nodes whose names match keywords in the query.
        2. Walk up to MAX_HOPS edges outward from each seed.
        3. For each reached node, fetch its code chunks from embeddings table.
        """
        keywords = [w for w in query.split() if len(w) > 3][:5]
        if not keywords:
            return [], [], []

        # Find seed nodes
        seed_result = await self.db.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.repo_id.in_(repo_ids),
                KnowledgeNode.name.ilike(f"%{keywords[0]}%"),
            ).limit(5)
        )
        seeds = seed_result.scalars().all()

        if not seeds:
            return [], [], []

        # BFS up to MAX_HOPS
        visited_ids = set(str(n.id) for n in seeds)
        frontier = list(seeds)
        all_nodes = list(seeds)
        all_edges: List[Dict] = []

        for _ in range(MAX_HOPS):
            next_frontier = []
            for node in frontier:
                edges_result = await self.db.execute(
                    select(KnowledgeEdge, KnowledgeNode)
                    .join(KnowledgeNode, KnowledgeEdge.target_node_id == KnowledgeNode.id)
                    .where(KnowledgeEdge.source_node_id == node.id)
                    .limit(10)
                )
                for edge, target in edges_result.fetchall():
                    all_edges.append({
                        "source": str(node.id),
                        "source_name": node.name,
                        "target": str(target.id),
                        "target_name": target.name,
                        "edge_type": edge.edge_type,
                        "weight": edge.weight,
                    })
                    if str(target.id) not in visited_ids:
                        visited_ids.add(str(target.id))
                        all_nodes.append(target)
                        next_frontier.append(target)
            frontier = next_frontier
            if not frontier:
                break

        # Fetch code chunks for all visited nodes by file_path
        file_paths = list({n.file_path for n in all_nodes if n.file_path})
        kg_chunks: List[Dict] = []
        if file_paths:
            for repo_id in repo_ids:
                for fp in file_paths[:limit]:
                    result = await self.db.execute(
                        text("""
                            SELECT id, file_path, content, language, chunk_type, chunk_name
                            FROM embeddings
                            WHERE repo_id = :repo_id AND file_path = :fp
                            LIMIT 3
                        """),
                        {"repo_id": repo_id, "fp": fp},
                    )
                    for row in result.fetchall():
                        kg_chunks.append({
                            "id": str(row.id),
                            "file_path": row.file_path,
                            "content": row.content,
                            "language": row.language,
                            "chunk_type": row.chunk_type,
                            "chunk_name": row.chunk_name,
                            "score": 0.5,   # base score for KG-sourced chunks
                        })

        node_dicts = [
            {
                "id": str(n.id),
                "name": n.name,
                "type": n.node_type,
                "repo": n.repo_full_name,
                "file_path": n.file_path,
            }
            for n in all_nodes
        ]

        return kg_chunks, node_dicts, all_edges

    # ── Reranker (delegates to HybridRetriever's reranker) ───────────────────

    def _rerank(self, query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
        return self.hybrid._rerank(query, candidates, top_k)
