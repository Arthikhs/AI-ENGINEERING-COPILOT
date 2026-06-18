from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from models.models import User, Repository, ArchitectureReport
from database import get_db
from api.auth import get_current_user
from agents.architecture_agent import ArchitectureAgent

router = APIRouter(prefix="/analyze", tags=["architecture"])


class ArchitectureRequest(BaseModel):
    repo_id: str


@router.post("/architecture")
async def analyze_architecture(
    body: ArchitectureRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate architecture analysis for a repository."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == body.repo_id, Repository.owner_id == current_user.id
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if not repo.is_indexed:
        raise HTTPException(status_code=400, detail="Repository must be indexed first")

    agent = ArchitectureAgent(db=db)
    report = await agent.analyze(repo_id=str(repo.id), repo_full_name=repo.full_name)
    return report


@router.get("/architecture/{repo_id}/latest")
async def get_latest_report(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ArchitectureReport)
        .where(ArchitectureReport.repo_id == repo_id)
        .order_by(ArchitectureReport.created_at.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No architecture report found")
    return {
        "id": str(report.id),
        "service_count": report.service_count,
        "api_count": report.api_count,
        "dependency_graph": report.dependency_graph,
        "circular_dependencies": report.circular_dependencies,
        "layers": report.layers,
        "summary": report.summary,
        "created_at": report.created_at,
    }
