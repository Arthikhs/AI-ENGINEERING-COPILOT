"""
Refactoring Agent — uses Model Router (refactoring task → gpt-4o)
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from rag.hybrid_retriever import HybridRetriever
from agents.state import AgentState
from agents.model_router_agent import routed_invoke
import logging

logger = logging.getLogger(__name__)

REFACTOR_PROMPT = """You are a senior software engineer specializing in clean code and refactoring.
Analyze the provided code and identify refactoring opportunities.

Detect:
1. LARGE CLASS — class with too many responsibilities (>300 lines or >10 methods)
2. LONG METHOD — methods >50 lines or doing too many things
3. DUPLICATE CODE — similar logic repeated across files
4. DEAD CODE — unused functions, variables, imports
5. GOD OBJECT — class that knows too much / does too much
6. FEATURE ENVY — method using data from another class excessively
7. DATA CLUMPS — groups of data that always appear together
8. MAGIC NUMBERS — unexplained numeric/string literals

For each issue output EXACTLY:
---
ISSUE: <issue type>
SEVERITY: HIGH|MEDIUM|LOW
FILE: <file path>
LOCATION: <class/method name>
DESCRIPTION: <what the problem is>
BEFORE:
```
<problematic code snippet>
```
AFTER:
```
<refactored version>
```
BENEFIT: <what improves>
---

End with:
REFACTORING_PLAN:
<numbered list of recommended refactoring steps in priority order>
"""


class RefactoringAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)

    async def analyze(self, repo_id: str, target_file: str = None) -> Dict[str, Any]:
        queries = [
            "large class many methods long file",
            "duplicate code repeated logic similar function",
            "long method complex function many lines",
            "unused variable dead code unreachable",
            "magic number hardcoded value constant",
        ]
        all_chunks: Dict[str, Dict] = {}
        for query in queries:
            chunks = await self.retriever.retrieve(query, repo_id, top_k=6)
            for c in chunks:
                if target_file is None or target_file in c["file_path"]:
                    all_chunks[c["id"]] = c

        if not all_chunks:
            return {"error": "No code found", "suggestions": []}

        context = "\n\n---\n\n".join(
            f"File: {c['file_path']}\n```\n{c['content'][:1000]}\n```"
            for c in list(all_chunks.values())[:20]
        )

        result = await routed_invoke(
            task_type="refactoring",
            messages=[
                SystemMessage(content=REFACTOR_PROMPT),
                HumanMessage(content=f"Code to analyze:\n\n{context}"),
            ],
        )
        analysis = result["response"].content

        return {
            "suggestions": self._parse_suggestions(analysis),
            "refactoring_plan": self._extract_plan(analysis),
            "files_analyzed": len(set(c["file_path"] for c in all_chunks.values())),
            "full_analysis": analysis,
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
            "estimated_cost_usd": result["estimated_cost_usd"],
        }

    async def run_graph(self, state: AgentState) -> AgentState:
        result = await self.analyze(state["repo_id"])
        state["answer"] = "\n".join(result.get("refactoring_plan", ["No refactoring needed."]))
        state["agent_type"] = "refactor"
        state["sources"] = []
        return state

    def _parse_suggestions(self, analysis: str) -> List[Dict]:
        suggestions = []
        blocks = analysis.split("---")
        for block in blocks:
            if "ISSUE:" not in block:
                continue
            s: Dict[str, Any] = {}
            lines = block.strip().split("\n")
            i = 0
            while i < len(lines):
                line = lines[i]
                for key in ["ISSUE", "SEVERITY", "FILE", "LOCATION", "DESCRIPTION", "BENEFIT"]:
                    if line.startswith(f"{key}:"):
                        s[key.lower()] = line[len(key) + 1:].strip()
                if line.strip() == "BEFORE:":
                    code, i = self._extract_code_block(lines, i + 1)
                    s["before"] = code
                    continue
                if line.strip() == "AFTER:":
                    code, i = self._extract_code_block(lines, i + 1)
                    s["after"] = code
                    continue
                i += 1
            if s.get("issue"):
                suggestions.append(s)
        return suggestions

    def _extract_code_block(self, lines: List[str], start: int):
        code_lines, i, in_block = [], start, False
        while i < len(lines):
            if lines[i].strip().startswith("```"):
                if not in_block:
                    in_block = True
                else:
                    return "\n".join(code_lines), i + 1
            elif in_block:
                code_lines.append(lines[i])
            i += 1
        return "\n".join(code_lines), i

    def _extract_plan(self, analysis: str) -> List[str]:
        plan, capture = [], False
        for line in analysis.split("\n"):
            if "REFACTORING_PLAN:" in line:
                capture = True
                continue
            if capture and line.strip():
                plan.append(line.strip())
        return plan
