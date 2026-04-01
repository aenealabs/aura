"""
Project Aura - Real-Time Monitoring Integration

Orchestrates the integration between anomaly detection and monitoring systems:
- CloudWatch Metrics for dashboards and alarms
- EventBridge for event-driven automation
- DynamoDB for audit trail and persistence
- ObservabilityService for Four Golden Signals

This service acts as the central hub that:
1. Registers callbacks with AnomalyDetectionService
2. Routes anomaly events to appropriate destinations
3. Provides unified statistics and health checks
4. Manages the lifecycle of monitoring components

Architecture:
    AnomalyDetectionService
           │
           │ on_anomaly()
           ▼
    RealTimeMonitoringIntegration
           │
           ├──► CloudWatchMetricsPublisher (metrics, alarms)
           ├──► EventBridgePublisher (event routing)
           ├──► AnomalyPersistenceService (audit trail)
           └──► ExternalToolConnectors (notifications)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class IntegrationMode(Enum):
    """Operating mode for the integration."""

    FULL = "full"  # All publishers enabled
    MINIMAL = "minimal"  # Only CloudWatch metrics
    MOCK = "mock"  # All mocked for testing


@dataclass
class IntegrationConfig:
    """Configuration for real-time monitoring integration."""

    # Publisher enablement
    enable_cloudwatch: bool = True
    enable_eventbridge: bool = True
    enable_persistence: bool = True
    enable_notifications: bool = True

    # Routing rules
    persist_all_severities: bool = True  # Persist INFO anomalies too
    notify_min_severity: str = "medium"  # Don't notify for LOW/INFO
    eventbridge_min_severity: str = "low"  # EventBridge for LOW and above

    # Performance
    batch_metrics: bool = True
    metrics_flush_interval: int = 60  # seconds

    @classmethod
    def from_environment(cls) -> "IntegrationConfig":
        """Load configuration from environment variables."""
        return cls(
            enable_cloudwatch=os.environ.get(
                "ENABLE_CLOUDWATCH_METRICS", "true"
            ).lower()
            == "true",
            enable_eventbridge=os.environ.get("ENABLE_EVENTBRIDGE", "true").lower()
            == "true",
            enable_persistence=os.environ.get(
                "ENABLE_ANOMALY_PERSISTENCE", "true"
            ).lower()
            == "true",
            enable_notifications=os.environ.get("ENABLE_NOTIFICATIONS", "true").lower()
            == "true",
            persist_all_severities=os.environ.get(
                "PERSIST_ALL_SEVERITIES", "true"
            ).lower()
            == "true",
            notify_min_severity=os.environ.get("NOTIFY_MIN_SEVERITY", "medium"),
            eventbridge_min_severity=os.environ.get("EVENTBRIDGE_MIN_SEVERITY", "low"),
        )


@dataclass
class IntegrationStats:
    """Statistics for the integration service."""

    anomalies_processed: int = 0
    cloudwatch_published: int = 0
    eventbridge_published: int = 0
    persistence_written: int = 0
    notifications_sent: int = 0
    errors: int = 0
    last_anomaly_time: datetime | None = None
    startup_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Severity Utilities
# =============================================================================


SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]


def severity_meets_threshold(severity: str, threshold: str) -> bool:
    """Check if severity meets or exceeds threshold."""
    try:
        severity_idx = SEVERITY_ORDER.index(severity.lower())
        threshold_idx = SEVERITY_ORDER.index(threshold.lower())
        return severity_idx >= threshold_idx
    except ValueError:
        # Unknown severity, default to True
        return True


# =============================================================================
# Real-Time Monitoring Integration
# =============================================================================


class RealTimeMonitoringIntegration:
    """
    Orchestrates real-time monitoring integration for anomaly detection.

    This service provides:
    - Unified callback registration with AnomalyDetectionService
    - Routing logic for different severity levels
    - Aggregated statistics across all publishers
    - Health checks for monitoring pipeline

    Usage:
        # Initialize with all components
        integration = RealTimeMonitoringIntegration()

        # Connect to anomaly detection
        integration.connect(anomaly_detector)

        # Or create with custom config
        config = IntegrationConfig(enable_notifications=False)
        integration = RealTimeMonitoringIntegration(config=config)
    """

    def __init__(
        self,
        config: IntegrationConfig | None = None,
        cloudwatch_publisher: Any | None = None,
        eventbridge_publisher: Any | None = None,
        persistence_service: Any | None = None,
    ):
        """
        Initialize the integration.

        Args:
            config: Integration configuration. Uses environment if not specified.
            cloudwatch_publisher: Optional pre-configured CloudWatch publisher
            eventbridge_publisher: Optional pre-configured EventBridge publisher
            persistence_service: Optional pre-configured persistence service
        """
        self.config = config or IntegrationConfig.from_environment()
        self.stats = IntegrationStats()

        # Lazy-loaded publishers
        self._cloudwatch_publisher = cloudwatch_publisher
        self._eventbridge_publisher = eventbridge_publisher
        self._persistence_service = persistence_service

        # Connected anomaly detector
        self._anomaly_detector: Any = None

        # Background tasks
        self._flush_task: asyncio.Task | None = None
        self._running = False

        logger.info(
            f"RealTimeMonitoringIntegration initialized: "
            f"cloudwatch={self.config.enable_cloudwatch}, "
            f"eventbridge={self.config.enable_eventbridge}, "
            f"persistence={self.config.enable_persistence}, "
            f"notifications={self.config.enable_notifications}"
        )

    # -------------------------------------------------------------------------
    # Publisher Access (Lazy Loading)
    # -------------------------------------------------------------------------

    @property
    def cloudwatch_publisher(self):
        """Get CloudWatch metrics publisher (lazy init)."""
        if self._cloudwatch_publisher is None and self.config.enable_cloudwatch:
            from src.services.cloudwatch_metrics_publisher import (
                get_cloudwatch_metrics_publisher,
            )

            self._cloudwatch_publisher = get_cloudwatch_metrics_publisher()
        return self._cloudwatch_publisher

    @property
    def eventbridge_publisher(self):
        """Get EventBridge publisher (lazy init)."""
        if self._eventbridge_publisher is None and self.config.enable_eventbridge:
            from src.services.eventbridge_publisher import get_eventbridge_publisher

            self._eventbridge_publisher = get_eventbridge_publisher()
        return self._eventbridge_publisher

    @property
    def persistence_service(self):
        """Get persistence service (lazy init)."""
        if self._persistence_service is None and self.config.enable_persistence:
            from src.services.anomaly_persistence_service import (
                get_anomaly_persistence_service,
            )

            self._persistence_service = get_anomaly_persistence_service()
        return self._persistence_service

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    def connect(self, anomaly_detector: Any) -> None:
        """
        Connect to an AnomalyDetectionService instance.

        Registers the integration callback to receive anomaly events.

        Args:
            anomaly_detector: AnomalyDetectionService instance
        """
        if self._anomaly_detector is not None:
            logger.warning("Already connected to an anomaly detector")
            return

        self._anomaly_detector = anomaly_detector
        anomaly_detector.on_anomaly(self._handle_anomaly)

        logger.info("Connected to AnomalyDetectionService")

    def disconnect(self) -> None:
        """Disconnect from the anomaly detector."""
        self._anomaly_detector = None
        logger.info("Disconnected from AnomalyDetectionService")

    async def start(self) -> None:
        """Start background tasks (e.g., metrics flushing)."""
        if self._running:
            return

        self._running = True

        # Start metrics flush task if batching enabled
        if self.config.batch_metrics and self.config.enable_cloudwatch:
            self._flush_task = asyncio.create_task(self._flush_loop())

        logger.info("RealTimeMonitoringIntegration started")

    async def stop(self) -> None:
        """Stop background tasks and flush pending data."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        if self.cloudwatch_publisher:
            await self.cloudwatch_publisher.flush()

        logger.info("RealTimeMonitoringIntegration stopped")

    # -------------------------------------------------------------------------
    # Anomaly Handling
    # -------------------------------------------------------------------------

    async def _handle_anomaly(self, anomaly: Any) -> None:
        """
        Handle an anomaly event from AnomalyDetectionService.

        Routes the anomaly to appropriate publishers based on configuration
        and severity thresholds.

        Args:
            anomaly: AnomalyEvent from AnomalyDetectionService
        """
        try:
            self.stats.anomalies_processed += 1
            self.stats.last_anomaly_time = datetime.now(timezone.utc)

            severity = anomaly.severity.value

            # Run all publishers concurrently
            tasks = []

            # 1. CloudWatch Metrics (always if enabled)
            if self.config.enable_cloudwatch and self.cloudwatch_publisher:
                tasks.append(self._publish_to_cloudwatch(anomaly))

            # 2. EventBridge (check severity threshold)
            if self.config.enable_eventbridge and self.eventbridge_publisher:
                if severity_meets_threshold(
                    severity, self.config.eventbridge_min_severity
                ):
                    tasks.append(self._publish_to_eventbridge(anomaly))

            # 3. Persistence (check if all severities or meets threshold)
            if self.config.enable_persistence and self.persistence_service:
                if self.config.persist_all_severities or severity_meets_threshold(
                    severity, "low"
                ):
                    tasks.append(self._persist_anomaly(anomaly))

            # 4. Notifications (check severity threshold)
            if self.config.enable_notifications:
                if severity_meets_threshold(severity, self.config.notify_min_severity):
                    tasks.append(self._send_notifications(anomaly))

            # Execute all tasks concurrently
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count errors
                for result in results:
                    if isinstance(result, Exception):
                        self.stats.errors += 1
                        logger.error(f"Publisher error: {result}")

        except Exception as e:
            self.stats.errors += 1
            logger.error(f"Error handling anomaly: {e}")

    async def _publish_to_cloudwatch(self, anomaly: Any) -> bool:
        """Publish anomaly to CloudWatch metrics."""
        try:
            success: bool = await self.cloudwatch_publisher.publish_anomaly(anomaly)
            if success:
                self.stats.cloudwatch_published += 1
            return bool(success)
        except Exception as e:
            logger.error(f"CloudWatch publish failed: {e}")
            raise

    async def _publish_to_eventbridge(self, anomaly: Any) -> bool:
        """Publish anomaly to EventBridge."""
        try:
            success: bool = await self.eventbridge_publisher.publish_anomaly_event(
                anomaly
            )
            if success:
                self.stats.eventbridge_published += 1
            return bool(success)
        except Exception as e:
            logger.error(f"EventBridge publish failed: {e}")
            raise

    async def _persist_anomaly(self, anomaly: Any) -> bool:
        """Persist anomaly to DynamoDB."""
        try:
            success: bool = await self.persistence_service.persist_anomaly(anomaly)
            if success:
                self.stats.persistence_written += 1
            return bool(success)
        except Exception as e:
            logger.error(f"Persistence failed: {e}")
            raise

    async def _send_notifications(self, anomaly: Any) -> bool:
        """Send notifications via external tool connectors."""
        try:
            # Import here to avoid circular imports
            from src.services.external_tool_connectors import (  # type: ignore[attr-defined]
                get_notification_router,
            )

            router = get_notification_router()
            success: bool = await router.route_notification(
                channel="all",
                message=f"[{anomaly.severity.value.upper()}] {anomaly.title}",
                title=f"Aura Anomaly: {anomaly.type.value}",
                metadata={
                    "anomaly_id": anomaly.id,
                    "type": anomaly.type.value,
                    "severity": anomaly.severity.value,
                    "source": anomaly.source,
                    "description": anomaly.description,
                },
            )
            if success:
                self.stats.notifications_sent += 1
            return bool(success)
        except ImportError:
            # External tool connectors not available
            logger.debug(
                "External tool connectors not available, skipping notifications"
            )
            return False
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            raise

    # -------------------------------------------------------------------------
    # Background Tasks
    # -------------------------------------------------------------------------

    async def _flush_loop(self) -> None:
        """Periodically flush batched metrics to CloudWatch."""
        while self._running:
            try:
                await asyncio.sleep(self.config.metrics_flush_interval)
                if self.cloudwatch_publisher:
                    await self.cloudwatch_publisher.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error: {e}")

    # -------------------------------------------------------------------------
    # Orchestrator & HITL Event Publishing
    # -------------------------------------------------------------------------

    async def publish_orchestrator_started(
        self,
        task_id: str,
        anomaly_id: str | None = None,
        task_type: str | None = None,
    ) -> None:
        """
        Publish orchestrator task started event.

        Args:
            task_id: MetaOrchestrator task ID
            anomaly_id: Related anomaly ID
            task_type: Type of task (investigate, remediate, etc.)
        """
        tasks = []

        if self.config.enable_cloudwatch and self.cloudwatch_publisher:
            tasks.append(
                self.cloudwatch_publisher.publish_orchestrator_event(
                    event_type="triggered",
                    task_id=task_id,
                )
            )

        if self.config.enable_eventbridge and self.eventbridge_publisher:
            from src.services.eventbridge_publisher import EventType

            tasks.append(
                self.eventbridge_publisher.publish_orchestrator_event(
                    event_type=EventType.ORCHESTRATOR_TASK_TRIGGERED,
                    task_id=task_id,
                    anomaly_id=anomaly_id,
                    task_type=task_type,
                )
            )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def publish_orchestrator_completed(
        self,
        task_id: str,
        anomaly_id: str | None = None,
        task_type: str | None = None,
        success: bool = True,
        duration_seconds: float | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        """
        Publish orchestrator task completed event.

        Args:
            task_id: MetaOrchestrator task ID
            anomaly_id: Related anomaly ID
            task_type: Type of task
            success: Whether task succeeded
            duration_seconds: Task duration
            result: Task result data
        """
        tasks = []

        if self.config.enable_cloudwatch and self.cloudwatch_publisher:
            tasks.append(
                self.cloudwatch_publisher.publish_orchestrator_event(
                    event_type="completed",
                    task_id=task_id,
                    success=success,
                    duration_seconds=duration_seconds,
                )
            )

        if self.config.enable_eventbridge and self.eventbridge_publisher:
            from src.services.eventbridge_publisher import EventType

            event_type = (
                EventType.ORCHESTRATOR_TASK_COMPLETED
                if success
                else EventType.ORCHESTRATOR_TASK_FAILED
            )
            tasks.append(
                self.eventbridge_publisher.publish_orchestrator_event(
                    event_type=event_type,
                    task_id=task_id,
                    anomaly_id=anomaly_id,
                    task_type=task_type,
                    success=success,
                    duration_seconds=duration_seconds,
                    result=result,
                )
            )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def publish_hitl_approval_required(
        self,
        approval_id: str,
        task_id: str | None = None,
        task_type: str | None = None,
    ) -> None:
        """
        Publish HITL approval required event.

        Args:
            approval_id: HITL approval ID
            task_id: Related orchestrator task ID
            task_type: Type of task requiring approval
        """
        tasks = []

        if self.config.enable_cloudwatch and self.cloudwatch_publisher:
            tasks.append(
                self.cloudwatch_publisher.publish_metric(
                    namespace="Aura/HITL",
                    metric_name="ApprovalRequests",
                    value=1.0,
                    dimensions={"TaskType": task_type or "unknown"},
                )
            )

        if self.config.enable_eventbridge and self.eventbridge_publisher:
            from src.services.eventbridge_publisher import EventType

            tasks.append(
                self.eventbridge_publisher.publish_hitl_event(
                    event_type=EventType.HITL_APPROVAL_REQUIRED,
                    approval_id=approval_id,
                    task_id=task_id,
                    task_type=task_type,
                )
            )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def publish_hitl_decision(
        self,
        approval_id: str,
        decision: str,
        reviewer: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """
        Publish HITL decision event.

        Args:
            approval_id: HITL approval ID
            decision: Decision made (approved, rejected, timeout)
            reviewer: Who made the decision
            task_id: Related orchestrator task ID
        """
        tasks = []

        if self.config.enable_cloudwatch and self.cloudwatch_publisher:
            tasks.append(
                self.cloudwatch_publisher.publish_metric(
                    namespace="Aura/HITL",
                    metric_name="DecisionsMade",
                    value=1.0,
                    dimensions={"Decision": decision},
                )
            )

        if self.config.enable_eventbridge and self.eventbridge_publisher:
            from src.services.eventbridge_publisher import EventType

            event_type = (
                EventType.HITL_TIMEOUT
                if decision == "timeout"
                else EventType.HITL_APPROVAL_COMPLETED
            )
            tasks.append(
                self.eventbridge_publisher.publish_hitl_event(
                    event_type=event_type,
                    approval_id=approval_id,
                    task_id=task_id,
                    decision=decision,
                    reviewer=reviewer,
                )
            )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # -------------------------------------------------------------------------
    # Statistics & Health
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics from all components."""
        stats = {
            "integration": {
                "anomalies_processed": self.stats.anomalies_processed,
                "cloudwatch_published": self.stats.cloudwatch_published,
                "eventbridge_published": self.stats.eventbridge_published,
                "persistence_written": self.stats.persistence_written,
                "notifications_sent": self.stats.notifications_sent,
                "errors": self.stats.errors,
                "last_anomaly_time": (
                    self.stats.last_anomaly_time.isoformat()
                    if self.stats.last_anomaly_time
                    else None
                ),
                "uptime_seconds": (
                    datetime.now(timezone.utc) - self.stats.startup_time
                ).total_seconds(),
            },
            "config": {
                "enable_cloudwatch": self.config.enable_cloudwatch,
                "enable_eventbridge": self.config.enable_eventbridge,
                "enable_persistence": self.config.enable_persistence,
                "enable_notifications": self.config.enable_notifications,
                "notify_min_severity": self.config.notify_min_severity,
            },
        }

        # Add component stats
        if self._cloudwatch_publisher:
            stats["cloudwatch"] = self._cloudwatch_publisher.get_stats()
        if self._eventbridge_publisher:
            stats["eventbridge"] = self._eventbridge_publisher.get_stats()
        if self._persistence_service:
            stats["persistence"] = self._persistence_service.get_stats()

        return stats

    def get_health(self) -> dict[str, Any]:
        """Get health status of all components."""
        health: dict[str, Any] = {
            "status": "healthy",
            "components": {},
        }

        # Check each component
        if self.config.enable_cloudwatch:
            cw_stats = (
                self._cloudwatch_publisher.get_stats()
                if self._cloudwatch_publisher
                else {}
            )
            health["components"]["cloudwatch"] = {
                "enabled": True,
                "mode": cw_stats.get("mode", "unknown"),
                "published": cw_stats.get("metrics_published", 0),
                "errors": cw_stats.get("publish_errors", 0),
            }

        if self.config.enable_eventbridge:
            eb_stats = (
                self._eventbridge_publisher.get_stats()
                if self._eventbridge_publisher
                else {}
            )
            health["components"]["eventbridge"] = {
                "enabled": True,
                "mode": eb_stats.get("mode", "unknown"),
                "published": eb_stats.get("events_published", 0),
                "errors": eb_stats.get("events_failed", 0),
            }

        if self.config.enable_persistence:
            db_stats = (
                self._persistence_service.get_stats()
                if self._persistence_service
                else {}
            )
            health["components"]["persistence"] = {
                "enabled": True,
                "mode": db_stats.get("mode", "unknown"),
                "written": db_stats.get("items_written", 0),
                "errors": db_stats.get("write_errors", 0),
            }

        # Determine overall health
        total_errors = sum(c.get("errors", 0) for c in health["components"].values())
        if total_errors > 10:
            health["status"] = "degraded"

        return health


# =============================================================================
# Factory Functions
# =============================================================================


_integration_instance: RealTimeMonitoringIntegration | None = None


def get_realtime_monitoring_integration() -> RealTimeMonitoringIntegration:
    """
    Get singleton real-time monitoring integration instance.

    Returns:
        RealTimeMonitoringIntegration instance
    """
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = RealTimeMonitoringIntegration()
    return _integration_instance


def create_realtime_monitoring_integration(
    config: IntegrationConfig | None = None,
    cloudwatch_publisher: Any = None,
    eventbridge_publisher: Any = None,
    persistence_service: Any = None,
) -> RealTimeMonitoringIntegration:
    """
    Create a new real-time monitoring integration instance.

    Args:
        config: Integration configuration
        cloudwatch_publisher: Optional pre-configured CloudWatch publisher
        eventbridge_publisher: Optional pre-configured EventBridge publisher
        persistence_service: Optional pre-configured persistence service

    Returns:
        New RealTimeMonitoringIntegration instance
    """
    return RealTimeMonitoringIntegration(
        config=config,
        cloudwatch_publisher=cloudwatch_publisher,
        eventbridge_publisher=eventbridge_publisher,
        persistence_service=persistence_service,
    )


# =============================================================================
# Convenience Function for Quick Setup
# =============================================================================


def setup_realtime_monitoring(anomaly_detector: Any) -> RealTimeMonitoringIntegration:
    """
    Quick setup for real-time monitoring integration.

    Creates the integration, connects to the anomaly detector, and starts
    background tasks.

    Usage:
        from src.services.anomaly_detection_service import AnomalyDetectionService
        from src.services.realtime_monitoring_integration import setup_realtime_monitoring

        detector = AnomalyDetectionService()
        integration = setup_realtime_monitoring(detector)

        # Integration is now active and will process all anomalies

    Args:
        anomaly_detector: AnomalyDetectionService instance

    Returns:
        Configured and connected RealTimeMonitoringIntegration
    """
    integration = get_realtime_monitoring_integration()
    integration.connect(anomaly_detector)

    # Start background tasks in event loop if available
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(integration.start())
    except RuntimeError:
        # No event loop running, start will be called later
        pass

    return integration
