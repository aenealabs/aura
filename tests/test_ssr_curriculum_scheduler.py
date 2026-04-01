"""
Tests for SSR Curriculum Scheduler.

Tests the progressive difficulty ramping, forgetting prevention,
and skill profile tracking for curriculum learning.
"""

import platform
from datetime import datetime, timezone

import pytest

from src.services.ssr.curriculum_scheduler import (
    CurriculumScheduler,
    CurriculumState,
    CurriculumStrategy,
    LearningPhase,
    SkillProfile,
)

# Run tests in forked processes for isolation
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestCurriculumStrategyEnum:
    """Tests for CurriculumStrategy enum."""

    def test_all_strategies_defined(self):
        """Verify all expected strategies exist."""
        expected = {"linear", "exponential", "adaptive", "self_paced", "mixed"}
        actual = {s.value for s in CurriculumStrategy}
        assert expected == actual


class TestLearningPhaseEnum:
    """Tests for LearningPhase enum."""

    def test_all_phases_defined(self):
        """Verify all expected phases exist."""
        expected = {"warmup", "ramping", "plateau", "challenge", "review"}
        actual = {p.value for p in LearningPhase}
        assert expected == actual


class TestSkillProfile:
    """Tests for SkillProfile dataclass."""

    def test_skill_profile_creation(self):
        """Test creating a skill profile."""
        profile = SkillProfile(
            bug_type="edge_case_handling",
            solve_rate=0.7,
            total_attempts=100,
            successful_solves=70,
            last_practiced=datetime.now(timezone.utc),
        )
        assert profile.bug_type == "edge_case_handling"
        assert profile.solve_rate == 0.7
        assert profile.total_attempts == 100

    def test_skill_profile_update(self):
        """Test updating skill profile after attempt."""
        profile = SkillProfile(
            bug_type="test_skill",
            solve_rate=0.5,
            total_attempts=10,
            successful_solves=5,
        )
        profile.update(solved=True, attempts=1)
        assert profile.total_attempts == 11
        assert profile.successful_solves == 6

    def test_skill_serialization(self):
        """Test serialization of skill profile."""
        now = datetime.now(timezone.utc)
        profile = SkillProfile(
            bug_type="test_skill",
            solve_rate=0.6,
            total_attempts=75,
            successful_solves=45,
            last_practiced=now,
        )
        data = profile.to_dict()
        assert data["bug_type"] == "test_skill"
        assert data["solve_rate"] == 0.6
        assert data["total_attempts"] == 75


class TestCurriculumState:
    """Tests for CurriculumState dataclass."""

    def test_state_creation(self):
        """Test creating curriculum state."""
        state = CurriculumState(
            current_difficulty=5,
            current_phase=LearningPhase.RAMPING,
            total_iterations=1000,
        )
        assert state.current_difficulty == 5
        assert state.current_phase == LearningPhase.RAMPING

    def test_state_serialization(self):
        """Test serialization of curriculum state."""
        state = CurriculumState(
            current_difficulty=7,
            current_phase=LearningPhase.PLATEAU,
            iterations_in_phase=50,
            total_iterations=500,
        )
        data = state.to_dict()
        restored = CurriculumState.from_dict(data)
        assert restored.current_difficulty == state.current_difficulty
        assert restored.current_phase == state.current_phase

    def test_state_default_values(self):
        """Test default values for curriculum state."""
        state = CurriculumState()
        assert state.current_difficulty == 1
        assert state.current_phase == LearningPhase.WARMUP
        assert state.iterations_in_phase == 0
        assert state.total_iterations == 0


class TestCurriculumScheduler:
    """Tests for CurriculumScheduler service."""

    @pytest.fixture
    def scheduler(self):
        """Create a CurriculumScheduler instance."""
        return CurriculumScheduler()

    def test_scheduler_initialization(self, scheduler):
        """Test scheduler initialization."""
        state = scheduler.state
        assert state.current_difficulty == 1
        assert state.current_phase == LearningPhase.WARMUP

    def test_custom_initialization(self):
        """Test scheduler with custom parameters."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.EXPONENTIAL,
            initial_difficulty=2,
            max_difficulty=8,
        )
        assert scheduler.strategy == CurriculumStrategy.EXPONENTIAL
        assert scheduler.initial_difficulty == 2
        assert scheduler.max_difficulty == 8

    def test_update_performance(self, scheduler):
        """Test updating performance metrics."""
        scheduler.update_performance(
            solve_rate=0.65,
            bug_types=["edge_case", "context_gathering"],
            solved=True,
            attempts=1,
        )
        assert scheduler.state.total_iterations == 1
        assert "edge_case" in scheduler.state.skill_profiles
        assert "context_gathering" in scheduler.state.skill_profiles

    def test_get_metrics(self, scheduler):
        """Test getting scheduler metrics."""
        scheduler.update_performance(solve_rate=0.7, bug_types=["skill_a"])
        metrics = scheduler.get_metrics()
        assert "current_difficulty" in metrics
        assert "current_phase" in metrics
        assert "strategy" in metrics

    def test_should_advance(self, scheduler):
        """Test checking if curriculum should advance."""
        # Initially should not advance (in warmup)
        assert scheduler.should_advance() is False

    def test_reset(self, scheduler):
        """Test resetting the scheduler."""
        scheduler.update_performance(solve_rate=0.8, bug_types=["test"])
        scheduler.reset()
        assert scheduler.state.current_difficulty == scheduler.initial_difficulty
        assert scheduler.state.current_phase == LearningPhase.WARMUP


class TestCurriculumEdgeCases:
    """Edge case tests for curriculum scheduler."""

    def test_empty_skills(self):
        """Test with no skills tracked."""
        scheduler = CurriculumScheduler()
        metrics = scheduler.get_metrics()
        assert metrics is not None
        assert metrics["skill_profiles"] == 0

    def test_difficulty_bounds(self):
        """Test that difficulty stays within bounds."""
        scheduler = CurriculumScheduler(initial_difficulty=1, max_difficulty=10)
        assert scheduler.state.current_difficulty >= 1
        assert scheduler.state.current_difficulty <= 10

    def test_detect_forgetting_empty(self):
        """Test forgetting detection with no history."""
        scheduler = CurriculumScheduler()
        forgetting = scheduler.detect_forgetting()
        assert forgetting == []

    def test_get_skill_gaps_empty(self):
        """Test skill gaps with no profiles."""
        scheduler = CurriculumScheduler()
        gaps = scheduler.get_skill_gaps()
        assert gaps == []


class TestSkillProfileExtended:
    """Extended tests for SkillProfile."""

    def test_update_mastery_level(self):
        """Test that mastery level updates after 10+ attempts."""
        profile = SkillProfile(bug_type="test_skill")
        # Simulate 10 successful solves
        for _ in range(10):
            profile.update(solved=True, attempts=1)
        assert profile.mastery_level == 10  # 100% solve rate = mastery 10

    def test_update_mastery_level_partial(self):
        """Test mastery level with partial success."""
        profile = SkillProfile(bug_type="test_skill")
        # Simulate 5 success + 5 failures
        for i in range(10):
            profile.update(solved=(i < 5), attempts=1)
        assert profile.mastery_level == 5  # 50% solve rate

    def test_update_not_solved(self):
        """Test updating profile when not solved."""
        profile = SkillProfile(
            bug_type="test_skill", total_attempts=5, successful_solves=3
        )
        profile.update(solved=False, attempts=2)
        assert profile.total_attempts == 6
        assert profile.successful_solves == 3

    def test_to_dict_all_fields(self):
        """Test to_dict includes all required fields."""
        profile = SkillProfile(
            bug_type="comprehensive_test",
            solve_rate=0.75,
            recent_solve_rate=0.8,
            total_attempts=100,
            successful_solves=75,
            avg_attempts_to_solve=1.5,
            mastery_level=7,
        )
        data = profile.to_dict()
        assert data["bug_type"] == "comprehensive_test"
        assert data["solve_rate"] == 0.75
        assert data["recent_solve_rate"] == 0.8
        assert data["total_attempts"] == 100
        assert data["successful_solves"] == 75
        assert data["avg_attempts_to_solve"] == 1.5
        assert data["mastery_level"] == 7
        assert "last_practiced" in data


class TestCurriculumStateExtended:
    """Extended tests for CurriculumState."""

    def test_to_dict_with_skill_profiles(self):
        """Test serialization with skill profiles."""
        state = CurriculumState(
            current_difficulty=5,
            current_phase=LearningPhase.RAMPING,
        )
        state.skill_profiles["bug_type_a"] = SkillProfile(
            bug_type="bug_type_a",
            solve_rate=0.6,
            total_attempts=50,
        )
        data = state.to_dict()
        assert "bug_type_a" in data["skill_profiles"]
        assert data["skill_profiles"]["bug_type_a"]["solve_rate"] == 0.6

    def test_to_dict_with_recent_solve_rates(self):
        """Test serialization with recent solve rates."""
        state = CurriculumState()
        state.recent_solve_rates = [0.5, 0.6, 0.7, 0.8]
        data = state.to_dict()
        assert data["recent_solve_rates"] == [0.5, 0.6, 0.7, 0.8]

    def test_to_dict_truncates_large_lists(self):
        """Test that to_dict truncates large lists."""
        state = CurriculumState()
        state.recent_solve_rates = list(range(200))
        data = state.to_dict()
        assert len(data["recent_solve_rates"]) == 100  # Last 100 only

    def test_from_dict_with_skill_profiles(self):
        """Test deserialization with skill profiles."""
        data = {
            "current_difficulty": 3,
            "current_phase": "plateau",
            "iterations_in_phase": 20,
            "total_iterations": 200,
            "recent_solve_rates": [0.6, 0.7],
            "difficulty_progression": [(1, 0.5), (2, 0.6)],
            "skill_profiles": {
                "type_a": {
                    "bug_type": "type_a",
                    "solve_rate": 0.65,
                    "recent_solve_rate": 0.7,
                    "total_attempts": 30,
                    "successful_solves": 20,
                    "avg_attempts_to_solve": 1.2,
                    "mastery_level": 6,
                }
            },
        }
        state = CurriculumState.from_dict(data)
        assert state.current_difficulty == 3
        assert state.current_phase == LearningPhase.PLATEAU
        assert "type_a" in state.skill_profiles
        assert state.skill_profiles["type_a"].solve_rate == 0.65


class TestCurriculumBatch:
    """Tests for CurriculumBatch dataclass."""

    def test_batch_to_dict(self):
        """Test CurriculumBatch serialization."""
        from src.services.ssr.curriculum_scheduler import CurriculumBatch

        batch = CurriculumBatch(
            bugs=[],  # Empty for this test
            target_difficulty=5,
            phase=LearningPhase.RAMPING,
            includes_review=True,
            difficulty_distribution={4: 5, 5: 10, 6: 5},
        )
        data = batch.to_dict()
        assert data["bug_count"] == 0
        assert data["target_difficulty"] == 5
        assert data["phase"] == "ramping"
        assert data["includes_review"] is True
        assert data["difficulty_distribution"] == {4: 5, 5: 10, 6: 5}


class TestCurriculumSchedulerStrategies:
    """Tests for different curriculum strategies."""

    def test_linear_strategy(self):
        """Test LINEAR strategy target difficulty calculation."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.LINEAR,
            initial_difficulty=3,
        )
        # Linear should just return current difficulty
        difficulty = scheduler._calculate_target_difficulty()
        assert difficulty == 3

    def test_exponential_strategy(self):
        """Test EXPONENTIAL strategy target difficulty calculation."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.EXPONENTIAL,
            initial_difficulty=1,
            max_difficulty=10,
        )
        # Initial difficulty should be 1
        difficulty = scheduler._calculate_target_difficulty()
        assert difficulty >= 1
        assert difficulty <= 10

    def test_exponential_strategy_with_iterations(self):
        """Test exponential strategy scales with iterations."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.EXPONENTIAL,
            initial_difficulty=1,
            max_difficulty=10,
        )
        # Simulate many iterations
        scheduler.state.total_iterations = 2000
        difficulty = scheduler._calculate_target_difficulty()
        # After many iterations, difficulty should be higher
        assert difficulty > 1

    def test_adaptive_strategy_high_solve_rate(self):
        """Test ADAPTIVE strategy increases difficulty on high solve rate."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.ADAPTIVE,
            initial_difficulty=5,
            max_difficulty=10,
        )
        scheduler._ema_solve_rate = 0.75  # High solve rate
        difficulty = scheduler._calculate_target_difficulty()
        assert difficulty == 6  # Should increase

    def test_adaptive_strategy_low_solve_rate(self):
        """Test ADAPTIVE strategy decreases difficulty on low solve rate."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.ADAPTIVE,
            initial_difficulty=1,  # Start at 1
            max_difficulty=10,
        )
        scheduler.state.current_difficulty = 5  # Currently at 5
        scheduler._ema_solve_rate = 0.35  # Low solve rate
        difficulty = scheduler._calculate_target_difficulty()
        assert difficulty == 4  # Should decrease

    def test_adaptive_strategy_at_min_difficulty(self):
        """Test ADAPTIVE won't go below initial difficulty."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.ADAPTIVE,
            initial_difficulty=1,
            max_difficulty=10,
        )
        scheduler.state.current_difficulty = 1
        scheduler._ema_solve_rate = 0.2  # Very low solve rate
        difficulty = scheduler._calculate_target_difficulty()
        assert difficulty == 1  # Should not go below initial

    def test_self_paced_strategy(self):
        """Test SELF_PACED strategy uses skill profiles."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.SELF_PACED,
            initial_difficulty=1,
            max_difficulty=10,
        )
        # Add skill profiles with various mastery levels
        scheduler.state.skill_profiles["type_a"] = SkillProfile(
            bug_type="type_a", mastery_level=8
        )
        scheduler.state.skill_profiles["type_b"] = SkillProfile(
            bug_type="type_b", mastery_level=6
        )
        difficulty = scheduler._calculate_target_difficulty()
        # Average mastery is 7, so difficulty should be 7
        assert difficulty == 7

    def test_self_paced_strategy_empty_profiles(self):
        """Test SELF_PACED with no skill profiles."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.SELF_PACED,
            initial_difficulty=1,
            max_difficulty=10,
        )
        difficulty = scheduler._calculate_target_difficulty()
        assert difficulty == 1  # Default when no profiles

    def test_mixed_strategy_normal(self):
        """Test MIXED strategy on normal iterations."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.MIXED,
            initial_difficulty=5,
            max_difficulty=10,
        )
        scheduler.state.current_difficulty = 5
        scheduler.state.total_iterations = 55  # Not divisible by 100
        difficulty = scheduler._calculate_target_difficulty()
        assert difficulty == 5  # Base difficulty

    def test_mixed_strategy_challenge_iteration(self):
        """Test MIXED strategy on challenge iterations."""
        scheduler = CurriculumScheduler(
            strategy=CurriculumStrategy.MIXED,
            initial_difficulty=5,
            max_difficulty=10,
        )
        scheduler.state.current_difficulty = 5
        scheduler.state.total_iterations = 100  # Challenge round
        difficulty = scheduler._calculate_target_difficulty()
        assert difficulty == 7  # Base + 2


class TestCurriculumSchedulerBatchSelection:
    """Tests for batch selection methods."""

    def test_get_next_batch_empty_bugs(self):
        """Test get_next_batch with no available bugs."""
        scheduler = CurriculumScheduler()
        batch = scheduler.get_next_batch([], batch_size=32)
        assert len(batch.bugs) == 0
        assert batch.target_difficulty == 1

    def test_select_bugs_by_difficulty(self):
        """Test that bugs are selected close to target difficulty."""
        from unittest.mock import MagicMock

        scheduler = CurriculumScheduler()

        # Create mock bugs with different difficulties
        bugs = []
        for diff in range(1, 11):
            mock_bug = MagicMock()
            mock_bug.difficulty = diff
            bugs.append(mock_bug)

        selected = scheduler._select_bugs(bugs, count=5, target_difficulty=5)
        assert len(selected) == 5
        # Selected bugs should be close to difficulty 5
        difficulties = [b.difficulty for b in selected]
        avg_diff = sum(difficulties) / len(difficulties)
        assert 4 <= avg_diff <= 6

    def test_select_review_bugs(self):
        """Test review bug selection."""
        from unittest.mock import MagicMock

        scheduler = CurriculumScheduler()
        scheduler.state.current_difficulty = 5

        # Create mock bugs at various difficulties
        bugs = []
        for diff in range(1, 10):
            mock_bug = MagicMock()
            mock_bug.difficulty = diff
            bugs.append(mock_bug)

        review = scheduler._select_review_bugs(bugs, count=3)
        # Should only select bugs below current difficulty
        for bug in review:
            assert bug.difficulty < 5


class TestCurriculumSchedulerPhases:
    """Tests for phase transitions."""

    def test_warmup_to_ramping_transition(self):
        """Test transition from warmup to ramping phase."""
        scheduler = CurriculumScheduler()
        assert scheduler.state.current_phase == LearningPhase.WARMUP

        # Simulate warmup iterations
        for _ in range(scheduler.WARMUP_ITERATIONS):
            scheduler.update_performance(solve_rate=0.5, bug_types=["test"])

        assert scheduler.state.current_phase == LearningPhase.RAMPING

    def test_ramping_to_plateau_transition(self):
        """Test transition from ramping to plateau on high solve rate."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.RAMPING
        scheduler._ema_solve_rate = 0.85  # Above MAX_SOLVE_RATE_FOR_PLATEAU

        scheduler._check_phase_transition()
        assert scheduler.state.current_phase == LearningPhase.PLATEAU

    def test_ramping_to_challenge_at_max_difficulty(self):
        """Test transition to challenge at max difficulty."""
        scheduler = CurriculumScheduler(max_difficulty=5)
        scheduler.state.current_phase = LearningPhase.RAMPING
        scheduler.state.current_difficulty = 5  # At max

        scheduler._check_phase_transition()
        assert scheduler.state.current_phase == LearningPhase.CHALLENGE

    def test_plateau_advance_and_transition(self):
        """Test plateau phase advancement."""
        scheduler = CurriculumScheduler(max_difficulty=10)
        scheduler.state.current_phase = LearningPhase.PLATEAU
        scheduler.state.current_difficulty = 5
        scheduler._ema_solve_rate = 0.65  # Above MIN_SOLVE_RATE_TO_ADVANCE
        scheduler.state.iterations_in_phase = scheduler.WARMUP_ITERATIONS + 1

        scheduler._check_phase_transition()
        # Should advance and transition back to ramping
        assert scheduler.state.current_phase == LearningPhase.RAMPING
        assert scheduler.state.current_difficulty == 6

    def test_challenge_to_review_on_forgetting(self):
        """Test transition to review when forgetting detected."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.CHALLENGE

        # Simulate forgetting by adding declining performance
        for i in range(20):
            scheduler.state.difficulty_progression.append((3, 0.8))
        for i in range(10):
            scheduler.state.difficulty_progression.append((3, 0.3))

        scheduler._check_phase_transition()
        assert scheduler.state.current_phase == LearningPhase.REVIEW

    def test_review_to_challenge_after_period(self):
        """Test transition back to challenge after review."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.REVIEW
        scheduler.state.iterations_in_phase = 25  # > 20

        scheduler._check_phase_transition()
        assert scheduler.state.current_phase == LearningPhase.CHALLENGE


class TestCurriculumSchedulerAdvancement:
    """Tests for curriculum advancement."""

    def test_should_advance_at_max_difficulty(self):
        """Test should_advance returns False at max difficulty."""
        scheduler = CurriculumScheduler(max_difficulty=10)
        scheduler.state.current_difficulty = 10
        assert scheduler.should_advance() is False

    def test_should_advance_warmup_phase(self):
        """Test should_advance in warmup phase."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.WARMUP

        # Not enough iterations
        scheduler.state.iterations_in_phase = 50
        assert scheduler.should_advance() is False

        # Enough iterations
        scheduler.state.iterations_in_phase = 100
        assert scheduler.should_advance() is True

    def test_should_advance_ramping_phase(self):
        """Test should_advance in ramping phase."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.RAMPING

        # Low solve rate
        scheduler._ema_solve_rate = 0.4
        assert scheduler.should_advance() is False

        # High solve rate
        scheduler._ema_solve_rate = 0.65
        assert scheduler.should_advance() is True

    def test_advance_curriculum(self):
        """Test advancing the curriculum."""
        scheduler = CurriculumScheduler(
            initial_difficulty=3,
            max_difficulty=10,
            difficulty_step=2,
        )
        scheduler.state.current_difficulty = 3
        scheduler._ema_solve_rate = 0.7

        new_diff = scheduler.advance_curriculum()
        assert new_diff == 5
        assert scheduler.state.current_difficulty == 5
        assert scheduler.state.iterations_in_phase == 0
        assert 3 in scheduler.state.last_review_difficulty

    def test_advance_curriculum_at_max(self):
        """Test advancing doesn't exceed max difficulty."""
        scheduler = CurriculumScheduler(max_difficulty=5, difficulty_step=2)
        scheduler.state.current_difficulty = 4

        new_diff = scheduler.advance_curriculum()
        assert new_diff == 5  # Capped at max


class TestCurriculumSchedulerForgettingDetection:
    """Tests for forgetting detection."""

    def test_detect_forgetting_with_data(self):
        """Test forgetting detection with declining performance."""
        scheduler = CurriculumScheduler()

        # Add good historical performance at difficulty 3
        for _ in range(20):
            scheduler.state.difficulty_progression.append((3, 0.8))

        # Add recent poor performance at difficulty 3
        for _ in range(10):
            scheduler.state.difficulty_progression.append((3, 0.3))

        forgetting = scheduler.detect_forgetting()
        assert 3 in forgetting

    def test_detect_forgetting_insufficient_data(self):
        """Test forgetting detection with insufficient data."""
        scheduler = CurriculumScheduler()

        # Only 3 data points - not enough for detection
        scheduler.state.difficulty_progression = [(3, 0.7), (3, 0.6), (3, 0.5)]

        forgetting = scheduler.detect_forgetting()
        assert forgetting == []

    def test_detect_forgetting_no_decline(self):
        """Test forgetting detection with stable performance."""
        scheduler = CurriculumScheduler()

        # Stable performance
        for _ in range(30):
            scheduler.state.difficulty_progression.append((3, 0.7))

        forgetting = scheduler.detect_forgetting()
        assert forgetting == []


class TestCurriculumSchedulerSkillGaps:
    """Tests for skill gap detection."""

    def test_get_skill_gaps_with_data(self):
        """Test skill gap detection with data."""
        scheduler = CurriculumScheduler()

        # Add skill with low mastery
        scheduler.state.skill_profiles["weak_skill"] = SkillProfile(
            bug_type="weak_skill",
            mastery_level=3,
            total_attempts=20,
            solve_rate=0.3,
        )

        # Add skill with high mastery
        scheduler.state.skill_profiles["strong_skill"] = SkillProfile(
            bug_type="strong_skill",
            mastery_level=8,
            total_attempts=50,
            solve_rate=0.8,
        )

        gaps = scheduler.get_skill_gaps()
        assert "weak_skill" in gaps
        assert "strong_skill" not in gaps

    def test_get_skill_gaps_insufficient_attempts(self):
        """Test skill gap detection excludes low-attempt skills."""
        scheduler = CurriculumScheduler()

        # Add skill with low mastery but few attempts
        scheduler.state.skill_profiles["new_skill"] = SkillProfile(
            bug_type="new_skill",
            mastery_level=2,
            total_attempts=5,  # Less than 10
        )

        gaps = scheduler.get_skill_gaps()
        assert "new_skill" not in gaps  # Not enough attempts to judge


class TestCurriculumSchedulerReviewLogic:
    """Tests for review logic."""

    def test_should_include_review_in_challenge(self):
        """Test review is included in challenge phase."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.CHALLENGE
        assert scheduler._should_include_review() is True

    def test_should_include_review_in_plateau(self):
        """Test review is included in plateau phase."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.PLATEAU
        assert scheduler._should_include_review() is True

    def test_should_include_review_periodic(self):
        """Test periodic review during ramping."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.RAMPING
        scheduler.state.iterations_in_phase = scheduler.REVIEW_INTERVAL_ITERATIONS
        assert scheduler._should_include_review() is True

    def test_should_not_include_review_early_ramping(self):
        """Test no review early in ramping phase."""
        scheduler = CurriculumScheduler()
        scheduler.state.current_phase = LearningPhase.RAMPING
        scheduler.state.iterations_in_phase = 10
        # No forgetting detected either
        assert scheduler._should_include_review() is False


class TestCurriculumSchedulerMetrics:
    """Tests for metrics reporting."""

    def test_get_metrics_comprehensive(self):
        """Test get_metrics returns all required fields."""
        scheduler = CurriculumScheduler(strategy=CurriculumStrategy.ADAPTIVE)
        scheduler.update_performance(solve_rate=0.7, bug_types=["test_type"])

        metrics = scheduler.get_metrics()

        assert metrics["strategy"] == "adaptive"
        assert "current_difficulty" in metrics
        assert "current_phase" in metrics
        assert "iterations_in_phase" in metrics
        assert "total_iterations" in metrics
        assert "ema_solve_rate" in metrics
        assert "skill_profiles" in metrics
        assert "avg_mastery" in metrics
        assert "skill_gaps" in metrics
        assert "forgetting_levels" in metrics
