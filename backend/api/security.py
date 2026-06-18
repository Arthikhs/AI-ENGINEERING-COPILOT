from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from models.models import User
from database import get_db
from api.auth import get_current_user
from agents.security_agent import SecurityReviewAgent

router = APIRouter(prefix="/security", tags=["security"])


class SecurityReviewRequest(BaseModel):
    repo_id: str


@router.post("/review")
async def security_review(
    body: SecurityReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Full security review of a repository.
    Detects: SQL Injection, XSS, SSRF, Hardcoded Secrets,
             Auth Flaws, Command Injection, Path Traversal.
    """
    from sqlalchemy import select
    from models.models import Repository
    result = await db.execute(
        select(Repository).where(
            Repository.id == body.repo_id,
            Repository.owner_id == current_user.id,
            Repository.is_indexed == True,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found or not indexed")

    agent = SecurityReviewAgent(db=db)
    return await agent.review(repo_id=body.repo_id)
