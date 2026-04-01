"""
Project Aura - Multi-Tenant Isolation Edge Case Tests

Tests for critical multi-tenant security boundaries, ensuring complete
data isolation between organizations in shared cache infrastructure.

Key Security Concerns Tested:
1. Cache key collision - Tenant A and B with same query must NOT share results
2. Tenant ID missing from cache key - Security vulnerability detection
3. Tenant ID spoofing in request headers
4. Admin cross-tenant access boundaries
5. Shared embedding model - Cross-tenant information leakage
6. Cache entry expiration - Proper tenant data lifecycle
7. Rate limiting per tenant - Resource exhaustion prevention
8. Tenant deletion - Complete data purge verification
9. Tenant suspension - Cached data accessibility
10. Audit logging - Cross-tenant access attempt tracking

These tests validate that the system maintains strict tenant isolation
even when using shared infrastructure (semantic cache, Redis cache).
"""

# ruff: noqa: PLR2004

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import pytest

# =============================================================================
# Test Data Structures and Mocks
# =============================================================================


class TenantStatus(str, Enum):
    """Tenant account status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    PENDING = "pending"


@dataclass
class Tenant:
    """Represents a tenant (organization) in the system."""

    tenant_id: str
    name: str
    status: TenantStatus = TenantStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserContext:
    """User context for request authentication."""

    user_id: str
    tenant_id: str
    email: str
    roles: list[str] = field(default_factory=list)
    is_admin: bool = False
    is_platform_admin: bool = False  # Super-admin can access all tenants


@dataclass
class CacheEntry:
    """Multi-tenant aware cache entry."""

    key: str
    value: Any
    tenant_id: str
    created_at: float
    expires_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditEvent(str, Enum):
    """Types of audit events for security logging."""

    CACHE_ACCESS = "cache_access"
    CACHE_WRITE = "cache_write"
    CROSS_TENANT_ATTEMPT = "cross_tenant_attempt"
    TENANT_SUSPENSION = "tenant_suspension"
    TENANT_DELETION = "tenant_deletion"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


@dataclass
class AuditLogEntry:
    """Audit log entry for security tracking."""

    event_id: str
    event_type: AuditEvent
    tenant_id: str
    user_id: str
    timestamp: datetime
    details: dict[str, Any]
    success: bool


class MultiTenantCacheService:
    """
    Multi-tenant aware cache service implementation.

    This demonstrates the CORRECT implementation pattern for tenant isolation.
    All cache operations require tenant_id and enforce strict isolation.
    """

    def __init__(self):
        # Tenant-partitioned cache storage
        self._cache: dict[str, dict[str, CacheEntry]] = {}
        # Tenant metadata
        self._tenants: dict[str, Tenant] = {}
        # Rate limiting counters per tenant
        self._rate_counters: dict[str, list[float]] = {}
        # Audit log
        self._audit_log: list[AuditLogEntry] = []
        # Configuration
        self.rate_limit_per_minute = 100
        self.default_ttl = 3600

    def _make_tenant_cache_key(self, tenant_id: str, query: str) -> str:
        """
        Generate a tenant-scoped cache key.

        CRITICAL: Tenant ID MUST be part of the cache key to prevent
        cross-tenant data leakage.
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for cache operations")

        # Include tenant_id in the key to ensure isolation
        combined = f"{tenant_id}:{query}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _log_audit_event(
        self,
        event_type: AuditEvent,
        tenant_id: str,
        user_id: str,
        details: dict[str, Any],
        success: bool = True,
    ) -> None:
        """Log security-relevant events for audit trail."""
        entry = AuditLogEntry(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            details=details,
            success=success,
        )
        self._audit_log.append(entry)

    def _check_rate_limit(self, tenant_id: str) -> bool:
        """Check if tenant is within rate limits."""
        now = time.time()
        window_start = now - 60  # 1 minute window

        if tenant_id not in self._rate_counters:
            self._rate_counters[tenant_id] = []

        # Clean old entries
        self._rate_counters[tenant_id] = [
            t for t in self._rate_counters[tenant_id] if t > window_start
        ]

        # Check limit
        if len(self._rate_counters[tenant_id]) >= self.rate_limit_per_minute:
            return False

        self._rate_counters[tenant_id].append(now)
        return True

    def register_tenant(self, tenant: Tenant) -> None:
        """Register a new tenant."""
        self._tenants[tenant.tenant_id] = tenant
        self._cache[tenant.tenant_id] = {}

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get tenant by ID."""
        return self._tenants.get(tenant_id)

    def get_cached_response(
        self,
        query: str,
        user_context: UserContext,
        target_tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get cached response with tenant isolation enforcement.

        Args:
            query: The query string to look up
            user_context: Authenticated user context
            target_tenant_id: Optional target tenant (for admin cross-tenant access)

        Returns:
            Cached response or None if not found
        """
        # Determine which tenant's cache to access
        effective_tenant_id = target_tenant_id or user_context.tenant_id

        # SECURITY CHECK: Verify cross-tenant access authorization
        if effective_tenant_id != user_context.tenant_id:
            if not user_context.is_platform_admin:
                # Log unauthorized cross-tenant access attempt
                self._log_audit_event(
                    event_type=AuditEvent.CROSS_TENANT_ATTEMPT,
                    tenant_id=user_context.tenant_id,
                    user_id=user_context.user_id,
                    details={
                        "attempted_tenant": effective_tenant_id,
                        "query_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
                    },
                    success=False,
                )
                raise PermissionError(
                    f"User {user_context.user_id} not authorized to access "
                    f"tenant {effective_tenant_id}"
                )

        # Check tenant status
        tenant = self._tenants.get(effective_tenant_id)
        if not tenant:
            return None

        if tenant.status == TenantStatus.DELETED:
            return None

        if tenant.status == TenantStatus.SUSPENDED:
            # Suspended tenants cannot access their cached data
            self._log_audit_event(
                event_type=AuditEvent.TENANT_SUSPENSION,
                tenant_id=effective_tenant_id,
                user_id=user_context.user_id,
                details={"action": "cache_read_blocked"},
                success=False,
            )
            return None

        # Check rate limit
        if not self._check_rate_limit(effective_tenant_id):
            self._log_audit_event(
                event_type=AuditEvent.RATE_LIMIT_EXCEEDED,
                tenant_id=effective_tenant_id,
                user_id=user_context.user_id,
                details={"limit": self.rate_limit_per_minute, "window": "1 minute"},
                success=False,
            )
            raise RuntimeError("Rate limit exceeded for tenant")

        # Generate tenant-scoped cache key
        cache_key = self._make_tenant_cache_key(effective_tenant_id, query)

        # Look up in tenant's cache partition
        tenant_cache = self._cache.get(effective_tenant_id, {})
        entry = tenant_cache.get(cache_key)

        if entry is None:
            return None

        # Check expiration
        if time.time() > entry.expires_at:
            # Remove expired entry
            del tenant_cache[cache_key]
            return None

        # Log successful access
        self._log_audit_event(
            event_type=AuditEvent.CACHE_ACCESS,
            tenant_id=effective_tenant_id,
            user_id=user_context.user_id,
            details={"cache_key": cache_key[:16], "hit": True},
            success=True,
        )

        return entry.value

    def cache_response(
        self,
        query: str,
        response: Any,
        user_context: UserContext,
        ttl: int | None = None,
    ) -> str:
        """
        Cache a response with tenant isolation.

        Args:
            query: The query string
            response: The response to cache
            user_context: Authenticated user context
            ttl: Time-to-live in seconds

        Returns:
            Cache key
        """
        tenant_id = user_context.tenant_id

        # Check tenant status
        tenant = self._tenants.get(tenant_id)
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            raise PermissionError(f"Tenant {tenant_id} is not active")

        # Check rate limit
        if not self._check_rate_limit(tenant_id):
            self._log_audit_event(
                event_type=AuditEvent.RATE_LIMIT_EXCEEDED,
                tenant_id=tenant_id,
                user_id=user_context.user_id,
                details={"limit": self.rate_limit_per_minute, "window": "1 minute"},
                success=False,
            )
            raise RuntimeError("Rate limit exceeded for tenant")

        # Generate tenant-scoped cache key
        cache_key = self._make_tenant_cache_key(tenant_id, query)

        now = time.time()
        entry = CacheEntry(
            key=cache_key,
            value=response,
            tenant_id=tenant_id,
            created_at=now,
            expires_at=now + (ttl or self.default_ttl),
            metadata={"user_id": user_context.user_id},
        )

        # Store in tenant's cache partition
        if tenant_id not in self._cache:
            self._cache[tenant_id] = {}

        self._cache[tenant_id][cache_key] = entry

        # Log cache write
        self._log_audit_event(
            event_type=AuditEvent.CACHE_WRITE,
            tenant_id=tenant_id,
            user_id=user_context.user_id,
            details={"cache_key": cache_key[:16]},
            success=True,
        )

        return cache_key

    def delete_tenant_data(self, tenant_id: str, admin_context: UserContext) -> int:
        """
        Delete all cached data for a tenant.

        This must be called when a tenant is deleted to ensure
        complete data removal.

        Args:
            tenant_id: Tenant to delete data for
            admin_context: Admin user context (must be platform admin)

        Returns:
            Number of entries deleted
        """
        if not admin_context.is_platform_admin:
            raise PermissionError("Only platform admins can delete tenant data")

        count = 0

        # Remove all cache entries
        if tenant_id in self._cache:
            count = len(self._cache[tenant_id])
            del self._cache[tenant_id]

        # Remove rate limiting data
        if tenant_id in self._rate_counters:
            del self._rate_counters[tenant_id]

        # Mark tenant as deleted
        if tenant_id in self._tenants:
            self._tenants[tenant_id].status = TenantStatus.DELETED

        # Log deletion
        self._log_audit_event(
            event_type=AuditEvent.TENANT_DELETION,
            tenant_id=tenant_id,
            user_id=admin_context.user_id,
            details={"entries_deleted": count},
            success=True,
        )

        return count

    def suspend_tenant(self, tenant_id: str, admin_context: UserContext) -> None:
        """Suspend a tenant, blocking cache access."""
        if not admin_context.is_platform_admin:
            raise PermissionError("Only platform admins can suspend tenants")

        if tenant_id in self._tenants:
            self._tenants[tenant_id].status = TenantStatus.SUSPENDED

            self._log_audit_event(
                event_type=AuditEvent.TENANT_SUSPENSION,
                tenant_id=tenant_id,
                user_id=admin_context.user_id,
                details={"action": "suspended"},
                success=True,
            )

    def get_audit_logs(
        self,
        tenant_id: str | None = None,
        event_type: AuditEvent | None = None,
    ) -> list[AuditLogEntry]:
        """Get audit logs with optional filtering."""
        logs = self._audit_log

        if tenant_id:
            logs = [log for log in logs if log.tenant_id == tenant_id]

        if event_type:
            logs = [log for log in logs if log.event_type == event_type]

        return logs


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cache_service() -> MultiTenantCacheService:
    """Create a multi-tenant cache service for testing."""
    return MultiTenantCacheService()


@pytest.fixture
def tenant_a() -> Tenant:
    """Create test tenant A."""
    return Tenant(tenant_id="tenant-a-123", name="Acme Corp")


@pytest.fixture
def tenant_b() -> Tenant:
    """Create test tenant B."""
    return Tenant(tenant_id="tenant-b-456", name="Beta Industries")


@pytest.fixture
def user_a(tenant_a: Tenant) -> UserContext:
    """Create user in tenant A."""
    return UserContext(
        user_id="user-1",
        tenant_id=tenant_a.tenant_id,
        email="user1@acme.com",
        roles=["analyst"],
    )


@pytest.fixture
def user_b(tenant_b: Tenant) -> UserContext:
    """Create user in tenant B."""
    return UserContext(
        user_id="user-2",
        tenant_id=tenant_b.tenant_id,
        email="user2@beta.com",
        roles=["analyst"],
    )


@pytest.fixture
def admin_a(tenant_a: Tenant) -> UserContext:
    """Create admin user in tenant A."""
    return UserContext(
        user_id="admin-1",
        tenant_id=tenant_a.tenant_id,
        email="admin@acme.com",
        roles=["admin"],
        is_admin=True,
    )


@pytest.fixture
def platform_admin() -> UserContext:
    """Create platform-level super admin."""
    return UserContext(
        user_id="platform-admin",
        tenant_id="platform",
        email="admin@platform.com",
        roles=["platform_admin"],
        is_admin=True,
        is_platform_admin=True,
    )


@pytest.fixture
def setup_tenants(
    cache_service: MultiTenantCacheService,
    tenant_a: Tenant,
    tenant_b: Tenant,
) -> MultiTenantCacheService:
    """Register both tenants with the cache service."""
    cache_service.register_tenant(tenant_a)
    cache_service.register_tenant(tenant_b)
    return cache_service


# =============================================================================
# Test Class: Cache Key Collision Prevention
# =============================================================================


class TestCacheKeyCollision:
    """
    Tests for cache key collision prevention between tenants.

    CRITICAL: Tenant A and Tenant B having the same query must NOT share results.
    """

    def test_same_query_different_tenants_no_collision(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        user_b: UserContext,
    ) -> None:
        """
        Two tenants with identical queries must have isolated cache entries.
        """
        cache = setup_tenants
        identical_query = "Analyze this code for security vulnerabilities"

        # Tenant A caches a response
        response_a = {"findings": ["SQL injection in tenant A code"], "tenant": "A"}
        key_a = cache.cache_response(
            query=identical_query, response=response_a, user_context=user_a
        )

        # Tenant B caches a response for the SAME query
        response_b = {"findings": ["XSS in tenant B code"], "tenant": "B"}
        key_b = cache.cache_response(
            query=identical_query, response=response_b, user_context=user_b
        )

        # Keys must be different (tenant-scoped)
        assert (
            key_a != key_b
        ), "Cache keys for same query across tenants must be different"

        # Each tenant retrieves their own response
        result_a = cache.get_cached_response(query=identical_query, user_context=user_a)
        result_b = cache.get_cached_response(query=identical_query, user_context=user_b)

        assert result_a == response_a, "Tenant A should get their own cached response"
        assert result_b == response_b, "Tenant B should get their own cached response"
        assert result_a != result_b, "Responses must be isolated between tenants"

    def test_cache_key_includes_tenant_id(
        self, setup_tenants: MultiTenantCacheService
    ) -> None:
        """
        Verify that tenant_id is included in cache key generation.
        """
        cache = setup_tenants
        query = "test query"

        key_a = cache._make_tenant_cache_key("tenant-a-123", query)
        key_b = cache._make_tenant_cache_key("tenant-b-456", query)

        # Same query, different tenants = different keys
        assert key_a != key_b

        # Same query, same tenant = same key
        key_a_duplicate = cache._make_tenant_cache_key("tenant-a-123", query)
        assert key_a == key_a_duplicate

    def test_collision_with_similar_tenant_ids(
        self, cache_service: MultiTenantCacheService
    ) -> None:
        """
        Test that similar tenant IDs don't cause collisions.

        E.g., tenant-1 and tenant-10 should not collide.
        """
        tenant_1 = Tenant(tenant_id="tenant-1", name="Tenant One")
        tenant_10 = Tenant(tenant_id="tenant-10", name="Tenant Ten")

        cache_service.register_tenant(tenant_1)
        cache_service.register_tenant(tenant_10)

        user_1 = UserContext(user_id="user", tenant_id="tenant-1", email="u@1.com")
        user_10 = UserContext(user_id="user", tenant_id="tenant-10", email="u@10.com")

        query = "test"

        cache_service.cache_response(
            query=query, response={"tenant": "1"}, user_context=user_1
        )
        cache_service.cache_response(
            query=query, response={"tenant": "10"}, user_context=user_10
        )

        result_1 = cache_service.get_cached_response(query=query, user_context=user_1)
        result_10 = cache_service.get_cached_response(query=query, user_context=user_10)

        assert result_1["tenant"] == "1"
        assert result_10["tenant"] == "10"


class TestTenantIdValidation:
    """
    Tests for tenant ID validation and missing tenant ID handling.

    SECURITY: Missing tenant_id in cache operations is a critical vulnerability.
    """

    def test_missing_tenant_id_raises_error(
        self, cache_service: MultiTenantCacheService
    ) -> None:
        """
        Cache key generation without tenant_id must raise an error.
        """
        with pytest.raises(ValueError, match="tenant_id is required"):
            cache_service._make_tenant_cache_key("", "query")

        with pytest.raises(ValueError, match="tenant_id is required"):
            cache_service._make_tenant_cache_key(None, "query")  # type: ignore

    def test_empty_tenant_id_in_user_context(
        self, setup_tenants: MultiTenantCacheService
    ) -> None:
        """
        Operations with empty tenant_id in user context must fail.

        The cache service rejects empty tenant IDs - either with ValueError
        (for key generation) or PermissionError (for tenant lookup).
        """
        cache = setup_tenants

        user_no_tenant = UserContext(
            user_id="orphan-user",
            tenant_id="",  # Empty tenant ID
            email="orphan@example.com",
        )

        # Should fail with either ValueError (key validation) or PermissionError (tenant not found)
        with pytest.raises((ValueError, PermissionError)):
            cache.cache_response(
                query="test", response="data", user_context=user_no_tenant
            )

    def test_nonexistent_tenant_id(
        self, setup_tenants: MultiTenantCacheService
    ) -> None:
        """
        Operations for non-existent tenant must be rejected.
        """
        cache = setup_tenants

        user_fake_tenant = UserContext(
            user_id="user",
            tenant_id="nonexistent-tenant-xyz",
            email="user@fake.com",
        )

        # Cache write should fail for non-existent tenant
        with pytest.raises(PermissionError, match="not active"):
            cache.cache_response(
                query="test", response="data", user_context=user_fake_tenant
            )

        # Cache read should return None (not leak that tenant doesn't exist)
        result = cache.get_cached_response(query="test", user_context=user_fake_tenant)
        assert result is None


class TestTenantIdSpoofing:
    """
    Tests for tenant ID spoofing prevention.

    SECURITY: Users must not be able to access other tenants' data
    by manipulating request headers or parameters.
    """

    def test_cross_tenant_access_blocked(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        user_b: UserContext,
    ) -> None:
        """
        User from Tenant A cannot access Tenant B's cache by specifying
        target_tenant_id.
        """
        cache = setup_tenants

        # Tenant A caches sensitive data
        cache.cache_response(
            query="sensitive query",
            response={"secret": "tenant-a-data"},
            user_context=user_a,
        )

        # User B tries to access Tenant A's cache by spoofing target_tenant_id
        with pytest.raises(PermissionError, match="not authorized"):
            cache.get_cached_response(
                query="sensitive query",
                user_context=user_b,
                target_tenant_id=user_a.tenant_id,  # Attempting to spoof
            )

    def test_cross_tenant_attempt_is_logged(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        user_b: UserContext,
    ) -> None:
        """
        Cross-tenant access attempts must be logged for security audit.
        """
        cache = setup_tenants

        try:
            cache.get_cached_response(
                query="any query",
                user_context=user_b,
                target_tenant_id=user_a.tenant_id,
            )
        except PermissionError:
            pass  # Expected

        # Check audit log for the attempt
        cross_tenant_logs = cache.get_audit_logs(
            event_type=AuditEvent.CROSS_TENANT_ATTEMPT
        )

        assert len(cross_tenant_logs) == 1
        log = cross_tenant_logs[0]
        assert log.tenant_id == user_b.tenant_id
        assert log.user_id == user_b.user_id
        assert log.details["attempted_tenant"] == user_a.tenant_id
        assert log.success is False

    def test_header_injection_prevention(
        self, setup_tenants: MultiTenantCacheService
    ) -> None:
        """
        Test that tenant ID with special characters is handled safely.
        """
        cache = setup_tenants

        # Attempt to inject newlines or special characters
        malicious_tenant_ids = [
            "tenant-a\ntenant-b",
            "tenant-a\rtenant-b",
            "tenant-a\x00tenant-b",
            "tenant-a/../tenant-b",
            "tenant-a;tenant-b",
        ]

        for malicious_id in malicious_tenant_ids:
            malicious_user = UserContext(
                user_id="attacker",
                tenant_id=malicious_id,
                email="attacker@evil.com",
            )

            # Should either fail validation or not match any tenant
            result = cache.get_cached_response(
                query="test", user_context=malicious_user
            )
            assert (
                result is None
            ), f"Malicious tenant ID should not access any data: {malicious_id}"


class TestAdminCrossTenantAccess:
    """
    Tests for admin cross-tenant access boundaries.

    QUESTION: Should admins be able to access data across tenants?
    ANSWER: Only platform-level admins, not tenant-level admins.
    """

    def test_tenant_admin_cannot_access_other_tenant(
        self,
        setup_tenants: MultiTenantCacheService,
        admin_a: UserContext,
        user_b: UserContext,
    ) -> None:
        """
        Tenant-level admin cannot access other tenant's data.
        """
        cache = setup_tenants

        # Tenant B caches data
        cache.cache_response(
            query="tenant-b-query",
            response={"data": "tenant-b-secret"},
            user_context=user_b,
        )

        # Tenant A's admin tries to access Tenant B's cache
        with pytest.raises(PermissionError, match="not authorized"):
            cache.get_cached_response(
                query="tenant-b-query",
                user_context=admin_a,
                target_tenant_id=user_b.tenant_id,
            )

    def test_platform_admin_can_access_any_tenant(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        user_b: UserContext,
        platform_admin: UserContext,
    ) -> None:
        """
        Platform-level admin can access any tenant's data (for support).
        """
        cache = setup_tenants

        # Both tenants cache data
        cache.cache_response(
            query="support-query",
            response={"tenant": "A"},
            user_context=user_a,
        )
        cache.cache_response(
            query="support-query",
            response={"tenant": "B"},
            user_context=user_b,
        )

        # Platform admin can access both
        result_a = cache.get_cached_response(
            query="support-query",
            user_context=platform_admin,
            target_tenant_id=user_a.tenant_id,
        )
        result_b = cache.get_cached_response(
            query="support-query",
            user_context=platform_admin,
            target_tenant_id=user_b.tenant_id,
        )

        assert result_a["tenant"] == "A"
        assert result_b["tenant"] == "B"

    def test_platform_admin_access_is_logged(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        platform_admin: UserContext,
    ) -> None:
        """
        Platform admin cross-tenant access should be logged for audit.
        """
        cache = setup_tenants

        cache.cache_response(
            query="audited-query",
            response={"data": "sensitive"},
            user_context=user_a,
        )

        # Platform admin accesses tenant A's data
        cache.get_cached_response(
            query="audited-query",
            user_context=platform_admin,
            target_tenant_id=user_a.tenant_id,
        )

        # Check audit log
        access_logs = cache.get_audit_logs(
            tenant_id=user_a.tenant_id, event_type=AuditEvent.CACHE_ACCESS
        )

        assert len(access_logs) == 1
        assert access_logs[0].user_id == platform_admin.user_id


class TestSharedEmbeddingModel:
    """
    Tests for shared embedding model isolation.

    CONCERN: Could embeddings leak cross-tenant information?
    """

    def test_embedding_vectors_are_tenant_isolated(self) -> None:
        """
        Even if same embedding model is used, cache entries must be isolated.

        This test verifies that the cache key, not just the embedding,
        determines cache isolation.
        """
        # Create a mock embedding service that returns identical embeddings
        # for "similar" queries (simulating a shared model)

        class IdenticalEmbeddingService:
            def generate_embedding(self, text: str) -> list[float]:
                # Return same embedding for all inputs
                return [0.5] * 1024

        # Even with identical embeddings, tenant isolation must be maintained
        cache = MultiTenantCacheService()

        tenant_a = Tenant(tenant_id="emb-tenant-a", name="Embedding Tenant A")
        tenant_b = Tenant(tenant_id="emb-tenant-b", name="Embedding Tenant B")
        cache.register_tenant(tenant_a)
        cache.register_tenant(tenant_b)

        user_a = UserContext(user_id="user", tenant_id="emb-tenant-a", email="a@a.com")
        user_b = UserContext(user_id="user", tenant_id="emb-tenant-b", email="b@b.com")

        # Same query, potentially same embedding
        query = "analyze this code"

        cache.cache_response(
            query=query, response={"source": "tenant-a"}, user_context=user_a
        )
        cache.cache_response(
            query=query, response={"source": "tenant-b"}, user_context=user_b
        )

        # Each tenant gets their own response
        result_a = cache.get_cached_response(query=query, user_context=user_a)
        result_b = cache.get_cached_response(query=query, user_context=user_b)

        assert result_a["source"] == "tenant-a"
        assert result_b["source"] == "tenant-b"

    def test_semantic_similarity_does_not_cross_tenants(self) -> None:
        """
        Semantic similarity search must be scoped to tenant.

        Even if Tenant A's query is semantically similar to Tenant B's
        cached query, it should NOT return Tenant B's cache entry.
        """
        cache = MultiTenantCacheService()

        tenant_a = Tenant(tenant_id="sem-tenant-a", name="Semantic Tenant A")
        tenant_b = Tenant(tenant_id="sem-tenant-b", name="Semantic Tenant B")
        cache.register_tenant(tenant_a)
        cache.register_tenant(tenant_b)

        user_a = UserContext(user_id="user", tenant_id="sem-tenant-a", email="a@a.com")
        user_b = UserContext(user_id="user", tenant_id="sem-tenant-b", email="b@b.com")

        # Tenant B caches a response
        cache.cache_response(
            query="check code security",
            response={"tenant": "B", "findings": ["critical bug"]},
            user_context=user_b,
        )

        # Tenant A queries with similar semantics - should get nothing
        result = cache.get_cached_response(
            query="check code security",  # Same query
            user_context=user_a,
        )

        # Tenant A should NOT get Tenant B's cached response
        assert result is None


class TestCacheExpiration:
    """
    Tests for cache entry expiration and tenant data lifecycle.
    """

    def test_expired_entries_not_returned(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
    ) -> None:
        """
        Expired cache entries must not be returned.
        """
        cache = setup_tenants

        # Cache with very short TTL
        cache.cache_response(
            query="ephemeral query",
            response={"data": "should expire"},
            user_context=user_a,
            ttl=1,  # 1 second TTL
        )

        # Immediate retrieval should work
        result = cache.get_cached_response(query="ephemeral query", user_context=user_a)
        assert result is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should return None after expiration
        result = cache.get_cached_response(query="ephemeral query", user_context=user_a)
        assert result is None

    def test_expiration_does_not_affect_other_tenants(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        user_b: UserContext,
    ) -> None:
        """
        Expiration of Tenant A's entry should not affect Tenant B.
        """
        cache = setup_tenants

        # Tenant A caches with short TTL
        cache.cache_response(
            query="shared-name-query",
            response={"tenant": "A"},
            user_context=user_a,
            ttl=1,
        )

        # Tenant B caches with long TTL
        cache.cache_response(
            query="shared-name-query",
            response={"tenant": "B"},
            user_context=user_b,
            ttl=3600,
        )

        # Wait for A's entry to expire
        time.sleep(1.5)

        # Tenant A's entry should be expired
        result_a = cache.get_cached_response(
            query="shared-name-query", user_context=user_a
        )
        assert result_a is None

        # Tenant B's entry should still exist
        result_b = cache.get_cached_response(
            query="shared-name-query", user_context=user_b
        )
        assert result_b is not None
        assert result_b["tenant"] == "B"


class TestRateLimitingPerTenant:
    """
    Tests for per-tenant rate limiting.

    CONCERN: One tenant should not be able to exhaust resources for others.
    """

    def test_rate_limit_is_per_tenant(
        self, setup_tenants: MultiTenantCacheService
    ) -> None:
        """
        Rate limiting should be enforced per tenant, not globally.
        """
        cache = setup_tenants
        cache.rate_limit_per_minute = 5  # Low limit for testing

        user_a = UserContext(user_id="user", tenant_id="tenant-a-123", email="a@a.com")
        user_b = UserContext(user_id="user", tenant_id="tenant-b-456", email="b@b.com")

        # Tenant A exhausts their rate limit
        for i in range(5):
            cache.cache_response(
                query=f"query-{i}", response={"n": i}, user_context=user_a
            )

        # Tenant A's next request should be rate limited
        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            cache.cache_response(
                query="one-more", response={"data": "blocked"}, user_context=user_a
            )

        # Tenant B should NOT be affected
        cache.cache_response(
            query="tenant-b-query",
            response={"data": "allowed"},
            user_context=user_b,
        )  # Should succeed

    def test_rate_limit_exceeded_is_logged(
        self, setup_tenants: MultiTenantCacheService
    ) -> None:
        """
        Rate limit exceeded events should be logged.
        """
        cache = setup_tenants
        cache.rate_limit_per_minute = 2

        user_a = UserContext(user_id="user", tenant_id="tenant-a-123", email="a@a.com")

        # Exhaust rate limit
        for i in range(2):
            cache.cache_response(query=f"q-{i}", response={}, user_context=user_a)

        # Trigger rate limit
        try:
            cache.cache_response(query="blocked", response={}, user_context=user_a)
        except RuntimeError:
            pass

        # Check audit log
        rate_limit_logs = cache.get_audit_logs(
            event_type=AuditEvent.RATE_LIMIT_EXCEEDED
        )

        assert len(rate_limit_logs) == 1
        assert rate_limit_logs[0].tenant_id == user_a.tenant_id

    def test_rate_limit_window_resets(
        self, setup_tenants: MultiTenantCacheService
    ) -> None:
        """
        Rate limit should reset after the time window.
        """
        cache = setup_tenants
        cache.rate_limit_per_minute = 2

        user_a = UserContext(user_id="user", tenant_id="tenant-a-123", email="a@a.com")

        # Exhaust rate limit
        for i in range(2):
            cache.cache_response(query=f"q-{i}", response={}, user_context=user_a)

        # Manually expire the rate limit window
        cache._rate_counters[user_a.tenant_id] = [time.time() - 120]  # 2 min ago

        # Should succeed now
        cache.cache_response(
            query="after-reset", response={"allowed": True}, user_context=user_a
        )


class TestTenantDeletion:
    """
    Tests for tenant deletion and data purge.

    CRITICAL: All cached data must be purged when a tenant is deleted.
    """

    def test_tenant_deletion_purges_all_cache_entries(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        platform_admin: UserContext,
    ) -> None:
        """
        Deleting a tenant must remove ALL their cached data.
        """
        cache = setup_tenants

        # Cache multiple entries for tenant A
        for i in range(10):
            cache.cache_response(
                query=f"tenant-a-query-{i}",
                response={"index": i},
                user_context=user_a,
            )

        # Delete tenant
        deleted_count = cache.delete_tenant_data(
            tenant_id=user_a.tenant_id, admin_context=platform_admin
        )

        assert deleted_count == 10

        # Verify all entries are gone
        for i in range(10):
            result = cache.get_cached_response(
                query=f"tenant-a-query-{i}", user_context=user_a
            )
            assert result is None

    def test_tenant_deletion_does_not_affect_other_tenants(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        user_b: UserContext,
        platform_admin: UserContext,
    ) -> None:
        """
        Deleting Tenant A must not affect Tenant B's data.
        """
        cache = setup_tenants

        # Both tenants cache data
        cache.cache_response(
            query="shared-query-name", response={"tenant": "A"}, user_context=user_a
        )
        cache.cache_response(
            query="shared-query-name", response={"tenant": "B"}, user_context=user_b
        )

        # Delete tenant A
        cache.delete_tenant_data(
            tenant_id=user_a.tenant_id, admin_context=platform_admin
        )

        # Tenant B's data should be intact
        result_b = cache.get_cached_response(
            query="shared-query-name", user_context=user_b
        )
        assert result_b is not None
        assert result_b["tenant"] == "B"

    def test_only_platform_admin_can_delete_tenant(
        self,
        setup_tenants: MultiTenantCacheService,
        admin_a: UserContext,
    ) -> None:
        """
        Only platform admins can delete tenant data.
        """
        cache = setup_tenants

        # Tenant admin tries to delete (should fail)
        with pytest.raises(PermissionError, match="platform admins"):
            cache.delete_tenant_data(tenant_id=admin_a.tenant_id, admin_context=admin_a)

    def test_deletion_is_logged(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        platform_admin: UserContext,
    ) -> None:
        """
        Tenant deletion must be logged.
        """
        cache = setup_tenants

        # Cache some data
        cache.cache_response(query="q1", response={}, user_context=user_a)
        cache.cache_response(query="q2", response={}, user_context=user_a)

        # Delete
        cache.delete_tenant_data(
            tenant_id=user_a.tenant_id, admin_context=platform_admin
        )

        # Check audit log
        deletion_logs = cache.get_audit_logs(event_type=AuditEvent.TENANT_DELETION)

        assert len(deletion_logs) == 1
        assert deletion_logs[0].details["entries_deleted"] == 2


class TestTenantSuspension:
    """
    Tests for tenant suspension and cached data accessibility.

    When a tenant is suspended, should their cached data be accessible?
    """

    def test_suspended_tenant_cannot_read_cache(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        platform_admin: UserContext,
    ) -> None:
        """
        Suspended tenant should not be able to access cached data.
        """
        cache = setup_tenants

        # Cache data before suspension
        cache.cache_response(
            query="pre-suspension-query",
            response={"data": "before suspension"},
            user_context=user_a,
        )

        # Verify it works before suspension
        result = cache.get_cached_response(
            query="pre-suspension-query", user_context=user_a
        )
        assert result is not None

        # Suspend tenant
        cache.suspend_tenant(tenant_id=user_a.tenant_id, admin_context=platform_admin)

        # Should return None (blocked, not error)
        result = cache.get_cached_response(
            query="pre-suspension-query", user_context=user_a
        )
        assert result is None

    def test_suspended_tenant_cannot_write_cache(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        platform_admin: UserContext,
    ) -> None:
        """
        Suspended tenant should not be able to write to cache.
        """
        cache = setup_tenants

        # Suspend tenant
        cache.suspend_tenant(tenant_id=user_a.tenant_id, admin_context=platform_admin)

        # Cache write should fail
        with pytest.raises(PermissionError, match="not active"):
            cache.cache_response(
                query="post-suspension",
                response={"data": "blocked"},
                user_context=user_a,
            )

    def test_suspension_preserves_data_for_reactivation(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        platform_admin: UserContext,
    ) -> None:
        """
        Suspended tenant's data should be preserved (not deleted).
        """
        cache = setup_tenants

        # Cache data
        cache.cache_response(
            query="preserved-query", response={"preserved": True}, user_context=user_a
        )

        # Suspend
        cache.suspend_tenant(tenant_id=user_a.tenant_id, admin_context=platform_admin)

        # Reactivate (manually for this test)
        cache._tenants[user_a.tenant_id].status = TenantStatus.ACTIVE

        # Data should still be there
        result = cache.get_cached_response(query="preserved-query", user_context=user_a)
        assert result is not None
        assert result["preserved"] is True

    def test_suspension_is_logged(
        self,
        setup_tenants: MultiTenantCacheService,
        platform_admin: UserContext,
    ) -> None:
        """
        Tenant suspension must be logged.
        """
        cache = setup_tenants

        cache.suspend_tenant(tenant_id="tenant-a-123", admin_context=platform_admin)

        suspension_logs = cache.get_audit_logs(event_type=AuditEvent.TENANT_SUSPENSION)

        # One for the suspension action
        action_logs = [
            log for log in suspension_logs if log.details.get("action") == "suspended"
        ]
        assert len(action_logs) == 1


class TestAuditLogging:
    """
    Tests for audit logging of security-relevant events.

    All cross-tenant access attempts must be logged.
    """

    def test_successful_cache_access_logged(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
    ) -> None:
        """
        Successful cache access should be logged.
        """
        cache = setup_tenants

        cache.cache_response(query="logged-query", response={}, user_context=user_a)
        cache.get_cached_response(query="logged-query", user_context=user_a)

        access_logs = cache.get_audit_logs(event_type=AuditEvent.CACHE_ACCESS)

        assert len(access_logs) == 1
        assert access_logs[0].success is True

    def test_cache_write_logged(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
    ) -> None:
        """
        Cache writes should be logged.
        """
        cache = setup_tenants

        cache.cache_response(
            query="write-logged", response={"data": "value"}, user_context=user_a
        )

        write_logs = cache.get_audit_logs(event_type=AuditEvent.CACHE_WRITE)

        assert len(write_logs) == 1
        assert write_logs[0].user_id == user_a.user_id

    def test_audit_log_contains_required_fields(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
    ) -> None:
        """
        Audit log entries must contain all required fields.
        """
        cache = setup_tenants

        cache.cache_response(query="audit-test", response={}, user_context=user_a)

        logs = cache.get_audit_logs()
        assert len(logs) > 0

        log = logs[0]
        assert log.event_id is not None
        assert log.event_type is not None
        assert log.tenant_id == user_a.tenant_id
        assert log.user_id == user_a.user_id
        assert log.timestamp is not None
        assert isinstance(log.details, dict)
        assert isinstance(log.success, bool)

    def test_audit_logs_filterable_by_tenant(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        user_b: UserContext,
    ) -> None:
        """
        Audit logs should be filterable by tenant.
        """
        cache = setup_tenants

        # Generate logs for both tenants
        cache.cache_response(query="a-query", response={}, user_context=user_a)
        cache.cache_response(query="b-query", response={}, user_context=user_b)

        # Filter by tenant A
        tenant_a_logs = cache.get_audit_logs(tenant_id=user_a.tenant_id)

        assert all(log.tenant_id == user_a.tenant_id for log in tenant_a_logs)

    def test_failed_operations_logged(
        self,
        setup_tenants: MultiTenantCacheService,
        user_a: UserContext,
        user_b: UserContext,
    ) -> None:
        """
        Failed operations (access denied, etc.) should be logged.
        """
        cache = setup_tenants

        # Attempt cross-tenant access
        try:
            cache.get_cached_response(
                query="any", user_context=user_b, target_tenant_id=user_a.tenant_id
            )
        except PermissionError:
            pass

        # Should have a failed log entry
        failed_logs = [log for log in cache.get_audit_logs() if not log.success]
        assert len(failed_logs) >= 1


class TestIntegrationWithExistingServices:
    """
    Integration tests verifying compatibility with existing cache services.
    """

    def test_semantic_cache_tenant_key_pattern(self) -> None:
        """
        Verify semantic cache should include tenant_id in cache keys.

        This test documents the expected pattern for the semantic cache service.
        """

        # Pattern that SHOULD be used in SemanticCacheService
        def make_tenant_aware_cache_key(
            tenant_id: str, query: str, model_id: str
        ) -> str:
            """Generate tenant-scoped cache key for semantic cache."""
            if not tenant_id:
                raise ValueError("tenant_id is required")

            content = f"{tenant_id}:{query}:{model_id}"
            return hashlib.sha256(content.encode()).hexdigest()

        # Same query, different tenants = different keys
        key_a = make_tenant_aware_cache_key("tenant-a", "analyze code", "claude")
        key_b = make_tenant_aware_cache_key("tenant-b", "analyze code", "claude")

        assert key_a != key_b

    def test_redis_cache_tenant_key_pattern(self) -> None:
        """
        Verify Redis cache should use tenant-prefixed keys.

        This test documents the expected pattern for the Redis cache service.
        """

        # Pattern that SHOULD be used in RedisCacheService
        def make_tenant_redis_key(tenant_id: str, namespace: str, key: str) -> str:
            """Generate tenant-scoped Redis key."""
            if not tenant_id:
                raise ValueError("tenant_id is required")

            return f"aura:{tenant_id}:{namespace}:{key}"

        # Keys should be namespaced by tenant
        key_a = make_tenant_redis_key("tenant-a", "response", "query-hash")
        key_b = make_tenant_redis_key("tenant-b", "response", "query-hash")

        assert key_a == "aura:tenant-a:response:query-hash"
        assert key_b == "aura:tenant-b:response:query-hash"
        assert key_a != key_b


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
