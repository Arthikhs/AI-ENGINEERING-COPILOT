from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response
import time
import logging

logger = logging.getLogger(__name__)

# --- OpenTelemetry Setup ---
provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("ai-engineering-copilot")

# --- Prometheus Metrics ---
REQUEST_COUNT = Counter(
    "api_requests_total", "Total API requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "api_request_duration_seconds", "API request latency", ["endpoint"]
)
AGENT_RUNS = Counter(
    "agent_runs_total", "Total agent executions", ["agent_type"]
)
RETRIEVAL_LATENCY = Histogram(
    "retrieval_duration_seconds", "Vector search latency"
)
TOKEN_USAGE = Counter(
    "llm_tokens_total", "LLM tokens consumed", ["model", "type"]
)
INGESTION_CHUNKS = Counter(
    "ingestion_chunks_total", "Total chunks ingested", ["repo_id"]
)


def setup_observability(app: FastAPI):
    FastAPIInstrumentor.instrument_app(app)

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(endpoint=request.url.path).observe(duration)

        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_agent_run(agent_type: str):
    AGENT_RUNS.labels(agent_type=agent_type).inc()


def record_token_usage(model: str, prompt_tokens: int, completion_tokens: int):
    TOKEN_USAGE.labels(model=model, type="prompt").inc(prompt_tokens)
    TOKEN_USAGE.labels(model=model, type="completion").inc(completion_tokens)
