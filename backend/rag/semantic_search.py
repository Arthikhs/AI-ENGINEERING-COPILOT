"""
Semantic Code Search — Google-like search over indexed code.
Uses Hybrid RAG (BM25 + Vector + Reranker) for best-in-class results.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from rag.hybrid_retriever import HybridRetriever
import logging

logger = logging.getLogger(__name__)


class SemanticSearchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)

    async def search(
        self,
        query: str,
        repo_id: str,
        top_k: int = 10,
        language_filter: Optional[str] = None,
        chunk_type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid semantic search with optional filters.
        Returns results ranked by relevance (BM25 + Vector + Reranker).
        """
        results = await self.retriever.retrieve(query, repo_id, top_k=top_k * 2)

        # Apply filters post-retrieval
        if language_filter:
            results = [r for r in results if (r.get("language") or "").lower() == language_filter.lower()]
        if chunk_type_filter:
            results = [r for r in results if (r.get("chunk_type") or "").lower() == chunk_type_filter.lower()]

        return results[:top_k]
