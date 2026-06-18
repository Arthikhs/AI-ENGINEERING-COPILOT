"""
Reviewer Agent — synthesizes outputs from multiple specialist agents.
Runs before the Response Agent when 2+ specialists were invoked.
Produces a coherent, cross-referenced review of all findings.
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from agents.state import AgentState
from agents.model_router_agent import routed_invoke
import logging

logger = logging.getLogger(__name__)

REVIEWER_PROMPT = """You are a senior engineering lead reviewing outputs from multiple AI agents.

Your job is to:
1. Cross-reference findings across agents (e.g. security issues in refactoring candidates)
2. Identify contradictions or overlaps
3. Prioritize the most critical findings
4. Surface connections that individual agents may have missed
5. Produce a structured synthesis

Output format:
CROSS_REFERENCES:
<list any connections between agent findings>

PRIORITY_FINDINGS:
<ranked list of most important issues/insights>

SYNTHESIS:
<2-3 paragraph coherent synthesis of all agent outputs>

RECOMMENDED_ACTIONS:
<numbered list of concrete next steps>
"""


class ReviewerAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self, state: AgentState) -> AgentState:
        """Synthesize outputs from all specialist agents that ran before this."""
        agent_outputs = state.get("agent_outputs", {})
        question = state["question"]

        # Collect specialist outputs (exclude retriever, reviewer, response)
        specialist_outputs = {
            k: v for k, v in agent_outputs.items()
            if k not in ("retriever", "reviewer", "response")
        }

        if not specialist_outputs:
            state["agent_outputs"]["reviewer"] = {"synthesis": "No specialist outputs to review."}
            return state

        # Build summary of each agent's output
        summaries = []
        for agent_name, output in specialist_outputs.items():
            if isinstance(output, dict):
                summary = output.get("answer") or output.get("summary") or output.get("synthesis", "")
                if not summary and "findings" in output:
                    findings = output["findings"]
                    summary = f"{len(findings)} findings: " + "; ".join(
                        f.get("description", "")[:80] for f in findings[:3]
                    )
                if not summary:
                    summary = str(output)[:300]
            else:
                summary = str(output)[:300]
            summaries.append(f"=== {agent_name.upper()} AGENT OUTPUT ===\n{summary}")

        combined = "\n\n".join(summaries)

        messages = [
            SystemMessage(content=REVIEWER_PROMPT),
            HumanMessage(content=(
                f"Original question: {question}\n\n"
                f"Agent outputs to review:\n\n{combined}"
            )),
        ]

        result = await routed_invoke(
            task_type="architecture",
            messages=messages,
        )
        raw = result["response"].content

        state["agent_outputs"]["reviewer"] = {
            "cross_references": self._extract_section(raw, "CROSS_REFERENCES:"),
            "priority_findings": self._extract_section(raw, "PRIORITY_FINDINGS:"),
            "synthesis": self._extract_section(raw, "SYNTHESIS:"),
            "recommended_actions": self._extract_section(raw, "RECOMMENDED_ACTIONS:"),
            "full_review": raw,
        }

        logger.info(f"ReviewerAgent: synthesized {len(specialist_outputs)} agent outputs")
        return state

    def _extract_section(self, text: str, marker: str) -> str:
        if marker not in text:
            return ""
        parts = text.split(marker, 1)
        if len(parts) < 2:
            return ""
        # Take content until next section marker
        section = parts[1]
        for next_marker in ["CROSS_REFERENCES:", "PRIORITY_FINDINGS:", "SYNTHESIS:", "RECOMMENDED_ACTIONS:"]:
            if next_marker != marker and next_marker in section:
                section = section.split(next_marker)[0]
        return section.strip()
