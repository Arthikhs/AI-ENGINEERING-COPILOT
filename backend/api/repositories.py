from typing import List, Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from models.models import User, Repository, RepositorySync, SyncStatus
from database import get_db
from api.auth import get_current_user
from ingestion.service import IngestionService
import httpx
import json
import asyncio
from datetime import datetime

router = APIRouter(prefix="/repos", tags=["repositories"])


class ConnectRepoRequest(BaseModel):
    full_name: str  # e.g. "owner/repo"
    branch: str = "main"


class RepoResponse(BaseModel):
    id: str
    full_name: str
    name: str
    description: Optional[str]
    language: Optional[str]
    is_indexed: bool
    total_files: int
    total_chunks: int
    last_synced_at: Optional[datetime]
    default_branch: str

    class Config:
        from_attributes = True


@router.post("/connect", response_model=RepoResponse)
async def connect_repository(
    body: ConnectRepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a GitHub repository to the platform."""
    # Check if already connected
    result = await db.execute(
        select(Repository).where(
            Repository.owner_id == current_user.id,
            Repository.full_name == body.full_name,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return _repo_to_response(existing)

    # Fetch repo info from GitHub
    headers = {"Authorization": f"Bearer {current_user.github_access_token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{body.full_name}", headers=headers
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Repository not found on GitHub")
        gh_repo = resp.json()

    repo = Repository(
        owner_id=current_user.id,
        github_repo_id=str(gh_repo["id"]),
        full_name=gh_repo["full_name"],
        name=gh_repo["name"],
        description=gh_repo.get("description"),
        default_branch=body.branch or gh_repo.get("default_branch", "main"),
        language=gh_repo.get("language"),
        clone_url=gh_repo["clone_url"],
        is_private=gh_repo.get("private", False),
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return _repo_to_response(repo)


@router.post("/{repo_id}/index")
async def index_repository(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger async repository indexing via Celery worker."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id, Repository.owner_id == current_user.id
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    sync = RepositorySync(repo_id=repo.id, branch=repo.default_branch)
    db.add(sync)
    await db.commit()
    await db.refresh(sync)

    # Try Celery first, fall back to BackgroundTasks if worker not running
    try:
        from worker import ingest_repository
        ingest_repository.delay(str(repo.id), str(sync.id), current_user.github_access_token)
    except Exception:
        import asyncio
        asyncio.create_task(
            IngestionService.run_ingestion(str(repo.id), str(sync.id), current_user.github_access_token)
        )

    return {"message": "Indexing started", "sync_id": str(sync.id)}


@router.get("/{repo_id}/index/progress")
async def index_progress(repo_id: str, sync_id: str):
    """
    SSE endpoint — streams real-time indexing progress from Redis.
    Poll: GET /repos/{repo_id}/index/progress?sync_id={sync_id}
    """
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            import redis.asyncio as aioredis
            from config import get_settings
            _r = aioredis.from_url(get_settings().redis_url, decode_responses=True)
            key = f"sync_progress:{sync_id}"
            for _ in range(120):   # max 2 minutes
                raw = await _r.get(key)
                if raw:
                    data = json.loads(raw)
                    yield f"data: {json.dumps(data)}\n\n"
                    if data.get("status") in ("completed", "failed"):
                        break
                await asyncio.sleep(1)
            yield "data: {\"status\": \"timeout\"}\n\n"
        except Exception as e:
            yield f"data: {{\"status\": \"error\", \"error\": \"{e}\"}}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("", response_model=List[RepoResponse])
async def list_repositories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Repository).where(Repository.owner_id == current_user.id)
    )
    return [_repo_to_response(r) for r in result.scalars().all()]


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repository(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id, Repository.owner_id == current_user.id
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return _repo_to_response(repo)


@router.get("/{repo_id}/sync/status")
async def get_sync_status(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RepositorySync)
        .where(RepositorySync.repo_id == repo_id)
        .order_by(RepositorySync.created_at.desc())
        .limit(1)
    )
    sync = result.scalar_one_or_none()
    if not sync:
        return {"status": "never_synced"}
    return {
        "status": sync.status,
        "files_processed": sync.files_processed,
        "chunks_created": sync.chunks_created,
        "error_message": sync.error_message,
        "started_at": sync.started_at,
        "completed_at": sync.completed_at,
    }


def _repo_to_response(repo: Repository) -> RepoResponse:
    return RepoResponse(
        id=str(repo.id),
        full_name=repo.full_name,
        name=repo.name,
        description=repo.description,
        language=repo.language,
        is_indexed=repo.is_indexed,
        total_files=repo.total_files,
        total_chunks=repo.total_chunks,
        last_synced_at=repo.last_synced_at,
        default_branch=repo.default_branch,
    )
