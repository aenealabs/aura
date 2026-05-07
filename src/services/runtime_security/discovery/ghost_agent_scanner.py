"""
Project Aura - Ghost Agent Scanner

Weekly reconciliation scanner that identifies orphaned credentials,
grants, baselines, and provenance records not mapped to a live
registered agent with recent activity.

Invoked by EventBridge scheduled rule. Orphans become ghost-agent
findings routed to HITL.

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 1)

Compliance:
- NIST 800-53 AC-2(3): Disable inactive accounts
- NIST 800-53 CM-8: Information system component inventory
- NIST 800-53 SI-4: Information system monitoring

Author: Project Aura Team
Created: 2026-04-06
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from .credential_enumerators.registry import EnumeratorRegistry, get_enumerator_registry
from .lifecycle_state_machine import (
    DecommissionTrigger,
    LifecycleState,
    LifecycleStateMachine,
    get_lifecycle_state_machine,
)

logger = logging.getLogger(__name__)


class GhostFindingSeverity(Enum):
    """Severity of a ghost agent finding."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class GhostAgentFinding:
    """Immutable record of a ghost agent discovery."""

    finding_id: str
    agent_id: str
    severity: GhostFindingSeverity
    reason: str
    active_credential_classes: tuple[str, ...]
    active_credential_count: int
    last_activity: Optional[datetime] = None
    owner_id: Optional[str] = None
    agent_tier: int = 4
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "finding_id": self.finding_id,
            "agent_id": self.agent_id,
            "severity": self.severity.value,
            "reason": self.reason,
            "active_credential_classes": list(self.active_credential_classes),
            "active_credential_count": self.active_credential_count,
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
            "owner_id": self.owner_id,
            "agent_tier": self.agent_tier,
            "discovered_at": self.discovered_at.isoformat(),
        }


@dataclass
class ScanResult:
    """Result of a ghost agent scan cycle."""

    findings: list[GhostAgentFinding] = field(default_factory=list)
    agents_scanned: int = 0
    ghost_agents_found: int = 0
    auto_triggered_decommissions: int = 0
    scan_started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    scan_completed_at: Optional[datetime] = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "findings": [f.to_dict() for f in self.findings],
            "agents_scanned": self.agents_scanned,
            "ghost_agents_found": self.ghost_agents_found,
            "auto_triggered_decommissions": self.auto_triggered_decommissions,
            "scan_started_at": self.scan_started_at.isoformat(),
            "scan_completed_at": (
                self.scan_completed_at.isoformat() if self.scan_completed_at else None
            ),
            "error_count": len(self.errors),
        }


class GhostAgentScanner:
    """
    Scans for ghost agents — registered agents with live credentials
    but no recent activity within the compliance-profile-driven
    dormancy window.

    Usage:
        scanner = GhostAgentScanner(dormancy_days=30)
        result = scanner.scan()
        for finding in result.findings:
            print(finding.agent_id, finding.severity)
    """

    def __init__(
        self,
        state_machine: Optional[LifecycleStateMachine] = None,
        enumerator_registry: Optional[EnumeratorRegistry] = None,
        dormancy_days: int = 30,
        auto_trigger_decommission: bool = False,
    ) -> None:
        """
        Initialize the ghost agent scanner.

        Args:
            state_machine: Lifecycle state machine.
            enumerator_registry: Credential enumerator registry.
            dormancy_days: Days of inactivity before an agent is
                considered dormant.
            auto_trigger_decommission: If True, automatically transition
                dormant ghost agents to DECOMMISSIONING.
        """
        self._state_machine = state_machine or get_lifecycle_state_machine()
        self._enumerator_registry = enumerator_registry or get_enumerator_registry()
        self._dormancy_days = dormancy_days
        self._auto_trigger = auto_trigger_decommission

    def scan(self) -> ScanResult:
        """
        Run a full ghost agent scan.

        Iterates all ACTIVE agents, checks for dormancy, and enumerates
        credentials for dormant agents. Ghost findings are created for
        dormant agents with live credentials.

        Returns:
            ScanResult with findings and metrics.
        """
        result = ScanResult()
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._dormancy_days)

        active_agents = self._state_machine.list_agents(state=LifecycleState.ACTIVE)
        # Also check dormant agents that haven't been decommissioned yet
        dormant_agents = self._state_machine.list_agents(state=LifecycleState.DORMANT)
        all_agents = active_agents + dormant_agents
        result.agents_scanned = len(all_agents)

        for agent_record in all_agents:
            try:
                finding = self._evaluate_agent(agent_record, cutoff)
                if finding is not None:
                    result.findings.append(finding)
                    result.ghost_agents_found += 1

                    if self._auto_trigger:
                        self._trigger_decommission(agent_record.agent_id)
                        result.auto_triggered_decommissions += 1

            except Exception as e:
                error_msg = f"Error scanning agent {agent_record.agent_id}: {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        result.scan_completed_at = datetime.now(timezone.utc)
        logger.info(
            f"Ghost agent scan complete: scanned={result.agents_scanned}, "
            f"ghosts={result.ghost_agents_found}, "
            f"errors={len(result.errors)}"
        )
        return result

    def _evaluate_agent(
        self,
        agent_record: Any,
        cutoff: datetime,
    ) -> Optional[GhostAgentFinding]:
        """
        Evaluate a single agent for ghost status.

        An agent is a ghost if:
        1. Last activity is older than the dormancy cutoff
        2. It still holds active credentials

        Args:
            agent_record: AgentLifecycleRecord from state machine.
            cutoff: Datetime threshold for dormancy.

        Returns:
            GhostAgentFinding if ghost detected, None otherwise.
        """
        if agent_record.last_activity > cutoff:
            return None  # Agent is active recently

        # Dormant — check for residual credentials
        enum_results = self._enumerator_registry.enumerate_all(agent_record.agent_id)
        active_classes = [
            r.credential_class for r in enum_results if r.active_count > 0
        ]
        total_active = sum(r.active_count for r in enum_results)

        if total_active == 0:
            return None  # Dormant but no credentials — not a ghost

        # Determine severity based on tier and credential count
        severity = self._classify_severity(
            agent_tier=agent_record.agent_tier,
            active_count=total_active,
            active_classes=active_classes,
        )

        import uuid

        return GhostAgentFinding(
            finding_id=str(uuid.uuid4()),
            agent_id=agent_record.agent_id,
            severity=severity,
            reason=(
                f"Agent dormant since {agent_record.last_activity.isoformat()} "
                f"with {total_active} active credential(s) across "
                f"{len(active_classes)} class(es)"
            ),
            active_credential_classes=tuple(active_classes),
            active_credential_count=total_active,
            last_activity=agent_record.last_activity,
            owner_id=agent_record.owner_id,
            agent_tier=agent_record.agent_tier,
        )

    def _classify_severity(
        self,
        agent_tier: int,
        active_count: int,
        active_classes: list[str],
    ) -> GhostFindingSeverity:
        """
        Classify ghost finding severity.

        - CRITICAL: Tier 1/2 with IAM or secrets credentials
        - HIGH: Tier 1/2 with any credentials, or tier 3/4 with IAM
        - MEDIUM: Tier 3/4 with non-IAM credentials
        - LOW: Minimal residual (e.g., baseline records only)
        """
        sensitive_classes = {
            "aws_iam_roles",
            "aws_access_keys",
            "secrets_manager",
            "ssm_parameters",
        }
        has_sensitive = bool(set(active_classes) & sensitive_classes)

        if agent_tier <= 2 and has_sensitive:
            return GhostFindingSeverity.CRITICAL
        if agent_tier <= 2 or has_sensitive:
            return GhostFindingSeverity.HIGH
        if active_count > 1:
            return GhostFindingSeverity.MEDIUM
        return GhostFindingSeverity.LOW

    def _trigger_decommission(self, agent_id: str) -> None:
        """Auto-transition a ghost agent to DORMANT then DECOMMISSIONING."""
        try:
            current = self._state_machine.get_state(agent_id)
            if current == LifecycleState.ACTIVE:
                self._state_machine.transition(
                    agent_id=agent_id,
                    to_state=LifecycleState.DORMANT,
                    trigger=DecommissionTrigger.DORMANCY_THRESHOLD,
                    initiated_by="ghost_agent_scanner",
                    reason="Dormancy threshold exceeded with active credentials",
                )
            # Now transition to DECOMMISSIONING
            self._state_machine.transition(
                agent_id=agent_id,
                to_state=LifecycleState.DECOMMISSIONING,
                trigger=DecommissionTrigger.DORMANCY_THRESHOLD,
                initiated_by="ghost_agent_scanner",
                reason="Ghost agent auto-decommission",
            )
            logger.info(f"Auto-triggered decommission for ghost agent {agent_id}")
        except Exception as e:
            logger.error(f"Failed to auto-trigger decommission for {agent_id}: {e}")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler for EventBridge scheduled invocation.

    Args:
        event: EventBridge event payload.
        context: Lambda execution context.

    Returns:
        Scan result summary.
    """
    dormancy_days = event.get("dormancy_days", 30)
    auto_trigger = event.get("auto_trigger_decommission", False)

    scanner = GhostAgentScanner(
        dormancy_days=dormancy_days,
        auto_trigger_decommission=auto_trigger,
    )
    result = scanner.scan()

    logger.info(f"Lambda scan complete: {result.ghost_agents_found} ghosts found")
    return result.to_dict()
