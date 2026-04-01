"""
Documentation Cache Service - 3-Tier Caching
=============================================

Provides multi-tier caching for documentation generation results.
ADR-056: Documentation Agent for Architecture and Data Flow Diagrams.

Cache Tiers:
- Tier 1: In-memory LRU cache (5 min TTL) - fastest, limited size
- Tier 2: Redis/ElastiCache (1 hour TTL) - shared across instances
- Tier 3: S3 (24 hour TTL) - durable, large capacity

Environment Variables:
    REDIS_HOST: Redis host (default: localhost)
    REDIS_PORT: Redis port (default: 6379)
    DOCS_CACHE_S3_BUCKET: S3 bucket for cache tier 3
    DOCS_CACHE_MEMORY_TTL: Memory cache TTL in seconds (default: 300)
    DOCS_CACHE_REDIS_TTL: Redis cache TTL in seconds (default: 3600)
    DOCS_CACHE_S3_TTL: S3 cache TTL in seconds (default: 86400)
"""

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Type variable for cached values
T = TypeVar("T")

# Optional Redis import
try:
    import redis
    from redis.exceptions import RedisError

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("redis package not installed - Redis cache tier unavailable")

# Optional boto3 import
try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.info("boto3 package not installed - S3 cache tier unavailable")


class CacheTier(Enum):
    """Cache tier identifiers."""

    MEMORY = "memory"
    REDIS = "redis"
    S3 = "s3"


@dataclass
class CacheConfig:
    """Configuration for documentation cache service."""

    # Memory tier settings
    memory_ttl: int = 300  # 5 minutes
    max_memory_entries: int = 100

    # Redis tier settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0
    redis_ttl: int = 3600  # 1 hour
    redis_key_prefix: str = "aura:docs:"

    # S3 tier settings
    s3_bucket: str = ""
    s3_prefix: str = "documentation-cache/"
    s3_ttl: int = 86400  # 24 hours

    # Connection settings
    redis_connect_timeout: float = 5.0
    redis_socket_timeout: float = 5.0

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Create config from environment variables."""
        return cls(
            memory_ttl=int(os.getenv("DOCS_CACHE_MEMORY_TTL", "300")),
            max_memory_entries=int(os.getenv("DOCS_CACHE_MAX_MEMORY", "100")),
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_password=os.getenv("REDIS_PASSWORD"),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            redis_ttl=int(os.getenv("DOCS_CACHE_REDIS_TTL", "3600")),
            s3_bucket=os.getenv("DOCS_CACHE_S3_BUCKET", ""),
            s3_prefix=os.getenv("DOCS_CACHE_S3_PREFIX", "documentation-cache/"),
            s3_ttl=int(os.getenv("DOCS_CACHE_S3_TTL", "86400")),
        )


@dataclass
class CacheEntry:
    """A cached documentation entry with metadata."""

    key: str
    value: dict[str, Any]
    created_at: float
    ttl: int
    tier: str

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl <= 0:
            return False
        return time.time() - self.created_at > self.ttl

    def to_json(self) -> str:
        """Serialize entry to JSON."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "CacheEntry":
        """Deserialize entry from JSON."""
        parsed = json.loads(data)
        return cls(**parsed)


class DocumentationCacheService:
    """
    3-tier caching service for documentation generation.

    Implements a cascading cache strategy:
    1. Check memory cache (fastest, 5 min TTL)
    2. Check Redis cache (shared, 1 hour TTL)
    3. Check S3 cache (durable, 24 hour TTL)

    On cache miss, the caller generates the value and it's stored
    in all available tiers for future requests.

    Example:
        >>> cache = DocumentationCacheService()
        >>> result = await cache.get("repo-123:architecture")
        >>> if result is None:
        ...     result = await generate_documentation(...)
        ...     await cache.set("repo-123:architecture", result)
    """

    def __init__(self, config: CacheConfig | None = None):
        """
        Initialize the 3-tier cache service.

        Args:
            config: Cache configuration (defaults to env-based config)
        """
        self.config = config or CacheConfig.from_env()

        # Tier 1: In-memory LRU cache
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Tier 2: Redis client
        self._redis_client: Any | None = None
        self._redis_available = False
        self._init_redis()

        # Tier 3: S3 client
        self._s3_client: Any | None = None
        self._s3_available = False
        self._init_s3()

        # Statistics
        self._stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "s3_hits": 0,
            "s3_misses": 0,
        }

        logger.info(
            f"DocumentationCacheService initialized: "
            f"memory=enabled, redis={self._redis_available}, s3={self._s3_available}"
        )

    def _init_redis(self) -> None:
        """Initialize Redis connection."""
        if not REDIS_AVAILABLE:
            return

        try:
            self._redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                password=self.config.redis_password,
                db=self.config.redis_db,
                socket_connect_timeout=self.config.redis_connect_timeout,
                socket_timeout=self.config.redis_socket_timeout,
                decode_responses=True,
            )
            # Test connection
            self._redis_client.ping()
            self._redis_available = True
            logger.info(
                f"Redis cache connected: {self.config.redis_host}:{self.config.redis_port}"
            )
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._redis_client = None
            self._redis_available = False

    def _init_s3(self) -> None:
        """Initialize S3 client."""
        if not BOTO3_AVAILABLE or not self.config.s3_bucket:
            return

        try:
            self._s3_client = boto3.client("s3")
            # Test bucket access
            self._s3_client.head_bucket(Bucket=self.config.s3_bucket)
            self._s3_available = True
            logger.info(f"S3 cache connected: {self.config.s3_bucket}")
        except Exception as e:
            logger.warning(f"S3 connection failed: {e}")
            self._s3_client = None
            self._s3_available = False

    def _make_cache_key(self, key: str) -> str:
        """Create a consistent cache key hash."""
        # Use SHA256 for consistent key hashing
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:32]
        return f"{self.config.redis_key_prefix}{key_hash}"

    def _make_s3_key(self, key: str) -> str:
        """Create S3 object key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:32]
        return f"{self.config.s3_prefix}{key_hash}.json"

    def _evict_memory_lru(self) -> None:
        """Evict oldest entries from memory cache if over limit."""
        while len(self._memory_cache) > self.config.max_memory_entries:
            evicted_key, _ = self._memory_cache.popitem(last=False)
            logger.debug(f"LRU evicted from memory cache: {evicted_key}")

    # =========================================================================
    # Memory Cache (Tier 1)
    # =========================================================================

    def _get_from_memory(self, key: str) -> dict[str, Any] | None:
        """Get value from memory cache."""
        cache_key = self._make_cache_key(key)

        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if not entry.is_expired():
                # Move to end for LRU
                self._memory_cache.move_to_end(cache_key)
                self._stats["memory_hits"] += 1
                logger.debug(f"Memory cache hit: {key}")
                return entry.value
            else:
                # Remove expired entry
                del self._memory_cache[cache_key]

        self._stats["memory_misses"] += 1
        return None

    def _set_in_memory(self, key: str, value: dict[str, Any]) -> None:
        """Set value in memory cache."""
        cache_key = self._make_cache_key(key)

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl=self.config.memory_ttl,
            tier=CacheTier.MEMORY.value,
        )

        self._memory_cache[cache_key] = entry
        self._memory_cache.move_to_end(cache_key)
        self._evict_memory_lru()

        logger.debug(f"Stored in memory cache: {key}")

    # =========================================================================
    # Redis Cache (Tier 2)
    # =========================================================================

    def _get_from_redis(self, key: str) -> dict[str, Any] | None:
        """Get value from Redis cache."""
        if not self._redis_available or not self._redis_client:
            return None

        cache_key = self._make_cache_key(key)

        try:
            data = self._redis_client.get(cache_key)
            if data:
                entry = CacheEntry.from_json(data)
                if not entry.is_expired():
                    self._stats["redis_hits"] += 1
                    logger.debug(f"Redis cache hit: {key}")
                    return entry.value
        except RedisError as e:
            logger.warning(f"Redis get failed: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Redis data parse failed: {e}")

        self._stats["redis_misses"] += 1
        return None

    def _set_in_redis(self, key: str, value: dict[str, Any]) -> None:
        """Set value in Redis cache."""
        if not self._redis_available or not self._redis_client:
            return

        cache_key = self._make_cache_key(key)

        try:
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=self.config.redis_ttl,
                tier=CacheTier.REDIS.value,
            )

            self._redis_client.setex(cache_key, self.config.redis_ttl, entry.to_json())
            logger.debug(f"Stored in Redis cache: {key}")
        except RedisError as e:
            logger.warning(f"Redis set failed: {e}")

    # =========================================================================
    # S3 Cache (Tier 3)
    # =========================================================================

    def _get_from_s3(self, key: str) -> dict[str, Any] | None:
        """Get value from S3 cache."""
        if not self._s3_available or not self._s3_client:
            return None

        s3_key = self._make_s3_key(key)

        try:
            response = self._s3_client.get_object(
                Bucket=self.config.s3_bucket, Key=s3_key
            )
            data = response["Body"].read().decode("utf-8")
            entry = CacheEntry.from_json(data)

            if not entry.is_expired():
                self._stats["s3_hits"] += 1
                logger.debug(f"S3 cache hit: {key}")
                return entry.value
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchKey":
                logger.warning(f"S3 get failed: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"S3 data parse failed: {e}")

        self._stats["s3_misses"] += 1
        return None

    def _set_in_s3(self, key: str, value: dict[str, Any]) -> None:
        """Set value in S3 cache."""
        if not self._s3_available or not self._s3_client:
            return

        s3_key = self._make_s3_key(key)

        try:
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=self.config.s3_ttl,
                tier=CacheTier.S3.value,
            )

            self._s3_client.put_object(
                Bucket=self.config.s3_bucket,
                Key=s3_key,
                Body=entry.to_json(),
                ContentType="application/json",
            )
            logger.debug(f"Stored in S3 cache: {key}")
        except ClientError as e:
            logger.warning(f"S3 set failed: {e}")

    # =========================================================================
    # Public API
    # =========================================================================

    def get(self, key: str) -> dict[str, Any] | None:
        """
        Get value from cache, checking all tiers.

        Checks tiers in order: memory -> redis -> s3.
        When found in a lower tier, promotes to higher tiers.

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        # Tier 1: Memory
        value = self._get_from_memory(key)
        if value is not None:
            return value

        # Tier 2: Redis
        value = self._get_from_redis(key)
        if value is not None:
            # Promote to memory
            self._set_in_memory(key, value)
            return value

        # Tier 3: S3
        value = self._get_from_s3(key)
        if value is not None:
            # Promote to memory and redis
            self._set_in_memory(key, value)
            self._set_in_redis(key, value)
            return value

        return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        """
        Set value in all cache tiers.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
        """
        # Store in all available tiers
        self._set_in_memory(key, value)
        self._set_in_redis(key, value)
        self._set_in_s3(key, value)

    def delete(self, key: str) -> None:
        """
        Delete value from all cache tiers.

        Args:
            key: Cache key
        """
        cache_key = self._make_cache_key(key)

        # Memory
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]

        # Redis
        if self._redis_available and self._redis_client:
            try:
                self._redis_client.delete(cache_key)
            except RedisError as e:
                logger.warning(f"Redis delete failed: {e}")

        # S3
        if self._s3_available and self._s3_client:
            try:
                s3_key = self._make_s3_key(key)
                self._s3_client.delete_object(Bucket=self.config.s3_bucket, Key=s3_key)
            except ClientError as e:
                logger.warning(f"S3 delete failed: {e}")

    def invalidate_repository(self, repository_id: str) -> int:
        """
        Invalidate all cache entries for a repository.

        This is typically called when a repository is re-ingested
        and all cached documentation is stale.

        Args:
            repository_id: Repository ID to invalidate

        Returns:
            Number of entries invalidated from memory cache
        """
        prefix = f"{self.config.redis_key_prefix}{repository_id}:"
        invalidated = 0

        # Memory - scan and delete matching keys
        keys_to_delete = [k for k in self._memory_cache.keys() if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._memory_cache[key]
            invalidated += 1

        # Redis - use SCAN to find matching keys
        if self._redis_available and self._redis_client:
            try:
                cursor = 0
                while True:
                    cursor, keys = self._redis_client.scan(
                        cursor, match=f"{prefix}*", count=100
                    )
                    if keys:
                        self._redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except RedisError as e:
                logger.warning(f"Redis invalidate failed: {e}")

        # S3 - list and delete matching objects
        if self._s3_available and self._s3_client:
            try:
                paginator = self._s3_client.get_paginator("list_objects_v2")
                for page in paginator.paginate(
                    Bucket=self.config.s3_bucket,
                    Prefix=f"{self.config.s3_prefix}{repository_id}/",
                ):
                    if "Contents" in page:
                        objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                        if objects:
                            self._s3_client.delete_objects(
                                Bucket=self.config.s3_bucket,
                                Delete={"Objects": objects},
                            )
            except ClientError as e:
                logger.warning(f"S3 invalidate failed: {e}")

        logger.info(f"Invalidated {invalidated} cache entries for {repository_id}")
        return invalidated

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hit/miss counts per tier
        """
        total_hits = (
            self._stats["memory_hits"]
            + self._stats["redis_hits"]
            + self._stats["s3_hits"]
        )
        total_misses = (
            self._stats["memory_misses"]
            + self._stats["redis_misses"]
            + self._stats["s3_misses"]
        )
        total = total_hits + total_misses

        return {
            "memory": {
                "hits": self._stats["memory_hits"],
                "misses": self._stats["memory_misses"],
                "entries": len(self._memory_cache),
            },
            "redis": {
                "hits": self._stats["redis_hits"],
                "misses": self._stats["redis_misses"],
                "available": self._redis_available,
            },
            "s3": {
                "hits": self._stats["s3_hits"],
                "misses": self._stats["s3_misses"],
                "available": self._s3_available,
            },
            "total": {
                "hits": total_hits,
                "misses": total_misses,
                "hit_rate": total_hits / total if total > 0 else 0.0,
            },
        }

    def clear_memory(self) -> int:
        """
        Clear the in-memory cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._memory_cache)
        self._memory_cache.clear()
        logger.info(f"Cleared {count} entries from memory cache")
        return count


# Factory function for creating cache service
def create_documentation_cache_service(
    config: CacheConfig | None = None,
) -> DocumentationCacheService:
    """
    Factory function to create a DocumentationCacheService.

    Args:
        config: Optional cache configuration

    Returns:
        Configured DocumentationCacheService instance
    """
    return DocumentationCacheService(config=config)
