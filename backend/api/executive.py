"""
Executive Engineering Dashboard API
Provides aggregated metrics for engineering managers:
- Technical debt
- Security risks
- Repository health
- PR trends
- AI usage stats
- Cost trends
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from database import get_db
from api.auth import get_current_user
from models.models import (
    User, Repository, PRReview, AgentRun,
    BenchmarkRun, HITLApproval
)

router = APIRouter(prefix="/executive", tags=["executive"])


@router.get("/dashboard")
async def executive_dashboard(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full executive dashboard — all metrics in one call."""
    since = datetime.utcnow() - timedelta(days=days)

    # ── Repository health ──────────────────────────────────────────────────────
    repo_result = await db.execute(select(Repository))
    repos = repo_result.scalars().all()
    total_repos = len(repos)
    indexed_repos = sum(1 for r in repos if r.is_indexed)
    total_files = sum(r.total_files or 0 for r in repos)
    total_chunks = sum(r.total_chunks or 0 for r in repos)

    # ── PR trends ──────────────────────────────────────────────────────────────
    pr_result = await db.execute(
        select(PRReview).where(PRReview.created_at >= since)
    )
    pr_reviews = pr_result.scalars().all()
    pr_by_risk = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for pr in pr_reviews:
        level = (pr.risk_level or "low").lower()
        pr_by_risk[level] = pr_by_risk.get(level, 0) + 1

    # ── Security risks ─────────────────────────────────────────────────────────
    hitl_result = await db.execute(
        select(HITLApproval).where(HITLApproval.created_at >= since)
    )
    hitl_approvals = hitl_result.scalars().all()
    pending_approvals = sum(1 for a in hitl_approvals if a.status == "pending")
    critical_security = sum(
        1 for a in hitl_approvals
        if (a.overall_risk or "").lower() in ("critical", "high")
    )

    # ── AI Usage (AgentRun) ────────────────────────────────────────────────────
    agent_result = await db.execute(
        select(AgentRun).where(AgentRun.created_at >= since)
    )
    agent_runs = agent_result.scalars().all()
    total_runs = len(agent_runs)
    by_task: dict = {}
    for run in agent_runs:
        by_task[run.task_type] = by_task.get(run.task_type, 0) + 1

    # ── Cost trends ────────────────────────────────────────────────────────────
    total_cost = sum(float(r.estimated_cost_usd or 0) for r in agent_runs)

    # Daily cost breakdown
    daily_costs: dict = {}
    for run in agent_runs:
        day = run.created_at.strftime("%Y-%m-%d")
        daily_costs[day] = daily_costs.get(day, 0.0) + float(run.estimated_cost_usd or 0)
    cost_trend = [{"date": d, "cost_usd": round(c, 4)} for d, c in sorted(daily_costs.items())]

    # ── Model usage distribution ───────────────────────────────────────────────
    model_usage: dict = {}
    for run in agent_runs:
        model_usage[run.model] = model_usage.get(run.model, 0) + 1

    # ── Technical debt proxy (from refactor agent runs) ────────────────────────
    refactor_runs = [r for r in agent_runs if r.task_type == "refactoring"]

    # ── Avg latency ────────────────────────────────────────────────────────────
    avg_latency = (
        sum(r.latency_ms or 0 for r in agent_runs) / total_runs
        if total_runs > 0 else 0
    )

    return {
        "period_days": days,
        "repository_health": {
            "total": total_repos,
            "indexed": indexed_repos,
            "total_files": total_files,
            "total_chunks": total_chunks,
        },
        "security_risks": {
            "total_reviews": len(hitl_approvals),
            "critical_or_high": critical_security,
            "pending_approvals": pending_approvals,
        },
        "pr_trends": {
            "total_reviews": len(pr_reviews),
            "by_risk_level": pr_by_risk,
        },
        "ai_usage": {
            "total_runs": total_runs,
            "by_task_type": by_task,
            "model_distribution": model_usage,
            "avg_latency_ms": round(avg_latency),
            "refactor_runs": len(refactor_runs),
        },
        "cost_summary": {
            "total_cost_usd": round(total_cost, 4),
            "avg_cost_per_run": round(total_cost / total_runs, 6) if total_runs else 0,
            "trend": cost_trend,
        },
    }
