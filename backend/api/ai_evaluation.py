"""
AI Evaluation API Endpoints
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from database import get_db
from api.auth import get_current_user
from models.models import User
from agents.ai_evaluator import (
    EvalCase, ModelEvaluator, ModelComparator, HallucinationDetector,
    persist_benchmark, persist_evaluation, DEFAULT_EVAL_CASES,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eval", tags=["ai-evaluation"])


class BenchmarkRequest(BaseModel):
    model: str
    task_type: str = "simple_qa"
    use_default_cases: bool = True
    custom_cases: list[dict] = []
    max_concurrency: int = 3


class CompareRequest(BaseModel):
    models: list[str]
    task_type: str = "simple_qa"
    use_default_cases: bool = True
    custom_cases: list[dict] = []


class HallucinationRequest(BaseModel):
    question: str
    answer: str
    contexts: list[str] = []
    use_llm_judge: bool = False


class SingleEvalRequest(BaseModel):
    model: str
    task_type: str
    question: str
    expected_answer: str = ""
    contexts: list[str] = []


def _build_cases(use_defaults: bool, custom: list[dict]) -> list[EvalCase]:
    cases = list(DEFAULT_EVAL_CASES) if use_defaults else []
    for c in custom:
        cases.append(EvalCase(
            id=c.get("id", "custom"),
            question=c["question"],
            expected_answer=c.get("expected_answer", ""),
            contexts=c.get("contexts", []),
        ))
    return cases


@router.post("/benchmark")
async def run_benchmark(
    req: BenchmarkRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cases = _build_cases(req.use_default_cases, req.custom_cases)
    summary = await ModelEvaluator().run_benchmark(cases, req.model, req.task_type, req.max_concurrency)
    background_tasks.add_task(persist_benchmark, summary, db)
    return summary.to_dict()


@router.post("/compare")
async def compare_models(
    req: CompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(req.models) < 2:
        return {"error": "Provide at least 2 models"}
    cases = _build_cases(req.use_default_cases, req.custom_cases)
    return await ModelComparator().compare(cases, req.models, req.task_type)


@router.post("/hallucination")
async def detect_hallucination(
    req: HallucinationRequest,
    current_user: User = Depends(get_current_user),
):
    return await HallucinationDetector().detect(req.question, req.answer, req.contexts, req.use_llm_judge)


@router.post("/single")
async def run_single_eval(
    req: SingleEvalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = EvalCase(id="single", question=req.question,
                    expected_answer=req.expected_answer, contexts=req.contexts)
    result = await ModelEvaluator().evaluate_case(case, req.model, req.task_type)
    await persist_evaluation(result, db)
    return result.to_dict()


@router.get("/runs")
async def list_runs(
    limit: int = 20,
    model: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    where = "WHERE model = :model" if model else ""
    result = await db.execute(
        text(f"SELECT id, agent_type, model, status, accuracy, avg_latency_ms, total_cost_usd, hallucination_rate, created_at FROM benchmark_runs {where} ORDER BY created_at DESC LIMIT :limit"),
        {"model": model, "limit": limit} if model else {"limit": limit},
    )
    return {"runs": [dict(r._mapping) for r in result.fetchall()]}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(text("SELECT * FROM benchmark_runs WHERE id = :id"), {"id": run_id})
    row = result.fetchone()
    return dict(row._mapping) if row else {"error": "Not found"}


@router.get("/leaderboard")
async def get_leaderboard(
    task_type: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    where = "WHERE agent_type = :task_type" if task_type else ""
    result = await db.execute(
        text(f"""
            SELECT model, COUNT(*) as total_runs,
                   AVG(accuracy) as avg_accuracy,
                   AVG(avg_latency_ms) as avg_latency_ms,
                   AVG(hallucination_rate) as avg_hallucination_rate,
                   SUM(total_cost_usd) as total_cost
            FROM benchmark_runs {where}
            GROUP BY model ORDER BY avg_accuracy DESC NULLS LAST LIMIT :limit
        """),
        {"task_type": task_type, "limit": limit} if task_type else {"limit": limit},
    )
    return {"leaderboard": [dict(r._mapping) for r in result.fetchall()]}


@router.get("/regression")
async def get_regression(
    model: str,
    baseline_model: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        text("SELECT model, accuracy, avg_latency_ms, hallucination_rate, total_cost_usd, created_at FROM benchmark_runs WHERE model = :model ORDER BY created_at DESC LIMIT 5"),
        {"model": model},
    )
    current_runs = [dict(r._mapping) for r in result.fetchall()]

    baseline_runs, regressions = [], []
    if baseline_model:
        b = await db.execute(
            text("SELECT model, accuracy, avg_latency_ms, hallucination_rate, total_cost_usd, created_at FROM benchmark_runs WHERE model = :model ORDER BY created_at DESC LIMIT 5"),
            {"model": baseline_model},
        )
        baseline_runs = [dict(r._mapping) for r in b.fetchall()]

    if current_runs and baseline_runs:
        c, b = current_runs[0], baseline_runs[0]
        if (c.get("accuracy") or 0) < (b.get("accuracy") or 0) - 0.05:
            regressions.append(f"Accuracy dropped: {c['accuracy']:.3f} vs {b['accuracy']:.3f}")
        if (c.get("hallucination_rate") or 0) > (b.get("hallucination_rate") or 0) + 0.1:
            regressions.append(f"Hallucination increased: {c['hallucination_rate']:.3f} vs {b['hallucination_rate']:.3f}")

    return {
        "model": model, "baseline_model": baseline_model,
        "current_runs": current_runs, "baseline_runs": baseline_runs,
        "regressions": regressions, "regression_detected": len(regressions) > 0,
    }


@router.get("/stats/hallucination")
async def hallucination_stats(
    model: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    where = "WHERE model = :model" if model else ""
    result = await db.execute(
        text(f"SELECT model, COUNT(*) as total_evals, AVG(hallucination_score) as avg_hallucination, AVG(faithfulness) as avg_faithfulness, AVG(latency_ms) as avg_latency_ms, SUM(cost_usd) as total_cost FROM llm_evaluations {where} GROUP BY model ORDER BY avg_hallucination ASC"),
        {"model": model} if model else {},
    )
    return {"stats": [dict(r._mapping) for r in result.fetchall()]}
