"""
Project Aura - Decommission Verifier

Orchestrates the agent decommission process: transitions the lifecycle
state machine, runs all credential enumerators, and produces or blocks
attestation based on results and agent tier.

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 1)

Flow:
  1. Transition agent to DECOMMISSIONING
  2. Run all credential enumerators
  3. If zero_confirmed: create attestation, sign, route HITL if tier 1/2
  4. If residual credentials: transition to REMEDIATION_REQUIRED, report

Compliance:
- NIST 800-53 AC-2: Account management
- NIST 800-53 PS-4: Personnel termination
- NIST 800-53 CM-8: Information system component inventory

Author: Project Aura Team
Created: 2026-04-06
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .attestation import AttestationService, DecommissionAttestation
from .credential_enumerators.registry import (
    EnumerationResult,
    EnumeratorRegistry,
    get_enumerator_registry,
)
from .lifecycle_state_machine import (
    DecommissionTrigger,
    InvalidTransitionError,
    LifecycleState,
    LifecycleStateMachine,
    get_lifecycle_state_machine,
)

logger = logging.getLogger(__name__)


@dataclass
class DecommissionReport:
    """Report from a decommission verification attempt."""

    agent_id: str
    trigger: DecommissionTrigger
    initiated_by: str
    enumeration_results: list[EnumerationResult] = field(default_factory=list)
    all_zero_confirmed: bool = False
    residual_credential_count: int = 0
    attestation: Optional[DecommissionAttestation] = None
    requires_hitl: bool = False
    error: Optional[str] = None
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "trigger": self.trigger.value,
            "initiated_by": self.initiated_by,
            "all_zero_confirmed": self.all_zero_confirmed,
            "residual_credential_count": self.residual_credential_count,
            "enumeration_results": [r.to_dict() for r in self.enumeration_results],
            "attestation": (
                self.attestation.to_dict() if self.attestation else None
            ),
            "requires_hitl": self.requires_hitl,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


class DecommissionVerifier:
    """
    Orchestrates agent decommission verification.

    Drives the lifecycle state machine through the decommission flow,
    enumerates all credential classes, and produces attestation when
    zero residual credentials are confirmed.

    Usage:
        verifier = DecommissionVerifier()
        report = verifier.verify_decommission(
            agent_id="agent-1",
            trigger=DecommissionTrigger.EXPLICIT_SHUTDOWN,
            initiated_by="admin",
        )
    """

    def __init__(
        self,
        state_machine: Optional[LifecycleStateMachine] = None,
        enumerator_registry: Optional[EnumeratorRegistry] = None,
        attestation_service: Optional[AttestationService] = None,
    ) -> None:
        self._state_machine = state_machine or get_lifecycle_state_machine()
        self._enumerator_registry = enumerator_registry or get_enumerator_registry()
        self._attestation_service = attestation_service or AttestationService()

    def verify_decommission(
        self,
        agent_id: str,
        trigger: DecommissionTrigger,
        initiated_by: str = "system",
        reason: str = "",
    ) -> DecommissionReport:
        """
        Run the full decommission verification for an agent.

        Args:
            agent_id: Agent to decommission.
            trigger: What caused the decommission.
            initiated_by: User or system component.
            reason: Human-readable reason.

        Returns:
            DecommissionReport with results and attestation status.
        """
        report = DecommissionReport(
            agent_id=agent_id,
            trigger=trigger,
            initiated_by=initiated_by,
        )

        # Transition to DECOMMISSIONING
        try:
            self._state_machine.transition(
                agent_id=agent_id,
                to_state=LifecycleState.DECOMMISSIONING,
                trigger=trigger,
                initiated_by=initiated_by,
                reason=reason,
            )
        except (KeyError, InvalidTransitionError) as e:
            report.error = str(e)
            report.completed_at = datetime.now(timezone.utc)
            logger.error(f"Decommission transition failed for {agent_id}: {e}")
            return report

        # Enumerate all credentials
        results = self._enumerator_registry.enumerate_all(agent_id)
        report.enumeration_results = results
        report.all_zero_confirmed = self._enumerator_registry.all_zero_confirmed(
            results
        )
        report.residual_credential_count = sum(
            r.active_count for r in results
        )

        if report.all_zero_confirmed:
            # Create and sign attestation
            summary = self._build_summary(results)
            record = self._state_machine.get_agent(agent_id)
            agent_tier = record.agent_tier if record else 4

            attestation = self._attestation_service.create_attestation(
                agent_id=agent_id,
                agent_tier=agent_tier,
                enumeration_summary=summary,
            )
            self._attestation_service.sign_verification(attestation.attestation_id)

            report.attestation = attestation
            report.requires_hitl = attestation.requires_cosign

            if not attestation.requires_cosign:
                # Tier 3/4: auto-complete
                self._state_machine.transition(
                    agent_id=agent_id,
                    to_state=LifecycleState.ATTESTED,
                    initiated_by="decommission_verifier",
                    reason="Zero credentials confirmed, verifier signed",
                )
        else:
            # Residual credentials found — route to remediation
            self._state_machine.transition(
                agent_id=agent_id,
                to_state=LifecycleState.REMEDIATION_REQUIRED,
                trigger=trigger,
                initiated_by="decommission_verifier",
                reason=(
                    f"Residual credentials found: "
                    f"{report.residual_credential_count} active across "
                    f"{sum(1 for r in results if r.needs_remediation)} classes"
                ),
            )

        report.completed_at = datetime.now(timezone.utc)
        logger.info(
            f"Decommission verification for {agent_id}: "
            f"zero_confirmed={report.all_zero_confirmed}, "
            f"residual={report.residual_credential_count}, "
            f"requires_hitl={report.requires_hitl}"
        )
        return report

    def complete_cosign(
        self,
        agent_id: str,
        attestation_id: str,
        cosigner_id: str,
    ) -> bool:
        """
        Complete HITL co-signing for a tier 1/2 agent decommission.

        Args:
            agent_id: Agent being decommissioned.
            attestation_id: Attestation awaiting co-sign.
            cosigner_id: Human approver.

        Returns:
            True if the agent transitioned to ATTESTED.
        """
        success = self._attestation_service.cosign(attestation_id, cosigner_id)
        if not success:
            return False

        try:
            self._state_machine.transition(
                agent_id=agent_id,
                to_state=LifecycleState.ATTESTED,
                initiated_by=cosigner_id,
                reason=f"Human co-sign by {cosigner_id}",
            )
            return True
        except (KeyError, InvalidTransitionError) as e:
            logger.error(f"Post-cosign transition failed for {agent_id}: {e}")
            return False

    def archive(self, agent_id: str, initiated_by: str = "system") -> bool:
        """
        Archive an attested agent (final state).

        Args:
            agent_id: Agent to archive.
            initiated_by: Who initiated archival.

        Returns:
            True if successfully archived.
        """
        try:
            self._state_machine.transition(
                agent_id=agent_id,
                to_state=LifecycleState.ARCHIVED,
                initiated_by=initiated_by,
                reason="Decommission complete, agent archived",
            )
            return True
        except (KeyError, InvalidTransitionError) as e:
            logger.error(f"Archive failed for {agent_id}: {e}")
            return False

    def _build_summary(
        self, results: list[EnumerationResult]
    ) -> dict[str, Any]:
        """Build enumeration summary for attestation record."""
        return {
            "total_classes": len(results),
            "all_zero_confirmed": all(r.zero_confirmed for r in results),
            "results": [
                {
                    "credential_class": r.credential_class,
                    "zero_confirmed": r.zero_confirmed,
                    "active_count": r.active_count,
                    "total_count": len(r.credentials),
                }
                for r in results
            ],
        }
