"""
Code Understanding Agent — uses Model Router (architecture task → gpt-4o)
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from agents.state import AgentState
from agents.model_router_agent import routed_invoke
import logging

logger = logging.getLogger(__name__)

CODE_PROMPT = """You are an expert software engineer performing deep code analysis.

Given the retrieved code context and the user's question, provide:

1. DIRECT_ANSWER: Direct answer to the question
2. CODE_FLOW: Step-by-step trace of the relevant code flow
3. KEY_COMPONENTS: List of key classes/functions involved with file paths
4. DEPENDENCIES: What this code depends on (imports, services, DBs)
5. POTENTIAL_ISSUES: Any bugs, edge cases, or concerns you notice

Format:
DIRECT_ANSWER:
<answer>

CODE_FLOW:
1. Step one
2. Step two

KEY_COMPONENTS:
- `ClassName` in `file_path.py` — description

DEPENDENCIES:
- Dependency 1

POTENTIAL_ISSUES:
- Issue 1 (if any)
"""


class CodeUnderstandingAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self, state: AgentState) -> AgentState:
        context = state.get("context", "")
        question = state["question"]

        if not context:
            state["agent_outputs"]["code"] = {
                "answer": "No code context available.",
                "direct_answer": "", "code_flow": [], "key_components": [],
            }
            return state

        result = await routed_invoke(
            task_type="architecture",
            messages=[
                SystemMessage(content=CODE_PROMPT),
                HumanMessage(content=f"Code context:\n{context[:8000]}\n\nQuestion: {question}"),
            ],
        )
        raw = result["response"].content

        state["agent_outputs"]["code"] = {
            "answer": raw,
            "direct_answer":    self._extract(raw, "DIRECT_ANSWER:"),
            "code_flow":        self._extract_list(raw, "CODE_FLOW:"),
            "key_components":   self._extract_list(raw, "KEY_COMPONENTS:"),
            "dependencies":     self._extract_list(raw, "DEPENDENCIES:"),
            "potential_issues": self._extract_list(raw, "POTENTIAL_ISSUES:"),
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
        }
        return state

    def _extract(self, text: str, marker: str) -> str:
        markers = ["DIRECT_ANSWER:", "CODE_FLOW:", "KEY_COMPONENTS:", "DEPENDENCIES:", "POTENTIAL_ISSUES:"]
        if marker not in text:
            return ""
        content = text.split(marker, 1)[1]
        for m in markers:
            if m != marker and m in content:
                content = content.split(m)[0]
        return content.strip()

    def _extract_list(self, text: str, marker: str) -> list:
        section = self._extract(text, marker)
        if not section:
            return []
        lines = [l.lstrip("0123456789.-• ").strip() for l in section.split("\n") if l.strip()]
        return [l for l in lines if l]
