"""
Model Router Agent
Routes tasks to the optimal LLM based on task type.
Tracks cost, latency, and quality per invocation.

Routing table:
  simple_qa         → gpt-4o-mini   (fast, cheap)
  security_review   → claude-3-5-sonnet (best reasoning for security)
  architecture      → gpt-4o        (strong reasoning)
  test_generation   → llama3        (local, code-focused)
  refactoring       → gpt-4o        (default)
  pr_review         → gpt-4o-mini
"""
import time
import logging
from typing import Any, Dict, Optional
from langchain.schema import BaseMessage
from llm_router import get_llm, MODELS
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Token cost per 1K tokens (USD) — approximate market rates
COST_PER_1K: Dict[str, Dict[str, float]] = {
    "gpt-4o":            {"input": 0.005,   "output": 0.015},
    "gpt-4o-mini":       {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo":       {"input": 0.01,    "output": 0.03},
    "claude-3-5-sonnet": {"input": 0.003,   "output": 0.015},
    "claude-3-haiku":    {"input": 0.00025, "output": 0.00125},
    "claude-3-opus":     {"input": 0.015,   "output": 0.075},
    "gemini-1.5-pro":    {"input": 0.0035,  "output": 0.0105},
    "gemini-1.5-flash":  {"input": 0.00035, "output": 0.00105},
    "llama3":            {"input": 0.0,     "output": 0.0},   # local
    "llama3.1":          {"input": 0.0,     "output": 0.0},
    "codellama":         {"input": 0.0,     "output": 0.0},
}

# Default routing map: task_type → model
TASK_ROUTING: Dict[str, str] = {
    "simple_qa":       "gpt-4o-mini",
    "security_review": "claude-3-5-sonnet",
    "architecture":    "gpt-4o",
    "test_generation": "llama3",
    "refactoring":     "gpt-4o",
    "pr_review":       "gpt-4o-mini",
    "documentation":   "gpt-4o-mini",
    "knowledge_graph": "gpt-4o",
    "chat":            "gpt-4o-mini",
    "code_analysis":   "gpt-4o",
    "system_design":   "gpt-4o",
}

# Quality score heuristics (0-1) — based on model capability benchmark
QUALITY_SCORES: Dict[str, float] = {
    "gpt-4o":            0.95,
    "gpt-4o-mini":       0.80,
    "gpt-4-turbo":       0.92,
    "claude-3-5-sonnet": 0.94,
    "claude-3-haiku":    0.75,
    "claude-3-opus":     0.96,
    "gemini-1.5-pro":    0.90,
    "gemini-1.5-flash":  0.78,
    "llama3":            0.72,
    "llama3.1":          0.74,
    "codellama":         0.76,
}


def route_model(task_type: str, override_model: Optional[str] = None) -> str:
    """Return the model name for a given task type."""
    if override_model:
        return override_model
    return TASK_ROUTING.get(task_type, settings.llm_model)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token counts."""
    rates = COST_PER_1K.get(model, {"input": 0.005, "output": 0.015})
    return (input_tokens / 1000 * rates["input"]) + (output_tokens / 1000 * rates["output"])


async def routed_invoke(
    task_type: str,
    messages: list[BaseMessage],
    override_model: Optional[str] = None,
    temperature: float = 0,
) -> Dict[str, Any]:
    """
    Invoke the best model for the task. Returns:
      {
        response: AIMessage,
        model: str,
        provider: str,
        task_type: str,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_usd: float,
        quality_score: float,
      }
    """
    model = route_model(task_type, override_model)
    llm = get_llm(model, temperature=temperature)

    start = time.perf_counter()
    response = await llm.ainvoke(messages)
    latency_ms = int((time.perf_counter() - start) * 1000)

    # Extract token usage from response metadata
    usage = getattr(response, "usage_metadata", None) or getattr(response, "response_metadata", {})
    input_tokens = (
        getattr(usage, "input_tokens", None)
        or (usage.get("token_usage", {}).get("prompt_tokens") if isinstance(usage, dict) else None)
        or 0
    )
    output_tokens = (
        getattr(usage, "output_tokens", None)
        or (usage.get("token_usage", {}).get("completion_tokens") if isinstance(usage, dict) else None)
        or 0
    )

    cost = estimate_cost(model, input_tokens, output_tokens)
    quality = QUALITY_SCORES.get(model, 0.80)
    provider = MODELS.get(model, {}).get("provider", "openai")

    logger.info(
        f"[ModelRouter] task={task_type} model={model} "
        f"latency={latency_ms}ms tokens={input_tokens}+{output_tokens} cost=${cost:.5f}"
    )

    return {
        "response": response,
        "model": model,
        "provider": provider,
        "task_type": task_type,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 6),
        "quality_score": quality,
    }
