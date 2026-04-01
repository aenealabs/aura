"""
Infrastructure as Code Correlation Engine
==========================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Correlates IaC definitions (CloudFormation, Terraform) with
discovered cloud resources. Identifies:
- Matched resources (IaC -> deployed resource)
- Unmatched IaC (defined but not deployed)
- Drift (deployed but not in IaC)

Supports:
- CloudFormation templates (YAML/JSON)
- Terraform configurations (HCL)
- CDK synthesized outputs
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.services.cloud_discovery.exceptions import IaCParseError
from src.services.cloud_discovery.types import (
    CloudResource,
    CloudResourceType,
    CorrelationResult,
    DiscoveryResult,
    IaCMapping,
)

logger = logging.getLogger(__name__)


@dataclass
class IaCResource:
    """Parsed IaC resource definition.

    Attributes:
        logical_id: Logical ID in template
        resource_type: AWS/Azure resource type string
        source_file: Path to IaC file
        source_line: Line number in source
        properties: Resource properties
        depends_on: Dependencies
        conditions: Conditional deployment
    """

    logical_id: str
    resource_type: str
    source_file: str
    source_line: int = 0
    properties: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)


class IaCCorrelator:
    """
    Correlates IaC definitions with discovered cloud resources.

    Usage:
        correlator = IaCCorrelator()

        # Parse IaC from repository
        iac_resources = await correlator.parse_repository(repo_path)

        # Correlate with discovered resources
        result = await correlator.correlate(
            repository_id='my-repo',
            iac_resources=iac_resources,
            discovery_result=discovery_result
        )

        print(f"Correlation rate: {result.correlation_rate:.1%}")
        print(f"Drift count: {result.drift_count}")
    """

    # CloudFormation resource type to CloudResourceType mapping
    CFN_TYPE_MAPPING = {
        "AWS::EC2::Instance": CloudResourceType.EC2_INSTANCE,
        "AWS::ECS::Cluster": CloudResourceType.ECS_CLUSTER,
        "AWS::ECS::Service": CloudResourceType.ECS_SERVICE,
        "AWS::EKS::Cluster": CloudResourceType.EKS_CLUSTER,
        "AWS::EKS::Nodegroup": CloudResourceType.EKS_NODEGROUP,
        "AWS::Lambda::Function": CloudResourceType.LAMBDA_FUNCTION,
        "AWS::S3::Bucket": CloudResourceType.S3_BUCKET,
        "AWS::RDS::DBInstance": CloudResourceType.RDS_INSTANCE,
        "AWS::RDS::DBCluster": CloudResourceType.RDS_CLUSTER,
        "AWS::DynamoDB::Table": CloudResourceType.DYNAMODB_TABLE,
        "AWS::Neptune::DBCluster": CloudResourceType.NEPTUNE_CLUSTER,
        "AWS::OpenSearchService::Domain": CloudResourceType.OPENSEARCH_DOMAIN,
        "AWS::ElastiCache::CacheCluster": CloudResourceType.ELASTICACHE_CLUSTER,
        "AWS::EC2::VPC": CloudResourceType.VPC,
        "AWS::EC2::Subnet": CloudResourceType.SUBNET,
        "AWS::EC2::SecurityGroup": CloudResourceType.SECURITY_GROUP,
        "AWS::ElasticLoadBalancingV2::LoadBalancer": CloudResourceType.ALB,
        "AWS::SQS::Queue": CloudResourceType.SQS_QUEUE,
        "AWS::SNS::Topic": CloudResourceType.SNS_TOPIC,
        "AWS::Events::EventBus": CloudResourceType.EVENTBRIDGE_BUS,
        "AWS::Kinesis::Stream": CloudResourceType.KINESIS_STREAM,
        "AWS::ApiGateway::RestApi": CloudResourceType.API_GATEWAY_REST,
        "AWS::ApiGatewayV2::Api": CloudResourceType.API_GATEWAY_HTTP,
        "AWS::AppSync::GraphQLApi": CloudResourceType.APPSYNC_API,
        "AWS::IAM::Role": CloudResourceType.IAM_ROLE,
        "AWS::IAM::Policy": CloudResourceType.IAM_POLICY,
    }

    # Terraform resource type mapping
    TF_TYPE_MAPPING = {
        "aws_instance": CloudResourceType.EC2_INSTANCE,
        "aws_ecs_cluster": CloudResourceType.ECS_CLUSTER,
        "aws_ecs_service": CloudResourceType.ECS_SERVICE,
        "aws_eks_cluster": CloudResourceType.EKS_CLUSTER,
        "aws_eks_node_group": CloudResourceType.EKS_NODEGROUP,
        "aws_lambda_function": CloudResourceType.LAMBDA_FUNCTION,
        "aws_s3_bucket": CloudResourceType.S3_BUCKET,
        "aws_db_instance": CloudResourceType.RDS_INSTANCE,
        "aws_rds_cluster": CloudResourceType.RDS_CLUSTER,
        "aws_dynamodb_table": CloudResourceType.DYNAMODB_TABLE,
        "aws_neptune_cluster": CloudResourceType.NEPTUNE_CLUSTER,
        "aws_opensearch_domain": CloudResourceType.OPENSEARCH_DOMAIN,
        "aws_elasticache_cluster": CloudResourceType.ELASTICACHE_CLUSTER,
        "aws_vpc": CloudResourceType.VPC,
        "aws_subnet": CloudResourceType.SUBNET,
        "aws_security_group": CloudResourceType.SECURITY_GROUP,
        "aws_lb": CloudResourceType.ALB,
        "aws_sqs_queue": CloudResourceType.SQS_QUEUE,
        "aws_sns_topic": CloudResourceType.SNS_TOPIC,
        "aws_cloudwatch_event_bus": CloudResourceType.EVENTBRIDGE_BUS,
        "aws_kinesis_stream": CloudResourceType.KINESIS_STREAM,
        "aws_api_gateway_rest_api": CloudResourceType.API_GATEWAY_REST,
        "aws_apigatewayv2_api": CloudResourceType.API_GATEWAY_HTTP,
        "aws_iam_role": CloudResourceType.IAM_ROLE,
        "aws_iam_policy": CloudResourceType.IAM_POLICY,
    }

    def __init__(self, use_mock: bool = False) -> None:
        """Initialize IaC correlator.

        Args:
            use_mock: Use mock mode for testing
        """
        self.use_mock = use_mock

    async def parse_repository(
        self,
        repo_path: str | Path,
        patterns: list[str] | None = None,
    ) -> list[IaCResource]:
        """Parse IaC resources from a repository.

        Args:
            repo_path: Path to repository root
            patterns: Glob patterns for IaC files

        Returns:
            List of parsed IaC resources
        """
        repo_path = Path(repo_path)
        if not repo_path.exists():
            raise IaCParseError(
                f"Repository path does not exist: {repo_path}",
                file_path=str(repo_path),
            )

        resources: list[IaCResource] = []

        # Default patterns
        if patterns is None:
            patterns = [
                "**/*.yaml",
                "**/*.yml",
                "**/*.json",
                "**/*.tf",
            ]

        for pattern in patterns:
            for file_path in repo_path.glob(pattern):
                if file_path.is_file():
                    try:
                        file_resources = await self._parse_file(file_path)
                        resources.extend(file_resources)
                    except Exception as e:
                        logger.warning(f"Failed to parse {file_path}: {e}")

        logger.info(f"Parsed {len(resources)} IaC resources from {repo_path}")
        return resources

    async def _parse_file(self, file_path: Path) -> list[IaCResource]:
        """Parse a single IaC file.

        Args:
            file_path: Path to IaC file

        Returns:
            List of IaC resources from the file
        """
        suffix = file_path.suffix.lower()

        if suffix in (".yaml", ".yml"):
            return await self._parse_yaml(file_path)
        elif suffix == ".json":
            return await self._parse_json(file_path)
        elif suffix == ".tf":
            return await self._parse_terraform(file_path)

        return []

    async def _parse_yaml(self, file_path: Path) -> list[IaCResource]:
        """Parse CloudFormation YAML template.

        Args:
            file_path: Path to YAML file

        Returns:
            List of IaC resources
        """
        try:
            content = file_path.read_text()
            template = yaml.safe_load(content)

            if not isinstance(template, dict):
                return []

            # Check if it's a CloudFormation template
            if "AWSTemplateFormatVersion" in template or "Resources" in template:
                return self._parse_cloudformation(template, str(file_path), content)

            return []

        except yaml.YAMLError as e:
            logger.debug(f"YAML parse error in {file_path}: {e}")
            return []

    async def _parse_json(self, file_path: Path) -> list[IaCResource]:
        """Parse CloudFormation JSON template.

        Args:
            file_path: Path to JSON file

        Returns:
            List of IaC resources
        """
        try:
            content = file_path.read_text()
            template = json.loads(content)

            if not isinstance(template, dict):
                return []

            # Check if it's a CloudFormation template
            if "AWSTemplateFormatVersion" in template or "Resources" in template:
                return self._parse_cloudformation(template, str(file_path), content)

            return []

        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse error in {file_path}: {e}")
            return []

    def _parse_cloudformation(
        self,
        template: dict[str, Any],
        file_path: str,
        content: str,
    ) -> list[IaCResource]:
        """Parse CloudFormation template resources.

        Args:
            template: Parsed template dict
            file_path: Source file path
            content: Raw file content for line number detection

        Returns:
            List of IaC resources
        """
        resources: list[IaCResource] = []
        cfn_resources = template.get("Resources", {})

        for logical_id, resource_def in cfn_resources.items():
            if not isinstance(resource_def, dict):
                continue

            resource_type = resource_def.get("Type", "")
            if not resource_type:
                continue

            # Try to find line number
            line_number = self._find_line_number(content, logical_id)

            resources.append(
                IaCResource(
                    logical_id=logical_id,
                    resource_type=resource_type,
                    source_file=file_path,
                    source_line=line_number,
                    properties=resource_def.get("Properties", {}),
                    depends_on=resource_def.get("DependsOn", []),
                    conditions={"Condition": resource_def.get("Condition")},
                )
            )

        return resources

    async def _parse_terraform(self, file_path: Path) -> list[IaCResource]:
        """Parse Terraform HCL file.

        This is a simplified parser that extracts resource blocks.
        For production, consider using python-hcl2.

        Args:
            file_path: Path to .tf file

        Returns:
            List of IaC resources
        """
        try:
            content = file_path.read_text()
            resources: list[IaCResource] = []

            # Simple regex to find resource blocks
            # resource "aws_instance" "my_instance" { ... }
            resource_pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"'

            for match in re.finditer(resource_pattern, content):
                resource_type = match.group(1)
                logical_id = match.group(2)
                line_number = content[: match.start()].count("\n") + 1

                resources.append(
                    IaCResource(
                        logical_id=logical_id,
                        resource_type=resource_type,
                        source_file=str(file_path),
                        source_line=line_number,
                    )
                )

            return resources

        except Exception as e:
            logger.debug(f"Terraform parse error in {file_path}: {e}")
            return []

    def _find_line_number(self, content: str, logical_id: str) -> int:
        """Find line number of a logical ID in file content.

        Args:
            content: File content
            logical_id: Resource logical ID

        Returns:
            Line number (1-based) or 0 if not found
        """
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if logical_id in line:
                return i
        return 0

    async def correlate(
        self,
        repository_id: str,
        iac_resources: list[IaCResource],
        discovery_result: DiscoveryResult,
        stack_name: str | None = None,
    ) -> CorrelationResult:
        """Correlate IaC resources with discovered cloud resources.

        Args:
            repository_id: Repository ID
            iac_resources: Parsed IaC resources
            discovery_result: Cloud discovery results
            stack_name: CloudFormation stack name for direct lookup

        Returns:
            Correlation result with matches and drift
        """
        if self.use_mock:
            return self._get_mock_correlation(repository_id, iac_resources)

        iac_mappings: list[IaCMapping] = []
        unmatched_iac: list[IaCMapping] = []

        # Build lookup index from discovered resources
        discovered_by_type: dict[CloudResourceType, list[CloudResource]] = {}
        for resource in discovery_result.resources:
            rtype = resource.resource_type
            if rtype not in discovered_by_type:
                discovered_by_type[rtype] = []
            discovered_by_type[rtype].append(resource)

        # Track matched discovered resources
        matched_resource_ids: set[str] = set()

        # Try to correlate each IaC resource
        for iac in iac_resources:
            cloud_type = self._get_cloud_type(iac.resource_type)
            if cloud_type == CloudResourceType.UNKNOWN:
                # Skip unknown types
                continue

            mapping = IaCMapping(
                logical_id=iac.logical_id,
                resource_type=iac.resource_type,
                source_file=iac.source_file,
                source_line=iac.source_line,
                stack_name=stack_name,
            )

            # Try to find matching discovered resource
            candidates = discovered_by_type.get(cloud_type, [])
            matched = self._find_best_match(iac, candidates)

            if matched:
                mapping.physical_resource_id = matched.resource_id
                mapping.confidence = self._calculate_confidence(iac, matched)
                matched_resource_ids.add(matched.resource_id)
                iac_mappings.append(mapping)
            else:
                unmatched_iac.append(mapping)

        # Find drift (discovered but not in IaC)
        unmatched_resources: list[CloudResource] = [
            r
            for r in discovery_result.resources
            if r.resource_id not in matched_resource_ids
            # Only track resources that could be in IaC
            and r.resource_type != CloudResourceType.UNKNOWN
        ]

        # Calculate overall confidence
        if iac_mappings:
            avg_confidence = sum(m.confidence for m in iac_mappings) / len(iac_mappings)
        else:
            avg_confidence = 0.0

        return CorrelationResult(
            repository_id=repository_id,
            iac_mappings=iac_mappings,
            unmatched_iac=unmatched_iac,
            unmatched_resources=unmatched_resources,
            correlation_confidence=avg_confidence,
        )

    def _get_cloud_type(self, resource_type: str) -> CloudResourceType:
        """Map IaC resource type to CloudResourceType.

        Args:
            resource_type: IaC resource type string

        Returns:
            CloudResourceType
        """
        # Try CloudFormation mapping
        if resource_type.startswith("AWS::"):
            return self.CFN_TYPE_MAPPING.get(resource_type, CloudResourceType.UNKNOWN)

        # Try Terraform mapping
        return self.TF_TYPE_MAPPING.get(resource_type, CloudResourceType.UNKNOWN)

    def _find_best_match(
        self,
        iac: IaCResource,
        candidates: list[CloudResource],
    ) -> CloudResource | None:
        """Find best matching discovered resource for IaC resource.

        Matching strategies:
        1. Exact name match via tags
        2. Logical ID in resource name
        3. Property-based matching

        Args:
            iac: IaC resource
            candidates: Candidate discovered resources

        Returns:
            Best matching resource or None
        """
        if not candidates:
            return None

        best_match: CloudResource | None = None
        best_score = 0.0

        for candidate in candidates:
            score = self._calculate_match_score(iac, candidate)
            if score > best_score:
                best_score = score
                best_match = candidate

        # Require minimum confidence
        if best_score >= 0.5:
            return best_match
        return None

    def _calculate_match_score(
        self, iac: IaCResource, resource: CloudResource
    ) -> float:
        """Calculate match score between IaC and discovered resource.

        Args:
            iac: IaC resource
            resource: Discovered resource

        Returns:
            Match score between 0.0 and 1.0
        """
        score = 0.0
        weights = {
            "name_match": 0.4,
            "tag_match": 0.3,
            "property_match": 0.3,
        }

        # Name matching
        logical_lower = iac.logical_id.lower().replace("-", "").replace("_", "")
        resource_lower = resource.name.lower().replace("-", "").replace("_", "")

        if logical_lower == resource_lower:
            score += weights["name_match"]
        elif logical_lower in resource_lower or resource_lower in logical_lower:
            score += weights["name_match"] * 0.5

        # Tag matching (aws:cloudformation:logical-id)
        cfn_logical_id = resource.tags.get("aws:cloudformation:logical-id", "")
        if cfn_logical_id == iac.logical_id:
            score += weights["tag_match"]
        elif iac.logical_id in resource.tags.values():
            score += weights["tag_match"] * 0.5

        # Property matching (basic for now)
        if iac.properties and resource.properties:
            prop_matches = 0
            prop_total = 0

            # Check a few common properties
            for prop_key in ["engine", "runtime", "instance_type"]:
                if prop_key in iac.properties and prop_key in resource.properties:
                    prop_total += 1
                    if str(iac.properties[prop_key]) == str(
                        resource.properties[prop_key]
                    ):
                        prop_matches += 1

            if prop_total > 0:
                score += weights["property_match"] * (prop_matches / prop_total)

        return score

    def _calculate_confidence(self, iac: IaCResource, resource: CloudResource) -> float:
        """Calculate confidence in IaC-to-resource correlation.

        Args:
            iac: IaC resource
            resource: Matched discovered resource

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Start with match score
        confidence = self._calculate_match_score(iac, resource)

        # Boost for CloudFormation tag match (ground truth)
        cfn_logical_id = resource.tags.get("aws:cloudformation:logical-id", "")
        if cfn_logical_id == iac.logical_id:
            confidence = min(1.0, confidence + 0.3)

        # Boost for stack name match
        cfn_stack = resource.tags.get("aws:cloudformation:stack-name", "")
        if cfn_stack:
            confidence = min(1.0, confidence + 0.1)

        return confidence

    def _get_mock_correlation(
        self, repository_id: str, iac_resources: list[IaCResource]
    ) -> CorrelationResult:
        """Get mock correlation result for testing.

        Args:
            repository_id: Repository ID
            iac_resources: IaC resources

        Returns:
            Mock correlation result
        """
        # Create mock mappings for half the resources
        mappings: list[IaCMapping] = []
        unmatched: list[IaCMapping] = []

        for i, iac in enumerate(iac_resources):
            mapping = IaCMapping(
                logical_id=iac.logical_id,
                resource_type=iac.resource_type,
                source_file=iac.source_file,
                source_line=iac.source_line,
            )

            if i % 2 == 0:
                mapping.physical_resource_id = f"arn:aws:mock:::{iac.logical_id}"
                mapping.confidence = 0.85
                mappings.append(mapping)
            else:
                unmatched.append(mapping)

        return CorrelationResult(
            repository_id=repository_id,
            iac_mappings=mappings,
            unmatched_iac=unmatched,
            unmatched_resources=[],
            correlation_confidence=0.85,
        )

    async def get_stack_resources(
        self,
        stack_name: str,
        session: Any,
        region: str = "us-east-1",
    ) -> dict[str, str]:
        """Get CloudFormation stack resources for direct correlation.

        Args:
            stack_name: CloudFormation stack name
            session: boto3 session
            region: AWS region

        Returns:
            Dict mapping logical IDs to physical resource IDs
        """
        cfn = session.client("cloudformation", region_name=region)

        resources: dict[str, str] = {}
        paginator = cfn.get_paginator("list_stack_resources")

        for page in paginator.paginate(StackName=stack_name):
            for resource in page.get("StackResourceSummaries", []):
                logical_id = resource.get("LogicalResourceId", "")
                physical_id = resource.get("PhysicalResourceId", "")
                if logical_id and physical_id:
                    resources[logical_id] = physical_id

        return resources
