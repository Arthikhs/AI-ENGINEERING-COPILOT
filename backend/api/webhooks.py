import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import Repository, RepositorySync
from database import get_db
from ingestion.service import IngestionService
from agents.github_pr_bot import GitHubPRBot
from config import get_settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle GitHub push/PR webhook events and trigger incremental re-indexing.
    Configure in GitHub repo → Settings → Webhooks.
    Payload URL: http://your-domain/webhooks/github
    Content type: application/json
    Secret: same value as GITHUB_WEBHOOK_SECRET in .env
    """
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event = request.headers.get("X-GitHub-Event", "")

    # Verify signature if webhook secret is configured
    webhook_secret = getattr(settings, "github_webhook_secret", "")
    if webhook_secret and not _verify_signature(payload_bytes, signature, webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()

    # Only handle push events to default branch
    if event == "push":
        ref = payload.get("ref", "")
        repo_full_name = payload.get("repository", {}).get("full_name", "")
        default_branch = payload.get("repository", {}).get("default_branch", "main")
        pusher_token = None  # webhook doesn't carry user token

        # Only re-index on push to default branch
        if ref != f"refs/heads/{default_branch}":
            return {"message": "Skipped — not default branch"}

        # Find matching repository records
        result = await db.execute(
            select(Repository).where(Repository.full_name == repo_full_name)
        )
        repos = result.scalars().all()

        if not repos:
            return {"message": "Repository not connected to this platform"}

        triggered = []
        for repo in repos:
            sync = RepositorySync(repo_id=repo.id, branch=repo.default_branch)
            db.add(sync)
            await db.flush()

            background_tasks.add_task(
                IngestionService.run_ingestion,
                str(repo.id),
                str(sync.id),
                repo.owner.github_access_token if repo.owner else "",
            )

            # ── Change Intelligence: analyze impact in background ──
            changed_files = [
                c.get("filename") or c.get("added") or ""
                for commit in payload.get("commits", [])
                for c in (
                    [{"filename": f} for f in commit.get("added", []) + commit.get("modified", []) + commit.get("removed", [])]
                )
                if c.get("filename")
            ]
            if not changed_files:
                # Flatten all commits
                for commit in payload.get("commits", []):
                    changed_files += commit.get("added", []) + commit.get("modified", []) + commit.get("removed", [])

            background_tasks.add_task(
                _run_change_intelligence,
                str(repo.id),
                repo.full_name,
                payload.get("after", ""),
                list(dict.fromkeys(changed_files))[:50],
                payload.get("pusher", {}).get("name", ""),
                default_branch,
            )

            triggered.append(str(repo.id))

        await db.commit()
        return {"message": f"Re-indexing triggered for {len(triggered)} repo(s)", "repo_ids": triggered}

    # Handle pull_request events — trigger AI review bot
    elif event == "pull_request":
        action = payload.get("action", "")
        pr_number = payload.get("number")
        repo_full_name = payload.get("repository", {}).get("full_name", "")

        if action in ("opened", "synchronize", "reopened"):
            result = await db.execute(
                select(Repository).where(Repository.full_name == repo_full_name)
            )
            repos = result.scalars().all()

            for repo in repos:
                github_token = repo.owner.github_access_token if repo.owner else ""
                if github_token and repo.is_indexed:
                    background_tasks.add_task(
                        _run_pr_bot,
                        repo_full_name,
                        pr_number,
                        str(repo.id),
                        action,
                        github_token,
                    )

            return {"message": f"PR #{pr_number} review triggered for {repo_full_name}"}

    return {"message": f"Event '{event}' acknowledged"}


async def _run_pr_bot(
    repo_full_name: str,
    pr_number: int,
    repo_id: str,
    action: str,
    github_token: str,
):
    """Background task: run AI PR review and post GitHub comment."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        bot = GitHubPRBot(github_token=github_token, db=db)
        await bot.handle_pr_event(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            repo_id=repo_id,
            action=action,
        )
    await engine.dispose()


async def _run_change_intelligence(
    repo_id: str,
    repo_full_name: str,
    commit_sha: str,
    changed_files: list,
    pusher: str,
    branch: str,
):
    """Background task: run Change Intelligence analysis on a push event."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from agents.change_intelligence_agent import ChangeIntelligenceAgent
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as db:
        agent = ChangeIntelligenceAgent(db)
        try:
            result = await agent.analyze(
                repo_id=repo_id,
                repo_full_name=repo_full_name,
                commit_sha=commit_sha,
                changed_files=changed_files,
                pusher=pusher,
                branch=branch,
            )
            print(f"[ChangeIntelligence] Report generated: {result.get('report_id')} — {result.get('summary')}")
        except Exception as e:
            print(f"[ChangeIntelligence] Failed for {repo_full_name}: {e}")
    await engine.dispose()
