"""
Tests for Trust Score Calculator (ADR-052 Phase 1).

Tests cover:
- AutonomyLevel enum and methods
- TrustTransition dataclass
- TrustScoreComponents calculations
- AgentTrustRecord tracking
- TrustScoreCalculator promotion/demotion logic
"""

import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.alignment.trust_calculator import (
    AgentTrustRecord,
    AutonomyLevel,
    TrustScoreCalculator,
    TrustScoreComponents,
    TrustTransition,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestAutonomyLevel:
    """Tests for AutonomyLevel enum."""

    def test_autonomy_level_values(self):
        """Test that autonomy levels have correct integer values."""
        assert AutonomyLevel.OBSERVE.value == 0
        assert AutonomyLevel.RECOMMEND.value == 1
        assert AutonomyLevel.EXECUTE_REVIEW.value == 2
        assert AutonomyLevel.AUTONOMOUS.value == 3

    def test_from_trust_score_observe(self):
        """Test OBSERVE level for low trust scores."""
        assert AutonomyLevel.from_trust_score(0.0) == AutonomyLevel.OBSERVE
        assert AutonomyLevel.from_trust_score(0.10) == AutonomyLevel.OBSERVE
        assert AutonomyLevel.from_trust_score(0.24) == AutonomyLevel.OBSERVE

    def test_from_trust_score_recommend(self):
        """Test RECOMMEND level for medium-low trust scores."""
        assert AutonomyLevel.from_trust_score(0.25) == AutonomyLevel.RECOMMEND
        assert AutonomyLevel.from_trust_score(0.35) == AutonomyLevel.RECOMMEND
        assert AutonomyLevel.from_trust_score(0.49) == AutonomyLevel.RECOMMEND

    def test_from_trust_score_execute_review(self):
        """Test EXECUTE_REVIEW level for medium-high trust scores."""
        assert AutonomyLevel.from_trust_score(0.50) == AutonomyLevel.EXECUTE_REVIEW
        assert AutonomyLevel.from_trust_score(0.60) == AutonomyLevel.EXECUTE_REVIEW
        assert AutonomyLevel.from_trust_score(0.74) == AutonomyLevel.EXECUTE_REVIEW

    def test_from_trust_score_autonomous(self):
        """Test AUTONOMOUS level for high trust scores."""
        assert AutonomyLevel.from_trust_score(0.75) == AutonomyLevel.AUTONOMOUS
        assert AutonomyLevel.from_trust_score(0.90) == AutonomyLevel.AUTONOMOUS
        assert AutonomyLevel.from_trust_score(1.0) == AutonomyLevel.AUTONOMOUS

    def test_description_property(self):
        """Test that each level has a description."""
        for level in AutonomyLevel:
            desc = level.description
            assert isinstance(desc, str)
            assert len(desc) > 10

    def test_min_trust_score_property(self):
        """Test minimum trust score thresholds."""
        assert AutonomyLevel.OBSERVE.min_trust_score == 0.0
        assert AutonomyLevel.RECOMMEND.min_trust_score == 0.25
        assert AutonomyLevel.EXECUTE_REVIEW.min_trust_score == 0.50
        assert AutonomyLevel.AUTONOMOUS.min_trust_score == 0.75


class TestTrustTransition:
    """Tests for TrustTransition dataclass."""

    def test_is_promotion(self):
        """Test promotion detection."""
        transition = TrustTransition(
            agent_id="agent-1",
            timestamp=datetime.now(timezone.utc),
            old_level=AutonomyLevel.OBSERVE,
            new_level=AutonomyLevel.RECOMMEND,
            old_score=0.20,
            new_score=0.30,
            reason="10 consecutive successes",
            triggered_by="automatic",
        )
        assert transition.is_promotion is True
        assert transition.is_demotion is False

    def test_is_demotion(self):
        """Test demotion detection."""
        transition = TrustTransition(
            agent_id="agent-1",
            timestamp=datetime.now(timezone.utc),
            old_level=AutonomyLevel.AUTONOMOUS,
            new_level=AutonomyLevel.EXECUTE_REVIEW,
            old_score=0.80,
            new_score=0.70,
            reason="Critical failure",
            triggered_by="automatic",
        )
        assert transition.is_demotion is True
        assert transition.is_promotion is False

    def test_same_level_transition(self):
        """Test neither promotion nor demotion."""
        transition = TrustTransition(
            agent_id="agent-1",
            timestamp=datetime.now(timezone.utc),
            old_level=AutonomyLevel.RECOMMEND,
            new_level=AutonomyLevel.RECOMMEND,
            old_score=0.30,
            new_score=0.35,
            reason="Score changed but level unchanged",
            triggered_by="automatic",
        )
        assert transition.is_promotion is False
        assert transition.is_demotion is False

    def test_to_dict(self):
        """Test dictionary conversion."""
        now = datetime.now(timezone.utc)
        transition = TrustTransition(
            agent_id="agent-1",
            timestamp=now,
            old_level=AutonomyLevel.OBSERVE,
            new_level=AutonomyLevel.RECOMMEND,
            old_score=0.20,
            new_score=0.30,
            reason="Test reason",
            triggered_by="manual",
        )
        result = transition.to_dict()

        assert result["agent_id"] == "agent-1"
        assert result["timestamp"] == now.isoformat()
        assert result["old_level"] == "OBSERVE"
        assert result["new_level"] == "RECOMMEND"
        assert result["old_score"] == 0.20
        assert result["new_score"] == 0.30
        assert result["reason"] == "Test reason"
        assert result["triggered_by"] == "manual"
        assert result["is_promotion"] is True
        assert result["is_demotion"] is False


class TestTrustScoreComponents:
    """Tests for TrustScoreComponents dataclass."""

    def test_default_initialization(self):
        """Test default values."""
        components = TrustScoreComponents()
        assert components.success_rate == 0.0
        assert components.confidence_calibration == 0.0
        assert components.override_acceptance == 1.0
        assert components.negative_outcome_absence == 1.0

    def test_calculate_score_initial(self):
        """Test initial score calculation."""
        components = TrustScoreComponents()
        # (0.0 * 0.40) + (0.0 * 0.25) + (1.0 * 0.20) + (1.0 * 0.15) = 0.35
        assert components.calculate_score() == pytest.approx(0.35)

    def test_calculate_score_perfect(self):
        """Test perfect score calculation."""
        components = TrustScoreComponents()
        components.success_rate = 1.0
        components.confidence_calibration = 1.0
        components.override_acceptance = 1.0
        components.negative_outcome_absence = 1.0
        assert components.calculate_score() == pytest.approx(1.0)

    def test_record_action_success(self):
        """Test recording successful actions."""
        components = TrustScoreComponents()
        components.record_action(was_successful=True)
        assert components.actions_total == 1
        assert components.actions_successful == 1
        assert components.success_rate == 1.0

    def test_record_action_failure(self):
        """Test recording failed actions."""
        components = TrustScoreComponents()
        components.record_action(was_successful=False)
        assert components.actions_total == 1
        assert components.actions_successful == 0
        assert components.success_rate == 0.0

    def test_record_action_mixed(self):
        """Test recording mixed success/failure."""
        components = TrustScoreComponents()
        components.record_action(was_successful=True)
        components.record_action(was_successful=True)
        components.record_action(was_successful=False)
        assert components.actions_total == 3
        assert components.actions_successful == 2
        assert components.success_rate == pytest.approx(2 / 3)

    def test_record_prediction_accurate(self):
        """Test recording accurate predictions."""
        components = TrustScoreComponents()
        components.record_prediction(confidence=0.8, was_accurate=True)
        assert components.predictions_total == 1
        assert components.predictions_accurate == 1
        assert components.confidence_calibration == 1.0

    def test_record_prediction_inaccurate(self):
        """Test recording inaccurate predictions."""
        components = TrustScoreComponents()
        components.record_prediction(confidence=0.9, was_accurate=False)
        assert components.predictions_total == 1
        assert components.predictions_accurate == 0
        assert components.confidence_calibration == 0.0

    def test_record_override_graceful(self):
        """Test recording graceful override acceptance."""
        components = TrustScoreComponents()
        components.record_override(was_accepted_gracefully=True)
        assert components.overrides_total == 1
        assert components.overrides_accepted == 1
        assert components.override_acceptance == 1.0

    def test_record_override_not_graceful(self):
        """Test recording non-graceful override."""
        components = TrustScoreComponents()
        components.record_override(was_accepted_gracefully=False)
        assert components.overrides_total == 1
        assert components.overrides_accepted == 0
        assert components.override_acceptance == 0.0

    def test_record_negative_outcome(self):
        """Test recording negative outcomes."""
        components = TrustScoreComponents()
        assert components.negative_outcome_absence == 1.0

        components.record_negative_outcome()
        assert components.negative_outcomes == 1
        assert components.negative_outcome_absence == 0.9

        components.record_negative_outcome()
        assert components.negative_outcomes == 2
        assert components.negative_outcome_absence == 0.8

    def test_negative_outcome_floor(self):
        """Test that negative outcome absence has a floor of 0."""
        components = TrustScoreComponents()
        for _ in range(15):
            components.record_negative_outcome()
        assert components.negative_outcome_absence == 0.0

    def test_to_dict(self):
        """Test dictionary conversion with all fields."""
        components = TrustScoreComponents()
        components.record_action(was_successful=True)
        components.record_prediction(confidence=0.8, was_accurate=True)

        result = components.to_dict()

        assert "score" in result
        assert "components" in result
        assert "tracking" in result
        assert "window_start" in result
        assert result["tracking"]["actions_total"] == 1
        assert result["tracking"]["predictions_total"] == 1


class TestAgentTrustRecord:
    """Tests for AgentTrustRecord dataclass."""

    def test_default_initialization(self):
        """Test default record values."""
        record = AgentTrustRecord(agent_id="agent-1")
        assert record.agent_id == "agent-1"
        assert record.current_level == AutonomyLevel.OBSERVE
        assert record.consecutive_successes == 0
        assert record.manually_set_level is None

    def test_trust_score_property(self):
        """Test trust_score property."""
        record = AgentTrustRecord(agent_id="agent-1")
        # Initial score from components
        assert record.trust_score == pytest.approx(0.35)

    def test_effective_level_without_override(self):
        """Test effective level without manual override."""
        record = AgentTrustRecord(agent_id="agent-1")
        record.current_level = AutonomyLevel.RECOMMEND
        assert record.effective_level == AutonomyLevel.RECOMMEND

    def test_effective_level_with_override(self):
        """Test effective level with manual override."""
        record = AgentTrustRecord(agent_id="agent-1")
        record.current_level = AutonomyLevel.RECOMMEND
        record.manually_set_level = AutonomyLevel.AUTONOMOUS
        assert record.effective_level == AutonomyLevel.AUTONOMOUS

    def test_to_dict(self):
        """Test dictionary conversion."""
        record = AgentTrustRecord(agent_id="agent-1")
        result = record.to_dict()

        assert result["agent_id"] == "agent-1"
        assert "trust_score" in result
        assert result["current_level"] == "OBSERVE"
        assert result["effective_level"] == "OBSERVE"
        assert result["manually_set_level"] is None
        assert "components" in result
        assert "recent_transitions" in result


class TestTrustScoreCalculator:
    """Tests for TrustScoreCalculator class."""

    @pytest.fixture
    def calculator(self):
        """Create a fresh calculator for each test."""
        return TrustScoreCalculator()

    def test_initialization(self, calculator):
        """Test calculator initialization."""
        assert calculator._agents == {}

    def test_get_or_create_agent_new(self, calculator):
        """Test creating a new agent record."""
        record = calculator.get_or_create_agent("agent-1")
        assert record.agent_id == "agent-1"
        assert record.current_level == AutonomyLevel.OBSERVE

    def test_get_or_create_agent_existing(self, calculator):
        """Test getting existing agent record."""
        record1 = calculator.get_or_create_agent("agent-1")
        record1.consecutive_successes = 5
        record2 = calculator.get_or_create_agent("agent-1")
        assert record2.consecutive_successes == 5
        assert record1 is record2

    def test_get_trust_score(self, calculator):
        """Test getting trust score."""
        score = calculator.get_trust_score("agent-1")
        assert score == pytest.approx(0.35)  # Initial score

    def test_get_autonomy_level(self, calculator):
        """Test getting autonomy level."""
        level = calculator.get_autonomy_level("agent-1")
        assert level == AutonomyLevel.OBSERVE

    def test_record_action_outcome_success(self, calculator):
        """Test recording successful action outcome."""
        result = calculator.record_action_outcome("agent-1", was_successful=True)
        assert result is None  # No transition on first success

        record = calculator.get_agent_record("agent-1")
        assert record.consecutive_successes == 1
        assert record.components.actions_total == 1
        assert record.components.actions_successful == 1

    def test_record_action_outcome_failure(self, calculator):
        """Test recording failed action outcome."""
        calculator.record_action_outcome("agent-1", was_successful=True)
        calculator.record_action_outcome("agent-1", was_successful=False)

        record = calculator.get_agent_record("agent-1")
        assert record.consecutive_successes == 0
        assert record.failures_in_7_days == 1

    def test_record_action_outcome_critical_failure(self, calculator):
        """Test recording critical failure."""
        calculator.record_action_outcome(
            "agent-1", was_successful=False, is_critical=True
        )

        record = calculator.get_agent_record("agent-1")
        assert record.critical_failures == 1
        assert record.failures_in_7_days == 1

    def test_promotion_after_consecutive_successes(self, calculator):
        """Test automatic promotion after 10 consecutive successes."""
        for i in range(9):
            result = calculator.record_action_outcome("agent-1", was_successful=True)
            assert result is None

        # 10th success should trigger promotion
        result = calculator.record_action_outcome("agent-1", was_successful=True)
        assert result is not None
        assert result.is_promotion is True
        assert result.new_level == AutonomyLevel.RECOMMEND
        assert result.triggered_by == "automatic"

    def test_demotion_after_critical_failure(self, calculator):
        """Test automatic demotion after critical failure."""
        # First promote the agent
        for _ in range(10):
            calculator.record_action_outcome("agent-1", was_successful=True)

        # Now cause critical failure
        result = calculator.record_action_outcome(
            "agent-1", was_successful=False, is_critical=True
        )
        assert result is not None
        assert result.is_demotion is True
        assert result.old_level == AutonomyLevel.RECOMMEND
        assert result.new_level == AutonomyLevel.OBSERVE

    def test_demotion_after_minor_failures(self, calculator):
        """Test demotion after 3 minor failures in 7 days."""
        # Promote to RECOMMEND first
        for _ in range(10):
            calculator.record_action_outcome("agent-1", was_successful=True)

        # 3 minor failures
        calculator.record_action_outcome("agent-1", was_successful=False)
        calculator.record_action_outcome("agent-1", was_successful=False)
        result = calculator.record_action_outcome("agent-1", was_successful=False)

        assert result is not None
        assert result.is_demotion is True

    def test_record_prediction_accuracy(self, calculator):
        """Test recording prediction accuracy."""
        calculator.record_prediction_accuracy("agent-1", 0.8, was_accurate=True)
        record = calculator.get_agent_record("agent-1")
        assert record.components.predictions_total == 1
        assert record.components.predictions_accurate == 1

    def test_record_override_response_graceful(self, calculator):
        """Test recording graceful override response."""
        result = calculator.record_override_response(
            "agent-1", accepted_gracefully=True
        )
        assert result is None  # No transition

        record = calculator.get_agent_record("agent-1")
        assert record.components.overrides_total == 1
        assert record.components.overrides_accepted == 1

    def test_record_override_response_not_graceful(self, calculator):
        """Test recording non-graceful override response."""
        result = calculator.record_override_response(
            "agent-1", accepted_gracefully=False
        )
        # No demotion from OBSERVE
        assert result is None

        record = calculator.get_agent_record("agent-1")
        assert record.consecutive_successes == 0
        assert record.failures_in_7_days == 1

    def test_record_negative_outcome_minor(self, calculator):
        """Test recording minor negative outcome."""
        result = calculator.record_negative_outcome(
            "agent-1", outcome_type="test_failure", severity="minor"
        )
        assert result is None

        record = calculator.get_agent_record("agent-1")
        assert record.components.negative_outcomes == 1

    def test_record_negative_outcome_critical(self, calculator):
        """Test recording critical negative outcome."""
        # First promote
        for _ in range(10):
            calculator.record_action_outcome("agent-1", was_successful=True)

        result = calculator.record_negative_outcome(
            "agent-1", outcome_type="security_incident", severity="critical"
        )
        assert result is not None
        assert result.is_demotion is True

    def test_set_manual_level(self, calculator):
        """Test manually setting autonomy level."""
        transition = calculator.set_manual_level(
            agent_id="agent-1",
            level=AutonomyLevel.AUTONOMOUS,
            reason="Emergency override",
            set_by="admin-user",
        )

        assert transition.new_level == AutonomyLevel.AUTONOMOUS
        assert transition.triggered_by == "manual"
        assert "admin-user" in transition.reason

        record = calculator.get_agent_record("agent-1")
        assert record.manually_set_level == AutonomyLevel.AUTONOMOUS
        assert record.effective_level == AutonomyLevel.AUTONOMOUS

    def test_clear_manual_level(self, calculator):
        """Test clearing manual level override."""
        calculator.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        transition = calculator.clear_manual_level("agent-1", "Testing complete")
        assert transition is not None
        assert transition.old_level == AutonomyLevel.AUTONOMOUS

        record = calculator.get_agent_record("agent-1")
        assert record.manually_set_level is None

    def test_clear_manual_level_no_override(self, calculator):
        """Test clearing when no manual level is set."""
        result = calculator.clear_manual_level("agent-1", "No override")
        assert result is None

    def test_no_auto_transition_with_manual_level(self, calculator):
        """Test that auto-transitions are blocked when manual level is set."""
        calculator.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Testing", "admin"
        )

        # 10 successes would normally trigger promotion
        for _ in range(10):
            result = calculator.record_action_outcome("agent-1", was_successful=True)
            assert result is None  # No auto-transition

    def test_decay_old_failures(self, calculator):
        """Test failure decay for old failures."""
        record = calculator.get_or_create_agent("agent-1")
        record.failures_in_7_days = 5
        record.last_failure_time = datetime.now(timezone.utc) - timedelta(days=8)

        calculator.decay_old_failures()

        assert record.failures_in_7_days == 0

    def test_decay_old_failures_recent(self, calculator):
        """Test that recent failures are not decayed."""
        record = calculator.get_or_create_agent("agent-1")
        record.failures_in_7_days = 5
        record.last_failure_time = datetime.now(timezone.utc) - timedelta(days=3)

        calculator.decay_old_failures()

        assert record.failures_in_7_days == 5

    def test_get_all_agents(self, calculator):
        """Test getting all agent records."""
        calculator.get_or_create_agent("agent-1")
        calculator.get_or_create_agent("agent-2")

        agents = calculator.get_all_agents()
        assert len(agents) == 2

    def test_get_agents_by_level(self, calculator):
        """Test getting agents by autonomy level."""
        calculator.get_or_create_agent("agent-1")
        calculator.set_manual_level("agent-2", AutonomyLevel.RECOMMEND, "Test", "admin")

        observe_agents = calculator.get_agents_by_level(AutonomyLevel.OBSERVE)
        recommend_agents = calculator.get_agents_by_level(AutonomyLevel.RECOMMEND)

        assert len(observe_agents) == 1
        assert observe_agents[0].agent_id == "agent-1"
        assert len(recommend_agents) == 1
        assert recommend_agents[0].agent_id == "agent-2"

    def test_get_low_trust_agents(self, calculator):
        """Test getting agents with low trust scores."""
        calculator.get_or_create_agent("agent-1")  # Default score ~0.35
        calculator.get_or_create_agent("agent-2")

        low_trust = calculator.get_low_trust_agents(threshold=0.5)
        assert len(low_trust) == 2

        low_trust = calculator.get_low_trust_agents(threshold=0.3)
        assert len(low_trust) == 0

    def test_get_summary_empty(self, calculator):
        """Test summary with no agents."""
        summary = calculator.get_summary()
        assert summary["total_agents"] == 0
        assert summary["avg_trust_score"] == 0.0

    def test_get_summary_with_agents(self, calculator):
        """Test summary with agents."""
        calculator.get_or_create_agent("agent-1")
        calculator.get_or_create_agent("agent-2")
        calculator.set_manual_level("agent-3", AutonomyLevel.RECOMMEND, "Test", "admin")

        summary = calculator.get_summary()
        assert summary["total_agents"] == 3
        assert summary["by_level"]["OBSERVE"]["count"] == 2
        assert summary["by_level"]["RECOMMEND"]["count"] == 1
        assert summary["avg_trust_score"] == pytest.approx(0.35)

    def test_persistence_callback(self):
        """Test persistence callback is called."""
        mock_callback = MagicMock()
        calculator = TrustScoreCalculator(persistence_callback=mock_callback)

        calculator.get_or_create_agent("agent-1")
        calculator.record_action_outcome("agent-1", was_successful=True)

        assert mock_callback.called

    def test_on_transition_callback(self):
        """Test transition callback is called."""
        mock_callback = MagicMock()
        calculator = TrustScoreCalculator(on_transition=mock_callback)

        # Trigger promotion
        for _ in range(10):
            calculator.record_action_outcome("agent-1", was_successful=True)

        assert mock_callback.called
        call_args = mock_callback.call_args[0][0]
        assert isinstance(call_args, TrustTransition)

    def test_reset_agent(self, calculator):
        """Test resetting an agent's trust record."""
        calculator.get_or_create_agent("agent-1")
        calculator.record_action_outcome("agent-1", was_successful=True)
        calculator.set_manual_level(
            "agent-1", AutonomyLevel.AUTONOMOUS, "Test", "admin"
        )

        calculator.reset_agent("agent-1")

        record = calculator.get_agent_record("agent-1")
        assert record.consecutive_successes == 0
        assert record.manually_set_level is None
        assert record.components.actions_total == 0

    def test_thread_safety(self, calculator):
        """Test that operations are thread-safe."""
        import threading

        results = []

        def record_actions():
            for _ in range(100):
                calculator.record_action_outcome("agent-1", was_successful=True)
                results.append(True)

        threads = [threading.Thread(target=record_actions) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 500
        record = calculator.get_agent_record("agent-1")
        assert record.components.actions_total == 500
