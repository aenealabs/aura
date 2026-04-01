"""
Project Aura - Cloud Runtime Security Metrics

CloudWatch metrics publisher for runtime security services.

Based on ADR-077: Cloud Runtime Security Integration
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .config import get_runtime_security_config


@dataclass
class MetricDatum:
    """A single metric data point."""

    name: str
    value: float
    unit: str = "Count"
    dimensions: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsTimer:
    """Context manager for timing operations."""

    def __init__(self, metric_name: str, publisher: "RuntimeSecurityMetricsPublisher"):
        self.metric_name = metric_name
        self.publisher = publisher
        self.start_time: Optional[float] = None
        self.duration_ms: Optional[float] = None

    def __enter__(self) -> "MetricsTimer":
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is not None:
            self.duration_ms = (time.time() - self.start_time) * 1000
            self.publisher.record_latency(self.metric_name, self.duration_ms)


class RuntimeSecurityMetricsPublisher:
    """Publishes CloudWatch metrics for runtime security services."""

    def __init__(self):
        self._config = get_runtime_security_config()
        self._buffer: list[MetricDatum] = []
        self._mock_mode = self._config.metrics.enabled is False

    @property
    def namespace(self) -> str:
        """Get CloudWatch namespace."""
        return self._config.metrics.namespace

    def _publish_batch(self, metrics: list[MetricDatum]) -> None:
        """Publish a batch of metrics to CloudWatch."""
        if self._mock_mode or not metrics:
            return

        # In production, this would use boto3 CloudWatch client
        # For now, we'll just buffer metrics

    def _maybe_flush(self) -> None:
        """Flush buffer if it exceeds configured size."""
        if len(self._buffer) >= self._config.metrics.buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush all buffered metrics to CloudWatch."""
        if self._buffer:
            self._publish_batch(self._buffer)
            self._buffer.clear()

    # Admission Controller Metrics

    def record_admission_decision(
        self,
        decision: str,
        cluster: str,
        namespace: str,
        resource_kind: str,
    ) -> None:
        """Record an admission decision."""
        self._buffer.append(
            MetricDatum(
                name="AdmissionDecision",
                value=1,
                unit="Count",
                dimensions={
                    "Decision": decision,
                    "Cluster": cluster,
                    "Namespace": namespace,
                    "ResourceKind": resource_kind,
                },
            )
        )
        self._maybe_flush()

    def record_admission_latency(self, latency_ms: float, cluster: str) -> None:
        """Record admission webhook latency."""
        self._buffer.append(
            MetricDatum(
                name="AdmissionLatency",
                value=latency_ms,
                unit="Milliseconds",
                dimensions={"Cluster": cluster},
            )
        )
        self._maybe_flush()

    def record_policy_violation(
        self,
        policy_type: str,
        severity: str,
        cluster: str,
    ) -> None:
        """Record a policy violation."""
        self._buffer.append(
            MetricDatum(
                name="PolicyViolation",
                value=1,
                unit="Count",
                dimensions={
                    "PolicyType": policy_type,
                    "Severity": severity,
                    "Cluster": cluster,
                },
            )
        )
        self._maybe_flush()

    def record_image_verification(
        self,
        result: str,  # success, failure, skipped
        cluster: str,
    ) -> None:
        """Record image verification result."""
        self._buffer.append(
            MetricDatum(
                name="ImageVerification",
                value=1,
                unit="Count",
                dimensions={"Result": result, "Cluster": cluster},
            )
        )
        self._maybe_flush()

    # Runtime Correlator Metrics

    def record_event_ingested(
        self,
        event_type: str,
        severity: str,
    ) -> None:
        """Record an ingested runtime event."""
        self._buffer.append(
            MetricDatum(
                name="RuntimeEventIngested",
                value=1,
                unit="Count",
                dimensions={"EventType": event_type, "Severity": severity},
            )
        )
        self._maybe_flush()

    def record_correlation_result(
        self,
        status: str,  # correlated, partial, failed
        event_type: str,
    ) -> None:
        """Record a correlation result."""
        self._buffer.append(
            MetricDatum(
                name="CorrelationResult",
                value=1,
                unit="Count",
                dimensions={"Status": status, "EventType": event_type},
            )
        )
        self._maybe_flush()

    def record_correlation_latency(
        self,
        latency_ms: float,
        event_type: str,
    ) -> None:
        """Record correlation latency."""
        self._buffer.append(
            MetricDatum(
                name="CorrelationLatency",
                value=latency_ms,
                unit="Milliseconds",
                dimensions={"EventType": event_type},
            )
        )
        self._maybe_flush()

    def record_resource_mapping_cache_hit(self, hit: bool) -> None:
        """Record resource mapping cache hit/miss."""
        self._buffer.append(
            MetricDatum(
                name="ResourceMappingCache",
                value=1,
                unit="Count",
                dimensions={"Result": "Hit" if hit else "Miss"},
            )
        )
        self._maybe_flush()

    # Escape Detector Metrics

    def record_escape_attempt(
        self,
        technique: str,
        cluster: str,
        blocked: bool,
    ) -> None:
        """Record a container escape attempt."""
        self._buffer.append(
            MetricDatum(
                name="ContainerEscapeAttempt",
                value=1,
                unit="Count",
                dimensions={
                    "Technique": technique,
                    "Cluster": cluster,
                    "Blocked": str(blocked),
                },
            )
        )
        self._maybe_flush()

    def record_falco_alert(
        self,
        rule: str,
        priority: str,
        cluster: str,
    ) -> None:
        """Record a Falco alert."""
        self._buffer.append(
            MetricDatum(
                name="FalcoAlert",
                value=1,
                unit="Count",
                dimensions={
                    "Rule": rule,
                    "Priority": priority,
                    "Cluster": cluster,
                },
            )
        )
        self._maybe_flush()

    def record_ebpf_event(
        self,
        syscall: str,
        cluster: str,
    ) -> None:
        """Record an eBPF-captured event."""
        self._buffer.append(
            MetricDatum(
                name="EBPFEvent",
                value=1,
                unit="Count",
                dimensions={"Syscall": syscall, "Cluster": cluster},
            )
        )
        self._maybe_flush()

    # General Metrics

    def record_latency(self, metric_name: str, latency_ms: float) -> None:
        """Record a generic latency metric."""
        self._buffer.append(
            MetricDatum(
                name=metric_name,
                value=latency_ms,
                unit="Milliseconds",
            )
        )
        self._maybe_flush()

    def record_error(
        self,
        service: str,
        error_type: str,
    ) -> None:
        """Record an error occurrence."""
        self._buffer.append(
            MetricDatum(
                name="Error",
                value=1,
                unit="Count",
                dimensions={"Service": service, "ErrorType": error_type},
            )
        )
        self._maybe_flush()

    def time_operation(self, metric_name: str) -> MetricsTimer:
        """Return a context manager for timing an operation."""
        return MetricsTimer(metric_name, self)


# Singleton instance
_metrics_instance: Optional[RuntimeSecurityMetricsPublisher] = None


def get_runtime_security_metrics() -> RuntimeSecurityMetricsPublisher:
    """Get singleton metrics publisher instance."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = RuntimeSecurityMetricsPublisher()
    return _metrics_instance


def reset_runtime_security_metrics() -> None:
    """Reset metrics publisher singleton (for testing)."""
    global _metrics_instance
    if _metrics_instance is not None:
        _metrics_instance.flush()
    _metrics_instance = None
