"""
Resource Topology Mapper Service - AWS DevOps Agent Parity

Implements comprehensive infrastructure topology mapping:
- Multi-cloud resource discovery (AWS, Azure, GCP)
- Service dependency graph construction
- Real-time topology updates
- Impact analysis for changes
- Drift detection
- Cost attribution by topology

Reference: ADR-030 Section 5.3 DevOps Agent Components
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class CloudProvider(str, Enum):
    """Cloud providers."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    ON_PREM = "on_premises"
    KUBERNETES = "kubernetes"


class ResourceType(str, Enum):
    """Types of cloud resources."""

    # Compute
    EC2_INSTANCE = "ec2_instance"
    LAMBDA_FUNCTION = "lambda_function"
    ECS_SERVICE = "ecs_service"
    EKS_DEPLOYMENT = "eks_deployment"
    FARGATE_TASK = "fargate_task"

    # Containers
    KUBERNETES_POD = "kubernetes_pod"
    KUBERNETES_SERVICE = "kubernetes_service"
    KUBERNETES_DEPLOYMENT = "kubernetes_deployment"
    KUBERNETES_INGRESS = "kubernetes_ingress"

    # Databases
    RDS_INSTANCE = "rds_instance"
    DYNAMODB_TABLE = "dynamodb_table"
    ELASTICACHE_CLUSTER = "elasticache_cluster"
    NEPTUNE_CLUSTER = "neptune_cluster"
    OPENSEARCH_DOMAIN = "opensearch_domain"

    # Storage
    S3_BUCKET = "s3_bucket"
    EFS_FILESYSTEM = "efs_filesystem"
    EBS_VOLUME = "ebs_volume"

    # Networking
    VPC = "vpc"
    SUBNET = "subnet"
    SECURITY_GROUP = "security_group"
    LOAD_BALANCER = "load_balancer"
    API_GATEWAY = "api_gateway"
    CLOUDFRONT = "cloudfront"
    ROUTE53 = "route53"

    # Messaging
    SQS_QUEUE = "sqs_queue"
    SNS_TOPIC = "sns_topic"
    EVENTBRIDGE = "eventbridge"
    KINESIS_STREAM = "kinesis_stream"

    # Serverless
    STEP_FUNCTION = "step_function"

    # Security
    IAM_ROLE = "iam_role"
    KMS_KEY = "kms_key"
    SECRETS_MANAGER = "secrets_manager"

    # Monitoring
    CLOUDWATCH_ALARM = "cloudwatch_alarm"
    CLOUDWATCH_LOG_GROUP = "cloudwatch_log_group"


class ResourceStatus(str, Enum):
    """Status of a resource."""

    RUNNING = "running"
    STOPPED = "stopped"
    PENDING = "pending"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    DELETED = "deleted"


class RelationshipType(str, Enum):
    """Types of relationships between resources."""

    DEPENDS_ON = "depends_on"
    CONNECTS_TO = "connects_to"
    CONTAINS = "contains"
    ROUTES_TO = "routes_to"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"
    TRIGGERS = "triggers"
    AUTHENTICATES_WITH = "authenticates_with"
    ENCRYPTS_WITH = "encrypts_with"
    MONITORS = "monitors"
    LOGS_TO = "logs_to"


class DriftType(str, Enum):
    """Types of configuration drift."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNMANAGED = "unmanaged"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ResourceTag:
    """A resource tag."""

    key: str
    value: str


@dataclass
class ResourceMetrics:
    """Metrics for a resource."""

    cpu_utilization: float | None = None
    memory_utilization: float | None = None
    network_in_bytes: float | None = None
    network_out_bytes: float | None = None
    request_count: int | None = None
    error_count: int | None = None
    latency_p50_ms: float | None = None
    latency_p99_ms: float | None = None
    cost_hourly: float | None = None
    cost_monthly: float | None = None


@dataclass
class Resource:
    """A cloud resource."""

    resource_id: str
    arn: str
    name: str
    resource_type: ResourceType
    provider: CloudProvider
    region: str
    account_id: str
    status: ResourceStatus

    # Metadata
    tags: list[ResourceTag] = field(default_factory=list)
    created_at: datetime | None = None
    last_modified: datetime | None = None

    # Configuration
    configuration: dict[str, Any] = field(default_factory=dict)

    # Metrics
    metrics: ResourceMetrics = field(default_factory=ResourceMetrics)

    # Environment classification
    environment: str = ""  # prod, staging, dev
    team: str = ""
    application: str = ""

    # Cost
    cost_center: str = ""
    monthly_cost: float = 0.0

    # Discovery
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceRelationship:
    """A relationship between two resources."""

    relationship_id: str
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    metadata: dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ServiceComponent:
    """A logical service composed of resources."""

    service_id: str
    name: str
    description: str
    owner: str
    team: str

    # Resources that make up this service
    resources: list[str] = field(default_factory=list)

    # Service-level metadata
    tier: str = "standard"  # critical, standard, non-critical
    sla_target: float = 99.9
    oncall_team: str = ""
    documentation_url: str = ""
    repository_url: str = ""

    # Endpoints
    endpoints: list[str] = field(default_factory=list)

    # Dependencies (other service IDs)
    upstream_services: list[str] = field(default_factory=list)
    downstream_services: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TopologySnapshot:
    """A point-in-time snapshot of the topology."""

    snapshot_id: str
    taken_at: datetime
    total_resources: int
    total_relationships: int
    total_services: int
    resources_by_type: dict[str, int]
    resources_by_region: dict[str, int]
    resources_by_environment: dict[str, int]
    total_monthly_cost: float


@dataclass
class DriftItem:
    """A single drift item."""

    drift_id: str
    resource_id: str
    drift_type: DriftType
    property_path: str
    expected_value: Any
    actual_value: Any
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    severity: str = "medium"  # low, medium, high, critical


@dataclass
class DriftReport:
    """Report of configuration drift."""

    report_id: str
    baseline_snapshot_id: str
    current_snapshot_id: str
    drift_items: list[DriftItem]
    total_drifted_resources: int
    by_drift_type: dict[str, int]
    by_severity: dict[str, int]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ImpactAnalysis:
    """Analysis of impact from a change."""

    analysis_id: str
    change_description: str
    target_resources: list[str]

    # Impact assessment
    directly_affected: list[str]
    indirectly_affected: list[str]
    affected_services: list[str]

    # Risk assessment
    risk_score: float
    risk_factors: list[str]

    # Recommendations
    recommendations: list[str]
    requires_approval: bool

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CostBreakdown:
    """Cost breakdown by topology element."""

    breakdown_id: str
    period_start: datetime
    period_end: datetime

    total_cost: float
    by_service: dict[str, float]
    by_resource_type: dict[str, float]
    by_environment: dict[str, float]
    by_team: dict[str, float]
    by_region: dict[str, float]

    # Trends
    cost_trend: str  # increasing, stable, decreasing
    cost_anomalies: list[dict[str, Any]]


# =============================================================================
# Resource Topology Mapper Service
# =============================================================================


class ResourceTopologyMapper:
    """
    Comprehensive infrastructure topology mapping service.

    Provides:
    - Multi-cloud resource discovery
    - Service dependency graph
    - Real-time topology updates
    - Impact analysis
    - Drift detection
    - Cost attribution
    """

    def __init__(
        self,
        neptune_client: Any = None,
        opensearch_client: Any = None,
        aws_client: Any = None,
        cost_explorer_client: Any = None,
    ):
        self._neptune = neptune_client
        self._opensearch = opensearch_client
        self._aws = aws_client
        self._cost_explorer = cost_explorer_client

        # In-memory storage (production uses Neptune graph)
        self._resources: dict[str, Resource] = {}
        self._relationships: dict[str, ResourceRelationship] = {}
        self._services: dict[str, ServiceComponent] = {}
        self._snapshots: dict[str, TopologySnapshot] = {}

        self._logger = logger.bind(service="resource_topology_mapper")

    # =========================================================================
    # Resource Discovery
    # =========================================================================

    async def discover_resources(
        self,
        account_id: str,
        regions: list[str] | None = None,
        resource_types: list[ResourceType] | None = None,
    ) -> list[Resource]:
        """
        Discover resources from cloud accounts.

        Args:
            account_id: AWS account ID
            regions: Regions to scan (defaults to all)
            resource_types: Resource types to discover (defaults to all)

        Returns:
            List of discovered resources
        """
        self._logger.info(
            "Starting resource discovery",
            account_id=account_id,
            regions=regions,
            resource_types=resource_types,
        )

        discovered = []

        # Default regions if not specified
        if not regions:
            regions = ["us-east-1", "us-west-2", "eu-west-1"]

        # Default resource types if not specified
        if not resource_types:
            resource_types = list(ResourceType)

        # Discover resources by type
        for region in regions:
            for resource_type in resource_types:
                try:
                    resources = await self._discover_by_type(
                        account_id, region, resource_type
                    )
                    discovered.extend(resources)
                except Exception as e:
                    self._logger.warning(
                        "Failed to discover resources",
                        region=region,
                        resource_type=resource_type.value,
                        error=str(e),
                    )

        # Store discovered resources
        for resource in discovered:
            self._resources[resource.resource_id] = resource

        # Discover relationships
        await self._discover_relationships(discovered)

        self._logger.info(
            "Resource discovery completed",
            total_discovered=len(discovered),
            relationships=len(self._relationships),
        )

        return discovered

    async def _discover_by_type(
        self, account_id: str, region: str, resource_type: ResourceType
    ) -> list[Resource]:
        """Discover resources of a specific type."""
        # In production, this would call AWS APIs
        # For now, return simulated resources

        resources = []

        # Simulate discovery based on type
        if resource_type == ResourceType.EC2_INSTANCE:
            resources = self._simulate_ec2_discovery(account_id, region)
        elif resource_type == ResourceType.RDS_INSTANCE:
            resources = self._simulate_rds_discovery(account_id, region)
        elif resource_type == ResourceType.LAMBDA_FUNCTION:
            resources = self._simulate_lambda_discovery(account_id, region)
        elif resource_type == ResourceType.S3_BUCKET:
            resources = self._simulate_s3_discovery(account_id, region)
        elif resource_type == ResourceType.EKS_DEPLOYMENT:
            resources = self._simulate_eks_discovery(account_id, region)

        return resources

    def _simulate_ec2_discovery(self, account_id: str, region: str) -> list[Resource]:
        """Simulate EC2 instance discovery."""
        instances = []
        for i in range(3):
            instance = Resource(
                resource_id=f"i-{uuid.uuid4().hex[:8]}",
                arn=f"arn:aws:ec2:{region}:{account_id}:instance/i-{uuid.uuid4().hex[:8]}",
                name=f"aura-api-{i+1}",
                resource_type=ResourceType.EC2_INSTANCE,
                provider=CloudProvider.AWS,
                region=region,
                account_id=account_id,
                status=ResourceStatus.RUNNING,
                tags=[
                    ResourceTag(key="Environment", value="production"),
                    ResourceTag(key="Application", value="aura"),
                    ResourceTag(key="Team", value="platform"),
                ],
                configuration={
                    "instance_type": "m5.xlarge",
                    "ami_id": "ami-12345678",
                    "vpc_id": f"vpc-{uuid.uuid4().hex[:8]}",
                    "subnet_id": f"subnet-{uuid.uuid4().hex[:8]}",
                },
                environment="production",
                team="platform",
                application="aura",
                monthly_cost=150.0,
            )
            instances.append(instance)
        return instances

    def _simulate_rds_discovery(self, account_id: str, region: str) -> list[Resource]:
        """Simulate RDS instance discovery."""
        return [
            Resource(
                resource_id=f"aura-db-{region}",
                arn=f"arn:aws:rds:{region}:{account_id}:db:aura-db",
                name="aura-db",
                resource_type=ResourceType.RDS_INSTANCE,
                provider=CloudProvider.AWS,
                region=region,
                account_id=account_id,
                status=ResourceStatus.RUNNING,
                tags=[
                    ResourceTag(key="Environment", value="production"),
                    ResourceTag(key="Application", value="aura"),
                ],
                configuration={
                    "engine": "postgres",
                    "engine_version": "15.4",
                    "instance_class": "db.r5.xlarge",
                    "multi_az": True,
                    "storage_type": "gp3",
                    "allocated_storage": 500,
                },
                environment="production",
                team="data",
                application="aura",
                monthly_cost=800.0,
            )
        ]

    def _simulate_lambda_discovery(
        self, account_id: str, region: str
    ) -> list[Resource]:
        """Simulate Lambda function discovery."""
        functions = []
        function_names = ["aura-processor", "aura-webhook", "aura-scheduler"]
        for name in function_names:
            functions.append(
                Resource(
                    resource_id=f"{name}-{region}",
                    arn=f"arn:aws:lambda:{region}:{account_id}:function:{name}",
                    name=name,
                    resource_type=ResourceType.LAMBDA_FUNCTION,
                    provider=CloudProvider.AWS,
                    region=region,
                    account_id=account_id,
                    status=ResourceStatus.RUNNING,
                    configuration={
                        "runtime": "python3.11",
                        "memory": 1024,
                        "timeout": 30,
                        "handler": "main.handler",
                    },
                    environment="production",
                    team="platform",
                    application="aura",
                    monthly_cost=25.0,
                )
            )
        return functions

    def _simulate_s3_discovery(self, account_id: str, region: str) -> list[Resource]:
        """Simulate S3 bucket discovery."""
        return [
            Resource(
                resource_id=f"aura-data-{account_id}",
                arn=f"arn:aws:s3:::aura-data-{account_id}",
                name=f"aura-data-{account_id}",
                resource_type=ResourceType.S3_BUCKET,
                provider=CloudProvider.AWS,
                region=region,
                account_id=account_id,
                status=ResourceStatus.RUNNING,
                configuration={
                    "versioning": True,
                    "encryption": "AES256",
                    "public_access_blocked": True,
                },
                environment="production",
                team="data",
                application="aura",
                monthly_cost=50.0,
            )
        ]

    def _simulate_eks_discovery(self, account_id: str, region: str) -> list[Resource]:
        """Simulate EKS deployment discovery."""
        deployments = []
        services = ["api-gateway", "auth-service", "agent-runtime"]
        for service in services:
            deployments.append(
                Resource(
                    resource_id=f"{service}-deployment",
                    arn=f"arn:aws:eks:{region}:{account_id}:deployment/{service}",
                    name=service,
                    resource_type=ResourceType.EKS_DEPLOYMENT,
                    provider=CloudProvider.AWS,
                    region=region,
                    account_id=account_id,
                    status=ResourceStatus.RUNNING,
                    configuration={
                        "replicas": 3,
                        "image": f"aura/{service}:latest",
                        "namespace": "aura-prod",
                    },
                    environment="production",
                    team="platform",
                    application="aura",
                    monthly_cost=200.0,
                )
            )
        return deployments

    async def _discover_relationships(self, resources: list[Resource]) -> None:
        """Discover relationships between resources."""
        # Build relationships based on resource types and configurations

        _resource_map = {r.resource_id: r for r in resources}  # noqa: F841

        for resource in resources:
            # EC2 -> RDS relationships
            if resource.resource_type == ResourceType.EC2_INSTANCE:
                for other in resources:
                    if other.resource_type == ResourceType.RDS_INSTANCE:
                        if other.environment == resource.environment:
                            rel = ResourceRelationship(
                                relationship_id=str(uuid.uuid4()),
                                source_id=resource.resource_id,
                                target_id=other.resource_id,
                                relationship_type=RelationshipType.CONNECTS_TO,
                                metadata={"protocol": "tcp", "port": 5432},
                            )
                            self._relationships[rel.relationship_id] = rel

            # Lambda -> S3 relationships
            if resource.resource_type == ResourceType.LAMBDA_FUNCTION:
                for other in resources:
                    if other.resource_type == ResourceType.S3_BUCKET:
                        if other.application == resource.application:
                            rel = ResourceRelationship(
                                relationship_id=str(uuid.uuid4()),
                                source_id=resource.resource_id,
                                target_id=other.resource_id,
                                relationship_type=RelationshipType.READS_FROM,
                                metadata={"access_type": "read_write"},
                            )
                            self._relationships[rel.relationship_id] = rel

            # EKS -> RDS relationships
            if resource.resource_type == ResourceType.EKS_DEPLOYMENT:
                for other in resources:
                    if other.resource_type == ResourceType.RDS_INSTANCE:
                        if other.environment == resource.environment:
                            rel = ResourceRelationship(
                                relationship_id=str(uuid.uuid4()),
                                source_id=resource.resource_id,
                                target_id=other.resource_id,
                                relationship_type=RelationshipType.DEPENDS_ON,
                                metadata={"protocol": "tcp", "port": 5432},
                            )
                            self._relationships[rel.relationship_id] = rel

    # =========================================================================
    # Service Management
    # =========================================================================

    def create_service(
        self,
        name: str,
        description: str,
        owner: str,
        team: str,
        resource_ids: list[str],
        tier: str = "standard",
    ) -> ServiceComponent:
        """
        Create a logical service from resources.

        Args:
            name: Service name
            description: Service description
            owner: Service owner
            team: Owning team
            resource_ids: Resource IDs that comprise this service
            tier: Service tier (critical, standard, non-critical)

        Returns:
            Created service component
        """
        service = ServiceComponent(
            service_id=str(uuid.uuid4()),
            name=name,
            description=description,
            owner=owner,
            team=team,
            resources=resource_ids,
            tier=tier,
        )

        self._services[service.service_id] = service

        # Infer dependencies from resource relationships
        self._infer_service_dependencies(service)

        self._logger.info(
            "Service created",
            service_id=service.service_id,
            name=name,
            resources=len(resource_ids),
        )

        return service

    def _infer_service_dependencies(self, service: ServiceComponent) -> None:
        """Infer service dependencies from resource relationships."""
        service_resources = set(service.resources)

        for rel in self._relationships.values():
            if (
                rel.source_id in service_resources
                and rel.target_id not in service_resources
            ):
                # Find the service that owns the target resource
                for other_service in self._services.values():
                    if rel.target_id in other_service.resources:
                        if other_service.service_id not in service.downstream_services:
                            service.downstream_services.append(other_service.service_id)
                        if service.service_id not in other_service.upstream_services:
                            other_service.upstream_services.append(service.service_id)

    def get_service(self, service_id: str) -> ServiceComponent | None:
        """Get a service by ID."""
        return self._services.get(service_id)

    def get_service_by_name(self, name: str) -> ServiceComponent | None:
        """Get a service by name."""
        for service in self._services.values():
            if service.name == name:
                return service
        return None

    # =========================================================================
    # Topology Queries
    # =========================================================================

    async def get_resource(self, resource_id: str) -> Resource | None:
        """Get a resource by ID."""
        return self._resources.get(resource_id)

    async def get_resources_by_type(
        self, resource_type: ResourceType
    ) -> list[Resource]:
        """Get all resources of a specific type."""
        return [r for r in self._resources.values() if r.resource_type == resource_type]

    async def get_resources_by_tag(self, key: str, value: str) -> list[Resource]:
        """Get resources by tag."""
        return [
            r
            for r in self._resources.values()
            if any(t.key == key and t.value == value for t in r.tags)
        ]

    async def get_upstream_resources(
        self, resource_id: str, depth: int = 1
    ) -> list[Resource]:
        """Get resources that depend on this resource."""
        upstream = []
        visited = set()

        def find_upstream(rid: str, current_depth: int):
            if current_depth > depth or rid in visited:
                return
            visited.add(rid)

            for rel in self._relationships.values():
                if rel.target_id == rid:
                    resource = self._resources.get(rel.source_id)
                    if resource:
                        upstream.append(resource)
                        find_upstream(rel.source_id, current_depth + 1)

        find_upstream(resource_id, 0)
        return upstream

    async def get_downstream_resources(
        self, resource_id: str, depth: int = 1
    ) -> list[Resource]:
        """Get resources that this resource depends on."""
        downstream = []
        visited = set()

        def find_downstream(rid: str, current_depth: int):
            if current_depth > depth or rid in visited:
                return
            visited.add(rid)

            for rel in self._relationships.values():
                if rel.source_id == rid:
                    resource = self._resources.get(rel.target_id)
                    if resource:
                        downstream.append(resource)
                        find_downstream(rel.target_id, current_depth + 1)

        find_downstream(resource_id, 0)
        return downstream

    async def get_service_topology(self, service_id: str) -> dict[str, Any]:
        """Get complete topology for a service."""
        service = self._services.get(service_id)
        if not service:
            return {}

        resources = [
            self._resources[rid] for rid in service.resources if rid in self._resources
        ]

        relationships = [
            rel
            for rel in self._relationships.values()
            if rel.source_id in service.resources or rel.target_id in service.resources
        ]

        return {
            "service": {
                "id": service.service_id,
                "name": service.name,
                "description": service.description,
                "owner": service.owner,
                "team": service.team,
                "tier": service.tier,
            },
            "resources": [
                {
                    "id": r.resource_id,
                    "name": r.name,
                    "type": r.resource_type.value,
                    "status": r.status.value,
                    "region": r.region,
                }
                for r in resources
            ],
            "relationships": [
                {
                    "source": rel.source_id,
                    "target": rel.target_id,
                    "type": rel.relationship_type.value,
                }
                for rel in relationships
            ],
            "upstream_services": service.upstream_services,
            "downstream_services": service.downstream_services,
        }

    # =========================================================================
    # Snapshot Management
    # =========================================================================

    async def take_snapshot(self) -> TopologySnapshot:
        """Take a snapshot of current topology."""
        snapshot_id = str(uuid.uuid4())

        # Single-pass aggregation for type, region, environment, and cost
        by_type: dict[str, int] = {}
        by_region: dict[str, int] = {}
        by_env: dict[str, int] = {}
        total_cost = 0.0

        for r in self._resources.values():
            type_name = r.resource_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
            by_region[r.region] = by_region.get(r.region, 0) + 1
            env = r.environment or "unknown"
            by_env[env] = by_env.get(env, 0) + 1
            total_cost += r.monthly_cost

        snapshot = TopologySnapshot(
            snapshot_id=snapshot_id,
            taken_at=datetime.now(timezone.utc),
            total_resources=len(self._resources),
            total_relationships=len(self._relationships),
            total_services=len(self._services),
            resources_by_type=by_type,
            resources_by_region=by_region,
            resources_by_environment=by_env,
            total_monthly_cost=total_cost,
        )

        self._snapshots[snapshot_id] = snapshot

        self._logger.info(
            "Topology snapshot taken",
            snapshot_id=snapshot_id,
            resources=snapshot.total_resources,
            relationships=snapshot.total_relationships,
        )

        return snapshot

    async def compare_snapshots(self, baseline_id: str, current_id: str) -> DriftReport:
        """Compare two snapshots to detect drift."""
        baseline = self._snapshots.get(baseline_id)
        current = self._snapshots.get(current_id)

        if not baseline or not current:
            raise ValueError("Snapshot not found")

        drift_items = []

        # Compare resource counts by type
        all_types = set(baseline.resources_by_type.keys()) | set(
            current.resources_by_type.keys()
        )

        for resource_type in all_types:
            baseline_count = baseline.resources_by_type.get(resource_type, 0)
            current_count = current.resources_by_type.get(resource_type, 0)

            if baseline_count != current_count:
                if baseline_count == 0:
                    drift_type = DriftType.ADDED
                elif current_count == 0:
                    drift_type = DriftType.REMOVED
                else:
                    drift_type = DriftType.MODIFIED

                drift_items.append(
                    DriftItem(
                        drift_id=str(uuid.uuid4()),
                        resource_id=resource_type,
                        drift_type=drift_type,
                        property_path="count",
                        expected_value=baseline_count,
                        actual_value=current_count,
                        severity=(
                            "medium"
                            if abs(current_count - baseline_count) <= 2
                            else "high"
                        ),
                    )
                )

        # Count by drift type
        by_drift_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}

        for item in drift_items:
            by_drift_type[item.drift_type.value] = (
                by_drift_type.get(item.drift_type.value, 0) + 1
            )
            by_severity[item.severity] = by_severity.get(item.severity, 0) + 1

        return DriftReport(
            report_id=str(uuid.uuid4()),
            baseline_snapshot_id=baseline_id,
            current_snapshot_id=current_id,
            drift_items=drift_items,
            total_drifted_resources=len({item.resource_id for item in drift_items}),
            by_drift_type=by_drift_type,
            by_severity=by_severity,
        )

    # =========================================================================
    # Impact Analysis
    # =========================================================================

    async def analyze_change_impact(
        self, target_resource_ids: list[str], change_description: str
    ) -> ImpactAnalysis:
        """
        Analyze the impact of a proposed change.

        Args:
            target_resource_ids: Resources being changed
            change_description: Description of the change

        Returns:
            Impact analysis
        """
        directly_affected = target_resource_ids.copy()
        indirectly_affected = []
        affected_services = []

        # Find upstream (dependent) resources
        for rid in target_resource_ids:
            upstream = await self.get_upstream_resources(rid, depth=3)
            indirectly_affected.extend([r.resource_id for r in upstream])

        indirectly_affected = list(set(indirectly_affected) - set(directly_affected))

        # Find affected services
        all_affected = set(directly_affected + indirectly_affected)
        for service in self._services.values():
            if any(rid in service.resources for rid in all_affected):
                affected_services.append(service.name)

        # Calculate risk score
        risk_score = 0.0
        risk_factors = []

        # More affected resources = higher risk
        risk_score += len(directly_affected) * 5
        risk_score += len(indirectly_affected) * 2

        if len(directly_affected) > 3:
            risk_factors.append(
                f"Multiple resources affected ({len(directly_affected)})"
            )

        if len(indirectly_affected) > 5:
            risk_factors.append(
                f"Large indirect impact ({len(indirectly_affected)} resources)"
            )

        # Check for critical services
        for service_name in affected_services:
            svc: ServiceComponent | None = self.get_service_by_name(service_name)
            if svc is not None and svc.tier == "critical":
                risk_score += 20
                risk_factors.append(f"Critical service affected: {service_name}")

        # Check for database resources
        for rid in target_resource_ids:
            resource = self._resources.get(rid)
            if resource and resource.resource_type in [
                ResourceType.RDS_INSTANCE,
                ResourceType.DYNAMODB_TABLE,
                ResourceType.NEPTUNE_CLUSTER,
            ]:
                risk_score += 15
                risk_factors.append(f"Database resource affected: {resource.name}")

        # Generate recommendations
        recommendations = []
        requires_approval = False

        if risk_score > 50:
            recommendations.append("Consider implementing change in stages")
            recommendations.append("Prepare rollback plan before proceeding")
            requires_approval = True

        if len(affected_services) > 1:
            recommendations.append("Coordinate with teams owning affected services")

        if any("Database" in f for f in risk_factors):
            recommendations.append("Take database snapshot before change")
            recommendations.append("Schedule during low-traffic period")
            requires_approval = True

        return ImpactAnalysis(
            analysis_id=str(uuid.uuid4()),
            change_description=change_description,
            target_resources=target_resource_ids,
            directly_affected=directly_affected,
            indirectly_affected=indirectly_affected,
            affected_services=affected_services,
            risk_score=min(100, risk_score),
            risk_factors=risk_factors,
            recommendations=recommendations,
            requires_approval=requires_approval,
        )

    # =========================================================================
    # Cost Attribution
    # =========================================================================

    async def get_cost_breakdown(self, days: int = 30) -> CostBreakdown:
        """
        Get cost breakdown by topology elements.

        Args:
            days: Number of days to analyze

        Returns:
            Cost breakdown
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        # Calculate costs by various dimensions
        by_service: dict[str, float] = {}
        by_resource_type: dict[str, float] = {}
        by_environment: dict[str, float] = {}
        by_team: dict[str, float] = {}
        by_region: dict[str, float] = {}

        total_cost = 0.0

        for resource in self._resources.values():
            cost = resource.monthly_cost * (days / 30)  # Prorate to period
            total_cost += cost

            # By resource type
            type_name = resource.resource_type.value
            by_resource_type[type_name] = by_resource_type.get(type_name, 0) + cost

            # By environment
            env = resource.environment or "unknown"
            by_environment[env] = by_environment.get(env, 0) + cost

            # By team
            team = resource.team or "unknown"
            by_team[team] = by_team.get(team, 0) + cost

            # By region
            by_region[resource.region] = by_region.get(resource.region, 0) + cost

        # By service
        for service in self._services.values():
            service_cost = sum(
                self._resources.get(
                    rid,
                    Resource(
                        resource_id="",
                        arn="",
                        name="",
                        resource_type=ResourceType.EC2_INSTANCE,
                        provider=CloudProvider.AWS,
                        region="",
                        account_id="",
                        status=ResourceStatus.UNKNOWN,
                    ),
                ).monthly_cost
                * (days / 30)
                for rid in service.resources
            )
            by_service[service.name] = service_cost

        # Detect anomalies (resources with cost > 2x average)
        if self._resources:
            avg_cost = total_cost / len(self._resources)
            anomalies = [
                {
                    "resource_id": r.resource_id,
                    "name": r.name,
                    "cost": r.monthly_cost * (days / 30),
                    "reason": "Cost significantly above average",
                }
                for r in self._resources.values()
                if r.monthly_cost * (days / 30) > avg_cost * 2
            ]
        else:
            anomalies = []

        return CostBreakdown(
            breakdown_id=str(uuid.uuid4()),
            period_start=start_time,
            period_end=end_time,
            total_cost=total_cost,
            by_service=by_service,
            by_resource_type=by_resource_type,
            by_environment=by_environment,
            by_team=by_team,
            by_region=by_region,
            cost_trend="stable",  # Would need historical data
            cost_anomalies=anomalies,
        )

    # =========================================================================
    # Export/Visualization
    # =========================================================================

    def export_to_graphviz(self) -> str:
        """Export topology to Graphviz DOT format."""
        lines = ["digraph Topology {", "  rankdir=LR;", "  node [shape=box];", ""]

        # Add nodes
        for resource in self._resources.values():
            color = {
                ResourceStatus.RUNNING: "green",
                ResourceStatus.STOPPED: "red",
                ResourceStatus.DEGRADED: "orange",
                ResourceStatus.PENDING: "yellow",
            }.get(resource.status, "gray")

            lines.append(
                f'  "{resource.resource_id}" [label="{resource.name}\\n{resource.resource_type.value}" '
                f'color="{color}"];'
            )

        # Add edges
        for rel in self._relationships.values():
            style = {
                RelationshipType.DEPENDS_ON: "solid",
                RelationshipType.CONNECTS_TO: "dashed",
                RelationshipType.CONTAINS: "dotted",
            }.get(rel.relationship_type, "solid")

            lines.append(
                f'  "{rel.source_id}" -> "{rel.target_id}" '
                f'[label="{rel.relationship_type.value}" style="{style}"];'
            )

        lines.append("}")

        return "\n".join(lines)

    def export_to_json(self) -> str:
        """Export topology to JSON format."""
        return json.dumps(
            {
                "resources": [
                    {
                        "id": r.resource_id,
                        "arn": r.arn,
                        "name": r.name,
                        "type": r.resource_type.value,
                        "provider": r.provider.value,
                        "region": r.region,
                        "status": r.status.value,
                        "environment": r.environment,
                        "team": r.team,
                        "monthly_cost": r.monthly_cost,
                    }
                    for r in self._resources.values()
                ],
                "relationships": [
                    {
                        "source": r.source_id,
                        "target": r.target_id,
                        "type": r.relationship_type.value,
                    }
                    for r in self._relationships.values()
                ],
                "services": [
                    {
                        "id": s.service_id,
                        "name": s.name,
                        "owner": s.owner,
                        "team": s.team,
                        "tier": s.tier,
                        "resources": s.resources,
                        "upstream": s.upstream_services,
                        "downstream": s.downstream_services,
                    }
                    for s in self._services.values()
                ],
            },
            indent=2,
        )
