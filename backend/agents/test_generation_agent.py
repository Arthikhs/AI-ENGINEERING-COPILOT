"""
Test Generation Agent — uses Model Router (test_generation → llama3 local)
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from rag.hybrid_retriever import HybridRetriever
from agents.state import AgentState
from agents.model_router_agent import routed_invoke
import logging

logger = logging.getLogger(__name__)

TEST_PROMPTS = {
    "Python": """You are a Python testing expert using pytest and unittest.mock.
Generate comprehensive tests: happy path, edge cases, exceptions, mocks.
Use pytest style. Output ONLY valid Python test code.""",

    "Java": """You are a Java testing expert using JUnit 5 and Mockito.
Generate @Test happy path, edge cases, assertThrows, @Mock dependencies.
Output ONLY valid Java test code.""",

    "JavaScript": """You are a JavaScript testing expert using Jest.
Generate describe/it blocks, jest.mock(), async/await tests.
Output ONLY valid Jest test code.""",

    "TypeScript": """You are a TypeScript testing expert using Jest + ts-jest.
Generate typed tests with describe/it, jest.mock() with proper typing.
Output ONLY valid TypeScript Jest test code.""",

    "default": """You are a testing expert. Generate comprehensive unit tests.
Include happy path, edge cases, and error cases. Mock external dependencies.""",
}


class TestGenerationAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)

    async def generate(self, repo_id: str, target: str, language: str = None) -> Dict[str, Any]:
        chunks = await self.retriever.retrieve(target, repo_id, top_k=5)
        if not chunks:
            return {"error": f"Could not find '{target}' in the codebase", "tests": ""}

        if not language:
            language = chunks[0].get("language") or "default"

        source_context = "\n\n".join(
            f"// File: {c['file_path']}\n{c['content']}"
            for c in chunks[:3]
        )
        system_prompt = TEST_PROMPTS.get(language, TEST_PROMPTS["default"])

        result = await routed_invoke(
            task_type="test_generation",
            messages=[
                SystemMessage(content=system_prompt),
                HumanMessage(content=(
                    f"Generate tests for: {target}\n\n"
                    f"Source code:\n```{language.lower()}\n{source_context}\n```"
                )),
            ],
            temperature=0.2,
        )

        source_file = chunks[0]["file_path"]
        return {
            "target": target,
            "language": language,
            "source_file": source_file,
            "test_filename": self._suggest_test_filename(source_file, language),
            "test_code": result["response"].content,
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
            "estimated_cost_usd": result["estimated_cost_usd"],
            "chunks_used": [
                {"file_path": c["file_path"], "chunk_name": c.get("chunk_name")}
                for c in chunks[:3]
            ],
        }

    async def run_graph(self, state: AgentState) -> AgentState:
        result = await self.generate(state["repo_id"], state["question"])
        state["answer"] = result.get("test_code", "Could not generate tests.")
        state["agent_type"] = "test_generation"
        state["sources"] = [{"file_path": c["file_path"]} for c in result.get("chunks_used", [])]
        return state

    def _suggest_test_filename(self, source_file: str, language: str) -> str:
        name = source_file.split("/")[-1].rsplit(".", 1)[0]
        return {
            "Python": f"test_{name}.py",
            "Java": f"{name}Test.java",
            "JavaScript": f"{name}.test.js",
            "TypeScript": f"{name}.test.ts",
        }.get(language, f"test_{name}.txt")
