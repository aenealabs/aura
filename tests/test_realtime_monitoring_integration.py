"""
Tests for Project Aura - Real-Time Monitoring Integration

Comprehensive tests for the orchestration between anomaly detection
and monitoring systems (CloudWatch, EventBridge, DynamoDB).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.realtime_monitoring_integration import (
    IntegrationConfig,
    IntegrationMode,
    IntegrationStats,
    RealTimeMonitoringIntegration,
    create_realtime_monitoring_integration,
    get_realtime_monitoring_integration,
    setup_realtime_monitoring,
    severity_meets_threshold,
)

# =============================================================================
# IntegrationMode Enum Tests
# =============================================================================


class TestIntegrationMode:
    """Tests for IntegrationMode enum."""

    def test_full(self):
        """Test FULL mode."""
        assert IntegrationMode.FULL.value == "full"

    def test_minimal(self):
        """Test MINIMAL mode."""
        assert IntegrationMode.MINIMAL.value == "minimal"

    def test_mock(self):
        """Test MOCK mode."""
        assert IntegrationMode.MOCK.value == "mock"

    def test_all_modes_exist(self):
        """Test all expected modes are defined."""
        expected = {"full", "minimal", "mock"}
        actual = {m.value for m in IntegrationMode}
        assert actual == expected


# =============================================================================
# IntegrationConfig Tests
# =============================================================================


class TestIntegrationConfig:
    """Tests for IntegrationConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = IntegrationConfig()

        assert config.enable_cloudwatch is True
        assert config.enable_eventbridge is True
        assert config.enable_persistence is True
        assert config.enable_notifications is True
        assert config.persist_all_severities is True
        assert config.notify_min_severity == "medium"
        assert config.eventbridge_min_severity == "low"
        assert config.batch_metrics is True
        assert config.metrics_flush_interval == 60

    def test_custom_config(self):
        """Test custom configuration values."""
        config = IntegrationConfig(
            enable_cloudwatch=False,
            enable_notifications=False,
            notify_min_severity="high",
            metrics_flush_interval=30,
        )

        assert config.enable_cloudwatch is False
        assert config.enable_notifications is False
        assert config.notify_min_severity == "high"
        assert config.metrics_flush_interval == 30

    @patch.dict(
        "os.environ",
        {
            "ENABLE_CLOUDWATCH_METRICS": "false",
            "ENABLE_EVENTBRIDGE": "true",
            "ENABLE_ANOMALY_PERSISTENCE": "false",
            "ENABLE_NOTIFICATIONS": "true",
            "PERSIST_ALL_SEVERITIES": "false",
            "NOTIFY_MIN_SEVERITY": "critical",
            "EVENTBRIDGE_MIN_SEVERITY": "medium",
        },
    )
    def test_from_environment(self):
        """Test loading config from environment variables."""
        config = IntegrationConfig.from_environment()

        assert config.enable_cloudwatch is False
        assert config.enable_eventbridge is True
        assert config.enable_persistence is False
        assert config.enable_notifications is True
        assert config.persist_all_severities is False
        assert config.notify_min_severity == "critical"
        assert config.eventbridge_min_severity == "medium"


# =============================================================================
# IntegrationStats Tests
# =============================================================================


class TestIntegrationStats:
    """Tests for IntegrationStats dataclass."""

    def test_default_stats(self):
        """Test default statistics values."""
        stats = IntegrationStats()

        assert stats.anomalies_processed == 0
        assert stats.cloudwatch_published == 0
        assert stats.eventbridge_published == 0
        assert stats.persistence_written == 0
        assert stats.notifications_sent == 0
        assert stats.errors == 0
        assert stats.last_anomaly_time is None
        assert stats.startup_time is not None

    def test_custom_stats(self):
        """Test custom statistics values."""
        now = datetime.now(timezone.utc)
        stats = IntegrationStats(
            anomalies_processed=100,
            cloudwatch_published=90,
            eventbridge_published=85,
            persistence_written=95,
            notifications_sent=50,
            errors=5,
            last_anomaly_time=now,
        )

        assert stats.anomalies_processed == 100
        assert stats.cloudwatch_published == 90
        assert stats.errors == 5
        assert stats.last_anomaly_time == now


# =============================================================================
# severity_meets_threshold Tests
# =============================================================================


class TestSeverityMeetsThreshold:
    """Tests for severity_meets_threshold function."""

    def test_critical_meets_all(self):
        """Test critical meets all thresholds."""
        assert severity_meets_threshold("critical", "info") is True
        assert severity_meets_threshold("critical", "low") is True
        assert severity_meets_threshold("critical", "medium") is True
        assert severity_meets_threshold("critical", "high") is True
        assert severity_meets_threshold("critical", "critical") is True

    def test_high_meets_up_to_high(self):
        """Test high meets thresholds up to high."""
        assert severity_meets_threshold("high", "info") is True
        assert severity_meets_threshold("high", "low") is True
        assert severity_meets_threshold("high", "medium") is True
        assert severity_meets_threshold("high", "high") is True
        assert severity_meets_threshold("high", "critical") is False

    def test_medium_meets_up_to_medium(self):
        """Test medium meets thresholds up to medium."""
        assert severity_meets_threshold("medium", "info") is True
        assert severity_meets_threshold("medium", "low") is True
        assert severity_meets_threshold("medium", "medium") is True
        assert severity_meets_threshold("medium", "high") is False
        assert severity_meets_threshold("medium", "critical") is False

    def test_low_meets_up_to_low(self):
        """Test low meets thresholds up to low."""
        assert severity_meets_threshold("low", "info") is True
        assert severity_meets_threshold("low", "low") is True
        assert severity_meets_threshold("low", "medium") is False
        assert severity_meets_threshold("low", "high") is False

    def test_info_only_meets_info(self):
        """Test info only meets info threshold."""
        assert severity_meets_threshold("info", "info") is True
        assert severity_meets_threshold("info", "low") is False
        assert severity_meets_threshold("info", "medium") is False

    def test_case_insensitive(self):
        """Test severity comparison is case insensitive."""
        assert severity_meets_threshold("HIGH", "low") is True
        assert severity_meets_threshold("high", "LOW") is True
        assert severity_meets_threshold("CRITICAL", "MEDIUM") is True

    def test_unknown_severity_returns_true(self):
        """Test unknown severity defaults to True."""
        assert severity_meets_threshold("unknown", "medium") is True
        assert severity_meets_threshold("high", "unknown") is True


# =============================================================================
# RealTimeMonitoringIntegration Initialization Tests
# =============================================================================


class TestRealTimeMonitoringIntegrationInit:
    """Tests for RealTimeMonitoringIntegration initialization."""

    def test_init_default(self):
        """Test default initialization."""
        integration = RealTimeMonitoringIntegration()

        assert integration.config is not None
        assert integration.stats is not None
        assert integration._cloudwatch_publisher is None
        assert integration._eventbridge_publisher is None
        assert integration._persistence_service is None
        assert integration._anomaly_detector is None
        assert integration._running is False

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = IntegrationConfig(
            enable_cloudwatch=False,
            enable_notifications=False,
        )
        integration = RealTimeMonitoringIntegration(config=config)

        assert integration.config.enable_cloudwatch is False
        assert integration.config.enable_notifications is False

    def test_init_with_publishers(self):
        """Test initialization with pre-configured publishers."""
        mock_cloudwatch = MagicMock()
        mock_eventbridge = MagicMock()
        mock_persistence = MagicMock()

        integration = RealTimeMonitoringIntegration(
            cloudwatch_publisher=mock_cloudwatch,
            eventbridge_publisher=mock_eventbridge,
            persistence_service=mock_persistence,
        )

        assert integration._cloudwatch_publisher == mock_cloudwatch
        assert integration._eventbridge_publisher == mock_eventbridge
        assert integration._persistence_service == mock_persistence


# =============================================================================
# RealTimeMonitoringIntegration Connection Tests
# =============================================================================


class TestRealTimeMonitoringIntegrationConnection:
    """Tests for connection management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.integration = RealTimeMonitoringIntegration()

    def test_connect(self):
        """Test connecting to anomaly detector."""
        mock_detector = MagicMock()

        self.integration.connect(mock_detector)

        assert self.integration._anomaly_detector == mock_detector
        mock_detector.on_anomaly.assert_called_once()

    def test_connect_already_connected(self):
        """Test connecting when already connected."""
        mock_detector1 = MagicMock()
        mock_detector2 = MagicMock()

        self.integration.connect(mock_detector1)
        self.integration.connect(mock_detector2)

        # Should still be connected to first detector
        assert self.integration._anomaly_detector == mock_detector1

    def test_disconnect(self):
        """Test disconnecting from anomaly detector."""
        mock_detector = MagicMock()
        self.integration.connect(mock_detector)

        self.integration.disconnect()

        assert self.integration._anomaly_detector is None


# =============================================================================
# RealTimeMonitoringIntegration Lifecycle Tests
# =============================================================================


class TestRealTimeMonitoringIntegrationLifecycle:
    """Tests for lifecycle management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = IntegrationConfig(
            enable_cloudwatch=True,
            batch_metrics=True,
        )
        self.mock_cloudwatch = MagicMock()
        self.mock_cloudwatch.flush = AsyncMock()

        self.integration = RealTimeMonitoringIntegration(
            config=self.config,
            cloudwatch_publisher=self.mock_cloudwatch,
        )

    @pytest.mark.asyncio
    async def test_start(self):
        """Test starting the integration."""
        await self.integration.start()

        assert self.integration._running is True

        # Clean up
        await self.integration.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test starting when already running."""
        await self.integration.start()
        await self.integration.start()  # Should not error

        assert self.integration._running is True

        await self.integration.stop()

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping the integration."""
        await self.integration.start()
        await self.integration.stop()

        assert self.integration._running is False
        self.mock_cloudwatch.flush.assert_called()


# =============================================================================
# RealTimeMonitoringIntegration Anomaly Handling Tests
# =============================================================================


class TestRealTimeMonitoringIntegrationAnomalyHandling:
    """Tests for anomaly handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cloudwatch = MagicMock()
        self.mock_cloudwatch.publish_anomaly = AsyncMock(return_value=True)

        self.mock_eventbridge = MagicMock()
        self.mock_eventbridge.publish_anomaly_event = AsyncMock(return_value=True)

        self.mock_persistence = MagicMock()
        self.mock_persistence.persist_anomaly = AsyncMock(return_value=True)

        self.config = IntegrationConfig(
            enable_cloudwatch=True,
            enable_eventbridge=True,
            enable_persistence=True,
            enable_notifications=False,  # Disable to avoid import issues
        )

        self.integration = RealTimeMonitoringIntegration(
            config=self.config,
            cloudwatch_publisher=self.mock_cloudwatch,
            eventbridge_publisher=self.mock_eventbridge,
            persistence_service=self.mock_persistence,
        )

    def _create_mock_anomaly(self, severity: str = "medium"):
        """Create a mock anomaly event."""
        mock_anomaly = MagicMock()
        mock_anomaly.severity = MagicMock()
        mock_anomaly.severity.value = severity
        mock_anomaly.id = "anomaly-123"
        mock_anomaly.title = "Test Anomaly"
        mock_anomaly.type = MagicMock()
        mock_anomaly.type.value = "security"
        mock_anomaly.source = "test"
        mock_anomaly.description = "Test description"
        return mock_anomaly

    @pytest.mark.asyncio
    async def test_handle_anomaly_all_publishers(self):
        """Test handling anomaly with all publishers enabled."""
        anomaly = self._create_mock_anomaly("high")

        await self.integration._handle_anomaly(anomaly)

        assert self.integration.stats.anomalies_processed == 1
        self.mock_cloudwatch.publish_anomaly.assert_called_once()
        self.mock_eventbridge.publish_anomaly_event.assert_called_once()
        self.mock_persistence.persist_anomaly.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_anomaly_updates_stats(self):
        """Test that handling anomaly updates statistics."""
        anomaly = self._create_mock_anomaly()

        await self.integration._handle_anomaly(anomaly)

        assert self.integration.stats.anomalies_processed == 1
        assert self.integration.stats.cloudwatch_published == 1
        assert self.integration.stats.eventbridge_published == 1
        assert self.integration.stats.persistence_written == 1
        assert self.integration.stats.last_anomaly_time is not None

    @pytest.mark.asyncio
    async def test_handle_anomaly_severity_filtering(self):
        """Test severity-based filtering for EventBridge."""
        self.integration.config.eventbridge_min_severity = "high"

        anomaly = self._create_mock_anomaly("low")
        await self.integration._handle_anomaly(anomaly)

        # EventBridge should NOT be called for low severity
        self.mock_eventbridge.publish_anomaly_event.assert_not_called()
        # But CloudWatch should still be called
        self.mock_cloudwatch.publish_anomaly.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_anomaly_publisher_error(self):
        """Test handling anomaly when publisher fails."""
        self.mock_cloudwatch.publish_anomaly = AsyncMock(
            side_effect=Exception("CloudWatch error")
        )

        anomaly = self._create_mock_anomaly()
        await self.integration._handle_anomaly(anomaly)

        assert self.integration.stats.errors >= 1


# =============================================================================
# RealTimeMonitoringIntegration Orchestrator Event Tests
# =============================================================================


class TestRealTimeMonitoringIntegrationOrchestratorEvents:
    """Tests for orchestrator event publishing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cloudwatch = MagicMock()
        self.mock_cloudwatch.publish_orchestrator_event = AsyncMock()
        self.mock_cloudwatch.publish_metric = AsyncMock()

        self.mock_eventbridge = MagicMock()
        self.mock_eventbridge.publish_orchestrator_event = AsyncMock()
        self.mock_eventbridge.publish_hitl_event = AsyncMock()

        self.config = IntegrationConfig(
            enable_cloudwatch=True,
            enable_eventbridge=True,
        )

        self.integration = RealTimeMonitoringIntegration(
            config=self.config,
            cloudwatch_publisher=self.mock_cloudwatch,
            eventbridge_publisher=self.mock_eventbridge,
        )

    @pytest.mark.asyncio
    async def test_publish_orchestrator_started(self):
        """Test publishing orchestrator started event."""
        await self.integration.publish_orchestrator_started(
            task_id="task-123",
            anomaly_id="anomaly-456",
            task_type="investigate",
        )

        self.mock_cloudwatch.publish_orchestrator_event.assert_called_once()
        self.mock_eventbridge.publish_orchestrator_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_orchestrator_completed(self):
        """Test publishing orchestrator completed event."""
        await self.integration.publish_orchestrator_completed(
            task_id="task-123",
            anomaly_id="anomaly-456",
            success=True,
            duration_seconds=30.5,
        )

        self.mock_cloudwatch.publish_orchestrator_event.assert_called_once()
        self.mock_eventbridge.publish_orchestrator_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_hitl_approval_required(self):
        """Test publishing HITL approval required event."""
        await self.integration.publish_hitl_approval_required(
            approval_id="approval-123",
            task_id="task-456",
            task_type="remediate",
        )

        self.mock_cloudwatch.publish_metric.assert_called_once()
        self.mock_eventbridge.publish_hitl_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_hitl_decision(self):
        """Test publishing HITL decision event."""
        await self.integration.publish_hitl_decision(
            approval_id="approval-123",
            decision="approved",
            reviewer="admin@example.com",
            task_id="task-456",
        )

        self.mock_cloudwatch.publish_metric.assert_called_once()
        self.mock_eventbridge.publish_hitl_event.assert_called_once()


# =============================================================================
# RealTimeMonitoringIntegration Statistics Tests
# =============================================================================


class TestRealTimeMonitoringIntegrationStats:
    """Tests for statistics and health."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_cloudwatch = MagicMock()
        self.mock_cloudwatch.get_stats = MagicMock(
            return_value={
                "mode": "aws",
                "metrics_published": 100,
                "publish_errors": 2,
            }
        )

        self.mock_eventbridge = MagicMock()
        self.mock_eventbridge.get_stats = MagicMock(
            return_value={
                "mode": "aws",
                "events_published": 50,
                "events_failed": 1,
            }
        )

        self.integration = RealTimeMonitoringIntegration(
            cloudwatch_publisher=self.mock_cloudwatch,
            eventbridge_publisher=self.mock_eventbridge,
        )

    def test_get_stats(self):
        """Test getting comprehensive statistics."""
        self.integration.stats.anomalies_processed = 100
        self.integration.stats.cloudwatch_published = 90
        self.integration.stats.errors = 5

        stats = self.integration.get_stats()

        assert "integration" in stats
        assert stats["integration"]["anomalies_processed"] == 100
        assert stats["integration"]["cloudwatch_published"] == 90
        assert stats["integration"]["errors"] == 5
        assert "config" in stats
        assert "cloudwatch" in stats
        assert "eventbridge" in stats

    def test_get_stats_uptime(self):
        """Test that stats include uptime."""
        stats = self.integration.get_stats()

        assert stats["integration"]["uptime_seconds"] >= 0

    def test_get_health(self):
        """Test getting health status."""
        health = self.integration.get_health()

        assert health["status"] == "healthy"
        assert "components" in health

    def test_get_health_cloudwatch_component(self):
        """Test CloudWatch component health."""
        health = self.integration.get_health()

        assert "cloudwatch" in health["components"]
        cw = health["components"]["cloudwatch"]
        assert cw["enabled"] is True
        assert cw["mode"] == "aws"
        assert cw["published"] == 100

    def test_get_health_degraded_on_errors(self):
        """Test health status becomes degraded on many errors."""
        self.mock_cloudwatch.get_stats = MagicMock(
            return_value={
                "mode": "aws",
                "metrics_published": 100,
                "publish_errors": 15,  # More than 10 errors
            }
        )

        health = self.integration.get_health()

        assert health["status"] == "degraded"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def teardown_method(self):
        """Reset singleton after each test."""
        import src.services.realtime_monitoring_integration as module

        module._integration_instance = None

    def test_get_realtime_monitoring_integration(self):
        """Test getting singleton instance."""
        integration1 = get_realtime_monitoring_integration()
        integration2 = get_realtime_monitoring_integration()

        assert integration1 is integration2
        assert isinstance(integration1, RealTimeMonitoringIntegration)

    def test_create_realtime_monitoring_integration(self):
        """Test creating new instance."""
        config = IntegrationConfig(enable_notifications=False)
        mock_cloudwatch = MagicMock()

        integration = create_realtime_monitoring_integration(
            config=config,
            cloudwatch_publisher=mock_cloudwatch,
        )

        assert integration.config.enable_notifications is False
        assert integration._cloudwatch_publisher == mock_cloudwatch

    def test_setup_realtime_monitoring(self):
        """Test quick setup function."""
        mock_detector = MagicMock()

        integration = setup_realtime_monitoring(mock_detector)

        assert integration._anomaly_detector == mock_detector
        mock_detector.on_anomaly.assert_called_once()


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_disabled_publishers_not_initialized(self):
        """Test that disabled publishers are not initialized."""
        config = IntegrationConfig(
            enable_cloudwatch=False,
            enable_eventbridge=False,
            enable_persistence=False,
        )
        integration = RealTimeMonitoringIntegration(config=config)

        # Access the lazy properties - should remain None
        assert integration._cloudwatch_publisher is None
        assert integration._eventbridge_publisher is None
        assert integration._persistence_service is None

    @pytest.mark.asyncio
    async def test_handle_anomaly_with_no_publishers(self):
        """Test handling anomaly with all publishers disabled."""
        config = IntegrationConfig(
            enable_cloudwatch=False,
            enable_eventbridge=False,
            enable_persistence=False,
            enable_notifications=False,
        )
        integration = RealTimeMonitoringIntegration(config=config)

        mock_anomaly = MagicMock()
        mock_anomaly.severity = MagicMock()
        mock_anomaly.severity.value = "high"

        # Should not raise
        await integration._handle_anomaly(mock_anomaly)

        assert integration.stats.anomalies_processed == 1

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """Test stopping without starting first."""
        integration = RealTimeMonitoringIntegration()

        # Should not raise
        await integration.stop()

        assert integration._running is False

    def test_stats_last_anomaly_time_none_in_output(self):
        """Test that None last_anomaly_time is handled in get_stats."""
        integration = RealTimeMonitoringIntegration()
        stats = integration.get_stats()

        assert stats["integration"]["last_anomaly_time"] is None

    def test_health_with_no_initialized_publishers(self):
        """Test health check with no initialized publishers."""
        integration = RealTimeMonitoringIntegration()
        health = integration.get_health()

        assert health["status"] == "healthy"
        # Components should still be reported as enabled but with unknown mode
        if integration.config.enable_cloudwatch:
            assert health["components"]["cloudwatch"]["mode"] == "unknown"
