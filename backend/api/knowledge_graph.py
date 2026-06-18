from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from models.models import User, Repository
from database import get_db
from api.auth import get_current_user
from agents.knowledge_graph_agent import KnowledgeGraphAgent
from rag.knowledge_graph import KnowledgeGraphBuilder

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


class KGQueryRequest(BaseModel):
    question: str


class BuildGraphRequest(BaseModel):
    repo_ids: Optional[List[str]] = None  # None = all indexed repos


class DependentsRequest(BaseModel):
    node_name: str


@router.post("/build")
async def build_knowledge_graph(
    body: BuildGraphRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Build / rebuild the knowledge graph for given repos.
    Parses imports and creates nodes + edges.
    Runs as a background task.
    """
    if body.repo_ids:
        # Validate ownership
        result = await db.execute(
            select(Repository).where(
                Repository.id.in_(body.repo_ids),
                Repository.owner_id == current_user.id,
                Repository.is_indexed == True,
            )
        )
        repos = result.scalars().all()
    else:
        # All indexed repos for this user
        result = await db.execute(
            select(Repository).where(
                Repository.owner_id == current_user.id,
                Repository.is_indexed == True,
            )
        )
        repos = result.scalars().all()

    if not repos:
        raise HTTPException(status_code=400, detail="No indexed repositories found")

    repo_ids = [str(r.id) for r in repos]

    background_tasks.add_task(_build_graphs_bg, repo_ids)

    return {
        "message": f"Building knowledge graph for {len(repos)} repositories",
        "repos": [r.full_name for r in repos],
    }


@router.get("/graph")
async def get_knowledge_graph(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the full multi-repo knowledge graph (nodes + edges) for visualization."""
    agent = KnowledgeGraphAgent(db=db)
    return await agent.get_graph(user_id=str(current_user.id))


@router.post("/query")
async def query_knowledge_graph(
    body: KGQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ask a cross-repository question using KG + RAG Fusion:
    Vector Search + Knowledge Graph Traversal + Cross-Encoder Reranker.
    Examples:
      - 'Which services indirectly depend on PaymentService?'
      - 'Which repos use the auth library?'
      - 'Show the dependency chain from AuthService to Database'
    """
    agent = KnowledgeGraphAgent(db=db)
    return await agent.query(
        question=body.question,
        user_id=str(current_user.id),
    )


@router.post("/dependents")
async def find_dependents(
    body: DependentsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Find all services/modules that depend on a specific node.
    Example: { 'node_name': 'UserService' }
    Returns: list of services that import/call UserService
    """
    agent = KnowledgeGraphAgent(db=db)
    return await agent.find_dependents(
        node_name=body.node_name,
        user_id=str(current_user.id),
    )


@router.get("/stats")
async def get_graph_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return summary statistics about the knowledge graph."""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT
                COUNT(DISTINCT kn.id) AS total_nodes,
                COUNT(DISTINCT ke.id) AS total_edges,
                COUNT(DISTINCT kn.repo_id) AS total_repos,
                COUNT(DISTINCT kn.node_type) AS node_types
            FROM knowledge_nodes kn
            LEFT JOIN knowledge_edges ke
                ON ke.source_node_id = kn.id OR ke.target_node_id = kn.id
            JOIN repositories r ON r.id = kn.repo_id
            WHERE r.owner_id = :user_id
        """).bindparams(user_id=str(current_user.id))
    )
    row = result.fetchone()

    # Node type breakdown
    type_result = await db.execute(
        text("""
            SELECT kn.node_type, COUNT(*) as count
            FROM knowledge_nodes kn
            JOIN repositories r ON r.id = kn.repo_id
            WHERE r.owner_id = :user_id
            GROUP BY kn.node_type
            ORDER BY count DESC
        """).bindparams(user_id=str(current_user.id))
    )

    return {
        "total_nodes": row.total_nodes or 0,
        "total_edges": row.total_edges or 0,
        "total_repos": row.total_repos or 0,
        "node_type_breakdown": {r.node_type: r.count for r in type_result.fetchall()},
    }


async def _build_graphs_bg(repo_ids: List[str]):
    """Background task: build knowledge graph for multiple repos."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        builder = KnowledgeGraphBuilder(db)
        for repo_id in repo_ids:
            try:
                result = await builder.build_for_repo(repo_id)
                print(f"KG built: {result}")
            except Exception as e:
                print(f"KG build failed for {repo_id}: {e}")

    await engine.dispose()
