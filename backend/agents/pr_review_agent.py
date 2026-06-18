"""
PR Review Agent — uses Model Router (pr_review → gpt-4o-mini)
"""
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langchain.schema import HumanMessage, SystemMessage
from models.models import PRReview
from agents.model_router_agent import routed_invoke
import httpx
import logging

logger = logging.getLogger(__name__)

PR_REVIEW_PROMPT = """You are a senior software engineer performing a thorough code review.
Analyze the provided diff and identify:

1. Bugs and logical errors
2. Security vulnerabilities (SQL injection, XSS, auth issues, etc.)
3. Null pointer / undefined access risks
4. Missing error handling
5. Performance issues
6. Missing or inadequate tests
7. Code style and complexity issues

For each finding, provide:
- Severity: CRITICAL | HIGH | MEDIUM | LOW | INFO
- File and approximate line
- Clear explanation
- Specific recommendation

Be concise and actionable. Format findings as a structured list.
End with an overall risk assessment: LOW | MEDIUM | HIGH | CRITICAL
"""


class PRReviewAgent:
    def __init__(self, github_token: str, db: AsyncSession):
        self.github_token = github_token
        self.db = db

    async def review(self, repo_full_name: str, pr_number: int, repo_id: str) -> Dict[str, Any]:
        pr_data = await self._fetch_pr(repo_full_name, pr_number)
        diff = await self._fetch_diff(repo_full_name, pr_number)

        if not diff:
            return {"error": "No diff available for this PR"}

        if len(diff) > 15000:
            diff = diff[:15000] + "\n... [diff truncated]"

        result = await routed_invoke(
            task_type="pr_review",
            messages=[
                SystemMessage(content=PR_REVIEW_PROMPT),
                HumanMessage(
                    content=f"PR #{pr_number}: {pr_data.get('title', '')}\n\n"
                            f"Base: {pr_data.get('base', {}).get('ref', 'main')} → "
                            f"Head: {pr_data.get('head', {}).get('ref', 'feature')}\n\n"
                            f"Diff:\n{diff}"
                ),
            ],
        )
        analysis = result["response"].content

        risk_level = "low"
        for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if level in analysis.upper():
                risk_level = level.lower()
                break

        findings = self._parse_findings(analysis)

        review = PRReview(
            repo_id=repo_id,
            pr_number=pr_number,
            pr_title=pr_data.get("title"),
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            head_branch=pr_data.get("head", {}).get("ref", ""),
            findings=findings,
            summary=analysis,
            risk_level=risk_level,
        )
        self.db.add(review)
        await self.db.commit()

        return {
            "pr_number": pr_number,
            "pr_title": pr_data.get("title"),
            "risk_level": risk_level,
            "findings": findings,
            "summary": analysis,
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
            "estimated_cost_usd": result["estimated_cost_usd"],
        }

    async def run_graph(self, state) -> dict:
        return state

    async def _fetch_pr(self, repo_full_name: str, pr_number: int) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}",
                headers=self._headers(), timeout=15,
            )
            return resp.json() if resp.status_code == 200 else {}

    async def _fetch_diff(self, repo_full_name: str, pr_number: int) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}",
                headers={**self._headers(), "Accept": "application/vnd.github.v3.diff"},
                timeout=15,
            )
            return resp.text if resp.status_code == 200 else ""

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
        }

    @staticmethod
    def _parse_findings(analysis: str) -> List[Dict[str, Any]]:
        findings = []
        lines = analysis.split("\n")
        for i, line in enumerate(lines):
            for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
                if severity in line.upper() and (":" in line or "-" in line):
                    findings.append({
                        "severity": severity,
                        "description": line.strip("- •*").strip(),
                        "line_context": lines[i + 1].strip() if i + 1 < len(lines) else "",
                    })
                    break
        return findings[:20]
