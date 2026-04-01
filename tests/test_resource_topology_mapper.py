"""
Project Aura - Resource Topology Mapper Tests

Tests for the resource topology mapping service that handles
infrastructure discovery, dependency graphs, and drift detection.
"""

import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# Save original modules before mocking to prevent test pollution
_modules_to_save = ["structlog"]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock structlog
mock_structlog = MagicMock()
mock_structlog.get_logger = MagicMock(return_value=MagicMock())
sys.modules["structlog"] = mock_structlog

from src.services.devops.resource_topology_mapper import (
    CloudProvider,
    CostBreakdown,
    DriftItem,
    DriftReport,
    DriftType,
    ImpactAnalysis,
    RelationshipType,
    Resource,
    ResourceMetrics,
    ResourceRelationship,
    ResourceStatus,
    ResourceTag,
    ResourceTopologyMapper,
    ResourceType,
    ServiceComponent,
    TopologySnapshot,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


class TestCloudProvider:
    """Tests for CloudProvider enum."""

    def test_aws_provider(self):
        """Test AWS provider."""
        assert CloudProvider.AWS.value == "aws"

    def test_azure_provider(self):
        """Test Azure provider."""
        assert CloudProvider.AZURE.value == "azure"

    def test_gcp_provider(self):
        """Test GCP provider."""
        assert CloudProvider.GCP.value == "gcp"

    def test_on_prem_provider(self):
        """Test on-premises provider."""
        assert CloudProvider.ON_PREM.value == "on_premises"

    def test_kubernetes_provider(self):
        """Test Kubernetes provider."""
        assert CloudProvider.KUBERNETES.value == "kubernetes"


class TestResourceType:
    """Tests for ResourceType enum."""

    def test_ec2_instance(self):
        """Test EC2 instance type."""
        assert ResourceType.EC2_INSTANCE.value == "ec2_instance"

    def test_lambda_function(self):
        """Test Lambda function type."""
        assert ResourceType.LAMBDA_FUNCTION.value == "lambda_function"

    def test_ecs_service(self):
        """Test ECS service type."""
        assert ResourceType.ECS_SERVICE.value == "ecs_service"

    def test_rds_instance(self):
        """Test RDS instance type."""
        assert ResourceType.RDS_INSTANCE.value == "rds_instance"

    def test_dynamodb_table(self):
        """Test DynamoDB table type."""
        assert ResourceType.DYNAMODB_TABLE.value == "dynamodb_table"

    def test_s3_bucket(self):
        """Test S3 bucket type."""
        assert ResourceType.S3_BUCKET.value == "s3_bucket"

    def test_vpc(self):
        """Test VPC type."""
        assert ResourceType.VPC.value == "vpc"

    def test_security_group(self):
        """Test security group type."""
        assert ResourceType.SECURITY_GROUP.value == "security_group"

    def test_kubernetes_pod(self):
        """Test Kubernetes pod type."""
        assert ResourceType.KUBERNETES_POD.value == "kubernetes_pod"

    def test_iam_role(self):
        """Test IAM role type."""
        assert ResourceType.IAM_ROLE.value == "iam_role"


class TestResourceStatus:
    """Tests for ResourceStatus enum."""

    def test_running_status(self):
        """Test running status."""
        assert ResourceStatus.RUNNING.value == "running"

    def test_stopped_status(self):
        """Test stopped status."""
        assert ResourceStatus.STOPPED.value == "stopped"

    def test_pending_status(self):
        """Test pending status."""
        assert ResourceStatus.PENDING.value == "pending"

    def test_degraded_status(self):
        """Test degraded status."""
        assert ResourceStatus.DEGRADED.value == "degraded"

    def test_unknown_status(self):
        """Test unknown status."""
        assert ResourceStatus.UNKNOWN.value == "unknown"

    def test_deleted_status(self):
        """Test deleted status."""
        assert ResourceStatus.DELETED.value == "deleted"


class TestRelationshipType:
    """Tests for RelationshipType enum."""

    def test_depends_on(self):
        """Test depends_on relationship."""
        assert RelationshipType.DEPENDS_ON.value == "depends_on"

    def test_connects_to(self):
        """Test connects_to relationship."""
        assert RelationshipType.CONNECTS_TO.value == "connects_to"

    def test_contains(self):
        """Test contains relationship."""
        assert RelationshipType.CONTAINS.value == "contains"

    def test_routes_to(self):
        """Test routes_to relationship."""
        assert RelationshipType.ROUTES_TO.value == "routes_to"

    def test_reads_from(self):
        """Test reads_from relationship."""
        assert RelationshipType.READS_FROM.value == "reads_from"

    def test_writes_to(self):
        """Test writes_to relationship."""
        assert RelationshipType.WRITES_TO.value == "writes_to"

    def test_triggers(self):
        """Test triggers relationship."""
        assert RelationshipType.TRIGGERS.value == "triggers"


class TestDriftType:
    """Tests for DriftType enum."""

    def test_added_drift(self):
        """Test added drift."""
        assert DriftType.ADDED.value == "added"

    def test_removed_drift(self):
        """Test removed drift."""
        assert DriftType.REMOVED.value == "removed"

    def test_modified_drift(self):
        """Test modified drift."""
        assert DriftType.MODIFIED.value == "modified"

    def test_unmanaged_drift(self):
        """Test unmanaged drift."""
        assert DriftType.UNMANAGED.value == "unmanaged"


class TestResourceTag:
    """Tests for ResourceTag dataclass."""

    def test_tag_creation(self):
        """Test tag creation."""
        tag = ResourceTag(key="Environment", value="production")
        assert tag.key == "Environment"
        assert tag.value == "production"

    def test_tag_different_values(self):
        """Test various tag values."""
        tags = [
            ResourceTag(key="Name", value="api-server"),
            ResourceTag(key="Team", value="platform"),
            ResourceTag(key="CostCenter", value="12345"),
        ]
        assert len(tags) == 3
        assert tags[0].key == "Name"


class TestResourceMetrics:
    """Tests for ResourceMetrics dataclass."""

    def test_default_metrics(self):
        """Test default metrics values."""
        metrics = ResourceMetrics()
        assert metrics.cpu_utilization is None
        assert metrics.memory_utilization is None
        assert metrics.network_in_bytes is None
        assert metrics.cost_hourly is None

    def test_metrics_with_values(self):
        """Test metrics with values."""
        metrics = ResourceMetrics(
            cpu_utilization=45.5,
            memory_utilization=60.2,
            request_count=1000,
            error_count=5,
            latency_p99_ms=250.0,
            cost_monthly=150.0,
        )
        assert metrics.cpu_utilization == 45.5
        assert metrics.memory_utilization == 60.2
        assert metrics.request_count == 1000
        assert metrics.cost_monthly == 150.0


class TestResource:
    """Tests for Resource dataclass."""

    def test_minimal_resource(self):
        """Test minimal resource creation."""
        resource = Resource(
            resource_id="i-12345",
            arn="arn:aws:ec2:us-east-1:123456789:instance/i-12345",
            name="api-server-1",
            resource_type=ResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123456789",
            status=ResourceStatus.RUNNING,
        )
        assert resource.resource_id == "i-12345"
        assert resource.resource_type == ResourceType.EC2_INSTANCE
        assert resource.status == ResourceStatus.RUNNING

    def test_resource_with_tags(self):
        """Test resource with tags."""
        tags = [
            ResourceTag(key="Environment", value="prod"),
            ResourceTag(key="Team", value="platform"),
        ]
        resource = Resource(
            resource_id="i-tagged",
            arn="arn:aws:ec2:us-east-1:123:instance/i-tagged",
            name="tagged-server",
            resource_type=ResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
            tags=tags,
        )
        assert len(resource.tags) == 2

    def test_resource_with_metrics(self):
        """Test resource with metrics."""
        metrics = ResourceMetrics(cpu_utilization=25.0)
        resource = Resource(
            resource_id="i-metrics",
            arn="arn:aws:ec2:us-east-1:123:instance/i-metrics",
            name="metrics-server",
            resource_type=ResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
            metrics=metrics,
        )
        assert resource.metrics.cpu_utilization == 25.0

    def test_resource_environment_classification(self):
        """Test resource environment classification."""
        resource = Resource(
            resource_id="i-prod",
            arn="arn:aws:ec2:us-east-1:123:instance/i-prod",
            name="prod-server",
            resource_type=ResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
            environment="prod",
            team="platform",
            application="api",
        )
        assert resource.environment == "prod"
        assert resource.team == "platform"


class TestResourceRelationship:
    """Tests for ResourceRelationship dataclass."""

    def test_relationship_creation(self):
        """Test relationship creation."""
        rel = ResourceRelationship(
            relationship_id="rel-123",
            source_id="i-12345",
            target_id="rds-12345",
            relationship_type=RelationshipType.CONNECTS_TO,
        )
        assert rel.relationship_id == "rel-123"
        assert rel.source_id == "i-12345"
        assert rel.target_id == "rds-12345"
        assert rel.relationship_type == RelationshipType.CONNECTS_TO

    def test_relationship_with_metadata(self):
        """Test relationship with metadata."""
        rel = ResourceRelationship(
            relationship_id="rel-meta",
            source_id="lambda-1",
            target_id="sqs-1",
            relationship_type=RelationshipType.WRITES_TO,
            metadata={"port": 443, "protocol": "https"},
        )
        assert rel.metadata["port"] == 443


class TestServiceComponent:
    """Tests for ServiceComponent dataclass."""

    def test_minimal_service(self):
        """Test minimal service creation."""
        service = ServiceComponent(
            service_id="svc-123",
            name="API Gateway",
            description="Main API gateway service",
            owner="platform-team",
            team="platform",
        )
        assert service.service_id == "svc-123"
        assert service.name == "API Gateway"
        assert service.resources == []

    def test_service_with_resources(self):
        """Test service with resources."""
        service = ServiceComponent(
            service_id="svc-full",
            name="User Service",
            description="User management",
            owner="user-team",
            team="core",
            resources=["i-12345", "rds-12345", "lambda-12345"],
        )
        assert len(service.resources) == 3

    def test_service_dependencies(self):
        """Test service dependencies."""
        service = ServiceComponent(
            service_id="svc-deps",
            name="Order Service",
            description="Order processing",
            owner="commerce-team",
            team="commerce",
            upstream_services=["svc-user", "svc-inventory"],
            downstream_services=["svc-notification"],
        )
        assert len(service.upstream_services) == 2
        assert len(service.downstream_services) == 1

    def test_service_metadata(self):
        """Test service metadata."""
        service = ServiceComponent(
            service_id="svc-meta",
            name="Critical Service",
            description="Critical service",
            owner="sre-team",
            team="sre",
            tier="critical",
            sla_target=99.99,
            oncall_team="sre-oncall",
            documentation_url="https://docs.example.com/svc",
            repository_url="https://github.com/example/svc",
        )
        assert service.tier == "critical"
        assert service.sla_target == 99.99


class TestTopologySnapshot:
    """Tests for TopologySnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test snapshot creation."""
        snapshot = TopologySnapshot(
            snapshot_id="snap-123",
            taken_at=datetime.now(timezone.utc),
            total_resources=100,
            total_relationships=250,
            total_services=10,
            resources_by_type={"ec2_instance": 50, "lambda_function": 30},
            resources_by_region={"us-east-1": 60, "us-west-2": 40},
            resources_by_environment={"prod": 70, "staging": 30},
            total_monthly_cost=5000.0,
        )
        assert snapshot.total_resources == 100
        assert snapshot.total_relationships == 250
        assert snapshot.resources_by_type["ec2_instance"] == 50


class TestDriftItem:
    """Tests for DriftItem dataclass."""

    def test_drift_item_creation(self):
        """Test drift item creation."""
        drift = DriftItem(
            drift_id="drift-123",
            resource_id="i-12345",
            drift_type=DriftType.MODIFIED,
            property_path="configuration.instance_type",
            expected_value="t3.medium",
            actual_value="t3.large",
        )
        assert drift.drift_id == "drift-123"
        assert drift.drift_type == DriftType.MODIFIED
        assert drift.expected_value == "t3.medium"
        assert drift.actual_value == "t3.large"

    def test_drift_item_severity(self):
        """Test drift item with severity."""
        drift = DriftItem(
            drift_id="drift-high",
            resource_id="sg-12345",
            drift_type=DriftType.MODIFIED,
            property_path="ingress_rules",
            expected_value=[],
            actual_value=[{"port": 22, "cidr": "0.0.0.0/0"}],
            severity="critical",
        )
        assert drift.severity == "critical"


class TestDriftReport:
    """Tests for DriftReport dataclass."""

    def test_drift_report_creation(self):
        """Test drift report creation."""
        report = DriftReport(
            report_id="report-123",
            baseline_snapshot_id="snap-baseline",
            current_snapshot_id="snap-current",
            drift_items=[],
            total_drifted_resources=5,
            by_drift_type={"modified": 3, "added": 2},
            by_severity={"high": 2, "medium": 3},
        )
        assert report.total_drifted_resources == 5
        assert report.by_drift_type["modified"] == 3


class TestImpactAnalysis:
    """Tests for ImpactAnalysis dataclass."""

    def test_impact_analysis_creation(self):
        """Test impact analysis creation."""
        analysis = ImpactAnalysis(
            analysis_id="impact-123",
            change_description="Update security group rules",
            target_resources=["sg-12345"],
            directly_affected=["sg-12345"],
            indirectly_affected=["i-12345", "i-67890"],
            affected_services=["svc-api"],
            risk_score=0.75,
            risk_factors=["Production environment", "Critical service"],
            recommendations=["Test in staging first"],
            requires_approval=True,
        )
        assert analysis.risk_score == 0.75
        assert analysis.requires_approval is True
        assert len(analysis.indirectly_affected) == 2


class TestCostBreakdown:
    """Tests for CostBreakdown dataclass."""

    def test_cost_breakdown_creation(self):
        """Test cost breakdown creation."""
        breakdown = CostBreakdown(
            breakdown_id="cost-123",
            period_start=datetime.now(timezone.utc) - timedelta(days=30),
            period_end=datetime.now(timezone.utc),
            total_cost=10000.0,
            by_service={"api": 3000, "database": 5000, "compute": 2000},
            by_resource_type={"ec2_instance": 5000, "rds_instance": 4000},
            by_environment={"prod": 8000, "staging": 2000},
            by_team={"platform": 6000, "core": 4000},
            by_region={"us-east-1": 7000, "us-west-2": 3000},
            cost_trend="stable",
            cost_anomalies=[],
        )
        assert breakdown.total_cost == 10000.0
        assert breakdown.cost_trend == "stable"


class TestResourceTopologyMapper:
    """Tests for ResourceTopologyMapper class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.mock_opensearch = MagicMock()
        self.mock_aws = MagicMock()
        self.mock_cost_explorer = MagicMock()

        self.mapper = ResourceTopologyMapper(
            neptune_client=self.mock_neptune,
            opensearch_client=self.mock_opensearch,
            aws_client=self.mock_aws,
            cost_explorer_client=self.mock_cost_explorer,
        )

    def test_init_clients(self):
        """Test initialization with clients."""
        assert self.mapper._neptune is not None
        assert self.mapper._opensearch is not None
        assert self.mapper._aws is not None

    def test_init_empty_storage(self):
        """Test initialization with empty storage."""
        assert self.mapper._resources == {}
        assert self.mapper._relationships == {}
        assert self.mapper._services == {}
        assert self.mapper._snapshots == {}

    def test_init_without_clients(self):
        """Test initialization without clients."""
        mapper = ResourceTopologyMapper()
        assert mapper._neptune is None
        assert mapper._opensearch is None

    @pytest.mark.asyncio
    async def test_discover_resources(self):
        """Test resource discovery."""
        # This would need more setup for a full test


class TestResourceTopologyMapperStorage:
    """Tests for in-memory storage operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = ResourceTopologyMapper()

    def test_add_resource(self):
        """Test adding resource to storage."""
        resource = Resource(
            resource_id="i-test",
            arn="arn:aws:ec2:us-east-1:123:instance/i-test",
            name="test-instance",
            resource_type=ResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            region="us-east-1",
            account_id="123",
            status=ResourceStatus.RUNNING,
        )
        self.mapper._resources[resource.resource_id] = resource
        assert "i-test" in self.mapper._resources

    def test_add_relationship(self):
        """Test adding relationship to storage."""
        rel = ResourceRelationship(
            relationship_id="rel-test",
            source_id="i-source",
            target_id="i-target",
            relationship_type=RelationshipType.DEPENDS_ON,
        )
        self.mapper._relationships[rel.relationship_id] = rel
        assert "rel-test" in self.mapper._relationships

    def test_add_service(self):
        """Test adding service to storage."""
        service = ServiceComponent(
            service_id="svc-test",
            name="Test Service",
            description="Test",
            owner="test-team",
            team="test",
        )
        self.mapper._services[service.service_id] = service
        assert "svc-test" in self.mapper._services


class TestResourceTypeCompleteness:
    """Tests for ResourceType completeness."""

    def test_compute_types_exist(self):
        """Test compute resource types exist."""
        assert ResourceType.EC2_INSTANCE
        assert ResourceType.LAMBDA_FUNCTION
        assert ResourceType.ECS_SERVICE
        assert ResourceType.EKS_DEPLOYMENT
        assert ResourceType.FARGATE_TASK

    def test_database_types_exist(self):
        """Test database resource types exist."""
        assert ResourceType.RDS_INSTANCE
        assert ResourceType.DYNAMODB_TABLE
        assert ResourceType.ELASTICACHE_CLUSTER
        assert ResourceType.NEPTUNE_CLUSTER
        assert ResourceType.OPENSEARCH_DOMAIN

    def test_storage_types_exist(self):
        """Test storage resource types exist."""
        assert ResourceType.S3_BUCKET
        assert ResourceType.EFS_FILESYSTEM
        assert ResourceType.EBS_VOLUME

    def test_networking_types_exist(self):
        """Test networking resource types exist."""
        assert ResourceType.VPC
        assert ResourceType.SUBNET
        assert ResourceType.SECURITY_GROUP
        assert ResourceType.LOAD_BALANCER
        assert ResourceType.API_GATEWAY

    def test_messaging_types_exist(self):
        """Test messaging resource types exist."""
        assert ResourceType.SQS_QUEUE
        assert ResourceType.SNS_TOPIC
        assert ResourceType.EVENTBRIDGE
        assert ResourceType.KINESIS_STREAM

    def test_security_types_exist(self):
        """Test security resource types exist."""
        assert ResourceType.IAM_ROLE
        assert ResourceType.KMS_KEY
        assert ResourceType.SECRETS_MANAGER

    def test_monitoring_types_exist(self):
        """Test monitoring resource types exist."""
        assert ResourceType.CLOUDWATCH_ALARM
        assert ResourceType.CLOUDWATCH_LOG_GROUP
