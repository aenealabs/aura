"""Tests for metrics publisher (Phase 2)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.memory_evolution import (
    MemoryEvolutionConfig,
    RefineOperation,
    RefineResult,
    reset_memory_evolution_config,
    set_memory_evolution_config,
)
from src.services.memory_evolution.metrics_publisher import (
    EvolutionMetricsPublisher,
    MetricDataPoint,
    MetricsBuffer,
    get_evolution_metrics_publisher,
    reset_evolution_metrics_publisher,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    reset_memory_evolution_config()
    reset_evolution_metrics_publisher()
    yield
    reset_memory_evolution_config()
    reset_evolution_metrics_publisher()


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
def mock_cloudwatch_client() -> MagicMock:
    """Create a mock CloudWatch client."""
    client = MagicMock()
    client.put_metric_data = AsyncMock(return_value={})
    return client


@pytest.fixture
def publisher(
    mock_cloudwatch_client: MagicMock,
    test_config: MemoryEvolutionConfig,
) -> EvolutionMetricsPublisher:
    """Create an EvolutionMetricsPublisher with mocks."""
    return EvolutionMetricsPublisher(
        cloudwatch_client=mock_cloudwatch_client,
        config=test_config,
        auto_flush=False,  # Manual flush for testing
    )


class TestMetricDataPoint:
    """Tests for MetricDataPoint dataclass."""

    def test_create_data_point(self):
        """Test creating a metric data point."""
        point = MetricDataPoint(
            name="TestMetric",
            value=42.0,
            unit="Count",
            dimensions={"Environment": "test"},
        )
        assert point.name == "TestMetric"
        assert point.value == 42.0
        assert point.unit == "Count"

    def test_to_cloudwatch_format(self):
        """Test conversion to CloudWatch format."""
        point = MetricDataPoint(
            name="TestMetric",
            value=42.0,
            unit="Count",
            dimensions={"Environment": "test", "AgentId": "agent-1"},
            timestamp=datetime(2026, 2, 4, 12, 0, 0, tzinfo=timezone.utc),
        )
        cw_format = point.to_cloudwatch_format()

        assert cw_format["MetricName"] == "TestMetric"
        assert cw_format["Value"] == 42.0
        assert cw_format["Unit"] == "Count"
        assert len(cw_format["Dimensions"]) == 2
        assert "Timestamp" in cw_format

    def test_to_cloudwatch_format_no_dimensions(self):
        """Test conversion without dimensions."""
        point = MetricDataPoint(
            name="SimpleMetric",
            value=1.0,
            unit="None",
        )
        cw_format = point.to_cloudwatch_format()

        assert cw_format["MetricName"] == "SimpleMetric"
        assert "Dimensions" not in cw_format


class TestMetricsBuffer:
    """Tests for MetricsBuffer."""

    def test_add_returns_false_when_not_full(self):
        """Test add returns False when buffer not full."""
        buffer = MetricsBuffer(max_size=5)
        point = MetricDataPoint(name="Test", value=1.0, unit="Count")

        is_full = buffer.add(point)

        assert is_full is False
        assert len(buffer.data_points) == 1

    def test_add_returns_true_when_full(self):
        """Test add returns True when buffer is full."""
        buffer = MetricsBuffer(max_size=2)
        point1 = MetricDataPoint(name="Test1", value=1.0, unit="Count")
        point2 = MetricDataPoint(name="Test2", value=2.0, unit="Count")

        buffer.add(point1)
        is_full = buffer.add(point2)

        assert is_full is True

    def test_flush_returns_and_clears(self):
        """Test flush returns data points and clears buffer."""
        buffer = MetricsBuffer(max_size=10)
        buffer.add(MetricDataPoint(name="Test1", value=1.0, unit="Count"))
        buffer.add(MetricDataPoint(name="Test2", value=2.0, unit="Count"))

        points = buffer.flush()

        assert len(points) == 2
        assert buffer.is_empty()

    def test_is_empty(self):
        """Test is_empty check."""
        buffer = MetricsBuffer()
        assert buffer.is_empty()

        buffer.add(MetricDataPoint(name="Test", value=1.0, unit="Count"))
        assert not buffer.is_empty()


class TestEvolutionMetricsPublisher:
    """Tests for EvolutionMetricsPublisher."""

    @pytest.mark.asyncio
    async def test_publish_refine_result(
        self,
        publisher: EvolutionMetricsPublisher,
    ):
        """Test publishing refine result metrics."""
        result = RefineResult(
            success=True,
            operation=RefineOperation.CONSOLIDATE,
            affected_memory_ids=["mem-1", "mem-2"],
            latency_ms=45.0,
        )

        await publisher.publish_refine_result(
            result=result,
            agent_id="agent-1",
            tenant_id="tenant-123",
        )

        # Should have added 3 metrics: count, latency, success
        assert len(publisher.buffer.data_points) >= 3

    @pytest.mark.asyncio
    async def test_publish_routing_decision(
        self,
        publisher: EvolutionMetricsPublisher,
    ):
        """Test publishing routing decision metrics."""
        await publisher.publish_routing_decision(
            operation=RefineOperation.REINFORCE,
            route="sync",
            confidence=0.95,
            latency_ms=5.0,
        )

        assert len(publisher.buffer.data_points) >= 2

    @pytest.mark.asyncio
    async def test_publish_evolution_metrics(
        self,
        publisher: EvolutionMetricsPublisher,
    ):
        """Test publishing evolution metrics."""
        await publisher.publish_evolution_metrics(
            agent_id="agent-1",
            tenant_id="tenant-123",
            evolution_gain=0.15,
            memory_utilization=0.8,
            strategy_reuse_rate=0.65,
            consolidation_efficiency=0.4,
        )

        assert len(publisher.buffer.data_points) >= 4

    @pytest.mark.asyncio
    async def test_publish_circuit_breaker_state(
        self,
        publisher: EvolutionMetricsPublisher,
    ):
        """Test publishing circuit breaker state."""
        await publisher.publish_circuit_breaker_state(
            operation=RefineOperation.CONSOLIDATE,
            is_open=True,
        )

        assert len(publisher.buffer.data_points) >= 1
        point = publisher.buffer.data_points[-1]
        assert point.value == 1.0  # Open = 1.0

    @pytest.mark.asyncio
    async def test_publish_queue_depth(
        self,
        publisher: EvolutionMetricsPublisher,
    ):
        """Test publishing queue depth."""
        await publisher.publish_queue_depth(
            queue_name="refine-async-queue",
            depth=42,
        )

        assert len(publisher.buffer.data_points) >= 1

    @pytest.mark.asyncio
    async def test_flush(
        self,
        publisher: EvolutionMetricsPublisher,
        mock_cloudwatch_client: MagicMock,
    ):
        """Test flushing metrics to CloudWatch."""
        # Add some metrics
        await publisher.publish_circuit_breaker_state(
            operation=RefineOperation.PRUNE,
            is_open=False,
        )

        count = await publisher.flush()

        assert count >= 1
        mock_cloudwatch_client.put_metric_data.assert_called_once()
        assert publisher.buffer.is_empty()

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(
        self,
        publisher: EvolutionMetricsPublisher,
        mock_cloudwatch_client: MagicMock,
    ):
        """Test flushing empty buffer does nothing."""
        count = await publisher.flush()

        assert count == 0
        mock_cloudwatch_client.put_metric_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_error_requeues(
        self,
        publisher: EvolutionMetricsPublisher,
        mock_cloudwatch_client: MagicMock,
    ):
        """Test that flush error re-adds metrics to buffer."""
        mock_cloudwatch_client.put_metric_data = AsyncMock(
            side_effect=Exception("CloudWatch error")
        )

        await publisher.publish_circuit_breaker_state(
            operation=RefineOperation.CONSOLIDATE,
            is_open=False,
        )
        initial_count = len(publisher.buffer.data_points)

        with pytest.raises(Exception, match="CloudWatch error"):
            await publisher.flush()

        # Metrics should be re-added to buffer
        assert len(publisher.buffer.data_points) == initial_count

    def test_get_base_dimensions(
        self,
        publisher: EvolutionMetricsPublisher,
    ):
        """Test getting base dimensions."""
        dims = publisher._get_base_dimensions()

        assert "Environment" in dims
        assert dims["Environment"] == "test"
        assert "ProjectName" in dims


class TestMetricsPublisherSingleton:
    """Tests for singleton management."""

    def test_get_returns_same_instance(self, mock_cloudwatch_client: MagicMock):
        """Test singleton returns same instance."""
        pub1 = get_evolution_metrics_publisher(cloudwatch_client=mock_cloudwatch_client)
        pub2 = get_evolution_metrics_publisher()
        assert pub1 is pub2

    def test_reset_clears_instance(self, mock_cloudwatch_client: MagicMock):
        """Test reset clears singleton."""
        pub1 = get_evolution_metrics_publisher(cloudwatch_client=mock_cloudwatch_client)
        reset_evolution_metrics_publisher()
        pub2 = get_evolution_metrics_publisher(cloudwatch_client=mock_cloudwatch_client)
        assert pub1 is not pub2

    def test_get_without_client_raises(self):
        """Test getting publisher without client raises."""
        with pytest.raises(ValueError, match="cloudwatch_client is required"):
            get_evolution_metrics_publisher()
