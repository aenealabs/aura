"""
Tests for DevOps Services - AWS DevOps Agent Parity

Covers:
- DeploymentHistoryCorrelator
- ResourceTopologyMapper
- IncidentPatternAnalyzer
- DevOpsAgentOrchestrator

Reference: ADR-030 Section 5.3 DevOps Agent Components
"""

from datetime import datetime, timedelta, timezone

import pytest

# Import directly from individual modules to avoid __init__.py export issues
from src.services.devops.deployment_history_correlator import (
    ChangeCategory,
    Deployment,
    DeploymentArtifact,
    DeploymentChange,
    DeploymentHistoryCorrelator,
    DeploymentMetrics,
    DeploymentStatus,
    DeploymentTarget,
    DeploymentType,
    Incident,
    IncidentSeverity,
    RiskLevel,
)
from src.services.devops.devops_agent_orchestrator import (
    Alert,
    AlertType,
    DevOpsAgentOrchestrator,
    DevOpsInsight,
    RemediationAction,
    RemediationStatus,
    TriageAction,
    TriageResult,
)
from src.services.devops.incident_pattern_analyzer import (
    Incident as IncidentAnalyzerIncident,
)
from src.services.devops.incident_pattern_analyzer import (
    IncidentCategory,
    IncidentPatternAnalyzer,
)
from src.services.devops.incident_pattern_analyzer import (
    IncidentSeverity as AnalyzerIncidentSeverity,
)
from src.services.devops.incident_pattern_analyzer import (
    IncidentStatus,
    IncidentTimeline,
    PatternType,
    RootCauseCategory,
    RunbookRecommendation,
)
from src.services.devops.resource_topology_mapper import (
    CloudProvider,
    RelationshipType,
    Resource,
    ResourceRelationship,
    ResourceStatus,
    ResourceTag,
    ResourceTopologyMapper,
    ResourceType,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def deployment_correlator():
    """Create a deployment history correlator instance."""
    return DeploymentHistoryCorrelator()


@pytest.fixture
def topology_mapper():
    """Create a resource topology mapper instance."""
    return ResourceTopologyMapper()


@pytest.fixture
def incident_analyzer():
    """Create an incident pattern analyzer instance."""
    return IncidentPatternAnalyzer()


@pytest.fixture
def devops_orchestrator():
    """Create a devops agent orchestrator instance."""
    return DevOpsAgentOrchestrator()


@pytest.fixture
def sample_deployment():
    """Create a sample deployment for testing."""
    return Deployment(
        deployment_id="deploy-001",
        name="api-service-v1.2.0",
        description="Deploy new API version with feature X",
        deployment_type=DeploymentType.ROLLING,
        status=DeploymentStatus.SUCCEEDED,
        changes=[
            DeploymentChange(
                change_id="change-001",
                category=ChangeCategory.CODE,
                description="Add new endpoint for user preferences",
                files_changed=["api/routes.py", "api/handlers.py"],
                commit_sha="abc123",
                author="developer@example.com",
            ),
            DeploymentChange(
                change_id="change-002",
                category=ChangeCategory.CONFIGURATION,
                description="Update timeout settings",
                files_changed=["config/settings.yaml"],
            ),
        ],
        artifacts=[
            DeploymentArtifact(
                artifact_id="artifact-001",
                name="api-service",
                version="1.2.0",
                artifact_type="container",
                registry="ecr.aws",
                sha256="sha256:abc123",
            )
        ],
        targets=[
            DeploymentTarget(
                target_id="target-001",
                name="api-service",
                environment="production",
                region="us-east-1",
                resource_type="eks",
                replica_count=3,
            )
        ],
        environment="production",
        initiated_by="ci-pipeline",
        metrics=DeploymentMetrics(
            duration_seconds=300,
            replicas_updated=3,
            replicas_failed=0,
            error_rate_before=0.01,
            error_rate_after=0.02,
            latency_p50_before=50,
            latency_p50_after=55,
            latency_p99_before=200,
            latency_p99_after=210,
        ),
    )


@pytest.fixture
def sample_incident():
    """Create a sample incident for testing."""
    return Incident(
        incident_id="inc-001",
        title="High Error Rate in API Service",
        description="Error rate spiked to 5% after recent deployment",
        severity=IncidentSeverity.SEV2,
        status="open",
        affected_services=["api-service", "auth-service"],
        affected_regions=["us-east-1"],
        customer_impact="Users experiencing intermittent errors",
        detected_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        error_rate_peak=0.05,
        latency_p99_peak=500,
        requests_affected=10000,
    )


@pytest.fixture
def sample_analyzer_incident():
    """Create a sample incident for the analyzer."""
    return IncidentAnalyzerIncident(
        incident_id="inc-002",
        title="Database Connection Failures",
        description="RDS connections timing out",
        severity=AnalyzerIncidentSeverity.SEV2,
        status=IncidentStatus.INVESTIGATING,
        category=IncidentCategory.AVAILABILITY,
        affected_services=["user-service", "order-service"],
        affected_regions=["us-west-2"],
        customer_impact="Users cannot complete purchases",
        detected_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )


@pytest.fixture
def sample_resource():
    """Create a sample resource for testing."""
    return Resource(
        resource_id="i-12345678",
        arn="arn:aws:ec2:us-east-1:123456789:instance/i-12345678",
        name="aura-api-1",
        resource_type=ResourceType.EC2_INSTANCE,
        provider=CloudProvider.AWS,
        region="us-east-1",
        account_id="123456789",
        status=ResourceStatus.RUNNING,
        tags=[
            ResourceTag(key="Environment", value="production"),
            ResourceTag(key="Team", value="platform"),
        ],
        configuration={"instance_type": "m5.xlarge"},
        environment="production",
        team="platform",
        application="aura",
        monthly_cost=150.0,
    )


@pytest.fixture
def sample_alert():
    """Create a sample alert for testing."""
    return Alert(
        alert_id="alert-001",
        alert_type=AlertType.THRESHOLD,
        severity="high",
        title="High Error Rate Alert",
        description="Error rate exceeded 5%",
        source="CloudWatch",
        service="api-service",
        metric_name="ErrorRate",
        metric_value=0.08,
        threshold=0.05,
        fired_at=datetime.now(timezone.utc),
    )


# =============================================================================
# DeploymentHistoryCorrelator Tests
# =============================================================================


class TestDeploymentHistoryCorrelator:
    """Tests for DeploymentHistoryCorrelator."""

    @pytest.mark.asyncio
    async def test_record_deployment(self, deployment_correlator, sample_deployment):
        """Test recording a deployment."""
        result = await deployment_correlator.record_deployment(sample_deployment)

        assert result.deployment_id == "deploy-001"
        assert result.risk_level is not None
        assert result.health_score <= 100

    @pytest.mark.asyncio
    async def test_record_deployment_calculates_risk(self, deployment_correlator):
        """Test that recording a deployment calculates risk properly."""
        deployment = Deployment(
            deployment_id="deploy-risk",
            name="high-risk-deploy",
            description="Database migration in production",
            deployment_type=DeploymentType.DATABASE_MIGRATION,
            status=DeploymentStatus.IN_PROGRESS,
            changes=[
                DeploymentChange(
                    change_id="db-change",
                    category=ChangeCategory.DATABASE,
                    description="Alter user table schema",
                )
            ],
            artifacts=[],
            targets=[
                DeploymentTarget(
                    target_id="db-target",
                    name="user-db",
                    environment="production",
                    region="us-east-1",
                    resource_type="rds",
                )
            ],
            environment="production",
            initiated_by="dba",
        )

        result = await deployment_correlator.record_deployment(deployment)

        # Database migration in production should be high/critical risk
        assert result.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert len(result.risk_factors) > 0
        assert any("Database" in f for f in result.risk_factors)

    @pytest.mark.asyncio
    async def test_update_deployment_status(
        self, deployment_correlator, sample_deployment
    ):
        """Test updating deployment status."""
        await deployment_correlator.record_deployment(sample_deployment)

        updated = await deployment_correlator.update_deployment_status(
            "deploy-001",
            DeploymentStatus.ROLLED_BACK,
        )

        assert updated.status == DeploymentStatus.ROLLED_BACK
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_deployment_with_metrics(
        self, deployment_correlator, sample_deployment
    ):
        """Test updating deployment with new metrics."""
        await deployment_correlator.record_deployment(sample_deployment)

        new_metrics = DeploymentMetrics(
            duration_seconds=600,
            replicas_updated=3,
            replicas_failed=1,
            error_rate_before=0.01,
            error_rate_after=0.10,  # Bad increase
            health_check_failures=5,
        )

        updated = await deployment_correlator.update_deployment_status(
            "deploy-001",
            DeploymentStatus.FAILED,
            metrics=new_metrics,
        )

        assert updated.metrics.error_rate_after == 0.10
        assert updated.health_score < 100  # Should be penalized

    @pytest.mark.asyncio
    async def test_record_incident(self, deployment_correlator, sample_incident):
        """Test recording an incident."""
        result = await deployment_correlator.record_incident(sample_incident)

        assert result.incident_id == "inc-001"

    @pytest.mark.asyncio
    async def test_correlate_incident_to_deployments(
        self, deployment_correlator, sample_deployment, sample_incident
    ):
        """Test correlating an incident to deployments."""
        # Record a deployment that happened before the incident
        sample_deployment.started_at = sample_incident.detected_at - timedelta(
            minutes=15
        )
        await deployment_correlator.record_deployment(sample_deployment)

        # Record the incident
        correlations = await deployment_correlator.correlate_incident_to_deployments(
            sample_incident
        )

        # Should find correlation due to time proximity and service overlap
        assert len(correlations) > 0
        correlation = correlations[0]
        assert correlation.deployment_id == "deploy-001"
        assert correlation.confidence_score >= 0.3

    @pytest.mark.asyncio
    async def test_analyze_blast_radius(self, deployment_correlator, sample_deployment):
        """Test blast radius analysis."""
        await deployment_correlator.record_deployment(sample_deployment)

        analysis = await deployment_correlator.analyze_blast_radius(sample_deployment)

        assert analysis.deployment_id == "deploy-001"
        assert len(analysis.directly_affected_services) > 0
        assert "api-service" in analysis.directly_affected_services

    @pytest.mark.asyncio
    async def test_recommend_rollback_should_rollback(self, deployment_correlator):
        """Test rollback recommendation when rollback is advised."""
        deployment = Deployment(
            deployment_id="deploy-bad",
            name="bad-deployment",
            description="Deployment with issues",
            deployment_type=DeploymentType.ROLLING,
            status=DeploymentStatus.SUCCEEDED,
            changes=[],
            artifacts=[],
            targets=[
                DeploymentTarget(
                    target_id="target",
                    name="service",
                    environment="production",
                    region="us-east-1",
                    resource_type="eks",
                )
            ],
            environment="production",
            initiated_by="ci",
            metrics=DeploymentMetrics(
                error_rate_before=0.01,
                error_rate_after=0.15,  # Big increase
                health_check_failures=10,
            ),
            health_score=50,
        )

        recommendation = await deployment_correlator.recommend_rollback(deployment)

        assert recommendation.should_rollback is True
        assert recommendation.confidence >= 0.5
        assert len(recommendation.reasons) > 0
        assert len(recommendation.rollback_steps) > 0

    @pytest.mark.asyncio
    async def test_recommend_rollback_no_rollback_needed(self, deployment_correlator):
        """Test rollback recommendation when no rollback needed."""
        deployment = Deployment(
            deployment_id="deploy-good",
            name="good-deployment",
            description="Healthy deployment",
            deployment_type=DeploymentType.BLUE_GREEN,
            status=DeploymentStatus.SUCCEEDED,
            changes=[],
            artifacts=[],
            targets=[],
            environment="staging",
            initiated_by="ci",
            metrics=DeploymentMetrics(
                error_rate_before=0.01,
                error_rate_after=0.01,  # No change
            ),
            health_score=95,
        )

        recommendation = await deployment_correlator.recommend_rollback(deployment)

        assert recommendation.should_rollback is False
        assert len(recommendation.alternative_actions) > 0

    @pytest.mark.asyncio
    async def test_generate_health_report(
        self, deployment_correlator, sample_deployment
    ):
        """Test generating deployment health report."""
        # Record several deployments
        for i in range(5):
            deployment = Deployment(
                deployment_id=f"deploy-{i}",
                name=f"deployment-{i}",
                description="Test deployment",
                deployment_type=DeploymentType.ROLLING,
                status=DeploymentStatus.SUCCEEDED if i < 4 else DeploymentStatus.FAILED,
                changes=[],
                artifacts=[],
                targets=[],
                environment="production",
                initiated_by="ci",
                metrics=DeploymentMetrics(duration_seconds=300),
            )
            await deployment_correlator.record_deployment(deployment)

        report = await deployment_correlator.generate_health_report(days=7)

        assert report.total_deployments == 5
        assert report.successful_deployments == 4
        assert report.failed_deployments == 1
        assert report.success_rate == 0.8

    def test_create_change_window(self, deployment_correlator):
        """Test creating a change window."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=4)

        window = deployment_correlator.create_change_window(
            name="Weekly Change Window",
            start_time=start,
            end_time=end,
            environment="production",
        )

        assert window.name == "Weekly Change Window"
        assert window.environment == "production"
        assert window.is_frozen is False

    def test_freeze_deployments(self, deployment_correlator):
        """Test freezing deployments."""
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=4)

        deployment_correlator.create_change_window(
            name="Window",
            start_time=start,
            end_time=end,
            environment="production",
        )

        deployment_correlator.freeze_deployments("production", "Major incident")

        for window in deployment_correlator._change_windows.values():
            if window.environment == "production":
                assert window.is_frozen is True

    def test_register_service_dependency(self, deployment_correlator):
        """Test registering service dependencies."""
        deployment_correlator.register_service_dependency(
            "api-service", ["auth-service", "user-service"]
        )

        deps = deployment_correlator.get_service_dependencies("api-service")
        assert "auth-service" in deps
        assert "user-service" in deps

    @pytest.mark.asyncio
    async def test_get_recent_deployments(
        self, deployment_correlator, sample_deployment
    ):
        """Test getting recent deployments."""
        await deployment_correlator.record_deployment(sample_deployment)

        deployments = await deployment_correlator.get_recent_deployments(limit=10)

        assert len(deployments) > 0
        assert deployments[0].deployment_id == "deploy-001"

    @pytest.mark.asyncio
    async def test_get_deployments_for_service(
        self, deployment_correlator, sample_deployment
    ):
        """Test getting deployments for a specific service."""
        await deployment_correlator.record_deployment(sample_deployment)

        deployments = await deployment_correlator.get_deployments_for_service(
            "api-service"
        )

        assert len(deployments) > 0


# =============================================================================
# ResourceTopologyMapper Tests
# =============================================================================


class TestResourceTopologyMapper:
    """Tests for ResourceTopologyMapper."""

    @pytest.mark.asyncio
    async def test_discover_resources(self, topology_mapper):
        """Test resource discovery."""
        resources = await topology_mapper.discover_resources(
            account_id="123456789",
            regions=["us-east-1"],
            resource_types=[ResourceType.EC2_INSTANCE, ResourceType.RDS_INSTANCE],
        )

        # Should discover simulated resources
        assert len(resources) > 0

    @pytest.mark.asyncio
    async def test_discover_resources_default_regions(self, topology_mapper):
        """Test resource discovery with default regions."""
        resources = await topology_mapper.discover_resources(
            account_id="123456789",
        )

        assert len(resources) > 0

    def test_create_service(self, topology_mapper, sample_resource):
        """Test creating a service from resources."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        service = topology_mapper.create_service(
            name="api-service",
            description="API Service",
            owner="platform-team",
            team="platform",
            resource_ids=[sample_resource.resource_id],
            tier="critical",
        )

        assert service.name == "api-service"
        assert service.tier == "critical"
        assert sample_resource.resource_id in service.resources

    def test_get_service(self, topology_mapper, sample_resource):
        """Test getting a service by ID."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource
        service = topology_mapper.create_service(
            name="test-service",
            description="Test",
            owner="team",
            team="team",
            resource_ids=[sample_resource.resource_id],
        )

        retrieved = topology_mapper.get_service(service.service_id)

        assert retrieved is not None
        assert retrieved.name == "test-service"

    def test_get_service_by_name(self, topology_mapper, sample_resource):
        """Test getting a service by name."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource
        topology_mapper.create_service(
            name="named-service",
            description="Test",
            owner="team",
            team="team",
            resource_ids=[sample_resource.resource_id],
        )

        service = topology_mapper.get_service_by_name("named-service")

        assert service is not None
        assert service.name == "named-service"

    @pytest.mark.asyncio
    async def test_get_resource(self, topology_mapper, sample_resource):
        """Test getting a resource by ID."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        resource = await topology_mapper.get_resource(sample_resource.resource_id)

        assert resource is not None
        assert resource.name == "aura-api-1"

    @pytest.mark.asyncio
    async def test_get_resources_by_type(self, topology_mapper):
        """Test getting resources by type."""
        await topology_mapper.discover_resources(
            account_id="123456789",
            regions=["us-east-1"],
        )

        ec2_instances = await topology_mapper.get_resources_by_type(
            ResourceType.EC2_INSTANCE
        )

        assert len(ec2_instances) > 0
        assert all(r.resource_type == ResourceType.EC2_INSTANCE for r in ec2_instances)

    @pytest.mark.asyncio
    async def test_get_resources_by_tag(self, topology_mapper, sample_resource):
        """Test getting resources by tag."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        resources = await topology_mapper.get_resources_by_tag(
            "Environment", "production"
        )

        assert len(resources) > 0

    @pytest.mark.asyncio
    async def test_get_upstream_resources(self, topology_mapper):
        """Test getting upstream resources."""
        # Create resources with relationships
        source = Resource(
            resource_id="source",
            arn="arn:source",
            name="source",
            resource_type=ResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
        )
        target = Resource(
            resource_id="target",
            arn="arn:target",
            name="target",
            resource_type=ResourceType.RDS_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
        )

        topology_mapper._resources["source"] = source
        topology_mapper._resources["target"] = target
        topology_mapper._relationships["rel-001"] = ResourceRelationship(
            relationship_id="rel-001",
            source_id="source",
            target_id="target",
            relationship_type=RelationshipType.DEPENDS_ON,
        )

        upstream = await topology_mapper.get_upstream_resources("target")

        assert len(upstream) > 0
        assert upstream[0].resource_id == "source"

    @pytest.mark.asyncio
    async def test_get_downstream_resources(self, topology_mapper):
        """Test getting downstream resources."""
        source = Resource(
            resource_id="source",
            arn="arn:source",
            name="source",
            resource_type=ResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
        )
        target = Resource(
            resource_id="target",
            arn="arn:target",
            name="target",
            resource_type=ResourceType.RDS_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
        )

        topology_mapper._resources["source"] = source
        topology_mapper._resources["target"] = target
        topology_mapper._relationships["rel-001"] = ResourceRelationship(
            relationship_id="rel-001",
            source_id="source",
            target_id="target",
            relationship_type=RelationshipType.DEPENDS_ON,
        )

        downstream = await topology_mapper.get_downstream_resources("source")

        assert len(downstream) > 0
        assert downstream[0].resource_id == "target"

    @pytest.mark.asyncio
    async def test_get_service_topology(self, topology_mapper, sample_resource):
        """Test getting service topology."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource
        service = topology_mapper.create_service(
            name="test-service",
            description="Test",
            owner="team",
            team="team",
            resource_ids=[sample_resource.resource_id],
        )

        topology = await topology_mapper.get_service_topology(service.service_id)

        assert topology is not None
        assert topology["service"]["name"] == "test-service"
        assert len(topology["resources"]) > 0

    @pytest.mark.asyncio
    async def test_take_snapshot(self, topology_mapper, sample_resource):
        """Test taking a topology snapshot."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        snapshot = await topology_mapper.take_snapshot()

        assert snapshot.total_resources == 1
        assert snapshot.total_monthly_cost > 0

    @pytest.mark.asyncio
    async def test_compare_snapshots(self, topology_mapper, sample_resource):
        """Test comparing topology snapshots."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        snapshot1 = await topology_mapper.take_snapshot()

        # Add another resource
        topology_mapper._resources["resource-2"] = Resource(
            resource_id="resource-2",
            arn="arn:resource-2",
            name="another-resource",
            resource_type=ResourceType.LAMBDA_FUNCTION,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
        )

        snapshot2 = await topology_mapper.take_snapshot()

        drift_report = await topology_mapper.compare_snapshots(
            snapshot1.snapshot_id,
            snapshot2.snapshot_id,
        )

        assert drift_report.total_drifted_resources > 0

    @pytest.mark.asyncio
    async def test_analyze_change_impact(self, topology_mapper, sample_resource):
        """Test analyzing change impact."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        _service = topology_mapper.create_service(
            name="critical-service",
            description="Critical",
            owner="team",
            team="team",
            resource_ids=[sample_resource.resource_id],
            tier="critical",
        )

        analysis = await topology_mapper.analyze_change_impact(
            target_resource_ids=[sample_resource.resource_id],
            change_description="Update instance type",
        )

        assert analysis is not None
        assert len(analysis.directly_affected) > 0
        assert analysis.risk_score > 0

    @pytest.mark.asyncio
    async def test_get_cost_breakdown(self, topology_mapper, sample_resource):
        """Test getting cost breakdown."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        breakdown = await topology_mapper.get_cost_breakdown(days=30)

        assert breakdown.total_cost > 0
        assert "production" in breakdown.by_environment

    def test_export_to_graphviz(self, topology_mapper, sample_resource):
        """Test exporting topology to Graphviz format."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        dot = topology_mapper.export_to_graphviz()

        assert "digraph Topology" in dot
        assert sample_resource.resource_id in dot

    def test_export_to_json(self, topology_mapper, sample_resource):
        """Test exporting topology to JSON format."""
        topology_mapper._resources[sample_resource.resource_id] = sample_resource

        json_str = topology_mapper.export_to_json()

        assert "resources" in json_str
        assert sample_resource.resource_id in json_str


# =============================================================================
# IncidentPatternAnalyzer Tests
# =============================================================================


class TestIncidentPatternAnalyzer:
    """Tests for IncidentPatternAnalyzer."""

    @pytest.mark.asyncio
    async def test_record_incident(self, incident_analyzer, sample_analyzer_incident):
        """Test recording an incident."""
        result = await incident_analyzer.record_incident(sample_analyzer_incident)

        assert result.incident_id == "inc-002"
        assert result.metrics is not None

    @pytest.mark.asyncio
    async def test_update_incident_status(
        self, incident_analyzer, sample_analyzer_incident
    ):
        """Test updating incident status."""
        await incident_analyzer.record_incident(sample_analyzer_incident)

        updated = await incident_analyzer.update_incident(
            "inc-002",
            status=IncidentStatus.RESOLVED,
            root_cause="Database connection pool exhausted",
            root_cause_category=RootCauseCategory.CAPACITY,
        )

        assert updated.status == IncidentStatus.RESOLVED
        assert updated.root_cause == "Database connection pool exhausted"
        assert updated.resolved_at is not None

    @pytest.mark.asyncio
    async def test_analyze_root_cause(
        self, incident_analyzer, sample_analyzer_incident
    ):
        """Test root cause analysis."""
        await incident_analyzer.record_incident(sample_analyzer_incident)

        analysis = await incident_analyzer.analyze_root_cause(sample_analyzer_incident)

        assert analysis is not None
        assert analysis.incident_id == "inc-002"
        assert (
            analysis.root_cause_category != RootCauseCategory.UNKNOWN
            or analysis.confidence <= 0.5
        )
        assert len(analysis.immediate_actions) > 0

    @pytest.mark.asyncio
    async def test_analyze_root_cause_with_deployment_correlation(
        self, incident_analyzer
    ):
        """Test root cause analysis with deployment correlation."""
        incident = IncidentAnalyzerIncident(
            incident_id="inc-deploy",
            title="Error rate spike",
            description="Errors after deployment",
            severity=AnalyzerIncidentSeverity.SEV2,
            status=IncidentStatus.INVESTIGATING,
            category=IncidentCategory.ERROR_RATE,
            affected_services=["api-service"],
            affected_regions=["us-east-1"],
            customer_impact="API errors",
            detected_at=datetime.now(timezone.utc),
            related_deployments=["deploy-001"],
        )

        await incident_analyzer.record_incident(incident)
        analysis = await incident_analyzer.analyze_root_cause(incident)

        assert analysis.root_cause_category == RootCauseCategory.CODE_CHANGE

    @pytest.mark.asyncio
    async def test_detect_patterns(self, incident_analyzer):
        """Test pattern detection across incidents."""
        # Create multiple similar incidents
        for i in range(5):
            incident = IncidentAnalyzerIncident(
                incident_id=f"pattern-inc-{i}",
                title="High Error Rate",
                description="Error rate increased",
                severity=AnalyzerIncidentSeverity.SEV3,
                status=IncidentStatus.RESOLVED,
                category=IncidentCategory.ERROR_RATE,
                affected_services=["api-service"],
                affected_regions=["us-east-1"],
                customer_impact="Intermittent errors",
                detected_at=datetime.now(timezone.utc) - timedelta(days=i * 10),
            )
            await incident_analyzer.record_incident(incident)

        patterns = await incident_analyzer.detect_patterns()

        # Should detect recurring pattern
        assert len(patterns) > 0
        assert any(p.pattern_type == PatternType.RECURRING for p in patterns)

    @pytest.mark.asyncio
    async def test_recommend_runbooks(
        self, incident_analyzer, sample_analyzer_incident
    ):
        """Test runbook recommendations."""
        recommendations = await incident_analyzer.recommend_runbooks(
            sample_analyzer_incident
        )

        assert len(recommendations) > 0
        assert all(r.relevance_score >= 0 for r in recommendations)

    def test_register_runbook(self, incident_analyzer):
        """Test registering a custom runbook."""
        incident_analyzer.register_runbook(
            runbook_id="custom-001",
            name="Custom Runbook",
            description="Custom incident response",
            category="availability",
            services=["api-service"],
            steps=["Step 1", "Step 2"],
            estimated_time="15 minutes",
            automated=True,
        )

        assert "custom-001" in incident_analyzer._runbooks
        assert incident_analyzer._runbooks["custom-001"]["automated"] is True

    def test_define_slo(self, incident_analyzer):
        """Test defining an SLO."""
        slo = incident_analyzer.define_slo(
            name="API Availability",
            service="api-service",
            objective_type="availability",
            target_value=99.9,
            window_days=30,
        )

        assert slo.name == "API Availability"
        assert slo.target_value == 99.9

    @pytest.mark.asyncio
    async def test_get_slo_status_healthy(self, incident_analyzer):
        """Test getting SLO status when healthy."""
        slo = incident_analyzer.define_slo(
            name="Healthy SLO",
            service="api-service",
            objective_type="availability",
            target_value=99.0,
        )

        status = await incident_analyzer.get_slo_status(slo.slo_id, 99.5)

        assert status.status == "healthy"
        assert status.error_budget_remaining > 0

    @pytest.mark.asyncio
    async def test_get_slo_status_breached(self, incident_analyzer):
        """Test getting SLO status when breached."""
        slo = incident_analyzer.define_slo(
            name="Breached SLO",
            service="api-service",
            objective_type="availability",
            target_value=99.9,
        )

        status = await incident_analyzer.get_slo_status(slo.slo_id, 98.0)

        assert status.status == "breached"

    @pytest.mark.asyncio
    async def test_generate_predictive_alerts(self, incident_analyzer):
        """Test generating predictive alerts."""
        # Define an SLO that will trigger warning
        _slo = incident_analyzer.define_slo(
            name="At Risk SLO",
            service="api-service",
            objective_type="availability",
            target_value=99.9,
        )

        alerts = await incident_analyzer.generate_predictive_alerts()

        # Should generate alerts based on SLO status
        assert isinstance(alerts, list)

    @pytest.mark.asyncio
    async def test_generate_post_incident_report(
        self, incident_analyzer, sample_analyzer_incident
    ):
        """Test generating post-incident report."""
        sample_analyzer_incident.resolved_at = datetime.now(timezone.utc)
        sample_analyzer_incident.metrics.mttr_seconds = 1800
        sample_analyzer_incident.root_cause = "Connection pool exhaustion"
        sample_analyzer_incident.actions_taken = ["Scaled up connections"]

        await incident_analyzer.record_incident(sample_analyzer_incident)

        report = await incident_analyzer.generate_post_incident_report(
            sample_analyzer_incident
        )

        assert report.incident_id == "inc-002"
        assert report.executive_summary != ""
        assert report.duration_minutes > 0


# =============================================================================
# DevOpsAgentOrchestrator Tests
# =============================================================================


class TestDevOpsAgentOrchestrator:
    """Tests for DevOpsAgentOrchestrator."""

    @pytest.mark.asyncio
    async def test_triage_alert_critical(self, devops_orchestrator, sample_alert):
        """Test triaging a critical alert."""
        sample_alert.severity = "critical"

        result = await devops_orchestrator.triage_alert(sample_alert)

        assert result.alert.alert_id == "alert-001"
        assert result.action == TriageAction.PAGE_ONCALL
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_triage_alert_with_deployment_correlation(
        self, devops_orchestrator, sample_alert
    ):
        """Test triaging an alert with deployment correlation."""
        # First record a deployment
        deployment = Deployment(
            deployment_id="deploy-recent",
            name="recent-deploy",
            description="Recent deployment",
            deployment_type=DeploymentType.ROLLING,
            status=DeploymentStatus.SUCCEEDED,
            changes=[],
            artifacts=[],
            targets=[
                DeploymentTarget(
                    target_id="target",
                    name="api-service",
                    environment="production",
                    region="us-east-1",
                    resource_type="eks",
                )
            ],
            environment="production",
            initiated_by="ci",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        await devops_orchestrator.deployment_correlator.record_deployment(deployment)

        result = await devops_orchestrator.triage_alert(sample_alert)

        assert len(result.recent_deployments) > 0
        assert any("deployment" in r.lower() for r in result.reasoning)

    @pytest.mark.asyncio
    async def test_triage_alert_monitor_low_severity(
        self, devops_orchestrator, sample_alert
    ):
        """Test triaging a low severity alert results in monitor action."""
        sample_alert.severity = "low"

        result = await devops_orchestrator.triage_alert(sample_alert)

        assert result.action == TriageAction.MONITOR

    @pytest.mark.asyncio
    async def test_execute_remediation_rollback(
        self, devops_orchestrator, sample_alert
    ):
        """Test executing rollback remediation."""
        # Record deployment first
        deployment = Deployment(
            deployment_id="deploy-for-rollback",
            name="deploy-rollback",
            description="Deployment to rollback",
            deployment_type=DeploymentType.ROLLING,
            status=DeploymentStatus.SUCCEEDED,
            changes=[],
            artifacts=[],
            targets=[
                DeploymentTarget(
                    target_id="target",
                    name="api-service",
                    environment="production",
                    region="us-east-1",
                    resource_type="eks",
                )
            ],
            environment="production",
            initiated_by="ci",
        )
        await devops_orchestrator.deployment_correlator.record_deployment(deployment)

        # Create triage result with rollback action
        triage_result = TriageResult(
            triage_id="triage-001",
            alert=sample_alert,
            action=TriageAction.ROLLBACK,
            confidence=0.85,
            reasoning=["Deployment correlated"],
            recent_deployments=[deployment],
            similar_incidents=[],
            affected_services=["api-service"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=True,
            remediation_steps=["Rollback", "Verify"],
            escalation_target=None,
            estimated_severity=AnalyzerIncidentSeverity.SEV2,
        )

        workflow = await devops_orchestrator.execute_remediation(triage_result)

        assert workflow.status in [
            RemediationStatus.SUCCEEDED,
            RemediationStatus.FAILED,
        ]
        assert len(workflow.actions) > 0

    @pytest.mark.asyncio
    async def test_execute_remediation_scale(self, devops_orchestrator, sample_alert):
        """Test executing scale remediation."""
        triage_result = TriageResult(
            triage_id="triage-scale",
            alert=sample_alert,
            action=TriageAction.SCALE,
            confidence=0.75,
            reasoning=["High load"],
            recent_deployments=[],
            similar_incidents=[],
            affected_services=["api-service"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=True,
            remediation_steps=["Scale up"],
            escalation_target=None,
            estimated_severity=AnalyzerIncidentSeverity.SEV3,
        )

        workflow = await devops_orchestrator.execute_remediation(triage_result)

        assert workflow.status in [
            RemediationStatus.SUCCEEDED,
            RemediationStatus.FAILED,
        ]
        assert any(a.action_type == "scale_out" for a in workflow.actions)

    @pytest.mark.asyncio
    async def test_execute_remediation_restart(self, devops_orchestrator, sample_alert):
        """Test executing restart remediation."""
        triage_result = TriageResult(
            triage_id="triage-restart",
            alert=sample_alert,
            action=TriageAction.RESTART,
            confidence=0.70,
            reasoning=["Unhealthy instances"],
            recent_deployments=[],
            similar_incidents=[],
            affected_services=["api-service"],
            blast_radius=[],
            runbook_recommendations=[],
            rollback_recommendation=None,
            auto_remediation_available=True,
            remediation_steps=["Restart instances"],
            escalation_target=None,
            estimated_severity=AnalyzerIncidentSeverity.SEV3,
        )

        workflow = await devops_orchestrator.execute_remediation(triage_result)

        assert any(a.action_type == "rolling_restart" for a in workflow.actions)

    def test_register_auto_remediation_rule(self, devops_orchestrator):
        """Test registering auto-remediation rule."""
        devops_orchestrator.register_auto_remediation_rule(
            service="api-service",
            metric="ErrorRate",
            severity="high",
            action=TriageAction.RESTART,
            steps=["Restart pods", "Verify health"],
        )

        assert len(devops_orchestrator._auto_remediation_rules) == 1
        assert (
            devops_orchestrator._auto_remediation_rules[0]["service"] == "api-service"
        )

    @pytest.mark.asyncio
    async def test_generate_operational_report(self, devops_orchestrator):
        """Test generating operational report."""
        # Record some data first
        deployment = Deployment(
            deployment_id="report-deploy",
            name="test-deploy",
            description="Test",
            deployment_type=DeploymentType.ROLLING,
            status=DeploymentStatus.SUCCEEDED,
            changes=[],
            artifacts=[],
            targets=[],
            environment="production",
            initiated_by="ci",
        )
        await devops_orchestrator.deployment_correlator.record_deployment(deployment)

        report = await devops_orchestrator.generate_operational_report(days=7)

        assert report.total_deployments >= 0
        assert report.period_start < report.period_end

    @pytest.mark.asyncio
    async def test_process_alert_end_to_end(self, devops_orchestrator, sample_alert):
        """Test end-to-end alert processing."""
        result = await devops_orchestrator.process_alert_end_to_end(sample_alert)

        assert "triage" in result
        assert "action_taken" in result
        assert "confidence" in result
        assert result["triage"].alert.alert_id == "alert-001"

    @pytest.mark.asyncio
    async def test_process_alert_creates_incident(
        self, devops_orchestrator, sample_alert
    ):
        """Test that processing critical alert creates incident."""
        sample_alert.severity = "critical"

        result = await devops_orchestrator.process_alert_end_to_end(sample_alert)

        # Critical alert should create incident
        assert result["incident"] is not None

    def test_component_access_properties(self, devops_orchestrator):
        """Test component access properties."""
        assert devops_orchestrator.deployment_correlator is not None
        assert devops_orchestrator.topology_mapper is not None
        assert devops_orchestrator.incident_analyzer is not None

    @pytest.mark.asyncio
    async def test_map_alert_severity(self, devops_orchestrator):
        """Test alert severity mapping."""
        assert (
            devops_orchestrator._map_alert_severity("critical")
            == AnalyzerIncidentSeverity.SEV1
        )
        assert (
            devops_orchestrator._map_alert_severity("high")
            == AnalyzerIncidentSeverity.SEV2
        )
        assert (
            devops_orchestrator._map_alert_severity("warning")
            == AnalyzerIncidentSeverity.SEV3
        )
        assert (
            devops_orchestrator._map_alert_severity("low")
            == AnalyzerIncidentSeverity.SEV4
        )
        assert (
            devops_orchestrator._map_alert_severity("unknown")
            == AnalyzerIncidentSeverity.SEV3
        )

    @pytest.mark.asyncio
    async def test_infer_category_from_alert(self, devops_orchestrator, sample_alert):
        """Test inferring incident category from alert."""
        sample_alert.metric_name = "ErrorRate"
        category = devops_orchestrator._infer_category(sample_alert)
        assert category == IncidentCategory.ERROR_RATE

        sample_alert.metric_name = "Latency_p99"
        category = devops_orchestrator._infer_category(sample_alert)
        assert category == IncidentCategory.LATENCY

        sample_alert.metric_name = "CPUUtilization"
        category = devops_orchestrator._infer_category(sample_alert)
        assert category == IncidentCategory.SATURATION


# =============================================================================
# Integration Tests
# =============================================================================


class TestDevOpsIntegration:
    """Integration tests across devops services."""

    @pytest.mark.asyncio
    async def test_full_incident_workflow(self):
        """Test full incident workflow across services."""
        orchestrator = DevOpsAgentOrchestrator()

        # 1. Record a deployment
        deployment = Deployment(
            deployment_id="integration-deploy",
            name="integration-test",
            description="Integration test deployment",
            deployment_type=DeploymentType.ROLLING,
            status=DeploymentStatus.SUCCEEDED,
            changes=[
                DeploymentChange(
                    change_id="change",
                    category=ChangeCategory.CODE,
                    description="Feature update",
                )
            ],
            artifacts=[],
            targets=[
                DeploymentTarget(
                    target_id="target",
                    name="test-service",
                    environment="production",
                    region="us-east-1",
                    resource_type="eks",
                )
            ],
            environment="production",
            initiated_by="ci",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        )
        await orchestrator.deployment_correlator.record_deployment(deployment)

        # 2. Alert fires
        alert = Alert(
            alert_id="integration-alert",
            alert_type=AlertType.THRESHOLD,
            severity="high",
            title="Error rate spike",
            description="Error rate increased after deployment",
            source="CloudWatch",
            service="test-service",
            metric_name="ErrorRate",
            metric_value=0.10,
            threshold=0.05,
        )

        # 3. Process alert end-to-end
        result = await orchestrator.process_alert_end_to_end(alert)

        # Verify workflow
        assert result["triage"] is not None
        assert result["action_taken"] in [a.value for a in TriageAction]

        # 4. Generate report
        report = await orchestrator.generate_operational_report(days=1)
        assert report.total_deployments >= 1

    @pytest.mark.asyncio
    async def test_topology_and_blast_radius(self):
        """Test topology mapping and blast radius analysis."""
        orchestrator = DevOpsAgentOrchestrator()

        # Discover resources
        await orchestrator.topology_mapper.discover_resources(
            account_id="123456789",
            regions=["us-east-1"],
        )

        # Create service
        resources = list(orchestrator.topology_mapper._resources.values())
        if resources:
            _service = orchestrator.topology_mapper.create_service(
                name="discovered-service",
                description="Auto-discovered service",
                owner="platform",
                team="platform",
                resource_ids=[r.resource_id for r in resources[:3]],
                tier="critical",
            )

            # Analyze impact
            impact = await orchestrator.topology_mapper.analyze_change_impact(
                target_resource_ids=[resources[0].resource_id],
                change_description="Instance type upgrade",
            )

            assert impact.risk_score > 0

    @pytest.mark.asyncio
    async def test_pattern_detection_and_prediction(self):
        """Test pattern detection and predictive alerting."""
        analyzer = IncidentPatternAnalyzer()

        # Record multiple incidents to establish pattern
        for i in range(5):
            incident = IncidentAnalyzerIncident(
                incident_id=f"pattern-{i}",
                title="Memory pressure",
                description="OOM events",
                severity=AnalyzerIncidentSeverity.SEV3,
                status=IncidentStatus.RESOLVED,
                category=IncidentCategory.SATURATION,
                affected_services=["memory-heavy-service"],
                affected_regions=["us-east-1"],
                customer_impact="Slow responses",
                detected_at=datetime.now(timezone.utc) - timedelta(days=i * 7),
                resolved_at=datetime.now(timezone.utc)
                - timedelta(days=i * 7)
                + timedelta(hours=1),
            )
            incident.metrics.mttr_seconds = 3600
            await analyzer.record_incident(incident)

        # Detect patterns
        patterns = await analyzer.detect_patterns()

        # Should find recurring pattern
        recurring_patterns = [
            p for p in patterns if p.pattern_type == PatternType.RECURRING
        ]
        assert len(recurring_patterns) > 0
        assert recurring_patterns[0].common_services == ["memory-heavy-service"]


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestDevOpsEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_update_nonexistent_deployment(self, deployment_correlator):
        """Test updating a non-existent deployment raises error."""
        with pytest.raises(ValueError, match="Deployment not found"):
            await deployment_correlator.update_deployment_status(
                "nonexistent",
                DeploymentStatus.SUCCEEDED,
            )

    @pytest.mark.asyncio
    async def test_update_nonexistent_incident(self, incident_analyzer):
        """Test updating a non-existent incident raises error."""
        with pytest.raises(ValueError, match="Incident not found"):
            await incident_analyzer.update_incident(
                "nonexistent",
                status=IncidentStatus.RESOLVED,
            )

    @pytest.mark.asyncio
    async def test_get_slo_status_nonexistent(self, incident_analyzer):
        """Test getting status of non-existent SLO raises error."""
        with pytest.raises(ValueError, match="SLO not found"):
            await incident_analyzer.get_slo_status("nonexistent", 99.5)

    @pytest.mark.asyncio
    async def test_compare_nonexistent_snapshots(self, topology_mapper):
        """Test comparing non-existent snapshots raises error."""
        with pytest.raises(ValueError, match="Snapshot not found"):
            await topology_mapper.compare_snapshots("snap1", "snap2")

    @pytest.mark.asyncio
    async def test_empty_service_topology(self, topology_mapper):
        """Test getting topology for non-existent service returns empty."""
        topology = await topology_mapper.get_service_topology("nonexistent")
        assert topology == {}

    @pytest.mark.asyncio
    async def test_health_report_no_deployments(self, deployment_correlator):
        """Test health report with no deployments."""
        report = await deployment_correlator.generate_health_report(days=7)

        assert report.total_deployments == 0
        assert report.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_pattern_detection_insufficient_data(self, incident_analyzer):
        """Test pattern detection with insufficient data."""
        # Only one incident - not enough for patterns
        incident = IncidentAnalyzerIncident(
            incident_id="single",
            title="Single incident",
            description="Only one",
            severity=AnalyzerIncidentSeverity.SEV3,
            status=IncidentStatus.RESOLVED,
            category=IncidentCategory.AVAILABILITY,
            affected_services=["service"],
            affected_regions=["us-east-1"],
            customer_impact="Minor",
            detected_at=datetime.now(timezone.utc),
        )
        await incident_analyzer.record_incident(incident)

        patterns = await incident_analyzer.detect_patterns()

        # Should not find patterns with single incident
        recurring = [p for p in patterns if p.pattern_type == PatternType.RECURRING]
        assert len(recurring) == 0

    @pytest.mark.asyncio
    async def test_cost_breakdown_empty_resources(self, topology_mapper):
        """Test cost breakdown with no resources."""
        breakdown = await topology_mapper.get_cost_breakdown(days=30)

        assert breakdown.total_cost == 0.0
        assert len(breakdown.cost_anomalies) == 0


# =============================================================================
# Data Model Tests
# =============================================================================


class TestDevOpsDataModels:
    """Test data model creation and validation."""

    def test_deployment_change_model(self):
        """Test DeploymentChange model."""
        change = DeploymentChange(
            change_id="change-001",
            category=ChangeCategory.CODE,
            description="Add feature",
            files_changed=["file1.py", "file2.py"],
            commit_sha="abc123",
            risk_score=0.5,
        )

        assert change.change_id == "change-001"
        assert change.category == ChangeCategory.CODE
        assert len(change.files_changed) == 2

    def test_resource_tag_model(self):
        """Test ResourceTag model."""
        tag = ResourceTag(key="Environment", value="production")

        assert tag.key == "Environment"
        assert tag.value == "production"

    def test_incident_timeline_model(self):
        """Test IncidentTimeline model."""
        timeline = IncidentTimeline(
            timestamp=datetime.now(timezone.utc),
            event_type="acknowledged",
            description="Incident acknowledged",
            actor="oncall@example.com",
        )

        assert timeline.event_type == "acknowledged"
        assert timeline.actor == "oncall@example.com"

    def test_runbook_recommendation_model(self):
        """Test RunbookRecommendation model."""
        recommendation = RunbookRecommendation(
            runbook_id="rb-001",
            name="Error Rate Response",
            description="Handle high error rates",
            relevance_score=0.9,
            matching_factors=["category match", "service match"],
            estimated_resolution_time="30 minutes",
            steps=["Check logs", "Scale up", "Monitor"],
            automation_available=True,
        )

        assert recommendation.relevance_score == 0.9
        assert recommendation.automation_available is True
        assert len(recommendation.steps) == 3

    def test_remediation_action_model(self):
        """Test RemediationAction model."""
        action = RemediationAction(
            action_id="action-001",
            action_type="rollback",
            target="api-service",
            parameters={"deployment_id": "deploy-001"},
        )

        assert action.status == RemediationStatus.PENDING
        assert action.action_type == "rollback"

    def test_devops_insight_model(self):
        """Test DevOpsInsight model."""
        insight = DevOpsInsight(
            insight_id="insight-001",
            category="deployments",
            title="High failure rate",
            description="Deployment success rate below target",
            severity="high",
            evidence=["5 failed deployments"],
            recommendations=["Improve testing"],
            affected_services=["api-service"],
        )

        assert insight.severity == "high"
        assert len(insight.recommendations) == 1
