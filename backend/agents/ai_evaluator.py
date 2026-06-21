"""
Advanced AI Evaluation Engine
  - Hallucination detection (N-gram + entailment + LLM-as-judge)
  - Agent benchmarking (accuracy, latency percentiles, pass rate)
  - Model comparison (side-by-side on same test cases)
  - Cost vs Quality Pareto analysis
  - Regression detection
"""
import time
import uuid
import asyncio
import logging
import statistics
from typing import Any, Optional
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class EvalCase:
    id: str
    question: str
    expected_answer: str
    contexts: list[str]
    metadata: dict = field(default_factory=dict)


@dataclass
class EvalResult:
    case_id: str
    model: str
    answer: str
    latency_ms: int
    cost_usd: float
    input_tokens: int
    output_tokens: int
    faithfulness_score: float = 0.0
    relevance_score: float = 0.0
    hallucination_score: float = 0.0
    accuracy_score: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkSummary:
    run_id: str
    model: str
    task_type: str
    total_cases: int
    passed: int
    failed: int
    accuracy: float
    avg_faithfulness: float
    avg_relevance: float
    avg_hallucination_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p90_latency_ms: float
    p99_latency_ms: float
    total_cost_usd: float
    cost_per_case_usd: float
    quality_score: float
    results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Hallucination Detector ─────────────────────────────────────────────────────

class HallucinationDetector:

    async def detect(self, question: str, answer: str, contexts: list[str], use_llm_judge: bool = False) -> dict[str, Any]:
        combined = " ".join(contexts)
        ngram   = self._ngram_overlap(answer, combined)
        entail  = self._entailment(answer, combined)

        llm_score, llm_reason = 0.5, ""
        if use_llm_judge and contexts:
            llm_score, llm_reason = await self._llm_judge(question, answer, contexts)

        if use_llm_judge:
            hall = round((1 - ngram) * 0.2 + (1 - entail) * 0.3 + (1 - llm_score) * 0.5, 3)
        else:
            hall = round((1 - ngram) * 0.4 + (1 - entail) * 0.6, 3)

        hall = max(0.0, min(1.0, hall))
        return {
            "hallucination_score": hall,
            "faithfulness_score":  round(1.0 - hall, 3),
            "ngram_overlap":       round(ngram, 3),
            "entailment_score":    round(entail, 3),
            "llm_judge_score":     round(llm_score, 3),
            "llm_reasoning":       llm_reason,
            "risk_level": "high" if hall > 0.6 else "medium" if hall > 0.3 else "low",
        }

    def _ngram_overlap(self, answer: str, context: str, n: int = 3) -> float:
        def ng(text: str) -> set:
            w = text.lower().split()
            return {tuple(w[i:i+n]) for i in range(len(w) - n + 1)}
        a, c = ng(answer), ng(context)
        return len(a & c) / len(a) if a else 0.5

    def _entailment(self, answer: str, context: str) -> float:
        import re
        stop = {"the","a","an","is","it","in","on","at","to","of","and","or","but","for","with","this","that","are","was"}
        aw = set(re.findall(r'\b\w{4,}\b', answer.lower())) - stop
        cw = set(re.findall(r'\b\w{4,}\b', context.lower()))
        return len(aw & cw) / len(aw) if aw else 0.5

    async def _llm_judge(self, question: str, answer: str, contexts: list[str]) -> tuple[float, str]:
        try:
            import re, json
            from agents.model_router_agent import routed_invoke
            from langchain.schema import HumanMessage, SystemMessage
            result = await routed_invoke(
                task_type="simple_qa",
                messages=[
                    SystemMessage(content='Rate 0.0-1.0 how well the answer is grounded in context. 1.0=fully grounded, 0.0=hallucinated. Reply ONLY: {"score": 0.X, "reasoning": "..."}'),
                    HumanMessage(content=f"Question: {question}\n\nContext:\n{chr(10).join(contexts[:2])[:1500]}\n\nAnswer: {answer[:800]}"),
                ],
                temperature=0.0,
            )
            m = re.search(r'\{.*\}', result["response"].content, re.DOTALL)
            if m:
                p = json.loads(m.group())
                return float(p.get("score", 0.5)), p.get("reasoning", "")
        except Exception as e:
            logger.debug(f"LLM judge failed: {e}")
        return 0.5, "LLM judge unavailable"


# ── Model Evaluator ────────────────────────────────────────────────────────────

class ModelEvaluator:

    def __init__(self):
        self.detector = HallucinationDetector()

    async def evaluate_case(self, case: EvalCase, model: str, task_type: str) -> EvalResult:
        from agents.model_router_agent import routed_invoke
        from langchain.schema import HumanMessage, SystemMessage
        start = time.time()
        answer = error = ""
        input_tokens = output_tokens = 0
        cost_usd = 0.0
        try:
            r = await routed_invoke(
                task_type=task_type,
                override_model=model,
                messages=[
                    SystemMessage(content="Answer concisely based on the context."),
                    HumanMessage(content=f"Context:\n{chr(10).join(case.contexts[:2])}\n\nQuestion: {case.question}"),
                ],
                temperature=0.0,
            )
            answer        = r["response"].content
            input_tokens  = r.get("input_tokens", 0)
            output_tokens = r.get("output_tokens", 0)
            cost_usd      = r.get("estimated_cost_usd", 0.0)
        except Exception as e:
            error = str(e)

        latency_ms = int((time.time() - start) * 1000)
        hall = await self.detector.detect(case.question, answer, case.contexts)
        acc  = self._accuracy(answer, case.expected_answer)

        return EvalResult(
            case_id=case.id, model=model, answer=answer,
            latency_ms=latency_ms, cost_usd=cost_usd,
            input_tokens=input_tokens, output_tokens=output_tokens,
            faithfulness_score=hall["faithfulness_score"],
            relevance_score=hall["entailment_score"],
            hallucination_score=hall["hallucination_score"],
            accuracy_score=acc, error=error,
        )

    def _accuracy(self, answer: str, expected: str) -> float:
        if not expected: return 0.5
        aw = set(answer.lower().split())
        ew = set(expected.lower().split())
        return round(len(aw & ew) / len(ew), 3) if ew else 0.5

    async def run_benchmark(self, cases: list[EvalCase], model: str, task_type: str, max_concurrency: int = 3) -> BenchmarkSummary:
        sem = asyncio.Semaphore(max_concurrency)
        async def run_one(c: EvalCase) -> EvalResult:
            async with sem:
                return await self.evaluate_case(c, model, task_type)

        results   = await asyncio.gather(*[run_one(c) for c in cases])
        latencies = sorted(r.latency_ms for r in results)

        def pct(data: list, p: int) -> float:
            return data[max(0, int(len(data) * p / 100) - 1)] if data else 0

        passed     = sum(1 for r in results if r.accuracy_score >= 0.5 and not r.error)
        total_cost = sum(r.cost_usd for r in results)
        avg = lambda key: statistics.mean(getattr(r, key) for r in results) if results else 0

        quality = round(avg("accuracy_score") * 0.35 + avg("faithfulness_score") * 0.30 +
                        avg("relevance_score") * 0.20 + (1 - avg("hallucination_score")) * 0.15, 3)

        return BenchmarkSummary(
            run_id=str(uuid.uuid4()), model=model, task_type=task_type,
            total_cases=len(cases), passed=passed, failed=len(cases) - passed,
            accuracy=round(avg("accuracy_score"), 3),
            avg_faithfulness=round(avg("faithfulness_score"), 3),
            avg_relevance=round(avg("relevance_score"), 3),
            avg_hallucination_rate=round(avg("hallucination_score"), 3),
            avg_latency_ms=round(statistics.mean(latencies) if latencies else 0),
            p50_latency_ms=round(pct(latencies, 50)),
            p90_latency_ms=round(pct(latencies, 90)),
            p99_latency_ms=round(pct(latencies, 99)),
            total_cost_usd=round(total_cost, 6),
            cost_per_case_usd=round(total_cost / max(len(cases), 1), 6),
            quality_score=quality,
            results=[r.to_dict() for r in results],
        )


# ── Model Comparator ───────────────────────────────────────────────────────────

class ModelComparator:

    def __init__(self):
        self.evaluator = ModelEvaluator()

    async def compare(self, cases: list[EvalCase], models: list[str], task_type: str) -> dict[str, Any]:
        summaries = await asyncio.gather(*[
            self.evaluator.run_benchmark(cases, m, task_type) for m in models
        ])
        leaderboard = sorted([s.to_dict() for s in summaries], key=lambda x: x["quality_score"], reverse=True)
        return {
            "comparison_id":    str(uuid.uuid4()),
            "task_type":        task_type,
            "models_compared":  models,
            "total_cases":      len(cases),
            "leaderboard":      leaderboard,
            "best_quality":     leaderboard[0]["model"] if leaderboard else None,
            "lowest_cost":      min(summaries, key=lambda s: s.cost_per_case_usd).model if summaries else None,
            "best_latency":     min(summaries, key=lambda s: s.avg_latency_ms).model if summaries else None,
            "pareto_optimal":   self._pareto(summaries),
            "regression_flags": self._regressions(summaries),
        }

    def _pareto(self, summaries: list[BenchmarkSummary]) -> list[dict]:
        pareto = []
        for s in summaries:
            dominated = any(
                o.model != s.model and
                o.quality_score >= s.quality_score and
                o.cost_per_case_usd <= s.cost_per_case_usd
                for o in summaries
            )
            if not dominated:
                pareto.append({"model": s.model, "quality_score": s.quality_score,
                               "cost_per_case_usd": s.cost_per_case_usd, "pareto_optimal": True})
        return pareto

    def _regressions(self, summaries: list[BenchmarkSummary]) -> list[dict]:
        flags = []
        for s in summaries:
            issues = []
            if s.avg_hallucination_rate > 0.3:
                issues.append(f"High hallucination: {s.avg_hallucination_rate:.2f}")
            if s.accuracy < 0.5:
                issues.append(f"Low accuracy: {s.accuracy:.2f}")
            if s.p99_latency_ms > 30_000:
                issues.append(f"High p99 latency: {s.p99_latency_ms}ms")
            if issues:
                flags.append({"model": s.model, "issues": issues})
        return flags


# ── DB Persistence ─────────────────────────────────────────────────────────────

async def persist_benchmark(summary: BenchmarkSummary, db) -> str:
    try:
        import json
        from sqlalchemy import text
        await db.execute(
            text("""
                INSERT INTO benchmark_runs
                  (id, agent_type, version_label, model, test_cases, results, status,
                   accuracy, avg_latency_ms, total_cost_usd, hallucination_rate, created_at)
                VALUES (:id, :agent_type, :label, :model, :cases::jsonb, :results::jsonb,
                        'completed', :accuracy, :latency, :cost, :hall_rate, now())
            """),
            {
                "id": summary.run_id, "agent_type": summary.task_type,
                "label": f"{summary.model}-eval", "model": summary.model,
                "cases": json.dumps([]), "results": json.dumps(summary.results[:50]),
                "accuracy": summary.accuracy, "latency": summary.avg_latency_ms,
                "cost": summary.total_cost_usd, "hall_rate": summary.avg_hallucination_rate,
            }
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"persist_benchmark failed: {e}")
    return summary.run_id


async def persist_evaluation(result: EvalResult, db) -> str:
    eval_id = str(uuid.uuid4())
    try:
        from sqlalchemy import text
        await db.execute(
            text("""
                INSERT INTO llm_evaluations
                  (id, model, task_type, question, answer, faithfulness, relevance,
                   hallucination_score, latency_ms, cost_usd, created_at)
                VALUES (:id, :model, :task_type, :question, :answer, :faith, :rel,
                        :hall, :latency, :cost, now())
            """),
            {
                "id": eval_id, "model": result.model, "task_type": "evaluation",
                "question": result.case_id[:200], "answer": result.answer[:2000],
                "faith": result.faithfulness_score, "rel": result.relevance_score,
                "hall": result.hallucination_score, "latency": result.latency_ms,
                "cost": result.cost_usd,
            }
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"persist_evaluation failed: {e}")
    return eval_id


# ── Default Test Cases ────────────────────────────────────────────────────────

DEFAULT_EVAL_CASES = [
    EvalCase(
        id="code-qa-001",
        question="What does FastAPI Depends() do?",
        expected_answer="Depends() is used for dependency injection in FastAPI route handlers.",
        contexts=["FastAPI uses Depends() for dependency injection. Functions marked with Depends are called and their return values injected into route handlers."],
    ),
    EvalCase(
        id="code-qa-002",
        question="What is asyncio.gather() used for?",
        expected_answer="asyncio.gather() runs multiple coroutines concurrently and returns their results.",
        contexts=["asyncio.gather(*coros) schedules multiple coroutines concurrently and returns a list of results when all complete."],
    ),
    EvalCase(
        id="security-001",
        question="How do you prevent SQL injection?",
        expected_answer="Use parameterized queries or ORM to prevent SQL injection.",
        contexts=["SQL injection prevention: always use parameterized queries, prepared statements, or ORM frameworks that escape inputs."],
    ),
    EvalCase(
        id="arch-001",
        question="What is the Single Responsibility Principle?",
        expected_answer="SRP means a class should have only one reason to change.",
        contexts=["SOLID: Single Responsibility Principle states every class should have one and only one reason to change."],
    ),
    EvalCase(
        id="hallucination-001",
        question="What is the capital of France?",
        expected_answer="Paris is the capital of France.",
        contexts=["France is a country in Western Europe. Its capital city is Paris."],
    ),
]
