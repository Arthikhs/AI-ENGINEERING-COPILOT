"""
Architecture Agent — uses Model Router (architecture → gpt-4o)
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain.schema import HumanMessage, SystemMessage
from models.models import ArchitectureReport
from agents.state import AgentState
from agents.model_router_agent import routed_invoke
import logging
import json

logger = logging.getLogger(__name__)

ARCHITECTURE_PROMPT = """You are a software architect analyzing a repository's codebase.
Based on the code samples provided, produce a structured architecture analysis.

Respond ONLY with valid JSON in this exact format:
{
  "services": ["ServiceA", "ServiceB"],
  "dependencies": {"ServiceA": ["ServiceB", "DB"]},
  "api_endpoints": ["/api/users", "/api/auth"],
  "circular_dependencies": [],
  "layers": {"presentation": [], "business": [], "data": []},
  "concerns": ["concern1"],
  "summary": "Brief architecture summary"
}
"""


class ArchitectureAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze(self, repo_id: str, repo_full_name: str) -> Dict[str, Any]:
        samples = await self._get_architecture_samples(repo_id)

        if not samples:
            return {"error": "No indexed files found"}

        context = "\n\n---\n\n".join(
            f"File: {s['file_path']}\n```\n{s['content'][:800]}\n```"
            for s in samples
        )

        result = await routed_invoke(
            task_type="architecture",
            messages=[
                SystemMessage(content=ARCHITECTURE_PROMPT),
                HumanMessage(content=f"Repository: {repo_full_name}\n\nCode samples:\n{context}"),
            ],
        )

        raw = result["response"].content

        # Extract JSON — handle markdown code fences
        try:
            # Strip ```json fences if present
            clean = raw.strip()
            if clean.startswith("```"):
                clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = "\n".join(clean.split("\n")[:-1])
            data = json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            data = {"summary": raw, "services": [], "dependencies": {}}

        report = ArchitectureReport(
            repo_id=repo_id,
            service_count=len(data.get("services", [])),
            api_count=len(data.get("api_endpoints", [])),
            dependency_graph=data.get("dependencies", {}),
            circular_dependencies=data.get("circular_dependencies", []),
            layers=data.get("layers", {}),
            summary=data.get("summary", ""),
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)

        return {
            "id": str(report.id),
            "services": data.get("services", []),
            "service_count": report.service_count,
            "api_count": report.api_count,
            "dependency_graph": report.dependency_graph,
            "circular_dependencies": report.circular_dependencies,
            "layers": report.layers,
            "api_endpoints": data.get("api_endpoints", []),
            "concerns": data.get("concerns", []),
            "summary": report.summary,
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
            "estimated_cost_usd": result["estimated_cost_usd"],
        }

    async def run_graph(self, state: AgentState) -> AgentState:
        result = await self.analyze(state["repo_id"], repo_full_name="")
        state["answer"] = result.get("summary", "Architecture analysis complete.")
        state["agent_type"] = "architecture"
        state["sources"] = []
        return state

    async def _get_architecture_samples(self, repo_id: str, limit: int = 30) -> list:
        result = await self.db.execute(
            text("""
                SELECT DISTINCT ON (file_path) file_path, content
                FROM embeddings
                WHERE repo_id = :repo_id
                  AND chunk_type IN ('class', 'function', 'module')
                ORDER BY file_path
                LIMIT :limit
            """).bindparams(repo_id=repo_id, limit=limit)
        )
        rows = result.fetchall()

        if not rows:
            result2 = await self.db.execute(
                text("""
                    SELECT DISTINCT ON (file_path) file_path, content
                    FROM embeddings
                    WHERE repo_id = :repo_id
                    ORDER BY file_path
                    LIMIT :limit
                """).bindparams(repo_id=repo_id, limit=limit)
            )
            rows = result2.fetchall()

        return [{"file_path": r.file_path, "content": r.content} for r in rows]
