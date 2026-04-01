"""
Tests for Project Aura - Production Observability Service

Comprehensive tests for the Four Golden Signals monitoring:
- Latency tracking
- Traffic (request rate) tracking
- Error rate tracking
- Saturation (resource usage) tracking
"""

import time
from datetime import datetime, timezone

import pytest

from src.services.observability_service import (
    Alert,
    AlertSeverity,
    Metric,
    ObservabilityService,
    ServiceHealth,
    get_monitor,
    monitored,
)

# =============================================================================
# ServiceHealth Enum Tests
# =============================================================================


class TestServiceHealth:
    """Tests for ServiceHealth enum."""

    def test_healthy(self):
        """Test HEALTHY status."""
        assert ServiceHealth.HEALTHY.value == "healthy"

    def test_degraded(self):
        """Test DEGRADED status."""
        assert ServiceHealth.DEGRADED.value == "degraded"

    def test_unhealthy(self):
        """Test UNHEALTHY status."""
        assert ServiceHealth.UNHEALTHY.value == "unhealthy"

    def test_unknown(self):
        """Test UNKNOWN status."""
        assert ServiceHealth.UNKNOWN.value == "unknown"

    def test_all_health_statuses_exist(self):
        """Test all expected health statuses are defined."""
        expected = {"healthy", "degraded", "unhealthy", "unknown"}
        actual = {h.value for h in ServiceHealth}
        assert actual == expected


# =============================================================================
# AlertSeverity Enum Tests
# =============================================================================


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_critical(self):
        """Test CRITICAL severity."""
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_high(self):
        """Test HIGH severity."""
        assert AlertSeverity.HIGH.value == "high"

    def test_medium(self):
        """Test MEDIUM severity."""
        assert AlertSeverity.MEDIUM.value == "medium"

    def test_low(self):
        """Test LOW severity."""
        assert AlertSeverity.LOW.value == "low"

    def test_info(self):
        """Test INFO severity."""
        assert AlertSeverity.INFO.value == "info"

    def test_all_severities_exist(self):
        """Test all expected severities are defined."""
        expected = {"critical", "high", "medium", "low", "info"}
        actual = {s.value for s in AlertSeverity}
        assert actual == expected


# =============================================================================
# Metric Dataclass Tests
# =============================================================================


class TestMetric:
    """Tests for Metric dataclass."""

    def test_minimal_metric(self):
        """Test minimal metric creation."""
        metric = Metric(name="cpu_usage", value=75.5, unit="percent")

        assert metric.name == "cpu_usage"
        assert metric.value == 75.5
        assert metric.unit == "percent"
        assert metric.timestamp is not None
        assert metric.tags == {}

    def test_full_metric(self):
        """Test full metric creation."""
        now = datetime.now(timezone.utc)
        metric = Metric(
            name="request_latency",
            value=150.0,
            unit="ms",
            timestamp=now,
            tags={"endpoint": "/api/v1/scan", "method": "POST"},
        )

        assert metric.name == "request_latency"
        assert metric.value == 150.0
        assert metric.timestamp == now
        assert metric.tags["endpoint"] == "/api/v1/scan"


# =============================================================================
# Alert Dataclass Tests
# =============================================================================


class TestAlert:
    """Tests for Alert dataclass."""

    def test_minimal_alert(self):
        """Test minimal alert creation."""
        alert = Alert(
            severity=AlertSeverity.HIGH,
            service="neptune",
            message="Connection timeout",
        )

        assert alert.severity == AlertSeverity.HIGH
        assert alert.service == "neptune"
        assert alert.message == "Connection timeout"
        assert alert.timestamp is not None
        assert alert.metadata == {}

    def test_full_alert(self):
        """Test full alert creation."""
        now = datetime.now(timezone.utc)
        alert = Alert(
            severity=AlertSeverity.CRITICAL,
            service="orchestrator",
            message="Service unavailable",
            timestamp=now,
            metadata={"error_code": 503, "region": "us-east-1"},
        )

        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.timestamp == now
        assert alert.metadata["error_code"] == 503


# =============================================================================
# ObservabilityService Initialization Tests
# =============================================================================


class TestObservabilityServiceInit:
    """Tests for ObservabilityService initialization."""

    def test_init_default(self):
        """Test default initialization."""
        monitor = ObservabilityService()

        assert monitor.latencies == {}
        assert monitor.request_counts == {}
        assert monitor.error_counts == {}
        assert monitor.success_counts == {}
        assert monitor.resource_usage == {}
        assert monitor.alerts == []
        assert monitor.service_start_time is not None

    def test_init_thresholds(self):
        """Test default alert thresholds."""
        monitor = ObservabilityService()

        assert monitor.alert_thresholds["error_rate"] == 0.05
        assert monitor.alert_thresholds["p95_latency"] == 5.0
        assert monitor.alert_thresholds["saturation"] == 0.80


# =============================================================================
# ObservabilityService Latency Tracking Tests (Golden Signal 1)
# =============================================================================


class TestObservabilityServiceLatency:
    """Tests for latency tracking (Golden Signal 1)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ObservabilityService()

    def test_record_latency(self):
        """Test recording latency."""
        self.monitor.record_latency("neptune.query", 0.5)
        self.monitor.record_latency("neptune.query", 0.8)

        assert len(self.monitor.latencies["neptune.query"]) == 2
        assert 0.5 in self.monitor.latencies["neptune.query"]

    @pytest.mark.slow
    def test_record_latency_max_size(self):
        """Test latency list is limited to 1000 items."""
        for i in range(1500):
            self.monitor.record_latency("test.op", float(i))

        assert len(self.monitor.latencies["test.op"]) == 1000

    def test_get_p95_latency(self):
        """Test getting 95th percentile latency."""
        # Record 100 latencies from 0.01 to 1.0
        for i in range(100):
            self.monitor.record_latency("test.op", (i + 1) / 100.0)

        p95 = self.monitor.get_p95_latency("test.op")

        assert p95 is not None
        assert p95 >= 0.95

    def test_get_p95_latency_no_data(self):
        """Test getting P95 latency with no data."""
        p95 = self.monitor.get_p95_latency("nonexistent")
        assert p95 is None

    def test_get_average_latency(self):
        """Test getting average latency."""
        self.monitor.record_latency("test.op", 1.0)
        self.monitor.record_latency("test.op", 2.0)
        self.monitor.record_latency("test.op", 3.0)

        avg = self.monitor.get_average_latency("test.op")

        assert avg == 2.0

    def test_get_average_latency_no_data(self):
        """Test getting average latency with no data."""
        avg = self.monitor.get_average_latency("nonexistent")
        assert avg is None

    def test_track_latency_context_manager(self):
        """Test latency tracking with context manager."""
        with self.monitor.track_latency("test.operation"):
            time.sleep(0.01)  # Small delay

        assert len(self.monitor.latencies["test.operation"]) == 1
        assert self.monitor.latencies["test.operation"][0] >= 0.01
        assert self.monitor.success_counts["test.operation"] == 1

    def test_track_latency_with_error(self):
        """Test latency tracking when error occurs."""
        with pytest.raises(ValueError):
            with self.monitor.track_latency("failing.operation"):
                raise ValueError("Test error")

        assert self.monitor.error_counts["failing.operation"] == 1
        assert len(self.monitor.latencies["failing.operation"]) == 1


# =============================================================================
# ObservabilityService Traffic Tracking Tests (Golden Signal 2)
# =============================================================================


class TestObservabilityServiceTraffic:
    """Tests for traffic tracking (Golden Signal 2)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ObservabilityService()

    def test_record_request(self):
        """Test recording requests."""
        self.monitor.record_request("/api/v1/scan")
        self.monitor.record_request("/api/v1/scan")
        self.monitor.record_request("/api/v1/status")

        assert self.monitor.request_counts["/api/v1/scan"] == 2
        assert self.monitor.request_counts["/api/v1/status"] == 1

    def test_get_request_rate(self):
        """Test getting request rate."""
        for _ in range(10):
            self.monitor.record_request("/api/v1/scan")

        rate = self.monitor.get_request_rate("/api/v1/scan")

        assert rate > 0

    def test_get_request_rate_no_requests(self):
        """Test request rate with no requests."""
        rate = self.monitor.get_request_rate("/nonexistent")
        assert rate == 0.0


# =============================================================================
# ObservabilityService Error Tracking Tests (Golden Signal 3)
# =============================================================================


class TestObservabilityServiceErrors:
    """Tests for error tracking (Golden Signal 3)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ObservabilityService()

    def test_record_error(self):
        """Test recording errors."""
        self.monitor.record_error("neptune.query")
        self.monitor.record_error("neptune.query")

        assert self.monitor.error_counts["neptune.query"] == 2

    def test_record_error_with_exception(self):
        """Test recording error with exception."""
        error = ValueError("Test error")
        self.monitor.record_error("test.operation", error=error)

        assert self.monitor.error_counts["test.operation"] == 1

    def test_record_success(self):
        """Test recording successful operations."""
        self.monitor.record_success("neptune.query")
        self.monitor.record_success("neptune.query")

        assert self.monitor.success_counts["neptune.query"] == 2

    def test_get_error_rate(self):
        """Test getting error rate."""
        # 2 errors, 8 successes = 20% error rate
        for _ in range(2):
            self.monitor.record_error("test.op")
        for _ in range(8):
            self.monitor.record_success("test.op")

        error_rate = self.monitor.get_error_rate("test.op")

        assert error_rate == 0.2

    def test_get_error_rate_no_requests(self):
        """Test error rate with no requests."""
        error_rate = self.monitor.get_error_rate("nonexistent")
        assert error_rate == 0.0

    def test_get_success_rate(self):
        """Test getting success rate."""
        for _ in range(3):
            self.monitor.record_error("test.op")
        for _ in range(7):
            self.monitor.record_success("test.op")

        success_rate = self.monitor.get_success_rate("test.op")

        assert success_rate == 0.7


# =============================================================================
# ObservabilityService Saturation Tracking Tests (Golden Signal 4)
# =============================================================================


class TestObservabilityServiceSaturation:
    """Tests for saturation tracking (Golden Signal 4)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ObservabilityService()

    def test_record_resource_usage(self):
        """Test recording resource usage."""
        self.monitor.record_resource_usage("cpu", 45.0)
        self.monitor.record_resource_usage("memory", 60.0)

        assert self.monitor.resource_usage["cpu"] == 45.0
        assert self.monitor.resource_usage["memory"] == 60.0

    def test_record_resource_usage_creates_alert(self):
        """Test that high resource usage creates alert."""
        self.monitor.record_resource_usage("cpu", 85.0)  # Above 80% threshold

        assert len(self.monitor.alerts) == 1
        assert self.monitor.alerts[0].severity == AlertSeverity.HIGH
        assert "cpu" in self.monitor.alerts[0].message


# =============================================================================
# ObservabilityService Health Check Tests
# =============================================================================


class TestObservabilityServiceHealth:
    """Tests for health checks."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ObservabilityService()

    def test_get_service_health_healthy(self):
        """Test healthy status with low errors and latency."""
        # Add some successful operations
        for _ in range(100):
            self.monitor.record_success("test.op")
            self.monitor.record_latency("test.op", 0.1)

        health = self.monitor.get_service_health()

        assert health == ServiceHealth.HEALTHY

    def test_get_service_health_degraded(self):
        """Test degraded status with moderate errors."""
        # 3% error rate (between 1% and 5%)
        for _ in range(3):
            self.monitor.record_error("test.op")
        for _ in range(97):
            self.monitor.record_success("test.op")

        health = self.monitor.get_service_health()

        assert health == ServiceHealth.DEGRADED

    def test_get_service_health_unhealthy_errors(self):
        """Test unhealthy status with high error rate."""
        # 10% error rate (above 5%)
        for _ in range(10):
            self.monitor.record_error("test.op")
        for _ in range(90):
            self.monitor.record_success("test.op")

        health = self.monitor.get_service_health()

        assert health == ServiceHealth.UNHEALTHY

    def test_get_service_health_unhealthy_latency(self):
        """Test unhealthy status with high latency."""
        # Record latencies above 5 seconds
        for _ in range(100):
            self.monitor.record_latency("test.op", 6.0)

        health = self.monitor.get_service_health()

        assert health == ServiceHealth.UNHEALTHY

    def test_get_health_report(self):
        """Test getting detailed health report."""
        self.monitor.record_request("/api/v1/scan")
        self.monitor.record_latency("neptune.query", 0.5)
        self.monitor.record_success("neptune.query")
        self.monitor.record_error("opensearch.query")

        report = self.monitor.get_health_report()

        assert "status" in report
        assert "uptime_seconds" in report
        assert "timestamp" in report
        assert "golden_signals" in report
        assert "latency" in report["golden_signals"]
        assert "traffic" in report["golden_signals"]
        assert "errors" in report["golden_signals"]
        assert "saturation" in report["golden_signals"]

    def test_get_health_report_latency_details(self):
        """Test health report latency details."""
        self.monitor.record_latency("test.op", 0.1)
        self.monitor.record_latency("test.op", 0.2)

        report = self.monitor.get_health_report()

        latency_data = report["golden_signals"]["latency"]["test.op"]
        assert "average_ms" in latency_data
        assert "p95_ms" in latency_data
        assert "sample_count" in latency_data
        assert latency_data["sample_count"] == 2

    def test_get_health_report_traffic_details(self):
        """Test health report traffic details."""
        for _ in range(5):
            self.monitor.record_request("/api/test")

        report = self.monitor.get_health_report()

        traffic_data = report["golden_signals"]["traffic"]["/api/test"]
        assert traffic_data["total_requests"] == 5
        assert "requests_per_second" in traffic_data

    def test_get_health_report_includes_alerts(self):
        """Test health report includes recent alerts."""
        self.monitor.create_alert(
            severity=AlertSeverity.HIGH,
            service="test",
            message="Test alert",
        )

        report = self.monitor.get_health_report()

        assert len(report["alerts"]) == 1
        assert report["alerts"][0]["message"] == "Test alert"


# =============================================================================
# ObservabilityService Alerting Tests
# =============================================================================


class TestObservabilityServiceAlerting:
    """Tests for alerting functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = ObservabilityService()

    def test_create_alert(self):
        """Test creating an alert."""
        self.monitor.create_alert(
            severity=AlertSeverity.CRITICAL,
            service="neptune",
            message="Connection pool exhausted",
            metadata={"pool_size": 100},
        )

        assert len(self.monitor.alerts) == 1
        alert = self.monitor.alerts[0]
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.service == "neptune"
        assert alert.metadata["pool_size"] == 100

    def test_create_alert_multiple(self):
        """Test creating multiple alerts."""
        for i in range(5):
            self.monitor.create_alert(
                severity=AlertSeverity.HIGH,
                service="test",
                message=f"Alert {i}",
            )

        assert len(self.monitor.alerts) == 5

    def test_latency_sla_violation_creates_alert(self):
        """Test that SLA violation creates alert."""
        # Record latency above 5 second threshold
        self.monitor.record_latency("slow.operation", 6.0)
        self.monitor._check_latency_sla("slow.operation", 6.0)

        assert len(self.monitor.alerts) == 1
        assert self.monitor.alerts[0].severity == AlertSeverity.MEDIUM

    def test_error_rate_threshold_creates_alert(self):
        """Test that high error rate creates alert."""
        # Record errors to exceed 5% threshold
        for _ in range(10):
            self.monitor.record_error("failing.op")
        for _ in range(90):
            self.monitor.record_success("failing.op")

        # Last error triggers the check
        initial_alerts = len(self.monitor.alerts)
        self.monitor.record_error("failing.op")

        # Should have at least one alert
        assert len(self.monitor.alerts) > initial_alerts


# =============================================================================
# Factory Function and Decorator Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions and decorators."""

    def teardown_method(self):
        """Reset singleton after each test."""
        import src.services.observability_service as module

        module._global_monitor = None

    def test_get_monitor(self):
        """Test getting singleton monitor instance."""
        monitor1 = get_monitor()
        monitor2 = get_monitor()

        assert monitor1 is monitor2
        assert isinstance(monitor1, ObservabilityService)

    def test_monitored_decorator(self):
        """Test @monitored decorator."""

        @monitored("test.decorated_function")
        def decorated_function():
            return 42

        result = decorated_function()

        assert result == 42

        monitor = get_monitor()
        assert len(monitor.latencies["test.decorated_function"]) == 1
        assert monitor.success_counts["test.decorated_function"] == 1

    def test_monitored_decorator_default_name(self):
        """Test @monitored decorator with default name."""

        @monitored()
        def my_function():
            return "hello"

        result = my_function()

        assert result == "hello"

    def test_monitored_decorator_with_error(self):
        """Test @monitored decorator when function raises."""

        @monitored("failing.function")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        monitor = get_monitor()
        assert monitor.error_counts["failing.function"] == 1


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_health_report(self):
        """Test health report with no data."""
        monitor = ObservabilityService()
        report = monitor.get_health_report()

        assert report["status"] == "healthy"
        assert report["golden_signals"]["latency"] == {}
        assert report["golden_signals"]["traffic"] == {}

    def test_health_with_no_operations(self):
        """Test health status with no operations recorded."""
        monitor = ObservabilityService()
        health = monitor.get_service_health()

        assert health == ServiceHealth.HEALTHY

    def test_multiple_operations(self):
        """Test tracking multiple different operations."""
        monitor = ObservabilityService()

        operations = ["neptune.query", "opensearch.search", "bedrock.invoke"]
        for op in operations:
            monitor.record_latency(op, 0.1)
            monitor.record_success(op)
            monitor.record_request(op)

        report = monitor.get_health_report()

        for op in operations:
            assert op in report["golden_signals"]["latency"]
            assert op in report["golden_signals"]["errors"]

    def test_alerts_limited_in_report(self):
        """Test that only last 10 alerts are in report."""
        monitor = ObservabilityService()

        for i in range(15):
            monitor.create_alert(
                severity=AlertSeverity.INFO,
                service="test",
                message=f"Alert {i}",
            )

        report = monitor.get_health_report()

        # Should only include last 10 alerts
        assert len(report["alerts"]) == 10

    def test_uptime_tracking(self):
        """Test uptime is tracked correctly."""
        monitor = ObservabilityService()

        # Wait a tiny bit
        time.sleep(0.01)

        report = monitor.get_health_report()

        assert report["uptime_seconds"] >= 0.01
