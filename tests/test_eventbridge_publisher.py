"""
Tests for Project Aura - EventBridge Event Publisher

Comprehensive tests for publishing anomaly events to AWS EventBridge
for event-driven automation and cross-service event routing.
"""

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# Save original modules before mocking to prevent test pollution
_modules_to_save = [
    "boto3",
    "botocore",
    "botocore.exceptions",
    "src.services.eventbridge_publisher",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock boto3 before importing the module
mock_boto3 = MagicMock()
mock_botocore = MagicMock()
sys.modules["boto3"] = mock_boto3
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore.exceptions
mock_botocore.exceptions.ClientError = Exception

from src.services.eventbridge_publisher import (
    EventBridgePublisher,
    EventDetail,
    EventType,
    PublisherMode,
    PublisherStats,
    create_eventbridge_publisher,
    get_eventbridge_publisher,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


# =============================================================================
# EventType Enum Tests
# =============================================================================


class TestEventType:
    """Tests for EventType enum."""

    def test_anomaly_detected(self):
        """Test ANOMALY_DETECTED event type."""
        assert EventType.ANOMALY_DETECTED.value == "aura.anomaly.detected"

    def test_anomaly_status_changed(self):
        """Test ANOMALY_STATUS_CHANGED event type."""
        assert EventType.ANOMALY_STATUS_CHANGED.value == "aura.anomaly.status_changed"

    def test_anomaly_resolved(self):
        """Test ANOMALY_RESOLVED event type."""
        assert EventType.ANOMALY_RESOLVED.value == "aura.anomaly.resolved"

    def test_cve_detected(self):
        """Test CVE_DETECTED event type."""
        assert EventType.CVE_DETECTED.value == "aura.security.cve_detected"

    def test_threat_detected(self):
        """Test THREAT_DETECTED event type."""
        assert EventType.THREAT_DETECTED.value == "aura.security.threat_detected"

    def test_vulnerability_found(self):
        """Test VULNERABILITY_FOUND event type."""
        assert (
            EventType.VULNERABILITY_FOUND.value == "aura.security.vulnerability_found"
        )

    def test_orchestrator_task_triggered(self):
        """Test ORCHESTRATOR_TASK_TRIGGERED event type."""
        assert (
            EventType.ORCHESTRATOR_TASK_TRIGGERED.value
            == "aura.orchestrator.task_triggered"
        )

    def test_orchestrator_task_completed(self):
        """Test ORCHESTRATOR_TASK_COMPLETED event type."""
        assert (
            EventType.ORCHESTRATOR_TASK_COMPLETED.value
            == "aura.orchestrator.task_completed"
        )

    def test_orchestrator_task_failed(self):
        """Test ORCHESTRATOR_TASK_FAILED event type."""
        assert (
            EventType.ORCHESTRATOR_TASK_FAILED.value == "aura.orchestrator.task_failed"
        )

    def test_hitl_approval_required(self):
        """Test HITL_APPROVAL_REQUIRED event type."""
        assert EventType.HITL_APPROVAL_REQUIRED.value == "aura.hitl.approval_required"

    def test_hitl_approval_completed(self):
        """Test HITL_APPROVAL_COMPLETED event type."""
        assert EventType.HITL_APPROVAL_COMPLETED.value == "aura.hitl.approval_completed"

    def test_hitl_timeout(self):
        """Test HITL_TIMEOUT event type."""
        assert EventType.HITL_TIMEOUT.value == "aura.hitl.timeout"

    def test_notification_sent(self):
        """Test NOTIFICATION_SENT event type."""
        assert EventType.NOTIFICATION_SENT.value == "aura.notification.sent"

    def test_notification_failed(self):
        """Test NOTIFICATION_FAILED event type."""
        assert EventType.NOTIFICATION_FAILED.value == "aura.notification.failed"

    def test_all_event_types_exist(self):
        """Test all expected event types are defined."""
        expected = {
            "aura.anomaly.detected",
            "aura.anomaly.status_changed",
            "aura.anomaly.resolved",
            "aura.security.cve_detected",
            "aura.security.threat_detected",
            "aura.security.vulnerability_found",
            "aura.orchestrator.task_triggered",
            "aura.orchestrator.task_completed",
            "aura.orchestrator.task_failed",
            "aura.hitl.approval_required",
            "aura.hitl.approval_completed",
            "aura.hitl.timeout",
            "aura.notification.sent",
            "aura.notification.failed",
            # Agent messaging events (Issue #19)
            "aura.agent.task_dispatched",
            "aura.agent.task_completed",
            "aura.agent.task_failed",
            "aura.agent.status_update",
        }
        actual = {e.value for e in EventType}
        assert actual == expected


# =============================================================================
# PublisherMode Enum Tests
# =============================================================================


class TestPublisherMode:
    """Tests for PublisherMode enum."""

    def test_aws(self):
        """Test AWS mode."""
        assert PublisherMode.AWS.value == "aws"

    def test_mock(self):
        """Test MOCK mode."""
        assert PublisherMode.MOCK.value == "mock"

    def test_all_modes_exist(self):
        """Test all expected modes are defined."""
        expected = {"aws", "mock"}
        actual = {m.value for m in PublisherMode}
        assert actual == expected


# =============================================================================
# EventDetail Tests
# =============================================================================


class TestEventDetail:
    """Tests for EventDetail dataclass."""

    def test_minimal_detail(self):
        """Test minimal event detail creation."""
        detail = EventDetail(event_type="aura.test.event")

        assert detail.event_type == "aura.test.event"
        assert detail.source_service == "anomaly-detection"
        assert detail.version == "1.0"
        assert detail.timestamp is not None
        assert detail.data == {}

    def test_full_detail(self):
        """Test full event detail creation."""
        detail = EventDetail(
            event_type="aura.anomaly.detected",
            source_service="meta-orchestrator",
            version="2.0",
            timestamp="2025-01-01T00:00:00Z",
            environment="production",
            data={"anomalyId": "123", "severity": "high"},
        )

        assert detail.event_type == "aura.anomaly.detected"
        assert detail.source_service == "meta-orchestrator"
        assert detail.version == "2.0"
        assert detail.environment == "production"
        assert detail.data["anomalyId"] == "123"

    def test_to_dict(self):
        """Test to_dict conversion."""
        detail = EventDetail(
            event_type="aura.test.event",
            source_service="test-service",
            data={"key": "value"},
        )

        result = detail.to_dict()

        assert result["eventType"] == "aura.test.event"
        assert result["sourceService"] == "test-service"
        assert result["version"] == "1.0"
        assert "timestamp" in result
        assert result["data"] == {"key": "value"}


# =============================================================================
# PublisherStats Tests
# =============================================================================


class TestPublisherStats:
    """Tests for PublisherStats dataclass."""

    def test_default_stats(self):
        """Test default statistics values."""
        stats = PublisherStats()

        assert stats.events_published == 0
        assert stats.events_failed == 0
        assert stats.last_publish_time is None
        assert stats.errors == []

    def test_custom_stats(self):
        """Test custom statistics values."""
        now = datetime.now(timezone.utc)
        stats = PublisherStats(
            events_published=100,
            events_failed=5,
            last_publish_time=now,
            errors=["Error 1", "Error 2"],
        )

        assert stats.events_published == 100
        assert stats.events_failed == 5
        assert stats.last_publish_time == now
        assert len(stats.errors) == 2


# =============================================================================
# EventBridgePublisher Initialization Tests
# =============================================================================


class TestEventBridgePublisherInit:
    """Tests for EventBridgePublisher initialization."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

        assert publisher.mode == PublisherMode.MOCK
        assert publisher.stats is not None
        assert publisher._mock_events == []

    def test_init_with_custom_region(self):
        """Test initialization with custom region."""
        publisher = EventBridgePublisher(
            mode=PublisherMode.MOCK,
            region="eu-west-1",
        )

        assert publisher.region == "eu-west-1"

    def test_init_with_custom_event_bus(self):
        """Test initialization with custom event bus name."""
        publisher = EventBridgePublisher(
            mode=PublisherMode.MOCK,
            event_bus_name="my-custom-bus",
        )

        assert publisher.event_bus_name == "my-custom-bus"

    @patch.dict("os.environ", {"EVENTBRIDGE_MODE": "mock"})
    def test_detect_mode_from_env_mock(self):
        """Test mode detection from environment variable."""
        publisher = EventBridgePublisher()
        assert publisher.mode == PublisherMode.MOCK

    @patch.dict("os.environ", {"EVENTBRIDGE_MODE": "aws"})
    def test_detect_mode_from_env_aws(self):
        """Test mode detection for AWS from environment."""
        publisher = EventBridgePublisher()
        assert publisher.mode == PublisherMode.AWS

    @patch.dict(
        "os.environ",
        {
            "PROJECT_NAME": "myproject",
            "ENVIRONMENT": "prod",
        },
        clear=False,
    )
    def test_event_bus_name_from_env(self):
        """Test event bus name construction from environment."""
        publisher = EventBridgePublisher(mode=PublisherMode.MOCK)
        assert "myproject" in publisher.event_bus_name
        assert "prod" in publisher.event_bus_name

    @patch.dict("os.environ", {"AURA_EVENT_BUS": "explicit-bus"})
    def test_event_bus_name_explicit_override(self):
        """Test explicit event bus name override."""
        publisher = EventBridgePublisher(mode=PublisherMode.MOCK)
        assert publisher.event_bus_name == "explicit-bus"


# =============================================================================
# EventBridgePublisher Publishing Tests
# =============================================================================


class TestEventBridgePublisherPublishing:
    """Tests for event publishing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

    @pytest.mark.asyncio
    async def test_publish_event(self):
        """Test publishing a single event."""
        result = await self.publisher.publish_event(
            event_type=EventType.ANOMALY_DETECTED,
            detail={"anomalyId": "123", "severity": "high"},
        )

        assert result is True
        assert self.publisher.stats.events_published == 1
        assert len(self.publisher._mock_events) == 1

    @pytest.mark.asyncio
    async def test_publish_event_with_source(self):
        """Test publishing event with custom source service."""
        await self.publisher.publish_event(
            event_type=EventType.ORCHESTRATOR_TASK_TRIGGERED,
            detail={"taskId": "task-123"},
            source_service="meta-orchestrator",
        )

        event = self.publisher._mock_events[0]
        assert event["detail"]["sourceService"] == "meta-orchestrator"

    @pytest.mark.asyncio
    async def test_publish_status_change(self):
        """Test publishing status change event."""
        result = await self.publisher.publish_status_change(
            anomaly_id="anomaly-123",
            old_status="open",
            new_status="investigating",
            changed_by="admin@example.com",
        )

        assert result is True
        event = self.publisher._mock_events[0]
        assert event["detail_type"] == EventType.ANOMALY_STATUS_CHANGED.value
        assert event["detail"]["data"]["anomalyId"] == "anomaly-123"
        assert event["detail"]["data"]["oldStatus"] == "open"
        assert event["detail"]["data"]["newStatus"] == "investigating"

    @pytest.mark.asyncio
    async def test_publish_orchestrator_event_triggered(self):
        """Test publishing orchestrator triggered event."""
        result = await self.publisher.publish_orchestrator_event(
            event_type=EventType.ORCHESTRATOR_TASK_TRIGGERED,
            task_id="task-123",
            anomaly_id="anomaly-456",
            task_type="investigate",
        )

        assert result is True
        event = self.publisher._mock_events[0]
        assert event["detail"]["data"]["taskId"] == "task-123"
        assert event["detail"]["data"]["anomalyId"] == "anomaly-456"

    @pytest.mark.asyncio
    async def test_publish_orchestrator_event_completed(self):
        """Test publishing orchestrator completed event."""
        result = await self.publisher.publish_orchestrator_event(
            event_type=EventType.ORCHESTRATOR_TASK_COMPLETED,
            task_id="task-123",
            success=True,
            duration_seconds=45.5,
            result={"patches_applied": 3},
        )

        assert result is True
        event = self.publisher._mock_events[0]
        assert event["detail"]["data"]["success"] is True
        assert event["detail"]["data"]["durationSeconds"] == 45.5
        assert event["detail"]["data"]["result"]["patches_applied"] == 3

    @pytest.mark.asyncio
    async def test_publish_hitl_event_required(self):
        """Test publishing HITL approval required event."""
        result = await self.publisher.publish_hitl_event(
            event_type=EventType.HITL_APPROVAL_REQUIRED,
            approval_id="approval-123",
            task_id="task-456",
            task_type="remediate",
        )

        assert result is True
        event = self.publisher._mock_events[0]
        assert event["detail"]["data"]["approvalId"] == "approval-123"
        assert event["detail"]["data"]["taskId"] == "task-456"

    @pytest.mark.asyncio
    async def test_publish_hitl_event_completed(self):
        """Test publishing HITL approval completed event."""
        result = await self.publisher.publish_hitl_event(
            event_type=EventType.HITL_APPROVAL_COMPLETED,
            approval_id="approval-123",
            decision="approved",
            reviewer="admin@example.com",
        )

        assert result is True
        event = self.publisher._mock_events[0]
        assert event["detail"]["data"]["decision"] == "approved"
        assert event["detail"]["data"]["reviewer"] == "admin@example.com"


# =============================================================================
# EventBridgePublisher Mock Events Tests
# =============================================================================


class TestEventBridgePublisherMockEvents:
    """Tests for mock event storage."""

    def setup_method(self):
        """Set up test fixtures."""
        self.publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

    @pytest.mark.asyncio
    async def test_get_mock_events(self):
        """Test getting mock events."""
        await self.publisher.publish_event(
            event_type=EventType.ANOMALY_DETECTED,
            detail={"test": "data"},
        )

        events = self.publisher.get_mock_events()

        assert len(events) == 1
        assert events[0]["detail"]["data"]["test"] == "data"

    @pytest.mark.asyncio
    async def test_get_mock_events_returns_copy(self):
        """Test that get_mock_events returns a copy."""
        await self.publisher.publish_event(
            event_type=EventType.ANOMALY_DETECTED,
            detail={},
        )

        events1 = self.publisher.get_mock_events()
        events2 = self.publisher.get_mock_events()

        assert events1 is not events2

    @pytest.mark.asyncio
    async def test_clear_mock_events(self):
        """Test clearing mock events."""
        await self.publisher.publish_event(
            event_type=EventType.ANOMALY_DETECTED,
            detail={},
        )
        await self.publisher.publish_event(
            event_type=EventType.ANOMALY_DETECTED,
            detail={},
        )

        self.publisher.clear_mock_events()

        assert len(self.publisher._mock_events) == 0

    @pytest.mark.asyncio
    async def test_mock_event_structure(self):
        """Test structure of mock events."""
        await self.publisher.publish_event(
            event_type=EventType.THREAT_DETECTED,
            detail={"threat": "test"},
        )

        event = self.publisher._mock_events[0]

        assert "source" in event
        assert event["source"] == "aura"
        assert "detail_type" in event
        assert event["detail_type"] == EventType.THREAT_DETECTED.value
        assert "detail" in event
        assert "event_bus" in event
        assert "published_at" in event


# =============================================================================
# EventBridgePublisher Statistics Tests
# =============================================================================


class TestEventBridgePublisherStats:
    """Tests for publisher statistics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

    def test_get_stats_initial(self):
        """Test initial statistics."""
        stats = self.publisher.get_stats()

        assert stats["mode"] == "mock"
        assert stats["events_published"] == 0
        assert stats["events_failed"] == 0
        assert stats["last_publish_time"] is None

    @pytest.mark.asyncio
    async def test_get_stats_after_publish(self):
        """Test statistics after publishing events."""
        await self.publisher.publish_event(
            event_type=EventType.ANOMALY_DETECTED,
            detail={},
        )

        stats = self.publisher.get_stats()

        assert stats["events_published"] == 1
        assert stats["last_publish_time"] is not None

    @pytest.mark.asyncio
    async def test_stats_include_event_bus(self):
        """Test that stats include event bus info."""
        stats = self.publisher.get_stats()

        assert "event_bus" in stats
        assert "region" in stats

    def test_stats_include_recent_errors(self):
        """Test that stats include recent errors."""
        self.publisher.stats.errors = [
            "Error 1",
            "Error 2",
            "Error 3",
            "Error 4",
            "Error 5",
            "Error 6",
        ]

        stats = self.publisher.get_stats()

        # Should only include last 5 errors
        assert len(stats["recent_errors"]) == 5
        assert "Error 6" in stats["recent_errors"]


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def teardown_method(self):
        """Reset singleton after each test."""
        import src.services.eventbridge_publisher as module

        module._publisher_instance = None

    def test_get_eventbridge_publisher(self):
        """Test getting singleton instance."""
        publisher1 = get_eventbridge_publisher()
        publisher2 = get_eventbridge_publisher()

        assert publisher1 is publisher2
        assert isinstance(publisher1, EventBridgePublisher)

    def test_create_eventbridge_publisher(self):
        """Test creating new instance."""
        publisher = create_eventbridge_publisher(
            mode=PublisherMode.MOCK,
            region="ap-southeast-1",
            event_bus_name="test-bus",
        )

        assert publisher.mode == PublisherMode.MOCK
        assert publisher.region == "ap-southeast-1"
        assert publisher.event_bus_name == "test-bus"


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_event_source_constant(self):
        """Test EVENT_SOURCE constant is correct."""
        assert EventBridgePublisher.EVENT_SOURCE == "aura"

    @pytest.mark.asyncio
    async def test_publish_multiple_events(self):
        """Test publishing multiple events."""
        publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

        for i in range(10):
            await publisher.publish_event(
                event_type=EventType.ANOMALY_DETECTED,
                detail={"index": i},
            )

        assert publisher.stats.events_published == 10
        assert len(publisher._mock_events) == 10

    @pytest.mark.asyncio
    async def test_publish_with_empty_detail(self):
        """Test publishing with empty detail."""
        publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

        result = await publisher.publish_event(
            event_type=EventType.NOTIFICATION_SENT,
            detail={},
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_publish_with_complex_detail(self):
        """Test publishing with complex nested detail."""
        publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

        result = await publisher.publish_event(
            event_type=EventType.ANOMALY_DETECTED,
            detail={
                "nested": {
                    "deep": {
                        "value": 123,
                        "list": [1, 2, 3],
                    }
                },
                "array": ["a", "b", "c"],
            },
        )

        assert result is True
        event = publisher._mock_events[0]
        assert event["detail"]["data"]["nested"]["deep"]["value"] == 123

    def test_client_lazy_initialization_mock(self):
        """Test client is None in mock mode."""
        publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

        # Access the client property
        client = publisher.client

        assert client is None

    @pytest.mark.asyncio
    async def test_stats_update_last_publish_time(self):
        """Test that last_publish_time is updated on each publish."""
        publisher = EventBridgePublisher(mode=PublisherMode.MOCK)

        await publisher.publish_event(EventType.ANOMALY_DETECTED, {})
        first_time = publisher.stats.last_publish_time

        await publisher.publish_event(EventType.ANOMALY_DETECTED, {})
        second_time = publisher.stats.last_publish_time

        assert second_time >= first_time
