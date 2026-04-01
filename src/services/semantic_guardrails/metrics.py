"""
Project Aura - Semantic Guardrails Metrics Publisher

Publishes CloudWatch metrics for monitoring guardrails performance,
threat detection rates, and latency percentiles.

Metrics Namespace: Aura/SemanticGuardrails

Key Metrics:
- ThreatDetected: Count by threat level and category
- ProcessingLatencyMs: Histogram of total processing time
- LayerLatencyMs: Histogram by layer
- FalsePositiveCount: Tracked false positive reports
- CorpusHitRate: Embedding corpus match rate
- CacheHitRate: Query cache effectiveness
- SessionEscalationCount: HITL escalations triggered

Security Rationale:
- Metrics enable anomaly detection for novel attack patterns
- Latency tracking ensures SLA compliance
- No PII or sensitive content in metrics (only aggregates)

Author: Project Aura Team
Created: 2026-01-25
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .config import MetricsConfig, get_guardrails_config
from .contracts import ThreatAssessment, ThreatCategory

logger = logging.getLogger(__name__)


class CloudWatchClient(Protocol):
    """Protocol for CloudWatch client."""

    def put_metric_data(self, **kwargs: Any) -> dict[str, Any]:
        """Put metric data to CloudWatch."""
        ...


class GuardrailsMetricsPublisher:
    """
    CloudWatch metrics publisher for semantic guardrails.

    Publishes performance and threat detection metrics to CloudWatch
    for monitoring, alerting, and dashboards.

    Metrics Published:
    - ThreatDetected: Threat count by level and category
    - ProcessingLatencyMs: End-to-end latency
    - LayerLatencyMs: Per-layer latency breakdown
    - CacheHitRate: Cache effectiveness
    - DecisionCount: Count by recommended action

    Usage:
        publisher = GuardrailsMetricsPublisher()
        publisher.record_assessment(assessment)
        publisher.flush()  # Batch publish to CloudWatch

    Thread-safe: Yes (with thread-safe CloudWatch client)
    """

    NAMESPACE = "Aura/SemanticGuardrails"

    def __init__(
        self,
        cloudwatch_client: Optional[CloudWatchClient] = None,
        config: Optional[MetricsConfig] = None,
    ):
        """
        Initialize the metrics publisher.

        Args:
            cloudwatch_client: CloudWatch client (uses mock if None)
            config: Metrics configuration (uses global config if None)
        """
        if config is None:
            global_config = get_guardrails_config()
            config = global_config.metrics
        self.config = config

        self._cloudwatch = cloudwatch_client
        self._mock_mode = cloudwatch_client is None

        # Metric buffer for batch publishing
        self._metric_buffer: list[dict[str, Any]] = []
        self._buffer_start_time: Optional[float] = None

        # Local counters for mock mode
        self._mock_metrics: dict[str, float] = {}

        if self._mock_mode:
            logger.info("GuardrailsMetricsPublisher initialized in MOCK mode")
        else:
            logger.info(
                f"GuardrailsMetricsPublisher initialized "
                f"(namespace={self.NAMESPACE}, buffer_size={config.buffer_size})"
            )

    def record_assessment(self, assessment: ThreatAssessment) -> None:
        """
        Record metrics from a threat assessment.

        Args:
            assessment: ThreatAssessment to record metrics from
        """
        if not self.config.enabled:
            return

        timestamp = datetime.now(timezone.utc)

        # Record threat level count
        self._add_metric(
            metric_name="ThreatDetected",
            value=1.0,
            unit="Count",
            dimensions={
                "ThreatLevel": assessment.threat_level.name,
                "Action": assessment.recommended_action.value,
            },
            timestamp=timestamp,
        )

        # Record threat category (if not NONE)
        if assessment.primary_category != ThreatCategory.NONE:
            self._add_metric(
                metric_name="ThreatByCategory",
                value=1.0,
                unit="Count",
                dimensions={
                    "Category": assessment.primary_category.value,
                    "ThreatLevel": assessment.threat_level.name,
                },
                timestamp=timestamp,
            )

        # Record total processing latency
        self._add_metric(
            metric_name="ProcessingLatencyMs",
            value=assessment.total_processing_time_ms,
            unit="Milliseconds",
            dimensions={},
            timestamp=timestamp,
        )

        # Record per-layer latency
        for layer_result in assessment.layer_results:
            self._add_metric(
                metric_name="LayerLatencyMs",
                value=layer_result.processing_time_ms,
                unit="Milliseconds",
                dimensions={
                    "Layer": layer_result.layer_name,
                    "LayerNumber": str(layer_result.layer_number),
                },
                timestamp=timestamp,
            )

        # Record confidence
        self._add_metric(
            metric_name="AssessmentConfidence",
            value=assessment.confidence,
            unit="None",
            dimensions={
                "ThreatLevel": assessment.threat_level.name,
            },
            timestamp=timestamp,
        )

        # Record intervention required
        if assessment.requires_intervention:
            self._add_metric(
                metric_name="InterventionRequired",
                value=1.0,
                unit="Count",
                dimensions={
                    "Action": assessment.recommended_action.value,
                },
                timestamp=timestamp,
            )

    def record_cache_hit(self, layer_name: str, hit: bool) -> None:
        """
        Record a cache hit or miss.

        Args:
            layer_name: Name of the layer (e.g., "embedding_detector")
            hit: True if cache hit, False if miss
        """
        if not self.config.enabled:
            return

        self._add_metric(
            metric_name="CacheAccess",
            value=1.0,
            unit="Count",
            dimensions={
                "Layer": layer_name,
                "Result": "Hit" if hit else "Miss",
            },
            timestamp=datetime.now(timezone.utc),
        )

    def record_corpus_match(self, matched: bool, similarity_score: float = 0.0) -> None:
        """
        Record an embedding corpus match result.

        Args:
            matched: True if similar threat found
            similarity_score: Highest similarity score (0.0-1.0)
        """
        if not self.config.enabled:
            return

        timestamp = datetime.now(timezone.utc)

        self._add_metric(
            metric_name="CorpusQuery",
            value=1.0,
            unit="Count",
            dimensions={
                "Result": "Match" if matched else "NoMatch",
            },
            timestamp=timestamp,
        )

        if matched and similarity_score > 0:
            self._add_metric(
                metric_name="CorpusSimilarityScore",
                value=similarity_score,
                unit="None",
                dimensions={},
                timestamp=timestamp,
            )

    def record_session_escalation(
        self, session_id: str, cumulative_score: float
    ) -> None:
        """
        Record a session HITL escalation.

        Args:
            session_id: Session identifier (not logged, just for context)
            cumulative_score: Cumulative threat score that triggered escalation
        """
        if not self.config.enabled:
            return

        timestamp = datetime.now(timezone.utc)

        self._add_metric(
            metric_name="SessionEscalation",
            value=1.0,
            unit="Count",
            dimensions={},
            timestamp=timestamp,
        )

        self._add_metric(
            metric_name="EscalationCumulativeScore",
            value=cumulative_score,
            unit="None",
            dimensions={},
            timestamp=timestamp,
        )

    def record_false_positive(self, category: ThreatCategory) -> None:
        """
        Record a reported false positive.

        Args:
            category: Category that was incorrectly flagged
        """
        if not self.config.enabled:
            return

        self._add_metric(
            metric_name="FalsePositiveReported",
            value=1.0,
            unit="Count",
            dimensions={
                "Category": category.value,
            },
            timestamp=datetime.now(timezone.utc),
        )

    def record_latency_percentile(
        self,
        percentile: str,
        latency_ms: float,
    ) -> None:
        """
        Record a latency percentile value.

        Args:
            percentile: Percentile name (e.g., "P50", "P95", "P99")
            latency_ms: Latency value in milliseconds
        """
        if not self.config.enabled:
            return

        self._add_metric(
            metric_name=f"Latency{percentile}",
            value=latency_ms,
            unit="Milliseconds",
            dimensions={},
            timestamp=datetime.now(timezone.utc),
        )

    def _add_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: dict[str, str],
        timestamp: datetime,
    ) -> None:
        """Add a metric to the buffer."""
        metric_data = {
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit,
            "Timestamp": timestamp,
            "Dimensions": [{"Name": k, "Value": v} for k, v in dimensions.items()],
        }
        self._metric_buffer.append(metric_data)

        # Track start time for buffer age
        if self._buffer_start_time is None:
            self._buffer_start_time = time.time()

        # Update mock metrics
        if self._mock_mode:
            key = f"{metric_name}:{':'.join(f'{k}={v}' for k, v in sorted(dimensions.items()))}"
            self._mock_metrics[key] = self._mock_metrics.get(key, 0) + value

        # Auto-flush if buffer is full
        if len(self._metric_buffer) >= self.config.buffer_size:
            self.flush()

    def flush(self) -> int:
        """
        Flush buffered metrics to CloudWatch.

        Returns:
            Number of metrics published
        """
        if not self._metric_buffer:
            return 0

        count = len(self._metric_buffer)

        if self._mock_mode:
            # In mock mode, just clear the buffer
            logger.debug(f"Mock flush: {count} metrics")
            self._metric_buffer.clear()
            self._buffer_start_time = None
            return count

        if not self._cloudwatch:
            self._metric_buffer.clear()
            self._buffer_start_time = None
            return 0

        # CloudWatch accepts max 1000 metrics per request
        # Split into batches if needed
        batch_size = 1000
        batches = [
            self._metric_buffer[i : i + batch_size]
            for i in range(0, len(self._metric_buffer), batch_size)
        ]

        for batch in batches:
            try:
                self._cloudwatch.put_metric_data(
                    Namespace=self.NAMESPACE,
                    MetricData=batch,
                )
            except Exception as e:
                logger.error(f"Failed to publish metrics batch: {e}")
                # Continue with other batches

        self._metric_buffer.clear()
        self._buffer_start_time = None

        logger.debug(f"Flushed {count} metrics to CloudWatch")
        return count

    def get_buffer_size(self) -> int:
        """Get current buffer size."""
        return len(self._metric_buffer)

    def get_buffer_age_seconds(self) -> float:
        """Get age of oldest metric in buffer."""
        if self._buffer_start_time is None:
            return 0.0
        return time.time() - self._buffer_start_time

    def get_mock_metrics(self) -> dict[str, float]:
        """Get mock metrics (for testing)."""
        return self._mock_metrics.copy()

    def clear_mock_metrics(self) -> None:
        """Clear mock metrics (for testing)."""
        self._mock_metrics.clear()


# =============================================================================
# Module-level convenience functions
# =============================================================================

_publisher_instance: Optional[GuardrailsMetricsPublisher] = None


def get_metrics_publisher() -> GuardrailsMetricsPublisher:
    """Get singleton GuardrailsMetricsPublisher instance."""
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = GuardrailsMetricsPublisher()
    return _publisher_instance


def record_threat_assessment(assessment: ThreatAssessment) -> None:
    """
    Convenience function to record a threat assessment.

    Args:
        assessment: ThreatAssessment to record
    """
    get_metrics_publisher().record_assessment(assessment)


def flush_metrics() -> int:
    """
    Convenience function to flush metrics.

    Returns:
        Number of metrics flushed
    """
    return get_metrics_publisher().flush()


def reset_metrics_publisher() -> None:
    """Reset metrics publisher singleton (for testing)."""
    global _publisher_instance
    _publisher_instance = None
