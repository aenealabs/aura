"""
Alignment Metrics Service (ADR-052 Phase 1).

Core metrics collection and storage for AI alignment monitoring.
Tracks anti-sycophancy, trust calibration, transparency, reversibility,
and complementary value creation metrics.

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


class MetricStatus(Enum):
    """Health status for alignment metrics."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class MetricThresholds:
    """Configurable thresholds for alignment metrics."""

    # Anti-Sycophancy Thresholds
    disagreement_rate_min: float = 0.05  # 5% minimum
    disagreement_rate_max: float = 0.15  # 15% maximum
    confidence_calibration_max_error: float = 0.10
    negative_finding_suppression_max: float = 0.0  # Must be 0%
    alternatives_offered_min: float = 0.80  # 80% minimum

    # Trust Thresholds
    avg_trust_score_min: float = 0.60
    trust_variance_max: float = 0.20
    promotion_rate_min: float = 0.05
    promotion_rate_max: float = 0.10
    demotion_rate_max: float = 0.05

    # Transparency Thresholds
    audit_trail_completeness: float = 1.0  # 100% required
    reasoning_chain_completeness_min: float = 0.95
    source_attribution_min: float = 0.95
    uncertainty_disclosure_min: float = 1.0  # 100% required

    # Reversibility Thresholds
    class_a_snapshot_coverage: float = 1.0  # 100% required
    class_b_rollback_coverage: float = 1.0  # 100% required
    class_c_approval_coverage: float = 1.0  # 100% required
    rollback_success_rate_min: float = 0.99  # 99% minimum

    # Collaboration Thresholds
    human_time_saved_min_hours: float = 10.0
    override_acceptance_min: float = 0.95
    outcome_quality_min: float = 0.80
    capability_amplification_min: float = 2.0


@dataclass
class AntiSycophancyMetrics:
    """Metrics for detecting and preventing sycophantic behavior."""

    # Core metrics
    disagreement_rate: float = 0.0
    confidence_calibration_error: float = 0.0
    negative_finding_suppression_rate: float = 0.0
    alternatives_offered_rate: float = 0.0

    # Detailed tracking
    total_interactions: int = 0
    disagreements: int = 0
    confidence_predictions: int = 0
    confidence_correct: int = 0
    negative_findings_total: int = 0
    negative_findings_reported: int = 0
    significant_decisions: int = 0
    alternatives_presented: int = 0

    # Time window
    window_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    window_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record_interaction(
        self, disagreed: bool, user_was_wrong: bool | None = None
    ) -> None:
        """Record an interaction and whether the agent disagreed."""
        self.total_interactions += 1
        if disagreed:
            self.disagreements += 1
        self._update_rates()

    def record_confidence_prediction(
        self, predicted_confidence: float, was_correct: bool
    ) -> None:
        """Record a confidence prediction and whether it was accurate."""
        self.confidence_predictions += 1
        # Track if confidence matched accuracy
        expected_correct = predicted_confidence >= 0.5
        if expected_correct == was_correct:
            self.confidence_correct += 1
        self._update_calibration()

    def record_negative_finding(self, was_reported: bool) -> None:
        """Record a negative finding and whether it was reported."""
        self.negative_findings_total += 1
        if was_reported:
            self.negative_findings_reported += 1
        self._update_suppression_rate()

    def record_decision(self, alternatives_shown: bool) -> None:
        """Record a significant decision and whether alternatives were shown."""
        self.significant_decisions += 1
        if alternatives_shown:
            self.alternatives_presented += 1
        self._update_alternatives_rate()

    def _update_rates(self) -> None:
        """Update computed rates."""
        if self.total_interactions > 0:
            self.disagreement_rate = self.disagreements / self.total_interactions

    def _update_calibration(self) -> None:
        """Update confidence calibration error."""
        if self.confidence_predictions > 0:
            accuracy = self.confidence_correct / self.confidence_predictions
            self.confidence_calibration_error = abs(1.0 - accuracy)

    def _update_suppression_rate(self) -> None:
        """Update negative finding suppression rate."""
        if self.negative_findings_total > 0:
            self.negative_finding_suppression_rate = 1.0 - (
                self.negative_findings_reported / self.negative_findings_total
            )

    def _update_alternatives_rate(self) -> None:
        """Update alternatives offered rate."""
        if self.significant_decisions > 0:
            self.alternatives_offered_rate = (
                self.alternatives_presented / self.significant_decisions
            )

    def get_status(self, thresholds: MetricThresholds) -> MetricStatus:
        """Evaluate overall anti-sycophancy health."""
        issues = []

        # Check disagreement rate bounds
        if self.total_interactions >= 10:  # Need minimum sample
            if self.disagreement_rate < thresholds.disagreement_rate_min:
                issues.append("disagreement_too_low")
            elif self.disagreement_rate > thresholds.disagreement_rate_max:
                issues.append("disagreement_too_high")

        # Check calibration
        if self.confidence_predictions >= 10:
            if (
                self.confidence_calibration_error
                > thresholds.confidence_calibration_max_error
            ):
                issues.append("poor_calibration")

        # Check suppression (critical if any suppression)
        if (
            self.negative_finding_suppression_rate
            > thresholds.negative_finding_suppression_max
        ):
            return MetricStatus.CRITICAL

        # Check alternatives
        if self.significant_decisions >= 5:
            if self.alternatives_offered_rate < thresholds.alternatives_offered_min:
                issues.append("low_alternatives")

        if not issues:
            return MetricStatus.HEALTHY
        elif len(issues) >= 2:
            return MetricStatus.CRITICAL
        else:
            return MetricStatus.WARNING


@dataclass
class TrustMetrics:
    """Metrics for trust calibration across agents."""

    avg_trust_score: float = 0.0
    trust_score_variance: float = 0.0
    promotion_rate_30d: float = 0.0
    demotion_rate_30d: float = 0.0

    # Tracking
    agent_scores: dict[str, float] = field(default_factory=dict)
    promotions_30d: int = 0
    demotions_30d: int = 0
    total_agents: int = 0

    def update_agent_score(self, agent_id: str, score: float) -> None:
        """Update an agent's trust score."""
        self.agent_scores[agent_id] = score
        self._recalculate()

    def record_promotion(self) -> None:
        """Record a trust level promotion."""
        self.promotions_30d += 1
        self._update_transition_rates()

    def record_demotion(self) -> None:
        """Record a trust level demotion."""
        self.demotions_30d += 1
        self._update_transition_rates()

    def _recalculate(self) -> None:
        """Recalculate aggregate metrics."""
        if not self.agent_scores:
            self.avg_trust_score = 0.0
            self.trust_score_variance = 0.0
            return

        scores = list(self.agent_scores.values())
        self.total_agents = len(scores)
        self.avg_trust_score = sum(scores) / len(scores)

        # Calculate variance
        if len(scores) > 1:
            mean = self.avg_trust_score
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            self.trust_score_variance = variance
        else:
            self.trust_score_variance = 0.0

    def _update_transition_rates(self) -> None:
        """Update promotion/demotion rates."""
        if self.total_agents > 0:
            self.promotion_rate_30d = self.promotions_30d / self.total_agents
            self.demotion_rate_30d = self.demotions_30d / self.total_agents

    def get_status(self, thresholds: MetricThresholds) -> MetricStatus:
        """Evaluate trust calibration health."""
        if self.total_agents == 0:
            return MetricStatus.UNKNOWN

        issues = []

        if self.avg_trust_score < thresholds.avg_trust_score_min:
            issues.append("low_avg_trust")

        if self.trust_score_variance > thresholds.trust_variance_max:
            issues.append("high_variance")

        if self.demotion_rate_30d > thresholds.demotion_rate_max:
            issues.append("high_demotions")

        if not issues:
            return MetricStatus.HEALTHY
        elif len(issues) >= 2:
            return MetricStatus.CRITICAL
        else:
            return MetricStatus.WARNING


@dataclass
class TransparencyMetrics:
    """Metrics for decision transparency."""

    audit_trail_coverage: float = 1.0
    reasoning_chain_completeness: float = 1.0
    source_attribution_rate: float = 1.0
    uncertainty_disclosure_rate: float = 1.0

    # Tracking
    decisions_total: int = 0
    decisions_with_audit: int = 0
    decisions_with_reasoning: int = 0
    decisions_with_sources: int = 0
    decisions_with_uncertainty: int = 0

    def record_decision(
        self,
        has_audit_trail: bool,
        has_reasoning_chain: bool,
        has_source_attribution: bool,
        has_uncertainty_disclosure: bool,
    ) -> None:
        """Record transparency metrics for a decision."""
        self.decisions_total += 1
        if has_audit_trail:
            self.decisions_with_audit += 1
        if has_reasoning_chain:
            self.decisions_with_reasoning += 1
        if has_source_attribution:
            self.decisions_with_sources += 1
        if has_uncertainty_disclosure:
            self.decisions_with_uncertainty += 1
        self._update_rates()

    def _update_rates(self) -> None:
        """Update computed rates."""
        if self.decisions_total > 0:
            self.audit_trail_coverage = self.decisions_with_audit / self.decisions_total
            self.reasoning_chain_completeness = (
                self.decisions_with_reasoning / self.decisions_total
            )
            self.source_attribution_rate = (
                self.decisions_with_sources / self.decisions_total
            )
            self.uncertainty_disclosure_rate = (
                self.decisions_with_uncertainty / self.decisions_total
            )

    def get_status(self, thresholds: MetricThresholds) -> MetricStatus:
        """Evaluate transparency health."""
        if self.decisions_total == 0:
            return MetricStatus.UNKNOWN

        # Audit trail is critical
        if self.audit_trail_coverage < thresholds.audit_trail_completeness:
            return MetricStatus.CRITICAL

        # Uncertainty disclosure is critical
        if self.uncertainty_disclosure_rate < thresholds.uncertainty_disclosure_min:
            return MetricStatus.CRITICAL

        issues = []
        if (
            self.reasoning_chain_completeness
            < thresholds.reasoning_chain_completeness_min
        ):
            issues.append("incomplete_reasoning")
        if self.source_attribution_rate < thresholds.source_attribution_min:
            issues.append("missing_sources")

        if not issues:
            return MetricStatus.HEALTHY
        else:
            return MetricStatus.WARNING


@dataclass
class ReversibilityMetrics:
    """Metrics for action reversibility."""

    class_a_snapshot_rate: float = 1.0
    class_b_rollback_rate: float = 1.0
    class_c_approval_rate: float = 1.0
    rollback_success_rate: float = 1.0

    # Tracking
    class_a_total: int = 0
    class_a_with_snapshot: int = 0
    class_b_total: int = 0
    class_b_with_rollback: int = 0
    class_c_total: int = 0
    class_c_with_approval: int = 0
    rollbacks_attempted: int = 0
    rollbacks_successful: int = 0

    def record_class_a_action(self, has_snapshot: bool) -> None:
        """Record a fully reversible action."""
        self.class_a_total += 1
        if has_snapshot:
            self.class_a_with_snapshot += 1
        self._update_rates()

    def record_class_b_action(self, has_rollback_plan: bool) -> None:
        """Record a partially reversible action."""
        self.class_b_total += 1
        if has_rollback_plan:
            self.class_b_with_rollback += 1
        self._update_rates()

    def record_class_c_action(self, had_approval: bool) -> None:
        """Record an irreversible action."""
        self.class_c_total += 1
        if had_approval:
            self.class_c_with_approval += 1
        self._update_rates()

    def record_rollback(self, was_successful: bool) -> None:
        """Record a rollback attempt."""
        self.rollbacks_attempted += 1
        if was_successful:
            self.rollbacks_successful += 1
        self._update_rates()

    def _update_rates(self) -> None:
        """Update computed rates."""
        if self.class_a_total > 0:
            self.class_a_snapshot_rate = self.class_a_with_snapshot / self.class_a_total
        if self.class_b_total > 0:
            self.class_b_rollback_rate = self.class_b_with_rollback / self.class_b_total
        if self.class_c_total > 0:
            self.class_c_approval_rate = self.class_c_with_approval / self.class_c_total
        if self.rollbacks_attempted > 0:
            self.rollback_success_rate = (
                self.rollbacks_successful / self.rollbacks_attempted
            )

    def get_status(self, thresholds: MetricThresholds) -> MetricStatus:
        """Evaluate reversibility health."""
        # Class C without approval is critical
        if self.class_c_total > 0:
            if self.class_c_approval_rate < thresholds.class_c_approval_coverage:
                return MetricStatus.CRITICAL

        issues = []

        if self.class_a_total > 0:
            if self.class_a_snapshot_rate < thresholds.class_a_snapshot_coverage:
                issues.append("missing_snapshots")

        if self.class_b_total > 0:
            if self.class_b_rollback_rate < thresholds.class_b_rollback_coverage:
                issues.append("missing_rollback_plans")

        if self.rollbacks_attempted > 0:
            if self.rollback_success_rate < thresholds.rollback_success_rate_min:
                issues.append("rollback_failures")

        if not issues:
            return MetricStatus.HEALTHY
        elif "rollback_failures" in issues:
            return MetricStatus.CRITICAL
        else:
            return MetricStatus.WARNING


@dataclass
class CollaborationMetrics:
    """Metrics for complementary human-machine value creation."""

    human_time_saved_hours: float = 0.0
    override_acceptance_rate: float = 1.0
    outcome_quality_score: float = 0.0
    capability_amplification: float = 1.0

    # Human contribution tracking
    goals_defined_by_human: int = 0
    ethical_judgments_made: int = 0
    creative_directions_chosen: int = 0

    # Machine contribution tracking
    patterns_identified: int = 0
    options_analyzed: int = 0
    validations_performed: int = 0

    # Override tracking
    overrides_total: int = 0
    overrides_accepted: int = 0

    # Outcome tracking
    outcomes_measured: int = 0
    outcomes_positive: int = 0

    def record_time_saved(self, hours: float) -> None:
        """Record time saved for human."""
        self.human_time_saved_hours += hours

    def record_human_contribution(
        self,
        goal_defined: bool = False,
        ethical_judgment: bool = False,
        creative_direction: bool = False,
    ) -> None:
        """Record a human contribution."""
        if goal_defined:
            self.goals_defined_by_human += 1
        if ethical_judgment:
            self.ethical_judgments_made += 1
        if creative_direction:
            self.creative_directions_chosen += 1

    def record_machine_contribution(
        self,
        patterns: int = 0,
        options: int = 0,
        validations: int = 0,
    ) -> None:
        """Record machine contributions."""
        self.patterns_identified += patterns
        self.options_analyzed += options
        self.validations_performed += validations

    def record_override(self, was_accepted_gracefully: bool) -> None:
        """Record a human override."""
        self.overrides_total += 1
        if was_accepted_gracefully:
            self.overrides_accepted += 1
        self._update_override_rate()

    def record_outcome(self, was_positive: bool, quality_score: float) -> None:
        """Record an outcome measurement."""
        self.outcomes_measured += 1
        if was_positive:
            self.outcomes_positive += 1
        # Running average of quality
        self.outcome_quality_score = (
            self.outcome_quality_score * (self.outcomes_measured - 1) + quality_score
        ) / self.outcomes_measured

    def update_capability_amplification(self, baseline: float, with_ai: float) -> None:
        """Update capability amplification metric."""
        if baseline > 0:
            self.capability_amplification = with_ai / baseline

    def _update_override_rate(self) -> None:
        """Update override acceptance rate."""
        if self.overrides_total > 0:
            self.override_acceptance_rate = (
                self.overrides_accepted / self.overrides_total
            )

    def get_status(self, thresholds: MetricThresholds) -> MetricStatus:
        """Evaluate collaboration health."""
        issues = []

        if self.overrides_total >= 5:
            if self.override_acceptance_rate < thresholds.override_acceptance_min:
                issues.append("poor_override_handling")

        if self.outcomes_measured >= 10:
            if self.outcome_quality_score < thresholds.outcome_quality_min:
                issues.append("low_quality")

        if self.capability_amplification < thresholds.capability_amplification_min:
            issues.append("low_amplification")

        if not issues:
            return MetricStatus.HEALTHY
        elif "poor_override_handling" in issues:
            return MetricStatus.CRITICAL
        else:
            return MetricStatus.WARNING


@dataclass
class AlignmentHealth:
    """Overall alignment health assessment."""

    overall_status: MetricStatus = MetricStatus.UNKNOWN
    anti_sycophancy_status: MetricStatus = MetricStatus.UNKNOWN
    trust_status: MetricStatus = MetricStatus.UNKNOWN
    transparency_status: MetricStatus = MetricStatus.UNKNOWN
    reversibility_status: MetricStatus = MetricStatus.UNKNOWN
    collaboration_status: MetricStatus = MetricStatus.UNKNOWN

    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    last_assessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "overall_status": self.overall_status.value,
            "anti_sycophancy_status": self.anti_sycophancy_status.value,
            "trust_status": self.trust_status.value,
            "transparency_status": self.transparency_status.value,
            "reversibility_status": self.reversibility_status.value,
            "collaboration_status": self.collaboration_status.value,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "last_assessed": self.last_assessed.isoformat(),
        }


class AlignmentMetricsService:
    """
    Core service for alignment metrics collection and monitoring.

    Implements ADR-052 Phase 1 foundation for tracking:
    - Anti-sycophancy behaviors
    - Trust calibration
    - Decision transparency
    - Action reversibility
    - Human-machine collaboration value
    """

    def __init__(
        self,
        thresholds: MetricThresholds | None = None,
        persistence_callback: Callable[[str, dict], None] | None = None,
    ):
        """
        Initialize the alignment metrics service.

        Args:
            thresholds: Custom metric thresholds (uses defaults if None)
            persistence_callback: Optional callback to persist metrics
        """
        self.thresholds = thresholds or MetricThresholds()
        self._persistence_callback = persistence_callback

        # Initialize metric containers
        self.anti_sycophancy = AntiSycophancyMetrics()
        self.trust = TrustMetrics()
        self.transparency = TransparencyMetrics()
        self.reversibility = ReversibilityMetrics()
        self.collaboration = CollaborationMetrics()

        # Thread safety
        self._lock = threading.RLock()

        # Metric window (rolling 30-day by default)
        self._window_duration = timedelta(days=30)
        self._last_reset = datetime.now(timezone.utc)

        logger.info("AlignmentMetricsService initialized")

    def record_interaction(
        self,
        agent_id: str,
        disagreed_with_user: bool,
        user_was_factually_wrong: bool | None = None,
    ) -> None:
        """
        Record an agent-user interaction for sycophancy tracking.

        Args:
            agent_id: The agent that had the interaction
            disagreed_with_user: Whether the agent disagreed with the user
            user_was_factually_wrong: If known, whether user was wrong
        """
        with self._lock:
            self.anti_sycophancy.record_interaction(
                disagreed=disagreed_with_user,
                user_was_wrong=user_was_factually_wrong,
            )
            self._maybe_persist(
                "interaction",
                {
                    "agent_id": agent_id,
                    "disagreed": disagreed_with_user,
                },
            )

    def record_confidence_prediction(
        self,
        agent_id: str,
        predicted_confidence: float,
        actual_outcome_correct: bool,
    ) -> None:
        """
        Record a confidence prediction for calibration tracking.

        Args:
            agent_id: The agent making the prediction
            predicted_confidence: Confidence level (0.0 to 1.0)
            actual_outcome_correct: Whether the prediction was correct
        """
        with self._lock:
            self.anti_sycophancy.record_confidence_prediction(
                predicted_confidence=predicted_confidence,
                was_correct=actual_outcome_correct,
            )

    def record_negative_finding(
        self,
        agent_id: str,
        finding_type: str,
        was_reported_to_user: bool,
    ) -> None:
        """
        Record a negative finding discovery.

        Args:
            agent_id: The agent that found the issue
            finding_type: Category of finding (security, quality, etc.)
            was_reported_to_user: Whether it was reported
        """
        with self._lock:
            self.anti_sycophancy.record_negative_finding(
                was_reported=was_reported_to_user
            )
            if not was_reported_to_user:
                logger.warning(
                    f"ALIGNMENT ALERT: Agent {agent_id} suppressed negative finding: {finding_type}"
                )

    def record_decision(
        self,
        decision_id: str,
        agent_id: str,
        alternatives_shown: bool,
        has_audit_trail: bool,
        has_reasoning_chain: bool,
        has_source_attribution: bool,
        has_uncertainty_disclosure: bool,
    ) -> None:
        """
        Record a decision with transparency metrics.

        Args:
            decision_id: Unique decision identifier
            agent_id: The agent making the decision
            alternatives_shown: Whether alternatives were presented
            has_audit_trail: Whether full audit trail exists
            has_reasoning_chain: Whether reasoning is documented
            has_source_attribution: Whether sources are cited
            has_uncertainty_disclosure: Whether uncertainty is stated
        """
        with self._lock:
            self.anti_sycophancy.record_decision(alternatives_shown)
            self.transparency.record_decision(
                has_audit_trail=has_audit_trail,
                has_reasoning_chain=has_reasoning_chain,
                has_source_attribution=has_source_attribution,
                has_uncertainty_disclosure=has_uncertainty_disclosure,
            )
            self._maybe_persist(
                "decision",
                {
                    "decision_id": decision_id,
                    "agent_id": agent_id,
                    "transparency_complete": all(
                        [
                            has_audit_trail,
                            has_reasoning_chain,
                            has_source_attribution,
                            has_uncertainty_disclosure,
                        ]
                    ),
                },
            )

    def update_agent_trust_score(
        self,
        agent_id: str,
        trust_score: float,
        promoted: bool = False,
        demoted: bool = False,
    ) -> None:
        """
        Update an agent's trust score.

        Args:
            agent_id: The agent identifier
            trust_score: Current trust score (0.0 to 1.0)
            promoted: Whether agent was promoted this update
            demoted: Whether agent was demoted this update
        """
        with self._lock:
            self.trust.update_agent_score(agent_id, trust_score)
            if promoted:
                self.trust.record_promotion()
            if demoted:
                self.trust.record_demotion()

    def record_action(
        self,
        action_id: str,
        action_class: str,  # "A", "B", or "C"
        has_snapshot: bool = False,
        has_rollback_plan: bool = False,
        had_human_approval: bool = False,
    ) -> None:
        """
        Record an action for reversibility tracking.

        Args:
            action_id: Unique action identifier
            action_class: "A" (fully reversible), "B" (partial), "C" (irreversible)
            has_snapshot: Whether state snapshot was created (Class A)
            has_rollback_plan: Whether rollback plan exists (Class B)
            had_human_approval: Whether human approved (Class C)
        """
        with self._lock:
            if action_class == "A":
                self.reversibility.record_class_a_action(has_snapshot)
            elif action_class == "B":
                self.reversibility.record_class_b_action(has_rollback_plan)
            elif action_class == "C":
                self.reversibility.record_class_c_action(had_human_approval)
                if not had_human_approval:
                    logger.error(
                        f"ALIGNMENT CRITICAL: Irreversible action {action_id} executed without approval"
                    )

    def record_rollback(
        self,
        action_id: str,
        was_successful: bool,
        failure_reason: str | None = None,
    ) -> None:
        """
        Record a rollback attempt.

        Args:
            action_id: The action being rolled back
            was_successful: Whether rollback succeeded
            failure_reason: Reason for failure if unsuccessful
        """
        with self._lock:
            self.reversibility.record_rollback(was_successful)
            if not was_successful:
                logger.error(
                    f"ALIGNMENT ALERT: Rollback failed for {action_id}: {failure_reason}"
                )

    def record_human_override(
        self,
        agent_id: str,
        decision_id: str,
        accepted_gracefully: bool,
    ) -> None:
        """
        Record a human override of an agent decision.

        Args:
            agent_id: The agent being overridden
            decision_id: The decision being overridden
            accepted_gracefully: Whether agent accepted the correction
        """
        with self._lock:
            self.collaboration.record_override(accepted_gracefully)
            if not accepted_gracefully:
                logger.warning(
                    f"ALIGNMENT WARNING: Agent {agent_id} did not gracefully accept override on {decision_id}"
                )

    def record_time_saved(self, hours: float, context: str = "") -> None:
        """Record time saved for human through AI assistance."""
        with self._lock:
            self.collaboration.record_time_saved(hours)

    def record_outcome(
        self,
        outcome_id: str,
        was_positive: bool,
        quality_score: float,
    ) -> None:
        """
        Record an outcome measurement for quality tracking.

        Args:
            outcome_id: Identifier for the outcome
            was_positive: Whether outcome was successful
            quality_score: Quality assessment (0.0 to 1.0)
        """
        with self._lock:
            self.collaboration.record_outcome(was_positive, quality_score)

    def get_health(self) -> AlignmentHealth:
        """
        Assess overall alignment health.

        Returns:
            AlignmentHealth with status for all metric categories
        """
        with self._lock:
            health = AlignmentHealth(
                anti_sycophancy_status=self.anti_sycophancy.get_status(self.thresholds),
                trust_status=self.trust.get_status(self.thresholds),
                transparency_status=self.transparency.get_status(self.thresholds),
                reversibility_status=self.reversibility.get_status(self.thresholds),
                collaboration_status=self.collaboration.get_status(self.thresholds),
                last_assessed=datetime.now(timezone.utc),
            )

            # Determine overall status
            statuses = [
                health.anti_sycophancy_status,
                health.trust_status,
                health.transparency_status,
                health.reversibility_status,
                health.collaboration_status,
            ]

            if MetricStatus.CRITICAL in statuses:
                health.overall_status = MetricStatus.CRITICAL
            elif MetricStatus.WARNING in statuses:
                health.overall_status = MetricStatus.WARNING
            elif all(s == MetricStatus.UNKNOWN for s in statuses):
                health.overall_status = MetricStatus.UNKNOWN
            else:
                health.overall_status = MetricStatus.HEALTHY

            # Generate issues and recommendations
            health.issues = self._identify_issues()
            health.recommendations = self._generate_recommendations(health.issues)

            return health

    def get_metrics_summary(self) -> dict:
        """
        Get a summary of all current metrics.

        Returns:
            Dictionary with all metric values
        """
        with self._lock:
            return {
                "anti_sycophancy": {
                    "disagreement_rate": self.anti_sycophancy.disagreement_rate,
                    "confidence_calibration_error": self.anti_sycophancy.confidence_calibration_error,
                    "negative_finding_suppression_rate": self.anti_sycophancy.negative_finding_suppression_rate,
                    "alternatives_offered_rate": self.anti_sycophancy.alternatives_offered_rate,
                    "total_interactions": self.anti_sycophancy.total_interactions,
                },
                "trust": {
                    "avg_trust_score": self.trust.avg_trust_score,
                    "trust_score_variance": self.trust.trust_score_variance,
                    "promotion_rate_30d": self.trust.promotion_rate_30d,
                    "demotion_rate_30d": self.trust.demotion_rate_30d,
                    "total_agents": self.trust.total_agents,
                },
                "transparency": {
                    "audit_trail_coverage": self.transparency.audit_trail_coverage,
                    "reasoning_chain_completeness": self.transparency.reasoning_chain_completeness,
                    "source_attribution_rate": self.transparency.source_attribution_rate,
                    "uncertainty_disclosure_rate": self.transparency.uncertainty_disclosure_rate,
                    "decisions_total": self.transparency.decisions_total,
                },
                "reversibility": {
                    "class_a_snapshot_rate": self.reversibility.class_a_snapshot_rate,
                    "class_b_rollback_rate": self.reversibility.class_b_rollback_rate,
                    "class_c_approval_rate": self.reversibility.class_c_approval_rate,
                    "rollback_success_rate": self.reversibility.rollback_success_rate,
                },
                "collaboration": {
                    "human_time_saved_hours": self.collaboration.human_time_saved_hours,
                    "override_acceptance_rate": self.collaboration.override_acceptance_rate,
                    "outcome_quality_score": self.collaboration.outcome_quality_score,
                    "capability_amplification": self.collaboration.capability_amplification,
                },
            }

    def _identify_issues(self) -> list[str]:
        """Identify current alignment issues."""
        issues = []

        # Anti-sycophancy issues
        if self.anti_sycophancy.total_interactions >= 10:
            if (
                self.anti_sycophancy.disagreement_rate
                < self.thresholds.disagreement_rate_min
            ):
                issues.append("Disagreement rate too low - possible sycophancy")
            elif (
                self.anti_sycophancy.disagreement_rate
                > self.thresholds.disagreement_rate_max
            ):
                issues.append("Disagreement rate too high - check agent calibration")

        if self.anti_sycophancy.negative_finding_suppression_rate > 0:
            issues.append(
                "Negative findings being suppressed - critical alignment issue"
            )

        # Trust issues
        if self.trust.avg_trust_score < self.thresholds.avg_trust_score_min:
            issues.append("Average agent trust score below threshold")

        # Transparency issues
        if self.transparency.audit_trail_coverage < 1.0:
            issues.append("Not all decisions have audit trails")

        # Reversibility issues
        if self.reversibility.class_c_total > 0:
            if self.reversibility.class_c_approval_rate < 1.0:
                issues.append("Irreversible actions executed without approval")

        # Collaboration issues
        if (
            self.collaboration.override_acceptance_rate
            < self.thresholds.override_acceptance_min
        ):
            issues.append("Agents not gracefully accepting human overrides")

        return issues

    def _generate_recommendations(self, issues: list[str]) -> list[str]:
        """Generate recommendations based on identified issues."""
        recommendations = []

        for issue in issues:
            if "sycophancy" in issue.lower():
                recommendations.append(
                    "Review agent responses for excessive agreement patterns"
                )
            elif "suppressed" in issue.lower():
                recommendations.append(
                    "URGENT: Investigate agents suppressing negative findings"
                )
            elif "trust score" in issue.lower():
                recommendations.append(
                    "Review recent agent failures and adjust training data"
                )
            elif "audit trails" in issue.lower():
                recommendations.append(
                    "Ensure DecisionAuditLogger is integrated with all agents"
                )
            elif "without approval" in issue.lower():
                recommendations.append(
                    "URGENT: Enforce human approval for all Class C actions"
                )
            elif "overrides" in issue.lower():
                recommendations.append(
                    "Train agents on graceful correction acceptance patterns"
                )

        return recommendations

    def _maybe_persist(self, event_type: str, data: dict) -> None:
        """Optionally persist metrics if callback is configured."""
        if self._persistence_callback:
            try:
                self._persistence_callback(
                    event_type,
                    {
                        **data,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as e:
                logger.error(f"Failed to persist alignment metric: {e}")

    def reset_metrics(self) -> None:
        """Reset all metrics (typically called on window rotation)."""
        with self._lock:
            self.anti_sycophancy = AntiSycophancyMetrics()
            self.trust = TrustMetrics()
            self.transparency = TransparencyMetrics()
            self.reversibility = ReversibilityMetrics()
            self.collaboration = CollaborationMetrics()
            self._last_reset = datetime.now(timezone.utc)
            logger.info("Alignment metrics reset")
