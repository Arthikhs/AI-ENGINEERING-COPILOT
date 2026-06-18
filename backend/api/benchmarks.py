"""
Agent Benchmark Dashboard API
Compare agent versions across accuracy, latency, cost, hallucination rate.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from database import get_db
from api.auth import get_current_user
from models.models import User, BenchmarkRun, AgentRun

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


class BenchmarkCreateRequest(BaseModel):
    agent_type: str
    version_label: str                 # e.g. "security-v2"
    model: str
    test_cases: list[dict]             # [{question, expected_answer, contexts}]


class BenchmarkRunRequest(BaseModel):
    benchmark_id: str


# ── Create benchmark ───────────────────────────────────────────────────────────

@router.post("")
async def create_benchmark(
    body: BenchmarkCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bm = BenchmarkRun(
        agent_type=body.agent_type,
        version_label=body.version_label,
        model=body.model,
        test_cases=body.test_cases,
        status="pending",
        created_by=current_user.id,
    )
    db.add(bm)
    await db.commit()
    return {"id": str(bm.id)}


# ── List benchmarks ────────────────────────────────────────────────────────────

@router.get("")
async def list_benchmarks(
    agent_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc())
    if agent_type:
        q = q.where(BenchmarkRun.agent_type == agent_type)
    result = await db.execute(q.limit(100))
    runs = result.scalars().all()
    return {
        "benchmarks": [
            {
                "id": str(b.id),
                "agent_type": b.agent_type,
                "version_label": b.version_label,
                "model": b.model,
                "status": b.status,
                "accuracy": b.accuracy,
                "avg_latency_ms": b.avg_latency_ms,
                "total_cost_usd": b.total_cost_usd,
                "hallucination_rate": b.hallucination_rate,
                "test_case_count": len(b.test_cases or []),
                "created_at": b.created_at.isoformat(),
            }
            for b in runs
        ]
    }


# ── Run a benchmark ────────────────────────────────────────────────────────────

@router.post("/{benchmark_id}/run")
async def run_benchmark(
    benchmark_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute all test cases and compute aggregate metrics."""
    result = await db.execute(select(BenchmarkRun).where(BenchmarkRun.id == benchmark_id))
    bm = result.scalar_one_or_none()
    if not bm:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    from agents.model_router_agent import routed_invoke
    from langchain.schema import HumanMessage

    bm.status = "running"
    await db.commit()

    total_latency = 0
    total_cost = 0.0
    correct = 0
    hallucinations = 0
    case_results = []

    for case in (bm.test_cases or []):
        try:
            run_result = await routed_invoke(
                task_type=bm.agent_type,
                messages=[HumanMessage(content=case.get("question", ""))],
                override_model=bm.model,
            )
            answer = run_result["response"].content
            expected = case.get("expected_answer", "")

            # Simple overlap-based accuracy
            overlap = len(set(answer.lower().split()) & set(expected.lower().split()))
            is_correct = overlap / max(len(expected.split()), 1) >= 0.5

            # Naive hallucination check: answer mentions entities not in context
            contexts_text = " ".join(case.get("contexts", []))
            answer_words = set(answer.lower().split())
            context_words = set(contexts_text.lower().split()) | set(expected.lower().split())
            unsupported = len(answer_words - context_words) / max(len(answer_words), 1)
            is_hallucination = unsupported > 0.6

            if is_correct:
                correct += 1
            if is_hallucination:
                hallucinations += 1

            total_latency += run_result["latency_ms"]
            total_cost += run_result["estimated_cost_usd"]

            case_results.append({
                "question": case.get("question"),
                "answer": answer,
                "is_correct": is_correct,
                "is_hallucination": is_hallucination,
                "latency_ms": run_result["latency_ms"],
                "cost_usd": run_result["estimated_cost_usd"],
            })
        except Exception as e:
            case_results.append({"question": case.get("question"), "error": str(e)})

    n = len(bm.test_cases or []) or 1
    bm.accuracy = round(correct / n, 3)
    bm.avg_latency_ms = round(total_latency / n)
    bm.total_cost_usd = round(total_cost, 4)
    bm.hallucination_rate = round(hallucinations / n, 3)
    bm.results = case_results
    bm.status = "completed"
    await db.commit()

    return {
        "id": str(bm.id),
        "accuracy": bm.accuracy,
        "avg_latency_ms": bm.avg_latency_ms,
        "total_cost_usd": bm.total_cost_usd,
        "hallucination_rate": bm.hallucination_rate,
        "status": bm.status,
        "results": case_results,
    }


# ── Compare two benchmark runs ─────────────────────────────────────────────────

@router.get("/compare")
async def compare_benchmarks(
    id_a: str,
    id_b: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result_a = await db.execute(select(BenchmarkRun).where(BenchmarkRun.id == id_a))
    result_b = await db.execute(select(BenchmarkRun).where(BenchmarkRun.id == id_b))
    a = result_a.scalar_one_or_none()
    b = result_b.scalar_one_or_none()
    if not a or not b:
        raise HTTPException(status_code=404, detail="One or both benchmarks not found")

    def _delta(va, vb):
        if va is None or vb is None:
            return None
        return round(float(va) - float(vb), 3)

    return {
        "a": {"id": str(a.id), "label": a.version_label, "model": a.model,
              "accuracy": a.accuracy, "avg_latency_ms": a.avg_latency_ms,
              "total_cost_usd": a.total_cost_usd, "hallucination_rate": a.hallucination_rate},
        "b": {"id": str(b.id), "label": b.version_label, "model": b.model,
              "accuracy": b.accuracy, "avg_latency_ms": b.avg_latency_ms,
              "total_cost_usd": b.total_cost_usd, "hallucination_rate": b.hallucination_rate},
        "delta": {
            "accuracy":          _delta(a.accuracy, b.accuracy),
            "avg_latency_ms":    _delta(a.avg_latency_ms, b.avg_latency_ms),
            "total_cost_usd":    _delta(a.total_cost_usd, b.total_cost_usd),
            "hallucination_rate": _delta(a.hallucination_rate, b.hallucination_rate),
        },
    }
