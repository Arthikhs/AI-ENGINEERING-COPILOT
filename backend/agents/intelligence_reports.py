"""
Engineering Intelligence Reports
Celery-scheduled daily/weekly/monthly report generation with Slack/email delivery.
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from models.models import (
    AgentRun, PRReview, ChangeIntelligenceReport,
    Repository, AutonomousEngineerJob
)

logger = logging.getLogger(__name__)


def get_sync_db():
    from database import SyncSessionLocal
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_daily_report(db: Session, date: datetime) -> dict[str, Any]:
    start = date.replace(hour=0, minute=0, second=0)
    end = date.replace(hour=23, minute=59, second=59)

    high_risk_prs = db.execute(
        select(func.count(PRReview.id)).where(
            PRReview.risk_level == "high",
            PRReview.created_at.between(start, end)
        )
    ).scalar() or 0

    change_reports = db.execute(
        select(ChangeIntelligenceReport).where(
            ChangeIntelligenceReport.created_at.between(start, end)
        )
    ).scalars().all()

    new_risks = []
    for r in change_reports:
        new_risks.extend(r.risks or [])

    agent_cost = db.execute(
        select(func.sum(AgentRun.estimated_cost_usd)).where(
            AgentRun.created_at.between(start, end)
        )
    ).scalar() or 0.0

    return {
        "type": "daily",
        "date": date.strftime("%Y-%m-%d"),
        "summary": {
            "high_risk_prs": high_risk_prs,
            "new_risks": len(new_risks),
            "ai_cost_usd": round(agent_cost, 4),
            "change_reports": len(change_reports),
        },
        "risks": new_risks[:20],
        "recommendations": _generate_recommendations(high_risk_prs, new_risks),
    }


def build_weekly_report(db: Session, week_start: datetime) -> dict[str, Any]:
    week_end = week_start + timedelta(days=7)

    total_runs = db.execute(
        select(func.count(AgentRun.id)).where(
            AgentRun.created_at.between(week_start, week_end)
        )
    ).scalar() or 0

    total_cost = db.execute(
        select(func.sum(AgentRun.estimated_cost_usd)).where(
            AgentRun.created_at.between(week_start, week_end)
        )
    ).scalar() or 0.0

    pr_reviews = db.execute(
        select(func.count(PRReview.id)).where(
            PRReview.created_at.between(week_start, week_end)
        )
    ).scalar() or 0

    auto_jobs = db.execute(
        select(func.count(AutonomousEngineerJob.id)).where(
            AutonomousEngineerJob.created_at.between(week_start, week_end)
        )
    ).scalar() or 0

    repos = db.execute(select(func.count(Repository.id))).scalar() or 0

    return {
        "type": "weekly",
        "period": f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}",
        "summary": {
            "ai_agent_runs": total_runs,
            "total_cost_usd": round(total_cost, 4),
            "pr_reviews_completed": pr_reviews,
            "autonomous_jobs": auto_jobs,
            "total_repositories": repos,
        },
        "cost_breakdown": _get_cost_breakdown(db, week_start, week_end),
        "productivity_insights": _get_productivity_insights(db, week_start, week_end),
    }


def build_monthly_report(db: Session, month_start: datetime) -> dict[str, Any]:
    month_end = month_start + timedelta(days=30)

    total_cost = db.execute(
        select(func.sum(AgentRun.estimated_cost_usd)).where(
            AgentRun.created_at.between(month_start, month_end)
        )
    ).scalar() or 0.0

    model_usage = db.execute(
        select(AgentRun.model, func.count(AgentRun.id), func.sum(AgentRun.estimated_cost_usd))
        .where(AgentRun.created_at.between(month_start, month_end))
        .group_by(AgentRun.model)
    ).all()

    return {
        "type": "monthly",
        "period": month_start.strftime("%B %Y"),
        "executive_summary": {
            "total_ai_cost_usd": round(total_cost, 4),
            "model_usage": [
                {"model": m[0], "runs": m[1], "cost": round(m[2] or 0, 4)}
                for m in model_usage
            ],
        },
        "platform_health": "stable",
        "recommendations": [
            "Consider upgrading to gpt-4o-mini for simple tasks to reduce costs.",
            "Enable automated test generation for repositories with low test coverage.",
        ],
    }


def _get_cost_breakdown(db, start, end):
    rows = db.execute(
        select(AgentRun.task_type, func.sum(AgentRun.estimated_cost_usd))
        .where(AgentRun.created_at.between(start, end))
        .group_by(AgentRun.task_type)
    ).all()
    return {r[0]: round(r[1] or 0, 4) for r in rows}


def _get_productivity_insights(db, start, end):
    avg_latency = db.execute(
        select(func.avg(AgentRun.latency_ms)).where(
            AgentRun.created_at.between(start, end)
        )
    ).scalar() or 0
    return {"avg_agent_latency_ms": round(avg_latency, 0)}


def _generate_recommendations(high_risk_prs: int, risks: list) -> list[str]:
    recs = []
    if high_risk_prs > 0:
        recs.append(f"Review {high_risk_prs} high-risk PRs before merging.")
    if len(risks) > 5:
        recs.append("High change activity detected — consider a stability freeze.")
    if not recs:
        recs.append("No critical issues today. Keep up the good work!")
    return recs


async def deliver_to_slack(report: dict, webhook_url: str):
    """Send report summary to Slack."""
    import httpx
    rtype = report.get("type", "report").title()
    summary = report.get("summary") or report.get("executive_summary", {})
    text = f"*{rtype} Engineering Report*\n```{str(summary)[:500]}```"
    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json={"text": text})
