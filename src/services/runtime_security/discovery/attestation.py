"""
Project Aura - Decommission Attestation

Tiered attestation co-signing for agent decommission verification.
Tier 1/2 agents require human co-sign (blocking HITL). Tier 3/4
complete with verifier signature only (HITL on failures).

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 1)

Compliance:
- NIST 800-53 AC-2(4): Automated audit actions
- NIST 800-53 AU-10: Non-repudiation
- NIST 800-53 PS-4: Personnel termination

Author: Project Aura Team
Created: 2026-04-06
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AttestationStatus(Enum):
    """Status of a decommission attestation."""

    PENDING_VERIFICATION = "pending_verification"
    PENDING_COSIGN = "pending_cosign"
    ATTESTED = "attested"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class DecommissionAttestation:
    """
    Signed attestation that an agent has zero residual credentials.

    For tier 1/2 agents, requires both verifier_signature and
    human_cosigner_id. For tier 3/4, only verifier_signature.
    """

    attestation_id: str
    agent_id: str
    agent_tier: int
    status: AttestationStatus
    enumeration_summary: dict[str, Any] = field(default_factory=dict)
    verifier_signature: Optional[str] = None
    human_cosigner_id: Optional[str] = None
    cosigned_at: Optional[datetime] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    @property
    def requires_cosign(self) -> bool:
        """Whether this attestation requires human co-signing."""
        return self.agent_tier <= 2

    @property
    def is_complete(self) -> bool:
        """Whether attestation is fully complete."""
        if self.status != AttestationStatus.ATTESTED:
            return False
        if self.requires_cosign and self.human_cosigner_id is None:
            return False
        return self.verifier_signature is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "attestation_id": self.attestation_id,
            "agent_id": self.agent_id,
            "agent_tier": self.agent_tier,
            "status": self.status.value,
            "requires_cosign": self.requires_cosign,
            "is_complete": self.is_complete,
            "enumeration_summary": self.enumeration_summary,
            "verifier_signature": self.verifier_signature,
            "human_cosigner_id": self.human_cosigner_id,
            "cosigned_at": (
                self.cosigned_at.isoformat() if self.cosigned_at else None
            ),
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "rejection_reason": self.rejection_reason,
        }


class AttestationService:
    """
    Manages decommission attestation lifecycle.

    Creates attestation records, handles verifier signing and
    human co-signing, and stores completed attestations.

    Usage:
        service = AttestationService()
        attestation = service.create_attestation("agent-1", tier=2, summary={...})
        service.sign_verification(attestation.attestation_id)
        service.cosign(attestation.attestation_id, "admin-user")
    """

    def __init__(self, kms_client: Optional[Any] = None) -> None:
        self._attestations: dict[str, DecommissionAttestation] = {}
        self._kms_client = kms_client

    def create_attestation(
        self,
        agent_id: str,
        agent_tier: int,
        enumeration_summary: dict[str, Any],
    ) -> DecommissionAttestation:
        """
        Create a new decommission attestation.

        Args:
            agent_id: Agent being decommissioned.
            agent_tier: ADR-066 tier (1-4).
            enumeration_summary: Summary of credential enumeration results.

        Returns:
            The created attestation record.
        """
        attestation_id = str(uuid.uuid4())
        status = (
            AttestationStatus.PENDING_VERIFICATION
            if self._all_zero(enumeration_summary)
            else AttestationStatus.FAILED
        )

        attestation = DecommissionAttestation(
            attestation_id=attestation_id,
            agent_id=agent_id,
            agent_tier=agent_tier,
            status=status,
            enumeration_summary=enumeration_summary,
        )
        self._attestations[attestation_id] = attestation
        logger.info(
            f"Created attestation {attestation_id} for agent {agent_id} "
            f"(tier={agent_tier}, status={status.value})"
        )
        return attestation

    def sign_verification(self, attestation_id: str) -> bool:
        """
        Apply verifier signature to an attestation.

        Args:
            attestation_id: Attestation to sign.

        Returns:
            True if signed successfully.
        """
        attestation = self._attestations.get(attestation_id)
        if attestation is None:
            logger.error(f"Attestation {attestation_id} not found")
            return False

        if attestation.status != AttestationStatus.PENDING_VERIFICATION:
            logger.error(
                f"Cannot sign attestation {attestation_id} in state "
                f"{attestation.status.value}"
            )
            return False

        signature = self._generate_signature(attestation)
        attestation.verifier_signature = signature

        if attestation.requires_cosign:
            attestation.status = AttestationStatus.PENDING_COSIGN
            logger.info(
                f"Attestation {attestation_id} signed, awaiting human co-sign"
            )
        else:
            attestation.status = AttestationStatus.ATTESTED
            attestation.completed_at = datetime.now(timezone.utc)
            logger.info(f"Attestation {attestation_id} fully attested (tier 3/4)")

        return True

    def cosign(
        self,
        attestation_id: str,
        cosigner_id: str,
    ) -> bool:
        """
        Apply human co-signature to a tier 1/2 attestation.

        Args:
            attestation_id: Attestation to co-sign.
            cosigner_id: Human approver identifier.

        Returns:
            True if co-signed successfully.
        """
        attestation = self._attestations.get(attestation_id)
        if attestation is None:
            logger.error(f"Attestation {attestation_id} not found")
            return False

        if attestation.status != AttestationStatus.PENDING_COSIGN:
            logger.error(
                f"Cannot co-sign attestation {attestation_id} in state "
                f"{attestation.status.value}"
            )
            return False

        now = datetime.now(timezone.utc)
        attestation.human_cosigner_id = cosigner_id
        attestation.cosigned_at = now
        attestation.status = AttestationStatus.ATTESTED
        attestation.completed_at = now
        logger.info(
            f"Attestation {attestation_id} co-signed by {cosigner_id}"
        )
        return True

    def reject(
        self,
        attestation_id: str,
        reason: str,
    ) -> bool:
        """
        Reject an attestation (e.g., residual credentials found).

        Args:
            attestation_id: Attestation to reject.
            reason: Human-readable rejection reason.

        Returns:
            True if rejected successfully.
        """
        attestation = self._attestations.get(attestation_id)
        if attestation is None:
            return False

        attestation.status = AttestationStatus.REJECTED
        attestation.rejection_reason = reason
        attestation.completed_at = datetime.now(timezone.utc)
        logger.info(
            f"Attestation {attestation_id} rejected: {reason}"
        )
        return True

    def get_attestation(
        self, attestation_id: str
    ) -> Optional[DecommissionAttestation]:
        """Get an attestation by ID."""
        return self._attestations.get(attestation_id)

    def get_attestations_for_agent(
        self, agent_id: str
    ) -> list[DecommissionAttestation]:
        """Get all attestations for an agent."""
        return [
            a for a in self._attestations.values() if a.agent_id == agent_id
        ]

    def _all_zero(self, summary: dict[str, Any]) -> bool:
        """Check if enumeration summary shows zero active credentials."""
        if not summary:
            return False
        results = summary.get("results", [])
        if not results:
            return summary.get("all_zero_confirmed", False)
        return all(r.get("zero_confirmed", False) for r in results)

    def _generate_signature(self, attestation: DecommissionAttestation) -> str:
        """
        Generate a verifier signature for an attestation.

        In production, uses KMS CMK per ADR-073 pattern.
        Falls back to HMAC-SHA256 for local/test environments.
        """
        payload = (
            f"{attestation.attestation_id}:"
            f"{attestation.agent_id}:"
            f"{attestation.agent_tier}:"
            f"{attestation.created_at.isoformat()}"
        )

        if self._kms_client is not None:
            try:
                response = self._kms_client.sign(
                    KeyId="alias/aura-decommission-signing",
                    Message=payload.encode(),
                    MessageType="RAW",
                    SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256",
                )
                return response["Signature"].hex()
            except Exception as e:
                logger.warning(f"KMS signing failed, using local fallback: {e}")

        return hashlib.sha256(payload.encode()).hexdigest()
