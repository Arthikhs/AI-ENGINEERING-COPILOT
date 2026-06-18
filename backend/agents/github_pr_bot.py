"""
GitHub PR Bot
Workflow: PR Opened → Webhook → Review Agent → Post Comment on PR
Makes the platform feel like a production SaaS (like GitHub Copilot or Codecov).
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from agents.pr_review_agent import PRReviewAgent
from config import get_settings
import httpx
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

BOT_COMMENT_HEADER = "## 🤖 AI Engineering Copilot — Automated Review\n\n"

RISK_EMOJI = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}

SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🔵",
    "INFO": "⚪",
}


class GitHubPRBot:
    def __init__(self, github_token: str, db: AsyncSession):
        self.github_token = github_token
        self.db = db

    async def handle_pr_event(
        self,
        repo_full_name: str,
        pr_number: int,
        repo_id: str,
        action: str = "opened",
    ) -> Dict[str, Any]:
        """
        Called from webhook handler when a PR is opened/updated.
        Runs AI review and posts result as a GitHub PR comment.
        """
        if action not in ("opened", "synchronize", "reopened"):
            return {"skipped": True, "reason": f"action '{action}' not handled"}

        logger.info(f"PR Bot triggered: {repo_full_name}#{pr_number} ({action})")

        # Run AI review
        agent = PRReviewAgent(github_token=self.github_token, db=self.db)
        review = await agent.review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            repo_id=repo_id,
        )

        if "error" in review:
            return {"error": review["error"]}

        # Format comment
        comment_body = self._format_comment(review)

        # Post comment to GitHub PR
        posted = await self._post_comment(repo_full_name, pr_number, comment_body)

        return {
            "pr_number": pr_number,
            "risk_level": review["risk_level"],
            "findings_count": len(review.get("findings", [])),
            "comment_posted": posted,
        }

    def _format_comment(self, review: Dict) -> str:
        risk = review.get("risk_level", "low")
        emoji = RISK_EMOJI.get(risk, "⚪")
        findings = review.get("findings", [])

        lines = [
            BOT_COMMENT_HEADER,
            f"**Overall Risk:** {emoji} `{risk.upper()}`  ",
            f"**Findings:** {len(findings)} issue(s) detected\n",
        ]

        if findings:
            lines.append("### 📋 Findings\n")
            for i, f in enumerate(findings[:10], 1):
                sev_emoji = SEVERITY_EMOJI.get(f.get("severity", "INFO"), "⚪")
                lines.append(
                    f"{i}. {sev_emoji} **[{f.get('severity', 'INFO')}]** "
                    f"{f.get('description', '').strip()}"
                )
            if len(findings) > 10:
                lines.append(f"\n*...and {len(findings) - 10} more findings.*")

        lines.append("\n### 📝 Summary\n")
        lines.append(review.get("summary", "")[:1000])
        lines.append(
            "\n\n---\n"
            "*Reviewed by [AI Engineering Copilot](https://github.com) · "
            "Powered by GPT-4o + LangGraph*"
        )

        return "\n".join(lines)

    async def _post_comment(
        self, repo_full_name: str, pr_number: int, body: str
    ) -> bool:
        url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={"body": body}, headers=headers)
            if resp.status_code == 201:
                logger.info(f"PR comment posted on {repo_full_name}#{pr_number}")
                return True
            else:
                logger.error(f"Failed to post PR comment: {resp.status_code} {resp.text}")
                return False
