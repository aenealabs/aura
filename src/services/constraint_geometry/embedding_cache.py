"""
Project Aura - Two-Tier Embedding Cache

Provides deterministic embedding retrieval through SHA-256 content hashing
and two-tier caching (in-process LRU + ElastiCache Redis).

Determinism guarantee: The same normalized text always produces the same
SHA-256 hash, which always retrieves the same embedding. Embeddings are
computed once (via Bedrock Titan) and cached permanently.

Author: Project Aura Team
Created: 2026-02-11
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Any, Optional, Protocol

from .config import CacheConfig

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding computation backends."""

    async def compute_embedding(self, text: str) -> list[float]:
        """Compute embedding vector for text."""
        ...


class RedisClient(Protocol):
    """Protocol for Redis cache operations."""

    async def get(self, key: str) -> Optional[bytes]:
        """Get value from Redis."""
        ...

    async def set(self, key: str, value: bytes, ex: Optional[int] = None) -> None:
        """Set value in Redis with optional TTL."""
        ...


class EmbeddingCache:
    """Two-tier embedding cache with deterministic key generation.

    Tier 1: In-process LRU cache (fastest, bounded memory)
    Tier 2: ElastiCache Redis (shared across pods, persistent)
    Tier 3: Bedrock Titan embedding computation (slowest, on cache miss)

    Usage:
        cache = EmbeddingCache(
            provider=bedrock_provider,
            redis=redis_client,
            config=CacheConfig(),
        )
        embedding = await cache.get_or_compute(output_hash, normalized_text)
    """

    def __init__(
        self,
        provider: Optional[EmbeddingProvider] = None,
        redis: Optional[RedisClient] = None,
        config: Optional[CacheConfig] = None,
    ):
        self._provider = provider
        self._redis = redis
        self._config = config or CacheConfig()

        # Tier 1: In-process LRU
        self._lru: OrderedDict[str, list[float]] = OrderedDict()
        self._lru_max_size = self._config.lru_max_size

        # Cache statistics
        self._hits_lru = 0
        self._hits_redis = 0
        self._misses = 0
        self._last_was_hit = False

    @property
    def last_was_hit(self) -> bool:
        """Whether the last get_or_compute call was a cache hit."""
        return self._last_was_hit

    @property
    def stats(self) -> dict[str, Any]:
        """Cache statistics."""
        total = self._hits_lru + self._hits_redis + self._misses
        return {
            "hits_lru": self._hits_lru,
            "hits_redis": self._hits_redis,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate": (self._hits_lru + self._hits_redis) / max(total, 1),
            "lru_size": len(self._lru),
            "lru_max_size": self._lru_max_size,
        }

    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute deterministic SHA-256 hash of normalized text.

        Args:
            text: Normalized text (whitespace-collapsed, stripped)

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for deterministic hashing.

        Collapses all whitespace to single spaces and strips leading/trailing.
        """
        return " ".join(text.strip().split())

    async def get_or_compute(
        self,
        output_hash: str,
        normalized_text: str,
    ) -> list[float]:
        """Get embedding from cache or compute via provider.

        Lookup order:
        1. In-process LRU cache
        2. ElastiCache Redis
        3. Bedrock Titan (compute + cache in both tiers)

        Args:
            output_hash: SHA-256 hash of normalized text
            normalized_text: The normalized text to embed on cache miss

        Returns:
            Embedding vector as list of floats
        """
        # Tier 1: LRU lookup
        embedding = self._lru_get(output_hash)
        if embedding is not None:
            self._hits_lru += 1
            self._last_was_hit = True
            return embedding

        # Tier 2: Redis lookup
        embedding = await self._redis_get(output_hash)
        if embedding is not None:
            self._hits_redis += 1
            self._last_was_hit = True
            # Promote to LRU
            self._lru_put(output_hash, embedding)
            return embedding

        # Tier 3: Compute embedding
        self._misses += 1
        self._last_was_hit = False

        if self._provider is None:
            raise RuntimeError(
                "No embedding provider configured and cache miss occurred. "
                "Provide an EmbeddingProvider or pre-warm the cache."
            )

        embedding = await self._provider.compute_embedding(normalized_text)

        # Store in both tiers
        self._lru_put(output_hash, embedding)
        await self._redis_put(output_hash, embedding)

        return embedding

    def get_cached(self, output_hash: str) -> Optional[list[float]]:
        """Synchronous LRU-only lookup (no Redis, no compute)."""
        return self._lru_get(output_hash)

    def put(self, output_hash: str, embedding: list[float]) -> None:
        """Manually insert an embedding into the LRU cache.

        Used for pre-warming the cache with known embeddings.
        """
        self._lru_put(output_hash, embedding)

    def clear(self) -> None:
        """Clear the LRU cache (for testing)."""
        self._lru.clear()
        self._hits_lru = 0
        self._hits_redis = 0
        self._misses = 0

    # -------------------------------------------------------------------------
    # Internal: LRU operations
    # -------------------------------------------------------------------------

    def _lru_get(self, key: str) -> Optional[list[float]]:
        """Get from LRU cache, moving to most-recently-used position."""
        if key in self._lru:
            self._lru.move_to_end(key)
            return self._lru[key]
        return None

    def _lru_put(self, key: str, value: list[float]) -> None:
        """Put into LRU cache, evicting oldest if at capacity."""
        if key in self._lru:
            self._lru.move_to_end(key)
            self._lru[key] = value
            return

        if len(self._lru) >= self._lru_max_size:
            self._lru.popitem(last=False)

        self._lru[key] = value

    # -------------------------------------------------------------------------
    # Internal: Redis operations
    # -------------------------------------------------------------------------

    async def _redis_get(self, key: str) -> Optional[list[float]]:
        """Get from Redis cache."""
        if not self._redis or not self._config.enable_redis:
            return None

        try:
            redis_key = f"{self._config.redis_key_prefix}{key}"
            data = await self._redis.get(redis_key)
            if data is not None:
                return json.loads(data)
        except Exception:
            logger.warning("Redis get failed for key %s", key, exc_info=True)

        return None

    async def _redis_put(self, key: str, value: list[float]) -> None:
        """Put into Redis cache."""
        if not self._redis or not self._config.enable_redis:
            return

        try:
            redis_key = f"{self._config.redis_key_prefix}{key}"
            data = json.dumps(value)
            await self._redis.set(
                redis_key,
                data.encode("utf-8"),
                ex=self._config.redis_ttl_seconds,
            )
        except Exception:
            logger.warning("Redis put failed for key %s", key, exc_info=True)
