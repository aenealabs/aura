"""Tests for evolution metrics (Phase 2)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.memory_evolution import (
    MemoryEvolutionConfig,
    RefineAction,
    RefineOperation,
    reset_memory_evolution_config,
    set_memory_evolution_config,
)
from src.services.memory_evolution.evolution_metrics import (
    EvolutionMetrics,
    EvolutionTracker,
    EvolutionTrackerConfig,
    TaskCompletionRecord,
    get_evolution_tracker,
    reset_evolution_tracker,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    reset_memory_evolution_config()
    reset_evolution_tracker()
    yield
    reset_memory_evolution_config()
    reset_evolution_tracker()


@pytest.fixture
def test_config() -> MemoryEvolutionConfig:
    """Create a test configuration."""
    config = MemoryEvolutionConfig(
        environment="test",
        project_name="aura-test",
    )
    set_memory_evolution_config(config)
    return config


@pytest.fixture
def mock_dynamodb_client() -> MagicMock:
    """Create a mock DynamoDB client."""
    client = MagicMock()
    client.put_item = AsyncMock(return_value={})
    client.query = AsyncMock(return_value={"Items": []})
    return client


@pytest.fixture
def mock_s3_client() -> MagicMock:
    """Create a mock S3 client."""
    client = MagicMock()
    client.put_object = AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_audit_logger() -> MagicMock:
    """Create a mock audit logger."""
    logger = MagicMock()
    logger.log_event = MagicMock(return_value="event-123")
    return logger


@pytest.fixture
def tracker(
    mock_dynamodb_client: MagicMock,
    mock_s3_client: MagicMock,
    mock_audit_logger: MagicMock,
    test_config: MemoryEvolutionConfig,
) -> EvolutionTracker:
    """Create an EvolutionTracker with mocks."""
    return EvolutionTracker(
        dynamodb_client=mock_dynamodb_client,
        s3_client=mock_s3_client,
        audit_logger=mock_audit_logger,
        main_config=test_config,
    )


class TestEvolutionMetrics:
    """Tests for EvolutionMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating evolution metrics."""
        metrics = EvolutionMetrics(
            retrieval_precision=0.85,
            retrieval_recall=0.9,
            strategy_reuse_rate=0.75,
            consolidation_count=5,
            memories_pruned=3,
            reinforcements_applied=10,
            evolution_gain=0.15,
            agent_id="agent-1",
            tenant_id="tenant-123",
            task_count=50,
        )
        assert metrics.retrieval_precision == 0.85
        assert metrics.consolidation_count == 5
        assert metrics.evolution_gain == 0.15

    def test_to_dict(self):
        """Test serialization to dictionary."""
        metrics = EvolutionMetrics(
            retrieval_precision=0.8,
            strategy_reuse_rate=0.6,
            agent_id="agent-1",
            tenant_id="tenant-123",
        )
        data = metrics.to_dict()
        assert data["retrieval_precision"] == 0.8
        assert data["strategy_reuse_rate"] == 0.6
        assert data["agent_id"] == "agent-1"

    def test_default_values(self):
        """Test default values."""
        metrics = EvolutionMetrics()
        assert metrics.retrieval_precision == 0.0
        assert metrics.consolidation_count == 0
        assert metrics.evolution_gain == 0.0
        assert metrics.agent_id == ""


class TestTaskCompletionRecord:
    """Tests for TaskCompletionRecord dataclass."""

    def test_create_record(self):
        """Test creating a task completion record."""
        record = TaskCompletionRecord(
            agent_id="agent-1",
            task_id="task-123",
            tenant_id="tenant-123",
            timestamp="2026-02-04T12:00:00Z",
            outcome="success",
            memories_used_count=5,
            strategies_applied_count=2,
            refine_actions_summary={"consolidate": 1, "prune": 2},
            quality_score=0.85,
            execution_time_ms=150.0,
        )
        assert record.agent_id == "agent-1"
        assert record.outcome == "success"
        assert record.quality_score == 0.85

    def test_to_dynamo_item(self):
        """Test conversion to DynamoDB item format."""
        record = TaskCompletionRecord(
            agent_id="agent-1",
            task_id="task-123",
            tenant_id="tenant-123",
            timestamp="2026-02-04T12:00:00Z",
            outcome="success",
            memories_used_count=5,
            strategies_applied_count=2,
            refine_actions_summary={"consolidate": 1},
            quality_score=0.85,
        )
        item = record.to_dynamo_item(ttl=1707048000)
        assert item["pk"]["S"] == "agent-1#2026-02-04"
        assert item["sk"]["S"] == "2026-02-04T12:00:00Z"
        assert item["task_id"]["S"] == "task-123"
        assert item["outcome"]["S"] == "success"
        assert item["memories_used_count"]["N"] == "5"


class TestEvolutionTrackerConfig:
    """Tests for EvolutionTrackerConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = EvolutionTrackerConfig()
        assert config.retention_days_dev == 90
        assert config.retention_days_prod == 365
        assert config.metrics_aggregation_interval == 60
        assert config.store_full_refine_actions is False
        assert config.min_tasks_for_gain == 10
        assert config.gain_window_size == 100


class TestEvolutionTracker:
    """Tests for EvolutionTracker."""

    @pytest.mark.asyncio
    async def test_record_task_completion(
        self,
        tracker: EvolutionTracker,
        mock_dynamodb_client: MagicMock,
        mock_audit_logger: MagicMock,
    ):
        """Test recording task completion."""
        action = RefineAction(
            operation=RefineOperation.CONSOLIDATE,
            target_memory_ids=["mem-1", "mem-2"],
            reasoning="Test consolidation",
            confidence=0.9,
            tenant_id="tenant-123",
            security_domain="development",
        )

        record = await tracker.record_task_completion(
            agent_id="agent-1",
            task_id="task-123",
            tenant_id="tenant-123",
            outcome="success",
            memories_used=["mem-1", "mem-2", "mem-3"],
            strategies_applied=["strat-1"],
            refine_actions=[action],
            quality_score=0.85,
            execution_time_ms=150.0,
        )

        assert record.agent_id == "agent-1"
        assert record.task_id == "task-123"
        assert record.outcome == "success"
        assert record.memories_used_count == 3
        mock_dynamodb_client.put_item.assert_called_once()
        mock_audit_logger.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_task_completion_with_s3(
        self,
        mock_dynamodb_client: MagicMock,
        mock_s3_client: MagicMock,
        test_config: MemoryEvolutionConfig,
    ):
        """Test recording task completion with S3 storage."""
        config = EvolutionTrackerConfig(store_full_refine_actions=True)
        tracker = EvolutionTracker(
            dynamodb_client=mock_dynamodb_client,
            s3_client=mock_s3_client,
            config=config,
            main_config=test_config,
        )

        action = RefineAction(
            operation=RefineOperation.PRUNE,
            target_memory_ids=["mem-old-1"],
            reasoning="Test prune",
            confidence=0.95,
            tenant_id="tenant-123",
            security_domain="development",
        )

        record = await tracker.record_task_completion(
            agent_id="agent-1",
            task_id="task-456",
            tenant_id="tenant-123",
            outcome="success",
            memories_used=["mem-1"],
            strategies_applied=[],
            refine_actions=[action],
        )

        assert record.s3_detail_key is not None
        mock_s3_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_compute_evolution_gain_insufficient_data(
        self,
        tracker: EvolutionTracker,
        mock_dynamodb_client: MagicMock,
    ):
        """Test evolution gain with insufficient data."""
        mock_dynamodb_client.query = AsyncMock(return_value={"Items": []})

        gain = await tracker.compute_evolution_gain(
            agent_id="agent-1",
            tenant_id="tenant-123",
        )

        assert gain == 0.0

    @pytest.mark.asyncio
    async def test_compute_evolution_gain_with_data(
        self,
        tracker: EvolutionTracker,
        mock_dynamodb_client: MagicMock,
    ):
        """Test evolution gain computation with sufficient data."""
        # Create mock items - 10 older failures, 10 newer successes
        items = []
        for i in range(20):
            outcome = "success" if i < 10 else "failure"
            items.append(
                {
                    "sk": {"S": f"2026-02-0{4 if i < 10 else 3}T{10+i:02d}:00:00Z"},
                    "outcome": {"S": outcome},
                }
            )

        mock_dynamodb_client.query = AsyncMock(return_value={"Items": items})

        gain = await tracker.compute_evolution_gain(
            agent_id="agent-1",
            tenant_id="tenant-123",
            window_size=20,
        )

        # Newer half has 100% success, older half has 0% success
        assert gain == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_get_metrics_for_window_empty(
        self,
        tracker: EvolutionTracker,
        mock_dynamodb_client: MagicMock,
    ):
        """Test getting metrics for empty window."""
        mock_dynamodb_client.query = AsyncMock(return_value={"Items": []})

        now = datetime.now(timezone.utc)
        metrics = await tracker.get_metrics_for_window(
            agent_id="agent-1",
            tenant_id="tenant-123",
            start_time=now - timedelta(days=1),
            end_time=now,
        )

        assert metrics.task_count == 0
        assert metrics.agent_id == "agent-1"

    def test_summarize_actions(self, tracker: EvolutionTracker):
        """Test summarizing refine actions."""
        actions = [
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-1"],
                reasoning="Test",
                confidence=0.9,
                tenant_id="t-1",
                security_domain="dev",
            ),
            RefineAction(
                operation=RefineOperation.CONSOLIDATE,
                target_memory_ids=["mem-2"],
                reasoning="Test",
                confidence=0.9,
                tenant_id="t-1",
                security_domain="dev",
            ),
            RefineAction(
                operation=RefineOperation.PRUNE,
                target_memory_ids=["mem-3"],
                reasoning="Test",
                confidence=0.9,
                tenant_id="t-1",
                security_domain="dev",
            ),
        ]

        summary = tracker._summarize_actions(actions)

        assert summary["consolidate"] == 2
        assert summary["prune"] == 1


class TestEvolutionTrackerSingleton:
    """Tests for singleton management."""

    def test_get_returns_same_instance(self, mock_dynamodb_client: MagicMock):
        """Test singleton returns same instance."""
        tracker1 = get_evolution_tracker(dynamodb_client=mock_dynamodb_client)
        tracker2 = get_evolution_tracker()
        assert tracker1 is tracker2

    def test_reset_clears_instance(self, mock_dynamodb_client: MagicMock):
        """Test reset clears singleton."""
        tracker1 = get_evolution_tracker(dynamodb_client=mock_dynamodb_client)
        reset_evolution_tracker()
        tracker2 = get_evolution_tracker(dynamodb_client=mock_dynamodb_client)
        assert tracker1 is not tracker2

    def test_get_without_client_raises(self):
        """Test getting tracker without client raises."""
        with pytest.raises(ValueError, match="dynamodb_client is required"):
            get_evolution_tracker()
