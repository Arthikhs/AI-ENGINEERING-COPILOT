"""
Human-in-the-Loop (HITL) Workflow using LangGraph.

Flow:
  SecurityAgent → parse findings → if HIGH/CRITICAL → await_approval → post_github_comment
                                   if LOW/MEDIUM    → auto_close

Approval is stored in DB. A separate API endpoint is polled or
a webhook signals approval/rejection.
"""
import uuid
import logging
from typing import Any, Dict, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import HITLApproval
from agents.security_agent import SecurityReviewAgent

logger = logging.getLogger(__name__)


# ── Graph State ───────────────────────────────────────────────────────────────

class HITLState(TypedDict):
    repo_id: str
    pr_number: Optional[int]
    github_token: Optional[str]
    findings: list
    overall_risk: str
    summary: str
    approval_id: str
    approval_status: str          # pending | approved | rejected
    comment_posted: bool


# ── Node functions ────────────────────────────────────────────────────────────

async def run_security_scan(state: HITLState, db: AsyncSession) -> HITLState:
    """Run security agent and populate findings."""
    agent = SecurityReviewAgent(db)
    result = await agent.review(state["repo_id"])
    return {
        **state,
        "findings": result.get("findings", []),
        "overall_risk": result.get("overall_risk", "low"),
        "summary": result.get("summary", ""),
    }


async def create_approval_request(state: HITLState, db: AsyncSession) -> HITLState:
    """Persist an approval record so a human can act on it."""
    approval_id = str(uuid.uuid4())
    high_findings = [
        f for f in state["findings"]
        if f.get("severity", "").upper() in ("CRITICAL", "HIGH")
    ]
    approval = HITLApproval(
        id=approval_id,
        repo_id=state["repo_id"],
        pr_number=state.get("pr_number"),
        findings=high_findings,
        overall_risk=state["overall_risk"],
        summary=state["summary"],
        status="pending",
    )
    db.add(approval)
    await db.commit()
    logger.info(f"[HITL] Created approval request {approval_id}")
    return {**state, "approval_id": approval_id, "approval_status": "pending"}


async def check_approval(state: HITLState, db: AsyncSession) -> HITLState:
    """Read current approval status from DB."""
    result = await db.execute(
        select(HITLApproval).where(HITLApproval.id == state["approval_id"])
    )
    approval = result.scalar_one_or_none()
    status = approval.status if approval else "rejected"
    return {**state, "approval_status": status}


async def post_github_comment(state: HITLState, db: AsyncSession) -> HITLState:
    """Post security findings as a GitHub PR comment after approval."""
    if not state.get("pr_number") or not state.get("github_token"):
        logger.warning("[HITL] No PR number or token — skipping GitHub comment")
        return {**state, "comment_posted": False}

    try:
        import httpx
        from config import get_settings
        settings = get_settings()

        # Parse repo owner/name from repo_id  — lookup in DB would be ideal
        # For simplicity we read it from the approval record
        result = await db.execute(
            select(HITLApproval).where(HITLApproval.id == state["approval_id"])
        )
        approval = result.scalar_one_or_none()

        body = _format_comment(state["findings"], state["overall_risk"], state["summary"])

        # We need the repo full_name; stored in approval.repo_full_name if available
        repo_full_name = getattr(approval, "repo_full_name", None)
        if not repo_full_name:
            logger.warning("[HITL] repo_full_name missing — cannot post comment")
            return {**state, "comment_posted": False}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/repos/{repo_full_name}/issues/{state['pr_number']}/comments",
                headers={
                    "Authorization": f"Bearer {state['github_token']}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={"body": body},
                timeout=15,
            )
            resp.raise_for_status()

        # Mark approval as acted upon
        if approval:
            approval.comment_posted = True
            await db.commit()

        logger.info(f"[HITL] Posted GitHub comment on PR #{state['pr_number']}")
        return {**state, "comment_posted": True}

    except Exception as e:
        logger.error(f"[HITL] Failed to post GitHub comment: {e}")
        return {**state, "comment_posted": False}


def _format_comment(findings: list, risk: str, summary: str) -> str:
    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(risk.lower(), "⚪")
    lines = [
        f"## {emoji} Security Review — Risk: **{risk.upper()}**",
        f"\n{summary}\n",
        "### High / Critical Findings\n",
    ]
    for f in findings[:10]:
        lines.append(
            f"- **{f.get('severity', '')} — {f.get('category', '')}** "
            f"(`{f.get('file', '')}` line {f.get('line', '?')})\n"
            f"  {f.get('explanation', '')}"
        )
    lines.append("\n> _Posted by AI Engineering Copilot HITL Workflow_")
    return "\n".join(lines)


# ── Router ────────────────────────────────────────────────────────────────────

def severity_router(state: HITLState) -> Literal["needs_approval", "auto_close"]:
    risk = state.get("overall_risk", "low").lower()
    high_count = sum(
        1 for f in state.get("findings", [])
        if f.get("severity", "").upper() in ("CRITICAL", "HIGH")
    )
    if risk in ("critical", "high") or high_count >= 1:
        return "needs_approval"
    return "auto_close"


def approval_router(state: HITLState) -> Literal["approved", "pending", "rejected"]:
    return state.get("approval_status", "pending")  # type: ignore


# ── Graph Builder ─────────────────────────────────────────────────────────────

def build_hitl_graph(db: AsyncSession):
    """Build and compile the HITL LangGraph. db is injected via closures."""

    async def _scan(s):      return await run_security_scan(s, db)
    async def _approval(s):  return await create_approval_request(s, db)
    async def _check(s):     return await check_approval(s, db)
    async def _comment(s):   return await post_github_comment(s, db)
    def _no_action(s):       return {**s, "comment_posted": False}

    graph = StateGraph(HITLState)
    graph.add_node("security_scan",       _scan)
    graph.add_node("create_approval",     _approval)
    graph.add_node("check_approval",      _check)
    graph.add_node("post_comment",        _comment)
    graph.add_node("auto_close",          _no_action)

    graph.set_entry_point("security_scan")
    graph.add_conditional_edges("security_scan", severity_router, {
        "needs_approval": "create_approval",
        "auto_close":     "auto_close",
    })
    graph.add_edge("create_approval", "check_approval")
    graph.add_conditional_edges("check_approval", approval_router, {
        "approved": "post_comment",
        "pending":  END,          # caller must re-invoke after human acts
        "rejected": "auto_close",
    })
    graph.add_edge("post_comment", END)
    graph.add_edge("auto_close",   END)

    return graph.compile()
