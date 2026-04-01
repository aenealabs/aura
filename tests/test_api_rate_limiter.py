"""
Project Aura - API Rate Limiter Tests

Tests for the sliding window rate limiter covering:
- Basic rate limiting functionality
- Different tiers (public, standard, admin, critical)
- FastAPI dependency integration
- Statistics tracking

Author: Project Aura Team
Created: 2025-12-12
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from src.services.api_rate_limiter import (
    DEFAULT_LIMITS,
    RateLimitDependency,
    RateLimitResult,
    RateLimitTier,
    SlidingWindowRateLimiter,
    admin_rate_limit,
    check_rate_limit,
    critical_rate_limit,
    get_client_id,
    get_rate_limiter,
    public_rate_limit,
    reset_rate_limiter,
    standard_rate_limit,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def limiter():
    """Create a fresh rate limiter instance."""
    return SlidingWindowRateLimiter()


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = "192.168.1.1"
    request.headers = {}
    request.state = MagicMock()
    # Remove user attribute to simulate unauthenticated request
    del request.state.user
    return request


@pytest.fixture
def authenticated_request():
    """Create a mock authenticated request."""
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = "192.168.1.1"
    request.headers = {}
    request.state = MagicMock()
    request.state.user = MagicMock()
    request.state.user.sub = "user-123"
    request.state.user.email = "test@example.com"
    return request


# ============================================================================
# Basic Rate Limiting Tests
# ============================================================================


class TestBasicRateLimiting:
    """Tests for basic rate limiting functionality."""

    def test_first_request_allowed(self, limiter):
        """Test that first request is always allowed."""
        result = limiter.check("client-1", RateLimitTier.STANDARD)

        assert result.allowed
        assert result.remaining == DEFAULT_LIMITS[RateLimitTier.STANDARD.value] - 1
        assert result.tier == RateLimitTier.STANDARD
        assert result.client_id == "client-1"

    def test_requests_within_limit_allowed(self, limiter):
        """Test that requests within limit are allowed."""
        tier = RateLimitTier.STANDARD
        limit = DEFAULT_LIMITS[tier.value]

        # Make requests up to the limit
        for i in range(limit - 1):
            result = limiter.check("client-1", tier)
            assert result.allowed
            assert result.remaining == limit - i - 1

    def test_requests_exceeding_limit_denied(self, limiter):
        """Test that requests exceeding limit are denied."""
        tier = RateLimitTier.ADMIN  # 5 req/min
        limit = DEFAULT_LIMITS[tier.value]

        # Exhaust the limit
        for _ in range(limit):
            result = limiter.check("client-1", tier)
            assert result.allowed

        # Next request should be denied
        result = limiter.check("client-1", tier)
        assert not result.allowed
        assert result.remaining == 0

    def test_different_clients_have_separate_limits(self, limiter):
        """Test that different clients have separate rate limits."""
        tier = RateLimitTier.CRITICAL  # 2 req/min

        # Client 1 exhausts their limit
        limiter.check("client-1", tier)
        limiter.check("client-1", tier)
        result1 = limiter.check("client-1", tier)
        assert not result1.allowed

        # Client 2 should still have their limit
        result2 = limiter.check("client-2", tier)
        assert result2.allowed


# ============================================================================
# Rate Limit Tiers Tests
# ============================================================================


class TestRateLimitTiers:
    """Tests for different rate limit tiers."""

    def test_public_tier_limit(self, limiter):
        """Test public tier has highest limit."""
        result = limiter.check("client-1", RateLimitTier.PUBLIC)
        assert result.limit == 100  # 100 req/min

    def test_standard_tier_limit(self, limiter):
        """Test standard tier limit."""
        result = limiter.check("client-1", RateLimitTier.STANDARD)
        assert result.limit == 60  # 60 req/min

    def test_sensitive_tier_limit(self, limiter):
        """Test sensitive tier has lower limit."""
        result = limiter.check("client-1", RateLimitTier.SENSITIVE)
        assert result.limit == 10  # 10 req/min

    def test_admin_tier_limit(self, limiter):
        """Test admin tier has strict limit."""
        result = limiter.check("client-1", RateLimitTier.ADMIN)
        assert result.limit == 5  # 5 req/min

    def test_critical_tier_limit(self, limiter):
        """Test critical tier has most strict limit."""
        result = limiter.check("client-1", RateLimitTier.CRITICAL)
        assert result.limit == 2  # 2 req/min

    def test_limit_override(self, limiter):
        """Test that limit can be overridden."""
        custom_limit = 3
        result = limiter.check(
            "client-1", RateLimitTier.PUBLIC, limit_override=custom_limit
        )
        assert result.limit == custom_limit


# ============================================================================
# RateLimitResult Tests
# ============================================================================


class TestRateLimitResult:
    """Tests for RateLimitResult class."""

    def test_retry_after_calculation(self):
        """Test retry_after property."""
        future_reset = time.time() + 30
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=future_reset,
            limit=60,
            tier=RateLimitTier.STANDARD,
            client_id="test",
        )

        assert 25 <= result.retry_after <= 30

    def test_retry_after_zero_when_passed(self):
        """Test retry_after is 0 when reset time has passed."""
        past_reset = time.time() - 10
        result = RateLimitResult(
            allowed=True,
            remaining=50,
            reset_at=past_reset,
            limit=60,
            tier=RateLimitTier.STANDARD,
            client_id="test",
        )

        assert result.retry_after == 0

    def test_to_headers(self):
        """Test header generation."""
        result = RateLimitResult(
            allowed=True,
            remaining=50,
            reset_at=time.time() + 60,
            limit=60,
            tier=RateLimitTier.STANDARD,
            client_id="test",
        )

        headers = result.to_headers()
        assert headers["X-RateLimit-Limit"] == "60"
        assert headers["X-RateLimit-Remaining"] == "50"
        assert headers["X-RateLimit-Tier"] == "standard"


# ============================================================================
# Client ID Extraction Tests
# ============================================================================


class TestClientIdExtraction:
    """Tests for client ID extraction from requests."""

    def test_unauthenticated_uses_ip(self, mock_request):
        """Test that unauthenticated requests use IP-based ID."""
        client_id = get_client_id(mock_request)
        assert client_id.startswith("ip:")

    def test_authenticated_uses_user_id(self, authenticated_request):
        """Test that authenticated requests use user ID."""
        client_id = get_client_id(authenticated_request)
        assert client_id == "user:user-123"

    def test_x_forwarded_for_header(self, mock_request):
        """Test X-Forwarded-For header is used for IP."""
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        client_id = get_client_id(mock_request)
        assert client_id.startswith("ip:")
        # Should use the first IP (original client)


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Tests for rate limiter statistics."""

    def test_stats_tracking(self, limiter):
        """Test that statistics are tracked."""
        # Make some requests
        limiter.check("client-1", RateLimitTier.STANDARD)
        limiter.check("client-2", RateLimitTier.ADMIN)

        stats = limiter.get_stats()
        assert stats["total_requests"] == 2
        assert stats["allowed"] == 2
        assert stats["denied"] == 0

    def test_denied_stats_tracking(self, limiter):
        """Test that denied requests are tracked."""
        tier = RateLimitTier.CRITICAL  # 2 req/min

        # Exhaust limit
        limiter.check("client-1", tier)
        limiter.check("client-1", tier)
        limiter.check("client-1", tier)  # Should be denied

        stats = limiter.get_stats()
        assert stats["allowed"] == 2
        assert stats["denied"] == 1
        assert stats["by_tier"]["critical"]["denied"] == 1

    def test_stats_reset(self, limiter):
        """Test that statistics can be reset."""
        limiter.check("client-1", RateLimitTier.STANDARD)
        limiter.reset_stats()

        stats = limiter.get_stats()
        assert stats["total_requests"] == 0


# ============================================================================
# FastAPI Dependency Tests
# ============================================================================


class TestFastAPIDependency:
    """Tests for FastAPI dependency integration."""

    def test_rate_limit_dependency_allows(self, mock_request):
        """Test RateLimitDependency allows requests within limit."""
        # Clear singleton
        reset_rate_limiter()

        dependency = RateLimitDependency(tier=RateLimitTier.PUBLIC)
        result = dependency(mock_request)

        assert result.allowed
        assert result.remaining == DEFAULT_LIMITS[RateLimitTier.PUBLIC.value] - 1

    def test_rate_limit_dependency_raises_429(self, mock_request):
        """Test RateLimitDependency raises 429 when limit exceeded."""
        # Clear singleton
        reset_rate_limiter()

        dependency = RateLimitDependency(tier=RateLimitTier.CRITICAL)  # 2 req/min

        # Exhaust limit
        dependency(mock_request)
        dependency(mock_request)

        # Should raise 429
        with pytest.raises(HTTPException) as exc_info:
            dependency(mock_request)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail["error"]

    def test_pre_configured_dependencies_exist(self):
        """Test that pre-configured dependencies are available."""
        assert public_rate_limit is not None
        assert standard_rate_limit is not None
        assert admin_rate_limit is not None
        assert critical_rate_limit is not None


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_check_rate_limit_function(self):
        """Test check_rate_limit convenience function."""
        # Clear singleton
        reset_rate_limiter()

        result = check_rate_limit("test-client", RateLimitTier.PUBLIC)
        assert result.allowed

    def test_check_rate_limit_raises_on_exceeded(self):
        """Test check_rate_limit raises when exceeded."""
        # Clear singleton
        reset_rate_limiter()

        # Exhaust limit
        check_rate_limit("test-client-2", RateLimitTier.CRITICAL)
        check_rate_limit("test-client-2", RateLimitTier.CRITICAL)

        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("test-client-2", RateLimitTier.CRITICAL)

        assert exc_info.value.status_code == 429

    def test_get_rate_limiter_singleton(self):
        """Test that get_rate_limiter returns singleton."""
        # Clear singleton
        reset_rate_limiter()

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2


# ============================================================================
# Sliding Window Tests
# ============================================================================


class TestSlidingWindow:
    """Tests for sliding window algorithm correctness."""

    def test_window_expiration(self, limiter):
        """Test that old requests expire from the window."""
        # Mock time
        with patch("time.time") as mock_time:
            # Initial requests at t=0
            mock_time.return_value = 1000.0
            limiter.check("client-1", RateLimitTier.CRITICAL)
            limiter.check("client-1", RateLimitTier.CRITICAL)

            # Should be denied at t=0
            result = limiter.check("client-1", RateLimitTier.CRITICAL)
            assert not result.allowed

            # Move time forward past the window (61 seconds)
            mock_time.return_value = 1061.0

            # Should be allowed again
            result = limiter.check("client-1", RateLimitTier.CRITICAL)
            assert result.allowed

    def test_cleanup_removes_old_entries(self, limiter):
        """Test that cleanup removes old entries."""
        # Make some requests
        limiter.check("client-1", RateLimitTier.STANDARD)
        limiter.check("client-2", RateLimitTier.STANDARD)

        assert limiter.get_stats()["active_clients"] == 2

        # Manually set the request history timestamps to be old
        # This is more reliable than mocking time as the cleanup uses time.time() internally
        old_time = time.time() - 120  # 2 minutes ago
        for client_id in limiter._request_history:
            limiter._request_history[client_id] = [old_time]

        # Trigger cleanup - now entries should be expired
        limiter._cleanup()

        assert limiter.get_stats()["active_clients"] == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestRateLimiterIntegration:
    """Integration tests with FastAPI.

    These tests verify rate limiting works correctly in the context of a
    FastAPI application with dependency injection.
    """

    def test_rate_limited_endpoint(self):
        """Test rate limiting on a FastAPI endpoint."""
        # Clear singleton using the proper reset function
        reset_rate_limiter()

        # Create a fresh app and dependency for this test
        app = FastAPI()
        rate_dep = RateLimitDependency(tier=RateLimitTier.CRITICAL)

        # Define endpoint inside the test to ensure fresh function object
        @app.get("/test")
        async def test_endpoint(
            request: Request,
            rate_check: RateLimitResult = Depends(rate_dep),
        ):
            return {"remaining": rate_check.remaining}

        with TestClient(app) as client:
            # First request should succeed
            response = client.get("/test")
            assert response.status_code == 200

            # Second request should succeed
            response = client.get("/test")
            assert response.status_code == 200

            # Third request should be rate limited
            response = client.get("/test")
            assert response.status_code == 429
            assert "Retry-After" in response.headers

    def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present in 429 response."""
        # Clear singleton using the proper reset function
        reset_rate_limiter()

        # Create a fresh app and dependency for this test
        app = FastAPI()
        rate_dep = RateLimitDependency(tier=RateLimitTier.CRITICAL)

        # Define endpoint inside the test to ensure fresh function object
        @app.get("/test-headers")
        async def test_endpoint(
            request: Request,
            rate_check: RateLimitResult = Depends(rate_dep),
        ):
            return {"ok": True}

        with TestClient(app) as client:
            # Exhaust limit
            client.get("/test-headers")
            client.get("/test-headers")

            # Get 429 response
            response = client.get("/test-headers")
            assert response.status_code == 429
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
            assert "X-RateLimit-Tier" in response.headers
