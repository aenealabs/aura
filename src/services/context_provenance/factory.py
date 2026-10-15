"""
Project Aura - Context Provenance Wiring Factory

Builds the index-time signer and the retrieval-time verifier from
configuration so ingestion and retrieval share one HMAC key (ADR-067).

Environment variables:
    AURA_CONTEXT_PROVENANCE_ENABLED   "true"/"1" enables recording at ingestion
                                      and verification at retrieval. Unset or
                                      false: factories return None and existing
                                      behavior is unchanged.
    AURA_INTEGRITY_HMAC_KEY           HMAC key (populated from SSM Parameter
    AURA_PROVENANCE_HMAC_KEY          Store / Secrets Manager). Signing and
                                      verification must use the same key; if
                                      both are set they must be equal.
    AURA_CONTEXT_PROVENANCE_STRICT    Fail closed on unverifiable items
                                      (default "true").
    AURA_PROVENANCE_REPOSITORY_SCOPE  Optional ``metadata.repository`` scope
                                      for evidence lookups.
    AURA_PROVENANCE_INTERNAL_ORGS     Optional comma-separated internal org ids
                                      for trust scoring.

Author: Project Aura Team
Created: 2026-10-14
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .evidence_loader import EvidenceStore, OpenSearchEvidenceLoader
from .integrity_service import IntegrityVerificationService
from .provenance_service import ContentProvenanceService
from .retrieval_verifier import RetrievalProvenanceVerifier
from .trust_scoring import TrustScoringEngine

logger = logging.getLogger(__name__)

ENABLED_ENV = "AURA_CONTEXT_PROVENANCE_ENABLED"
STRICT_ENV = "AURA_CONTEXT_PROVENANCE_STRICT"
REPOSITORY_SCOPE_ENV = "AURA_PROVENANCE_REPOSITORY_SCOPE"
INTERNAL_ORGS_ENV = "AURA_PROVENANCE_INTERNAL_ORGS"
INTEGRITY_KEY_ENV = "AURA_INTEGRITY_HMAC_KEY"
PROVENANCE_KEY_ENV = "AURA_PROVENANCE_HMAC_KEY"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in _TRUE_VALUES


def provenance_enabled() -> bool:
    """Return True when ADR-067 provenance recording/verification is enabled."""
    return _env_flag(ENABLED_ENV, default=False)


def resolve_hmac_key() -> str:
    """Resolve the single HMAC key shared by signer and verifier.

    Raises:
        RuntimeError: When no key is configured, or when the integrity and
            provenance keys are both set but differ (every item would fail
            HMAC validation and be excluded).
    """
    integrity_key = os.environ.get(INTEGRITY_KEY_ENV) or ""
    provenance_key = os.environ.get(PROVENANCE_KEY_ENV) or ""
    if integrity_key and provenance_key and integrity_key != provenance_key:
        raise RuntimeError(
            f"{INTEGRITY_KEY_ENV} and {PROVENANCE_KEY_ENV} differ; index-time "
            "signing and retrieval-time verification must share one key."
        )
    key = integrity_key or provenance_key
    if not key:
        raise RuntimeError(
            f"{INTEGRITY_KEY_ENV} (or {PROVENANCE_KEY_ENV}) is required when "
            f"{ENABLED_ENV} is set. Set it via SSM Parameter Store or "
            "environment configuration."
        )
    return key


def create_provenance_service_from_env() -> Optional[ContentProvenanceService]:
    """Build the index-time signer for GitIngestionService, or None if disabled."""
    if not provenance_enabled():
        return None
    return ContentProvenanceService(hmac_secret_key=resolve_hmac_key())


def create_provenance_verifier(
    evidence_store: EvidenceStore,
    hmac_key: str,
    *,
    strict: bool = True,
    repository: Optional[str] = None,
    trust_engine: Optional[TrustScoringEngine] = None,
    quarantine_manager: Optional[Any] = None,
    audit_logger: Optional[Any] = None,
) -> RetrievalProvenanceVerifier:
    """Build a retrieval-time verifier reading evidence from ``evidence_store``.

    Args:
        evidence_store: Store exposing ``find_by_file_path``
            (OpenSearchVectorService)
        hmac_key: Key used at index time to sign content
        strict: Fail closed on unverifiable items
        repository: Optional ``metadata.repository`` lookup scope
        trust_engine: Trust engine (default: no internal/partner orgs)
        quarantine_manager: Optional QuarantineManager
        audit_logger: Optional ProvenanceAuditLogger
    """
    return RetrievalProvenanceVerifier(
        evidence_loader=OpenSearchEvidenceLoader(evidence_store, repository),
        integrity_service=IntegrityVerificationService(hmac_secret_key=hmac_key),
        trust_engine=trust_engine or TrustScoringEngine(),
        quarantine_manager=quarantine_manager,
        audit_logger=audit_logger,
        strict=strict,
    )


def create_provenance_verifier_from_env(
    evidence_store: EvidenceStore,
    quarantine_manager: Optional[Any] = None,
    audit_logger: Optional[Any] = None,
) -> Optional[RetrievalProvenanceVerifier]:
    """Build the retrieval-time verifier from environment, or None if disabled.

    Raises:
        RuntimeError: When enabled but the HMAC key is missing/inconsistent.
    """
    if not provenance_enabled():
        return None
    internal_orgs = [
        org.strip()
        for org in os.environ.get(INTERNAL_ORGS_ENV, "").split(",")
        if org.strip()
    ]
    strict = _env_flag(STRICT_ENV, default=True)
    verifier = create_provenance_verifier(
        evidence_store,
        resolve_hmac_key(),
        strict=strict,
        repository=os.environ.get(REPOSITORY_SCOPE_ENV) or None,
        trust_engine=TrustScoringEngine(internal_org_ids=internal_orgs),
        quarantine_manager=quarantine_manager,
        audit_logger=audit_logger,
    )
    logger.info(f"ADR-067 retrieval provenance verification enabled (strict={strict})")
    return verifier
