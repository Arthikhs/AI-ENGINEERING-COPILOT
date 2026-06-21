"""
Observability API
  GET /observability/metrics/summary  — list all tracked metrics
  GET /observability/agent-stats      — agent run stats from DB
  GET /observability/cost-breakdown   — cost per workflow type
  GET /observability/workflow-graph   — recent agent execution graph data
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from api.auth import get_current_user
from models.models import User
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/metrics/summary")
async def metrics_summary(current_user: User = Depends(get_current_user)):
    """List all Prometheus metrics tracked by the platform."""
    return {
        "prometheus_endpoint": "/metrics",
        "grafana_dashboard":   "http://localhost:3001",
        "tracked_metrics": [
            {"name": "api_requests_total",                   "type": "counter",   "description": "Total API requests by method/endpoint/status"},
            {"name": "api_request_duration_seconds",         "type": "histogram", "description": "API latency — p50/p90/p95/p99"},
            {"name": "rate_limit_hits_total",                "type": "counter",   "description": "Rate-limited requests by identifier type"},
            {"name": "agent_runs_total",                     "type": "counter",   "description": "Agent executions by type and status"},
            {"name": "agent_execution_duration_seconds",     "type": "histogram", "description": "Agent execution latency by type"},
            {"name": "agent_graph_steps_total",              "type": "histogram", "description": "LangGraph steps per workflow run"},
            {"name": "agent_errors_total",                   "type": "counter",   "description": "Agent errors by type, step, error_type"},
            {"name": "active_workflows_count",               "type": "gauge",     "description": "Currently running workflows"},
            {"name": "llm_tokens_total",                     "type": "counter",   "description": "LLM input/output tokens by model"},
            {"name": "llm_cost_usd_total",                   "type": "counter",   "description": "Cumulative LLM cost by model/task"},
            {"name": "llm_response_duration_seconds",        "type": "histogram", "description": "LLM API call latency by model/task"},
            {"name": "model_routing_decisions_total",        "type": "counter",   "description": "Model routing decisions by task/model/provider"},
            {"name": "retrieval_duration_seconds",           "type": "histogram", "description": "Vector/hybrid search latency by retriever type"},
            {"name": "retrieval_hits_total",                 "type": "counter",   "description": "Retrieval hits vs misses"},
            {"name": "llm_hallucination_score",              "type": "histogram", "description": "Hallucination score distribution by model"},
            {"name": "llm_faithfulness_score",               "type": "histogram", "description": "Faithfulness score distribution by model"},
            {"name": "sandbox_executions_total",             "type": "counter",   "description": "Sandbox executions by language/status"},
            {"name": "sandbox_execution_duration_seconds",   "type": "histogram", "description": "Sandbox execution time by language"},
            {"name": "autonomous_engineer_jobs_total",       "type": "counter",   "description": "Autonomous issue-to-PR jobs by status"},
            {"name": "autonomous_engineer_duration_seconds", "type": "histogram", "description": "End-to-end autonomous workflow duration"},
            {"name": "workflow_cost_usd_total",              "type": "counter",   "description": "AI cost per workflow type"},
            {"name": "knowledge_graph_nodes_total",          "type": "gauge",     "description": "KG nodes by type"},
            {"name": "knowledge_graph_edges_total",          "type": "gauge",     "description": "KG edges by type"},
            {"name": "ingestion_chunks_total",               "type": "counter",   "description": "Chunks ingested by repo"},
        ],
    }


@router.get("/agent-stats")
async def agent_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Agent run stats from DB for the last N hours."""
    result = await db.execute(
        text("""
            SELECT task_type, model, provider,
                   COUNT(*) AS total_runs,
                   AVG(latency_ms) AS avg_latency_ms,
                   PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY latency_ms) AS p90_latency_ms,
                   SUM(estimated_cost_usd) AS total_cost_usd,
                   SUM(input_tokens) AS total_input_tokens,
                   SUM(output_tokens) AS total_output_tokens,
                   AVG(quality_score) AS avg_quality_score
            FROM agent_runs
            WHERE created_at >= NOW() - INTERVAL '1 hour' * :hours
            GROUP BY task_type, model, provider
            ORDER BY total_runs DESC
            LIMIT 50
        """),
        {"hours": hours},
    )
    rows = result.fetchall()
    return {"hours": hours, "stats": [dict(r._mapping) for r in rows]}


@router.get("/cost-breakdown")
async def cost_breakdown(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cost breakdown by task type, model, and provider."""
    result = await db.execute(
        text("""
            SELECT task_type, model, provider,
                   COUNT(*) AS runs,
                   SUM(estimated_cost_usd) AS total_cost_usd,
                   AVG(estimated_cost_usd) AS avg_cost_per_run,
                   SUM(input_tokens + output_tokens) AS total_tokens
            FROM agent_runs
            WHERE created_at >= NOW() - INTERVAL '1 hour' * :hours
            GROUP BY task_type, model, provider
            ORDER BY total_cost_usd DESC
            LIMIT 30
        """),
        {"hours": hours},
    )
    rows = result.fetchall()

    total_result = await db.execute(
        text("""
            SELECT SUM(estimated_cost_usd) AS total_cost_usd,
                   COUNT(*) AS total_runs,
                   SUM(input_tokens + output_tokens) AS total_tokens
            FROM agent_runs
            WHERE created_at >= NOW() - INTERVAL '1 hour' * :hours
        """),
        {"hours": hours},
    )
    totals = dict(total_result.fetchone()._mapping)
    return {"hours": hours, "totals": totals, "breakdown": [dict(r._mapping) for r in rows]}


@router.get("/workflow-graph")
async def workflow_graph(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent autonomous engineer job execution graph data."""
    result = await db.execute(
        text("""
            SELECT id, repo_full_name, issue_number, issue_title,
                   status, branch_name, pr_url, step_log,
                   files_changed, created_at, updated_at
            FROM autonomous_engineer_jobs
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.fetchall()
    jobs = [dict(r._mapping) for r in rows]

    # Build execution graph nodes/edges from step_log
    graph_data = []
    for job in jobs:
        steps = job.get("step_log") or []
        nodes = [{"id": i, "label": s[:60], "status": "success" if "✅" in s else "failed" if "❌" in s else "warning"} for i, s in enumerate(steps)]
        edges = [{"from": i, "to": i + 1} for i in range(len(nodes) - 1)]
        graph_data.append({
            "job_id":      str(job["id"]),
            "issue":       f"#{job['issue_number']} {job.get('issue_title', '')}",
            "status":      job["status"],
            "pr_url":      job.get("pr_url"),
            "nodes":       nodes,
            "edges":       edges,
            "created_at":  str(job["created_at"]),
        })

    return {"jobs": graph_data, "total": len(graph_data)}


@router.get("/retrieval-quality")
async def retrieval_quality(
    repo_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieval quality stats — chunk counts and coverage per repo."""
    where = "WHERE repo_id = :repo_id" if repo_id else ""
    result = await db.execute(
        text(f"""
            SELECT
                r.full_name,
                COUNT(DISTINCT f.id) AS total_files,
                COUNT(c.id)          AS total_chunks,
                AVG(LENGTH(c.content)) AS avg_chunk_size,
                MAX(r.last_synced_at)  AS last_synced
            FROM repositories r
            LEFT JOIN files f ON f.repo_id = r.id
            LEFT JOIN chunks c ON c.repo_id = r.id
            {where}
            GROUP BY r.id, r.full_name
            ORDER BY total_chunks DESC
            LIMIT 20
        """),
        {"repo_id": repo_id} if repo_id else {},
    )
    rows = result.fetchall()
    return {"repos": [dict(r._mapping) for r in rows]}
