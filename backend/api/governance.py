"""
Architecture Governance API
Endpoints:
  GET  /governance/{repo_id}              — Run full governance scan
  GET  /governance/{repo_id}/violations   — Get violations (filterable)
  GET  /governance/{repo_id}/report       — Get governance report summary
  GET  /governance/rules                  — List all built-in rules
  POST /governance/{repo_id}/fix-suggest  — AI fix suggestion for a violation
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from api.auth import get_current_user
from models.models import User
from agents.governance_engine import (
    run_governance_analysis, get_ai_fix_suggestion, BUILT_IN_RULES
)

router = APIRouter(prefix="/governance", tags=["governance"])
logger = logging.getLogger(__name__)


# ── Schemas ────────────────────────────────────────────────────────────────────

class FixSuggestionRequest(BaseModel):
    violation: dict


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/rules")
async def list_rules(current_user: User = Depends(get_current_user)):
    """List all built-in governance rules."""
    return {
        "rules": [
            {
                "id":          r["id"],
                "name":        r["name"],
                "rule_type":   r["rule_type"],
                "severity":    r["severity"],
                "description": r["description"],
                "suggestion":  r.get("suggestion", ""),
            }
            for r in BUILT_IN_RULES
        ],
        "total": len(BUILT_IN_RULES),
    }


@router.get("/{repo_id}")
async def scan_governance(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run full architecture governance analysis on a repository."""
    report = await run_governance_analysis(repo_id, db)
    return report


@router.get("/{repo_id}/violations")
async def get_violations(
    repo_id: str,
    severity: Optional[str] = None,
    rule_type: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get persisted governance violations, filterable by severity and rule type."""
    query = "SELECT * FROM governance_violations WHERE repo_id = :repo_id"
    params: dict = {"repo_id": repo_id}

    if severity:
        query += " AND severity = :severity"
        params["severity"] = severity
    if rule_type:
        query += " AND rule_type = :rule_type"
        params["rule_type"] = rule_type

    query += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = limit

    result = await db.execute(text(query), params)
    rows = result.fetchall()
    return {
        "violations": [dict(r._mapping) for r in rows],
        "total": len(rows),
    }


@router.get("/{repo_id}/report")
async def get_governance_report(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get governance summary report with trends."""
    result = await db.execute(
        text("""
            SELECT
                severity,
                rule_type,
                COUNT(*) as count
            FROM governance_violations
            WHERE repo_id = :repo_id
            GROUP BY severity, rule_type
            ORDER BY severity, rule_type
        """),
        {"repo_id": repo_id}
    )
    rows = result.fetchall()

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_type: dict = {}
    for row in rows:
        d = dict(row._mapping)
        sev = d["severity"]
        rtype = d["rule_type"]
        count = d["count"]
        severity_counts[sev] = severity_counts.get(sev, 0) + count
        by_type[rtype] = by_type.get(rtype, 0) + count

    total = sum(severity_counts.values())
    deductions = (
        severity_counts.get("critical", 0) * 20 +
        severity_counts.get("high", 0)     * 10 +
        severity_counts.get("medium", 0)   * 5  +
        severity_counts.get("low", 0)      * 1
    )
    score = max(0, 100 - deductions)

    return {
        "repo_id":          repo_id,
        "governance_score": score,
        "grade":            _grade(score),
        "total_violations": total,
        "severity_counts":  severity_counts,
        "by_type":          by_type,
        "recommendation":   _recommend(severity_counts),
    }


@router.post("/{repo_id}/fix-suggest")
async def ai_fix_suggestion(
    repo_id: str,
    req: FixSuggestionRequest,
    current_user: User = Depends(get_current_user),
):
    """Get an AI-powered fix suggestion for a specific violation."""
    suggestion = await get_ai_fix_suggestion(req.violation)
    return {"suggestion": suggestion}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _grade(score: int) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def _recommend(counts: dict) -> str:
    if counts.get("critical", 0) > 0:
        return f"🔴 Fix {counts['critical']} critical violation(s) immediately — these are security or runtime risks."
    if counts.get("high", 0) > 3:
        return f"🟠 Address {counts['high']} high severity violations to improve architectural stability."
    if counts.get("medium", 0) > 5:
        return "🟡 Several medium-severity issues found. Schedule a refactoring sprint."
    return "✅ Architecture is in good shape. Continue monitoring."
