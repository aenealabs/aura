"""CloudWatch metrics publisher for Constitutional AI Phase 4.

This module provides specialized CloudWatch metrics publishing for
Constitutional AI evaluation metrics as specified in ADR-063 Phase 4.

Key metrics published:
- CritiqueLatencyP95: P95 critique latency (<500ms target)
- CritiqueAccuracy: Agreement with human evaluation (>90% target)
- RevisionConvergenceRate: Successful revision rate (>95% target)
- CacheHitRate: Semantic cache effectiveness (>30% target)
- NonEvasiveRate: Constructive engagement rate (>70% target)
- GoldenSetPassRate: Regression test pass rate
- EvaluationPairsProcessed: Daily evaluation volume
- Issues by severity: CRITICAL, HIGH, MEDIUM, LOW counts
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CAIMetricName(Enum):
    """Constitutional AI metric names for CloudWatch."""

    # Latency metrics
    CRITIQUE_LATENCY_P95 = "CritiqueLatencyP95"
    CRITIQUE_LATENCY_AVG = "CritiqueLatencyAvg"
    REVISION_LATENCY_P95 = "RevisionLatencyP95"

    # Quality metrics
    CRITIQUE_ACCURACY = "CritiqueAccuracy"
    REVISION_CONVERGENCE_RATE = "RevisionConvergenceRate"
    NON_EVASIVE_RATE = "NonEvasiveRate"
    GOLDEN_SET_PASS_RATE = "GoldenSetPassRate"

    # Optimization metrics
    CACHE_HIT_RATE = "CacheHitRate"
    FAST_PATH_BLOCK_RATE = "FastPathBlockRate"

    # Volume metrics
    EVALUATION_PAIRS_PROCESSED = "EvaluationPairsProcessed"
    CRITIQUE_COUNT = "CritiqueCount"
    REVISION_COUNT = "RevisionCount"

    # Issue counts
    CRITICAL_ISSUES = "CriticalIssues"
    HIGH_ISSUES = "HighIssues"
    MEDIUM_ISSUES = "MediumIssues"
    LOW_ISSUES = "LowIssues"

    # Regression metrics
    REGRESSIONS_DETECTED = "RegressionsDetected"
    CRITICAL_REGRESSIONS = "CriticalRegressions"


# CloudWatch namespace for Constitutional AI
CONSTITUTIONAL_AI_NAMESPACE = "Aura/ConstitutionalAI"


class CAIMetricsMode(Enum):
    """Operating modes for metrics publisher."""

    MOCK = "mock"  # In-memory storage for testing
    AWS = "aws"  # Real CloudWatch


@dataclass
class CAIMetricsPublisherConfig:
    """Configuration for CAI metrics publisher."""

    mode: CAIMetricsMode = CAIMetricsMode.MOCK
    namespace: str = CONSTITUTIONAL_AI_NAMESPACE
    environment: str = "dev"
    service_name: str = "constitutional-ai"
    buffer_size: int = 100
    flush_interval_seconds: float = 60.0
    enabled: bool = True


@dataclass
class MetricDatum:
    """A single metric data point."""

    metric_name: str
    value: float
    unit: str = "None"
    dimensions: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_cloudwatch_format(self) -> Dict[str, Any]:
        """Convert to CloudWatch PutMetricData format."""
        datum = {
            "MetricName": self.metric_name,
            "Value": self.value,
            "Unit": self.unit,
            "Timestamp": self.timestamp.isoformat(),
        }
        if self.dimensions:
            datum["Dimensions"] = [
                {"Name": k, "Value": v} for k, v in self.dimensions.items()
            ]
        return datum


@dataclass
class PublisherStats:
    """Statistics for the metrics publisher."""

    metrics_published: int = 0
    metrics_buffered: int = 0
    publish_errors: int = 0
    last_flush_time: Optional[datetime] = None
    buffer_flushes: int = 0


class CAIMetricsPublisher:
    """CloudWatch metrics publisher for Constitutional AI.

    Publishes evaluation metrics to CloudWatch for dashboard visualization
    and alerting as specified in ADR-063 Phase 4.
    """

    def __init__(
        self,
        config: Optional[CAIMetricsPublisherConfig] = None,
    ):
        """Initialize the metrics publisher.

        Args:
            config: Publisher configuration
        """
        self.config = config or CAIMetricsPublisherConfig()
        self._buffer: List[MetricDatum] = []
        self._stats = PublisherStats()
        self._cloudwatch_client = None
        self._flush_task: Optional[asyncio.Task] = None

        # Default dimensions added to all metrics
        self._default_dimensions = {
            "Environment": self.config.environment,
            "Service": self.config.service_name,
        }

    async def publish_evaluation_metrics(
        self,
        critique_accuracy: float,
        revision_convergence_rate: float,
        cache_hit_rate: float,
        non_evasive_rate: float,
        golden_set_pass_rate: float,
        critique_latency_p95_ms: float,
        evaluation_pairs_processed: int = 0,
        critique_count: int = 0,
        issues_by_severity: Optional[Dict[str, int]] = None,
    ) -> bool:
        """Publish a complete set of evaluation metrics.

        Args:
            critique_accuracy: Agreement rate with human labels (0.0-1.0)
            revision_convergence_rate: Successful revision rate (0.0-1.0)
            cache_hit_rate: Cache hit rate (0.0-1.0)
            non_evasive_rate: Non-evasive engagement rate (0.0-1.0)
            golden_set_pass_rate: Golden set pass rate (0.0-1.0)
            critique_latency_p95_ms: P95 critique latency in milliseconds
            evaluation_pairs_processed: Number of pairs evaluated
            critique_count: Total critiques performed
            issues_by_severity: Dict of severity -> count

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enabled:
            return True

        issues = issues_by_severity or {}

        metrics = [
            # Quality metrics (as percentages)
            MetricDatum(
                metric_name=CAIMetricName.CRITIQUE_ACCURACY.value,
                value=critique_accuracy * 100,
                unit="Percent",
            ),
            MetricDatum(
                metric_name=CAIMetricName.REVISION_CONVERGENCE_RATE.value,
                value=revision_convergence_rate * 100,
                unit="Percent",
            ),
            MetricDatum(
                metric_name=CAIMetricName.CACHE_HIT_RATE.value,
                value=cache_hit_rate * 100,
                unit="Percent",
            ),
            MetricDatum(
                metric_name=CAIMetricName.NON_EVASIVE_RATE.value,
                value=non_evasive_rate * 100,
                unit="Percent",
            ),
            MetricDatum(
                metric_name=CAIMetricName.GOLDEN_SET_PASS_RATE.value,
                value=golden_set_pass_rate * 100,
                unit="Percent",
            ),
            # Latency metrics
            MetricDatum(
                metric_name=CAIMetricName.CRITIQUE_LATENCY_P95.value,
                value=critique_latency_p95_ms,
                unit="Milliseconds",
            ),
            # Volume metrics
            MetricDatum(
                metric_name=CAIMetricName.EVALUATION_PAIRS_PROCESSED.value,
                value=float(evaluation_pairs_processed),
                unit="Count",
            ),
            MetricDatum(
                metric_name=CAIMetricName.CRITIQUE_COUNT.value,
                value=float(critique_count),
                unit="Count",
            ),
            # Issue counts
            MetricDatum(
                metric_name=CAIMetricName.CRITICAL_ISSUES.value,
                value=float(issues.get("critical", 0)),
                unit="Count",
            ),
            MetricDatum(
                metric_name=CAIMetricName.HIGH_ISSUES.value,
                value=float(issues.get("high", 0)),
                unit="Count",
            ),
            MetricDatum(
                metric_name=CAIMetricName.MEDIUM_ISSUES.value,
                value=float(issues.get("medium", 0)),
                unit="Count",
            ),
            MetricDatum(
                metric_name=CAIMetricName.LOW_ISSUES.value,
                value=float(issues.get("low", 0)),
                unit="Count",
            ),
        ]

        return await self._publish_metrics(metrics)

    async def publish_regression_metrics(
        self,
        pass_rate: float,
        regressions_detected: int,
        critical_regressions: int,
    ) -> bool:
        """Publish regression testing metrics.

        Args:
            pass_rate: Golden set pass rate (0.0-1.0)
            regressions_detected: Total regressions detected
            critical_regressions: Critical severity regressions

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enabled:
            return True

        metrics = [
            MetricDatum(
                metric_name=CAIMetricName.GOLDEN_SET_PASS_RATE.value,
                value=pass_rate * 100,
                unit="Percent",
            ),
            MetricDatum(
                metric_name=CAIMetricName.REGRESSIONS_DETECTED.value,
                value=float(regressions_detected),
                unit="Count",
            ),
            MetricDatum(
                metric_name=CAIMetricName.CRITICAL_REGRESSIONS.value,
                value=float(critical_regressions),
                unit="Count",
            ),
        ]

        return await self._publish_metrics(metrics)

    async def publish_latency_metrics(
        self,
        critique_latency_p95_ms: float,
        critique_latency_avg_ms: float,
        revision_latency_p95_ms: Optional[float] = None,
    ) -> bool:
        """Publish latency metrics.

        Args:
            critique_latency_p95_ms: P95 critique latency
            critique_latency_avg_ms: Average critique latency
            revision_latency_p95_ms: Optional P95 revision latency

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enabled:
            return True

        metrics = [
            MetricDatum(
                metric_name=CAIMetricName.CRITIQUE_LATENCY_P95.value,
                value=critique_latency_p95_ms,
                unit="Milliseconds",
            ),
            MetricDatum(
                metric_name=CAIMetricName.CRITIQUE_LATENCY_AVG.value,
                value=critique_latency_avg_ms,
                unit="Milliseconds",
            ),
        ]

        if revision_latency_p95_ms is not None:
            metrics.append(
                MetricDatum(
                    metric_name=CAIMetricName.REVISION_LATENCY_P95.value,
                    value=revision_latency_p95_ms,
                    unit="Milliseconds",
                )
            )

        return await self._publish_metrics(metrics)

    async def publish_optimization_metrics(
        self,
        cache_hit_rate: float,
        fast_path_block_rate: float,
    ) -> bool:
        """Publish optimization metrics (cache, fast-path).

        Args:
            cache_hit_rate: Semantic cache hit rate (0.0-1.0)
            fast_path_block_rate: Fast-path block rate (0.0-1.0)

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enabled:
            return True

        metrics = [
            MetricDatum(
                metric_name=CAIMetricName.CACHE_HIT_RATE.value,
                value=cache_hit_rate * 100,
                unit="Percent",
            ),
            MetricDatum(
                metric_name=CAIMetricName.FAST_PATH_BLOCK_RATE.value,
                value=fast_path_block_rate * 100,
                unit="Percent",
            ),
        ]

        return await self._publish_metrics(metrics)

    async def publish_metric(
        self,
        metric_name: CAIMetricName,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None,
        immediate: bool = False,
    ) -> bool:
        """Publish a single metric.

        Args:
            metric_name: The metric name enum
            value: The metric value
            unit: CloudWatch unit (Count, Percent, Milliseconds, etc.)
            dimensions: Additional dimensions
            immediate: If True, flush buffer immediately

        Returns:
            True if successful, False otherwise
        """
        if not self.config.enabled:
            return True

        datum = MetricDatum(
            metric_name=metric_name.value,
            value=value,
            unit=unit,
            dimensions=dimensions or {},
        )

        return await self._publish_metrics([datum], immediate=immediate)

    async def _publish_metrics(
        self,
        metrics: List[MetricDatum],
        immediate: bool = False,
    ) -> bool:
        """Internal method to publish metrics.

        Args:
            metrics: List of metric data points
            immediate: If True, flush immediately

        Returns:
            True if successful
        """
        # Add default dimensions to all metrics
        for metric in metrics:
            metric.dimensions.update(self._default_dimensions)

        if self.config.mode == CAIMetricsMode.MOCK:
            # Mock mode - just track stats
            self._buffer.extend(metrics)
            self._stats.metrics_buffered = len(self._buffer)
            if immediate or len(self._buffer) >= self.config.buffer_size:
                return await self._mock_flush()
            return True
        else:
            # AWS mode - buffer and flush
            self._buffer.extend(metrics)
            self._stats.metrics_buffered = len(self._buffer)

            if immediate or len(self._buffer) >= self.config.buffer_size:
                return await self._flush_to_cloudwatch()
            return True

    async def _mock_flush(self) -> bool:
        """Mock flush for testing."""
        count = len(self._buffer)
        self._stats.metrics_published += count
        self._stats.buffer_flushes += 1
        self._stats.last_flush_time = datetime.now(timezone.utc)
        self._buffer.clear()
        self._stats.metrics_buffered = 0
        logger.debug(f"Mock flushed {count} metrics")
        return True

    async def _flush_to_cloudwatch(self) -> bool:
        """Flush buffered metrics to CloudWatch."""
        if not self._buffer:
            return True

        if self._cloudwatch_client is None:
            try:
                import boto3

                self._cloudwatch_client = boto3.client("cloudwatch")
            except Exception as e:
                logger.error(f"Failed to create CloudWatch client: {e}")
                self._stats.publish_errors += 1
                return False

        try:
            # CloudWatch allows max 1000 metrics per request
            batch_size = 1000
            for i in range(0, len(self._buffer), batch_size):
                batch = self._buffer[i : i + batch_size]
                metric_data = [m.to_cloudwatch_format() for m in batch]

                self._cloudwatch_client.put_metric_data(
                    Namespace=self.config.namespace,
                    MetricData=metric_data,
                )

            count = len(self._buffer)
            self._stats.metrics_published += count
            self._stats.buffer_flushes += 1
            self._stats.last_flush_time = datetime.now(timezone.utc)
            self._buffer.clear()
            self._stats.metrics_buffered = 0

            logger.info(f"Flushed {count} metrics to CloudWatch")
            return True

        except Exception as e:
            logger.error(f"Failed to flush metrics to CloudWatch: {e}")
            self._stats.publish_errors += 1
            return False

    async def flush(self) -> bool:
        """Manually flush all buffered metrics.

        Returns:
            True if successful
        """
        if self.config.mode == CAIMetricsMode.MOCK:
            return await self._mock_flush()
        else:
            return await self._flush_to_cloudwatch()

    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics.

        Returns:
            Dict with publisher stats
        """
        return {
            "metrics_published": self._stats.metrics_published,
            "metrics_buffered": self._stats.metrics_buffered,
            "publish_errors": self._stats.publish_errors,
            "buffer_flushes": self._stats.buffer_flushes,
            "last_flush_time": (
                self._stats.last_flush_time.isoformat()
                if self._stats.last_flush_time
                else None
            ),
            "mode": self.config.mode.value,
            "enabled": self.config.enabled,
        }

    def get_buffered_metrics(self) -> List[Dict[str, Any]]:
        """Get currently buffered metrics (for testing).

        Returns:
            List of buffered metric data
        """
        return [m.to_cloudwatch_format() for m in self._buffer]


# Factory function
def create_cai_metrics_publisher(
    mode: str = "mock",
    environment: str = "dev",
    enabled: bool = True,
) -> CAIMetricsPublisher:
    """Create a CAIMetricsPublisher with specified mode.

    Args:
        mode: "mock" or "aws"
        environment: Environment name (dev, qa, prod)
        enabled: Whether metrics are enabled

    Returns:
        Configured CAIMetricsPublisher
    """
    config = CAIMetricsPublisherConfig(
        mode=CAIMetricsMode.MOCK if mode == "mock" else CAIMetricsMode.AWS,
        environment=environment,
        enabled=enabled,
    )
    return CAIMetricsPublisher(config=config)
