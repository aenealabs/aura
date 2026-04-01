"""
Tests for integrity verification service.

Tests content hash verification, HMAC validation, and caching.
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest

from src.services.context_provenance import (
    IntegrityResult,
    IntegrityStatus,
    IntegrityVerificationService,
    configure_integrity_service,
    get_integrity_service,
    reset_integrity_service,
)


class TestIntegrityVerificationService:
    """Test IntegrityVerificationService class."""

    def test_initialization(self):
        """Test service initialization."""
        service = IntegrityVerificationService(hmac_secret_key="test-secret")
        assert service._cache_ttl == 300
        assert len(service._verification_cache) == 0

    def test_initialization_custom_ttl(self):
        """Test service initialization with custom TTL."""
        service = IntegrityVerificationService(
            hmac_secret_key="test-secret",
            cache_ttl_seconds=600,
        )
        assert service._cache_ttl == 600


class TestVerify:
    """Test verify method."""

    @pytest.fixture
    def service(self):
        """Create service for tests."""
        return IntegrityVerificationService(hmac_secret_key="test-secret-key")

    def test_verify_valid_content(self, service: IntegrityVerificationService):
        """Test verification of valid content."""
        content = "def hello(): pass"

        # Compute expected hashes
        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        expected_hmac = hmac.new(
            b"test-secret-key",
            content.encode(),
            hashlib.sha256,
        ).hexdigest()

        result = service.verify(
            content=content,
            stored_hash=expected_hash,
            stored_hmac=expected_hmac,
        )

        assert result.status == IntegrityStatus.VERIFIED
        assert result.content_hash_match is True
        assert result.hmac_valid is True
        assert result.verified_at is not None

    def test_verify_hash_mismatch(self, service: IntegrityVerificationService):
        """Test verification with hash mismatch."""
        content = "def hello(): pass"

        result = service.verify(
            content=content,
            stored_hash="invalid_hash",
            stored_hmac="invalid_hmac",
        )

        assert result.status == IntegrityStatus.FAILED
        assert result.content_hash_match is False
        assert "hash mismatch" in result.details.lower()

    def test_verify_hmac_invalid(self, service: IntegrityVerificationService):
        """Test verification with invalid HMAC but valid hash."""
        content = "def hello(): pass"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()

        result = service.verify(
            content=content,
            stored_hash=expected_hash,
            stored_hmac="invalid_hmac",
        )

        assert result.status == IntegrityStatus.HMAC_INVALID
        assert result.content_hash_match is True
        assert result.hmac_valid is False

    def test_verify_missing_hashes(self, service: IntegrityVerificationService):
        """Test verification with missing hashes."""
        result = service.verify(
            content="def hello(): pass",
            stored_hash="",
            stored_hmac="",
        )

        assert result.status == IntegrityStatus.HASH_MISSING
        assert result.content_hash_match is False
        assert result.hmac_valid is False

    def test_verify_with_caching(self, service: IntegrityVerificationService):
        """Test that verification results are cached."""
        content = "def hello(): pass"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        expected_hmac = hmac.new(
            b"test-secret-key",
            content.encode(),
            hashlib.sha256,
        ).hexdigest()

        # First call - cache miss
        result1 = service.verify(
            content=content,
            stored_hash=expected_hash,
            stored_hmac=expected_hmac,
            chunk_id="test-chunk-001",
        )

        # Second call - cache hit
        result2 = service.verify(
            content=content,
            stored_hash=expected_hash,
            stored_hmac=expected_hmac,
            chunk_id="test-chunk-001",
        )

        stats = service.get_cache_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1

    def test_verify_cache_expiration(self, service: IntegrityVerificationService):
        """Test cache expiration."""
        content = "def hello(): pass"
        expected_hash = hashlib.sha256(content.encode()).hexdigest()
        expected_hmac = hmac.new(
            b"test-secret-key",
            content.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Create expired cache entry
        result = service.verify(
            content=content,
            stored_hash=expected_hash,
            stored_hmac=expected_hmac,
            chunk_id="test-chunk-001",
        )

        # Manually expire the cache entry
        expired_time = datetime.now(timezone.utc) - timedelta(seconds=400)
        service._verification_cache["test-chunk-001"] = (result, expired_time)

        # Next call should be a cache miss
        service.verify(
            content=content,
            stored_hash=expected_hash,
            stored_hmac=expected_hmac,
            chunk_id="test-chunk-001",
        )

        stats = service.get_cache_stats()
        # 2 misses: first call + expired call
        assert stats["cache_misses"] == 2


class TestBatchVerify:
    """Test batch_verify method."""

    @pytest.fixture
    def service(self):
        """Create service for tests."""
        return IntegrityVerificationService(hmac_secret_key="test-secret-key")

    def test_batch_verify_multiple_chunks(self, service: IntegrityVerificationService):
        """Test batch verification of multiple chunks."""
        chunks = []
        for i in range(3):
            content = f"def func_{i}(): pass"
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            content_hmac = hmac.new(
                b"test-secret-key",
                content.encode(),
                hashlib.sha256,
            ).hexdigest()

            chunks.append(
                {
                    "id": f"chunk-{i}",
                    "content": content,
                    "integrity": {
                        "content_hash": content_hash,
                        "content_hmac": content_hmac,
                    },
                }
            )

        results = service.batch_verify(chunks)

        assert len(results) == 3
        for chunk_id, result in results.items():
            assert result.status == IntegrityStatus.VERIFIED

    def test_batch_verify_mixed_results(self, service: IntegrityVerificationService):
        """Test batch verification with mixed results."""
        content = "def valid(): pass"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        content_hmac = hmac.new(
            b"test-secret-key",
            content.encode(),
            hashlib.sha256,
        ).hexdigest()

        chunks = [
            {
                "chunk_id": "valid-chunk",
                "content": content,
                "integrity": {
                    "content_hash": content_hash,
                    "content_hmac": content_hmac,
                },
            },
            {
                "id": "invalid-chunk",
                "content": "tampered content",
                "integrity": {
                    "content_hash": content_hash,
                    "content_hmac": content_hmac,
                },
            },
        ]

        results = service.batch_verify(chunks)

        assert results["valid-chunk"].status == IntegrityStatus.VERIFIED
        assert results["invalid-chunk"].status == IntegrityStatus.FAILED


class TestVerifyChunkBoundary:
    """Test verify_chunk_boundary method."""

    @pytest.fixture
    def service(self):
        """Create service for tests."""
        return IntegrityVerificationService(hmac_secret_key="test-secret")

    def test_verify_boundary_valid(self, service: IntegrityVerificationService):
        """Test boundary verification with valid hash."""
        content = "a" * 200  # More than 100 chars

        # Compute boundary hash
        first_chars = content[:100]
        last_chars = content[-100:]
        boundary_data = f"{first_chars}|{last_chars}|{len(content)}"
        stored_hash = hashlib.sha256(boundary_data.encode()).hexdigest()[:32]

        assert service.verify_chunk_boundary(content, stored_hash) is True

    def test_verify_boundary_invalid(self, service: IntegrityVerificationService):
        """Test boundary verification with invalid hash."""
        content = "a" * 200
        assert service.verify_chunk_boundary(content, "invalid_hash") is False

    def test_verify_boundary_missing(self, service: IntegrityVerificationService):
        """Test boundary verification with missing hash."""
        assert service.verify_chunk_boundary("content", "") is False


class TestCacheManagement:
    """Test cache management methods."""

    @pytest.fixture
    def service(self):
        """Create service for tests."""
        return IntegrityVerificationService(hmac_secret_key="test-secret")

    def test_invalidate_cache(self, service: IntegrityVerificationService):
        """Test invalidating a cache entry."""
        # Add entry to cache
        result = IntegrityResult(
            status=IntegrityStatus.VERIFIED,
            content_hash_match=True,
            hmac_valid=True,
            verified_at=datetime.now(timezone.utc),
        )
        service._verification_cache["chunk-001"] = (result, datetime.now(timezone.utc))

        assert service.invalidate_cache("chunk-001") is True
        assert "chunk-001" not in service._verification_cache

    def test_invalidate_cache_not_found(self, service: IntegrityVerificationService):
        """Test invalidating non-existent cache entry."""
        assert service.invalidate_cache("non-existent") is False

    def test_clear_cache(self, service: IntegrityVerificationService):
        """Test clearing all cache entries."""
        # Add entries to cache
        result = IntegrityResult(
            status=IntegrityStatus.VERIFIED,
            content_hash_match=True,
            hmac_valid=True,
            verified_at=datetime.now(timezone.utc),
        )
        now = datetime.now(timezone.utc)
        for i in range(5):
            service._verification_cache[f"chunk-{i}"] = (result, now)

        cleared = service.clear_cache()
        assert cleared == 5
        assert len(service._verification_cache) == 0


class TestCacheStats:
    """Test cache statistics."""

    @pytest.fixture
    def service(self):
        """Create service for tests."""
        return IntegrityVerificationService(hmac_secret_key="test-secret")

    def test_get_cache_stats(self, service: IntegrityVerificationService):
        """Test getting cache statistics."""
        stats = service.get_cache_stats()

        assert "cache_size" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "hit_rate" in stats
        assert "verifications_passed" in stats
        assert "verifications_failed" in stats

    def test_reset_stats(self, service: IntegrityVerificationService):
        """Test resetting statistics."""
        service._cache_hits = 10
        service._cache_misses = 5
        service._verifications_passed = 8
        service._verifications_failed = 2

        service.reset_stats()

        assert service._cache_hits == 0
        assert service._cache_misses == 0
        assert service._verifications_passed == 0
        assert service._verifications_failed == 0


class TestSingletonFunctions:
    """Test singleton management functions."""

    def test_get_integrity_service(self):
        """Test get_integrity_service returns singleton."""
        service1 = get_integrity_service()
        service2 = get_integrity_service()
        assert service1 is service2

    def test_reset_integrity_service(self):
        """Test reset_integrity_service creates new instance."""
        service1 = get_integrity_service()
        reset_integrity_service()
        service2 = get_integrity_service()
        assert service1 is not service2

    def test_configure_integrity_service(self):
        """Test configure_integrity_service."""
        service = configure_integrity_service(
            hmac_secret_key="custom-key",
            cache_ttl_seconds=600,
        )
        assert service._cache_ttl == 600
