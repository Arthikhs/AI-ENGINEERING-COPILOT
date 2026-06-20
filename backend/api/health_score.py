"""
Repository Health Score API
Endpoints:
  GET  /health-score/{repo_id}          — Compute & return health score
  GET  /health-score/{repo_id}/history  — Get historical scores for trend
  GET  /health-score/{repo_id}/compare  — Compare two time periods
  GET  /health-score/all                — Health scores for all repos
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from database import get_db
from api.auth import get_current_user
from models.models import User, Repository
from agents.health_score import compute_health_score, get_health_score_history

router = APIRouter(prefix="/health-score", tags=["health-score"])
logger = logging.getLogger(__name__)


@router.get("/all")
async def get_all_health_scores(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get latest health score for all repositories owned by user."""
    repos_result = await db.execute(
        select(Repository).where(Repository.owner_id == current_user.id, Repository.is_indexed == True)
    )
    repos = repos_result.scalars().all()

    scores = []
    for repo in repos:
        result = await db.execute(
            text("""
                SELECT overall_score, security_score, architecture_score,
                       test_coverage_score, created_at
                FROM repo_health_scores
                WHERE repo_id = :repo_id
                ORDER BY created_at DESC LIMIT 1
            """),
            {"repo_id": str(repo.id)}
        )
        row = result.fetchone()
        scores.append({
            "repo_id":       str(repo.id),
            "repo_name":     repo.full_name,
            "overall_score": float(row[0]) if row else None,
            "last_computed": row[4].isoformat() if row and row[4] else None,
        })

    return {"repos": sorted(scores, key=lambda x: x["overall_score"] or 0, reverse=True)}


@router.get("/{repo_id}")
async def get_health_score(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute and return full health score for a repository."""
    return await compute_health_score(repo_id, db)


@router.get("/{repo_id}/history")
async def get_score_history(
    repo_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get historical health scores for trend analysis."""
    history = await get_health_score_history(repo_id, db, limit)
    return {"history": history, "total": len(history)}


@router.get("/{repo_id}/compare")
async def compare_scores(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare latest score vs previous score."""
    history = await get_health_score_history(repo_id, db, limit=2)
    if len(history) < 2:
        return {"message": "Not enough history for comparison", "history": history}

    latest = history[0]
    previous = history[1]

    dimensions = ["security_score", "architecture_score", "test_coverage_score",
                  "code_quality_score", "dependency_score", "documentation_score"]

    comparison = {}
    for dim in dimensions:
        curr = float(latest.get(dim) or 0)
        prev = float(previous.get(dim) or 0)
        comparison[dim] = {
            "current":  round(curr, 1),
            "previous": round(prev, 1),
            "delta":    round(curr - prev, 1),
            "trend":    "up" if curr > prev else "down" if curr < prev else "stable",
        }

    return {
        "latest":     latest,
        "previous":   previous,
        "comparison": comparison,
        "overall_delta": round(
            float(latest.get("overall_score") or 0) - float(previous.get("overall_score") or 0), 1
        ),
    }
