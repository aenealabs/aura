"""
Tests for Phase 3 Alignment Services (ADR-052).

Tests cover:
- AlignmentAnalyticsService: Trend analysis, alerts, reports
- Alignment API endpoints: Health, metrics, alerts, overrides, rollback

Reference: ADR-052 AI Alignment Principles & Human-Machine Collaboration
"""

import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


# =============================================================================
# AlignmentAnalyticsService Tests
# =============================================================================


class TestAlignmentAnalyticsService:
    """Tests for the analytics service."""

    def test_service_initialization(self):
        """Test analytics service initializes correctly."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        assert service._retention_days == 90
        assert service._max_data_points == 100000
        assert len(service._thresholds) > 0
        assert "disagreement_rate" in service._thresholds

    def test_service_custom_initialization(self):
        """Test analytics service with custom parameters."""
        from src.services.alignment.analytics import (
            AlertThreshold,
            AlignmentAnalyticsService,
        )

        custom_threshold = AlertThreshold(
            metric_name="custom_metric",
            warning_threshold=0.5,
            critical_threshold=0.8,
            comparison="greater_than",
        )

        service = AlignmentAnalyticsService(
            retention_days=30,
            max_data_points=1000,
            thresholds={"custom_metric": custom_threshold},
        )

        assert service._retention_days == 30
        assert service._max_data_points == 1000
        assert "custom_metric" in service._thresholds

    def test_record_metric(self):
        """Test recording a metric observation."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        data_point = service.record_metric(
            metric_name="trust_score",
            value=0.85,
            agent_id="agent-001",
            metadata={"source": "test"},
        )

        assert data_point.metric_name == "trust_score"
        assert data_point.value == 0.85
        assert data_point.agent_id == "agent-001"
        assert data_point.metadata["source"] == "test"

    def test_record_metrics_batch(self):
        """Test recording multiple metrics at once."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        metrics = [
            {"name": "trust_score", "value": 0.85, "agent_id": "agent-001"},
            {"name": "transparency_score", "value": 0.92, "agent_id": "agent-001"},
            {"name": "disagreement_rate", "value": 0.08, "agent_id": "agent-001"},
        ]

        data_points = service.record_metrics_batch(metrics)

        assert len(data_points) == 3
        assert data_points[0].metric_name == "trust_score"
        assert data_points[1].metric_name == "transparency_score"
        assert data_points[2].metric_name == "disagreement_rate"

    def test_analyze_trend_insufficient_data(self):
        """Test trend analysis with insufficient data."""
        from src.services.alignment.analytics import (
            AlignmentAnalyticsService,
            TrendDirection,
        )

        service = AlignmentAnalyticsService()

        # Only record one data point
        service.record_metric("trust_score", 0.85)

        trend = service.analyze_trend("trust_score", period_hours=24)

        assert trend.direction == TrendDirection.UNKNOWN
        assert trend.data_points == 1

    def test_analyze_trend_with_data(self):
        """Test trend analysis with sufficient data."""
        from src.services.alignment.analytics import (
            AlignmentAnalyticsService,
            TrendDirection,
        )

        service = AlignmentAnalyticsService()

        # Record increasing values
        now = datetime.now(timezone.utc)
        for i in range(10):
            service.record_metric(
                "trust_score",
                value=0.5 + (i * 0.05),  # 0.5, 0.55, 0.60, ...
                timestamp=now - timedelta(hours=10 - i),
            )

        trend = service.analyze_trend("trust_score", period_hours=24)

        assert trend.data_points == 10
        assert trend.direction in [TrendDirection.IMPROVING, TrendDirection.STABLE]
        assert trend.current_value > trend.previous_value

    def test_analyze_trend_degrading(self):
        """Test trend analysis detects degrading trends."""
        from src.services.alignment.analytics import (
            AlignmentAnalyticsService,
            TrendDirection,
        )

        service = AlignmentAnalyticsService()

        # Record decreasing values
        now = datetime.now(timezone.utc)
        for i in range(10):
            service.record_metric(
                "trust_score",
                value=0.95 - (i * 0.05),  # 0.95, 0.90, 0.85, ...
                timestamp=now - timedelta(hours=10 - i),
            )

        trend = service.analyze_trend("trust_score", period_hours=24)

        assert trend.direction == TrendDirection.DEGRADING
        assert trend.current_value < trend.previous_value

    def test_compare_agents(self):
        """Test agent comparison functionality."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        # Record metrics for multiple agents
        service.record_metric("trust_score", 0.85, agent_id="agent-001")
        service.record_metric("trust_score", 0.75, agent_id="agent-002")
        service.record_metric("trust_score", 0.95, agent_id="agent-003")

        comparison = service.compare_agents("trust_score", period_hours=24)

        assert len(comparison.agents) == 3
        assert comparison.best_agent_id == "agent-003"
        assert comparison.worst_agent_id == "agent-002"

    def test_alert_threshold_triggering(self):
        """Test alert threshold triggering."""
        from src.services.alignment.analytics import (
            AlertSeverity,
            AlignmentAnalyticsService,
        )

        service = AlignmentAnalyticsService()

        # Record metric that should trigger critical alert (trust_score < 0.30)
        service.record_metric("trust_score", 0.25)

        alerts = service.get_alerts()

        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL
        assert alerts[0].metric_name == "trust_score"

    def test_alert_threshold_warning(self):
        """Test alert threshold triggering warning level."""
        from src.services.alignment.analytics import (
            AlertSeverity,
            AlignmentAnalyticsService,
        )

        service = AlignmentAnalyticsService()

        # Record metric that should trigger warning alert (trust_score < 0.50)
        service.record_metric("trust_score", 0.45)

        alerts = service.get_alerts()

        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_alert_cooldown(self):
        """Test alert cooldown prevents duplicate alerts."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        # Record multiple metrics that would trigger alerts
        service.record_metric("trust_score", 0.25)
        service.record_metric("trust_score", 0.20)
        service.record_metric("trust_score", 0.15)

        alerts = service.get_alerts()

        # Should only have 1 alert due to cooldown
        assert len(alerts) == 1

    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        from src.services.alignment.analytics import (
            AlertStatus,
            AlignmentAnalyticsService,
        )

        service = AlignmentAnalyticsService()

        service.record_metric("trust_score", 0.25)
        alerts = service.get_alerts()
        alert_id = alerts[0].alert_id

        result = service.acknowledge_alert(alert_id, "user-001")

        assert result is not None
        assert result.status == AlertStatus.ACKNOWLEDGED
        assert result.acknowledged_by == "user-001"

    def test_resolve_alert(self):
        """Test resolving an alert."""
        from src.services.alignment.analytics import (
            AlertStatus,
            AlignmentAnalyticsService,
        )

        service = AlignmentAnalyticsService()

        service.record_metric("trust_score", 0.25)
        alerts = service.get_alerts()
        alert_id = alerts[0].alert_id

        result = service.resolve_alert(alert_id, "user-001")

        assert result is not None
        assert result.status == AlertStatus.RESOLVED
        assert result.resolved_by == "user-001"

    def test_suppress_alert(self):
        """Test suppressing an alert."""
        from src.services.alignment.analytics import (
            AlertStatus,
            AlignmentAnalyticsService,
        )

        service = AlignmentAnalyticsService()

        service.record_metric("trust_score", 0.25)
        alerts = service.get_alerts()
        alert_id = alerts[0].alert_id

        result = service.suppress_alert(alert_id, suppress_hours=24)

        assert result is not None
        assert result.status == AlertStatus.SUPPRESSED
        assert result.suppressed_until is not None

    def test_generate_report(self):
        """Test generating alignment report."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        # Record some data
        for i in range(5):
            service.record_metric("trust_score", 0.8 + (i * 0.02), agent_id="agent-001")
            service.record_metric("disagreement_rate", 0.08, agent_id="agent-001")

        report = service.generate_report(period_hours=24)

        assert report.report_id is not None
        assert len(report.trends) > 0
        assert report.overall_health_score >= 0.0
        assert report.overall_health_score <= 1.0

    def test_get_time_series(self):
        """Test getting time series data."""
        from src.services.alignment.analytics import (
            AlignmentAnalyticsService,
            TimeGranularity,
        )

        service = AlignmentAnalyticsService()

        # Record hourly data
        now = datetime.now(timezone.utc)
        for i in range(24):
            service.record_metric(
                "trust_score",
                value=0.80 + (i * 0.005),
                timestamp=now - timedelta(hours=24 - i),
            )

        time_series = service.get_time_series(
            "trust_score",
            period_hours=24,
            granularity=TimeGranularity.HOUR,
        )

        assert len(time_series) > 0
        assert "timestamp" in time_series[0]
        assert "value" in time_series[0]

    def test_get_stats(self):
        """Test getting service statistics."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        service.record_metric("trust_score", 0.85)
        service.record_metric("trust_score", 0.25)  # Triggers alert

        stats = service.get_stats()

        assert stats["total_data_points"] == 2
        assert stats["total_alerts"] >= 1
        assert stats["retention_days"] == 90

    def test_set_threshold(self):
        """Test setting custom threshold."""
        from src.services.alignment.analytics import (
            AlertThreshold,
            AlignmentAnalyticsService,
        )

        service = AlignmentAnalyticsService()

        new_threshold = AlertThreshold(
            metric_name="custom_metric",
            warning_threshold=0.5,
            critical_threshold=0.3,
            comparison="less_than",
        )

        service.set_threshold(new_threshold)

        assert "custom_metric" in service._thresholds

    def test_clear_data(self):
        """Test clearing historical data."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        # Record data
        for i in range(10):
            service.record_metric("trust_score", 0.85)

        # Clear all data
        removed = service.clear_data()

        assert removed == 10
        assert len(service._data_points) == 0

    def test_clear_data_older_than(self):
        """Test clearing data older than specified time."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        now = datetime.now(timezone.utc)

        # Record old data
        for i in range(5):
            service.record_metric(
                "trust_score",
                0.85,
                timestamp=now - timedelta(hours=48),
            )

        # Record recent data
        for i in range(5):
            service.record_metric("trust_score", 0.85)

        # Clear data older than 24 hours
        removed = service.clear_data(older_than_hours=24)

        assert removed == 5
        assert len(service._data_points) == 5

    def test_anomaly_detection(self):
        """Test anomaly detection in trends."""
        from src.services.alignment.analytics import AlignmentAnalyticsService

        service = AlignmentAnalyticsService()

        now = datetime.now(timezone.utc)

        # Record stable values
        for i in range(9):
            service.record_metric(
                "trust_score",
                value=0.80,  # Stable at 80%
                timestamp=now - timedelta(hours=10 - i),
            )

        # Add anomaly
        service.record_metric(
            "trust_score",
            value=0.20,  # Sudden drop
            timestamp=now,
        )

        trend = service.analyze_trend("trust_score", period_hours=24)

        # Current value is much lower than mean, should detect anomaly
        assert trend.is_anomaly or trend.anomaly_score > 0.5


# =============================================================================
# Package Exports Tests
# =============================================================================


class TestPhase3PackageExports:
    """Test that Phase 3 classes are properly exported."""

    def test_analytics_exports(self):
        """Test analytics classes are exported from package."""
        from src.services.alignment import (
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

        # All classes should be importable
        assert AlignmentAnalyticsService is not None
        assert AlignmentAlert is not None
        assert AlignmentReport is not None
        assert TrendAnalysis is not None
        assert TrendDirection is not None
        assert TimeGranularity is not None
        assert AlertSeverity is not None
        assert AlertStatus is not None
        assert AlertThreshold is not None
        assert MetricDataPoint is not None
        assert AgentComparison is not None


# =============================================================================
# API Endpoints Tests
# =============================================================================


class TestAlignmentEndpoints:
    """Tests for alignment API endpoints."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        from src.services.alignment.analytics import (
            AlertSeverity,
            AlertStatus,
            AlignmentAlert,
            TrendAnalysis,
            TrendDirection,
        )
        from src.services.alignment.reversibility import ActionClass
        from src.services.alignment.rollback_service import RollbackCapability
        from src.services.alignment.trust_autonomy import OverrideRecord
        from src.services.alignment.trust_calculator import AutonomyLevel

        # Create mock analytics service
        mock_analytics = MagicMock()
        mock_analytics.get_alerts.return_value = [
            AlignmentAlert(
                alert_id="alert-001",
                severity=AlertSeverity.WARNING,
                status=AlertStatus.ACTIVE,
                metric_name="trust_score",
                threshold_value=0.50,
                actual_value=0.45,
                message="Trust score below warning threshold",
                agent_id="agent-001",
                triggered_at=datetime.now(timezone.utc),
            )
        ]
        mock_analytics.analyze_trend.return_value = TrendAnalysis(
            metric_name="trust_score",
            direction=TrendDirection.STABLE,
            slope=0.0,
            confidence=0.8,
            current_value=0.85,
            previous_value=0.83,
            change_percent=2.4,
            period_start=datetime.now(timezone.utc) - timedelta(hours=24),
            period_end=datetime.now(timezone.utc),
            data_points=100,
        )
        mock_analytics.acknowledge_alert.return_value = AlignmentAlert(
            alert_id="alert-001",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACKNOWLEDGED,
            metric_name="trust_score",
            threshold_value=0.50,
            actual_value=0.45,
            message="Trust score below warning threshold",
            agent_id="agent-001",
            triggered_at=datetime.now(timezone.utc),
            acknowledged_at=datetime.now(timezone.utc),
            acknowledged_by="user-001",
        )

        # Create mock metrics service
        mock_metrics = MagicMock()
        mock_metrics.get_health.return_value = MagicMock(
            overall_score=0.85,
            trust=MagicMock(avg_trust_score=0.82),
            transparency=MagicMock(audit_trail_completeness=0.95),
            reversibility=MagicMock(class_a_snapshot_coverage=0.98),
        )

        # Create mock sycophancy guard
        mock_guard = MagicMock()
        mock_guard.get_validation_stats.return_value = {
            "violation_rate": 0.02,
            "agents_tracked": 5,
        }

        # Create mock trust autonomy
        mock_autonomy = MagicMock()
        mock_autonomy.get_agent_autonomy_level.return_value = AutonomyLevel.RECOMMEND
        mock_autonomy.grant_temporary_override.return_value = OverrideRecord(
            agent_id="agent-001",
            override_type="promotion",
            old_level=AutonomyLevel.RECOMMEND,
            new_level=AutonomyLevel.EXECUTE_REVIEW,
            reason="Testing",
            overridden_by="user-001",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        # Create mock rollback service
        mock_rollback = MagicMock()
        mock_rollback.get_rollback_capability.return_value = RollbackCapability(
            action_id="action-001",
            action_class=ActionClass.FULLY_REVERSIBLE,
            can_rollback=True,
            snapshot_available=True,
            plan_available=False,
            estimated_duration_seconds=30,
            potential_side_effects=[],
            requires_downtime=False,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

        return {
            "analytics": mock_analytics,
            "metrics": mock_metrics,
            "guard": mock_guard,
            "autonomy": mock_autonomy,
            "rollback": mock_rollback,
        }

    def test_get_alignment_health(self, mock_services):
        """Test getting alignment health endpoint."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api import alignment_endpoints
        from src.api.alignment_endpoints import get_current_user, router
        from src.api.auth import User

        # Set up mocks
        alignment_endpoints.set_analytics_service(mock_services["analytics"])
        alignment_endpoints.set_metrics_service(mock_services["metrics"])
        alignment_endpoints.set_sycophancy_guard(mock_services["guard"])

        # Create test app
        app = FastAPI()
        app.include_router(router)

        # Override authentication dependency
        mock_user = User(sub="test-user", email="test@example.com", groups=["admin"])
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            client = TestClient(app)
            response = client.get("/api/v1/alignment/health")

            assert response.status_code == 200
            data = response.json()
            assert "overall_score" in data
            assert "status" in data
            assert "trust_score" in data
        finally:
            app.dependency_overrides.clear()

    def test_get_alerts(self, mock_services):
        """Test getting alerts endpoint."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api import alignment_endpoints
        from src.api.alignment_endpoints import get_current_user, router
        from src.api.auth import User

        alignment_endpoints.set_analytics_service(mock_services["analytics"])

        app = FastAPI()
        app.include_router(router)

        mock_user = User(sub="test-user", email="test@example.com", groups=["admin"])
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            client = TestClient(app)
            response = client.get("/api/v1/alignment/alerts")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            if len(data) > 0:
                assert "alert_id" in data[0]
                assert "severity" in data[0]
        finally:
            app.dependency_overrides.clear()

    def test_acknowledge_alert(self, mock_services):
        """Test acknowledging alert endpoint."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api import alignment_endpoints
        from src.api.alignment_endpoints import get_current_user, router
        from src.api.auth import User

        alignment_endpoints.set_analytics_service(mock_services["analytics"])

        app = FastAPI()
        app.include_router(router)

        mock_user = User(sub="test-user", email="test@example.com", groups=["admin"])
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            client = TestClient(app)
            response = client.post("/api/v1/alignment/alerts/alert-001/acknowledge")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "acknowledged"
        finally:
            app.dependency_overrides.clear()

    def test_get_trends(self, mock_services):
        """Test getting trends endpoint."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api import alignment_endpoints
        from src.api.alignment_endpoints import get_current_user, router
        from src.api.auth import User

        alignment_endpoints.set_analytics_service(mock_services["analytics"])

        app = FastAPI()
        app.include_router(router)

        mock_user = User(sub="test-user", email="test@example.com", groups=["admin"])
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            client = TestClient(app)
            response = client.get("/api/v1/alignment/trends?period_hours=24")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
        finally:
            app.dependency_overrides.clear()

    def test_get_rollback_capability(self, mock_services):
        """Test getting rollback capability endpoint."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api import alignment_endpoints
        from src.api.alignment_endpoints import get_current_user, router
        from src.api.auth import User

        alignment_endpoints.set_rollback_service(mock_services["rollback"])

        app = FastAPI()
        app.include_router(router)

        mock_user = User(sub="test-user", email="test@example.com", groups=["admin"])
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            client = TestClient(app)
            response = client.get("/api/v1/alignment/rollback/action-001/capability")

            assert response.status_code == 200
            data = response.json()
            assert data["can_rollback"] is True
            assert data["snapshot_available"] is True
        finally:
            app.dependency_overrides.clear()


# =============================================================================
# Integration Tests
# =============================================================================


class TestPhase3Integration:
    """Integration tests for Phase 3 components."""

    def test_analytics_with_metrics_service(self):
        """Test analytics service integrates with metrics service."""
        from src.services.alignment.analytics import AlignmentAnalyticsService
        from src.services.alignment.metrics_service import AlignmentMetricsService

        analytics = AlignmentAnalyticsService()
        metrics = AlignmentMetricsService()

        # Record metrics through metrics service
        metrics.record_interaction("agent-001", disagreed_with_user=True)
        metrics.record_confidence_prediction(
            "agent-001", predicted_confidence=0.8, actual_outcome_correct=True
        )

        # Get health from metrics service
        health = metrics.get_health()

        # Record analytics based on health status
        # AlignmentHealth returns status enums, not numeric values
        # Use 1.0 for healthy, 0.5 for warning, 0.0 for critical
        from src.services.alignment.metrics_service import MetricStatus

        trust_score = (
            1.0
            if health.trust_status == MetricStatus.HEALTHY
            else 0.5 if health.trust_status == MetricStatus.WARNING else 0.0
        )
        analytics.record_metric("trust_score", trust_score)

        transparency_score = (
            1.0
            if health.transparency_status == MetricStatus.HEALTHY
            else 0.5 if health.transparency_status == MetricStatus.WARNING else 0.0
        )
        analytics.record_metric("transparency_score", transparency_score)

        # Generate report
        report = analytics.generate_report()

        assert report.overall_health_score >= 0.0

    def test_analytics_with_sycophancy_guard(self):
        """Test analytics service integrates with sycophancy guard."""
        from src.services.alignment.analytics import AlignmentAnalyticsService
        from src.services.alignment.sycophancy_guard import (
            ResponseContext,
            ResponseSeverity,
            SycophancyGuard,
        )

        analytics = AlignmentAnalyticsService()
        guard = SycophancyGuard()

        # Validate a response
        context = ResponseContext(
            response_text="I disagree with that approach.",
            agent_id="agent-001",
            user_query="Should we use microservices?",
            severity=ResponseSeverity.MEDIUM,
            stated_confidence=0.75,
            alternatives_presented=1,
        )

        result = guard.validate_response(context)

        # Record analytics based on validation
        if result.is_valid:
            analytics.record_metric("sycophancy_health", 1.0, agent_id="agent-001")
        else:
            analytics.record_metric("sycophancy_health", 0.0, agent_id="agent-001")

        stats = analytics.get_stats()
        assert stats["total_data_points"] >= 1

    def test_analytics_with_rollback_service(self):
        """Test analytics service integrates with rollback service."""
        from src.services.alignment.analytics import AlignmentAnalyticsService
        from src.services.alignment.rollback_service import RollbackService

        analytics = AlignmentAnalyticsService()
        rollback = RollbackService()

        # Create a snapshot
        snapshot = rollback.create_snapshot(
            action_id="action-001",
            resource_type="file",
            resource_id="/path/to/file.py",
            state_data={"content": "original content"},
        )

        # Record analytics
        analytics.record_metric(
            "rollback_snapshot_created",
            1.0,
            metadata={"action_id": snapshot.action_id},
        )

        # Check capability
        capability = rollback.get_rollback_capability("action-001")

        if capability.can_rollback:
            analytics.record_metric("rollback_available", 1.0)
        else:
            analytics.record_metric("rollback_available", 0.0)

        stats = analytics.get_stats()
        assert stats["total_data_points"] >= 2

    def test_end_to_end_alignment_flow(self):
        """Test complete alignment monitoring flow."""
        from src.services.alignment.analytics import (
            AlertStatus,
            AlignmentAnalyticsService,
        )
        from src.services.alignment.metrics_service import AlignmentMetricsService
        from src.services.alignment.rollback_service import RollbackService
        from src.services.alignment.sycophancy_guard import SycophancyGuard
        from src.services.alignment.trust_autonomy import TrustBasedAutonomy

        # Initialize all services
        analytics = AlignmentAnalyticsService()
        metrics = AlignmentMetricsService()
        guard = SycophancyGuard()
        autonomy = TrustBasedAutonomy()
        rollback = RollbackService()

        # Simulate agent activity
        agent_id = "agent-001"

        # 1. Record trust metrics
        analytics.record_metric("trust_score", 0.85, agent_id=agent_id)

        # 2. Record disagreement
        guard.record_disagreement(agent_id, disagreed=True)
        metrics.record_interaction(agent_id, disagreed_with_user=True)

        # 3. Create rollback snapshot
        rollback.create_snapshot(
            action_id="action-001",
            resource_type="config",
            resource_id="settings.yaml",
            state_data={"key": "value"},
        )

        # 4. Generate report
        report = analytics.generate_report(period_hours=1)

        # Verify
        assert report.overall_health_score >= 0.0
        assert report.report_id is not None

        # 5. Get and resolve any alerts
        alerts = analytics.get_alerts(status=AlertStatus.ACTIVE)
        for alert in alerts:
            analytics.resolve_alert(alert.alert_id, "test-user")

        # Verify all alerts resolved
        active_alerts = analytics.get_alerts(status=AlertStatus.ACTIVE)
        assert len(active_alerts) == 0
