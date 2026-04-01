"""
Project Aura - CGE CloudWatch Metrics Publisher

Publishes coherence scores, latency, cache hit rates, and escalation
rates to CloudWatch for operational monitoring and alerting.

Author: Project Aura Team
Created: 2026-02-11
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .config import MetricsConfig
from .contracts import CoherenceAction, CoherenceResult

logger = logging.getLogger(__name__)


class CloudWatchClient(Protocol):
    """Protocol for CloudWatch metrics publishing."""

    def put_metric_data(
        self,
        Namespace: str,
        MetricData: list[dict[str, Any]],
    ) -> dict[str, Any]: ...


@dataclass
class MetricDatum:
    """Single metric data point."""

    name: str
    value: float
    unit: str = "None"
    dimensions: dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None


class CGEMetricsPublisher:
    """Buffered CloudWatch metrics publisher for the CGE.

    Buffers metric data points and flushes to CloudWatch in batches
    to minimize API calls while maintaining near-real-time visibility.
    """

    def __init__(
        self,
        cloudwatch_client: Optional[CloudWatchClient] = None,
        config: Optional[MetricsConfig] = None,
        environment: str = "dev",
    ):
        self._client = cloudwatch_client
        self._config = config or MetricsConfig()
        self._environment = environment
        self._buffer: deque[MetricDatum] = deque(maxlen=self._config.buffer_size * 2)
        self._last_flush = time.monotonic()

    def record_assessment(self, result: CoherenceResult) -> None:
        """Record metrics for a coherence assessment.

        Publishes:
        - CCS composite score
        - Per-axis scores
        - Latency
        - Cache hit/miss
        - Action taken
        """
        if not self._config.enabled:
            return

        base_dims = self._base_dimensions(result.policy_profile)

        # Composite CCS score
        self._buffer_metric(
            name=self._config.metric_ccs_score,
            value=result.composite_score,
            unit="None",
            dimensions=base_dims,
        )

        # Latency
        self._buffer_metric(
            name=self._config.metric_latency,
            value=result.computation_time_ms,
            unit="Milliseconds",
            dimensions=base_dims,
        )

        # Cache hit rate (1.0 for hit, 0.0 for miss)
        self._buffer_metric(
            name=self._config.metric_cache_hit,
            value=1.0 if result.cache_hit else 0.0,
            unit="None",
            dimensions=base_dims,
        )

        # Escalation rate (1.0 if escalated or rejected, 0.0 otherwise)
        escalated = result.action in (CoherenceAction.ESCALATE, CoherenceAction.REJECT)
        self._buffer_metric(
            name=self._config.metric_escalation_rate,
            value=1.0 if escalated else 0.0,
            unit="None",
            dimensions=base_dims,
        )

        # Per-axis scores
        if self._config.include_axis:
            for axis_score in result.axis_scores:
                axis_dims = {**base_dims, "Axis": axis_score.axis.value}
                self._buffer_metric(
                    name=self._config.metric_axis_score,
                    value=axis_score.score,
                    unit="None",
                    dimensions=axis_dims,
                )

        # Auto-flush if buffer is full
        if len(self._buffer) >= self._config.buffer_size:
            self.flush()

    def flush(self) -> int:
        """Flush buffered metrics to CloudWatch.

        Returns:
            Number of metrics flushed
        """
        if not self._buffer or not self._client or not self._config.enabled:
            return 0

        metrics_to_send = []
        while self._buffer:
            datum = self._buffer.popleft()
            metric_data: dict[str, Any] = {
                "MetricName": datum.name,
                "Value": datum.value,
                "Unit": datum.unit,
            }
            if datum.dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": v} for k, v in datum.dimensions.items()
                ]
            if datum.timestamp:
                metric_data["Timestamp"] = datum.timestamp
            metrics_to_send.append(metric_data)

        if not metrics_to_send:
            return 0

        # CloudWatch accepts max 1000 metrics per PutMetricData call
        count = 0
        for i in range(0, len(metrics_to_send), 1000):
            batch = metrics_to_send[i : i + 1000]
            try:
                self._client.put_metric_data(
                    Namespace=self._config.namespace,
                    MetricData=batch,
                )
                count += len(batch)
            except Exception:
                logger.warning(
                    "Failed to publish %d metrics to CloudWatch",
                    len(batch),
                    exc_info=True,
                )

        self._last_flush = time.monotonic()
        return count

    def _buffer_metric(
        self,
        name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[dict[str, str]] = None,
    ) -> None:
        """Add a metric to the buffer."""
        self._buffer.append(
            MetricDatum(
                name=name,
                value=value,
                unit=unit,
                dimensions=dimensions or {},
                timestamp=datetime.now(timezone.utc),
            )
        )

    def _base_dimensions(self, profile: str) -> dict[str, str]:
        """Build base dimensions for metrics."""
        dims: dict[str, str] = {}
        if self._config.include_environment:
            dims["Environment"] = self._environment
        if self._config.include_profile:
            dims["PolicyProfile"] = profile
        return dims


# Singleton
_publisher_instance: Optional[CGEMetricsPublisher] = None


def get_metrics_publisher() -> CGEMetricsPublisher:
    """Get singleton metrics publisher."""
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = CGEMetricsPublisher()
    return _publisher_instance


def reset_metrics_publisher() -> None:
    """Reset singleton (for testing)."""
    global _publisher_instance
    _publisher_instance = None
