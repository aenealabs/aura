"""
Tests for DevOps Agent Orchestrator.

Tests cover:
- Alert triage logic
- Auto-remediation workflows
- Operational reporting
- Integration with component services
"""

import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.devops.deployment_history_correlator import (
    Deployment,
    DeploymentHealthReport,
    DeploymentStatus,
    RollbackRecommendation,
)
from src.services.devops.devops_agent_orchestrator import (
    Alert,
    AlertType,
    DevOpsAgentOrchestrator,
    DevOpsInsight,
    OperationalReport,
    RemediationAction,
    RemediationStatus,
    RemediationWorkflow,
    TriageAction,
    TriageResult,
)
from src.services.devops.incident_pattern_analyzer import (
    Incident,
    IncidentCategory,
    IncidentMetrics,
    IncidentPattern,
    IncidentSeverity,
    IncidentStatus,
)
from src.services.devops.resource_topology_mapper import TopologySnapshot

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_neptune_client():
    """Mock Neptune client."""
    return MagicMock()


@pytest.fixture
def mock_opensearch_client():
    """Mock OpenSearch client."""
    return MagicMock()


@pytest.fixture
def mock_cloudwatch_client():
    """Mock CloudWatch client."""
    return MagicMock()


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    client = MagicMock()
    client.generate = AsyncMock(return_value="mock response")
    return client


@pytest.fixture
def mock_notification_service():
    """Mock notification service."""
    service = MagicMock()
    service.send = AsyncMock()
    return service


@pytest.fixture
def orchestrator(
    mock_neptune_client,
    mock_opensearch_client,
    mock_cloudwatch_client,
    mock_llm_client,
    mock_notification_service,
):
    """Create orchestrator with mocked dependencies."""
    return DevOpsAgentOrchestrator(
        neptune_client=mock_neptune_client,
        opensearch_client=mock_opensearch_client,
        cloudwatch_client=mock_cloudwatch_client,
        llm_client=mock_llm_client,
        notification_service=mock_notification_service,
    )


@pytest.fixture
def sample_alert():
    """Create sample alert."""
    return Alert(
        alert_id="alert-001",
        alert_type=AlertType.THRESHOLD,
        severity="high",
        title="High CPU Usage",
        description="CPU usage exceeded 90%",
        source="CloudWatch",
        service="api-gateway",
        metric_name="CPUUtilization",
        metric_value=95.0,
        threshold=90.0,
    )


@pytest.fixture
def critical_alert():
    """Create critical alert."""
    return Alert(
        alert_id="alert-critical",
        alert_type=AlertType.THRESHOLD,
        severity="critical",
        title="Service Unavailable",
        description="API endpoint returning 503",
        source="CloudWatch",
        service="payment-service",
        metric_name="5xxErrorRate",
        metric_value=50.0,
        threshold=5.0,
    )


@pytest.fixture
def sample_deployment():
    """Create sample deployment."""
    from src.services.devops.deployment_history_correlator import (
        ChangeCategory,
        DeploymentArtifact,
        DeploymentChange,
        DeploymentTarget,
        DeploymentType,
    )

    return Deployment(
        deployment_id="deploy-001",
        name="api-gateway-v1.2.3",
        description="Bug fixes and improvements",
        deployment_type=DeploymentType.ROLLING,
        status=DeploymentStatus.SUCCEEDED,
        changes=[
            DeploymentChange(
                change_id="change-001",
                category=ChangeCategory.CODE,
                description="Fix API bug",
            )
        ],
        artifacts=[
            DeploymentArtifact(
                artifact_id="artifact-001",
                name="api-gateway",
                version="1.2.3",
                artifact_type="container",
            )
        ],
        targets=[
            DeploymentTarget(
                target_id="target-001",
                name="api-gateway-prod",
                environment="production",
                region="us-east-1",
                resource_type="eks",
            )
        ],
        environment="production",
        initiated_by="ci-pipeline",
        started_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        completed_at=datetime.now(timezone.utc) - timedelta(minutes=25),
    )


@pytest.fixture
def sample_incident():
    """Create sample incident."""
    return Incident(
        incident_id="incident-001",
        title="API Latency Spike",
        description="Latency increased above threshold",
        severity=IncidentSeverity.SEV2,
        status=IncidentStatus.RESOLVED,
        category=IncidentCategory.LATENCY,
        affected_services=["api-gateway"],
        affected_regions=["us-east-1"],
        customer_impact="Slow response times",
        detected_at=datetime.now(timezone.utc) - timedelta(hours=1),
        resolved_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        metrics=IncidentMetrics(
            time_to_detect_seconds=60,
            time_to_acknowledge_seconds=120,
            time_to_mitigate_seconds=600,
            time_to_resolve_seconds=1800,
            mttr_seconds=600,
            mttd_seconds=60,
        ),
    )


# =============================================================================
# Test Data Models
# =============================================================================


class TestAlertDataclass:
    """Test Alert dataclass."""

    def test_alert_creation(self):
        """Test basic alert creation."""
        alert = Alert(
            alert_id="test-001",
            alert_type=AlertType.ANOMALY,
            severity="warning",
            title="Test Alert",
            description="Test description",
            source="TestSource",
            service="test-service",
            metric_name="test_metric",
            metric_value=100.0,
        )
        assert alert.alert_id == "test-001"
        assert alert.alert_type == AlertType.ANOMALY
        assert alert.threshold is None
        assert alert.labels == {}

    def test_alert_with_optional_fields(self):
        """Test alert with all optional fields."""
        alert = Alert(
            alert_id="test-002",
            alert_type=AlertType.PREDICTIVE,
            severity="high",
            title="Predictive Alert",
            description="Predicted failure",
            source="ML",
            service="ml-service",
            metric_name="predicted_error_rate",
            metric_value=0.15,
            threshold=0.1,
            labels={"env": "prod", "team": "platform"},
            annotations={"runbook": "https://runbook.example.com"},
        )
        assert alert.threshold == 0.1
        assert alert.labels["env"] == "prod"
        assert "runbook" in alert.annotations


class TestTriageResult:
    """Test TriageResult dataclass."""

    def test_triage_result_creation(self, sample_alert):
        """Test triage result creation."""
        result = TriageResult(
            triage_id="triage-001",
            alert=sample_alert,
            action=TriageAction.MONITOR,
            confidence=0.8,
            reasoning=["No recent deployments", "Low blast radius"],
            recent_deployments=[],
            similar_incidents=[],
            affected_services=["api-gateway"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=False,
            remediation_steps=[],
            escalation_target=None,
            estimated_severity=IncidentSeverity.SEV3,
        )
        assert result.triage_id == "triage-001"
        assert result.action == TriageAction.MONITOR
        assert result.confidence == 0.8
        assert len(result.reasoning) == 2


class TestRemediationWorkflow:
    """Test RemediationWorkflow dataclass."""

    def test_workflow_creation(self, sample_alert):
        """Test workflow creation."""
        action = RemediationAction(
            action_id="action-001",
            action_type="restart",
            target="api-gateway",
            parameters={"batch_size": 1},
        )
        workflow = RemediationWorkflow(
            workflow_id="workflow-001",
            trigger_alert=sample_alert,
            incident_id=None,
            actions=[action],
            status=RemediationStatus.PENDING,
            started_at=datetime.now(timezone.utc),
        )
        assert workflow.workflow_id == "workflow-001"
        assert len(workflow.actions) == 1
        assert workflow.status == RemediationStatus.PENDING


# =============================================================================
# Test DevOpsAgentOrchestrator Initialization
# =============================================================================


class TestOrchestratorInit:
    """Test orchestrator initialization."""

    def test_init_with_all_clients(self, orchestrator):
        """Test initialization with all clients."""
        assert orchestrator._neptune is not None
        assert orchestrator._opensearch is not None
        assert orchestrator._cloudwatch is not None
        assert orchestrator._llm is not None
        assert orchestrator._notifications is not None

    def test_init_without_clients(self):
        """Test initialization without clients."""
        orch = DevOpsAgentOrchestrator()
        assert orch._neptune is None
        assert orch._remediation_workflows == {}
        assert orch._triage_results == {}

    def test_component_services_initialized(self, orchestrator):
        """Test component services are initialized."""
        assert orchestrator._deployment_correlator is not None
        assert orchestrator._topology_mapper is not None
        assert orchestrator._incident_analyzer is not None

    def test_properties_expose_components(self, orchestrator):
        """Test properties expose component services."""
        assert orchestrator.deployment_correlator is orchestrator._deployment_correlator
        assert orchestrator.topology_mapper is orchestrator._topology_mapper
        assert orchestrator.incident_analyzer is orchestrator._incident_analyzer


# =============================================================================
# Test Alert Severity Mapping
# =============================================================================


class TestSeverityMapping:
    """Test alert severity mapping."""

    def test_map_critical_severity(self, orchestrator):
        """Test mapping critical severity."""
        result = orchestrator._map_alert_severity("critical")
        assert result == IncidentSeverity.SEV1

    def test_map_high_severity(self, orchestrator):
        """Test mapping high severity."""
        result = orchestrator._map_alert_severity("high")
        assert result == IncidentSeverity.SEV2

    def test_map_warning_severity(self, orchestrator):
        """Test mapping warning severity."""
        result = orchestrator._map_alert_severity("warning")
        assert result == IncidentSeverity.SEV3

    def test_map_medium_severity(self, orchestrator):
        """Test mapping medium severity."""
        result = orchestrator._map_alert_severity("medium")
        assert result == IncidentSeverity.SEV3

    def test_map_low_severity(self, orchestrator):
        """Test mapping low severity."""
        result = orchestrator._map_alert_severity("low")
        assert result == IncidentSeverity.SEV4

    def test_map_info_severity(self, orchestrator):
        """Test mapping info severity."""
        result = orchestrator._map_alert_severity("info")
        assert result == IncidentSeverity.SEV4

    def test_map_unknown_severity(self, orchestrator):
        """Test mapping unknown severity defaults to SEV3."""
        result = orchestrator._map_alert_severity("unknown")
        assert result == IncidentSeverity.SEV3

    def test_map_case_insensitive(self, orchestrator):
        """Test severity mapping is case-insensitive."""
        assert orchestrator._map_alert_severity("CRITICAL") == IncidentSeverity.SEV1
        assert orchestrator._map_alert_severity("High") == IncidentSeverity.SEV2


# =============================================================================
# Test Category Inference
# =============================================================================


class TestCategoryInference:
    """Test incident category inference."""

    def test_infer_error_rate_category(self, orchestrator, sample_alert):
        """Test inferring error rate category."""
        sample_alert.metric_name = "5xxErrorRate"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.ERROR_RATE

    def test_infer_latency_category(self, orchestrator, sample_alert):
        """Test inferring latency category."""
        sample_alert.metric_name = "p99_latency"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.LATENCY

    def test_infer_duration_category(self, orchestrator, sample_alert):
        """Test inferring duration category (maps to latency)."""
        sample_alert.metric_name = "request_duration"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.LATENCY

    def test_infer_availability_category(self, orchestrator, sample_alert):
        """Test inferring availability category."""
        sample_alert.metric_name = "service_availability"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.AVAILABILITY

    def test_infer_health_category(self, orchestrator, sample_alert):
        """Test inferring health category (maps to availability)."""
        sample_alert.metric_name = "health_check_failed"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.AVAILABILITY

    def test_infer_cpu_saturation_category(self, orchestrator, sample_alert):
        """Test inferring CPU saturation category."""
        sample_alert.metric_name = "CPUUtilization"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.SATURATION

    def test_infer_memory_saturation_category(self, orchestrator, sample_alert):
        """Test inferring memory saturation category."""
        sample_alert.metric_name = "MemoryUsage"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.SATURATION

    def test_infer_disk_saturation_category(self, orchestrator, sample_alert):
        """Test inferring disk saturation category."""
        sample_alert.metric_name = "DiskUtilization"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.SATURATION

    def test_infer_unknown_defaults_to_availability(self, orchestrator, sample_alert):
        """Test unknown metric defaults to availability."""
        sample_alert.metric_name = "unknown_metric"
        result = orchestrator._infer_category(sample_alert)
        assert result == IncidentCategory.AVAILABILITY


# =============================================================================
# Test Triage Action Determination
# =============================================================================


class TestTriageActionDetermination:
    """Test triage action determination logic."""

    def test_critical_with_rollback_recommendation(self, orchestrator, critical_alert):
        """Test critical alert with rollback recommendation."""
        rollback = RollbackRecommendation(
            recommendation_id="rec-001",
            deployment_id="deploy-001",
            should_rollback=True,
            confidence=0.9,
            reasons=["Recent deployment correlated with failure"],
            evidence=["Error rate spike after deploy"],
            rollback_steps=["Revert deployment"],
            estimated_rollback_time="5 minutes",
            rollback_risks=["Brief service interruption"],
            alternative_actions=["Scale up", "Restart pods"],
        )
        action, confidence = orchestrator._determine_triage_action(
            critical_alert,
            deployment_correlated=True,
            similar_incidents=[],
            rollback_recommendation=rollback,
            blast_radius=[],
        )
        assert action == TriageAction.ROLLBACK
        assert confidence == 0.85

    def test_critical_without_rollback(self, orchestrator, critical_alert):
        """Test critical alert without rollback goes to page oncall."""
        action, confidence = orchestrator._determine_triage_action(
            critical_alert,
            deployment_correlated=False,
            similar_incidents=[],
            rollback_recommendation=None,
            blast_radius=[],
        )
        assert action == TriageAction.PAGE_ONCALL
        assert confidence == 0.9

    def test_high_severity_large_blast_radius(self, orchestrator, sample_alert):
        """Test high severity with large blast radius escalates."""
        sample_alert.severity = "high"
        action, confidence = orchestrator._determine_triage_action(
            sample_alert,
            deployment_correlated=False,
            similar_incidents=[],
            rollback_recommendation=None,
            blast_radius=["svc1", "svc2", "svc3", "svc4"],
        )
        assert action == TriageAction.ESCALATE
        assert confidence == 0.8

    def test_similar_auto_resolved_incidents(
        self, orchestrator, sample_alert, sample_incident
    ):
        """Test similar auto-resolved incidents trigger auto-remediation."""
        # Make incident look auto-resolved quickly
        sample_incident.metrics = IncidentMetrics(
            time_to_detect_seconds=60,
            time_to_acknowledge_seconds=120,
            time_to_mitigate_seconds=600,
            time_to_resolve_seconds=600,
            mttr_seconds=600,  # Under 900 seconds
            mttd_seconds=60,
        )
        action, confidence = orchestrator._determine_triage_action(
            sample_alert,
            deployment_correlated=False,
            similar_incidents=[sample_incident],
            rollback_recommendation=None,
            blast_radius=[],
        )
        assert action == TriageAction.AUTO_REMEDIATE
        assert confidence == 0.7

    def test_deployment_correlated_with_rollback(self, orchestrator, sample_alert):
        """Test deployment correlation with rollback recommendation."""
        rollback = RollbackRecommendation(
            recommendation_id="rec-002",
            deployment_id="deploy-001",
            should_rollback=True,
            confidence=0.8,
            reasons=["Deployment correlated"],
            evidence=["Error rate increase"],
            rollback_steps=["Rollback"],
            estimated_rollback_time="5 minutes",
            rollback_risks=["Service disruption"],
            alternative_actions=["Scale up"],
        )
        action, confidence = orchestrator._determine_triage_action(
            sample_alert,
            deployment_correlated=True,
            similar_incidents=[],
            rollback_recommendation=rollback,
            blast_radius=[],
        )
        assert action == TriageAction.ROLLBACK
        assert confidence == 0.75

    def test_deployment_correlated_without_rollback(self, orchestrator, sample_alert):
        """Test deployment correlation without rollback creates incident."""
        action, confidence = orchestrator._determine_triage_action(
            sample_alert,
            deployment_correlated=True,
            similar_incidents=[],
            rollback_recommendation=None,
            blast_radius=[],
        )
        assert action == TriageAction.CREATE_INCIDENT
        assert confidence == 0.7

    def test_warning_severity_monitors(self, orchestrator, sample_alert):
        """Test warning severity results in monitoring."""
        sample_alert.severity = "warning"
        action, confidence = orchestrator._determine_triage_action(
            sample_alert,
            deployment_correlated=False,
            similar_incidents=[],
            rollback_recommendation=None,
            blast_radius=[],
        )
        assert action == TriageAction.MONITOR
        assert confidence == 0.6

    def test_low_severity_monitors(self, orchestrator, sample_alert):
        """Test low severity results in monitoring."""
        sample_alert.severity = "low"
        action, confidence = orchestrator._determine_triage_action(
            sample_alert,
            deployment_correlated=False,
            similar_incidents=[],
            rollback_recommendation=None,
            blast_radius=[],
        )
        assert action == TriageAction.MONITOR
        assert confidence == 0.5


# =============================================================================
# Test Auto-Remediation Check
# =============================================================================


class TestAutoRemediationCheck:
    """Test auto-remediation availability check."""

    def test_check_auto_remediation_rollback(self, orchestrator, sample_alert):
        """Test rollback action has remediation steps."""
        available, steps = orchestrator._check_auto_remediation(
            sample_alert, TriageAction.ROLLBACK
        )
        assert available is True
        assert "Identify deployment to rollback" in steps
        assert "Execute rollback procedure" in steps

    def test_check_auto_remediation_scale(self, orchestrator, sample_alert):
        """Test scale action has remediation steps."""
        available, steps = orchestrator._check_auto_remediation(
            sample_alert, TriageAction.SCALE
        )
        assert available is True
        assert "Calculate required capacity" in steps
        assert "Scale service horizontally" in steps

    def test_check_auto_remediation_restart(self, orchestrator, sample_alert):
        """Test restart action has remediation steps."""
        available, steps = orchestrator._check_auto_remediation(
            sample_alert, TriageAction.RESTART
        )
        assert available is True
        assert "Identify unhealthy instances" in steps
        assert "Restart instances" in steps

    def test_check_auto_remediation_not_available(self, orchestrator, sample_alert):
        """Test non-remediation actions return unavailable."""
        available, steps = orchestrator._check_auto_remediation(
            sample_alert, TriageAction.MONITOR
        )
        assert available is False
        assert steps == []

    def test_check_auto_remediation_with_rule(self, orchestrator, sample_alert):
        """Test custom rule provides remediation steps."""
        orchestrator.register_auto_remediation_rule(
            service="api-gateway",
            metric="CPUUtilization",
            severity="high",
            steps=["Scale pod replicas", "Check for memory leaks"],
        )
        available, steps = orchestrator._check_auto_remediation(
            sample_alert, TriageAction.AUTO_REMEDIATE
        )
        assert available is True
        assert "Scale pod replicas" in steps


# =============================================================================
# Test Rule Matching
# =============================================================================


class TestRuleMatching:
    """Test remediation rule matching."""

    def test_rule_matches_all_fields(self, orchestrator, sample_alert):
        """Test rule matches when all fields match."""
        rule = {
            "service": "api-gateway",
            "metric": "CPUUtilization",
            "severity": "high",
        }
        assert orchestrator._rule_matches_alert(rule, sample_alert) is True

    def test_rule_service_mismatch(self, orchestrator, sample_alert):
        """Test rule doesn't match with wrong service."""
        rule = {"service": "other-service"}
        assert orchestrator._rule_matches_alert(rule, sample_alert) is False

    def test_rule_metric_mismatch(self, orchestrator, sample_alert):
        """Test rule doesn't match with wrong metric."""
        rule = {"metric": "MemoryUtilization"}
        assert orchestrator._rule_matches_alert(rule, sample_alert) is False

    def test_rule_severity_mismatch(self, orchestrator, sample_alert):
        """Test rule doesn't match with wrong severity."""
        rule = {"severity": "critical"}
        assert orchestrator._rule_matches_alert(rule, sample_alert) is False

    def test_rule_empty_matches_all(self, orchestrator, sample_alert):
        """Test empty rule matches all alerts."""
        rule = {}
        assert orchestrator._rule_matches_alert(rule, sample_alert) is True


# =============================================================================
# Test Escalation Target
# =============================================================================


class TestEscalationTarget:
    """Test escalation target determination."""

    def test_get_escalation_target(self, orchestrator):
        """Test getting escalation target."""
        target = orchestrator._get_escalation_target("api-gateway")
        assert target == "api-gateway-oncall"


# =============================================================================
# Test Severity Estimation
# =============================================================================


class TestSeverityEstimation:
    """Test incident severity estimation."""

    def test_estimate_severity_base(self, orchestrator, sample_alert):
        """Test base severity estimation."""
        severity = orchestrator._estimate_incident_severity(
            sample_alert, blast_radius=[], similar_incidents=[]
        )
        assert severity == IncidentSeverity.SEV2  # high -> SEV2

    def test_estimate_severity_large_blast_radius(self, orchestrator, sample_alert):
        """Test severity upgrade with large blast radius."""
        sample_alert.severity = "medium"
        severity = orchestrator._estimate_incident_severity(
            sample_alert,
            blast_radius=["svc1", "svc2", "svc3", "svc4", "svc5", "svc6"],
            similar_incidents=[],
        )
        assert severity == IncidentSeverity.SEV2  # upgraded from SEV3

    def test_estimate_severity_critical_no_upgrade(self, orchestrator, critical_alert):
        """Test critical severity not upgraded further."""
        severity = orchestrator._estimate_incident_severity(
            critical_alert,
            blast_radius=["svc1", "svc2", "svc3", "svc4", "svc5", "svc6"],
            similar_incidents=[],
        )
        assert severity == IncidentSeverity.SEV1

    def test_estimate_severity_similar_incidents(self, orchestrator, sample_alert):
        """Test severity influenced by similar incidents."""
        sample_alert.severity = "medium"
        similar = [
            Incident(
                incident_id="inc-1",
                title="Similar",
                description="",
                severity=IncidentSeverity.SEV1,
                status=IncidentStatus.RESOLVED,
                category=IncidentCategory.LATENCY,
                affected_services=["api-gateway"],
                affected_regions=[],
                customer_impact="",
                detected_at=datetime.now(timezone.utc),
            ),
            Incident(
                incident_id="inc-2",
                title="Similar 2",
                description="",
                severity=IncidentSeverity.SEV2,
                status=IncidentStatus.RESOLVED,
                category=IncidentCategory.LATENCY,
                affected_services=["api-gateway"],
                affected_regions=[],
                customer_impact="",
                detected_at=datetime.now(timezone.utc),
            ),
        ]
        severity = orchestrator._estimate_incident_severity(
            sample_alert, blast_radius=[], similar_incidents=similar
        )
        assert severity == IncidentSeverity.SEV2  # avg severity is high


# =============================================================================
# Test Alert Triage
# =============================================================================


class TestAlertTriage:
    """Test alert triage flow."""

    @pytest.mark.asyncio
    async def test_triage_alert_basic(self, orchestrator, sample_alert):
        """Test basic alert triage."""
        # Mock component responses
        orchestrator._deployment_correlator.get_deployments_for_service = AsyncMock(
            return_value=[]
        )
        orchestrator._incident_analyzer.recommend_runbooks = AsyncMock(return_value=[])

        result = await orchestrator.triage_alert(sample_alert)

        assert result.triage_id is not None
        assert result.alert == sample_alert
        assert result.action in TriageAction
        assert 0 <= result.confidence <= 1
        assert result.triage_id in orchestrator._triage_results

    @pytest.mark.asyncio
    async def test_triage_alert_with_recent_deployment(
        self, orchestrator, sample_alert, sample_deployment
    ):
        """Test triage with recent deployment correlation."""
        orchestrator._deployment_correlator.get_deployments_for_service = AsyncMock(
            return_value=[sample_deployment]
        )
        orchestrator._deployment_correlator.recommend_rollback = AsyncMock(
            return_value=RollbackRecommendation(
                recommendation_id="rec-003",
                deployment_id=sample_deployment.deployment_id,
                should_rollback=True,
                confidence=0.85,
                reasons=["Recent deployment"],
                evidence=["Metric correlation"],
                rollback_steps=[],
                estimated_rollback_time="5 minutes",
                rollback_risks=[],
                alternative_actions=[],
            )
        )
        orchestrator._incident_analyzer.recommend_runbooks = AsyncMock(return_value=[])

        result = await orchestrator.triage_alert(sample_alert)

        assert len(result.recent_deployments) == 1
        assert result.rollback_recommendation is not None
        assert "Recent deployment" in result.reasoning[0]

    @pytest.mark.asyncio
    async def test_triage_critical_alert_pages_oncall(
        self, orchestrator, critical_alert
    ):
        """Test critical alert pages oncall."""
        orchestrator._deployment_correlator.get_deployments_for_service = AsyncMock(
            return_value=[]
        )
        orchestrator._incident_analyzer.recommend_runbooks = AsyncMock(return_value=[])

        result = await orchestrator.triage_alert(critical_alert)

        assert result.action == TriageAction.PAGE_ONCALL
        assert result.escalation_target == "payment-service-oncall"


# =============================================================================
# Test Remediation Workflow
# =============================================================================


class TestRemediationWorkflowExtended:
    """Extended tests for remediation workflow execution."""

    @pytest.mark.asyncio
    async def test_execute_rollback_remediation(
        self, orchestrator, sample_alert, sample_deployment
    ):
        """Test rollback remediation execution."""
        triage_result = TriageResult(
            triage_id="triage-001",
            alert=sample_alert,
            action=TriageAction.ROLLBACK,
            confidence=0.85,
            reasoning=[],
            recent_deployments=[sample_deployment],
            similar_incidents=[],
            affected_services=["api-gateway"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=True,
            remediation_steps=["Rollback deployment"],
            escalation_target=None,
            estimated_severity=IncidentSeverity.SEV2,
        )

        workflow = await orchestrator.execute_remediation(triage_result)

        assert workflow.workflow_id is not None
        assert workflow.status == RemediationStatus.SUCCEEDED
        assert len(workflow.actions) == 2  # rollback + verify_health
        assert workflow.actions[0].action_type == "rollback"
        assert workflow.workflow_id in orchestrator._remediation_workflows

    @pytest.mark.asyncio
    async def test_execute_scale_remediation(self, orchestrator, sample_alert):
        """Test scale remediation execution."""
        triage_result = TriageResult(
            triage_id="triage-002",
            alert=sample_alert,
            action=TriageAction.SCALE,
            confidence=0.8,
            reasoning=[],
            recent_deployments=[],
            similar_incidents=[],
            affected_services=["api-gateway"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=True,
            remediation_steps=[],
            escalation_target=None,
            estimated_severity=IncidentSeverity.SEV3,
        )

        workflow = await orchestrator.execute_remediation(triage_result)

        assert workflow.status == RemediationStatus.SUCCEEDED
        assert len(workflow.actions) == 2
        assert workflow.actions[0].action_type == "scale_out"

    @pytest.mark.asyncio
    async def test_execute_restart_remediation(self, orchestrator, sample_alert):
        """Test restart remediation execution."""
        triage_result = TriageResult(
            triage_id="triage-003",
            alert=sample_alert,
            action=TriageAction.RESTART,
            confidence=0.75,
            reasoning=[],
            recent_deployments=[],
            similar_incidents=[],
            affected_services=["api-gateway"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=True,
            remediation_steps=[],
            escalation_target=None,
            estimated_severity=IncidentSeverity.SEV3,
        )

        workflow = await orchestrator.execute_remediation(triage_result)

        assert workflow.status == RemediationStatus.SUCCEEDED
        assert workflow.actions[0].action_type == "rolling_restart"

    @pytest.mark.asyncio
    async def test_execute_generic_remediation(self, orchestrator, sample_alert):
        """Test generic auto-remediation."""
        triage_result = TriageResult(
            triage_id="triage-004",
            alert=sample_alert,
            action=TriageAction.AUTO_REMEDIATE,
            confidence=0.7,
            reasoning=[],
            recent_deployments=[],
            similar_incidents=[],
            affected_services=["api-gateway"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=True,
            remediation_steps=["Step 1", "Step 2", "Step 3"],
            escalation_target=None,
            estimated_severity=IncidentSeverity.SEV3,
        )

        workflow = await orchestrator.execute_remediation(triage_result)

        assert workflow.status == RemediationStatus.SUCCEEDED
        assert len(workflow.actions) == 3
        assert workflow.actions[0].action_type == "runbook_step"

    @pytest.mark.asyncio
    async def test_remediation_action_failure(
        self, orchestrator, sample_alert, sample_deployment
    ):
        """Test remediation workflow handles action failure."""
        triage_result = TriageResult(
            triage_id="triage-005",
            alert=sample_alert,
            action=TriageAction.ROLLBACK,
            confidence=0.85,
            reasoning=[],
            recent_deployments=[sample_deployment],
            similar_incidents=[],
            affected_services=["api-gateway"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=True,
            remediation_steps=[],
            escalation_target=None,
            estimated_severity=IncidentSeverity.SEV2,
        )

        # Make action execution fail
        orchestrator._execute_action = AsyncMock(side_effect=Exception("Action failed"))

        workflow = await orchestrator.execute_remediation(triage_result)

        assert workflow.status == RemediationStatus.FAILED
        assert workflow.actions[0].status == RemediationStatus.FAILED
        assert "Action failed" in workflow.actions[0].error


# =============================================================================
# Test Auto-Remediation Rule Registration
# =============================================================================


class TestAutoRemediationRuleRegistration:
    """Test auto-remediation rule registration."""

    def test_register_rule(self, orchestrator):
        """Test registering a remediation rule."""
        orchestrator.register_auto_remediation_rule(
            service="api-gateway",
            metric="CPUUtilization",
            severity="high",
            action=TriageAction.SCALE,
            steps=["Scale out", "Verify"],
        )

        assert len(orchestrator._auto_remediation_rules) == 1
        rule = orchestrator._auto_remediation_rules[0]
        assert rule["service"] == "api-gateway"
        assert rule["action"] == TriageAction.SCALE

    def test_register_multiple_rules(self, orchestrator):
        """Test registering multiple rules."""
        orchestrator.register_auto_remediation_rule(service="svc1")
        orchestrator.register_auto_remediation_rule(service="svc2")

        assert len(orchestrator._auto_remediation_rules) == 2


# =============================================================================
# Test Operational Report Generation
# =============================================================================


class TestOperationalReportGeneration:
    """Test operational report generation."""

    @pytest.mark.asyncio
    async def test_generate_operational_report(self, orchestrator):
        """Test generating operational report."""
        # Mock component responses
        orchestrator._deployment_correlator.generate_health_report = AsyncMock(
            return_value=DeploymentHealthReport(
                report_id="report-001",
                time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
                time_range_end=datetime.now(timezone.utc),
                total_deployments=50,
                successful_deployments=47,
                failed_deployments=3,
                rolled_back_deployments=2,
                success_rate=0.94,
                mean_time_to_deploy=300,
                mean_time_to_rollback=60,
                deployments_causing_incidents=5,
                incident_correlation_rate=0.1,
                deployments_by_environment={"production": 50},
                success_rate_by_environment={"production": 0.94},
                deployment_frequency_trend="stable",
                quality_trend="improving",
                top_failure_reasons=[],
                high_risk_services=["api-gateway"],
            )
        )
        orchestrator._topology_mapper.take_snapshot = AsyncMock(
            return_value=TopologySnapshot(
                snapshot_id="snap-001",
                taken_at=datetime.now(timezone.utc),
                total_resources=100,
                total_relationships=50,
                total_services=10,
                resources_by_type={"ec2": 50, "rds": 10},
                resources_by_region={"us-east-1": 100},
                resources_by_environment={"production": 100},
                total_monthly_cost=5000.0,
            )
        )
        orchestrator._incident_analyzer.generate_predictive_alerts = AsyncMock(
            return_value=[]
        )

        report = await orchestrator.generate_operational_report(days=7)

        assert report.report_id is not None
        assert report.total_deployments == 50
        assert report.deployment_success_rate == 0.94
        assert report.total_resources == 100

    @pytest.mark.asyncio
    async def test_operational_report_with_incidents(
        self, orchestrator, sample_incident
    ):
        """Test report includes incident metrics."""
        # Add incident to analyzer
        orchestrator._incident_analyzer._incidents["inc-001"] = sample_incident

        orchestrator._deployment_correlator.generate_health_report = AsyncMock(
            return_value=DeploymentHealthReport(
                report_id="report-002",
                time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
                time_range_end=datetime.now(timezone.utc),
                total_deployments=10,
                successful_deployments=10,
                failed_deployments=0,
                rolled_back_deployments=0,
                success_rate=1.0,
                mean_time_to_deploy=300,
                mean_time_to_rollback=0,
                deployments_causing_incidents=0,
                incident_correlation_rate=0.0,
                deployments_by_environment={"production": 10},
                success_rate_by_environment={"production": 1.0},
                deployment_frequency_trend="stable",
                quality_trend="stable",
                top_failure_reasons=[],
                high_risk_services=[],
            )
        )
        orchestrator._topology_mapper.take_snapshot = AsyncMock(
            return_value=TopologySnapshot(
                snapshot_id="snap-002",
                taken_at=datetime.now(timezone.utc),
                total_resources=50,
                total_relationships=25,
                total_services=5,
                resources_by_type={"ec2": 25, "rds": 5},
                resources_by_region={"us-east-1": 50},
                resources_by_environment={"production": 50},
                total_monthly_cost=2500.0,
            )
        )
        orchestrator._incident_analyzer.generate_predictive_alerts = AsyncMock(
            return_value=[]
        )

        report = await orchestrator.generate_operational_report(days=7)

        assert report.total_incidents >= 0


# =============================================================================
# Test Insight Generation
# =============================================================================


class TestInsightGeneration:
    """Test operational insight generation."""

    @pytest.mark.asyncio
    async def test_generate_deployment_quality_insight(self, orchestrator):
        """Test generating deployment quality insight."""
        deployment_health = DeploymentHealthReport(
            report_id="report-001",
            time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
            time_range_end=datetime.now(timezone.utc),
            total_deployments=50,
            successful_deployments=45,
            failed_deployments=5,
            rolled_back_deployments=3,
            success_rate=0.90,  # Below 95% target
            mean_time_to_deploy=300,
            mean_time_to_rollback=60,
            deployments_causing_incidents=0,
            incident_correlation_rate=0.0,
            deployments_by_environment={"production": 50},
            success_rate_by_environment={"production": 0.90},
            deployment_frequency_trend="stable",
            quality_trend="declining",
            top_failure_reasons=[],
            high_risk_services=["api-gateway"],
        )

        insights = await orchestrator._generate_insights(deployment_health, [], [])

        assert len(insights) >= 1
        deployment_insight = next(
            (i for i in insights if i.category == "deployments"), None
        )
        assert deployment_insight is not None
        assert "Below Target" in deployment_insight.title

    @pytest.mark.asyncio
    async def test_generate_incident_correlation_insight(self, orchestrator):
        """Test generating incident correlation insight."""
        deployment_health = DeploymentHealthReport(
            report_id="report-002",
            time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
            time_range_end=datetime.now(timezone.utc),
            total_deployments=50,
            successful_deployments=50,
            failed_deployments=0,
            rolled_back_deployments=0,
            success_rate=1.0,
            mean_time_to_deploy=300,
            mean_time_to_rollback=0,
            deployments_causing_incidents=10,
            incident_correlation_rate=0.2,  # Above 10%
            deployments_by_environment={"production": 50},
            success_rate_by_environment={"production": 1.0},
            deployment_frequency_trend="stable",
            quality_trend="stable",
            top_failure_reasons=[],
            high_risk_services=[],
        )

        insights = await orchestrator._generate_insights(deployment_health, [], [])

        incident_insight = next(
            (i for i in insights if i.category == "incidents"), None
        )
        assert incident_insight is not None
        assert "Correlation" in incident_insight.title

    @pytest.mark.asyncio
    async def test_generate_pattern_insight(self, orchestrator):
        """Test generating pattern-based insight."""
        from src.services.devops.incident_pattern_analyzer import PatternType

        pattern = IncidentPattern(
            pattern_id="pattern-001",
            pattern_type=PatternType.RECURRING,
            name="Memory Leak Pattern",
            description="Recurring memory exhaustion in service",
            matching_incidents=["inc-1", "inc-2", "inc-3", "inc-4", "inc-5"],
            occurrence_count=5,
            first_occurrence=datetime.now(timezone.utc) - timedelta(days=30),
            last_occurrence=datetime.now(timezone.utc),
            common_services=["api-gateway"],
            common_root_causes=["Memory leak"],
            common_time_windows=["business hours"],
            average_severity=2.0,
            average_mttr_seconds=600,
            confidence_score=0.85,
            recommended_actions=["Implement memory limits"],
            prevention_suggestions=["Set resource limits", "Add memory alerts"],
        )

        deployment_health = DeploymentHealthReport(
            report_id="report-003",
            time_range_start=datetime.now(timezone.utc) - timedelta(days=7),
            time_range_end=datetime.now(timezone.utc),
            total_deployments=50,
            successful_deployments=50,
            failed_deployments=0,
            rolled_back_deployments=0,
            success_rate=1.0,
            mean_time_to_deploy=300,
            mean_time_to_rollback=0,
            deployments_causing_incidents=0,
            incident_correlation_rate=0.0,
            deployments_by_environment={"production": 50},
            success_rate_by_environment={"production": 1.0},
            deployment_frequency_trend="stable",
            quality_trend="stable",
            top_failure_reasons=[],
            high_risk_services=[],
        )

        insights = await orchestrator._generate_insights(
            deployment_health, [], [pattern]
        )

        pattern_insight = next((i for i in insights if i.category == "patterns"), None)
        assert pattern_insight is not None
        assert "Memory Leak Pattern" in pattern_insight.title


# =============================================================================
# Test End-to-End Processing
# =============================================================================


class TestEndToEndProcessing:
    """Test end-to-end alert processing."""

    @pytest.mark.asyncio
    async def test_process_alert_end_to_end_with_remediation(
        self, orchestrator, sample_alert, sample_incident
    ):
        """Test complete alert processing with auto-remediation."""
        # Setup mocks
        orchestrator._deployment_correlator.get_deployments_for_service = AsyncMock(
            return_value=[]
        )
        orchestrator._incident_analyzer.recommend_runbooks = AsyncMock(return_value=[])

        # Add similar incident that was auto-resolved
        sample_incident.metrics = IncidentMetrics(
            time_to_detect_seconds=60,
            time_to_acknowledge_seconds=120,
            time_to_mitigate_seconds=300,
            time_to_resolve_seconds=600,
            mttr_seconds=600,
            mttd_seconds=60,
        )
        orchestrator._incident_analyzer._incidents["inc-001"] = sample_incident

        result = await orchestrator.process_alert_end_to_end(sample_alert)

        assert "triage" in result
        assert "action_taken" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_process_alert_creates_incident(self, orchestrator, critical_alert):
        """Test alert processing creates incident for critical alerts."""
        orchestrator._deployment_correlator.get_deployments_for_service = AsyncMock(
            return_value=[]
        )
        orchestrator._incident_analyzer.recommend_runbooks = AsyncMock(return_value=[])
        orchestrator._incident_analyzer.record_incident = AsyncMock()

        result = await orchestrator.process_alert_end_to_end(critical_alert)

        assert result["incident"] is not None
        assert result["action_taken"] == TriageAction.PAGE_ONCALL.value


# =============================================================================
# Test Enums
# =============================================================================


class TestEnums:
    """Test enum values."""

    def test_triage_action_values(self):
        """Test TriageAction enum values."""
        assert TriageAction.AUTO_REMEDIATE.value == "auto_remediate"
        assert TriageAction.ESCALATE.value == "escalate"
        assert TriageAction.PAGE_ONCALL.value == "page_oncall"
        assert TriageAction.CREATE_INCIDENT.value == "create_incident"
        assert TriageAction.MONITOR.value == "monitor"
        assert TriageAction.ROLLBACK.value == "rollback"
        assert TriageAction.SCALE.value == "scale"
        assert TriageAction.RESTART.value == "restart"

    def test_remediation_status_values(self):
        """Test RemediationStatus enum values."""
        assert RemediationStatus.PENDING.value == "pending"
        assert RemediationStatus.IN_PROGRESS.value == "in_progress"
        assert RemediationStatus.SUCCEEDED.value == "succeeded"
        assert RemediationStatus.FAILED.value == "failed"
        assert RemediationStatus.SKIPPED.value == "skipped"

    def test_alert_type_values(self):
        """Test AlertType enum values."""
        assert AlertType.THRESHOLD.value == "threshold"
        assert AlertType.ANOMALY.value == "anomaly"
        assert AlertType.PREDICTIVE.value == "predictive"
        assert AlertType.PATTERN.value == "pattern"


# =============================================================================
# Test DevOpsInsight Dataclass
# =============================================================================


class TestDevOpsInsight:
    """Test DevOpsInsight dataclass."""

    def test_insight_creation(self):
        """Test insight creation."""
        insight = DevOpsInsight(
            insight_id="insight-001",
            category="deployments",
            title="Test Insight",
            description="Test description",
            severity="high",
            evidence=["Evidence 1"],
            recommendations=["Recommendation 1"],
            affected_services=["service-1"],
        )
        assert insight.insight_id == "insight-001"
        assert insight.category == "deployments"
        assert len(insight.evidence) == 1


# =============================================================================
# Test OperationalReport Dataclass
# =============================================================================


class TestOperationalReportDataclass:
    """Test OperationalReport dataclass."""

    def test_report_creation(self):
        """Test report creation."""
        report = OperationalReport(
            report_id="report-001",
            period_start=datetime.now(timezone.utc) - timedelta(days=7),
            period_end=datetime.now(timezone.utc),
            total_deployments=50,
            successful_deployments=45,
            failed_deployments=5,
            deployment_success_rate=0.9,
            mean_time_to_deploy=300,
            total_incidents=10,
            incidents_by_severity={"sev2": 5, "sev3": 5},
            mttr_seconds=600,
            incidents_per_deployment=0.2,
            slo_statuses=[],
            slos_at_risk=0,
            total_resources=100,
            resources_by_status={"healthy": 95, "degraded": 5},
            estimated_monthly_cost=5000.0,
            active_patterns=[],
            predictive_alerts=[],
            insights=[],
        )
        assert report.report_id == "report-001"
        assert report.deployment_success_rate == 0.9
        assert report.total_incidents == 10
