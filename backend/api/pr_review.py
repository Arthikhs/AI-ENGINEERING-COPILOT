from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from models.models import User, Repository, PRReview
from database import get_db
from api.auth import get_current_user
from agents.pr_review_agent import PRReviewAgent

router = APIRouter(prefix="/review", tags=["pr-review"])


class PRReviewRequest(BaseModel):
    repo_id: str
    pr_number: int


@router.post("/pr")
async def review_pull_request(
    body: PRReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze a pull request for bugs, security issues, and code quality."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == body.repo_id, Repository.owner_id == current_user.id
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    agent = PRReviewAgent(github_token=current_user.github_access_token, db=db)
    review_result = await agent.review(
        repo_full_name=repo.full_name,
        pr_number=body.pr_number,
        repo_id=str(repo.id),
    )
    return review_result


@router.get("/pr/{repo_id}")
async def list_pr_reviews(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PRReview)
        .where(PRReview.repo_id == repo_id)
        .order_by(PRReview.created_at.desc())
        .limit(20)
    )
    reviews = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "pr_number": r.pr_number,
            "pr_title": r.pr_title,
            "risk_level": r.risk_level,
            "findings_count": len(r.findings),
            "created_at": r.created_at,
        }
        for r in reviews
    ]
