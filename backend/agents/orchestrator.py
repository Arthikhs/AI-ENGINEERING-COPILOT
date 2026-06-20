"""
Multi-Agent LangGraph Orchestrator
Routes to: QA | Architecture | KnowledgeGraph | Security |
           Refactor | TestGen | SystemDesign | Search
With: Memory injection + intent detection
"""
from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.qa_agent import QAAgent
from agents.architecture_agent import ArchitectureAgent
from agents.knowledge_graph_agent import KnowledgeGraphAgent
from agents.security_agent import SecurityReviewAgent
from agents.refactoring_agent import RefactoringAgent
from agents.test_generation_agent import TestGenerationAgent
from agents.system_design_agent import SystemDesignAgent
from agents.memory import AgentMemory
from rag.vector_store import VectorStore
from rag.hybrid_retriever import HybridRetriever
from agents.model_router_agent import routed_invoke, route_model
import logging

logger = logging.getLogger(__name__)

# ── Intent keyword maps ───────────────────────────────────────────────────────
KG_KW       = ["which services", "who depends", "depends on", "cross-repo",
                "all repositories", "microservice", "shared library",
                "service map", "inter-service", "across repos"]
ARCH_KW     = ["architecture", "structure", "layers", "diagram", "flow"]
SECURITY_KW = ["security", "vulnerability", "injection", "xss", "ssrf",
               "secret", "hardcoded", "auth flaw", "exploit", "cve"]
REFACTOR_KW = ["refactor", "code smell", "duplicate code", "large class",
               "long method", "dead code", "clean up", "improve code"]
TEST_KW     = ["generate test", "write test", "unit test", "junit",
               "pytest", "jest", "mock", "test for"]
DESIGN_KW   = ["explain flow", "system design", "draw diagram",
               "mermaid", "plantuml", "sequence diagram", "how does.*flow"]
SEARCH_KW   = ["find", "search", "where is", "show all", "locate",
               "which files", "find all"]


class AgentOrchestrator:
    def __init__(self, db: AsyncSession, user_id: str = ""):
        self.db = db
        self.user_id = user_id
        self.vector_store = VectorStore(db)
        self.memory = AgentMemory(db)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("detect_intent",       self._detect_intent)
        graph.add_node("qa_agent",             QAAgent(self.db, self.vector_store).run)
        graph.add_node("architecture_agent",   ArchitectureAgent(db=self.db).run_graph)
        graph.add_node("knowledge_graph_agent",self._run_kg_agent)
        graph.add_node("security_agent",       SecurityReviewAgent(db=self.db).run_graph)
        graph.add_node("refactor_agent",       RefactoringAgent(db=self.db).run_graph)
        graph.add_node("test_gen_agent",       TestGenerationAgent(db=self.db).run_graph)
        graph.add_node("system_design_agent",  SystemDesignAgent(db=self.db).run_graph)
        graph.add_node("search_agent",         self._run_search_agent)

        graph.set_entry_point("detect_intent")
        graph.add_conditional_edges(
            "detect_intent",
            lambda s: s["intent"],
            {
                "qa":             "qa_agent",
                "architecture":   "architecture_agent",
                "knowledge_graph":"knowledge_graph_agent",
                "security":       "security_agent",
                "refactor":       "refactor_agent",
                "test_gen":       "test_gen_agent",
                "system_design":  "system_design_agent",
                "search":         "search_agent",
            },
        )
        for node in ["qa_agent","architecture_agent","knowledge_graph_agent",
                     "security_agent","refactor_agent","test_gen_agent",
                     "system_design_agent","search_agent"]:
            graph.add_edge(node, END)

        return graph.compile()

    async def _detect_intent(self, state: AgentState) -> AgentState:
        q = state["question"].lower()
        if   any(kw in q for kw in KG_KW):       state["intent"] = "knowledge_graph"
        elif any(kw in q for kw in SECURITY_KW):  state["intent"] = "security"
        elif any(kw in q for kw in REFACTOR_KW):  state["intent"] = "refactor"
        elif any(kw in q for kw in TEST_KW):       state["intent"] = "test_gen"
        elif any(kw in q for kw in DESIGN_KW):     state["intent"] = "system_design"
        elif any(kw in q for kw in SEARCH_KW):     state["intent"] = "search"
        elif any(kw in q for kw in ARCH_KW):       state["intent"] = "architecture"
        else:                                       state["intent"] = "qa"
        return state

    async def _run_kg_agent(self, state: AgentState) -> AgentState:
        agent = KnowledgeGraphAgent(db=self.db)
        result = await agent.query(state["question"], state["user_id"])
        state["answer"] = result["answer"]
        state["agent_type"] = "knowledge_graph"
        state["sources"] = result.get("sources", [])
        return state

    async def _run_search_agent(self, state: AgentState) -> AgentState:
        """Hybrid RAG semantic search — returns top results formatted."""
        from rag.hybrid_retriever import HybridRetriever
        retriever = HybridRetriever(self.db)
        chunks = await retriever.retrieve(state["question"], state["repo_id"], top_k=10)

        if not chunks:
            state["answer"] = "No results found."
            state["agent_type"] = "search"
            state["sources"] = []
            return state

        # Format search results
        lines = [f"### 🔍 Search Results for: `{state['question']}`\n"]
        for i, c in enumerate(chunks, 1):
            score = c.get("rerank_score") or c.get("score", 0)
            lines.append(
                f"**{i}. `{c['file_path']}`**"
                + (f" → `{c['chunk_name']}`" if c.get("chunk_name") else "")
                + f" *(relevance: {score:.2f}, source: {c.get('retrieval_source','hybrid')})*\n"
                + f"```{(c.get('language') or '').lower()}\n{c['content'][:300]}\n```\n"
            )

        state["answer"] = "\n".join(lines)
        state["agent_type"] = "search"
        state["sources"] = [
            {"file_path": c["file_path"], "chunk_name": c.get("chunk_name"),
             "similarity": c.get("rerank_score") or c.get("score", 0)}
            for c in chunks
        ]
        return state

    async def run(
        self, question: str, repo_id: str,
        user_id: str = "", conversation_id: str = None
    ) -> Dict[str, Any]:
        # Inject memory
        mem = await self.memory.get_memory(user_id, repo_id, conversation_id)

        initial_state = AgentState(
            question=question,
            repo_id=repo_id,
            user_id=user_id,
            intent="",
            retrieved_chunks=[],
            context=self.memory.format_for_prompt(mem),
            answer="",
            sources=[],
            agent_type="",
            token_usage={},
            memory=mem,
            error=None,
            plan=[],
            agent_outputs={},
            retriever_chunks=[],
            model_used="",
            latency_ms=0,
            estimated_cost_usd=0.0,
        )
        result = await self.graph.ainvoke(initial_state)
        return {
            "content":             result["answer"],
            "agent_type":          result["agent_type"],
            "sources":             result["sources"],
            "intent":              result["intent"],
            "token_usage":         result.get("token_usage", {}),
            "model_used":          result.get("model_used", route_model(result.get("intent", "qa"))),
            "latency_ms":          result.get("latency_ms", 0),
            "estimated_cost_usd":  result.get("estimated_cost_usd", 0.0),
        }

    async def stream(
        self, question: str, repo_id: str,
        user_id: str = "", conversation_id: str = None
    ) -> AsyncGenerator[dict, None]:
        mem = await self.memory.get_memory(user_id, repo_id, conversation_id)

        initial_state = AgentState(
            question=question,
            repo_id=repo_id,
            user_id=user_id,
            intent="",
            retrieved_chunks=[],
            context=self.memory.format_for_prompt(mem),
            answer="",
            sources=[],
            agent_type="",
            token_usage={},
            memory=mem,
            error=None,
            plan=[],
            agent_outputs={},
            retriever_chunks=[],
            model_used="",
            latency_ms=0,
            estimated_cost_usd=0.0,
        )
        async for event in self.graph.astream_events(initial_state, version="v1"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {"type": "token", "content": chunk.content}
            elif event["event"] == "on_chain_end" and event["name"] == "LangGraph":
                output = event["data"].get("output", {})
                yield {
                    "type":       "done",
                    "agent_type": output.get("agent_type", "qa"),
                    "sources":    output.get("sources", []),
                    "intent":     output.get("intent", "qa"),
                }
