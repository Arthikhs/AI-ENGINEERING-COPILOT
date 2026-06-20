"""
Repository Change Intelligence Agent
On GitHub push webhook:
  1. Identify changed files
  2. Map each file to its architectural layer / service
  3. Detect which other services might be affected (via KG edges)
  4. Generate risk assessment using LLM
  5. Persist report to DB
"""
import logging
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from langchain.schema import HumanMessage, SystemMessage
from models.models import KnowledgeNode, KnowledgeEdge, Repository, ChangeIntelligenceReport
from agents.model_router_agent import routed_invoke

logger = logging.getLogger(__name__)

CHANGE_INTEL_PROMPT = """You are a senior software architect performing change impact analysis.

Given a list of changed files from a git push, analyze:

1. ARCHITECTURAL IMPACT
   - Which layers are affected? (API, service, data, config, test)
   - Is this a breaking change?
   - Are any public interfaces modified?

2. POTENTIAL RISKS
   - What could break downstream?
   - Are there migration concerns (DB schema, API contracts)?
   - Security implications?

3. AFFECTED SERVICES
   - Which services likely need testing or deployment?
   - Any cascading effects?

4. RECOMMENDATION
   - What should the team do before merging/deploying?

Respond in this JSON format:
{
  "architectural_impact": {
    "layers_affected": ["api", "service"],
    "is_breaking_change": false,
    "interfaces_modified": ["UserService.authenticate()"]
  },
  "risks": [
    {"level": "HIGH", "description": "...", "file": "..."}
  ],
  "affected_services": ["AuthService", "UserService"],
  "recommendation": "...",
  "summary": "One sentence summary"
}
"""


class ChangeIntelligenceAgent:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze(
        self,
        repo_id: str,
        repo_full_name: str,
        commit_sha: str,
        changed_files: List[str],
        pusher: str = "",
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Full change impact analysis for a push event."""

        # 1. Classify files by layer
        file_classifications = self._classify_files(changed_files)

        # 2. Find affected KG nodes for changed files
        affected_nodes = await self._find_affected_nodes(repo_id, changed_files)

        # 3. Walk KG edges — find indirectly affected services
        downstream = await self._find_downstream_services(affected_nodes)

        # 4. LLM risk analysis
        context = self._build_context(
            changed_files, file_classifications, affected_nodes, downstream
        )

        result = await routed_invoke(
            task_type="architecture",
            messages=[
                SystemMessage(content=CHANGE_INTEL_PROMPT),
                HumanMessage(content=(
                    f"Repository: {repo_full_name}\n"
                    f"Branch: {branch}\n"
                    f"Commit: {commit_sha}\n"
                    f"Pusher: {pusher}\n\n"
                    f"{context}"
                )),
            ],
        )

        import json
        try:
            analysis = json.loads(result["response"].content)
        except Exception:
            analysis = {"summary": result["response"].content, "risks": [], "affected_services": []}

        # 5. Merge KG-detected affected services with LLM findings
        kg_affected = [n["name"] for n in downstream]
        llm_affected = analysis.get("affected_services", [])
        all_affected = list(dict.fromkeys(kg_affected + llm_affected))  # dedupe, preserve order

        report_data = {
            "repo_id": repo_id,
            "repo_full_name": repo_full_name,
            "commit_sha": commit_sha,
            "branch": branch,
            "pusher": pusher,
            "files_changed": changed_files,
            "file_classifications": file_classifications,
            "architectural_impact": analysis.get("architectural_impact", {}),
            "risks": analysis.get("risks", []),
            "affected_services": all_affected,
            "kg_downstream_nodes": downstream,
            "recommendation": analysis.get("recommendation", ""),
            "summary": analysis.get("summary", ""),
            "model_used": result["model"],
            "latency_ms": result["latency_ms"],
        }

        # 6. Persist
        report = ChangeIntelligenceReport(
            repo_id=repo_id,
            commit_sha=commit_sha,
            branch=branch,
            pusher=pusher,
            files_changed=changed_files,
            architectural_impact=analysis.get("architectural_impact", {}),
            risks=analysis.get("risks", []),
            affected_services=all_affected,
            recommendation=analysis.get("recommendation", ""),
            summary=analysis.get("summary", ""),
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)

        report_data["report_id"] = str(report.id)

        # Notify Slack / Teams if any HIGH/CRITICAL risks found
        high_risks = [r for r in analysis.get("risks", []) if r.get("level", "").upper() in ("HIGH", "CRITICAL")]
        if high_risks:
            msg = (
                f"⚠️ *Change Intelligence Alert* — `{repo_full_name}`\n"
                f"Commit `{commit_sha[:8]}` by {pusher} on `{branch}`\n"
                f"{len(high_risks)} high/critical risk(s) detected\n"
                f"{analysis.get('summary', '')[:300]}"
            )
            try:
                from api.integrations import notify_slack, notify_teams
                await notify_slack(msg)
                await notify_teams(msg)
            except Exception as e:
                logger.warning(f"Change intel notification failed (non-fatal): {e}")

        return report_data

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _classify_files(self, files: List[str]) -> Dict[str, str]:
        """Classify each changed file into an architectural layer."""
        classification = {}
        for f in files:
            f_lower = f.lower()
            if any(k in f_lower for k in ["test", "spec", "__tests__"]):
                layer = "test"
            elif any(k in f_lower for k in ["migration", "alembic", "schema"]):
                layer = "database_migration"
            elif any(k in f_lower for k in ["api/", "router", "handler", "controller", "endpoint"]):
                layer = "api"
            elif any(k in f_lower for k in ["model", "entity", "dto"]):
                layer = "model"
            elif any(k in f_lower for k in ["config", ".env", "settings"]):
                layer = "config"
            elif any(k in f_lower for k in ["docker", "k8s", "helm", "terraform", "infra"]):
                layer = "infrastructure"
            elif any(k in f_lower for k in ["service", "manager", "processor"]):
                layer = "service"
            else:
                layer = "general"
            classification[f] = layer
        return classification

    async def _find_affected_nodes(
        self, repo_id: str, changed_files: List[str]
    ) -> List[Dict]:
        """Find KG nodes whose file_path matches any changed file."""
        if not changed_files:
            return []
        nodes = []
        for fp in changed_files:
            result = await self.db.execute(
                select(KnowledgeNode).where(
                    KnowledgeNode.repo_id == repo_id,
                    KnowledgeNode.file_path == fp,
                )
            )
            for node in result.scalars().all():
                nodes.append({
                    "id": str(node.id),
                    "name": node.name,
                    "type": node.node_type,
                    "file_path": node.file_path,
                })
        return nodes

    async def _find_downstream_services(self, affected_nodes: List[Dict]) -> List[Dict]:
        """Walk KG edges — find services that depend on the changed nodes."""
        downstream = {}
        for node in affected_nodes:
            result = await self.db.execute(
                select(KnowledgeEdge, KnowledgeNode)
                .join(KnowledgeNode, KnowledgeEdge.source_node_id == KnowledgeNode.id)
                .where(KnowledgeEdge.target_node_id == node["id"])
            )
            for edge, source_node in result.fetchall():
                sid = str(source_node.id)
                if sid not in downstream:
                    downstream[sid] = {
                        "id": sid,
                        "name": source_node.name,
                        "type": source_node.node_type,
                        "depends_on": node["name"],
                        "edge_type": edge.edge_type,
                    }
        return list(downstream.values())

    def _build_context(
        self,
        files: List[str],
        classifications: Dict[str, str],
        affected_nodes: List[Dict],
        downstream: List[Dict],
    ) -> str:
        lines = ["=== Changed Files ==="]
        for f in files[:30]:
            layer = classifications.get(f, "general")
            lines.append(f"  [{layer}] {f}")

        if affected_nodes:
            lines.append("\n=== Directly Affected Services/Modules (from Knowledge Graph) ===")
            for n in affected_nodes:
                lines.append(f"  {n['name']} ({n['type']}) — {n['file_path']}")

        if downstream:
            lines.append("\n=== Downstream Services (depend on changed modules) ===")
            for d in downstream:
                lines.append(f"  {d['name']} ({d['type']}) — depends on {d['depends_on']} via {d['edge_type']}")

        return "\n".join(lines)
