from typing import Optional, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import json
from models.models import User, Repository, Conversation, Message
from database import get_db
from api.auth import get_current_user
from agents.orchestrator import AgentOrchestrator
from agents.multi_agent_orchestrator import MultiAgentOrchestrator

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    repo_id: str
    message: str
    conversation_id: Optional[str] = None
    mode: str = "simple"   # "simple" | "multi_agent"


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    content: str
    agent_type: str
    sources: list
    model_used: str = ""
    latency_ms: int = 0
    estimated_cost_usd: float = 0.0
    plan: list = []
    agents_used: list = []


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get an AI response."""
    repo = await _get_repo(body.repo_id, current_user.id, db)

    # Get or create conversation
    conversation = await _get_or_create_conversation(
        body.conversation_id, current_user.id, repo.id, body.message, db
    )

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id, role="user", content=body.message
    )
    db.add(user_msg)
    await db.flush()

    # Run agent — simple or multi-agent
    if body.mode == "multi_agent":
        orchestrator = MultiAgentOrchestrator(db, user_id=str(current_user.id))
    else:
        orchestrator = AgentOrchestrator(db, user_id=str(current_user.id))
    result = await orchestrator.run(body.message, str(repo.id), user_id=str(current_user.id))

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result["content"],
        agent_type=result["agent_type"],
        sources=result.get("sources", []),
        token_usage=result.get("token_usage", {}),
    )
    db.add(assistant_msg)
    await db.commit()

    return ChatResponse(
        conversation_id=str(conversation.id),
        message_id=str(assistant_msg.id),
        content=result["content"],
        agent_type=result["agent_type"],
        sources=result.get("sources", []),
        model_used=result.get("model_used", ""),
        latency_ms=result.get("latency_ms", 0),
        estimated_cost_usd=result.get("estimated_cost_usd", 0.0),
        plan=result.get("plan", []),
        agents_used=result.get("agents_used", []),
    )


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream chat response using Server-Sent Events."""
    repo = await _get_repo(body.repo_id, current_user.id, db)

    async def event_generator() -> AsyncGenerator[str, None]:
        if body.mode == "multi_agent":
            orchestrator = MultiAgentOrchestrator(db, user_id=str(current_user.id))
        else:
            orchestrator = AgentOrchestrator(db, user_id=str(current_user.id))
        async for chunk in orchestrator.stream(body.message, str(repo.id), user_id=str(current_user.id)):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/conversations")
async def get_conversations(
    repo_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Conversation).where(Conversation.user_id == current_user.id)
    if repo_id:
        query = query.where(Conversation.repo_id == repo_id)
    result = await db.execute(query.order_by(Conversation.updated_at.desc()))
    convs = result.scalars().all()
    return [{"id": str(c.id), "title": c.title, "created_at": c.created_at} for c in convs]


@router.get("/conversations/{conv_id}/messages")
async def get_messages(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Message)
        .join(Conversation)
        .where(Conversation.id == conv_id, Conversation.user_id == current_user.id)
        .order_by(Message.created_at)
    )
    msgs = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "agent_type": m.agent_type,
            "sources": m.sources,
            "created_at": m.created_at,
        }
        for m in msgs
    ]


async def _get_repo(repo_id: str, user_id, db: AsyncSession) -> Repository:
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.owner_id == user_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not repo.is_indexed:
        raise HTTPException(status_code=400, detail="Repository not yet indexed")
    return repo


async def _get_or_create_conversation(
    conv_id: Optional[str], user_id, repo_id, first_message: str, db: AsyncSession
) -> Conversation:
    if conv_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conv_id, Conversation.user_id == user_id
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    title = first_message[:60] + "..." if len(first_message) > 60 else first_message
    conv = Conversation(user_id=user_id, repo_id=repo_id, title=title)
    db.add(conv)
    await db.flush()
    return conv
