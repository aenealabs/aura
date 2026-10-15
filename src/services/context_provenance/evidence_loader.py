"""
Project Aura - Index-Time Evidence Recording and Retrieval-Time Loading

Closes the ADR-067 loop between ingestion and retrieval:

- ``build_evidence_fields`` runs at index time. It collects provenance and
  computes the SHA-256 + HMAC integrity record (via ContentProvenanceService)
  over the exact text stored in the OpenSearch document, and returns the
  ``provenance`` / ``integrity`` / ``status`` fields described in ADR-067
  ("OpenSearch Integrity Fields").
- ``OpenSearchEvidenceLoader`` runs at retrieval time. It is the async
  ``path -> RetrievalEvidence | None`` callable consumed by
  RetrievalProvenanceVerifier, reading the stored text and evidence for a
  file in a single document lookup.

Storage rationale: the OpenSearch document is the only store that holds both
the content that is served and its evidence, so one lookup yields everything
the verifier needs. Neptune vertices hold per-entity metadata but not file
content, so verifying from Neptune would still require a second read.

Author: Project Aura Team
Created: 2026-10-14
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Protocol

from .contracts import ProvenanceRecord
from .provenance_service import ContentProvenanceService
from .retrieval_verifier import RetrievalEvidence

logger = logging.getLogger(__name__)

STATUS_ACTIVE = "ACTIVE"


class EvidenceStore(Protocol):
    """Document store that returns indexed text plus ADR-067 evidence."""

    def find_by_file_path(
        self,
        file_path: str,
        repository: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return documents (id, text, metadata, provenance, integrity)."""
        ...


def build_evidence_fields(
    provenance_service: ContentProvenanceService,
    file_path: str,
    stored_text: str,
    git_info: dict[str, Any],
    embedding: Optional[list[float]] = None,
) -> dict[str, Any]:
    """Build the ADR-067 evidence fields for one indexed document.

    The integrity record is computed over ``stored_text`` -- the exact text
    persisted in the document -- so retrieval-time verification checks the
    content that will actually be served.

    Args:
        provenance_service: Index-time signer (holds the HMAC key)
        file_path: Repository-relative path (for logging)
        stored_text: Text persisted in the document
        git_info: Git metadata accepted by ``collect_provenance``
        embedding: Optional vector; when given its fingerprint is recorded

    Returns:
        Dict with ``provenance``, ``integrity`` and ``status`` keys
    """
    provenance, integrity = provenance_service.collect_provenance(
        file_path=file_path, content=stored_text, git_info=git_info
    )
    if embedding:
        provenance_service.set_embedding_fingerprint(integrity, embedding)
    return {
        "provenance": provenance.to_dict(),
        "integrity": integrity.to_dict(),
        "status": STATUS_ACTIVE,
    }


class OpenSearchEvidenceLoader:
    """Async evidence loader backed by the OpenSearch code-embeddings index.

    Returns None (no evidence) when no document exists for the path, when the
    document carries no provenance/integrity fields (indexed before evidence
    recording was enabled), or when the path is ambiguous -- several
    documents from different repositories share the same relative path and
    no ``repository`` scope was configured. Under the verifier's strict
    default all of these exclude the item. Store errors propagate so the
    verifier records them as verifier errors.

    Args:
        store: Object exposing ``find_by_file_path`` (OpenSearchVectorService)
        repository: Optional ``metadata.repository`` scope for lookups
    """

    def __init__(self, store: EvidenceStore, repository: Optional[str] = None):
        self.store = store
        self.repository = repository

    async def __call__(self, file_path: str) -> Optional[RetrievalEvidence]:
        """Load evidence for a retrieved file path."""
        documents = await asyncio.to_thread(
            self.store.find_by_file_path, file_path, self.repository, 2
        )
        if not documents:
            return None
        if len(documents) > 1:
            logger.warning(
                f"Ambiguous provenance lookup for {file_path}: "
                f"{len(documents)} documents match; configure a repository scope"
            )
            return None
        return self._to_evidence(documents[0])

    @staticmethod
    def _to_evidence(document: dict[str, Any]) -> Optional[RetrievalEvidence]:
        provenance = document.get("provenance")
        integrity = document.get("integrity")
        if not isinstance(provenance, dict) or not isinstance(integrity, dict):
            return None
        return RetrievalEvidence(
            content=document.get("text", ""),
            stored_hash=integrity.get("content_hash", ""),
            stored_hmac=integrity.get("content_hmac", ""),
            provenance=ProvenanceRecord.from_dict(provenance),
            chunk_id=document.get("id"),
        )
