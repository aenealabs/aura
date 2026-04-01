"""
Incident Detector Service

Monitors multiple sources to detect break/fix events that should be documented.
Sources include CloudWatch Logs, CloudFormation events, CodeBuild state changes,
and Git commit patterns.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class IncidentType(Enum):
    """Types of incidents that can be detected."""

    CODEBUILD_FAILURE_RECOVERY = "codebuild_failure_recovery"
    CLOUDFORMATION_ROLLBACK_RECOVERY = "cloudformation_rollback_recovery"
    CLOUDFORMATION_STACK_FIX = "cloudformation_stack_fix"
    DOCKER_BUILD_FIX = "docker_build_fix"
    IAM_PERMISSION_FIX = "iam_permission_fix"
    ECR_CONFLICT_RESOLUTION = "ecr_conflict_resolution"
    SHELL_SYNTAX_FIX = "shell_syntax_fix"
    GENERAL_BUG_FIX = "general_bug_fix"
    INFRASTRUCTURE_FIX = "infrastructure_fix"
    SECURITY_FIX = "security_fix"


@dataclass
class ErrorSignature:
    """Unique signature for an error pattern."""

    pattern: str
    service: str
    severity: str = "medium"
    keywords: list[str] = field(default_factory=list)

    def matches(self, text: str) -> bool:
        """Check if this signature matches the given text."""
        return bool(re.search(self.pattern, text, re.IGNORECASE | re.MULTILINE))


@dataclass
class ResolutionStep:
    """A single step in the resolution process."""

    command: str
    output: str
    timestamp: datetime
    success: bool
    description: str = ""


@dataclass
class Incident:
    """Represents a detected break/fix incident."""

    id: str
    incident_type: IncidentType
    title: str
    description: str
    error_messages: list[str]
    error_signatures: list[ErrorSignature]
    resolution_steps: list[ResolutionStep]
    affected_services: list[str]
    affected_resources: list[str]
    root_cause: str
    start_time: datetime
    end_time: datetime
    source: str  # cloudwatch, cloudformation, git, manual
    source_id: str  # build ID, stack name, commit SHA
    confidence: float = 0.0  # 0.0 to 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def resolution_duration_minutes(self) -> float:
        """Calculate time to resolution in minutes."""
        delta = self.end_time - self.start_time
        return delta.total_seconds() / 60

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence detection."""
        return self.confidence >= 0.7


class IncidentDetector:
    """
    Detects break/fix incidents from various sources.

    Monitors:
    - CloudWatch Logs for error patterns followed by success
    - CloudFormation stack events for rollback recovery
    - CodeBuild build state changes
    - Git commits with fix patterns
    """

    # Known error patterns and their classifications
    ERROR_PATTERNS = {
        "codebuild": [
            ErrorSignature(
                pattern=r"exec format error|exit code:?\s*255",
                service="docker",
                severity="high",
                keywords=["docker", "platform", "architecture", "arm64", "amd64"],
            ),
            ErrorSignature(
                pattern=r"\[\[:\s*not found",
                service="codebuild",
                severity="medium",
                keywords=["bash", "shell", "syntax", "conditional"],
            ),
            ErrorSignature(
                pattern=r"AccessDenied.*cloudformation",
                service="iam",
                severity="high",
                keywords=["iam", "permissions", "cloudformation", "access"],
            ),
            ErrorSignature(
                pattern=r"AccessDenied.*bedrock",
                service="bedrock",
                severity="high",
                keywords=["bedrock", "iam", "permissions", "guardrails"],
            ),
        ],
        "cloudformation": [
            ErrorSignature(
                pattern=r"AlreadyExists.*ECR",
                service="ecr",
                severity="medium",
                keywords=["ecr", "repository", "exists", "conflict"],
            ),
            ErrorSignature(
                pattern=r"ROLLBACK_COMPLETE",
                service="cloudformation",
                severity="high",
                keywords=["cloudformation", "rollback", "stack", "failed"],
            ),
            ErrorSignature(
                pattern=r"Resource.*already exists",
                service="cloudformation",
                severity="medium",
                keywords=["resource", "conflict", "exists"],
            ),
        ],
        "git": [
            ErrorSignature(
                pattern=r"^fix(\(.+\))?:",
                service="general",
                severity="medium",
                keywords=["fix", "bug", "resolve"],
            ),
            ErrorSignature(
                pattern=r"^hotfix:",
                service="general",
                severity="high",
                keywords=["hotfix", "urgent", "critical"],
            ),
        ],
    }

    # CloudFormation states indicating failure and recovery
    CF_FAILURE_STATES = {
        "ROLLBACK_COMPLETE",
        "CREATE_FAILED",
        "DELETE_FAILED",
        "UPDATE_ROLLBACK_COMPLETE",
        "UPDATE_ROLLBACK_FAILED",
    }

    CF_SUCCESS_STATES = {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "DELETE_COMPLETE",
    }

    def __init__(
        self,
        region: str = "us-east-1",
        project_name: str = "aura",
        environment: str = "dev",
    ):
        """
        Initialize the incident detector.

        Args:
            region: AWS region
            project_name: Project name for filtering resources
            environment: Environment (dev, qa, prod)
        """
        self.region = region
        self.project_name = project_name
        self.environment = environment

        # Initialize AWS clients
        self.logs_client = boto3.client("logs", region_name=region)
        self.cf_client = boto3.client("cloudformation", region_name=region)
        self.codebuild_client = boto3.client("codebuild", region_name=region)

    async def detect_incidents(
        self,
        hours: int = 24,
        sources: Optional[list[str]] = None,
    ) -> list[Incident]:
        """
        Detect break/fix incidents from the specified time window.

        Args:
            hours: Number of hours to look back
            sources: List of sources to check (cloudwatch, cloudformation, git)
                    If None, checks all sources.

        Returns:
            List of detected incidents
        """
        sources = sources or ["cloudwatch", "cloudformation", "codebuild"]
        incidents = []

        if "codebuild" in sources:
            incidents.extend(await self._detect_codebuild_incidents(hours))

        if "cloudformation" in sources:
            incidents.extend(await self._detect_cloudformation_incidents(hours))

        if "cloudwatch" in sources:
            incidents.extend(await self._detect_cloudwatch_incidents(hours))

        # Sort by confidence (highest first)
        incidents.sort(key=lambda x: x.confidence, reverse=True)

        return incidents

    async def _detect_codebuild_incidents(self, hours: int) -> list[Incident]:
        """Detect CodeBuild failure → success patterns."""
        incidents: list[Incident] = []

        try:
            # List recent builds for application deploy project
            project_name = f"{self.project_name}-application-deploy-{self.environment}"

            response = self.codebuild_client.list_builds_for_project(
                projectName=project_name,
                sortOrder="DESCENDING",
            )

            build_ids = response.get("ids", [])[:20]  # Last 20 builds

            if not build_ids:
                return incidents

            # Get build details
            builds_response = self.codebuild_client.batch_get_builds(ids=build_ids)
            builds = builds_response.get("builds", [])

            # Look for failure → success patterns
            for i, build in enumerate(builds):
                if build["buildStatus"] == "SUCCEEDED" and i + 1 < len(builds):
                    prev_build = builds[i + 1]
                    if prev_build["buildStatus"] in ("FAILED", "FAULT"):
                        # Found a recovery pattern
                        incident = await self._analyze_codebuild_recovery(
                            failed_build=prev_build,
                            success_build=build,
                        )
                        if incident:
                            incidents.append(incident)

        except ClientError as e:
            logger.error(f"Error detecting CodeBuild incidents: {e}")

        return incidents

    async def _analyze_codebuild_recovery(
        self,
        failed_build: dict,
        success_build: dict,
    ) -> Optional[Incident]:
        """Analyze a CodeBuild failure → success pattern."""
        try:
            # Get logs from failed build
            log_group = failed_build.get("logs", {}).get("groupName")
            log_stream = failed_build.get("logs", {}).get("streamName")

            if not log_group or not log_stream:
                return None

            # Fetch error logs
            logs_response = self.logs_client.get_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                limit=500,
            )

            log_messages = [
                event["message"] for event in logs_response.get("events", [])
            ]
            log_text = "\n".join(log_messages)

            # Match error patterns
            matched_signatures = []
            for signature in self.ERROR_PATTERNS.get("codebuild", []):
                if signature.matches(log_text):
                    matched_signatures.append(signature)

            if not matched_signatures:
                return None

            # Determine incident type from signatures
            incident_type = self._classify_incident_type(matched_signatures)

            # Extract error messages
            error_messages = self._extract_error_messages(log_text)

            # Build incident
            incident = Incident(
                id=f"cb-{failed_build['id'][-12:]}",
                incident_type=incident_type,
                title=self._generate_incident_title(matched_signatures),
                description=f"CodeBuild project {failed_build['projectName']} failed and was subsequently fixed.",
                error_messages=error_messages,
                error_signatures=matched_signatures,
                resolution_steps=[],  # Will be populated by git commit analysis
                affected_services=list({sig.service for sig in matched_signatures}),
                affected_resources=[failed_build["projectName"]],
                root_cause=self._infer_root_cause(matched_signatures, error_messages),
                start_time=datetime.fromisoformat(
                    failed_build["startTime"].replace("Z", "+00:00")
                ),
                end_time=datetime.fromisoformat(
                    success_build["endTime"].replace("Z", "+00:00")
                ),
                source="codebuild",
                source_id=failed_build["id"],
                confidence=self._calculate_confidence(matched_signatures),
                metadata={
                    "failed_build_id": failed_build["id"],
                    "success_build_id": success_build["id"],
                    "log_group": log_group,
                    "log_stream": log_stream,
                },
            )

            return incident

        except ClientError as e:
            logger.error(f"Error analyzing CodeBuild recovery: {e}")
            return None

    async def _detect_cloudformation_incidents(self, hours: int) -> list[Incident]:
        """Detect CloudFormation rollback → recovery patterns."""
        incidents: list[Incident] = []

        try:
            # List stacks with our project prefix
            paginator = self.cf_client.get_paginator("list_stacks")

            # Cast to list[str] to avoid mypy literal type error
            status_filter: list[str] = list(self.CF_SUCCESS_STATES)
            for page in paginator.paginate(
                StackStatusFilter=status_filter  # type: ignore[arg-type]
            ):
                for stack in page.get("StackSummaries", []):
                    if not stack["StackName"].startswith(self.project_name):
                        continue

                    # Check stack events for recent rollback recovery
                    incident = await self._check_stack_for_recovery(
                        stack["StackName"], hours
                    )
                    if incident:
                        incidents.append(incident)

        except ClientError as e:
            logger.error(f"Error detecting CloudFormation incidents: {e}")

        return incidents

    async def _check_stack_for_recovery(
        self,
        stack_name: str,
        hours: int,
    ) -> Optional[Incident]:
        """Check if a stack has recovered from a failure recently."""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            # Get stack events
            events_response = self.cf_client.describe_stack_events(StackName=stack_name)

            events = events_response.get("StackEvents", [])

            # Look for failure → success pattern in events
            failure_event = None
            success_event = None

            for event in events:
                event_time = event["Timestamp"].replace(tzinfo=None)
                if event_time < cutoff_time:
                    break

                status = event.get("ResourceStatus", "")

                if status in self.CF_FAILURE_STATES and not failure_event:
                    failure_event = event
                elif status in self.CF_SUCCESS_STATES and failure_event:
                    success_event = event
                    break

            if not (failure_event and success_event):
                return None

            # Match error patterns
            reason = failure_event.get("ResourceStatusReason", "")
            matched_signatures = []

            for signature in self.ERROR_PATTERNS.get("cloudformation", []):
                if signature.matches(reason):
                    matched_signatures.append(signature)

            if not matched_signatures:
                # Generic CloudFormation failure
                matched_signatures = [
                    ErrorSignature(
                        pattern=r".*",
                        service="cloudformation",
                        severity="medium",
                        keywords=["cloudformation", "stack", "deployment"],
                    )
                ]

            incident_type = self._classify_incident_type(matched_signatures)

            return Incident(
                id=f"cf-{stack_name[-20:]}",
                incident_type=incident_type,
                title=f"CloudFormation Stack Recovery: {stack_name}",
                description=f"Stack {stack_name} recovered from {failure_event.get('ResourceStatus')}",
                error_messages=[reason] if reason else [],
                error_signatures=matched_signatures,
                resolution_steps=[],
                affected_services=list({sig.service for sig in matched_signatures}),
                affected_resources=[stack_name],
                root_cause=self._infer_root_cause(matched_signatures, [reason]),
                start_time=failure_event["Timestamp"].replace(tzinfo=None),
                end_time=success_event["Timestamp"].replace(tzinfo=None),
                source="cloudformation",
                source_id=stack_name,
                confidence=self._calculate_confidence(matched_signatures),
                metadata={
                    "stack_name": stack_name,
                    "failure_status": failure_event.get("ResourceStatus"),
                    "success_status": success_event.get("ResourceStatus"),
                    "failure_reason": reason,
                },
            )

        except ClientError as e:
            logger.error(f"Error checking stack {stack_name}: {e}")
            return None

    async def _detect_cloudwatch_incidents(self, hours: int) -> list[Incident]:
        """Detect incidents from CloudWatch log patterns."""
        # This would analyze CloudWatch Logs for error → success patterns
        # Implementation depends on specific log group structure
        return []

    def _classify_incident_type(self, signatures: list[ErrorSignature]) -> IncidentType:
        """Classify the incident type based on error signatures."""
        services = {sig.service for sig in signatures}
        keywords = set()
        for sig in signatures:
            keywords.update(sig.keywords)

        if "docker" in services or "platform" in keywords or "architecture" in keywords:
            return IncidentType.DOCKER_BUILD_FIX

        if "iam" in services or "permissions" in keywords:
            return IncidentType.IAM_PERMISSION_FIX

        if "ecr" in services or "repository" in keywords:
            return IncidentType.ECR_CONFLICT_RESOLUTION

        if "bash" in keywords or "shell" in keywords:
            return IncidentType.SHELL_SYNTAX_FIX

        if "cloudformation" in services:
            return IncidentType.CLOUDFORMATION_STACK_FIX

        if "bedrock" in services:
            return IncidentType.IAM_PERMISSION_FIX

        return IncidentType.GENERAL_BUG_FIX

    def _generate_incident_title(self, signatures: list[ErrorSignature]) -> str:
        """Generate a descriptive title from error signatures."""
        if not signatures:
            return "Unknown Incident"

        primary_sig = signatures[0]
        keywords = primary_sig.keywords[:3]

        service = primary_sig.service.upper()
        keyword_str = " ".join(kw.title() for kw in keywords)

        return f"{service} Issue: {keyword_str}"

    def _extract_error_messages(self, log_text: str) -> list[str]:
        """Extract key error messages from log text."""
        error_patterns = [
            r"(?:ERROR|FATAL|FAILED)[:]\s*(.+?)(?:\n|$)",
            r"An error occurred.*?:\s*(.+?)(?:\n|$)",
            r"(?:exit code|returned):?\s*(\d+)",
            r"AccessDenied.*?(?:\n|$)",
            r"AlreadyExists.*?(?:\n|$)",
        ]

        messages = []
        for pattern in error_patterns:
            matches = re.findall(pattern, log_text, re.IGNORECASE)
            messages.extend(matches[:3])  # Limit to 3 per pattern

        return list(set(messages))[:10]  # Dedupe and limit total

    def _infer_root_cause(
        self,
        signatures: list[ErrorSignature],
        error_messages: list[str],
    ) -> str:
        """Infer the root cause from signatures and error messages."""
        if not signatures:
            return "Unknown root cause"

        primary_sig = signatures[0]

        # Map signatures to known root causes
        cause_map = {
            "docker": "Docker image architecture mismatch (ARM64 vs AMD64)",
            "bash": "Bash-specific syntax used in POSIX shell environment",
            "iam": "Missing IAM permissions for the operation",
            "ecr": "ECR repository already exists outside CloudFormation",
            "cloudformation": "CloudFormation stack in failed state",
            "bedrock": "Missing Bedrock service permissions",
        }

        return cause_map.get(
            primary_sig.service, f"{primary_sig.service} configuration issue"
        )

    def _calculate_confidence(self, signatures: list[ErrorSignature]) -> float:
        """Calculate confidence score for the detection."""
        if not signatures:
            return 0.3

        # Base confidence from number of matching signatures
        base = min(0.5 + (len(signatures) * 0.1), 0.8)

        # Boost for high-severity signatures
        severity_boost = sum(0.1 for sig in signatures if sig.severity == "high")

        return min(base + severity_boost, 1.0)

    async def detect_from_git_commits(
        self,
        commits: list[dict],
    ) -> list[Incident]:
        """
        Detect incidents from git commit messages.

        Args:
            commits: List of commit dicts with 'sha', 'message', 'timestamp', 'files'

        Returns:
            List of detected incidents
        """
        incidents = []

        for commit in commits:
            message = commit.get("message", "")

            # Check for fix patterns
            matched_signatures = []
            for signature in self.ERROR_PATTERNS.get("git", []):
                if signature.matches(message):
                    matched_signatures.append(signature)

            if matched_signatures:
                # Parse commit message for details
                incident = self._create_incident_from_commit(commit, matched_signatures)
                if incident:
                    incidents.append(incident)

        return incidents

    def _create_incident_from_commit(
        self,
        commit: dict,
        signatures: list[ErrorSignature],
    ) -> Optional[Incident]:
        """Create an incident from a git commit."""
        message = commit.get("message", "")
        sha = commit.get("sha", "unknown")
        timestamp = commit.get("timestamp", datetime.now())
        files = commit.get("files", [])

        # Extract title from first line
        title = message.split("\n")[0]

        # Determine affected services from files
        services = set()
        for f in files:
            if "cloudformation" in f:
                services.add("cloudformation")
            if "buildspec" in f:
                services.add("codebuild")
            if "docker" in f or "Dockerfile" in f:
                services.add("docker")
            if "iam" in f.lower():
                services.add("iam")

        return Incident(
            id=f"git-{sha[:8]}",
            incident_type=self._classify_incident_type(signatures),
            title=title,
            description=message,
            error_messages=[],
            error_signatures=signatures,
            resolution_steps=[],
            affected_services=list(services) or ["general"],
            affected_resources=files,
            root_cause="See commit message for details",
            start_time=timestamp,
            end_time=timestamp,
            source="git",
            source_id=sha,
            confidence=0.6,  # Lower confidence for git-based detection
            metadata={
                "commit_sha": sha,
                "files_changed": files,
            },
        )
