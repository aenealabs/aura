"""
Project Aura - Runtime-to-Code Correlator Service

Ingests CloudTrail, GuardDuty, and VPC Flow Log events and correlates them
to Infrastructure as Code definitions and source code via git blame.

Based on ADR-077: Cloud Runtime Security Integration
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .config import RuntimeSecurityConfig, get_runtime_security_config
from .contracts import (
    AWSResource,
    CorrelationResult,
    CorrelationStatus,
    EventType,
    IaCProvider,
    IaCResource,
    ResourceMapping,
    ResourceType,
    RuntimeEvent,
    Severity,
)
from .exceptions import (
    EventParsingError,
)
from .metrics import get_runtime_security_metrics

logger = logging.getLogger(__name__)


# CloudFormation resource type to AWS resource type mapping
CLOUDFORMATION_TYPE_MAP = {
    "AWS::EC2::Instance": ResourceType.EC2_INSTANCE,
    "AWS::EKS::Cluster": ResourceType.EKS_CLUSTER,
    "AWS::EKS::Nodegroup": ResourceType.EKS_NODEGROUP,
    "AWS::Lambda::Function": ResourceType.LAMBDA_FUNCTION,
    "AWS::S3::Bucket": ResourceType.S3_BUCKET,
    "AWS::RDS::DBInstance": ResourceType.RDS_INSTANCE,
    "AWS::IAM::Role": ResourceType.IAM_ROLE,
    "AWS::EC2::SecurityGroup": ResourceType.SECURITY_GROUP,
    "AWS::EC2::VPC": ResourceType.VPC,
    "AWS::ECS::Service": ResourceType.ECS_SERVICE,
    "AWS::DynamoDB::Table": ResourceType.DYNAMODB_TABLE,
}

# Terraform resource type to AWS resource type mapping
TERRAFORM_TYPE_MAP = {
    "aws_instance": ResourceType.EC2_INSTANCE,
    "aws_eks_cluster": ResourceType.EKS_CLUSTER,
    "aws_eks_node_group": ResourceType.EKS_NODEGROUP,
    "aws_lambda_function": ResourceType.LAMBDA_FUNCTION,
    "aws_s3_bucket": ResourceType.S3_BUCKET,
    "aws_db_instance": ResourceType.RDS_INSTANCE,
    "aws_iam_role": ResourceType.IAM_ROLE,
    "aws_security_group": ResourceType.SECURITY_GROUP,
    "aws_vpc": ResourceType.VPC,
    "aws_ecs_service": ResourceType.ECS_SERVICE,
    "aws_dynamodb_table": ResourceType.DYNAMODB_TABLE,
}


class RuntimeCorrelator:
    """
    Correlates runtime events to source code via IaC mappings.

    Correlation Chain:
    1. Runtime Event → AWS Resource ARN
    2. AWS Resource → IaC Resource Definition (Terraform/CloudFormation)
    3. IaC Resource → Git File Path
    4. Git File → Git Blame → Developer Attribution
    5. Developer → Neptune Code Graph → Related Vulnerabilities
    """

    def __init__(self, config: Optional[RuntimeSecurityConfig] = None):
        """Initialize runtime correlator with configuration."""
        self._config = config or get_runtime_security_config()
        self._metrics = get_runtime_security_metrics()
        self._resource_cache: dict[str, ResourceMapping] = {}
        self._terraform_state: dict[str, dict[str, Any]] = {}
        self._cloudformation_resources: dict[str, dict[str, Any]] = {}
        self._events: dict[str, RuntimeEvent] = {}

    def ingest_cloudtrail_event(self, raw_event: dict[str, Any]) -> RuntimeEvent:
        """
        Parse and ingest a CloudTrail event.

        Args:
            raw_event: Raw CloudTrail event JSON

        Returns:
            Parsed RuntimeEvent
        """
        try:
            event_id = raw_event.get("eventID", str(uuid.uuid4()))
            event_name = raw_event.get("eventName", "Unknown")
            event_source = raw_event.get("eventSource", "unknown.amazonaws.com")
            event_time = raw_event.get(
                "eventTime", datetime.now(timezone.utc).isoformat()
            )
            aws_region = raw_event.get("awsRegion", "us-east-1")
            account_id = raw_event.get("recipientAccountId", "")

            # Parse timestamp
            if isinstance(event_time, str):
                timestamp = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            else:
                timestamp = datetime.now(timezone.utc)

            # Extract resource ARN from request/response
            resource_arn = self._extract_resource_arn(raw_event)

            # Determine severity based on event type
            severity = self._classify_cloudtrail_severity(event_name, raw_event)

            # Build description
            user_identity = raw_event.get("userIdentity", {})
            principal = user_identity.get(
                "arn", user_identity.get("principalId", "unknown")
            )
            description = f"{event_name} by {principal} via {event_source}"

            event = RuntimeEvent(
                event_id=f"ct-{event_id}",
                event_type=EventType.CLOUDTRAIL,
                severity=severity,
                aws_account_id=account_id,
                region=aws_region,
                timestamp=timestamp,
                resource_arn=resource_arn,
                description=description,
                raw_event=raw_event,
            )

            self._events[event.event_id] = event
            self._metrics.record_event_ingested(
                event_type=EventType.CLOUDTRAIL.value,
                severity=severity.name,
            )

            return event

        except Exception as e:
            logger.error(f"Failed to parse CloudTrail event: {e}")
            raise EventParsingError(f"CloudTrail parsing failed: {e}")

    def ingest_guardduty_finding(self, raw_finding: dict[str, Any]) -> RuntimeEvent:
        """
        Parse and ingest a GuardDuty finding.

        Args:
            raw_finding: Raw GuardDuty finding JSON

        Returns:
            Parsed RuntimeEvent
        """
        try:
            finding_id = raw_finding.get("Id", str(uuid.uuid4()))
            finding_type = raw_finding.get("Type", "Unknown")
            severity_value = raw_finding.get("Severity", 5)
            account_id = raw_finding.get("AccountId", "")
            region = raw_finding.get("Region", "us-east-1")
            created_at = raw_finding.get(
                "CreatedAt", datetime.now(timezone.utc).isoformat()
            )

            # Parse timestamp
            if isinstance(created_at, str):
                timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                timestamp = datetime.now(timezone.utc)

            # Extract resource ARN
            resource = raw_finding.get("Resource", {})
            resource_arn = resource.get("ResourceType", None)
            if resource.get("InstanceDetails"):
                resource_arn = resource["InstanceDetails"].get("InstanceId")

            # Map GuardDuty severity (0-10) to our severity enum
            if severity_value >= 8:
                severity = Severity.CRITICAL
            elif severity_value >= 6:
                severity = Severity.HIGH
            elif severity_value >= 4:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            # Build description
            description = raw_finding.get("Title", finding_type)

            event = RuntimeEvent(
                event_id=f"gd-{finding_id}",
                event_type=EventType.GUARDDUTY,
                severity=severity,
                aws_account_id=account_id,
                region=region,
                timestamp=timestamp,
                resource_arn=resource_arn,
                description=description,
                raw_event=raw_finding,
            )

            self._events[event.event_id] = event
            self._metrics.record_event_ingested(
                event_type=EventType.GUARDDUTY.value,
                severity=severity.name,
            )

            return event

        except Exception as e:
            logger.error(f"Failed to parse GuardDuty finding: {e}")
            raise EventParsingError(f"GuardDuty parsing failed: {e}")

    def ingest_vpc_flow_log(self, raw_log: dict[str, Any]) -> RuntimeEvent:
        """
        Parse and ingest a VPC Flow Log event.

        Args:
            raw_log: Parsed VPC Flow Log record

        Returns:
            Parsed RuntimeEvent
        """
        try:
            # VPC Flow Log fields
            account_id = raw_log.get("account-id", "")
            interface_id = raw_log.get("interface-id", "")
            src_addr = raw_log.get("srcaddr", "")
            dst_addr = raw_log.get("dstaddr", "")
            src_port = raw_log.get("srcport", 0)
            dst_port = raw_log.get("dstport", 0)
            protocol = raw_log.get("protocol", "")
            action = raw_log.get("action", "")
            _log_status = raw_log.get("log-status", "")  # Reserved for future use
            region = raw_log.get("region", "us-east-1")

            # Generate event ID
            event_id = hashlib.sha256(
                f"{interface_id}-{src_addr}-{dst_addr}-{src_port}-{dst_port}".encode()
            ).hexdigest()[:16]

            timestamp = datetime.now(timezone.utc)
            if raw_log.get("start"):
                timestamp = datetime.fromtimestamp(
                    int(raw_log["start"]), tz=timezone.utc
                )

            # Determine severity based on action
            if action == "REJECT":
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            description = (
                f"Flow {action}: {src_addr}:{src_port} -> {dst_addr}:{dst_port} "
                f"(protocol: {protocol}, interface: {interface_id})"
            )

            event = RuntimeEvent(
                event_id=f"vf-{event_id}",
                event_type=EventType.VPC_FLOW,
                severity=severity,
                aws_account_id=account_id,
                region=region,
                timestamp=timestamp,
                resource_arn=interface_id,  # ENI ID
                description=description,
                raw_event=raw_log,
            )

            self._events[event.event_id] = event
            self._metrics.record_event_ingested(
                event_type=EventType.VPC_FLOW.value,
                severity=severity.name,
            )

            return event

        except Exception as e:
            logger.error(f"Failed to parse VPC Flow Log: {e}")
            raise EventParsingError(f"VPC Flow Log parsing failed: {e}")

    def correlate(self, event: RuntimeEvent) -> CorrelationResult:
        """
        Correlate a runtime event to source code.

        Args:
            event: The runtime event to correlate

        Returns:
            CorrelationResult with the correlation chain
        """
        with self._metrics.time_operation("CorrelationLatency"):
            try:
                correlation_chain: list[str] = []

                # Step 1: Get AWS resource from ARN
                aws_resource = None
                if event.resource_arn:
                    aws_resource = self._get_aws_resource(event.resource_arn)
                    if aws_resource:
                        correlation_chain.append(f"AWS Resource: {aws_resource.name}")

                if not aws_resource:
                    return CorrelationResult(
                        event_id=event.event_id,
                        status=CorrelationStatus.PARTIAL,
                        confidence=0.3,
                        correlation_chain=correlation_chain,
                        error_message="Could not identify AWS resource from event",
                    )

                # Step 2: Map to IaC resource
                iac_resource = self._map_to_iac(aws_resource)
                if iac_resource:
                    correlation_chain.append(
                        f"IaC Resource: {iac_resource.file_path}:{iac_resource.line_number}"
                    )

                if not iac_resource:
                    return CorrelationResult(
                        event_id=event.event_id,
                        status=CorrelationStatus.PARTIAL,
                        aws_resource=aws_resource,
                        confidence=0.5,
                        correlation_chain=correlation_chain,
                        error_message="Could not map resource to IaC definition",
                    )

                # Step 3: Get git blame attribution
                git_blame_author = None
                git_commit = None
                if iac_resource.file_path:
                    blame_result = self._git_blame(
                        iac_resource.file_path, iac_resource.line_number
                    )
                    if blame_result:
                        git_blame_author = blame_result.get("author")
                        git_commit = blame_result.get("commit")
                        correlation_chain.append(
                            f"Git Blame: {git_blame_author} ({git_commit[:7]})"
                        )

                # Update event with correlation data
                event.correlation_status = CorrelationStatus.CORRELATED
                event.code_path = iac_resource.file_path
                event.code_owner = git_blame_author

                result = CorrelationResult(
                    event_id=event.event_id,
                    status=CorrelationStatus.CORRELATED,
                    aws_resource=aws_resource,
                    iac_resource=iac_resource,
                    code_file=iac_resource.file_path,
                    code_line_start=iac_resource.line_number,
                    code_line_end=iac_resource.line_number + 20,  # Estimate
                    git_blame_author=git_blame_author,
                    git_commit=git_commit,
                    confidence=0.95 if git_blame_author else 0.8,
                    correlation_chain=correlation_chain,
                )

                self._metrics.record_correlation_result(
                    status=result.status.value,
                    event_type=event.event_type.value,
                )

                return result

            except Exception as e:
                logger.error(f"Correlation failed for event {event.event_id}: {e}")
                return CorrelationResult(
                    event_id=event.event_id,
                    status=CorrelationStatus.FAILED,
                    confidence=0.0,
                    error_message=str(e),
                )

    def get_event(self, event_id: str) -> Optional[RuntimeEvent]:
        """Get an event by ID."""
        return self._events.get(event_id)

    def register_terraform_state(self, state_data: dict[str, Any]) -> int:
        """
        Register Terraform state for resource mapping.

        Args:
            state_data: Parsed terraform.tfstate content

        Returns:
            Number of resources registered
        """
        count = 0
        resources = state_data.get("resources", [])

        for resource in resources:
            resource_type = resource.get("type", "")
            resource_name = resource.get("name", "")
            module = resource.get("module", "")

            for instance in resource.get("instances", []):
                attributes = instance.get("attributes", {})
                arn = attributes.get("arn") or attributes.get("id")

                if arn:
                    state_key = (
                        f"{module}.{resource_type}.{resource_name}"
                        if module
                        else f"{resource_type}.{resource_name}"
                    )
                    self._terraform_state[arn] = {
                        "state_key": state_key,
                        "resource_type": resource_type,
                        "resource_name": resource_name,
                        "module": module,
                        "attributes": attributes,
                    }
                    count += 1

        logger.info(f"Registered {count} resources from Terraform state")
        return count

    def register_cloudformation_resources(
        self, template_path: str, resources: dict[str, Any]
    ) -> int:
        """
        Register CloudFormation resources for mapping.

        Args:
            template_path: Path to the CloudFormation template
            resources: Physical resource IDs from stack

        Returns:
            Number of resources registered
        """
        count = 0
        for logical_id, physical_id in resources.items():
            if physical_id:
                self._cloudformation_resources[physical_id] = {
                    "logical_id": logical_id,
                    "template_path": template_path,
                }
                count += 1

        logger.info(
            f"Registered {count} resources from CloudFormation template {template_path}"
        )
        return count

    def add_resource_mapping(self, mapping: ResourceMapping) -> None:
        """Add a manual resource mapping."""
        self._resource_cache[mapping.aws_resource_arn] = mapping

    def _extract_resource_arn(self, cloudtrail_event: dict[str, Any]) -> Optional[str]:
        """Extract resource ARN from CloudTrail event."""
        # Check common locations for ARN
        resources = cloudtrail_event.get("resources", [])
        if resources:
            return resources[0].get("ARN")

        request_params = cloudtrail_event.get("requestParameters", {})
        response = cloudtrail_event.get("responseElements", {})

        # Check request parameters
        for key in [
            "instanceId",
            "bucketName",
            "functionName",
            "roleArn",
            "clusterName",
        ]:
            if key in request_params:
                return request_params[key]

        # Check response elements
        if response:
            # Handle instancesSet with nested items structure
            instances_set = response.get("instancesSet", {})
            if isinstance(instances_set, dict):
                items = instances_set.get("items", [])
                if items and isinstance(items, list):
                    return items[0].get("instanceId")

            # Handle other response structures
            for key in ["function", "role", "cluster"]:
                if key in response:
                    item = response[key]
                    if isinstance(item, dict):
                        return (
                            item.get("instanceId")
                            or item.get("functionArn")
                            or item.get("arn")
                        )
                    elif isinstance(item, list) and item:
                        return item[0].get("instanceId")

        return None

    def _classify_cloudtrail_severity(
        self, event_name: str, event: dict[str, Any]
    ) -> Severity:
        """Classify CloudTrail event severity."""
        # High-risk events
        critical_patterns = [
            "DeleteBucket",
            "DeleteCluster",
            "DeleteDBInstance",
            "DeleteTable",
            "PutBucketPolicy",
            "CreateAccessKey",
            "AssumeRole",
            "ConsoleLogin",
        ]

        high_patterns = [
            "CreateUser",
            "AttachUserPolicy",
            "AttachRolePolicy",
            "UpdateFunctionCode",
            "ModifyInstanceAttribute",
            "AuthorizeSecurityGroupIngress",
        ]

        for pattern in critical_patterns:
            if pattern.lower() in event_name.lower():
                return Severity.CRITICAL

        for pattern in high_patterns:
            if pattern.lower() in event_name.lower():
                return Severity.HIGH

        # Check for errors
        error_code = event.get("errorCode")
        if error_code:
            if "AccessDenied" in error_code or "Unauthorized" in error_code:
                return Severity.MEDIUM

        return Severity.LOW

    def _get_aws_resource(self, arn_or_id: str) -> Optional[AWSResource]:
        """Get AWS resource details from ARN or ID."""
        # Parse ARN to get resource type
        resource_type = ResourceType.UNKNOWN
        name = arn_or_id
        account_id = ""
        region = ""

        if arn_or_id.startswith("arn:"):
            parts = arn_or_id.split(":")
            if len(parts) >= 6:
                _partition = parts[1]  # Available for GovCloud detection
                service = parts[2]
                region = parts[3]
                account_id = parts[4]
                resource_part = ":".join(parts[5:])

                # Determine resource type from service
                service_type_map = {
                    "ec2": ResourceType.EC2_INSTANCE,
                    "eks": ResourceType.EKS_CLUSTER,
                    "lambda": ResourceType.LAMBDA_FUNCTION,
                    "s3": ResourceType.S3_BUCKET,
                    "rds": ResourceType.RDS_INSTANCE,
                    "iam": ResourceType.IAM_ROLE,
                    "dynamodb": ResourceType.DYNAMODB_TABLE,
                }
                resource_type = service_type_map.get(service, ResourceType.UNKNOWN)
                name = (
                    resource_part.split("/")[-1]
                    if "/" in resource_part
                    else resource_part
                )

        # Check if it's an instance ID
        elif arn_or_id.startswith("i-"):
            resource_type = ResourceType.EC2_INSTANCE
            name = arn_or_id

        return AWSResource(
            resource_arn=arn_or_id,
            resource_type=resource_type,
            name=name,
            aws_account_id=account_id,
            region=region,
            last_seen=datetime.now(timezone.utc),
        )

    def _map_to_iac(self, resource: AWSResource) -> Optional[IaCResource]:
        """Map AWS resource to IaC definition."""
        # Check cache first
        if resource.resource_arn in self._resource_cache:
            mapping = self._resource_cache[resource.resource_arn]
            return IaCResource(
                iac_resource_id=mapping.iac_resource_id,
                resource_type=resource.resource_type.value,
                provider=mapping.iac_provider,
                file_path=mapping.iac_file_path,
                line_number=1,  # Would need to parse file to get exact line
                git_commit=mapping.git_commit,
            )

        # Check Terraform state
        if resource.resource_arn in self._terraform_state:
            tf_resource = self._terraform_state[resource.resource_arn]
            return IaCResource(
                iac_resource_id=tf_resource["state_key"],
                resource_type=tf_resource["resource_type"],
                provider=IaCProvider.TERRAFORM,
                file_path=f"terraform/{tf_resource['module'] or 'main'}.tf",
                line_number=1,
                module=tf_resource.get("module"),
                resource_name=tf_resource["resource_name"],
            )

        # Check CloudFormation resources
        if resource.resource_arn in self._cloudformation_resources:
            cfn_resource = self._cloudformation_resources[resource.resource_arn]
            return IaCResource(
                iac_resource_id=cfn_resource["logical_id"],
                resource_type=resource.resource_type.value,
                provider=IaCProvider.CLOUDFORMATION,
                file_path=cfn_resource["template_path"],
                line_number=1,
                resource_name=cfn_resource["logical_id"],
            )

        # Mock mode - simulate IaC mapping
        if self._config.storage.use_mock_storage:
            return IaCResource(
                iac_resource_id=f"mock-{resource.name}",
                resource_type=resource.resource_type.value,
                provider=IaCProvider.CLOUDFORMATION,
                file_path=f"deploy/cloudformation/{resource.resource_type.value.lower().replace('::', '-')}.yaml",
                line_number=42,
                resource_name=resource.name,
            )

        return None

    def _git_blame(self, file_path: str, line_number: int) -> Optional[dict[str, Any]]:
        """
        Get git blame information for a file line.

        In production, this would run `git blame` on the file.
        For mock mode, returns simulated data.
        """
        if self._config.storage.use_mock_storage:
            return {
                "author": "developer@aenealabs.com",
                "commit": "abc123def456",
                "date": datetime.now(timezone.utc).isoformat(),
                "summary": "Infrastructure update",
            }

        # Would run git blame here
        # subprocess.run(["git", "blame", "-L", f"{line_number},{line_number}", file_path])
        return None


# Singleton instance
_correlator_instance: Optional[RuntimeCorrelator] = None


def get_runtime_correlator() -> RuntimeCorrelator:
    """Get singleton runtime correlator instance."""
    global _correlator_instance
    if _correlator_instance is None:
        _correlator_instance = RuntimeCorrelator()
    return _correlator_instance


def reset_runtime_correlator() -> None:
    """Reset runtime correlator singleton (for testing)."""
    global _correlator_instance
    _correlator_instance = None
