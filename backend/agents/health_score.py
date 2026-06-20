"""
Repository Health Score System — Enterprise Grade
Scores across 6 dimensions (0-100 each):
  - Security Score      (25%) — PR risk levels + governance security violations
  - Architecture Score  (20%) — Circular deps + governance violations
  - Test Coverage Score (20%) — Test file ratio + test function presence
  - Code Quality Score  (15%) — Function length + complexity + docstrings
  - Dependency Score    (10%) — Change risk + outdated deps indicators
  - Documentation Score (10%) — Docstring coverage + README presence

Features:
  - Weighted overall score (0-100)
  - Letter grade (A-F)
  - Per-dimension recommendations
  - DB persistence for trend tracking
  - Historical comparison (delta from last run)
"""
import re
import uuid
import logging
from datetime import datetime
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from models.models import (
    CodeChunk, CodeFile, PRReview, ArchitectureReport,
    ChangeIntelligenceReport, Repository
)

logger = logging.getLogger(__name__)

WEIGHTS = {
    "security":       0.25,
    "architecture":   0.20,
    "test_coverage":  0.20,
    "code_quality":   0.15,
    "dependency":     0.10,
    "documentation":  0.10,
}


# ── Individual Dimension Scorers ───────────────────────────────────────────────

async def compute_security_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on PR risk levels and governance security violations."""
    reviews_result = await db.execute(
        select(PRReview)
        .where(PRReview.repo_id == repo_id)
        .order_by(PRReview.created_at.desc())
        .limit(20)
    )
    reviews = reviews_result.scalars().all()

    if not reviews:
        return 70.0, {"note": "No PR reviews yet — baseline score applied", "recommendation": "Run PR reviews to get accurate security scoring."}

    high_risk   = sum(1 for r in reviews if r.risk_level == "high")
    medium_risk = sum(1 for r in reviews if r.risk_level == "medium")
    low_risk    = sum(1 for r in reviews if r.risk_level == "low")

    # Check governance security violations
    gov_result = await db.execute(
        text("SELECT COUNT(*) FROM governance_violations WHERE repo_id = :repo_id AND rule_type = 'security_antipattern'"),
        {"repo_id": repo_id}
    )
    gov_violations = gov_result.scalar() or 0

    score = max(0, 100 - (high_risk * 15) - (medium_risk * 7) - (gov_violations * 10))

    recommendation = None
    if high_risk > 0:
        recommendation = f"Fix {high_risk} high-risk PR(s) immediately."
    elif gov_violations > 0:
        recommendation = f"Remove {gov_violations} hardcoded secret(s) from codebase."
    elif medium_risk > 3:
        recommendation = "Review medium-risk PRs before merging to main."

    return float(score), {
        "high_risk_prs":      high_risk,
        "medium_risk_prs":    medium_risk,
        "low_risk_prs":       low_risk,
        "security_violations": gov_violations,
        "recommendation":     recommendation,
    }


async def compute_architecture_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on architecture report + governance architecture violations."""
    arch_result = await db.execute(
        select(ArchitectureReport)
        .where(ArchitectureReport.repo_id == repo_id)
        .order_by(ArchitectureReport.created_at.desc())
        .limit(1)
    )
    report = arch_result.scalar_one_or_none()
    circular = len(report.circular_dependencies or []) if report else 0

    gov_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM governance_violations
            WHERE repo_id = :repo_id
            AND rule_type IN ('layer_violation', 'circular_dependency', 'tight_coupling')
        """),
        {"repo_id": repo_id}
    )
    arch_violations = gov_result.scalar() or 0

    score = max(0, 100 - (circular * 10) - (arch_violations * 5))

    recommendation = None
    if circular > 0:
        recommendation = f"Resolve {circular} circular dependency/dependencies."
    elif arch_violations > 3:
        recommendation = "Refactor layer violations — use service layer between API and DB."

    return float(score), {
        "circular_dependencies": circular,
        "architecture_violations": arch_violations,
        "has_architecture_report": report is not None,
        "recommendation": recommendation,
    }


async def compute_test_coverage_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on test file ratio and test function presence."""
    total_result = await db.execute(
        select(func.count(CodeFile.id)).where(CodeFile.repo_id == repo_id)
    )
    total_files = total_result.scalar() or 1

    test_result = await db.execute(
        select(func.count(CodeFile.id)).where(
            CodeFile.repo_id == repo_id,
            CodeFile.file_path.ilike("%test%")
        )
    )
    test_files = test_result.scalar() or 0

    # Count test functions
    test_fn_result = await db.execute(
        select(func.count(CodeChunk.id)).where(
            CodeChunk.repo_id == repo_id,
            CodeChunk.chunk_name.ilike("test_%")
        )
    )
    test_functions = test_fn_result.scalar() or 0

    ratio = test_files / max(total_files, 1)
    # 33% test ratio = 100, weighted with test function presence
    score = min(100, (ratio * 250) + min(50, test_functions * 0.5))

    recommendation = None
    if ratio < 0.1:
        recommendation = "Critical: Less than 10% of files have tests. Add unit tests immediately."
    elif ratio < 0.2:
        recommendation = "Add more test coverage — aim for at least 30% test file ratio."
    elif test_functions < 10:
        recommendation = "Increase number of test functions per test file."

    return float(score), {
        "test_files":      test_files,
        "total_files":     total_files,
        "test_ratio":      round(ratio, 3),
        "test_functions":  test_functions,
        "recommendation":  recommendation,
    }


async def compute_code_quality_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on function length, complexity and docstring coverage."""
    result = await db.execute(
        select(CodeChunk).where(
            CodeChunk.repo_id == repo_id,
            CodeChunk.chunk_type == "function"
        ).limit(500)
    )
    chunks = result.scalars().all()

    if not chunks:
        return 70.0, {"note": "No function chunks found — index repository first.", "recommendation": "Index this repository to get code quality analysis."}

    long_functions  = 0
    undocumented    = 0
    complex_funcs   = 0

    for chunk in chunks:
        content = chunk.content or ""
        lines   = (chunk.end_line or 0) - (chunk.start_line or 0)

        if lines > 100:
            long_functions += 1

        if not re.search(r'"""[\s\S]+?"""|\'\'\'[\s\S]+?\'\'\'|//\s\w', content):
            undocumented += 1

        # Simple complexity: count if/for/while/try branches
        branch_count = len(re.findall(r'\b(if|elif|for|while|try|except|case)\b', content))
        if branch_count > 10:
            complex_funcs += 1

    total     = len(chunks)
    long_r    = long_functions / total
    undoc_r   = undocumented   / total
    complex_r = complex_funcs  / total

    score = max(0, 100 - (long_r * 25) - (undoc_r * 15) - (complex_r * 20))

    recommendation = None
    if long_r > 0.3:
        recommendation = f"Refactor {long_functions} long functions (>100 lines) into smaller units."
    elif undoc_r > 0.5:
        recommendation = f"Add docstrings to {undocumented} undocumented functions."
    elif complex_r > 0.2:
        recommendation = f"Reduce complexity in {complex_funcs} high-branch functions."

    return float(score), {
        "total_functions":        total,
        "long_functions":         long_functions,
        "undocumented_functions": undocumented,
        "complex_functions":      complex_funcs,
        "recommendation":         recommendation,
    }


async def compute_dependency_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on change risk and tight coupling governance violations."""
    change_result = await db.execute(
        select(ChangeIntelligenceReport)
        .where(ChangeIntelligenceReport.repo_id == repo_id)
        .order_by(ChangeIntelligenceReport.created_at.desc())
        .limit(10)
    )
    reports = change_result.scalars().all()

    high_risks = sum(
        len([r for r in (rep.risks or []) if r.get("severity") == "high"])
        for rep in reports
    )

    coupling_result = await db.execute(
        text("SELECT COUNT(*) FROM governance_violations WHERE repo_id = :repo_id AND rule_type = 'tight_coupling'"),
        {"repo_id": repo_id}
    )
    tight_coupling = coupling_result.scalar() or 0

    score = max(0, 100 - (high_risks * 8) - (tight_coupling * 10))

    recommendation = None
    if tight_coupling > 0:
        recommendation = f"Reduce tight coupling in {tight_coupling} file(s) — use dependency injection."
    elif high_risks > 3:
        recommendation = "High change risk detected — consider feature flags for risky changes."

    return float(score), {
        "recent_high_risks": high_risks,
        "tight_coupling_files": tight_coupling,
        "change_reports_analyzed": len(reports),
        "recommendation": recommendation,
    }


async def compute_documentation_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on docstring coverage in classes and functions."""
    result = await db.execute(
        select(CodeChunk).where(
            CodeChunk.repo_id == repo_id,
            CodeChunk.chunk_type.in_(["class", "function"])
        ).limit(500)
    )
    chunks = result.scalars().all()

    if not chunks:
        return 60.0, {"note": "No code chunks found.", "recommendation": "Index the repository to analyze documentation coverage."}

    documented = sum(
        1 for c in chunks
        if re.search(r'"""[\s\S]+?"""|\'\'\'[\s\S]+?\'\'\'', c.content or "")
    )
    total = len(chunks)
    ratio = documented / total
    score = float(ratio * 100)

    recommendation = None
    if ratio < 0.3:
        recommendation = f"Only {int(ratio*100)}% of classes/functions are documented. Add docstrings."
    elif ratio < 0.6:
        recommendation = "Improve documentation coverage — aim for 80%+."

    return score, {
        "documented":     documented,
        "total":          total,
        "coverage_pct":   round(ratio * 100, 1),
        "recommendation": recommendation,
    }


# ── Main Scorer ────────────────────────────────────────────────────────────────

async def compute_health_score(repo_id: str, db: AsyncSession) -> dict[str, Any]:
    """Compute full health score, persist it and return with delta from last run."""

    # Compute all dimensions in parallel
    import asyncio
    results = await asyncio.gather(
        compute_security_score(repo_id, db),
        compute_architecture_score(repo_id, db),
        compute_test_coverage_score(repo_id, db),
        compute_code_quality_score(repo_id, db),
        compute_dependency_score(repo_id, db),
        compute_documentation_score(repo_id, db),
    )

    names = ["security", "architecture", "test_coverage", "code_quality", "dependency", "documentation"]
    scores = {name: {"score": round(res[0], 1), "details": res[1]} for name, res in zip(names, results)}

    overall = sum(scores[n]["score"] * WEIGHTS[n] for n in names)
    overall = round(overall, 1)

    # Get previous score for delta
    prev = await _get_previous_score(repo_id, db)
    delta = round(overall - prev, 1) if prev is not None else None

    # Persist new score
    await _persist_score(repo_id, overall, scores, db)

    # Build dimension output
    weight_labels = {"security": "25%", "architecture": "20%", "test_coverage": "20%",
                     "code_quality": "15%", "dependency": "10%", "documentation": "10%"}
    dimensions = {
        name: {
            "score":          scores[name]["score"],
            "weight":         weight_labels[name],
            "details":        scores[name]["details"],
            "recommendation": scores[name]["details"].pop("recommendation", None),
        }
        for name in names
    }

    # Top recommendations (only non-null ones)
    recommendations = [
        dimensions[n]["recommendation"]
        for n in names
        if dimensions[n]["recommendation"]
    ]

    return {
        "repo_id":          repo_id,
        "overall_score":    overall,
        "grade":            _grade(overall),
        "delta":            delta,
        "dimensions":       dimensions,
        "recommendations":  recommendations[:3],
        "computed_at":      datetime.utcnow().isoformat(),
    }


async def get_health_score_history(repo_id: str, db: AsyncSession, limit: int = 10) -> list[dict]:
    """Get historical health scores for trend analysis."""
    result = await db.execute(
        text("""
            SELECT overall_score, security_score, architecture_score,
                   test_coverage_score, code_quality_score,
                   dependency_score, documentation_score, created_at
            FROM repo_health_scores
            WHERE repo_id = :repo_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"repo_id": repo_id, "limit": limit}
    )
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


async def _get_previous_score(repo_id: str, db: AsyncSession) -> float | None:
    try:
        result = await db.execute(
            text("SELECT overall_score FROM repo_health_scores WHERE repo_id = :repo_id ORDER BY created_at DESC LIMIT 1"),
            {"repo_id": repo_id}
        )
        row = result.fetchone()
        return float(row[0]) if row else None
    except Exception:
        return None


async def _persist_score(repo_id: str, overall: float, scores: dict, db: AsyncSession):
    """Persist health score snapshot to database."""
    try:
        await db.execute(
            text("""
                INSERT INTO repo_health_scores
                  (id, repo_id, overall_score, security_score, architecture_score,
                   test_coverage_score, code_quality_score, dependency_score,
                   documentation_score, details, created_at)
                VALUES
                  (:id, :repo_id, :overall, :security, :architecture,
                   :test_coverage, :code_quality, :dependency,
                   :documentation, :details::jsonb, now())
            """),
            {
                "id":            str(uuid.uuid4()),
                "repo_id":       repo_id,
                "overall":       overall,
                "security":      scores["security"]["score"],
                "architecture":  scores["architecture"]["score"],
                "test_coverage": scores["test_coverage"]["score"],
                "code_quality":  scores["code_quality"]["score"],
                "dependency":    scores["dependency"]["score"],
                "documentation": scores["documentation"]["score"],
                "details":       str(scores),
            }
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist health score: {e}")
