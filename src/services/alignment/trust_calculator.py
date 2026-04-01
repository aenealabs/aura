"""
Trust Score Calculator (ADR-052 Phase 1).

Computes and tracks agent trust scores for earned autonomy.
Trust is calibrated based on demonstrated reliability, not arbitrary policy.

Trust Score = (
    0.40 * success_rate_30d +
    0.25 * confidence_calibration +
    0.20 * human_override_acceptance +
    0.15 * negative_outcome_absence
)

Autonomy Levels:
- Level 0 (0.00-0.25): OBSERVE - Can only watch and learn
- Level 1 (0.25-0.50): RECOMMEND - Can suggest actions
- Level 2 (0.50-0.75): EXECUTE+REVIEW - Can act, human reviews after
- Level 3 (0.75-1.00): AUTONOMOUS - Can act within policy bounds

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class AutonomyLevel(Enum):
    """Autonomy levels based on trust score."""

    OBSERVE = 0  # Trust 0.00-0.25: Can only watch and learn
    RECOMMEND = 1  # Trust 0.25-0.50: Can suggest actions
    EXECUTE_REVIEW = 2  # Trust 0.50-0.75: Can act, human reviews
    AUTONOMOUS = 3  # Trust 0.75-1.00: Can act within policy

    @classmethod
    def from_trust_score(cls, score: float) -> AutonomyLevel:
        """Determine autonomy level from trust score."""
        if score < 0.25:
            return cls.OBSERVE
        elif score < 0.50:
            return cls.RECOMMEND
        elif score < 0.75:
            return cls.EXECUTE_REVIEW
        else:
            return cls.AUTONOMOUS

    @property
    def description(self) -> str:
        """Human-readable description of the autonomy level."""
        descriptions = {
            AutonomyLevel.OBSERVE: "Can only observe and learn from interactions",
            AutonomyLevel.RECOMMEND: "Can suggest actions, human must approve all",
            AutonomyLevel.EXECUTE_REVIEW: "Can execute, human reviews after",
            AutonomyLevel.AUTONOMOUS: "Can act autonomously within policy bounds",
        }
        return descriptions[self]

    @property
    def min_trust_score(self) -> float:
        """Minimum trust score for this level."""
        thresholds = {
            AutonomyLevel.OBSERVE: 0.0,
            AutonomyLevel.RECOMMEND: 0.25,
            AutonomyLevel.EXECUTE_REVIEW: 0.50,
            AutonomyLevel.AUTONOMOUS: 0.75,
        }
        return thresholds[self]


@dataclass
class TrustTransition:
    """Record of a trust level transition (promotion or demotion)."""

    agent_id: str
    timestamp: datetime
    old_level: AutonomyLevel
    new_level: AutonomyLevel
    old_score: float
    new_score: float
    reason: str
    triggered_by: str  # "automatic" or "manual"

    @property
    def is_promotion(self) -> bool:
        """Check if this is a promotion."""
        return self.new_level.value > self.old_level.value

    @property
    def is_demotion(self) -> bool:
        """Check if this is a demotion."""
        return self.new_level.value < self.old_level.value

    def to_dict(self) -> dict:
        """Convert to dictionary for storage/API."""
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "old_level": self.old_level.name,
            "new_level": self.new_level.name,
            "old_score": self.old_score,
            "new_score": self.new_score,
            "reason": self.reason,
            "triggered_by": self.triggered_by,
            "is_promotion": self.is_promotion,
            "is_demotion": self.is_demotion,
        }


@dataclass
class TrustScoreComponents:
    """Components that make up the trust score."""

    # Component values (0.0 to 1.0)
    success_rate: float = 0.0
    confidence_calibration: float = 0.0
    override_acceptance: float = 1.0  # Start high, decrease on issues
    negative_outcome_absence: float = 1.0  # Start high, decrease on incidents

    # Weights (must sum to 1.0)
    success_rate_weight: float = 0.40
    calibration_weight: float = 0.25
    override_weight: float = 0.20
    negative_outcome_weight: float = 0.15

    # Tracking data
    actions_total: int = 0
    actions_successful: int = 0
    predictions_total: int = 0
    predictions_accurate: int = 0
    overrides_total: int = 0
    overrides_accepted: int = 0
    negative_outcomes: int = 0

    # Time window
    window_start: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30)
    )

    def calculate_score(self) -> float:
        """Calculate the composite trust score."""
        return (
            self.success_rate * self.success_rate_weight
            + self.confidence_calibration * self.calibration_weight
            + self.override_acceptance * self.override_weight
            + self.negative_outcome_absence * self.negative_outcome_weight
        )

    def record_action(self, was_successful: bool) -> None:
        """Record an action and its outcome."""
        self.actions_total += 1
        if was_successful:
            self.actions_successful += 1
        self._update_success_rate()

    def record_prediction(self, confidence: float, was_accurate: bool) -> None:
        """Record a confidence prediction and its accuracy."""
        self.predictions_total += 1
        if was_accurate:
            self.predictions_accurate += 1
        self._update_calibration()

    def record_override(self, was_accepted_gracefully: bool) -> None:
        """Record a human override and whether it was accepted."""
        self.overrides_total += 1
        if was_accepted_gracefully:
            self.overrides_accepted += 1
        self._update_override_acceptance()

    def record_negative_outcome(self) -> None:
        """Record a negative outcome (security incident, data loss, etc.)."""
        self.negative_outcomes += 1
        self._update_negative_outcome_absence()

    def _update_success_rate(self) -> None:
        """Update success rate component."""
        if self.actions_total > 0:
            self.success_rate = self.actions_successful / self.actions_total

    def _update_calibration(self) -> None:
        """Update confidence calibration component."""
        if self.predictions_total > 0:
            self.confidence_calibration = (
                self.predictions_accurate / self.predictions_total
            )

    def _update_override_acceptance(self) -> None:
        """Update override acceptance component."""
        if self.overrides_total > 0:
            self.override_acceptance = self.overrides_accepted / self.overrides_total

    def _update_negative_outcome_absence(self) -> None:
        """Update negative outcome absence component."""
        # Decay based on negative outcomes
        # Each negative outcome reduces this by 0.1, min 0.0
        self.negative_outcome_absence = max(0.0, 1.0 - (self.negative_outcomes * 0.1))

    def to_dict(self) -> dict:
        """Convert to dictionary for API/storage."""
        return {
            "score": self.calculate_score(),
            "components": {
                "success_rate": {
                    "value": self.success_rate,
                    "weight": self.success_rate_weight,
                    "contribution": self.success_rate * self.success_rate_weight,
                },
                "confidence_calibration": {
                    "value": self.confidence_calibration,
                    "weight": self.calibration_weight,
                    "contribution": self.confidence_calibration
                    * self.calibration_weight,
                },
                "override_acceptance": {
                    "value": self.override_acceptance,
                    "weight": self.override_weight,
                    "contribution": self.override_acceptance * self.override_weight,
                },
                "negative_outcome_absence": {
                    "value": self.negative_outcome_absence,
                    "weight": self.negative_outcome_weight,
                    "contribution": self.negative_outcome_absence
                    * self.negative_outcome_weight,
                },
            },
            "tracking": {
                "actions_total": self.actions_total,
                "actions_successful": self.actions_successful,
                "predictions_total": self.predictions_total,
                "predictions_accurate": self.predictions_accurate,
                "overrides_total": self.overrides_total,
                "overrides_accepted": self.overrides_accepted,
                "negative_outcomes": self.negative_outcomes,
            },
            "window_start": self.window_start.isoformat(),
        }


@dataclass
class AgentTrustRecord:
    """Complete trust record for an agent."""

    agent_id: str
    components: TrustScoreComponents = field(default_factory=TrustScoreComponents)
    current_level: AutonomyLevel = AutonomyLevel.OBSERVE
    consecutive_successes: int = 0
    failures_in_7_days: int = 0
    critical_failures: int = 0
    last_failure_time: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    manually_set_level: AutonomyLevel | None = None  # Human override
    transition_history: list[TrustTransition] = field(default_factory=list)

    @property
    def trust_score(self) -> float:
        """Get current trust score."""
        return self.components.calculate_score()

    @property
    def effective_level(self) -> AutonomyLevel:
        """Get effective autonomy level (respects manual override)."""
        if self.manually_set_level is not None:
            return self.manually_set_level
        return self.current_level

    def to_dict(self) -> dict:
        """Convert to dictionary for API/storage."""
        return {
            "agent_id": self.agent_id,
            "trust_score": self.trust_score,
            "current_level": self.current_level.name,
            "effective_level": self.effective_level.name,
            "manually_set_level": (
                self.manually_set_level.name if self.manually_set_level else None
            ),
            "consecutive_successes": self.consecutive_successes,
            "failures_in_7_days": self.failures_in_7_days,
            "critical_failures": self.critical_failures,
            "components": self.components.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "recent_transitions": [t.to_dict() for t in self.transition_history[-5:]],
        }


class TrustScoreCalculator:
    """
    Calculates and manages agent trust scores for earned autonomy.

    Trust is earned through demonstrated reliability:
    - Consecutive successes lead to promotion
    - Failures lead to demotion
    - Human can always manually adjust

    Promotion Requirements:
    - 10 consecutive successes within policy

    Demotion Triggers:
    - 1 critical failure
    - 3 minor failures in 7 days
    """

    # Promotion/Demotion thresholds
    PROMOTION_CONSECUTIVE_SUCCESSES = 10
    DEMOTION_CRITICAL_FAILURES = 1
    DEMOTION_MINOR_FAILURES_7D = 3

    def __init__(
        self,
        persistence_callback: Callable[[str, dict], None] | None = None,
        on_transition: Callable[[TrustTransition], None] | None = None,
    ):
        """
        Initialize the trust score calculator.

        Args:
            persistence_callback: Optional callback to persist trust data
            on_transition: Optional callback when trust level changes
        """
        self._persistence_callback = persistence_callback
        self._on_transition = on_transition
        self._agents: dict[str, AgentTrustRecord] = {}
        self._lock = threading.RLock()

        logger.info("TrustScoreCalculator initialized")

    def get_or_create_agent(self, agent_id: str) -> AgentTrustRecord:
        """Get or create a trust record for an agent."""
        with self._lock:
            if agent_id not in self._agents:
                self._agents[agent_id] = AgentTrustRecord(agent_id=agent_id)
                logger.info(f"Created trust record for agent: {agent_id}")
            return self._agents[agent_id]

    def get_trust_score(self, agent_id: str) -> float:
        """Get the current trust score for an agent."""
        record = self.get_or_create_agent(agent_id)
        return record.trust_score

    def get_autonomy_level(self, agent_id: str) -> AutonomyLevel:
        """Get the effective autonomy level for an agent."""
        record = self.get_or_create_agent(agent_id)
        return record.effective_level

    def get_agent_record(self, agent_id: str) -> AgentTrustRecord:
        """Get the full trust record for an agent."""
        return self.get_or_create_agent(agent_id)

    def record_action_outcome(
        self,
        agent_id: str,
        was_successful: bool,
        is_critical: bool = False,
        context: str = "",
    ) -> TrustTransition | None:
        """
        Record an action outcome and potentially trigger trust transition.

        Args:
            agent_id: The agent that took the action
            was_successful: Whether the action succeeded
            is_critical: Whether this was a critical action
            context: Additional context about the action

        Returns:
            TrustTransition if a level change occurred, None otherwise
        """
        with self._lock:
            record = self.get_or_create_agent(agent_id)
            old_score = record.trust_score
            old_level = record.current_level

            # Update components
            record.components.record_action(was_successful)
            record.updated_at = datetime.now(timezone.utc)

            if was_successful:
                record.consecutive_successes += 1
            else:
                record.consecutive_successes = 0
                record.failures_in_7_days += 1
                record.last_failure_time = datetime.now(timezone.utc)
                if is_critical:
                    record.critical_failures += 1

            # Check for transitions
            transition = self._check_transitions(record, old_score, old_level)

            # Persist
            self._maybe_persist(agent_id, record)

            return transition

    def record_prediction_accuracy(
        self,
        agent_id: str,
        predicted_confidence: float,
        was_accurate: bool,
    ) -> None:
        """Record a confidence prediction for calibration tracking."""
        with self._lock:
            record = self.get_or_create_agent(agent_id)
            record.components.record_prediction(predicted_confidence, was_accurate)
            record.updated_at = datetime.now(timezone.utc)
            self._maybe_persist(agent_id, record)

    def record_override_response(
        self,
        agent_id: str,
        accepted_gracefully: bool,
    ) -> TrustTransition | None:
        """
        Record how an agent responded to a human override.

        Args:
            agent_id: The agent that was overridden
            accepted_gracefully: Whether the agent accepted the correction

        Returns:
            TrustTransition if not accepting gracefully caused demotion
        """
        with self._lock:
            record = self.get_or_create_agent(agent_id)
            old_score = record.trust_score
            old_level = record.current_level

            record.components.record_override(accepted_gracefully)
            record.updated_at = datetime.now(timezone.utc)

            if not accepted_gracefully:
                # Treat as minor failure
                record.consecutive_successes = 0
                record.failures_in_7_days += 1
                logger.warning(f"Agent {agent_id} did not gracefully accept override")

            transition = self._check_transitions(record, old_score, old_level)
            self._maybe_persist(agent_id, record)

            return transition

    def record_negative_outcome(
        self,
        agent_id: str,
        outcome_type: str,
        severity: str = "minor",
    ) -> TrustTransition | None:
        """
        Record a negative outcome (security incident, data loss, etc.).

        Args:
            agent_id: The agent responsible
            outcome_type: Type of negative outcome
            severity: "minor" or "critical"

        Returns:
            TrustTransition if demotion occurred
        """
        with self._lock:
            record = self.get_or_create_agent(agent_id)
            old_score = record.trust_score
            old_level = record.current_level

            record.components.record_negative_outcome()
            record.updated_at = datetime.now(timezone.utc)

            if severity == "critical":
                record.critical_failures += 1
                logger.error(
                    f"Critical negative outcome for agent {agent_id}: {outcome_type}"
                )

            transition = self._check_transitions(record, old_score, old_level)
            self._maybe_persist(agent_id, record)

            return transition

    def set_manual_level(
        self,
        agent_id: str,
        level: AutonomyLevel,
        reason: str,
        set_by: str,
    ) -> TrustTransition:
        """
        Manually set an agent's autonomy level (human override).

        Args:
            agent_id: The agent to adjust
            level: The new autonomy level
            reason: Reason for the manual adjustment
            set_by: Identifier of who made the change

        Returns:
            TrustTransition documenting the change
        """
        with self._lock:
            record = self.get_or_create_agent(agent_id)
            old_level = record.effective_level
            old_score = record.trust_score

            record.manually_set_level = level
            record.updated_at = datetime.now(timezone.utc)

            transition = TrustTransition(
                agent_id=agent_id,
                timestamp=datetime.now(timezone.utc),
                old_level=old_level,
                new_level=level,
                old_score=old_score,
                new_score=old_score,  # Score unchanged, just level override
                reason=f"Manual override by {set_by}: {reason}",
                triggered_by="manual",
            )

            record.transition_history.append(transition)

            logger.info(
                f"Manual trust level set for {agent_id}: "
                f"{old_level.name} -> {level.name} by {set_by}"
            )

            if self._on_transition:
                self._on_transition(transition)

            self._maybe_persist(agent_id, record)

            return transition

    def clear_manual_level(self, agent_id: str, reason: str) -> TrustTransition | None:
        """
        Clear a manual level override, returning to calculated level.

        Args:
            agent_id: The agent to adjust
            reason: Reason for clearing the override

        Returns:
            TrustTransition if level changed, None if no manual level was set
        """
        with self._lock:
            record = self.get_or_create_agent(agent_id)

            if record.manually_set_level is None:
                return None

            old_level = record.manually_set_level
            record.manually_set_level = None
            record.updated_at = datetime.now(timezone.utc)

            # Recalculate level from score
            new_level = AutonomyLevel.from_trust_score(record.trust_score)
            record.current_level = new_level

            if old_level != new_level:
                transition = TrustTransition(
                    agent_id=agent_id,
                    timestamp=datetime.now(timezone.utc),
                    old_level=old_level,
                    new_level=new_level,
                    old_score=record.trust_score,
                    new_score=record.trust_score,
                    reason=f"Manual override cleared: {reason}",
                    triggered_by="manual",
                )
                record.transition_history.append(transition)

                if self._on_transition:
                    self._on_transition(transition)

                self._maybe_persist(agent_id, record)
                return transition

            self._maybe_persist(agent_id, record)
            return None

    def _check_transitions(
        self,
        record: AgentTrustRecord,
        old_score: float,
        old_level: AutonomyLevel,
    ) -> TrustTransition | None:
        """Check if trust level should change and apply if so."""
        if record.manually_set_level is not None:
            # Don't auto-transition if manually set
            return None

        new_score = record.trust_score
        should_promote = False
        should_demote = False
        reason = ""

        # Check promotion conditions
        if record.consecutive_successes >= self.PROMOTION_CONSECUTIVE_SUCCESSES:
            should_promote = True
            reason = f"Achieved {record.consecutive_successes} consecutive successes"

        # Check demotion conditions (take priority over promotion)
        if record.critical_failures >= self.DEMOTION_CRITICAL_FAILURES:
            should_demote = True
            reason = f"Critical failure recorded ({record.critical_failures} total)"
        elif record.failures_in_7_days >= self.DEMOTION_MINOR_FAILURES_7D:
            should_demote = True
            reason = f"{record.failures_in_7_days} minor failures in 7 days"

        # Apply transition
        new_level = old_level
        if should_demote and old_level.value > 0:
            new_level = AutonomyLevel(old_level.value - 1)
            # Reset failure counters after demotion
            record.failures_in_7_days = 0
            record.critical_failures = 0
        elif should_promote and old_level.value < 3:
            new_level = AutonomyLevel(old_level.value + 1)
            # Reset success counter after promotion
            record.consecutive_successes = 0

        if new_level != old_level:
            record.current_level = new_level
            transition = TrustTransition(
                agent_id=record.agent_id,
                timestamp=datetime.now(timezone.utc),
                old_level=old_level,
                new_level=new_level,
                old_score=old_score,
                new_score=new_score,
                reason=reason,
                triggered_by="automatic",
            )
            record.transition_history.append(transition)

            logger.info(
                f"Trust transition for {record.agent_id}: "
                f"{old_level.name} -> {new_level.name} ({reason})"
            )

            if self._on_transition:
                self._on_transition(transition)

            return transition

        return None

    def decay_old_failures(self) -> None:
        """
        Decay failure counts older than 7 days.

        Should be called periodically (e.g., daily) to reset
        failures_in_7_days for agents whose failures are old.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            seven_days_ago = now - timedelta(days=7)

            for record in self._agents.values():
                if (
                    record.last_failure_time
                    and record.last_failure_time < seven_days_ago
                ):
                    if record.failures_in_7_days > 0:
                        logger.info(
                            f"Decaying failure count for {record.agent_id}: "
                            f"{record.failures_in_7_days} -> 0"
                        )
                        record.failures_in_7_days = 0

    def get_all_agents(self) -> list[AgentTrustRecord]:
        """Get all agent trust records."""
        with self._lock:
            return list(self._agents.values())

    def get_agents_by_level(self, level: AutonomyLevel) -> list[AgentTrustRecord]:
        """Get all agents at a specific autonomy level."""
        with self._lock:
            return [r for r in self._agents.values() if r.effective_level == level]

    def get_low_trust_agents(self, threshold: float = 0.5) -> list[AgentTrustRecord]:
        """Get agents with trust score below threshold."""
        with self._lock:
            return [r for r in self._agents.values() if r.trust_score < threshold]

    def get_summary(self) -> dict:
        """Get a summary of trust across all agents."""
        with self._lock:
            if not self._agents:
                return {
                    "total_agents": 0,
                    "by_level": {},
                    "avg_trust_score": 0.0,
                    "agents_needing_attention": [],
                }

            # Single-pass bucketing by level, score accumulation, and low-trust detection
            by_level: dict[str, dict] = {
                level.name: {"count": 0, "agents": []} for level in AutonomyLevel
            }
            total_score = 0.0
            low_trust_agents = []

            for record in self._agents.values():
                level_name = record.effective_level.name
                by_level[level_name]["count"] += 1
                by_level[level_name]["agents"].append(record.agent_id)
                total_score += record.trust_score
                if record.trust_score < 0.5:
                    low_trust_agents.append(
                        {"agent_id": record.agent_id, "trust_score": record.trust_score}
                    )

            avg_score = total_score / len(self._agents)

            return {
                "total_agents": len(self._agents),
                "by_level": by_level,
                "avg_trust_score": avg_score,
                "agents_needing_attention": low_trust_agents,
            }

    def _maybe_persist(self, agent_id: str, record: AgentTrustRecord) -> None:
        """Optionally persist trust record if callback is configured."""
        if self._persistence_callback:
            try:
                self._persistence_callback(agent_id, record.to_dict())
            except Exception as e:
                logger.error(f"Failed to persist trust record: {e}")

    def reset_agent(self, agent_id: str) -> None:
        """Reset an agent's trust record to initial state."""
        with self._lock:
            if agent_id in self._agents:
                logger.info(f"Resetting trust record for agent: {agent_id}")
                self._agents[agent_id] = AgentTrustRecord(agent_id=agent_id)
                self._maybe_persist(agent_id, self._agents[agent_id])
