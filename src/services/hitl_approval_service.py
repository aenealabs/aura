"""
Project Aura - HITL Approval Service

Provides DynamoDB-backed persistence for human-in-the-loop approval requests,
enabling audit trails and workflow state management for security patch approvals.

Implements the HITL Approval workflow described in docs/design/HITL_SANDBOX_ARCHITECTURE.md
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Autonomy policy service (lazy import to avoid circular deps)
_autonomy_service = None

# Boto3 imports (available in AWS environment)
try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    ClientError = Exception  # Fallback for type hints when boto3 not available
    logger.warning("Boto3 not available - using mock mode")


class ApprovalStatus(Enum):
    """Status states for approval requests."""

    PENDING = "PENDING"  # Awaiting human review
    APPROVED = "APPROVED"  # Human approved the patch
    REJECTED = "REJECTED"  # Human rejected the patch
    EXPIRED = "EXPIRED"  # Approval timeout exceeded
    CANCELLED = "CANCELLED"  # Request was cancelled
    ESCALATED = "ESCALATED"  # Escalated to backup reviewer


class EscalationAction(Enum):
    """Actions taken during expiration processing."""

    ESCALATE = "ESCALATE"  # Escalate to backup reviewer (CRITICAL/HIGH)
    EXPIRE = "EXPIRE"  # Mark as expired and re-queue (MEDIUM/LOW)
    WARN = "WARN"  # Send warning, not yet expired


class PatchSeverity(Enum):
    """Severity levels for patches requiring approval."""

    CRITICAL = "CRITICAL"  # Security vulnerability - requires immediate attention
    HIGH = "HIGH"  # Important fix - requires prompt review
    MEDIUM = "MEDIUM"  # Standard change - normal review cycle
    LOW = "LOW"  # Minor improvement - can be batched


class HITLMode(Enum):
    """Operating modes for HITL service."""

    MOCK = "mock"  # In-memory storage for testing
    AWS = "aws"  # Real DynamoDB


class HITLApprovalError(Exception):
    """General HITL approval operation error."""


@dataclass
class ExpirationResult:
    """Result of processing a single expiration."""

    approval_id: str
    action: EscalationAction
    success: bool
    message: str
    escalated_to: str | None = None


@dataclass
class ExpirationProcessingResult:
    """Result of processing all expirations."""

    processed: int
    escalated: int
    expired: int
    warnings_sent: int
    errors: int
    details: list[ExpirationResult] = field(default_factory=list)


@dataclass
class HITLDecision:
    """
    Result of checking whether HITL approval is required.

    This is returned when using autonomy-aware approval flow.
    """

    requires_hitl: bool
    approval_request: ApprovalRequest | None
    autonomy_level: str
    reason: str
    auto_approved: bool = False
    guardrail_triggered: bool = False
    organization_id: str | None = None
    policy_id: str | None = None


@dataclass
class ApprovalRequest:
    """
    Represents a human-in-the-loop approval request for a security patch.

    Attributes:
        approval_id: Unique identifier for this approval request
        patch_id: Identifier of the patch being reviewed
        vulnerability_id: Identifier of the detected vulnerability
        status: Current approval status
        severity: Patch severity level
        created_at: Timestamp when request was created
        expires_at: Timestamp when request expires
        reviewer_email: Email of the assigned reviewer (optional)
        reviewed_at: Timestamp when decision was made (optional)
        reviewed_by: Identity of the reviewer (optional)
        decision_reason: Reason provided for approval/rejection
        sandbox_test_results: Results from sandbox testing
        patch_diff: The actual code changes
        original_code: The vulnerable code being patched
        metadata: Additional context information
        escalation_count: Number of times this request has been escalated
        last_escalated_at: Timestamp of last escalation
        warning_sent_at: Timestamp when expiration warning was sent
    """

    approval_id: str
    patch_id: str
    vulnerability_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    severity: PatchSeverity = PatchSeverity.MEDIUM
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""
    reviewer_email: str | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    decision_reason: str | None = None
    sandbox_test_results: dict[str, Any] = field(default_factory=dict)
    patch_diff: str = ""
    original_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    escalation_count: int = 0
    last_escalated_at: str | None = None
    warning_sent_at: str | None = None


class HITLApprovalService:
    """
    DynamoDB-backed service for managing HITL approval requests.

    Features:
    - Create and track approval requests
    - Query by status, severity, or reviewer
    - Process approval/rejection decisions
    - Automatic expiration handling
    - Full audit trail for compliance

    Usage:
        >>> service = HITLApprovalService(mode=HITLMode.AWS)
        >>> request = service.create_approval_request(
        ...     patch_id="patch-123",
        ...     vulnerability_id="vuln-456",
        ...     severity=PatchSeverity.HIGH,
        ...     patch_diff="...",
        ...     sandbox_results={"tests_passed": 10}
        ... )
        >>> service.approve_request(request.approval_id, "security-lead@company.com", "LGTM")
    """

    # Default approval timeout: 24 hours
    DEFAULT_TIMEOUT_HOURS = 24
    # Default TTL for records: 90 days (compliance retention)
    DEFAULT_TTL_DAYS = 90
    # Warning threshold: 75% of timeout (send warning before expiry)
    WARNING_THRESHOLD_PERCENT = 0.75
    # Maximum escalation attempts before marking expired
    MAX_ESCALATIONS = 2
    # Number of status buckets for partition spreading (prevents hot partitions)
    NUM_STATUS_BUCKETS = 10

    def __init__(
        self,
        mode: HITLMode = HITLMode.MOCK,
        table_name: str | None = None,
        region: str | None = None,
        timeout_hours: int | None = None,
        notification_service: Any | None = None,
        backup_reviewers: list[str] | None = None,
        escalation_timeout_hours: int | None = None,
    ):
        """
        Initialize HITL Approval Service.

        Args:
            mode: Operating mode (MOCK or AWS)
            table_name: DynamoDB table name (default: aura-approval-requests-{env})
            region: AWS region (default: us-east-1)
            timeout_hours: Hours before approval request expires
            notification_service: NotificationService instance for alerts
            backup_reviewers: List of backup reviewer emails for escalation
            escalation_timeout_hours: Hours before next escalation/expiry
        """
        self.mode = mode
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.timeout_hours = timeout_hours or self.DEFAULT_TIMEOUT_HOURS
        self.notification_service = notification_service
        self.backup_reviewers = backup_reviewers or []
        self.escalation_timeout_hours = escalation_timeout_hours or self.timeout_hours

        # Audit log for state transitions (in-memory for now, can be persisted)
        self.audit_entries: list[dict[str, Any]] = []

        # Determine table name
        env = os.environ.get("ENVIRONMENT", "dev")
        project = os.environ.get("PROJECT_NAME", "aura")
        self.table_name = table_name or f"{project}-approval-requests-{env}"

        # In-memory store for mock mode
        self.mock_store: dict[str, dict[str, Any]] = {}

        # Initialize DynamoDB client
        if self.mode == HITLMode.AWS and BOTO3_AVAILABLE:
            self._init_dynamodb_client()
        else:
            if self.mode == HITLMode.AWS:
                logger.warning(
                    "AWS mode requested but boto3 not available. Using MOCK mode."
                )
                self.mode = HITLMode.MOCK
            self._init_mock_mode()

        logger.info(
            f"HITLApprovalService initialized in {self.mode.value} mode "
            f"(table: {self.table_name}, timeout: {self.timeout_hours}h, "
            f"backup_reviewers: {len(self.backup_reviewers)})"
        )

    def _init_dynamodb_client(self) -> None:
        """Initialize DynamoDB client."""
        try:
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.table = self.dynamodb.Table(self.table_name)

            # Verify table exists
            self.table.load()
            logger.info(f"Connected to DynamoDB table: {self.table_name}")

        except Exception as e:
            logger.error(f"Failed to connect to DynamoDB: {e}")
            logger.warning("Falling back to MOCK mode")
            self.mode = HITLMode.MOCK
            self._init_mock_mode()

    def _init_mock_mode(self) -> None:
        """Initialize mock mode and optionally seed demo approval requests.

        When ``AURA_SEED_MOCK_APPROVALS`` is unset or truthy (the default in
        local dev), the in-memory store is pre-populated with a varied set
        of demo approval requests so the HITL Approvals page has data to
        render. Set ``AURA_SEED_MOCK_APPROVALS=false`` to keep the store
        empty (e.g. for unit tests that build their own fixtures).
        """
        logger.info("Mock mode initialized (in-memory storage)")

        seed_flag = os.environ.get("AURA_SEED_MOCK_APPROVALS", "true").lower()
        if seed_flag in ("0", "false", "no", "off"):
            return

        self._seed_demo_approvals()
        logger.info(
            "Seeded %d demo approval requests (set AURA_SEED_MOCK_APPROVALS=false to disable)",
            len(self.mock_store),
        )

    def _seed_demo_approvals(self) -> None:
        """Populate ``mock_store`` with a representative set of demo data.

        Generates seven PENDING entries (matching the sidebar badge), two
        APPROVED, and one REJECTED — giving the UI populated views across
        the All / Pending / Approved / Rejected filter tabs.
        """
        now = datetime.now(timezone.utc)
        ttl_seconds = self.DEFAULT_TTL_DAYS * 24 * 60 * 60

        demos: list[dict[str, Any]] = [
            {
                "title": "SQL injection in user search endpoint",
                "description": "Untrusted input concatenated into a Gremlin "
                "string in the user-search handler. Patch parameterizes the "
                "query and adds an integration test.",
                "severity": PatchSeverity.CRITICAL,
                "status": ApprovalStatus.PENDING,
                "cve": "CVE-2024-9921",
                "file": "src/api/users.py",
                "lines_changed": 14,
                "sandbox_status": "running",
                "test_results": None,
                "created_offset_minutes": -23,
                "generated_by": "coder-agent",
                "requested_by": "scanner-pipeline",
            },
            {
                "title": "Hardcoded AWS credential in onboarding script",
                "description": "Static access key found in the team-invite "
                "Lambda deploy script. Patch rotates to SSM SecureString and "
                "removes the leaked key.",
                "severity": PatchSeverity.CRITICAL,
                "status": ApprovalStatus.PENDING,
                "cve": None,
                "file": "scripts/onboarding/invite_team.py",
                "lines_changed": 22,
                "sandbox_status": "queued",
                "test_results": None,
                "created_offset_minutes": -47,
                "generated_by": "secrets-detector",
                "requested_by": "scanner-pipeline",
            },
            {
                "title": "Bypass-able JWT signature on /admin endpoints",
                "description": "Algorithm allowlist accepts both HS256 and "
                "RS256 — algorithm confusion attack possible. Patch pins to "
                "the configured signing algorithm.",
                "severity": PatchSeverity.HIGH,
                "status": ApprovalStatus.PENDING,
                "cve": "CVE-2025-30412",
                "file": "src/services/identity/token_service.py",
                "lines_changed": 6,
                "sandbox_status": "passed",
                "test_results": {"passed": 47, "failed": 0, "duration_s": 12},
                "created_offset_minutes": -110,
                "generated_by": "coder-agent",
                "requested_by": "audit-finding-86",
            },
            {
                "title": "Container escape risk in vuln-scan sandbox task",
                "description": "ECS task definition lacks ReadonlyRootFilesystem "
                "and capability drops. Patch adds the missing ECS hardening "
                "primitives and a deny-all egress security group.",
                "severity": PatchSeverity.HIGH,
                "status": ApprovalStatus.PENDING,
                "cve": None,
                "file": "deploy/cloudformation/sandbox.yaml",
                "lines_changed": 33,
                "sandbox_status": "passed",
                "test_results": {"passed": 12, "failed": 0, "duration_s": 4},
                "created_offset_minutes": -180,
                "generated_by": "iac-agent",
                "requested_by": "audit-h3",
            },
            {
                "title": "Path traversal in repo-clone tarball extractor",
                "description": "Tar extraction does not validate member paths "
                "against the destination directory. Patch wraps extraction in "
                "the standard safe-extract helper.",
                "severity": PatchSeverity.MEDIUM,
                "status": ApprovalStatus.PENDING,
                "cve": "CVE-2007-4559",
                "file": "src/services/repository/clone.py",
                "lines_changed": 18,
                "sandbox_status": "passed",
                "test_results": {"passed": 9, "failed": 0, "duration_s": 3},
                "created_offset_minutes": -260,
                "generated_by": "coder-agent",
                "requested_by": "scanner-pipeline",
            },
            {
                "title": "Verbose stack traces leaked on /api/v1/health failures",
                "description": "Unhandled exception path returns the full "
                "Python traceback in the response body. Patch wraps the "
                "handler in the standard sanitize-and-log middleware.",
                "severity": PatchSeverity.MEDIUM,
                "status": ApprovalStatus.PENDING,
                "cve": None,
                "file": "src/api/health_endpoints.py",
                "lines_changed": 11,
                "sandbox_status": "passed",
                "test_results": {"passed": 6, "failed": 0, "duration_s": 1},
                "created_offset_minutes": -380,
                "generated_by": "coder-agent",
                "requested_by": "scanner-pipeline",
            },
            {
                "title": "Outdated dependency: requests<2.32 (CVE-2024-35195)",
                "description": "Requirements floor allows a vulnerable version "
                "of requests. Patch raises the floor and confirms transitive "
                "lock alignment.",
                "severity": PatchSeverity.LOW,
                "status": ApprovalStatus.PENDING,
                "cve": "CVE-2024-35195",
                "file": "requirements.txt",
                "lines_changed": 2,
                "sandbox_status": "passed",
                "test_results": {"passed": 158, "failed": 0, "duration_s": 28},
                "created_offset_minutes": -640,
                "generated_by": "supply-chain-agent",
                "requested_by": "dependabot-mirror",
            },
            {
                "title": "XSS in markdown renderer for incident notes",
                "description": "Sanitizer allowlist did not strip <script> "
                "tags inside fenced code blocks. Patch tightens the allowlist "
                "and adds a regression fixture.",
                "severity": PatchSeverity.HIGH,
                "status": ApprovalStatus.APPROVED,
                "cve": "CVE-2024-21235",
                "file": "src/services/incidents/markdown_render.py",
                "lines_changed": 19,
                "sandbox_status": "passed",
                "test_results": {"passed": 31, "failed": 0, "duration_s": 7},
                "created_offset_minutes": -2880,
                "reviewed_offset_minutes": -2700,
                "reviewer": "alice@aenealabs.com",
                "generated_by": "coder-agent",
                "requested_by": "scanner-pipeline",
            },
            {
                "title": "Server-side request forgery in webhook proxy",
                "description": "Webhook proxy followed redirects to internal "
                "metadata endpoints. Patch enforces an SSRF-safe HTTP client "
                "with allowlisted egress.",
                "severity": PatchSeverity.HIGH,
                "status": ApprovalStatus.APPROVED,
                "cve": "CVE-2024-22361",
                "file": "src/api/webhook_handler.py",
                "lines_changed": 27,
                "sandbox_status": "passed",
                "test_results": {"passed": 22, "failed": 0, "duration_s": 5},
                "created_offset_minutes": -5760,
                "reviewed_offset_minutes": -5500,
                "reviewer": "ben@aenealabs.com",
                "generated_by": "coder-agent",
                "requested_by": "audit-h-webhook",
            },
            {
                "title": "Replace deprecated md5() in cache key generation",
                "description": "Cache key generator used hashlib.md5() without "
                "usedforsecurity=False. Patch swaps to blake2b for clarity. "
                "Rejected: the change broke an undocumented external "
                "consumer keyed on the legacy hash.",
                "severity": PatchSeverity.LOW,
                "status": ApprovalStatus.REJECTED,
                "cve": None,
                "file": "src/services/cache/keys.py",
                "lines_changed": 5,
                "sandbox_status": "passed",
                "test_results": {"passed": 4, "failed": 0, "duration_s": 1},
                "created_offset_minutes": -10080,
                "reviewed_offset_minutes": -9900,
                "reviewer": "carla@aenealabs.com",
                "decision_reason": "Breaks public cache-key contract; "
                "address as part of the v3 cache rev rather than a hot "
                "patch.",
                "generated_by": "lint-agent",
                "requested_by": "scanner-pipeline",
            },
        ]

        for d in demos:
            approval_id = f"appr-demo-{uuid.uuid4().hex[:12]}"
            patch_id = f"patch-demo-{uuid.uuid4().hex[:12]}"
            vulnerability_id = (
                f"vuln-{d['cve'].lower()}" if d.get("cve") else f"vuln-{uuid.uuid4().hex[:8]}"
            )
            created_at_dt = now + timedelta(minutes=d["created_offset_minutes"])
            expires_at_dt = created_at_dt + timedelta(hours=self.timeout_hours)

            metadata = {
                "title": d["title"],
                "description": d["description"],
                "affected_file": d["file"],
                "lines_changed": d["lines_changed"],
                "generated_by": d["generated_by"],
                "sandbox_status": d["sandbox_status"],
                "test_results": d["test_results"],
                "requested_by": d["requested_by"],
            }

            item: dict[str, Any] = {
                "approvalId": approval_id,
                "statusBucket": self._compute_status_bucket(
                    d["status"].value, approval_id
                ),
                "patchId": patch_id,
                "vulnerabilityId": vulnerability_id,
                "status": d["status"].value,
                "severity": d["severity"].value,
                "createdAt": created_at_dt.isoformat(),
                "expiresAt": expires_at_dt.isoformat(),
                "reviewerEmail": d.get("reviewer"),
                "reviewedAt": (
                    (now + timedelta(minutes=d["reviewed_offset_minutes"])).isoformat()
                    if "reviewed_offset_minutes" in d
                    else None
                ),
                "reviewedBy": d.get("reviewer"),
                "decisionReason": d.get("decision_reason"),
                "sandboxTestResults": d.get("test_results") or {},
                "patchDiff": "",
                "originalCode": "",
                "metadata": metadata,
                "escalationCount": 0,
                "lastEscalatedAt": None,
                "warningSentAt": None,
                "createdAtTimestamp": int(created_at_dt.timestamp()),
                "updatedAt": int(time.time()),
                "ttl": int(time.time()) + ttl_seconds,
            }
            self.mock_store[approval_id] = item

    def _compute_status_bucket(self, status: str, item_id: str) -> str:
        """
        Compute status bucket for partition spreading.

        Distributes items across multiple partitions to prevent hot partition
        issues when many items share the same status (e.g., PENDING).

        Args:
            status: The status value (e.g., "PENDING")
            item_id: Unique item ID for consistent bucket assignment

        Returns:
            Status bucket key (e.g., "PENDING#3")
        """
        bucket = hash(item_id) % self.NUM_STATUS_BUCKETS
        return f"{status}#{bucket}"

    def _query_reviewed_items_by_date_range(
        self,
        start_date: datetime | None,
        end_date: datetime | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Query reviewed items using ReviewedAtIndex GSI for efficient time-range queries.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of results

        Returns:
            List of item dictionaries
        """
        # Determine the date range
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            # Default to last 90 days if no start date specified
            start_date = end_date - timedelta(days=90)

        # Compute the months we need to query
        months_to_query: list[str] = []
        current = start_date.replace(day=1)
        while current <= end_date:
            months_to_query.append(current.strftime("%Y-%m"))
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        # Query each month partition and collect results
        all_items: list[dict[str, Any]] = []
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())

        for month in months_to_query:
            query_params: dict[str, Any] = {
                "IndexName": "ReviewedAtIndex",
                "KeyConditionExpression": (
                    "reviewedAtMonth = :month AND "
                    "reviewedAtTimestamp BETWEEN :start AND :end"
                ),
                "ExpressionAttributeValues": {
                    ":month": month,
                    ":start": start_timestamp,
                    ":end": end_timestamp,
                },
                "ScanIndexForward": False,  # Descending order
            }
            response = self.table.query(**query_params)
            all_items.extend(response.get("Items", []))

            if len(all_items) >= limit:
                break

        return all_items[:limit]

    def _generate_approval_id(self) -> str:
        """Generate unique approval ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"approval-{timestamp}-{unique_id}"

    def _calculate_expiry(self) -> str:
        """Calculate expiration timestamp."""
        expiry_time = time.time() + (self.timeout_hours * 60 * 60)
        return datetime.fromtimestamp(expiry_time).isoformat()

    def create_approval_request(
        self,
        patch_id: str,
        vulnerability_id: str,
        severity: PatchSeverity = PatchSeverity.MEDIUM,
        patch_diff: str = "",
        original_code: str = "",
        sandbox_results: dict[str, Any] | None = None,
        reviewer_email: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """
        Create a new approval request for a security patch.

        Args:
            patch_id: Identifier of the patch
            vulnerability_id: Identifier of the vulnerability
            severity: Severity level of the patch
            patch_diff: The code changes
            original_code: The vulnerable code
            sandbox_results: Results from sandbox testing
            reviewer_email: Optional assigned reviewer
            metadata: Additional context

        Returns:
            Created ApprovalRequest instance

        Raises:
            HITLApprovalError: If creation fails
        """
        try:
            request = ApprovalRequest(
                approval_id=self._generate_approval_id(),
                patch_id=patch_id,
                vulnerability_id=vulnerability_id,
                status=ApprovalStatus.PENDING,
                severity=severity,
                created_at=datetime.now().isoformat(),
                expires_at=self._calculate_expiry(),
                reviewer_email=reviewer_email,
                sandbox_test_results=sandbox_results or {},
                patch_diff=patch_diff,
                original_code=original_code,
                metadata=metadata or {},
            )

            # Save to database
            self._save_request(request)

            logger.info(
                f"Created approval request {request.approval_id} "
                f"(patch: {patch_id}, severity: {severity.value})"
            )

            return request

        except Exception as e:
            logger.error(f"Failed to create approval request: {e}")
            raise HITLApprovalError(f"Failed to create approval request: {e}") from e

    def create_or_auto_approve(
        self,
        patch_id: str,
        vulnerability_id: str,
        organization_id: str,
        policy_id: str | None = None,
        severity: PatchSeverity = PatchSeverity.MEDIUM,
        operation: str = "security_patch",
        repository: str = "",
        patch_diff: str = "",
        original_code: str = "",
        sandbox_results: dict[str, Any] | None = None,
        reviewer_email: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> HITLDecision:
        """
        Check autonomy policy and create approval request if needed.

        This method integrates with the AutonomyPolicyService to determine
        whether HITL approval is required based on the organization's policy.

        If HITL is not required, the action can be auto-approved without
        creating an approval request (though it's still logged for audit).

        Args:
            patch_id: Identifier of the patch
            vulnerability_id: Identifier of the vulnerability
            organization_id: Organization identifier (tenant)
            policy_id: Specific policy ID (or fetches org default)
            severity: Severity level of the patch
            operation: Type of operation (e.g., "security_patch", "deployment")
            repository: Repository name (optional)
            patch_diff: The code changes
            original_code: The vulnerable code
            sandbox_results: Results from sandbox testing
            reviewer_email: Optional assigned reviewer
            metadata: Additional context

        Returns:
            HITLDecision indicating whether HITL is required and the result

        Example:
            >>> decision = service.create_or_auto_approve(
            ...     patch_id="patch-123",
            ...     vulnerability_id="vuln-456",
            ...     organization_id="org-789",
            ...     severity=PatchSeverity.HIGH,
            ... )
            >>> if decision.requires_hitl:
            ...     # Wait for human approval
            ...     await wait_for_approval(decision.approval_request.approval_id)
            ... else:
            ...     # Action was auto-approved
            ...     apply_patch(patch_id)
        """
        # Lazy import to avoid circular dependencies
        global _autonomy_service
        if _autonomy_service is None:
            try:
                from src.services.autonomy_policy_service import (
                    AutonomyServiceMode,
                    create_autonomy_policy_service,
                )

                mode = (
                    AutonomyServiceMode.AWS
                    if os.environ.get("USE_AWS_DYNAMODB")
                    else AutonomyServiceMode.MOCK
                )
                _autonomy_service = create_autonomy_policy_service(mode=mode)
            except Exception as e:
                logger.warning(f"Could not load autonomy policy service: {e}")
                # Fall back to requiring HITL
                return self._fallback_to_hitl(
                    patch_id=patch_id,
                    vulnerability_id=vulnerability_id,
                    severity=severity,
                    patch_diff=patch_diff,
                    original_code=original_code,
                    sandbox_results=sandbox_results,
                    reviewer_email=reviewer_email,
                    metadata=metadata,
                    organization_id=organization_id,
                    policy_id=policy_id,
                    reason="Autonomy service unavailable - defaulting to HITL",
                )

        # Get the organization's policy
        if policy_id:
            policy = _autonomy_service.get_policy(policy_id)
        else:
            policy = _autonomy_service.get_policy_for_organization(organization_id)

        if not policy:
            logger.warning(f"No autonomy policy found for org {organization_id}")
            return self._fallback_to_hitl(
                patch_id=patch_id,
                vulnerability_id=vulnerability_id,
                severity=severity,
                patch_diff=patch_diff,
                original_code=original_code,
                sandbox_results=sandbox_results,
                reviewer_email=reviewer_email,
                metadata=metadata,
                organization_id=organization_id,
                policy_id=policy_id,
                reason="No autonomy policy configured - defaulting to HITL",
            )

        # Check if HITL is required based on policy
        requires_hitl = policy.requires_hitl(
            severity=severity.value,
            operation=operation,
            repository=repository,
        )

        autonomy_level = policy.get_autonomy_level(
            severity=severity.value,
            operation=operation,
            repository=repository,
        )

        guardrail_triggered = operation in policy.guardrails

        if requires_hitl:
            # Create approval request
            request = self.create_approval_request(
                patch_id=patch_id,
                vulnerability_id=vulnerability_id,
                severity=severity,
                patch_diff=patch_diff,
                original_code=original_code,
                sandbox_results=sandbox_results,
                reviewer_email=reviewer_email,
                metadata={
                    **(metadata or {}),
                    "organization_id": organization_id,
                    "policy_id": policy.policy_id,
                    "autonomy_level": autonomy_level.value,
                    "operation": operation,
                    "repository": repository,
                },
            )

            reason = self._build_hitl_reason(
                policy, severity, operation, autonomy_level, guardrail_triggered
            )

            logger.info(
                f"HITL required for patch {patch_id} (org: {organization_id}, "
                f"severity: {severity.value}, level: {autonomy_level.value})"
            )

            return HITLDecision(
                requires_hitl=True,
                approval_request=request,
                autonomy_level=autonomy_level.value,
                reason=reason,
                auto_approved=False,
                guardrail_triggered=guardrail_triggered,
                organization_id=organization_id,
                policy_id=policy.policy_id,
            )

        else:
            # Auto-approve - record decision for audit but don't require approval
            logger.info(
                f"Auto-approved patch {patch_id} (org: {organization_id}, "
                f"severity: {severity.value}, level: {autonomy_level.value})"
            )

            # Record the auto-approval decision for audit trail
            _autonomy_service.record_autonomous_decision(
                policy_id=policy.policy_id,
                execution_id=f"auto-{patch_id}",
                severity=severity.value,
                operation=operation,
                repository=repository,
                autonomy_level=autonomy_level,
                hitl_required=False,
                hitl_bypassed=True,
                auto_approved=True,
            )

            return HITLDecision(
                requires_hitl=False,
                approval_request=None,
                autonomy_level=autonomy_level.value,
                reason=f"Auto-approved: {autonomy_level.value} allows automatic processing",
                auto_approved=True,
                guardrail_triggered=False,
                organization_id=organization_id,
                policy_id=policy.policy_id,
            )

    def _fallback_to_hitl(
        self,
        patch_id: str,
        vulnerability_id: str,
        severity: PatchSeverity,
        patch_diff: str,
        original_code: str,
        sandbox_results: dict[str, Any] | None,
        reviewer_email: str | None,
        metadata: dict[str, Any] | None,
        organization_id: str,
        policy_id: str | None,
        reason: str,
    ) -> HITLDecision:
        """Create approval request when falling back to HITL mode."""
        request = self.create_approval_request(
            patch_id=patch_id,
            vulnerability_id=vulnerability_id,
            severity=severity,
            patch_diff=patch_diff,
            original_code=original_code,
            sandbox_results=sandbox_results,
            reviewer_email=reviewer_email,
            metadata={
                **(metadata or {}),
                "organization_id": organization_id,
                "fallback_reason": reason,
            },
        )

        return HITLDecision(
            requires_hitl=True,
            approval_request=request,
            autonomy_level="unknown",
            reason=reason,
            auto_approved=False,
            guardrail_triggered=False,
            organization_id=organization_id,
            policy_id=policy_id,
        )

    def _build_hitl_reason(
        self,
        policy: Any,
        severity: PatchSeverity,
        operation: str,
        autonomy_level: Any,
        guardrail_triggered: bool,
    ) -> str:
        """Build explanation for why HITL is required."""
        if guardrail_triggered:
            return f"Guardrail triggered: '{operation}' always requires HITL approval"
        elif autonomy_level.value == "full_hitl":
            return "Policy requires HITL approval for all actions"
        elif autonomy_level.value == "critical_hitl":
            return f"Policy requires HITL for {severity.value} severity actions"
        else:
            return f"HITL required based on autonomy level: {autonomy_level.value}"

    def _save_request(self, request: ApprovalRequest) -> None:
        """Save approval request to database."""
        # Compute status bucket for partition spreading
        status_bucket = self._compute_status_bucket(
            request.status.value, request.approval_id
        )

        # Convert to dict for storage
        item = {
            "approvalId": request.approval_id,
            "patchId": request.patch_id,
            "vulnerabilityId": request.vulnerability_id,
            "status": request.status.value,
            "statusBucket": status_bucket,  # Partition spreading key
            "severity": request.severity.value,
            "createdAt": request.created_at,
            "expiresAt": request.expires_at,
            "reviewerEmail": request.reviewer_email,
            "reviewedAt": request.reviewed_at,
            "reviewedBy": request.reviewed_by,
            "decisionReason": request.decision_reason,
            "sandboxTestResults": request.sandbox_test_results,
            "patchDiff": request.patch_diff,
            "originalCode": request.original_code,
            "metadata": request.metadata,
            # Escalation tracking fields
            "escalationCount": request.escalation_count,
            "lastEscalatedAt": request.last_escalated_at,
            "warningSentAt": request.warning_sent_at,
            # DynamoDB metadata
            "createdAtTimestamp": int(
                datetime.fromisoformat(request.created_at).timestamp()
            ),
            "updatedAt": int(time.time()),
            "ttl": int(time.time()) + (self.DEFAULT_TTL_DAYS * 24 * 60 * 60),
        }

        if self.mode == HITLMode.MOCK:
            self.mock_store[request.approval_id] = item
            logger.debug(f"[MOCK] Saved approval request: {request.approval_id}")
        else:
            self.table.put_item(Item=item)
            logger.debug(f"Saved approval request to DynamoDB: {request.approval_id}")

    def get_request(self, approval_id: str) -> ApprovalRequest | None:
        """
        Retrieve an approval request by ID.

        Args:
            approval_id: Approval request identifier

        Returns:
            ApprovalRequest or None if not found
        """
        try:
            if self.mode == HITLMode.MOCK:
                item = self.mock_store.get(approval_id)
            else:
                response = self.table.get_item(Key={"approvalId": approval_id})
                item = response.get("Item")

            if not item:
                return None

            return self._item_to_request(item)

        except Exception as e:
            logger.error(f"Failed to get approval request {approval_id}: {e}")
            return None

    def _item_to_request(self, item: dict[str, Any]) -> ApprovalRequest:
        """Convert DynamoDB item to ApprovalRequest."""
        return ApprovalRequest(
            approval_id=item.get("approvalId", ""),
            patch_id=item.get("patchId", ""),
            vulnerability_id=item.get("vulnerabilityId", ""),
            status=ApprovalStatus(item.get("status", "PENDING")),
            severity=PatchSeverity(item.get("severity", "MEDIUM")),
            created_at=item.get("createdAt", ""),
            expires_at=item.get("expiresAt", ""),
            reviewer_email=item.get("reviewerEmail"),
            reviewed_at=item.get("reviewedAt"),
            reviewed_by=item.get("reviewedBy"),
            decision_reason=item.get("decisionReason"),
            sandbox_test_results=item.get("sandboxTestResults", {}),
            patch_diff=item.get("patchDiff", ""),
            original_code=item.get("originalCode", ""),
            metadata=item.get("metadata", {}),
            escalation_count=item.get("escalationCount", 0),
            last_escalated_at=item.get("lastEscalatedAt"),
            warning_sent_at=item.get("warningSentAt"),
        )

    def _request_to_dict(self, request: ApprovalRequest) -> dict[str, Any]:
        """Convert ApprovalRequest to dict for API responses."""
        return {
            "approval_id": request.approval_id,
            "patch_id": request.patch_id,
            "vulnerability_id": request.vulnerability_id,
            "status": request.status.value,
            "severity": request.severity.value,
            "created_at": request.created_at,
            "expires_at": request.expires_at,
            "reviewer_email": request.reviewer_email,
            "reviewed_at": request.reviewed_at,
            "reviewed_by": request.reviewed_by,
            "decision_reason": request.decision_reason,
            "sandbox_test_results": request.sandbox_test_results,
            "patch_diff": request.patch_diff,
            "original_code": request.original_code,
            "metadata": request.metadata,
            "escalation_count": request.escalation_count,
            "last_escalated_at": request.last_escalated_at,
            "warning_sent_at": request.warning_sent_at,
        }

    def get_all_requests(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get all approval requests regardless of status.

        Args:
            limit: Maximum number of results

        Returns:
            List of approval request dicts
        """
        try:
            if self.mode == HITLMode.MOCK:
                items = list(self.mock_store.values())
                # Sort by created_at descending (newest first)
                items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
                requests = [self._item_to_request(item) for item in items[:limit]]
                return [self._request_to_dict(r) for r in requests]

            # Real DynamoDB scan (for all statuses)
            response = self.table.scan(Limit=limit)
            items = response.get("Items", [])
            requests = [self._item_to_request(item) for item in items]
            return [self._request_to_dict(r) for r in requests]

        except Exception as e:
            logger.error(f"Failed to get all requests: {e}")
            return []

    def get_pending_requests(
        self,
        severity: PatchSeverity | None = None,
        limit: int = 100,
    ) -> list[ApprovalRequest]:
        """
        Get all pending approval requests.

        Args:
            severity: Optional filter by severity
            limit: Maximum number of results

        Returns:
            List of pending ApprovalRequest objects
        """
        try:
            if self.mode == HITLMode.MOCK:
                requests = [
                    self._item_to_request(item)
                    for item in self.mock_store.values()
                    if item.get("status") == ApprovalStatus.PENDING.value
                ]
                if severity:
                    requests = [r for r in requests if r.severity == severity]
                # Sort by severity (CRITICAL first) then created_at
                severity_order = {
                    PatchSeverity.CRITICAL: 0,
                    PatchSeverity.HIGH: 1,
                    PatchSeverity.MEDIUM: 2,
                    PatchSeverity.LOW: 3,
                }
                requests.sort(key=lambda r: (severity_order[r.severity], r.created_at))
                return requests[:limit]

            # Scatter-gather across all status buckets (prevents hot partition)
            all_items: list[dict[str, Any]] = []
            status = ApprovalStatus.PENDING.value

            for bucket in range(self.NUM_STATUS_BUCKETS):
                status_bucket = f"{status}#{bucket}"
                query_params: dict[str, Any] = {
                    "IndexName": "StatusBucketIndex",
                    "KeyConditionExpression": "statusBucket = :sb",
                    "ExpressionAttributeValues": {":sb": status_bucket},
                    "ScanIndexForward": True,
                }
                if severity:
                    query_params["FilterExpression"] = "severity = :severity"
                    query_params["ExpressionAttributeValues"][
                        ":severity"
                    ] = severity.value

                response = self.table.query(**query_params)
                all_items.extend(response.get("Items", []))

            # Sort by createdAtTimestamp and limit
            all_items.sort(key=lambda x: x.get("createdAtTimestamp", 0))
            return [self._item_to_request(item) for item in all_items[:limit]]

        except Exception as e:
            logger.error(f"Failed to get pending requests: {e}")
            return []

    def get_requests_by_patch(self, patch_id: str) -> list[ApprovalRequest]:
        """
        Get all approval requests for a specific patch.

        Args:
            patch_id: Patch identifier

        Returns:
            List of ApprovalRequest objects
        """
        try:
            if self.mode == HITLMode.MOCK:
                return [
                    self._item_to_request(item)
                    for item in self.mock_store.values()
                    if item.get("patchId") == patch_id
                ]

            # Real DynamoDB query using PatchIdIndex GSI
            response = self.table.query(
                IndexName="PatchIdIndex",
                KeyConditionExpression="patchId = :patchId",
                ExpressionAttributeValues={":patchId": patch_id},
            )
            return [self._item_to_request(item) for item in response.get("Items", [])]

        except Exception as e:
            logger.error(f"Failed to get requests for patch {patch_id}: {e}")
            return []

    def approve_request(
        self,
        approval_id: str,
        reviewer_id: str,
        reason: str | None = None,
    ) -> bool:
        """
        Approve an approval request.

        Args:
            approval_id: Approval request identifier
            reviewer_id: Identity of the reviewer (email or username)
            reason: Optional reason for approval

        Returns:
            True if successful
        """
        return self._process_decision(
            approval_id=approval_id,
            status=ApprovalStatus.APPROVED,
            reviewer_id=reviewer_id,
            reason=reason,
        )

    def reject_request(
        self,
        approval_id: str,
        reviewer_id: str,
        reason: str,
    ) -> bool:
        """
        Reject an approval request.

        Args:
            approval_id: Approval request identifier
            reviewer_id: Identity of the reviewer
            reason: Required reason for rejection

        Returns:
            True if successful
        """
        if not reason:
            raise HITLApprovalError("Rejection reason is required")

        return self._process_decision(
            approval_id=approval_id,
            status=ApprovalStatus.REJECTED,
            reviewer_id=reviewer_id,
            reason=reason,
        )

    def _process_decision(
        self,
        approval_id: str,
        status: ApprovalStatus,
        reviewer_id: str,
        reason: str | None,
    ) -> bool:
        """Process an approval decision."""
        try:
            request = self.get_request(approval_id)
            if not request:
                logger.warning(f"Approval request not found: {approval_id}")
                return False

            if request.status != ApprovalStatus.PENDING:
                logger.warning(
                    f"Cannot process decision for non-pending request: {approval_id}"
                )
                return False

            # Check if expired
            if self._is_expired(request):
                logger.warning(f"Approval request has expired: {approval_id}")
                self._mark_expired(approval_id)
                return False

            # Update the request
            now_dt = datetime.now()
            now = now_dt.isoformat()
            reviewed_at_month = now_dt.strftime("%Y-%m")  # For time-range GSI
            reviewed_at_timestamp = int(now_dt.timestamp())

            if self.mode == HITLMode.MOCK:
                if approval_id in self.mock_store:
                    self.mock_store[approval_id].update(
                        {
                            "status": status.value,
                            "reviewedAt": now,
                            "reviewedAtMonth": reviewed_at_month,
                            "reviewedAtTimestamp": reviewed_at_timestamp,
                            "reviewedBy": reviewer_id,
                            "decisionReason": reason,
                            "updatedAt": int(time.time()),
                        }
                    )
            else:
                try:
                    # Use conditional write to prevent race conditions
                    # Only update if the item exists and status is still PENDING
                    new_status_bucket = self._compute_status_bucket(
                        status.value, approval_id
                    )
                    self.table.update_item(
                        Key={"approvalId": approval_id},
                        UpdateExpression=(
                            "SET #status = :status, "
                            "statusBucket = :statusBucket, "
                            "reviewedAt = :reviewedAt, "
                            "reviewedAtMonth = :reviewedAtMonth, "
                            "reviewedAtTimestamp = :reviewedAtTimestamp, "
                            "reviewedBy = :reviewedBy, "
                            "decisionReason = :reason, "
                            "updatedAt = :updatedAt"
                        ),
                        ConditionExpression=(
                            "attribute_exists(approvalId) AND #status = :expected_status"
                        ),
                        ExpressionAttributeNames={"#status": "status"},
                        ExpressionAttributeValues={
                            ":status": status.value,
                            ":statusBucket": new_status_bucket,
                            ":reviewedAt": now,
                            ":reviewedAtMonth": reviewed_at_month,
                            ":reviewedAtTimestamp": reviewed_at_timestamp,
                            ":reviewedBy": reviewer_id,
                            ":reason": reason,
                            ":updatedAt": int(time.time()),
                            ":expected_status": ApprovalStatus.PENDING.value,
                        },
                    )
                except ClientError as e:
                    if (
                        e.response.get("Error", {}).get("Code")
                        == "ConditionalCheckFailedException"
                    ):
                        logger.warning(
                            f"Conditional check failed for {approval_id} - "
                            "request may have been processed by another reviewer"
                        )
                        return False
                    raise

            logger.info(
                f"Processed {status.value} decision for {approval_id} "
                f"by {reviewer_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to process decision: {e}")
            return False

    def _is_expired(self, request: ApprovalRequest) -> bool:
        """Check if an approval request has expired."""
        if not request.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(request.expires_at)
            return datetime.now() > expires
        except ValueError:
            return False

    def _mark_expired(self, approval_id: str) -> None:
        """Mark an approval request as expired."""
        try:
            new_status_bucket = self._compute_status_bucket(
                ApprovalStatus.EXPIRED.value, approval_id
            )
            if self.mode == HITLMode.MOCK:
                if approval_id in self.mock_store:
                    self.mock_store[approval_id][
                        "status"
                    ] = ApprovalStatus.EXPIRED.value
                    self.mock_store[approval_id]["statusBucket"] = new_status_bucket
            else:
                self.table.update_item(
                    Key={"approvalId": approval_id},
                    UpdateExpression=(
                        "SET #status = :status, "
                        "statusBucket = :statusBucket, "
                        "updatedAt = :updatedAt"
                    ),
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": ApprovalStatus.EXPIRED.value,
                        ":statusBucket": new_status_bucket,
                        ":updatedAt": int(time.time()),
                    },
                )
            logger.info(f"Marked approval request as expired: {approval_id}")
        except Exception as e:
            logger.error(f"Failed to mark request as expired: {e}")

    def cancel_request(self, approval_id: str, reason: str | None = None) -> bool:
        """
        Cancel an approval request.

        Args:
            approval_id: Approval request identifier
            reason: Optional cancellation reason

        Returns:
            True if successful
        """
        try:
            if self.mode == HITLMode.MOCK:
                if approval_id in self.mock_store:
                    self.mock_store[approval_id].update(
                        {
                            "status": ApprovalStatus.CANCELLED.value,
                            "decisionReason": reason,
                            "updatedAt": int(time.time()),
                        }
                    )
                    return True
                return False

            try:
                # Use conditional write - only cancel if still PENDING
                new_status_bucket = self._compute_status_bucket(
                    ApprovalStatus.CANCELLED.value, approval_id
                )
                self.table.update_item(
                    Key={"approvalId": approval_id},
                    UpdateExpression=(
                        "SET #status = :status, "
                        "statusBucket = :statusBucket, "
                        "decisionReason = :reason, "
                        "updatedAt = :updatedAt"
                    ),
                    ConditionExpression=(
                        "attribute_exists(approvalId) AND #status = :expected_status"
                    ),
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": ApprovalStatus.CANCELLED.value,
                        ":statusBucket": new_status_bucket,
                        ":reason": reason,
                        ":updatedAt": int(time.time()),
                        ":expected_status": ApprovalStatus.PENDING.value,
                    },
                )
            except ClientError as e:
                if (
                    e.response.get("Error", {}).get("Code")
                    == "ConditionalCheckFailedException"
                ):
                    logger.warning(
                        f"Cannot cancel {approval_id} - request is no longer pending"
                    )
                    return False
                raise

            logger.info(f"Cancelled approval request: {approval_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel request: {e}")
            return False

    def get_audit_log(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Get audit log of all approval decisions.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of records

        Returns:
            List of audit log entries
        """
        try:
            # Get all non-pending requests (i.e., decisions made)
            if self.mode == HITLMode.MOCK:
                items = [
                    item
                    for item in self.mock_store.values()
                    if item.get("status") != ApprovalStatus.PENDING.value
                ]
                # Filter by date range in mock mode
                if start_date or end_date:
                    filtered_items = []
                    for item in items:
                        reviewed_at = item.get("reviewedAt")
                        if reviewed_at:
                            try:
                                reviewed_dt = datetime.fromisoformat(reviewed_at)
                                if start_date and reviewed_dt < start_date:
                                    continue
                                if end_date and reviewed_dt > end_date:
                                    continue
                            except ValueError:
                                continue
                        filtered_items.append(item)
                    items = filtered_items
            else:
                # Use ReviewedAtIndex GSI for efficient time-range queries
                items = self._query_reviewed_items_by_date_range(
                    start_date, end_date, limit
                )

            audit_entries = []
            for item in items:
                audit_entries.append(
                    {
                        "approval_id": item.get("approvalId"),
                        "patch_id": item.get("patchId"),
                        "vulnerability_id": item.get("vulnerabilityId"),
                        "status": item.get("status"),
                        "severity": item.get("severity"),
                        "reviewed_by": item.get("reviewedBy"),
                        "reviewed_at": item.get("reviewedAt"),
                        "decision_reason": item.get("decisionReason"),
                        "created_at": item.get("createdAt"),
                    }
                )

            # Sort by reviewed_at descending
            audit_entries.sort(key=lambda x: x.get("reviewed_at") or "", reverse=True)
            return audit_entries[:limit]

        except Exception as e:
            logger.error(f"Failed to get audit log: {e}")
            return []

    def process_expirations(self) -> ExpirationProcessingResult:
        """
        Process all pending approval requests for expiration handling.

        This method is designed to be called by a scheduled Lambda function (hourly).
        It performs the following:
        1. Scans all PENDING requests
        2. For requests approaching expiration (75% of timeout): sends warning
        3. For expired CRITICAL/HIGH severity: escalates to backup reviewer
        4. For expired MEDIUM/LOW severity: marks as expired, queues for re-processing

        Returns:
            ExpirationProcessingResult with summary of actions taken
        """
        result = ExpirationProcessingResult(
            processed=0,
            escalated=0,
            expired=0,
            warnings_sent=0,
            errors=0,
        )

        try:
            # Get all pending requests
            pending_requests = self.get_pending_requests(limit=1000)
            logger.info(f"Processing {len(pending_requests)} pending approval requests")

            for request in pending_requests:
                result.processed += 1

                try:
                    action = self._determine_action(request)

                    if action == EscalationAction.WARN:
                        exp_result = self._send_warning(request)
                        if exp_result.success:
                            result.warnings_sent += 1
                        result.details.append(exp_result)

                    elif action == EscalationAction.ESCALATE:
                        exp_result = self._escalate_request(request)
                        if exp_result.success:
                            result.escalated += 1
                        result.details.append(exp_result)

                    elif action == EscalationAction.EXPIRE:
                        exp_result = self._expire_request(request)
                        if exp_result.success:
                            result.expired += 1
                        result.details.append(exp_result)

                except Exception as e:
                    logger.error(f"Error processing request {request.approval_id}: {e}")
                    result.errors += 1
                    result.details.append(
                        ExpirationResult(
                            approval_id=request.approval_id,
                            action=EscalationAction.EXPIRE,
                            success=False,
                            message=str(e),
                        )
                    )

            # Log audit entry for processing run
            self._log_audit(
                event_type="expiration_processing",
                details={
                    "processed": result.processed,
                    "escalated": result.escalated,
                    "expired": result.expired,
                    "warnings_sent": result.warnings_sent,
                    "errors": result.errors,
                },
            )

            logger.info(
                f"Expiration processing complete: {result.processed} processed, "
                f"{result.escalated} escalated, {result.expired} expired, "
                f"{result.warnings_sent} warnings, {result.errors} errors"
            )

        except Exception as e:
            logger.error(f"Failed to process expirations: {e}")
            result.errors += 1

        return result

    def _determine_action(self, request: ApprovalRequest) -> EscalationAction | None:
        """
        Determine what action to take for a pending request.

        Args:
            request: The approval request to evaluate

        Returns:
            EscalationAction or None if no action needed
        """
        now = datetime.now()

        try:
            created = datetime.fromisoformat(request.created_at)
            expires = datetime.fromisoformat(request.expires_at)
        except ValueError:
            logger.warning(f"Invalid timestamps for request {request.approval_id}")
            return None

        total_duration = (expires - created).total_seconds()
        elapsed = (now - created).total_seconds()

        if elapsed <= 0 or total_duration <= 0:
            return None

        elapsed_percent = elapsed / total_duration

        # Check if expired
        if now > expires:
            # CRITICAL/HIGH severity: escalate if under max escalations
            if request.severity in (PatchSeverity.CRITICAL, PatchSeverity.HIGH):
                if request.escalation_count < self.MAX_ESCALATIONS:
                    return EscalationAction.ESCALATE
                else:
                    # Max escalations reached, mark as expired
                    return EscalationAction.EXPIRE
            else:
                # MEDIUM/LOW severity: expire and re-queue
                return EscalationAction.EXPIRE

        # Check if warning threshold reached (and warning not already sent)
        if elapsed_percent >= self.WARNING_THRESHOLD_PERCENT:
            if not request.warning_sent_at:
                return EscalationAction.WARN

        return None

    def _send_warning(self, request: ApprovalRequest) -> ExpirationResult:
        """
        Send expiration warning for a request.

        Args:
            request: The approval request

        Returns:
            ExpirationResult
        """
        try:
            # Send notification if service available
            if self.notification_service:
                recipients = [request.reviewer_email] if request.reviewer_email else []
                if not recipients and self.backup_reviewers:
                    recipients = self.backup_reviewers[:1]  # First backup as fallback

                if recipients:
                    self.notification_service.send_expiration_warning(
                        approval_id=request.approval_id,
                        patch_id=request.patch_id,
                        severity=request.severity.value,
                        expires_at=request.expires_at,
                        recipients=recipients,
                    )

            # Update warning_sent_at timestamp
            self._update_request_field(
                request.approval_id,
                "warningSentAt",
                datetime.now().isoformat(),
            )

            # Log audit entry
            self._log_audit(
                event_type="expiration_warning_sent",
                approval_id=request.approval_id,
                details={
                    "severity": request.severity.value,
                    "expires_at": request.expires_at,
                },
            )

            logger.info(f"Sent expiration warning for {request.approval_id}")

            return ExpirationResult(
                approval_id=request.approval_id,
                action=EscalationAction.WARN,
                success=True,
                message="Expiration warning sent",
            )

        except Exception as e:
            logger.error(f"Failed to send warning for {request.approval_id}: {e}")
            return ExpirationResult(
                approval_id=request.approval_id,
                action=EscalationAction.WARN,
                success=False,
                message=str(e),
            )

    def _escalate_request(self, request: ApprovalRequest) -> ExpirationResult:
        """
        Escalate a request to the next backup reviewer.

        Args:
            request: The approval request to escalate

        Returns:
            ExpirationResult
        """
        try:
            # Determine next escalation reviewer
            escalation_index = request.escalation_count
            if escalation_index >= len(self.backup_reviewers):
                # No more backup reviewers, mark as expired
                return self._expire_request(request)

            new_reviewer = self.backup_reviewers[escalation_index]
            new_escalation_count = request.escalation_count + 1

            # Calculate new expiration time
            new_expires_at = datetime.now() + timedelta(
                hours=self.escalation_timeout_hours
            )

            # Prepare update values with explicit types
            status_value: str = ApprovalStatus.ESCALATED.value
            last_escalated_value: str = datetime.now().isoformat()
            expires_value: str = new_expires_at.isoformat()
            updated_at_value: int = int(time.time())

            # Compute new status bucket for partition spreading
            new_status_bucket = self._compute_status_bucket(
                status_value, request.approval_id
            )

            if self.mode == HITLMode.MOCK:
                if request.approval_id in self.mock_store:
                    self.mock_store[request.approval_id].update(
                        {
                            "status": status_value,
                            "statusBucket": new_status_bucket,
                            "reviewerEmail": new_reviewer,
                            "escalationCount": new_escalation_count,
                            "lastEscalatedAt": last_escalated_value,
                            "expiresAt": expires_value,
                            "updatedAt": updated_at_value,
                        }
                    )
            else:
                self.table.update_item(
                    Key={"approvalId": request.approval_id},
                    UpdateExpression=(
                        "SET #status = :status, "
                        "statusBucket = :statusBucket, "
                        "reviewerEmail = :reviewer, "
                        "escalationCount = :count, "
                        "lastEscalatedAt = :escalated, "
                        "expiresAt = :expires, "
                        "updatedAt = :updated"
                    ),
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": status_value,
                        ":statusBucket": new_status_bucket,
                        ":reviewer": new_reviewer,
                        ":count": new_escalation_count,
                        ":escalated": last_escalated_value,
                        ":expires": expires_value,
                        ":updated": updated_at_value,
                    },
                )

            # Send escalation notification
            if self.notification_service:
                self.notification_service.send_escalation_notification(
                    approval_id=request.approval_id,
                    patch_id=request.patch_id,
                    vulnerability_id=request.vulnerability_id,
                    severity=request.severity.value,
                    original_reviewer=request.reviewer_email,
                    escalated_to=new_reviewer,
                    escalation_count=new_escalation_count,
                    expires_at=new_expires_at.isoformat(),
                    sandbox_results=request.sandbox_test_results,
                    patch_diff=request.patch_diff,
                )

            # Log audit entry
            self._log_audit(
                event_type="escalation",
                approval_id=request.approval_id,
                details={
                    "severity": request.severity.value,
                    "original_reviewer": request.reviewer_email,
                    "escalated_to": new_reviewer,
                    "escalation_count": new_escalation_count,
                    "new_expires_at": new_expires_at.isoformat(),
                },
            )

            logger.info(
                f"Escalated {request.approval_id} to {new_reviewer} "
                f"(escalation #{new_escalation_count})"
            )

            return ExpirationResult(
                approval_id=request.approval_id,
                action=EscalationAction.ESCALATE,
                success=True,
                message=f"Escalated to {new_reviewer}",
                escalated_to=new_reviewer,
            )

        except Exception as e:
            logger.error(f"Failed to escalate {request.approval_id}: {e}")
            return ExpirationResult(
                approval_id=request.approval_id,
                action=EscalationAction.ESCALATE,
                success=False,
                message=str(e),
            )

    def _expire_request(self, request: ApprovalRequest) -> ExpirationResult:
        """
        Mark a request as expired and queue for re-processing.

        Args:
            request: The approval request to expire

        Returns:
            ExpirationResult
        """
        try:
            # Mark as expired
            self._mark_expired(request.approval_id)

            # Send expiration notification
            if self.notification_service:
                recipients = []
                if request.reviewer_email:
                    recipients.append(request.reviewer_email)
                recipients.extend(self.backup_reviewers)

                if recipients:
                    self.notification_service.send_expiration_notification(
                        approval_id=request.approval_id,
                        patch_id=request.patch_id,
                        vulnerability_id=request.vulnerability_id,
                        severity=request.severity.value,
                        recipients=recipients,
                        requeued=True,
                    )

            # Log audit entry
            self._log_audit(
                event_type="expiration",
                approval_id=request.approval_id,
                details={
                    "severity": request.severity.value,
                    "escalation_count": request.escalation_count,
                    "requeued": True,
                },
            )

            logger.info(f"Expired and re-queued {request.approval_id}")

            return ExpirationResult(
                approval_id=request.approval_id,
                action=EscalationAction.EXPIRE,
                success=True,
                message="Expired and queued for re-processing",
            )

        except Exception as e:
            logger.error(f"Failed to expire {request.approval_id}: {e}")
            return ExpirationResult(
                approval_id=request.approval_id,
                action=EscalationAction.EXPIRE,
                success=False,
                message=str(e),
            )

    def _update_request_field(
        self,
        approval_id: str,
        field_name: str,
        value: Any,
    ) -> None:
        """
        Update a single field on an approval request.

        Args:
            approval_id: The approval request ID
            field_name: DynamoDB attribute name
            value: New value
        """
        # If updating status, also update statusBucket for partition spreading
        if field_name == "status":
            new_status_bucket = self._compute_status_bucket(value, approval_id)
            if self.mode == HITLMode.MOCK:
                if approval_id in self.mock_store:
                    self.mock_store[approval_id][field_name] = value
                    self.mock_store[approval_id]["statusBucket"] = new_status_bucket
                    self.mock_store[approval_id]["updatedAt"] = int(time.time())
            else:
                self.table.update_item(
                    Key={"approvalId": approval_id},
                    UpdateExpression=(
                        "SET #status = :value, statusBucket = :sb, updatedAt = :updated"
                    ),
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":value": value,
                        ":sb": new_status_bucket,
                        ":updated": int(time.time()),
                    },
                )
        else:
            if self.mode == HITLMode.MOCK:
                if approval_id in self.mock_store:
                    self.mock_store[approval_id][field_name] = value
                    self.mock_store[approval_id]["updatedAt"] = int(time.time())
            else:
                self.table.update_item(
                    Key={"approvalId": approval_id},
                    UpdateExpression=f"SET {field_name} = :value, updatedAt = :updated",
                    ExpressionAttributeValues={
                        ":value": value,
                        ":updated": int(time.time()),
                    },
                )

    def _log_audit(
        self,
        event_type: str,
        approval_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an audit entry for compliance tracking.

        Args:
            event_type: Type of event (e.g., 'escalation', 'expiration')
            approval_id: Optional approval request ID
            details: Additional event details
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "approval_id": approval_id,
            "details": details or {},
        }
        self.audit_entries.append(entry)
        logger.debug(f"Audit: {event_type} - {approval_id or 'system'}")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get approval request statistics.

        Returns:
            Dictionary with approval statistics
        """
        try:
            if self.mode == HITLMode.MOCK:
                items = list(self.mock_store.values())
            else:
                # Full table scan (expensive - use with caution)
                response = self.table.scan()
                items = response.get("Items", [])

            # Use typed counters to avoid mypy issues with mixed-type dict
            pending_count = 0
            approved_count = 0
            rejected_count = 0
            expired_count = 0
            cancelled_count = 0
            by_severity: dict[str, int] = {
                "CRITICAL": 0,
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0,
            }
            approval_times: list[float] = []

            for item in items:
                status = item.get("status", "")
                severity = item.get("severity", "MEDIUM")

                # Count by status
                if status == ApprovalStatus.PENDING.value:
                    pending_count += 1
                elif status == ApprovalStatus.APPROVED.value:
                    approved_count += 1
                elif status == ApprovalStatus.REJECTED.value:
                    rejected_count += 1
                elif status == ApprovalStatus.EXPIRED.value:
                    expired_count += 1
                elif status == ApprovalStatus.CANCELLED.value:
                    cancelled_count += 1

                # Count by severity
                if severity in by_severity:
                    by_severity[severity] += 1

                # Calculate approval time for approved requests
                if status == ApprovalStatus.APPROVED.value:
                    created = item.get("createdAt")
                    reviewed = item.get("reviewedAt")
                    if created and reviewed:
                        try:
                            created_dt = datetime.fromisoformat(created)
                            reviewed_dt = datetime.fromisoformat(reviewed)
                            hours = (reviewed_dt - created_dt).total_seconds() / 3600
                            approval_times.append(hours)
                        except ValueError:
                            pass

            avg_approval_time = 0.0
            if approval_times:
                avg_approval_time = round(sum(approval_times) / len(approval_times), 2)

            return {
                "total_requests": len(items),
                "pending": pending_count,
                "approved": approved_count,
                "rejected": rejected_count,
                "expired": expired_count,
                "cancelled": cancelled_count,
                "by_severity": by_severity,
                "avg_approval_time_hours": avg_approval_time,
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}


# Factory function
def create_hitl_approval_service(
    use_mock: bool = False,
    timeout_hours: int | None = None,
) -> HITLApprovalService:
    """
    Create and return a HITLApprovalService instance.

    Args:
        use_mock: Force mock mode for testing
        timeout_hours: Custom approval timeout

    Returns:
        Configured HITLApprovalService instance
    """
    if use_mock:
        mode = HITLMode.MOCK
    else:
        mode = (
            HITLMode.AWS
            if BOTO3_AVAILABLE and os.environ.get("AWS_REGION")
            else HITLMode.MOCK
        )

    return HITLApprovalService(mode=mode, timeout_hours=timeout_hours)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - HITL Approval Service Demo")
    print("=" * 60)

    service = create_hitl_approval_service(use_mock=True)
    print(f"\nMode: {service.mode.value}")
    print(f"Table: {service.table_name}")
    print(f"Timeout: {service.timeout_hours}h")

    # Test create
    print("\nCreating approval request...")
    request = service.create_approval_request(
        patch_id="patch-sha256-upgrade",
        vulnerability_id="vuln-sha1-weak-hash",
        severity=PatchSeverity.HIGH,
        patch_diff="- hashlib.sha1(data)\n+ hashlib.sha256(data)",
        sandbox_results={"tests_passed": 42, "tests_failed": 0},
    )
    print(f"Created: {request.approval_id}")

    # Test retrieve
    print("\nRetrieving request...")
    retrieved = service.get_request(request.approval_id)
    print(f"Status: {retrieved.status.value if retrieved else 'Not found'}")

    # Test pending list
    print("\nGetting pending requests...")
    pending = service.get_pending_requests()
    print(f"Pending: {len(pending)}")

    # Test approve
    print("\nApproving request...")
    service.approve_request(
        request.approval_id,
        "security-lead@company.com",
        "Code review passed, tests look good",
    )
    approved = service.get_request(request.approval_id)
    print(f"New status: {approved.status.value if approved else 'Not found'}")

    # Test statistics
    print("\nGetting statistics...")
    stats = service.get_statistics()
    print(f"Stats: {stats}")

    print("\n" + "=" * 60)
    print("Demo complete!")
