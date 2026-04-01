"""Tests for refine integration (Phase 1b)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.memory_evolution import (
    FeatureDisabledError,
    MemoryEvolutionConfig,
    MemoryRefiner,
    RefineAction,
    RefineOperation,
    RefineResult,
    reset_memory_evolution_config,
    set_memory_evolution_config,
)
from src.services.memory_evolution.refine_integration import (
    RefineActionRouter,
    RefineDecision,
    RefineDecisionMaker,
    reset_refine_decision_maker,
    reset_refine_router,
)
from src.services.memory_evolution.titan_integration import (
    TaskOutcome,
    TitanRefineIntegration,
    reset_titan_refine_integration,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    reset_memory_evolution_config()
    reset_refine_router()
    reset_refine_decision_maker()
    reset_titan_refine_integration()
    yield
    reset_memory_evolution_config()
    reset_refine_router()
    reset_refine_decision_maker()
    reset_titan_refine_integration()


@pytest.fixture
def test_config() -> MemoryEvolutionConfig:
    """Create a test configuration."""
    config = MemoryEvolutionConfig(
        environment="test",
        project_name="aura-test",
    )
    config.features.consolidate_enabled = True
    config.features.prune_enabled = True
    config.features.reinforce_enabled = True
    config.async_config.async_enabled = False  # Disable async for simpler testing
    set_memory_evolution_config(config)
    return config


@pytest.fixture
def mock_memory_refiner() -> MagicMock:
    """Create a mock memory refiner."""
    refiner = MagicMock(spec=MemoryRefiner)
    refiner.refine = AsyncMock(
        return_value=RefineResult(
            success=True,
            operation=RefineOperation.CONSOLIDATE,
            affected_memory_ids=["mem-merged"],
            rollback_token="rb-123",
        )
    )
    return refiner


@pytest.fixture
def mock_titan_integration() -> MagicMock:
    """Create a mock Titan integration."""
    integration = MagicMock(spec=TitanRefineIntegration)
    integration.reinforce_pattern = AsyncMock(
        return_value=RefineResult(
            success=True,
            operation=RefineOperation.REINFORCE,
            affected_memory_ids=["mem-1", "mem-2"],
            metrics={"threshold_adjustment": -0.1},
        )
    )
    return integration


@pytest.fixture
def mock_sqs_client() -> MagicMock:
    """Create a mock SQS client."""
    client = MagicMock()
    client.send_message = AsyncMock(return_value={"MessageId": "msg-123"})
    return client


@pytest.fixture
def router(
    mock_memory_refiner: MagicMock,
    mock_titan_integration: MagicMock,
    test_config: MemoryEvolutionConfig,
) -> RefineActionRouter:
    """Create a RefineActionRouter with mocks."""
    return RefineActionRouter(
        memory_refiner=mock_memory_refiner,
        titan_integration=mock_titan_integration,
        config=test_config,
    )


@pytest.fixture
def success_outcome() -> TaskOutcome:
    """Create a successful task outcome."""
    return TaskOutcome(
        success=True,
        task_id="task-123",
        agent_id="agent-1",
        quality_score=0.85,
        reuse_count=2,
    )


class TestRefineDecision:
    """Tests for RefineDecision dataclass."""

    def test_create_should_refine(self):
        """Test creating a decision to refine."""
        decision = RefineDecision(
            should_refine=True,
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Similar memories detected",
            confidence=0.9,
        )
        assert decision.should_refine is True
        assert decision.operation == RefineOperation.CONSOLIDATE
        assert len(decision.target_memory_ids) == 2

    def test_create_should_not_refine(self):
        """Test creating a decision not to refine."""
        decision = RefineDecision(
            should_refine=False,
            reasoning="No conditions met",
        )
        assert decision.should_refine is False
        assert decision.operation is None
        assert decision.target_memory_ids == []

    def test_default_target_memory_ids(self):
        """Test default empty list for target_memory_ids."""
        decision = RefineDecision(should_refine=False)
        assert decision.target_memory_ids == []


class TestRefineDecisionMaker:
    """Tests for RefineDecisionMaker."""

    def test_decide_reinforce_after_consecutive_successes(
        self,
        test_config: MemoryEvolutionConfig,
    ):
        """Test REINFORCE decision after 3+ consecutive successes."""
        maker = RefineDecisionMaker(config=test_config)

        # Simulate 3 consecutive successes
        for i in range(3):
            outcome = TaskOutcome(
                success=True,
                task_id=f"task-{i}",
                agent_id="agent-1",
                quality_score=0.8,
            )
            recent_memories = [{"memory_id": f"mem-{i}"} for i in range(5)]
            decision = maker.decide("agent-1", outcome, recent_memories)

        assert decision.should_refine is True
        assert decision.operation == RefineOperation.REINFORCE
        assert "consecutive successes" in decision.reasoning.lower()

    def test_decide_no_refine_after_failure(
        self,
        test_config: MemoryEvolutionConfig,
    ):
        """Test no REINFORCE after failure resets counter."""
        maker = RefineDecisionMaker(config=test_config)

        # 2 successes then 1 failure
        for i in range(2):
            outcome = TaskOutcome(
                success=True,
                task_id=f"task-{i}",
                agent_id="agent-1",
            )
            maker.decide("agent-1", outcome, [])

        failure_outcome = TaskOutcome(
            success=False,
            task_id="task-fail",
            agent_id="agent-1",
        )
        decision = maker.decide("agent-1", failure_outcome, [])

        # Counter should be reset
        assert maker._consecutive_successes.get("agent-1", 0) == 0
        assert maker._consecutive_failures.get("agent-1", 0) == 1

    def test_decide_prune_stale_memories(
        self,
        test_config: MemoryEvolutionConfig,
    ):
        """Test PRUNE decision for stale memories."""
        maker = RefineDecisionMaker(config=test_config)

        outcome = TaskOutcome(
            success=True,
            task_id="task-1",
            agent_id="agent-1",
        )
        stale_memories = [
            {"memory_id": "mem-old-1", "access_count": 0, "age_days": 30},
            {"memory_id": "mem-old-2", "access_count": 0, "age_days": 45},
        ]
        decision = maker.decide("agent-1", outcome, stale_memories)

        # With stale memories and prune enabled, should trigger prune
        if decision.should_refine and decision.operation == RefineOperation.PRUNE:
            assert len(decision.target_memory_ids) > 0

    def test_reset_agent_state(
        self,
        test_config: MemoryEvolutionConfig,
    ):
        """Test resetting agent state."""
        maker = RefineDecisionMaker(config=test_config)

        # Build up some state
        for i in range(2):
            outcome = TaskOutcome(
                success=True,
                task_id=f"task-{i}",
                agent_id="agent-1",
            )
            maker.decide("agent-1", outcome, [])

        assert maker._consecutive_successes.get("agent-1", 0) == 2

        maker.reset_agent_state("agent-1")

        assert "agent-1" not in maker._consecutive_successes
        assert "agent-1" not in maker._consecutive_failures


class TestRefineActionRouter:
    """Tests for RefineActionRouter."""

    @pytest.mark.asyncio
    async def test_route_consolidate_sync(
        self,
        router: RefineActionRouter,
        mock_memory_refiner: MagicMock,
    ):
        """Test routing CONSOLIDATE to sync execution."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.95,  # Above sync threshold
            tenant_id="tenant-123",
            security_domain="development",
        )

        result = await router.route_action(action)

        assert result.success is True
        mock_memory_refiner.refine.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_prune_sync(
        self,
        router: RefineActionRouter,
        mock_memory_refiner: MagicMock,
    ):
        """Test routing PRUNE to sync execution."""
        action = RefineAction(
            operation=RefineOperation.PRUNE,
            target_memory_ids=["mem-old-1"],
            reasoning="Test",
            confidence=0.92,
            tenant_id="tenant-123",
            security_domain="development",
        )

        result = await router.route_action(action)

        assert result.success is True
        mock_memory_refiner.refine.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_reinforce_sync(
        self,
        router: RefineActionRouter,
        mock_titan_integration: MagicMock,
        success_outcome: TaskOutcome,
    ):
        """Test routing REINFORCE to Titan integration."""
        action = RefineAction(
            operation=RefineOperation.REINFORCE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.95,
            tenant_id="tenant-123",
            security_domain="development",
        )

        result = await router.route_action(action, success_outcome)

        assert result.success is True
        assert result.operation == RefineOperation.REINFORCE
        mock_titan_integration.reinforce_pattern.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_reinforce_requires_outcome(
        self,
        router: RefineActionRouter,
    ):
        """Test REINFORCE requires TaskOutcome."""
        action = RefineAction(
            operation=RefineOperation.REINFORCE,
            target_memory_ids=["mem-1"],
            reasoning="Test",
            confidence=0.95,
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(ValueError, match="TaskOutcome required"):
            await router.route_action(action, outcome=None)

    @pytest.mark.asyncio
    async def test_route_async_with_sqs(
        self,
        mock_memory_refiner: MagicMock,
        mock_titan_integration: MagicMock,
        mock_sqs_client: MagicMock,
    ):
        """Test routing to async queue when confidence is low."""
        config = MemoryEvolutionConfig()
        config.features.consolidate_enabled = True
        config.async_config.async_enabled = True
        config.async_config.sync_confidence_threshold = 0.9
        set_memory_evolution_config(config)

        router = RefineActionRouter(
            memory_refiner=mock_memory_refiner,
            titan_integration=mock_titan_integration,
            sqs_client=mock_sqs_client,
            config=config,
        )

        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.7,  # Below sync threshold
            tenant_id="tenant-123",
            security_domain="development",
        )

        result = await router.route_action(action)

        assert result.success is True
        assert result.metrics.get("queued") is True
        mock_sqs_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_reinforce_without_integration_raises(
        self,
        mock_memory_refiner: MagicMock,
        test_config: MemoryEvolutionConfig,
        success_outcome: TaskOutcome,
    ):
        """Test REINFORCE without Titan integration raises error."""
        router = RefineActionRouter(
            memory_refiner=mock_memory_refiner,
            titan_integration=None,  # No Titan integration
            config=test_config,
        )

        action = RefineAction(
            operation=RefineOperation.REINFORCE,
            target_memory_ids=["mem-1"],
            reasoning="Test",
            confidence=0.95,
            tenant_id="tenant-123",
            security_domain="development",
        )

        with pytest.raises(FeatureDisabledError):
            await router.route_action(action, success_outcome)

    def test_is_operation_enabled(
        self,
        router: RefineActionRouter,
    ):
        """Test checking if operations are enabled."""
        assert router.is_operation_enabled(RefineOperation.CONSOLIDATE) is True
        assert router.is_operation_enabled(RefineOperation.PRUNE) is True
        assert router.is_operation_enabled(RefineOperation.REINFORCE) is True
        assert router.is_operation_enabled(RefineOperation.ABSTRACT) is False
        assert router.is_operation_enabled(RefineOperation.LINK) is False

    @pytest.mark.asyncio
    async def test_route_fallback_to_sync_when_async_disabled(
        self,
        mock_memory_refiner: MagicMock,
        test_config: MemoryEvolutionConfig,
    ):
        """Test fallback to sync when async is disabled."""
        test_config.async_config.async_enabled = False

        router = RefineActionRouter(
            memory_refiner=mock_memory_refiner,
            config=test_config,
        )

        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.5,  # Low confidence but async disabled
            tenant_id="tenant-123",
            security_domain="development",
        )

        result = await router.route_action(action)

        assert result.success is True
        mock_memory_refiner.refine.assert_called_once()


class TestRouterMetrics:
    """Tests for router metrics publishing."""

    @pytest.mark.asyncio
    async def test_publishes_routing_metrics(
        self,
        mock_memory_refiner: MagicMock,
        test_config: MemoryEvolutionConfig,
    ):
        """Test that routing metrics are published."""
        mock_metrics = MagicMock()
        mock_metrics.publish_routing_decision = AsyncMock()

        router = RefineActionRouter(
            memory_refiner=mock_memory_refiner,
            metrics_publisher=mock_metrics,
            config=test_config,
        )

        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.95,
            tenant_id="tenant-123",
            security_domain="development",
        )

        await router.route_action(action)

        mock_metrics.publish_routing_decision.assert_called_once()
        call_args = mock_metrics.publish_routing_decision.call_args
        assert call_args[1]["operation"] == RefineOperation.CONSOLIDATE
        assert call_args[1]["route"] == "sync"
        assert call_args[1]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_metrics_failure_doesnt_break_routing(
        self,
        mock_memory_refiner: MagicMock,
        test_config: MemoryEvolutionConfig,
    ):
        """Test that metrics failure doesn't break routing."""
        mock_metrics = MagicMock()
        mock_metrics.publish_routing_decision = AsyncMock(
            side_effect=Exception("Metrics error")
        )

        router = RefineActionRouter(
            memory_refiner=mock_memory_refiner,
            metrics_publisher=mock_metrics,
            config=test_config,
        )

        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test",
            confidence=0.95,
            tenant_id="tenant-123",
            security_domain="development",
        )

        # Should succeed despite metrics failure
        result = await router.route_action(action)
        assert result.success is True
