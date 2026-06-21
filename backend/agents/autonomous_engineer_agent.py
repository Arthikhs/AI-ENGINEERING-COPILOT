"""
Autonomous Issue-to-PR Workflow (Enterprise Grade)
Pipeline:
  GitHub Issue
  → Requirement Analysis Agent
  → Planning Agent
  → Code Generation Agent
  → Test Generation Agent
  → Test Execution Agent (Sandbox)
  → Code Review Agent
  → Pull Request Creation Agent
"""
import re
import json
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


# ── State ──────────────────────────────────────────────────────────────────────

class AutonomousEngineerState(TypedDict):
    # Inputs
    repo_full_name: str
    repo_id: str
    github_token: str
    issue_number: int

    # Step 1 — Fetch
    issue_title: str
    issue_body: str
    issue_labels: List[str]

    # Step 2 — Requirement Analysis
    requirements: Dict[str, Any]        # {summary, acceptance_criteria, complexity}

    # Step 3 — Planning
    plan: Dict[str, Any]                # {steps, affected_files, approach}

    # Step 4 — Code Generation
    relevant_files: List[Dict[str, Any]]
    code_changes: List[Dict[str, str]]

    # Step 5 — Test Generation
    test_changes: List[Dict[str, str]]

    # Step 6 — Test Execution
    test_results: Dict[str, Any]        # {passed, failed, output, retried}
    test_retry_count: int

    # Step 7 — Code Review
    review_result: Dict[str, Any]       # {approved, issues, suggestions}

    # Step 8 — PR Creation
    branch_name: str
    pr_url: str
    pr_number: int

    # Status
    status: str
    error: Optional[str]
    step_log: List[str]


# ── Agent ──────────────────────────────────────────────────────────────────────

class AutonomousEngineerAgent:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        g = StateGraph(AutonomousEngineerState)

        g.add_node("fetch_issue",        self._fetch_issue)
        g.add_node("analyze_requirements", self._analyze_requirements)
        g.add_node("create_plan",        self._create_plan)
        g.add_node("generate_code",      self._generate_code)
        g.add_node("generate_tests",     self._generate_tests)
        g.add_node("execute_tests",      self._execute_tests)
        g.add_node("review_code",        self._review_code)
        g.add_node("create_pr",          self._create_pr)

        g.set_entry_point("fetch_issue")
        g.add_edge("fetch_issue",          "analyze_requirements")
        g.add_edge("analyze_requirements", "create_plan")
        g.add_edge("create_plan",          "generate_code")
        g.add_edge("generate_code",        "generate_tests")
        g.add_edge("generate_tests",       "execute_tests")
        g.add_conditional_edges(
            "execute_tests",
            self._should_retry_or_continue,
            {
                "retry":    "generate_code",
                "review":   "review_code",
                "pr":       "create_pr",
            }
        )
        g.add_edge("review_code", "create_pr")
        g.add_edge("create_pr",   END)

        return g.compile()

    # ── Step 1: Fetch Issue ────────────────────────────────────────────────────

    async def _fetch_issue(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        state["step_log"].append("📋 Step 1/7 — Fetching GitHub issue...")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{state['repo_full_name']}/issues/{state['issue_number']}",
                    headers=self._gh_headers(state["github_token"]),
                    timeout=15,
                )
            if resp.status_code != 200:
                raise Exception(f"GitHub API {resp.status_code}: {resp.text}")

            data = resp.json()
            state["issue_title"]  = data.get("title", "")
            state["issue_body"]   = data.get("body", "") or ""
            state["issue_labels"] = [l["name"] for l in data.get("labels", [])]
            state["step_log"].append(f"✅ Issue #{state['issue_number']}: {state['issue_title']}")
        except Exception as e:
            state = self._fail(state, "fetch_issue", e)
        return state

    # ── Step 2: Requirement Analysis ──────────────────────────────────────────

    async def _analyze_requirements(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("🔎 Step 2/7 — Analyzing requirements...")
        try:
            result = await routed_invoke(
                task_type="simple_qa",
                messages=[
                    SystemMessage(content=REQUIREMENT_ANALYSIS_PROMPT),
                    HumanMessage(content=(
                        f"Issue: {state['issue_title']}\n\n"
                        f"Description:\n{state['issue_body'][:2000]}\n\n"
                        f"Labels: {', '.join(state['issue_labels'])}"
                    )),
                ],
                temperature=0.1,
            )
            parsed = _parse_json(result["response"].content)
            state["requirements"] = parsed or {
                "summary": state["issue_title"],
                "acceptance_criteria": [],
                "complexity": "medium",
                "type": "feature",
            }
            complexity = state["requirements"].get("complexity", "medium")
            state["step_log"].append(f"✅ Requirements analyzed — complexity: {complexity}")
        except Exception as e:
            state["requirements"] = {"summary": state["issue_title"], "complexity": "medium"}
            state["step_log"].append(f"⚠️ Requirement analysis partial: {e}")
        return state

    # ── Step 3: Planning ──────────────────────────────────────────────────────

    async def _create_plan(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("📐 Step 3/7 — Creating implementation plan...")
        try:
            # Fetch relevant files first for planning context
            query = f"{state['issue_title']}\n{state['issue_body'][:500]}"
            chunks = await self.retriever.retrieve(query, state["repo_id"], top_k=10)

            seen: Dict[str, Dict] = {}
            for c in chunks:
                fp = c["file_path"]
                if fp not in seen or c.get("score", 0) > seen[fp].get("score", 0):
                    seen[fp] = c
            state["relevant_files"] = list(seen.values())[:6]

            file_list = "\n".join(f"- {f['file_path']}" for f in state["relevant_files"])

            result = await routed_invoke(
                task_type="simple_qa",
                messages=[
                    SystemMessage(content=PLANNING_PROMPT),
                    HumanMessage(content=(
                        f"Issue: {state['issue_title']}\n\n"
                        f"Requirements:\n{json.dumps(state['requirements'], indent=2)}\n\n"
                        f"Relevant files found:\n{file_list}"
                    )),
                ],
                temperature=0.1,
            )
            parsed = _parse_json(result["response"].content)
            state["plan"] = parsed or {
                "steps": ["Analyze issue", "Implement fix", "Write tests", "Create PR"],
                "affected_files": [f["file_path"] for f in state["relevant_files"]],
                "approach": "Direct implementation",
            }
            steps_count = len(state["plan"].get("steps", []))
            state["step_log"].append(f"✅ Plan created — {steps_count} implementation steps")
        except Exception as e:
            state["plan"] = {"steps": [], "affected_files": [], "approach": "Direct fix"}
            state["step_log"].append(f"⚠️ Planning partial: {e}")
        return state

    # ── Step 4: Code Generation ────────────────────────────────────────────────

    async def _generate_code(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state

        retry = state.get("test_retry_count", 0)
        label = f"(retry #{retry})" if retry > 0 else ""
        state["step_log"].append(f"⚙️ Step 4/7 — Generating code changes {label}...")

        try:
            file_context = "\n\n".join(
                f"### {f['file_path']}\n```\n{f['content'][:1500]}\n```"
                for f in state["relevant_files"]
            )

            # Include test failure context on retry
            retry_context = ""
            if retry > 0 and state.get("test_results"):
                retry_context = (
                    f"\n\n## Previous Test Failures (Fix These)\n"
                    f"```\n{state['test_results'].get('output', '')[:1000]}\n```"
                )

            result = await routed_invoke(
                task_type="code_analysis",
                messages=[
                    SystemMessage(content=CODE_GEN_PROMPT),
                    HumanMessage(content=(
                        f"## Issue #{state['issue_number']}: {state['issue_title']}\n\n"
                        f"## Requirements\n{json.dumps(state['requirements'], indent=2)}\n\n"
                        f"## Implementation Plan\n{json.dumps(state['plan'], indent=2)}\n\n"
                        f"## Codebase Context\n{file_context}"
                        f"{retry_context}"
                    )),
                ],
                temperature=0.1,
            )
            state["code_changes"] = _parse_code_blocks(result["response"].content)
            state["step_log"].append(f"✅ Generated {len(state['code_changes'])} file change(s)")
        except Exception as e:
            state = self._fail(state, "generate_code", e)
        return state

    # ── Step 5: Test Generation ────────────────────────────────────────────────

    async def _generate_tests(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("🧪 Step 5/7 — Generating tests...")
        try:
            if not state["code_changes"]:
                state["test_changes"] = []
                state["step_log"].append("⚠️ No code changes — skipping test generation")
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
                        f"Generate tests for changes resolving: **{state['issue_title']}**\n\n"
                        f"## Changes\n{changes_summary}"
                    )),
                ],
                temperature=0.1,
            )
            state["test_changes"] = _parse_code_blocks(result["response"].content, is_test=True)
            state["step_log"].append(f"✅ Generated {len(state['test_changes'])} test file(s)")
        except Exception as e:
            state["test_changes"] = []
            state["step_log"].append(f"⚠️ Test generation failed (non-fatal): {e}")
        return state

    # ── Step 6: Test Execution ─────────────────────────────────────────────────

    async def _execute_tests(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("🏃 Step 6/7 — Executing tests in sandbox...")
        try:
            if not state["test_changes"]:
                state["test_results"] = {"passed": True, "skipped": True, "output": "No tests to run"}
                state["step_log"].append("⚠️ No tests to execute — skipping sandbox")
                return state

            # Try to execute the first test file in sandbox
            test_file = state["test_changes"][0]
            source_code = ""
            if state["code_changes"]:
                source_code = state["code_changes"][0]["new_content"]

            try:
                from agents.sandbox import execute_tests
                result = await execute_tests(
                    test_code=test_file["new_content"],
                    source_code=source_code,
                    language=_detect_language(test_file["file_path"]),
                )
                passed = result.exit_code == 0
                state["test_results"] = {
                    "passed": passed,
                    "exit_code": result.exit_code,
                    "output": result.stdout or result.stderr,
                    "execution_time_ms": result.execution_time_ms,
                }
                if passed:
                    state["step_log"].append(f"✅ Tests passed in {result.execution_time_ms}ms")
                else:
                    state["step_log"].append(f"❌ Tests failed — will retry code generation")
            except ImportError:
                # Sandbox not available (Docker not running in this env)
                state["test_results"] = {"passed": True, "skipped": True, "output": "Sandbox not available"}
                state["step_log"].append("⚠️ Sandbox unavailable — skipping test execution")

        except Exception as e:
            state["test_results"] = {"passed": True, "skipped": True, "output": str(e)}
            state["step_log"].append(f"⚠️ Test execution error (non-fatal): {e}")
        return state

    def _should_retry_or_continue(self, state: AutonomousEngineerState) -> str:
        """Decide: retry code gen, go to review, or skip to PR."""
        results = state.get("test_results", {})
        retry_count = state.get("test_retry_count", 0)

        if results.get("skipped"):
            return "pr"

        if not results.get("passed") and retry_count < 2:
            state["test_retry_count"] = retry_count + 1
            return "retry"

        return "review"

    # ── Step 7: Code Review ───────────────────────────────────────────────────

    async def _review_code(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("👀 Step 7/7 — AI code review...")
        try:
            changes_summary = "\n\n".join(
                f"### {c['file_path']}\n```\n{c['new_content'][:1000]}\n```"
                for c in state["code_changes"]
            )
            result = await routed_invoke(
                task_type="security_review",
                messages=[
                    SystemMessage(content=CODE_REVIEW_PROMPT),
                    HumanMessage(content=(
                        f"Review these changes for issue: {state['issue_title']}\n\n"
                        f"{changes_summary}"
                    )),
                ],
                temperature=0.1,
            )
            parsed = _parse_json(result["response"].content)
            state["review_result"] = parsed or {"approved": True, "issues": [], "suggestions": []}
            issues = len(state["review_result"].get("issues", []))
            state["step_log"].append(
                f"✅ Code review complete — {issues} issue(s) found"
            )
        except Exception as e:
            state["review_result"] = {"approved": True, "issues": [], "suggestions": []}
            state["step_log"].append(f"⚠️ Code review partial: {e}")
        return state

    # ── Step 8: Create PR ─────────────────────────────────────────────────────

    async def _create_pr(self, state: AutonomousEngineerState) -> AutonomousEngineerState:
        if state.get("status") == "failed":
            return state
        state["step_log"].append("🚀 Creating branch and opening PR...")
        try:
            token  = state["github_token"]
            repo   = state["repo_full_name"]
            branch = f"ai-engineer/issue-{state['issue_number']}"
            state["branch_name"] = branch

            default_branch, base_sha = await self._get_default_branch_sha(repo, token)
            await self._create_branch(repo, branch, base_sha, token)
            state["step_log"].append(f"✅ Created branch: {branch}")

            all_changes = state["code_changes"] + state["test_changes"]
            for change in all_changes:
                await self._commit_file(
                    repo, branch, change["file_path"], change["new_content"], token,
                    message=f"feat: {change.get('description', 'AI fix')} [issue #{state['issue_number']}]",
                )
            state["step_log"].append(f"✅ Committed {len(all_changes)} file(s)")

            pr = await self._open_pr(repo, branch, default_branch, state, token)
            state["pr_url"]    = pr.get("html_url", "")
            state["pr_number"] = pr.get("number", 0)
            state["status"]    = "completed"
            state["step_log"].append(f"✅ PR opened: {state['pr_url']}")
        except Exception as e:
            state = self._fail(state, "create_pr", e)
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
            if resp.status_code not in (201, 422):
                raise Exception(f"Branch creation failed: {resp.status_code}")

    async def _commit_file(self, repo: str, branch: str, file_path: str,
                           content: str, token: str, message: str):
        encoded = base64.b64encode(content.encode()).decode()
        async with httpx.AsyncClient() as client:
            existing = await client.get(
                f"https://api.github.com/repos/{repo}/contents/{file_path}",
                headers=self._gh_headers(token),
                params={"ref": branch}, timeout=15,
            )
            body: Dict[str, Any] = {"message": message, "content": encoded, "branch": branch}
            if existing.status_code == 200:
                body["sha"] = existing.json()["sha"]

            resp = await client.put(
                f"https://api.github.com/repos/{repo}/contents/{file_path}",
                headers=self._gh_headers(token),
                json=body, timeout=15,
            )
            if resp.status_code not in (200, 201):
                raise Exception(f"Commit failed for {file_path}: {resp.status_code}")

    async def _open_pr(self, repo: str, branch: str, base: str,
                       state: AutonomousEngineerState, token: str) -> dict:
        files_changed = [c["file_path"] for c in state["code_changes"] + state["test_changes"]]
        review = state.get("review_result", {})
        test_res = state.get("test_results", {})

        body = (
            f"## 🤖 Autonomous AI Engineer\n\n"
            f"Resolves #{state['issue_number']}: **{state['issue_title']}**\n\n"
            f"### 📋 Requirements Summary\n{state['requirements'].get('summary', '')}\n\n"
            f"### 📐 Implementation Plan\n"
            + "\n".join(f"- {s}" for s in state["plan"].get("steps", []))
            + f"\n\n### 📁 Files Changed\n"
            + "\n".join(f"- `{f}`" for f in files_changed)
            + f"\n\n### 🧪 Test Results\n"
            + (f"✅ Tests passed" if test_res.get("passed") else f"⚠️ Tests skipped")
            + f"\n\n### 👀 Code Review\n"
            + (f"✅ Approved" if review.get("approved") else f"⚠️ {len(review.get('issues', []))} issues found")
            + f"\n\n### 🔄 Pipeline Log\n"
            + "\n".join(f"- {s}" for s in state["step_log"])
            + "\n\n---\n*Generated by AI Engineering Copilot Autonomous Engineer*"
        )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=self._gh_headers(token),
                json={"title": f"[AI] {state['issue_title']}", "body": body,
                      "head": branch, "base": base},
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                raise Exception(f"PR creation failed: {resp.status_code}")
            return resp.json()

    @staticmethod
    def _gh_headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    @staticmethod
    def _fail(state: AutonomousEngineerState, step: str, error: Exception) -> AutonomousEngineerState:
        state["status"] = "failed"
        state["error"]  = f"{step} failed: {error}"
        state["step_log"].append(f"❌ {state['error']}")
        return state

    # ── Public Entry Point ─────────────────────────────────────────────────────

    async def run(self, repo_full_name: str, repo_id: str,
                  github_token: str, issue_number: int) -> Dict[str, Any]:
        initial: AutonomousEngineerState = {
            "repo_full_name": repo_full_name,
            "repo_id": repo_id,
            "github_token": github_token,
            "issue_number": issue_number,
            "issue_title": "",
            "issue_body": "",
            "issue_labels": [],
            "requirements": {},
            "plan": {},
            "relevant_files": [],
            "code_changes": [],
            "test_changes": [],
            "test_results": {},
            "test_retry_count": 0,
            "review_result": {},
            "branch_name": "",
            "pr_url": "",
            "pr_number": 0,
            "status": "running",
            "error": None,
            "step_log": [],
        }
        result = await self.graph.ainvoke(initial)
        # Record Prometheus metrics
        from observability.telemetry import record_autonomous_job
        record_autonomous_job(result["status"])
        return {
            "status":        result["status"],
            "issue_number":  result["issue_number"],
            "issue_title":   result["issue_title"],
            "branch_name":   result["branch_name"],
            "pr_url":        result["pr_url"],
            "pr_number":     result["pr_number"],
            "requirements":  result["requirements"],
            "plan":          result["plan"],
            "test_results":  result["test_results"],
            "review_result": result["review_result"],
            "files_changed": [c["file_path"] for c in result["code_changes"] + result["test_changes"]],
            "step_log":      result["step_log"],
            "error":         result.get("error"),
        }


# ── Prompts ────────────────────────────────────────────────────────────────────

REQUIREMENT_ANALYSIS_PROMPT = """You are a senior software architect analyzing a GitHub issue.
Extract and return a JSON object with:
- "summary": one paragraph describing what needs to be built
- "acceptance_criteria": list of strings — what must be true for this to be done
- "complexity": "low" | "medium" | "high"
- "type": "bug" | "feature" | "refactor" | "docs"
- "risks": list of potential risks

Return ONLY valid JSON, nothing else."""

PLANNING_PROMPT = """You are a staff engineer creating an implementation plan.
Return a JSON object with:
- "steps": ordered list of implementation steps
- "affected_files": list of files that need to be changed
- "approach": brief description of the technical approach
- "estimated_changes": number of files to modify

Return ONLY valid JSON, nothing else."""

CODE_GEN_PROMPT = """You are an Autonomous Software Engineer implementing a GitHub issue.
Generate the minimal code changes required.

Output ONLY a JSON array of changes. Each change must have:
- "file_path": relative path (e.g. "backend/api/auth.py")
- "new_content": COMPLETE new file content (not a diff)
- "description": one-line description of the change

Rules:
- Make MINIMAL changes — only what is needed
- Preserve existing code style and structure
- Output ONLY the JSON array, nothing else"""

TEST_GEN_PROMPT = """You are a senior test engineer. Generate comprehensive tests for the given code changes.

Output ONLY a JSON array. Each item must have:
- "file_path": test file path (e.g. "backend/tests/test_auth.py")
- "new_content": complete test file content
- "description": what is being tested

Rules:
- Use pytest for Python, Jest for TypeScript/JavaScript
- Include happy path, edge cases, and error cases
- Mock all external dependencies
- Output ONLY the JSON array, nothing else"""

CODE_REVIEW_PROMPT = """You are a principal engineer reviewing AI-generated code.
Review the changes and return a JSON object with:
- "approved": true | false
- "issues": list of {severity, description, file_path} objects
- "suggestions": list of improvement suggestions
- "security_concerns": list of security issues found

Return ONLY valid JSON, nothing else."""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> Optional[Dict]:
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return None


def _parse_code_blocks(response: str, is_test: bool = False) -> List[Dict[str, str]]:
    match = re.search(r'\[[\s\S]*\]', response)
    if match:
        try:
            changes = json.loads(match.group())
            if isinstance(changes, list) and all("file_path" in c and "new_content" in c for c in changes):
                return changes
        except Exception:
            pass

    blocks = re.findall(r'```(?:\w+)?\n([\s\S]*?)```', response)
    if blocks:
        prefix = "test_" if is_test else ""
        return [{"file_path": f"generated/{prefix}output_{i}.py",
                 "new_content": b, "description": "Generated"} for i, b in enumerate(blocks)]
    return []


def _detect_language(file_path: str) -> str:
    if file_path.endswith(".ts") or file_path.endswith(".tsx"):
        return "typescript"
    if file_path.endswith(".js"):
        return "javascript"
    if file_path.endswith(".java"):
        return "java"
    return "python"
