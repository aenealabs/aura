"""
Tests for Anomaly Detection Service.

Tests real-time anomaly detection capabilities including:
- Statistical baseline calculation and anomaly detection
- Security event processing
- MetaOrchestrator integration
- External notification triggering
- Deduplication and lifecycle management
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.anomaly_detection_service import (
    AnomalyDetectionService,
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    MetricBaseline,
    create_anomaly_detector,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def detector():
    """Create a basic anomaly detector for testing."""
    return AnomalyDetectionService(
        baseline_window_hours=24,
        min_samples_for_baseline=10,  # Lower threshold for testing
        enable_notifications=True,
    )


@pytest.fixture
def detector_with_baseline(detector):
    """Create detector with pre-populated baseline."""
    # Simulate 20 normal metric readings (mean=100, small variance)
    for i in range(20):
        detector.record_metric(
            "api.latency_p95",
            100.0 + (i % 5) - 2,  # Values around 98-102
            check_anomaly=False,
        )

    # Also add error rate baseline
    for i in range(20):
        detector.record_metric(
            "api.error_rate",
            0.01 + (i % 3) * 0.002,  # Values around 0.01-0.014
            check_anomaly=False,
        )

    return detector


@pytest.fixture
def sample_cve_event():
    """Sample CVE security event."""
    return {
        "type": "new_cve",
        "cve_id": "CVE-2025-0001",
        "severity": "CRITICAL",
        "title": "Remote Code Execution in requests library",
        "description": "A critical RCE vulnerability in the requests library",
        "affected_components": ["requirements.txt", "src/utils/http.py"],
    }


@pytest.fixture
def sample_exploitation_event():
    """Sample known exploitation event."""
    return {
        "type": "known_exploitation",
        "cve_id": "CVE-2024-9999",
        "severity": "CRITICAL",
        "title": "Actively Exploited Vulnerability",
        "description": "CISA KEV indicates active exploitation in the wild",
        "affected_components": ["package-lock.json"],
    }


# =============================================================================
# Basic Initialization Tests
# =============================================================================


class TestAnomalyDetectionServiceInit:
    """Test service initialization."""

    def test_initialization(self, detector):
        """Test detector initializes with correct defaults."""
        assert detector.baseline_window_hours == 24
        assert detector.min_samples_for_baseline == 10
        assert detector.enable_notifications is True
        assert not detector._is_monitoring

    def test_default_rules_loaded(self, detector):
        """Test default detection rules are loaded."""
        assert len(detector._rules) > 0
        rule_ids = [r.id for r in detector._rules]
        assert "critical-cve" in rule_ids
        assert "known-exploitation" in rule_ids
        assert "sandbox-escape" in rule_ids

    def test_factory_function(self):
        """Test create_anomaly_detector factory."""
        detector = create_anomaly_detector(
            enable_notifications=False,
            baseline_window_hours=12,
        )
        assert detector.enable_notifications is False
        assert detector.baseline_window_hours == 12


# =============================================================================
# Metric Recording and Baseline Tests
# =============================================================================


class TestMetricRecording:
    """Test metric recording and baseline calculation."""

    def test_record_metric_stores_value(self, detector):
        """Test recording a metric stores it in the window."""
        detector.record_metric("test.metric", 100.0, check_anomaly=False)
        assert len(detector._metric_windows["test.metric"]) == 1

    def test_baseline_not_created_with_few_samples(self, detector):
        """Test baseline not created until min samples reached."""
        for i in range(5):  # Less than min_samples (10)
            detector.record_metric("test.metric", 100.0, check_anomaly=False)

        assert "test.metric" not in detector._baselines

    def test_baseline_created_with_enough_samples(self, detector):
        """Test baseline is created when min samples reached."""
        for i in range(15):  # More than min_samples (10)
            detector.record_metric("test.metric", 100.0 + i * 0.1, check_anomaly=False)

        assert "test.metric" in detector._baselines
        baseline = detector._baselines["test.metric"]
        assert baseline.sample_count >= 10  # At least min_samples
        assert 100.0 < baseline.mean < 101.5  # Mean around 100.x range

    def test_baseline_statistics(self, detector):
        """Test baseline calculates correct statistics."""
        values = [100, 102, 98, 101, 99, 100, 103, 97, 100, 101]
        for v in values:
            detector.record_metric("test.metric", v, check_anomaly=False)

        baseline = detector._baselines["test.metric"]
        assert abs(baseline.mean - 100.1) < 0.1
        assert baseline.min_value == 97
        assert baseline.max_value == 103
        assert baseline.median == 100.0


class TestAnomalyDetectionFromBaseline:
    """Test anomaly detection using statistical baselines."""

    def test_normal_value_not_flagged(self, detector_with_baseline):
        """Test normal values don't trigger anomaly."""
        result = detector_with_baseline.record_metric("api.latency_p95", 101.0)
        assert result is None  # No anomaly

    def test_extreme_value_triggers_anomaly(self, detector_with_baseline):
        """Test extreme value triggers anomaly."""
        # Value way outside normal range (mean~100, inject 500)
        result = detector_with_baseline.record_metric("api.latency_p95", 500.0)

        assert result is not None
        assert isinstance(result, AnomalyEvent)
        assert result.type == AnomalyType.LATENCY_SPIKE
        assert result.severity in (AnomalySeverity.MEDIUM, AnomalySeverity.HIGH)

    def test_high_error_rate_triggers_critical(self, detector_with_baseline):
        """Test high error rate triggers critical anomaly."""
        # Normal error rate ~0.01, inject 0.5 (50%)
        result = detector_with_baseline.record_metric("api.error_rate", 0.50)

        assert result is not None
        assert result.type == AnomalyType.ERROR_RATE_SURGE
        assert result.severity in (AnomalySeverity.HIGH, AnomalySeverity.CRITICAL)

    def test_z_score_in_metadata(self, detector_with_baseline):
        """Test z-score is included in anomaly metadata."""
        result = detector_with_baseline.record_metric("api.latency_p95", 1000.0)

        assert result is not None
        assert "z_score" in result.metadata
        assert result.metadata["z_score"] > 3.0  # Beyond threshold


class TestThresholdDetection:
    """Test anomaly detection using default thresholds."""

    def test_error_rate_threshold(self, detector):
        """Test error rate threshold detection before baseline."""
        # No baseline yet, should use default threshold (0.05)
        result = detector.record_metric("service.error_rate", 0.10)  # 10%

        assert result is not None
        assert result.type == AnomalyType.ERROR_RATE_SURGE

    def test_latency_threshold(self, detector):
        """Test latency threshold detection before baseline."""
        result = detector.record_metric("api.latency_p95_ms", 6000)  # 6 seconds

        assert result is not None
        assert result.type == AnomalyType.LATENCY_SPIKE

    def test_below_threshold_not_flagged(self, detector):
        """Test values below threshold not flagged."""
        result = detector.record_metric("service.error_rate", 0.02)  # 2%
        assert result is None


# =============================================================================
# Security Event Processing Tests
# =============================================================================


class TestSecurityEventProcessing:
    """Test security event processing."""

    @pytest.mark.asyncio
    async def test_critical_cve_creates_anomaly(self, detector, sample_cve_event):
        """Test critical CVE creates high-severity anomaly."""
        result = await detector.process_security_event(sample_cve_event)

        assert result is not None
        assert result.type == AnomalyType.NEW_CVE
        assert result.severity == AnomalySeverity.CRITICAL
        assert result.cve_id == "CVE-2025-0001"
        assert "requests library" in result.description

    @pytest.mark.asyncio
    async def test_exploitation_event(self, detector, sample_exploitation_event):
        """Test known exploitation creates critical anomaly."""
        result = await detector.process_security_event(sample_exploitation_event)

        assert result is not None
        assert result.type == AnomalyType.KNOWN_EXPLOITATION
        assert result.severity == AnomalySeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_medium_severity_event(self, detector):
        """Test medium severity event processing."""
        event = {
            "type": "dependency_vulnerability",
            "severity": "MEDIUM",
            "title": "Minor vulnerability in dev dependency",
            "description": "Non-critical issue in test library",
        }
        result = await detector.process_security_event(event)

        assert result is not None
        assert result.severity == AnomalySeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_affected_components_tracked(self, detector, sample_cve_event):
        """Test affected components are tracked."""
        result = await detector.process_security_event(sample_cve_event)

        assert result.affected_components == [
            "requirements.txt",
            "src/utils/http.py",
        ]

    @pytest.mark.asyncio
    async def test_recommended_action_generated(self, detector, sample_cve_event):
        """Test recommended action is generated."""
        result = await detector.process_security_event(sample_cve_event)

        assert result.recommended_action is not None
        assert "patch" in result.recommended_action.lower()


# =============================================================================
# Deduplication Tests
# =============================================================================


class TestDeduplication:
    """Test anomaly deduplication."""

    @pytest.mark.asyncio
    async def test_duplicate_suppressed(self, detector, sample_cve_event):
        """Test duplicate anomalies are suppressed."""
        # First event creates anomaly
        result1 = await detector.process_security_event(sample_cve_event)
        assert result1 is not None

        # Second identical event is suppressed
        result2 = await detector.process_security_event(sample_cve_event)
        assert result2 is None

    @pytest.mark.asyncio
    async def test_different_events_not_deduplicated(self, detector):
        """Test different events are not deduplicated."""
        event1 = {"type": "new_cve", "cve_id": "CVE-2025-0001", "severity": "HIGH"}
        event2 = {"type": "new_cve", "cve_id": "CVE-2025-0002", "severity": "HIGH"}

        result1 = await detector.process_security_event(event1)
        result2 = await detector.process_security_event(event2)

        assert result1 is not None
        assert result2 is not None
        assert result1.cve_id != result2.cve_id

    def test_metric_anomaly_deduplication(self, detector_with_baseline):
        """Test metric anomalies are deduplicated."""
        # First extreme value creates anomaly
        result1 = detector_with_baseline.record_metric("api.latency_p95", 500.0)
        assert result1 is not None

        # Immediate second extreme value is deduplicated
        result2 = detector_with_baseline.record_metric("api.latency_p95", 600.0)
        assert result2 is None

    def test_dedup_key_generation(self, detector):
        """Test dedup key is correctly generated."""
        event = AnomalyEvent(
            id="test-1",
            type=AnomalyType.NEW_CVE,
            severity=AnomalySeverity.CRITICAL,
            title="Test",
            description="Test",
            source="test",
            cve_id="CVE-2025-0001",
        )

        # CVE ID should be in dedup key
        assert "CVE-2025-0001" in event.dedup_key


# =============================================================================
# Callback and Notification Tests
# =============================================================================


class TestCallbacks:
    """Test anomaly callback system."""

    @pytest.mark.asyncio
    async def test_callback_registered_and_called(self, detector, sample_cve_event):
        """Test callbacks are called on anomaly detection."""
        callback_received = []

        def my_callback(event):
            callback_received.append(event)

        detector.on_anomaly(my_callback)
        await detector.process_security_event(sample_cve_event)

        # Give callbacks time to execute
        await asyncio.sleep(0.1)

        assert len(callback_received) == 1
        assert callback_received[0].cve_id == "CVE-2025-0001"

    @pytest.mark.asyncio
    async def test_async_callback_supported(self, detector, sample_cve_event):
        """Test async callbacks are supported."""
        callback_received = []

        async def my_async_callback(event):
            await asyncio.sleep(0.01)
            callback_received.append(event)

        detector.on_anomaly(my_async_callback)
        await detector.process_security_event(sample_cve_event)

        # Give async callbacks time to execute
        await asyncio.sleep(0.2)

        assert len(callback_received) == 1


class TestExternalNotifications:
    """Test external tool notifications."""

    @pytest.fixture
    def mock_slack(self):
        """Mock Slack connector."""
        mock = MagicMock()
        mock.send_security_alert = AsyncMock(return_value=MagicMock(success=True))
        return mock

    @pytest.fixture
    def mock_jira(self):
        """Mock Jira connector."""
        mock = MagicMock()
        mock.create_security_issue = AsyncMock(return_value=MagicMock(success=True))
        return mock

    @pytest.fixture
    def mock_pagerduty(self):
        """Mock PagerDuty connector."""
        mock = MagicMock()
        mock.trigger_security_incident = AsyncMock(return_value=MagicMock(success=True))
        return mock

    @pytest.mark.asyncio
    async def test_critical_notifies_all(
        self, detector, mock_slack, mock_jira, mock_pagerduty
    ):
        """Test critical anomaly notifies all channels."""
        anomaly = AnomalyEvent(
            id="test-1",
            type=AnomalyType.NEW_CVE,
            severity=AnomalySeverity.CRITICAL,
            title="Critical Vulnerability",
            description="Test description",
            source="test",
            cve_id="CVE-2025-0001",
        )

        results = await detector.send_notifications(
            anomaly,
            slack_connector=mock_slack,
            jira_connector=mock_jira,
            pagerduty_connector=mock_pagerduty,
        )

        assert results["slack"] is True
        assert results["jira"] is True
        assert results["pagerduty"] is True

        mock_slack.send_security_alert.assert_called_once()
        mock_jira.create_security_issue.assert_called_once()
        mock_pagerduty.trigger_security_incident.assert_called_once()

    @pytest.mark.asyncio
    async def test_high_skips_pagerduty(
        self, detector, mock_slack, mock_jira, mock_pagerduty
    ):
        """Test HIGH severity doesn't trigger PagerDuty."""
        anomaly = AnomalyEvent(
            id="test-1",
            type=AnomalyType.ERROR_RATE_SURGE,
            severity=AnomalySeverity.HIGH,
            title="Error Rate Surge",
            description="Test",
            source="test",
        )

        results = await detector.send_notifications(
            anomaly,
            slack_connector=mock_slack,
            jira_connector=mock_jira,
            pagerduty_connector=mock_pagerduty,
        )

        assert "slack" in results
        assert "jira" in results
        assert "pagerduty" not in results  # Not called for HIGH

        mock_pagerduty.trigger_security_incident.assert_not_called()

    @pytest.mark.asyncio
    async def test_low_severity_skips_notifications(
        self, detector, mock_slack, mock_jira, mock_pagerduty
    ):
        """Test LOW severity doesn't send any notifications."""
        anomaly = AnomalyEvent(
            id="test-1",
            type=AnomalyType.PATTERN_MATCH,
            severity=AnomalySeverity.LOW,
            title="Low Priority Event",
            description="Test",
            source="test",
        )

        results = await detector.send_notifications(
            anomaly,
            slack_connector=mock_slack,
            jira_connector=mock_jira,
            pagerduty_connector=mock_pagerduty,
        )

        assert results == {}
        mock_slack.send_security_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_notifications_disabled(self, mock_slack, mock_jira, mock_pagerduty):
        """Test notifications can be disabled."""
        detector = AnomalyDetectionService(enable_notifications=False)

        anomaly = AnomalyEvent(
            id="test-1",
            type=AnomalyType.NEW_CVE,
            severity=AnomalySeverity.CRITICAL,
            title="Critical Vulnerability",
            description="Test",
            source="test",
        )

        results = await detector.send_notifications(
            anomaly,
            slack_connector=mock_slack,
        )

        assert results == {}
        mock_slack.send_security_alert.assert_not_called()


# =============================================================================
# MetaOrchestrator Integration Tests
# =============================================================================


class TestOrchestratorIntegration:
    """Test MetaOrchestrator triggering."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock MetaOrchestrator."""
        mock = MagicMock()
        result = MagicMock()
        result.success = True
        result.task_id = "task-123"
        result.hitl_required = False
        mock.execute = AsyncMock(return_value=result)
        return mock

    @pytest.fixture
    def mock_orchestrator_hitl(self):
        """Mock MetaOrchestrator that requires HITL."""
        mock = MagicMock()
        result = MagicMock()
        result.success = True
        result.task_id = "task-456"
        result.hitl_required = True
        result.hitl_request_id = "hitl-789"
        mock.execute = AsyncMock(return_value=result)
        return mock

    @pytest.mark.asyncio
    async def test_trigger_orchestrator_success(
        self, detector, mock_orchestrator, sample_cve_event
    ):
        """Test triggering orchestrator for anomaly."""
        anomaly = await detector.process_security_event(sample_cve_event)

        result = await detector.trigger_orchestrator(anomaly, mock_orchestrator)

        assert result["success"] is True
        assert result["task_id"] == "task-123"
        assert anomaly.status == AnomalyStatus.RESOLVED

        # Verify orchestrator was called with correct parameters
        mock_orchestrator.execute.assert_called_once()
        call_kwargs = mock_orchestrator.execute.call_args.kwargs
        assert "CRITICAL" in call_kwargs["severity"]
        assert "CVE-2025-0001" in call_kwargs["context"]["cve_id"]

    @pytest.mark.asyncio
    async def test_trigger_orchestrator_hitl_required(
        self, detector, mock_orchestrator_hitl, sample_cve_event
    ):
        """Test orchestrator response requiring HITL."""
        anomaly = await detector.process_security_event(sample_cve_event)

        result = await detector.trigger_orchestrator(anomaly, mock_orchestrator_hitl)

        assert result["success"] is True
        assert result["hitl_required"] is True
        assert result["hitl_approval_id"] == "hitl-789"
        assert anomaly.status == AnomalyStatus.INVESTIGATING
        assert anomaly.hitl_approval_id == "hitl-789"

    @pytest.mark.asyncio
    async def test_orchestrator_task_built_correctly(
        self, detector, mock_orchestrator, sample_cve_event
    ):
        """Test task description is built correctly."""
        anomaly = await detector.process_security_event(sample_cve_event)
        await detector.trigger_orchestrator(anomaly, mock_orchestrator)

        call_kwargs = mock_orchestrator.execute.call_args.kwargs
        task = call_kwargs["task"]

        assert "CVE-2025-0001" in task
        assert "patch" in task.lower() or "analyze" in task.lower()


# =============================================================================
# Anomaly Lifecycle Tests
# =============================================================================


class TestAnomalyLifecycle:
    """Test anomaly lifecycle management."""

    @pytest.mark.asyncio
    async def test_get_active_anomalies(self, detector, sample_cve_event):
        """Test getting active anomalies."""
        await detector.process_security_event(sample_cve_event)
        await detector.process_security_event(
            {
                "type": "new_cve",
                "cve_id": "CVE-2025-0002",
                "severity": "HIGH",
            }
        )

        active = detector.get_active_anomalies()
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_resolve_anomaly(self, detector, sample_cve_event):
        """Test resolving an anomaly."""
        anomaly = await detector.process_security_event(sample_cve_event)
        dedup_key = anomaly.dedup_key

        detector.resolve_anomaly(dedup_key, "Patch applied")

        resolved = detector.get_anomaly(dedup_key)
        assert resolved.status == AnomalyStatus.RESOLVED
        assert "Patch applied" in resolved.metadata["resolution"]

    @pytest.mark.asyncio
    async def test_dismiss_anomaly(self, detector, sample_cve_event):
        """Test dismissing an anomaly."""
        anomaly = await detector.process_security_event(sample_cve_event)
        dedup_key = anomaly.dedup_key

        detector.dismiss_anomaly(dedup_key, "Not applicable to our stack")

        dismissed = detector.get_anomaly(dedup_key)
        assert dismissed.status == AnomalyStatus.DISMISSED

    @pytest.mark.asyncio
    async def test_resolved_not_in_active(self, detector, sample_cve_event):
        """Test resolved anomalies not in active list."""
        anomaly = await detector.process_security_event(sample_cve_event)
        detector.resolve_anomaly(anomaly.dedup_key)

        active = detector.get_active_anomalies()
        assert len(active) == 0


# =============================================================================
# Statistics Tests
# =============================================================================


class TestStatistics:
    """Test statistics tracking."""

    @pytest.mark.asyncio
    async def test_statistics_tracked(self, detector, sample_cve_event):
        """Test statistics are tracked correctly."""
        await detector.process_security_event(sample_cve_event)

        stats = detector.get_statistics()
        assert stats["total_anomalies_detected"] == 1
        assert stats["anomalies_by_type"]["new_cve"] == 1
        assert stats["anomalies_by_severity"]["critical"] == 1

    @pytest.mark.asyncio
    async def test_orchestrator_trigger_counted(self, detector, sample_cve_event):
        """Test orchestrator triggers are counted."""
        mock_orchestrator = MagicMock()
        result = MagicMock()
        result.success = True
        result.task_id = "task-123"
        result.hitl_required = False
        mock_orchestrator.execute = AsyncMock(return_value=result)

        anomaly = await detector.process_security_event(sample_cve_event)
        await detector.trigger_orchestrator(anomaly, mock_orchestrator)

        stats = detector.get_statistics()
        assert stats["orchestrator_triggers"] == 1

    @pytest.mark.asyncio
    async def test_false_positive_counted(self, detector, sample_cve_event):
        """Test false positives are counted."""
        anomaly = await detector.process_security_event(sample_cve_event)
        detector.dismiss_anomaly(anomaly.dedup_key, "false_positive")

        stats = detector.get_statistics()
        assert stats["false_positives_dismissed"] == 1


# =============================================================================
# Monitoring Loop Tests
# =============================================================================


class TestMonitoringLoop:
    """Test background monitoring loop."""

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, detector):
        """Test starting and stopping monitoring loop."""
        assert not detector._is_monitoring

        await detector.start_monitoring(check_interval_seconds=1)
        assert detector._is_monitoring

        await detector.stop_monitoring()
        assert not detector._is_monitoring

    @pytest.mark.asyncio
    async def test_monitoring_checks_observability(self, detector):
        """Test monitoring loop checks observability service."""
        mock_obs = MagicMock()
        mock_obs.get_health_report.return_value = {
            "golden_signals": {
                "errors": {"error_rate": 0.02},
                "latency": {"p95_ms": 150},
                "saturation": {"cpu_percent": 50},
            }
        }

        await detector.start_monitoring(
            observability_service=mock_obs,
            check_interval_seconds=0.1,
        )

        await asyncio.sleep(0.3)  # Allow a few checks
        await detector.stop_monitoring()

        # Verify observability was checked
        assert mock_obs.get_health_report.call_count >= 1

    @pytest.mark.asyncio
    async def test_duplicate_start_prevented(self, detector):
        """Test duplicate monitoring start is prevented."""
        await detector.start_monitoring(check_interval_seconds=1)
        await detector.start_monitoring(check_interval_seconds=1)  # Should be no-op

        # Still only one monitoring task
        assert detector._monitoring_task is not None
        await detector.stop_monitoring()


# =============================================================================
# MetricBaseline Model Tests
# =============================================================================


class TestMetricBaseline:
    """Test MetricBaseline dataclass."""

    def test_is_anomaly_detection(self):
        """Test anomaly detection using Z-score."""
        baseline = MetricBaseline(
            metric_name="test",
            mean=100.0,
            std_dev=10.0,
            median=100.0,
            min_value=80.0,
            max_value=120.0,
            sample_count=100,
        )

        # Normal value (within 3 sigma)
        is_anomaly, z_score = baseline.is_anomaly(110.0)
        assert is_anomaly is False
        assert z_score == 1.0

        # Anomalous value (beyond 3 sigma)
        is_anomaly, z_score = baseline.is_anomaly(150.0)
        assert is_anomaly is True
        assert z_score == 5.0

    def test_zero_std_dev_handled(self):
        """Test zero std dev doesn't cause division error."""
        baseline = MetricBaseline(
            metric_name="test",
            mean=100.0,
            std_dev=0.0,  # All values identical
            median=100.0,
            min_value=100.0,
            max_value=100.0,
            sample_count=100,
        )

        is_anomaly, z_score = baseline.is_anomaly(100.0)
        assert is_anomaly is False
        assert z_score == 0.0
