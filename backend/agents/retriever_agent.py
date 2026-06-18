"""
Retriever Agent — dedicated hybrid search node.
Always runs first in the multi-agent pipeline when code context is needed.

Returns structured retrieval results:
{
  "relevant_files": [...],
  "relevant_methods": [...],
  "documentation": [...]
}
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from rag.hybrid_retriever import HybridRetriever
from agents.state import AgentState
import logging

logger = logging.getLogger(__name__)


class RetrieverAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)

    async def run(self, state: AgentState) -> AgentState:
        """Hybrid retrieval: BM25 + Vector + Cross-Encoder Reranker."""
        question = state["question"]
        repo_id = state["repo_id"]

        try:
            chunks = await self.retriever.retrieve(question, repo_id, top_k=12)
        except Exception as e:
            logger.error(f"RetrieverAgent failed: {e}")
            chunks = []

        # Categorise chunks
        relevant_files: List[str] = []
        relevant_methods: List[Dict] = []
        documentation: List[Dict] = []
        seen_files: set = set()

        for c in chunks:
            fp = c.get("file_path", "")
            if fp not in seen_files:
                relevant_files.append(fp)
                seen_files.add(fp)

            ct = c.get("chunk_type", "")
            if ct in ("function", "method", "class"):
                relevant_methods.append({
                    "file": fp,
                    "name": c.get("chunk_name", ""),
                    "type": ct,
                    "content": c.get("content", "")[:300],
                })
            elif ct in ("module", "docstring", "comment"):
                documentation.append({
                    "file": fp,
                    "content": c.get("content", "")[:300],
                })

        # Store in state
        state["retriever_chunks"] = chunks
        state["retrieved_chunks"] = chunks   # keep legacy field in sync
        state["agent_outputs"]["retriever"] = {
            "relevant_files": relevant_files,
            "relevant_methods": relevant_methods,
            "documentation": documentation,
            "total_chunks": len(chunks),
        }

        # Build shared context string for downstream agents
        context_parts = []
        for c in chunks:
            header = f"File: {c['file_path']}"
            if c.get("chunk_name"):
                header += f" | {c['chunk_type']}: {c['chunk_name']}"
            context_parts.append(f"{header}\n```\n{c['content'][:600]}\n```")
        state["context"] = "\n\n---\n\n".join(context_parts)

        state["sources"] = [
            {
                "file_path": c["file_path"],
                "chunk_name": c.get("chunk_name"),
                "score": c.get("rerank_score", c.get("score", 0)),
                "retrieval_source": c.get("retrieval_source", "vector"),
            }
            for c in chunks[:6]
        ]

        logger.info(f"RetrieverAgent: {len(chunks)} chunks from {len(relevant_files)} files")
        return state
