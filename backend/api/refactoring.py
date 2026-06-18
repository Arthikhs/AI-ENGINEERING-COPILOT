from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from models.models import User
from database import get_db
from api.auth import get_current_user
from agents.refactoring_agent import RefactoringAgent

router = APIRouter(prefix="/refactor", tags=["refactoring"])


class RefactorRequest(BaseModel):
    repo_id: str
    target_file: Optional[str] = None   # optional: focus on specific file


@router.post("/analyze")
async def analyze_refactoring(
    body: RefactorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Detect code smells and generate refactoring suggestions.
    Finds: Large Classes, Long Methods, Duplicate Code, Dead Code, Magic Numbers.
    Returns before/after examples for each issue.
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

    agent = RefactoringAgent(db=db)
    return await agent.analyze(repo_id=body.repo_id, target_file=body.target_file)
