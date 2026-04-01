"""
Project Aura - Deployment History Correlator Tests

Tests for the deployment tracking and incident correlation service.
"""

import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

# Save original modules before mocking to prevent test pollution
_modules_to_save = ["structlog", "src.services.devops.deployment_history_correlator"]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock structlog
mock_structlog = MagicMock()
mock_structlog.get_logger = MagicMock(return_value=MagicMock())
sys.modules["structlog"] = mock_structlog

from src.services.devops.deployment_history_correlator import (
    BlastRadiusAnalysis,
    ChangeCategory,
    ChangeWindow,
    CorrelationConfidence,
    Deployment,
    DeploymentArtifact,
    DeploymentChange,
    DeploymentCorrelation,
    DeploymentHealthReport,
    DeploymentHistoryCorrelator,
    DeploymentMetrics,
    DeploymentStatus,
    DeploymentTarget,
    DeploymentType,
    Incident,
    IncidentSeverity,
    RiskLevel,
    RollbackRecommendation,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


class TestDeploymentStatus:
    """Tests for DeploymentStatus enum."""

    def test_pending_status(self):
        """Test pending status."""
        assert DeploymentStatus.PENDING.value == "pending"

    def test_in_progress_status(self):
        """Test in progress status."""
        assert DeploymentStatus.IN_PROGRESS.value == "in_progress"

    def test_succeeded_status(self):
        """Test succeeded status."""
        assert DeploymentStatus.SUCCEEDED.value == "succeeded"

    def test_failed_status(self):
        """Test failed status."""
        assert DeploymentStatus.FAILED.value == "failed"

    def test_rolled_back_status(self):
        """Test rolled back status."""
        assert DeploymentStatus.ROLLED_BACK.value == "rolled_back"

    def test_cancelled_status(self):
        """Test cancelled status."""
        assert DeploymentStatus.CANCELLED.value == "cancelled"

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        statuses = list(DeploymentStatus)
        assert len(statuses) == 6


class TestDeploymentType:
    """Tests for DeploymentType enum."""

    def test_rolling_type(self):
        """Test rolling deployment type."""
        assert DeploymentType.ROLLING.value == "rolling"

    def test_blue_green_type(self):
        """Test blue-green deployment type."""
        assert DeploymentType.BLUE_GREEN.value == "blue_green"

    def test_canary_type(self):
        """Test canary deployment type."""
        assert DeploymentType.CANARY.value == "canary"

    def test_recreate_type(self):
        """Test recreate deployment type."""
        assert DeploymentType.RECREATE.value == "recreate"

    def test_feature_flag_type(self):
        """Test feature flag deployment type."""
        assert DeploymentType.FEATURE_FLAG.value == "feature_flag"

    def test_database_migration_type(self):
        """Test database migration type."""
        assert DeploymentType.DATABASE_MIGRATION.value == "database_migration"

    def test_infrastructure_type(self):
        """Test infrastructure deployment type."""
        assert DeploymentType.INFRASTRUCTURE.value == "infrastructure"

    def test_configuration_type(self):
        """Test configuration deployment type."""
        assert DeploymentType.CONFIGURATION.value == "configuration"


class TestChangeCategory:
    """Tests for ChangeCategory enum."""

    def test_code_category(self):
        """Test code category."""
        assert ChangeCategory.CODE.value == "code"

    def test_configuration_category(self):
        """Test configuration category."""
        assert ChangeCategory.CONFIGURATION.value == "configuration"

    def test_infrastructure_category(self):
        """Test infrastructure category."""
        assert ChangeCategory.INFRASTRUCTURE.value == "infrastructure"

    def test_dependency_category(self):
        """Test dependency category."""
        assert ChangeCategory.DEPENDENCY.value == "dependency"

    def test_database_category(self):
        """Test database category."""
        assert ChangeCategory.DATABASE.value == "database"

    def test_security_category(self):
        """Test security category."""
        assert ChangeCategory.SECURITY.value == "security"

    def test_feature_flag_category(self):
        """Test feature flag category."""
        assert ChangeCategory.FEATURE_FLAG.value == "feature_flag"


class TestIncidentSeverity:
    """Tests for IncidentSeverity enum."""

    def test_sev1(self):
        """Test SEV1 severity."""
        assert IncidentSeverity.SEV1.value == "sev1"

    def test_sev2(self):
        """Test SEV2 severity."""
        assert IncidentSeverity.SEV2.value == "sev2"

    def test_sev3(self):
        """Test SEV3 severity."""
        assert IncidentSeverity.SEV3.value == "sev3"

    def test_sev4(self):
        """Test SEV4 severity."""
        assert IncidentSeverity.SEV4.value == "sev4"


class TestCorrelationConfidence:
    """Tests for CorrelationConfidence enum."""

    def test_high_confidence(self):
        """Test high confidence."""
        assert CorrelationConfidence.HIGH.value == "high"

    def test_medium_confidence(self):
        """Test medium confidence."""
        assert CorrelationConfidence.MEDIUM.value == "medium"

    def test_low_confidence(self):
        """Test low confidence."""
        assert CorrelationConfidence.LOW.value == "low"


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_critical_risk(self):
        """Test critical risk level."""
        assert RiskLevel.CRITICAL.value == "critical"

    def test_high_risk(self):
        """Test high risk level."""
        assert RiskLevel.HIGH.value == "high"

    def test_medium_risk(self):
        """Test medium risk level."""
        assert RiskLevel.MEDIUM.value == "medium"

    def test_low_risk(self):
        """Test low risk level."""
        assert RiskLevel.LOW.value == "low"


class TestDeploymentChange:
    """Tests for DeploymentChange dataclass."""

    def test_minimal_change(self):
        """Test minimal change creation."""
        change = DeploymentChange(
            change_id="chg-123",
            category=ChangeCategory.CODE,
            description="Update user service",
        )
        assert change.change_id == "chg-123"
        assert change.category == ChangeCategory.CODE
        assert change.files_changed == []

    def test_change_with_files(self):
        """Test change with files."""
        change = DeploymentChange(
            change_id="chg-files",
            category=ChangeCategory.CODE,
            description="Update API",
            files_changed=["api/handler.py", "api/models.py"],
            commit_sha="abc123",
            author="developer@example.com",
        )
        assert len(change.files_changed) == 2
        assert change.commit_sha == "abc123"

    def test_change_with_risk(self):
        """Test change with risk score."""
        change = DeploymentChange(
            change_id="chg-risk",
            category=ChangeCategory.DATABASE,
            description="Schema migration",
            risk_score=0.8,
            ticket_id="JIRA-123",
        )
        assert change.risk_score == 0.8
        assert change.ticket_id == "JIRA-123"


class TestDeploymentArtifact:
    """Tests for DeploymentArtifact dataclass."""

    def test_artifact_creation(self):
        """Test artifact creation."""
        artifact = DeploymentArtifact(
            artifact_id="art-123",
            name="api-service",
            version="1.2.3",
            artifact_type="container",
        )
        assert artifact.artifact_id == "art-123"
        assert artifact.version == "1.2.3"

    def test_artifact_with_registry(self):
        """Test artifact with registry info."""
        artifact = DeploymentArtifact(
            artifact_id="art-reg",
            name="web-app",
            version="2.0.0",
            artifact_type="container",
            registry="123456789.dkr.ecr.us-east-1.amazonaws.com",
            sha256="sha256:abcdef123456",
            size_bytes=50000000,
            build_id="build-789",
        )
        assert "amazonaws.com" in artifact.registry
        assert artifact.size_bytes == 50000000


class TestDeploymentTarget:
    """Tests for DeploymentTarget dataclass."""

    def test_target_creation(self):
        """Test target creation."""
        target = DeploymentTarget(
            target_id="target-123",
            name="api-cluster",
            environment="production",
            region="us-east-1",
            resource_type="eks",
        )
        assert target.target_id == "target-123"
        assert target.environment == "production"

    def test_target_with_replicas(self):
        """Test target with replicas."""
        target = DeploymentTarget(
            target_id="target-replicas",
            name="worker-cluster",
            environment="staging",
            region="us-west-2",
            resource_type="ecs",
            replica_count=5,
            current_version="1.0.0",
        )
        assert target.replica_count == 5


class TestDeploymentMetrics:
    """Tests for DeploymentMetrics dataclass."""

    def test_default_metrics(self):
        """Test default metrics values."""
        metrics = DeploymentMetrics()
        assert metrics.duration_seconds == 0.0
        assert metrics.replicas_updated == 0
        assert metrics.error_rate_before == 0.0

    def test_metrics_with_values(self):
        """Test metrics with values."""
        metrics = DeploymentMetrics(
            duration_seconds=300.0,
            replicas_updated=5,
            replicas_failed=0,
            error_rate_before=0.01,
            error_rate_after=0.02,
            latency_p99_before=100.0,
            latency_p99_after=150.0,
        )
        assert metrics.duration_seconds == 300.0
        assert metrics.latency_p99_after == 150.0


class TestDeployment:
    """Tests for Deployment dataclass."""

    def test_minimal_deployment(self):
        """Test minimal deployment creation."""
        deployment = Deployment(
            deployment_id="dep-123",
            name="API Update",
            description="Update API to v2",
            deployment_type=DeploymentType.ROLLING,
            status=DeploymentStatus.SUCCEEDED,
            changes=[],
            artifacts=[],
            targets=[],
            environment="production",
            initiated_by="deploy-bot",
        )
        assert deployment.deployment_id == "dep-123"
        assert deployment.status == DeploymentStatus.SUCCEEDED

    def test_deployment_with_changes(self):
        """Test deployment with changes."""
        change = DeploymentChange(
            change_id="chg-1",
            category=ChangeCategory.CODE,
            description="Bug fix",
        )
        deployment = Deployment(
            deployment_id="dep-changes",
            name="Bug Fix",
            description="Fix critical bug",
            deployment_type=DeploymentType.CANARY,
            status=DeploymentStatus.IN_PROGRESS,
            changes=[change],
            artifacts=[],
            targets=[],
            environment="staging",
            initiated_by="developer",
        )
        assert len(deployment.changes) == 1

    def test_deployment_with_risk(self):
        """Test deployment with risk assessment."""
        deployment = Deployment(
            deployment_id="dep-risky",
            name="Major Update",
            description="Major refactor",
            deployment_type=DeploymentType.BLUE_GREEN,
            status=DeploymentStatus.PENDING,
            changes=[],
            artifacts=[],
            targets=[],
            environment="production",
            initiated_by="release-manager",
            risk_level=RiskLevel.HIGH,
            risk_factors=["Database migration", "Breaking API changes"],
        )
        assert deployment.risk_level == RiskLevel.HIGH
        assert len(deployment.risk_factors) == 2


class TestIncident:
    """Tests for Incident dataclass."""

    def test_minimal_incident(self):
        """Test minimal incident creation."""
        incident = Incident(
            incident_id="inc-123",
            title="API Latency Spike",
            description="API response times increased",
            severity=IncidentSeverity.SEV2,
            status="investigating",
            affected_services=["api-gateway"],
            affected_regions=["us-east-1"],
            customer_impact="Increased latency for 10% of users",
            detected_at=datetime.now(timezone.utc),
        )
        assert incident.severity == IncidentSeverity.SEV2
        assert len(incident.affected_services) == 1

    def test_incident_with_metrics(self):
        """Test incident with metrics."""
        incident = Incident(
            incident_id="inc-metrics",
            title="Error Rate Spike",
            description="5xx errors increased",
            severity=IncidentSeverity.SEV1,
            status="open",
            affected_services=["payment-service"],
            affected_regions=["us-east-1", "us-west-2"],
            customer_impact="Payment failures",
            detected_at=datetime.now(timezone.utc),
            error_rate_peak=0.15,
            latency_p99_peak=5000.0,
            requests_affected=10000,
        )
        assert incident.error_rate_peak == 0.15

    def test_incident_with_root_cause(self):
        """Test incident with root cause."""
        incident = Incident(
            incident_id="inc-rca",
            title="Database Connection Issue",
            description="Connection pool exhausted",
            severity=IncidentSeverity.SEV3,
            status="resolved",
            affected_services=["user-service"],
            affected_regions=["us-east-1"],
            customer_impact="Slow user lookups",
            detected_at=datetime.now(timezone.utc) - timedelta(hours=2),
            resolved_at=datetime.now(timezone.utc),
            root_cause="Insufficient connection pool size",
            root_cause_category="configuration",
        )
        assert incident.root_cause_category == "configuration"


class TestDeploymentCorrelation:
    """Tests for DeploymentCorrelation dataclass."""

    def test_correlation_creation(self):
        """Test correlation creation."""
        correlation = DeploymentCorrelation(
            correlation_id="corr-123",
            deployment_id="dep-456",
            incident_id="inc-789",
            confidence=CorrelationConfidence.HIGH,
            confidence_score=0.92,
            correlation_factors=["Time proximity", "Same service"],
            timeline_analysis="Incident started 5 minutes after deployment",
            change_analysis="Deployment included database changes",
            estimated_impact="50% of users affected",
            blast_radius=["api-gateway", "payment-service"],
            recommended_action="Rollback recommended",
            rollback_recommended=True,
        )
        assert correlation.confidence_score == 0.92
        assert correlation.rollback_recommended is True


class TestBlastRadiusAnalysis:
    """Tests for BlastRadiusAnalysis dataclass."""

    def test_blast_radius_creation(self):
        """Test blast radius analysis creation."""
        analysis = BlastRadiusAnalysis(
            deployment_id="dep-blast",
            directly_affected_services=["api-gateway", "user-service"],
            directly_affected_regions=["us-east-1"],
            downstream_services=["notification-service"],
            upstream_services=["auth-service"],
            affected_data_stores=["user-db"],
            affected_queues=["event-queue"],
            estimated_users_affected=10000,
            estimated_requests_per_minute=5000,
            total_blast_radius_score=0.75,
            risk_factors=["Production environment", "Peak hours"],
        )
        assert analysis.total_blast_radius_score == 0.75
        assert analysis.estimated_users_affected == 10000


class TestRollbackRecommendation:
    """Tests for RollbackRecommendation dataclass."""

    def test_rollback_recommendation(self):
        """Test rollback recommendation creation."""
        recommendation = RollbackRecommendation(
            recommendation_id="rec-123",
            deployment_id="dep-456",
            should_rollback=True,
            confidence=0.85,
            reasons=["Error rate increased 300%", "Customer complaints"],
            evidence=["CloudWatch metrics", "PagerDuty alerts"],
            rollback_steps=["Stop canary", "Revert to v1.0.0", "Verify health"],
            estimated_rollback_time="5 minutes",
            rollback_risks=["Data consistency during rollback"],
            alternative_actions=["Apply hotfix", "Scale up"],
        )
        assert recommendation.should_rollback is True
        assert len(recommendation.rollback_steps) == 3

    def test_no_rollback_recommendation(self):
        """Test recommendation against rollback."""
        recommendation = RollbackRecommendation(
            recommendation_id="rec-no-rollback",
            deployment_id="dep-ok",
            should_rollback=False,
            confidence=0.90,
            reasons=["Metrics within normal range"],
            evidence=["All health checks passing"],
            rollback_steps=[],
            estimated_rollback_time="N/A",
            rollback_risks=[],
            alternative_actions=["Continue monitoring"],
        )
        assert recommendation.should_rollback is False


class TestDeploymentHealthReport:
    """Tests for DeploymentHealthReport dataclass."""

    def test_health_report_creation(self):
        """Test health report creation."""
        report = DeploymentHealthReport(
            report_id="report-123",
            time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
            time_range_end=datetime.now(timezone.utc),
            total_deployments=50,
            successful_deployments=45,
            failed_deployments=3,
            rolled_back_deployments=2,
            success_rate=0.90,
            mean_time_to_deploy=300.0,
            mean_time_to_rollback=120.0,
            deployments_causing_incidents=2,
            incident_correlation_rate=0.04,
            deployments_by_environment={"prod": 20, "staging": 30},
            success_rate_by_environment={"prod": 0.95, "staging": 0.87},
            deployment_frequency_trend="increasing",
            quality_trend="stable",
            top_failure_reasons=[{"reason": "Test failures", "count": 2}],
            high_risk_services=["legacy-api"],
        )
        assert report.success_rate == 0.90
        assert report.total_deployments == 50


class TestChangeWindow:
    """Tests for ChangeWindow dataclass."""

    def test_change_window_creation(self):
        """Test change window creation."""
        window = ChangeWindow(
            window_id="window-123",
            name="Weekly Change Window",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=4),
            environment="production",
        )
        assert window.window_id == "window-123"
        assert window.is_frozen is False

    def test_frozen_window(self):
        """Test frozen change window."""
        window = ChangeWindow(
            window_id="window-frozen",
            name="Black Friday Freeze",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(days=5),
            environment="production",
            is_frozen=True,
            restrictions=["No code deployments", "No database changes"],
        )
        assert window.is_frozen is True
        assert len(window.restrictions) == 2


class TestDeploymentHistoryCorrelator:
    """Tests for DeploymentHistoryCorrelator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_opensearch = MagicMock()
        self.mock_cloudwatch = MagicMock()
        self.mock_llm = MagicMock()

        self.correlator = DeploymentHistoryCorrelator(
            neptune_client=self.mock_neptune,
            opensearch_client=self.mock_opensearch,
            cloudwatch_client=self.mock_cloudwatch,
            llm_client=self.mock_llm,
        )

    def test_init_clients(self):
        """Test initialization with clients."""
        assert self.correlator._neptune is not None
        assert self.correlator._opensearch is not None
        assert self.correlator._cloudwatch is not None
        assert self.correlator._llm is not None

    def test_init_empty_storage(self):
        """Test initialization with empty storage."""
        assert self.correlator._deployments == {}
        assert self.correlator._incidents == {}
        assert self.correlator._correlations == {}
        assert self.correlator._change_windows == {}

    def test_init_without_clients(self):
        """Test initialization without clients."""
        correlator = DeploymentHistoryCorrelator()
        assert correlator._neptune is None
        assert correlator._opensearch is None

    def test_correlation_weights(self):
        """Test correlation weights sum to 1."""
        weights = self.correlator._correlation_weights
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001


class TestDeploymentHistoryCorrelatorStorage:
    """Tests for in-memory storage operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.correlator = DeploymentHistoryCorrelator()

    def test_add_deployment(self):
        """Test adding deployment to storage."""
        deployment = Deployment(
            deployment_id="dep-test",
            name="Test Deployment",
            description="Test",
            deployment_type=DeploymentType.ROLLING,
            status=DeploymentStatus.SUCCEEDED,
            changes=[],
            artifacts=[],
            targets=[],
            environment="staging",
            initiated_by="test",
        )
        self.correlator._deployments[deployment.deployment_id] = deployment
        assert "dep-test" in self.correlator._deployments

    def test_add_incident(self):
        """Test adding incident to storage."""
        incident = Incident(
            incident_id="inc-test",
            title="Test Incident",
            description="Test",
            severity=IncidentSeverity.SEV3,
            status="open",
            affected_services=["test-service"],
            affected_regions=["us-east-1"],
            customer_impact="Minimal",
            detected_at=datetime.now(timezone.utc),
        )
        self.correlator._incidents[incident.incident_id] = incident
        assert "inc-test" in self.correlator._incidents

    def test_add_correlation(self):
        """Test adding correlation to storage."""
        correlation = DeploymentCorrelation(
            correlation_id="corr-test",
            deployment_id="dep-1",
            incident_id="inc-1",
            confidence=CorrelationConfidence.MEDIUM,
            confidence_score=0.65,
            correlation_factors=["Time proximity"],
            timeline_analysis="Incident after deployment",
            change_analysis="Related changes",
            estimated_impact="Minor",
            blast_radius=["service-a"],
            recommended_action="Monitor",
        )
        self.correlator._correlations[correlation.correlation_id] = correlation
        assert "corr-test" in self.correlator._correlations

    def test_add_change_window(self):
        """Test adding change window to storage."""
        window = ChangeWindow(
            window_id="win-test",
            name="Test Window",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc) + timedelta(hours=2),
            environment="staging",
        )
        self.correlator._change_windows[window.window_id] = window
        assert "win-test" in self.correlator._change_windows


class TestDeploymentTypeCompleteness:
    """Tests for deployment type completeness."""

    def test_all_deployment_strategies(self):
        """Test all common deployment strategies exist."""
        assert DeploymentType.ROLLING
        assert DeploymentType.BLUE_GREEN
        assert DeploymentType.CANARY
        assert DeploymentType.RECREATE

    def test_all_change_types(self):
        """Test all common change types exist."""
        assert DeploymentType.FEATURE_FLAG
        assert DeploymentType.DATABASE_MIGRATION
        assert DeploymentType.INFRASTRUCTURE
        assert DeploymentType.CONFIGURATION


class TestChangeCategoryCompleteness:
    """Tests for change category completeness."""

    def test_common_categories_exist(self):
        """Test common change categories exist."""
        categories = list(ChangeCategory)
        assert len(categories) == 7

    def test_category_string_values(self):
        """Test all categories are string enums."""
        for category in ChangeCategory:
            assert isinstance(category.value, str)
