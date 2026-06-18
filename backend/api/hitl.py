"""
Human-in-the-Loop API
Endpoints to trigger HITL security workflow, list pending approvals, and act on them.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from api.auth import get_current_user
from models.models import User, HITLApproval
from agents.hitl_workflow import build_hitl_graph, HITLState

router = APIRouter(prefix="/hitl", tags=["hitl"])


class HITLTriggerRequest(BaseModel):
    repo_id: str
    pr_number: Optional[int] = None
    github_token: Optional[str] = None


class ApprovalActionRequest(BaseModel):
    action: str   # "approve" | "reject"


# ── Trigger HITL workflow ──────────────────────────────────────────────────────

@router.post("/trigger")
async def trigger_hitl(
    body: HITLTriggerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start the HITL security review workflow for a repo/PR."""
    graph = build_hitl_graph(db)
    initial_state: HITLState = {
        "repo_id": body.repo_id,
        "pr_number": body.pr_number,
        "github_token": body.github_token,
        "findings": [],
        "overall_risk": "low",
        "summary": "",
        "approval_id": "",
        "approval_status": "pending",
        "comment_posted": False,
    }
    final_state = await graph.ainvoke(initial_state)
    return {
        "approval_id": final_state.get("approval_id"),
        "approval_status": final_state.get("approval_status"),
        "overall_risk": final_state.get("overall_risk"),
        "findings_count": len(final_state.get("findings", [])),
        "comment_posted": final_state.get("comment_posted"),
        "summary": final_state.get("summary"),
    }


# ── List pending approvals ─────────────────────────────────────────────────────

@router.get("/approvals")
async def list_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HITLApproval).order_by(HITLApproval.created_at.desc()).limit(50)
    )
    approvals = result.scalars().all()
    return {
        "approvals": [
            {
                "id": str(a.id),
                "repo_id": str(a.repo_id),
                "pr_number": a.pr_number,
                "overall_risk": a.overall_risk,
                "status": a.status,
                "findings_count": len(a.findings or []),
                "summary": a.summary,
                "created_at": a.created_at.isoformat(),
            }
            for a in approvals
        ]
    }


# ── Get single approval ────────────────────────────────────────────────────────

@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(HITLApproval).where(HITLApproval.id == approval_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {
        "id": str(a.id),
        "repo_id": str(a.repo_id),
        "pr_number": a.pr_number,
        "overall_risk": a.overall_risk,
        "status": a.status,
        "findings": a.findings,
        "summary": a.summary,
        "comment_posted": a.comment_posted,
        "created_at": a.created_at.isoformat(),
    }


# ── Approve / Reject ───────────────────────────────────────────────────────────

@router.post("/approvals/{approval_id}/action")
async def approval_action(
    approval_id: str,
    body: ApprovalActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    result = await db.execute(select(HITLApproval).where(HITLApproval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    approval.status = "approved" if body.action == "approve" else "rejected"
    await db.commit()

    # If approved, re-run the graph to post GitHub comment
    if approval.status == "approved":
        graph = build_hitl_graph(db)
        state: HITLState = {
            "repo_id": str(approval.repo_id),
            "pr_number": approval.pr_number,
            "github_token": None,
            "findings": approval.findings or [],
            "overall_risk": approval.overall_risk or "low",
            "summary": approval.summary or "",
            "approval_id": approval_id,
            "approval_status": "approved",
            "comment_posted": False,
        }
        final = await graph.ainvoke(state)
        return {"status": "approved", "comment_posted": final.get("comment_posted")}

    return {"status": approval.status}
