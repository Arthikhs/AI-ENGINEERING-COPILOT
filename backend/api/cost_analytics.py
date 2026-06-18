"""
Cost Analytics — tracks token usage and computes $ costs per model/agent/repo.
Stored in Redis for real-time dashboard; aggregated on demand.
"""
import json
from datetime import datetime, date
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from api.auth import get_current_user
from models.models import User
from database import get_db
from config import get_settings

router = APIRouter(prefix="/analytics/costs", tags=["cost-analytics"])
settings = get_settings()

# OpenAI pricing per 1M tokens (as of 2024) — update as needed
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o":                    {"input": 5.00,  "output": 15.00},
    "gpt-4o-mini":               {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":               {"input": 10.00, "output": 30.00},
    "text-embedding-3-large":    {"input": 0.13,  "output": 0.0},
    "text-embedding-3-small":    {"input": 0.02,  "output": 0.0},
}

try:
    import redis.asyncio as aioredis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
except Exception:
    _redis = None


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 5.00, "output": 15.00})
    return (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000


async def record_usage(
    user_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    agent_type: str = "unknown",
    repo_id: Optional[str] = None,
):
    """Call this after every LLM invocation to track cost."""
    if not _redis:
        return
    cost = compute_cost(model, prompt_tokens, completion_tokens)
    today = date.today().isoformat()
    key = f"costs:{user_id}:{today}"

    # Load existing
    raw = await _redis.get(key)
    data = json.loads(raw) if raw else {"total_cost": 0.0, "models": {}, "agents": {}, "calls": 0}

    data["total_cost"] = round(data["total_cost"] + cost, 6)
    data["calls"] += 1

    # Per-model breakdown
    if model not in data["models"]:
        data["models"][model] = {"cost": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    data["models"][model]["cost"] = round(data["models"][model]["cost"] + cost, 6)
    data["models"][model]["prompt_tokens"] += prompt_tokens
    data["models"][model]["completion_tokens"] += completion_tokens
    data["models"][model]["calls"] += 1

    # Per-agent breakdown
    if agent_type not in data["agents"]:
        data["agents"][agent_type] = {"cost": 0.0, "calls": 0}
    data["agents"][agent_type]["cost"] = round(data["agents"][agent_type]["cost"] + cost, 6)
    data["agents"][agent_type]["calls"] += 1

    await _redis.setex(key, 60 * 60 * 24 * 30, json.dumps(data))  # 30-day TTL


@router.get("/summary")
async def get_cost_summary(
    days: int = 7,
    current_user: User = Depends(get_current_user),
):
    """Return cost summary for the last N days."""
    if not _redis:
        return {"error": "Redis not available", "total_cost": 0}

    from datetime import timedelta
    total = 0.0
    daily = []
    models_agg: Dict[str, Any] = {}
    agents_agg: Dict[str, Any] = {}
    calls_total = 0

    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        raw = await _redis.get(f"costs:{current_user.id}:{d}")
        if not raw:
            daily.append({"date": d, "cost": 0.0, "calls": 0})
            continue
        data = json.loads(raw)
        total += data["total_cost"]
        calls_total += data["calls"]
        daily.append({"date": d, "cost": round(data["total_cost"], 4), "calls": data["calls"]})

        for model, stats in data.get("models", {}).items():
            if model not in models_agg:
                models_agg[model] = {"cost": 0.0, "calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
            models_agg[model]["cost"] = round(models_agg[model]["cost"] + stats["cost"], 4)
            models_agg[model]["calls"] += stats["calls"]
            models_agg[model]["prompt_tokens"] += stats.get("prompt_tokens", 0)
            models_agg[model]["completion_tokens"] += stats.get("completion_tokens", 0)

        for agent, stats in data.get("agents", {}).items():
            if agent not in agents_agg:
                agents_agg[agent] = {"cost": 0.0, "calls": 0}
            agents_agg[agent]["cost"] = round(agents_agg[agent]["cost"] + stats["cost"], 4)
            agents_agg[agent]["calls"] += stats["calls"]

    return {
        "period_days": days,
        "total_cost_usd": round(total, 4),
        "total_calls": calls_total,
        "daily": list(reversed(daily)),
        "by_model": models_agg,
        "by_agent": agents_agg,
        "pricing_reference": MODEL_PRICING,
    }
