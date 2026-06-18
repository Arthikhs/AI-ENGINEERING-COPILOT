from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from observability.telemetry import setup_observability
from api.github_auth import router as auth_router
from api.repositories import router as repos_router
from api.chat import router as chat_router
from api.pr_review import router as pr_router
from api.architecture import router as arch_router
from api.webhooks import router as webhook_router
from api.knowledge_graph import router as kg_router
from api.security import router as security_router
from api.refactoring import router as refactor_router
from api.test_generation import router as tests_router
from api.tools import router as tools_router
from api.agents import router as agents_router
from api.organizations import router as orgs_router
from api.cost_analytics import router as costs_router
from api.model_router import router as model_router_router
from api.hitl import router as hitl_router
from api.prompts import router as prompts_router
from api.benchmarks import router as benchmarks_router
from api.executive import router as executive_router
from api.change_intelligence import router as change_intel_router
from api.integrations import router as integrations_router
from config import get_settings
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

# Configure LangSmith tracing
if settings.langchain_tracing_v2 and settings.langchain_api_key:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Engineering Copilot...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="AI Engineering Copilot",
    version=settings.app_version,
    description="Intelligent platform for developer productivity using RAG and Agentic AI",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_observability(app)

app.include_router(auth_router)
app.include_router(repos_router)
app.include_router(chat_router)
app.include_router(pr_router)
app.include_router(arch_router)
app.include_router(webhook_router)
app.include_router(kg_router)
app.include_router(security_router)
app.include_router(refactor_router)
app.include_router(tests_router)
app.include_router(tools_router)
app.include_router(agents_router)
app.include_router(orgs_router)
app.include_router(costs_router)
app.include_router(model_router_router)
app.include_router(hitl_router)
app.include_router(prompts_router)
app.include_router(benchmarks_router)
app.include_router(executive_router)
app.include_router(change_intel_router)
app.include_router(integrations_router)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.app_version}


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
