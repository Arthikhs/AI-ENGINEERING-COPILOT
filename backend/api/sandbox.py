"""
Secure Code Execution Sandbox API
Endpoints:
  POST /sandbox/execute         — Execute code in isolated sandbox
  POST /sandbox/test            — Execute tests against source code
  GET  /sandbox/languages       — List supported languages
  GET  /sandbox/status          — Check if Docker sandbox is available
  GET  /sandbox/history         — Execution history for current user
"""
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from api.auth import get_current_user
from models.models import User
from agents.sandbox import (
    execute_code_with_retry, execute_tests,
    log_execution, is_docker_available, SUPPORTED_LANGUAGES, LIMITS
)

router = APIRouter(prefix="/sandbox", tags=["sandbox"])
logger = logging.getLogger(__name__)


# ── Schemas ────────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    code:     str              = Field(..., min_length=1, max_length=50_000)
    language: str              = Field(..., description="python | javascript | typescript | java")
    stdin:    Optional[str]    = None


class TestExecuteRequest(BaseModel):
    source_code: str           = Field(..., max_length=50_000)
    test_code:   str           = Field(..., max_length=50_000)
    language:    str           = "python"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/languages")
async def list_languages():
    """Return supported languages and sandbox limits."""
    return {
        "languages": SUPPORTED_LANGUAGES,
        "limits": {
            "memory":       LIMITS["mem_limit"],
            "cpu":          "50% of 1 core",
            "timeout_sec":  LIMITS["timeout_sec"],
            "max_pids":     LIMITS["pids_limit"],
            "network":      "none (isolated)",
        }
    }


@router.get("/status")
async def sandbox_status():
    """Check if Docker sandbox is available."""
    available = is_docker_available()
    return {
        "available": available,
        "message": "Docker sandbox is ready" if available else "Docker is not running on this server",
    }


@router.post("/execute")
async def execute_sandbox(
    req: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute code in an isolated Docker sandbox.
    Supports Python, JavaScript, TypeScript, Java.
    """
    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language. Supported: {SUPPORTED_LANGUAGES}"
        )

    result = await execute_code_with_retry(
        code=req.code,
        language=req.language,
        stdin_data=req.stdin,
    )

    # Log to DB (non-blocking)
    await log_execution(result, job_id=None, db_session=db)

    return {
        **result.to_dict(),
        "language": req.language,
    }


@router.post("/test")
async def execute_sandbox_tests(
    req: TestExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute test code against source code in isolated sandbox.
    Combines source + tests and runs them.
    """
    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language. Supported: {SUPPORTED_LANGUAGES}"
        )

    result = await execute_tests(
        test_code=req.test_code,
        source_code=req.source_code,
        language=req.language,
    )

    await log_execution(result, job_id=None, db_session=db)

    return {
        **result.to_dict(),
        "language": req.language,
        "tests_passed": result.success,
    }


@router.get("/history")
async def execution_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent sandbox execution history."""
    result = await db.execute(
        text("""
            SELECT id, language, status, exit_code,
                   execution_time_ms, created_at,
                   LEFT(stdout, 500) as stdout_preview,
                   LEFT(stderr, 500) as stderr_preview
            FROM sandbox_executions
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"limit": limit}
    )
    rows = result.fetchall()
    return {"executions": [dict(r._mapping) for r in rows]}
