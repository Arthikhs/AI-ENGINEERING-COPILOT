"""
Agent Memory Service
Stores conversation history per user+repo for contextual follow-ups.
"Continue our previous architecture discussion."
"What about the token refresh logic?" (after asking about AuthService)
"""
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import Message, Conversation
import logging

logger = logging.getLogger(__name__)

MAX_MEMORY_MESSAGES = 10


class AgentMemory:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_memory(
        self, user_id: str, repo_id: str, conversation_id: str = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recent conversation turns for context injection."""
        if conversation_id:
            query = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(MAX_MEMORY_MESSAGES)
            )
        else:
            query = (
                select(Message)
                .join(Conversation)
                .where(
                    Conversation.user_id == user_id,
                    Conversation.repo_id == repo_id,
                )
                .order_by(Message.created_at.desc())
                .limit(MAX_MEMORY_MESSAGES)
            )

        result = await self.db.execute(query)
        messages = list(reversed(result.scalars().all()))
        return [{"role": m.role, "content": m.content[:500]} for m in messages]

    def format_for_prompt(self, memory: List[Dict]) -> str:
        if not memory:
            return ""
        lines = ["=== Previous Conversation ==="]
        for m in memory:
            role = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{role}: {m['content']}")
        lines.append("=== End of Previous Conversation ===\n")
        return "\n".join(lines)

    # alias used by qa_agent.py
    def format_memory_for_prompt(self, memory: List[Dict]) -> str:
        return self.format_for_prompt(memory)
