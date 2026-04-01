"""Tests for Titan memory integration (Phase 1b)."""

from unittest.mock import MagicMock

import pytest

from src.services.memory_evolution import (
    FeatureDisabledError,
    MemoryEvolutionConfig,
    RefineAction,
    RefineOperation,
    reset_memory_evolution_config,
    reset_titan_refine_integration,
    set_memory_evolution_config,
)
from src.services.memory_evolution.titan_integration import (
    ReinforceMetrics,
    SurpriseCalculator,
    TaskOutcome,
    TitanRefineIntegration,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    reset_memory_evolution_config()
    reset_titan_refine_integration()
    yield
    reset_memory_evolution_config()
    reset_titan_refine_integration()


@pytest.fixture
def reinforce_enabled_config() -> MemoryEvolutionConfig:
    """Create config with REINFORCE enabled."""
    config = MemoryEvolutionConfig(
        environment="test",
        project_name="aura-test",
    )
    config.features.reinforce_enabled = True
    set_memory_evolution_config(config)
    return config


@pytest.fixture
def mock_titan_service() -> MagicMock:
    """Create a mock Titan memory service."""
    service = MagicMock()
    service.config = MagicMock()
    service.config.memorization_threshold = 0.7
    service.config.ttt_learning_rate = 0.001
    service.compute_surprise = MagicMock(return_value=0.5)
    return service


@pytest.fixture
def titan_integration(
    mock_titan_service: MagicMock,
    reinforce_enabled_config: MemoryEvolutionConfig,
) -> TitanRefineIntegration:
    """Create TitanRefineIntegration with mocks."""
    return TitanRefineIntegration(
        titan_service=mock_titan_service,
        config=reinforce_enabled_config,
    )


@pytest.fixture
def success_outcome() -> TaskOutcome:
    """Create a successful task outcome."""
    return TaskOutcome(
        success=True,
        task_id="task-123",
        agent_id="coder-agent-1",
        execution_time_ms=150.0,
        quality_score=0.85,
        reuse_count=3,
    )


@pytest.fixture
def failure_outcome() -> TaskOutcome:
    """Create a failed task outcome."""
    return TaskOutcome(
        success=False,
        task_id="task-456",
        agent_id="coder-agent-1",
        execution_time_ms=500.0,
        error_message="Test failure",
        quality_score=0.2,
        reuse_count=0,
    )


@pytest.fixture
def reinforce_action() -> RefineAction:
    """Create a REINFORCE action."""
    return RefineAction(
        operation=RefineOperation.REINFORCE,
        target_memory_ids=["mem-1", "mem-2", "mem-3"],
        reasoning="Strengthen successful debugging pattern",
        confidence=0.9,
        tenant_id="tenant-123",
        security_domain="development",
        agent_id="coder-agent-1",
        metadata={"expected_outcome": {"success": True, "quality_score": 0.8}},
    )


class TestTaskOutcome:
    """Tests for TaskOutcome dataclass."""

    def test_create_success_outcome(self, success_outcome: TaskOutcome):
        """Test creating a successful outcome."""
        assert success_outcome.success is True
        assert success_outcome.task_id == "task-123"
        assert success_outcome.quality_score == 0.85

    def test_create_failure_outcome(self, failure_outcome: TaskOutcome):
        """Test creating a failed outcome."""
        assert failure_outcome.success is False
        assert failure_outcome.error_message == "Test failure"

    def test_to_dict(self, success_outcome: TaskOutcome):
        """Test serialization to dictionary."""
        data = success_outcome.to_dict()
        assert data["success"] is True
        assert data["task_id"] == "task-123"
        assert data["quality_score"] == 0.85
        assert data["reuse_count"] == 3


class TestSurpriseCalculator:
    """Tests for SurpriseCalculator."""

    def test_compute_delta_no_expectation_success(self):
        """Test delta with no expectation and success."""
        calc = SurpriseCalculator()
        outcome = TaskOutcome(
            success=True,
            task_id="task-1",
            agent_id="agent-1",
        )
        delta = calc.compute_delta(None, outcome)
        assert delta == 1.0  # Maximum positive surprise

    def test_compute_delta_no_expectation_failure(self):
        """Test delta with no expectation and failure."""
        calc = SurpriseCalculator()
        outcome = TaskOutcome(
            success=False,
            task_id="task-1",
            agent_id="agent-1",
        )
        delta = calc.compute_delta(None, outcome)
        assert delta == -0.5  # Negative surprise

    def test_compute_delta_exceeded_expectations(self):
        """Test delta when outcome exceeds expectations."""
        calc = SurpriseCalculator()
        expected = {"success": False, "quality_score": 0.3}
        outcome = TaskOutcome(
            success=True,
            task_id="task-1",
            agent_id="agent-1",
            quality_score=0.9,
        )
        delta = calc.compute_delta(expected, outcome)
        assert delta > 0  # Positive surprise

    def test_compute_delta_failed_expectations(self):
        """Test delta when outcome fails expectations."""
        calc = SurpriseCalculator()
        expected = {"success": True, "quality_score": 0.8}
        outcome = TaskOutcome(
            success=False,
            task_id="task-1",
            agent_id="agent-1",
            quality_score=0.2,
        )
        delta = calc.compute_delta(expected, outcome)
        assert delta < 0  # Negative surprise

    def test_momentum_smoothing(self):
        """Test that momentum smoothing is applied."""
        calc = SurpriseCalculator(momentum=0.9)
        # Use expected outcomes so momentum smoothing code path is triggered
        expected = {"success": True, "quality_score": 0.5}
        outcome1 = TaskOutcome(
            success=True,
            task_id="task-1",
            agent_id="agent-1",
            quality_score=0.9,
        )
        outcome2 = TaskOutcome(
            success=True,
            task_id="task-2",
            agent_id="agent-1",
            quality_score=0.3,
        )

        delta1 = calc.compute_delta(expected, outcome1)
        delta2 = calc.compute_delta(expected, outcome2)

        # Second call should be influenced by first due to momentum
        # High quality (0.9) vs low quality (0.3) should produce different deltas
        assert delta1 != delta2

    def test_reset_agent(self):
        """Test resetting agent state."""
        calc = SurpriseCalculator()
        # Use expected outcome so _running_avg is populated
        expected = {"success": True, "quality_score": 0.5}
        outcome = TaskOutcome(
            success=True,
            task_id="task-1",
            agent_id="agent-1",
            quality_score=0.8,
        )
        calc.compute_delta(expected, outcome)
        assert "agent-1" in calc._running_avg

        calc.reset_agent("agent-1")
        assert "agent-1" not in calc._running_avg


class TestTitanRefineIntegration:
    """Tests for TitanRefineIntegration."""

    @pytest.mark.asyncio
    async def test_reinforce_success_lowers_threshold(
        self,
        titan_integration: TitanRefineIntegration,
        reinforce_action: RefineAction,
        success_outcome: TaskOutcome,
    ):
        """Test that successful outcomes lower memorization threshold."""
        result = await titan_integration.reinforce_pattern(
            reinforce_action, success_outcome
        )

        assert result.success is True
        assert result.operation == RefineOperation.REINFORCE
        assert len(result.affected_memory_ids) == 3

        # Check threshold was lowered
        for memory_id in reinforce_action.target_memory_ids:
            effective = titan_integration.get_effective_threshold(memory_id)
            assert effective < titan_integration.titan.config.memorization_threshold

    @pytest.mark.asyncio
    async def test_reinforce_success_increases_learning_rate(
        self,
        titan_integration: TitanRefineIntegration,
        reinforce_action: RefineAction,
        success_outcome: TaskOutcome,
    ):
        """Test that successful outcomes increase learning rate."""
        await titan_integration.reinforce_pattern(reinforce_action, success_outcome)

        for memory_id in reinforce_action.target_memory_ids:
            effective_lr = titan_integration.get_effective_learning_rate(memory_id)
            base_lr = titan_integration.titan.config.ttt_learning_rate
            assert effective_lr > base_lr

    @pytest.mark.asyncio
    async def test_reinforce_failure_raises_threshold(
        self,
        titan_integration: TitanRefineIntegration,
        reinforce_action: RefineAction,
        failure_outcome: TaskOutcome,
    ):
        """Test that failed outcomes raise memorization threshold."""
        result = await titan_integration.reinforce_pattern(
            reinforce_action, failure_outcome
        )

        assert result.success is True

        # Check threshold was raised slightly
        for memory_id in reinforce_action.target_memory_ids:
            adjustment = titan_integration._threshold_adjustments.get(memory_id, 0)
            assert adjustment > 0  # Positive adjustment = higher threshold

    @pytest.mark.asyncio
    async def test_reinforce_disabled_raises_error(
        self,
        mock_titan_service: MagicMock,
        reinforce_action: RefineAction,
        success_outcome: TaskOutcome,
    ):
        """Test that REINFORCE raises error when disabled."""
        config = MemoryEvolutionConfig()
        config.features.reinforce_enabled = False
        set_memory_evolution_config(config)

        integration = TitanRefineIntegration(
            titan_service=mock_titan_service,
            config=config,
        )

        with pytest.raises(FeatureDisabledError):
            await integration.reinforce_pattern(reinforce_action, success_outcome)

    @pytest.mark.asyncio
    async def test_reinforce_wrong_operation_raises_error(
        self,
        titan_integration: TitanRefineIntegration,
        success_outcome: TaskOutcome,
    ):
        """Test that non-REINFORCE operation raises error."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,  # Wrong operation
            target_memory_ids=["mem-1"],
            reasoning="Test",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(Exception):  # ValidationError
            await titan_integration.reinforce_pattern(action, success_outcome)

    @pytest.mark.asyncio
    async def test_reinforce_metrics_in_result(
        self,
        titan_integration: TitanRefineIntegration,
        reinforce_action: RefineAction,
        success_outcome: TaskOutcome,
    ):
        """Test that result contains reinforcement metrics."""
        result = await titan_integration.reinforce_pattern(
            reinforce_action, success_outcome
        )

        assert "threshold_adjustment" in result.metrics
        assert "learning_rate_multiplier" in result.metrics
        assert "surprise_delta" in result.metrics
        assert "affected_memories" in result.metrics
        assert result.metrics["affected_memories"] == 3

    def test_get_reinforcement_stats(
        self,
        titan_integration: TitanRefineIntegration,
    ):
        """Test getting reinforcement statistics."""
        # Apply some adjustments
        titan_integration._threshold_adjustments["mem-1"] = -0.1
        titan_integration._threshold_adjustments["mem-2"] = -0.05
        titan_integration._learning_rate_multipliers["mem-1"] = 1.5

        stats = titan_integration.get_reinforcement_stats()

        assert stats["memories_with_threshold_adjustment"] == 2
        assert stats["memories_with_lr_adjustment"] == 1
        assert stats["avg_threshold_adjustment"] == pytest.approx(-0.075)

    def test_reset_memory_adjustments(
        self,
        titan_integration: TitanRefineIntegration,
    ):
        """Test resetting adjustments for a specific memory."""
        titan_integration._threshold_adjustments["mem-1"] = -0.1
        titan_integration._learning_rate_multipliers["mem-1"] = 1.5

        titan_integration.reset_memory_adjustments("mem-1")

        assert "mem-1" not in titan_integration._threshold_adjustments
        assert "mem-1" not in titan_integration._learning_rate_multipliers

    def test_reset_all_adjustments(
        self,
        titan_integration: TitanRefineIntegration,
    ):
        """Test resetting all adjustments."""
        titan_integration._threshold_adjustments["mem-1"] = -0.1
        titan_integration._threshold_adjustments["mem-2"] = -0.05
        titan_integration._learning_rate_multipliers["mem-1"] = 1.5

        titan_integration.reset_all_adjustments()

        assert len(titan_integration._threshold_adjustments) == 0
        assert len(titan_integration._learning_rate_multipliers) == 0

    def test_threshold_adjustment_bounds(
        self,
        titan_integration: TitanRefineIntegration,
    ):
        """Test that threshold adjustments are bounded."""
        # Apply many negative adjustments
        for _ in range(20):
            titan_integration._apply_threshold_adjustment("mem-1", -0.1)

        adjustment = titan_integration._threshold_adjustments["mem-1"]
        assert adjustment >= -0.3  # Bounded at -0.3

    def test_learning_rate_multiplier_bounds(
        self,
        titan_integration: TitanRefineIntegration,
    ):
        """Test that learning rate multipliers are bounded."""
        # Apply many positive multipliers
        for _ in range(20):
            titan_integration._apply_learning_rate_multiplier("mem-1", 1.5)

        multiplier = titan_integration._learning_rate_multipliers["mem-1"]
        max_factor = titan_integration.config.reinforce.max_reinforcement_factor
        assert multiplier <= max_factor


class TestReinforceMetrics:
    """Tests for ReinforceMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating reinforce metrics."""
        metrics = ReinforceMetrics(
            threshold_adjustment=-0.1,
            learning_rate_multiplier=1.2,
            surprise_delta=0.5,
            affected_memories=3,
            latency_ms=45.0,
        )
        assert metrics.threshold_adjustment == -0.1
        assert metrics.affected_memories == 3

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = ReinforceMetrics(
            threshold_adjustment=-0.08,
            learning_rate_multiplier=1.15,
            surprise_delta=0.3,
            affected_memories=5,
            latency_ms=32.5,
        )
        data = metrics.to_dict()

        assert data["threshold_adjustment"] == -0.08
        assert data["learning_rate_multiplier"] == 1.15
        assert data["surprise_delta"] == 0.3
        assert data["affected_memories"] == 5
        assert data["latency_ms"] == 32.5
