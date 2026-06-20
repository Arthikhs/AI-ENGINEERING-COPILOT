"""
Architecture Governance Engine
Detects violations: layer violations, circular deps, god classes, anti-patterns.
"""
import re
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import CodeChunk, KnowledgeEdge, KnowledgeNode

logger = logging.getLogger(__name__)

BUILT_IN_RULES = [
    {
        "name": "No Direct DB Access from Controllers",
        "rule_type": "layer_violation",
        "severity": "high",
        "description": "Controllers/routes should not import database models directly.",
        "pattern": r"(router|controller|route).*import.*\b(Base|Column|Session|engine)\b",
    },
    {
        "name": "God Class Detection",
        "rule_type": "god_class",
        "severity": "medium",
        "description": "Classes with more than 20 methods indicate poor separation of concerns.",
        "threshold": 20,
    },
    {
        "name": "Circular Import Detection",
        "rule_type": "circular_dependency",
        "severity": "high",
        "description": "Circular imports cause runtime errors and tight coupling.",
    },
    {
        "name": "Direct Database in API Layer",
        "rule_type": "layer_violation",
        "severity": "high",
        "description": "API layer should use service layer, not query DB directly.",
        "pattern": r"api/.*\b(execute|query|session\.add|db\.query)\b",
    },
    {
        "name": "Hardcoded Secrets",
        "rule_type": "security_antipattern",
        "severity": "critical",
        "description": "Hardcoded credentials or secrets detected.",
        "pattern": r"(password|secret|api_key|token)\s*=\s*[\"'][^\"']{8,}[\"']",
    },
    {
        "name": "Overly Long Functions",
        "rule_type": "code_quality",
        "severity": "low",
        "description": "Functions exceeding 100 lines reduce maintainability.",
        "threshold": 100,
    },
]


def detect_layer_violations(chunks: list[dict]) -> list[dict]:
    violations = []
    for chunk in chunks:
        content = chunk.get("content", "")
        file_path = chunk.get("file_path", "")
        for rule in BUILT_IN_RULES:
            if rule["rule_type"] != "layer_violation":
                continue
            pattern = rule.get("pattern", "")
            if pattern and re.search(pattern, content, re.IGNORECASE):
                violations.append({
                    "rule_type": rule["rule_type"],
                    "severity": rule["severity"],
                    "file_path": file_path,
                    "description": rule["description"],
                    "rule_name": rule["name"],
                    "suggestion": "Move database access to a dedicated service/repository layer.",
                })
    return violations


def detect_god_classes(chunks: list[dict]) -> list[dict]:
    violations = []
    for chunk in chunks:
        if chunk.get("chunk_type") != "class":
            continue
        content = chunk.get("content", "")
        method_count = len(re.findall(r"^\s+def ", content, re.MULTILINE))
        if method_count > 20:
            violations.append({
                "rule_type": "god_class",
                "severity": "medium",
                "file_path": chunk.get("file_path", ""),
                "description": f"Class '{chunk.get('chunk_name', 'Unknown')}' has {method_count} methods (threshold: 20).",
                "rule_name": "God Class Detection",
                "suggestion": "Break this class into smaller, focused classes (Single Responsibility Principle).",
            })
    return violations


def detect_security_antipatterns(chunks: list[dict]) -> list[dict]:
    violations = []
    pattern = re.compile(
        r'(password|secret|api_key|token|private_key)\s*=\s*["\'][^"\']{8,}["\']',
        re.IGNORECASE
    )
    for chunk in chunks:
        content = chunk.get("content", "")
        file_path = chunk.get("file_path", "")
        if ".env" in file_path or "test" in file_path.lower():
            continue
        matches = pattern.findall(content)
        if matches:
            violations.append({
                "rule_type": "security_antipattern",
                "severity": "critical",
                "file_path": file_path,
                "description": f"Possible hardcoded secret detected: {matches[0][0]}",
                "rule_name": "Hardcoded Secrets",
                "suggestion": "Move secrets to environment variables or a secrets manager.",
            })
    return violations


def detect_long_functions(chunks: list[dict]) -> list[dict]:
    violations = []
    for chunk in chunks:
        if chunk.get("chunk_type") not in ("function", "method"):
            continue
        start = chunk.get("start_line", 0) or 0
        end = chunk.get("end_line", 0) or 0
        length = end - start
        if length > 100:
            violations.append({
                "rule_type": "code_quality",
                "severity": "low",
                "file_path": chunk.get("file_path", ""),
                "description": f"Function '{chunk.get('chunk_name', '')}' is {length} lines long (threshold: 100).",
                "rule_name": "Overly Long Functions",
                "suggestion": "Refactor into smaller, composable functions.",
            })
    return violations


def detect_circular_dependencies(edges: list[dict]) -> list[dict]:
    """Simple cycle detection using DFS on knowledge graph edges."""
    graph: dict[str, set] = {}
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src and tgt:
            graph.setdefault(src, set()).add(tgt)

    visited, rec_stack = set(), set()
    cycles = []

    def dfs(node, path):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path + [neighbor])
            elif neighbor in rec_stack:
                cycle_start = path.index(neighbor) if neighbor in path else 0
                cycles.append(path[cycle_start:] + [neighbor])
        rec_stack.discard(node)

    for node in graph:
        if node not in visited:
            dfs(node, [node])

    violations = []
    for cycle in cycles[:10]:  # limit to 10
        violations.append({
            "rule_type": "circular_dependency",
            "severity": "high",
            "file_path": " → ".join(cycle),
            "description": f"Circular dependency detected: {' → '.join(cycle)}",
            "rule_name": "Circular Import Detection",
            "suggestion": "Introduce an interface or break the cycle using dependency injection.",
        })
    return violations


async def run_governance_analysis(repo_id: str, db: AsyncSession) -> dict[str, Any]:
    """Run all governance rules against a repository."""
    result = await db.execute(
        select(CodeChunk).where(CodeChunk.repo_id == repo_id).limit(2000)
    )
    chunks = result.scalars().all()
    chunk_dicts = [
        {
            "content": c.content,
            "file_path": c.file_path,
            "chunk_type": c.chunk_type,
            "chunk_name": c.chunk_name,
            "start_line": c.start_line,
            "end_line": c.end_line,
        }
        for c in chunks
    ]

    edge_result = await db.execute(
        select(KnowledgeEdge, KnowledgeNode)
        .join(KnowledgeNode, KnowledgeEdge.source_node_id == KnowledgeNode.id)
        .limit(500)
    )
    edges = [
        {"source": row[1].name, "target": str(row[0].target_node_id)}
        for row in edge_result.all()
    ]

    violations = []
    violations.extend(detect_layer_violations(chunk_dicts))
    violations.extend(detect_god_classes(chunk_dicts))
    violations.extend(detect_security_antipatterns(chunk_dicts))
    violations.extend(detect_long_functions(chunk_dicts))
    violations.extend(detect_circular_dependencies(edges))

    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for v in violations:
        sev = v.get("severity", "low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return {
        "total_violations": len(violations),
        "severity_counts": severity_counts,
        "violations": violations,
        "rules_applied": len(BUILT_IN_RULES),
    }
