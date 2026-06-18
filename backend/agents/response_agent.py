"""
Response Agent — always the final node in the multi-agent pipeline.
Composes a single, polished answer from all agent outputs.
Without this agent, responses from multiple specialists are fragmented.
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from agents.state import AgentState
from agents.memory import AgentMemory
from agents.model_router_agent import routed_invoke
import logging

logger = logging.getLogger(__name__)

RESPONSE_PROMPT = """You are the final Response Agent in a multi-agent AI engineering assistant.

Your job is to compose a single, clear, well-structured answer for the user.

You will receive:
- The original user question
- Outputs from specialist agents (retriever, code, architecture, security, refactor, reviewer, etc.)
- Conversation memory (if any)

Guidelines:
- Synthesize all relevant information into ONE cohesive response
- Lead with the direct answer to the question
- Use markdown formatting (headers, code blocks, bullet points)
- Cite specific files/functions using `file_path:function_name` format
- Include the most important findings from each agent that ran
- If the reviewer agent ran, incorporate its priority findings and synthesis
- Be comprehensive but concise — no padding, no repetition
- End with actionable next steps if relevant
"""


class ResponseAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self, state: AgentState) -> AgentState:
        """Compose the final unified response."""
        question = state["question"]
        agent_outputs = state.get("agent_outputs", {})
        memory = state.get("memory", [])

        # Build context from all agent outputs
        sections = []

        # Retriever context
        retriever_out = agent_outputs.get("retriever", {})
        if retriever_out:
            files = retriever_out.get("relevant_files", [])
            methods = retriever_out.get("relevant_methods", [])
            if files:
                sections.append(f"RETRIEVED FILES:\n" + "\n".join(f"- {f}" for f in files[:8]))
            if methods:
                method_lines = [f"- {m['type']}: {m['name']} in {m['file']}" for m in methods[:6]]
                sections.append("RELEVANT METHODS:\n" + "\n".join(method_lines))

        # Code agent output
        code_out = agent_outputs.get("code", {})
        if code_out and isinstance(code_out, dict):
            answer = code_out.get("answer", "")
            if answer:
                sections.append(f"CODE ANALYSIS:\n{answer[:1500]}")

        # Architecture output
        arch_out = agent_outputs.get("architecture", {})
        if arch_out and isinstance(arch_out, dict):
            summary = arch_out.get("summary") or arch_out.get("answer", "")
            if summary:
                sections.append(f"ARCHITECTURE:\n{summary[:800]}")

        # Security output
        sec_out = agent_outputs.get("security", {})
        if sec_out and isinstance(sec_out, dict):
            findings = sec_out.get("findings", [])
            summary = sec_out.get("summary", "")
            if findings:
                items = [f"- [{f.get('severity')}] {f.get('category')}: {f.get('explanation', '')[:100]}"
                         for f in findings[:5]]
                sections.append("SECURITY FINDINGS:\n" + "\n".join(items))
            elif summary:
                sections.append(f"SECURITY:\n{summary[:500]}")

        # Refactoring output
        refactor_out = agent_outputs.get("refactor", {})
        if refactor_out and isinstance(refactor_out, dict):
            suggestions = refactor_out.get("suggestions", [])
            plan = refactor_out.get("refactoring_plan", [])
            if suggestions:
                items = [f"- [{s.get('severity')}] {s.get('issue')} in {s.get('location', s.get('file', ''))}"
                         for s in suggestions[:5]]
                sections.append("REFACTORING:\n" + "\n".join(items))
            if plan:
                sections.append("REFACTORING PLAN:\n" + "\n".join(f"{i+1}. {p}" for i, p in enumerate(plan[:5])))

        # Test generation output
        test_out = agent_outputs.get("test_gen", {})
        if test_out and isinstance(test_out, dict):
            test_code = test_out.get("test_code", "")
            if test_code:
                sections.append(f"GENERATED TESTS ({test_out.get('language', '')}):\n```\n{test_code[:800]}\n```")

        # System design output
        design_out = agent_outputs.get("system_design", {})
        if design_out and isinstance(design_out, dict):
            mermaid = design_out.get("mermaid", "")
            explanation = design_out.get("explanation", "")
            if mermaid:
                sections.append(f"SYSTEM DESIGN:\n```mermaid\n{mermaid}\n```")
            if explanation:
                sections.append(f"DESIGN EXPLANATION:\n{explanation[:500]}")

        # Documentation output
        doc_out = agent_outputs.get("documentation", {})
        if doc_out and isinstance(doc_out, dict):
            summary = doc_out.get("summary", "")
            readme = doc_out.get("readme", "")
            if summary:
                sections.append(f"DOCUMENTATION SUMMARY:\n{summary[:600]}")
            elif readme:
                sections.append(f"GENERATED README:\n{readme[:800]}")

        # Reviewer synthesis (highest priority — use this as primary context)
        reviewer_out = agent_outputs.get("reviewer", {})
        if reviewer_out and isinstance(reviewer_out, dict):
            synthesis = reviewer_out.get("synthesis", "")
            priority = reviewer_out.get("priority_findings", "")
            actions = reviewer_out.get("recommended_actions", "")
            if synthesis:
                sections.insert(0, f"CROSS-AGENT SYNTHESIS:\n{synthesis[:1000]}")
            if priority:
                sections.append(f"PRIORITY FINDINGS:\n{priority[:600]}")
            if actions:
                sections.append(f"RECOMMENDED ACTIONS:\n{actions[:400]}")

        # Memory context
        memory_text = ""
        if memory:
            memory_svc = AgentMemory(self.db)
            memory_text = memory_svc.format_memory_for_prompt(memory) + "\n\n"

        combined_context = "\n\n".join(sections)
        agents_used = [k for k in agent_outputs.keys() if k != "response"]

        messages = [
            SystemMessage(content=RESPONSE_PROMPT),
            HumanMessage(content=(
                f"{memory_text}"
                f"Agents that ran: {', '.join(agents_used)}\n\n"
                f"Agent outputs:\n{combined_context}\n\n"
                f"User question: {question}\n\n"
                f"Compose the final answer:"
            )),
        ]

        result = await routed_invoke(
            task_type="simple_qa",
            messages=messages,
            temperature=0.1,
        )
        response = result["response"]

        state["answer"] = response.content
        state["agent_type"] = "multi_agent"
        state["model_used"] = result["model"]
        state["latency_ms"] = result["latency_ms"]
        state["estimated_cost_usd"] = result["estimated_cost_usd"]

        logger.info(f"ResponseAgent: final answer composed from {len(agents_used)} agent(s)")
        return state
