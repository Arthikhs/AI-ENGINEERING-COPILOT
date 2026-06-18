"""
Hybrid RAG: BM25 + Vector Search + Cross-Encoder Reranking
Production-grade retrieval pipeline used by systems like Sourcegraph.

Pipeline:
  Query
    ↓
  BM25 (keyword recall)  +  Vector Search (semantic recall)
    ↓
  Merge + Deduplicate
    ↓
  Cross-Encoder Reranker (BGE)
    ↓
  Top-K chunks → LLM
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from embeddings.service import EmbeddingService
import logging
import re

logger = logging.getLogger(__name__)

# BGE reranker — lightweight, runs locally, no API cost
RERANKER_MODEL = "BAAI/bge-reranker-base"
_reranker: Optional[CrossEncoder] = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
    return _reranker


class HybridRetriever:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()

    async def retrieve(
        self,
        query: str,
        repo_id: str,
        top_k: int = 8,
        bm25_candidates: int = 30,
        vector_candidates: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Full hybrid retrieval pipeline:
        1. BM25 keyword search over stored chunks
        2. Vector similarity search
        3. Merge + deduplicate
        4. Cross-encoder reranking
        """
        # Run both retrievals in parallel
        bm25_results = await self._bm25_search(query, repo_id, bm25_candidates)
        vector_results = await self._vector_search(query, repo_id, vector_candidates)

        # Merge and deduplicate by chunk id
        merged: Dict[str, Dict] = {}
        for chunk in vector_results:
            merged[chunk["id"]] = {**chunk, "retrieval_source": "vector"}
        for chunk in bm25_results:
            if chunk["id"] not in merged:
                merged[chunk["id"]] = {**chunk, "retrieval_source": "bm25"}
            else:
                merged[chunk["id"]]["retrieval_source"] = "hybrid"

        candidates = list(merged.values())
        if not candidates:
            return []

        # Rerank with cross-encoder
        reranked = self._rerank(query, candidates, top_k)
        return reranked

    async def _vector_search(self, query: str, repo_id: str, limit: int) -> List[Dict]:
        embedding = await self.embedding_service.embed(query)
        embedding_str = f"[{','.join(map(str, embedding))}]"

        result = await self.db.execute(
            text("""
                SELECT id, file_path, content, language, chunk_type, chunk_name,
                       1 - (embedding <=> :emb::vector) AS similarity
                FROM embeddings
                WHERE repo_id = :repo_id
                ORDER BY embedding <=> :emb::vector
                LIMIT :limit
            """),
            {"emb": embedding_str, "repo_id": repo_id, "limit": limit},
        )
        return [
            {
                "id": str(r.id), "file_path": r.file_path, "content": r.content,
                "language": r.language, "chunk_type": r.chunk_type,
                "chunk_name": r.chunk_name, "score": float(r.similarity),
            }
            for r in result.fetchall()
        ]

    async def _bm25_search(self, query: str, repo_id: str, limit: int) -> List[Dict]:
        # Fetch candidate pool from DB (broader than needed, BM25 will rank)
        result = await self.db.execute(
            text("""
                SELECT id, file_path, content, language, chunk_type, chunk_name
                FROM embeddings
                WHERE repo_id = :repo_id
                LIMIT 500
            """),
            {"repo_id": repo_id},
        )
        rows = result.fetchall()
        if not rows:
            return []

        # Tokenise
        tokenised_corpus = [self._tokenise(r.content) for r in rows]
        bm25 = BM25Okapi(tokenised_corpus)
        query_tokens = self._tokenise(query)
        scores = bm25.get_scores(query_tokens)

        # Sort by score, take top candidates
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:limit]
        return [
            {
                "id": str(rows[i].id), "file_path": rows[i].file_path,
                "content": rows[i].content, "language": rows[i].language,
                "chunk_type": rows[i].chunk_type, "chunk_name": rows[i].chunk_name,
                "score": float(score),
            }
            for i, score in ranked if score > 0
        ]

    def _rerank(self, query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
        if not candidates:
            return []
        try:
            reranker = _get_reranker()
            pairs = [[query, c["content"][:512]] for c in candidates]
            scores = reranker.predict(pairs)
            for i, chunk in enumerate(candidates):
                chunk["rerank_score"] = float(scores[i])
            reranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0), reverse=True)
            return reranked[:top_k]
        except Exception as e:
            logger.warning(f"Reranker failed, falling back to score sort: {e}")
            return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())
