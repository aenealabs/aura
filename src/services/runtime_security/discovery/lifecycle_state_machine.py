"""
Project Aura - Agent Lifecycle State Machine

Enforces lifecycle transitions for agent decommissioning:
  active -> dormant -> decommissioning -> attested -> archived

Invalid transitions are rejected. State changes are logged
for audit compliance.

Based on ADR-086: Agentic Identity Lifecycle Controls (Phase 1)

Compliance:
- NIST 800-53 AC-2: Account management (lifecycle enforcement)
- NIST 800-53 PS-4: Personnel termination (credential revocation)
- NIST 800-53 CM-8: Information system component inventory

Author: Project Aura Team
Created: 2026-04-06
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LifecycleState(Enum):
    """Agent lifecycle states."""

    ACTIVE = "active"
    DORMANT = "dormant"
    DECOMMISSIONING = "decommissioning"
    REMEDIATION_REQUIRED = "remediation_required"
    ATTESTED = "attested"
    ARCHIVED = "archived"


class DecommissionTrigger(Enum):
    """Events that trigger decommission evaluation."""

    EXPLICIT_SHUTDOWN = "explicit_shutdown"
    DORMANCY_THRESHOLD = "dormancy_threshold"
    OWNER_DEACTIVATED = "owner_deactivated"
    GRANT_JUSTIFICATION_EXPIRED = "grant_justification_expired"
    WORKFLOW_DEPRECATED = "workflow_deprecated"
    PILOT_ABANDONED = "pilot_abandoned"
    ANOMALY_QUARANTINE = "anomaly_quarantine"


# Valid state transitions
_VALID_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.ACTIVE: {LifecycleState.DORMANT, LifecycleState.DECOMMISSIONING},
    LifecycleState.DORMANT: {LifecycleState.ACTIVE, LifecycleState.DECOMMISSIONING},
    LifecycleState.DECOMMISSIONING: {
        LifecycleState.ATTESTED,
        LifecycleState.REMEDIATION_REQUIRED,
    },
    LifecycleState.REMEDIATION_REQUIRED: {LifecycleState.DECOMMISSIONING},
    LifecycleState.ATTESTED: {LifecycleState.ARCHIVED},
    LifecycleState.ARCHIVED: set(),  # Terminal state
}


@dataclass(frozen=True)
class LifecycleTransition:
    """Immutable record of a state transition."""

    agent_id: str
    from_state: LifecycleState
    to_state: LifecycleState
    trigger: Optional[DecommissionTrigger]
    initiated_by: str
    timestamp: datetime
    reason: str = ""
    metadata: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "trigger": self.trigger.value if self.trigger else None,
            "initiated_by": self.initiated_by,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass
class AgentLifecycleRecord:
    """Mutable record tracking an agent's current lifecycle state."""

    agent_id: str
    current_state: LifecycleState = LifecycleState.ACTIVE
    owner_id: Optional[str] = None
    agent_tier: int = 4  # Default to lowest tier (read-only)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    state_changed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    transitions: list[LifecycleTransition] = field(default_factory=list)
    pending_trigger: Optional[DecommissionTrigger] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "current_state": self.current_state.value,
            "owner_id": self.owner_id,
            "agent_tier": self.agent_tier,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "state_changed_at": self.state_changed_at.isoformat(),
            "pending_trigger": (
                self.pending_trigger.value if self.pending_trigger else None
            ),
            "transition_count": len(self.transitions),
        }


class InvalidTransitionError(Exception):
    """Raised when an invalid lifecycle transition is attempted."""

    def __init__(
        self,
        agent_id: str,
        from_state: LifecycleState,
        to_state: LifecycleState,
    ):
        self.agent_id = agent_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid transition for agent {agent_id}: "
            f"{from_state.value} -> {to_state.value}"
        )


class LifecycleStateMachine:
    """
    Manages lifecycle state transitions for all tracked agents.

    Enforces valid transitions and maintains an audit trail of all
    state changes.

    Usage:
        sm = LifecycleStateMachine()
        sm.register_agent("agent-1", owner_id="user-1", agent_tier=2)
        sm.transition("agent-1", LifecycleState.DORMANT,
                       trigger=DecommissionTrigger.DORMANCY_THRESHOLD,
                       initiated_by="ghost_scanner")
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentLifecycleRecord] = {}

    def register_agent(
        self,
        agent_id: str,
        owner_id: Optional[str] = None,
        agent_tier: int = 4,
        initial_state: LifecycleState = LifecycleState.ACTIVE,
    ) -> AgentLifecycleRecord:
        """
        Register an agent for lifecycle tracking.

        Args:
            agent_id: Unique agent identifier.
            owner_id: Human owner of this agent.
            agent_tier: ADR-066 tier classification (1-4).
            initial_state: Starting state (default ACTIVE).

        Returns:
            The created lifecycle record.
        """
        record = AgentLifecycleRecord(
            agent_id=agent_id,
            current_state=initial_state,
            owner_id=owner_id,
            agent_tier=agent_tier,
        )
        self._agents[agent_id] = record
        logger.info(
            f"Registered agent {agent_id} (tier={agent_tier}, "
            f"state={initial_state.value})"
        )
        return record

    def get_agent(self, agent_id: str) -> Optional[AgentLifecycleRecord]:
        """Get lifecycle record for an agent."""
        return self._agents.get(agent_id)

    def get_state(self, agent_id: str) -> Optional[LifecycleState]:
        """Get current lifecycle state for an agent."""
        record = self._agents.get(agent_id)
        return record.current_state if record else None

    def is_valid_transition(
        self, from_state: LifecycleState, to_state: LifecycleState
    ) -> bool:
        """Check if a transition is valid."""
        return to_state in _VALID_TRANSITIONS.get(from_state, set())

    def transition(
        self,
        agent_id: str,
        to_state: LifecycleState,
        trigger: Optional[DecommissionTrigger] = None,
        initiated_by: str = "system",
        reason: str = "",
        metadata: Optional[dict[str, str]] = None,
    ) -> LifecycleTransition:
        """
        Transition an agent to a new lifecycle state.

        Args:
            agent_id: Agent to transition.
            to_state: Target state.
            trigger: What caused this transition.
            initiated_by: User or system component initiating.
            reason: Human-readable reason.
            metadata: Additional context.

        Returns:
            The recorded transition.

        Raises:
            KeyError: If agent_id is not registered.
            InvalidTransitionError: If transition is not valid.
        """
        record = self._agents.get(agent_id)
        if record is None:
            raise KeyError(f"Agent {agent_id} not registered in lifecycle tracker")

        from_state = record.current_state
        if not self.is_valid_transition(from_state, to_state):
            raise InvalidTransitionError(agent_id, from_state, to_state)

        now = datetime.now(timezone.utc)
        transition = LifecycleTransition(
            agent_id=agent_id,
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            initiated_by=initiated_by,
            timestamp=now,
            reason=reason,
            metadata=tuple((metadata or {}).items()),
        )

        record.current_state = to_state
        record.state_changed_at = now
        record.pending_trigger = trigger
        record.transitions.append(transition)

        logger.info(
            f"Agent {agent_id}: {from_state.value} -> {to_state.value} "
            f"(trigger={trigger.value if trigger else 'none'}, "
            f"by={initiated_by})"
        )
        return transition

    def record_activity(self, agent_id: str) -> None:
        """Update last_activity timestamp for an agent."""
        record = self._agents.get(agent_id)
        if record:
            record.last_activity = datetime.now(timezone.utc)

    def list_agents(
        self,
        state: Optional[LifecycleState] = None,
    ) -> list[AgentLifecycleRecord]:
        """
        List tracked agents, optionally filtered by state.

        Args:
            state: Filter to this state, or None for all.

        Returns:
            List of matching lifecycle records.
        """
        if state is None:
            return list(self._agents.values())
        return [r for r in self._agents.values() if r.current_state == state]

    def count_by_state(self) -> dict[str, int]:
        """Get agent counts grouped by lifecycle state."""
        counts: dict[str, int] = {s.value: 0 for s in LifecycleState}
        for record in self._agents.values():
            counts[record.current_state.value] += 1
        return counts

    def get_transitions(self, agent_id: str) -> list[LifecycleTransition]:
        """Get full transition history for an agent."""
        record = self._agents.get(agent_id)
        return list(record.transitions) if record else []

    def requires_hitl_cosign(self, agent_id: str) -> bool:
        """
        Check if this agent's decommission requires HITL co-signing.

        Per ADR-066 tier classification:
        - Tier 1/2: Verifier signature + human co-sign (blocking HITL)
        - Tier 3/4: Verifier signature only (HITL on failures)
        """
        record = self._agents.get(agent_id)
        if record is None:
            return True  # Default to requiring HITL for unknown agents
        return record.agent_tier <= 2


# Global singleton
_lifecycle_state_machine: Optional[LifecycleStateMachine] = None


def get_lifecycle_state_machine() -> LifecycleStateMachine:
    """Get the global lifecycle state machine instance."""
    global _lifecycle_state_machine
    if _lifecycle_state_machine is None:
        _lifecycle_state_machine = LifecycleStateMachine()
    return _lifecycle_state_machine


def reset_lifecycle_state_machine() -> None:
    """Reset the global lifecycle state machine (for testing)."""
    global _lifecycle_state_machine
    _lifecycle_state_machine = None
