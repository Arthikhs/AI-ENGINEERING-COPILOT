"""
Celery Worker — Async Repository Processing
Moves repo indexing off the request thread into a Redis-backed queue.

Flow:
  POST /repos/{id}/index
       ↓
  Celery Task queued (instant response)
       ↓
  Worker clones + chunks + embeds in background
       ↓
  Progress stored in Redis (polled by SSE endpoint)
       ↓
  Completed event
"""
from celery import Celery
from celery.utils.log import get_task_logger
import asyncio
import json
import redis as sync_redis
from config import get_settings

settings = get_settings()
logger = get_task_logger(__name__)

# Celery app using Redis as broker + backend
celery_app = Celery(
    "copilot_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,   # one task at a time per worker (heavy I/O)
    task_acks_late=True,
)

# Sync Redis client for progress updates
_redis = sync_redis.from_url(settings.redis_url, decode_responses=True)

PROGRESS_TTL = 60 * 60  # 1 hour


def _set_progress(sync_id: str, data: dict):
    """Store progress in Redis so SSE endpoint can stream it."""
    _redis.setex(f"sync_progress:{sync_id}", PROGRESS_TTL, json.dumps(data))


@celery_app.task(bind=True, name="tasks.ingest_repository")
def ingest_repository(self, repo_id: str, sync_id: str, github_token: str):
    """
    Background task: clone repo → chunk → embed → store.
    Progress is written to Redis at each stage.
    """
    _set_progress(sync_id, {"status": "running", "stage": "cloning", "pct": 5})
    logger.info(f"Starting ingestion for repo {repo_id}, sync {sync_id}")

    try:
        # Run the async ingestion pipeline in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            from ingestion.service import IngestionService, _progress_callback
            await IngestionService.run_ingestion(
                repo_id, sync_id, github_token,
                progress_cb=lambda stage, pct: _set_progress(sync_id, {
                    "status": "running", "stage": stage, "pct": pct
                })
            )

        loop.run_until_complete(_run())
        loop.close()

        _set_progress(sync_id, {"status": "completed", "stage": "done", "pct": 100})
        logger.info(f"Ingestion completed: sync {sync_id}")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        _set_progress(sync_id, {"status": "failed", "stage": "error", "pct": 0, "error": str(e)})
        raise self.retry(exc=e, max_retries=2, countdown=30)
