"""
Project Aura - Streaming Analysis Service Metrics

CloudWatch metrics publisher for streaming analysis with
latency tracking, throughput monitoring, and cache statistics.

Based on ADR-079: Scale & AI Model Security
"""

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .config import StreamingConfig, get_streaming_config


@dataclass
class LatencyMetric:
    """Individual latency measurement."""

    operation: str
    latency_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricBuffer:
    """Buffer for batching metrics."""

    metrics: deque = field(default_factory=lambda: deque(maxlen=1000))
    lock: threading.Lock = field(default_factory=threading.Lock)


class StreamingMetricsPublisher:
    """
    Publishes metrics for streaming analysis service.

    Supports:
    - Analysis latency (P50, P95, P99)
    - Throughput (requests/minute, files/minute)
    - Cache hit rates
    - Worker utilization
    - Error rates
    """

    def __init__(self, config: Optional[StreamingConfig] = None):
        """Initialize metrics publisher."""
        self._config = config or get_streaming_config()
        self._cloudwatch = None
        self._buffer = MetricBuffer()
        self._latencies: deque[LatencyMetric] = deque(maxlen=10000)
        self._lock = threading.RLock()  # Use RLock to allow reentrant locking

        # Counters
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._timeout_count = 0
        self._files_analyzed = 0
        self._feedback_generated = 0
        self._cache_hits = 0
        self._cache_misses = 0

        # Initialize CloudWatch client if enabled
        if self._config.metrics.enabled:
            try:
                import boto3

                self._cloudwatch = boto3.client("cloudwatch")
            except ImportError:
                pass

    def record_analysis_latency(
        self,
        latency_ms: float,
        scope: str = "incremental",
        success: bool = True,
    ) -> None:
        """Record analysis latency."""
        with self._lock:
            self._latencies.append(
                LatencyMetric(
                    operation="analysis",
                    latency_ms=latency_ms,
                    tags={"scope": scope, "success": str(success).lower()},
                )
            )
            self._request_count += 1
            if success:
                self._success_count += 1
            else:
                self._failure_count += 1

    def record_cache_hit(self, cache_type: str = "ast") -> None:
        """Record cache hit."""
        with self._lock:
            self._cache_hits += 1
        self._add_metric("CacheHit", 1, {"CacheType": cache_type})

    def record_cache_miss(self, cache_type: str = "ast") -> None:
        """Record cache miss."""
        with self._lock:
            self._cache_misses += 1
        self._add_metric("CacheMiss", 1, {"CacheType": cache_type})

    def record_files_analyzed(self, count: int) -> None:
        """Record files analyzed."""
        with self._lock:
            self._files_analyzed += count
        self._add_metric("FilesAnalyzed", count)

    def record_feedback_generated(
        self,
        count: int,
        severity: str = "all",
    ) -> None:
        """Record feedback items generated."""
        with self._lock:
            self._feedback_generated += count
        self._add_metric("FeedbackGenerated", count, {"Severity": severity})

    def record_timeout(self) -> None:
        """Record analysis timeout."""
        with self._lock:
            self._timeout_count += 1
        self._add_metric("AnalysisTimeout", 1)

    def record_kinesis_records(
        self,
        count: int,
        stream: str,
        operation: str = "write",
    ) -> None:
        """Record Kinesis operations."""
        self._add_metric(
            f"Kinesis{operation.capitalize()}Records",
            count,
            {"Stream": stream},
        )

    def record_worker_utilization(
        self,
        active_workers: int,
        total_workers: int,
    ) -> None:
        """Record worker pool utilization."""
        utilization = (active_workers / total_workers * 100) if total_workers > 0 else 0
        self._add_metric("ActiveWorkers", active_workers)
        self._add_metric("WorkerUtilization", utilization, unit="Percent")

    def record_notification_sent(
        self,
        provider: str,
        success: bool = True,
    ) -> None:
        """Record CI/CD notification."""
        status = "Success" if success else "Failed"
        self._add_metric(f"Notification{status}", 1, {"Provider": provider})

    def get_latency_percentiles(
        self,
        operation: str = "analysis",
    ) -> dict[str, float]:
        """Calculate latency percentiles."""
        with self._lock:
            relevant = [
                m.latency_ms for m in self._latencies if m.operation == operation
            ]

        if not relevant:
            return {"p50": 0, "p95": 0, "p99": 0}

        sorted_latencies = sorted(relevant)
        n = len(sorted_latencies)

        return {
            "p50": sorted_latencies[int(n * 0.50)] if n > 0 else 0,
            "p95": sorted_latencies[int(n * 0.95)] if n > 0 else 0,
            "p99": sorted_latencies[int(n * 0.99)] if n > 0 else 0,
        }

    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        with self._lock:
            total = self._cache_hits + self._cache_misses
        return (self._cache_hits / total) if total > 0 else 0.0

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        with self._lock:
            total = self._success_count + self._failure_count
        return (self._success_count / total) if total > 0 else 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        with self._lock:
            percentiles = self.get_latency_percentiles()
            return {
                "request_count": self._request_count,
                "success_count": self._success_count,
                "failure_count": self._failure_count,
                "timeout_count": self._timeout_count,
                "files_analyzed": self._files_analyzed,
                "feedback_generated": self._feedback_generated,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_hit_rate": self.get_cache_hit_rate(),
                "success_rate": self.get_success_rate(),
                "latency_p50_ms": percentiles["p50"],
                "latency_p95_ms": percentiles["p95"],
                "latency_p99_ms": percentiles["p99"],
            }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self._request_count = 0
            self._success_count = 0
            self._failure_count = 0
            self._timeout_count = 0
            self._files_analyzed = 0
            self._feedback_generated = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._latencies.clear()

    def _add_metric(
        self,
        name: str,
        value: float,
        dimensions: Optional[dict[str, str]] = None,
        unit: str = "Count",
    ) -> None:
        """Add metric to buffer."""
        metric = {
            "MetricName": name,
            "Value": value,
            "Unit": unit,
            "Timestamp": datetime.now(timezone.utc).isoformat(),
            "Dimensions": dimensions or {},
        }

        with self._buffer.lock:
            self._buffer.metrics.append(metric)

        # Flush if buffer is getting full
        if len(self._buffer.metrics) >= self._config.metrics.buffer_size:
            self.flush()

    def flush(self) -> int:
        """Flush metrics to CloudWatch."""
        if not self._config.metrics.enabled or not self._cloudwatch:
            with self._buffer.lock:
                count = len(self._buffer.metrics)
                self._buffer.metrics.clear()
            return count

        with self._buffer.lock:
            metrics_to_send = list(self._buffer.metrics)
            self._buffer.metrics.clear()

        if not metrics_to_send:
            return 0

        try:
            # Convert to CloudWatch format
            metric_data = []
            for m in metrics_to_send:
                dimensions = [
                    {"Name": k, "Value": v} for k, v in m.get("Dimensions", {}).items()
                ]
                dimensions.append(
                    {"Name": "Environment", "Value": self._config.environment}
                )

                metric_data.append(
                    {
                        "MetricName": m["MetricName"],
                        "Value": m["Value"],
                        "Unit": m.get("Unit", "Count"),
                        "Dimensions": dimensions,
                    }
                )

            # Send in batches of 20 (CloudWatch limit)
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i : i + 20]
                self._cloudwatch.put_metric_data(
                    Namespace=self._config.metrics.namespace,
                    MetricData=batch,
                )

            return len(metrics_to_send)
        except Exception:
            # Re-add metrics on failure
            with self._buffer.lock:
                for m in metrics_to_send:
                    self._buffer.metrics.append(m)
            return 0

    def publish_latency_percentiles(self) -> None:
        """Publish latency percentile metrics."""
        percentiles = self.get_latency_percentiles()

        self._add_metric("AnalysisLatencyP50", percentiles["p50"], unit="Milliseconds")
        self._add_metric("AnalysisLatencyP95", percentiles["p95"], unit="Milliseconds")
        self._add_metric("AnalysisLatencyP99", percentiles["p99"], unit="Milliseconds")

    def publish_aggregate_metrics(self) -> None:
        """Publish aggregate metrics."""
        stats = self.get_stats()

        self._add_metric("TotalRequests", stats["request_count"])
        self._add_metric("SuccessfulRequests", stats["success_count"])
        self._add_metric("FailedRequests", stats["failure_count"])
        self._add_metric("TimeoutRequests", stats["timeout_count"])
        self._add_metric("CacheHitRate", stats["cache_hit_rate"] * 100, unit="Percent")
        self._add_metric("SuccessRate", stats["success_rate"] * 100, unit="Percent")

        self.flush()


# Singleton pattern
_streaming_metrics: Optional[StreamingMetricsPublisher] = None


def get_streaming_metrics() -> StreamingMetricsPublisher:
    """Get singleton metrics publisher."""
    global _streaming_metrics
    if _streaming_metrics is None:
        _streaming_metrics = StreamingMetricsPublisher()
    return _streaming_metrics


def reset_streaming_metrics() -> None:
    """Reset singleton metrics publisher."""
    global _streaming_metrics
    _streaming_metrics = None
