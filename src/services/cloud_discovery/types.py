"""
Cloud Discovery Type Definitions
=================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Type definitions for cloud resource discovery and IaC correlation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CloudProvider(Enum):
    """Supported cloud providers for resource discovery."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"  # Future support


class CloudResourceType(Enum):
    """Types of cloud resources that can be discovered.

    Categories:
    - Compute: EC2, ECS, EKS, Lambda
    - Storage: S3, EBS, EFS
    - Database: RDS, DynamoDB, Neptune, OpenSearch
    - Networking: VPC, Subnets, Security Groups, Load Balancers
    - Messaging: SQS, SNS, EventBridge
    - API: API Gateway, AppSync
    """

    # Compute
    EC2_INSTANCE = "ec2_instance"
    ECS_CLUSTER = "ecs_cluster"
    ECS_SERVICE = "ecs_service"
    EKS_CLUSTER = "eks_cluster"
    EKS_NODEGROUP = "eks_nodegroup"
    LAMBDA_FUNCTION = "lambda_function"

    # Storage
    S3_BUCKET = "s3_bucket"
    EBS_VOLUME = "ebs_volume"
    EFS_FILESYSTEM = "efs_filesystem"

    # Database
    RDS_INSTANCE = "rds_instance"
    RDS_CLUSTER = "rds_cluster"
    DYNAMODB_TABLE = "dynamodb_table"
    NEPTUNE_CLUSTER = "neptune_cluster"
    OPENSEARCH_DOMAIN = "opensearch_domain"
    ELASTICACHE_CLUSTER = "elasticache_cluster"

    # Networking
    VPC = "vpc"
    SUBNET = "subnet"
    SECURITY_GROUP = "security_group"
    ALB = "alb"
    NLB = "nlb"
    CLOUDFRONT_DISTRIBUTION = "cloudfront_distribution"
    ROUTE53_HOSTEDZONE = "route53_hostedzone"

    # Messaging
    SQS_QUEUE = "sqs_queue"
    SNS_TOPIC = "sns_topic"
    EVENTBRIDGE_BUS = "eventbridge_bus"
    KINESIS_STREAM = "kinesis_stream"

    # API
    API_GATEWAY_REST = "api_gateway_rest"
    API_GATEWAY_HTTP = "api_gateway_http"
    APPSYNC_API = "appsync_api"

    # IAM
    IAM_ROLE = "iam_role"
    IAM_POLICY = "iam_policy"

    # Secrets/Config
    SECRETS_MANAGER_SECRET = "secrets_manager_secret"
    SSM_PARAMETER = "ssm_parameter"

    # Unknown/Other
    UNKNOWN = "unknown"

    @classmethod
    def from_aws_type(cls, aws_type: str) -> "CloudResourceType":
        """Convert AWS resource type string to CloudResourceType.

        Args:
            aws_type: AWS resource type (e.g., 'AWS::EC2::Instance')

        Returns:
            Corresponding CloudResourceType
        """
        mapping = {
            "AWS::EC2::Instance": cls.EC2_INSTANCE,
            "AWS::ECS::Cluster": cls.ECS_CLUSTER,
            "AWS::ECS::Service": cls.ECS_SERVICE,
            "AWS::EKS::Cluster": cls.EKS_CLUSTER,
            "AWS::EKS::Nodegroup": cls.EKS_NODEGROUP,
            "AWS::Lambda::Function": cls.LAMBDA_FUNCTION,
            "AWS::S3::Bucket": cls.S3_BUCKET,
            "AWS::EC2::Volume": cls.EBS_VOLUME,
            "AWS::EFS::FileSystem": cls.EFS_FILESYSTEM,
            "AWS::RDS::DBInstance": cls.RDS_INSTANCE,
            "AWS::RDS::DBCluster": cls.RDS_CLUSTER,
            "AWS::DynamoDB::Table": cls.DYNAMODB_TABLE,
            "AWS::Neptune::DBCluster": cls.NEPTUNE_CLUSTER,
            "AWS::OpenSearchService::Domain": cls.OPENSEARCH_DOMAIN,
            "AWS::ElastiCache::CacheCluster": cls.ELASTICACHE_CLUSTER,
            "AWS::EC2::VPC": cls.VPC,
            "AWS::EC2::Subnet": cls.SUBNET,
            "AWS::EC2::SecurityGroup": cls.SECURITY_GROUP,
            "AWS::ElasticLoadBalancingV2::LoadBalancer": cls.ALB,
            "AWS::SQS::Queue": cls.SQS_QUEUE,
            "AWS::SNS::Topic": cls.SNS_TOPIC,
            "AWS::Events::EventBus": cls.EVENTBRIDGE_BUS,
            "AWS::Kinesis::Stream": cls.KINESIS_STREAM,
            "AWS::ApiGateway::RestApi": cls.API_GATEWAY_REST,
            "AWS::ApiGatewayV2::Api": cls.API_GATEWAY_HTTP,
            "AWS::AppSync::GraphQLApi": cls.APPSYNC_API,
            "AWS::IAM::Role": cls.IAM_ROLE,
            "AWS::IAM::Policy": cls.IAM_POLICY,
            "AWS::SecretsManager::Secret": cls.SECRETS_MANAGER_SECRET,
            "AWS::SSM::Parameter": cls.SSM_PARAMETER,
            "AWS::CloudFront::Distribution": cls.CLOUDFRONT_DISTRIBUTION,
            "AWS::Route53::HostedZone": cls.ROUTE53_HOSTEDZONE,
        }
        return mapping.get(aws_type, cls.UNKNOWN)


class DiscoveryScope(Enum):
    """Scope of cloud resource discovery."""

    ACCOUNT = "account"  # Entire AWS account
    REGION = "region"  # Single region
    VPC = "vpc"  # Single VPC
    TAG = "tag"  # Resources matching specific tags
    SERVICE = "service"  # Specific AWS service


class RelationshipType(Enum):
    """Types of relationships between cloud resources."""

    # Network connectivity
    CONNECTS_TO = "connects_to"  # Network connection
    ROUTES_TO = "routes_to"  # Network routing
    EXPOSES = "exposes"  # Publicly exposes

    # Containment
    CONTAINS = "contains"  # Parent contains child
    DEPLOYED_IN = "deployed_in"  # Resource deployed in environment
    ATTACHED_TO = "attached_to"  # Resource attached to another

    # Data flow
    READS_FROM = "reads_from"  # Reads data from
    WRITES_TO = "writes_to"  # Writes data to
    PUBLISHES_TO = "publishes_to"  # Publishes messages to
    SUBSCRIBES_TO = "subscribes_to"  # Subscribes to messages from

    # Security
    ALLOWS_ACCESS = "allows_access"  # Security rule allows access
    DENIES_ACCESS = "denies_access"  # Security rule denies access
    ASSUMES_ROLE = "assumes_role"  # IAM role assumption

    # Configuration
    CONFIGURES = "configures"  # Configuration relationship
    REFERENCES = "references"  # References another resource


@dataclass
class CloudResource:
    """Represents a discovered cloud resource.

    Attributes:
        resource_id: Unique identifier (ARN for AWS)
        resource_type: Type of cloud resource
        provider: Cloud provider
        name: Human-readable name
        region: Cloud region
        account_id: Cloud account ID
        tags: Resource tags
        properties: Provider-specific properties
        iac_logical_id: Logical ID from IaC template (if correlated)
        iac_source_file: Path to IaC template file
        confidence: Confidence in resource identification
        discovered_at: Timestamp of discovery
        metadata: Additional metadata
    """

    resource_id: str
    resource_type: CloudResourceType
    provider: CloudProvider
    name: str
    region: str = ""
    account_id: str = ""
    tags: dict[str, str] = field(default_factory=dict)
    properties: dict[str, Any] = field(default_factory=dict)
    iac_logical_id: str | None = None
    iac_source_file: str | None = None
    confidence: float = 1.0
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    @property
    def arn(self) -> str:
        """Get the ARN for AWS resources."""
        if self.provider == CloudProvider.AWS:
            return self.resource_id
        return ""

    @property
    def is_correlated(self) -> bool:
        """Check if resource is correlated with IaC."""
        return self.iac_logical_id is not None


@dataclass
class ResourceRelationship:
    """Represents a relationship between cloud resources.

    Attributes:
        source_id: Source resource ID
        target_id: Target resource ID
        relationship_type: Type of relationship
        properties: Relationship-specific properties
        confidence: Confidence in the relationship
        metadata: Additional metadata
    """

    source_id: str
    target_id: str
    relationship_type: RelationshipType
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass
class DiscoveryResult:
    """Result of cloud resource discovery.

    Attributes:
        provider: Cloud provider that was discovered
        account_id: Account that was discovered
        regions: Regions that were discovered
        resources: Discovered resources
        relationships: Discovered relationships
        discovered_at: Timestamp of discovery
        discovery_time_ms: Time taken for discovery
        warnings: Warnings during discovery
        errors: Errors during discovery
        metadata: Additional metadata
    """

    provider: CloudProvider
    account_id: str
    regions: list[str] = field(default_factory=list)
    resources: list[CloudResource] = field(default_factory=list)
    relationships: list[ResourceRelationship] = field(default_factory=list)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    discovery_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def resource_count(self) -> int:
        """Get total number of discovered resources."""
        return len(self.resources)

    @property
    def relationship_count(self) -> int:
        """Get total number of discovered relationships."""
        return len(self.relationships)

    def get_resources_by_type(
        self, resource_type: CloudResourceType
    ) -> list[CloudResource]:
        """Get resources filtered by type.

        Args:
            resource_type: Type of resources to filter

        Returns:
            List of resources matching the type
        """
        return [r for r in self.resources if r.resource_type == resource_type]


@dataclass
class IaCMapping:
    """Mapping between IaC definition and cloud resource.

    Attributes:
        logical_id: Logical ID from IaC template
        resource_type: CloudFormation/Terraform resource type string
        source_file: Path to IaC template file
        source_line: Line number in source file
        physical_resource_id: Actual deployed resource ID (ARN)
        stack_name: CloudFormation stack name (if applicable)
        confidence: Confidence in the mapping
        metadata: Additional metadata
    """

    logical_id: str
    resource_type: str
    source_file: str
    source_line: int = 0
    physical_resource_id: str | None = None
    stack_name: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

    @property
    def is_deployed(self) -> bool:
        """Check if the IaC resource has been deployed."""
        return self.physical_resource_id is not None


@dataclass
class CorrelationResult:
    """Result of correlating IaC with discovered resources.

    Attributes:
        repository_id: Repository containing IaC
        iac_mappings: IaC to resource mappings
        unmatched_iac: IaC resources without deployed match
        unmatched_resources: Deployed resources without IaC match
        correlation_confidence: Overall correlation confidence
        correlated_at: Timestamp of correlation
        metadata: Additional metadata
    """

    repository_id: str
    iac_mappings: list[IaCMapping] = field(default_factory=list)
    unmatched_iac: list[IaCMapping] = field(default_factory=list)
    unmatched_resources: list[CloudResource] = field(default_factory=list)
    correlation_confidence: float = 1.0
    correlated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence is in valid range."""
        if not 0.0 <= self.correlation_confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.correlation_confidence}"
            )

    @property
    def correlation_rate(self) -> float:
        """Calculate the correlation rate (matched / total IaC resources).

        Returns:
            Correlation rate between 0.0 and 1.0
        """
        total = len(self.iac_mappings) + len(self.unmatched_iac)
        if total == 0:
            return 0.0
        matched = sum(1 for m in self.iac_mappings if m.is_deployed)
        return matched / total

    @property
    def drift_count(self) -> int:
        """Count of resources that exist but aren't in IaC."""
        return len(self.unmatched_resources)
