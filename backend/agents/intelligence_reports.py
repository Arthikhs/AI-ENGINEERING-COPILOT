"""
Engineering Intelligence Reports — Enterprise Grade
Generates Daily / Weekly / Monthly reports with:
  - Rich structured content
  - DB persistence
  - Slack delivery
  - Teams delivery
  - Celery scheduled tasks
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ── Daily Report ───────────────────────────────────────────────────────────────

def build_daily_report(db: Session, date: datetime) -> dict[str, Any]:
    start = date.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    end   = date.replace(hour=23, minute=59, second=59, microsecond=999999)

    from models.models import PRReview, ChangeIntelligenceReport, AgentRun, AutonomousEngineerJob

    high_risk_prs = db.execute(
        select(func.count(PRReview.id)).where(
            PRReview.risk_level == "high",
            PRReview.created_at.between(start, end)
        )
    ).scalar() or 0

    medium_risk_prs = db.execute(
        select(func.count(PRReview.id)).where(
            PRReview.risk_level == "medium",
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
    high_risks = [r for r in new_risks if r.get("severity") == "high"]

    ai_cost = db.execute(
        select(func.sum(AgentRun.estimated_cost_usd)).where(
            AgentRun.created_at.between(start, end)
        )
    ).scalar() or 0.0

    ai_runs = db.execute(
        select(func.count(AgentRun.id)).where(
            AgentRun.created_at.between(start, end)
        )
    ).scalar() or 0

    auto_jobs = db.execute(
        select(func.count(AutonomousEngineerJob.id)).where(
            AutonomousEngineerJob.created_at.between(start, end)
        )
    ).scalar() or 0

    # Failed autonomous jobs
    failed_jobs = db.execute(
        select(func.count(AutonomousEngineerJob.id)).where(
            AutonomousEngineerJob.status == "failed",
            AutonomousEngineerJob.created_at.between(start, end)
        )
    ).scalar() or 0

    return {
        "type":   "daily",
        "date":   date.strftime("%Y-%m-%d"),
        "title":  f"Daily Engineering Report — {date.strftime('%B %d, %Y')}",
        "summary": {
            "high_risk_prs":     high_risk_prs,
            "medium_risk_prs":   medium_risk_prs,
            "new_high_risks":    len(high_risks),
            "change_reports":    len(change_reports),
            "ai_agent_runs":     ai_runs,
            "ai_cost_usd":       round(ai_cost, 4),
            "autonomous_jobs":   auto_jobs,
            "failed_jobs":       failed_jobs,
        },
        "high_risks":      high_risks[:10],
        "recommendations": _daily_recommendations(high_risk_prs, high_risks, failed_jobs),
        "action_items":    _daily_action_items(high_risk_prs, high_risks, failed_jobs),
    }


# ── Weekly Report ──────────────────────────────────────────────────────────────

def build_weekly_report(db: Session, week_start: datetime) -> dict[str, Any]:
    week_end = week_start + timedelta(days=7)

    from models.models import PRReview, AgentRun, AutonomousEngineerJob, Repository

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

    avg_latency = db.execute(
        select(func.avg(AgentRun.latency_ms)).where(
            AgentRun.created_at.between(week_start, week_end)
        )
    ).scalar() or 0

    pr_reviews = db.execute(
        select(func.count(PRReview.id)).where(
            PRReview.created_at.between(week_start, week_end)
        )
    ).scalar() or 0

    high_risk_prs = db.execute(
        select(func.count(PRReview.id)).where(
            PRReview.risk_level == "high",
            PRReview.created_at.between(week_start, week_end)
        )
    ).scalar() or 0

    auto_jobs_total = db.execute(
        select(func.count(AutonomousEngineerJob.id)).where(
            AutonomousEngineerJob.created_at.between(week_start, week_end)
        )
    ).scalar() or 0

    auto_jobs_completed = db.execute(
        select(func.count(AutonomousEngineerJob.id)).where(
            AutonomousEngineerJob.status == "completed",
            AutonomousEngineerJob.created_at.between(week_start, week_end)
        )
    ).scalar() or 0

    total_repos = db.execute(select(func.count(Repository.id))).scalar() or 0
    indexed_repos = db.execute(
        select(func.count(Repository.id)).where(Repository.is_indexed == True)
    ).scalar() or 0

    cost_by_task = _get_cost_breakdown(db, week_start, week_end)
    model_usage  = _get_model_usage(db, week_start, week_end)

    success_rate = round((auto_jobs_completed / max(auto_jobs_total, 1)) * 100, 1)

    return {
        "type":   "weekly",
        "title":  f"Weekly Engineering Report — {week_start.strftime('%b %d')} to {week_end.strftime('%b %d, %Y')}",
        "period": f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}",
        "summary": {
            "ai_agent_runs":           total_runs,
            "total_cost_usd":          round(total_cost, 4),
            "avg_agent_latency_ms":    round(avg_latency),
            "pr_reviews_completed":    pr_reviews,
            "high_risk_prs":           high_risk_prs,
            "autonomous_jobs":         auto_jobs_total,
            "autonomous_success_rate": f"{success_rate}%",
            "total_repositories":      total_repos,
            "indexed_repositories":    indexed_repos,
        },
        "cost_breakdown":       cost_by_task,
        "model_usage":          model_usage,
        "productivity_insights": {
            "avg_agent_latency_ms": round(avg_latency),
            "cost_per_run_usd":     round(total_cost / max(total_runs, 1), 6),
            "autonomous_success_rate": f"{success_rate}%",
        },
        "recommendations": _weekly_recommendations(high_risk_prs, total_cost, success_rate),
    }


# ── Monthly Report ─────────────────────────────────────────────────────────────

def build_monthly_report(db: Session, month_start: datetime) -> dict[str, Any]:
    month_end = month_start + timedelta(days=30)

    from models.models import AgentRun, PRReview, Repository, AutonomousEngineerJob

    total_cost = db.execute(
        select(func.sum(AgentRun.estimated_cost_usd)).where(
            AgentRun.created_at.between(month_start, month_end)
        )
    ).scalar() or 0.0

    total_runs = db.execute(
        select(func.count(AgentRun.id)).where(
            AgentRun.created_at.between(month_start, month_end)
        )
    ).scalar() or 0

    total_prs = db.execute(
        select(func.count(PRReview.id)).where(
            PRReview.created_at.between(month_start, month_end)
        )
    ).scalar() or 0

    high_risk_prs = db.execute(
        select(func.count(PRReview.id)).where(
            PRReview.risk_level == "high",
            PRReview.created_at.between(month_start, month_end)
        )
    ).scalar() or 0

    auto_jobs = db.execute(
        select(func.count(AutonomousEngineerJob.id)).where(
            AutonomousEngineerJob.created_at.between(month_start, month_end)
        )
    ).scalar() or 0

    total_repos  = db.execute(select(func.count(Repository.id))).scalar() or 0
    model_usage  = _get_model_usage(db, month_start, month_end)
    cost_by_task = _get_cost_breakdown(db, month_start, month_end)

    # Daily cost trend (last 30 days)
    daily_costs = []
    for i in range(30):
        day_start = month_start + timedelta(days=i)
        day_end   = day_start + timedelta(days=1)
        cost = db.execute(
            select(func.sum(AgentRun.estimated_cost_usd)).where(
                AgentRun.created_at.between(day_start, day_end)
            )
        ).scalar() or 0.0
        daily_costs.append({"date": day_start.strftime("%Y-%m-%d"), "cost": round(cost, 4)})

    return {
        "type":   "monthly",
        "title":  f"Monthly Executive Report — {month_start.strftime('%B %Y')}",
        "period": month_start.strftime("%B %Y"),
        "executive_summary": {
            "total_ai_cost_usd":   round(total_cost, 4),
            "total_agent_runs":    total_runs,
            "pr_reviews":          total_prs,
            "high_risk_prs":       high_risk_prs,
            "autonomous_jobs":     auto_jobs,
            "total_repositories":  total_repos,
            "avg_daily_cost_usd":  round(total_cost / 30, 4),
        },
        "model_usage":    model_usage,
        "cost_breakdown": cost_by_task,
        "daily_cost_trend": daily_costs,
        "platform_health": _assess_platform_health(high_risk_prs, total_cost, total_runs),
        "recommendations": _monthly_recommendations(high_risk_prs, total_cost, model_usage),
    }


# ── Delivery ───────────────────────────────────────────────────────────────────

async def deliver_to_slack(report: dict, webhook_url: str) -> bool:
    """Send formatted report to Slack webhook."""
    import httpx
    try:
        rtype   = report.get("type", "").title()
        title   = report.get("title", f"{rtype} Report")
        summary = report.get("summary") or report.get("executive_summary", {})

        # Build Slack blocks
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"📊 {title}"}
            },
            {"type": "divider"},
        ]

        # Summary fields
        fields = []
        for k, v in list(summary.items())[:8]:
            fields.append({
                "type": "mrkdwn",
                "text": f"*{k.replace('_', ' ').title()}*\n{v}"
            })
        if fields:
            blocks.append({"type": "section", "fields": fields[:8]})

        # Recommendations
        recs = report.get("recommendations", [])
        if recs:
            rec_text = "\n".join(f"• {r}" for r in recs[:3])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*💡 Recommendations*\n{rec_text}"}
            })

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"blocks": blocks, "text": title})
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Slack delivery failed: {e}")
        return False


async def deliver_to_teams(report: dict, webhook_url: str) -> bool:
    """Send report to Microsoft Teams webhook."""
    import httpx
    try:
        title   = report.get("title", "Engineering Report")
        summary = report.get("summary") or report.get("executive_summary", {})
        facts   = [{"name": k.replace("_", " ").title(), "value": str(v)} for k, v in list(summary.items())[:6]]

        payload = {
            "@type":      "MessageCard",
            "@context":   "https://schema.org/extensions",
            "themeColor": "0078D4",
            "summary":    title,
            "sections": [{
                "activityTitle": f"📊 {title}",
                "facts":         facts,
                "text":          "\n".join(f"• {r}" for r in report.get("recommendations", [])[:3]),
            }]
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json=payload)
            return resp.status_code in (200, 202)
    except Exception as e:
        logger.error(f"Teams delivery failed: {e}")
        return False


async def persist_report(report: dict, db_session) -> str:
    """Save report to engineering_reports table."""
    report_id = str(uuid.uuid4())
    try:
        import json
        await db_session.execute(
            text("""
                INSERT INTO engineering_reports
                  (id, report_type, content, created_at)
                VALUES (:id, :rtype, :content::jsonb, now())
            """),
            {
                "id":      report_id,
                "rtype":   report.get("type", "unknown"),
                "content": json.dumps(report),
            }
        )
        await db_session.commit()
    except Exception as e:
        logger.warning(f"Failed to persist report: {e}")
    return report_id


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_cost_breakdown(db, start, end) -> dict:
    from models.models import AgentRun
    rows = db.execute(
        select(AgentRun.task_type, func.sum(AgentRun.estimated_cost_usd))
        .where(AgentRun.created_at.between(start, end))
        .group_by(AgentRun.task_type)
        .order_by(func.sum(AgentRun.estimated_cost_usd).desc())
    ).all()
    return {r[0]: round(r[1] or 0, 4) for r in rows}


def _get_model_usage(db, start, end) -> list:
    from models.models import AgentRun
    rows = db.execute(
        select(
            AgentRun.model,
            func.count(AgentRun.id),
            func.sum(AgentRun.estimated_cost_usd),
            func.avg(AgentRun.latency_ms),
        )
        .where(AgentRun.created_at.between(start, end))
        .group_by(AgentRun.model)
        .order_by(func.count(AgentRun.id).desc())
    ).all()
    return [
        {
            "model":           r[0],
            "runs":            r[1],
            "total_cost_usd":  round(r[2] or 0, 4),
            "avg_latency_ms":  round(r[3] or 0),
        }
        for r in rows
    ]


def _daily_recommendations(high_risk: int, risks: list, failed_jobs: int) -> list[str]:
    recs = []
    if high_risk > 0:
        recs.append(f"🔴 Review {high_risk} high-risk PR(s) before merging to main.")
    if len(risks) > 3:
        recs.append(f"⚠️ {len(risks)} high-risk changes detected — consider a stability freeze.")
    if failed_jobs > 0:
        recs.append(f"🤖 {failed_jobs} autonomous engineer job(s) failed — check GitHub tokens.")
    if not recs:
        recs.append("✅ No critical issues today. Engineering health is good.")
    return recs


def _daily_action_items(high_risk: int, risks: list, failed_jobs: int) -> list[dict]:
    items = []
    if high_risk > 0:
        items.append({"priority": "high",   "action": f"Review {high_risk} high-risk PR(s)", "owner": "Team Lead"})
    if failed_jobs > 0:
        items.append({"priority": "medium", "action": "Fix failed autonomous engineer jobs",   "owner": "DevOps"})
    if len(risks) > 5:
        items.append({"priority": "medium", "action": "Review change intelligence report",     "owner": "Architect"})
    return items


def _weekly_recommendations(high_risk: int, cost: float, success_rate: float) -> list[str]:
    recs = []
    if high_risk > 5:
        recs.append(f"Too many high-risk PRs ({high_risk}) — implement stricter PR review gates.")
    if cost > 10:
        recs.append(f"AI cost ${cost:.2f} this week — route simple tasks to cheaper models.")
    if success_rate < 70:
        recs.append(f"Autonomous engineer success rate is {success_rate}% — improve issue descriptions.")
    if not recs:
        recs.append("Engineering metrics look healthy this week. Keep up the good work!")
    return recs


def _monthly_recommendations(high_risk: int, cost: float, model_usage: list) -> list[str]:
    recs = [
        "Consider enabling automated test generation for all new PRs.",
        "Run architecture governance scan monthly to track technical debt trends.",
    ]
    if cost > 50:
        recs.insert(0, f"Monthly AI cost ${cost:.2f} — consider caching frequent queries.")
    if high_risk > 20:
        recs.insert(0, f"{high_risk} high-risk PRs this month — schedule a security review sprint.")
    return recs[:4]


def _assess_platform_health(high_risk: int, cost: float, runs: int) -> str:
    if high_risk > 10 or cost > 100:
        return "needs_attention"
    if high_risk > 3 or cost > 20:
        return "warning"
    return "healthy"
