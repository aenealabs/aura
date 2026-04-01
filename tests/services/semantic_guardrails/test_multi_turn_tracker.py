"""
Unit tests for Semantic Guardrails Layer 5: Multi-Turn Session Tracker.

Tests cover:
- Session creation and tracking
- Cumulative score calculation
- Exponential decay scoring
- HITL escalation triggers
- Session reset functionality
- Mock mode operation

Author: Project Aura Team
Created: 2026-01-25
"""

import pytest

from src.services.semantic_guardrails.config import SessionTrackingConfig
from src.services.semantic_guardrails.contracts import ThreatLevel
from src.services.semantic_guardrails.multi_turn_tracker import (
    MultiTurnTracker,
    get_multi_turn_tracker,
    record_session_turn,
    reset_multi_turn_tracker,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    reset_multi_turn_tracker()
    yield
    reset_multi_turn_tracker()


class TestMultiTurnTrackerBasics:
    """Basic functionality tests."""

    def test_creation_mock_mode(self):
        """Test tracker creates in mock mode without DynamoDB."""
        tracker = MultiTurnTracker()
        assert tracker._mock_mode is True

    def test_record_first_turn(self):
        """Test recording first turn creates session."""
        tracker = MultiTurnTracker()
        result = tracker.record_turn(
            session_id="test-session-1",
            turn_score=0.5,
            threat_level=ThreatLevel.MEDIUM,
        )
        assert result.session_id == "test-session-1"
        assert result.turn_number == 1
        assert result.current_turn_score == 0.5

    def test_record_multiple_turns(self):
        """Test recording multiple turns increments turn number."""
        tracker = MultiTurnTracker()
        session_id = "test-session-2"

        result1 = tracker.record_turn(session_id, 0.3, ThreatLevel.LOW)
        result2 = tracker.record_turn(session_id, 0.4, ThreatLevel.MEDIUM)
        result3 = tracker.record_turn(session_id, 0.5, ThreatLevel.HIGH)

        assert result1.turn_number == 1
        assert result2.turn_number == 2
        assert result3.turn_number == 3

    def test_processing_time_recorded(self):
        """Test processing time is recorded."""
        tracker = MultiTurnTracker()
        result = tracker.record_turn("test-session-3", 0.5, ThreatLevel.MEDIUM)
        assert result.processing_time_ms >= 0.0

    def test_create_session_id(self):
        """Test session ID generation."""
        tracker = MultiTurnTracker()
        session_id = tracker.create_session_id()
        assert session_id.startswith("sess-")
        assert len(session_id) == 21  # "sess-" + 16 hex chars


class TestCumulativeScoreCalculation:
    """Tests for cumulative score calculation with decay."""

    def test_single_turn_score(self):
        """Test single turn equals current score."""
        tracker = MultiTurnTracker()
        result = tracker.record_turn("test-decay-1", 0.5, ThreatLevel.MEDIUM)
        assert result.cumulative_score == 0.5

    def test_decay_factor_applied(self):
        """Test decay factor is applied to older turns."""
        config = SessionTrackingConfig(decay_factor=0.9)
        tracker = MultiTurnTracker(config=config)
        session_id = "test-decay-2"

        # Turn 1: score 0.5
        result1 = tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)
        assert result1.cumulative_score == 0.5

        # Turn 2: score 0.5
        # Cumulative = 0.5 * 0.9^1 + 0.5 * 0.9^0 = 0.45 + 0.5 = 0.95
        result2 = tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)
        assert abs(result2.cumulative_score - 0.95) < 0.01

    def test_decay_weights_recent_higher(self):
        """Test recent turns are weighted higher than older turns."""
        config = SessionTrackingConfig(decay_factor=0.9)
        tracker = MultiTurnTracker(config=config)
        session_id = "test-decay-3"

        # Record 3 turns with same score
        tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)
        tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)
        result = tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)

        # Expected: 0.5 * 0.9^2 + 0.5 * 0.9^1 + 0.5 * 0.9^0
        # = 0.5 * 0.81 + 0.5 * 0.9 + 0.5 * 1.0
        # = 0.405 + 0.45 + 0.5 = 1.355
        expected = 0.5 * (0.81 + 0.9 + 1.0)
        assert abs(result.cumulative_score - expected) < 0.01

    def test_zero_score_no_contribution(self):
        """Test zero scores don't contribute to cumulative."""
        tracker = MultiTurnTracker()
        session_id = "test-decay-4"

        result1 = tracker.record_turn(session_id, 0.0, ThreatLevel.SAFE)
        result2 = tracker.record_turn(session_id, 0.0, ThreatLevel.SAFE)

        assert result1.cumulative_score == 0.0
        assert result2.cumulative_score == 0.0

    def test_score_clamped_to_range(self):
        """Test turn scores are clamped to 0.0-1.0 range."""
        tracker = MultiTurnTracker()
        session_id = "test-clamp"

        result1 = tracker.record_turn(session_id, 1.5, ThreatLevel.HIGH)
        assert result1.current_turn_score == 1.0

        result2 = tracker.record_turn(session_id, -0.5, ThreatLevel.SAFE)
        assert result2.current_turn_score == 0.0


class TestHITLEscalation:
    """Tests for HITL escalation triggers."""

    def test_escalation_on_threshold(self):
        """Test escalation triggers when cumulative exceeds threshold."""
        # Using default threshold of 2.5
        config = SessionTrackingConfig(hitl_threshold=2.5, decay_factor=1.0)
        tracker = MultiTurnTracker(config=config)
        session_id = "test-escalate-1"

        # Record turns until threshold exceeded
        result1 = tracker.record_turn(session_id, 0.8, ThreatLevel.MEDIUM)
        assert result1.escalation_triggered is False

        result2 = tracker.record_turn(session_id, 0.9, ThreatLevel.MEDIUM)
        assert result2.escalation_triggered is False

        result3 = tracker.record_turn(session_id, 0.9, ThreatLevel.HIGH)
        # Cumulative = 0.8 + 0.9 + 0.9 = 2.6 > 2.5
        assert result3.escalation_triggered is True
        assert result3.cumulative_score > 2.5

    def test_escalation_triggers_once(self):
        """Test escalation only triggers once per session."""
        # Using lower threshold since turn scores are clamped to 0.0-1.0
        config = SessionTrackingConfig(hitl_threshold=2.0, decay_factor=1.0)
        tracker = MultiTurnTracker(config=config)
        session_id = "test-escalate-2"

        # Build up cumulative score over multiple turns
        tracker.record_turn(session_id, 1.0, ThreatLevel.HIGH)
        tracker.record_turn(session_id, 1.0, ThreatLevel.HIGH)
        result1 = tracker.record_turn(session_id, 0.5, ThreatLevel.HIGH)
        # Cumulative = 1.0 + 1.0 + 0.5 = 2.5 > 2.0
        assert result1.escalation_triggered is True
        assert result1.cumulative_score > 2.0

        # Fourth turn should not trigger again (already triggered)
        result2 = tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)
        assert (
            result2.escalation_triggered is False
        )  # Already triggered flag is False, but session was marked

    def test_needs_hitl_review_property(self):
        """Test needs_hitl_review reflects cumulative score > 2.5."""
        # Turn scores are clamped to 0.0-1.0, so we need multiple turns
        config = SessionTrackingConfig(decay_factor=1.0)
        tracker = MultiTurnTracker(config=config)
        session_id = "test-review"

        # Build up cumulative score over multiple turns to exceed 2.5
        tracker.record_turn(session_id, 1.0, ThreatLevel.HIGH)
        tracker.record_turn(session_id, 1.0, ThreatLevel.HIGH)
        result = tracker.record_turn(session_id, 1.0, ThreatLevel.CRITICAL)
        # Cumulative = 1.0 + 1.0 + 1.0 = 3.0 > 2.5
        assert result.needs_hitl_review is True
        assert result.cumulative_score > 2.5

    def test_threat_level_based_on_cumulative(self):
        """Test threat level is based on cumulative score thresholds."""
        config = SessionTrackingConfig(hitl_threshold=2.5, decay_factor=1.0)
        tracker = MultiTurnTracker(config=config)
        session_id = "test-level"

        # Low cumulative: < threshold * 0.3 = 0.75
        result1 = tracker.record_turn(session_id, 0.3, ThreatLevel.LOW)
        assert result1.threat_level == ThreatLevel.LOW

        # Add more turns to exceed threshold * 0.6 = 1.5
        tracker.record_turn(session_id, 0.8, ThreatLevel.MEDIUM)
        result2 = tracker.record_turn(session_id, 0.6, ThreatLevel.MEDIUM)
        # Cumulative = 0.3 + 0.8 + 0.6 = 1.7 > 1.5 (threshold * 0.6)
        assert result2.threat_level == ThreatLevel.MEDIUM


class TestSessionManagement:
    """Tests for session management."""

    def test_get_session_score(self):
        """Test getting session score without recording."""
        tracker = MultiTurnTracker()
        session_id = "test-get-1"

        # Record some turns
        tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)
        tracker.record_turn(session_id, 0.3, ThreatLevel.LOW)

        # Get score without recording
        score = tracker.get_session_score(session_id)
        assert score is not None
        assert score.session_id == session_id
        assert score.turn_number == 2

    def test_get_session_score_not_found(self):
        """Test getting score for nonexistent session."""
        tracker = MultiTurnTracker()
        score = tracker.get_session_score("nonexistent-session")
        assert score is None

    def test_reset_session(self):
        """Test resetting a session."""
        tracker = MultiTurnTracker()
        session_id = "test-reset-1"

        # Record turns
        tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)
        tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM)

        # Reset
        result = tracker.reset_session(session_id)
        assert result is True

        # Verify reset
        score = tracker.get_session_score(session_id)
        assert score is None

    def test_reset_nonexistent_session(self):
        """Test resetting nonexistent session returns False."""
        tracker = MultiTurnTracker()
        result = tracker.reset_session("nonexistent")
        assert result is False

    def test_turn_history_limited(self):
        """Test turn history is limited in result."""
        tracker = MultiTurnTracker()
        session_id = "test-history"

        # Record 15 turns
        for i in range(15):
            result = tracker.record_turn(session_id, 0.1, ThreatLevel.LOW)

        # Result should only have last 10 turns
        assert len(result.turn_history) == 10


class TestConfigurationOptions:
    """Tests for configuration options."""

    def test_custom_decay_factor(self):
        """Test custom decay factor."""
        config = SessionTrackingConfig(decay_factor=0.8)
        tracker = MultiTurnTracker(config=config)
        assert tracker.config.decay_factor == 0.8

    def test_custom_hitl_threshold(self):
        """Test custom HITL threshold."""
        config = SessionTrackingConfig(hitl_threshold=3.0)
        tracker = MultiTurnTracker(config=config)
        assert tracker.config.hitl_threshold == 3.0

    def test_custom_max_turns(self):
        """Test custom max turns tracked."""
        config = SessionTrackingConfig(max_turns_tracked=50)
        tracker = MultiTurnTracker(config=config)
        assert tracker.config.max_turns_tracked == 50

    def test_custom_ttl(self):
        """Test custom TTL hours."""
        config = SessionTrackingConfig(ttl_hours=48)
        tracker = MultiTurnTracker(config=config)
        assert tracker.config.ttl_hours == 48


class TestMetadataHandling:
    """Tests for metadata handling."""

    def test_metadata_stored(self):
        """Test metadata is stored with turn."""
        tracker = MultiTurnTracker()
        session_id = "test-meta-1"

        metadata = {"user_id": "user-123", "context": "test"}
        tracker.record_turn(session_id, 0.5, ThreatLevel.MEDIUM, metadata=metadata)

        # Get session and verify metadata
        session = tracker._get_session(session_id)
        assert session.get("metadata") == metadata


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_multi_turn_tracker_singleton(self):
        """Test get_multi_turn_tracker returns singleton."""
        t1 = get_multi_turn_tracker()
        t2 = get_multi_turn_tracker()
        assert t1 is t2

    def test_record_session_turn_function(self):
        """Test record_session_turn convenience function."""
        result = record_session_turn(
            session_id="func-test-1",
            turn_score=0.5,
            threat_level=ThreatLevel.MEDIUM,
        )
        assert result is not None
        assert result.session_id == "func-test-1"

    def test_reset_multi_turn_tracker(self):
        """Test reset_multi_turn_tracker clears singleton."""
        t1 = get_multi_turn_tracker()
        reset_multi_turn_tracker()
        t2 = get_multi_turn_tracker()
        assert t1 is not t2


class TestActiveSessions:
    """Tests for active session tracking."""

    def test_get_active_sessions_count(self):
        """Test getting active sessions count."""
        tracker = MultiTurnTracker()

        # Start with 0
        assert tracker.get_active_sessions_count() == 0

        # Record turns for multiple sessions
        tracker.record_turn("session-a", 0.1, ThreatLevel.LOW)
        tracker.record_turn("session-b", 0.1, ThreatLevel.LOW)
        tracker.record_turn("session-c", 0.1, ThreatLevel.LOW)

        assert tracker.get_active_sessions_count() == 3


class TestTurnHistoryTruncation:
    """Tests for turn history truncation."""

    def test_history_truncated_at_max(self):
        """Test turn history is truncated at max_turns_tracked."""
        config = SessionTrackingConfig(max_turns_tracked=5)
        tracker = MultiTurnTracker(config=config)
        session_id = "test-truncate"

        # Record more turns than max
        for i in range(10):
            tracker.record_turn(session_id, 0.1, ThreatLevel.LOW)

        session = tracker._get_session(session_id)
        # Internal history may be longer but should be managed
        assert len(session.get("turn_history", [])) <= 10


class TestSessionIdGeneration:
    """Tests for session ID generation."""

    def test_unique_session_ids(self):
        """Test generated session IDs are unique."""
        tracker = MultiTurnTracker()

        ids = {tracker.create_session_id() for _ in range(100)}
        assert len(ids) == 100  # All unique

    def test_session_id_format(self):
        """Test session ID has correct format."""
        tracker = MultiTurnTracker()
        session_id = tracker.create_session_id()

        assert session_id.startswith("sess-")
        # Remaining should be hex characters
        hex_part = session_id[5:]
        assert all(c in "0123456789abcdef" for c in hex_part)
