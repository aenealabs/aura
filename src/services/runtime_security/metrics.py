"""
Project Aura - Cloud Runtime Security Metrics

CloudWatch metrics publisher for runtime security services.

Based on ADR-077: Cloud Runtime Security Integration
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .config import get_runtime_security_config

logger = logging.getLogger(__name__)


# CloudWatch PutMetricData accepts at most 1000 MetricDatum entries
# per request (and 40 KB per request). 500 is a conservative ceiling
# that fits well inside both limits even with rich dimension sets.
_CLOUDWATCH_BATCH_LIMIT = 500


def _build_boto3_cloudwatch_client() -> Any:
    """Construct the production boto3 CloudWatch client.

    Imported lazily so unit tests that don't touch the real emitter
    path (i.e. set ``cloudwatch_client=None`` and verify the buffer
    snapshot) never need to install boto3 or mock it. Production
    instantiates the publisher with the real client.
    """
    import boto3  # local import; not a runtime dep of the buffer-only path

    return boto3.client("cloudwatch")


def _datum_to_cloudwatch_payload(datum: "MetricDatum") -> dict[str, Any]:
    """Convert internal MetricDatum to CloudWatch PutMetricData shape."""
    payload: dict[str, Any] = {
        "MetricName": datum.name,
        "Value": datum.value,
        "Unit": datum.unit,
        "Timestamp": datum.timestamp,
    }
    if datum.dimensions:
        payload["Dimensions"] = [
            {"Name": k, "Value": str(v)} for k, v in datum.dimensions.items()
        ]
    return payload


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
    """Publishes CloudWatch metrics for runtime security services.

    Two modes:

    - **mock**: when the config disables metrics OR when the caller
      passes ``cloudwatch_client=None`` AND no environment client is
      available. Metrics buffer locally and are NOT shipped. Tests
      use this mode to assert on the buffer snapshot.
    - **emit**: when a boto3 CloudWatch client is configured (either
      injected or auto-constructed). ``flush()`` ships the buffered
      batch via ``PutMetricData``.
    """

    def __init__(self, cloudwatch_client: Optional[Any] = None):
        self._config = get_runtime_security_config()
        self._buffer: list[MetricDatum] = []
        # Mock mode trips when config explicitly disables metrics OR
        # when the caller did not provide a client AND we fail to
        # construct one. ``cloudwatch_client=None`` is a useful test
        # hook so callers can opt out of boto3 import.
        config_disabled = self._config.metrics.enabled is False
        self._cloudwatch: Optional[Any]
        if config_disabled:
            self._cloudwatch = None
            self._mock_mode = True
        else:
            self._cloudwatch = cloudwatch_client
            self._mock_mode = cloudwatch_client is None

    @property
    def namespace(self) -> str:
        """Get CloudWatch namespace."""
        return self._config.metrics.namespace

    def _publish_batch(self, metrics: list[MetricDatum]) -> None:
        """Ship a batch of metrics to CloudWatch via boto3.

        Splits oversized batches at the CloudWatch ``PutMetricData``
        request limit. Per-batch failures are logged and swallowed so
        a single bad batch does not lose subsequent batches; the
        worker keeps emitting whatever it can.
        """
        if self._mock_mode or not metrics:
            return

        if self._cloudwatch is None:
            # Defensive: caller flipped mock_mode False without a client.
            logger.warning(
                "RuntimeSecurityMetricsPublisher in emit mode with no client; "
                "dropping %d metrics",
                len(metrics),
            )
            return

        # Slice into <=1000-element batches at CloudWatch's request cap.
        for offset in range(0, len(metrics), _CLOUDWATCH_BATCH_LIMIT):
            batch = metrics[offset : offset + _CLOUDWATCH_BATCH_LIMIT]
            payload = [_datum_to_cloudwatch_payload(d) for d in batch]
            try:
                self._cloudwatch.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=payload,
                )
            except Exception as exc:  # noqa: BLE001 - telemetry is best-effort
                logger.error(
                    "Failed to publish runtime-security metrics batch " "(size=%d): %s",
                    len(batch),
                    exc,
                )

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
