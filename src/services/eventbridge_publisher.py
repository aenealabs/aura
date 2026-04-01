"""
Project Aura - EventBridge Event Publisher

Publishes anomaly events to AWS EventBridge for:
- Event-driven automation (Lambda, Step Functions)
- Cross-service event routing
- Audit trail integration
- Third-party integrations via EventBridge rules

Event Types:
- aura.anomaly.detected: New anomaly detected
- aura.anomaly.status_changed: Anomaly status transition
- aura.security.cve_detected: New CVE found
- aura.security.threat_detected: Active threat intelligence
- aura.orchestrator.task_triggered: MetaOrchestrator started
- aura.orchestrator.task_completed: MetaOrchestrator finished
- aura.agent.task_dispatched: Task dispatched to agent queue
- aura.agent.task_completed: Agent finished task successfully
- aura.agent.task_failed: Agent task failed after retries
- aura.hitl.approval_required: Human review needed
- aura.hitl.approval_completed: Human decision made

Integration:
- Subscribes to AnomalyDetectionService via on_anomaly callback
- Can be used standalone for custom event publishing
- Supports both synchronous and asynchronous publishing
"""

import asyncio
import json
import logging
import os
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


class EventType(Enum):
    """EventBridge event types for Aura."""

    # Anomaly events
    ANOMALY_DETECTED = "aura.anomaly.detected"
    ANOMALY_STATUS_CHANGED = "aura.anomaly.status_changed"
    ANOMALY_RESOLVED = "aura.anomaly.resolved"

    # Security events
    CVE_DETECTED = "aura.security.cve_detected"
    THREAT_DETECTED = "aura.security.threat_detected"
    VULNERABILITY_FOUND = "aura.security.vulnerability_found"

    # Orchestrator events
    ORCHESTRATOR_TASK_TRIGGERED = "aura.orchestrator.task_triggered"
    ORCHESTRATOR_TASK_COMPLETED = "aura.orchestrator.task_completed"
    ORCHESTRATOR_TASK_FAILED = "aura.orchestrator.task_failed"

    # Agent task events (Issue #19 - Microservices Messaging)
    AGENT_TASK_DISPATCHED = "aura.agent.task_dispatched"
    AGENT_TASK_COMPLETED = "aura.agent.task_completed"
    AGENT_TASK_FAILED = "aura.agent.task_failed"
    AGENT_STATUS_UPDATE = "aura.agent.status_update"

    # HITL events
    HITL_APPROVAL_REQUIRED = "aura.hitl.approval_required"
    HITL_APPROVAL_COMPLETED = "aura.hitl.approval_completed"
    HITL_TIMEOUT = "aura.hitl.timeout"

    # Notification events
    NOTIFICATION_SENT = "aura.notification.sent"
    NOTIFICATION_FAILED = "aura.notification.failed"


class PublisherMode(Enum):
    """Operating mode for the publisher."""

    AWS = "aws"  # Real EventBridge API calls
    MOCK = "mock"  # Local testing without AWS


@dataclass
class EventDetail:
    """Event detail payload for EventBridge."""

    event_type: str
    source_service: str = "anomaly-detection"
    version: str = "1.0"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    environment: str = field(
        default_factory=lambda: os.environ.get("AURA_ENV", "development")
    )
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for EventBridge."""
        return {
            "eventType": self.event_type,
            "sourceService": self.source_service,
            "version": self.version,
            "timestamp": self.timestamp,
            "environment": self.environment,
            "data": self.data,
        }


@dataclass
class PublisherStats:
    """Statistics for the event publisher."""

    events_published: int = 0
    events_failed: int = 0
    last_publish_time: datetime | None = None
    errors: list[str] = field(default_factory=list)


# =============================================================================
# EventBridge Publisher
# =============================================================================


class EventBridgePublisher:
    """
    Publishes events to AWS EventBridge.

    Enables event-driven architecture for:
    - Triggering Lambda functions on anomalies
    - Starting Step Functions workflows
    - Routing events to SNS/SQS for notifications
    - Cross-account event sharing

    Usage:
        publisher = EventBridgePublisher()

        # Publish anomaly event
        await publisher.publish_anomaly_event(anomaly)

        # Publish custom event
        await publisher.publish_event(
            event_type=EventType.HITL_APPROVAL_REQUIRED,
            detail={"approval_id": "123", "task_type": "patch"}
        )
    """

    # Event source for all Aura events
    EVENT_SOURCE = "aura"

    def __init__(
        self,
        mode: PublisherMode | None = None,
        region: str | None = None,
        event_bus_name: str | None = None,
    ):
        """
        Initialize EventBridge publisher.

        Args:
            mode: Operating mode (AWS or MOCK). Auto-detected if not specified.
            region: AWS region. Uses AWS_REGION env var if not specified.
            event_bus_name: EventBridge event bus name. Auto-detected from
                            PROJECT_NAME/ENVIRONMENT if not specified.
        """
        self.mode = mode or self._detect_mode()
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.event_bus_name = event_bus_name or self._get_event_bus_name()

        # Statistics
        self.stats = PublisherStats()

        # EventBridge client (lazy initialization)
        self._client: Any = None

        # Mock storage for testing
        self._mock_events: list[dict[str, Any]] = []

        logger.info(
            f"EventBridgePublisher initialized: mode={self.mode.value}, "
            f"region={self.region}, event_bus={self.event_bus_name}"
        )

    def _detect_mode(self) -> PublisherMode:
        """Auto-detect operating mode based on environment."""
        # Check for explicit mode setting
        mode_env = os.environ.get("EVENTBRIDGE_MODE", "").lower()
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

    def _get_event_bus_name(self) -> str:
        """
        Get EventBridge event bus name from environment.

        Priority:
        1. AURA_EVENT_BUS environment variable (explicit override)
        2. Construct from PROJECT_NAME and ENVIRONMENT: {project}-anomaly-events-{env}
        3. Fall back to 'default' event bus

        Returns:
            Event bus name
        """
        # Check for explicit override
        explicit_bus = os.environ.get("AURA_EVENT_BUS")
        if explicit_bus:
            return explicit_bus

        # Try to construct from project/environment
        project = os.environ.get("PROJECT_NAME", "aura")
        environment = os.environ.get("ENVIRONMENT", "dev")

        # Construct bus name matching CloudFormation pattern
        return f"{project}-anomaly-events-{environment}"

    @property
    def client(self):
        """Lazy-initialize EventBridge client."""
        if self._client is None:
            if self.mode == PublisherMode.AWS:
                self._client = boto3.client("events", region_name=self.region)
            else:
                self._client = None
        return self._client

    # -------------------------------------------------------------------------
    # Core Publishing Methods
    # -------------------------------------------------------------------------

    async def publish_event(
        self,
        event_type: EventType,
        detail: dict[str, Any],
        source_service: str = "anomaly-detection",
    ) -> bool:
        """
        Publish a single event to EventBridge.

        Args:
            event_type: Type of event
            detail: Event detail payload
            source_service: Source service name

        Returns:
            True if event was published successfully
        """
        event_detail = EventDetail(
            event_type=event_type.value,
            source_service=source_service,
            data=detail,
        )

        return await self._put_event(event_type.value, event_detail)

    async def publish_anomaly_event(self, anomaly: Any) -> bool:
        """
        Publish an anomaly event to EventBridge.

        This method is designed to be used as a callback for AnomalyDetectionService:
            detector.on_anomaly(publisher.publish_anomaly_event)

        Args:
            anomaly: AnomalyEvent from AnomalyDetectionService

        Returns:
            True if event was published successfully
        """
        # Import here to avoid circular imports
        from src.services.anomaly_detection_service import AnomalyEvent, AnomalyType

        if not isinstance(anomaly, AnomalyEvent):
            logger.warning(f"Invalid anomaly type: {type(anomaly)}")
            return False

        # Determine event type based on anomaly type
        if anomaly.type in (AnomalyType.NEW_CVE, AnomalyType.KNOWN_EXPLOITATION):
            event_type = EventType.CVE_DETECTED
        elif anomaly.type == AnomalyType.SECURITY_EVENT:
            event_type = EventType.THREAT_DETECTED
        elif anomaly.type == AnomalyType.DEPENDENCY_VULNERABILITY:
            event_type = EventType.VULNERABILITY_FOUND
        else:
            event_type = EventType.ANOMALY_DETECTED

        # Build event detail
        detail: dict[str, Any] = {
            "anomalyId": anomaly.id,
            "type": anomaly.type.value,
            "severity": anomaly.severity.value,
            "status": anomaly.status.value,
            "title": anomaly.title,
            "description": anomaly.description,
            "source": anomaly.source,
            "timestamp": anomaly.timestamp.isoformat(),
            "dedupKey": anomaly.dedup_key,
            "affectedComponents": anomaly.affected_components,
            "recommendedAction": anomaly.recommended_action,
        }

        # Add CVE-specific fields
        if anomaly.cve_id:
            detail["cveId"] = anomaly.cve_id

        # Add orchestrator/HITL references
        if anomaly.orchestrator_task_id:
            detail["orchestratorTaskId"] = anomaly.orchestrator_task_id
        if anomaly.hitl_approval_id:
            detail["hitlApprovalId"] = anomaly.hitl_approval_id

        # Add metadata (already dict[str, Any] from AnomalyEvent)
        if anomaly.metadata:
            detail["metadata"] = anomaly.metadata

        success = await self.publish_event(event_type, detail)

        if success:
            logger.debug(
                f"Published anomaly event: {event_type.value} "
                f"({anomaly.type.value}, {anomaly.severity.value})"
            )

        return success

    async def publish_status_change(
        self,
        anomaly_id: str,
        old_status: str,
        new_status: str,
        changed_by: str = "system",
    ) -> bool:
        """
        Publish anomaly status change event.

        Args:
            anomaly_id: ID of the anomaly
            old_status: Previous status
            new_status: New status
            changed_by: Who/what changed the status

        Returns:
            True if event was published successfully
        """
        detail = {
            "anomalyId": anomaly_id,
            "oldStatus": old_status,
            "newStatus": new_status,
            "changedBy": changed_by,
        }

        return await self.publish_event(EventType.ANOMALY_STATUS_CHANGED, detail)

    async def publish_orchestrator_event(
        self,
        event_type: EventType,
        task_id: str,
        anomaly_id: str | None = None,
        task_type: str | None = None,
        success: bool = True,
        duration_seconds: float | None = None,
        result: dict[str, Any] | None = None,
    ) -> bool:
        """
        Publish orchestrator task event.

        Args:
            event_type: ORCHESTRATOR_TASK_TRIGGERED/COMPLETED/FAILED
            task_id: Orchestrator task ID
            anomaly_id: Related anomaly ID (if applicable)
            task_type: Type of task (investigate, remediate, etc.)
            success: Whether the task succeeded (for completed events)
            duration_seconds: Task duration
            result: Task result data

        Returns:
            True if event was published successfully
        """
        detail: dict[str, Any] = {
            "taskId": task_id,
            "taskType": task_type,
            "success": success,
        }

        if anomaly_id:
            detail["anomalyId"] = anomaly_id
        if duration_seconds is not None:
            detail["durationSeconds"] = duration_seconds
        if result:
            detail["result"] = result

        return await self.publish_event(
            event_type, detail, source_service="meta-orchestrator"
        )

    async def publish_hitl_event(
        self,
        event_type: EventType,
        approval_id: str,
        task_id: str | None = None,
        task_type: str | None = None,
        decision: str | None = None,
        reviewer: str | None = None,
    ) -> bool:
        """
        Publish HITL approval event.

        Args:
            event_type: HITL_APPROVAL_REQUIRED/COMPLETED/TIMEOUT
            approval_id: HITL approval ID
            task_id: Related orchestrator task ID
            task_type: Type of task requiring approval
            decision: Approval decision (for completed events)
            reviewer: Who made the decision

        Returns:
            True if event was published successfully
        """
        detail = {
            "approvalId": approval_id,
        }

        if task_id:
            detail["taskId"] = task_id
        if task_type:
            detail["taskType"] = task_type
        if decision:
            detail["decision"] = decision
        if reviewer:
            detail["reviewer"] = reviewer

        return await self.publish_event(
            event_type, detail, source_service="hitl-service"
        )

    # -------------------------------------------------------------------------
    # AWS API Methods
    # -------------------------------------------------------------------------

    async def _put_event(self, detail_type: str, event_detail: EventDetail) -> bool:
        """
        Call EventBridge PutEvents API.

        Args:
            detail_type: Event detail type (e.g., 'aura.anomaly.detected')
            event_detail: Event detail payload

        Returns:
            True if API call succeeded
        """
        if self.mode == PublisherMode.MOCK:
            return self._mock_publish(detail_type, event_detail)

        try:
            entry = {
                "Source": self.EVENT_SOURCE,
                "DetailType": detail_type,
                "Detail": json.dumps(event_detail.to_dict()),
                "EventBusName": self.event_bus_name,
            }

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.client.put_events(Entries=[entry])
            )

            # Check for failures
            if response.get("FailedEntryCount", 0) > 0:
                failed = response.get("Entries", [{}])[0]
                error_msg = f"EventBridge put failed: {failed.get('ErrorMessage', 'Unknown error')}"
                logger.error(error_msg)
                self.stats.events_failed += 1
                self.stats.errors.append(error_msg)
                return False

            self.stats.events_published += 1
            self.stats.last_publish_time = datetime.now(timezone.utc)

            logger.debug(f"Published event: {detail_type}")
            return True

        except ClientError as e:
            error_msg = f"EventBridge PutEvents failed: {e}"
            logger.error(error_msg)
            self.stats.events_failed += 1
            self.stats.errors.append(error_msg)
            return False

    def _mock_publish(self, detail_type: str, event_detail: EventDetail) -> bool:
        """
        Mock publish for testing.

        Args:
            detail_type: Event detail type
            event_detail: Event detail payload

        Returns:
            Always True in mock mode
        """
        self._mock_events.append(
            {
                "source": self.EVENT_SOURCE,
                "detail_type": detail_type,
                "detail": event_detail.to_dict(),
                "event_bus": self.event_bus_name,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.stats.events_published += 1
        self.stats.last_publish_time = datetime.now(timezone.utc)

        logger.debug(f"[MOCK] Published event: {detail_type}")
        return True

    # -------------------------------------------------------------------------
    # Statistics & Testing
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get publisher statistics."""
        return {
            "mode": self.mode.value,
            "region": self.region,
            "event_bus": self.event_bus_name,
            "events_published": self.stats.events_published,
            "events_failed": self.stats.events_failed,
            "last_publish_time": (
                self.stats.last_publish_time.isoformat()
                if self.stats.last_publish_time
                else None
            ),
            "recent_errors": self.stats.errors[-5:],  # Last 5 errors
        }

    def get_mock_events(self) -> list[dict[str, Any]]:
        """Get mock-published events (for testing)."""
        return self._mock_events.copy()

    def clear_mock_events(self) -> None:
        """Clear mock events (for testing)."""
        self._mock_events.clear()


# =============================================================================
# Factory Function
# =============================================================================


_publisher_instance: EventBridgePublisher | None = None


def get_eventbridge_publisher() -> EventBridgePublisher:
    """
    Get singleton EventBridge publisher instance.

    Returns:
        EventBridgePublisher instance
    """
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = EventBridgePublisher()
    return _publisher_instance


def create_eventbridge_publisher(
    mode: PublisherMode | None = None,
    region: str | None = None,
    event_bus_name: str | None = None,
) -> EventBridgePublisher:
    """
    Create a new EventBridge publisher instance.

    Args:
        mode: Operating mode (AWS or MOCK)
        region: AWS region
        event_bus_name: EventBridge event bus name

    Returns:
        New EventBridgePublisher instance
    """
    return EventBridgePublisher(mode=mode, region=region, event_bus_name=event_bus_name)
