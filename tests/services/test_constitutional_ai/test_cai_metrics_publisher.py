"""Unit tests for Constitutional AI Metrics Publisher.

Tests CloudWatch metrics publishing for Phase 4 evaluation.
"""

from datetime import datetime, timezone

import pytest

from src.services.constitutional_ai.cai_metrics_publisher import (
    CAIMetricName,
    CAIMetricsMode,
    CAIMetricsPublisher,
    CAIMetricsPublisherConfig,
    MetricDatum,
    PublisherStats,
    create_cai_metrics_publisher,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config() -> CAIMetricsPublisherConfig:
    """Create mock CAI metrics publisher config."""
    return CAIMetricsPublisherConfig(
        mode=CAIMetricsMode.MOCK,
        namespace="Aura/ConstitutionalAI",
        environment="dev",
        service_name="constitutional-ai",
        buffer_size=10,
        enabled=True,
    )


@pytest.fixture
def mock_publisher(mock_config) -> CAIMetricsPublisher:
    """Create a mock CAIMetricsPublisher."""
    return CAIMetricsPublisher(config=mock_config)


@pytest.fixture
def disabled_config() -> CAIMetricsPublisherConfig:
    """Create disabled CAI metrics publisher config."""
    return CAIMetricsPublisherConfig(
        mode=CAIMetricsMode.MOCK,
        enabled=False,
    )


@pytest.fixture
def disabled_publisher(disabled_config) -> CAIMetricsPublisher:
    """Create a disabled CAIMetricsPublisher."""
    return CAIMetricsPublisher(config=disabled_config)


# =============================================================================
# Test CAIMetricsPublisherConfig
# =============================================================================


class TestCAIMetricsPublisherConfig:
    """Tests for CAIMetricsPublisherConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CAIMetricsPublisherConfig()
        assert config.mode == CAIMetricsMode.MOCK
        assert config.namespace == "Aura/ConstitutionalAI"
        assert config.environment == "dev"
        assert config.buffer_size == 100
        assert config.enabled is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CAIMetricsPublisherConfig(
            mode=CAIMetricsMode.AWS,
            namespace="Custom/Namespace",
            environment="prod",
            buffer_size=50,
            enabled=True,
        )
        assert config.mode == CAIMetricsMode.AWS
        assert config.namespace == "Custom/Namespace"
        assert config.environment == "prod"
        assert config.buffer_size == 50


# =============================================================================
# Test CAIMetricsPublisher Initialization
# =============================================================================


class TestCAIMetricsPublisherInit:
    """Tests for CAIMetricsPublisher initialization."""

    def test_init_mock_mode(self, mock_config):
        """Test initializing in mock mode."""
        publisher = CAIMetricsPublisher(config=mock_config)
        assert publisher.config.mode == CAIMetricsMode.MOCK

    def test_init_default_config(self):
        """Test initializing with default config."""
        publisher = CAIMetricsPublisher()
        assert publisher.config is not None

    def test_init_sets_default_dimensions(self, mock_publisher):
        """Test that default dimensions are set."""
        assert "Environment" in mock_publisher._default_dimensions
        assert "Service" in mock_publisher._default_dimensions


# =============================================================================
# Test publish_evaluation_metrics
# =============================================================================


class TestPublishEvaluationMetrics:
    """Tests for publish_evaluation_metrics method."""

    @pytest.mark.asyncio
    async def test_publish_evaluation_metrics_mock_mode(self, mock_publisher):
        """Test publishing evaluation metrics in mock mode."""
        result = await mock_publisher.publish_evaluation_metrics(
            critique_accuracy=0.92,
            revision_convergence_rate=0.96,
            cache_hit_rate=0.35,
            non_evasive_rate=0.75,
            golden_set_pass_rate=0.95,
            critique_latency_p95_ms=450.0,
            evaluation_pairs_processed=100,
            critique_count=500,
            issues_by_severity={"critical": 2, "high": 5, "medium": 10, "low": 20},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_publish_evaluation_metrics_disabled(self, disabled_publisher):
        """Test publishing when disabled returns True without publishing."""
        result = await disabled_publisher.publish_evaluation_metrics(
            critique_accuracy=0.92,
            revision_convergence_rate=0.96,
            cache_hit_rate=0.35,
            non_evasive_rate=0.75,
            golden_set_pass_rate=0.95,
            critique_latency_p95_ms=450.0,
        )
        assert result is True
        # Should not have buffered any metrics
        assert len(disabled_publisher._buffer) == 0

    @pytest.mark.asyncio
    async def test_publish_evaluation_metrics_tracks_stats(self, mock_publisher):
        """Test that metrics publishing updates stats."""
        await mock_publisher.publish_evaluation_metrics(
            critique_accuracy=0.92,
            revision_convergence_rate=0.96,
            cache_hit_rate=0.35,
            non_evasive_rate=0.75,
            golden_set_pass_rate=0.95,
            critique_latency_p95_ms=450.0,
        )
        # Metrics should have been published (mock mode auto-flushes when buffer is small)
        assert mock_publisher._stats.metrics_published > 0


# =============================================================================
# Test publish_regression_metrics
# =============================================================================


class TestPublishRegressionMetrics:
    """Tests for publish_regression_metrics method."""

    @pytest.mark.asyncio
    async def test_publish_regression_metrics(self, mock_publisher):
        """Test publishing regression metrics."""
        result = await mock_publisher.publish_regression_metrics(
            pass_rate=0.95,
            regressions_detected=5,
            critical_regressions=2,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_publish_regression_metrics_disabled(self, disabled_publisher):
        """Test publishing regression metrics when disabled."""
        result = await disabled_publisher.publish_regression_metrics(
            pass_rate=0.95,
            regressions_detected=5,
            critical_regressions=2,
        )
        assert result is True


# =============================================================================
# Test publish_latency_metrics
# =============================================================================


class TestPublishLatencyMetrics:
    """Tests for publish_latency_metrics method."""

    @pytest.mark.asyncio
    async def test_publish_latency_metrics(self, mock_publisher):
        """Test publishing latency metrics."""
        result = await mock_publisher.publish_latency_metrics(
            critique_latency_p95_ms=450.0,
            critique_latency_avg_ms=250.0,
            revision_latency_p95_ms=800.0,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_publish_latency_metrics_without_revision(self, mock_publisher):
        """Test publishing latency metrics without revision latency."""
        result = await mock_publisher.publish_latency_metrics(
            critique_latency_p95_ms=450.0,
            critique_latency_avg_ms=250.0,
        )
        assert result is True


# =============================================================================
# Test publish_optimization_metrics
# =============================================================================


class TestPublishOptimizationMetrics:
    """Tests for publish_optimization_metrics method."""

    @pytest.mark.asyncio
    async def test_publish_optimization_metrics(self, mock_publisher):
        """Test publishing optimization metrics."""
        result = await mock_publisher.publish_optimization_metrics(
            cache_hit_rate=0.35,
            fast_path_block_rate=0.15,
        )
        assert result is True


# =============================================================================
# Test publish_metric
# =============================================================================


class TestPublishMetric:
    """Tests for publish_metric method."""

    @pytest.mark.asyncio
    async def test_publish_single_metric(self, mock_publisher):
        """Test publishing a single metric."""
        result = await mock_publisher.publish_metric(
            metric_name=CAIMetricName.CRITIQUE_ACCURACY,
            value=92.0,
            unit="Percent",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_publish_metric_with_dimensions(self, mock_publisher):
        """Test publishing a metric with custom dimensions."""
        result = await mock_publisher.publish_metric(
            metric_name=CAIMetricName.EVALUATION_PAIRS_PROCESSED,
            value=100.0,
            unit="Count",
            dimensions={"BatchId": "batch_001"},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_publish_metric_immediate_flush(self, mock_publisher):
        """Test publishing with immediate flush."""
        result = await mock_publisher.publish_metric(
            metric_name=CAIMetricName.CRITICAL_REGRESSIONS,
            value=2.0,
            unit="Count",
            immediate=True,
        )
        assert result is True


# =============================================================================
# Test flush
# =============================================================================


class TestFlush:
    """Tests for flush method."""

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self, mock_publisher):
        """Test flushing an empty buffer."""
        result = await mock_publisher.flush()
        assert result is True

    @pytest.mark.asyncio
    async def test_flush_with_metrics(self, mock_publisher):
        """Test flushing buffered metrics."""
        # Buffer some metrics
        await mock_publisher.publish_metric(
            metric_name=CAIMetricName.CRITIQUE_COUNT,
            value=100.0,
            unit="Count",
        )
        # Flush
        result = await mock_publisher.flush()
        assert result is True
        # Buffer should be empty after flush
        assert mock_publisher._stats.metrics_buffered == 0


# =============================================================================
# Test get_stats
# =============================================================================


class TestGetStats:
    """Tests for get_stats method."""

    def test_get_stats_initial(self, mock_publisher):
        """Test getting stats before any publishing."""
        stats = mock_publisher.get_stats()
        assert stats["metrics_published"] == 0
        assert stats["metrics_buffered"] == 0
        assert stats["publish_errors"] == 0
        assert stats["mode"] == "mock"
        assert stats["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_stats_after_publishing(self, mock_publisher):
        """Test getting stats after publishing."""
        await mock_publisher.publish_metric(
            metric_name=CAIMetricName.CRITIQUE_ACCURACY,
            value=92.0,
            immediate=True,
        )
        stats = mock_publisher.get_stats()
        assert stats["metrics_published"] > 0
        assert stats["buffer_flushes"] > 0


# =============================================================================
# Test get_buffered_metrics
# =============================================================================


class TestGetBufferedMetrics:
    """Tests for get_buffered_metrics method."""

    @pytest.mark.asyncio
    async def test_get_buffered_metrics_empty(self, mock_publisher):
        """Test getting buffered metrics when empty."""
        metrics = mock_publisher.get_buffered_metrics()
        assert metrics == []

    @pytest.mark.asyncio
    async def test_get_buffered_metrics_with_data(self, mock_publisher):
        """Test getting buffered metrics with data."""
        await mock_publisher.publish_metric(
            metric_name=CAIMetricName.CRITIQUE_ACCURACY,
            value=92.0,
        )
        metrics = mock_publisher.get_buffered_metrics()
        assert len(metrics) > 0
        assert all("MetricName" in m for m in metrics)


# =============================================================================
# Test MetricDatum
# =============================================================================


class TestMetricDatum:
    """Tests for MetricDatum model."""

    def test_create_metric_datum(self):
        """Test creating a MetricDatum."""
        datum = MetricDatum(
            metric_name="TestMetric",
            value=42.0,
            unit="Count",
            dimensions={"Env": "dev"},
        )
        assert datum.metric_name == "TestMetric"
        assert datum.value == 42.0
        assert datum.unit == "Count"
        assert datum.dimensions == {"Env": "dev"}

    def test_to_cloudwatch_format(self):
        """Test MetricDatum.to_cloudwatch_format()."""
        datum = MetricDatum(
            metric_name="TestMetric",
            value=42.0,
            unit="Count",
            dimensions={"Env": "dev"},
            timestamp=datetime(2026, 1, 21, tzinfo=timezone.utc),
        )
        formatted = datum.to_cloudwatch_format()
        assert formatted["MetricName"] == "TestMetric"
        assert formatted["Value"] == 42.0
        assert formatted["Unit"] == "Count"
        assert "Dimensions" in formatted
        assert formatted["Dimensions"][0]["Name"] == "Env"
        assert formatted["Dimensions"][0]["Value"] == "dev"

    def test_to_cloudwatch_format_no_dimensions(self):
        """Test MetricDatum.to_cloudwatch_format() without dimensions."""
        datum = MetricDatum(
            metric_name="TestMetric",
            value=42.0,
        )
        formatted = datum.to_cloudwatch_format()
        assert "Dimensions" not in formatted or formatted["Dimensions"] == []


# =============================================================================
# Test CAIMetricName Enum
# =============================================================================


class TestCAIMetricName:
    """Tests for CAIMetricName enum."""

    def test_metric_names_exist(self):
        """Test that expected metric names exist."""
        assert CAIMetricName.CRITIQUE_LATENCY_P95.value == "CritiqueLatencyP95"
        assert CAIMetricName.CRITIQUE_ACCURACY.value == "CritiqueAccuracy"
        assert (
            CAIMetricName.REVISION_CONVERGENCE_RATE.value == "RevisionConvergenceRate"
        )
        assert CAIMetricName.CACHE_HIT_RATE.value == "CacheHitRate"
        assert CAIMetricName.NON_EVASIVE_RATE.value == "NonEvasiveRate"
        assert CAIMetricName.GOLDEN_SET_PASS_RATE.value == "GoldenSetPassRate"

    def test_issue_metric_names(self):
        """Test issue-related metric names."""
        assert CAIMetricName.CRITICAL_ISSUES.value == "CriticalIssues"
        assert CAIMetricName.HIGH_ISSUES.value == "HighIssues"
        assert CAIMetricName.MEDIUM_ISSUES.value == "MediumIssues"
        assert CAIMetricName.LOW_ISSUES.value == "LowIssues"


# =============================================================================
# Test create_cai_metrics_publisher Factory
# =============================================================================


class TestCreateCaiMetricsPublisher:
    """Tests for create_cai_metrics_publisher factory function."""

    def test_create_mock_publisher(self):
        """Test creating a mock publisher."""
        publisher = create_cai_metrics_publisher(mode="mock")
        assert publisher.config.mode == CAIMetricsMode.MOCK

    def test_create_aws_publisher(self):
        """Test creating an AWS publisher."""
        publisher = create_cai_metrics_publisher(mode="aws")
        assert publisher.config.mode == CAIMetricsMode.AWS

    def test_create_with_environment(self):
        """Test creating publisher with environment."""
        publisher = create_cai_metrics_publisher(
            mode="mock",
            environment="prod",
        )
        assert publisher.config.environment == "prod"

    def test_create_disabled_publisher(self):
        """Test creating a disabled publisher."""
        publisher = create_cai_metrics_publisher(
            mode="mock",
            enabled=False,
        )
        assert publisher.config.enabled is False


# =============================================================================
# Test PublisherStats
# =============================================================================


class TestPublisherStats:
    """Tests for PublisherStats model."""

    def test_default_stats(self):
        """Test default PublisherStats values."""
        stats = PublisherStats()
        assert stats.metrics_published == 0
        assert stats.metrics_buffered == 0
        assert stats.publish_errors == 0
        assert stats.last_flush_time is None
        assert stats.buffer_flushes == 0
