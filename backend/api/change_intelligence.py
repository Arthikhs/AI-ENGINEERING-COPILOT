"""
Repository Change Intelligence API
View AI-generated impact reports from GitHub push events.
Also supports manual trigger for testing.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from api.auth import get_current_user
from models.models import User, Repository, ChangeIntelligenceReport

router = APIRouter(prefix="/change-intelligence", tags=["change-intelligence"])


class ManualAnalyzeRequest(BaseModel):
    repo_id: str
    commit_sha: str = "manual"
    branch: str = "main"
    changed_files: list[str]
    pusher: str = "manual"


# ── List reports ───────────────────────────────────────────────────────────────

@router.get("/reports")
async def list_reports(
    repo_id: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ChangeIntelligenceReport).order_by(
        ChangeIntelligenceReport.created_at.desc()
    )
    if repo_id:
        q = q.where(ChangeIntelligenceReport.repo_id == repo_id)
    result = await db.execute(q.limit(limit))
    reports = result.scalars().all()
    return {
        "reports": [
            {
                "id": str(r.id),
                "repo_id": str(r.repo_id),
                "commit_sha": r.commit_sha,
                "branch": r.branch,
                "pusher": r.pusher,
                "files_changed_count": len(r.files_changed or []),
                "affected_services_count": len(r.affected_services or []),
                "risk_count": len(r.risks or []),
                "summary": r.summary,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ]
    }


# ── Get single report ──────────────────────────────────────────────────────────

@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChangeIntelligenceReport).where(ChangeIntelligenceReport.id == report_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": str(r.id),
        "repo_id": str(r.repo_id),
        "commit_sha": r.commit_sha,
        "branch": r.branch,
        "pusher": r.pusher,
        "files_changed": r.files_changed,
        "architectural_impact": r.architectural_impact,
        "risks": r.risks,
        "affected_services": r.affected_services,
        "recommendation": r.recommendation,
        "summary": r.summary,
        "created_at": r.created_at.isoformat(),
    }


# ── Manual trigger (for testing without a webhook) ────────────────────────────

@router.post("/analyze")
async def manual_analyze(
    body: ManualAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger Change Intelligence analysis — useful for demos and testing."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == body.repo_id,
            Repository.owner_id == current_user.id,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from agents.change_intelligence_agent import ChangeIntelligenceAgent
    agent = ChangeIntelligenceAgent(db)
    report = await agent.analyze(
        repo_id=body.repo_id,
        repo_full_name=repo.full_name,
        commit_sha=body.commit_sha,
        changed_files=body.changed_files,
        pusher=body.pusher,
        branch=body.branch,
    )
    return report
