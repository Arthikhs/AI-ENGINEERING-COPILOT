"""
Planner Agent — the "brain" of the multi-agent pipeline.

Receives the user question and decides:
  - Which agents to invoke
  - In what order
  - Whether retrieval is required first

Returns an ordered plan: e.g. ["retriever", "code", "architecture", "reviewer", "response"]

Available agents:
  retriever    — Hybrid RAG search (always first if code context needed)
  code         — Deep code understanding / Q&A
  architecture — Service dependency + layer analysis
  security     — Vulnerability detection
  refactor     — Code smell + refactoring suggestions
  test_gen     — Unit test generation
  system_design— Architecture diagram generation
  documentation— README / API docs / sequence diagram generation
  reviewer     — Synthesizes outputs from multiple agents
  response     — Final answer composition (always last)
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from agents.state import AgentState
from agents.model_router_agent import routed_invoke
import json
import logging

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """You are the Planner Agent in a multi-agent AI engineering assistant.

Your job is to analyze the user's question and produce an ORDERED execution plan
of agents that should handle it.

Available agents and their responsibilities:
- retriever:      Hybrid code search (BM25 + Vector + Reranker). Use when code context is needed.
- code:           Deep code understanding, explain logic, trace call graphs, class relationships.
- architecture:   Service dependency graph, layer analysis, circular dependency detection.
- security:       Detect SQL injection, XSS, hardcoded secrets, auth flaws, SSRF.
- refactor:       Detect large classes, long methods, duplicate code, dead code. Suggest improvements.
- test_gen:       Generate unit tests (pytest/JUnit/Jest) for a function or class.
- system_design:  Generate Mermaid/PlantUML architecture diagrams.
- documentation:  Generate README, API docs, or sequence diagrams.
- reviewer:       Synthesize outputs from multiple agents into coherent insights.
- response:       ALWAYS the final agent. Composes the final answer from all outputs.

Rules:
1. ALWAYS include "response" as the last agent.
2. Include "retriever" first whenever code context is needed (almost always).
3. Include "reviewer" before "response" when 2+ specialist agents are used.
4. Keep the plan minimal — only include agents that are actually needed.
5. For simple Q&A questions: ["retriever", "code", "response"]
6. For complex multi-aspect questions: include multiple specialists + reviewer.

Respond ONLY with a valid JSON object in this exact format:
{
  "plan": ["retriever", "code", "response"],
  "reasoning": "Brief explanation of why these agents were chosen"
}
"""

# Fallback plans for when LLM planning fails
FALLBACK_PLANS: Dict[str, List[str]] = {
    "architecture":   ["retriever", "architecture", "response"],
    "security":       ["retriever", "security", "response"],
    "refactor":       ["retriever", "refactor", "response"],
    "test_gen":       ["retriever", "test_gen", "response"],
    "system_design":  ["retriever", "system_design", "response"],
    "documentation":  ["retriever", "documentation", "response"],
    "complex":        ["retriever", "code", "architecture", "security", "reviewer", "response"],
    "default":        ["retriever", "code", "response"],
}

COMPLEX_KEYWORDS = [
    "explain everything", "full analysis", "complete overview",
    "how does the entire", "analyze the whole", "deep dive",
]


class PlannerAgent:
    def __init__(self, db: AsyncSession, model: str = None):
        self.db = db
        self._model = model  # optional override

    async def plan(self, state: AgentState) -> AgentState:
        """Decide which agents to run and in what order."""
        question = state["question"]

        try:
            result = await routed_invoke(
                task_type="simple_qa",
                messages=[
                    SystemMessage(content=PLANNER_PROMPT),
                    HumanMessage(content=f"User question: {question}"),
                ],
                override_model=self._model,
            )
            parsed = json.loads(result["response"].content)
            plan = parsed.get("plan", [])
            reasoning = parsed.get("reasoning", "")

            # Validate — ensure response is always last
            if not plan or "response" not in plan:
                plan = FALLBACK_PLANS["default"]
            elif plan[-1] != "response":
                plan.append("response")

            logger.info(f"Planner: {plan} | Reason: {reasoning}")
            state["plan"] = plan
            state["agent_outputs"] = {}
            state["agent_type"] = "multi_agent"

        except Exception as e:
            logger.warning(f"Planner LLM failed ({e}), using keyword fallback")
            state["plan"] = self._keyword_fallback(question)
            state["agent_outputs"] = {}
            state["agent_type"] = "multi_agent"

        return state

    def _keyword_fallback(self, question: str) -> List[str]:
        q = question.lower()
        if any(kw in q for kw in COMPLEX_KEYWORDS):
            return FALLBACK_PLANS["complex"]
        if any(kw in q for kw in ["architecture", "structure", "layers", "diagram"]):
            return FALLBACK_PLANS["architecture"]
        if any(kw in q for kw in ["security", "vulnerability", "injection", "xss"]):
            return FALLBACK_PLANS["security"]
        if any(kw in q for kw in ["refactor", "code smell", "duplicate", "dead code"]):
            return FALLBACK_PLANS["refactor"]
        if any(kw in q for kw in ["generate test", "unit test", "write test"]):
            return FALLBACK_PLANS["test_gen"]
        if any(kw in q for kw in ["system design", "mermaid", "plantuml", "flow diagram"]):
            return FALLBACK_PLANS["system_design"]
        if any(kw in q for kw in ["documentation", "readme", "api docs", "document"]):
            return FALLBACK_PLANS["documentation"]
        return FALLBACK_PLANS["default"]
