# Screenshots Guide

This folder contains screenshots of the live application.

## Screen 1 — Login Page
**File:** `01_login.png`

The GitHub OAuth login screen.
- Clean dark theme
- "Continue with GitHub" button
- Tech stack displayed at bottom (GPT-4o · LangGraph · pgvector)

---

## Screen 2 — Dashboard
**File:** `02_dashboard.png`

Main dashboard after login.
- Stats cards: Total Repos, Indexed Repos, Code Chunks
- Quick action cards: Chat, PR Review, Architecture
- Recent repositories list with sync status badges

---

## Screen 3 — Repositories Page
**File:** `03_repositories.png`

Repository management.
- Connect repo form (input: `owner/repo`)
- List of connected repos with language badges
- Index / Re-index buttons
- Sync status indicators (Indexed / Not indexed)

---

## Screen 4 — Chat Interface
**File:** `04_chat.png`

AI-powered code Q&A.
- Repo selector dropdown (left panel)
- Example question suggestions on first load
- User/assistant message bubbles
- Syntax highlighted code blocks in responses
- Source file references below each answer
- Agent type badge (qa agent / architecture agent)

---

## Screen 5 — PR Review
**File:** `05_pr_review.png`

Automated pull request analysis.
- Repo selector + PR number input
- Risk level badge (LOW / MEDIUM / HIGH / CRITICAL)
- Severity-tagged findings list (CRITICAL / HIGH / MEDIUM / LOW / INFO)
- Expandable full AI analysis section
- Past reviews history

---

## Screen 6 — Architecture Analyzer
**File:** `06_architecture.png`

Repository architecture analysis.
- Summary text from GPT-4o
- Stats: Services count, API endpoints count, Circular deps
- Services/modules badge list
- Dependency graph (Service A → Service B)
- Circular dependency warnings in red
- Architectural layers breakdown

---

## Screen 7 — API Docs (Swagger)
**File:** `07_api_docs.png`

FastAPI auto-generated documentation at `/docs`.
- All endpoints grouped by tag
- Request/response schemas
- Interactive testing UI

---

## Screen 8 — Grafana Dashboard
**File:** `08_grafana.png`

Observability metrics dashboard.
- API request rate
- Response latency histogram
- Agent run counts by type
- LLM token consumption
- Vector retrieval latency

---

## How to Take Screenshots

1. Start the app: `docker-compose up -d`
2. Open `http://localhost:5173`
3. Login with GitHub
4. Connect a repository (e.g. `your-username/your-repo`)
5. Click Index → wait for indexing to complete
6. Go through each screen and capture screenshots
7. Save them in this folder with the names above
