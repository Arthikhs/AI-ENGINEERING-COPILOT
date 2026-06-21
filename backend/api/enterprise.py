"""
Enterprise Features API
Covers: Sandbox, Governance, Health Score, Reports, Feature Flags, Evaluation
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from api.auth import get_current_user
from models.models import User
from agents.governance_engine import run_governance_analysis
from agents.health_score import compute_health_score
from agents.intelligence_reports import build_daily_report, build_weekly_report, build_monthly_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enterprise", tags=["enterprise"])


# ─── Sandbox ──────────────────────────────────────────────────────────────────

class SandboxRequest(BaseModel):
    code: str
    language: str = "python"
    test_input: Optional[str] = None


@router.post("/sandbox/execute")
async def execute_sandbox(req: SandboxRequest, current_user: User = Depends(get_current_user)):
    """Execute code in isolated Docker sandbox."""
    from agents.sandbox import execute_code
    result = await execute_code(req.code, req.language, req.test_input)
    return result.to_dict()


@router.post("/sandbox/test")
async def execute_sandbox_tests(
    req: SandboxRequest,
    source_code: str = "",
    current_user: User = Depends(get_current_user)
):
    """Execute tests against source code in sandbox."""
    from agents.sandbox import execute_tests
    result = await execute_tests(req.code, source_code, req.language)
    return result.to_dict()


# ─── Architecture Governance ──────────────────────────────────────────────────

@router.get("/governance/{repo_id}")
async def get_governance_report(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Run architecture governance analysis on a repository."""
    report = await run_governance_analysis(repo_id, db)
    return report


@router.get("/governance/{repo_id}/violations")
async def get_violations(
    repo_id: str,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get governance violations filtered by severity."""
    report = await run_governance_analysis(repo_id, db)
    violations = report["violations"]
    if severity:
        violations = [v for v in violations if v["severity"] == severity]
    return {"violations": violations, "total": len(violations)}


# ─── Repository Health Score ──────────────────────────────────────────────────

@router.get("/health-score/{repo_id}")
async def get_health_score(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compute and return repository health score."""
    score = await compute_health_score(repo_id, db)
    return score


@router.get("/health-score/{repo_id}/history")
async def get_health_score_history(
    repo_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get historical health scores for trend analysis."""
    from models.models import Repository
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT overall_score, security_score, architecture_score, test_coverage_score, created_at FROM repo_health_scores WHERE repo_id = :repo_id ORDER BY created_at DESC LIMIT :limit"),
        {"repo_id": repo_id, "limit": limit}
    )
    rows = result.fetchall()
    return {"history": [dict(r._mapping) for r in rows]}


# ─── Engineering Reports ──────────────────────────────────────────────────────

@router.get("/reports/daily")
async def get_daily_report(
    date: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Generate daily engineering intelligence report."""
    import asyncio
    from database import SyncSessionLocal
    target_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.utcnow()

    def _build():
        sync_db = SyncSessionLocal()
        try:
            return build_daily_report(sync_db, target_date)
        finally:
            sync_db.close()

    return await asyncio.get_event_loop().run_in_executor(None, _build)


@router.get("/reports/weekly")
async def get_weekly_report(
    current_user: User = Depends(get_current_user)
):
    """Generate weekly engineering intelligence report."""
    import asyncio
    from database import SyncSessionLocal
    week_start = datetime.utcnow() - timedelta(days=7)

    def _build():
        sync_db = SyncSessionLocal()
        try:
            return build_weekly_report(sync_db, week_start)
        finally:
            sync_db.close()

    return await asyncio.get_event_loop().run_in_executor(None, _build)


@router.get("/reports/monthly")
async def get_monthly_report(
    current_user: User = Depends(get_current_user)
):
    """Generate monthly executive engineering report."""
    import asyncio
    from database import SyncSessionLocal
    month_start = datetime.utcnow().replace(day=1)

    def _build():
        sync_db = SyncSessionLocal()
        try:
            return build_monthly_report(sync_db, month_start)
        finally:
            sync_db.close()

    return await asyncio.get_event_loop().run_in_executor(None, _build)


# ─── Feature Flags ────────────────────────────────────────────────────────────

class FeatureFlagUpdate(BaseModel):
    is_enabled: bool
    rollout_percentage: int = 100


@router.get("/feature-flags")
async def list_feature_flags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all feature flags."""
    from sqlalchemy import text
    result = await db.execute(text("SELECT * FROM feature_flags ORDER BY name"))
    rows = result.fetchall()
    return {"flags": [dict(r._mapping) for r in rows]}


@router.post("/feature-flags/{flag_name}")
async def upsert_feature_flag(
    flag_name: str,
    update: FeatureFlagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update a feature flag."""
    from sqlalchemy import text
    await db.execute(
        text("""
            INSERT INTO feature_flags (id, name, is_enabled, rollout_percentage, updated_at)
            VALUES (:id, :name, :enabled, :pct, now())
            ON CONFLICT (name) DO UPDATE SET is_enabled = :enabled, rollout_percentage = :pct, updated_at = now()
        """),
        {"id": str(uuid.uuid4()), "name": flag_name, "enabled": update.is_enabled, "pct": update.rollout_percentage}
    )
    await db.commit()
    return {"flag": flag_name, "is_enabled": update.is_enabled}


# ─── LLM Evaluation ──────────────────────────────────────────────────────────

class EvalRequest(BaseModel):
    model: str
    task_type: str
    question: str
    answer: str
    contexts: list[str] = []


@router.post("/eval/run")
async def run_evaluation(
    req: EvalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    # Simple hallucination check: verify answer is grounded in contexts
    hallucination_score = 0.0
    if req.contexts:
        combined_context = " ".join(req.contexts).lower()
        answer_words = set(req.answer.lower().split())
        context_words = set(combined_context.split())
        overlap = len(answer_words & context_words) / max(len(answer_words), 1)
        hallucination_score = round(1.0 - min(overlap * 2, 1.0), 3)

    # Store evaluation
    eval_id = str(uuid.uuid4())
    from sqlalchemy import text
    await db.execute(
        text("""
            INSERT INTO llm_evaluations (id, model, task_type, question, answer, hallucination_score, created_at)
            VALUES (:id, :model, :task_type, :question, :answer, :hall, now())
        """),
        {
            "id": eval_id, "model": req.model, "task_type": req.task_type,
            "question": req.question, "answer": req.answer[:2000],
            "hall": hallucination_score,
        }
    )
    await db.commit()

    return {
        "eval_id": eval_id,
        "model": req.model,
        "hallucination_score": hallucination_score,
        "grounding_quality": "low" if hallucination_score > 0.7 else "medium" if hallucination_score > 0.3 else "high",
    }


@router.get("/eval/stats")
async def get_eval_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get evaluation statistics grouped by model."""
    from sqlalchemy import text
    result = await db.execute(text("""
        SELECT model, task_type,
               COUNT(*) as total_runs,
               AVG(hallucination_score) as avg_hallucination,
               AVG(latency_ms) as avg_latency_ms,
               SUM(cost_usd) as total_cost
        FROM llm_evaluations
        GROUP BY model, task_type
        ORDER BY model
    """))
    rows = result.fetchall()
    return {"stats": [dict(r._mapping) for r in rows]}
