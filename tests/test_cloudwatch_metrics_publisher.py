"""
Project Aura - CloudWatch Metrics Publisher Tests

Tests for the CloudWatch metrics publisher that publishes anomaly detection
metrics and events to AWS CloudWatch.
"""

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Save original modules before mocking to prevent test pollution
_modules_to_save = [
    "boto3",
    "botocore",
    "botocore.exceptions",
    "src.services.cloudwatch_metrics_publisher",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock boto3 before importing
mock_boto3 = MagicMock()
mock_boto3.client = MagicMock(return_value=MagicMock())
sys.modules["boto3"] = mock_boto3

mock_botocore = MagicMock()
mock_botocore.exceptions = MagicMock()
mock_botocore.exceptions.ClientError = Exception
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore.exceptions

from src.services.cloudwatch_metrics_publisher import (
    CloudWatchMetricsPublisher,
    MetricDatum,
    MetricNamespace,
    PublisherMode,
    PublisherStats,
    create_metrics_publisher,
    get_metrics_publisher,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


class TestMetricNamespace:
    """Tests for MetricNamespace enum."""

    def test_anomalies(self):
        """Test anomalies namespace."""
        assert MetricNamespace.ANOMALIES.value == "Aura/Anomalies"

    def test_security(self):
        """Test security namespace."""
        assert MetricNamespace.SECURITY.value == "Aura/Security"

    def test_orchestrator(self):
        """Test orchestrator namespace."""
        assert MetricNamespace.ORCHESTRATOR.value == "Aura/Orchestrator"

    def test_notifications(self):
        """Test notifications namespace."""
        assert MetricNamespace.NOTIFICATIONS.value == "Aura/Notifications"

    def test_observability(self):
        """Test observability namespace."""
        assert MetricNamespace.OBSERVABILITY.value == "Aura/Observability"

    def test_autonomy(self):
        """Test autonomy namespace."""
        assert MetricNamespace.AUTONOMY.value == "Aura/Autonomy"

    def test_gpu_scheduler(self):
        """Test GPU scheduler namespace."""
        assert MetricNamespace.GPU_SCHEDULER.value == "Aura/GPUScheduler"

    def test_constitutional_ai_namespace(self):
        """Test Constitutional AI namespace."""
        assert MetricNamespace.CONSTITUTIONAL_AI.value == "Aura/ConstitutionalAI"

    def test_all_namespaces_exist(self):
        """Test all expected namespaces exist."""
        namespaces = list(MetricNamespace)
        assert len(namespaces) == 8


class TestPublisherMode:
    """Tests for PublisherMode enum."""

    def test_aws_mode(self):
        """Test AWS mode."""
        assert PublisherMode.AWS.value == "aws"

    def test_mock_mode(self):
        """Test mock mode."""
        assert PublisherMode.MOCK.value == "mock"


class TestMetricDatum:
    """Tests for MetricDatum dataclass."""

    def test_minimal_datum(self):
        """Test minimal metric datum creation."""
        datum = MetricDatum(
            metric_name="TestMetric",
            value=1.0,
        )
        assert datum.metric_name == "TestMetric"
        assert datum.value == 1.0
        assert datum.unit == "Count"
        assert datum.dimensions == {}
        assert datum.storage_resolution == 60

    def test_full_datum(self):
        """Test full metric datum creation."""
        timestamp = datetime.now(timezone.utc)
        datum = MetricDatum(
            metric_name="FullMetric",
            value=42.5,
            unit="Seconds",
            dimensions={"Type": "test", "Severity": "high"},
            timestamp=timestamp,
            storage_resolution=1,  # High resolution
        )
        assert datum.unit == "Seconds"
        assert datum.dimensions["Type"] == "test"
        assert datum.timestamp == timestamp
        assert datum.storage_resolution == 1

    def test_to_cloudwatch_format_minimal(self):
        """Test conversion to CloudWatch format without dimensions."""
        datum = MetricDatum(
            metric_name="SimpleMetric",
            value=10.0,
        )
        cw_format = datum.to_cloudwatch_format()

        assert cw_format["MetricName"] == "SimpleMetric"
        assert cw_format["Value"] == 10.0
        assert cw_format["Unit"] == "Count"
        assert "Dimensions" not in cw_format

    def test_to_cloudwatch_format_with_dimensions(self):
        """Test conversion to CloudWatch format with dimensions."""
        datum = MetricDatum(
            metric_name="DimensionMetric",
            value=5.0,
            dimensions={"Environment": "prod", "Service": "api"},
        )
        cw_format = datum.to_cloudwatch_format()

        assert "Dimensions" in cw_format
        assert len(cw_format["Dimensions"]) == 2
        dimension_names = [d["Name"] for d in cw_format["Dimensions"]]
        assert "Environment" in dimension_names
        assert "Service" in dimension_names


class TestPublisherStats:
    """Tests for PublisherStats dataclass."""

    def test_default_stats(self):
        """Test default stats values."""
        stats = PublisherStats()
        assert stats.metrics_published == 0
        assert stats.metrics_failed == 0
        assert stats.batches_sent == 0
        assert stats.last_publish_time is None
        assert stats.errors == []

    def test_stats_with_values(self):
        """Test stats with custom values."""
        stats = PublisherStats(
            metrics_published=100,
            metrics_failed=5,
            batches_sent=10,
            last_publish_time=datetime.now(timezone.utc),
            errors=["Error 1", "Error 2"],
        )
        assert stats.metrics_published == 100
        assert stats.metrics_failed == 5
        assert len(stats.errors) == 2


class TestCloudWatchMetricsPublisher:
    """Tests for CloudWatchMetricsPublisher class."""

    def test_init_mock_mode_explicit(self):
        """Test initialization in mock mode explicitly."""
        publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)
        assert publisher.mode == PublisherMode.MOCK

    def test_init_aws_mode_explicit(self):
        """Test initialization in AWS mode explicitly."""
        publisher = CloudWatchMetricsPublisher(mode=PublisherMode.AWS)
        assert publisher.mode == PublisherMode.AWS

    def test_init_default_region(self):
        """Test initialization with default region."""
        publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)
        assert publisher.region == "us-east-1"

    def test_init_custom_region(self):
        """Test initialization with custom region."""
        publisher = CloudWatchMetricsPublisher(
            mode=PublisherMode.MOCK,
            region="eu-west-1",
        )
        assert publisher.region == "eu-west-1"

    def test_init_buffer_size(self):
        """Test initialization with custom buffer size."""
        publisher = CloudWatchMetricsPublisher(
            mode=PublisherMode.MOCK,
            buffer_size=200,
        )
        assert publisher.buffer_size == 200

    def test_init_auto_flush_interval(self):
        """Test initialization with custom flush interval."""
        publisher = CloudWatchMetricsPublisher(
            mode=PublisherMode.MOCK,
            auto_flush_interval=120,
        )
        assert publisher.auto_flush_interval == 120

    def test_init_stats(self):
        """Test stats are initialized."""
        publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)
        assert publisher.stats is not None
        assert publisher.stats.metrics_published == 0

    def test_init_buffer_empty(self):
        """Test buffer is initially empty."""
        publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)
        assert len(publisher._buffer) == 0

    def test_max_metrics_per_batch(self):
        """Test max metrics per batch constant."""
        assert CloudWatchMetricsPublisher.MAX_METRICS_PER_BATCH == 1000


class TestCloudWatchMetricsPublisherPublishing:
    """Tests for publishing functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)

    @pytest.mark.asyncio
    async def test_publish_metric_buffered(self):
        """Test publishing metric to buffer."""
        result = await self.publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="TestCount",
            value=1.0,
        )

        assert result is True
        assert len(self.publisher._buffer["Aura/Anomalies"]) == 1

    @pytest.mark.asyncio
    async def test_publish_metric_with_dimensions(self):
        """Test publishing metric with dimensions."""
        await self.publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="TestCount",
            value=1.0,
            dimensions={"Type": "test"},
        )

        buffered = self.publisher._buffer["Aura/Anomalies"][0]
        assert "Type" in buffered.dimensions

    @pytest.mark.asyncio
    async def test_publish_metric_immediate(self):
        """Test publishing metric immediately."""
        result = await self.publisher.publish_metric(
            namespace=MetricNamespace.SECURITY,
            metric_name="Immediate",
            value=1.0,
            immediate=True,
        )

        assert result is True
        # Should be in mock metrics, not buffer
        assert len(self.publisher._mock_metrics) == 1

    @pytest.mark.asyncio
    async def test_publish_metric_string_namespace(self):
        """Test publishing with string namespace."""
        await self.publisher.publish_metric(
            namespace="Custom/Namespace",
            metric_name="Custom",
            value=1.0,
        )

        assert "Custom/Namespace" in self.publisher._buffer

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self):
        """Test flushing empty buffer."""
        result = await self.publisher.flush()
        assert result is True

    @pytest.mark.asyncio
    async def test_flush_with_metrics(self):
        """Test flushing buffer with metrics."""
        await self.publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="Test1",
            value=1.0,
        )
        await self.publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="Test2",
            value=2.0,
        )

        result = await self.publisher.flush()

        assert result is True
        assert len(self.publisher._buffer) == 0
        assert len(self.publisher._mock_metrics) == 2

    @pytest.mark.asyncio
    async def test_mock_publish_updates_stats(self):
        """Test mock publish updates statistics."""
        await self.publisher.publish_metric(
            namespace=MetricNamespace.SECURITY,
            metric_name="Test",
            value=1.0,
            immediate=True,
        )

        assert self.publisher.stats.metrics_published == 1
        assert self.publisher.stats.batches_sent == 1
        assert self.publisher.stats.last_publish_time is not None


class TestCloudWatchMetricsPublisherEvents:
    """Tests for event publishing methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)

    @pytest.mark.asyncio
    async def test_publish_orchestrator_event(self):
        """Test publishing orchestrator event."""
        result = await self.publisher.publish_orchestrator_event(
            event_type="task_completed",
            task_id="task-123",
            success=True,
            duration_seconds=5.5,
        )

        assert result is True
        # Should have event count and duration metrics
        assert len(self.publisher._buffer[MetricNamespace.ORCHESTRATOR.value]) >= 1

    @pytest.mark.asyncio
    async def test_publish_orchestrator_event_without_duration(self):
        """Test publishing orchestrator event without duration."""
        result = await self.publisher.publish_orchestrator_event(
            event_type="task_triggered",
            success=True,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_publish_notification_event(self):
        """Test publishing notification event."""
        result = await self.publisher.publish_notification_event(
            channel="slack",
            success=True,
            latency_ms=150.0,
        )

        assert result is True
        assert len(self.publisher._buffer[MetricNamespace.NOTIFICATIONS.value]) >= 1

    @pytest.mark.asyncio
    async def test_publish_notification_event_failure(self):
        """Test publishing failed notification event."""
        result = await self.publisher.publish_notification_event(
            channel="pagerduty",
            success=False,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_publish_observability_metrics(self):
        """Test publishing observability (Four Golden Signals) metrics."""
        result = await self.publisher.publish_observability_metrics(
            error_rate=0.02,
            latency_p95=150.0,
            request_count=1000,
            saturation=0.75,
        )

        assert result is True
        assert len(self.publisher._buffer[MetricNamespace.OBSERVABILITY.value]) == 4

    @pytest.mark.asyncio
    async def test_publish_autonomy_event(self):
        """Test publishing autonomy event."""
        result = await self.publisher.publish_autonomy_event(
            event_type="policy_created",
            organization_id="org-123",
            policy_id="policy-abc",
            user="admin@example.com",
        )

        assert result is True
        assert len(self.publisher._buffer[MetricNamespace.AUTONOMY.value]) >= 1

    @pytest.mark.asyncio
    async def test_publish_autonomy_event_hitl_toggled(self):
        """Test publishing HITL toggle event."""
        result = await self.publisher.publish_autonomy_event(
            event_type="hitl_toggled",
            organization_id="org-123",
            hitl_enabled=False,
            user="admin",
        )

        assert result is True
        # Should publish to mock immediately for HITL disabled
        assert len(self.publisher._mock_metrics) > 0

    @pytest.mark.asyncio
    async def test_publish_autonomy_event_auto_approval(self):
        """Test publishing auto-approval event."""
        result = await self.publisher.publish_autonomy_event(
            event_type="auto_approval",
            organization_id="org-123",
            auto_approved=True,
            severity="low",
            operation="patch_deploy",
            autonomy_level="assisted",
        )

        assert result is True


class TestCloudWatchMetricsPublisherStats:
    """Tests for statistics and health methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)

    def test_get_stats(self):
        """Test getting publisher statistics."""
        stats = self.publisher.get_stats()

        assert "mode" in stats
        assert stats["mode"] == "mock"
        assert "region" in stats
        assert "metrics_published" in stats
        assert "metrics_failed" in stats
        assert "batches_sent" in stats
        assert "buffer_sizes" in stats
        assert "recent_errors" in stats

    @pytest.mark.asyncio
    async def test_get_stats_after_publish(self):
        """Test stats after publishing."""
        await self.publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="Test",
            value=1.0,
            immediate=True,
        )

        stats = self.publisher.get_stats()
        assert stats["metrics_published"] == 1
        assert stats["batches_sent"] == 1
        assert stats["last_publish_time"] is not None

    def test_get_mock_metrics(self):
        """Test getting mock metrics."""
        metrics = self.publisher.get_mock_metrics()
        assert isinstance(metrics, list)
        assert len(metrics) == 0

    @pytest.mark.asyncio
    async def test_get_mock_metrics_after_publish(self):
        """Test getting mock metrics after publishing."""
        await self.publisher.publish_metric(
            namespace=MetricNamespace.SECURITY,
            metric_name="CVEDetected",
            value=1.0,
            immediate=True,
        )

        metrics = self.publisher.get_mock_metrics()
        assert len(metrics) == 1
        assert metrics[0]["metric_name"] == "CVEDetected"

    def test_clear_mock_metrics(self):
        """Test clearing mock metrics."""
        self.publisher._mock_metrics = [{"test": "metric"}]
        self.publisher.clear_mock_metrics()
        assert len(self.publisher._mock_metrics) == 0


class TestCloudWatchMetricsPublisherLifecycle:
    """Tests for lifecycle methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.publisher = CloudWatchMetricsPublisher(
            mode=PublisherMode.MOCK,
            auto_flush_interval=0,  # Disable auto-flush for tests
        )

    @pytest.mark.asyncio
    async def test_start(self):
        """Test starting the publisher."""
        await self.publisher.start()
        assert self.publisher._running is True

    @pytest.mark.asyncio
    async def test_start_twice(self):
        """Test starting publisher twice does nothing."""
        await self.publisher.start()
        await self.publisher.start()
        assert self.publisher._running is True

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping the publisher."""
        await self.publisher.start()
        await self.publisher.stop()
        assert self.publisher._running is False

    @pytest.mark.asyncio
    async def test_stop_flushes_buffer(self):
        """Test stopping flushes remaining metrics."""
        await self.publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="Test",
            value=1.0,
        )

        await self.publisher.stop()

        assert len(self.publisher._buffer) == 0
        assert len(self.publisher._mock_metrics) == 1


class TestCloudWatchMetricsPublisherModeDetection:
    """Tests for mode detection."""

    def test_detect_mode_default_mock(self):
        """Test default mode is mock without AWS environment."""
        publisher = CloudWatchMetricsPublisher()
        # In test environment without AWS creds, should be mock
        assert publisher.mode == PublisherMode.MOCK

    @patch.dict("os.environ", {"CLOUDWATCH_MODE": "mock"})
    def test_detect_mode_env_mock(self):
        """Test mode detection from environment variable."""
        publisher = CloudWatchMetricsPublisher()
        assert publisher.mode == PublisherMode.MOCK

    @patch.dict("os.environ", {"CLOUDWATCH_MODE": "aws"})
    def test_detect_mode_env_aws(self):
        """Test mode detection from environment variable."""
        publisher = CloudWatchMetricsPublisher()
        assert publisher.mode == PublisherMode.AWS


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_metrics_publisher(self):
        """Test getting singleton publisher."""
        publisher = get_metrics_publisher()
        assert publisher is not None
        assert isinstance(publisher, CloudWatchMetricsPublisher)

    def test_get_metrics_publisher_singleton(self):
        """Test publisher is a singleton."""
        publisher1 = get_metrics_publisher()
        publisher2 = get_metrics_publisher()
        assert publisher1 is publisher2

    def test_create_metrics_publisher(self):
        """Test creating new publisher."""
        publisher = create_metrics_publisher(mode=PublisherMode.MOCK)
        assert publisher is not None
        assert publisher.mode == PublisherMode.MOCK

    def test_create_metrics_publisher_with_region(self):
        """Test creating publisher with custom region."""
        publisher = create_metrics_publisher(
            mode=PublisherMode.MOCK,
            region="ap-northeast-1",
        )
        assert publisher.region == "ap-northeast-1"


class TestDefaultDimensions:
    """Tests for default dimensions."""

    def test_default_dimensions_exist(self):
        """Test default dimensions are defined."""
        assert "Environment" in CloudWatchMetricsPublisher.DEFAULT_DIMENSIONS
        assert "Service" in CloudWatchMetricsPublisher.DEFAULT_DIMENSIONS

    @pytest.mark.asyncio
    async def test_default_dimensions_added(self):
        """Test default dimensions are added to metrics."""
        publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)
        await publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="Test",
            value=1.0,
        )

        buffered = publisher._buffer["Aura/Anomalies"][0]
        assert "Service" in buffered.dimensions
        assert buffered.dimensions["Service"] == "aura"

    @pytest.mark.asyncio
    async def test_custom_dimensions_merged(self):
        """Test custom dimensions are merged with defaults."""
        publisher = CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)
        await publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="Test",
            value=1.0,
            dimensions={"Custom": "value"},
        )

        buffered = publisher._buffer["Aura/Anomalies"][0]
        assert "Custom" in buffered.dimensions
        assert "Service" in buffered.dimensions
