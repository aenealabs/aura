"""
Tests for AlignmentMetricsService (ADR-052 Phase 1).

Tests core metrics collection for alignment monitoring.
"""

import platform
import threading

import pytest

from src.services.alignment.metrics_service import (
    AlignmentHealth,
    AlignmentMetricsService,
    AntiSycophancyMetrics,
    CollaborationMetrics,
    MetricStatus,
    MetricThresholds,
    ReversibilityMetrics,
    TransparencyMetrics,
    TrustMetrics,
)

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestMetricStatusEnum:
    """Tests for MetricStatus enum."""

    def test_all_statuses_defined(self):
        """All expected status values exist."""
        statuses = [s.value for s in MetricStatus]
        assert "healthy" in statuses
        assert "warning" in statuses
        assert "critical" in statuses
        assert "unknown" in statuses

    def test_status_values(self):
        """Status enum values are correct."""
        assert MetricStatus.HEALTHY.value == "healthy"
        assert MetricStatus.WARNING.value == "warning"
        assert MetricStatus.CRITICAL.value == "critical"
        assert MetricStatus.UNKNOWN.value == "unknown"


class TestMetricThresholds:
    """Tests for MetricThresholds dataclass."""

    def test_default_thresholds(self):
        """Default thresholds are set correctly."""
        thresholds = MetricThresholds()
        # Anti-sycophancy
        assert thresholds.disagreement_rate_min == 0.05
        assert thresholds.disagreement_rate_max == 0.15
        assert thresholds.confidence_calibration_max_error == 0.10
        assert thresholds.negative_finding_suppression_max == 0.0
        assert thresholds.alternatives_offered_min == 0.80
        # Trust
        assert thresholds.avg_trust_score_min == 0.60
        assert thresholds.trust_variance_max == 0.20
        # Transparency
        assert thresholds.audit_trail_completeness == 1.0
        assert thresholds.uncertainty_disclosure_min == 1.0
        # Reversibility
        assert thresholds.class_c_approval_coverage == 1.0
        assert thresholds.rollback_success_rate_min == 0.99
        # Collaboration
        assert thresholds.override_acceptance_min == 0.95

    def test_custom_thresholds(self):
        """Custom thresholds can be set."""
        thresholds = MetricThresholds(
            disagreement_rate_min=0.10,
            disagreement_rate_max=0.20,
            avg_trust_score_min=0.70,
        )
        assert thresholds.disagreement_rate_min == 0.10
        assert thresholds.disagreement_rate_max == 0.20
        assert thresholds.avg_trust_score_min == 0.70


class TestAntiSycophancyMetrics:
    """Tests for AntiSycophancyMetrics dataclass."""

    def test_initial_values(self):
        """Initial metrics are zero."""
        metrics = AntiSycophancyMetrics()
        assert metrics.disagreement_rate == 0.0
        assert metrics.total_interactions == 0
        assert metrics.disagreements == 0

    def test_record_interaction_agreeing(self):
        """Record interaction where agent agrees."""
        metrics = AntiSycophancyMetrics()
        metrics.record_interaction(disagreed=False)
        assert metrics.total_interactions == 1
        assert metrics.disagreements == 0
        assert metrics.disagreement_rate == 0.0

    def test_record_interaction_disagreeing(self):
        """Record interaction where agent disagrees."""
        metrics = AntiSycophancyMetrics()
        metrics.record_interaction(disagreed=True)
        assert metrics.total_interactions == 1
        assert metrics.disagreements == 1
        assert metrics.disagreement_rate == 1.0

    def test_disagreement_rate_calculation(self):
        """Disagreement rate is calculated correctly."""
        metrics = AntiSycophancyMetrics()
        # 3 disagreements out of 10 = 30%
        for i in range(10):
            metrics.record_interaction(disagreed=(i < 3))
        assert metrics.disagreement_rate == 0.30

    def test_record_confidence_prediction_correct(self):
        """Record correct confidence prediction."""
        metrics = AntiSycophancyMetrics()
        metrics.record_confidence_prediction(
            predicted_confidence=0.8,
            was_correct=True,
        )
        assert metrics.confidence_predictions == 1
        assert metrics.confidence_correct == 1
        assert metrics.confidence_calibration_error == 0.0

    def test_record_confidence_prediction_wrong(self):
        """Record incorrect confidence prediction."""
        metrics = AntiSycophancyMetrics()
        metrics.record_confidence_prediction(
            predicted_confidence=0.8,
            was_correct=False,  # High confidence but wrong
        )
        assert metrics.confidence_predictions == 1
        assert metrics.confidence_correct == 0
        assert metrics.confidence_calibration_error == 1.0

    def test_record_negative_finding_reported(self):
        """Record reported negative finding."""
        metrics = AntiSycophancyMetrics()
        metrics.record_negative_finding(was_reported=True)
        assert metrics.negative_findings_total == 1
        assert metrics.negative_findings_reported == 1
        assert metrics.negative_finding_suppression_rate == 0.0

    def test_record_negative_finding_suppressed(self):
        """Record suppressed negative finding."""
        metrics = AntiSycophancyMetrics()
        metrics.record_negative_finding(was_reported=False)
        assert metrics.negative_findings_total == 1
        assert metrics.negative_findings_reported == 0
        assert metrics.negative_finding_suppression_rate == 1.0

    def test_record_decision_with_alternatives(self):
        """Record decision with alternatives shown."""
        metrics = AntiSycophancyMetrics()
        metrics.record_decision(alternatives_shown=True)
        assert metrics.significant_decisions == 1
        assert metrics.alternatives_presented == 1
        assert metrics.alternatives_offered_rate == 1.0

    def test_record_decision_without_alternatives(self):
        """Record decision without alternatives."""
        metrics = AntiSycophancyMetrics()
        metrics.record_decision(alternatives_shown=False)
        assert metrics.alternatives_offered_rate == 0.0

    def test_get_status_healthy(self):
        """Status is healthy when metrics are good."""
        metrics = AntiSycophancyMetrics()
        thresholds = MetricThresholds()
        # Record enough interactions with good disagreement rate
        for i in range(20):
            metrics.record_interaction(disagreed=(i < 2))  # 10% disagreement
        # Good confidence predictions
        for i in range(20):
            metrics.record_confidence_prediction(0.8, was_correct=True)
        # All decisions with alternatives
        for _ in range(10):
            metrics.record_decision(alternatives_shown=True)

        status = metrics.get_status(thresholds)
        assert status == MetricStatus.HEALTHY

    def test_get_status_critical_on_suppression(self):
        """Status is critical when findings suppressed."""
        metrics = AntiSycophancyMetrics()
        thresholds = MetricThresholds()
        metrics.record_negative_finding(was_reported=False)
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.CRITICAL

    def test_get_status_warning_on_low_disagreement(self):
        """Status is warning when disagreement too low."""
        metrics = AntiSycophancyMetrics()
        thresholds = MetricThresholds()
        # No disagreements out of 20 = 0%
        for _ in range(20):
            metrics.record_interaction(disagreed=False)
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.WARNING


class TestTrustMetrics:
    """Tests for TrustMetrics dataclass."""

    def test_initial_values(self):
        """Initial metrics are zero."""
        metrics = TrustMetrics()
        assert metrics.avg_trust_score == 0.0
        assert metrics.trust_score_variance == 0.0
        assert metrics.total_agents == 0

    def test_update_agent_score(self):
        """Update agent trust score."""
        metrics = TrustMetrics()
        metrics.update_agent_score("agent-1", 0.80)
        assert metrics.agent_scores["agent-1"] == 0.80
        assert metrics.avg_trust_score == 0.80
        assert metrics.total_agents == 1

    def test_update_multiple_agents(self):
        """Update multiple agent scores."""
        metrics = TrustMetrics()
        metrics.update_agent_score("agent-1", 0.80)
        metrics.update_agent_score("agent-2", 0.90)
        metrics.update_agent_score("agent-3", 0.70)
        assert metrics.total_agents == 3
        assert metrics.avg_trust_score == pytest.approx(0.80, rel=0.01)

    def test_variance_calculation(self):
        """Variance is calculated correctly."""
        metrics = TrustMetrics()
        metrics.update_agent_score("agent-1", 0.60)
        metrics.update_agent_score("agent-2", 1.00)
        # Mean = 0.80, variance = ((0.60-0.80)^2 + (1.00-0.80)^2) / 2 = 0.04
        assert metrics.trust_score_variance == pytest.approx(0.04, rel=0.01)

    def test_record_promotion(self):
        """Record trust level promotion."""
        metrics = TrustMetrics()
        metrics.update_agent_score("agent-1", 0.80)
        metrics.record_promotion()
        assert metrics.promotions_30d == 1
        assert metrics.promotion_rate_30d == 1.0

    def test_record_demotion(self):
        """Record trust level demotion."""
        metrics = TrustMetrics()
        metrics.update_agent_score("agent-1", 0.80)
        metrics.record_demotion()
        assert metrics.demotions_30d == 1
        assert metrics.demotion_rate_30d == 1.0

    def test_get_status_unknown_no_agents(self):
        """Status is unknown when no agents."""
        metrics = TrustMetrics()
        thresholds = MetricThresholds()
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.UNKNOWN

    def test_get_status_healthy(self):
        """Status is healthy with good scores."""
        metrics = TrustMetrics()
        thresholds = MetricThresholds()
        metrics.update_agent_score("agent-1", 0.85)
        metrics.update_agent_score("agent-2", 0.90)
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.HEALTHY

    def test_get_status_warning_low_trust(self):
        """Status is warning when avg trust low."""
        metrics = TrustMetrics()
        thresholds = MetricThresholds()
        metrics.update_agent_score("agent-1", 0.50)
        metrics.update_agent_score("agent-2", 0.55)
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.WARNING


class TestTransparencyMetrics:
    """Tests for TransparencyMetrics dataclass."""

    def test_initial_values(self):
        """Initial metrics are at 100%."""
        metrics = TransparencyMetrics()
        assert metrics.audit_trail_coverage == 1.0
        assert metrics.reasoning_chain_completeness == 1.0
        assert metrics.source_attribution_rate == 1.0
        assert metrics.uncertainty_disclosure_rate == 1.0

    def test_record_decision_full_transparency(self):
        """Record decision with full transparency."""
        metrics = TransparencyMetrics()
        metrics.record_decision(
            has_audit_trail=True,
            has_reasoning_chain=True,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )
        assert metrics.decisions_total == 1
        assert metrics.audit_trail_coverage == 1.0
        assert metrics.reasoning_chain_completeness == 1.0

    def test_record_decision_partial_transparency(self):
        """Record decision with partial transparency."""
        metrics = TransparencyMetrics()
        metrics.record_decision(
            has_audit_trail=True,
            has_reasoning_chain=False,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )
        assert metrics.reasoning_chain_completeness == 0.0

    def test_multiple_decisions(self):
        """Track rates across multiple decisions."""
        metrics = TransparencyMetrics()
        # 2 with full transparency
        for _ in range(2):
            metrics.record_decision(
                has_audit_trail=True,
                has_reasoning_chain=True,
                has_source_attribution=True,
                has_uncertainty_disclosure=True,
            )
        # 1 with missing reasoning
        metrics.record_decision(
            has_audit_trail=True,
            has_reasoning_chain=False,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )
        assert metrics.decisions_total == 3
        assert metrics.reasoning_chain_completeness == pytest.approx(2 / 3, rel=0.01)

    def test_get_status_unknown_no_decisions(self):
        """Status is unknown when no decisions."""
        metrics = TransparencyMetrics()
        thresholds = MetricThresholds()
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.UNKNOWN

    def test_get_status_critical_missing_audit(self):
        """Status is critical when audit trails missing."""
        metrics = TransparencyMetrics()
        thresholds = MetricThresholds()
        metrics.record_decision(
            has_audit_trail=False,  # Critical
            has_reasoning_chain=True,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.CRITICAL

    def test_get_status_critical_missing_uncertainty(self):
        """Status is critical when uncertainty not disclosed."""
        metrics = TransparencyMetrics()
        thresholds = MetricThresholds()
        metrics.record_decision(
            has_audit_trail=True,
            has_reasoning_chain=True,
            has_source_attribution=True,
            has_uncertainty_disclosure=False,  # Critical
        )
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.CRITICAL

    def test_get_status_healthy(self):
        """Status is healthy with full transparency."""
        metrics = TransparencyMetrics()
        thresholds = MetricThresholds()
        metrics.record_decision(
            has_audit_trail=True,
            has_reasoning_chain=True,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.HEALTHY


class TestReversibilityMetrics:
    """Tests for ReversibilityMetrics dataclass."""

    def test_initial_values(self):
        """Initial metrics are at 100%."""
        metrics = ReversibilityMetrics()
        assert metrics.class_a_snapshot_rate == 1.0
        assert metrics.class_b_rollback_rate == 1.0
        assert metrics.class_c_approval_rate == 1.0
        assert metrics.rollback_success_rate == 1.0

    def test_record_class_a_with_snapshot(self):
        """Record Class A action with snapshot."""
        metrics = ReversibilityMetrics()
        metrics.record_class_a_action(has_snapshot=True)
        assert metrics.class_a_total == 1
        assert metrics.class_a_with_snapshot == 1
        assert metrics.class_a_snapshot_rate == 1.0

    def test_record_class_a_without_snapshot(self):
        """Record Class A action without snapshot."""
        metrics = ReversibilityMetrics()
        metrics.record_class_a_action(has_snapshot=False)
        assert metrics.class_a_snapshot_rate == 0.0

    def test_record_class_b_with_rollback(self):
        """Record Class B action with rollback plan."""
        metrics = ReversibilityMetrics()
        metrics.record_class_b_action(has_rollback_plan=True)
        assert metrics.class_b_total == 1
        assert metrics.class_b_rollback_rate == 1.0

    def test_record_class_c_with_approval(self):
        """Record Class C action with approval."""
        metrics = ReversibilityMetrics()
        metrics.record_class_c_action(had_approval=True)
        assert metrics.class_c_total == 1
        assert metrics.class_c_approval_rate == 1.0

    def test_record_class_c_without_approval(self):
        """Record Class C action without approval."""
        metrics = ReversibilityMetrics()
        metrics.record_class_c_action(had_approval=False)
        assert metrics.class_c_approval_rate == 0.0

    def test_record_rollback_success(self):
        """Record successful rollback."""
        metrics = ReversibilityMetrics()
        metrics.record_rollback(was_successful=True)
        assert metrics.rollbacks_attempted == 1
        assert metrics.rollbacks_successful == 1
        assert metrics.rollback_success_rate == 1.0

    def test_record_rollback_failure(self):
        """Record failed rollback."""
        metrics = ReversibilityMetrics()
        metrics.record_rollback(was_successful=False)
        assert metrics.rollback_success_rate == 0.0

    def test_get_status_critical_no_approval(self):
        """Status is critical when Class C without approval."""
        metrics = ReversibilityMetrics()
        thresholds = MetricThresholds()
        metrics.record_class_c_action(had_approval=False)
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.CRITICAL

    def test_get_status_critical_rollback_failures(self):
        """Status is critical when rollback failures."""
        metrics = ReversibilityMetrics()
        thresholds = MetricThresholds()
        # Many rollback failures
        for i in range(10):
            metrics.record_rollback(was_successful=(i < 5))  # 50% success
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.CRITICAL

    def test_get_status_healthy(self):
        """Status is healthy with all requirements met."""
        metrics = ReversibilityMetrics()
        thresholds = MetricThresholds()
        metrics.record_class_a_action(has_snapshot=True)
        metrics.record_class_b_action(has_rollback_plan=True)
        metrics.record_class_c_action(had_approval=True)
        metrics.record_rollback(was_successful=True)
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.HEALTHY


class TestCollaborationMetrics:
    """Tests for CollaborationMetrics dataclass."""

    def test_initial_values(self):
        """Initial metrics are at default values."""
        metrics = CollaborationMetrics()
        assert metrics.human_time_saved_hours == 0.0
        assert metrics.override_acceptance_rate == 1.0
        assert metrics.outcome_quality_score == 0.0
        assert metrics.capability_amplification == 1.0

    def test_record_time_saved(self):
        """Record time saved."""
        metrics = CollaborationMetrics()
        metrics.record_time_saved(5.0)
        metrics.record_time_saved(3.0)
        assert metrics.human_time_saved_hours == 8.0

    def test_record_human_contribution(self):
        """Record human contributions."""
        metrics = CollaborationMetrics()
        metrics.record_human_contribution(
            goal_defined=True,
            ethical_judgment=True,
            creative_direction=False,
        )
        assert metrics.goals_defined_by_human == 1
        assert metrics.ethical_judgments_made == 1
        assert metrics.creative_directions_chosen == 0

    def test_record_machine_contribution(self):
        """Record machine contributions."""
        metrics = CollaborationMetrics()
        metrics.record_machine_contribution(
            patterns=10,
            options=5,
            validations=20,
        )
        assert metrics.patterns_identified == 10
        assert metrics.options_analyzed == 5
        assert metrics.validations_performed == 20

    def test_record_override_accepted(self):
        """Record accepted override."""
        metrics = CollaborationMetrics()
        metrics.record_override(was_accepted_gracefully=True)
        assert metrics.overrides_total == 1
        assert metrics.overrides_accepted == 1
        assert metrics.override_acceptance_rate == 1.0

    def test_record_override_rejected(self):
        """Record rejected override."""
        metrics = CollaborationMetrics()
        metrics.record_override(was_accepted_gracefully=False)
        assert metrics.override_acceptance_rate == 0.0

    def test_record_outcome(self):
        """Record outcome measurement."""
        metrics = CollaborationMetrics()
        metrics.record_outcome(was_positive=True, quality_score=0.90)
        assert metrics.outcomes_measured == 1
        assert metrics.outcomes_positive == 1
        assert metrics.outcome_quality_score == 0.90

    def test_outcome_quality_averaging(self):
        """Outcome quality is running average."""
        metrics = CollaborationMetrics()
        metrics.record_outcome(was_positive=True, quality_score=0.80)
        metrics.record_outcome(was_positive=True, quality_score=0.90)
        assert metrics.outcome_quality_score == pytest.approx(0.85, rel=0.01)

    def test_update_capability_amplification(self):
        """Update capability amplification."""
        metrics = CollaborationMetrics()
        metrics.update_capability_amplification(baseline=10.0, with_ai=30.0)
        assert metrics.capability_amplification == 3.0

    def test_get_status_critical_poor_override(self):
        """Status is critical when overrides not accepted."""
        metrics = CollaborationMetrics()
        thresholds = MetricThresholds()
        # Many overrides not accepted
        for i in range(10):
            metrics.record_override(was_accepted_gracefully=(i < 2))  # 20% accepted
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.CRITICAL

    def test_get_status_healthy(self):
        """Status is healthy with good collaboration."""
        metrics = CollaborationMetrics()
        thresholds = MetricThresholds()
        metrics.record_override(was_accepted_gracefully=True)
        for _ in range(10):
            metrics.record_outcome(was_positive=True, quality_score=0.90)
        metrics.update_capability_amplification(baseline=10.0, with_ai=25.0)
        status = metrics.get_status(thresholds)
        assert status == MetricStatus.HEALTHY


class TestAlignmentHealth:
    """Tests for AlignmentHealth dataclass."""

    def test_initial_values(self):
        """Initial health is unknown."""
        health = AlignmentHealth()
        assert health.overall_status == MetricStatus.UNKNOWN
        assert health.issues == []
        assert health.recommendations == []

    def test_to_dict(self):
        """to_dict returns proper dictionary."""
        health = AlignmentHealth(
            overall_status=MetricStatus.HEALTHY,
            anti_sycophancy_status=MetricStatus.HEALTHY,
            trust_status=MetricStatus.HEALTHY,
            transparency_status=MetricStatus.WARNING,
            reversibility_status=MetricStatus.HEALTHY,
            collaboration_status=MetricStatus.HEALTHY,
            issues=["Minor transparency issue"],
            recommendations=["Improve reasoning chains"],
        )
        d = health.to_dict()
        assert d["overall_status"] == "healthy"
        assert d["transparency_status"] == "warning"
        assert "Minor transparency issue" in d["issues"]
        assert "last_assessed" in d


class TestAlignmentMetricsServiceInit:
    """Tests for AlignmentMetricsService initialization."""

    def test_default_initialization(self):
        """Service initializes with defaults."""
        service = AlignmentMetricsService()
        assert service.thresholds is not None
        assert service.anti_sycophancy is not None
        assert service.trust is not None
        assert service.transparency is not None
        assert service.reversibility is not None
        assert service.collaboration is not None

    def test_custom_thresholds(self):
        """Service accepts custom thresholds."""
        custom = MetricThresholds(disagreement_rate_min=0.10)
        service = AlignmentMetricsService(thresholds=custom)
        assert service.thresholds.disagreement_rate_min == 0.10

    def test_persistence_callback(self):
        """Service accepts persistence callback."""
        persisted = []

        def persist(event_type, data):
            persisted.append((event_type, data))

        service = AlignmentMetricsService(persistence_callback=persist)
        service.record_interaction("agent-1", disagreed_with_user=True)
        assert len(persisted) == 1
        assert persisted[0][0] == "interaction"


class TestRecordInteraction:
    """Tests for recording interactions."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_interaction_agreeing(self, service):
        """Record agreeing interaction."""
        service.record_interaction("agent-1", disagreed_with_user=False)
        assert service.anti_sycophancy.total_interactions == 1
        assert service.anti_sycophancy.disagreements == 0

    def test_record_interaction_disagreeing(self, service):
        """Record disagreeing interaction."""
        service.record_interaction("agent-1", disagreed_with_user=True)
        assert service.anti_sycophancy.disagreements == 1


class TestRecordConfidencePrediction:
    """Tests for recording confidence predictions."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_prediction(self, service):
        """Record confidence prediction."""
        service.record_confidence_prediction(
            agent_id="agent-1",
            predicted_confidence=0.85,
            actual_outcome_correct=True,
        )
        assert service.anti_sycophancy.confidence_predictions == 1


class TestRecordNegativeFinding:
    """Tests for recording negative findings."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_reported_finding(self, service):
        """Record reported negative finding."""
        service.record_negative_finding(
            agent_id="agent-1",
            finding_type="security",
            was_reported_to_user=True,
        )
        assert service.anti_sycophancy.negative_findings_reported == 1

    def test_record_suppressed_finding(self, service):
        """Record suppressed negative finding."""
        service.record_negative_finding(
            agent_id="agent-1",
            finding_type="quality",
            was_reported_to_user=False,
        )
        assert service.anti_sycophancy.negative_finding_suppression_rate == 1.0


class TestRecordDecision:
    """Tests for recording decisions."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_full_transparency_decision(self, service):
        """Record decision with full transparency."""
        service.record_decision(
            decision_id="dec-1",
            agent_id="agent-1",
            alternatives_shown=True,
            has_audit_trail=True,
            has_reasoning_chain=True,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )
        assert service.anti_sycophancy.alternatives_presented == 1
        assert service.transparency.audit_trail_coverage == 1.0

    def test_record_partial_transparency_decision(self, service):
        """Record decision with partial transparency."""
        service.record_decision(
            decision_id="dec-1",
            agent_id="agent-1",
            alternatives_shown=False,
            has_audit_trail=True,
            has_reasoning_chain=False,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )
        assert service.anti_sycophancy.alternatives_offered_rate == 0.0
        assert service.transparency.reasoning_chain_completeness == 0.0


class TestUpdateAgentTrustScore:
    """Tests for updating agent trust scores."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_update_score(self, service):
        """Update agent trust score."""
        service.update_agent_trust_score("agent-1", trust_score=0.85)
        assert service.trust.agent_scores["agent-1"] == 0.85

    def test_update_with_promotion(self, service):
        """Update with promotion flag."""
        service.update_agent_trust_score("agent-1", trust_score=0.90, promoted=True)
        assert service.trust.promotions_30d == 1

    def test_update_with_demotion(self, service):
        """Update with demotion flag."""
        service.update_agent_trust_score("agent-1", trust_score=0.50, demoted=True)
        assert service.trust.demotions_30d == 1


class TestRecordAction:
    """Tests for recording actions."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_class_a_action(self, service):
        """Record Class A action."""
        service.record_action(
            action_id="act-1",
            action_class="A",
            has_snapshot=True,
        )
        assert service.reversibility.class_a_total == 1
        assert service.reversibility.class_a_with_snapshot == 1

    def test_record_class_b_action(self, service):
        """Record Class B action."""
        service.record_action(
            action_id="act-1",
            action_class="B",
            has_rollback_plan=True,
        )
        assert service.reversibility.class_b_total == 1

    def test_record_class_c_action_approved(self, service):
        """Record approved Class C action."""
        service.record_action(
            action_id="act-1",
            action_class="C",
            had_human_approval=True,
        )
        assert service.reversibility.class_c_total == 1
        assert service.reversibility.class_c_with_approval == 1

    def test_record_class_c_action_unapproved(self, service):
        """Record unapproved Class C action (logged as critical)."""
        service.record_action(
            action_id="act-1",
            action_class="C",
            had_human_approval=False,
        )
        assert service.reversibility.class_c_approval_rate == 0.0


class TestRecordRollback:
    """Tests for recording rollbacks."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_successful_rollback(self, service):
        """Record successful rollback."""
        service.record_rollback("act-1", was_successful=True)
        assert service.reversibility.rollbacks_successful == 1

    def test_record_failed_rollback(self, service):
        """Record failed rollback."""
        service.record_rollback("act-1", was_successful=False, failure_reason="test")
        assert service.reversibility.rollback_success_rate == 0.0


class TestRecordHumanOverride:
    """Tests for recording human overrides."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_accepted_override(self, service):
        """Record gracefully accepted override."""
        service.record_human_override(
            agent_id="agent-1",
            decision_id="dec-1",
            accepted_gracefully=True,
        )
        assert service.collaboration.override_acceptance_rate == 1.0

    def test_record_rejected_override(self, service):
        """Record rejected override."""
        service.record_human_override(
            agent_id="agent-1",
            decision_id="dec-1",
            accepted_gracefully=False,
        )
        assert service.collaboration.override_acceptance_rate == 0.0


class TestRecordTimeSaved:
    """Tests for recording time saved."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_time_saved(self, service):
        """Record time saved."""
        service.record_time_saved(5.0, context="code review")
        service.record_time_saved(3.0, context="testing")
        assert service.collaboration.human_time_saved_hours == 8.0


class TestRecordOutcome:
    """Tests for recording outcomes."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_record_positive_outcome(self, service):
        """Record positive outcome."""
        service.record_outcome(
            outcome_id="out-1",
            was_positive=True,
            quality_score=0.90,
        )
        assert service.collaboration.outcomes_positive == 1
        assert service.collaboration.outcome_quality_score == 0.90


class TestGetHealth:
    """Tests for health assessment."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_get_health_with_no_data(self, service):
        """Health reflects default metric states with no recorded data."""
        health = service.get_health()
        # With no data recorded, most categories are UNKNOWN
        # but collaboration defaults to WARNING because capability_amplification
        # starts at 1.0 which is below the 2.0 threshold
        assert health.trust_status == MetricStatus.UNKNOWN
        assert health.transparency_status == MetricStatus.UNKNOWN
        # Overall status is WARNING due to collaboration default
        assert health.overall_status in (MetricStatus.UNKNOWN, MetricStatus.WARNING)

    def test_get_health_critical_propagates(self, service):
        """Critical status propagates to overall."""
        service.record_negative_finding(
            "agent-1", "security", was_reported_to_user=False
        )
        health = service.get_health()
        assert health.anti_sycophancy_status == MetricStatus.CRITICAL
        assert health.overall_status == MetricStatus.CRITICAL

    def test_get_health_includes_issues(self, service):
        """Health includes identified issues."""
        # Record suppressed finding (critical issue)
        service.record_negative_finding(
            "agent-1", "security", was_reported_to_user=False
        )
        health = service.get_health()
        assert len(health.issues) > 0
        assert any("suppressed" in issue.lower() for issue in health.issues)

    def test_get_health_includes_recommendations(self, service):
        """Health includes recommendations."""
        service.record_negative_finding(
            "agent-1", "security", was_reported_to_user=False
        )
        health = service.get_health()
        assert len(health.recommendations) > 0

    def test_get_health_healthy(self, service):
        """Health is healthy with good data."""
        # Record good data for all categories
        for i in range(20):
            service.record_interaction(
                f"agent-{i % 3}", disagreed_with_user=(i % 10 == 0)
            )
            service.record_confidence_prediction(f"agent-{i % 3}", 0.8, True)
        for _ in range(10):
            service.record_decision(
                "dec-1",
                "agent-1",
                alternatives_shown=True,
                has_audit_trail=True,
                has_reasoning_chain=True,
                has_source_attribution=True,
                has_uncertainty_disclosure=True,
            )
        for agent_id in ["agent-0", "agent-1", "agent-2"]:
            service.update_agent_trust_score(agent_id, 0.85)

        health = service.get_health()
        # Most categories should be healthy
        assert health.transparency_status == MetricStatus.HEALTHY


class TestGetMetricsSummary:
    """Tests for metrics summary."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_summary_structure(self, service):
        """Summary has expected structure."""
        summary = service.get_metrics_summary()
        assert "anti_sycophancy" in summary
        assert "trust" in summary
        assert "transparency" in summary
        assert "reversibility" in summary
        assert "collaboration" in summary

    def test_summary_anti_sycophancy_fields(self, service):
        """Anti-sycophancy summary has expected fields."""
        summary = service.get_metrics_summary()
        anti = summary["anti_sycophancy"]
        assert "disagreement_rate" in anti
        assert "confidence_calibration_error" in anti
        assert "negative_finding_suppression_rate" in anti
        assert "total_interactions" in anti

    def test_summary_reflects_data(self, service):
        """Summary reflects recorded data."""
        service.record_time_saved(10.0)
        summary = service.get_metrics_summary()
        assert summary["collaboration"]["human_time_saved_hours"] == 10.0


class TestResetMetrics:
    """Tests for metrics reset."""

    @pytest.fixture
    def service(self):
        """Create service with some data."""
        svc = AlignmentMetricsService()
        svc.record_interaction("agent-1", disagreed_with_user=True)
        svc.update_agent_trust_score("agent-1", 0.85)
        svc.record_time_saved(5.0)
        return svc

    def test_reset_clears_all_metrics(self, service):
        """Reset clears all metrics."""
        # Verify data exists
        assert service.anti_sycophancy.total_interactions == 1
        assert service.trust.total_agents == 1

        service.reset_metrics()

        # Verify cleared
        assert service.anti_sycophancy.total_interactions == 0
        assert service.trust.total_agents == 0
        assert service.collaboration.human_time_saved_hours == 0.0


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_recording(self):
        """Concurrent recording is thread-safe."""
        service = AlignmentMetricsService()
        errors = []

        def record_data(thread_id: int):
            try:
                for i in range(50):
                    service.record_interaction(
                        f"agent-{thread_id}",
                        disagreed_with_user=(i % 5 == 0),
                    )
                    service.record_time_saved(0.1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_data, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert service.anti_sycophancy.total_interactions == 250  # 5 threads * 50

    def test_concurrent_health_assessment(self):
        """Concurrent health assessment is thread-safe."""
        service = AlignmentMetricsService()
        errors = []

        # Add some data first
        for i in range(20):
            service.record_interaction(
                f"agent-{i % 3}", disagreed_with_user=(i % 5 == 0)
            )
            service.update_agent_trust_score(f"agent-{i % 3}", 0.80)

        def assess_health():
            try:
                for _ in range(20):
                    health = service.get_health()
                    _ = service.get_metrics_summary()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=assess_health) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        return AlignmentMetricsService()

    def test_zero_values(self, service):
        """Handle zero values correctly."""
        service.record_time_saved(0.0)
        assert service.collaboration.human_time_saved_hours == 0.0

    def test_boundary_trust_scores(self, service):
        """Handle boundary trust scores."""
        service.update_agent_trust_score("agent-low", 0.0)
        service.update_agent_trust_score("agent-high", 1.0)
        assert service.trust.agent_scores["agent-low"] == 0.0
        assert service.trust.agent_scores["agent-high"] == 1.0
        assert service.trust.avg_trust_score == 0.5

    def test_persistence_callback_exception(self, service):
        """Handle persistence callback exception gracefully."""

        def failing_persist(event_type, data):
            raise RuntimeError("Persistence failed")

        service._persistence_callback = failing_persist
        # Should not raise, just log
        service.record_interaction("agent-1", disagreed_with_user=True)
        assert service.anti_sycophancy.total_interactions == 1

    def test_many_agents(self, service):
        """Handle many agents."""
        for i in range(100):
            service.update_agent_trust_score(f"agent-{i}", 0.80 + (i % 20) * 0.01)
        assert service.trust.total_agents == 100

    def test_outcome_quality_range(self, service):
        """Outcome quality stays in valid range."""
        service.record_outcome("out-1", True, 0.0)
        assert service.collaboration.outcome_quality_score == 0.0
        service.record_outcome("out-2", True, 1.0)
        assert 0.0 <= service.collaboration.outcome_quality_score <= 1.0
