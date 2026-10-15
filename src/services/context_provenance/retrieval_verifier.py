"""
Project Aura - Retrieval-Time Provenance Verifier

Composes the existing context provenance components into the
retrieval-time flow described in ADR-067 ("Integration with
ContextRetrievalService"):

    1. Quarantine check (QuarantineManager.is_quarantined)
    2. Integrity verification (IntegrityVerificationService.verify)
    3. Trust scoring (TrustScoringEngine.compute_trust_score)
    4. Audit logging (ProvenanceAuditLogger)

No new cryptography is introduced; hashing and HMAC validation are
delegated to IntegrityVerificationService.

The verifier fails CLOSED for an item that cannot be verified when
``strict`` is True (the default): missing evidence, evidence-loader
errors, and errors from any configured component all exclude the item.
With ``strict=False`` the item is served with ``trust_score=None`` for
infrastructure errors only (content that positively fails integrity,
is quarantined, or is untrusted is always excluded).

Author: Project Aura Team
Created: 2026-10-14
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from .contracts import IntegrityStatus, ProvenanceRecord, QuarantineReason, TrustScore
from .integrity_service import IntegrityVerificationService
from .trust_scoring import TrustScoringEngine

logger = logging.getLogger(__name__)


@dataclass
class RetrievalEvidence:
    """Index-time evidence needed to verify one retrieved item.

    Supplied by the evidence loader (typically reads the content and the
    stored integrity/provenance properties from Neptune or OpenSearch).
    """

    content: str
    stored_hash: str
    stored_hmac: str
    provenance: ProvenanceRecord
    chunk_id: Optional[str] = None


class VerificationOutcome(Enum):
    """Why an item was admitted or excluded."""

    VERIFIED = "verified"
    UNVERIFIED_ADMITTED = "unverified_admitted"  # non-strict, infra error
    QUARANTINED = "quarantined"
    INTEGRITY_FAILED = "integrity_failed"
    LOW_TRUST = "low_trust"
    NO_EVIDENCE = "no_evidence"
    VERIFIER_ERROR = "verifier_error"


@dataclass
class VerificationDecision:
    """Result of verifying a single retrieved item."""

    item_id: str
    allowed: bool
    outcome: VerificationOutcome
    trust_score: Optional[TrustScore] = None
    details: Optional[str] = None


EvidenceLoader = Callable[[str], Awaitable[Optional[RetrievalEvidence]]]


class RetrievalProvenanceVerifier:
    """Verifies retrieved items before they are returned to callers.

    Args:
        evidence_loader: Async callable mapping an item id (file path) to
            its RetrievalEvidence, or None when no index-time evidence exists.
        integrity_service: Hash/HMAC verification (required).
        trust_engine: Trust score computation (required).
        quarantine_manager: Optional; quarantined items are excluded and
            integrity failures are quarantined for HITL review.
        audit_logger: Optional; exclusions and served items are audited.
        strict: Fail closed on unverifiable items (default True).
    """

    def __init__(
        self,
        evidence_loader: EvidenceLoader,
        integrity_service: IntegrityVerificationService,
        trust_engine: TrustScoringEngine,
        quarantine_manager: Optional[Any] = None,
        audit_logger: Optional[Any] = None,
        strict: bool = True,
    ):
        self._load = evidence_loader
        self.integrity = integrity_service
        self.trust = trust_engine
        self.quarantine = quarantine_manager
        self.audit = audit_logger
        self.strict = strict

    async def verify_item(self, item_id: str) -> VerificationDecision:
        """Verify one item; never raises."""
        try:
            return await self._verify(item_id)
        except Exception as e:  # noqa: BLE001 - fail closed on any error
            logger.error(f"Provenance verification error for {item_id}: {e}")
            return self._on_error(item_id, f"{type(e).__name__}: {e}")

    def _on_error(self, item_id: str, details: str) -> VerificationDecision:
        if self.strict:
            return VerificationDecision(
                item_id, False, VerificationOutcome.VERIFIER_ERROR, None, details
            )
        return VerificationDecision(
            item_id, True, VerificationOutcome.UNVERIFIED_ADMITTED, None, details
        )

    async def _verify(self, item_id: str) -> VerificationDecision:
        if self.quarantine is not None and await self.quarantine.is_quarantined(
            item_id
        ):
            await self._audit_exclusion(item_id, "quarantined", None)
            return VerificationDecision(
                item_id, False, VerificationOutcome.QUARANTINED, None, "quarantined"
            )

        evidence = await self._load(item_id)
        if evidence is None:
            if not self.strict:
                return VerificationDecision(
                    item_id,
                    True,
                    VerificationOutcome.UNVERIFIED_ADMITTED,
                    None,
                    "no integrity evidence (non-strict)",
                )
            await self._audit_exclusion(item_id, "no_evidence", None)
            return VerificationDecision(
                item_id,
                False,
                VerificationOutcome.NO_EVIDENCE,
                None,
                "no integrity evidence stored for item",
            )

        chunk_id = evidence.chunk_id or item_id
        # No chunk_id is passed: the integrity service caches results by
        # chunk_id, so a cached VERIFIED would mask content tampered after
        # the first check. Hash + HMAC over a stored document is cheap.
        result = self.integrity.verify(
            content=evidence.content,
            stored_hash=evidence.stored_hash,
            stored_hmac=evidence.stored_hmac,
        )
        if not result.verified:
            # Missing hashes are an absence of evidence, not tampering.
            if result.status == IntegrityStatus.HASH_MISSING:
                await self._audit_exclusion(item_id, "hash_missing", result.details)
                return VerificationDecision(
                    item_id,
                    not self.strict,
                    (
                        VerificationOutcome.UNVERIFIED_ADMITTED
                        if not self.strict
                        else VerificationOutcome.NO_EVIDENCE
                    ),
                    None,
                    result.details,
                )
            await self._quarantine(
                chunk_id, evidence, QuarantineReason.INTEGRITY_FAILURE, result.details
            )
            await self._audit_exclusion(item_id, result.status.value, result.details)
            return VerificationDecision(
                item_id,
                False,
                VerificationOutcome.INTEGRITY_FAILED,
                None,
                result.details,
            )

        score = self.trust.compute_trust_score(
            evidence.provenance, integrity_verified=True
        )
        if self.trust.should_quarantine(score):
            await self._quarantine(
                chunk_id, evidence, QuarantineReason.LOW_TRUST, f"score={score.score}"
            )
            await self._audit_exclusion(item_id, "low_trust", f"score={score.score}")
            return VerificationDecision(
                item_id, False, VerificationOutcome.LOW_TRUST, score, "untrusted"
            )

        if self.audit is not None:
            try:
                await self.audit.log_content_served(item_id, score.score)
            except Exception as e:  # noqa: BLE001 - audit must not block serving
                logger.warning(f"Audit log failed for served item {item_id}: {e}")
        return VerificationDecision(item_id, True, VerificationOutcome.VERIFIED, score)

    async def _quarantine(
        self,
        chunk_id: str,
        evidence: RetrievalEvidence,
        reason: QuarantineReason,
        details: Optional[str],
    ) -> None:
        if self.quarantine is None:
            return
        try:
            await self.quarantine.quarantine(
                chunk_id=chunk_id,
                content=evidence.content,
                reason=reason,
                details=details or reason.value,
                provenance=evidence.provenance,
            )
        except Exception as e:  # noqa: BLE001 - item is excluded regardless
            logger.error(f"Quarantine failed for {chunk_id}: {e}")

    async def _audit_exclusion(
        self, item_id: str, reason: str, details: Optional[str]
    ) -> None:
        logger.warning(f"Provenance exclusion: {item_id} reason={reason}")
        if self.audit is None:
            return
        try:
            await self.audit.log_integrity_failed(item_id, reason=reason)
        except Exception as e:  # noqa: BLE001 - audit must not change outcome
            logger.warning(f"Audit log failed for excluded item {item_id}: {e}")
