# Data Flow Diagrams

## 1. Repository Ingestion Flow

```
Developer
    │
    │  POST /repos/connect { full_name: "owner/repo" }
    ▼
FastAPI
    │
    │  Fetch repo info from GitHub API
    ▼
GitHub API ──► Repo metadata (name, language, clone_url)
    │
    │  POST /repos/{id}/index
    ▼
Background Task (non-blocking)
    │
    ├── git clone --depth=1 (authenticated HTTPS)
    │
    ├── Walk files (Path.rglob)
    │       ├── Skip: node_modules, .git, __pycache__
    │       └── Accept: .py .js .ts .java .go .rb ...
    │
    ├── For each file:
    │       ├── Read content (UTF-8)
    │       ├── Detect language
    │       ├── CodeChunker.chunk() → List[ChunkDict]
    │       ├── EmbeddingService.embed_batch() → List[Vector]
    │       └── INSERT INTO embeddings (pgvector)
    │
    └── UPDATE repositories SET is_indexed=true
```

## 2. Chat / Q&A Flow

```
User types: "How does JWT authentication work?"
    │
    │  POST /chat { repo_id, message }
    ▼
FastAPI
    │
    ▼
AgentOrchestrator.run()
    │
    ├── detect_intent node
    │       └── keyword check → intent = "qa"
    │
    └── qa_agent node
            │
            ├── VectorStore.similarity_search()
            │       ├── EmbeddingService.embed(question)
            │       ├── SELECT ... ORDER BY embedding <=> query LIMIT 10
            │       └── Returns top 10 chunks with similarity scores
            │
            ├── Build context from chunks
            │
            ├── ChatOpenAI.ainvoke([SystemMessage, HumanMessage])
            │       └── GPT-4o generates answer
            │
            └── Return { answer, sources, agent_type, token_usage }
    │
    ▼
Save Message to DB (conversation history)
    │
    ▼
Response to frontend with sources
```

## 3. PR Review Flow

```
Developer
    │
    │  POST /review/pr { repo_id, pr_number: 143 }
    ▼
PRReviewAgent.review()
    │
    ├── GET /repos/{owner}/{repo}/pulls/{pr_number}
    │       └── PR metadata (title, base, head)
    │
    ├── GET /repos/{owner}/{repo}/pulls/{pr_number}
    │       Accept: application/vnd.github.v3.diff
    │       └── Raw unified diff
    │
    ├── Truncate diff to 15,000 chars if needed
    │
    ├── ChatOpenAI.ainvoke(PR_REVIEW_PROMPT + diff)
    │       └── GPT-4o analyzes for:
    │               - Bugs / logical errors
    │               - Security vulnerabilities
    │               - Null pointer risks
    │               - Missing error handling
    │               - Performance issues
    │               - Missing tests
    │
    ├── Parse findings (severity extraction)
    ├── Determine risk level (CRITICAL/HIGH/MEDIUM/LOW)
    └── Save PRReview to database
```

## 4. Architecture Analysis Flow

```
Developer
    │
    │  POST /analyze/architecture { repo_id }
    ▼
ArchitectureAgent.analyze()
    │
    ├── SELECT DISTINCT ON (file_path) file_path, content
    │   FROM embeddings WHERE repo_id = ?
    │   AND chunk_type IN ('class','function','module')
    │   LIMIT 30
    │
    ├── Build context (800 chars per file sample)
    │
    ├── ChatOpenAI.ainvoke(ARCHITECTURE_PROMPT)
    │       response_format: json_object
    │       └── GPT-4o returns:
    │               {
    │                 services: [...],
    │                 dependencies: {A: [B, C]},
    │                 api_endpoints: [...],
    │                 circular_dependencies: [[A,B,A]],
    │                 layers: {presentation:[...], data:[...]},
    │                 concerns: [...],
    │                 summary: "..."
    │               }
    │
    └── Save ArchitectureReport to database
```

## 5. GitHub Webhook Incremental Sync

```
git push origin main
    │
    │  GitHub sends POST /webhooks/github
    ▼
Webhook Handler
    │
    ├── Verify HMAC-SHA256 signature
    ├── Check event = "push" + ref = "refs/heads/main"
    │
    ├── Find all Repository records with full_name
    │
    └── For each repo:
            ├── Create RepositorySync record
            └── Background task: run_ingestion()
                    └── (same flow as manual index)
```
