"""
Slack / Microsoft Teams Integration
Handles incoming slash commands and @mentions from both platforms.

Slack:  Slash command  POST /integrations/slack/command
        Event API      POST /integrations/slack/events
Teams:  Outgoing hook  POST /integrations/teams/message

Command syntax (same for both):
  @copilot review pr #123
  @copilot security <repo>
  @copilot ask <question>
  @copilot status
"""
import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from config import get_settings
from database import get_db
from models.models import Repository, User

router = APIRouter(prefix="/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)
settings = get_settings()


# ── Request / Response schemas ─────────────────────────────────────────────────

class TeamsMessageRequest(BaseModel):
    text: str
    user_name: Optional[str] = None
    channel: Optional[str] = None
    webhook_url: Optional[str] = None   # Teams incoming webhook URL to reply to


class IntegrationConfigRequest(BaseModel):
    slack_bot_token: Optional[str] = None
    slack_signing_secret: Optional[str] = None
    teams_webhook_url: Optional[str] = None


# ── Slack signature verification ───────────────────────────────────────────────

def _verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    signing_secret = getattr(settings, "slack_signing_secret", "")
    if not signing_secret:
        return True   # Skip verification if not configured
    base = f"v0:{timestamp}:{body.decode()}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Command parser ─────────────────────────────────────────────────────────────

def _parse_command(text: str) -> Dict[str, Any]:
    """
    Parse @copilot commands into structured intent.
    Returns: { intent, repo_name, pr_number, question }
    """
    text = text.lower().strip()
    # Strip @copilot prefix if present
    for prefix in ["@copilot", "/copilot", "copilot"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    if text.startswith("review pr") or text.startswith("review #"):
        import re
        m = re.search(r"#?(\d+)", text)
        return {"intent": "pr_review", "pr_number": int(m.group(1)) if m else None}

    if text.startswith("security"):
        parts = text.split(maxsplit=1)
        return {"intent": "security", "repo_name": parts[1] if len(parts) > 1 else None}

    if text.startswith("ask"):
        question = text[3:].strip()
        return {"intent": "ask", "question": question}

    if text.startswith("status"):
        return {"intent": "status"}

    if text.startswith("help"):
        return {"intent": "help"}

    # Fallback: treat everything as a question
    return {"intent": "ask", "question": text}


HELP_TEXT = (
    "*AI Engineering Copilot* — Available commands:\n"
    "• `@copilot review pr #123` — AI review of a pull request\n"
    "• `@copilot security <repo>` — Run security scan\n"
    "• `@copilot ask <question>` — Ask about your codebase\n"
    "• `@copilot status` — Platform health check\n"
    "• `@copilot help` — Show this message"
)


async def _handle_command(
    text: str,
    user_name: str,
    db: AsyncSession,
) -> str:
    """Dispatch command to the correct agent and return a plain-text response."""
    cmd = _parse_command(text)
    intent = cmd["intent"]

    if intent == "help":
        return HELP_TEXT

    if intent == "status":
        return (
            "✅ *AI Engineering Copilot* is healthy.\n"
            "Models: GPT-4o, Claude 3.5 Sonnet, Llama 3\n"
            "Agents: Security, Architecture, PR Review, Q&A"
        )

    if intent == "ask":
        question = cmd.get("question", "")
        if not question:
            return "Please provide a question. Usage: `@copilot ask <your question>`"
        try:
            from agents.model_router_agent import routed_invoke
            from langchain.schema import HumanMessage
            result = await routed_invoke(
                task_type="simple_qa",
                messages=[HumanMessage(content=question)],
            )
            answer = result["response"].content
            model = result["model"]
            latency = result["latency_ms"]
            return f"*Answer* (via {model}, {latency}ms):\n{answer[:1500]}"
        except Exception as e:
            logger.error(f"[Integration] ask failed: {e}")
            return f"❌ Error processing question: {str(e)[:200]}"

    if intent == "pr_review":
        pr_number = cmd.get("pr_number")
        if not pr_number:
            return "Please specify a PR number. Usage: `@copilot review pr #123`"
        # Find the most recently connected repo for this user
        result = await db.execute(
            select(Repository).where(Repository.is_indexed == True).limit(1)
        )
        repo = result.scalar_one_or_none()
        if not repo:
            return "❌ No indexed repository found. Please connect and index a repository first."
        try:
            from agents.pr_review_agent import PRReviewAgent
            agent = PRReviewAgent(
                github_token=getattr(settings, "github_token", ""),
                db=db,
            )
            review = await agent.review(str(repo.id), pr_number)
            risk = review.get("risk_level", "unknown").upper()
            summary = review.get("summary", "No summary available.")
            findings_count = len(review.get("findings", []))
            return (
                f"*PR #{pr_number} Review* — Risk: *{risk}*\n"
                f"{summary}\n"
                f"_{findings_count} finding(s) detected._"
            )
        except Exception as e:
            logger.error(f"[Integration] PR review failed: {e}")
            return f"❌ PR review failed: {str(e)[:200]}"

    if intent == "security":
        repo_name = cmd.get("repo_name")
        result = await db.execute(
            select(Repository).where(Repository.is_indexed == True).limit(1)
        )
        repo = result.scalar_one_or_none()
        if not repo:
            return "❌ No indexed repository found."
        try:
            from agents.security_agent import SecurityReviewAgent
            agent = SecurityReviewAgent(db)
            review = await agent.review(str(repo.id))
            risk = review.get("overall_risk", "unknown").upper()
            summary = review.get("summary", "")
            findings = review.get("findings", [])
            high = [f for f in findings if f.get("severity", "").upper() in ("CRITICAL", "HIGH")]
            return (
                f"*Security Review* — {repo.full_name}\n"
                f"Overall Risk: *{risk}*\n"
                f"{summary}\n"
                f"_{len(high)} high/critical finding(s)._"
            )
        except Exception as e:
            return f"❌ Security scan failed: {str(e)[:200]}"

    return "Unknown command. Type `@copilot help` for available commands."


# ── Slack endpoints ────────────────────────────────────────────────────────────

@router.post("/slack/command")
async def slack_slash_command(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Handle Slack slash commands (/copilot ...)."""
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Replay attack prevention
    if abs(time.time() - float(timestamp or 0)) > 300:
        raise HTTPException(status_code=400, detail="Request too old")

    if not _verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    form = await request.form()
    text = str(form.get("text", ""))
    user_name = str(form.get("user_name", "user"))
    response_url = str(form.get("response_url", ""))

    # Acknowledge immediately (Slack requires < 3s response)
    background_tasks.add_task(
        _slack_deferred_response, text, user_name, response_url, db
    )
    return {"response_type": "ephemeral", "text": "⏳ Processing your request..."}


@router.post("/slack/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Handle Slack Event API (app_mention, message)."""
    payload = await request.json()

    # URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    event = payload.get("event", {})
    event_type = event.get("type", "")

    if event_type in ("app_mention", "message") and not event.get("bot_id"):
        text = event.get("text", "")
        channel = event.get("channel", "")
        user = event.get("user", "user")
        background_tasks.add_task(
            _slack_channel_reply, text, user, channel, db
        )

    return {"ok": True}


# ── Teams endpoint ─────────────────────────────────────────────────────────────

@router.post("/teams/message")
async def teams_message(
    body: TeamsMessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Handle Microsoft Teams outgoing webhook messages."""
    text = body.text or ""
    user_name = body.user_name or "user"
    webhook_url = body.webhook_url or getattr(settings, "teams_webhook_url", "")

    background_tasks.add_task(
        _teams_deferred_response, text, user_name, webhook_url, db
    )
    return {"type": "message", "text": "⏳ Processing your request..."}


# ── Proactive notification helpers ────────────────────────────────────────────

async def notify_slack(message: str, channel: str = "") -> bool:
    """Send a proactive message to a Slack channel."""
    bot_token = getattr(settings, "slack_bot_token", "")
    default_channel = getattr(settings, "slack_default_channel", "#engineering")
    if not bot_token:
        logger.warning("[Slack] Bot token not configured")
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}"},
                json={"channel": channel or default_channel, "text": message},
                timeout=10,
            )
        return resp.json().get("ok", False)
    except Exception as e:
        logger.error(f"[Slack] notify failed: {e}")
        return False


async def notify_teams(message: str, webhook_url: str = "") -> bool:
    """Send a proactive message to a Teams channel via incoming webhook."""
    url = webhook_url or getattr(settings, "teams_webhook_url", "")
    if not url:
        logger.warning("[Teams] Webhook URL not configured")
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"text": message},
                timeout=10,
            )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"[Teams] notify failed: {e}")
        return False


# ── Config endpoint ────────────────────────────────────────────────────────────

@router.post("/test-command")
async def test_command(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Test a copilot command directly without Slack/Teams."""
    body = await request.json()
    text = body.get("text", "")
    answer = await _handle_command(text, "test-user", db)
    return {"response": answer}
async def get_integration_config(current_user: User = Depends(get_current_user)):
    """Return which integrations are currently configured."""
    return {
        "slack": {
            "configured": bool(getattr(settings, "slack_bot_token", "")),
            "signing_secret": bool(getattr(settings, "slack_signing_secret", "")),
            "default_channel": getattr(settings, "slack_default_channel", ""),
        },
        "teams": {
            "configured": bool(getattr(settings, "teams_webhook_url", "")),
        },
        "commands": [
            "@copilot review pr #<number>",
            "@copilot security <repo>",
            "@copilot ask <question>",
            "@copilot status",
            "@copilot help",
        ],
    }


# ── Background helpers ─────────────────────────────────────────────────────────

async def _slack_deferred_response(text: str, user: str, response_url: str, db: AsyncSession):
    answer = await _handle_command(text, user, db)
    if not response_url:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                response_url,
                json={"response_type": "in_channel", "text": answer},
                timeout=10,
            )
    except Exception as e:
        logger.error(f"[Slack] deferred response failed: {e}")


async def _slack_channel_reply(text: str, user: str, channel: str, db: AsyncSession):
    answer = await _handle_command(text, user, db)
    await notify_slack(f"<@{user}> {answer}", channel)


async def _teams_deferred_response(text: str, user: str, webhook_url: str, db: AsyncSession):
    answer = await _handle_command(text, user, db)
    await notify_teams(f"**{user}**: {answer}", webhook_url)
