"""
Unified API for: Security Review, Refactoring, Test Generation,
System Design Diagram, Semantic Search, LLM Evaluation (Ragas).
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from models.models import User, Repository
from database import get_db
from api.auth import get_current_user
from agents.security_agent import SecurityReviewAgent
from agents.refactoring_agent import RefactoringAgent
from agents.test_generation_agent import TestGenerationAgent
from agents.system_design_agent import SystemDesignAgent
from agents.documentation_agent import DocumentationAgent
from rag.semantic_search import SemanticSearchService

router = APIRouter(prefix="/agents", tags=["agents"])


# ── Request models ─────────────────────────────────────────────────────────────

class RepoRequest(BaseModel):
    repo_id: str

class RefactorRequest(BaseModel):
    repo_id: str
    target_file: Optional[str] = None

class TestGenRequest(BaseModel):
    repo_id: str
    target: str               # function/class name or description
    language: Optional[str] = None

class SystemDesignRequest(BaseModel):
    repo_id: str
    query: str                # e.g. "Explain order processing flow"

class SearchRequest(BaseModel):
    repo_id: str
    query: str
    top_k: int = 10
    language_filter: Optional[str] = None
    chunk_type_filter: Optional[str] = None

class DocumentationRequest(BaseModel):
    repo_id: str
    target: Optional[str] = None   # specific file, class, or function to document


class EvalRequest(BaseModel):
    repo_id: str
    question: str
    answer: str
    contexts: list[str]


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_indexed_repo(repo_id: str, user_id, db: AsyncSession) -> Repository:
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id,
            Repository.owner_id == user_id,
            Repository.is_indexed == True,
        )
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found or not indexed")
    return repo


# ── Security Review ────────────────────────────────────────────────────────────

@router.post("/security/review")
async def security_review(
    body: RepoRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full security scan: SQL injection, hardcoded secrets, XSS, SSRF, auth flaws, etc."""
    await _get_indexed_repo(body.repo_id, current_user.id, db)
    agent = SecurityReviewAgent(db)
    return await agent.review(body.repo_id)


# ── Refactoring ────────────────────────────────────────────────────────────────

@router.post("/refactor/analyze")
async def refactor_analyze(
    body: RefactorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detect code smells (large class, duplicate code, long methods, dead code) and suggest refactoring."""
    await _get_indexed_repo(body.repo_id, current_user.id, db)
    agent = RefactoringAgent(db)
    return await agent.analyze(body.repo_id, target_file=body.target_file)


# ── Test Generation ────────────────────────────────────────────────────────────

@router.post("/tests/generate")
async def generate_tests(
    body: TestGenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate unit tests (pytest / JUnit / Jest) for any function, class, or module."""
    await _get_indexed_repo(body.repo_id, current_user.id, db)
    agent = TestGenerationAgent(db)
    return await agent.generate(body.repo_id, body.target, language=body.language)


# ── System Design Diagram ──────────────────────────────────────────────────────

@router.post("/system-design/generate")
async def generate_system_design(
    body: SystemDesignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate Mermaid + PlantUML architecture diagrams from natural language queries."""
    await _get_indexed_repo(body.repo_id, current_user.id, db)
    agent = SystemDesignAgent(db)
    return await agent.generate(body.query, body.repo_id)


# ── Semantic Code Search ───────────────────────────────────────────────────────

@router.post("/search")
async def semantic_search(
    body: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hybrid semantic search (BM25 + Vector + Reranker) over indexed code."""
    await _get_indexed_repo(body.repo_id, current_user.id, db)
    svc = SemanticSearchService(db)
    results = await svc.search(
        query=body.query,
        repo_id=body.repo_id,
        top_k=body.top_k,
        language_filter=body.language_filter,
        chunk_type_filter=body.chunk_type_filter,
    )
    return {"query": body.query, "results": results, "count": len(results)}


# ── Documentation Generation ───────────────────────────────────────────────────

@router.post("/docs/generate")
async def generate_documentation(
    body: DocumentationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate README, API docs, and sequence diagrams from source code."""
    await _get_indexed_repo(body.repo_id, current_user.id, db)
    agent = DocumentationAgent(db)
    return await agent.generate(body.repo_id, target=body.target)


# ── LLM Evaluation (Ragas) ─────────────────────────────────────────────────────

@router.post("/eval")
async def evaluate_answer(
    body: EvalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluate RAG answer quality using Ragas metrics:
    - faithfulness: is the answer grounded in the retrieved context?
    - answer_relevancy: does the answer address the question?
    - context_recall: do the contexts cover the answer?
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_recall
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from config import get_settings
        settings = get_settings()

        data = {
            "question": [body.question],
            "answer": [body.answer],
            "contexts": [body.contexts],
            "ground_truth": [body.answer],  # self-eval: use answer as ground truth
        }
        dataset = Dataset.from_dict(data)

        llm_wrapper = LangchainLLMWrapper(
            ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key)
        )
        emb_wrapper = LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(api_key=settings.openai_api_key)
        )

        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_recall],
            llm=llm_wrapper,
            embeddings=emb_wrapper,
        )
        scores = result.to_pandas().iloc[0].to_dict()
        return {
            "question": body.question,
            "faithfulness": round(float(scores.get("faithfulness", 0)), 4),
            "answer_relevancy": round(float(scores.get("answer_relevancy", 0)), 4),
            "context_recall": round(float(scores.get("context_recall", 0)), 4),
        }
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="ragas not installed. Run: pip install ragas datasets",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
