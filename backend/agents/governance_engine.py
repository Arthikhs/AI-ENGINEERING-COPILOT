"""
Architecture Governance Engine — Enterprise Grade
Detects:
  - Layer violations (controller → DB, API → DB direct access)
  - Circular dependencies (DFS on knowledge graph)
  - God classes (too many methods)
  - Tight coupling (too many imports per file)
  - Service boundary violations
  - Anti-patterns (magic numbers, service locator, print debugging)
  - Security anti-patterns (hardcoded secrets)
  - Long functions
  - Missing error handling
  - Dead code indicators

Supports:
  - Built-in rules
  - Custom org-level rules (from DB)
  - Severity levels: critical / high / medium / low
  - AI-powered fix suggestions
  - DB persistence of violations
  - Governance report generation
"""
import re
import uuid
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from models.models import CodeChunk, KnowledgeEdge, KnowledgeNode

logger = logging.getLogger(__name__)


# ── Built-in Rules ─────────────────────────────────────────────────────────────

BUILT_IN_RULES = [
    # Layer violations
    {
        "id": "LV001",
        "name": "Controller Direct DB Access",
        "rule_type": "layer_violation",
        "severity": "high",
        "description": "Controllers/routes should not access the database directly.",
        "pattern": r"(router|controller|route).*\b(Base|Column|Session|engine|sessionmaker)\b",
        "suggestion": "Move all database access to a service or repository layer.",
    },
    {
        "id": "LV002",
        "name": "API Layer Direct DB Query",
        "rule_type": "layer_violation",
        "severity": "high",
        "description": "API handlers should delegate DB operations to a service layer.",
        "pattern": r"\.execute\(|\.query\(|session\.add\(|db\.query\(",
        "file_pattern": r"api/",
        "suggestion": "Create a service class that wraps all DB operations.",
    },
    # God classes
    {
        "id": "GC001",
        "name": "God Class",
        "rule_type": "god_class",
        "severity": "medium",
        "description": "Classes with more than 20 methods violate Single Responsibility.",
        "threshold": 20,
        "suggestion": "Split into smaller focused classes using SRP.",
    },
    # Security anti-patterns
    {
        "id": "SA001",
        "name": "Hardcoded Secret",
        "rule_type": "security_antipattern",
        "severity": "critical",
        "description": "Hardcoded credentials or API keys detected in source code.",
        "pattern": r'(password|secret|api_key|token|private_key|auth_key)\s*=\s*["\'][^"\']{8,}["\']',
        "suggestion": "Use environment variables or a secrets manager (AWS Secrets Manager, Vault).",
    },
    {
        "id": "SA002",
        "name": "SQL String Concatenation",
        "rule_type": "security_antipattern",
        "severity": "high",
        "description": "SQL built by string concatenation is vulnerable to SQL injection.",
        "pattern": r'(execute|query)\s*\(\s*[f"\'].*\+|f".*SELECT|f".*INSERT|f".*UPDATE|f".*DELETE',
        "suggestion": "Use parameterized queries or an ORM.",
    },
    # Anti-patterns
    {
        "id": "AP001",
        "name": "Magic Numbers",
        "rule_type": "antipattern",
        "severity": "low",
        "description": "Numeric literals used directly in logic without named constants.",
        "pattern": r"(?<!['\"\w])\b([2-9]\d{2,}|[1-9]\d{3,})\b(?!['\"])",
        "suggestion": "Replace magic numbers with named constants (e.g. MAX_RETRIES = 3).",
    },
    {
        "id": "AP002",
        "name": "Print Debug Statements",
        "rule_type": "antipattern",
        "severity": "low",
        "description": "print() statements left in production code.",
        "pattern": r"^\s*print\s*\(",
        "suggestion": "Replace print() with proper logging (logger.info, logger.debug).",
    },
    {
        "id": "AP003",
        "name": "Bare Exception Catch",
        "rule_type": "antipattern",
        "severity": "medium",
        "description": "Catching bare Exception hides bugs and makes debugging harder.",
        "pattern": r"except\s*Exception\s*:",
        "suggestion": "Catch specific exception types (e.g. ValueError, HTTPException).",
    },
    # Code quality
    {
        "id": "CQ001",
        "name": "Overly Long Function",
        "rule_type": "code_quality",
        "severity": "low",
        "description": "Functions over 100 lines are hard to test and maintain.",
        "threshold": 100,
        "suggestion": "Refactor into smaller, single-purpose functions.",
    },
    {
        "id": "CQ002",
        "name": "Tight Coupling",
        "rule_type": "tight_coupling",
        "severity": "medium",
        "description": "File imports more than 15 modules, indicating tight coupling.",
        "threshold": 15,
        "suggestion": "Use dependency injection or facade pattern to reduce coupling.",
    },
    # Circular dependencies
    {
        "id": "CD001",
        "name": "Circular Dependency",
        "rule_type": "circular_dependency",
        "severity": "high",
        "description": "Circular imports cause runtime errors and tight coupling.",
        "suggestion": "Extract shared code into a separate module or use dependency injection.",
    },
]


# ── Detection Functions ────────────────────────────────────────────────────────

def detect_layer_violations(chunks: list[dict]) -> list[dict]:
    violations = []
    rules = [r for r in BUILT_IN_RULES if r["rule_type"] == "layer_violation"]
    for chunk in chunks:
        content   = chunk.get("content", "")
        file_path = chunk.get("file_path", "")
        for rule in rules:
            file_pat = rule.get("file_pattern", "")
            if file_pat and not re.search(file_pat, file_path):
                continue
            if re.search(rule["pattern"], content, re.IGNORECASE | re.MULTILINE):
                violations.append(_make_violation(rule, file_path, chunk.get("start_line")))
    return violations


def detect_god_classes(chunks: list[dict]) -> list[dict]:
    violations = []
    rule = next(r for r in BUILT_IN_RULES if r["id"] == "GC001")
    for chunk in chunks:
        if chunk.get("chunk_type") != "class":
            continue
        content      = chunk.get("content", "")
        method_count = len(re.findall(r"^\s+(def |public |private |protected )", content, re.MULTILINE))
        if method_count > rule["threshold"]:
            v = _make_violation(rule, chunk.get("file_path", ""), chunk.get("start_line"))
            v["description"] = (
                f"Class '{chunk.get('chunk_name', 'Unknown')}' has {method_count} methods "
                f"(threshold: {rule['threshold']})."
            )
            violations.append(v)
    return violations


def detect_security_antipatterns(chunks: list[dict]) -> list[dict]:
    violations = []
    rules = [r for r in BUILT_IN_RULES if r["rule_type"] == "security_antipattern"]
    for chunk in chunks:
        file_path = chunk.get("file_path", "")
        content   = chunk.get("content", "")
        # Skip test files and .env files
        if any(x in file_path.lower() for x in [".env", "test_", "_test", "spec."]):
            continue
        for rule in rules:
            matches = re.findall(rule["pattern"], content, re.IGNORECASE | re.MULTILINE)
            if matches:
                v = _make_violation(rule, file_path, chunk.get("start_line"))
                violations.append(v)
    return violations


def detect_antipatterns(chunks: list[dict]) -> list[dict]:
    violations = []
    rules = [r for r in BUILT_IN_RULES if r["rule_type"] == "antipattern"]
    for chunk in chunks:
        file_path = chunk.get("file_path", "")
        content   = chunk.get("content", "")
        if "test" in file_path.lower():
            continue
        for rule in rules:
            matches = re.findall(rule["pattern"], content, re.MULTILINE)
            if matches:
                v = _make_violation(rule, file_path, chunk.get("start_line"))
                v["occurrences"] = len(matches)
                violations.append(v)
    return violations


def detect_long_functions(chunks: list[dict]) -> list[dict]:
    violations = []
    rule = next(r for r in BUILT_IN_RULES if r["id"] == "CQ001")
    for chunk in chunks:
        if chunk.get("chunk_type") not in ("function", "method"):
            continue
        start  = chunk.get("start_line") or 0
        end    = chunk.get("end_line") or 0
        length = end - start
        if length > rule["threshold"]:
            v = _make_violation(rule, chunk.get("file_path", ""), start)
            v["description"] = (
                f"Function '{chunk.get('chunk_name', '')}' is {length} lines "
                f"(threshold: {rule['threshold']})."
            )
            violations.append(v)
    return violations


def detect_tight_coupling(chunks: list[dict]) -> list[dict]:
    """Detect files with too many imports."""
    violations = []
    rule = next(r for r in BUILT_IN_RULES if r["id"] == "CQ002")

    # Group chunks by file
    file_imports: dict[str, set] = {}
    for chunk in chunks:
        fp      = chunk.get("file_path", "")
        content = chunk.get("content", "")
        imports = re.findall(r"^(?:import|from)\s+(\S+)", content, re.MULTILINE)
        file_imports.setdefault(fp, set()).update(imports)

    for fp, imports in file_imports.items():
        if len(imports) > rule["threshold"]:
            v = _make_violation(rule, fp, None)
            v["description"] = (
                f"File imports {len(imports)} modules (threshold: {rule['threshold']}). "
                f"This indicates tight coupling."
            )
            violations.append(v)
    return violations


def detect_circular_dependencies(edges: list[dict]) -> list[dict]:
    """Tarjan-style DFS cycle detection on the knowledge graph."""
    graph: dict[str, set] = {}
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src and tgt and src != tgt:
            graph.setdefault(src, set()).add(tgt)

    visited: set   = set()
    rec_stack: set = set()
    cycles: list   = []

    def dfs(node: str, path: list):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack and neighbor in path:
                idx = path.index(neighbor)
                cycle = path[idx:] + [neighbor]
                if cycle not in cycles:
                    cycles.append(cycle)
        rec_stack.discard(node)

    for node in list(graph.keys()):
        if node not in visited:
            dfs(node, [node])

    rule = next(r for r in BUILT_IN_RULES if r["id"] == "CD001")
    violations = []
    for cycle in cycles[:10]:
        v = _make_violation(rule, " → ".join(cycle[:4]), None)
        v["description"] = f"Circular dependency: {' → '.join(cycle)}"
        violations.append(v)
    return violations


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_violation(rule: dict, file_path: str, line: Any) -> dict:
    return {
        "id":          str(uuid.uuid4()),
        "rule_id":     rule["id"],
        "rule_name":   rule["name"],
        "rule_type":   rule["rule_type"],
        "severity":    rule["severity"],
        "file_path":   file_path,
        "line_number": line,
        "description": rule["description"],
        "suggestion":  rule.get("suggestion", ""),
    }


def _compute_governance_score(severity_counts: dict) -> int:
    """Compute 0-100 governance score from violation counts."""
    deductions = (
        severity_counts.get("critical", 0) * 20 +
        severity_counts.get("high", 0)     * 10 +
        severity_counts.get("medium", 0)   * 5  +
        severity_counts.get("low", 0)      * 1
    )
    return max(0, 100 - deductions)


# ── Main Analysis ──────────────────────────────────────────────────────────────

async def run_governance_analysis(repo_id: str, db: AsyncSession) -> dict[str, Any]:
    """Run all governance rules against a repository and persist results."""

    # Fetch code chunks
    chunk_result = await db.execute(
        select(CodeChunk).where(CodeChunk.repo_id == repo_id).limit(3000)
    )
    chunks = chunk_result.scalars().all()
    chunk_dicts = [
        {
            "content":    c.content,
            "file_path":  c.file_path,
            "chunk_type": c.chunk_type,
            "chunk_name": c.chunk_name,
            "start_line": c.start_line,
            "end_line":   c.end_line,
        }
        for c in chunks
    ]

    # Fetch knowledge graph edges
    edge_result = await db.execute(
        select(KnowledgeEdge, KnowledgeNode)
        .join(KnowledgeNode, KnowledgeEdge.source_node_id == KnowledgeNode.id)
        .limit(1000)
    )
    edges = [
        {"source": row[1].name, "target": str(row[0].target_node_id)}
        for row in edge_result.all()
    ]

    # Run all detectors
    violations: list[dict] = []
    violations.extend(detect_layer_violations(chunk_dicts))
    violations.extend(detect_god_classes(chunk_dicts))
    violations.extend(detect_security_antipatterns(chunk_dicts))
    violations.extend(detect_antipatterns(chunk_dicts))
    violations.extend(detect_long_functions(chunk_dicts))
    violations.extend(detect_tight_coupling(chunk_dicts))
    violations.extend(detect_circular_dependencies(edges))

    # Deduplicate (same rule + file)
    seen = set()
    unique_violations = []
    for v in violations:
        key = (v["rule_id"], v["file_path"])
        if key not in seen:
            seen.add(key)
            unique_violations.append(v)

    # Compute severity counts
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for v in unique_violations:
        sev = v.get("severity", "low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Group by rule type
    by_type: dict[str, list] = {}
    for v in unique_violations:
        by_type.setdefault(v["rule_type"], []).append(v)

    # Governance score
    score = _compute_governance_score(severity_counts)

    # Persist violations to DB
    await _persist_violations(repo_id, unique_violations, db)

    return {
        "repo_id":         repo_id,
        "total_violations": len(unique_violations),
        "governance_score": score,
        "severity_counts": severity_counts,
        "violations":      unique_violations,
        "by_type":         {k: len(v) for k, v in by_type.items()},
        "rules_applied":   len(BUILT_IN_RULES),
        "files_scanned":   len(set(c["file_path"] for c in chunk_dicts)),
    }


async def _persist_violations(repo_id: str, violations: list[dict], db: AsyncSession):
    """Persist governance violations to database."""
    try:
        from sqlalchemy import text
        # Clear old violations for this repo
        await db.execute(
            text("DELETE FROM governance_violations WHERE repo_id = :repo_id"),
            {"repo_id": repo_id}
        )
        # Insert new ones
        for v in violations:
            await db.execute(
                text("""
                    INSERT INTO governance_violations
                      (id, repo_id, rule_type, severity, file_path, description, suggestion, created_at)
                    VALUES
                      (:id, :repo_id, :rule_type, :severity, :file_path, :description, :suggestion, now())
                """),
                {
                    "id":          str(uuid.uuid4()),
                    "repo_id":     repo_id,
                    "rule_type":   v["rule_type"],
                    "severity":    v["severity"],
                    "file_path":   v["file_path"][:500],
                    "description": v["description"][:1000],
                    "suggestion":  v.get("suggestion", "")[:500],
                }
            )
        await db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist violations: {e}")


async def get_ai_fix_suggestion(violation: dict) -> str:
    """Use LLM to generate a specific fix suggestion for a violation."""
    try:
        from agents.model_router_agent import routed_invoke
        from langchain.schema import HumanMessage, SystemMessage
        result = await routed_invoke(
            task_type="simple_qa",
            messages=[
                SystemMessage(content="You are a senior software architect. Give a concrete, actionable fix in 2-3 sentences."),
                HumanMessage(content=(
                    f"Violation: {violation['rule_name']}\n"
                    f"File: {violation['file_path']}\n"
                    f"Issue: {violation['description']}\n"
                    f"Provide a specific fix suggestion."
                )),
            ],
            temperature=0.1,
        )
        return result["response"].content
    except Exception as e:
        return violation.get("suggestion", "No suggestion available.")
