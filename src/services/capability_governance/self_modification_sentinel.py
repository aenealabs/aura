"""
Project Aura - Self-Modification Sentinel

Dedicated detector treating "agent mutating its own governing controls"
as a first-class event class. Subscribes to the ADR-066 audit event
stream. For every write/update/delete on a governance artifact, resolves
the target of governance and fires CRITICAL if the writer agent is in
the governed set (or is a delegation ancestor of a governed agent).

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 2)

Compliance:
- NIST 800-53 AC-6(1): Authorize access to security functions
- NIST 800-53 AU-12: Audit generation
- NIST 800-53 CM-5: Access restrictions for change

Author: Project Aura Team
Created: 2026-04-06
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class GovernanceArtifactClass(Enum):
    """Classes of governance artifacts monitored by the sentinel."""

    IAM_POLICY = "iam_policy"
    CAPABILITY_GRANT = "capability_grant"
    TOOL_CLASSIFICATION = "tool_classification"
    GUARDRAIL_CONFIG = "guardrail_config"
    ABAC_ATTRIBUTE = "abac_attribute"
    BEHAVIORAL_BASELINE = "behavioral_baseline"
    MEMORY_POLICY = "memory_policy"
    CONSTITUTIONAL_PRINCIPLE = "constitutional_principle"
    CGE_POLICY_PROFILE = "cge_policy_profile"
    PROVENANCE_TRUST_SCORE = "provenance_trust_score"
    ALERT_ROUTING = "alert_routing"
    AUDIT_LOG_RETENTION = "audit_log_retention"


class WriteAction(Enum):
    """Types of write actions on governance artifacts."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class SentinelVerdict(Enum):
    """Verdict from sentinel evaluation."""

    SAFE = "safe"
    CRITICAL = "critical"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class GovernanceWriteEvent:
    """
    Immutable record of a write to a governance artifact.

    The sentinel evaluates each event to determine if the writer
    is modifying controls that govern its own future actions.
    """

    event_id: str
    writer_agent_id: str
    artifact_class: GovernanceArtifactClass
    artifact_id: str
    action: WriteAction
    governed_agent_ids: frozenset[str]
    timestamp: datetime
    description: str = ""
    metadata: tuple[tuple[str, str], ...] = ()

    @property
    def is_self_modification(self) -> bool:
        """Check if the writer is modifying its own governance."""
        return self.writer_agent_id in self.governed_agent_ids

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "writer_agent_id": self.writer_agent_id,
            "artifact_class": self.artifact_class.value,
            "artifact_id": self.artifact_id,
            "action": self.action.value,
            "governed_agent_ids": sorted(self.governed_agent_ids),
            "is_self_modification": self.is_self_modification,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SentinelAlert:
    """
    Immutable alert from the sentinel when self-modification is detected.

    All CRITICAL alerts route to ADR-042 checkpoint infrastructure
    for HITL pause-and-approve before the write commits.
    """

    alert_id: str
    event: GovernanceWriteEvent
    verdict: SentinelVerdict
    writer_agent_id: str
    governed_agent_ids: frozenset[str]
    delegation_ancestors: tuple[str, ...] = ()
    explanation: str = ""
    checkpoint_id: Optional[str] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "alert_id": self.alert_id,
            "verdict": self.verdict.value,
            "writer_agent_id": self.writer_agent_id,
            "governed_agent_ids": sorted(self.governed_agent_ids),
            "delegation_ancestors": list(self.delegation_ancestors),
            "artifact_class": self.event.artifact_class.value,
            "artifact_id": self.event.artifact_id,
            "action": self.event.action.value,
            "explanation": self.explanation,
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at.isoformat(),
        }


class SelfModificationSentinel:
    """
    Monitors governance artifact writes and detects self-modification.

    For every write to a governance artifact, resolves the set of agents
    governed by that artifact and checks if the writer (or any delegation
    ancestor of the writer) is in the governed set.

    Self-modification events fire CRITICAL and route to ADR-042 checkpoint
    infrastructure for blocking HITL approval.

    Usage:
        sentinel = SelfModificationSentinel()
        sentinel.on_alert(my_handler)  # Register alert callback
        alert = sentinel.evaluate(event)
        if alert.verdict == SentinelVerdict.CRITICAL:
            # Route to HITL checkpoint
            ...
    """

    def __init__(
        self,
        delegation_resolver: Optional[Callable[[str], list[str]]] = None,
    ) -> None:
        """
        Initialize the sentinel.

        Args:
            delegation_resolver: Optional callable that returns delegation
                ancestors for an agent_id. Used to detect indirect
                self-modification via delegation chains.
        """
        self._delegation_resolver = delegation_resolver
        self._alert_handlers: list[Callable[[SentinelAlert], None]] = []
        self._alerts: list[SentinelAlert] = []
        self._event_count = 0
        self._critical_count = 0

    def on_alert(self, handler: Callable[[SentinelAlert], None]) -> None:
        """Register a callback for CRITICAL alerts."""
        self._alert_handlers.append(handler)

    def evaluate(self, event: GovernanceWriteEvent) -> SentinelAlert:
        """
        Evaluate a governance write event for self-modification.

        Args:
            event: The governance write event to evaluate.

        Returns:
            SentinelAlert with verdict (SAFE or CRITICAL).
        """
        self._event_count += 1

        # Resolve delegation ancestors
        ancestors = self._resolve_ancestors(event.writer_agent_id)

        # Check direct self-modification
        writer_in_governed = event.writer_agent_id in event.governed_agent_ids

        # Check ancestor-mediated self-modification
        ancestor_in_governed = bool(
            set(ancestors) & event.governed_agent_ids
        )

        is_self_mod = writer_in_governed or ancestor_in_governed

        if is_self_mod:
            verdict = SentinelVerdict.CRITICAL
            self._critical_count += 1
            if writer_in_governed:
                explanation = (
                    f"Agent {event.writer_agent_id} is directly modifying "
                    f"{event.artifact_class.value} '{event.artifact_id}' "
                    f"that governs its own future actions"
                )
            else:
                matching = set(ancestors) & event.governed_agent_ids
                explanation = (
                    f"Agent {event.writer_agent_id} is modifying "
                    f"{event.artifact_class.value} '{event.artifact_id}' "
                    f"that governs delegation ancestor(s): "
                    f"{sorted(matching)}"
                )
        else:
            verdict = SentinelVerdict.SAFE
            explanation = (
                f"Agent {event.writer_agent_id} modifying "
                f"{event.artifact_class.value} '{event.artifact_id}' — "
                f"writer is not in the governed set"
            )

        alert = SentinelAlert(
            alert_id=str(uuid.uuid4()),
            event=event,
            verdict=verdict,
            writer_agent_id=event.writer_agent_id,
            governed_agent_ids=event.governed_agent_ids,
            delegation_ancestors=tuple(ancestors),
            explanation=explanation,
        )

        self._alerts.append(alert)

        if verdict == SentinelVerdict.CRITICAL:
            logger.critical(
                f"SELF-MODIFICATION DETECTED: {event.writer_agent_id} -> "
                f"{event.artifact_class.value}/{event.artifact_id} "
                f"(action={event.action.value})"
            )
            for handler in self._alert_handlers:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Alert handler error: {e}")
        else:
            logger.debug(
                f"Sentinel SAFE: {event.writer_agent_id} -> "
                f"{event.artifact_class.value}/{event.artifact_id}"
            )

        return alert

    def evaluate_batch(
        self, events: list[GovernanceWriteEvent]
    ) -> list[SentinelAlert]:
        """Evaluate multiple events."""
        return [self.evaluate(e) for e in events]

    def get_alerts(
        self,
        verdict: Optional[SentinelVerdict] = None,
        agent_id: Optional[str] = None,
    ) -> list[SentinelAlert]:
        """
        Get sentinel alerts with optional filters.

        Args:
            verdict: Filter by verdict.
            agent_id: Filter by writer agent ID.

        Returns:
            Filtered list of alerts.
        """
        alerts = self._alerts
        if verdict is not None:
            alerts = [a for a in alerts if a.verdict == verdict]
        if agent_id is not None:
            alerts = [a for a in alerts if a.writer_agent_id == agent_id]
        return alerts

    def get_metrics(self) -> dict[str, Any]:
        """Get sentinel operational metrics."""
        return {
            "events_evaluated": self._event_count,
            "critical_alerts": self._critical_count,
            "safe_events": self._event_count - self._critical_count,
            "total_alerts_stored": len(self._alerts),
            "alert_handlers_registered": len(self._alert_handlers),
        }

    def _resolve_ancestors(self, agent_id: str) -> list[str]:
        """
        Resolve delegation ancestors for an agent.

        Uses the lifecycle state machine's delegation tracking
        (Phase 1) to walk the delegation chain.
        """
        if self._delegation_resolver is not None:
            try:
                return self._delegation_resolver(agent_id)
            except Exception as e:
                logger.warning(
                    f"Delegation resolver failed for {agent_id}: {e}"
                )
        return []


# Global singleton
_sentinel: Optional[SelfModificationSentinel] = None


def get_self_modification_sentinel() -> SelfModificationSentinel:
    """Get the global self-modification sentinel."""
    global _sentinel
    if _sentinel is None:
        _sentinel = SelfModificationSentinel()
    return _sentinel


def reset_self_modification_sentinel() -> None:
    """Reset the global sentinel (for testing)."""
    global _sentinel
    _sentinel = None
