"""
Tests for Alignment Services (ADR-052 Phase 1).

Comprehensive tests for:
- AlignmentMetricsService
- TrustScoreCalculator
- ReversibilityClassifier
- DecisionAuditLogger
"""

import platform
from unittest.mock import MagicMock, patch

import pytest

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestAlignmentMetricsService:
    """Tests for AlignmentMetricsService."""

    def test_initialization(self) -> None:
        """Test service initializes with default thresholds."""
        from src.services.alignment import AlignmentMetricsService, MetricThresholds

        service = AlignmentMetricsService()
        assert service.thresholds is not None
        assert isinstance(service.thresholds, MetricThresholds)

    def test_custom_thresholds(self) -> None:
        """Test service accepts custom thresholds."""
        from src.services.alignment import AlignmentMetricsService, MetricThresholds

        custom = MetricThresholds(disagreement_rate_min=0.10)
        service = AlignmentMetricsService(thresholds=custom)
        assert service.thresholds.disagreement_rate_min == 0.10

    def test_record_interaction(self) -> None:
        """Test recording interactions updates disagreement rate."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        # Record 10 interactions, 2 disagreements
        for i in range(10):
            service.record_interaction(
                agent_id="agent-1",
                disagreed_with_user=(i < 2),
            )

        assert service.anti_sycophancy.total_interactions == 10
        assert service.anti_sycophancy.disagreements == 2
        assert service.anti_sycophancy.disagreement_rate == 0.2

    def test_record_confidence_prediction(self) -> None:
        """Test recording confidence predictions updates calibration."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        # Record predictions
        service.record_confidence_prediction("agent-1", 0.9, True)
        service.record_confidence_prediction("agent-1", 0.8, True)
        service.record_confidence_prediction("agent-1", 0.7, False)

        assert service.anti_sycophancy.confidence_predictions == 3
        assert service.anti_sycophancy.confidence_correct == 2

    def test_record_negative_finding_logs_warning(self) -> None:
        """Test suppressed findings are logged as warnings."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        with patch("src.services.alignment.metrics_service.logger") as mock_logger:
            service.record_negative_finding(
                agent_id="agent-1",
                finding_type="security_vulnerability",
                was_reported_to_user=False,
            )
            mock_logger.warning.assert_called()

    def test_record_decision_transparency(self) -> None:
        """Test recording decisions updates transparency metrics."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        service.record_decision(
            decision_id="dec-1",
            agent_id="agent-1",
            alternatives_shown=True,
            has_audit_trail=True,
            has_reasoning_chain=True,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )

        assert service.transparency.decisions_total == 1
        assert service.transparency.audit_trail_coverage == 1.0
        assert service.transparency.reasoning_chain_completeness == 1.0

    def test_update_agent_trust_score(self) -> None:
        """Test updating agent trust scores."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        service.update_agent_trust_score("agent-1", 0.75)
        service.update_agent_trust_score("agent-2", 0.85)

        assert service.trust.avg_trust_score == 0.80
        assert service.trust.total_agents == 2

    def test_record_action_classes(self) -> None:
        """Test recording actions by class."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        service.record_action("act-1", "A", has_snapshot=True)
        service.record_action("act-2", "B", has_rollback_plan=True)
        service.record_action("act-3", "C", had_human_approval=True)

        assert service.reversibility.class_a_total == 1
        assert service.reversibility.class_b_total == 1
        assert service.reversibility.class_c_total == 1

    def test_record_irreversible_without_approval_logs_error(self) -> None:
        """Test irreversible actions without approval are logged as errors."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        with patch("src.services.alignment.metrics_service.logger") as mock_logger:
            service.record_action("act-1", "C", had_human_approval=False)
            mock_logger.error.assert_called()

    def test_record_rollback(self) -> None:
        """Test recording rollback attempts."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        service.record_rollback("act-1", was_successful=True)
        service.record_rollback("act-2", was_successful=False, failure_reason="timeout")

        assert service.reversibility.rollbacks_attempted == 2
        assert service.reversibility.rollbacks_successful == 1
        assert service.reversibility.rollback_success_rate == 0.5

    def test_record_human_override(self) -> None:
        """Test recording human overrides."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        service.record_human_override("agent-1", "dec-1", accepted_gracefully=True)
        service.record_human_override("agent-1", "dec-2", accepted_gracefully=False)

        assert service.collaboration.overrides_total == 2
        assert service.collaboration.overrides_accepted == 1
        assert service.collaboration.override_acceptance_rate == 0.5

    def test_record_time_saved(self) -> None:
        """Test recording time saved."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        service.record_time_saved(5.0, "code_review")
        service.record_time_saved(3.5, "security_scan")

        assert service.collaboration.human_time_saved_hours == 8.5

    def test_get_health_healthy(self) -> None:
        """Test health assessment when all metrics are healthy."""
        from src.services.alignment import AlignmentMetricsService
        from src.services.alignment.metrics_service import MetricStatus

        service = AlignmentMetricsService()

        # Set up healthy state
        for i in range(20):
            service.record_interaction("agent-1", disagreed_with_user=(i % 10 == 0))

        service.update_agent_trust_score("agent-1", 0.75)

        for i in range(10):
            service.record_decision(
                f"dec-{i}",
                "agent-1",
                alternatives_shown=True,
                has_audit_trail=True,
                has_reasoning_chain=True,
                has_source_attribution=True,
                has_uncertainty_disclosure=True,
            )

        service.record_action("act-1", "A", has_snapshot=True)
        service.record_action("act-2", "C", had_human_approval=True)

        health = service.get_health()
        assert health.transparency_status == MetricStatus.HEALTHY
        assert health.reversibility_status == MetricStatus.HEALTHY

    def test_get_health_critical_on_suppression(self) -> None:
        """Test health is critical when negative findings are suppressed."""
        from src.services.alignment import AlignmentMetricsService
        from src.services.alignment.metrics_service import MetricStatus

        service = AlignmentMetricsService()

        # Suppress a negative finding
        service.record_negative_finding(
            "agent-1", "security", was_reported_to_user=False
        )

        health = service.get_health()
        assert health.anti_sycophancy_status == MetricStatus.CRITICAL

    def test_get_metrics_summary(self) -> None:
        """Test getting metrics summary."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        service.record_interaction("agent-1", disagreed_with_user=True)
        service.update_agent_trust_score("agent-1", 0.8)

        summary = service.get_metrics_summary()

        assert "anti_sycophancy" in summary
        assert "trust" in summary
        assert "transparency" in summary
        assert "reversibility" in summary
        assert "collaboration" in summary

    def test_reset_metrics(self) -> None:
        """Test resetting all metrics."""
        from src.services.alignment import AlignmentMetricsService

        service = AlignmentMetricsService()

        service.record_interaction("agent-1", disagreed_with_user=True)
        service.record_time_saved(10.0)

        service.reset_metrics()

        assert service.anti_sycophancy.total_interactions == 0
        assert service.collaboration.human_time_saved_hours == 0.0


class TestTrustScoreCalculator:
    """Tests for TrustScoreCalculator."""

    def test_initialization(self) -> None:
        """Test calculator initializes correctly."""
        from src.services.alignment import TrustScoreCalculator

        calc = TrustScoreCalculator()
        assert calc is not None

    def test_get_or_create_agent(self) -> None:
        """Test getting or creating agent records."""
        from src.services.alignment import TrustScoreCalculator

        calc = TrustScoreCalculator()

        record = calc.get_or_create_agent("agent-1")
        assert record.agent_id == "agent-1"
        # Initial score is 0.35 because override_acceptance=1.0 and
        # negative_outcome_absence=1.0 contribute: 0.20*1.0 + 0.15*1.0 = 0.35
        assert record.trust_score == pytest.approx(0.35, rel=0.01)

        # Second call returns same record
        record2 = calc.get_or_create_agent("agent-1")
        assert record2 is record

    def test_autonomy_level_from_score(self) -> None:
        """Test autonomy level determination from score."""
        from src.services.alignment import AutonomyLevel

        assert AutonomyLevel.from_trust_score(0.1) == AutonomyLevel.OBSERVE
        assert AutonomyLevel.from_trust_score(0.3) == AutonomyLevel.RECOMMEND
        assert AutonomyLevel.from_trust_score(0.6) == AutonomyLevel.EXECUTE_REVIEW
        assert AutonomyLevel.from_trust_score(0.9) == AutonomyLevel.AUTONOMOUS

    def test_record_action_outcome_success(self) -> None:
        """Test recording successful action outcomes."""
        from src.services.alignment import TrustScoreCalculator

        calc = TrustScoreCalculator()

        for i in range(5):
            calc.record_action_outcome("agent-1", was_successful=True)

        record = calc.get_agent_record("agent-1")
        assert record.consecutive_successes == 5
        assert record.components.actions_successful == 5

    def test_record_action_outcome_failure_resets_streak(self) -> None:
        """Test failure resets consecutive success streak."""
        from src.services.alignment import TrustScoreCalculator

        calc = TrustScoreCalculator()

        for i in range(5):
            calc.record_action_outcome("agent-1", was_successful=True)

        calc.record_action_outcome("agent-1", was_successful=False)

        record = calc.get_agent_record("agent-1")
        assert record.consecutive_successes == 0
        assert record.failures_in_7_days == 1

    def test_promotion_after_consecutive_successes(self) -> None:
        """Test agent is promoted after 10 consecutive successes."""
        from src.services.alignment import AutonomyLevel, TrustScoreCalculator

        calc = TrustScoreCalculator()

        # Start at OBSERVE level
        record = calc.get_or_create_agent("agent-1")
        assert record.current_level == AutonomyLevel.OBSERVE

        # Record 10 successes
        transition = None
        for i in range(10):
            transition = calc.record_action_outcome("agent-1", was_successful=True)

        # Should be promoted
        assert transition is not None
        assert transition.is_promotion
        assert transition.new_level == AutonomyLevel.RECOMMEND

    def test_demotion_on_critical_failure(self) -> None:
        """Test agent is demoted on critical failure."""
        from src.services.alignment import AutonomyLevel, TrustScoreCalculator

        calc = TrustScoreCalculator()

        # Get agent to RECOMMEND level
        for i in range(10):
            calc.record_action_outcome("agent-1", was_successful=True)

        record = calc.get_agent_record("agent-1")
        assert record.current_level == AutonomyLevel.RECOMMEND

        # Critical failure
        transition = calc.record_action_outcome(
            "agent-1",
            was_successful=False,
            is_critical=True,
        )

        assert transition is not None
        assert transition.is_demotion
        assert transition.new_level == AutonomyLevel.OBSERVE

    def test_demotion_on_multiple_minor_failures(self) -> None:
        """Test agent is demoted after 3 minor failures in 7 days."""
        from src.services.alignment import AutonomyLevel, TrustScoreCalculator

        calc = TrustScoreCalculator()

        # Get agent to RECOMMEND level
        for i in range(10):
            calc.record_action_outcome("agent-1", was_successful=True)

        record = calc.get_agent_record("agent-1")
        assert record.current_level == AutonomyLevel.RECOMMEND

        # 3 minor failures
        for i in range(3):
            transition = calc.record_action_outcome("agent-1", was_successful=False)

        assert transition is not None
        assert transition.is_demotion

    def test_manual_level_override(self) -> None:
        """Test manual level override by human."""
        from src.services.alignment import AutonomyLevel, TrustScoreCalculator

        calc = TrustScoreCalculator()

        transition = calc.set_manual_level(
            "agent-1",
            AutonomyLevel.AUTONOMOUS,
            reason="Trusted agent for critical ops",
            set_by="admin",
        )

        assert transition.triggered_by == "manual"
        record = calc.get_agent_record("agent-1")
        assert record.effective_level == AutonomyLevel.AUTONOMOUS
        assert record.manually_set_level == AutonomyLevel.AUTONOMOUS

    def test_clear_manual_level(self) -> None:
        """Test clearing manual level override."""
        from src.services.alignment import AutonomyLevel, TrustScoreCalculator

        calc = TrustScoreCalculator()

        calc.set_manual_level(
            "agent-1",
            AutonomyLevel.AUTONOMOUS,
            reason="Testing",
            set_by="admin",
        )

        calc.clear_manual_level("agent-1", "Returning to calculated level")

        record = calc.get_agent_record("agent-1")
        assert record.manually_set_level is None
        # Initial score 0.35 puts agent in RECOMMEND level (0.25-0.50)
        assert record.effective_level == AutonomyLevel.RECOMMEND

    def test_record_override_response(self) -> None:
        """Test recording override responses."""
        from src.services.alignment import TrustScoreCalculator

        calc = TrustScoreCalculator()

        calc.record_override_response("agent-1", accepted_gracefully=True)
        record = calc.get_agent_record("agent-1")
        assert record.components.overrides_accepted == 1

        calc.record_override_response("agent-1", accepted_gracefully=False)
        assert record.failures_in_7_days == 1  # Treated as minor failure

    def test_record_negative_outcome(self) -> None:
        """Test recording negative outcomes."""
        from src.services.alignment import TrustScoreCalculator

        calc = TrustScoreCalculator()

        calc.record_negative_outcome("agent-1", "security_incident", "critical")

        record = calc.get_agent_record("agent-1")
        assert record.critical_failures == 1
        assert record.components.negative_outcome_absence < 1.0

    def test_get_summary(self) -> None:
        """Test getting trust summary."""
        from src.services.alignment import TrustScoreCalculator

        calc = TrustScoreCalculator()

        calc.get_or_create_agent("agent-1")
        calc.get_or_create_agent("agent-2")

        summary = calc.get_summary()
        assert summary["total_agents"] == 2
        assert "by_level" in summary
        assert "avg_trust_score" in summary

    def test_get_low_trust_agents(self) -> None:
        """Test getting low trust agents."""
        from src.services.alignment import TrustScoreCalculator

        calc = TrustScoreCalculator()

        calc.get_or_create_agent("agent-1")  # Score 0.0

        # Manually set high score for agent-2
        record = calc.get_or_create_agent("agent-2")
        for _ in range(20):
            record.components.record_action(was_successful=True)

        low_trust = calc.get_low_trust_agents(threshold=0.5)
        assert len(low_trust) == 1
        assert low_trust[0].agent_id == "agent-1"

    def test_transition_callback(self) -> None:
        """Test transition callback is invoked."""
        from src.services.alignment import TrustScoreCalculator

        callback = MagicMock()
        calc = TrustScoreCalculator(on_transition=callback)

        for i in range(10):
            calc.record_action_outcome("agent-1", was_successful=True)

        callback.assert_called()

    def test_trust_score_components(self) -> None:
        """Test trust score component calculation."""
        from src.services.alignment import TrustScoreComponents

        components = TrustScoreComponents()

        # Record some data
        components.record_action(was_successful=True)
        components.record_action(was_successful=True)
        components.record_action(was_successful=False)

        assert components.success_rate == pytest.approx(2 / 3, rel=0.01)

        # Check weighted score
        score = components.calculate_score()
        assert 0 <= score <= 1


class TestReversibilityClassifier:
    """Tests for ReversibilityClassifier."""

    def test_initialization(self) -> None:
        """Test classifier initializes correctly."""
        from src.services.alignment import ReversibilityClassifier

        classifier = ReversibilityClassifier()
        assert classifier is not None

    def test_classify_fully_reversible(self) -> None:
        """Test classification of fully reversible actions."""
        from src.services.alignment import (
            ActionClass,
            ActionMetadata,
            ReversibilityClassifier,
        )

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="code_change",
            target_resource="src/main.py",
            target_resource_type="file",
        )

        result = classifier.classify(metadata)
        assert result == ActionClass.FULLY_REVERSIBLE

    def test_classify_partially_reversible(self) -> None:
        """Test classification of partially reversible actions."""
        from src.services.alignment import (
            ActionClass,
            ActionMetadata,
            ReversibilityClassifier,
        )

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="data_modification",
            target_resource="users_table",
            target_resource_type="database",
        )

        result = classifier.classify(metadata)
        assert result == ActionClass.PARTIALLY_REVERSIBLE

    def test_classify_irreversible(self) -> None:
        """Test classification of irreversible actions."""
        from src.services.alignment import (
            ActionClass,
            ActionMetadata,
            ReversibilityClassifier,
        )

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="data_deletion",
            target_resource="users_table",
            target_resource_type="database",
            is_destructive=True,
        )

        result = classifier.classify(metadata)
        assert result == ActionClass.IRREVERSIBLE

    def test_classify_escalation_to_irreversible(self) -> None:
        """Test that destructive production actions escalate to irreversible."""
        from src.services.alignment import (
            ActionClass,
            ActionMetadata,
            ReversibilityClassifier,
        )

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="code_change",  # Normally fully reversible
            target_resource="src/main.py",
            target_resource_type="file",
            is_production=True,
            is_destructive=True,
        )

        result = classifier.classify(metadata)
        assert result == ActionClass.IRREVERSIBLE

    def test_pre_action_check_class_a(self) -> None:
        """Test pre-action check creates snapshot for Class A."""
        from src.services.alignment import ActionMetadata, ReversibilityClassifier

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="code_change",
            target_resource="src/main.py",
            target_resource_type="file",
        )

        current_state = {"content": "original code"}

        approval = classifier.pre_action_check(
            action_id="act-1",
            metadata=metadata,
            agent_autonomy_level=2,
            current_state=current_state,
        )

        assert approval.approved is True
        assert approval.snapshot is not None
        assert approval.snapshot.state_data == current_state

    def test_pre_action_check_class_b(self) -> None:
        """Test pre-action check generates rollback plan for Class B."""
        from src.services.alignment import ActionMetadata, ReversibilityClassifier

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="deployment",
            target_resource="api-service",
            target_resource_type="kubernetes",
        )

        approval = classifier.pre_action_check(
            action_id="act-1",
            metadata=metadata,
            agent_autonomy_level=2,
        )

        assert approval.approved is True
        assert approval.rollback_plan is not None
        assert len(approval.rollback_plan.steps) > 0

    def test_pre_action_check_class_c_requires_approval(self) -> None:
        """Test pre-action check requires human approval for Class C."""
        from src.services.alignment import ActionMetadata, ReversibilityClassifier

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="data_deletion",
            target_resource="users_table",
            target_resource_type="database",
        )

        approval = classifier.pre_action_check(
            action_id="act-1",
            metadata=metadata,
            agent_autonomy_level=3,
        )

        assert approval.approved is False
        assert approval.requires_human_approval is True

    def test_pre_action_check_insufficient_autonomy(self) -> None:
        """Test pre-action check rejects when autonomy level insufficient."""
        from src.services.alignment import ActionMetadata, ReversibilityClassifier

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="code_change",
            target_resource="src/main.py",
            target_resource_type="file",
        )

        approval = classifier.pre_action_check(
            action_id="act-1",
            metadata=metadata,
            agent_autonomy_level=1,  # RECOMMEND level, needs 2
        )

        assert approval.approved is False
        assert "insufficient" in approval.rejection_reason.lower()

    def test_approve_irreversible_action(self) -> None:
        """Test approving irreversible action by human."""
        from src.services.alignment import ReversibilityClassifier

        classifier = ReversibilityClassifier()

        approval = classifier.approve_irreversible_action(
            action_id="act-1",
            approved_by="admin",
            reason="Required for critical cleanup",
        )

        assert approval.approved is True
        assert approval.requires_human_approval is False

    def test_snapshot_integrity(self) -> None:
        """Test snapshot integrity verification."""
        from src.services.alignment import StateSnapshot

        snapshot = StateSnapshot(
            snapshot_id="snap-1",
            action_id="act-1",
            resource_type="file",
            resource_id="src/main.py",
            state_data={"content": "test"},
        )

        assert snapshot.verify_integrity() is True

        # Tamper with data
        snapshot.state_data["content"] = "modified"
        assert snapshot.verify_integrity() is False

    def test_rollback_plan_viability(self) -> None:
        """Test rollback plan viability for non-reversible actions."""
        from src.services.alignment import ActionMetadata, ReversibilityClassifier

        classifier = ReversibilityClassifier()

        metadata = ActionMetadata(
            action_type="email_send",
            target_resource="user@example.com",
            target_resource_type="email",
            has_side_effects=True,
        )

        approval = classifier.pre_action_check(
            action_id="act-1",
            metadata=metadata,
            agent_autonomy_level=2,
        )

        # Email send should have non-viable rollback plan
        assert approval.rollback_plan is not None
        assert approval.rollback_plan.is_viable is False

    def test_get_metrics(self) -> None:
        """Test getting reversibility metrics."""
        from src.services.alignment import ActionMetadata, ReversibilityClassifier

        classifier = ReversibilityClassifier()

        metadata_a = ActionMetadata(
            action_type="code_change",
            target_resource="file.py",
            target_resource_type="file",
        )
        metadata_c = ActionMetadata(
            action_type="data_deletion",
            target_resource="table",
            target_resource_type="database",
        )

        classifier.pre_action_check("act-1", metadata_a, 2)
        classifier.pre_action_check("act-2", metadata_c, 3)

        metrics = classifier.get_metrics()
        assert metrics["classifications"]["class_a"] == 1
        assert metrics["classifications"]["class_c"] == 1


class TestDecisionAuditLogger:
    """Tests for DecisionAuditLogger."""

    def test_initialization(self) -> None:
        """Test logger initializes correctly."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger()
        assert logger_service is not None

    def test_create_decision_record(self) -> None:
        """Test creating a decision record."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger()

        record = logger_service.create_decision_record(
            decision_id="dec-1",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Reviewed security changes",
        )

        assert record.decision_id == "dec-1"
        assert record.agent_id == "agent-1"

    def test_add_reasoning_chain(self) -> None:
        """Test adding reasoning steps."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger()

        record = logger_service.create_decision_record(
            decision_id="dec-1",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Review",
        )

        logger_service.add_reasoning_step(
            record,
            step_number=1,
            description="Identified SQL query pattern",
            evidence=["Line 45: string concatenation"],
            confidence=0.95,
        )
        logger_service.add_reasoning_step(
            record,
            step_number=2,
            description="Checked against OWASP guidelines",
            references=["OWASP A03:2021"],
        )

        assert len(record.reasoning_chain) == 2
        assert record.reasoning_chain[0].step_number == 1

    def test_add_alternatives(self) -> None:
        """Test adding alternative options."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger()

        record = logger_service.create_decision_record(
            decision_id="dec-1",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Review",
        )

        logger_service.add_alternative(
            record,
            option_id="opt-1",
            description="Parameterized queries",
            confidence=0.95,
            pros=["Standard solution", "Secure"],
            was_chosen=True,
        )
        logger_service.add_alternative(
            record,
            option_id="opt-2",
            description="Input sanitization",
            confidence=0.70,
            cons=["Can be bypassed"],
            rejection_reason="Less secure",
        )

        assert len(record.alternatives) == 2
        assert record.has_alternatives() is True

    def test_set_uncertainty(self) -> None:
        """Test setting uncertainty disclosure."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger()

        record = logger_service.create_decision_record(
            decision_id="dec-1",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Review",
        )

        logger_service.set_uncertainty(
            record,
            overall_confidence=0.85,
            uncertainty_factors=["Legacy code patterns unclear"],
            validation_recommendations=["Manual review of edge cases"],
        )

        assert record.uncertainty.overall_confidence == 0.85
        assert len(record.uncertainty.uncertainty_factors) == 1

    def test_validate_record_missing_reasoning(self) -> None:
        """Test validation fails without reasoning chain."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger(require_reasoning_chain=True)

        record = logger_service.create_decision_record(
            decision_id="dec-1",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Review",
        )

        is_valid, issues = logger_service.validate_record(record)
        assert is_valid is False
        assert any("reasoning" in issue.lower() for issue in issues)

    def test_validate_record_complete(self) -> None:
        """Test validation passes with complete record."""
        from src.services.alignment import DecisionAuditLogger
        from src.services.alignment.audit_logger import DecisionSeverity

        logger_service = DecisionAuditLogger()

        record = logger_service.create_decision_record(
            decision_id="dec-1",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Review",
            severity=DecisionSeverity.SIGNIFICANT,
        )

        logger_service.add_context(
            record,
            knowledge_sources=["file.py"],
            user_instructions="Review for security",
        )
        logger_service.add_reasoning_step(record, 1, "Analyzed code", confidence=0.9)
        logger_service.add_alternative(
            record, "opt-1", "Option A", 0.9, was_chosen=True
        )
        logger_service.add_alternative(record, "opt-2", "Option B", 0.7)
        logger_service.set_uncertainty(record, 0.9)

        is_valid, issues = logger_service.validate_record(record)
        assert is_valid is True
        assert len(issues) == 0

    def test_log_decision(self) -> None:
        """Test logging a decision."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger(
            require_reasoning_chain=False,
            require_alternatives=False,
        )

        record = logger_service.create_decision_record(
            decision_id="dec-1",
            agent_id="agent-1",
            decision_type="code_review",
            decision_summary="Review",
        )
        logger_service.add_context(record, user_instructions="Review code")
        logger_service.set_uncertainty(record, 0.9)

        success, issues = logger_service.log_decision(record)
        assert success is True

        # Retrieve logged decision
        retrieved = logger_service.get_decision("dec-1")
        assert retrieved is not None
        assert retrieved.decision_id == "dec-1"

    def test_update_outcome(self) -> None:
        """Test updating decision outcome."""
        from src.services.alignment import DecisionAuditLogger
        from src.services.alignment.audit_logger import DecisionOutcome

        logger_service = DecisionAuditLogger(
            require_reasoning_chain=False,
            require_alternatives=False,
        )

        record = logger_service.create_decision_record(
            "dec-1", "agent-1", "review", "Review"
        )
        logger_service.add_context(record, user_instructions="Review")
        logger_service.set_uncertainty(record, 0.9)
        logger_service.log_decision(record)

        success = logger_service.update_outcome("dec-1", DecisionOutcome.SUCCESSFUL)
        assert success is True

        retrieved = logger_service.get_decision("dec-1")
        assert retrieved.outcome == DecisionOutcome.SUCCESSFUL

    def test_record_human_review(self) -> None:
        """Test recording human review."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger(
            require_reasoning_chain=False,
            require_alternatives=False,
        )

        record = logger_service.create_decision_record(
            "dec-1", "agent-1", "review", "Review"
        )
        logger_service.add_context(record, user_instructions="Review")
        logger_service.set_uncertainty(record, 0.9)
        logger_service.log_decision(record)

        success = logger_service.record_human_review(
            "dec-1",
            reviewer="admin",
            comments="Looks good",
        )
        assert success is True

        retrieved = logger_service.get_decision("dec-1")
        assert retrieved.human_reviewed is True
        assert retrieved.human_reviewer == "admin"

    def test_get_decisions_by_agent(self) -> None:
        """Test getting decisions by agent."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger(
            require_reasoning_chain=False,
            require_alternatives=False,
        )

        for i in range(3):
            record = logger_service.create_decision_record(
                f"dec-{i}", "agent-1", "review", "Review"
            )
            logger_service.add_context(record, user_instructions="Review")
            logger_service.set_uncertainty(record, 0.9)
            logger_service.log_decision(record)

        decisions = logger_service.get_decisions_by_agent("agent-1")
        assert len(decisions) == 3

    def test_get_decisions_needing_review(self) -> None:
        """Test getting unreviewed significant decisions."""
        from src.services.alignment import DecisionAuditLogger
        from src.services.alignment.audit_logger import DecisionSeverity

        logger_service = DecisionAuditLogger(
            require_reasoning_chain=False,
            require_alternatives=False,
        )

        record = logger_service.create_decision_record(
            "dec-1",
            "agent-1",
            "review",
            "Review",
            severity=DecisionSeverity.CRITICAL,
        )
        logger_service.add_context(record, user_instructions="Review")
        logger_service.set_uncertainty(record, 0.9)
        logger_service.log_decision(record)

        needing_review = logger_service.get_decisions_needing_review()
        assert len(needing_review) == 1

    def test_get_metrics(self) -> None:
        """Test getting audit metrics."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger(
            require_reasoning_chain=False,
            require_alternatives=False,
        )

        record = logger_service.create_decision_record(
            "dec-1", "agent-1", "review", "Review"
        )
        logger_service.add_context(record, user_instructions="Review")
        logger_service.set_uncertainty(record, 0.9)
        logger_service.add_reasoning_step(record, 1, "Step")
        logger_service.log_decision(record)

        metrics = logger_service.get_metrics()
        assert metrics["total_decisions"] == 1
        assert metrics["decisions_stored"] == 1

    def test_export_decisions(self) -> None:
        """Test exporting decisions."""
        from src.services.alignment import DecisionAuditLogger

        logger_service = DecisionAuditLogger(
            require_reasoning_chain=False,
            require_alternatives=False,
        )

        record = logger_service.create_decision_record(
            "dec-1", "agent-1", "review", "Review"
        )
        logger_service.add_context(record, user_instructions="Review")
        logger_service.set_uncertainty(record, 0.9)
        logger_service.log_decision(record)

        exported = logger_service.export_decisions()
        assert len(exported) == 1
        assert exported[0]["decision_id"] == "dec-1"

    def test_decision_record_integrity(self) -> None:
        """Test decision record integrity verification."""
        from src.services.alignment import DecisionRecord

        record = DecisionRecord(
            decision_id="dec-1",
            agent_id="agent-1",
            decision_type="review",
            decision_summary="Review",
        )

        assert record.verify_integrity() is True

        # Tamper
        record.decision_summary = "Modified"
        assert record.verify_integrity() is False


class TestPackageExports:
    """Test that package exports are correct."""

    def test_all_exports_available(self) -> None:
        """Test all expected exports are available."""
        from src.services import alignment

        # Metrics Service
        assert hasattr(alignment, "AlignmentMetricsService")
        assert hasattr(alignment, "AlignmentHealth")
        assert hasattr(alignment, "AntiSycophancyMetrics")
        assert hasattr(alignment, "MetricThresholds")

        # Trust Calculator
        assert hasattr(alignment, "TrustScoreCalculator")
        assert hasattr(alignment, "TrustScoreComponents")
        assert hasattr(alignment, "TrustTransition")
        assert hasattr(alignment, "AutonomyLevel")

        # Reversibility
        assert hasattr(alignment, "ReversibilityClassifier")
        assert hasattr(alignment, "ActionClass")
        assert hasattr(alignment, "ActionMetadata")
        assert hasattr(alignment, "RollbackPlan")
        assert hasattr(alignment, "StateSnapshot")

        # Audit Logger
        assert hasattr(alignment, "DecisionAuditLogger")
        assert hasattr(alignment, "DecisionRecord")
        assert hasattr(alignment, "ReasoningStep")
        assert hasattr(alignment, "AlternativeOption")
        assert hasattr(alignment, "UncertaintyDisclosure")


class TestIntegration:
    """Integration tests for alignment services working together."""

    def test_full_alignment_workflow(self) -> None:
        """Test complete alignment workflow across all services."""
        from src.services.alignment import (
            ActionMetadata,
            AlignmentMetricsService,
            DecisionAuditLogger,
            ReversibilityClassifier,
            TrustScoreCalculator,
        )
        from src.services.alignment.audit_logger import DecisionSeverity

        # Initialize all services
        metrics = AlignmentMetricsService()
        trust = TrustScoreCalculator()
        reversibility = ReversibilityClassifier()
        audit = DecisionAuditLogger(
            require_reasoning_chain=False,
            require_alternatives=False,
        )

        agent_id = "security-agent-1"

        # 1. Agent makes a decision
        record = audit.create_decision_record(
            decision_id="dec-001",
            agent_id=agent_id,
            decision_type="vulnerability_assessment",
            decision_summary="SQL injection vulnerability detected",
            severity=DecisionSeverity.SIGNIFICANT,
        )
        audit.add_context(record, knowledge_sources=["auth.py"])
        audit.set_uncertainty(record, 0.92)
        audit.add_reasoning_step(record, 1, "Found SQL pattern")
        audit.log_decision(record)

        # 2. Record the decision in metrics
        metrics.record_decision(
            decision_id="dec-001",
            agent_id=agent_id,
            alternatives_shown=True,
            has_audit_trail=True,
            has_reasoning_chain=True,
            has_source_attribution=True,
            has_uncertainty_disclosure=True,
        )

        # 3. Check action reversibility before proceeding
        action_metadata = ActionMetadata(
            action_type="code_change",
            target_resource="auth.py",
            target_resource_type="file",
            agent_id=agent_id,
        )

        # Get agent's current autonomy level
        autonomy = trust.get_autonomy_level(agent_id)
        approval = reversibility.pre_action_check(
            action_id="act-001",
            metadata=action_metadata,
            agent_autonomy_level=autonomy.value,
            current_state={"content": "original"},
        )

        # 4. Record action outcome
        if approval.approved:
            metrics.record_action("act-001", "A", has_snapshot=True)
            trust.record_action_outcome(agent_id, was_successful=True)

        # 5. Check overall alignment health
        health = metrics.get_health()
        assert health is not None

        # 6. Verify trust score updated
        score = trust.get_trust_score(agent_id)
        assert score > 0

    def test_alignment_metrics_integration(self) -> None:
        """Test metrics service integration with trust calculator."""
        from src.services.alignment import AlignmentMetricsService, TrustScoreCalculator

        metrics = AlignmentMetricsService()
        trust = TrustScoreCalculator()

        agent_id = "agent-1"

        # Build up trust
        for i in range(10):
            trust.record_action_outcome(agent_id, was_successful=True)

        # Report to metrics
        score = trust.get_trust_score(agent_id)
        metrics.update_agent_trust_score(agent_id, score)

        # Check metrics reflect trust data
        summary = metrics.get_metrics_summary()
        assert summary["trust"]["avg_trust_score"] > 0
