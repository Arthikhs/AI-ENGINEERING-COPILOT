"""
Autonomous Engineer API
Endpoints:
  POST /autonomous-engineer/run           — Trigger agent from a GitHub issue
  GET  /autonomous-engineer/jobs/{job_id} — Get job status
  GET  /autonomous-engineer/jobs          — List jobs for current user
  POST /autonomous-engineer/webhook/issue — GitHub Issues webhook (label-triggered)
"""
import uuid
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models.models import Repository, User, AutonomousEngineerJob
from agents.autonomous_engineer_agent import AutonomousEngineerAgent
from api.auth import get_current_user
from config import get_settings

router = APIRouter(prefix="/autonomous-engineer", tags=["autonomous-engineer"])
logger = logging.getLogger(__name__)
settings = get_settings()


# ── Schemas ────────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    repo_id: str
    issue_number: int


class RunResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _job_to_dict(job: AutonomousEngineerJob) -> Dict[str, Any]:
    return {
        "job_id":        str(job.id),
        "status":        job.status,
        "user_id":       str(job.user_id),
        "repo_id":       str(job.repo_id),
        "repo_full_name": job.repo_full_name,
        "issue_number":  job.issue_number,
        "issue_title":   job.issue_title,
        "branch_name":   job.branch_name,
        "pr_url":        job.pr_url or "",
        "pr_number":     job.pr_number or 0,
        "files_changed": job.files_changed or [],
        "step_log":      job.step_log or [],
        "error":         job.error,
        "created_at":    job.created_at.isoformat() if job.created_at else None,
    }


# ── Background runner ──────────────────────────────────────────────────────────

async def _run_agent(job_id: str, repo_full_name: str, repo_id: str, github_token: str, issue_number: int):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # Mark running
        result = await db.execute(select(AutonomousEngineerJob).where(AutonomousEngineerJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            await engine.dispose()
            return
        job.status = "running"
        await db.commit()

    try:
        async with Session() as db:
            agent = AutonomousEngineerAgent(db)
            result_data = await agent.run(
                repo_full_name=repo_full_name,
                repo_id=repo_id,
                github_token=github_token,
                issue_number=issue_number,
            )

        async with Session() as db:
            result = await db.execute(select(AutonomousEngineerJob).where(AutonomousEngineerJob.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status        = result_data["status"]
                job.issue_title   = result_data.get("issue_title", "")
                job.branch_name   = result_data.get("branch_name", "")
                job.pr_url        = result_data.get("pr_url", "")
                job.pr_number     = result_data.get("pr_number") or None
                job.files_changed = result_data.get("files_changed", [])
                job.step_log      = result_data.get("step_log", [])
                job.error         = result_data.get("error")
                await db.commit()

    except Exception as e:
        logger.exception(f"Autonomous engineer job {job_id} failed")
        async with Session() as db:
            result = await db.execute(select(AutonomousEngineerJob).where(AutonomousEngineerJob.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.error  = str(e)
                await db.commit()
    finally:
        await engine.dispose()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunResponse)
async def run_autonomous_engineer(
    req: RunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger the Autonomous Engineer Agent for a GitHub issue."""
    result = await db.execute(select(Repository).where(
        Repository.id == req.repo_id,
        Repository.owner_id == current_user.id,
    ))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    github_token = repo.owner.github_access_token if repo.owner else settings.github_token
    if not github_token:
        raise HTTPException(status_code=400, detail="No GitHub token available for this repository")

    job = AutonomousEngineerJob(
        user_id=current_user.id,
        repo_id=repo.id,
        repo_full_name=repo.full_name,
        issue_number=req.issue_number,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        _run_agent,
        str(job.id),
        repo.full_name,
        str(repo.id),
        github_token,
        req.issue_number,
    )

    return RunResponse(
        job_id=str(job.id),
        status="queued",
        message=f"Autonomous engineer started for issue #{req.issue_number} in {repo.full_name}",
    )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll the status of an autonomous engineer job."""
    result = await db.execute(select(AutonomousEngineerJob).where(AutonomousEngineerJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if str(job.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    return _job_to_dict(job)


@router.get("/jobs")
async def list_jobs(
    repo_id: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List autonomous engineer jobs for the current user."""
    query = select(AutonomousEngineerJob).where(
        AutonomousEngineerJob.user_id == current_user.id
    ).order_by(AutonomousEngineerJob.created_at.desc()).limit(50)

    if repo_id:
        query = query.where(AutonomousEngineerJob.repo_id == repo_id)

    result = await db.execute(query)
    return {"jobs": [_job_to_dict(j) for j in result.scalars().all()]}


@router.post("/webhook/issue")
async def issue_webhook(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    GitHub Issues webhook — auto-trigger agent when issue is labeled 'ai-engineer'.
    Configure in GitHub: Settings → Webhooks → Issues event.
    """
    action = request.get("action", "")
    issue = request.get("issue", {})
    labels = [l["name"] for l in issue.get("labels", [])]

    if action not in ("labeled", "opened") or "ai-engineer" not in labels:
        return {"skipped": True}

    repo_full_name = request.get("repository", {}).get("full_name", "")
    issue_number = issue.get("number")

    result = await db.execute(select(Repository).where(Repository.full_name == repo_full_name))
    repo = result.scalar_one_or_none()
    if not repo or not repo.is_indexed:
        return {"skipped": True, "reason": "repo not indexed"}

    github_token = repo.owner.github_access_token if repo.owner else settings.github_token
    if not github_token:
        return {"skipped": True, "reason": "no token"}

    job = AutonomousEngineerJob(
        user_id=repo.owner_id,
        repo_id=repo.id,
        repo_full_name=repo.full_name,
        issue_number=issue_number,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(_run_agent, str(job.id), repo.full_name, str(repo.id), github_token, issue_number)
    return {"triggered": True, "job_id": str(job.id), "issue_number": issue_number}
