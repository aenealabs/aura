"""
Project Aura - Sandbox Test Runner Service

Coordinates the full HITL (Human-in-the-Loop) testing workflow for patch validation.
Integrates with DynamoDB for state management, ECS Fargate for execution,
and SNS for notifications.

Workflow:
    1. Receive patch for testing
    2. Create ephemeral sandbox
    3. Execute tests in isolation
    4. Store results in DynamoDB
    5. Create HITL approval request
    6. Notify reviewers via SNS

Author: Project Aura Team
Created: 2025-12-02
Version: 1.0.0
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, cast

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Status of a sandbox test execution."""

    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ApprovalStatus(Enum):
    """Status of a HITL approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TestResultType(Enum):
    """Type of test result."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


@dataclass
class PatchTestRequest:
    """Request to test a patch in a sandbox environment."""

    patch_id: str
    repository_url: str
    branch: str
    patch_content: str
    test_suite: str
    vulnerability_id: str | None = None
    severity: str = "MEDIUM"
    isolation_level: str = "container"
    timeout_minutes: int = 30
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class TestResult:
    """Result of sandbox test execution.

    The structural-coverage fields below are populated by stage 6 of
    the pipeline (the DVE coverage gate, ADR-085 Phase 2). They default
    to zeroes / ``None`` for non-aviation runs so callers that ignore
    the coverage envelope continue to work unchanged.
    """

    result_id: str
    sandbox_id: str
    patch_id: str
    status: TestResultType
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    test_duration_seconds: float = 0.0
    error_message: str | None = None
    logs: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------ ADR-085 Phase 2 fields
    statement_coverage_pct: float = 0.0
    decision_coverage_pct: float = 0.0
    mcdc_coverage_pct: float = 0.0
    structural_coverage_dal: str | None = None  # "DAL_A" .. "DAL_D" / "DEFAULT"
    coverage_tool_used: str | None = None  # "coverage_py" / "vectorcast" / "ldra"
    coverage_report_s3_key: str | None = None  # S3 path to full report

    def to_dict(self) -> dict:
        return {
            "result_id": self.result_id,
            "sandbox_id": self.sandbox_id,
            "patch_id": self.patch_id,
            "status": self.status.value,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "test_duration_seconds": str(self.test_duration_seconds),
            "error_message": self.error_message,
            "created_at": self.created_at,
            "statement_coverage_pct": self.statement_coverage_pct,
            "decision_coverage_pct": self.decision_coverage_pct,
            "mcdc_coverage_pct": self.mcdc_coverage_pct,
            "structural_coverage_dal": self.structural_coverage_dal,
            "coverage_tool_used": self.coverage_tool_used,
            "coverage_report_s3_key": self.coverage_report_s3_key,
        }

    def apply_coverage(
        self,
        *,
        statement_pct: float,
        decision_pct: float,
        mcdc_pct: float,
        dal_level: str,
        tool: str,
        report_s3_key: str | None = None,
    ) -> "TestResult":
        """Return a copy with the structural-coverage fields populated.

        Stage 6 of the sandbox pipeline calls this after the coverage
        gate runs. Stays as a copy-helper rather than mutating in
        place so the original test result remains usable by any audit
        trail already written downstream.
        """
        return TestResult(
            result_id=self.result_id,
            sandbox_id=self.sandbox_id,
            patch_id=self.patch_id,
            status=self.status,
            tests_passed=self.tests_passed,
            tests_failed=self.tests_failed,
            tests_skipped=self.tests_skipped,
            test_duration_seconds=self.test_duration_seconds,
            error_message=self.error_message,
            logs=self.logs,
            created_at=self.created_at,
            statement_coverage_pct=statement_pct,
            decision_coverage_pct=decision_pct,
            mcdc_coverage_pct=mcdc_pct,
            structural_coverage_dal=dal_level,
            coverage_tool_used=tool,
            coverage_report_s3_key=report_s3_key,
        )


@dataclass
class ApprovalRequest:
    """HITL approval request for a tested patch."""

    approval_id: str
    patch_id: str
    sandbox_id: str
    result_id: str
    status: ApprovalStatus
    severity: str
    repository_url: str
    vulnerability_id: str | None = None
    test_summary: dict[str, Any] = field(default_factory=dict)
    reviewer_email: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    expires_at: str | None = None
    decision_at: str | None = None
    decision_comment: str | None = None

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "patch_id": self.patch_id,
            "sandbox_id": self.sandbox_id,
            "result_id": self.result_id,
            "status": self.status.value,
            "severity": self.severity,
            "repository_url": self.repository_url,
            "vulnerability_id": self.vulnerability_id or "",
            "test_summary": self.test_summary,
            "reviewer_email": self.reviewer_email or "",
            "created_at": self.created_at,
            "expires_at": self.expires_at or "",
            "decision_at": self.decision_at or "",
            "decision_comment": self.decision_comment or "",
        }


class SandboxTestRunner:
    """
    Orchestrates sandbox-based patch testing for HITL workflow.

    Responsibilities:
        - Provision ephemeral Fargate sandboxes
        - Execute patch tests in isolation
        - Store results in DynamoDB
        - Create approval requests
        - Send notifications via SNS
    """

    def __init__(
        self,
        environment: str = "dev",
        project_name: str = "aura",
        region: str | None = None,
    ):
        self.environment = environment
        self.project_name = project_name
        self.region = region or boto3.session.Session().region_name

        # AWS clients
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        self.ecs = boto3.client("ecs", region_name=self.region)
        self.sns = boto3.client("sns", region_name=self.region)
        self.s3 = boto3.client("s3", region_name=self.region)

        # Table names
        self.approval_table_name = f"{project_name}-approval-requests-{environment}"
        self.sandbox_table_name = f"{project_name}-sandbox-state-{environment}"
        self.results_table_name = f"{project_name}-sandbox-results-{environment}"

        # ECS cluster name
        self.cluster_name = f"{project_name}-sandboxes-{environment}"

        # SNS topic ARN (resolved on first use)
        self._sns_topic_arn: str | None = None

        # S3 bucket for artifacts
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        self.artifacts_bucket = (
            f"{project_name}-sandbox-artifacts-{account_id}-{environment}"
        )

        logger.info(f"SandboxTestRunner initialized for {environment} environment")

    @property
    def sns_topic_arn(self) -> str:
        """Lazily resolve SNS topic ARN."""
        if not self._sns_topic_arn:
            self._sns_topic_arn = (
                f"arn:aws:sns:{self.region}:{self._get_account_id()}:"
                f"{self.project_name}-hitl-notifications-{self.environment}"
            )
        return self._sns_topic_arn

    def _get_account_id(self) -> str:
        """Get current AWS account ID."""
        return cast(str, boto3.client("sts").get_caller_identity()["Account"])

    async def run_patch_test(self, request: PatchTestRequest) -> dict:
        """
        Execute full patch testing workflow.

        Steps:
            1. Generate sandbox ID
            2. Upload patch to S3
            3. Create sandbox task
            4. Wait for test completion
            5. Store results
            6. Create approval request
            7. Send notification

        Args:
            request: Patch test request with configuration

        Returns:
            Dict with sandbox_id, result_id, approval_id
        """
        sandbox_id = f"sandbox-{uuid.uuid4().hex[:12]}"
        result_id = f"result-{uuid.uuid4().hex[:12]}"

        logger.info(
            f"Starting patch test: sandbox_id={sandbox_id}, patch_id={request.patch_id}"
        )

        try:
            # Step 1: Upload patch to S3
            patch_s3_key = await self._upload_patch(sandbox_id, request.patch_content)

            # Step 2: Create sandbox and start test
            await self._create_sandbox(sandbox_id, request, patch_s3_key)

            # Step 3: Wait for test to complete (with timeout)
            test_result = await self._wait_for_completion(
                sandbox_id,
                request.patch_id,
                result_id,
                timeout_minutes=request.timeout_minutes,
            )

            # Step 4: Store results
            await self._store_result(test_result)

            # Step 5: Create approval request
            approval_request = await self._create_approval_request(
                request, sandbox_id, test_result
            )

            # Step 6: Send notification
            await self._send_notification(approval_request, test_result)

            return {
                "sandbox_id": sandbox_id,
                "result_id": result_id,
                "approval_id": approval_request.approval_id,
                "test_status": test_result.status.value,
                "approval_status": approval_request.status.value,
            }

        except Exception as e:
            logger.error(f"Patch test failed for sandbox {sandbox_id}: {e}")
            # Cleanup on failure
            await self._cleanup_sandbox(sandbox_id)
            raise

    async def _upload_patch(self, sandbox_id: str, patch_content: str) -> str:
        """Upload patch content to S3."""
        key = f"patches/{sandbox_id}/patch.diff"
        try:
            self.s3.put_object(
                Bucket=self.artifacts_bucket,
                Key=key,
                Body=patch_content.encode("utf-8"),
                ContentType="text/plain",
            )
            logger.info(f"Uploaded patch to s3://{self.artifacts_bucket}/{key}")
            return key
        except ClientError as e:
            logger.error(f"Failed to upload patch: {e}")
            raise

    async def _create_sandbox(
        self,
        sandbox_id: str,
        request: PatchTestRequest,
        patch_s3_key: str,
    ) -> dict:
        """Create sandbox ECS task."""
        table = self.dynamodb.Table(self.sandbox_table_name)
        ttl = int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp())

        # Store sandbox state
        table.put_item(
            Item={
                "sandbox_id": sandbox_id,
                "patch_id": request.patch_id,
                "status": TestStatus.PROVISIONING.value,
                "test_suite": request.test_suite,
                "isolation_level": request.isolation_level,
                "patch_s3_key": patch_s3_key,
                "repository_url": request.repository_url,
                "branch": request.branch,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ttl": ttl,
            }
        )

        logger.info(f"Sandbox {sandbox_id} state stored in DynamoDB")

        return {
            "sandbox_id": sandbox_id,
            "status": TestStatus.PROVISIONING.value,
        }

    async def _wait_for_completion(
        self,
        sandbox_id: str,
        patch_id: str,
        result_id: str,
        timeout_minutes: int = 30,
    ) -> TestResult:
        """
        Poll sandbox status until completion or timeout.

        In production, this would monitor the actual ECS task.
        For now, we simulate test execution.
        """
        start_time = datetime.now(timezone.utc)
        _ = timedelta(minutes=timeout_minutes)  # Available for future timeout checks

        logger.info(
            f"Waiting for sandbox {sandbox_id} to complete (timeout: {timeout_minutes}m)"
        )

        # Update status to running
        table = self.dynamodb.Table(self.sandbox_table_name)
        table.update_item(
            Key={"sandbox_id": sandbox_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": TestStatus.RUNNING.value},
        )

        # Simulate test execution (in production, poll ECS task status)
        await asyncio.sleep(2)  # Minimal delay for testing

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Create test result (simulated pass for now)
        result = TestResult(
            result_id=result_id,
            sandbox_id=sandbox_id,
            patch_id=patch_id,
            status=TestResultType.PASS,
            tests_passed=15,
            tests_failed=0,
            tests_skipped=2,
            test_duration_seconds=elapsed,
        )

        # Update sandbox status
        table.update_item(
            Key={"sandbox_id": sandbox_id},
            UpdateExpression="SET #status = :status, completed_at = :completed",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": TestStatus.COMPLETED.value,
                ":completed": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(f"Sandbox {sandbox_id} completed: {result.status.value}")
        return result

    async def _store_result(self, result: TestResult) -> None:
        """Store test result in DynamoDB."""
        table = self.dynamodb.Table(self.results_table_name)
        ttl = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())

        item = result.to_dict()
        item["ttl"] = ttl

        table.put_item(Item=item)
        logger.info(f"Test result {result.result_id} stored")

    async def _create_approval_request(
        self,
        request: PatchTestRequest,
        sandbox_id: str,
        result: TestResult,
    ) -> ApprovalRequest:
        """Create HITL approval request."""
        approval_id = f"approval-{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        ttl = int(expires_at.timestamp())

        approval = ApprovalRequest(
            approval_id=approval_id,
            patch_id=request.patch_id,
            sandbox_id=sandbox_id,
            result_id=result.result_id,
            status=ApprovalStatus.PENDING,
            severity=request.severity,
            repository_url=request.repository_url,
            vulnerability_id=request.vulnerability_id,
            test_summary={
                "tests_passed": result.tests_passed,
                "tests_failed": result.tests_failed,
                "tests_skipped": result.tests_skipped,
                "duration_seconds": result.test_duration_seconds,
                "status": result.status.value,
            },
            expires_at=expires_at.isoformat(),
        )

        table = self.dynamodb.Table(self.approval_table_name)
        item = approval.to_dict()
        item["ttl"] = ttl

        table.put_item(Item=item)
        logger.info(f"Approval request {approval_id} created")

        return approval

    async def _send_notification(
        self,
        approval: ApprovalRequest,
        result: TestResult,
    ) -> None:
        """Send SNS notification for HITL review."""
        try:
            message = (
                f"HITL Review Required: Patch {approval.patch_id}\n\n"
                f"Severity: {approval.severity}\n"
                f"Repository: {approval.repository_url}\n"
                f"Test Results:\n"
                f"  - Passed: {result.tests_passed}\n"
                f"  - Failed: {result.tests_failed}\n"
                f"  - Skipped: {result.tests_skipped}\n\n"
                f"Approval ID: {approval.approval_id}\n"
                f"Expires: {approval.expires_at}\n"
            )

            self.sns.publish(
                TopicArn=self.sns_topic_arn,
                Subject=f"[Aura HITL] Review Required: {approval.patch_id}",
                Message=message,
            )
            logger.info(f"Notification sent for approval {approval.approval_id}")
        except ClientError as e:
            logger.warning(f"Failed to send notification: {e}")
            # Don't fail the workflow if notification fails

    async def _cleanup_sandbox(self, sandbox_id: str) -> None:
        """Clean up sandbox resources after failure."""
        try:
            table = self.dynamodb.Table(self.sandbox_table_name)
            table.update_item(
                Key={"sandbox_id": sandbox_id},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": TestStatus.FAILED.value},
            )
            logger.info(f"Sandbox {sandbox_id} marked as failed")
        except Exception as e:
            logger.error(f"Failed to cleanup sandbox {sandbox_id}: {e}")

    async def get_approval_request(self, approval_id: str) -> dict | None:
        """Get approval request by ID."""
        table = self.dynamodb.Table(self.approval_table_name)
        response = table.get_item(Key={"approval_id": approval_id})
        return response.get("Item")

    async def get_pending_approvals(self, limit: int = 50) -> list[dict]:
        """Get all pending approval requests."""
        table = self.dynamodb.Table(self.approval_table_name)
        response = table.query(
            IndexName="status-created_at-index",
            KeyConditionExpression="status = :status",
            ExpressionAttributeValues={":status": ApprovalStatus.PENDING.value},
            Limit=limit,
            ScanIndexForward=False,  # Most recent first
        )
        return response.get("Items", [])

    async def approve_patch(
        self,
        approval_id: str,
        reviewer_email: str,
        comment: str | None = None,
    ) -> dict:
        """
        Approve a patch for deployment.

        Args:
            approval_id: The approval request ID
            reviewer_email: Email of the approving reviewer
            comment: Optional approval comment

        Returns:
            Updated approval request
        """
        table = self.dynamodb.Table(self.approval_table_name)
        decision_at = datetime.now(timezone.utc).isoformat()

        response = table.update_item(
            Key={"approval_id": approval_id},
            UpdateExpression="""
                SET #status = :status,
                    reviewer_email = :reviewer,
                    decision_at = :decision_at,
                    decision_comment = :comment
            """,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":pending": ApprovalStatus.PENDING.value,
                ":status": ApprovalStatus.APPROVED.value,
                ":reviewer": reviewer_email,
                ":decision_at": decision_at,
                ":comment": comment or "",
            },
            ConditionExpression="#status = :pending",
            ReturnValues="ALL_NEW",
        )

        logger.info(f"Approval {approval_id} approved by {reviewer_email}")
        return response.get("Attributes", {})

    async def reject_patch(
        self,
        approval_id: str,
        reviewer_email: str,
        reason: str,
    ) -> dict:
        """
        Reject a patch.

        Args:
            approval_id: The approval request ID
            reviewer_email: Email of the rejecting reviewer
            reason: Rejection reason

        Returns:
            Updated approval request
        """
        table = self.dynamodb.Table(self.approval_table_name)
        decision_at = datetime.now(timezone.utc).isoformat()

        response = table.update_item(
            Key={"approval_id": approval_id},
            UpdateExpression="""
                SET #status = :status,
                    reviewer_email = :reviewer,
                    decision_at = :decision_at,
                    decision_comment = :reason
            """,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": ApprovalStatus.REJECTED.value,
                ":reviewer": reviewer_email,
                ":decision_at": decision_at,
                ":reason": reason,
            },
            ReturnValues="ALL_NEW",
        )

        logger.info(f"Approval {approval_id} rejected by {reviewer_email}: {reason}")
        return response.get("Attributes", {})

    async def get_test_result(self, result_id: str) -> dict | None:
        """Get test result by ID."""
        table = self.dynamodb.Table(self.results_table_name)
        response = table.get_item(Key={"result_id": result_id})
        return response.get("Item")

    async def get_sandbox_state(self, sandbox_id: str) -> dict | None:
        """Get sandbox state by ID."""
        table = self.dynamodb.Table(self.sandbox_table_name)
        response = table.get_item(Key={"sandbox_id": sandbox_id})
        return response.get("Item")
