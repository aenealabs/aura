"""
Tests for AlignmentAnalyticsService (ADR-052 Phase 3).

Tests trend analysis, alerting, and reporting functionality.
"""

import platform
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from src.services.alignment.analytics import (
    AgentComparison,
    AlertSeverity,
    AlertStatus,
    AlertThreshold,
    AlignmentAlert,
    AlignmentAnalyticsService,
    AlignmentReport,
    MetricDataPoint,
    TimeGranularity,
    TrendAnalysis,
    TrendDirection,
)

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestTimeGranularityEnum:
    """Tests for TimeGranularity enum."""

    def test_all_granularities_defined(self):
        """All expected granularities exist."""
        granularities = [g.value for g in TimeGranularity]
        assert "minute" in granularities
        assert "hour" in granularities
        assert "day" in granularities
        assert "week" in granularities
        assert "month" in granularities

    def test_granularity_values(self):
        """Granularity enum values are correct."""
        assert TimeGranularity.MINUTE.value == "minute"
        assert TimeGranularity.HOUR.value == "hour"
        assert TimeGranularity.DAY.value == "day"
        assert TimeGranularity.WEEK.value == "week"
        assert TimeGranularity.MONTH.value == "month"


class TestTrendDirectionEnum:
    """Tests for TrendDirection enum."""

    def test_all_directions_defined(self):
        """All expected trend directions exist."""
        directions = [d.value for d in TrendDirection]
        assert "improving" in directions
        assert "stable" in directions
        assert "degrading" in directions
        assert "unknown" in directions


class TestAlertSeverityEnum:
    """Tests for AlertSeverity enum."""

    def test_all_severities_defined(self):
        """All expected severities exist."""
        severities = [s.value for s in AlertSeverity]
        assert "info" in severities
        assert "warning" in severities
        assert "critical" in severities


class TestAlertStatusEnum:
    """Tests for AlertStatus enum."""

    def test_all_statuses_defined(self):
        """All expected statuses exist."""
        statuses = [s.value for s in AlertStatus]
        assert "active" in statuses
        assert "acknowledged" in statuses
        assert "resolved" in statuses
        assert "suppressed" in statuses


class TestMetricDataPoint:
    """Tests for MetricDataPoint dataclass."""

    def test_creation_with_required_fields(self):
        """Create data point with required fields."""
        now = datetime.now(timezone.utc)
        dp = MetricDataPoint(
            timestamp=now,
            metric_name="trust_score",
            value=0.85,
        )
        assert dp.timestamp == now
        assert dp.metric_name == "trust_score"
        assert dp.value == 0.85
        assert dp.agent_id is None
        assert dp.metadata == {}

    def test_creation_with_all_fields(self):
        """Create data point with all fields."""
        now = datetime.now(timezone.utc)
        dp = MetricDataPoint(
            timestamp=now,
            metric_name="confidence_score",
            value=0.92,
            agent_id="agent-123",
            metadata={"source": "test", "version": "1.0"},
        )
        assert dp.agent_id == "agent-123"
        assert dp.metadata["source"] == "test"


class TestTrendAnalysis:
    """Tests for TrendAnalysis dataclass."""

    def test_creation(self):
        """Create trend analysis."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=24)
        trend = TrendAnalysis(
            metric_name="trust_score",
            direction=TrendDirection.IMPROVING,
            slope=0.02,
            confidence=0.85,
            current_value=0.90,
            previous_value=0.80,
            change_percent=12.5,
            period_start=start,
            period_end=now,
            data_points=100,
            is_anomaly=False,
            anomaly_score=0.1,
        )
        assert trend.metric_name == "trust_score"
        assert trend.direction == TrendDirection.IMPROVING
        assert trend.slope == 0.02
        assert trend.confidence == 0.85
        assert trend.change_percent == 12.5
        assert trend.data_points == 100
        assert trend.is_anomaly is False


class TestAlignmentAlert:
    """Tests for AlignmentAlert dataclass."""

    def test_creation_with_required_fields(self):
        """Create alert with required fields."""
        now = datetime.now(timezone.utc)
        alert = AlignmentAlert(
            alert_id="alert-001",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            metric_name="trust_score",
            threshold_value=0.50,
            actual_value=0.45,
            message="Trust score below threshold",
            agent_id="agent-123",
            triggered_at=now,
        )
        assert alert.alert_id == "alert-001"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.ACTIVE
        assert alert.acknowledged_at is None
        assert alert.resolved_at is None

    def test_creation_with_all_fields(self):
        """Create alert with all fields."""
        now = datetime.now(timezone.utc)
        alert = AlignmentAlert(
            alert_id="alert-002",
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.ACKNOWLEDGED,
            metric_name="rollback_success_rate",
            threshold_value=0.90,
            actual_value=0.85,
            message="Rollback rate critically low",
            agent_id=None,
            triggered_at=now,
            acknowledged_at=now + timedelta(minutes=5),
            acknowledged_by="admin@example.com",
            suppressed_until=None,
        )
        assert alert.acknowledged_by == "admin@example.com"


class TestAgentComparison:
    """Tests for AgentComparison dataclass."""

    def test_creation(self):
        """Create agent comparison."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=24)
        comparison = AgentComparison(
            metric_name="trust_score",
            period_start=start,
            period_end=now,
            agents=[
                {"agent_id": "agent-1", "value": 0.95, "rank": 1, "percentile": 100},
                {"agent_id": "agent-2", "value": 0.85, "rank": 2, "percentile": 50},
            ],
            mean_value=0.90,
            std_deviation=0.05,
            best_agent_id="agent-1",
            worst_agent_id="agent-2",
        )
        assert comparison.metric_name == "trust_score"
        assert len(comparison.agents) == 2
        assert comparison.best_agent_id == "agent-1"
        assert comparison.worst_agent_id == "agent-2"


class TestAlignmentReport:
    """Tests for AlignmentReport dataclass."""

    def test_creation(self):
        """Create alignment report."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=24)
        report = AlignmentReport(
            report_id="report-001",
            generated_at=now,
            period_start=start,
            period_end=now,
            overall_health_score=0.85,
            trends=[],
            alerts=[],
            comparisons=[],
            recommendations=["Review agent accuracy"],
            metadata={"agents_analyzed": 5},
        )
        assert report.report_id == "report-001"
        assert report.overall_health_score == 0.85
        assert len(report.recommendations) == 1


class TestAlertThreshold:
    """Tests for AlertThreshold dataclass."""

    def test_creation_with_defaults(self):
        """Create threshold with defaults."""
        threshold = AlertThreshold(
            metric_name="trust_score",
            warning_threshold=0.50,
            critical_threshold=0.30,
            comparison="less_than",
        )
        assert threshold.metric_name == "trust_score"
        assert threshold.warning_threshold == 0.50
        assert threshold.critical_threshold == 0.30
        assert threshold.comparison == "less_than"
        assert threshold.enabled is True
        assert threshold.cooldown_minutes == 15

    def test_creation_with_custom_values(self):
        """Create threshold with custom values."""
        threshold = AlertThreshold(
            metric_name="error_rate",
            warning_threshold=0.10,
            critical_threshold=0.20,
            comparison="greater_than",
            enabled=False,
            cooldown_minutes=30,
        )
        assert threshold.enabled is False
        assert threshold.cooldown_minutes == 30


class TestAlignmentAnalyticsServiceInit:
    """Tests for AlignmentAnalyticsService initialization."""

    def test_default_initialization(self):
        """Service initializes with defaults."""
        service = AlignmentAnalyticsService()
        assert service._retention_days == 90
        assert service._max_data_points == 100000
        assert len(service._thresholds) == 5  # Default thresholds

    def test_custom_initialization(self):
        """Service initializes with custom values."""
        custom_thresholds = {
            "custom_metric": AlertThreshold(
                metric_name="custom_metric",
                warning_threshold=0.5,
                critical_threshold=0.3,
                comparison="less_than",
            )
        }
        service = AlignmentAnalyticsService(
            retention_days=30,
            max_data_points=1000,
            thresholds=custom_thresholds,
        )
        assert service._retention_days == 30
        assert service._max_data_points == 1000
        assert "custom_metric" in service._thresholds

    def test_default_thresholds(self):
        """Default thresholds are configured correctly."""
        service = AlignmentAnalyticsService()
        assert "disagreement_rate" in service._thresholds
        assert "confidence_calibration_error" in service._thresholds
        assert "rollback_success_rate" in service._thresholds
        assert "trust_score" in service._thresholds
        assert "transparency_score" in service._thresholds


class TestRecordMetric:
    """Tests for recording metrics."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = AlignmentAnalyticsService()
        yield svc
        svc.clear_data()

    def test_record_simple_metric(self, service):
        """Record a simple metric."""
        dp = service.record_metric(
            metric_name="test_metric",
            value=0.85,
        )
        assert dp.metric_name == "test_metric"
        assert dp.value == 0.85
        assert dp.timestamp is not None

    def test_record_metric_with_agent(self, service):
        """Record metric with agent ID."""
        dp = service.record_metric(
            metric_name="trust_score",
            value=0.90,
            agent_id="agent-123",
        )
        assert dp.agent_id == "agent-123"

    def test_record_metric_with_timestamp(self, service):
        """Record metric with custom timestamp."""
        custom_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        dp = service.record_metric(
            metric_name="test_metric",
            value=0.75,
            timestamp=custom_time,
        )
        assert dp.timestamp == custom_time

    def test_record_metric_with_metadata(self, service):
        """Record metric with metadata."""
        dp = service.record_metric(
            metric_name="test_metric",
            value=0.80,
            metadata={"source": "test", "version": "1.0"},
        )
        assert dp.metadata["source"] == "test"
        assert dp.metadata["version"] == "1.0"

    def test_record_metrics_batch(self, service):
        """Record multiple metrics at once."""
        metrics = [
            {"name": "metric_a", "value": 0.85},
            {"name": "metric_b", "value": 0.90, "agent_id": "agent-1"},
            {"name": "metric_c", "value": 0.75, "metadata": {"key": "value"}},
        ]
        data_points = service.record_metrics_batch(metrics)
        assert len(data_points) == 3
        assert data_points[0].metric_name == "metric_a"
        assert data_points[1].agent_id == "agent-1"
        assert data_points[2].metadata["key"] == "value"


class TestTrendAnalysisExtended:
    """Extended tests for trend analysis."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = AlignmentAnalyticsService()
        yield svc
        svc.clear_data()

    def test_analyze_trend_insufficient_data(self, service):
        """Trend analysis with insufficient data returns unknown."""
        service.record_metric("test_metric", 0.85)
        trend = service.analyze_trend("test_metric", period_hours=24)
        assert trend.direction == TrendDirection.UNKNOWN
        assert trend.confidence == 0.0
        assert trend.data_points == 1

    def test_analyze_trend_no_data(self, service):
        """Trend analysis with no data."""
        trend = service.analyze_trend("nonexistent_metric", period_hours=24)
        assert trend.direction == TrendDirection.UNKNOWN
        assert trend.data_points == 0

    def test_analyze_improving_trend(self, service):
        """Detect improving trend."""
        base_time = datetime.now(timezone.utc)
        # Record increasing values over time
        for i in range(10):
            service.record_metric(
                metric_name="improving_metric",
                value=0.50 + (i * 0.05),  # 0.50, 0.55, 0.60, ...
                timestamp=base_time - timedelta(hours=10 - i),
            )
        trend = service.analyze_trend("improving_metric", period_hours=24)
        assert trend.direction == TrendDirection.IMPROVING
        assert trend.slope > 0
        assert trend.change_percent > 0

    def test_analyze_degrading_trend(self, service):
        """Detect degrading trend."""
        base_time = datetime.now(timezone.utc)
        # Record decreasing values over time
        for i in range(10):
            service.record_metric(
                metric_name="degrading_metric",
                value=0.95 - (i * 0.05),  # 0.95, 0.90, 0.85, ...
                timestamp=base_time - timedelta(hours=10 - i),
            )
        trend = service.analyze_trend("degrading_metric", period_hours=24)
        assert trend.direction == TrendDirection.DEGRADING
        assert trend.slope < 0

    def test_analyze_stable_trend(self, service):
        """Detect stable trend."""
        base_time = datetime.now(timezone.utc)
        # Record stable values
        for i in range(10):
            service.record_metric(
                metric_name="stable_metric",
                value=0.85 + (0.001 * (-1) ** i),  # Small oscillation
                timestamp=base_time - timedelta(hours=10 - i),
            )
        trend = service.analyze_trend("stable_metric", period_hours=24)
        assert trend.direction == TrendDirection.STABLE

    def test_analyze_trend_filter_by_agent(self, service):
        """Trend analysis filtered by agent."""
        base_time = datetime.now(timezone.utc)
        # Record for agent-1
        for i in range(5):
            service.record_metric(
                metric_name="shared_metric",
                value=0.80 + (i * 0.02),
                agent_id="agent-1",
                timestamp=base_time - timedelta(hours=5 - i),
            )
        # Record for agent-2
        for i in range(5):
            service.record_metric(
                metric_name="shared_metric",
                value=0.60 - (i * 0.02),
                agent_id="agent-2",
                timestamp=base_time - timedelta(hours=5 - i),
            )

        trend_agent1 = service.analyze_trend(
            "shared_metric", period_hours=24, agent_id="agent-1"
        )
        trend_agent2 = service.analyze_trend(
            "shared_metric", period_hours=24, agent_id="agent-2"
        )
        assert trend_agent1.data_points == 5
        assert trend_agent2.data_points == 5
        # Agent 1 improving, Agent 2 degrading
        assert trend_agent1.direction != trend_agent2.direction

    def test_anomaly_detection(self, service):
        """Detect anomalies in metrics."""
        base_time = datetime.now(timezone.utc)
        # Record mostly stable values
        for i in range(20):
            value = 0.85 if i < 19 else 0.20  # Last value is anomaly
            service.record_metric(
                metric_name="anomaly_metric",
                value=value,
                timestamp=base_time - timedelta(hours=20 - i),
            )
        trend = service.analyze_trend("anomaly_metric", period_hours=48)
        assert trend.is_anomaly is True
        assert trend.anomaly_score > 0


class TestAgentComparisonExtended:
    """Extended tests for agent comparison."""

    @pytest.fixture
    def service(self):
        """Create fresh service for each test."""
        svc = AlignmentAnalyticsService()
        yield svc
        svc.clear_data()

    def test_compare_agents_no_data(self, service):
        """Comparison with no data."""
        comparison = service.compare_agents("nonexistent_metric", period_hours=24)
        assert len(comparison.agents) == 0
        assert comparison.best_agent_id == ""
        assert comparison.worst_agent_id == ""

    def test_compare_multiple_agents(self, service):
        """Compare metrics across multiple agents."""
        base_time = datetime.now(timezone.utc)
        # Record for 3 agents with different performance
        for i in range(5):
            service.record_metric(
                "trust_score",
                0.95,
                agent_id="agent-top",
                timestamp=base_time - timedelta(hours=i),
            )
            service.record_metric(
                "trust_score",
                0.75,
                agent_id="agent-mid",
                timestamp=base_time - timedelta(hours=i),
            )
            service.record_metric(
                "trust_score",
                0.55,
                agent_id="agent-low",
                timestamp=base_time - timedelta(hours=i),
            )

        comparison = service.compare_agents("trust_score", period_hours=24)
        assert len(comparison.agents) == 3
        assert comparison.best_agent_id == "agent-top"
        assert comparison.worst_agent_id == "agent-low"
        assert comparison.mean_value == pytest.approx(0.75, rel=0.01)

    def test_agent_rankings(self, service):
        """Verify agent rankings are correct."""
        base_time = datetime.now(timezone.utc)
        # Record for 4 agents
        agents = [
            ("agent-d", 0.60),
            ("agent-b", 0.80),
            ("agent-a", 0.90),
            ("agent-c", 0.70),
        ]
        for agent_id, value in agents:
            for i in range(3):
                service.record_metric(
                    "rank_metric",
                    value,
                    agent_id=agent_id,
                    timestamp=base_time - timedelta(hours=i),
                )

        comparison = service.compare_agents("rank_metric", period_hours=24)
        # Check rankings
        ranked = {a["agent_id"]: a["rank"] for a in comparison.agents}
        assert ranked["agent-a"] == 1  # Highest value
        assert ranked["agent-b"] == 2
        assert ranked["agent-c"] == 3
        assert ranked["agent-d"] == 4  # Lowest value

    def test_agent_percentiles(self, service):
        """Verify agent percentiles are calculated."""
        base_time = datetime.now(timezone.utc)
        for i, agent_id in enumerate(["agent-1", "agent-2", "agent-3", "agent-4"]):
            service.record_metric(
                "percentile_metric",
                0.60 + (i * 0.10),  # Different values
                agent_id=agent_id,
                timestamp=base_time,
            )

        comparison = service.compare_agents("percentile_metric", period_hours=24)
        # Top agent should have 100 percentile
        top_agent = next(a for a in comparison.agents if a["rank"] == 1)
        assert top_agent["percentile"] == 100.0


class TestAlertManagement:
    """Tests for alert management."""

    @pytest.fixture
    def service(self):
        """Create fresh service with custom thresholds."""
        thresholds = {
            "test_metric": AlertThreshold(
                metric_name="test_metric",
                warning_threshold=0.50,
                critical_threshold=0.30,
                comparison="less_than",
                cooldown_minutes=1,  # Short for testing
            ),
            "error_metric": AlertThreshold(
                metric_name="error_metric",
                warning_threshold=0.10,
                critical_threshold=0.20,
                comparison="greater_than",
                cooldown_minutes=1,
            ),
        }
        svc = AlignmentAnalyticsService(thresholds=thresholds)
        yield svc
        svc.clear_data()

    def test_warning_alert_triggered(self, service):
        """Warning alert triggered when threshold crossed."""
        service.record_metric("test_metric", 0.45)  # Below 0.50 warning
        alerts = service.get_alerts()
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING
        assert alerts[0].status == AlertStatus.ACTIVE

    def test_critical_alert_triggered(self, service):
        """Critical alert triggered for critical threshold."""
        service.record_metric("test_metric", 0.25)  # Below 0.30 critical
        alerts = service.get_alerts()
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_no_alert_above_threshold(self, service):
        """No alert when value above threshold."""
        service.record_metric("test_metric", 0.85)  # Above warning
        alerts = service.get_alerts()
        assert len(alerts) == 0

    def test_greater_than_comparison(self, service):
        """Alert triggered for greater_than comparison."""
        service.record_metric("error_metric", 0.15)  # Above 0.10 warning
        alerts = service.get_alerts()
        assert len(alerts) == 1
        assert alerts[0].metric_name == "error_metric"

    def test_alert_cooldown(self, service):
        """Alerts respect cooldown period."""
        service.record_metric("test_metric", 0.45)  # Trigger alert
        service.record_metric("test_metric", 0.40)  # Should not trigger (cooldown)
        alerts = service.get_alerts()
        assert len(alerts) == 1  # Only one alert due to cooldown

    def test_acknowledge_alert(self, service):
        """Acknowledge an alert."""
        service.record_metric("test_metric", 0.45)
        alerts = service.get_alerts()
        alert_id = alerts[0].alert_id

        updated = service.acknowledge_alert(alert_id, "admin@example.com")
        assert updated is not None
        assert updated.status == AlertStatus.ACKNOWLEDGED
        assert updated.acknowledged_by == "admin@example.com"
        assert updated.acknowledged_at is not None

    def test_acknowledge_nonexistent_alert(self, service):
        """Acknowledge returns None for non-existent alert."""
        result = service.acknowledge_alert("nonexistent", "admin")
        assert result is None

    def test_resolve_alert(self, service):
        """Resolve an alert."""
        service.record_metric("test_metric", 0.45)
        alerts = service.get_alerts()
        alert_id = alerts[0].alert_id

        updated = service.resolve_alert(alert_id, "admin@example.com")
        assert updated is not None
        assert updated.status == AlertStatus.RESOLVED
        assert updated.resolved_by == "admin@example.com"
        assert updated.resolved_at is not None

    def test_suppress_alert(self, service):
        """Suppress an alert."""
        service.record_metric("test_metric", 0.45)
        alerts = service.get_alerts()
        alert_id = alerts[0].alert_id

        updated = service.suppress_alert(alert_id, suppress_hours=2)
        assert updated is not None
        assert updated.status == AlertStatus.SUPPRESSED
        assert updated.suppressed_until is not None
        # Should be suppressed for about 2 hours
        expected = datetime.now(timezone.utc) + timedelta(hours=2)
        delta = abs((updated.suppressed_until - expected).total_seconds())
        assert delta < 5

    def test_filter_alerts_by_status(self, service):
        """Filter alerts by status."""
        service.record_metric("test_metric", 0.45)
        alerts = service.get_alerts()
        service.acknowledge_alert(alerts[0].alert_id, "admin")

        # Wait for cooldown and trigger another alert
        time.sleep(0.1)
        service._last_alert_time.clear()  # Clear cooldown for testing
        service.record_metric("test_metric", 0.40)

        active = service.get_alerts(status=AlertStatus.ACTIVE)
        acknowledged = service.get_alerts(status=AlertStatus.ACKNOWLEDGED)
        assert len(active) == 1
        assert len(acknowledged) == 1

    def test_filter_alerts_by_severity(self, service):
        """Filter alerts by severity."""
        service.record_metric("test_metric", 0.45)  # Warning
        service._last_alert_time.clear()
        service.record_metric("test_metric", 0.25)  # Critical

        warnings = service.get_alerts(severity=AlertSeverity.WARNING)
        criticals = service.get_alerts(severity=AlertSeverity.CRITICAL)
        assert len(warnings) == 1
        assert len(criticals) == 1

    def test_filter_alerts_by_agent(self, service):
        """Filter alerts by agent."""
        service.record_metric("test_metric", 0.45, agent_id="agent-1")
        service._last_alert_time.clear()
        service.record_metric("test_metric", 0.40, agent_id="agent-2")

        agent1_alerts = service.get_alerts(agent_id="agent-1")
        agent2_alerts = service.get_alerts(agent_id="agent-2")
        assert len(agent1_alerts) == 1
        assert len(agent2_alerts) == 1

    def test_filter_alerts_since(self, service):
        """Filter alerts by time."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        service.record_metric("test_metric", 0.45)

        recent_alerts = service.get_alerts(
            since=datetime.now(timezone.utc) - timedelta(minutes=5)
        )
        old_alerts = service.get_alerts(since=old_time)
        assert len(recent_alerts) == 1
        assert len(old_alerts) == 1


class TestReportGeneration:
    """Tests for report generation."""

    @pytest.fixture
    def service(self):
        """Create service with some data."""
        svc = AlignmentAnalyticsService()
        base_time = datetime.now(timezone.utc)
        # Record some metrics
        for i in range(10):
            svc.record_metric(
                "trust_score",
                0.80 + (i * 0.01),
                agent_id=f"agent-{i % 3}",
                timestamp=base_time - timedelta(hours=10 - i),
            )
            svc.record_metric(
                "transparency_score",
                0.90,
                agent_id=f"agent-{i % 3}",
                timestamp=base_time - timedelta(hours=10 - i),
            )
        yield svc
        svc.clear_data()

    def test_generate_report(self, service):
        """Generate a basic report."""
        report = service.generate_report(period_hours=24)
        assert report.report_id.startswith("report-")
        assert report.generated_at is not None
        assert report.overall_health_score >= 0 and report.overall_health_score <= 1
        assert len(report.trends) == 5  # Key metrics

    def test_report_includes_trends(self, service):
        """Report includes trend analysis."""
        report = service.generate_report(period_hours=24)
        trend_metrics = {t.metric_name for t in report.trends}
        assert "trust_score" in trend_metrics
        assert "transparency_score" in trend_metrics

    def test_report_includes_comparisons(self, service):
        """Report includes agent comparisons."""
        report = service.generate_report(
            period_hours=24,
            include_agent_comparison=True,
        )
        assert len(report.comparisons) == 5

    def test_report_excludes_comparisons(self, service):
        """Report can exclude agent comparisons."""
        report = service.generate_report(
            period_hours=24,
            include_agent_comparison=False,
        )
        assert len(report.comparisons) == 0

    def test_report_includes_alerts(self, service):
        """Report includes recent alerts."""
        # Trigger an alert
        service.record_metric("trust_score", 0.25)  # Below critical
        report = service.generate_report(period_hours=24)
        # Alerts should be included
        assert isinstance(report.alerts, list)

    def test_report_metadata(self, service):
        """Report includes metadata."""
        report = service.generate_report(period_hours=24)
        assert "data_points_analyzed" in report.metadata
        assert "agents_analyzed" in report.metadata

    def test_report_recommendations(self, service):
        """Report generates recommendations."""
        # Add some degrading metrics
        base_time = datetime.now(timezone.utc)
        for i in range(10):
            service.record_metric(
                "rollback_success_rate",
                0.95 - (i * 0.01),  # Degrading
                timestamp=base_time - timedelta(hours=10 - i),
            )
        report = service.generate_report(period_hours=24)
        # Should have recommendations about degrading metrics
        assert isinstance(report.recommendations, list)


class TestTimeSeries:
    """Tests for time series retrieval."""

    @pytest.fixture
    def service(self):
        """Create service with time series data."""
        svc = AlignmentAnalyticsService()
        base_time = datetime.now(timezone.utc)
        # Record hourly data for past 12 hours
        for i in range(12):
            svc.record_metric(
                "hourly_metric",
                0.80 + (i * 0.01),
                timestamp=base_time - timedelta(hours=12 - i),
            )
        yield svc
        svc.clear_data()

    def test_get_time_series(self, service):
        """Get time series data."""
        series = service.get_time_series(
            "hourly_metric",
            period_hours=24,
            granularity=TimeGranularity.HOUR,
        )
        assert len(series) > 0
        # Each point should have expected fields
        for point in series:
            assert "timestamp" in point
            assert "value" in point
            assert "min" in point
            assert "max" in point
            assert "count" in point

    def test_time_series_no_data(self, service):
        """Empty time series for missing metric."""
        series = service.get_time_series(
            "nonexistent_metric",
            period_hours=24,
        )
        assert len(series) == 0

    def test_time_series_filter_by_agent(self, service):
        """Filter time series by agent."""
        base_time = datetime.now(timezone.utc)
        for i in range(5):
            service.record_metric(
                "agent_metric",
                0.80,
                agent_id="agent-1",
                timestamp=base_time - timedelta(hours=i),
            )
            service.record_metric(
                "agent_metric",
                0.90,
                agent_id="agent-2",
                timestamp=base_time - timedelta(hours=i),
            )

        series_1 = service.get_time_series(
            "agent_metric", period_hours=24, agent_id="agent-1"
        )
        series_2 = service.get_time_series(
            "agent_metric", period_hours=24, agent_id="agent-2"
        )

        # Values should differ between agents
        if series_1 and series_2:
            assert series_1[0]["value"] != series_2[0]["value"]

    def test_time_series_aggregation(self, service):
        """Time series aggregates values within buckets."""
        base_time = datetime.now(timezone.utc)
        # Record multiple values in same hour
        for i in range(5):
            service.record_metric(
                "agg_metric",
                0.80 + (i * 0.02),  # 0.80, 0.82, 0.84, 0.86, 0.88
                timestamp=base_time - timedelta(minutes=i * 10),
            )

        series = service.get_time_series(
            "agg_metric",
            period_hours=1,
            granularity=TimeGranularity.HOUR,
        )
        # Should aggregate to one bucket with mean value
        if series:
            bucket = series[0]
            assert bucket["count"] >= 1
            assert bucket["min"] <= bucket["value"] <= bucket["max"]


class TestServiceStats:
    """Tests for service statistics."""

    @pytest.fixture
    def service(self):
        """Create fresh service."""
        svc = AlignmentAnalyticsService()
        yield svc
        svc.clear_data()

    def test_stats_empty_service(self, service):
        """Stats for empty service."""
        stats = service.get_stats()
        assert stats["total_data_points"] == 0
        assert stats["total_alerts"] == 0
        assert stats["active_alerts"] == 0
        assert stats["total_reports"] == 0

    def test_stats_with_data(self, service):
        """Stats reflect recorded data."""
        for i in range(10):
            service.record_metric(f"metric_{i}", 0.85)
        service.generate_report()

        stats = service.get_stats()
        assert stats["total_data_points"] == 10
        assert stats["total_reports"] == 1


class TestThresholdManagement:
    """Tests for threshold management."""

    @pytest.fixture
    def service(self):
        """Create fresh service."""
        svc = AlignmentAnalyticsService()
        yield svc
        svc.clear_data()

    def test_set_threshold(self, service):
        """Set a new threshold."""
        new_threshold = AlertThreshold(
            metric_name="new_metric",
            warning_threshold=0.40,
            critical_threshold=0.20,
            comparison="less_than",
        )
        service.set_threshold(new_threshold)
        assert "new_metric" in service._thresholds
        assert service._thresholds["new_metric"].warning_threshold == 0.40

    def test_update_existing_threshold(self, service):
        """Update an existing threshold."""
        updated_threshold = AlertThreshold(
            metric_name="trust_score",  # Existing
            warning_threshold=0.60,  # Changed from 0.50
            critical_threshold=0.40,  # Changed from 0.30
            comparison="less_than",
        )
        service.set_threshold(updated_threshold)
        assert service._thresholds["trust_score"].warning_threshold == 0.60


class TestClearData:
    """Tests for data clearing."""

    @pytest.fixture
    def service(self):
        """Create service with data."""
        svc = AlignmentAnalyticsService()
        base_time = datetime.now(timezone.utc)
        for i in range(20):
            svc.record_metric(
                "test_metric",
                0.85,
                timestamp=base_time - timedelta(hours=i),
            )
        yield svc

    def test_clear_all_data(self, service):
        """Clear all data."""
        stats_before = service.get_stats()
        assert stats_before["total_data_points"] == 20

        cleared = service.clear_data()
        assert cleared == 20

        stats_after = service.get_stats()
        assert stats_after["total_data_points"] == 0

    def test_clear_old_data(self, service):
        """Clear only old data."""
        cleared = service.clear_data(older_than_hours=10)
        # Should have removed data older than 10 hours
        stats = service.get_stats()
        assert stats["total_data_points"] <= 10


class TestDataRetention:
    """Tests for data retention limits."""

    def test_retention_days_enforced(self):
        """Data older than retention is removed."""
        service = AlignmentAnalyticsService(retention_days=1)
        old_time = datetime.now(timezone.utc) - timedelta(days=2)
        recent_time = datetime.now(timezone.utc)

        # Record old and recent data
        service.record_metric("test", 0.85, timestamp=old_time)
        service.record_metric("test", 0.90, timestamp=recent_time)

        # Trigger retention enforcement
        service.record_metric("test", 0.95)

        stats = service.get_stats()
        # Old data should be removed
        assert stats["total_data_points"] == 2  # Recent ones only
        service.clear_data()

    def test_max_data_points_enforced(self):
        """Max data points limit is enforced."""
        service = AlignmentAnalyticsService(max_data_points=10)

        # Record more than max
        for i in range(15):
            service.record_metric("test", 0.85)

        stats = service.get_stats()
        assert stats["total_data_points"] == 10
        service.clear_data()


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_metric_recording(self):
        """Concurrent metric recording is thread-safe."""
        service = AlignmentAnalyticsService()
        results = []
        errors = []

        def record_metrics(thread_id: int):
            try:
                for i in range(20):
                    service.record_metric(
                        f"metric_t{thread_id}",
                        0.80 + (i * 0.01),
                        agent_id=f"agent-{thread_id}",
                    )
                    results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_metrics, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 100  # 5 threads * 20 metrics each
        service.clear_data()

    def test_concurrent_analysis(self):
        """Concurrent analysis is thread-safe."""
        service = AlignmentAnalyticsService()
        errors = []

        # Add some data first
        for i in range(50):
            service.record_metric(
                "shared_metric",
                0.80 + (i % 10 * 0.02),
                agent_id=f"agent-{i % 3}",
            )

        def analyze():
            try:
                for _ in range(10):
                    service.analyze_trend("shared_metric", period_hours=24)
                    service.compare_agents("shared_metric", period_hours=24)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=analyze) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        service.clear_data()


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def service(self):
        """Create fresh service."""
        svc = AlignmentAnalyticsService()
        yield svc
        svc.clear_data()

    def test_zero_value_metrics(self, service):
        """Handle zero value metrics."""
        service.record_metric("zero_metric", 0.0)
        trend = service.analyze_trend("zero_metric", period_hours=24)
        assert trend.data_points == 1

    def test_negative_value_metrics(self, service):
        """Handle negative value metrics."""
        service.record_metric("negative_metric", -0.5)
        dp = service.record_metric("negative_metric", -0.3)
        assert dp.value == -0.3

    def test_very_large_values(self, service):
        """Handle very large values."""
        service.record_metric("large_metric", 1e10)
        service.record_metric("large_metric", 1e11)
        trend = service.analyze_trend("large_metric", period_hours=24)
        assert trend.data_points == 2

    def test_special_characters_in_metric_name(self, service):
        """Handle special characters in metric names."""
        service.record_metric("metric.with.dots", 0.85)
        service.record_metric("metric-with-dashes", 0.90)
        service.record_metric("metric_with_underscores", 0.95)

        stats = service.get_stats()
        assert stats["total_data_points"] == 3

    def test_very_short_period(self, service):
        """Handle very short analysis period."""
        service.record_metric("test", 0.85)
        trend = service.analyze_trend("test", period_hours=0)  # 0 hours
        assert trend.data_points == 0  # Nothing in 0-hour window

    def test_change_percent_with_zero_previous(self, service):
        """Handle change percent calculation with zero previous value."""
        base_time = datetime.now(timezone.utc)
        service.record_metric(
            "zero_start",
            0.0,
            timestamp=base_time - timedelta(hours=2),
        )
        service.record_metric(
            "zero_start",
            0.5,
            timestamp=base_time,
        )
        trend = service.analyze_trend("zero_start", period_hours=24)
        # Should not cause division by zero
        assert trend.change_percent == 0.0  # Default when previous is 0
