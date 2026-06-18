"""
Knowledge Graph Builder
Parses import/dependency relationships from code chunks
and stores them as nodes + edges in the knowledge graph.
"""
import re
import uuid
from typing import List, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from models.models import KnowledgeNode, KnowledgeEdge, Repository
import logging

logger = logging.getLogger(__name__)

# Language-specific import patterns
IMPORT_PATTERNS = {
    "Python": [
        re.compile(r"^from\s+([\w.]+)\s+import", re.MULTILINE),
        re.compile(r"^import\s+([\w.]+)", re.MULTILINE),
    ],
    "JavaScript": [
        re.compile(r'import\s+.*?\s+from\s+[\'\"]([\w@/.-]+)[\'\"]', re.MULTILINE),
        re.compile(r'require\([\'\"]([\w@/.-]+)[\'\"]\)', re.MULTILINE),
    ],
    "TypeScript": [
        re.compile(r'import\s+.*?\s+from\s+[\'\"]([\w@/.-]+)[\'\"]', re.MULTILINE),
        re.compile(r'require\([\'\"]([\w@/.-]+)[\'\"]\)', re.MULTILINE),
    ],
    "Java": [
        re.compile(r'^import\s+([\w.]+);', re.MULTILINE),
    ],
    "Go": [
        re.compile(r'"([\w./\-]+)"', re.MULTILINE),
    ],
}

# Class/service detection patterns per language
CLASS_PATTERNS = {
    "Python": re.compile(r'^class\s+(\w+)', re.MULTILINE),
    "JavaScript": re.compile(r'class\s+(\w+)', re.MULTILINE),
    "TypeScript": re.compile(r'class\s+(\w+)', re.MULTILINE),
    "Java": re.compile(r'(?:public|private|protected)?\s*class\s+(\w+)', re.MULTILINE),
}


class KnowledgeGraphBuilder:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_for_repo(self, repo_id: str) -> Dict:
        """Build knowledge graph nodes and edges for a single repository."""
        # Load repo info
        result = await self.db.execute(
            select(Repository).where(Repository.id == repo_id)
        )
        repo = result.scalar_one_or_none()
        if not repo:
            return {"error": "Repository not found"}

        # Clear existing nodes/edges for this repo
        await self.db.execute(
            delete(KnowledgeNode).where(KnowledgeNode.repo_id == repo_id)
        )
        await self.db.flush()

        # Fetch all embeddings for this repo grouped by file
        rows = await self._fetch_file_contents(repo_id)

        nodes_created = 0
        edges_created = 0
        file_node_map: Dict[str, uuid.UUID] = {}  # file_path → node_id

        # Pass 1: Create nodes for each file/class
        for file_path, content, language in rows:
            node_type = self._classify_node_type(file_path, content, language)
            node_name = self._extract_primary_name(file_path, content, language)

            node = KnowledgeNode(
                repo_id=repo_id,
                repo_full_name=repo.full_name,
                node_type=node_type,
                name=node_name,
                file_path=file_path,
                language=language,
                metadata={"classes": self._extract_classes(content, language)},
            )
            self.db.add(node)
            await self.db.flush()
            file_node_map[file_path] = node.id
            nodes_created += 1

        # Pass 2: Create edges from import analysis
        for file_path, content, language in rows:
            source_id = file_node_map.get(file_path)
            if not source_id:
                continue

            imports = self._extract_imports(content, language)
            for imp in imports:
                # Try to resolve import to a known file node
                target_id = self._resolve_import(imp, file_node_map, language)
                if target_id and target_id != source_id:
                    # Check if edge already exists (increment weight)
                    existing = await self._find_edge(source_id, target_id)
                    if existing:
                        existing.weight += 1
                    else:
                        edge = KnowledgeEdge(
                            source_node_id=source_id,
                            target_node_id=target_id,
                            edge_type="imports",
                            weight=1,
                        )
                        self.db.add(edge)
                        edges_created += 1

        await self.db.commit()
        logger.info(f"Knowledge graph built: {nodes_created} nodes, {edges_created} edges for {repo.full_name}")
        return {"nodes": nodes_created, "edges": edges_created, "repo": repo.full_name}

    async def _fetch_file_contents(self, repo_id: str) -> List[Tuple[str, str, str]]:
        """Fetch one representative chunk per file."""
        result = await self.db.execute(
            text("""
                SELECT DISTINCT ON (file_path) file_path, content, language
                FROM embeddings
                WHERE repo_id = :repo_id
                ORDER BY file_path
            """).bindparams(repo_id=repo_id)
        )
        return [(r.file_path, r.content, r.language or "") for r in result.fetchall()]

    async def _find_edge(self, source_id: uuid.UUID, target_id: uuid.UUID):
        result = await self.db.execute(
            select(KnowledgeEdge).where(
                KnowledgeEdge.source_node_id == source_id,
                KnowledgeEdge.target_node_id == target_id,
            )
        )
        return result.scalar_one_or_none()

    def _extract_imports(self, content: str, language: str) -> List[str]:
        patterns = IMPORT_PATTERNS.get(language, [])
        imports = []
        for pattern in patterns:
            imports.extend(pattern.findall(content))
        return list(set(imports))

    def _extract_classes(self, content: str, language: str) -> List[str]:
        pattern = CLASS_PATTERNS.get(language)
        if not pattern:
            return []
        return pattern.findall(content)[:10]

    def _classify_node_type(self, file_path: str, content: str, language: str) -> str:
        name_lower = file_path.lower()
        if any(k in name_lower for k in ["service", "svc"]):
            return "service"
        if any(k in name_lower for k in ["controller", "router", "handler", "view"]):
            return "controller"
        if any(k in name_lower for k in ["model", "entity", "schema"]):
            return "model"
        if any(k in name_lower for k in ["repo", "repository", "dao", "store"]):
            return "repository"
        if any(k in name_lower for k in ["util", "helper", "common", "shared", "lib"]):
            return "library"
        if any(k in name_lower for k in ["config", "setting", "env"]):
            return "config"
        if any(k in name_lower for k in ["test", "spec"]):
            return "test"
        return "module"

    def _extract_primary_name(self, file_path: str, content: str, language: str) -> str:
        # Try class name first
        classes = self._extract_classes(content, language)
        if classes:
            return classes[0]
        # Fall back to filename without extension
        filename = file_path.split("/")[-1]
        return filename.rsplit(".", 1)[0] if "." in filename else filename

    def _resolve_import(
        self, import_str: str, file_node_map: Dict[str, uuid.UUID], language: str
    ) -> uuid.UUID | None:
        """Try to match an import string to a known file node."""
        # Normalize import to path-like string
        normalized = import_str.replace(".", "/").replace("-", "_").lower()

        for file_path, node_id in file_node_map.items():
            path_lower = file_path.lower().replace("\\", "/")
            # Strip extension for comparison
            path_stem = path_lower.rsplit(".", 1)[0]
            if normalized in path_stem or path_stem.endswith(normalized):
                return node_id

        return None
