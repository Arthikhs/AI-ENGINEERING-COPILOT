"""
Multi-Agent Orchestrator
Full LangGraph pipeline:

User Query
    │
    ▼
Planner Agent  (decides which agents + order)
    │
    ▼
Retriever Agent  (hybrid BM25 + Vector + Reranker)
    │
    ├──────────────┬──────────────┬──────────────┐
    ▼              ▼              ▼              ▼
Code Agent   Architecture   Security      Refactor/TestGen/
             Agent          Agent         Design/Docs Agent
    └──────────────┴──────────────┴──────────────┘
                          │
                          ▼
                   Reviewer Agent  (if 2+ specialists)
                          │
                          ▼
                   Response Agent  (always last)
"""
from typing import AsyncGenerator, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.planner_agent import PlannerAgent
from agents.retriever_agent import RetrieverAgent
from agents.code_agent import CodeUnderstandingAgent
from agents.architecture_agent import ArchitectureAgent
from agents.security_agent import SecurityReviewAgent
from agents.refactoring_agent import RefactoringAgent
from agents.test_generation_agent import TestGenerationAgent
from agents.system_design_agent import SystemDesignAgent
from agents.documentation_agent import DocumentationAgent
from agents.reviewer_agent import ReviewerAgent
from agents.response_agent import ResponseAgent
from agents.memory import AgentMemory
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# All specialist agent names that can appear in a plan
SPECIALIST_AGENTS = {
    "code", "architecture", "security", "refactor",
    "test_gen", "system_design", "documentation",
}


class MultiAgentOrchestrator:
    def __init__(self, db: AsyncSession, user_id: str = ""):
        self.db = db
        self.user_id = user_id
        self._agents = self._init_agents()
        self.graph = self._build_graph()

    def _init_agents(self) -> Dict[str, Any]:
        return {
            "planner":       PlannerAgent(self.db),
            "retriever":     RetrieverAgent(self.db),
            "code":          CodeUnderstandingAgent(self.db),
            "architecture":  ArchitectureAgent(self.db),
            "security":      SecurityReviewAgent(self.db),
            "refactor":      RefactoringAgent(self.db),
            "test_gen":      TestGenerationAgent(self.db),
            "system_design": SystemDesignAgent(self.db),
            "documentation": DocumentationAgent(self.db),
            "reviewer":      ReviewerAgent(self.db),
            "response":      ResponseAgent(self.db),
        }

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        # ── Nodes ──────────────────────────────────────────────────────────
        graph.add_node("planner",       self._agents["planner"].plan)
        graph.add_node("inject_memory", self._inject_memory)
        graph.add_node("retriever",     self._agents["retriever"].run)
        graph.add_node("code",          self._agents["code"].run)
        graph.add_node("architecture",  self._run_architecture)
        graph.add_node("security",      self._run_security)
        graph.add_node("refactor",      self._run_refactor)
        graph.add_node("test_gen",      self._run_test_gen)
        graph.add_node("system_design", self._run_system_design)
        graph.add_node("documentation", self._agents["documentation"].run)
        graph.add_node("reviewer",      self._agents["reviewer"].run)
        graph.add_node("response",      self._agents["response"].run)

        # ── Entry ──────────────────────────────────────────────────────────
        graph.set_entry_point("planner")
        graph.add_edge("planner", "inject_memory")
        graph.add_edge("inject_memory", "retriever")

        # After retriever: route to first specialist in plan
        graph.add_conditional_edges(
            "retriever",
            self._next_after_retriever,
            {
                "code":          "code",
                "architecture":  "architecture",
                "security":      "security",
                "refactor":      "refactor",
                "test_gen":      "test_gen",
                "system_design": "system_design",
                "documentation": "documentation",
                "reviewer":      "reviewer",
                "response":      "response",
            },
        )

        # Each specialist routes to next planned step
        for specialist in SPECIALIST_AGENTS:
            graph.add_conditional_edges(
                specialist,
                self._route_next,
                {
                    "code":          "code",
                    "architecture":  "architecture",
                    "security":      "security",
                    "refactor":      "refactor",
                    "test_gen":      "test_gen",
                    "system_design": "system_design",
                    "documentation": "documentation",
                    "reviewer":      "reviewer",
                    "response":      "response",
                },
            )

        graph.add_conditional_edges(
            "reviewer",
            self._route_next,
            {"response": "response"},
        )
        graph.add_edge("response", END)

        return graph.compile()

    # ── Routing helpers ────────────────────────────────────────────────────

    def _next_after_retriever(self, state: AgentState) -> str:
        """After retriever, go to first specialist (or reviewer/response)."""
        plan = state.get("plan", [])
        # Find first item after "retriever" in plan
        try:
            idx = plan.index("retriever")
            return plan[idx + 1] if idx + 1 < len(plan) else "response"
        except ValueError:
            return "response"

    def _route_next(self, state: AgentState) -> str:
        """Route to next agent in the plan after current one completes."""
        plan = state.get("plan", [])
        outputs = state.get("agent_outputs", {})
        completed = set(outputs.keys())

        for step in plan:
            if step not in completed and step in {
                "code", "architecture", "security", "refactor",
                "test_gen", "system_design", "documentation",
                "reviewer", "response",
            }:
                return step
        return "response"

    # ── Memory injection ───────────────────────────────────────────────────

    async def _inject_memory(self, state: AgentState) -> AgentState:
        if state.get("user_id"):
            memory_svc = AgentMemory(self.db)
            state["memory"] = await memory_svc.get_memory(
                user_id=state["user_id"],
                repo_id=state["repo_id"],
            )
        return state

    # ── Specialist adapters (store output in agent_outputs) ────────────────

    async def _run_architecture(self, state: AgentState) -> AgentState:
        agent = self._agents["architecture"]
        result = await agent.analyze(state["repo_id"], repo_full_name="")
        state["agent_outputs"]["architecture"] = result
        return state

    async def _run_security(self, state: AgentState) -> AgentState:
        agent = self._agents["security"]
        result = await agent.review(state["repo_id"])
        state["agent_outputs"]["security"] = result
        return state

    async def _run_refactor(self, state: AgentState) -> AgentState:
        agent = self._agents["refactor"]
        result = await agent.analyze(state["repo_id"])
        state["agent_outputs"]["refactor"] = result
        return state

    async def _run_test_gen(self, state: AgentState) -> AgentState:
        agent = self._agents["test_gen"]
        result = await agent.generate(state["repo_id"], state["question"])
        state["agent_outputs"]["test_gen"] = result
        return state

    async def _run_system_design(self, state: AgentState) -> AgentState:
        agent = self._agents["system_design"]
        result = await agent.generate(state["question"], state["repo_id"])
        state["agent_outputs"]["system_design"] = result
        return state

    # ── Public interface ───────────────────────────────────────────────────

    def _make_initial_state(self, question: str, repo_id: str, user_id: str) -> AgentState:
        return AgentState(
            question=question,
            repo_id=repo_id,
            user_id=user_id,
            intent="",
            plan=[],
            agent_outputs={},
            retriever_chunks=[],
            retrieved_chunks=[],
            context="",
            answer="",
            sources=[],
            agent_type="multi_agent",
            token_usage={},
            memory=[],
            error=None,
            model_used="",
            latency_ms=0,
            estimated_cost_usd=0.0,
        )

    async def run(self, question: str, repo_id: str, user_id: str = "") -> Dict[str, Any]:
        state = self._make_initial_state(question, repo_id, user_id)
        result = await self.graph.ainvoke(state)
        return {
            "content": result["answer"],
            "agent_type": "multi_agent",
            "plan": result.get("plan", []),
            "agents_used": list(result.get("agent_outputs", {}).keys()),
            "sources": result.get("sources", []),
            "token_usage": result.get("token_usage", {}),
            "agent_outputs": result.get("agent_outputs", {}),
            "model_used": result.get("model_used", ""),
            "latency_ms": result.get("latency_ms", 0),
            "estimated_cost_usd": result.get("estimated_cost_usd", 0.0),
        }

    async def stream(self, question: str, repo_id: str, user_id: str = "") -> AsyncGenerator[dict, None]:
        state = self._make_initial_state(question, repo_id, user_id)
        async for event in self.graph.astream_events(state, version="v1"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {"type": "token", "content": chunk.content}
            elif event["event"] == "on_chain_end" and event["name"] == "LangGraph":
                output = event["data"].get("output", {})
                yield {
                    "type": "done",
                    "agent_type": "multi_agent",
                    "plan": output.get("plan", []),
                    "agents_used": list(output.get("agent_outputs", {}).keys()),
                    "sources": output.get("sources", []),
                }
