# System Architecture

## High-Level Architecture

```
                     ┌─────────────────┐
                     │    GitHub Repo  │
                     └────────┬────────┘
                              │  OAuth / Webhook / API
                              ▼
                 ┌────────────────────────┐
                 │ Repository Ingestion   │
                 │  - GitPython clone     │
                 │  - File walker         │
                 │  - Language detection  │
                 └────────┬───────────────┘
                          │
                          ▼
                 ┌────────────────────────┐
                 │  Code Chunking Engine  │
                 │  - Python AST chunker  │
                 │  - JS/TS regex chunker │
                 │  - Java chunker        │
                 │  - Sliding window      │
                 └────────┬───────────────┘
                          │
                          ▼
                 ┌────────────────────────┐
                 │  Embedding Pipeline    │
                 │  text-embedding-3-large│
                 │  1536-D vectors        │
                 │  Batched (100/req)     │
                 └────────┬───────────────┘
                          │
                          ▼
                 ┌────────────────────────┐
                 │  PostgreSQL + pgvector │
                 │  HNSW Index            │
                 │  Cosine similarity     │
                 │  10 tables             │
                 └────────┬───────────────┘
                          │
                          ▼
               ┌──────────────────────────┐
               │  LangGraph Agent System  │
               │  Intent Detection        │
               └────────────┬─────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐
  │  Q&A Agent  │  │  PR Review   │  │  Architecture    │
  │  RAG-based  │  │  Agent       │  │  Analyzer Agent  │
  │  GPT-4o     │  │  Diff+GPT-4o │  │  JSON report     │
  └──────┬──────┘  └──────┬───────┘  └────────┬─────────┘
         └──────────────────┼──────────────────┘
                            ▼
                   ┌─────────────────┐
                   │  FastAPI Backend │
                   │  + LangSmith    │
                   │  + OTel Metrics │
                   └────────┬────────┘
                            ▼
                   ┌─────────────────┐
                   │  React Frontend  │
                   │  Vite+TypeScript │
                   │  Tailwind CSS    │
                   └─────────────────┘
```

## Component Details

### 1. Repository Ingestion Service
- Clones GitHub repos using GitPython with authenticated HTTPS
- Walks all files, skips `node_modules`, `.git`, `__pycache__`, etc.
- Supports 22 file extensions
- Stores file metadata in PostgreSQL
- Background task — non-blocking
- Webhook-triggered incremental re-sync on `git push`

### 2. Code Chunking Engine
| Language | Strategy |
|---|---|
| Python | AST boundary detection (def/class) |
| JavaScript/TypeScript | Regex function/class boundaries |
| Java | Method signature regex |
| All others | Sliding window (60 lines, 50 step) |

Max chunk size: 1500 chars with 5-line overlap

### 3. Embedding Pipeline
- Model: `text-embedding-3-large` (OpenAI)
- Dimensions: 1536
- Batch size: 100 chunks per API call
- Zero-vector fallback on failure

### 4. Vector Database
- PostgreSQL 16 + pgvector extension
- HNSW index: `m=16, ef_construction=64`
- Cosine similarity search (`<=>` operator)
- Scoped per repo_id for isolation

### 5. LangGraph Agent System
```
State: AgentState (TypedDict)
  - question, repo_id, intent
  - retrieved_chunks, context
  - answer, sources, agent_type
  - token_usage, error

Graph Nodes:
  detect_intent → qa_agent | architecture_agent

Routing:
  keywords [architecture, structure, services,
            dependencies, layers, diagram]
    → architecture_agent
  everything else
    → qa_agent
```

### 6. FastAPI Backend
- Async SQLAlchemy with connection pooling (10 + 20 overflow)
- JWT auth (HS256, 24h expiry)
- Background tasks for long-running ingestion
- SSE streaming for chat
- CORS configured for frontend

### 7. Observability Stack
```
FastAPI App
    │
    ├── OpenTelemetry (traces)
    │       └── ConsoleSpanExporter (dev)
    │
    ├── Prometheus metrics at /metrics
    │       ├── api_requests_total
    │       ├── api_request_duration_seconds
    │       ├── agent_runs_total
    │       ├── retrieval_duration_seconds
    │       ├── llm_tokens_total
    │       └── ingestion_chunks_total
    │
    └── LangSmith (LLM traces)
            ├── Prompt versions
            ├── Token usage
            ├── Latency per agent
            └── Chain visualization
```
