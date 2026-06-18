from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from agents.state import AgentState
from agents.memory import AgentMemory
from agents.model_router_agent import routed_invoke
from rag.vector_store import VectorStore
import logging

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """You are an expert software engineering assistant with deep knowledge of codebases.
You answer questions about the code by analyzing the retrieved code snippets.

Guidelines:
- Be precise and cite specific files/functions when relevant
- Explain complex logic clearly
- If you find security concerns, mention them
- Format code references as `file_path:line_number`
- If context is insufficient, say so rather than guessing
- Use the previous conversation history (if provided) to maintain continuity
"""


class QAAgent:
    def __init__(self, db: AsyncSession, vector_store: VectorStore, llm=None):
        # llm param kept for backward compat but ignored — router selects model
        self.db = db
        self.vector_store = vector_store

    async def run(self, state: AgentState) -> AgentState:
        question = state["question"]
        repo_id = state["repo_id"]

        chunks = await self.vector_store.similarity_search(
            query=question, repo_id=repo_id, limit=10
        )

        if not chunks:
            state["answer"] = "No relevant code found in the repository for your question."
            state["agent_type"] = "qa"
            state["sources"] = []
            return state

        context_parts = []
        for chunk in chunks:
            header = f"File: {chunk['file_path']}"
            if chunk.get("chunk_name"):
                header += f" | {chunk['chunk_type']}: {chunk['chunk_name']}"
            context_parts.append(f"{header}\n```\n{chunk['content']}\n```")
        context = "\n\n---\n\n".join(context_parts)

        memory_text = ""
        memory = state.get("memory") or []
        if memory:
            memory_svc = AgentMemory(self.db)
            memory_text = memory_svc.format_memory_for_prompt(memory) + "\n\n"

        result = await routed_invoke(
            task_type="simple_qa",
            messages=[
                SystemMessage(content=QA_SYSTEM_PROMPT),
                HumanMessage(content=f"{memory_text}Codebase Context:\n{context}\n\nQuestion: {question}"),
            ],
        )

        state["answer"] = result["response"].content
        state["agent_type"] = "qa"
        state["context"] = context
        state["retrieved_chunks"] = chunks
        state["model_used"] = result["model"]
        state["latency_ms"] = result["latency_ms"]
        state["estimated_cost_usd"] = result["estimated_cost_usd"]
        state["sources"] = [
            {
                "file_path": c["file_path"],
                "chunk_name": c.get("chunk_name"),
                "similarity": c["similarity"],
            }
            for c in chunks[:5]
        ]
        return state
