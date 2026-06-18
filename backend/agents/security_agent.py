"""
Security Review Agent
Analyzes code for: SQL Injection, Hardcoded Secrets, XSS, SSRF,
Auth Flaws, Command Injection, Path Traversal, Insecure Crypto.
Uses Hybrid RAG to find security-sensitive code patterns.
"""
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from rag.hybrid_retriever import HybridRetriever
from agents.state import AgentState
from agents.model_router_agent import routed_invoke
import logging

logger = logging.getLogger(__name__)

SECURITY_PROMPT = """You are a senior application security engineer (AppSec).
Analyze the provided code for security vulnerabilities.

Check for ALL of the following:
1. SQL Injection — string concatenation in queries
2. Hardcoded Secrets — API keys, passwords, tokens in source
3. XSS — unescaped user input in HTML/templates
4. SSRF — user-controlled URLs in HTTP requests
5. Authentication Flaws — missing auth checks, weak JWT, no expiry
6. Command Injection — os.system, subprocess with user input
7. Path Traversal — user-controlled file paths
8. Insecure Crypto — MD5/SHA1 for passwords, weak random
9. Mass Assignment — unfiltered request body to DB
10. Sensitive Data Exposure — PII/secrets in logs or responses

For EACH finding output EXACTLY this format:
---
SEVERITY: CRITICAL|HIGH|MEDIUM|LOW
CATEGORY: <vulnerability type>
FILE: <file path>
LINE: <approximate line or range>
CODE: <vulnerable code snippet>
EXPLANATION: <why this is vulnerable>
FIX: <concrete fix with code example>
---

End with:
OVERALL RISK: CRITICAL|HIGH|MEDIUM|LOW
SUMMARY: <2-3 sentence executive summary>
"""

# Patterns to target security-sensitive code
SECURITY_QUERIES = [
    "SQL query string concatenation database",
    "password secret token API key hardcoded",
    "authentication JWT token validation",
    "HTTP request URL user input fetch",
    "file path open read user input",
    "subprocess os system exec shell",
    "HTML template render user input",
    "encrypt decrypt hash password",
]


class SecurityReviewAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)

    async def review(self, repo_id: str) -> Dict[str, Any]:
        """Full security review of a repository."""
        all_chunks: Dict[str, Dict] = {}
        for query in SECURITY_QUERIES:
            chunks = await self.retriever.retrieve(query, repo_id, top_k=5)
            for c in chunks:
                all_chunks[c["id"]] = c

        if not all_chunks:
            return {"error": "No code found to review", "findings": []}

        context = self._build_context(list(all_chunks.values())[:25])

        result = await routed_invoke(
            task_type="security_review",
            messages=[
                SystemMessage(content=SECURITY_PROMPT),
                HumanMessage(content=f"Code to analyze:\n\n{context}"),
            ],
        )
        analysis = result["response"].content

        findings = self._parse_findings(analysis)
        overall_risk = self._extract_risk(analysis)
        summary = self._extract_summary(analysis)

        return {
            "findings": findings,
            "overall_risk": overall_risk,
            "summary": summary,
            "files_analyzed": len(set(c["file_path"] for c in all_chunks.values())),
            "full_analysis": analysis,
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
            "estimated_cost_usd": result["estimated_cost_usd"],
        }

    async def run_graph(self, state: AgentState) -> AgentState:
        result = await self.review(state["repo_id"])
        state["answer"] = result.get("summary", "Security review complete.")
        state["agent_type"] = "security"
        state["sources"] = []
        return state

    def _build_context(self, chunks: List[Dict]) -> str:
        parts = []
        for c in chunks:
            header = f"File: {c['file_path']}"
            if c.get("chunk_name"):
                header += f" | {c['chunk_type']}: {c['chunk_name']}"
            parts.append(f"{header}\n```\n{c['content'][:800]}\n```")
        return "\n\n---\n\n".join(parts)

    def _parse_findings(self, analysis: str) -> List[Dict]:
        findings = []
        blocks = analysis.split("---")
        for block in blocks:
            if "SEVERITY:" not in block:
                continue
            finding = {}
            for line in block.strip().split("\n"):
                for key in ["SEVERITY", "CATEGORY", "FILE", "LINE", "CODE", "EXPLANATION", "FIX"]:
                    if line.startswith(f"{key}:"):
                        finding[key.lower()] = line[len(key) + 1:].strip()
            if finding.get("severity"):
                findings.append(finding)
        return findings

    def _extract_risk(self, analysis: str) -> str:
        for line in analysis.split("\n"):
            if line.startswith("OVERALL RISK:"):
                val = line.replace("OVERALL RISK:", "").strip().upper()
                if val in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                    return val.lower()
        return "medium"

    def _extract_summary(self, analysis: str) -> str:
        for i, line in enumerate(analysis.split("\n")):
            if line.startswith("SUMMARY:"):
                return line.replace("SUMMARY:", "").strip()
        return analysis[-300:] if len(analysis) > 300 else analysis
