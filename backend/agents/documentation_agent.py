"""
Documentation Agent — uses Model Router (documentation → gpt-4o-mini)
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

DOC_PROMPT = """You are a senior technical writer and software architect.
Generate comprehensive documentation based on the provided source code.

You MUST produce ALL of the following sections:

## README
```markdown
# <Service/Module Name>

## Overview
<What this service does>

## Features
- Feature 1

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET    | /... | ...         |

## Dependencies
- Dependency 1

## Setup
<Setup instructions>
```

## API_DOCS
### <FunctionName>
**Description:** <what it does>
**Parameters:** <params with types>
**Returns:** <return type>

## SEQUENCE_DIAGRAM
```mermaid
sequenceDiagram
    participant Client
    participant ServiceA
    Client->>ServiceA: request()
    ServiceA-->>Client: response
```

## SUMMARY
<2-3 paragraph summary of the codebase/module>
"""

DOC_QUERIES = [
    "API endpoints routes handlers",
    "class definition public methods",
    "function parameters return types",
    "module overview imports dependencies",
    "README documentation setup",
]


class DocumentationAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)

    async def generate(self, repo_id: str, target: str = None) -> Dict[str, Any]:
        all_chunks: Dict[str, Dict] = {}
        queries = DOC_QUERIES if not target else [target] + DOC_QUERIES[:3]

        for query in queries:
            chunks = await self.retriever.retrieve(query, repo_id, top_k=5)
            for c in chunks:
                if target is None or target.lower() in c["file_path"].lower() or target.lower() in (c.get("chunk_name") or "").lower():
                    all_chunks[c["id"]] = c

        if not all_chunks:
            return {"error": "No code found to document"}

        context = "\n\n---\n\n".join(
            f"File: {c['file_path']}\n```\n{c['content'][:800]}\n```"
            for c in list(all_chunks.values())[:20]
        )

        result = await routed_invoke(
            task_type="documentation",
            messages=[
                SystemMessage(content=DOC_PROMPT),
                HumanMessage(content=f"Generate documentation for:\n\n{context}"),
            ],
            temperature=0.1,
        )
        raw = result["response"].content

        return {
            "readme": self._extract_section(raw, "README"),
            "api_docs": self._extract_section(raw, "API_DOCS"),
            "sequence_diagram": self._extract_mermaid(raw),
            "summary": self._extract_section(raw, "SUMMARY"),
            "files_documented": len(set(c["file_path"] for c in all_chunks.values())),
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
            "estimated_cost_usd": result["estimated_cost_usd"],
            "full_output": raw,
        }

    async def run(self, state: AgentState) -> AgentState:
        context = state.get("context", "")
        question = state["question"]

        if not context:
            state["agent_outputs"]["documentation"] = {"error": "No code context available"}
            return state

        result = await routed_invoke(
            task_type="documentation",
            messages=[
                SystemMessage(content=DOC_PROMPT),
                HumanMessage(content=f"Request: {question}\n\nCode:\n{context[:6000]}"),
            ],
            temperature=0.1,
        )
        raw = result["response"].content

        state["agent_outputs"]["documentation"] = {
            "readme": self._extract_section(raw, "README"),
            "api_docs": self._extract_section(raw, "API_DOCS"),
            "sequence_diagram": self._extract_mermaid(raw),
            "summary": self._extract_section(raw, "SUMMARY"),
            "full_output": raw,
        }
        return state

    async def run_graph(self, state: AgentState) -> AgentState:
        result = await self.generate(state["repo_id"])
        state["answer"] = result.get("summary") or result.get("readme", "Documentation generated.")
        state["agent_type"] = "documentation"
        state["sources"] = []
        return state

    def _extract_section(self, text: str, marker: str) -> str:
        pattern = rf"## {marker}\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            content = match.group(1).strip()
            content = re.sub(r"^```\w*\n", "", content)
            content = re.sub(r"\n```$", "", content)
            return content.strip()
        return ""

    def _extract_mermaid(self, text: str) -> str:
        match = re.search(r"```mermaid\n(.*?)```", text, re.DOTALL)
        return match.group(1).strip() if match else ""
