"""
Decision Audit Logger (ADR-052 Phase 1).

Enhanced audit trail with reasoning chains for complete transparency.
Every agent decision is logged with full context, alternatives considered,
and uncertainty disclosure.

Decision Audit Record Structure:
- Decision ID and metadata
- Context (knowledge sources, previous decisions, user instructions)
- Reasoning chain (step-by-step logic)
- Alternatives considered (with confidence scores)
- Uncertainty disclosure (confidence, factors, recommendations)

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class DecisionSeverity(Enum):
    """Severity/importance level of a decision."""

    TRIVIAL = "trivial"  # Minor decisions (formatting, style)
    NORMAL = "normal"  # Standard decisions
    SIGNIFICANT = "significant"  # Important decisions requiring attention
    CRITICAL = "critical"  # Critical decisions with major impact


class DecisionOutcome(Enum):
    """Outcome status of a decision."""

    PENDING = "pending"  # Decision made, outcome not yet known
    SUCCESSFUL = "successful"  # Decision led to positive outcome
    FAILED = "failed"  # Decision led to negative outcome
    OVERRIDDEN = "overridden"  # Decision was overridden by human
    ROLLED_BACK = "rolled_back"  # Decision was rolled back


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain."""

    step_number: int
    description: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 1.0  # 0.0 to 1.0
    references: list[str] = field(default_factory=list)  # File paths, URLs, etc.

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "step": self.step_number,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "references": self.references,
        }


@dataclass
class AlternativeOption:
    """An alternative option that was considered."""

    option_id: str
    description: str
    confidence: float  # 0.0 to 1.0
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    was_chosen: bool = False
    rejection_reason: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "option_id": self.option_id,
            "description": self.description,
            "confidence": self.confidence,
            "pros": self.pros,
            "cons": self.cons,
            "was_chosen": self.was_chosen,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class UncertaintyDisclosure:
    """Disclosure of uncertainty in a decision."""

    overall_confidence: float  # 0.0 to 1.0
    confidence_lower_bound: float = 0.0  # Lower bound of confidence interval
    confidence_upper_bound: float = 1.0  # Upper bound
    uncertainty_factors: list[str] = field(default_factory=list)
    assumptions_made: list[str] = field(default_factory=list)
    validation_recommendations: list[str] = field(default_factory=list)
    potential_failure_modes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "overall_confidence": self.overall_confidence,
            "confidence_interval": {
                "lower": self.confidence_lower_bound,
                "upper": self.confidence_upper_bound,
            },
            "uncertainty_factors": self.uncertainty_factors,
            "assumptions_made": self.assumptions_made,
            "validation_recommendations": self.validation_recommendations,
            "potential_failure_modes": self.potential_failure_modes,
        }


@dataclass
class DecisionContext:
    """Context in which a decision was made."""

    knowledge_sources: list[str] = field(default_factory=list)
    previous_decisions: list[str] = field(default_factory=list)  # Decision IDs
    user_instructions: str = ""
    environmental_factors: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "knowledge_sources": self.knowledge_sources,
            "previous_decisions": self.previous_decisions,
            "user_instructions": self.user_instructions,
            "environmental_factors": self.environmental_factors,
            "constraints": self.constraints,
            "goals": self.goals,
        }


@dataclass
class DecisionRecord:
    """Complete audit record for an agent decision."""

    decision_id: str
    agent_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Decision details
    decision_type: str = ""  # e.g., "code_review", "vulnerability_assessment"
    decision_summary: str = ""  # Brief description
    severity: DecisionSeverity = DecisionSeverity.NORMAL
    outcome: DecisionOutcome = DecisionOutcome.PENDING

    # Transparency components
    context: DecisionContext = field(default_factory=DecisionContext)
    reasoning_chain: list[ReasoningStep] = field(default_factory=list)
    alternatives: list[AlternativeOption] = field(default_factory=list)
    uncertainty: UncertaintyDisclosure = field(
        default_factory=lambda: UncertaintyDisclosure(overall_confidence=1.0)
    )

    # Action taken
    action_taken: str = ""
    action_id: str | None = None  # Links to reversibility system

    # Audit metadata
    checksum: str = ""
    parent_decision_id: str | None = None
    child_decision_ids: list[str] = field(default_factory=list)

    # Human review
    human_reviewed: bool = False
    human_reviewer: str | None = None
    human_review_timestamp: datetime | None = None
    human_comments: str | None = None

    def __post_init__(self) -> None:
        """Calculate checksum after initialization."""
        if not self.checksum:
            self.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate checksum for integrity verification."""
        data = {
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "decision_type": self.decision_type,
            "decision_summary": self.decision_summary,
            "action_taken": self.action_taken,
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode(), usedforsecurity=False).hexdigest()[:16]

    def verify_integrity(self) -> bool:
        """Verify the record hasn't been tampered with."""
        return self.checksum == self._calculate_checksum()

    def has_complete_transparency(self) -> bool:
        """Check if all transparency components are present."""
        return all(
            [
                len(self.reasoning_chain) > 0,
                len(self.context.knowledge_sources) > 0
                or self.context.user_instructions,
                self.uncertainty.overall_confidence > 0,
            ]
        )

    def has_alternatives(self) -> bool:
        """Check if alternatives were presented."""
        return len(self.alternatives) >= 2  # At least chosen + 1 alternative

    def to_dict(self) -> dict:
        """Convert to dictionary for storage/API."""
        return {
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "decision_type": self.decision_type,
            "decision_summary": self.decision_summary,
            "severity": self.severity.value,
            "outcome": self.outcome.value,
            "context": self.context.to_dict(),
            "reasoning_chain": [s.to_dict() for s in self.reasoning_chain],
            "alternatives": [a.to_dict() for a in self.alternatives],
            "uncertainty": self.uncertainty.to_dict(),
            "action_taken": self.action_taken,
            "action_id": self.action_id,
            "checksum": self.checksum,
            "parent_decision_id": self.parent_decision_id,
            "child_decision_ids": self.child_decision_ids,
            "human_reviewed": self.human_reviewed,
            "human_reviewer": self.human_reviewer,
            "human_review_timestamp": (
                self.human_review_timestamp.isoformat()
                if self.human_review_timestamp
                else None
            ),
            "human_comments": self.human_comments,
            "has_complete_transparency": self.has_complete_transparency(),
            "has_alternatives": self.has_alternatives(),
        }


class DecisionAuditLogger:
    """
    Logs agent decisions with complete transparency.

    Ensures every decision has:
    - Full reasoning chain
    - Alternatives considered
    - Uncertainty disclosure
    - Audit trail for compliance
    """

    def __init__(
        self,
        persistence_callback: Callable[[DecisionRecord], None] | None = None,
        require_alternatives: bool = True,
        require_reasoning_chain: bool = True,
        require_uncertainty: bool = True,
    ):
        """
        Initialize the decision audit logger.

        Args:
            persistence_callback: Callback to persist decision records
            require_alternatives: Require alternatives for significant decisions
            require_reasoning_chain: Require reasoning chain for all decisions
            require_uncertainty: Require uncertainty disclosure
        """
        self._persistence_callback = persistence_callback
        self._require_alternatives = require_alternatives
        self._require_reasoning_chain = require_reasoning_chain
        self._require_uncertainty = require_uncertainty

        # In-memory storage (for testing or small deployments)
        self._decisions: dict[str, DecisionRecord] = {}
        self._decisions_by_agent: dict[str, list[str]] = {}
        self._lock = threading.RLock()

        # Metrics
        self._total_decisions = 0
        self._decisions_with_full_transparency = 0
        self._decisions_with_alternatives = 0
        self._decisions_overridden = 0

        logger.info("DecisionAuditLogger initialized")

    def create_decision_record(
        self,
        decision_id: str,
        agent_id: str,
        decision_type: str,
        decision_summary: str,
        severity: DecisionSeverity = DecisionSeverity.NORMAL,
    ) -> DecisionRecord:
        """
        Create a new decision record.

        Args:
            decision_id: Unique identifier for the decision
            agent_id: The agent making the decision
            decision_type: Category of decision
            decision_summary: Brief description
            severity: Importance level

        Returns:
            New DecisionRecord to be populated with transparency components
        """
        record = DecisionRecord(
            decision_id=decision_id,
            agent_id=agent_id,
            decision_type=decision_type,
            decision_summary=decision_summary,
            severity=severity,
        )
        return record

    def add_context(
        self,
        record: DecisionRecord,
        knowledge_sources: list[str] | None = None,
        previous_decisions: list[str] | None = None,
        user_instructions: str = "",
        environmental_factors: dict[str, Any] | None = None,
        constraints: list[str] | None = None,
        goals: list[str] | None = None,
    ) -> DecisionRecord:
        """Add context to a decision record."""
        if knowledge_sources:
            record.context.knowledge_sources = knowledge_sources
        if previous_decisions:
            record.context.previous_decisions = previous_decisions
        if user_instructions:
            record.context.user_instructions = user_instructions
        if environmental_factors:
            record.context.environmental_factors = environmental_factors
        if constraints:
            record.context.constraints = constraints
        if goals:
            record.context.goals = goals
        return record

    def add_reasoning_step(
        self,
        record: DecisionRecord,
        step_number: int,
        description: str,
        evidence: list[str] | None = None,
        confidence: float = 1.0,
        references: list[str] | None = None,
    ) -> DecisionRecord:
        """Add a reasoning step to the decision chain."""
        step = ReasoningStep(
            step_number=step_number,
            description=description,
            evidence=evidence or [],
            confidence=confidence,
            references=references or [],
        )
        record.reasoning_chain.append(step)
        # Keep sorted by step number
        record.reasoning_chain.sort(key=lambda s: s.step_number)
        return record

    def add_alternative(
        self,
        record: DecisionRecord,
        option_id: str,
        description: str,
        confidence: float,
        pros: list[str] | None = None,
        cons: list[str] | None = None,
        was_chosen: bool = False,
        rejection_reason: str | None = None,
    ) -> DecisionRecord:
        """Add an alternative option that was considered."""
        alternative = AlternativeOption(
            option_id=option_id,
            description=description,
            confidence=confidence,
            pros=pros or [],
            cons=cons or [],
            was_chosen=was_chosen,
            rejection_reason=rejection_reason,
        )
        record.alternatives.append(alternative)
        return record

    def set_uncertainty(
        self,
        record: DecisionRecord,
        overall_confidence: float,
        confidence_lower_bound: float | None = None,
        confidence_upper_bound: float | None = None,
        uncertainty_factors: list[str] | None = None,
        assumptions_made: list[str] | None = None,
        validation_recommendations: list[str] | None = None,
        potential_failure_modes: list[str] | None = None,
    ) -> DecisionRecord:
        """Set uncertainty disclosure for the decision."""
        record.uncertainty = UncertaintyDisclosure(
            overall_confidence=overall_confidence,
            confidence_lower_bound=confidence_lower_bound or overall_confidence - 0.1,
            confidence_upper_bound=confidence_upper_bound
            or min(1.0, overall_confidence + 0.1),
            uncertainty_factors=uncertainty_factors or [],
            assumptions_made=assumptions_made or [],
            validation_recommendations=validation_recommendations or [],
            potential_failure_modes=potential_failure_modes or [],
        )
        return record

    def set_action(
        self,
        record: DecisionRecord,
        action_taken: str,
        action_id: str | None = None,
    ) -> DecisionRecord:
        """Set the action that was taken based on the decision."""
        record.action_taken = action_taken
        record.action_id = action_id
        return record

    def validate_record(self, record: DecisionRecord) -> tuple[bool, list[str]]:
        """
        Validate that a decision record meets transparency requirements.

        Args:
            record: The decision record to validate

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check reasoning chain
        if self._require_reasoning_chain and len(record.reasoning_chain) == 0:
            issues.append("Missing reasoning chain")

        # Check alternatives for significant/critical decisions
        if self._require_alternatives:
            if record.severity in (
                DecisionSeverity.SIGNIFICANT,
                DecisionSeverity.CRITICAL,
            ):
                if not record.has_alternatives():
                    issues.append(
                        f"Significant decision requires alternatives "
                        f"(found {len(record.alternatives)}, need >= 2)"
                    )

        # Check uncertainty
        if self._require_uncertainty:
            if record.uncertainty.overall_confidence <= 0:
                issues.append("Missing uncertainty disclosure")

        # Check context
        if (
            not record.context.knowledge_sources
            and not record.context.user_instructions
        ):
            issues.append("Missing context (no knowledge sources or user instructions)")

        return len(issues) == 0, issues

    def log_decision(
        self,
        record: DecisionRecord,
        force: bool = False,
    ) -> tuple[bool, list[str]]:
        """
        Log a decision record.

        Args:
            record: The complete decision record
            force: Log even if validation fails (logs warning)

        Returns:
            Tuple of (success, list of issues if any)
        """
        is_valid, issues = self.validate_record(record)

        if not is_valid and not force:
            logger.warning(f"Decision {record.decision_id} failed validation: {issues}")
            return False, issues

        if not is_valid and force:
            logger.warning(
                f"Forcing log of decision {record.decision_id} despite issues: {issues}"
            )

        with self._lock:
            # Recalculate checksum before storing
            record.checksum = record._calculate_checksum()

            # Store
            self._decisions[record.decision_id] = record

            # Index by agent
            if record.agent_id not in self._decisions_by_agent:
                self._decisions_by_agent[record.agent_id] = []
            self._decisions_by_agent[record.agent_id].append(record.decision_id)

            # Update metrics
            self._total_decisions += 1
            if record.has_complete_transparency():
                self._decisions_with_full_transparency += 1
            if record.has_alternatives():
                self._decisions_with_alternatives += 1

            # Persist
            if self._persistence_callback:
                try:
                    self._persistence_callback(record)
                except Exception as e:
                    logger.error(f"Failed to persist decision record: {e}")

            logger.debug(
                f"Logged decision {record.decision_id} from agent {record.agent_id}"
            )

        return True, issues

    def update_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        outcome_details: str = "",
    ) -> bool:
        """
        Update the outcome of a logged decision.

        Args:
            decision_id: The decision to update
            outcome: The outcome status
            outcome_details: Additional details about the outcome

        Returns:
            True if update succeeded
        """
        with self._lock:
            if decision_id not in self._decisions:
                logger.warning(f"Decision {decision_id} not found for outcome update")
                return False

            record = self._decisions[decision_id]
            record.outcome = outcome

            if outcome == DecisionOutcome.OVERRIDDEN:
                self._decisions_overridden += 1

            logger.info(
                f"Updated decision {decision_id} outcome to {outcome.value}: {outcome_details}"
            )

            if self._persistence_callback:
                try:
                    self._persistence_callback(record)
                except Exception as e:
                    logger.error(f"Failed to persist outcome update: {e}")

            return True

    def record_human_review(
        self,
        decision_id: str,
        reviewer: str,
        comments: str = "",
        override_outcome: DecisionOutcome | None = None,
    ) -> bool:
        """
        Record that a decision was reviewed by a human.

        Args:
            decision_id: The decision that was reviewed
            reviewer: Identifier of the reviewer
            comments: Review comments
            override_outcome: If set, override the decision outcome

        Returns:
            True if recording succeeded
        """
        with self._lock:
            if decision_id not in self._decisions:
                logger.warning(f"Decision {decision_id} not found for human review")
                return False

            record = self._decisions[decision_id]
            record.human_reviewed = True
            record.human_reviewer = reviewer
            record.human_review_timestamp = datetime.now(timezone.utc)
            record.human_comments = comments

            if override_outcome:
                record.outcome = override_outcome
                self._decisions_overridden += 1

            logger.info(
                f"Decision {decision_id} reviewed by {reviewer}"
                + (
                    f" - outcome changed to {override_outcome.value}"
                    if override_outcome
                    else ""
                )
            )

            if self._persistence_callback:
                try:
                    self._persistence_callback(record)
                except Exception as e:
                    logger.error(f"Failed to persist human review: {e}")

            return True

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        """Get a decision record by ID."""
        with self._lock:
            return self._decisions.get(decision_id)

    def get_decisions_by_agent(
        self,
        agent_id: str,
        limit: int = 100,
    ) -> list[DecisionRecord]:
        """Get recent decisions by a specific agent."""
        with self._lock:
            decision_ids = self._decisions_by_agent.get(agent_id, [])
            decisions = [
                self._decisions[did]
                for did in decision_ids[-limit:]
                if did in self._decisions
            ]
            return sorted(decisions, key=lambda d: d.timestamp, reverse=True)

    def get_decisions_needing_review(
        self,
        severity_threshold: DecisionSeverity = DecisionSeverity.SIGNIFICANT,
    ) -> list[DecisionRecord]:
        """Get unreviewed decisions at or above severity threshold."""
        with self._lock:
            threshold_value = list(DecisionSeverity).index(severity_threshold)
            return [
                d
                for d in self._decisions.values()
                if not d.human_reviewed
                and list(DecisionSeverity).index(d.severity) >= threshold_value
            ]

    def get_overridden_decisions(
        self,
        since: datetime | None = None,
    ) -> list[DecisionRecord]:
        """Get decisions that were overridden by humans."""
        with self._lock:
            since = since or (datetime.now(timezone.utc) - timedelta(days=30))
            return [
                d
                for d in self._decisions.values()
                if d.outcome == DecisionOutcome.OVERRIDDEN and d.timestamp >= since
            ]

    def get_metrics(self) -> dict:
        """Get audit logging metrics."""
        with self._lock:
            return {
                "total_decisions": self._total_decisions,
                "decisions_with_full_transparency": self._decisions_with_full_transparency,
                "transparency_rate": (
                    self._decisions_with_full_transparency / self._total_decisions
                    if self._total_decisions > 0
                    else 1.0
                ),
                "decisions_with_alternatives": self._decisions_with_alternatives,
                "alternatives_rate": (
                    self._decisions_with_alternatives / self._total_decisions
                    if self._total_decisions > 0
                    else 1.0
                ),
                "decisions_overridden": self._decisions_overridden,
                "override_rate": (
                    self._decisions_overridden / self._total_decisions
                    if self._total_decisions > 0
                    else 0.0
                ),
                "decisions_stored": len(self._decisions),
                "agents_tracked": len(self._decisions_by_agent),
            }

    def export_decisions(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        agent_id: str | None = None,
    ) -> list[dict]:
        """
        Export decisions for external audit.

        Args:
            since: Start of time range
            until: End of time range
            agent_id: Filter by specific agent

        Returns:
            List of decision records as dictionaries
        """
        with self._lock:
            decisions = list(self._decisions.values())

            if since:
                decisions = [d for d in decisions if d.timestamp >= since]
            if until:
                decisions = [d for d in decisions if d.timestamp <= until]
            if agent_id:
                decisions = [d for d in decisions if d.agent_id == agent_id]

            return [d.to_dict() for d in sorted(decisions, key=lambda d: d.timestamp)]

    def clear_old_decisions(
        self,
        older_than: timedelta | None = None,
    ) -> int:
        """
        Clear decisions older than specified duration.

        Args:
            older_than: Duration threshold (default: 90 days)

        Returns:
            Number of decisions cleared
        """
        if older_than is None:
            older_than = timedelta(days=90)
        with self._lock:
            cutoff = datetime.now(timezone.utc) - older_than
            old_ids = [
                did for did, d in self._decisions.items() if d.timestamp < cutoff
            ]

            for did in old_ids:
                record = self._decisions.pop(did)
                # Remove from agent index
                if record.agent_id in self._decisions_by_agent:
                    try:
                        self._decisions_by_agent[record.agent_id].remove(did)
                    except ValueError:
                        pass

            if old_ids:
                logger.info(f"Cleared {len(old_ids)} old decision records")

            return len(old_ids)
