"""
API Quota Management Endpoints
- Per-org daily usage
- Quota override management
- Feature flag management (Redis-backed fast path)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from api.auth import get_current_user
from models.models import User
from middleware import quota_manager, cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quota", tags=["quota"])


@router.get("/usage/{org_id}")
async def get_quota_usage(
    org_id: str,
    date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Get current quota usage for an organization."""
    return await quota_manager.get_usage(org_id, date)


@router.get("/check/{org_id}")
async def check_quota(
    org_id: str,
    tokens: int = 0,
    cost_usd: float = 0.0,
    current_user: User = Depends(get_current_user),
):
    """Check if org has remaining quota without consuming it."""
    status = await quota_manager.get_usage(org_id)
    limits = quota_manager.QUOTA_DEFAULTS
    exceeded = (
        status.get("requests", 0) >= limits["requests_per_day"] or
        status.get("tokens", 0)   >= limits["tokens_per_day"] or
        status.get("cost_usd", 0) >= limits["cost_per_day_usd"]
    )
    return {**status, "quota_exceeded": exceeded}


@router.delete("/cache/{namespace}")
async def invalidate_cache(
    namespace: str,
    key: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Invalidate distributed cache for a namespace."""
    await cache.invalidate(namespace, key or "")
    return {"invalidated": True, "namespace": namespace}
