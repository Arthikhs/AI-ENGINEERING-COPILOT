"""
Repository Health Score System
Generates a 0-100 score across 6 dimensions.
"""
import logging
import re
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.models import (
    CodeChunk, CodeFile, PRReview, ArchitectureReport,
    ChangeIntelligenceReport, Repository
)

logger = logging.getLogger(__name__)

WEIGHTS = {
    "security": 0.25,
    "architecture": 0.20,
    "test_coverage": 0.20,
    "code_quality": 0.15,
    "dependency": 0.10,
    "documentation": 0.10,
}


async def compute_security_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on recent security findings."""
    result = await db.execute(
        select(PRReview).where(PRReview.repo_id == repo_id).order_by(PRReview.created_at.desc()).limit(10)
    )
    reviews = result.scalars().all()
    if not reviews:
        return 70.0, {"note": "No PR reviews found, using baseline score"}

    high_risk = sum(1 for r in reviews if r.risk_level == "high")
    medium_risk = sum(1 for r in reviews if r.risk_level == "medium")
    score = max(0, 100 - (high_risk * 15) - (medium_risk * 5))
    return float(score), {"high_risk_prs": high_risk, "medium_risk_prs": medium_risk}


async def compute_architecture_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on latest architecture report circular deps."""
    result = await db.execute(
        select(ArchitectureReport).where(
            ArchitectureReport.repo_id == repo_id
        ).order_by(ArchitectureReport.created_at.desc()).limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        return 65.0, {"note": "No architecture report found"}

    circular = len(report.circular_dependencies or [])
    score = max(0, 100 - (circular * 10))
    return float(score), {"circular_dependencies": circular}


async def compute_test_coverage_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on ratio of test files to source files."""
    result = await db.execute(
        select(func.count(CodeFile.id)).where(CodeFile.repo_id == repo_id)
    )
    total_files = result.scalar() or 1

    test_result = await db.execute(
        select(func.count(CodeFile.id)).where(
            CodeFile.repo_id == repo_id,
            CodeFile.file_path.ilike("%test%")
        )
    )
    test_files = test_result.scalar() or 0

    ratio = test_files / total_files
    score = min(100, ratio * 300)  # 33% test ratio = 100 score
    return float(score), {"test_files": test_files, "total_files": total_files, "ratio": round(ratio, 2)}


async def compute_code_quality_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on avg function length and docstring presence."""
    result = await db.execute(
        select(CodeChunk).where(
            CodeChunk.repo_id == repo_id,
            CodeChunk.chunk_type == "function"
        ).limit(500)
    )
    chunks = result.scalars().all()
    if not chunks:
        return 70.0, {"note": "No function chunks found"}

    long_functions = 0
    undocumented = 0
    for chunk in chunks:
        lines = (chunk.end_line or 0) - (chunk.start_line or 0)
        if lines > 100:
            long_functions += 1
        if not re.search(r'""".*"""', chunk.content or "", re.DOTALL):
            undocumented += 1

    total = len(chunks)
    long_ratio = long_functions / total
    undoc_ratio = undocumented / total
    score = max(0, 100 - (long_ratio * 30) - (undoc_ratio * 20))
    return float(score), {
        "long_functions": long_functions,
        "undocumented_functions": undocumented,
        "total_functions": total,
    }


async def compute_dependency_score(repo_id: str, db: AsyncSession) -> tuple[float, dict]:
    """Score based on change intelligence risk findings."""
    result = await db.execute(
        select(ChangeIntelligenceReport).where(
            ChangeIntelligenceReport.repo_id == repo_id
        ).order_by(ChangeIntelligenceReport.created_at.desc()).limit(5)
    )
    reports = result.scalars().all()
    if not reports:
        return 75.0, {"note": "No change reports found"}

    high_risks = sum(
        len([r for r in (rep.risks or []) if r.get("severity") == "high"])
        for rep in reports
    )
    score = max(0, 100 - (high_risks * 10))
    return float(score), {"recent_high_risks": high_risks}


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
        return 60.0, {"note": "No chunks found"}

    documented = sum(
        1 for c in chunks
        if re.search(r'("""|\'\'\').+?("""|\'\'\')|(//\s.+?)(\n|$)', c.content or "", re.DOTALL)
    )
    ratio = documented / len(chunks)
    return float(ratio * 100), {"documented": documented, "total": len(chunks), "ratio": round(ratio, 2)}


async def compute_health_score(repo_id: str, db: AsyncSession) -> dict[str, Any]:
    """Compute overall health score for a repository."""
    security_score, security_details = await compute_security_score(repo_id, db)
    arch_score, arch_details = await compute_architecture_score(repo_id, db)
    test_score, test_details = await compute_test_coverage_score(repo_id, db)
    quality_score, quality_details = await compute_code_quality_score(repo_id, db)
    dep_score, dep_details = await compute_dependency_score(repo_id, db)
    doc_score, doc_details = await compute_documentation_score(repo_id, db)

    overall = (
        security_score * WEIGHTS["security"] +
        arch_score * WEIGHTS["architecture"] +
        test_score * WEIGHTS["test_coverage"] +
        quality_score * WEIGHTS["code_quality"] +
        dep_score * WEIGHTS["dependency"] +
        doc_score * WEIGHTS["documentation"]
    )

    def grade(s):
        if s >= 90: return "A"
        if s >= 80: return "B"
        if s >= 70: return "C"
        if s >= 60: return "D"
        return "F"

    return {
        "overall_score": round(overall, 1),
        "grade": grade(overall),
        "dimensions": {
            "security": {"score": round(security_score, 1), "weight": "25%", "details": security_details},
            "architecture": {"score": round(arch_score, 1), "weight": "20%", "details": arch_details},
            "test_coverage": {"score": round(test_score, 1), "weight": "20%", "details": test_details},
            "code_quality": {"score": round(quality_score, 1), "weight": "15%", "details": quality_details},
            "dependency_health": {"score": round(dep_score, 1), "weight": "10%", "details": dep_details},
            "documentation": {"score": round(doc_score, 1), "weight": "10%", "details": doc_details},
        },
    }
