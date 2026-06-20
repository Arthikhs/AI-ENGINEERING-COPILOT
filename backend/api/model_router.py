"""
Model Router API
Exposes routing table, per-model stats, and a live test-invoke endpoint.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from langchain.schema import HumanMessage, SystemMessage
from database import get_db
from api.auth import get_current_user
from models.models import User, AgentRun
from agents.model_router_agent import (
    TASK_ROUTING, COST_PER_1K, QUALITY_SCORES, route_model, routed_invoke
)
from llm_router import get_available_models

router = APIRouter(prefix="/router", tags=["model-router"])


class InvokeRequest(BaseModel):
    task_type: str
    prompt: str
    override_model: Optional[str] = None


class RoutingUpdateRequest(BaseModel):
    task_type: str
    model: str


# ── GET routing table ──────────────────────────────────────────────────────────

@router.get("/routing-table")
async def get_routing_table(current_user: User = Depends(get_current_user)):
    """Return the current task → model routing table with metadata."""
    rows = []
    for task, model in TASK_ROUTING.items():
        rows.append({
            "task_type": task,
            "model": model,
            "quality_score": QUALITY_SCORES.get(model, 0.80),
            "cost_per_1k_input": COST_PER_1K.get(model, {}).get("input", 0),
            "cost_per_1k_output": COST_PER_1K.get(model, {}).get("output", 0),
        })
    return {"routing_table": rows, "available_models": get_available_models()}


# ── GET per-model stats from DB ────────────────────────────────────────────────

@router.get("/stats")
async def get_router_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate cost, latency, and call counts per model from AgentRun history."""
    result = await db.execute(
        select(
            AgentRun.model,
            AgentRun.task_type,
            func.count(AgentRun.id).label("calls"),
            func.avg(AgentRun.latency_ms).label("avg_latency_ms"),
            func.sum(AgentRun.estimated_cost_usd).label("total_cost_usd"),
            func.avg(AgentRun.quality_score).label("avg_quality"),
        ).group_by(AgentRun.model, AgentRun.task_type)
    )
    rows = result.fetchall()
    stats = [
        {
            "model": r.model,
            "task_type": r.task_type,
            "calls": r.calls,
            "avg_latency_ms": round(r.avg_latency_ms or 0),
            "total_cost_usd": round(float(r.total_cost_usd or 0), 4),
            "avg_quality": round(float(r.avg_quality or 0), 3),
        }
        for r in rows
    ]
    return {"stats": stats}


# ── POST test invoke ───────────────────────────────────────────────────────────

@router.post("/invoke")
async def invoke_routed(
    body: InvokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a prompt through the router and return the response + telemetry."""
    try:
        result = await routed_invoke(
            task_type=body.task_type,
            messages=[HumanMessage(content=body.prompt)],
            override_model=body.override_model,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # routed_invoke already persists a run via _persist_agent_run (fire-and-forget).
    # Here we update it with the user_id by adding a separate user-linked record.
    run = AgentRun(
        user_id=current_user.id,
        task_type=result["task_type"],
        model=result["model"],
        provider=result["provider"],
        latency_ms=result["latency_ms"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        estimated_cost_usd=result["estimated_cost_usd"],
        quality_score=result["quality_score"],
    )
    db.add(run)
    await db.commit()

    return {
        "content": result["response"].content,
        "model": result["model"],
        "provider": result["provider"],
        "task_type": result["task_type"],
        "latency_ms": result["latency_ms"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "estimated_cost_usd": result["estimated_cost_usd"],
        "quality_score": result["quality_score"],
    }
