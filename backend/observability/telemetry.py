"""
Enterprise Observability — Production Grade
Tracks:
  - Agent execution graph (LangGraph step spans)
  - Cost per workflow
  - Token consumption per model/task
  - Retrieval quality metrics
  - Model routing decisions
  - Failure analytics
  - Sandbox execution metrics
  - Autonomous workflow metrics
"""
import time
import logging
from contextlib import contextmanager, asynccontextmanager
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST,
)
from fastapi import FastAPI, Response

logger = logging.getLogger(__name__)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    _OTEL_FASTAPI = True
except ImportError:
    _OTEL_FASTAPI = False

# ── OpenTelemetry ──────────────────────────────────────────────────────────────
provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("ai-engineering-copilot", "1.0.0")

# ── API ────────────────────────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "api_requests_total", "Total API requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "api_request_duration_seconds", "API request latency",
    ["endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
RATE_LIMIT_HITS = Counter(
    "rate_limit_hits_total", "Rate-limited requests",
    ["identifier_type"],
)

# ── Agent Execution ────────────────────────────────────────────────────────────
AGENT_RUNS = Counter(
    "agent_runs_total", "Total agent executions",
    ["agent_type", "status"],
)
AGENT_LATENCY = Histogram(
    "agent_execution_duration_seconds", "Agent execution latency",
    ["agent_type"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)
AGENT_STEPS = Histogram(
    "agent_graph_steps_total", "LangGraph steps per workflow run",
    ["workflow_type"],
    buckets=[1, 2, 3, 5, 7, 10, 15, 20],
)
AGENT_ERRORS = Counter(
    "agent_errors_total", "Agent errors by type and step",
    ["agent_type", "step", "error_type"],
)
ACTIVE_WORKFLOWS = Gauge(
    "active_workflows_count", "Currently running workflows",
    ["workflow_type"],
)

# ── LLM / Tokens ──────────────────────────────────────────────────────────────
TOKEN_USAGE = Counter(
    "llm_tokens_total", "LLM tokens consumed",
    ["model", "token_type"],
)
LLM_COST = Counter(
    "llm_cost_usd_total", "Cumulative LLM cost in USD",
    ["model", "task_type"],
)
LLM_LATENCY = Histogram(
    "llm_response_duration_seconds", "LLM API call latency",
    ["model", "task_type"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 45.0],
)
MODEL_ROUTING_DECISIONS = Counter(
    "model_routing_decisions_total", "Model routing decisions",
    ["task_type", "model", "provider"],
)
LLM_ERRORS = Counter(
    "llm_errors_total", "LLM API errors",
    ["model", "error_type"],
)

# ── Retrieval ──────────────────────────────────────────────────────────────────
RETRIEVAL_LATENCY = Histogram(
    "retrieval_duration_seconds", "Vector/hybrid search latency",
    ["retriever_type"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)
RETRIEVAL_RESULTS = Histogram(
    "retrieval_results_count", "Chunks returned per retrieval",
    ["retriever_type"],
    buckets=[1, 3, 5, 10, 20, 50],
)
RETRIEVAL_HIT_RATE = Counter(
    "retrieval_hits_total", "Retrieval hits vs misses",
    ["result"],
)

# ── Eval Quality ───────────────────────────────────────────────────────────────
HALLUCINATION_SCORE = Histogram(
    "llm_hallucination_score", "Hallucination score distribution",
    ["model"],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0],
)
FAITHFULNESS_SCORE = Histogram(
    "llm_faithfulness_score", "Answer faithfulness score",
    ["model"],
    buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
)

# ── Sandbox ────────────────────────────────────────────────────────────────────
SANDBOX_EXECUTIONS = Counter(
    "sandbox_executions_total", "Sandbox code executions",
    ["language", "status"],
)
SANDBOX_LATENCY = Histogram(
    "sandbox_execution_duration_seconds", "Sandbox execution time",
    ["language"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# ── Autonomous Engineer ────────────────────────────────────────────────────────
AUTONOMOUS_JOBS = Counter(
    "autonomous_engineer_jobs_total", "Autonomous issue-to-PR jobs",
    ["status"],
)
AUTONOMOUS_JOB_DURATION = Histogram(
    "autonomous_engineer_duration_seconds", "End-to-end workflow duration",
    buckets=[30, 60, 120, 300, 600, 900, 1800],
)
PR_CREATED = Counter(
    "pull_requests_created_total", "PRs created by autonomous engineer",
)

# ── Cost per Workflow ──────────────────────────────────────────────────────────
WORKFLOW_COST = Counter(
    "workflow_cost_usd_total", "AI cost per workflow type",
    ["workflow_type"],
)

# ── Knowledge Graph ────────────────────────────────────────────────────────────
KG_NODES = Gauge("knowledge_graph_nodes_total", "KG nodes", ["node_type"])
KG_EDGES = Gauge("knowledge_graph_edges_total", "KG edges", ["edge_type"])

# ── Ingestion ──────────────────────────────────────────────────────────────────
INGESTION_CHUNKS = Counter("ingestion_chunks_total", "Total chunks ingested", ["repo_id"])
INGESTION_ERRORS = Counter("ingestion_errors_total", "Ingestion errors by stage", ["stage"])


# ── Context Managers ───────────────────────────────────────────────────────────

@contextmanager
def trace_agent_step(agent_type: str, step_name: str, attributes: dict = None):
    """Trace a single LangGraph agent step with OTel span + Prometheus latency."""
    with tracer.start_as_current_span(f"{agent_type}.{step_name}") as span:
        span.set_attribute("agent.type", agent_type)
        span.set_attribute("agent.step", step_name)
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, str(v))
        start = time.time()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            AGENT_ERRORS.labels(
                agent_type=agent_type,
                step=step_name,
                error_type=type(e).__name__,
            ).inc()
            raise
        finally:
            AGENT_LATENCY.labels(agent_type=agent_type).observe(time.time() - start)


@asynccontextmanager
async def trace_workflow(workflow_type: str, job_id: str = ""):
    """Trace a full async workflow run."""
    ACTIVE_WORKFLOWS.labels(workflow_type=workflow_type).inc()
    start = time.time()
    with tracer.start_as_current_span(f"workflow.{workflow_type}") as span:
        span.set_attribute("workflow.type", workflow_type)
        span.set_attribute("workflow.job_id", job_id)
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
            AGENT_RUNS.labels(agent_type=workflow_type, status="success").inc()
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            AGENT_RUNS.labels(agent_type=workflow_type, status="failed").inc()
            raise
        finally:
            AUTONOMOUS_JOB_DURATION.observe(time.time() - start)
            ACTIVE_WORKFLOWS.labels(workflow_type=workflow_type).dec()


# ── Recording Helpers ──────────────────────────────────────────────────────────

def record_agent_run(agent_type: str, status: str = "success"):
    AGENT_RUNS.labels(agent_type=agent_type, status=status).inc()


def record_token_usage(
    model: str, input_tokens: int, output_tokens: int,
    task_type: str = "unknown", cost_usd: float = 0.0,
):
    TOKEN_USAGE.labels(model=model, token_type="input").inc(input_tokens)
    TOKEN_USAGE.labels(model=model, token_type="output").inc(output_tokens)
    if cost_usd > 0:
        LLM_COST.labels(model=model, task_type=task_type).inc(cost_usd)


def record_model_routing(task_type: str, model: str, provider: str):
    MODEL_ROUTING_DECISIONS.labels(task_type=task_type, model=model, provider=provider).inc()


def record_retrieval(retriever_type: str, latency_s: float, result_count: int):
    RETRIEVAL_LATENCY.labels(retriever_type=retriever_type).observe(latency_s)
    RETRIEVAL_RESULTS.labels(retriever_type=retriever_type).observe(result_count)
    RETRIEVAL_HIT_RATE.labels(result="hit" if result_count > 0 else "miss").inc()


def record_sandbox(language: str, status: str, duration_s: float):
    SANDBOX_EXECUTIONS.labels(language=language, status=status).inc()
    SANDBOX_LATENCY.labels(language=language).observe(duration_s)


def record_eval_scores(model: str, hallucination: float, faithfulness: float):
    HALLUCINATION_SCORE.labels(model=model).observe(hallucination)
    FAITHFULNESS_SCORE.labels(model=model).observe(faithfulness)


def record_workflow_cost(workflow_type: str, cost_usd: float):
    WORKFLOW_COST.labels(workflow_type=workflow_type).inc(cost_usd)


def record_autonomous_job(status: str):
    AUTONOMOUS_JOBS.labels(status=status).inc()
    if status == "completed":
        PR_CREATED.inc()


# ── FastAPI Setup ──────────────────────────────────────────────────────────────

def setup_observability(app: FastAPI):
    if _OTEL_FASTAPI:
        FastAPIInstrumentor.instrument_app(app)

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        if request.url.path in ("/metrics", "/health", "/"):
            return await call_next(request)
        start = time.time()
        response = await call_next(request)
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(endpoint=request.url.path).observe(time.time() - start)
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/metrics/summary", tags=["observability"])
    async def metrics_summary():
        return {
            "prometheus_endpoint": "/metrics",
            "tracked_metrics": [
                "api_requests_total",
                "api_request_duration_seconds",
                "rate_limit_hits_total",
                "agent_runs_total",
                "agent_execution_duration_seconds",
                "agent_graph_steps_total",
                "agent_errors_total",
                "active_workflows_count",
                "llm_tokens_total",
                "llm_cost_usd_total",
                "llm_response_duration_seconds",
                "model_routing_decisions_total",
                "retrieval_duration_seconds",
                "retrieval_hits_total",
                "llm_hallucination_score",
                "llm_faithfulness_score",
                "sandbox_executions_total",
                "autonomous_engineer_jobs_total",
                "autonomous_engineer_duration_seconds",
                "workflow_cost_usd_total",
                "knowledge_graph_nodes_total",
                "ingestion_chunks_total",
            ],
        }
