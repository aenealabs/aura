"""
Tests for Real-Time Monitoring Integration

Tests the CloudWatch Metrics Publisher, EventBridge Publisher,
Anomaly Persistence Service, and the integration layer that wires them together.
"""

import asyncio
import platform
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.anomaly_detection_service import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_anomaly():
    """Create a sample anomaly event for testing."""
    return AnomalyEvent(
        id="anomaly-test-001",
        type=AnomalyType.SECURITY_EVENT,
        severity=AnomalySeverity.HIGH,
        title="Suspicious activity detected",
        description="Unusual login pattern from unknown IP",
        source="security-monitor",
        timestamp=datetime.now(timezone.utc),
        status=AnomalyStatus.DETECTED,
        affected_components=["auth-service", "user-api"],
        recommended_action="Review access logs and verify user identity",
        metadata={"ip_address": "192.168.1.100", "user_id": "user-123"},
    )


@pytest.fixture
def sample_cve_anomaly():
    """Create a CVE anomaly event for testing."""
    return AnomalyEvent(
        id="anomaly-cve-001",
        type=AnomalyType.NEW_CVE,
        severity=AnomalySeverity.CRITICAL,
        title="Critical CVE detected in dependency",
        description="CVE-2024-12345 affects lodash < 4.17.21",
        source="vulnerability-scanner",
        timestamp=datetime.now(timezone.utc),
        status=AnomalyStatus.DETECTED,
        cve_id="CVE-2024-12345",
        affected_components=["package.json", "node_modules/lodash"],
        recommended_action="Upgrade lodash to version 4.17.21 or later",
    )


# =============================================================================
# CloudWatch Metrics Publisher Tests
# =============================================================================


class TestCloudWatchMetricsPublisher:
    """Tests for CloudWatchMetricsPublisher service."""

    @pytest.fixture
    def mock_publisher(self):
        """Create a mock mode publisher."""
        from src.services.cloudwatch_metrics_publisher import (
            CloudWatchMetricsPublisher,
            PublisherMode,
        )

        return CloudWatchMetricsPublisher(mode=PublisherMode.MOCK)

    @pytest.mark.asyncio
    async def test_publish_metric_mock_mode(self, mock_publisher):
        """Test publishing a metric in mock mode."""
        success = await mock_publisher.publish_metric(
            namespace="Aura/Test",
            metric_name="TestMetric",
            value=42.0,
            unit="Count",
            dimensions={"Environment": "test"},
        )

        # Metrics are buffered by default, flush to publish
        await mock_publisher.flush()

        assert success is True
        # After flush, metrics should be published
        assert mock_publisher.stats.metrics_published == 1

    @pytest.mark.asyncio
    async def test_publish_anomaly(self, mock_publisher, sample_anomaly):
        """Test publishing an anomaly event as metrics."""
        success = await mock_publisher.publish_anomaly(sample_anomaly)

        assert success is True
        # Should publish multiple metrics for the anomaly
        assert mock_publisher.stats.metrics_published >= 1

    @pytest.mark.asyncio
    async def test_publish_anomaly_with_cve(self, mock_publisher, sample_cve_anomaly):
        """Test publishing a CVE anomaly event."""
        success = await mock_publisher.publish_anomaly(sample_cve_anomaly)

        assert success is True
        assert mock_publisher.stats.metrics_published >= 1

    @pytest.mark.asyncio
    async def test_batch_metrics(self, mock_publisher):
        """Test batching multiple metrics."""
        # Publish multiple metrics
        for i in range(10):
            await mock_publisher.publish_metric(
                namespace="Aura/Test",
                metric_name=f"Metric{i}",
                value=float(i),
                immediate=False,  # Batch mode
            )

        # Flush the batch
        await mock_publisher.flush()

        # All metrics should be published
        assert mock_publisher.stats.metrics_published == 10

    @pytest.mark.asyncio
    async def test_publish_orchestrator_event(self, mock_publisher):
        """Test publishing orchestrator events."""
        success = await mock_publisher.publish_orchestrator_event(
            event_type="completed",
            task_id="task-123",
            success=True,
            duration_seconds=45.5,
        )

        # Flush to ensure metrics are counted
        await mock_publisher.flush()
        assert success is True
        # In mock mode, metrics are buffered then flushed
        assert (
            mock_publisher.stats.metrics_published >= 1
            or mock_publisher.stats.batches_sent >= 1
        )

    def test_get_stats(self, mock_publisher):
        """Test getting publisher statistics."""
        stats = mock_publisher.get_stats()

        assert "mode" in stats
        assert stats["mode"] == "mock"
        assert "metrics_published" in stats
        assert "region" in stats

    def test_mode_detection(self):
        """Test automatic mode detection."""
        from src.services.cloudwatch_metrics_publisher import (
            CloudWatchMetricsPublisher,
            PublisherMode,
        )

        # Without AWS environment, should default to MOCK
        with patch.dict("os.environ", {}, clear=True):
            publisher = CloudWatchMetricsPublisher()
            assert publisher.mode == PublisherMode.MOCK


# =============================================================================
# EventBridge Publisher Tests
# =============================================================================


class TestEventBridgePublisher:
    """Tests for EventBridgePublisher service."""

    @pytest.fixture
    def mock_publisher(self):
        """Create a mock mode publisher."""
        from src.services.eventbridge_publisher import (
            EventBridgePublisher,
            PublisherMode,
        )

        return EventBridgePublisher(mode=PublisherMode.MOCK)

    @pytest.mark.asyncio
    async def test_publish_anomaly_event(self, mock_publisher, sample_anomaly):
        """Test publishing an anomaly event."""
        success = await mock_publisher.publish_anomaly_event(sample_anomaly)

        assert success is True
        assert mock_publisher.stats.events_published == 1

        # Check mock events
        events = mock_publisher.get_mock_events()
        assert len(events) == 1
        assert events[0]["source"] == "aura"

    @pytest.mark.asyncio
    async def test_publish_cve_event(self, mock_publisher, sample_cve_anomaly):
        """Test publishing a CVE event maps to correct event type."""
        success = await mock_publisher.publish_anomaly_event(sample_cve_anomaly)

        assert success is True
        events = mock_publisher.get_mock_events()
        assert len(events) == 1
        # CVE should map to CVE_DETECTED event type
        assert "cve" in events[0]["detail_type"].lower()

    @pytest.mark.asyncio
    async def test_publish_status_change(self, mock_publisher):
        """Test publishing anomaly status change."""
        success = await mock_publisher.publish_status_change(
            anomaly_id="anomaly-123",
            old_status="detected",
            new_status="investigating",
            changed_by="auto-triage",
        )

        assert success is True
        events = mock_publisher.get_mock_events()
        assert len(events) == 1
        assert "status_changed" in events[0]["detail_type"]

    @pytest.mark.asyncio
    async def test_publish_orchestrator_event(self, mock_publisher):
        """Test publishing orchestrator events."""
        from src.services.eventbridge_publisher import EventType

        success = await mock_publisher.publish_orchestrator_event(
            event_type=EventType.ORCHESTRATOR_TASK_COMPLETED,
            task_id="task-456",
            anomaly_id="anomaly-123",
            task_type="investigate",
            success=True,
            duration_seconds=30.0,
        )

        assert success is True
        events = mock_publisher.get_mock_events()
        assert len(events) == 1
        assert "orchestrator" in events[0]["detail_type"]

    @pytest.mark.asyncio
    async def test_publish_hitl_event(self, mock_publisher):
        """Test publishing HITL approval events."""
        from src.services.eventbridge_publisher import EventType

        success = await mock_publisher.publish_hitl_event(
            event_type=EventType.HITL_APPROVAL_REQUIRED,
            approval_id="approval-789",
            task_id="task-456",
            task_type="patch_deployment",
        )

        assert success is True
        events = mock_publisher.get_mock_events()
        assert len(events) == 1
        assert "hitl" in events[0]["detail_type"]

    def test_clear_mock_events(self, mock_publisher):
        """Test clearing mock events."""
        asyncio.run(mock_publisher.publish_status_change("a", "b", "c"))
        assert len(mock_publisher.get_mock_events()) == 1

        mock_publisher.clear_mock_events()
        assert len(mock_publisher.get_mock_events()) == 0


# =============================================================================
# Anomaly Persistence Service Tests
# =============================================================================


class TestAnomalyPersistenceService:
    """Tests for AnomalyPersistenceService."""

    @pytest.fixture
    def mock_persistence(self):
        """Create a mock mode persistence service."""
        from src.services.anomaly_persistence_service import (
            AnomalyPersistenceService,
            PersistenceMode,
        )

        return AnomalyPersistenceService(mode=PersistenceMode.MOCK)

    @pytest.mark.asyncio
    async def test_persist_anomaly(self, mock_persistence, sample_anomaly):
        """Test persisting an anomaly."""
        success = await mock_persistence.persist_anomaly(sample_anomaly)

        assert success is True
        assert mock_persistence.stats.items_written == 1

        # Verify it can be retrieved
        record = await mock_persistence.get_anomaly(sample_anomaly.id)
        assert record is not None
        assert record.anomaly_id == sample_anomaly.id
        assert record.severity == sample_anomaly.severity.value

    @pytest.mark.asyncio
    async def test_update_status(self, mock_persistence, sample_anomaly):
        """Test updating anomaly status."""
        await mock_persistence.persist_anomaly(sample_anomaly)

        success = await mock_persistence.update_status(
            anomaly_id=sample_anomaly.id,
            new_status="resolved",
            resolved_by="security-team",
        )

        assert success is True
        assert mock_persistence.stats.items_updated == 1

        # Verify status was updated
        record = await mock_persistence.get_anomaly(sample_anomaly.id)
        assert record.status == "resolved"

    @pytest.mark.asyncio
    async def test_query_by_status(self, mock_persistence, sample_anomaly):
        """Test querying anomalies by status."""
        await mock_persistence.persist_anomaly(sample_anomaly)

        result = await mock_persistence.query_by_status("detected")

        assert result.count >= 1
        assert any(item.anomaly_id == sample_anomaly.id for item in result.items)

    @pytest.mark.asyncio
    async def test_query_by_severity(self, mock_persistence, sample_anomaly):
        """Test querying anomalies by severity."""
        await mock_persistence.persist_anomaly(sample_anomaly)

        result = await mock_persistence.query_by_severity("high", hours=24)

        assert result.count >= 1
        assert any(item.anomaly_id == sample_anomaly.id for item in result.items)

    @pytest.mark.asyncio
    async def test_check_dedup_window(self, mock_persistence, sample_anomaly):
        """Test deduplication window check."""
        await mock_persistence.persist_anomaly(sample_anomaly)

        # Check for duplicates with same dedup key
        duplicates = await mock_persistence.check_dedup_window(
            dedup_key=sample_anomaly.dedup_key, hours=1
        )

        assert len(duplicates) == 1
        assert duplicates[0].anomaly_id == sample_anomaly.id

    @pytest.mark.asyncio
    async def test_link_orchestrator_task(self, mock_persistence, sample_anomaly):
        """Test linking an orchestrator task to an anomaly."""
        await mock_persistence.persist_anomaly(sample_anomaly)

        success = await mock_persistence.link_orchestrator_task(
            anomaly_id=sample_anomaly.id, task_id="task-999"
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_link_hitl_approval(self, mock_persistence, sample_anomaly):
        """Test linking a HITL approval to an anomaly."""
        await mock_persistence.persist_anomaly(sample_anomaly)

        success = await mock_persistence.link_hitl_approval(
            anomaly_id=sample_anomaly.id, approval_id="approval-888"
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_get_anomaly_summary(
        self, mock_persistence, sample_anomaly, sample_cve_anomaly
    ):
        """Test getting anomaly summary statistics."""
        await mock_persistence.persist_anomaly(sample_anomaly)
        await mock_persistence.persist_anomaly(sample_cve_anomaly)

        summary = await mock_persistence.get_anomaly_summary(hours=24)

        assert summary["total"] == 2
        assert "by_status" in summary
        assert "by_severity" in summary
        assert "by_type" in summary

    def test_get_stats(self, mock_persistence):
        """Test getting persistence statistics."""
        stats = mock_persistence.get_stats()

        assert "mode" in stats
        assert stats["mode"] == "mock"
        assert "table" in stats
        assert "ttl_days" in stats


# =============================================================================
# Real-Time Monitoring Integration Tests
# =============================================================================


class TestRealTimeMonitoringIntegration:
    """Tests for RealTimeMonitoringIntegration service."""

    @pytest.fixture
    def mock_integration(self):
        """Create a mock integration with mocked publishers."""
        from src.services.anomaly_persistence_service import (
            AnomalyPersistenceService,
            PersistenceMode,
        )
        from src.services.cloudwatch_metrics_publisher import CloudWatchMetricsPublisher
        from src.services.cloudwatch_metrics_publisher import PublisherMode as CWMode
        from src.services.eventbridge_publisher import EventBridgePublisher
        from src.services.eventbridge_publisher import PublisherMode as EBMode
        from src.services.realtime_monitoring_integration import (
            IntegrationConfig,
            RealTimeMonitoringIntegration,
        )

        config = IntegrationConfig(
            enable_cloudwatch=True,
            enable_eventbridge=True,
            enable_persistence=True,
            enable_notifications=False,  # Disable for testing
        )

        return RealTimeMonitoringIntegration(
            config=config,
            cloudwatch_publisher=CloudWatchMetricsPublisher(mode=CWMode.MOCK),
            eventbridge_publisher=EventBridgePublisher(mode=EBMode.MOCK),
            persistence_service=AnomalyPersistenceService(mode=PersistenceMode.MOCK),
        )

    @pytest.mark.asyncio
    async def test_handle_anomaly(self, mock_integration, sample_anomaly):
        """Test handling an anomaly routes to all publishers."""
        await mock_integration._handle_anomaly(sample_anomaly)

        assert mock_integration.stats.anomalies_processed == 1
        assert mock_integration.stats.cloudwatch_published == 1
        assert mock_integration.stats.eventbridge_published == 1
        assert mock_integration.stats.persistence_written == 1

    @pytest.mark.asyncio
    async def test_severity_routing(self, mock_integration):
        """Test severity-based routing."""
        from src.services.realtime_monitoring_integration import (
            severity_meets_threshold,
        )

        # Test severity comparisons
        assert severity_meets_threshold("critical", "low") is True
        assert severity_meets_threshold("high", "medium") is True
        assert severity_meets_threshold("low", "high") is False
        assert severity_meets_threshold("info", "medium") is False

    @pytest.mark.asyncio
    async def test_connect_to_detector(self, mock_integration):
        """Test connecting to anomaly detector."""
        # Create a mock anomaly detector
        mock_detector = MagicMock()
        mock_detector.on_anomaly = MagicMock()

        mock_integration.connect(mock_detector)

        mock_detector.on_anomaly.assert_called_once()
        assert mock_integration._anomaly_detector is mock_detector

    @pytest.mark.asyncio
    async def test_publish_orchestrator_started(self, mock_integration):
        """Test publishing orchestrator started event."""
        await mock_integration.publish_orchestrator_started(
            task_id="task-123",
            anomaly_id="anomaly-456",
            task_type="investigate",
        )

        # Flush CloudWatch metrics
        await mock_integration._cloudwatch_publisher.flush()

        # Should publish to EventBridge (CloudWatch may be buffered)
        assert len(mock_integration._eventbridge_publisher.get_mock_events()) >= 1

    @pytest.mark.asyncio
    async def test_publish_orchestrator_completed(self, mock_integration):
        """Test publishing orchestrator completed event."""
        await mock_integration.publish_orchestrator_completed(
            task_id="task-123",
            anomaly_id="anomaly-456",
            task_type="remediate",
            success=True,
            duration_seconds=120.0,
            result={"patches_applied": 3},
        )

        # Flush CloudWatch metrics
        await mock_integration._cloudwatch_publisher.flush()

        # Should publish to EventBridge
        assert len(mock_integration._eventbridge_publisher.get_mock_events()) >= 1

    @pytest.mark.asyncio
    async def test_publish_hitl_approval_required(self, mock_integration):
        """Test publishing HITL approval required event."""
        await mock_integration.publish_hitl_approval_required(
            approval_id="approval-123",
            task_id="task-456",
            task_type="patch_deployment",
        )

        # Flush CloudWatch metrics
        await mock_integration._cloudwatch_publisher.flush()

        # Should publish to EventBridge
        assert len(mock_integration._eventbridge_publisher.get_mock_events()) >= 1

    @pytest.mark.asyncio
    async def test_publish_hitl_decision(self, mock_integration):
        """Test publishing HITL decision event."""
        await mock_integration.publish_hitl_decision(
            approval_id="approval-123",
            decision="approved",
            reviewer="security-admin@example.com",
            task_id="task-456",
        )

        # Flush CloudWatch metrics
        await mock_integration._cloudwatch_publisher.flush()

        # Should publish to EventBridge
        assert len(mock_integration._eventbridge_publisher.get_mock_events()) >= 1

    def test_get_stats(self, mock_integration):
        """Test getting comprehensive statistics."""
        stats = mock_integration.get_stats()

        assert "integration" in stats
        assert "config" in stats
        assert "cloudwatch" in stats
        assert "eventbridge" in stats
        assert "persistence" in stats

    def test_get_health(self, mock_integration):
        """Test getting health status."""
        health = mock_integration.get_health()

        assert health["status"] == "healthy"
        assert "components" in health
        assert "cloudwatch" in health["components"]
        assert "eventbridge" in health["components"]
        assert "persistence" in health["components"]


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory/singleton functions."""

    def test_get_cloudwatch_metrics_publisher(self):
        """Test singleton pattern for CloudWatch publisher."""
        from src.services.cloudwatch_metrics_publisher import (
            get_cloudwatch_metrics_publisher,
        )

        publisher1 = get_cloudwatch_metrics_publisher()
        publisher2 = get_cloudwatch_metrics_publisher()

        assert publisher1 is publisher2

    def test_get_eventbridge_publisher(self):
        """Test singleton pattern for EventBridge publisher."""
        from src.services.eventbridge_publisher import get_eventbridge_publisher

        publisher1 = get_eventbridge_publisher()
        publisher2 = get_eventbridge_publisher()

        assert publisher1 is publisher2

    def test_get_anomaly_persistence_service(self):
        """Test singleton pattern for persistence service."""
        from src.services.anomaly_persistence_service import (
            get_anomaly_persistence_service,
        )

        service1 = get_anomaly_persistence_service()
        service2 = get_anomaly_persistence_service()

        assert service1 is service2

    def test_get_realtime_monitoring_integration(self):
        """Test singleton pattern for integration service."""
        from src.services.realtime_monitoring_integration import (
            get_realtime_monitoring_integration,
        )

        integration1 = get_realtime_monitoring_integration()
        integration2 = get_realtime_monitoring_integration()

        assert integration1 is integration2


# =============================================================================
# Integration with AnomalyDetectionService Tests
# =============================================================================


class TestAnomalyDetectionIntegration:
    """Tests for integration with AnomalyDetectionService."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_anomaly):
        """Test the full pipeline from anomaly detection to monitoring."""
        from src.services.anomaly_detection_service import AnomalyDetectionService
        from src.services.anomaly_persistence_service import (
            AnomalyPersistenceService,
            PersistenceMode,
        )
        from src.services.cloudwatch_metrics_publisher import CloudWatchMetricsPublisher
        from src.services.cloudwatch_metrics_publisher import PublisherMode as CWMode
        from src.services.eventbridge_publisher import EventBridgePublisher
        from src.services.eventbridge_publisher import PublisherMode as EBMode
        from src.services.realtime_monitoring_integration import (
            IntegrationConfig,
            RealTimeMonitoringIntegration,
        )

        # Create mocked components
        cw_publisher = CloudWatchMetricsPublisher(mode=CWMode.MOCK)
        eb_publisher = EventBridgePublisher(mode=EBMode.MOCK)
        persistence = AnomalyPersistenceService(mode=PersistenceMode.MOCK)

        config = IntegrationConfig(enable_notifications=False)
        integration = RealTimeMonitoringIntegration(
            config=config,
            cloudwatch_publisher=cw_publisher,
            eventbridge_publisher=eb_publisher,
            persistence_service=persistence,
        )

        # Create anomaly detector and connect integration
        detector = AnomalyDetectionService()
        integration.connect(detector)

        # Manually trigger the callback with our sample anomaly
        await integration._handle_anomaly(sample_anomaly)

        # Verify all components received the anomaly
        assert cw_publisher.stats.metrics_published >= 1
        assert len(eb_publisher.get_mock_events()) >= 1
        assert persistence.stats.items_written >= 1

        # Verify the anomaly was persisted correctly
        record = await persistence.get_anomaly(sample_anomaly.id)
        assert record is not None
        assert record.title == sample_anomaly.title

    @pytest.mark.asyncio
    async def test_setup_realtime_monitoring(self):
        """Test the convenience setup function."""
        from src.services.anomaly_detection_service import AnomalyDetectionService
        from src.services.realtime_monitoring_integration import (
            setup_realtime_monitoring,
        )

        detector = AnomalyDetectionService()
        integration = setup_realtime_monitoring(detector)

        assert integration._anomaly_detector is detector
