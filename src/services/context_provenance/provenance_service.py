"""
Project Aura - Content Provenance Service

Collects and stores provenance data for indexed content.
Operates at index time to capture origin information before
content enters Neptune and OpenSearch.

Security Rationale:
- Provenance tracking enables audit trails
- Integrity hashes detect tampering
- HMAC signatures prevent forgery
- Embedding fingerprints detect vector manipulation

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from .contracts import IntegrityRecord, ProvenanceRecord

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ContentProvenanceService:
    """
    Collects and stores provenance data for indexed content.

    Operates at index time to capture origin information
    before content enters Neptune and OpenSearch.

    Usage:
        service = ContentProvenanceService(hmac_secret_key="secret")
        provenance, integrity = service.collect_provenance(
            file_path="src/main.py",
            content="def main(): pass",
            git_info={"commit_sha": "abc123", ...},
        )
    """

    def __init__(
        self,
        hmac_secret_key: str,
        neptune_client: Optional[Any] = None,
        opensearch_client: Optional[Any] = None,
    ):
        """
        Initialize provenance service.

        Args:
            hmac_secret_key: Secret key for HMAC signatures (from Secrets Manager)
            neptune_client: Optional Neptune graph database client
            opensearch_client: Optional OpenSearch client
        """
        self._hmac_key = hmac_secret_key.encode()
        self.neptune = neptune_client
        self.opensearch = opensearch_client

        logger.debug("ContentProvenanceService initialized")

    def collect_provenance(
        self,
        file_path: str,
        content: str,
        git_info: dict[str, Any],
    ) -> tuple[ProvenanceRecord, IntegrityRecord]:
        """
        Collect provenance and generate integrity records for content.

        Args:
            file_path: Path to source file
            content: File content being indexed
            git_info: Git metadata (commit, author, timestamp, etc.)

        Returns:
            Tuple of (ProvenanceRecord, IntegrityRecord)
        """
        # Build provenance record
        timestamp = git_info.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        provenance = ProvenanceRecord(
            repository_id=git_info.get("repository_id", "unknown"),
            commit_sha=git_info.get("commit_sha", ""),
            author_id=git_info.get("author_id", ""),
            author_email=git_info.get("author_email", ""),
            timestamp=timestamp,
            branch=git_info.get("branch", "main"),
            signature=git_info.get("gpg_signature"),
        )

        # Generate integrity hashes
        content_hash = self._compute_sha256(content)
        content_hmac = self._compute_hmac(content)
        chunk_boundary_hash = self._compute_chunk_boundary_hash(content)

        integrity = IntegrityRecord(
            content_hash_sha256=content_hash,
            content_hmac=content_hmac,
            chunk_boundary_hash=chunk_boundary_hash,
            embedding_fingerprint="",  # Set after embedding generation
            indexed_at=datetime.now(timezone.utc),
        )

        logger.info(
            f"Collected provenance for {file_path}: "
            f"repo={provenance.repository_id}, "
            f"commit={provenance.commit_sha[:8] if provenance.commit_sha else 'none'}"
        )

        return provenance, integrity

    def set_embedding_fingerprint(
        self,
        integrity: IntegrityRecord,
        embedding: list[float],
    ) -> IntegrityRecord:
        """
        Add embedding fingerprint to integrity record.

        The fingerprint is a hash of the first and last 16 dimensions
        plus the vector norm, enabling detection of embedding tampering.

        Args:
            integrity: IntegrityRecord to update
            embedding: Embedding vector

        Returns:
            Updated IntegrityRecord with fingerprint
        """
        if not embedding:
            logger.warning("Empty embedding provided for fingerprint")
            return integrity

        # Compute fingerprint from embedding characteristics
        fingerprint_data = (
            str(embedding[:16])
            + str(embedding[-16:])
            + str(sum(x * x for x in embedding) ** 0.5)
        )
        integrity.embedding_fingerprint = self._compute_sha256(fingerprint_data)

        logger.debug(
            f"Set embedding fingerprint: {integrity.embedding_fingerprint[:16]}..."
        )

        return integrity

    def verify_embedding_fingerprint(
        self,
        embedding: list[float],
        stored_fingerprint: str,
    ) -> bool:
        """
        Verify embedding against stored fingerprint.

        Args:
            embedding: Current embedding vector
            stored_fingerprint: Fingerprint from indexing time

        Returns:
            True if fingerprint matches
        """
        if not embedding or not stored_fingerprint:
            return False

        fingerprint_data = (
            str(embedding[:16])
            + str(embedding[-16:])
            + str(sum(x * x for x in embedding) ** 0.5)
        )
        computed = self._compute_sha256(fingerprint_data)

        return computed == stored_fingerprint

    async def store_provenance_neptune(
        self,
        entity_id: str,
        provenance: ProvenanceRecord,
        integrity: IntegrityRecord,
    ) -> None:
        """
        Store provenance and integrity data in Neptune graph.

        Args:
            entity_id: Neptune vertex entity_id
            provenance: Provenance record to store
            integrity: Integrity record to store
        """
        if not self.neptune:
            logger.warning("Neptune client not configured, skipping storage")
            return

        properties = {
            "provenance_repository_id": provenance.repository_id,
            "provenance_commit_sha": provenance.commit_sha,
            "provenance_author_id": provenance.author_id,
            "provenance_author_email": provenance.author_email,
            "provenance_timestamp": provenance.timestamp.isoformat(),
            "provenance_branch": provenance.branch,
            "provenance_signature": provenance.signature or "",
            "content_hash_sha256": integrity.content_hash_sha256,
            "content_hmac": integrity.content_hmac,
            "chunk_boundary_hash": integrity.chunk_boundary_hash,
            "embedding_fingerprint": integrity.embedding_fingerprint,
            "indexed_at": integrity.indexed_at.isoformat(),
            "quarantine_status": "ACTIVE",
        }

        # Build Gremlin query to update vertex properties
        property_updates = ", ".join(
            f".property('{k}', '{v}')" for k, v in properties.items()
        )

        query = f"g.V().has('entity_id', '{entity_id}'){property_updates}"

        try:
            self.neptune.client.submit(query).all().result()
            logger.debug(f"Stored provenance in Neptune for entity {entity_id}")
        except Exception as e:
            logger.error(f"Failed to store provenance in Neptune: {e}")
            raise

    async def store_provenance_opensearch(
        self,
        doc_id: str,
        provenance: ProvenanceRecord,
        integrity: IntegrityRecord,
    ) -> None:
        """
        Store provenance and integrity data in OpenSearch.

        Args:
            doc_id: OpenSearch document ID
            provenance: Provenance record to store
            integrity: Integrity record to store
        """
        if not self.opensearch:
            logger.warning("OpenSearch client not configured, skipping storage")
            return

        update_body = {
            "doc": {
                "provenance": provenance.to_dict(),
                "integrity": integrity.to_dict(),
                "trust": {
                    "score": 0.0,  # Will be computed by TrustScoringEngine
                    "score_components": {},
                    "updated_at": None,
                },
                "status": "ACTIVE",
            }
        }

        try:
            self.opensearch.update(
                index="aura-code-embeddings",
                id=doc_id,
                body=update_body,
            )
            logger.debug(f"Stored provenance in OpenSearch for doc {doc_id}")
        except Exception as e:
            logger.error(f"Failed to store provenance in OpenSearch: {e}")
            raise

    def _compute_sha256(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _compute_hmac(self, content: str) -> str:
        """Compute HMAC-SHA256 signature of content."""
        return hmac.new(
            self._hmac_key,
            content.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _compute_chunk_boundary_hash(self, content: str) -> str:
        """
        Compute hash of chunk boundaries.

        This detects if chunk boundaries have been maliciously
        shifted to hide or expose specific content.
        """
        # Hash first 100 and last 100 chars plus total length
        first_chars = content[:100] if len(content) >= 100 else content
        last_chars = content[-100:] if len(content) >= 100 else content
        boundary_data = f"{first_chars}|{last_chars}|{len(content)}"
        return hashlib.sha256(boundary_data.encode()).hexdigest()[:32]

    def compute_content_hash(self, content: str) -> str:
        """
        Compute content hash for verification.

        Public method for external verification.

        Args:
            content: Content to hash

        Returns:
            SHA-256 hash as hex string
        """
        return self._compute_sha256(content)

    def compute_content_hmac(self, content: str) -> str:
        """
        Compute HMAC signature for verification.

        Public method for external verification.

        Args:
            content: Content to sign

        Returns:
            HMAC-SHA256 signature as hex string
        """
        return self._compute_hmac(content)


# =============================================================================
# Module-Level Functions
# =============================================================================


_provenance_service: Optional[ContentProvenanceService] = None


def get_provenance_service() -> ContentProvenanceService:
    """Get the global provenance service instance."""
    global _provenance_service
    if _provenance_service is None:
        hmac_key = os.environ.get("AURA_PROVENANCE_HMAC_KEY")
        if not hmac_key:
            raise RuntimeError(
                "AURA_PROVENANCE_HMAC_KEY environment variable is required. "
                "Set it via SSM Parameter Store or environment configuration."
            )
        _provenance_service = ContentProvenanceService(
            hmac_secret_key=hmac_key
        )
    return _provenance_service


def configure_provenance_service(
    hmac_secret_key: str,
    neptune_client: Optional[Any] = None,
    opensearch_client: Optional[Any] = None,
) -> ContentProvenanceService:
    """Configure the global provenance service."""
    global _provenance_service
    _provenance_service = ContentProvenanceService(
        hmac_secret_key=hmac_secret_key,
        neptune_client=neptune_client,
        opensearch_client=opensearch_client,
    )
    return _provenance_service


def reset_provenance_service() -> None:
    """Reset the global provenance service (for testing)."""
    global _provenance_service
    _provenance_service = None
