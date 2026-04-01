"""
Project Aura - API Rate Limiter Service

Provides rate limiting for API endpoints to prevent:
- DoS attacks
- API abuse
- Resource exhaustion

Implements sliding window rate limiting algorithm.

Author: Project Aura Team
Created: 2025-12-12
"""

# NOTE: Not using `from __future__ import annotations` because FastAPI needs
# runtime type inspection for Request dependency injection.

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class RateLimitTier(Enum):
    """Rate limit tiers for different endpoint categories."""

    # Public endpoints - loose limits
    PUBLIC = "public"  # 100 req/min per IP

    # Authenticated endpoints - standard limits
    STANDARD = "standard"  # 60 req/min per user

    # Sensitive operations - strict limits
    SENSITIVE = "sensitive"  # 10 req/min per user

    # Admin operations - very strict
    ADMIN = "admin"  # 5 req/min per user

    # Critical operations (HITL, deployments) - most strict
    CRITICAL = "critical"  # 2 req/min per user

    # Webhook/callback endpoints - burst friendly
    WEBHOOK = "webhook"  # 200 req/min per source


# Default rate limits (requests per minute) per tier
# Uses string keys to avoid enum identity issues in forked test processes
DEFAULT_LIMITS: dict[str, int] = {
    "public": 100,
    "standard": 60,
    "sensitive": 10,
    "admin": 5,
    "critical": 2,
    "webhook": 200,
}


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    remaining: int
    reset_at: float
    limit: int
    tier: RateLimitTier
    client_id: str

    @property
    def retry_after(self) -> int:
        """Seconds until rate limit resets."""
        return max(0, int(self.reset_at - time.time()))

    def to_headers(self) -> dict[str, str]:
        """Generate rate limit headers for response."""
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_at)),
            "X-RateLimit-Tier": self.tier.value,
        }


@dataclass
class RateLimitConfig:
    """Configuration for a specific rate limit rule."""

    tier: RateLimitTier = RateLimitTier.STANDARD
    requests_per_minute: int | None = None  # Override default for tier
    burst_allowance: int = 0  # Extra requests allowed in burst
    exempt_paths: list[str] = field(default_factory=list)

    @property
    def effective_limit(self) -> int:
        """Get effective limit including burst."""
        base_limit = self.requests_per_minute or DEFAULT_LIMITS[self.tier.value]
        return base_limit + self.burst_allowance


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter using in-memory storage.

    Uses a sliding window algorithm for smooth rate limiting
    without the burst issues of fixed windows.

    For production, should be backed by Redis for distributed rate limiting.
    """

    # Window size in seconds (1 minute)
    WINDOW_SIZE = 60

    def __init__(self, cleanup_interval: int = 300) -> None:
        """
        Initialize rate limiter.

        Args:
            cleanup_interval: Seconds between cleanup of old entries
        """
        # {client_id: [timestamp, timestamp, ...]}
        self._request_history: dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

        # Statistics
        self._stats: dict[str, Any] = {
            "total_requests": 0,
            "allowed": 0,
            "denied": 0,
            "by_tier": {
                tier.value: {"allowed": 0, "denied": 0} for tier in RateLimitTier
            },
        }

    def check(
        self,
        client_id: str,
        tier: RateLimitTier = RateLimitTier.STANDARD,
        limit_override: int | None = None,
    ) -> RateLimitResult:
        """
        Check if request should be allowed.

        Args:
            client_id: Unique identifier for the client (IP, user_id, API key)
            tier: Rate limit tier to apply
            limit_override: Override the default limit for the tier

        Returns:
            RateLimitResult with allowed status and metadata
        """
        now = time.time()
        window_start = now - self.WINDOW_SIZE

        # Periodically cleanup old entries
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
            self._last_cleanup = now

        # Get limit for this tier
        limit = limit_override or DEFAULT_LIMITS[tier.value]

        # Get request history for this client
        history = self._request_history[client_id]

        # Remove old entries outside the window
        history[:] = [ts for ts in history if ts > window_start]

        # Count requests in current window
        request_count = len(history)

        # Check if allowed (before recording current request)
        allowed = request_count < limit

        # Update stats
        self._stats["total_requests"] += 1
        if allowed:
            self._stats["allowed"] += 1
            self._stats["by_tier"][tier.value]["allowed"] += 1
            # Record this request
            history.append(now)
            # Calculate remaining AFTER recording current request
            remaining = max(0, limit - len(history))
        else:
            self._stats["denied"] += 1
            self._stats["by_tier"][tier.value]["denied"] += 1
            remaining = 0

        # Calculate reset time (when oldest request in window expires)
        if history:
            reset_at = min(history) + self.WINDOW_SIZE
        else:
            reset_at = now + self.WINDOW_SIZE

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining if allowed else 0,
            reset_at=reset_at,
            limit=limit,
            tier=tier,
            client_id=client_id,
        )

    def _cleanup(self) -> None:
        """Remove old entries to prevent memory growth."""
        now = time.time()
        window_start = now - self.WINDOW_SIZE

        # Remove entries older than window
        for client_id in list(self._request_history.keys()):
            history = self._request_history[client_id]
            history[:] = [ts for ts in history if ts > window_start]

            # Remove empty entries
            if not history:
                del self._request_history[client_id]

        logger.debug(
            f"Rate limiter cleanup: {len(self._request_history)} active clients"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            **self._stats,
            "active_clients": len(self._request_history),
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "total_requests": 0,
            "allowed": 0,
            "denied": 0,
            "by_tier": {
                tier.value: {"allowed": 0, "denied": 0} for tier in RateLimitTier
            },
        }


# =============================================================================
# FastAPI Integration
# =============================================================================
# Rate limiter singleton and disable state are managed via src.api.dependencies
# using @lru_cache factories. This module re-exports for backwards compatibility.

from src.api.dependencies import disable_rate_limiting  # noqa: F401
from src.api.dependencies import enable_rate_limiting  # noqa: F401
from src.api.dependencies import (
    clear_rate_limiter_cache,
    get_rate_limiter,
    is_rate_limiting_disabled,
)


def reset_rate_limiter() -> None:
    """
    Reset the global rate limiter instance.

    Used in tests to prevent rate limit state from bleeding between tests.
    Should NOT be called in production code.
    """
    clear_rate_limiter_cache()


def get_client_id(request: Request, use_user_id: bool = True) -> str:
    """
    Extract client identifier from request.

    Uses user ID if authenticated, otherwise falls back to IP.

    Args:
        request: FastAPI request
        use_user_id: Use authenticated user ID if available

    Returns:
        Client identifier string
    """
    # Try to get authenticated user
    if use_user_id and hasattr(request.state, "user"):
        user = request.state.user
        if hasattr(user, "sub"):
            return f"user:{user.sub}"
        if hasattr(user, "email"):
            return f"user:{user.email}"

    # Fall back to IP address
    client_ip = request.client.host if request.client else "unknown"

    # Check for X-Forwarded-For header (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        client_ip = forwarded.split(",")[0].strip()

    # Hash the IP for privacy in logs
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:12]
    return f"ip:{ip_hash}"


def rate_limit(
    tier: RateLimitTier = RateLimitTier.STANDARD,
    limit_override: int | None = None,
    key_func: Callable[[Request], str] | None = None,
) -> Callable:
    """
    Rate limiting decorator for FastAPI endpoints.

    Usage:
        @router.get("/resource")
        @rate_limit(tier=RateLimitTier.SENSITIVE)
        async def get_resource(request: Request):
            ...

    Args:
        tier: Rate limit tier to apply
        limit_override: Override default limit for tier
        key_func: Custom function to extract client key from request

    Returns:
        Decorated endpoint function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find Request object in args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if request is None:
                # No request object - skip rate limiting
                logger.warning(
                    f"Rate limit decorator on {func.__name__} but no Request found"
                )
                return (
                    await func(*args, **kwargs)
                    if asyncio.iscoroutinefunction(func)
                    else func(*args, **kwargs)
                )

            # Get client identifier
            if key_func:
                client_id = key_func(request)
            else:
                client_id = get_client_id(request)

            # Check rate limit
            limiter = get_rate_limiter()
            result = limiter.check(client_id, tier, limit_override)

            if not result.allowed:
                logger.warning(
                    f"Rate limit exceeded for {client_id}: "
                    f"tier={tier.value}, limit={result.limit}, retry_after={result.retry_after}s"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "Rate limit exceeded",
                        "tier": tier.value,
                        "limit": result.limit,
                        "retry_after": result.retry_after,
                    },
                    headers={
                        "Retry-After": str(result.retry_after),
                        **result.to_headers(),
                    },
                )

            # Add rate limit headers to response
            # Note: In production, use Response.headers in the endpoint
            # or middleware for cleaner header injection

            # Call the actual endpoint
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# FastAPI Dependency
# =============================================================================


class RateLimitDependency:
    """
    Rate limiting as a FastAPI dependency.

    Usage:
        @router.get("/resource")
        async def get_resource(
            request: Request,
            rate_check: RateLimitResult = Depends(RateLimitDependency(tier=RateLimitTier.SENSITIVE))
        ):
            # rate_check.remaining shows remaining requests
            ...
    """

    def __init__(
        self,
        tier: RateLimitTier = RateLimitTier.STANDARD,
        limit_override: int | None = None,
        key_func: Callable[[Request], str] | None = None,
    ):
        self.tier = tier
        self.limit_override = limit_override
        self.key_func = key_func

    def __call__(self, request: Request) -> RateLimitResult:
        """Check rate limit and return result."""
        # Skip rate limiting if disabled (for tests)
        if is_rate_limiting_disabled():
            return RateLimitResult(
                allowed=True,
                remaining=999,
                reset_at=time.time() + 60,
                limit=1000,
                tier=self.tier,
                client_id="disabled",
            )

        # Get client identifier
        if self.key_func:
            client_id = self.key_func(request)
        else:
            client_id = get_client_id(request)

        # Check rate limit
        limiter = get_rate_limiter()
        result = limiter.check(client_id, self.tier, self.limit_override)

        if not result.allowed:
            logger.warning(
                f"Rate limit exceeded for {client_id}: "
                f"tier={self.tier.value}, retry_after={result.retry_after}s"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "tier": self.tier.value,
                    "limit": result.limit,
                    "retry_after": result.retry_after,
                },
                headers={
                    "Retry-After": str(result.retry_after),
                    **result.to_headers(),
                },
            )

        return result


# =============================================================================
# Convenience Functions
# =============================================================================


# Pre-configured dependencies for common use cases
public_rate_limit = RateLimitDependency(tier=RateLimitTier.PUBLIC)
standard_rate_limit = RateLimitDependency(tier=RateLimitTier.STANDARD)
sensitive_rate_limit = RateLimitDependency(tier=RateLimitTier.SENSITIVE)
admin_rate_limit = RateLimitDependency(tier=RateLimitTier.ADMIN)
critical_rate_limit = RateLimitDependency(tier=RateLimitTier.CRITICAL)


def check_rate_limit(
    client_id: str,
    tier: RateLimitTier = RateLimitTier.STANDARD,
) -> RateLimitResult:
    """
    Convenience function to check rate limit.

    Args:
        client_id: Client identifier
        tier: Rate limit tier

    Returns:
        RateLimitResult

    Raises:
        HTTPException: If rate limit exceeded
    """
    limiter = get_rate_limiter()
    result = limiter.check(client_id, tier)

    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": result.retry_after,
            },
            headers={"Retry-After": str(result.retry_after)},
        )

    return result
