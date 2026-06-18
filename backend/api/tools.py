from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
from models.models import User
from database import get_db
from api.auth import get_current_user
from agents.system_design_agent import SystemDesignAgent
from rag.semantic_search import SemanticSearchService

router = APIRouter(prefix="/tools", tags=["tools"])


# ── System Design ─────────────────────────────────────────────────────────────
class SystemDesignRequest(BaseModel):
    repo_id: str
    query: str     # e.g. "Explain the order processing flow"


@router.post("/system-design")
async def generate_system_design(
    body: SystemDesignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate architecture diagrams (Mermaid + PlantUML) from natural language.
    Example: 'Explain the payment processing flow'
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
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Repository not found or not indexed")

    agent = SystemDesignAgent(db=db)
    return await agent.generate(query=body.query, repo_id=body.repo_id)


# ── Semantic Search ───────────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    repo_id: str
    query: str
    top_k: int = 10
    language_filter: Optional[str] = None
    chunk_type_filter: Optional[str] = None   # function | class | module | block


@router.post("/search")
async def semantic_search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid semantic code search (BM25 + Vector + Reranker).
    Examples:
      - 'Find JWT validation logic'
      - 'Find Kafka producers'
      - 'Find Redis cache usage'
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
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Repository not found or not indexed")

    search = SemanticSearchService(db=db)
    results = await search.search(
        query=body.query,
        repo_id=body.repo_id,
        top_k=body.top_k,
        language_filter=body.language_filter,
        chunk_type_filter=body.chunk_type_filter,
    )
    return {"query": body.query, "results": results, "count": len(results)}
