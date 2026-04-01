"""
Project Aura - CloudWatch Metrics Publisher

Publishes anomaly detection metrics and events to AWS CloudWatch for:
- Real-time dashboards and visualization
- CloudWatch Alarms for automated alerting
- Integration with AWS observability ecosystem

Metrics Published:
- Aura/Anomalies: Detection counts by type and severity
- Aura/Security: CVE detections, security events
- Aura/Orchestrator: Task triggers, success rates
- Aura/Notifications: Delivery status by channel

Integration:
- Subscribes to AnomalyDetectionService via on_anomaly callback
- Batches metrics for efficient API usage (max 1000 metrics/request)
- Supports both synchronous and asynchronous publishing
"""

import asyncio
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class MetricNamespace(Enum):
    """CloudWatch metric namespaces for Aura."""

    ANOMALIES = "Aura/Anomalies"
    SECURITY = "Aura/Security"
    ORCHESTRATOR = "Aura/Orchestrator"
    NOTIFICATIONS = "Aura/Notifications"
    OBSERVABILITY = "Aura/Observability"
    AUTONOMY = "Aura/Autonomy"
    GPU_SCHEDULER = "Aura/GPUScheduler"
    CONSTITUTIONAL_AI = "Aura/ConstitutionalAI"


class PublisherMode(Enum):
    """Operating mode for the publisher."""

    AWS = "aws"  # Real CloudWatch API calls
    MOCK = "mock"  # Local testing without AWS


@dataclass
class MetricDatum:
    """Single metric data point for CloudWatch."""

    metric_name: str
    value: float
    unit: str = "Count"
    dimensions: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    storage_resolution: int = 60  # Standard resolution (1 minute)

    def to_cloudwatch_format(self) -> dict[str, Any]:
        """Convert to CloudWatch PutMetricData format."""
        datum = {
            "MetricName": self.metric_name,
            "Value": self.value,
            "Unit": self.unit,
            "Timestamp": self.timestamp,
            "StorageResolution": self.storage_resolution,
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
    metrics_failed: int = 0
    batches_sent: int = 0
    last_publish_time: datetime | None = None
    errors: list[str] = field(default_factory=list)


# =============================================================================
# CloudWatch Metrics Publisher
# =============================================================================


class CloudWatchMetricsPublisher:
    """
    Publishes metrics to AWS CloudWatch.

    Supports:
    - Anomaly event metrics (type, severity, status)
    - Security metrics (CVEs, vulnerabilities)
    - Orchestrator metrics (task triggers, outcomes)
    - Notification delivery metrics

    Usage:
        publisher = CloudWatchMetricsPublisher()

        # Publish single metric
        await publisher.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="DetectionCount",
            value=1.0,
            dimensions={"Type": "latency_spike", "Severity": "high"}
        )

        # Publish anomaly event (registers as callback with AnomalyDetectionService)
        await publisher.publish_anomaly(anomaly_event)

        # Flush any buffered metrics
        await publisher.flush()
    """

    # Maximum metrics per PutMetricData call
    MAX_METRICS_PER_BATCH = 1000

    # Default dimensions added to all metrics
    DEFAULT_DIMENSIONS = {
        "Environment": os.environ.get("AURA_ENV", "development"),
        "Service": "aura",
    }

    def __init__(
        self,
        mode: PublisherMode | None = None,
        region: str | None = None,
        buffer_size: int = 100,
        auto_flush_interval: int = 60,
    ):
        """
        Initialize CloudWatch metrics publisher.

        Args:
            mode: Operating mode (AWS or MOCK). Auto-detected if not specified.
            region: AWS region. Uses AWS_REGION env var if not specified.
            buffer_size: Number of metrics to buffer before auto-flush.
            auto_flush_interval: Seconds between auto-flush (0 to disable).
        """
        self.mode = mode or self._detect_mode()
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.buffer_size = buffer_size
        self.auto_flush_interval = auto_flush_interval

        # Metrics buffer (namespace -> list of MetricDatum)
        self._buffer: dict[str, list[MetricDatum]] = defaultdict(list)
        self._buffer_lock = asyncio.Lock()

        # Statistics
        self.stats = PublisherStats()

        # CloudWatch client (lazy initialization)
        self._client: Any = None

        # Mock storage for testing
        self._mock_metrics: list[dict[str, Any]] = []

        # Background flush task
        self._flush_task: asyncio.Task | None = None
        self._running = False

        logger.info(
            f"CloudWatchMetricsPublisher initialized: mode={self.mode.value}, "
            f"region={self.region}, buffer_size={buffer_size}"
        )

    def _detect_mode(self) -> PublisherMode:
        """Auto-detect operating mode based on environment."""
        # Check for explicit mode setting
        mode_env = os.environ.get("CLOUDWATCH_MODE", "").lower()
        if mode_env == "mock":
            return PublisherMode.MOCK
        if mode_env == "aws":
            return PublisherMode.AWS

        # Check for AWS credentials indicators
        if any(
            [
                os.environ.get("AWS_EXECUTION_ENV"),  # Lambda/ECS
                os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"),  # ECS/EKS
                os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE"),  # IRSA
            ]
        ):
            return PublisherMode.AWS

        # Default to mock for local development
        return PublisherMode.MOCK

    @property
    def client(self):
        """Lazy-initialize CloudWatch client."""
        if self._client is None:
            if self.mode == PublisherMode.AWS:
                self._client = boto3.client("cloudwatch", region_name=self.region)
            else:
                self._client = None
        return self._client

    # -------------------------------------------------------------------------
    # Core Publishing Methods
    # -------------------------------------------------------------------------

    async def publish_metric(
        self,
        namespace: MetricNamespace | str,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
        timestamp: datetime | None = None,
        immediate: bool = False,
    ) -> bool:
        """
        Publish a single metric to CloudWatch.

        Args:
            namespace: CloudWatch namespace (MetricNamespace enum or string)
            metric_name: Name of the metric
            value: Metric value
            unit: CloudWatch unit (Count, Seconds, Percent, etc.)
            dimensions: Additional dimensions (merged with defaults)
            timestamp: Metric timestamp (defaults to now)
            immediate: If True, flush immediately without buffering

        Returns:
            True if metric was published/buffered successfully
        """
        # Normalize namespace to string
        namespace_str = (
            namespace.value if isinstance(namespace, MetricNamespace) else namespace
        )

        # Merge dimensions with defaults
        all_dimensions = {**self.DEFAULT_DIMENSIONS}
        if dimensions:
            all_dimensions.update(dimensions)

        datum = MetricDatum(
            metric_name=metric_name,
            value=value,
            unit=unit,
            dimensions=all_dimensions,
            timestamp=timestamp or datetime.now(timezone.utc),
        )

        if immediate:
            return await self._publish_batch(namespace_str, [datum])

        # Add to buffer
        async with self._buffer_lock:
            self._buffer[namespace_str].append(datum)

            # Auto-flush if buffer is full
            if len(self._buffer[namespace_str]) >= self.buffer_size:
                metrics = self._buffer[namespace_str]
                self._buffer[namespace_str] = []
                # Release lock before network call
                asyncio.create_task(self._publish_batch(namespace_str, metrics))

        return True

    async def publish_anomaly(self, anomaly: Any) -> bool:
        """
        Publish metrics for an anomaly event.

        This method is designed to be used as a callback for AnomalyDetectionService:
            detector.on_anomaly(publisher.publish_anomaly)

        Publishes multiple metrics:
        - DetectionCount: Count of anomalies by type
        - SeverityCount: Count by severity level
        - StatusTransition: Status changes

        Args:
            anomaly: AnomalyEvent from AnomalyDetectionService

        Returns:
            True if all metrics were published successfully
        """
        # Import here to avoid circular imports
        from src.services.anomaly_detection_service import (
            AnomalyEvent,
            AnomalySeverity,
            AnomalyType,
        )

        if not isinstance(anomaly, AnomalyEvent):
            logger.warning(f"Invalid anomaly type: {type(anomaly)}")
            return False

        timestamp = anomaly.timestamp

        # Metric 1: Detection count by type
        await self.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="DetectionCount",
            value=1.0,
            dimensions={
                "Type": anomaly.type.value,
                "Source": anomaly.source,
            },
            timestamp=timestamp,
        )

        # Metric 2: Severity count
        await self.publish_metric(
            namespace=MetricNamespace.ANOMALIES,
            metric_name="SeverityCount",
            value=1.0,
            dimensions={
                "Severity": anomaly.severity.value,
            },
            timestamp=timestamp,
        )

        # Metric 3: CVE-specific metrics (if applicable)
        if anomaly.type in (AnomalyType.NEW_CVE, AnomalyType.KNOWN_EXPLOITATION):
            await self.publish_metric(
                namespace=MetricNamespace.SECURITY,
                metric_name="CVEDetected",
                value=1.0,
                dimensions={
                    "Severity": anomaly.severity.value,
                    "Exploited": (
                        "true"
                        if anomaly.type == AnomalyType.KNOWN_EXPLOITATION
                        else "false"
                    ),
                },
                timestamp=timestamp,
            )

        # Metric 4: Critical/High severity alert (for alarming)
        if anomaly.severity in (AnomalySeverity.CRITICAL, AnomalySeverity.HIGH):
            await self.publish_metric(
                namespace=MetricNamespace.ANOMALIES,
                metric_name="HighSeverityAlert",
                value=1.0,
                dimensions={
                    "Type": anomaly.type.value,
                    "Severity": anomaly.severity.value,
                },
                timestamp=timestamp,
                immediate=True,  # Flush immediately for critical alerts
            )

        logger.debug(
            f"Published anomaly metrics: {anomaly.type.value} ({anomaly.severity.value})"
        )
        return True

    async def publish_orchestrator_event(
        self,
        event_type: str,
        task_id: str | None = None,
        success: bool = True,
        duration_seconds: float | None = None,
    ) -> bool:
        """
        Publish orchestrator execution metrics.

        Args:
            event_type: Type of event (task_triggered, task_completed, task_failed)
            task_id: Orchestrator task ID
            success: Whether the operation succeeded
            duration_seconds: Duration of the operation

        Returns:
            True if metrics were published successfully
        """
        timestamp = datetime.now(timezone.utc)

        # Event count
        await self.publish_metric(
            namespace=MetricNamespace.ORCHESTRATOR,
            metric_name="EventCount",
            value=1.0,
            dimensions={
                "EventType": event_type,
                "Success": "true" if success else "false",
            },
            timestamp=timestamp,
        )

        # Duration (if provided)
        if duration_seconds is not None:
            await self.publish_metric(
                namespace=MetricNamespace.ORCHESTRATOR,
                metric_name="TaskDuration",
                value=duration_seconds,
                unit="Seconds",
                dimensions={"EventType": event_type},
                timestamp=timestamp,
            )

        return True

    async def publish_notification_event(
        self,
        channel: str,
        success: bool,
        latency_ms: float | None = None,
    ) -> bool:
        """
        Publish notification delivery metrics.

        Args:
            channel: Notification channel (slack, jira, pagerduty)
            success: Whether delivery succeeded
            latency_ms: Delivery latency in milliseconds

        Returns:
            True if metrics were published successfully
        """
        timestamp = datetime.now(timezone.utc)

        # Delivery count
        await self.publish_metric(
            namespace=MetricNamespace.NOTIFICATIONS,
            metric_name="DeliveryCount",
            value=1.0,
            dimensions={
                "Channel": channel,
                "Success": "true" if success else "false",
            },
            timestamp=timestamp,
        )

        # Latency (if provided)
        if latency_ms is not None:
            await self.publish_metric(
                namespace=MetricNamespace.NOTIFICATIONS,
                metric_name="DeliveryLatency",
                value=latency_ms,
                unit="Milliseconds",
                dimensions={"Channel": channel},
                timestamp=timestamp,
            )

        return True

    async def publish_observability_metrics(
        self,
        error_rate: float,
        latency_p95: float,
        request_count: int,
        saturation: float,
    ) -> bool:
        """
        Publish Four Golden Signals metrics from ObservabilityService.

        Args:
            error_rate: Error rate (0.0 - 1.0)
            latency_p95: P95 latency in milliseconds
            request_count: Total request count
            saturation: Resource saturation (0.0 - 1.0)

        Returns:
            True if metrics were published successfully
        """
        timestamp = datetime.now(timezone.utc)

        await self.publish_metric(
            namespace=MetricNamespace.OBSERVABILITY,
            metric_name="ErrorRate",
            value=error_rate * 100,  # Convert to percentage
            unit="Percent",
            timestamp=timestamp,
        )

        await self.publish_metric(
            namespace=MetricNamespace.OBSERVABILITY,
            metric_name="LatencyP95",
            value=latency_p95,
            unit="Milliseconds",
            timestamp=timestamp,
        )

        await self.publish_metric(
            namespace=MetricNamespace.OBSERVABILITY,
            metric_name="RequestCount",
            value=float(request_count),
            unit="Count",
            timestamp=timestamp,
        )

        await self.publish_metric(
            namespace=MetricNamespace.OBSERVABILITY,
            metric_name="ResourceSaturation",
            value=saturation * 100,  # Convert to percentage
            unit="Percent",
            timestamp=timestamp,
        )

        return True

    async def publish_autonomy_event(
        self,
        event_type: str,
        organization_id: str,
        policy_id: str | None = None,
        user: str | None = None,
        hitl_enabled: bool | None = None,
        autonomy_level: str | None = None,
        severity: str | None = None,
        operation: str | None = None,
        auto_approved: bool = False,
    ) -> bool:
        """
        Publish autonomy-related metrics for compliance dashboards.

        Event types:
        - hitl_toggled: HITL was enabled/disabled
        - policy_created: New autonomy policy created
        - policy_updated: Existing policy modified
        - policy_deleted: Policy deactivated
        - hitl_check: HITL requirement checked for an action
        - auto_approval: Action was auto-approved without HITL

        Args:
            event_type: Type of autonomy event
            organization_id: Organization identifier
            policy_id: Policy identifier (optional)
            user: User who triggered the event (optional)
            hitl_enabled: New HITL state (for toggle events)
            autonomy_level: Autonomy level (for check events)
            severity: Severity level (for check events)
            operation: Operation type (for check events)
            auto_approved: Whether action was auto-approved

        Returns:
            True if metrics were published successfully
        """
        timestamp = datetime.now(timezone.utc)

        # Core event metric
        dimensions = {
            "EventType": event_type,
            "OrganizationId": organization_id,
        }
        if policy_id:
            dimensions["PolicyId"] = policy_id

        await self.publish_metric(
            namespace=MetricNamespace.AUTONOMY,
            metric_name="EventCount",
            value=1.0,
            dimensions=dimensions,
            timestamp=timestamp,
        )

        # HITL toggle metrics (for compliance dashboards)
        if event_type == "hitl_toggled" and hitl_enabled is not None:
            await self.publish_metric(
                namespace=MetricNamespace.AUTONOMY,
                metric_name="HITLToggle",
                value=1.0,
                dimensions={
                    "OrganizationId": organization_id,
                    "HITLEnabled": "true" if hitl_enabled else "false",
                    "User": user or "unknown",
                },
                timestamp=timestamp,
                immediate=True,  # Important for audit
            )

            # Track HITL disabled events separately for alerting
            if not hitl_enabled:
                await self.publish_metric(
                    namespace=MetricNamespace.AUTONOMY,
                    metric_name="HITLDisabledCount",
                    value=1.0,
                    dimensions={
                        "OrganizationId": organization_id,
                    },
                    timestamp=timestamp,
                    immediate=True,
                )

        # Auto-approval metrics (for monitoring bypassed HITL)
        if auto_approved:
            await self.publish_metric(
                namespace=MetricNamespace.AUTONOMY,
                metric_name="AutoApprovalCount",
                value=1.0,
                dimensions={
                    "OrganizationId": organization_id,
                    "Severity": severity or "unknown",
                    "Operation": operation or "unknown",
                    "AutonomyLevel": autonomy_level or "unknown",
                },
                timestamp=timestamp,
            )

        logger.debug(
            f"Published autonomy event: {event_type} for org {organization_id}"
        )
        return True

    # -------------------------------------------------------------------------
    # Buffer Management
    # -------------------------------------------------------------------------

    async def flush(self) -> bool:
        """
        Flush all buffered metrics to CloudWatch.

        Returns:
            True if all metrics were flushed successfully
        """
        async with self._buffer_lock:
            all_success = True
            for namespace, metrics in self._buffer.items():
                if metrics:
                    success = await self._publish_batch(namespace, metrics)
                    all_success = all_success and success
            self._buffer.clear()
        return all_success

    async def _publish_batch(self, namespace: str, metrics: list[MetricDatum]) -> bool:
        """
        Publish a batch of metrics to CloudWatch.

        Args:
            namespace: CloudWatch namespace
            metrics: List of metrics to publish

        Returns:
            True if batch was published successfully
        """
        if not metrics:
            return True

        if self.mode == PublisherMode.MOCK:
            return self._mock_publish(namespace, metrics)

        # Split into chunks of MAX_METRICS_PER_BATCH
        for i in range(0, len(metrics), self.MAX_METRICS_PER_BATCH):
            chunk = metrics[i : i + self.MAX_METRICS_PER_BATCH]
            success = await self._put_metric_data(namespace, chunk)
            if not success:
                return False

        return True

    async def _put_metric_data(
        self, namespace: str, metrics: list[MetricDatum]
    ) -> bool:
        """
        Call CloudWatch PutMetricData API.

        Args:
            namespace: CloudWatch namespace
            metrics: List of metrics to publish

        Returns:
            True if API call succeeded
        """
        try:
            metric_data = [m.to_cloudwatch_format() for m in metrics]

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.put_metric_data(
                    Namespace=namespace, MetricData=metric_data
                ),
            )

            self.stats.metrics_published += len(metrics)
            self.stats.batches_sent += 1
            self.stats.last_publish_time = datetime.now(timezone.utc)

            logger.debug(f"Published {len(metrics)} metrics to {namespace}")
            return True

        except ClientError as e:
            error_msg = f"CloudWatch PutMetricData failed: {e}"
            logger.error(error_msg)
            self.stats.metrics_failed += len(metrics)
            self.stats.errors.append(error_msg)
            return False

    def _mock_publish(self, namespace: str, metrics: list[MetricDatum]) -> bool:
        """
        Mock publish for testing.

        Args:
            namespace: CloudWatch namespace
            metrics: List of metrics to publish

        Returns:
            Always True in mock mode
        """
        for m in metrics:
            self._mock_metrics.append(
                {
                    "namespace": namespace,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "unit": m.unit,
                    "dimensions": m.dimensions,
                    "timestamp": m.timestamp.isoformat(),
                }
            )
        self.stats.metrics_published += len(metrics)
        self.stats.batches_sent += 1
        self.stats.last_publish_time = datetime.now(timezone.utc)

        logger.debug(f"[MOCK] Published {len(metrics)} metrics to {namespace}")
        return True

    # -------------------------------------------------------------------------
    # Background Processing
    # -------------------------------------------------------------------------

    async def start(self) -> None:
        """Start background flush task."""
        if self._running:
            return

        self._running = True
        if self.auto_flush_interval > 0:
            self._flush_task = asyncio.create_task(self._background_flush())
            logger.info(
                f"Started background flush task (interval: {self.auto_flush_interval}s)"
            )

    async def stop(self) -> None:
        """Stop background flush task and flush remaining metrics."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Final flush
        await self.flush()
        logger.info("CloudWatch metrics publisher stopped")

    async def _background_flush(self) -> None:
        """Background task to periodically flush metrics."""
        while self._running:
            try:
                await asyncio.sleep(self.auto_flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background flush error: {e}")

    # -------------------------------------------------------------------------
    # Statistics & Health
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get publisher statistics."""
        return {
            "mode": self.mode.value,
            "region": self.region,
            "metrics_published": self.stats.metrics_published,
            "metrics_failed": self.stats.metrics_failed,
            "batches_sent": self.stats.batches_sent,
            "last_publish_time": (
                self.stats.last_publish_time.isoformat()
                if self.stats.last_publish_time
                else None
            ),
            "buffer_sizes": {ns: len(m) for ns, m in self._buffer.items()},
            "recent_errors": self.stats.errors[-5:],  # Last 5 errors
        }

    def get_mock_metrics(self) -> list[dict[str, Any]]:
        """Get mock-published metrics (for testing)."""
        return self._mock_metrics.copy()

    def clear_mock_metrics(self) -> None:
        """Clear mock metrics (for testing)."""
        self._mock_metrics.clear()


# =============================================================================
# Factory Function
# =============================================================================


_publisher_instance: CloudWatchMetricsPublisher | None = None


def get_metrics_publisher() -> CloudWatchMetricsPublisher:
    """
    Get singleton CloudWatch metrics publisher instance.

    Returns:
        CloudWatchMetricsPublisher instance
    """
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = CloudWatchMetricsPublisher()
    return _publisher_instance


def create_metrics_publisher(
    mode: PublisherMode | None = None,
    region: str | None = None,
) -> CloudWatchMetricsPublisher:
    """
    Create a new CloudWatch metrics publisher instance.

    Args:
        mode: Operating mode (AWS or MOCK)
        region: AWS region

    Returns:
        New CloudWatchMetricsPublisher instance
    """
    return CloudWatchMetricsPublisher(mode=mode, region=region)


# Alias for consistency with other services
get_cloudwatch_metrics_publisher = get_metrics_publisher
