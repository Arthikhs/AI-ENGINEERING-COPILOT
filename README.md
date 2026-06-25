# 🤖 AI Engineering Copilot Platform

> **An intelligent full-stack AI platform for developer productivity — featuring multi-agent orchestration, hybrid RAG, knowledge graph fusion, model routing, human-in-the-loop workflows, prompt management, agent benchmarking, Slack/Teams integration, repository change intelligence, and an executive engineering dashboard.**

[![CI/CD](https://github.com/your-username/ai-engineering-copilot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/your-username/ai-engineering-copilot/actions)

Built with **LangGraph** · **FastAPI** · **React** · **PostgreSQL/pgvector** · **GPT-4o** · **Claude 3.5** · **Llama 3** · **OpenTelemetry** · **Ragas**

---

## 🎯 What Is This?

Engineering teams waste massive time on knowledge silos, slow PR reviews, architecture drift, and lack of AI visibility for leadership. **AI Engineering Copilot** solves all of this with a production-grade AI platform that:

- Continuously ingests your GitHub repositories into a semantic knowledge base
- Routes every task to the **optimal LLM** (GPT-4o-mini for Q&A, Claude for security, GPT-4o for architecture, Llama 3 for test generation)
- Answers deep architectural questions using **Knowledge Graph + RAG Fusion** (vector + BM25 + graph traversal + reranker)
- Enforces **human approval** before posting high-severity security findings to GitHub
- Lets you manage, version, A/B test, and roll back **prompts** used by every agent
- Benchmarks agents across accuracy, latency, cost, and hallucination rate
- Automatically generates **change impact reports** on every GitHub push
- Sends alerts and accepts commands via **Slack** and **Microsoft Teams**
- Gives engineering managers an **executive dashboard** with cost trends, security risks, and AI usage

---

## 🏗️ System Architecture

```
                     ┌─────────────────┐
                     │    GitHub Repo  │
                     └────────┬────────┘
                              │ OAuth / Webhook
                              ▼
                 ┌────────────────────────┐
                 │ Repository Ingestion   │
                 │  GitPython + Walker    │
                 └────────┬───────────────┘
                          │
                          ▼
                 ┌────────────────────────┐
                 │  Code Chunking Engine  │
                 │  AST + Regex + Window  │
                 └────────┬───────────────┘
                          │
                          ▼
                 ┌────────────────────────┐
                 │  Embedding Generation  │
                 │  text-embedding-3-large│
                 │  Redis Cache (7-day)   │
                 └────────┬───────────────┘
                          │
                          ▼
                 ┌────────────────────────┐
                 │  PostgreSQL + pgvector │
                 │  HNSW Index            │
                 └────────┬───────────────┘
                          │
                          ▼
          ┌───────────────────────────────────────┐
          │        Model Router Agent              │
          │  simple_qa    → gpt-4o-mini            │
          │  security     → claude-3-5-sonnet      │
          │  architecture → gpt-4o                 │
          │  test_gen     → llama3 (local)         │
          │  Tracks: cost · latency · quality      │
          └───────────────┬───────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────────────┐
          │   KG + RAG Fusion Retriever            │
          │   Vector + BM25 + Graph Traversal      │
          │   + Cross-Encoder Reranker (BGE)       │
          └───────────────┬───────────────────────┘
                          │
                          ▼
          ┌───────────────────────────────────────┐
          │  Multi-Agent LangGraph Pipeline        │
          │  Planner → Retriever                  │
          │  Security (HITL) | Architecture        │
          │  Refactor | TestGen | Design | Docs    │
          │  Reviewer → Response                  │
          └───────────────┬───────────────────────┘
                          │
               ┌──────────┴──────────┐
               │    FastAPI Backend   │
               │    LangSmith / OTel  │
               └──────────┬──────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     React Frontend   Slack Bot      Teams Bot
     18 Pages · SSE  @copilot cmds  @copilot cmds
```

---

## ⚙️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18, TypeScript, Vite | UI framework |
| **Styling** | Tailwind CSS, lucide-react | Design system |
| **State** | Zustand + React Query | Client state + server cache |
| **Backend** | FastAPI, Python 3.12 | REST API + SSE streaming |
| **AI Agents** | LangGraph, LangChain | Multi-agent orchestration |
| **LLMs** | GPT-4o, GPT-4o-mini, Claude 3.5, Gemini 1.5, Llama 3 | Multi-model routing |
| **Embeddings** | text-embedding-3-large | 1536-dim code vectors |
| **Vector DB** | PostgreSQL 16 + pgvector | HNSW similarity search |
| **Hybrid RAG** | BM25 + pgvector + BGE Reranker + KG Traversal | Production-grade fusion retrieval |
| **Cache** | Redis 7 | Embedding cache + session |
| **Auth** | GitHub OAuth + JWT | User authentication |
| **Tracing** | LangSmith | LLM agent observability |
| **Metrics** | OpenTelemetry + Prometheus + Grafana | System observability |
| **Evaluation** | Ragas | RAG quality measurement |
| **Integrations** | Slack API, Microsoft Teams Webhooks | Chat-ops |
| **Deploy** | Docker Compose | Container orchestration |
| **CI/CD** | GitHub Actions | Test → Build → Deploy |
| **Migrations** | Alembic | DB schema versioning |

---

## 🤖 Multi-Agent Pipeline

```
User Query
    │
    ▼
Planner Agent  ← decides which agents + order (GPT-4o)
    │
    ▼
Retriever Agent  ← KG + RAG Fusion: Vector + BM25 + Graph + Reranker
    │
    ├───────────┬───────────┬───────────┬───────────┐
    ▼           ▼           ▼           ▼           ▼
Security    Architecture  Refactor   TestGen    Design/Docs
(HITL)      Agent         Agent      Agent      Agents
    └───────────┴───────────┴───────────┴───────────┘
                          │
                          ▼
                   Reviewer Agent
                          │
                          ▼
                   Response Agent → Final Answer
```

---

## 🚀 10 New Enterprise Features

### 1. Model Router Agent
Every task is automatically routed to the best LLM:

| Task | Model | Why |
|---|---|---|
| Simple Q&A | gpt-4o-mini | Fast + cheap |
| Security Review | claude-3-5-sonnet | Best security reasoning |
| Architecture | gpt-4o | Strong structural reasoning |
| Test Generation | llama3 (local) | Code-focused, free |
| PR Review | gpt-4o-mini | Cost-efficient |

Tracks **cost**, **latency**, and **quality score** per invocation. All stats visible in the router stats API.

### 2. Human-in-the-Loop (HITL) Workflow
LangGraph-powered approval gate for security findings:

```
Security Agent
      ↓
HIGH / CRITICAL findings?
      ↓ yes
Create Approval Request (DB)
      ↓
Await Human Action  ← /hitl/approvals/{id}/action
      ↓ approved
Post GitHub PR Comment
```

### 3. Prompt Management System
- Store versioned prompts per agent type
- Full version history with rollback
- A/B test groups (group A vs group B)
- Active version pinning
- Runtime prompt override for any agent

### 4. Agent Playground
Dedicated page to independently test each agent:
- Select agent type (Security, Architecture, Refactoring, TestGen, Q&A, PR Review)
- See which model is selected by the router
- Run any prompt and view response + latency + cost + quality score

### 5. Agent Benchmark Dashboard
Compare agent versions side by side:

| Metric | Description |
|---|---|
| Accuracy | % of test cases answered correctly |
| Avg Latency | Mean response time (ms) |
| Total Cost | USD spent on test suite |
| Hallucination Rate | % answers unsupported by context |

Create benchmarks, run them, compare two versions with a delta view.

### 6. Knowledge Graph + RAG Fusion
Upgraded from plain vector search to a 3-signal fusion pipeline:

```
Query
  ├── Vector Search    (semantic recall)
  ├── BM25             (keyword recall)
  └── KG Traversal     (structural recall — BFS up to 2 hops)
        ↓
  Merge + Deduplicate
        ↓
  Cross-Encoder Reranker (BGE)
        ↓
  Top-K enriched chunks → LLM
```

Now answers questions like *"Which services **indirectly** depend on PaymentService?"*

### 7. Repository Change Intelligence
On every GitHub push event:
1. Classify changed files by architectural layer (API, service, model, migration, config, infra)
2. Map changed files to Knowledge Graph nodes
3. Walk KG edges to find downstream services
4. LLM generates risk assessment + recommendation
5. Report stored and visible in the UI

Manual trigger available for demos without a live webhook.

### 8. Slack / Teams Integration
```
Slack / Teams
      │
@copilot review pr #123     → AI PR review
@copilot security <repo>    → Security scan
@copilot ask <question>     → Code Q&A
@copilot status             → Health check
@copilot help               → Command list
```

- Slack: Slash commands + Event API (app_mention)
- Teams: Outgoing webhooks
- Proactive notifications: `notify_slack()` / `notify_teams()` callable from any agent

### 9. Executive Engineering Dashboard
For engineering managers — all metrics in one view:

| Section | Metrics |
|---|---|
| Repository Health | Total repos, indexed, files, chunks |
| Security Risks | Critical/high findings, pending HITL approvals |
| PR Trends | Reviews by risk level (critical/high/medium/low) |
| AI Usage | Runs by task type, model distribution, avg latency |
| Cost Trends | Total USD, avg per run, daily cost chart |

Configurable time window: 7d / 30d / 90d.

---

## 🚀 Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- OpenAI API key → [platform.openai.com](https://platform.openai.com)
- GitHub OAuth App → [github.com/settings/developers](https://github.com/settings/developers)

### Step 1 — GitHub OAuth App

1. GitHub → Settings → Developer Settings → OAuth Apps → New OAuth App
2. Homepage URL: `http://localhost:5173`
3. Callback URL: `http://localhost:8000/auth/github/callback`
4. Copy **Client ID** and **Client Secret**

### Step 2 — Configure Environment

```bash
cd ai-engineering-copilot/backend
cp .env.example .env
```

Minimum required in `.env`:
```env
OPENAI_API_KEY=sk-...
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
JWT_SECRET_KEY=any-random-32-char-string

# Optional — enables Claude routing for security agent
ANTHROPIC_API_KEY=sk-ant-...

# Optional — Slack integration
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...

# Optional — Teams integration
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
```

### Step 3 — Launch

```bash
cd ai-engineering-copilot
docker-compose up -d
```

### Step 4 — Open

| Service | URL |
|---|---|
| 🌐 Frontend | http://localhost:5173 |
| ⚡ API Docs | http://localhost:8000/docs |
| 📊 Grafana | http://localhost:3001 (admin/admin) |
| 🔥 Prometheus | http://localhost:9090 |

---

## 💻 Local Development

```bash
# Start only infra
docker-compose up postgres redis -d

# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## 📁 Project Structure

```
ai-engineering-copilot/
│
├── backend/
│   ├── agents/
│   │   ├── model_router_agent.py        # Smart LLM routing + cost/latency tracking
│   │   ├── hitl_workflow.py             # LangGraph HITL security approval flow
│   │   ├── change_intelligence_agent.py # Push event impact analysis
│   │   ├── knowledge_graph_agent.py     # KG + RAG Fusion queries
│   │   ├── multi_agent_orchestrator.py  # Full LangGraph pipeline
│   │   ├── security_agent.py            # Vulnerability detection
│   │   ├── architecture_agent.py        # Service dependency graph
│   │   ├── refactoring_agent.py         # Code smell detection
│   │   ├── test_generation_agent.py     # pytest/JUnit/Jest generation
│   │   ├── system_design_agent.py       # Mermaid/PlantUML diagrams
│   │   ├── documentation_agent.py       # README/API docs generation
│   │   ├── pr_review_agent.py           # GitHub PR diff analysis
│   │   └── github_pr_bot.py             # Auto-post PR comments
│   │
│   ├── api/
│   │   ├── model_router.py              # /router/* — routing table + stats + invoke
│   │   ├── hitl.py                      # /hitl/* — approval workflow endpoints
│   │   ├── prompts.py                   # /prompts/* — versioned prompt management
│   │   ├── benchmarks.py               # /benchmarks/* — agent benchmark runner
│   │   ├── executive.py                 # /executive/dashboard
│   │   ├── change_intelligence.py       # /change-intelligence/*
│   │   ├── integrations.py              # /integrations/* — Slack + Teams
│   │   ├── knowledge_graph.py           # /knowledge-graph/* (KG + RAG Fusion)
│   │   ├── agents.py                    # /agents/* — Security/Refactor/TestGen/etc
│   │   ├── chat.py                      # /chat — SSE streaming + multi-agent mode
│   │   ├── webhooks.py                  # GitHub push/PR → re-index + change intel
│   │   └── ...
│   │
│   ├── rag/
│   │   ├── kg_rag_fusion.py             # NEW: KG + Vector + BM25 + Reranker fusion
│   │   ├── hybrid_retriever.py          # BM25 + Vector + BGE Cross-Encoder
│   │   ├── knowledge_graph.py           # Import/dependency graph builder
│   │   └── vector_store.py              # pgvector cosine search
│   │
│   ├── models/models.py                 # 17 SQLAlchemy ORM models
│   ├── llm_router.py                    # Multi-provider LLM factory
│   └── config.py                        # Pydantic settings (incl. Slack/Teams)
│
├── frontend/src/pages/
│   ├── PlaygroundPage.tsx               # Agent Playground
│   ├── PromptsPage.tsx                  # Prompt Management
│   ├── BenchmarkPage.tsx                # Agent Benchmark Dashboard
│   ├── ExecutivePage.tsx                # Executive Engineering Dashboard
│   ├── ChangeIntelligencePage.tsx       # Repository Change Intelligence
│   ├── IntegrationsPage.tsx             # Slack / Teams setup + test
│   ├── KnowledgeGraphPage.tsx           # KG + RAG Fusion (upgraded)
│   └── ... (12 existing pages)
│
└── docker-compose.yml
```

---

## 🔌 Complete API Reference

### Model Router
| Method | Endpoint | Description |
|---|---|---|
| GET | `/router/routing-table` | Current task → model mapping |
| GET | `/router/stats` | Cost, latency, calls per model |
| POST | `/router/invoke` | Route a prompt to the best model |

### Human-in-the-Loop
| Method | Endpoint | Description |
|---|---|---|
| POST | `/hitl/trigger` | Start HITL security workflow |
| GET | `/hitl/approvals` | List pending approvals |
| GET | `/hitl/approvals/{id}` | Get single approval |
| POST | `/hitl/approvals/{id}/action` | approve / reject |

### Prompt Management
| Method | Endpoint | Description |
|---|---|---|
| GET | `/prompts` | List all prompt templates |
| POST | `/prompts` | Create new prompt |
| GET | `/prompts/{id}` | Get prompt + version history |
| POST | `/prompts/{id}/versions` | Add new version |
| POST | `/prompts/{id}/rollback/{version}` | Rollback to version |
| GET | `/prompts/active/{agent_type}` | Get active prompt for agent |

### Benchmarks
| Method | Endpoint | Description |
|---|---|---|
| POST | `/benchmarks` | Create benchmark |
| GET | `/benchmarks` | List benchmarks |
| POST | `/benchmarks/{id}/run` | Run benchmark test suite |
| GET | `/benchmarks/compare?id_a=&id_b=` | Compare two runs |

### Executive Dashboard
| Method | Endpoint | Description |
|---|---|---|
| GET | `/executive/dashboard?days=30` | Full executive metrics |

### Change Intelligence
| Method | Endpoint | Description |
|---|---|---|
| GET | `/change-intelligence/reports` | List impact reports |
| GET | `/change-intelligence/reports/{id}` | Get single report |
| POST | `/change-intelligence/analyze` | Manual trigger |

### Integrations
| Method | Endpoint | Description |
|---|---|---|
| POST | `/integrations/slack/command` | Slack slash command handler |
| POST | `/integrations/slack/events` | Slack Event API handler |
| POST | `/integrations/teams/message` | Teams outgoing webhook |
| POST | `/integrations/test-command` | Test any command locally |
| GET | `/integrations/config` | Integration status |

### Knowledge Graph (KG + RAG Fusion)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/knowledge-graph/build` | Build multi-repo graph |
| GET | `/knowledge-graph/graph` | Full graph (nodes + edges) |
| POST | `/knowledge-graph/query` | Fusion query (Vector + BM25 + KG + Reranker) |
| POST | `/knowledge-graph/dependents` | Find dependents of a node |
| GET | `/knowledge-graph/stats` | Graph statistics |

### Chat / Repositories / PR Review / Architecture / Security / Agents
*(see `/docs` Swagger UI for full reference)*

---

## 🗄️ Database Schema

```
users                         -- GitHub OAuth users
repositories                  -- Connected GitHub repos
repository_syncs              -- Ingestion job history
files                         -- Indexed source files
chunks                        -- Code chunks (AST-aware)
embeddings                    -- pgvector 1536-D vectors (HNSW)
conversations                 -- Chat sessions
messages                      -- Chat messages + agent metadata
pr_reviews                    -- PR analysis results
architecture_reports          -- Architecture analysis results
knowledge_nodes               -- Knowledge graph nodes
knowledge_edges               -- Knowledge graph edges (weighted)
hitl_approvals                -- Human-in-the-loop approval requests
agent_runs                    -- Model router telemetry (cost/latency)
prompt_templates              -- Versioned prompt templates
prompt_versions               -- Prompt version history
benchmark_runs                -- Agent benchmark results
change_intelligence_reports   -- Push event impact analysis
```

---

## 🔄 CI/CD Pipeline

```
git push main
      │
      ▼
GitHub Actions
      ├── Backend: pytest + ruff + mypy
      ├── Frontend: tsc + vite build
      ▼
Build Docker Images
      ├── ghcr.io/.../backend:latest
      └── ghcr.io/.../frontend:latest
      ▼
Deploy via SSH → docker-compose pull && up -d
```

---

## 📊 Observability

| Tool | What it tracks |
|---|---|
| **LangSmith** | Every agent run, prompt, token usage, latency per step |
| **Prometheus** | API requests, agent runs, retrieval latency, token consumption |
| **Grafana** | Dashboards for all Prometheus metrics |
| **AgentRun table** | Per-model cost, latency, quality score from model router |
| **Ragas** | Faithfulness, answer relevancy, context recall for RAG |

---

## 📝 Resume Bullet Points

> Built a production-grade **AI Engineering Copilot** using **LangGraph** (10-agent pipeline), **FastAPI**, **React 18**, **PostgreSQL/pgvector**, and a **KG + RAG Fusion** retriever (Vector + BM25 + Knowledge Graph traversal + BGE Cross-Encoder reranker). Implemented a **Model Router Agent** that dynamically selects GPT-4o, Claude 3.5, or Llama 3 per task with cost/latency tracking. Built **Human-in-the-Loop** approval gates using LangGraph, a **Prompt Management System** with versioning and A/B testing, an **Agent Benchmark Dashboard** (accuracy, latency, cost, hallucination rate), **Repository Change Intelligence** that auto-generates architectural impact reports on every GitHub push, and **Slack/Teams** chatbot integration — all with full observability via LangSmith, OpenTelemetry, and Ragas.

---

## 🛠️ Troubleshooting

**Missing LLM provider:**
```bash
pip install langchain-anthropic langchain-google-genai langchain-ollama
```

**pgvector extension missing:**
```bash
docker exec -it copilot_postgres psql -U copilot -d copilot_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Run all migrations:**
```bash
cd backend && alembic upgrade head
```

**Reset everything:**
```bash
docker-compose down -v && docker-compose up -d
```

---

## 📄 License

MIT License — free to use, modify, and distribute.


