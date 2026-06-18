"""
System Design Agent — uses Model Router (architecture → gpt-4o)
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from rag.hybrid_retriever import HybridRetriever
from agents.state import AgentState
from agents.model_router_agent import routed_invoke
import logging
import re

logger = logging.getLogger(__name__)

SYSTEM_DESIGN_PROMPT = """You are a software architect who generates precise system design diagrams.

Based on the code provided, generate:
1. A Mermaid flowchart diagram showing the flow
2. A PlantUML sequence diagram showing interactions
3. A text explanation

Rules:
- Use ONLY components visible in the code
- Show data flow direction with arrows
- Include databases, queues, external services
- Label each arrow with the operation

Output EXACTLY in this format:

MERMAID:
```mermaid
flowchart TD
    A[Component] --> B[Component]
    B --> C[(Database)]
```

PLANTUML:
```plantuml
@startuml
participant "ComponentA" as A
participant "ComponentB" as B
A -> B: operation()
B --> A: response
@enduml
```

EXPLANATION:
<2-3 paragraph explanation of the flow>

COMPONENTS:
<comma-separated list of all components identified>
"""


class SystemDesignAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)

    async def generate(self, query: str, repo_id: str) -> Dict[str, Any]:
        chunks = await self.retriever.retrieve(query, repo_id, top_k=12)

        if not chunks:
            return {"error": "No relevant code found for diagram generation"}

        context = "\n\n---\n\n".join(
            f"File: {c['file_path']}\n```\n{c['content'][:600]}\n```"
            for c in chunks
        )

        result = await routed_invoke(
            task_type="architecture",
            messages=[
                SystemMessage(content=SYSTEM_DESIGN_PROMPT),
                HumanMessage(content=f"Query: {query}\n\nCode context:\n{context}"),
            ],
        )
        raw = result["response"].content

        return {
            "query": query,
            "mermaid": self._extract_block(raw, "mermaid"),
            "plantuml": self._extract_block(raw, "plantuml"),
            "explanation": self._extract_section(raw, "EXPLANATION:"),
            "components": self._extract_components(raw),
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
            "estimated_cost_usd": result["estimated_cost_usd"],
            "sources": [
                {"file_path": c["file_path"], "chunk_name": c.get("chunk_name")}
                for c in chunks[:6]
            ],
        }

    async def run_graph(self, state: AgentState) -> AgentState:
        result = await self.generate(state["question"], state["repo_id"])
        state["answer"] = (
            f"```mermaid\n{result.get('mermaid', '')}\n```\n\n"
            f"{result.get('explanation', '')}"
        )
        state["agent_type"] = "system_design"
        state["sources"] = result.get("sources", [])
        return state

    def _extract_block(self, text: str, lang: str) -> str:
        match = re.search(rf"```{lang}\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _extract_section(self, text: str, marker: str) -> str:
        if marker not in text:
            return ""
        section = text.split(marker, 1)[1].split("\n\n")[0].strip()
        return section

    def _extract_components(self, text: str) -> list:
        section = self._extract_section(text, "COMPONENTS:")
        return [c.strip() for c in section.split(",") if c.strip()] if section else []
