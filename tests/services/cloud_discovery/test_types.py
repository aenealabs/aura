"""
Tests for Cloud Discovery Type Definitions
==========================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Tests for type definitions: enums, dataclasses, and type conversion.
"""

import platform
from datetime import datetime, timezone

import pytest

# pytest-forked on macOS to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.cloud_discovery.types import (
    CloudProvider,
    CloudResource,
    CloudResourceType,
    CorrelationResult,
    DiscoveryResult,
    DiscoveryScope,
    IaCMapping,
    RelationshipType,
    ResourceRelationship,
)


class TestCloudProvider:
    """Tests for CloudProvider enum."""

    def test_aws_value(self) -> None:
        """Test AWS provider value."""
        assert CloudProvider.AWS.value == "aws"

    def test_azure_value(self) -> None:
        """Test Azure provider value."""
        assert CloudProvider.AZURE.value == "azure"

    def test_gcp_value(self) -> None:
        """Test GCP provider value."""
        assert CloudProvider.GCP.value == "gcp"

    def test_provider_from_string(self) -> None:
        """Test creating provider from string value."""
        assert CloudProvider("aws") == CloudProvider.AWS
        assert CloudProvider("azure") == CloudProvider.AZURE


class TestCloudResourceType:
    """Tests for CloudResourceType enum."""

    def test_compute_types(self) -> None:
        """Test compute resource types."""
        assert CloudResourceType.EC2_INSTANCE.value == "ec2_instance"
        assert CloudResourceType.ECS_CLUSTER.value == "ecs_cluster"
        assert CloudResourceType.EKS_CLUSTER.value == "eks_cluster"
        assert CloudResourceType.LAMBDA_FUNCTION.value == "lambda_function"

    def test_storage_types(self) -> None:
        """Test storage resource types."""
        assert CloudResourceType.S3_BUCKET.value == "s3_bucket"
        assert CloudResourceType.EBS_VOLUME.value == "ebs_volume"
        assert CloudResourceType.EFS_FILESYSTEM.value == "efs_filesystem"

    def test_database_types(self) -> None:
        """Test database resource types."""
        assert CloudResourceType.RDS_INSTANCE.value == "rds_instance"
        assert CloudResourceType.DYNAMODB_TABLE.value == "dynamodb_table"
        assert CloudResourceType.NEPTUNE_CLUSTER.value == "neptune_cluster"
        assert CloudResourceType.OPENSEARCH_DOMAIN.value == "opensearch_domain"

    def test_networking_types(self) -> None:
        """Test networking resource types."""
        assert CloudResourceType.VPC.value == "vpc"
        assert CloudResourceType.SUBNET.value == "subnet"
        assert CloudResourceType.SECURITY_GROUP.value == "security_group"
        assert CloudResourceType.ALB.value == "alb"

    def test_messaging_types(self) -> None:
        """Test messaging resource types."""
        assert CloudResourceType.SQS_QUEUE.value == "sqs_queue"
        assert CloudResourceType.SNS_TOPIC.value == "sns_topic"
        assert CloudResourceType.EVENTBRIDGE_BUS.value == "eventbridge_bus"

    def test_from_aws_type_ec2(self) -> None:
        """Test AWS type mapping for EC2."""
        result = CloudResourceType.from_aws_type("AWS::EC2::Instance")
        assert result == CloudResourceType.EC2_INSTANCE

    def test_from_aws_type_lambda(self) -> None:
        """Test AWS type mapping for Lambda."""
        result = CloudResourceType.from_aws_type("AWS::Lambda::Function")
        assert result == CloudResourceType.LAMBDA_FUNCTION

    def test_from_aws_type_s3(self) -> None:
        """Test AWS type mapping for S3."""
        result = CloudResourceType.from_aws_type("AWS::S3::Bucket")
        assert result == CloudResourceType.S3_BUCKET

    def test_from_aws_type_dynamodb(self) -> None:
        """Test AWS type mapping for DynamoDB."""
        result = CloudResourceType.from_aws_type("AWS::DynamoDB::Table")
        assert result == CloudResourceType.DYNAMODB_TABLE

    def test_from_aws_type_vpc(self) -> None:
        """Test AWS type mapping for VPC."""
        result = CloudResourceType.from_aws_type("AWS::EC2::VPC")
        assert result == CloudResourceType.VPC

    def test_from_aws_type_rds(self) -> None:
        """Test AWS type mapping for RDS."""
        result = CloudResourceType.from_aws_type("AWS::RDS::DBInstance")
        assert result == CloudResourceType.RDS_INSTANCE

    def test_from_aws_type_opensearch(self) -> None:
        """Test AWS type mapping for OpenSearch."""
        result = CloudResourceType.from_aws_type("AWS::OpenSearchService::Domain")
        assert result == CloudResourceType.OPENSEARCH_DOMAIN

    def test_from_aws_type_unknown(self) -> None:
        """Test AWS type mapping returns UNKNOWN for unrecognized types."""
        result = CloudResourceType.from_aws_type("AWS::UnknownService::Resource")
        assert result == CloudResourceType.UNKNOWN

    def test_from_aws_type_empty_string(self) -> None:
        """Test AWS type mapping with empty string."""
        result = CloudResourceType.from_aws_type("")
        assert result == CloudResourceType.UNKNOWN

    def test_from_aws_type_iam(self) -> None:
        """Test AWS type mapping for IAM resources."""
        assert (
            CloudResourceType.from_aws_type("AWS::IAM::Role")
            == CloudResourceType.IAM_ROLE
        )
        assert (
            CloudResourceType.from_aws_type("AWS::IAM::Policy")
            == CloudResourceType.IAM_POLICY
        )

    def test_from_aws_type_secrets(self) -> None:
        """Test AWS type mapping for secrets resources."""
        result = CloudResourceType.from_aws_type("AWS::SecretsManager::Secret")
        assert result == CloudResourceType.SECRETS_MANAGER_SECRET

    def test_from_aws_type_api_gateway(self) -> None:
        """Test AWS type mapping for API Gateway."""
        assert (
            CloudResourceType.from_aws_type("AWS::ApiGateway::RestApi")
            == CloudResourceType.API_GATEWAY_REST
        )
        assert (
            CloudResourceType.from_aws_type("AWS::ApiGatewayV2::Api")
            == CloudResourceType.API_GATEWAY_HTTP
        )


class TestDiscoveryScope:
    """Tests for DiscoveryScope enum."""

    def test_scope_values(self) -> None:
        """Test scope enum values."""
        assert DiscoveryScope.ACCOUNT.value == "account"
        assert DiscoveryScope.REGION.value == "region"
        assert DiscoveryScope.VPC.value == "vpc"
        assert DiscoveryScope.TAG.value == "tag"
        assert DiscoveryScope.SERVICE.value == "service"


class TestRelationshipType:
    """Tests for RelationshipType enum."""

    def test_network_relationships(self) -> None:
        """Test network relationship types."""
        assert RelationshipType.CONNECTS_TO.value == "connects_to"
        assert RelationshipType.ROUTES_TO.value == "routes_to"
        assert RelationshipType.EXPOSES.value == "exposes"

    def test_containment_relationships(self) -> None:
        """Test containment relationship types."""
        assert RelationshipType.CONTAINS.value == "contains"
        assert RelationshipType.DEPLOYED_IN.value == "deployed_in"
        assert RelationshipType.ATTACHED_TO.value == "attached_to"

    def test_data_flow_relationships(self) -> None:
        """Test data flow relationship types."""
        assert RelationshipType.READS_FROM.value == "reads_from"
        assert RelationshipType.WRITES_TO.value == "writes_to"
        assert RelationshipType.PUBLISHES_TO.value == "publishes_to"
        assert RelationshipType.SUBSCRIBES_TO.value == "subscribes_to"

    def test_security_relationships(self) -> None:
        """Test security relationship types."""
        assert RelationshipType.ALLOWS_ACCESS.value == "allows_access"
        assert RelationshipType.DENIES_ACCESS.value == "denies_access"
        assert RelationshipType.ASSUMES_ROLE.value == "assumes_role"


class TestCloudResource:
    """Tests for CloudResource dataclass."""

    def test_create_minimal_resource(self) -> None:
        """Test creating resource with minimal required fields."""
        resource = CloudResource(
            resource_id="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            resource_type=CloudResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            name="my-instance",
        )
        assert (
            resource.resource_id
            == "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
        )
        assert resource.resource_type == CloudResourceType.EC2_INSTANCE
        assert resource.provider == CloudProvider.AWS
        assert resource.name == "my-instance"
        assert resource.region == ""
        assert resource.account_id == ""
        assert resource.tags == {}
        assert resource.properties == {}
        assert resource.confidence == 1.0

    def test_create_full_resource(self) -> None:
        """Test creating resource with all fields."""
        resource = CloudResource(
            resource_id="arn:aws:s3:::my-bucket",
            resource_type=CloudResourceType.S3_BUCKET,
            provider=CloudProvider.AWS,
            name="my-bucket",
            region="us-east-1",
            account_id="123456789012",
            tags={"Environment": "dev", "Project": "aura"},
            properties={"versioning": True, "encryption": "AES256"},
            iac_logical_id="MyBucket",
            iac_source_file="deploy/cloudformation/storage.yaml",
            confidence=0.95,
            metadata={"discovered_via": "s3:ListBuckets"},
        )
        assert resource.region == "us-east-1"
        assert resource.account_id == "123456789012"
        assert resource.tags == {"Environment": "dev", "Project": "aura"}
        assert resource.properties["versioning"] is True
        assert resource.iac_logical_id == "MyBucket"
        assert resource.iac_source_file == "deploy/cloudformation/storage.yaml"
        assert resource.confidence == 0.95

    def test_confidence_validation_valid(self) -> None:
        """Test that valid confidence values are accepted."""
        resource_low = CloudResource(
            resource_id="test-id",
            resource_type=CloudResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            name="test",
            confidence=0.0,
        )
        assert resource_low.confidence == 0.0

        resource_high = CloudResource(
            resource_id="test-id",
            resource_type=CloudResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            name="test",
            confidence=1.0,
        )
        assert resource_high.confidence == 1.0

    def test_confidence_validation_invalid(self) -> None:
        """Test that invalid confidence values raise error."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            CloudResource(
                resource_id="test-id",
                resource_type=CloudResourceType.EC2_INSTANCE,
                provider=CloudProvider.AWS,
                name="test",
                confidence=1.5,
            )

        with pytest.raises(ValueError, match="Confidence must be between"):
            CloudResource(
                resource_id="test-id",
                resource_type=CloudResourceType.EC2_INSTANCE,
                provider=CloudProvider.AWS,
                name="test",
                confidence=-0.1,
            )

    def test_arn_property_aws(self) -> None:
        """Test ARN property returns resource_id for AWS."""
        resource = CloudResource(
            resource_id="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type=CloudResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            name="test",
        )
        assert resource.arn == "arn:aws:ec2:us-east-1:123456789012:instance/i-123"

    def test_arn_property_non_aws(self) -> None:
        """Test ARN property returns empty string for non-AWS."""
        resource = CloudResource(
            resource_id="/subscriptions/sub-id/resourceGroups/rg",
            resource_type=CloudResourceType.VPC,
            provider=CloudProvider.AZURE,
            name="test",
        )
        assert resource.arn == ""

    def test_is_correlated_property(self) -> None:
        """Test is_correlated property."""
        resource_uncorrelated = CloudResource(
            resource_id="test-id",
            resource_type=CloudResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            name="test",
        )
        assert resource_uncorrelated.is_correlated is False

        resource_correlated = CloudResource(
            resource_id="test-id",
            resource_type=CloudResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            name="test",
            iac_logical_id="MyInstance",
        )
        assert resource_correlated.is_correlated is True

    def test_discovered_at_default(self) -> None:
        """Test discovered_at defaults to current UTC time."""
        before = datetime.now(timezone.utc)
        resource = CloudResource(
            resource_id="test-id",
            resource_type=CloudResourceType.EC2_INSTANCE,
            provider=CloudProvider.AWS,
            name="test",
        )
        after = datetime.now(timezone.utc)
        assert before <= resource.discovered_at <= after


class TestResourceRelationship:
    """Tests for ResourceRelationship dataclass."""

    def test_create_relationship(self) -> None:
        """Test creating a relationship."""
        rel = ResourceRelationship(
            source_id="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            target_id="arn:aws:dynamodb:us-east-1:123456789012:table/my-table",
            relationship_type=RelationshipType.WRITES_TO,
        )
        assert rel.source_id == "arn:aws:lambda:us-east-1:123456789012:function:my-func"
        assert rel.target_id == "arn:aws:dynamodb:us-east-1:123456789012:table/my-table"
        assert rel.relationship_type == RelationshipType.WRITES_TO
        assert rel.confidence == 1.0

    def test_relationship_with_properties(self) -> None:
        """Test relationship with properties."""
        rel = ResourceRelationship(
            source_id="source-id",
            target_id="target-id",
            relationship_type=RelationshipType.ALLOWS_ACCESS,
            properties={"port": 443, "protocol": "HTTPS"},
            confidence=0.9,
        )
        assert rel.properties["port"] == 443
        assert rel.confidence == 0.9

    def test_relationship_confidence_validation(self) -> None:
        """Test relationship confidence validation."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            ResourceRelationship(
                source_id="source",
                target_id="target",
                relationship_type=RelationshipType.CONNECTS_TO,
                confidence=2.0,
            )


class TestDiscoveryResult:
    """Tests for DiscoveryResult dataclass."""

    def test_create_empty_result(self) -> None:
        """Test creating empty discovery result."""
        result = DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id="123456789012",
        )
        assert result.provider == CloudProvider.AWS
        assert result.account_id == "123456789012"
        assert result.resources == []
        assert result.relationships == []
        assert result.resource_count == 0
        assert result.relationship_count == 0

    def test_result_with_resources(self) -> None:
        """Test result with resources."""
        resources = [
            CloudResource(
                resource_id="id-1",
                resource_type=CloudResourceType.EC2_INSTANCE,
                provider=CloudProvider.AWS,
                name="instance-1",
            ),
            CloudResource(
                resource_id="id-2",
                resource_type=CloudResourceType.S3_BUCKET,
                provider=CloudProvider.AWS,
                name="bucket-1",
            ),
        ]
        result = DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            resources=resources,
        )
        assert result.resource_count == 2

    def test_get_resources_by_type(self) -> None:
        """Test filtering resources by type."""
        resources = [
            CloudResource(
                resource_id="id-1",
                resource_type=CloudResourceType.EC2_INSTANCE,
                provider=CloudProvider.AWS,
                name="instance-1",
            ),
            CloudResource(
                resource_id="id-2",
                resource_type=CloudResourceType.EC2_INSTANCE,
                provider=CloudProvider.AWS,
                name="instance-2",
            ),
            CloudResource(
                resource_id="id-3",
                resource_type=CloudResourceType.S3_BUCKET,
                provider=CloudProvider.AWS,
                name="bucket-1",
            ),
        ]
        result = DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            resources=resources,
        )

        ec2_resources = result.get_resources_by_type(CloudResourceType.EC2_INSTANCE)
        assert len(ec2_resources) == 2
        assert all(
            r.resource_type == CloudResourceType.EC2_INSTANCE for r in ec2_resources
        )

        s3_resources = result.get_resources_by_type(CloudResourceType.S3_BUCKET)
        assert len(s3_resources) == 1

        rds_resources = result.get_resources_by_type(CloudResourceType.RDS_INSTANCE)
        assert len(rds_resources) == 0


class TestIaCMapping:
    """Tests for IaCMapping dataclass."""

    def test_create_mapping(self) -> None:
        """Test creating IaC mapping."""
        mapping = IaCMapping(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="deploy/cloudformation/storage.yaml",
            source_line=42,
        )
        assert mapping.logical_id == "MyBucket"
        assert mapping.resource_type == "AWS::S3::Bucket"
        assert mapping.source_file == "deploy/cloudformation/storage.yaml"
        assert mapping.source_line == 42
        assert mapping.is_deployed is False

    def test_mapping_deployed(self) -> None:
        """Test mapping with deployed resource."""
        mapping = IaCMapping(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
            physical_resource_id="arn:aws:s3:::actual-bucket-name",
            stack_name="my-stack",
        )
        assert mapping.is_deployed is True
        assert mapping.physical_resource_id == "arn:aws:s3:::actual-bucket-name"

    def test_mapping_confidence_validation(self) -> None:
        """Test mapping confidence validation."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            IaCMapping(
                logical_id="MyResource",
                resource_type="AWS::EC2::Instance",
                source_file="template.yaml",
                confidence=-0.5,
            )


class TestCorrelationResult:
    """Tests for CorrelationResult dataclass."""

    def test_create_correlation_result(self) -> None:
        """Test creating correlation result."""
        result = CorrelationResult(
            repository_id="my-repo",
        )
        assert result.repository_id == "my-repo"
        assert result.iac_mappings == []
        assert result.unmatched_iac == []
        assert result.unmatched_resources == []
        assert result.correlation_rate == 0.0
        assert result.drift_count == 0

    def test_correlation_rate_calculation(self) -> None:
        """Test correlation rate calculation."""
        deployed_mapping = IaCMapping(
            logical_id="DeployedResource",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
            physical_resource_id="arn:aws:s3:::deployed-bucket",
        )
        unmatched_mapping = IaCMapping(
            logical_id="UnmatchedResource",
            resource_type="AWS::EC2::Instance",
            source_file="template.yaml",
        )

        result = CorrelationResult(
            repository_id="my-repo",
            iac_mappings=[deployed_mapping],
            unmatched_iac=[unmatched_mapping],
        )

        # 1 deployed / 2 total = 0.5
        assert result.correlation_rate == 0.5

    def test_correlation_rate_all_deployed(self) -> None:
        """Test correlation rate when all deployed."""
        mappings = [
            IaCMapping(
                logical_id=f"Resource{i}",
                resource_type="AWS::S3::Bucket",
                source_file="template.yaml",
                physical_resource_id=f"arn:aws:s3:::bucket-{i}",
            )
            for i in range(5)
        ]

        result = CorrelationResult(
            repository_id="my-repo",
            iac_mappings=mappings,
        )
        assert result.correlation_rate == 1.0

    def test_drift_count(self) -> None:
        """Test drift count."""
        unmatched = [
            CloudResource(
                resource_id=f"orphan-{i}",
                resource_type=CloudResourceType.EC2_INSTANCE,
                provider=CloudProvider.AWS,
                name=f"orphan-instance-{i}",
            )
            for i in range(3)
        ]

        result = CorrelationResult(
            repository_id="my-repo",
            unmatched_resources=unmatched,
        )
        assert result.drift_count == 3

    def test_correlation_confidence_validation(self) -> None:
        """Test correlation confidence validation."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            CorrelationResult(
                repository_id="my-repo",
                correlation_confidence=1.5,
            )
