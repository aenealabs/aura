"""
Project Aura - Integrity Verification Service

Verifies integrity of retrieved content at retrieval time.
Ensures content has not been modified since indexing.

Security Rationale:
- Hash verification detects content tampering
- HMAC validation prevents signature forgery
- Caching reduces verification overhead
- Batch verification improves performance

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from .contracts import IntegrityResult, IntegrityStatus

logger = logging.getLogger(__name__)


class IntegrityVerificationService:
    """
    Verifies integrity of retrieved content.

    Operates at retrieval time to ensure content
    has not been modified since indexing.

    Usage:
        service = IntegrityVerificationService(hmac_secret_key="secret")
        result = service.verify(
            content="def main(): pass",
            stored_hash="abc123...",
            stored_hmac="def456...",
        )
        if result.verified:
            # Safe to use content
            pass
    """

    def __init__(
        self,
        hmac_secret_key: str,
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize integrity verification service.

        Args:
            hmac_secret_key: Secret key for HMAC validation
            cache_ttl_seconds: TTL for verification cache
        """
        self._hmac_key = hmac_secret_key.encode()
        self._cache_ttl = cache_ttl_seconds
        self._verification_cache: dict[str, tuple[IntegrityResult, datetime]] = {}

        # Metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._verifications_passed = 0
        self._verifications_failed = 0

        logger.debug(
            f"IntegrityVerificationService initialized "
            f"(cache_ttl={cache_ttl_seconds}s)"
        )

    def verify(
        self,
        content: str,
        stored_hash: str,
        stored_hmac: str,
        chunk_id: Optional[str] = None,
    ) -> IntegrityResult:
        """
        Verify content integrity against stored hashes.

        Args:
            content: Retrieved content to verify
            stored_hash: SHA-256 hash from index time
            stored_hmac: HMAC signature from index time
            chunk_id: Optional chunk ID for caching

        Returns:
            IntegrityResult with verification status
        """
        now = datetime.now(timezone.utc)

        # Check cache
        if chunk_id and chunk_id in self._verification_cache:
            cached_result, cached_at = self._verification_cache[chunk_id]
            age = (now - cached_at).total_seconds()
            if age < self._cache_ttl:
                self._cache_hits += 1
                return cached_result
            else:
                # Cache expired, remove it
                del self._verification_cache[chunk_id]

        self._cache_misses += 1

        # Handle missing hashes
        if not stored_hash or not stored_hmac:
            result = IntegrityResult(
                status=IntegrityStatus.HASH_MISSING,
                content_hash_match=False,
                hmac_valid=False,
                verified_at=now,
                details="No integrity hashes stored for this content",
            )
            self._verifications_failed += 1
            return result

        # Verify content hash
        computed_hash = hashlib.sha256(content.encode()).hexdigest()
        hash_match = computed_hash == stored_hash

        # Verify HMAC
        computed_hmac = hmac.new(
            self._hmac_key,
            content.encode(),
            hashlib.sha256,
        ).hexdigest()
        hmac_valid = hmac.compare_digest(computed_hmac, stored_hmac)

        # Determine status
        if hash_match and hmac_valid:
            status = IntegrityStatus.VERIFIED
            details = None
            self._verifications_passed += 1
        elif not hash_match:
            status = IntegrityStatus.FAILED
            details = (
                f"Content hash mismatch: expected {stored_hash[:16]}..., "
                f"got {computed_hash[:16]}..."
            )
            self._verifications_failed += 1
        else:
            status = IntegrityStatus.HMAC_INVALID
            details = "HMAC signature validation failed - possible tampering"
            self._verifications_failed += 1

        result = IntegrityResult(
            status=status,
            content_hash_match=hash_match,
            hmac_valid=hmac_valid,
            verified_at=now,
            details=details,
        )

        # Cache result
        if chunk_id:
            self._verification_cache[chunk_id] = (result, now)

        if status != IntegrityStatus.VERIFIED:
            logger.warning(
                f"Integrity verification failed for chunk {chunk_id}: {status.value}"
            )

        return result

    def batch_verify(
        self,
        chunks: list[dict[str, Any]],
    ) -> dict[str, IntegrityResult]:
        """
        Verify integrity of multiple chunks.

        Args:
            chunks: List of chunk dicts with content, hash, hmac, id

        Returns:
            Dict mapping chunk_id to IntegrityResult
        """
        results = {}
        for chunk in chunks:
            chunk_id = chunk.get("id", chunk.get("chunk_id", ""))
            integrity_data = chunk.get("integrity", {})

            result = self.verify(
                content=chunk.get("content", ""),
                stored_hash=integrity_data.get("content_hash", ""),
                stored_hmac=integrity_data.get("content_hmac", ""),
                chunk_id=chunk_id,
            )
            results[chunk_id] = result

        # Log batch summary
        passed = sum(1 for r in results.values() if r.verified)
        failed = len(results) - passed
        logger.info(
            f"Batch verification complete: {passed} passed, {failed} failed "
            f"(total: {len(results)})"
        )

        return results

    def verify_chunk_boundary(
        self,
        content: str,
        stored_boundary_hash: str,
    ) -> bool:
        """
        Verify chunk boundary hash.

        Detects if chunk boundaries have been manipulated.

        Args:
            content: Content to verify
            stored_boundary_hash: Hash from index time

        Returns:
            True if boundary hash matches
        """
        if not stored_boundary_hash:
            return False

        # Compute current boundary hash
        first_chars = content[:100] if len(content) >= 100 else content
        last_chars = content[-100:] if len(content) >= 100 else content
        boundary_data = f"{first_chars}|{last_chars}|{len(content)}"
        computed_hash = hashlib.sha256(boundary_data.encode()).hexdigest()[:32]

        return computed_hash == stored_boundary_hash

    def invalidate_cache(self, chunk_id: str) -> bool:
        """
        Invalidate cached verification result.

        Args:
            chunk_id: Chunk ID to invalidate

        Returns:
            True if entry was removed
        """
        if chunk_id in self._verification_cache:
            del self._verification_cache[chunk_id]
            return True
        return False

    def clear_cache(self) -> int:
        """
        Clear all cached verification results.

        Returns:
            Number of entries cleared
        """
        count = len(self._verification_cache)
        self._verification_cache.clear()
        logger.info(f"Cleared {count} entries from verification cache")
        return count

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0.0

        return {
            "cache_size": len(self._verification_cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
            "verifications_passed": self._verifications_passed,
            "verifications_failed": self._verifications_failed,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._cache_hits = 0
        self._cache_misses = 0
        self._verifications_passed = 0
        self._verifications_failed = 0


# =============================================================================
# Module-Level Functions
# =============================================================================


_integrity_service: Optional[IntegrityVerificationService] = None


def get_integrity_service() -> IntegrityVerificationService:
    """Get the global integrity verification service instance."""
    global _integrity_service
    if _integrity_service is None:
        hmac_key = os.environ.get("AURA_INTEGRITY_HMAC_KEY")
        if not hmac_key:
            raise RuntimeError(
                "AURA_INTEGRITY_HMAC_KEY environment variable is required. "
                "Set it via SSM Parameter Store or environment configuration."
            )
        _integrity_service = IntegrityVerificationService(hmac_secret_key=hmac_key)
    return _integrity_service


def configure_integrity_service(
    hmac_secret_key: str,
    cache_ttl_seconds: int = 300,
) -> IntegrityVerificationService:
    """Configure the global integrity verification service."""
    global _integrity_service
    _integrity_service = IntegrityVerificationService(
        hmac_secret_key=hmac_secret_key,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    return _integrity_service


def reset_integrity_service() -> None:
    """Reset the global integrity service (for testing)."""
    global _integrity_service
    _integrity_service = None
