"""Tests for IntegrityVerificationService."""

import hashlib
import hmac as hmac_lib

import pytest

from src.services.context_provenance.contracts import IntegrityStatus
from src.services.context_provenance.integrity_service import (
    IntegrityVerificationService,
    configure_integrity_service,
    get_integrity_service,
    reset_integrity_service,
)


@pytest.fixture
def hmac_key():
    """Test HMAC key."""
    return "test-secret-key-for-verification"


@pytest.fixture
def integrity_service(hmac_key):
    """Create an integrity service for testing."""
    return IntegrityVerificationService(
        hmac_secret_key=hmac_key,
        cache_ttl_seconds=60,
    )


@pytest.fixture(autouse=True)
def reset_service():
    """Reset global service after each test."""
    yield
    reset_integrity_service()


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


def compute_hmac(content: str, key: str) -> str:
    """Compute HMAC-SHA256 of content."""
    return hmac_lib.new(key.encode(), content.encode(), hashlib.sha256).hexdigest()


class TestIntegrityVerificationService:
    """Tests for IntegrityVerificationService."""

    def test_verify_valid_content(self, integrity_service, hmac_key):
        """Test verifying content with valid hashes."""
        content = "def main(): pass"
        stored_hash = compute_hash(content)
        stored_hmac = compute_hmac(content, hmac_key)

        result = integrity_service.verify(
            content=content,
            stored_hash=stored_hash,
            stored_hmac=stored_hmac,
        )

        assert result.status == IntegrityStatus.VERIFIED
        assert result.content_hash_match is True
        assert result.hmac_valid is True
        assert result.verified is True

    def test_verify_modified_content(self, integrity_service, hmac_key):
        """Test that modified content is detected."""
        original = "def main(): pass"
        modified = "def main(): return True  # backdoor"

        stored_hash = compute_hash(original)
        stored_hmac = compute_hmac(original, hmac_key)

        result = integrity_service.verify(
            content=modified,
            stored_hash=stored_hash,
            stored_hmac=stored_hmac,
        )

        assert result.status == IntegrityStatus.FAILED
        assert result.content_hash_match is False
        assert result.verified is False
        assert "mismatch" in result.details.lower()

    def test_verify_invalid_hmac(self, integrity_service, hmac_key):
        """Test that invalid HMAC is detected."""
        content = "def main(): pass"
        stored_hash = compute_hash(content)
        forged_hmac = "0" * 64  # Forged HMAC

        result = integrity_service.verify(
            content=content,
            stored_hash=stored_hash,
            stored_hmac=forged_hmac,
        )

        assert result.status == IntegrityStatus.HMAC_INVALID
        assert result.content_hash_match is True  # Hash is correct
        assert result.hmac_valid is False  # But HMAC is not
        assert result.verified is False

    def test_verify_missing_hashes(self, integrity_service):
        """Test handling missing stored hashes."""
        content = "def main(): pass"

        result = integrity_service.verify(
            content=content,
            stored_hash="",
            stored_hmac="",
        )

        assert result.status == IntegrityStatus.HASH_MISSING
        assert result.verified is False

    def test_verify_caching(self, integrity_service, hmac_key):
        """Test verification result caching."""
        content = "def main(): pass"
        stored_hash = compute_hash(content)
        stored_hmac = compute_hmac(content, hmac_key)
        chunk_id = "test-chunk-123"

        # First call - cache miss
        result1 = integrity_service.verify(
            content=content,
            stored_hash=stored_hash,
            stored_hmac=stored_hmac,
            chunk_id=chunk_id,
        )

        stats = integrity_service.get_cache_stats()
        assert stats["cache_misses"] == 1
        assert stats["cache_hits"] == 0

        # Second call - cache hit
        result2 = integrity_service.verify(
            content=content,
            stored_hash=stored_hash,
            stored_hmac=stored_hmac,
            chunk_id=chunk_id,
        )

        stats = integrity_service.get_cache_stats()
        assert stats["cache_hits"] == 1

        assert result1.status == result2.status

    def test_batch_verify(self, integrity_service, hmac_key):
        """Test batch verification of multiple chunks."""
        chunks = []
        for i in range(5):
            content = f"content {i}"
            chunks.append(
                {
                    "id": f"chunk-{i}",
                    "content": content,
                    "integrity": {
                        "content_hash": compute_hash(content),
                        "content_hmac": compute_hmac(content, hmac_key),
                    },
                }
            )

        # Add one tampered chunk
        tampered_content = "tampered content"
        original_hash = compute_hash("original content")
        original_hmac = compute_hmac("original content", hmac_key)
        chunks.append(
            {
                "id": "chunk-tampered",
                "content": tampered_content,
                "integrity": {
                    "content_hash": original_hash,
                    "content_hmac": original_hmac,
                },
            }
        )

        results = integrity_service.batch_verify(chunks)

        assert len(results) == 6
        assert all(results[f"chunk-{i}"].verified for i in range(5))
        assert not results["chunk-tampered"].verified

    def test_verify_chunk_boundary(self, integrity_service):
        """Test chunk boundary verification."""
        content = "a" * 200  # Long enough for boundary check

        # Compute boundary hash
        first_chars = content[:100]
        last_chars = content[-100:]
        boundary_data = f"{first_chars}|{last_chars}|{len(content)}"
        stored_boundary_hash = hashlib.sha256(boundary_data.encode()).hexdigest()[:32]

        # Should match
        assert integrity_service.verify_chunk_boundary(content, stored_boundary_hash)

        # Different content should not match
        different_content = "b" * 200
        assert not integrity_service.verify_chunk_boundary(
            different_content, stored_boundary_hash
        )

    def test_invalidate_cache(self, integrity_service, hmac_key):
        """Test invalidating cache entry."""
        content = "def main(): pass"
        stored_hash = compute_hash(content)
        stored_hmac = compute_hmac(content, hmac_key)
        chunk_id = "test-chunk"

        # Populate cache
        integrity_service.verify(
            content=content,
            stored_hash=stored_hash,
            stored_hmac=stored_hmac,
            chunk_id=chunk_id,
        )

        stats = integrity_service.get_cache_stats()
        assert stats["cache_size"] == 1

        # Invalidate
        removed = integrity_service.invalidate_cache(chunk_id)
        assert removed is True

        stats = integrity_service.get_cache_stats()
        assert stats["cache_size"] == 0

        # Invalidating non-existent entry
        removed = integrity_service.invalidate_cache("non-existent")
        assert removed is False

    def test_clear_cache(self, integrity_service, hmac_key):
        """Test clearing entire cache."""
        # Add multiple entries
        for i in range(5):
            content = f"content {i}"
            integrity_service.verify(
                content=content,
                stored_hash=compute_hash(content),
                stored_hmac=compute_hmac(content, hmac_key),
                chunk_id=f"chunk-{i}",
            )

        stats = integrity_service.get_cache_stats()
        assert stats["cache_size"] == 5

        count = integrity_service.clear_cache()
        assert count == 5

        stats = integrity_service.get_cache_stats()
        assert stats["cache_size"] == 0

    def test_get_cache_stats(self, integrity_service, hmac_key):
        """Test getting cache statistics."""
        content = "test"
        stored_hash = compute_hash(content)
        stored_hmac = compute_hmac(content, hmac_key)

        # Verify a few times
        for i in range(3):
            integrity_service.verify(
                content=content,
                stored_hash=stored_hash,
                stored_hmac=stored_hmac,
                chunk_id=f"chunk-{i}",
            )

        stats = integrity_service.get_cache_stats()

        assert "cache_size" in stats
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "hit_rate" in stats
        assert "verifications_passed" in stats
        assert "verifications_failed" in stats

    def test_reset_stats(self, integrity_service, hmac_key):
        """Test resetting statistics."""
        content = "test"
        integrity_service.verify(
            content=content,
            stored_hash=compute_hash(content),
            stored_hmac=compute_hmac(content, hmac_key),
        )

        stats_before = integrity_service.get_cache_stats()
        assert stats_before["verifications_passed"] > 0

        integrity_service.reset_stats()

        stats_after = integrity_service.get_cache_stats()
        assert stats_after["verifications_passed"] == 0
        assert stats_after["cache_hits"] == 0


class TestIntegrityServiceSingleton:
    """Tests for global singleton management."""

    def test_get_integrity_service(self):
        """Test getting global service instance."""
        service = get_integrity_service()
        assert service is not None

    def test_configure_integrity_service(self):
        """Test configuring global service."""
        service = configure_integrity_service(
            hmac_secret_key="custom-key",
            cache_ttl_seconds=120,
        )

        assert service is not None
        assert service._cache_ttl == 120

    def test_reset_integrity_service(self):
        """Test resetting global service."""
        service1 = get_integrity_service()
        reset_integrity_service()
        service2 = get_integrity_service()

        assert service1 is not service2
