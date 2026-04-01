"""
AWS Discovery Provider
======================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Discovers AWS resources using boto3 APIs. Supports:
- EC2, ECS, EKS compute resources
- RDS, DynamoDB, Neptune databases
- S3, EFS storage
- SQS, SNS, EventBridge messaging
- API Gateway, Lambda serverless
- VPC networking

GovCloud compatibility:
- Uses partition-aware ARNs
- Handles GovCloud service availability
"""

import logging
import os
from datetime import datetime, timezone

from src.services.cloud_discovery.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker,
)
from src.services.cloud_discovery.credential_proxy import (
    AuthenticatedSession,
    CredentialProxyService,
)
from src.services.cloud_discovery.exceptions import GovCloudUnavailableError
from src.services.cloud_discovery.types import (
    CloudProvider,
    CloudResource,
    CloudResourceType,
    DiscoveryResult,
    DiscoveryScope,
    RelationshipType,
    ResourceRelationship,
)

logger = logging.getLogger(__name__)


class AWSDiscoveryProvider:
    """
    AWS resource discovery provider.

    Discovers AWS resources across multiple services and builds
    a resource graph with relationships.

    Usage:
        provider = AWSDiscoveryProvider(credential_proxy)

        # Discover all resources in account
        result = await provider.discover(
            account_id='123456789012',
            regions=['us-east-1', 'us-west-2']
        )

        # Discover specific services
        result = await provider.discover(
            account_id='123456789012',
            regions=['us-east-1'],
            services=['ec2', 'rds', 's3']
        )
    """

    # Services not available in GovCloud
    GOVCLOUD_UNAVAILABLE_SERVICES = {
        "discovery",  # AWS Application Discovery Service
        "resource-explorer-2",  # AWS Resource Explorer
        "servicecatalog-appregistry",  # AWS Service Catalog AppRegistry
    }

    # GovCloud regions
    GOVCLOUD_REGIONS = {"us-gov-west-1", "us-gov-east-1"}

    # Default services to discover
    DEFAULT_SERVICES = [
        "ec2",
        "ecs",
        "eks",
        "lambda",
        "rds",
        "dynamodb",
        "s3",
        "sqs",
        "sns",
        "apigateway",
        "elasticache",
    ]

    def __init__(
        self,
        credential_proxy: CredentialProxyService | None = None,
        use_mock: bool = False,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize AWS discovery provider.

        Args:
            credential_proxy: Credential proxy for secure authentication
            use_mock: Use mock mode for testing
            circuit_breaker_config: Config for circuit breakers
        """
        self.credential_proxy = credential_proxy
        self.use_mock = use_mock
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()

        # Lazy-initialized boto3 session
        self._session: AuthenticatedSession | None = None

    def _get_partition(self, region: str) -> str:
        """Get AWS partition for region.

        Args:
            region: AWS region

        Returns:
            'aws' or 'aws-us-gov'
        """
        if region in self.GOVCLOUD_REGIONS:
            return "aws-us-gov"
        return "aws"

    def _is_govcloud(self, region: str) -> bool:
        """Check if region is GovCloud."""
        return region in self.GOVCLOUD_REGIONS

    def _check_govcloud_availability(self, service: str, region: str) -> None:
        """Check if service is available in GovCloud.

        Args:
            service: AWS service name
            region: Region

        Raises:
            GovCloudUnavailableError: If service unavailable in GovCloud
        """
        if self._is_govcloud(region) and service in self.GOVCLOUD_UNAVAILABLE_SERVICES:
            raise GovCloudUnavailableError(
                f"Service {service} is not available in GovCloud",
                service=service,
                region=region,
                alternative="Use AWS Config for resource discovery",
            )

    async def _get_session(self, account_id: str, region: str) -> AuthenticatedSession:
        """Get authenticated session.

        Args:
            account_id: AWS account ID
            region: AWS region

        Returns:
            Authenticated session
        """
        if self.use_mock:
            from unittest.mock import MagicMock

            mock_session = MagicMock()
            mock_session.region_name = region
            return AuthenticatedSession(
                provider=CloudProvider.AWS,
                account_id=account_id,
                region=region,
                session_type="boto3_mock",
                session_object=mock_session,
            )

        if self.credential_proxy:
            return await self.credential_proxy.get_discovery_session(
                CloudProvider.AWS, account_id, region
            )

        # Fall back to default credentials
        import boto3

        return AuthenticatedSession(
            provider=CloudProvider.AWS,
            account_id=account_id,
            region=region,
            session_type="boto3",
            session_object=boto3.Session(region_name=region),
        )

    def _get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """Get circuit breaker for service.

        Args:
            service: AWS service name

        Returns:
            Circuit breaker instance
        """
        return get_circuit_breaker("aws", service)

    async def discover(
        self,
        account_id: str,
        regions: list[str] | None = None,
        services: list[str] | None = None,
        scope: DiscoveryScope = DiscoveryScope.ACCOUNT,
        timeout_seconds: float = 300.0,
        tags_filter: dict[str, str] | None = None,
    ) -> DiscoveryResult:
        """Discover AWS resources.

        Args:
            account_id: AWS account ID
            regions: Regions to discover (default: current region)
            services: Services to discover (default: all)
            scope: Discovery scope
            timeout_seconds: Discovery timeout
            tags_filter: Optional filter by tags

        Returns:
            DiscoveryResult with discovered resources
        """
        start_time = datetime.now(timezone.utc)
        regions = regions or [os.environ.get("AWS_REGION", "us-east-1")]
        services = services or self.DEFAULT_SERVICES

        all_resources: list[CloudResource] = []
        all_relationships: list[ResourceRelationship] = []
        warnings: list[str] = []
        errors: list[str] = []

        for region in regions:
            try:
                session = await self._get_session(account_id, region)

                for service in services:
                    try:
                        # Check GovCloud availability
                        self._check_govcloud_availability(service, region)

                        # Discover with circuit breaker
                        breaker = self._get_circuit_breaker(service)
                        async with breaker:
                            resources, relationships = await self._discover_service(
                                session, service, region, tags_filter
                            )
                            all_resources.extend(resources)
                            all_relationships.extend(relationships)

                    except GovCloudUnavailableError as e:
                        warnings.append(f"{service} in {region}: {e.message}")
                    except Exception as e:
                        errors.append(f"Error discovering {service} in {region}: {e}")
                        logger.error(f"Discovery error: {e}", exc_info=True)

            except Exception as e:
                errors.append(f"Error accessing {region}: {e}")

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        return DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id=account_id,
            regions=regions,
            resources=all_resources,
            relationships=all_relationships,
            discovery_time_ms=elapsed,
            warnings=warnings,
            errors=errors,
        )

    async def _discover_service(
        self,
        session: AuthenticatedSession,
        service: str,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover resources for a specific service.

        Args:
            session: Authenticated session
            service: AWS service name
            region: AWS region
            tags_filter: Optional tag filter

        Returns:
            Tuple of (resources, relationships)
        """
        if self.use_mock:
            return self._get_mock_resources(service, session.account_id, region)

        # Service-specific discovery methods
        discovery_methods = {
            "ec2": self._discover_ec2,
            "ecs": self._discover_ecs,
            "eks": self._discover_eks,
            "lambda": self._discover_lambda,
            "rds": self._discover_rds,
            "dynamodb": self._discover_dynamodb,
            "s3": self._discover_s3,
            "sqs": self._discover_sqs,
            "sns": self._discover_sns,
            "apigateway": self._discover_apigateway,
            "elasticache": self._discover_elasticache,
        }

        method = discovery_methods.get(service)
        if method:
            return await method(session, region, tags_filter)

        logger.warning(f"No discovery method for service: {service}")
        return [], []

    async def _discover_ec2(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover EC2 resources."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        ec2 = session.session_object.client("ec2", region_name=region)

        # Discover instances
        filters = []
        if tags_filter:
            for key, value in tags_filter.items():
                filters.append({"Name": f"tag:{key}", "Values": [value]})

        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate(Filters=filters if filters else []):
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance["InstanceId"]
                    partition = self._get_partition(region)
                    arn = f"arn:{partition}:ec2:{region}:{session.account_id}:instance/{instance_id}"

                    tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}

                    resources.append(
                        CloudResource(
                            resource_id=arn,
                            resource_type=CloudResourceType.EC2_INSTANCE,
                            provider=CloudProvider.AWS,
                            name=tags.get("Name", instance_id),
                            region=region,
                            account_id=session.account_id,
                            tags=tags,
                            properties={
                                "instance_type": instance.get("InstanceType"),
                                "state": instance.get("State", {}).get("Name"),
                                "vpc_id": instance.get("VpcId"),
                                "subnet_id": instance.get("SubnetId"),
                                "private_ip": instance.get("PrivateIpAddress"),
                                "public_ip": instance.get("PublicIpAddress"),
                                "security_groups": [
                                    sg["GroupId"]
                                    for sg in instance.get("SecurityGroups", [])
                                ],
                            },
                        )
                    )

                    # Add VPC relationship
                    if instance.get("VpcId"):
                        vpc_arn = f"arn:{partition}:ec2:{region}:{session.account_id}:vpc/{instance['VpcId']}"
                        relationships.append(
                            ResourceRelationship(
                                source_id=arn,
                                target_id=vpc_arn,
                                relationship_type=RelationshipType.DEPLOYED_IN,
                            )
                        )

        # Discover VPCs
        vpcs = ec2.describe_vpcs().get("Vpcs", [])
        for vpc in vpcs:
            vpc_id = vpc["VpcId"]
            partition = self._get_partition(region)
            arn = f"arn:{partition}:ec2:{region}:{session.account_id}:vpc/{vpc_id}"

            tags = {t["Key"]: t["Value"] for t in vpc.get("Tags", [])}

            resources.append(
                CloudResource(
                    resource_id=arn,
                    resource_type=CloudResourceType.VPC,
                    provider=CloudProvider.AWS,
                    name=tags.get("Name", vpc_id),
                    region=region,
                    account_id=session.account_id,
                    tags=tags,
                    properties={
                        "cidr_block": vpc.get("CidrBlock"),
                        "is_default": vpc.get("IsDefault", False),
                        "state": vpc.get("State"),
                    },
                )
            )

        return resources, relationships

    async def _discover_ecs(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover ECS resources."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        ecs = session.session_object.client("ecs", region_name=region)

        # List clusters
        cluster_arns = ecs.list_clusters().get("clusterArns", [])

        if cluster_arns:
            clusters = ecs.describe_clusters(clusters=cluster_arns).get("clusters", [])

            for cluster in clusters:
                cluster_arn = cluster["clusterArn"]
                tags = {t["key"]: t["value"] for t in cluster.get("tags", [])}

                resources.append(
                    CloudResource(
                        resource_id=cluster_arn,
                        resource_type=CloudResourceType.ECS_CLUSTER,
                        provider=CloudProvider.AWS,
                        name=cluster.get("clusterName", ""),
                        region=region,
                        account_id=session.account_id,
                        tags=tags,
                        properties={
                            "status": cluster.get("status"),
                            "running_tasks": cluster.get("runningTasksCount", 0),
                            "pending_tasks": cluster.get("pendingTasksCount", 0),
                            "active_services": cluster.get("activeServicesCount", 0),
                        },
                    )
                )

                # Discover services in cluster
                service_arns = ecs.list_services(cluster=cluster_arn).get(
                    "serviceArns", []
                )
                if service_arns:
                    services = ecs.describe_services(
                        cluster=cluster_arn, services=service_arns
                    ).get("services", [])

                    for service in services:
                        service_arn = service["serviceArn"]
                        svc_tags = {
                            t["key"]: t["value"] for t in service.get("tags", [])
                        }

                        resources.append(
                            CloudResource(
                                resource_id=service_arn,
                                resource_type=CloudResourceType.ECS_SERVICE,
                                provider=CloudProvider.AWS,
                                name=service.get("serviceName", ""),
                                region=region,
                                account_id=session.account_id,
                                tags=svc_tags,
                                properties={
                                    "status": service.get("status"),
                                    "desired_count": service.get("desiredCount", 0),
                                    "running_count": service.get("runningCount", 0),
                                    "task_definition": service.get("taskDefinition"),
                                    "launch_type": service.get("launchType"),
                                },
                            )
                        )

                        # Add cluster relationship
                        relationships.append(
                            ResourceRelationship(
                                source_id=service_arn,
                                target_id=cluster_arn,
                                relationship_type=RelationshipType.DEPLOYED_IN,
                            )
                        )

        return resources, relationships

    async def _discover_eks(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover EKS resources."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        eks = session.session_object.client("eks", region_name=region)

        cluster_names = eks.list_clusters().get("clusters", [])

        for name in cluster_names:
            cluster = eks.describe_cluster(name=name).get("cluster", {})
            cluster_arn = cluster.get("arn", "")
            tags = cluster.get("tags", {})

            resources.append(
                CloudResource(
                    resource_id=cluster_arn,
                    resource_type=CloudResourceType.EKS_CLUSTER,
                    provider=CloudProvider.AWS,
                    name=name,
                    region=region,
                    account_id=session.account_id,
                    tags=tags,
                    properties={
                        "status": cluster.get("status"),
                        "version": cluster.get("version"),
                        "endpoint": cluster.get("endpoint"),
                        "vpc_id": cluster.get("resourcesVpcConfig", {}).get("vpcId"),
                        "subnet_ids": cluster.get("resourcesVpcConfig", {}).get(
                            "subnetIds", []
                        ),
                    },
                )
            )

            # Add VPC relationship
            vpc_id = cluster.get("resourcesVpcConfig", {}).get("vpcId")
            if vpc_id:
                partition = self._get_partition(region)
                vpc_arn = (
                    f"arn:{partition}:ec2:{region}:{session.account_id}:vpc/{vpc_id}"
                )
                relationships.append(
                    ResourceRelationship(
                        source_id=cluster_arn,
                        target_id=vpc_arn,
                        relationship_type=RelationshipType.DEPLOYED_IN,
                    )
                )

        return resources, relationships

    async def _discover_lambda(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover Lambda functions."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        lambda_client = session.session_object.client("lambda", region_name=region)

        paginator = lambda_client.get_paginator("list_functions")
        for page in paginator.paginate():
            for func in page.get("Functions", []):
                func_arn = func["FunctionArn"]

                # Get tags
                try:
                    tags = lambda_client.list_tags(Resource=func_arn).get("Tags", {})
                except Exception:
                    tags = {}

                # Apply tag filter if specified
                if tags_filter:
                    if not all(tags.get(k) == v for k, v in tags_filter.items()):
                        continue

                resources.append(
                    CloudResource(
                        resource_id=func_arn,
                        resource_type=CloudResourceType.LAMBDA_FUNCTION,
                        provider=CloudProvider.AWS,
                        name=func.get("FunctionName", ""),
                        region=region,
                        account_id=session.account_id,
                        tags=tags,
                        properties={
                            "runtime": func.get("Runtime"),
                            "handler": func.get("Handler"),
                            "memory_size": func.get("MemorySize"),
                            "timeout": func.get("Timeout"),
                            "last_modified": func.get("LastModified"),
                        },
                    )
                )

        return resources, relationships

    async def _discover_rds(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover RDS resources."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        rds = session.session_object.client("rds", region_name=region)

        # Discover DB instances
        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for instance in page.get("DBInstances", []):
                instance_arn = instance["DBInstanceArn"]
                tags = {t["Key"]: t["Value"] for t in instance.get("TagList", [])}

                resources.append(
                    CloudResource(
                        resource_id=instance_arn,
                        resource_type=CloudResourceType.RDS_INSTANCE,
                        provider=CloudProvider.AWS,
                        name=instance.get("DBInstanceIdentifier", ""),
                        region=region,
                        account_id=session.account_id,
                        tags=tags,
                        properties={
                            "engine": instance.get("Engine"),
                            "engine_version": instance.get("EngineVersion"),
                            "instance_class": instance.get("DBInstanceClass"),
                            "storage_type": instance.get("StorageType"),
                            "allocated_storage": instance.get("AllocatedStorage"),
                            "status": instance.get("DBInstanceStatus"),
                            "endpoint": instance.get("Endpoint", {}).get("Address"),
                            "port": instance.get("Endpoint", {}).get("Port"),
                            "multi_az": instance.get("MultiAZ", False),
                        },
                    )
                )

        # Discover DB clusters (Aurora)
        clusters_paginator = rds.get_paginator("describe_db_clusters")
        for page in clusters_paginator.paginate():
            for cluster in page.get("DBClusters", []):
                cluster_arn = cluster["DBClusterArn"]
                tags = {t["Key"]: t["Value"] for t in cluster.get("TagList", [])}

                resources.append(
                    CloudResource(
                        resource_id=cluster_arn,
                        resource_type=CloudResourceType.RDS_CLUSTER,
                        provider=CloudProvider.AWS,
                        name=cluster.get("DBClusterIdentifier", ""),
                        region=region,
                        account_id=session.account_id,
                        tags=tags,
                        properties={
                            "engine": cluster.get("Engine"),
                            "engine_version": cluster.get("EngineVersion"),
                            "status": cluster.get("Status"),
                            "endpoint": cluster.get("Endpoint"),
                            "reader_endpoint": cluster.get("ReaderEndpoint"),
                            "port": cluster.get("Port"),
                            "multi_az": cluster.get("MultiAZ", False),
                        },
                    )
                )

        return resources, relationships

    async def _discover_dynamodb(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover DynamoDB tables."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        dynamodb = session.session_object.client("dynamodb", region_name=region)

        paginator = dynamodb.get_paginator("list_tables")
        for page in paginator.paginate():
            for table_name in page.get("TableNames", []):
                table = dynamodb.describe_table(TableName=table_name).get("Table", {})
                table_arn = table.get("TableArn", "")

                # Get tags
                try:
                    tags_response = dynamodb.list_tags_of_resource(
                        ResourceArn=table_arn
                    )
                    tags = {t["Key"]: t["Value"] for t in tags_response.get("Tags", [])}
                except Exception:
                    tags = {}

                resources.append(
                    CloudResource(
                        resource_id=table_arn,
                        resource_type=CloudResourceType.DYNAMODB_TABLE,
                        provider=CloudProvider.AWS,
                        name=table_name,
                        region=region,
                        account_id=session.account_id,
                        tags=tags,
                        properties={
                            "status": table.get("TableStatus"),
                            "item_count": table.get("ItemCount", 0),
                            "size_bytes": table.get("TableSizeBytes", 0),
                            "billing_mode": table.get("BillingModeSummary", {}).get(
                                "BillingMode", "PROVISIONED"
                            ),
                            "key_schema": [
                                {"name": k["AttributeName"], "type": k["KeyType"]}
                                for k in table.get("KeySchema", [])
                            ],
                        },
                    )
                )

        return resources, relationships

    async def _discover_s3(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover S3 buckets."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        s3 = session.session_object.client("s3", region_name=region)

        buckets = s3.list_buckets().get("Buckets", [])

        for bucket in buckets:
            bucket_name = bucket["Name"]

            # Get bucket location
            try:
                location = s3.get_bucket_location(Bucket=bucket_name)
                bucket_region = location.get("LocationConstraint") or "us-east-1"
            except Exception:
                bucket_region = region

            # Skip buckets not in target region
            if bucket_region != region:
                continue

            partition = self._get_partition(region)
            bucket_arn = f"arn:{partition}:s3:::{bucket_name}"

            # Get tags
            try:
                tags_response = s3.get_bucket_tagging(Bucket=bucket_name)
                tags = {t["Key"]: t["Value"] for t in tags_response.get("TagSet", [])}
            except Exception:
                tags = {}

            resources.append(
                CloudResource(
                    resource_id=bucket_arn,
                    resource_type=CloudResourceType.S3_BUCKET,
                    provider=CloudProvider.AWS,
                    name=bucket_name,
                    region=bucket_region,
                    account_id=session.account_id,
                    tags=tags,
                    properties={
                        "creation_date": bucket.get("CreationDate"),
                    },
                )
            )

        return resources, relationships

    async def _discover_sqs(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover SQS queues."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        sqs = session.session_object.client("sqs", region_name=region)

        queues = sqs.list_queues().get("QueueUrls", [])

        for queue_url in queues:
            # Get queue attributes
            attrs = sqs.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=["All"]
            ).get("Attributes", {})

            queue_arn = attrs.get("QueueArn", "")
            queue_name = queue_url.split("/")[-1]

            # Get tags
            try:
                tags = sqs.list_queue_tags(QueueUrl=queue_url).get("Tags", {})
            except Exception:
                tags = {}

            resources.append(
                CloudResource(
                    resource_id=queue_arn,
                    resource_type=CloudResourceType.SQS_QUEUE,
                    provider=CloudProvider.AWS,
                    name=queue_name,
                    region=region,
                    account_id=session.account_id,
                    tags=tags,
                    properties={
                        "queue_url": queue_url,
                        "visibility_timeout": attrs.get("VisibilityTimeout"),
                        "delay_seconds": attrs.get("DelaySeconds"),
                        "max_message_size": attrs.get("MaximumMessageSize"),
                        "message_retention": attrs.get("MessageRetentionPeriod"),
                        "approx_messages": attrs.get(
                            "ApproximateNumberOfMessages", "0"
                        ),
                        "is_fifo": queue_name.endswith(".fifo"),
                    },
                )
            )

        return resources, relationships

    async def _discover_sns(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover SNS topics."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        sns = session.session_object.client("sns", region_name=region)

        paginator = sns.get_paginator("list_topics")
        for page in paginator.paginate():
            for topic in page.get("Topics", []):
                topic_arn = topic["TopicArn"]
                topic_name = topic_arn.split(":")[-1]

                # Get attributes
                attrs = sns.get_topic_attributes(TopicArn=topic_arn).get(
                    "Attributes", {}
                )

                # Get tags
                try:
                    tags = {
                        t["Key"]: t["Value"]
                        for t in sns.list_tags_for_resource(ResourceArn=topic_arn).get(
                            "Tags", []
                        )
                    }
                except Exception:
                    tags = {}

                resources.append(
                    CloudResource(
                        resource_id=topic_arn,
                        resource_type=CloudResourceType.SNS_TOPIC,
                        provider=CloudProvider.AWS,
                        name=topic_name,
                        region=region,
                        account_id=session.account_id,
                        tags=tags,
                        properties={
                            "display_name": attrs.get("DisplayName"),
                            "subscriptions_confirmed": attrs.get(
                                "SubscriptionsConfirmed", "0"
                            ),
                            "subscriptions_pending": attrs.get(
                                "SubscriptionsPending", "0"
                            ),
                        },
                    )
                )

        return resources, relationships

    async def _discover_apigateway(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover API Gateway resources."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        apigw = session.session_object.client("apigateway", region_name=region)

        # REST APIs
        rest_apis = apigw.get_rest_apis().get("items", [])
        partition = self._get_partition(region)

        for api in rest_apis:
            api_id = api["id"]
            api_arn = f"arn:{partition}:apigateway:{region}::/restapis/{api_id}"

            resources.append(
                CloudResource(
                    resource_id=api_arn,
                    resource_type=CloudResourceType.API_GATEWAY_REST,
                    provider=CloudProvider.AWS,
                    name=api.get("name", ""),
                    region=region,
                    account_id=session.account_id,
                    tags=api.get("tags", {}),
                    properties={
                        "api_id": api_id,
                        "description": api.get("description"),
                        "created_date": api.get("createdDate"),
                        "endpoint_configuration": api.get("endpointConfiguration", {}),
                    },
                )
            )

        return resources, relationships

    async def _discover_elasticache(
        self,
        session: AuthenticatedSession,
        region: str,
        tags_filter: dict[str, str] | None = None,
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Discover ElastiCache resources."""
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        elasticache = session.session_object.client("elasticache", region_name=region)

        paginator = elasticache.get_paginator("describe_cache_clusters")
        for page in paginator.paginate(ShowCacheNodeInfo=True):
            for cluster in page.get("CacheClusters", []):
                cluster_id = cluster["CacheClusterId"]
                cluster_arn = cluster.get("ARN", "")

                # Get tags
                try:
                    tags = {
                        t["Key"]: t["Value"]
                        for t in elasticache.list_tags_for_resource(
                            ResourceName=cluster_arn
                        ).get("TagList", [])
                    }
                except Exception:
                    tags = {}

                resources.append(
                    CloudResource(
                        resource_id=cluster_arn,
                        resource_type=CloudResourceType.ELASTICACHE_CLUSTER,
                        provider=CloudProvider.AWS,
                        name=cluster_id,
                        region=region,
                        account_id=session.account_id,
                        tags=tags,
                        properties={
                            "engine": cluster.get("Engine"),
                            "engine_version": cluster.get("EngineVersion"),
                            "node_type": cluster.get("CacheNodeType"),
                            "num_nodes": cluster.get("NumCacheNodes", 0),
                            "status": cluster.get("CacheClusterStatus"),
                        },
                    )
                )

        return resources, relationships

    def _get_mock_resources(
        self, service: str, account_id: str, region: str
    ) -> tuple[list[CloudResource], list[ResourceRelationship]]:
        """Get mock resources for testing.

        Args:
            service: AWS service name
            account_id: Account ID
            region: Region

        Returns:
            Tuple of mock (resources, relationships)
        """
        partition = self._get_partition(region)
        resources: list[CloudResource] = []
        relationships: list[ResourceRelationship] = []

        if service == "ec2":
            resources.append(
                CloudResource(
                    resource_id=f"arn:{partition}:ec2:{region}:{account_id}:instance/i-mock123",
                    resource_type=CloudResourceType.EC2_INSTANCE,
                    provider=CloudProvider.AWS,
                    name="mock-instance",
                    region=region,
                    account_id=account_id,
                    tags={"Environment": "dev"},
                    properties={"instance_type": "t3.micro", "state": "running"},
                )
            )
        elif service == "rds":
            resources.append(
                CloudResource(
                    resource_id=f"arn:{partition}:rds:{region}:{account_id}:db:mock-db",
                    resource_type=CloudResourceType.RDS_INSTANCE,
                    provider=CloudProvider.AWS,
                    name="mock-db",
                    region=region,
                    account_id=account_id,
                    tags={"Environment": "dev"},
                    properties={"engine": "postgres", "status": "available"},
                )
            )
        elif service == "lambda":
            resources.append(
                CloudResource(
                    resource_id=f"arn:{partition}:lambda:{region}:{account_id}:function:mock-function",
                    resource_type=CloudResourceType.LAMBDA_FUNCTION,
                    provider=CloudProvider.AWS,
                    name="mock-function",
                    region=region,
                    account_id=account_id,
                    tags={"Environment": "dev"},
                    properties={"runtime": "python3.11", "memory_size": 256},
                )
            )

        return resources, relationships
