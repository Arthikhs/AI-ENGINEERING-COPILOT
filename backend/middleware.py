"""
Production-Grade Middleware
  - Distributed Rate Limiting  (Redis sliding window per IP + per user)
  - API Quota Management       (per-org daily token/request quotas)
  - Distributed Cache Layer    (Redis-backed response caching)
  - Request ID injection       (for tracing)
  - Security headers
"""
import time
import uuid
import logging
import hashlib
import json
from typing import Optional, Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Redis client (shared) ─────────────────────────────────────────────────────

_redis_client: Optional[aioredis.Redis] = None
_redis_lock = asyncio.Lock() if False else None  # initialized lazily

import asyncio as _asyncio
_redis_init_lock = _asyncio.Lock()


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    async with _redis_init_lock:
        if _redis_client is None:
            _redis_client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
            )
    return _redis_client


# ── Rate Limiting Middleware ───────────────────────────────────────────────────

# Endpoint-specific rate limit overrides (requests per minute)
RATE_LIMIT_OVERRIDES: dict[str, int] = {
    "/auth/github":          20,
    "/enterprise/sandbox":   10,
    "/autonomous-engineer":  5,
    "/repos/":               30,
    "/chat/":                60,
}

DEFAULT_RPM = 120       # requests per minute per IP
BURST_ALLOWANCE = 1.5   # allow 50% burst


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter using Redis.
    - Per-IP limiting for anonymous requests
    - Per-user limiting for authenticated requests (header X-User-ID)
    - Per-endpoint overrides
    - Returns Retry-After header on 429
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks and metrics
        if request.url.path in ("/health", "/metrics", "/"):
            return await call_next(request)

        try:
            redis = await get_redis()
            limit = self._get_limit(request.url.path)
            identifier = self._get_identifier(request)
            window_key = f"rl:{identifier}:{int(time.time() // 60)}"

            count = await redis.incr(window_key)
            if count == 1:
                await redis.expire(window_key, 65)  # 65s TTL (window + buffer)

            burst_limit = int(limit * BURST_ALLOWANCE)
            if count > burst_limit:
                retry_after = 60 - (int(time.time()) % 60)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "limit": limit,
                        "retry_after_seconds": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                    },
                )

            response = await call_next(request)
            remaining = max(0, burst_limit - count)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response

        except Exception as e:
            logger.warning(f"Rate limit middleware error (non-fatal): {e}")
            return await call_next(request)

    def _get_limit(self, path: str) -> int:
        for prefix, limit in RATE_LIMIT_OVERRIDES.items():
            if path.startswith(prefix):
                return limit
        return DEFAULT_RPM

    def _get_identifier(self, request: Request) -> str:
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return f"user:{user_id}"
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        return f"ip:{ip}"


# ── Security Headers Middleware ────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers on every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# ── Request ID Middleware ──────────────────────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID for distributed tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── API Quota Manager ─────────────────────────────────────────────────────────

class QuotaManager:
    """
    Per-org daily API quota management.
    Tracks: request count, token consumption, cost.
    """

    QUOTA_DEFAULTS = {
        "requests_per_day": 10_000,
        "tokens_per_day":   5_000_000,
        "cost_per_day_usd": 50.0,
    }

    async def check_and_consume(
        self,
        org_id: str,
        tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> dict:
        """Check quota and consume if within limits. Returns quota status."""
        try:
            redis = await get_redis()
            today = time.strftime("%Y-%m-%d")
            base_key = f"quota:{org_id}:{today}"

            pipe = redis.pipeline()
            pipe.incr(f"{base_key}:requests")
            pipe.incrbyfloat(f"{base_key}:tokens", tokens)
            pipe.incrbyfloat(f"{base_key}:cost", cost_usd)
            results = await pipe.execute()

            # Set TTL on first request of the day
            if results[0] == 1:
                await redis.expire(f"{base_key}:requests", 86_400 + 3_600)
                await redis.expire(f"{base_key}:tokens",   86_400 + 3_600)
                await redis.expire(f"{base_key}:cost",     86_400 + 3_600)

            current = {
                "requests": int(results[0]),
                "tokens":   float(results[1]),
                "cost_usd": float(results[2]),
            }

            quota_exceeded = (
                current["requests"] > self.QUOTA_DEFAULTS["requests_per_day"] or
                current["tokens"]   > self.QUOTA_DEFAULTS["tokens_per_day"] or
                current["cost_usd"] > self.QUOTA_DEFAULTS["cost_per_day_usd"]
            )

            return {
                "org_id":         org_id,
                "date":           today,
                "current":        current,
                "limits":         self.QUOTA_DEFAULTS,
                "quota_exceeded": quota_exceeded,
                "remaining": {
                    "requests": max(0, self.QUOTA_DEFAULTS["requests_per_day"] - current["requests"]),
                    "tokens":   max(0, self.QUOTA_DEFAULTS["tokens_per_day"]   - current["tokens"]),
                    "cost_usd": max(0, self.QUOTA_DEFAULTS["cost_per_day_usd"] - current["cost_usd"]),
                },
            }
        except Exception as e:
            logger.warning(f"Quota check failed (non-fatal): {e}")
            return {"quota_exceeded": False}

    async def get_usage(self, org_id: str, date: Optional[str] = None) -> dict:
        """Get current quota usage for an org."""
        try:
            redis = await get_redis()
            day = date or time.strftime("%Y-%m-%d")
            base_key = f"quota:{org_id}:{day}"

            pipe = redis.pipeline()
            pipe.get(f"{base_key}:requests")
            pipe.get(f"{base_key}:tokens")
            pipe.get(f"{base_key}:cost")
            results = await pipe.execute()

            return {
                "org_id": org_id,
                "date":   day,
                "requests": int(results[0] or 0),
                "tokens":   float(results[1] or 0),
                "cost_usd": float(results[2] or 0),
                "limits":   self.QUOTA_DEFAULTS,
            }
        except Exception as e:
            logger.warning(f"Quota usage fetch failed: {e}")
            return {}


# ── Distributed Cache ──────────────────────────────────────────────────────────

class DistributedCache:
    """
    Redis-backed response cache.
    Use for expensive AI operations (health scores, governance reports, etc.)
    """

    DEFAULT_TTL = 300  # 5 minutes

    def __init__(self, prefix: str = "cache"):
        self.prefix = prefix

    def _key(self, namespace: str, *args) -> str:
        raw = f"{namespace}:{':'.join(str(a) for a in args)}"
        return f"{self.prefix}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    async def get(self, namespace: str, *args) -> Optional[dict]:
        try:
            redis = await get_redis()
            data = await redis.get(self._key(namespace, *args))
            return json.loads(data) if data else None
        except Exception:
            return None

    async def set(self, namespace: str, value: dict, ttl: int = DEFAULT_TTL, key: str = "") -> None:
        try:
            redis = await get_redis()
            await redis.setex(
                self._key(namespace, key),
                ttl,
                json.dumps(value, default=str),
            )
        except Exception as e:
            logger.warning(f"Cache set failed (non-fatal): {e}")

    async def invalidate(self, namespace: str, key: str = "") -> None:
        try:
            redis = await get_redis()
            await redis.delete(self._key(namespace, key))
        except Exception:
            pass

    async def get_or_compute(
        self,
        namespace: str,
        compute_fn: Callable,
        ttl: int = DEFAULT_TTL,
        key: str = "",
    ) -> dict:
        """Cache-aside pattern: get from cache or compute and store."""
        cached = await self.get(namespace, key)
        if cached is not None:
            cached["_cached"] = True
            return cached
        result = await compute_fn()
        await self.set(namespace, result, ttl, key)
        return result


# ── Singleton instances ────────────────────────────────────────────────────────

quota_manager = QuotaManager()
cache = DistributedCache(prefix="copilot")
