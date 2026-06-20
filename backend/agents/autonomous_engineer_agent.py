"""
Autonomous Software Engineer Agent
Pipeline: GitHub Issue → Understand → Find Files → Generate Code → Generate Tests → Create PR

Given a GitHub issue URL, this agent:
1. Fetches and understands the issue
2. Finds relevant files in the codebase via RAG
3. Generates code changes
4. Generates tests for the changes
5. Creates a branch, commits the changes, and opens a PR
"""
import re
import base64
import logging
from typing import TypedDict, List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph import StateGraph, END
from langchain.schema import HumanMessage, SystemMessage
from rag.hybrid_retriever import HybridRetriever
from agents.model_router_agent import routed_invoke
import httpx

logger = logging.getLogger(__name__)


# ── State ─────────────────────────────────────────────────────────────────────

class AutonomousEngineerState(TypedDict):
    # Inputs
    repo_full_name: str       # e.g. "owner/repo"
    repo_id: str
    github_token: str
    issue_number: int

    # Populated during pipeline
    issue_title: str
    issue_body: str
    issue_labels: List[str]
    relevant_files: List[Dict[str, Any]]  # [{file_path, content, chunk_name}]
    code_changes: List[Dict[str, str]]    # [{file_path, new_content, description}]
    test_changes: List[Dict[str, str]]    # [{file_path, new_content}]
    branch_name: str
    pr_url: str
    pr_number: int

    # Status
    status: str   # running | completed | failed
    error: Optional[str]
    step_log: List[str]


# ── Agent ─────────────────────────────────────────────────────────────────────

class AutonomousEngineerAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        g = StateGraph(AutonomousEngineerState)
        g.add_node("fetch_issue",     self._fetch_issue)
        g.add_node("find_files",      self._find_files)
        g.add_node("generate_code",   self._generate_code)
        g.add_node("generate_tests",  self._generate_tests)
        g.add_node("create_pr",       self._create_pr)

        g.set_entry_point("fetch_issue")
        g.add_edge("fetch_issue",    "find_files")
        g.add_edge("find_files",     "generate_code")
        g.add_edge("generate_code",  "generate_tests")
        g.add_edge("generate_tests", "create_pr")
        g.add_edge("create_pr",      END)
        return g.compile()

    # ── Step 1: Fetch GitHub Issue ────────────────────────────────────────────

    async def _fetch_issue(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        state["step_log"].append("📋 Fetching GitHub issue...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{state['repo_full_name']}/issues/{state['issue_number']}",
                    headers=self._gh_headers(state["github_token"]),
                    timeout=15,
                )
            if resp.status_code != 200:
                raise Exception(f"GitHub API returned {resp.status_code}")

            data = resp.json()
            state["issue_title"] = data.get("title", "")
            state["issue_body"] = data.get("body", "") or ""
            state["issue_labels"] = [l["name"] for l in data.get("labels", [])]
            state["step_log"].append(f"✅ Issue #{state['issue_number']}: {state['issue_title']}")
        except Exception as e:
            state["status"] = "failed"
            state["error"] = f"fetch_issue failed: {e}"
            state["step_log"].append(f"❌ {state['error']}")
        return state

    # ── Step 2: Find Relevant Files via RAG ───────────────────────────────────

    async def _find_files(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("🔍 Finding relevant files in codebase...")
        try:
            query = f"{state['issue_title']}\n{state['issue_body'][:500]}"
            chunks = await self.retriever.retrieve(query, state["repo_id"], top_k=8)

            # Deduplicate by file_path, keep highest-scored chunk per file
            seen: Dict[str, Dict] = {}
            for c in chunks:
                fp = c["file_path"]
                if fp not in seen or c.get("score", 0) > seen[fp].get("score", 0):
                    seen[fp] = c

            state["relevant_files"] = list(seen.values())[:5]
            paths = [f["file_path"] for f in state["relevant_files"]]
            state["step_log"].append(f"✅ Found {len(paths)} relevant files: {', '.join(paths)}")
        except Exception as e:
            state["status"] = "failed"
            state["error"] = f"find_files failed: {e}"
            state["step_log"].append(f"❌ {state['error']}")
        return state

    # ── Step 3: Generate Code Changes ─────────────────────────────────────────

    async def _generate_code(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("⚙️ Generating code changes...")
        try:
            file_context = "\n\n".join(
                f"### File: {f['file_path']}\n```\n{f['content'][:1500]}\n```"
                for f in state["relevant_files"]
            )
            result = await routed_invoke(
                task_type="code_analysis",
                messages=[
                    SystemMessage(content=CODE_GEN_PROMPT),
                    HumanMessage(content=(
                        f"## Issue #{state['issue_number']}: {state['issue_title']}\n\n"
                        f"{state['issue_body'][:1000]}\n\n"
                        f"## Relevant Codebase Context\n{file_context}"
                    )),
                ],
                temperature=0.1,
            )
            state["code_changes"] = _parse_code_blocks(result["response"].content)
            state["step_log"].append(f"✅ Generated {len(state['code_changes'])} file change(s)")
        except Exception as e:
            state["status"] = "failed"
            state["error"] = f"generate_code failed: {e}"
            state["step_log"].append(f"❌ {state['error']}")
        return state

    # ── Step 4: Generate Tests ────────────────────────────────────────────────

    async def _generate_tests(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("🧪 Generating tests...")
        try:
            if not state["code_changes"]:
                state["test_changes"] = []
                state["step_log"].append("⚠️ No code changes to test")
                return state

            changes_summary = "\n\n".join(
                f"### {c['file_path']}\n```\n{c['new_content'][:1200]}\n```"
                for c in state["code_changes"]
            )
            result = await routed_invoke(
                task_type="test_generation",
                messages=[
                    SystemMessage(content=TEST_GEN_PROMPT),
                    HumanMessage(content=(
                        f"Generate tests for these changes made to resolve:\n"
                        f"**{state['issue_title']}**\n\n{changes_summary}"
                    )),
                ],
                temperature=0.1,
            )
            state["test_changes"] = _parse_code_blocks(result["response"].content, is_test=True)
            state["step_log"].append(f"✅ Generated {len(state['test_changes'])} test file(s)")
        except Exception as e:
            # Non-fatal — still create the PR without tests
            state["test_changes"] = []
            state["step_log"].append(f"⚠️ Test generation failed (non-fatal): {e}")
        return state

    # ── Step 5: Create Branch + Commit + PR ───────────────────────────────────

    async def _create_pr(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("🚀 Creating branch and opening PR...")
        try:
            token = state["github_token"]
            repo = state["repo_full_name"]
            branch = f"ai-engineer/issue-{state['issue_number']}"
            state["branch_name"] = branch

            # Get default branch SHA
            default_branch, base_sha = await self._get_default_branch_sha(repo, token)

            # Create branch
            await self._create_branch(repo, branch, base_sha, token)
            state["step_log"].append(f"✅ Created branch: {branch}")

            # Commit all changes (code + tests)
            all_changes = state["code_changes"] + state["test_changes"]
            for change in all_changes:
                await self._commit_file(repo, branch, change["file_path"], change["new_content"], token,
                                        message=f"feat: {change.get('description', 'AI-generated change')} [issue #{state['issue_number']}]")

            state["step_log"].append(f"✅ Committed {len(all_changes)} file(s)")

            # Open PR
            pr = await self._open_pr(repo, branch, default_branch, state, token)
            state["pr_url"] = pr.get("html_url", "")
            state["pr_number"] = pr.get("number", 0)
            state["status"] = "completed"
            state["step_log"].append(f"✅ PR opened: {state['pr_url']}")
        except Exception as e:
            state["status"] = "failed"
            state["error"] = f"create_pr failed: {e}"
            state["step_log"].append(f"❌ {state['error']}")
        return state

    # ── GitHub Helpers ─────────────────────────────────────────────────────────

    async def _get_default_branch_sha(self, repo: str, token: str):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo}",
                headers=self._gh_headers(token), timeout=15,
            )
            data = resp.json()
            default_branch = data["default_branch"]
            ref_resp = await client.get(
                f"https://api.github.com/repos/{repo}/git/ref/heads/{default_branch}",
                headers=self._gh_headers(token), timeout=15,
            )
            sha = ref_resp.json()["object"]["sha"]
        return default_branch, sha

    async def _create_branch(self, repo: str, branch: str, sha: str, token: str):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/repos/{repo}/git/refs",
                headers=self._gh_headers(token),
                json={"ref": f"refs/heads/{branch}", "sha": sha},
                timeout=15,
            )
            if resp.status_code not in (201, 422):  # 422 = already exists
                raise Exception(f"Branch creation failed: {resp.status_code} {resp.text}")

    async def _commit_file(self, repo: str, branch: str, file_path: str, content: str, token: str, message: str):
        encoded = base64.b64encode(content.encode()).decode()
        async with httpx.AsyncClient() as client:
            # Check if file exists to get its SHA (needed for update)
            existing = await client.get(
                f"https://api.github.com/repos/{repo}/contents/{file_path}",
                headers=self._gh_headers(token),
                params={"ref": branch},
                timeout=15,
            )
            body: Dict[str, Any] = {"message": message, "content": encoded, "branch": branch}
            if existing.status_code == 200:
                body["sha"] = existing.json()["sha"]

            resp = await client.put(
                f"https://api.github.com/repos/{repo}/contents/{file_path}",
                headers=self._gh_headers(token),
                json=body,
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                raise Exception(f"Commit failed for {file_path}: {resp.status_code} {resp.text}")

    async def _open_pr(self, repo: str, branch: str, base: str, state: AutonomousEngineerState, token: str) -> dict:
        files_changed = [c["file_path"] for c in state["code_changes"] + state["test_changes"]]
        body = (
            f"## 🤖 Autonomous AI Engineer\n\n"
            f"Resolves #{state['issue_number']}: **{state['issue_title']}**\n\n"
            f"### Changes Made\n"
            + "\n".join(f"- `{f}`" for f in files_changed)
            + f"\n\n### Steps Taken\n"
            + "\n".join(f"- {s}" for s in state["step_log"])
            + "\n\n---\n*Generated by AI Engineering Copilot Autonomous Engineer*"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=self._gh_headers(token),
                json={
                    "title": f"[AI] {state['issue_title']}",
                    "body": body,
                    "head": branch,
                    "base": base,
                },
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                raise Exception(f"PR creation failed: {resp.status_code} {resp.text}")
            return resp.json()

    @staticmethod
    def _gh_headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    # ── Public Entry Point ─────────────────────────────────────────────────────

    async def run(
        self,
        repo_full_name: str,
        repo_id: str,
        github_token: str,
        issue_number: int,
    ) -> Dict[str, Any]:
        initial: AutonomousEngineerState = {
            "repo_full_name": repo_full_name,
            "repo_id": repo_id,
            "github_token": github_token,
            "issue_number": issue_number,
            "issue_title": "",
            "issue_body": "",
            "issue_labels": [],
            "relevant_files": [],
            "code_changes": [],
            "test_changes": [],
            "branch_name": "",
            "pr_url": "",
            "pr_number": 0,
            "status": "running",
            "error": None,
            "step_log": [],
        }
        result = await self.graph.ainvoke(initial)
        return {
            "status":       result["status"],
            "issue_number": result["issue_number"],
            "issue_title":  result["issue_title"],
            "branch_name":  result["branch_name"],
            "pr_url":       result["pr_url"],
            "pr_number":    result["pr_number"],
            "files_changed": [c["file_path"] for c in result["code_changes"] + result["test_changes"]],
            "step_log":     result["step_log"],
            "error":        result.get("error"),
        }


# ── Prompts ───────────────────────────────────────────────────────────────────

CODE_GEN_PROMPT = """You are an Autonomous Software Engineer. Given a GitHub issue and relevant codebase context, generate the minimal code changes required to resolve the issue.

Output ONLY a JSON array of changes. Each change must have:
- "file_path": relative path (e.g. "backend/api/auth.py")
- "new_content": the COMPLETE new file content (not a diff)
- "description": one-line description of the change

Example:
```json
[
  {
    "file_path": "backend/api/auth.py",
    "new_content": "...full file content...",
    "description": "Add rate limiting to login endpoint"
  }
]
```

Rules:
- Make MINIMAL changes — only what's needed to solve the issue
- Preserve existing code structure and style
- If adding a new file, provide its full content
- Output ONLY the JSON array, nothing else
"""

TEST_GEN_PROMPT = """You are a senior test engineer. Given code changes, generate comprehensive unit tests.

Output ONLY a JSON array. Each item must have:
- "file_path": test file path (e.g. "backend/tests/test_auth.py")
- "new_content": complete test file content
- "description": what is being tested

Rules:
- Use pytest for Python, Jest for TypeScript/JavaScript
- Include happy path, edge cases, and error cases
- Mock external dependencies
- Output ONLY the JSON array, nothing else
"""


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_code_blocks(response: str, is_test: bool = False) -> List[Dict[str, str]]:
    """Extract JSON array from LLM response, with fallback."""
    import json

    # Try to extract JSON array from response
    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            changes = json.loads(json_match.group())
            if isinstance(changes, list) and all("file_path" in c and "new_content" in c for c in changes):
                return changes
        except json.JSONDecodeError:
            pass

    # Fallback: extract fenced code blocks
    blocks = re.findall(r'```(?:\w+)?\n([\s\S]*?)```', response)
    if blocks:
        prefix = "test_" if is_test else ""
        return [{"file_path": f"generated/{prefix}output_{i}.py", "new_content": b, "description": "Generated code"} for i, b in enumerate(blocks)]

    return []
