"""
Project Aura - Security Telemetry Service

Queries AWS security services for real-time threat intelligence:
- GuardDuty: Active threat findings (malware, unauthorized access, etc.)
- CloudWatch Logs: WAF events, CloudTrail anomalies
- VPC Flow Logs: Network anomaly patterns

This service replaces mock data in ThreatIntelligenceAgent._analyze_internal_telemetry()
with real AWS security telemetry.

Compliance:
- CMMC Level 3: SI-4 (Information System Monitoring)
- NIST 800-53: SI-4, AU-6 (Audit Review)
- SOX: Continuous monitoring requirements
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_guardduty.client import GuardDutyClient
    from mypy_boto3_logs.client import CloudWatchLogsClient

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class TelemetryMode(Enum):
    """Operating mode for the telemetry service."""

    AWS = "aws"  # Real AWS API calls
    MOCK = "mock"  # Local testing without AWS


class FindingSeverity(Enum):
    """GuardDuty finding severity levels."""

    CRITICAL = "critical"  # 8.0-10.0 (immediate action)
    HIGH = "high"  # 7.0-7.9 (urgent)
    MEDIUM = "medium"  # 4.0-6.9 (attention needed)
    LOW = "low"  # 1.0-3.9 (informational)
    INFORMATIONAL = "informational"  # 0.0-0.9


class FindingType(Enum):
    """Types of security findings."""

    GUARDDUTY = "guardduty"
    WAF_EVENT = "waf_event"
    CLOUDTRAIL_ANOMALY = "cloudtrail_anomaly"
    VPC_FLOW_ANOMALY = "vpc_flow_anomaly"
    APPLICATION_ERROR = "application_error"


@dataclass
class SecurityFinding:
    """Structured security finding from AWS services."""

    id: str
    finding_type: FindingType
    severity: FindingSeverity
    title: str
    description: str
    detected_at: datetime
    source_service: str
    affected_resources: list[str] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "finding_type": self.finding_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "source_service": self.source_service,
            "affected_resources": self.affected_resources,
            "indicators": self.indicators,
            "recommended_actions": self.recommended_actions,
        }


@dataclass
class TelemetryConfig:
    """Configuration for security telemetry service."""

    # Time window for queries
    lookback_hours: int = 24

    # GuardDuty settings
    guardduty_enabled: bool = True
    guardduty_min_severity: float = 4.0  # MEDIUM and above

    # WAF log settings
    waf_logs_enabled: bool = True
    waf_log_group: str = ""  # Auto-detected if empty

    # CloudTrail settings
    cloudtrail_enabled: bool = True
    cloudtrail_log_group: str = ""  # Auto-detected if empty

    # Limits
    max_findings_per_source: int = 100


# =============================================================================
# Security Telemetry Service
# =============================================================================


class SecurityTelemetryService:
    """
    Queries AWS security services for real-time threat intelligence.

    Integrates with:
    - GuardDuty: Threat detection findings
    - CloudWatch Logs Insights: WAF and CloudTrail events
    - VPC Flow Logs: Network anomalies

    Usage:
        service = SecurityTelemetryService(mode=TelemetryMode.AWS)
        findings = await service.get_security_findings()

        # Filter by type
        guardduty_findings = await service.get_guardduty_findings()
        waf_events = await service.get_waf_events()
    """

    def __init__(
        self,
        mode: TelemetryMode = TelemetryMode.MOCK,
        config: TelemetryConfig | None = None,
        region: str | None = None,
    ):
        """Initialize security telemetry service.

        Args:
            mode: AWS or MOCK mode
            config: Telemetry configuration
            region: AWS region (defaults to environment or us-east-1)
        """
        self.mode = mode
        self.config = config or TelemetryConfig()
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        # Initialize AWS clients in AWS mode
        self._guardduty_client: "GuardDutyClient | None" = None
        self._logs_client: "CloudWatchLogsClient | None" = None
        self._detector_id: str | None = None

        if self.mode == TelemetryMode.AWS:
            self._init_aws_clients()

        # Cache for detector ID
        self._detector_id_cache: str | None = None

        logger.info(f"SecurityTelemetryService initialized in {mode.value} mode")

    def _init_aws_clients(self) -> None:
        """Initialize AWS service clients."""
        try:
            self._guardduty_client = boto3.client("guardduty", region_name=self.region)
            self._logs_client = boto3.client("logs", region_name=self.region)
            logger.info("AWS clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            raise

    async def get_security_findings(
        self,
        finding_types: list[FindingType] | None = None,
        min_severity: FindingSeverity | None = None,
    ) -> list[SecurityFinding]:
        """Get all security findings from enabled sources.

        Args:
            finding_types: Filter by finding types (None = all enabled)
            min_severity: Minimum severity to include

        Returns:
            List of security findings from all sources
        """
        findings: list[SecurityFinding] = []

        # Determine which sources to query
        types_to_query = finding_types or [
            FindingType.GUARDDUTY,
            FindingType.WAF_EVENT,
            FindingType.CLOUDTRAIL_ANOMALY,
        ]

        # Query each source concurrently
        tasks = []
        if FindingType.GUARDDUTY in types_to_query and self.config.guardduty_enabled:
            tasks.append(self.get_guardduty_findings())
        if FindingType.WAF_EVENT in types_to_query and self.config.waf_logs_enabled:
            tasks.append(self.get_waf_events())
        if (
            FindingType.CLOUDTRAIL_ANOMALY in types_to_query
            and self.config.cloudtrail_enabled
        ):
            tasks.append(self.get_cloudtrail_anomalies())

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error querying security source: {result}")
                elif isinstance(result, list):
                    findings.extend(result)

        # Filter by severity if specified
        if min_severity:
            severity_order = [
                FindingSeverity.INFORMATIONAL,
                FindingSeverity.LOW,
                FindingSeverity.MEDIUM,
                FindingSeverity.HIGH,
                FindingSeverity.CRITICAL,
            ]
            min_index = severity_order.index(min_severity)
            findings = [
                f for f in findings if severity_order.index(f.severity) >= min_index
            ]

        # Sort by severity (critical first) then by time
        severity_priority = {
            FindingSeverity.CRITICAL: 0,
            FindingSeverity.HIGH: 1,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.LOW: 3,
            FindingSeverity.INFORMATIONAL: 4,
        }
        findings.sort(
            key=lambda f: (severity_priority[f.severity], -f.detected_at.timestamp())
        )

        return findings

    async def get_guardduty_findings(self) -> list[SecurityFinding]:
        """Get active GuardDuty findings.

        Returns:
            List of GuardDuty findings as SecurityFinding objects
        """
        if self.mode == TelemetryMode.MOCK:
            return self._get_mock_guardduty_findings()

        if self._guardduty_client is None:
            logger.error("GuardDuty client not initialized")
            return []

        findings: list[SecurityFinding] = []

        try:
            # Get detector ID
            detector_id = await self._get_detector_id()
            if not detector_id:
                logger.warning("No GuardDuty detector found")
                return []

            # Calculate time window
            start_time = datetime.now(timezone.utc) - timedelta(
                hours=self.config.lookback_hours
            )

            # List findings with severity filter
            finding_criteria = {
                "Criterion": {
                    "severity": {
                        "Gte": int(self.config.guardduty_min_severity),
                    },
                    "updatedAt": {
                        "Gte": int(start_time.timestamp() * 1000),
                    },
                }
            }

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._guardduty_client.list_findings(  # type: ignore[union-attr]
                    DetectorId=detector_id,
                    FindingCriteria=finding_criteria,
                    MaxResults=min(50, self.config.max_findings_per_source),
                ),
            )

            finding_ids = response.get("FindingIds", [])
            if not finding_ids:
                logger.info("No GuardDuty findings in time window")
                return []

            # Get finding details
            details_response = await loop.run_in_executor(
                None,
                lambda: self._guardduty_client.get_findings(  # type: ignore[union-attr]
                    DetectorId=detector_id,
                    FindingIds=finding_ids,
                ),
            )

            # Convert to SecurityFinding objects
            for finding in details_response.get("Findings", []):
                security_finding = self._parse_guardduty_finding(finding)
                if security_finding:
                    findings.append(security_finding)

            logger.info(f"Retrieved {len(findings)} GuardDuty findings")

        except ClientError as e:
            logger.error(f"GuardDuty API error: {e}")
        except Exception as e:
            logger.error(f"Error getting GuardDuty findings: {e}")

        return findings

    async def _get_detector_id(self) -> str | None:
        """Get the GuardDuty detector ID for the account.

        Returns:
            Detector ID or None if not found
        """
        if self._detector_id_cache:
            return self._detector_id_cache

        if self._guardduty_client is None:
            logger.error("GuardDuty client not initialized")
            return None

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, self._guardduty_client.list_detectors
            )
            detector_ids = response.get("DetectorIds", [])
            if detector_ids:
                self._detector_id_cache = detector_ids[0]
                return self._detector_id_cache
        except Exception as e:
            logger.error(f"Error getting detector ID: {e}")

        return None

    def _parse_guardduty_finding(self, finding: dict) -> SecurityFinding | None:
        """Parse a GuardDuty finding into SecurityFinding.

        Args:
            finding: Raw GuardDuty finding data

        Returns:
            SecurityFinding object or None if parsing fails
        """
        try:
            # Map severity score to enum
            severity_score = finding.get("Severity", 0)
            if severity_score >= 8.0:
                severity = FindingSeverity.CRITICAL
            elif severity_score >= 7.0:
                severity = FindingSeverity.HIGH
            elif severity_score >= 4.0:
                severity = FindingSeverity.MEDIUM
            elif severity_score >= 1.0:
                severity = FindingSeverity.LOW
            else:
                severity = FindingSeverity.INFORMATIONAL

            # Extract affected resources
            resource = finding.get("Resource", {})
            affected = []
            if "InstanceDetails" in resource:
                instance = resource["InstanceDetails"]
                affected.append(f"EC2: {instance.get('InstanceId', 'unknown')}")
            if "S3BucketDetails" in resource:
                for bucket in resource["S3BucketDetails"]:
                    affected.append(f"S3: {bucket.get('Name', 'unknown')}")
            if "EksClusterDetails" in resource:
                cluster = resource["EksClusterDetails"]
                affected.append(f"EKS: {cluster.get('Name', 'unknown')}")

            # Extract indicators of compromise
            indicators = []
            service = finding.get("Service", {})
            action = service.get("Action", {})

            # Network connection indicators
            if "NetworkConnectionAction" in action:
                conn = action["NetworkConnectionAction"]
                if "RemoteIpDetails" in conn:
                    ip = conn["RemoteIpDetails"].get("IpAddressV4", "unknown")
                    indicators.append(f"Remote IP: {ip}")
                if "LocalPortDetails" in conn:
                    port = conn["LocalPortDetails"].get("Port", "unknown")
                    indicators.append(f"Local Port: {port}")

            # AWS API call indicators
            if "AwsApiCallAction" in action:
                api = action["AwsApiCallAction"]
                indicators.append(f"API: {api.get('Api', 'unknown')}")
                if "RemoteIpDetails" in api:
                    ip = api["RemoteIpDetails"].get("IpAddressV4", "unknown")
                    indicators.append(f"Caller IP: {ip}")

            # Build recommended actions based on finding type
            finding_type = finding.get("Type", "")
            actions = self._get_guardduty_recommendations(finding_type)

            return SecurityFinding(
                id=finding.get("Id", "unknown"),
                finding_type=FindingType.GUARDDUTY,
                severity=severity,
                title=finding.get("Title", "Unknown GuardDuty Finding"),
                description=finding.get("Description", ""),
                detected_at=datetime.fromisoformat(
                    finding.get(
                        "UpdatedAt", datetime.now(timezone.utc).isoformat()
                    ).replace("Z", "+00:00")
                ),
                source_service="GuardDuty",
                affected_resources=affected,
                indicators=indicators,
                recommended_actions=actions,
                raw_data=finding,
            )
        except Exception as e:
            logger.error(f"Error parsing GuardDuty finding: {e}")
            return None

    def _get_guardduty_recommendations(self, finding_type: str) -> list[str]:
        """Get recommended actions for a GuardDuty finding type.

        Args:
            finding_type: GuardDuty finding type string

        Returns:
            List of recommended actions
        """
        recommendations = {
            "UnauthorizedAccess": [
                "Review IAM policies for excessive permissions",
                "Enable MFA for affected users/roles",
                "Rotate compromised credentials immediately",
                "Check CloudTrail for unauthorized API calls",
            ],
            "Trojan": [
                "Isolate affected instance immediately",
                "Capture forensic image before termination",
                "Scan related resources for lateral movement",
                "Review security group rules",
            ],
            "Backdoor": [
                "Terminate affected instance",
                "Audit all instances launched from same AMI",
                "Review instance launch permissions",
                "Check for persistence mechanisms",
            ],
            "CryptoCurrency": [
                "Terminate mining instance",
                "Review cost anomalies in billing",
                "Check for compromised credentials",
                "Audit instance launch history",
            ],
            "Recon": [
                "Review security group ingress rules",
                "Consider implementing AWS Network Firewall",
                "Enable VPC Flow Logs if not already",
                "Block source IP at WAF/Security Group level",
            ],
        }

        # Match finding type prefix
        for prefix, actions in recommendations.items():
            if prefix in finding_type:
                return actions

        # Default recommendations
        return [
            "Review finding details in GuardDuty console",
            "Investigate affected resources",
            "Consider enabling additional AWS security services",
            "Document incident for compliance",
        ]

    async def get_waf_events(self) -> list[SecurityFinding]:
        """Get WAF blocked requests from CloudWatch Logs.

        Returns:
            List of WAF events as SecurityFinding objects
        """
        if self.mode == TelemetryMode.MOCK:
            return self._get_mock_waf_events()

        if self._logs_client is None:
            logger.error("CloudWatch Logs client not initialized")
            return []

        findings: list[SecurityFinding] = []

        try:
            # Determine WAF log group
            log_group = (
                self.config.waf_log_group
                or f"aws-waf-logs-aura-{os.environ.get('ENVIRONMENT', 'dev')}"
            )

            # Check if log group exists
            loop = asyncio.get_event_loop()
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self._logs_client.describe_log_groups(  # type: ignore[union-attr]
                        logGroupNamePrefix=log_group, limit=1
                    ),
                )
            except ClientError:
                logger.info(f"WAF log group {log_group} not found")
                return []

            # Query for blocked requests
            start_time = datetime.now(timezone.utc) - timedelta(
                hours=self.config.lookback_hours
            )

            query = """
            fields @timestamp, @message, action, terminatingRuleId,
                   httpRequest.clientIp, httpRequest.uri, httpRequest.httpMethod
            | filter action = 'BLOCK'
            | sort @timestamp desc
            | limit 100
            """

            # Start query
            start_response = await loop.run_in_executor(
                None,
                lambda: self._logs_client.start_query(  # type: ignore[union-attr]
                    logGroupName=log_group,
                    startTime=int(start_time.timestamp()),
                    endTime=int(datetime.now(timezone.utc).timestamp()),
                    queryString=query,
                ),
            )

            query_id = start_response["queryId"]

            # Wait for query to complete (with timeout)
            for _ in range(30):  # Max 30 seconds
                await asyncio.sleep(1)
                result = await loop.run_in_executor(
                    None,
                    lambda: self._logs_client.get_query_results(queryId=query_id),  # type: ignore[union-attr]
                )
                if result["status"] == "Complete":
                    break

            # Parse results
            for record in result.get("results", [])[
                : self.config.max_findings_per_source
            ]:
                finding = self._parse_waf_event(record)
                if finding:
                    findings.append(finding)

            logger.info(f"Retrieved {len(findings)} WAF events")

        except ClientError as e:
            logger.error(f"CloudWatch Logs API error: {e}")
        except Exception as e:
            logger.error(f"Error getting WAF events: {e}")

        return findings

    def _parse_waf_event(self, record: list[dict]) -> SecurityFinding | None:
        """Parse a WAF log record into SecurityFinding.

        Args:
            record: CloudWatch Logs Insights result record

        Returns:
            SecurityFinding object or None
        """
        try:
            # Extract fields from result
            fields = {item["field"]: item["value"] for item in record}

            timestamp_str = fields.get("@timestamp", "")
            client_ip = fields.get("httpRequest.clientIp", "unknown")
            uri = fields.get("httpRequest.uri", "/")
            method = fields.get("httpRequest.httpMethod", "GET")
            rule = fields.get("terminatingRuleId", "unknown")

            # Determine severity based on rule
            severity = FindingSeverity.MEDIUM
            if "SQL" in rule or "XSS" in rule:
                severity = FindingSeverity.HIGH
            elif "Rate" in rule:
                severity = FindingSeverity.LOW

            return SecurityFinding(
                id=f"waf-{hash(f'{timestamp_str}-{client_ip}')}",
                finding_type=FindingType.WAF_EVENT,
                severity=severity,
                title=f"WAF Blocked: {rule}",
                description=f"WAF blocked {method} request to {uri} from {client_ip}",
                detected_at=(
                    datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if timestamp_str
                    else datetime.now(timezone.utc)
                ),
                source_service="AWS WAF",
                affected_resources=[uri],
                indicators=[f"Source IP: {client_ip}", f"Rule: {rule}"],
                recommended_actions=[
                    "Review WAF rule effectiveness",
                    "Consider IP-based blocking if pattern continues",
                    "Check for related attack patterns",
                ],
                raw_data=fields,
            )
        except Exception as e:
            logger.error(f"Error parsing WAF event: {e}")
            return None

    async def get_cloudtrail_anomalies(self) -> list[SecurityFinding]:
        """Get CloudTrail anomalies from CloudWatch Logs.

        Returns:
            List of CloudTrail anomalies as SecurityFinding objects
        """
        if self.mode == TelemetryMode.MOCK:
            return self._get_mock_cloudtrail_anomalies()

        if self._logs_client is None:
            logger.error("CloudWatch Logs client not initialized")
            return []

        findings: list[SecurityFinding] = []

        try:
            # Determine CloudTrail log group
            log_group = (
                self.config.cloudtrail_log_group
                or f"aura-cloudtrail-{os.environ.get('ENVIRONMENT', 'dev')}"
            )

            loop = asyncio.get_event_loop()

            # Query for suspicious API calls
            start_time = datetime.now(timezone.utc) - timedelta(
                hours=self.config.lookback_hours
            )

            # Look for error events and sensitive API calls
            query = """
            fields @timestamp, eventName, errorCode, errorMessage,
                   userIdentity.arn, sourceIPAddress, awsRegion
            | filter errorCode like /AccessDenied|Unauthorized|Invalid/
                or eventName like /Delete|Terminate|Create.*User|Attach.*Policy/
            | sort @timestamp desc
            | limit 50
            """

            try:
                start_response = await loop.run_in_executor(
                    None,
                    lambda: self._logs_client.start_query(  # type: ignore[union-attr]
                        logGroupName=log_group,
                        startTime=int(start_time.timestamp()),
                        endTime=int(datetime.now(timezone.utc).timestamp()),
                        queryString=query,
                    ),
                )
            except ClientError as e:
                if "ResourceNotFoundException" in str(e):
                    logger.info(f"CloudTrail log group {log_group} not found")
                    return []
                raise

            query_id = start_response["queryId"]

            # Wait for query completion
            for _ in range(30):
                await asyncio.sleep(1)
                result = await loop.run_in_executor(
                    None,
                    lambda: self._logs_client.get_query_results(queryId=query_id),  # type: ignore[union-attr]
                )
                if result["status"] == "Complete":
                    break

            # Parse results
            for record in result.get("results", [])[
                : self.config.max_findings_per_source
            ]:
                finding = self._parse_cloudtrail_event(record)
                if finding:
                    findings.append(finding)

            logger.info(f"Retrieved {len(findings)} CloudTrail anomalies")

        except Exception as e:
            logger.error(f"Error getting CloudTrail anomalies: {e}")

        return findings

    def _parse_cloudtrail_event(self, record: list[dict]) -> SecurityFinding | None:
        """Parse a CloudTrail log record into SecurityFinding.

        Args:
            record: CloudWatch Logs Insights result record

        Returns:
            SecurityFinding object or None
        """
        try:
            fields = {item["field"]: item["value"] for item in record}

            event_name = fields.get("eventName", "unknown")
            error_code = fields.get("errorCode", "")
            user_arn = fields.get("userIdentity.arn", "unknown")
            source_ip = fields.get("sourceIPAddress", "unknown")
            timestamp_str = fields.get("@timestamp", "")

            # Determine severity
            severity = FindingSeverity.MEDIUM
            if "Delete" in event_name or "Terminate" in event_name:
                severity = FindingSeverity.HIGH
            if "AccessDenied" in error_code:
                severity = FindingSeverity.MEDIUM
            if "CreateUser" in event_name or "AttachPolicy" in event_name:
                severity = FindingSeverity.HIGH

            title = f"CloudTrail: {event_name}"
            if error_code:
                title += f" ({error_code})"

            return SecurityFinding(
                id=f"cloudtrail-{hash(f'{timestamp_str}-{event_name}')}",
                finding_type=FindingType.CLOUDTRAIL_ANOMALY,
                severity=severity,
                title=title,
                description=f"API call {event_name} by {user_arn} from {source_ip}",
                detected_at=(
                    datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if timestamp_str
                    else datetime.now(timezone.utc)
                ),
                source_service="CloudTrail",
                affected_resources=[user_arn],
                indicators=[f"Source IP: {source_ip}", f"Event: {event_name}"],
                recommended_actions=[
                    "Review IAM permissions for the user/role",
                    "Check for unauthorized access patterns",
                    "Verify the action was intentional",
                ],
                raw_data=fields,
            )
        except Exception as e:
            logger.error(f"Error parsing CloudTrail event: {e}")
            return None

    # =========================================================================
    # Mock Data for Testing
    # =========================================================================

    def _get_mock_guardduty_findings(self) -> list[SecurityFinding]:
        """Return mock GuardDuty findings for testing."""
        return [
            SecurityFinding(
                id="gd-mock-001",
                finding_type=FindingType.GUARDDUTY,
                severity=FindingSeverity.HIGH,
                title="UnauthorizedAccess:EC2/SSHBruteForce",
                description="SSH brute force attack detected against EC2 instance",
                detected_at=datetime.now(timezone.utc) - timedelta(hours=2),
                source_service="GuardDuty",
                affected_resources=["EC2: i-0abc123def456"],
                indicators=[
                    "Remote IP: 203.0.113.50",
                    "Port: 22",
                    "Failed attempts: 500+",
                ],
                recommended_actions=[
                    "Block source IP at security group level",
                    "Enable AWS Network Firewall",
                    "Review SSH access patterns",
                ],
            ),
            SecurityFinding(
                id="gd-mock-002",
                finding_type=FindingType.GUARDDUTY,
                severity=FindingSeverity.MEDIUM,
                title="Recon:EC2/PortProbeUnprotectedPort",
                description="Port scanning detected from external IP",
                detected_at=datetime.now(timezone.utc) - timedelta(hours=5),
                source_service="GuardDuty",
                affected_resources=["EC2: i-0xyz789abc123"],
                indicators=["Remote IP: 198.51.100.25", "Ports scanned: 20+"],
                recommended_actions=[
                    "Review security group ingress rules",
                    "Consider implementing AWS Network Firewall",
                ],
            ),
        ]

    def _get_mock_waf_events(self) -> list[SecurityFinding]:
        """Return mock WAF events for testing."""
        return [
            SecurityFinding(
                id="waf-mock-001",
                finding_type=FindingType.WAF_EVENT,
                severity=FindingSeverity.HIGH,
                title="WAF Blocked: SQLInjection",
                description="WAF blocked POST request to /api/v1/query with SQL injection pattern",
                detected_at=datetime.now(timezone.utc) - timedelta(hours=1),
                source_service="AWS WAF",
                affected_resources=["/api/v1/query"],
                indicators=[
                    "Source IP: 192.0.2.100",
                    "Rule: AWSManagedRulesSQLiRuleSet",
                    "Pattern: UNION SELECT",
                ],
                recommended_actions=[
                    "Review application input validation",
                    "Add parameterized queries if not present",
                    "Consider IP-based rate limiting",
                ],
            ),
        ]

    def _get_mock_cloudtrail_anomalies(self) -> list[SecurityFinding]:
        """Return mock CloudTrail anomalies for testing."""
        return [
            SecurityFinding(
                id="ct-mock-001",
                finding_type=FindingType.CLOUDTRAIL_ANOMALY,
                severity=FindingSeverity.MEDIUM,
                title="CloudTrail: DeleteBucket (AccessDenied)",
                description="Failed attempt to delete S3 bucket by unknown principal",
                detected_at=datetime.now(timezone.utc) - timedelta(hours=3),
                source_service="CloudTrail",
                affected_resources=["arn:aws:iam::123456789012:user/suspicious-user"],
                indicators=[
                    "Source IP: 203.0.113.75",
                    "Event: DeleteBucket",
                    "Error: AccessDenied",
                ],
                recommended_actions=[
                    "Review IAM permissions",
                    "Check for credential compromise",
                    "Enable MFA for sensitive operations",
                ],
            ),
        ]


# =============================================================================
# Factory Functions
# =============================================================================


def create_security_telemetry_service(
    use_aws: bool = True,
    config: TelemetryConfig | None = None,
) -> SecurityTelemetryService:
    """Create a security telemetry service with appropriate mode.

    Args:
        use_aws: True for AWS mode, False for mock mode
        config: Optional telemetry configuration

    Returns:
        Configured SecurityTelemetryService instance
    """
    mode = TelemetryMode.AWS if use_aws else TelemetryMode.MOCK
    return SecurityTelemetryService(mode=mode, config=config)
