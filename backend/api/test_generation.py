from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from models.models import User
from database import get_db
from api.auth import get_current_user
from agents.test_generation_agent import TestGenerationAgent

router = APIRouter(prefix="/tests", tags=["test-generation"])


class TestGenRequest(BaseModel):
    repo_id: str
    target: str             # function/class name or description
    language: Optional[str] = None


@router.post("/generate")
async def generate_tests(
    body: TestGenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate unit tests for any function or class in the codebase.
    Supports: Python (pytest), Java (JUnit+Mockito), JS/TS (Jest).
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

    agent = TestGenerationAgent(db=db)
    return await agent.generate(
        repo_id=body.repo_id,
        target=body.target,
        language=body.language,
    )
