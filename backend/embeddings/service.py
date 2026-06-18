from typing import List
from openai import AsyncOpenAI
from config import get_settings
import hashlib
import json
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis cache — optional, gracefully skips if Redis is unavailable
try:
    import redis.asyncio as aioredis
    _redis = aioredis.from_url(settings.redis_url, decode_responses=False)
except Exception:
    _redis = None

EMBEDDING_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days


class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        self.batch_size = 100

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()
        return f"emb:{digest}"

    async def embed(self, text: str) -> List[float]:
        """Embed a single text with Redis caching."""
        text = text.replace("\n", " ").strip()
        if not text:
            return [0.0] * self.dimensions

        # Try cache first
        if _redis:
            try:
                cached = await _redis.get(self._cache_key(text))
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        response = await self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dimensions
        )
        embedding = response.data[0].embedding

        # Store in cache
        if _redis:
            try:
                await _redis.setex(
                    self._cache_key(text), EMBEDDING_CACHE_TTL, json.dumps(embedding)
                )
            except Exception:
                pass

        return embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts in batches with per-item caching."""
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = [t.replace("\n", " ").strip() or " " for t in texts[i:i + self.batch_size]]
            try:
                response = await self.client.embeddings.create(
                    model=self.model, input=batch, dimensions=self.dimensions
                )
                batch_embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Embedding batch failed: {e}")
                all_embeddings.extend([[0.0] * self.dimensions] * len(batch))

        return all_embeddings
