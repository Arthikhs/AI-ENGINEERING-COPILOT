from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from embeddings.service import EmbeddingService
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()

    async def similarity_search(
        self,
        query: str,
        repo_id: str,
        limit: int = 10,
        language_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for semantically similar code chunks within a single repo."""
        query_embedding = await self.embedding_service.embed(query)
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        sql = """
            SELECT
                e.id,
                e.file_path,
                e.content,
                e.language,
                e.chunk_type,
                e.chunk_name,
                1 - (e.embedding <=> :embedding::vector) AS similarity
            FROM embeddings e
            WHERE e.repo_id = :repo_id
            {language_filter}
            ORDER BY e.embedding <=> :embedding::vector
            LIMIT :limit
        """.format(
            language_filter="AND e.language = :language" if language_filter else ""
        )

        params = {
            "embedding": embedding_str,
            "repo_id": repo_id,
            "limit": limit,
        }
        if language_filter:
            params["language"] = language_filter

        result = await self.db.execute(text(sql), params)
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "file_path": row.file_path,
                "content": row.content,
                "language": row.language,
                "chunk_type": row.chunk_type,
                "chunk_name": row.chunk_name,
                "similarity": round(float(row.similarity), 4),
            }
            for row in rows
        ]

    async def cross_repo_search(
        self,
        query: str,
        repo_ids: List[str],
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Cross-repository semantic search.
        Searches across multiple repos and returns results tagged with repo info.
        """
        if not repo_ids:
            return []

        query_embedding = await self.embedding_service.embed(query)
        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        # Build parameterized repo_ids list
        repo_placeholders = ", ".join(f":repo_{i}" for i in range(len(repo_ids)))
        params: Dict[str, Any] = {
            "embedding": embedding_str,
            "limit": limit,
        }
        for i, rid in enumerate(repo_ids):
            params[f"repo_{i}"] = rid

        sql = f"""
            SELECT
                e.id,
                e.repo_id,
                r.full_name AS repo_full_name,
                r.name AS repo_name,
                e.file_path,
                e.content,
                e.language,
                e.chunk_type,
                e.chunk_name,
                1 - (e.embedding <=> :embedding::vector) AS similarity
            FROM embeddings e
            JOIN repositories r ON r.id = e.repo_id
            WHERE e.repo_id IN ({repo_placeholders})
            ORDER BY e.embedding <=> :embedding::vector
            LIMIT :limit
        """

        result = await self.db.execute(text(sql), params)
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "repo_id": str(row.repo_id),
                "repo_full_name": row.repo_full_name,
                "repo_name": row.repo_name,
                "file_path": row.file_path,
                "content": row.content,
                "language": row.language,
                "chunk_type": row.chunk_type,
                "chunk_name": row.chunk_name,
                "similarity": round(float(row.similarity), 4),
            }
            for row in rows
        ]
