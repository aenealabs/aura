"""
Project Aura - Incident Pattern Analyzer Tests

Tests for the IncidentPatternAnalyzer service that implements
comprehensive incident analysis and pattern detection per ADR-030.
"""

from datetime import datetime, timedelta, timezone

from src.services.devops.incident_pattern_analyzer import (
    AlertSeverity,
    Incident,
    IncidentCategory,
    IncidentMetrics,
    IncidentPattern,
    IncidentSeverity,
    IncidentStatus,
    IncidentTimeline,
    PatternType,
    PredictiveAlert,
    RootCauseAnalysis,
    RootCauseCategory,
    RunbookRecommendation,
    SLODefinition,
    SLOStatus,
)


class TestIncidentSeverity:
    """Tests for IncidentSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert IncidentSeverity.SEV1.value == "sev1"
        assert IncidentSeverity.SEV2.value == "sev2"
        assert IncidentSeverity.SEV3.value == "sev3"
        assert IncidentSeverity.SEV4.value == "sev4"

    def test_severity_ordering(self):
        """Test that all severities are defined."""
        severities = list(IncidentSeverity)
        assert len(severities) == 4


class TestIncidentStatus:
    """Tests for IncidentStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert IncidentStatus.DETECTED.value == "detected"
        assert IncidentStatus.ACKNOWLEDGED.value == "acknowledged"
        assert IncidentStatus.INVESTIGATING.value == "investigating"
        assert IncidentStatus.IDENTIFIED.value == "identified"
        assert IncidentStatus.MITIGATING.value == "mitigating"
        assert IncidentStatus.RESOLVED.value == "resolved"
        assert IncidentStatus.CLOSED.value == "closed"

    def test_all_statuses(self):
        """Test that all lifecycle statuses are defined."""
        statuses = list(IncidentStatus)
        assert len(statuses) == 7


class TestIncidentCategory:
    """Tests for IncidentCategory enum."""

    def test_category_values(self):
        """Test category enum values."""
        assert IncidentCategory.AVAILABILITY.value == "availability"
        assert IncidentCategory.LATENCY.value == "latency"
        assert IncidentCategory.ERROR_RATE.value == "error_rate"
        assert IncidentCategory.SECURITY.value == "security"

    def test_all_categories(self):
        """Test that all categories are defined."""
        categories = list(IncidentCategory)
        assert len(categories) == 8


class TestRootCauseCategory:
    """Tests for RootCauseCategory enum."""

    def test_root_cause_values(self):
        """Test root cause category values."""
        assert RootCauseCategory.CODE_CHANGE.value == "code_change"
        assert RootCauseCategory.INFRASTRUCTURE.value == "infrastructure"
        assert RootCauseCategory.HUMAN_ERROR.value == "human_error"
        assert RootCauseCategory.UNKNOWN.value == "unknown"

    def test_all_root_causes(self):
        """Test that all root cause categories are defined."""
        categories = list(RootCauseCategory)
        assert len(categories) == 10


class TestPatternType:
    """Tests for PatternType enum."""

    def test_pattern_type_values(self):
        """Test pattern type values."""
        assert PatternType.RECURRING.value == "recurring"
        assert PatternType.CASCADING.value == "cascading"
        assert PatternType.TIME_BASED.value == "time_based"
        assert PatternType.DEPLOYMENT_RELATED.value == "deployment_related"


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_alert_severity_values(self):
        """Test alert severity values."""
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.INFO.value == "info"


class TestIncidentTimeline:
    """Tests for IncidentTimeline dataclass."""

    def test_timeline_creation(self):
        """Test basic timeline event creation."""
        now = datetime.now(timezone.utc)
        event = IncidentTimeline(
            timestamp=now,
            event_type="detected",
            description="Alert triggered by monitoring",
        )
        assert event.timestamp == now
        assert event.event_type == "detected"
        assert event.description == "Alert triggered by monitoring"
        assert event.actor == ""
        assert event.metadata == {}

    def test_timeline_with_actor(self):
        """Test timeline event with actor."""
        event = IncidentTimeline(
            timestamp=datetime.now(timezone.utc),
            event_type="acknowledged",
            description="Incident acknowledged",
            actor="oncall@example.com",
        )
        assert event.actor == "oncall@example.com"

    def test_timeline_with_metadata(self):
        """Test timeline event with metadata."""
        metadata = {"alert_id": "alert-123", "severity": "critical"}
        event = IncidentTimeline(
            timestamp=datetime.now(timezone.utc),
            event_type="escalated",
            description="Escalated to management",
            metadata=metadata,
        )
        assert event.metadata == metadata


class TestIncidentMetrics:
    """Tests for IncidentMetrics dataclass."""

    def test_metrics_defaults(self):
        """Test default metrics values."""
        metrics = IncidentMetrics()
        assert metrics.error_rate_peak == 0.0
        assert metrics.latency_p99_peak_ms == 0.0
        assert metrics.availability_nadir == 100.0
        assert metrics.requests_affected == 0
        assert metrics.users_affected == 0
        assert metrics.time_to_detect_seconds == 0.0
        assert metrics.mttr_seconds == 0.0

    def test_metrics_with_values(self):
        """Test metrics with custom values."""
        metrics = IncidentMetrics(
            error_rate_peak=25.5,
            latency_p99_peak_ms=5000.0,
            availability_nadir=85.0,
            requests_affected=50000,
            users_affected=1200,
            time_to_detect_seconds=120.0,
            mttr_seconds=1800.0,
        )
        assert metrics.error_rate_peak == 25.5
        assert metrics.latency_p99_peak_ms == 5000.0
        assert metrics.users_affected == 1200
        assert metrics.mttr_seconds == 1800.0


class TestIncident:
    """Tests for Incident dataclass."""

    def test_incident_creation_minimal(self):
        """Test minimal incident creation."""
        now = datetime.now(timezone.utc)
        incident = Incident(
            incident_id="inc-001",
            title="API Gateway Outage",
            description="Complete API gateway failure",
            severity=IncidentSeverity.SEV1,
            status=IncidentStatus.DETECTED,
            category=IncidentCategory.AVAILABILITY,
            affected_services=["api-gateway"],
            affected_regions=["us-east-1"],
            customer_impact="All API requests failing",
            detected_at=now,
        )
        assert incident.incident_id == "inc-001"
        assert incident.severity == IncidentSeverity.SEV1
        assert incident.status == IncidentStatus.DETECTED
        assert incident.affected_services == ["api-gateway"]

    def test_incident_defaults(self):
        """Test incident default values."""
        incident = Incident(
            incident_id="inc-002",
            title="Test Incident",
            description="Test",
            severity=IncidentSeverity.SEV3,
            status=IncidentStatus.DETECTED,
            category=IncidentCategory.LATENCY,
            affected_services=["service-a"],
            affected_regions=["us-west-2"],
            customer_impact="Slow responses",
            detected_at=datetime.now(timezone.utc),
        )
        assert incident.root_cause == ""
        assert incident.root_cause_category == RootCauseCategory.UNKNOWN
        assert incident.contributing_factors == []
        assert incident.timeline == []
        assert incident.postmortem_url == ""

    def test_incident_full(self):
        """Test incident with all fields."""
        now = datetime.now(timezone.utc)
        incident = Incident(
            incident_id="inc-003",
            title="Database Connectivity Issues",
            description="Intermittent database connection failures",
            severity=IncidentSeverity.SEV2,
            status=IncidentStatus.RESOLVED,
            category=IncidentCategory.ERROR_RATE,
            affected_services=["user-service", "order-service"],
            affected_regions=["us-east-1", "eu-west-1"],
            customer_impact="Failed transactions",
            detected_at=now - timedelta(hours=2),
            acknowledged_at=now - timedelta(hours=1, minutes=55),
            resolved_at=now,
            root_cause="Connection pool exhaustion",
            root_cause_category=RootCauseCategory.CONFIGURATION_CHANGE,
            contributing_factors=["High traffic", "Slow queries"],
            incident_commander="lead@example.com",
            responders=["dev1@example.com", "dev2@example.com"],
        )
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.root_cause_category == RootCauseCategory.CONFIGURATION_CHANGE
        assert len(incident.responders) == 2


class TestIncidentPattern:
    """Tests for IncidentPattern dataclass."""

    def test_pattern_creation(self):
        """Test pattern creation."""
        now = datetime.now(timezone.utc)
        pattern = IncidentPattern(
            pattern_id="pat-001",
            pattern_type=PatternType.RECURRING,
            name="Monday Morning Outages",
            description="Recurring outages every Monday morning",
            matching_incidents=["inc-001", "inc-005", "inc-010"],
            occurrence_count=3,
            first_occurrence=now - timedelta(days=30),
            last_occurrence=now - timedelta(days=7),
            common_services=["api-gateway"],
            common_root_causes=["capacity"],
            common_time_windows=["Monday 8-10 AM"],
            average_severity=1.5,
            average_mttr_seconds=3600.0,
            confidence_score=0.85,
            recommended_actions=["Add capacity before Monday"],
            prevention_suggestions=["Pre-scale on Sunday night"],
        )
        assert pattern.pattern_id == "pat-001"
        assert pattern.pattern_type == PatternType.RECURRING
        assert pattern.occurrence_count == 3
        assert pattern.confidence_score == 0.85


class TestRootCauseAnalysis:
    """Tests for RootCauseAnalysis dataclass."""

    def test_rca_creation(self):
        """Test root cause analysis creation."""
        rca = RootCauseAnalysis(
            analysis_id="rca-001",
            incident_id="inc-001",
            root_cause="Memory leak in user service",
            root_cause_category=RootCauseCategory.CODE_CHANGE,
            confidence=0.92,
            evidence=["Memory graphs", "Heap dumps", "Deployment correlation"],
            timeline_analysis="Memory increased after deploy-123",
            contributing_factors=["High traffic", "No memory limits"],
            ruled_out=["Network issues", "Database problems"],
            correlated_events=[{"type": "deployment", "id": "deploy-123"}],
            correlated_deployments=["deploy-123"],
            immediate_actions=["Rollback to previous version"],
            long_term_fixes=["Fix memory leak", "Add memory limits"],
            prevention_measures=["Memory profiling in CI"],
        )
        assert rca.analysis_id == "rca-001"
        assert rca.root_cause_category == RootCauseCategory.CODE_CHANGE
        assert rca.confidence == 0.92
        assert len(rca.evidence) == 3


class TestRunbookRecommendation:
    """Tests for RunbookRecommendation dataclass."""

    def test_runbook_creation(self):
        """Test runbook recommendation creation."""
        runbook = RunbookRecommendation(
            runbook_id="rb-001",
            name="API Gateway Recovery",
            description="Steps to recover API gateway",
            relevance_score=0.95,
            matching_factors=["api-gateway", "availability"],
            estimated_resolution_time="15 minutes",
            steps=["Check health", "Restart service", "Verify traffic"],
        )
        assert runbook.runbook_id == "rb-001"
        assert runbook.relevance_score == 0.95
        assert runbook.automation_available is False

    def test_runbook_with_automation(self):
        """Test runbook with automation available."""
        runbook = RunbookRecommendation(
            runbook_id="rb-002",
            name="Auto-scale EKS",
            description="Automatically scale EKS cluster",
            relevance_score=0.88,
            matching_factors=["eks", "capacity"],
            estimated_resolution_time="5 minutes",
            steps=["Trigger auto-scaler"],
            automation_available=True,
        )
        assert runbook.automation_available is True


class TestSLODefinition:
    """Tests for SLODefinition dataclass."""

    def test_slo_definition_defaults(self):
        """Test SLO definition with defaults."""
        slo = SLODefinition(
            slo_id="slo-001",
            name="API Availability",
            service="api-gateway",
            objective_type="availability",
            target_value=99.9,
        )
        assert slo.slo_id == "slo-001"
        assert slo.window_days == 30
        assert slo.burn_rate_threshold == 1.0
        assert slo.error_budget_policy == ""

    def test_slo_definition_full(self):
        """Test SLO definition with all fields."""
        slo = SLODefinition(
            slo_id="slo-002",
            name="API Latency P99",
            service="api-gateway",
            objective_type="latency",
            target_value=200.0,
            window_days=7,
            burn_rate_threshold=2.0,
            error_budget_policy="Freeze deploys if budget < 10%",
        )
        assert slo.window_days == 7
        assert slo.burn_rate_threshold == 2.0


class TestSLOStatus:
    """Tests for SLOStatus dataclass."""

    def test_slo_status_creation(self):
        """Test SLO status creation."""
        now = datetime.now(timezone.utc)
        status = SLOStatus(
            slo_id="slo-001",
            slo_name="API Availability",
            service="api-gateway",
            current_value=99.85,
            target_value=99.9,
            error_budget_remaining=15.0,
            error_budget_consumed=85.0,
            burn_rate=1.5,
            projected_breach_date=now + timedelta(days=3),
            status="warning",
            window_start=now - timedelta(days=30),
            window_end=now,
        )
        assert status.current_value == 99.85
        assert status.error_budget_consumed == 85.0
        assert status.status == "warning"

    def test_slo_status_healthy(self):
        """Test healthy SLO status."""
        now = datetime.now(timezone.utc)
        status = SLOStatus(
            slo_id="slo-002",
            slo_name="API Latency",
            service="api-gateway",
            current_value=99.99,
            target_value=99.9,
            error_budget_remaining=95.0,
            error_budget_consumed=5.0,
            burn_rate=0.2,
            projected_breach_date=None,
            status="healthy",
            window_start=now - timedelta(days=30),
            window_end=now,
        )
        assert status.status == "healthy"
        assert status.projected_breach_date is None


class TestPredictiveAlert:
    """Tests for PredictiveAlert dataclass."""

    def test_predictive_alert_creation(self):
        """Test predictive alert creation."""
        alert = PredictiveAlert(
            alert_id="alert-001",
            alert_type="capacity_exhaustion",
            severity=AlertSeverity.WARNING,
            title="Predicted Memory Exhaustion",
            description="Memory usage trending toward exhaustion",
            predicted_incident_type="availability",
            confidence=0.78,
            prediction_basis=["Memory trend", "Traffic forecast"],
            recommended_actions=["Scale up nodes", "Add memory"],
            affected_services=["user-service"],
        )
        assert alert.alert_id == "alert-001"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.confidence == 0.78
        assert alert.predicted_time is None

    def test_predictive_alert_with_time(self):
        """Test predictive alert with predicted time."""
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        alert = PredictiveAlert(
            alert_id="alert-002",
            alert_type="slo_breach",
            severity=AlertSeverity.CRITICAL,
            title="Predicted SLO Breach",
            description="SLO breach predicted in 2 hours",
            predicted_incident_type="latency",
            confidence=0.92,
            prediction_basis=["Burn rate analysis"],
            recommended_actions=["Investigate latency"],
            affected_services=["api-gateway"],
            predicted_time=future,
        )
        assert alert.predicted_time is not None
        assert alert.severity == AlertSeverity.CRITICAL
