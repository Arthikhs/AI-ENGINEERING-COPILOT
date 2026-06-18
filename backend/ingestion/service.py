import os
import tempfile
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Callable, Optional
import git
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import update, text
from models.models import Repository, RepositorySync, CodeFile, CodeChunk, SyncStatus
from ingestion.chunker import CodeChunker
from embeddings.service import EmbeddingService
from config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Dummy sentinel so worker.py can import without circular issues
_progress_callback = None

SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb",
    ".cs", ".cpp", ".c", ".rs", ".php", ".kt", ".scala", ".swift",
    ".md", ".yml", ".yaml", ".json", ".sql", ".sh",
}

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", "coverage", ".pytest_cache",
}


class IngestionService:
    @staticmethod
    async def run_ingestion(
        repo_id: str, sync_id: str, github_token: str,
        progress_cb: Optional[Callable] = None,
    ):
        """Background task: clone repo, chunk, embed, store."""
        engine = create_async_engine(settings.database_url)
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with SessionLocal() as db:
            try:
                await IngestionService._run(repo_id, sync_id, github_token, db, progress_cb)
            except Exception as e:
                logger.error(f"Ingestion failed for repo {repo_id}: {e}")
                await db.execute(
                    update(RepositorySync)
                    .where(RepositorySync.id == sync_id)
                    .values(status=SyncStatus.FAILED, error_message=str(e), completed_at=datetime.utcnow())
                )
                await db.commit()
            finally:
                await engine.dispose()

    @staticmethod
    async def _run(
        repo_id: str, sync_id: str, github_token: str, db: AsyncSession,
        progress_cb: Optional[Callable] = None,
    ):
        def _progress(stage: str, pct: int):
            if progress_cb:
                progress_cb(stage, pct)
        from sqlalchemy import select

        # Mark sync as running
        await db.execute(
            update(RepositorySync)
            .where(RepositorySync.id == sync_id)
            .values(status=SyncStatus.RUNNING, started_at=datetime.utcnow())
        )
        await db.commit()

        # Fetch repo
        result = await db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one()

        # Build authenticated clone URL
        clone_url = repo.clone_url.replace(
            "https://", f"https://{github_token}@"
        ) if github_token else repo.clone_url

        with tempfile.TemporaryDirectory() as tmpdir:
            _progress("cloning", 10)
            logger.info(f"Cloning {repo.full_name} into {tmpdir}")
            git_repo = git.Repo.clone_from(
                clone_url, tmpdir, branch=repo.default_branch, depth=1
            )
            commit_sha = git_repo.head.commit.hexsha
            _progress("chunking", 20)

            files_processed = 0
            chunks_created = 0
            chunker = CodeChunker()
            embedding_service = EmbeddingService()

            # Walk repository files
            for file_path in Path(tmpdir).rglob("*"):
                if not file_path.is_file():
                    continue
                if any(skip in file_path.parts for skip in SKIP_DIRS):
                    continue
                if file_path.suffix not in SUPPORTED_EXTENSIONS:
                    continue

                relative_path = str(file_path.relative_to(tmpdir))
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if not content.strip() or len(content) > 500_000:
                        continue

                    language = _detect_language(file_path.suffix)

                    # Store file record
                    code_file = CodeFile(
                        repo_id=repo_id,
                        file_path=relative_path,
                        language=language,
                        size_bytes=file_path.stat().st_size,
                        commit_sha=commit_sha,
                    )
                    db.add(code_file)
                    await db.flush()

                    # Chunk the file
                    chunks = chunker.chunk(content, relative_path, language)

                    # Generate embeddings in batches
                    texts = [c["content"] for c in chunks]
                    embeddings = await embedding_service.embed_batch(texts)

                    for chunk_data, embedding in zip(chunks, embeddings):
                        chunk = CodeChunk(
                            repo_id=repo_id,
                            file_id=code_file.id,
                            file_path=relative_path,
                            content=chunk_data["content"],
                            chunk_type=chunk_data.get("type"),
                            chunk_name=chunk_data.get("name"),
                            start_line=chunk_data.get("start_line"),
                            end_line=chunk_data.get("end_line"),
                            language=language,
                        )
                        db.add(chunk)
                        await db.flush()

                        # Store embedding via raw SQL for pgvector
                        embedding_str = f"[{','.join(map(str, embedding))}]"
                        await db.execute(
                            text(
                                "INSERT INTO embeddings "
                                "(chunk_id, repo_id, file_path, content, embedding, language, chunk_type, chunk_name) "
                                "VALUES (:chunk_id, :repo_id, :file_path, :content, :embedding::vector, "
                                ":language, :chunk_type, :chunk_name)"
                            ),
                            {
                                "chunk_id": str(chunk.id),
                                "repo_id": repo_id,
                                "file_path": relative_path,
                                "content": chunk_data["content"],
                                "embedding": embedding_str,
                                "language": language,
                                "chunk_type": chunk_data.get("type"),
                                "chunk_name": chunk_data.get("name"),
                            },
                        )
                        chunks_created += 1

                    code_file.is_indexed = True
                    files_processed += 1
                    if files_processed % 10 == 0:
                        pct = min(20 + int((files_processed / max(total_files, 1)) * 70), 90)
                        _progress("embedding", pct)

                except Exception as e:
                    logger.warning(f"Failed to process {relative_path}: {e}")
                    continue

            # Update repo and sync status
            await db.execute(
                update(Repository)
                .where(Repository.id == repo_id)
                .values(
                    is_indexed=True,
                    total_files=files_processed,
                    total_chunks=chunks_created,
                    last_commit=commit_sha,
                    last_synced_at=datetime.utcnow(),
                )
            )
            await db.execute(
                update(RepositorySync)
                .where(RepositorySync.id == sync_id)
                .values(
                    status=SyncStatus.COMPLETED,
                    commit_sha=commit_sha,
                    files_processed=files_processed,
                    chunks_created=chunks_created,
                    completed_at=datetime.utcnow(),
                )
            )
            await db.commit()
            logger.info(f"Ingestion complete: {files_processed} files, {chunks_created} chunks")


def _detect_language(suffix: str) -> str:
    mapping = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".tsx": "TypeScript", ".jsx": "JavaScript", ".java": "Java",
        ".go": "Go", ".rb": "Ruby", ".cs": "C#", ".cpp": "C++",
        ".c": "C", ".rs": "Rust", ".php": "PHP", ".kt": "Kotlin",
        ".scala": "Scala", ".swift": "Swift", ".sql": "SQL",
        ".sh": "Shell", ".md": "Markdown", ".yml": "YAML",
        ".yaml": "YAML", ".json": "JSON",
    }
    return mapping.get(suffix, "Unknown")
