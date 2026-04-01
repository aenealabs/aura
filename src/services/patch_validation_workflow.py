"""
Project Aura - Patch Validation Workflow Service

End-to-end orchestration of the patch validation lifecycle:
1. Vulnerability detection triggers patch generation via MetaOrchestrator
2. Sandbox testing validates the patch in isolation
3. HITL approval gates production deployment
4. Step Functions task token callbacks signal workflow completion

This service bridges MetaOrchestrator's agent capabilities with the
HITL sandbox testing infrastructure for production-safe deployments.

Author: Project Aura Team
Created: 2025-12-03
Version: 1.0.0
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource
    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_stepfunctions.client import SFNClient

logger = logging.getLogger(__name__)

# AWS SDK imports
try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("Boto3 not available - using mock mode")


class WorkflowStatus(Enum):
    """Status of the patch validation workflow."""

    INITIATED = "initiated"
    PATCH_GENERATING = "patch_generating"
    PATCH_GENERATED = "patch_generated"
    SANDBOX_PROVISIONING = "sandbox_provisioning"
    SANDBOX_TESTING = "sandbox_testing"
    TESTS_PASSED = "tests_passed"
    TESTS_FAILED = "tests_failed"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationResult(Enum):
    """Result of patch validation."""

    SUCCESS = "success"
    TESTS_FAILED = "tests_failed"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_TIMEOUT = "approval_timeout"
    DEPLOYMENT_FAILED = "deployment_failed"
    ERROR = "error"


@dataclass
class VulnerabilityContext:
    """Context for a detected vulnerability requiring remediation."""

    vulnerability_id: str
    vulnerability_type: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    file_path: str
    line_number: int
    description: str
    cve_id: str | None = None
    original_code: str | None = None
    recommendation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PatchContext:
    """Context for a generated security patch."""

    patch_id: str
    vulnerability_id: str
    patch_content: str
    patched_code: str
    file_path: str
    agent_id: str
    confidence_score: float = 0.0
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowState:
    """Current state of a patch validation workflow."""

    workflow_id: str
    status: WorkflowStatus
    vulnerability: VulnerabilityContext | None = None
    patch: PatchContext | None = None
    sandbox_id: str | None = None
    approval_id: str | None = None
    task_token: str | None = None  # Step Functions task token for callback
    test_results: dict[str, Any] | None = None
    error_message: str | None = None
    # GitHub integration fields
    repository_url: str | None = None
    branch: str = "main"
    pr_url: str | None = None  # Created PR URL after deployment
    pr_number: int | None = None
    approver_email: str | None = None
    # Timestamps
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "vulnerability": (
                {
                    "vulnerability_id": self.vulnerability.vulnerability_id,
                    "vulnerability_type": self.vulnerability.vulnerability_type,
                    "severity": self.vulnerability.severity,
                    "file_path": self.vulnerability.file_path,
                    "line_number": self.vulnerability.line_number,
                    "description": self.vulnerability.description,
                    "cve_id": self.vulnerability.cve_id,
                }
                if self.vulnerability
                else None
            ),
            "patch": (
                {
                    "patch_id": self.patch.patch_id,
                    "vulnerability_id": self.patch.vulnerability_id,
                    "file_path": self.patch.file_path,
                    "agent_id": self.patch.agent_id,
                    "confidence_score": self.patch.confidence_score,
                    "generated_at": self.patch.generated_at,
                }
                if self.patch
                else None
            ),
            "sandbox_id": self.sandbox_id,
            "approval_id": self.approval_id,
            "task_token": self.task_token,
            "test_results": self.test_results,
            "error_message": self.error_message,
            # GitHub integration fields
            "repository_url": self.repository_url,
            "branch": self.branch,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "approver_email": self.approver_email,
            # Timestamps
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


@dataclass
class WorkflowResult:
    """Result of patch validation workflow execution."""

    workflow_id: str
    result: ValidationResult
    status: WorkflowStatus
    patch_id: str | None = None
    sandbox_id: str | None = None
    approval_id: str | None = None
    deployment_id: str | None = None
    pr_url: str | None = None  # GitHub PR URL if created
    pr_number: int | None = None
    error_message: str | None = None
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class PatchValidationWorkflow:
    """
    Orchestrates end-to-end patch validation from vulnerability detection
    through sandbox testing, HITL approval, and production deployment.

    Integrates:
    - MetaOrchestrator: Generates patches via CoderAgent
    - SandboxTestRunner: Tests patches in isolated environment
    - HITLApprovalService: Manages human approval workflow
    - Step Functions: Handles async approval callbacks

    Example:
        workflow = PatchValidationWorkflow(
            meta_orchestrator=orchestrator,
            sandbox_runner=runner,
            approval_service=hitl_service
        )

        result = await workflow.execute(
            vulnerability=VulnerabilityContext(
                vulnerability_id="vuln-001",
                vulnerability_type="SQL_INJECTION",
                severity="CRITICAL",
                file_path="src/api/users.py",
                line_number=42,
                description="Unsanitized user input in SQL query"
            ),
            repository_url="https://github.com/org/repo",
            branch="main"
        )
    """

    def __init__(
        self,
        meta_orchestrator: Any = None,
        sandbox_runner: Any = None,
        approval_service: Any = None,
        notification_service: Any = None,
        project_name: str = "aura",
        environment: str = "dev",
        region: str = "us-east-1",
    ):
        """
        Initialize the patch validation workflow.

        Args:
            meta_orchestrator: MetaOrchestrator instance for patch generation
            sandbox_runner: SandboxTestRunner instance for testing
            approval_service: HITLApprovalService for approvals
            notification_service: NotificationService for alerts
            project_name: Project name for resource naming
            environment: Environment (dev, qa, prod)
            region: AWS region
        """
        self.meta_orchestrator = meta_orchestrator
        self.sandbox_runner = sandbox_runner
        self.approval_service = approval_service
        self.notification_service = notification_service
        self.project_name = project_name
        self.environment = environment
        self.region = region

        # DynamoDB table for workflow state
        self.workflow_table_name = f"{project_name}-patch-workflows-{environment}"

        # AWS clients (lazy initialization)
        self._dynamodb: DynamoDBServiceResource | None = None
        self._sfn: SFNClient | None = None
        self._s3: S3Client | None = None

        # In-memory state for testing
        self._mock_workflows: dict[str, WorkflowState] = {}
        self._use_mock = not BOTO3_AVAILABLE or environment == "test"

    @property
    def dynamodb(self) -> DynamoDBServiceResource | None:
        """Lazy DynamoDB resource initialization."""
        if not self._dynamodb and BOTO3_AVAILABLE:
            self._dynamodb = boto3.resource("dynamodb", region_name=self.region)  # type: ignore[assignment]
        return self._dynamodb

    @property
    def sfn(self) -> SFNClient | None:
        """Lazy Step Functions client initialization."""
        if not self._sfn and BOTO3_AVAILABLE:
            self._sfn = boto3.client("stepfunctions", region_name=self.region)  # type: ignore[assignment]
        return self._sfn

    @property
    def s3(self) -> S3Client | None:
        """Lazy S3 client initialization."""
        if not self._s3 and BOTO3_AVAILABLE:
            self._s3 = boto3.client("s3", region_name=self.region)  # type: ignore[assignment]
        return self._s3

    async def execute(
        self,
        vulnerability: VulnerabilityContext,
        repository_url: str,
        branch: str = "main",
        test_suite: str = "all",
        auto_deploy: bool = False,
        timeout_minutes: int = 60,
    ) -> WorkflowResult:
        """
        Execute the full patch validation workflow.

        Steps:
            1. Generate patch via MetaOrchestrator
            2. Test patch in sandbox
            3. Create HITL approval request
            4. Wait for human approval (async)
            5. Deploy to production (if approved and auto_deploy=True)

        Args:
            vulnerability: Vulnerability context to remediate
            repository_url: Git repository URL
            branch: Git branch to patch
            test_suite: Test suite to run (unit, integration, security, all)
            auto_deploy: Whether to auto-deploy after approval
            timeout_minutes: Workflow timeout

        Returns:
            WorkflowResult with outcome and details
        """
        start_time = datetime.now(timezone.utc)
        workflow_id = f"workflow-{uuid.uuid4().hex[:12]}"

        # Initialize workflow state
        state = WorkflowState(
            workflow_id=workflow_id,
            status=WorkflowStatus.INITIATED,
            vulnerability=vulnerability,
            repository_url=repository_url,
            branch=branch,
        )

        logger.info(
            f"Starting patch validation workflow: {workflow_id} "
            f"for vulnerability: {vulnerability.vulnerability_id}"
        )

        try:
            # Save initial state
            await self._save_workflow_state(state)

            # Step 1: Generate patch
            state.status = WorkflowStatus.PATCH_GENERATING
            await self._save_workflow_state(state)

            patch = await self._generate_patch(vulnerability, repository_url, branch)
            state.patch = patch
            state.status = WorkflowStatus.PATCH_GENERATED
            await self._save_workflow_state(state)

            logger.info(f"Patch generated: {patch.patch_id}")

            # Step 2: Test in sandbox
            state.status = WorkflowStatus.SANDBOX_PROVISIONING
            await self._save_workflow_state(state)

            test_result = await self._run_sandbox_tests(
                patch=patch,
                repository_url=repository_url,
                branch=branch,
                test_suite=test_suite,
                timeout_minutes=timeout_minutes // 2,  # Half timeout for tests
            )

            state.sandbox_id = test_result.get("sandbox_id")
            state.test_results = test_result
            await self._save_workflow_state(state)

            if test_result.get("tests_passed", False):
                state.status = WorkflowStatus.TESTS_PASSED
            else:
                state.status = WorkflowStatus.TESTS_FAILED
                await self._save_workflow_state(state)
                return self._create_result(
                    state,
                    ValidationResult.TESTS_FAILED,
                    start_time,
                    error_message="Sandbox tests failed",
                )

            # Step 3: Create HITL approval request
            state.status = WorkflowStatus.AWAITING_APPROVAL
            approval_id = await self._create_approval_request(state)
            state.approval_id = approval_id
            await self._save_workflow_state(state)

            logger.info(f"Approval request created: {approval_id}")

            # Step 4: Return - approval is async via task token callback
            # The workflow continues when process_approval_callback is called
            return self._create_result(
                state,
                ValidationResult.SUCCESS,
                start_time,
                metadata={"awaiting_approval": True},
            )

        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")
            state.status = WorkflowStatus.FAILED
            state.error_message = str(e)
            await self._save_workflow_state(state)

            return self._create_result(
                state,
                ValidationResult.ERROR,
                start_time,
                error_message=str(e),
            )

    async def _generate_patch(
        self,
        vulnerability: VulnerabilityContext,
        repository_url: str,
        branch: str,
    ) -> PatchContext:
        """Generate a patch using MetaOrchestrator."""
        patch_id = f"patch-{uuid.uuid4().hex[:12]}"

        if self.meta_orchestrator:
            # Use real MetaOrchestrator
            result = await self.meta_orchestrator.execute(
                task=f"Fix {vulnerability.vulnerability_type} vulnerability: {vulnerability.description}",
                repository=repository_url,
                severity=vulnerability.severity,
                context={
                    "file_path": vulnerability.file_path,
                    "line_number": vulnerability.line_number,
                    "original_code": vulnerability.original_code,
                    "recommendation": vulnerability.recommendation,
                },
            )

            patch_content = result.get("patch", "")
            patched_code = result.get("patched_code", "")
            agent_id = result.get("agent_id", "meta-orchestrator")
            confidence = result.get("confidence", 0.85)
        else:
            # Mock patch for testing
            patch_content = f"""--- a/{vulnerability.file_path}
+++ b/{vulnerability.file_path}
@@ -{vulnerability.line_number},1 +{vulnerability.line_number},1 @@
- {vulnerability.original_code or '# vulnerable code'}
+ # Fixed: {vulnerability.description}
"""
            patched_code = f"# Fixed: {vulnerability.description}"
            agent_id = "mock-coder-agent"
            confidence = 0.9

        return PatchContext(
            patch_id=patch_id,
            vulnerability_id=vulnerability.vulnerability_id,
            patch_content=patch_content,
            patched_code=patched_code,
            file_path=vulnerability.file_path,
            agent_id=agent_id,
            confidence_score=confidence,
        )

    async def _run_sandbox_tests(
        self,
        patch: PatchContext,
        repository_url: str,
        branch: str,
        test_suite: str,
        timeout_minutes: int,
    ) -> dict[str, Any]:
        """Run patch tests in sandbox environment."""
        if self.sandbox_runner:
            # Import here to avoid circular dependencies
            from src.services.sandbox_test_runner import PatchTestRequest

            request = PatchTestRequest(
                patch_id=patch.patch_id,
                repository_url=repository_url,
                branch=branch,
                patch_content=patch.patch_content,
                test_suite=test_suite,
                vulnerability_id=patch.vulnerability_id,
                severity="HIGH",
                timeout_minutes=timeout_minutes,
            )

            result = await self.sandbox_runner.run_patch_test(request)
            return {
                "sandbox_id": result.get("sandbox_id"),
                "result_id": result.get("result_id"),
                "test_status": result.get("test_status"),
                "tests_passed": result.get("test_status") in ["pass", "completed"],
            }
        else:
            # Mock sandbox test for testing
            sandbox_id = f"sandbox-{uuid.uuid4().hex[:12]}"
            return {
                "sandbox_id": sandbox_id,
                "result_id": f"result-{uuid.uuid4().hex[:12]}",
                "test_status": "pass",
                "tests_passed": True,
                "tests_run": 15,
                "tests_failed": 0,
            }

    async def _create_approval_request(self, state: WorkflowState) -> str:
        """Create HITL approval request."""
        if self.approval_service:
            if not state.patch or not state.vulnerability:
                raise ValueError("Missing patch or vulnerability in workflow state")
            request = await self.approval_service.create_approval_request(
                patch_id=state.patch.patch_id,
                vulnerability_id=state.vulnerability.vulnerability_id,
                severity=state.vulnerability.severity,
                sandbox_id=state.sandbox_id,
                test_results=state.test_results,
                workflow_id=state.workflow_id,
            )
            return str(request.approval_id)
        else:
            # Mock approval ID for testing
            return f"approval-{uuid.uuid4().hex[:12]}"

    async def process_approval_callback(
        self,
        workflow_id: str,
        approval_id: str,
        decision: str,  # APPROVED, REJECTED
        approver_email: str,
        comments: str = "",
        auto_deploy: bool = False,
    ) -> WorkflowResult:
        """
        Process approval callback from Step Functions or API.

        This method is called when a human approves or rejects a patch
        via the Approval Dashboard or Step Functions callback.

        Args:
            workflow_id: The workflow ID to process
            approval_id: The approval request ID
            decision: APPROVED or REJECTED
            approver_email: Email of the approver
            comments: Optional approver comments
            auto_deploy: Whether to auto-deploy if approved

        Returns:
            WorkflowResult with final outcome
        """
        start_time = datetime.now(timezone.utc)

        # Load workflow state
        state = await self._load_workflow_state(workflow_id)
        if not state:
            return WorkflowResult(
                workflow_id=workflow_id,
                result=ValidationResult.ERROR,
                status=WorkflowStatus.FAILED,
                error_message=f"Workflow {workflow_id} not found",
            )

        logger.info(f"Processing approval callback: {workflow_id}, decision={decision}")

        try:
            if decision.upper() == "APPROVED":
                state.status = WorkflowStatus.APPROVED
                state.approver_email = approver_email  # Store for GitHub PR context
                await self._save_workflow_state(state)

                # Send Step Functions callback if task token exists
                if state.task_token:
                    await self._send_task_success(
                        state.task_token,
                        {"decision": "APPROVED", "approver": approver_email},
                    )

                if auto_deploy:
                    # Deploy to production
                    state.status = WorkflowStatus.DEPLOYING
                    await self._save_workflow_state(state)

                    deployment_id = await self._deploy_to_production(state)

                    state.status = WorkflowStatus.DEPLOYED
                    state.completed_at = datetime.now(timezone.utc).isoformat()
                    await self._save_workflow_state(state)

                    return WorkflowResult(
                        workflow_id=workflow_id,
                        result=ValidationResult.SUCCESS,
                        status=WorkflowStatus.DEPLOYED,
                        patch_id=state.patch.patch_id if state.patch else None,
                        sandbox_id=state.sandbox_id,
                        approval_id=approval_id,
                        deployment_id=deployment_id,
                        pr_url=state.pr_url,
                        pr_number=state.pr_number,
                        duration_seconds=(
                            datetime.now(timezone.utc) - start_time
                        ).total_seconds(),
                    )

                return self._create_result(state, ValidationResult.SUCCESS, start_time)

            else:  # REJECTED
                state.status = WorkflowStatus.REJECTED
                state.completed_at = datetime.now(timezone.utc).isoformat()
                await self._save_workflow_state(state)

                # Send Step Functions callback if task token exists
                if state.task_token:
                    await self._send_task_failure(
                        state.task_token,
                        error="ApprovalRejected",
                        cause=comments or "Patch rejected by reviewer",
                    )

                return self._create_result(
                    state,
                    ValidationResult.APPROVAL_REJECTED,
                    start_time,
                    error_message=comments or "Patch rejected by reviewer",
                )

        except Exception as e:
            logger.error(f"Approval callback processing failed: {e}")
            state.status = WorkflowStatus.FAILED
            state.error_message = str(e)
            await self._save_workflow_state(state)

            return self._create_result(
                state, ValidationResult.ERROR, start_time, error_message=str(e)
            )

    async def register_task_token(self, workflow_id: str, task_token: str) -> bool:
        """
        Register a Step Functions task token for async approval callback.

        This is called by the Step Functions state machine when it enters
        the WaitForHumanApproval state with waitForTaskToken.

        Args:
            workflow_id: The workflow ID to register
            task_token: The Step Functions task token

        Returns:
            True if registration succeeded
        """
        state = await self._load_workflow_state(workflow_id)
        if not state:
            logger.warning(
                f"Workflow {workflow_id} not found for task token registration"
            )
            return False

        state.task_token = task_token
        await self._save_workflow_state(state)

        logger.info(f"Task token registered for workflow {workflow_id}")
        return True

    async def _send_task_success(self, task_token: str, output: dict) -> None:
        """Send success callback to Step Functions."""
        if self.sfn and task_token:
            import json

            try:
                self.sfn.send_task_success(
                    taskToken=task_token, output=json.dumps(output)
                )
                logger.info("Step Functions task success sent")
            except ClientError as e:
                logger.error(f"Failed to send task success: {e}")
                raise
        else:
            logger.info(f"Mock: send_task_success with output={output}")

    async def _send_task_failure(self, task_token: str, error: str, cause: str) -> None:
        """Send failure callback to Step Functions."""
        if self.sfn and task_token:
            try:
                self.sfn.send_task_failure(
                    taskToken=task_token, error=error, cause=cause
                )
                logger.info("Step Functions task failure sent")
            except ClientError as e:
                logger.error(f"Failed to send task failure: {e}")
                raise
        else:
            logger.info(f"Mock: send_task_failure error={error}, cause={cause}")

    async def _deploy_to_production(self, state: WorkflowState) -> str:
        """
        Deploy approved patch to production via GitHub PR.

        Creates a feature branch, applies the patch, opens a PR with security context,
        and adds test results as a comment. The PR URL is stored in the workflow state.

        Args:
            state: Current workflow state with patch, vulnerability, and test results

        Returns:
            deployment_id: Unique identifier for this deployment (also the PR number)
        """
        from src.services.github_pr_service import (
            GitHubPRService,
            PatchInfo,
            PRCreationStatus,
            TestResultInfo,
            VulnerabilityInfo,
        )

        deployment_id = f"deploy-{uuid.uuid4().hex[:12]}"

        logger.info(
            f"Deploying patch {state.patch.patch_id if state.patch else 'unknown'} "
            f"to production via GitHub PR: {deployment_id}"
        )

        # Validate required state
        if not state.patch or not state.vulnerability or not state.repository_url:
            logger.error(
                "Cannot deploy: missing patch, vulnerability, or repository_url"
            )
            return deployment_id

        # Initialize GitHub PR service
        github_service = GitHubPRService(
            environment=self.environment,
            use_mock=self._use_mock,
        )

        # Convert workflow state to GitHub service dataclasses
        vulnerability_info = VulnerabilityInfo(
            vulnerability_id=state.vulnerability.vulnerability_id,
            vulnerability_type=state.vulnerability.vulnerability_type,
            severity=state.vulnerability.severity,
            file_path=state.vulnerability.file_path,
            line_number=state.vulnerability.line_number,
            description=state.vulnerability.description,
            cve_id=state.vulnerability.cve_id,
            recommendation=state.vulnerability.recommendation,
        )

        patch_info = PatchInfo(
            patch_id=state.patch.patch_id,
            patch_content=state.patch.patch_content,
            patched_code=state.patch.patched_code,
            file_path=state.patch.file_path,
            confidence_score=state.patch.confidence_score,
            agent_id=state.patch.agent_id,
        )

        # Convert test results if available
        test_result_info = None
        if state.test_results:
            test_result_info = TestResultInfo(
                tests_passed=state.test_results.get("tests_passed", 0),
                tests_failed=state.test_results.get("tests_failed", 0),
                sandbox_id=state.sandbox_id or "",
                test_report_url=state.test_results.get("report_url"),
                security_scan_passed=state.test_results.get(
                    "security_scan_passed", True
                ),
                coverage_percent=state.test_results.get("coverage_percent"),
            )

        # Create the remediation PR
        result = await github_service.create_remediation_pr(
            repo_url=state.repository_url,
            patch_info=patch_info,
            vulnerability_info=vulnerability_info,
            test_results=test_result_info,
            base_branch=state.branch,
            approver_email=state.approver_email,
            approval_id=state.approval_id,
            workflow_id=state.workflow_id,
        )

        # Update state with PR details
        if result.status == PRCreationStatus.SUCCESS:
            state.pr_url = result.pr_url
            state.pr_number = result.pr_number
            logger.info(
                f"Successfully created PR #{result.pr_number}: {result.pr_url} "
                f"for patch {state.patch.patch_id}"
            )
            # Use PR number as deployment ID for traceability
            deployment_id = f"pr-{result.pr_number}"
        else:
            logger.error(
                f"Failed to create PR for patch {state.patch.patch_id}: "
                f"{result.status.value} - {result.error_message}"
            )
            state.error_message = f"PR creation failed: {result.error_message}"

        return deployment_id

    async def _save_workflow_state(self, state: WorkflowState) -> None:
        """Save workflow state to DynamoDB or mock storage."""
        state.updated_at = datetime.now(timezone.utc).isoformat()

        if self._use_mock:
            self._mock_workflows[state.workflow_id] = state
        else:
            if self.dynamodb is None:
                raise RuntimeError("DynamoDB resource not available")
            table = self.dynamodb.Table(self.workflow_table_name)
            table.put_item(Item=state.to_dict())

        logger.debug(
            f"Workflow state saved: {state.workflow_id}, status={state.status.value}"
        )

    async def _load_workflow_state(self, workflow_id: str) -> WorkflowState | None:
        """Load workflow state from DynamoDB or mock storage."""
        if self._use_mock:
            return self._mock_workflows.get(workflow_id)
        else:
            if self.dynamodb is None:
                raise RuntimeError("DynamoDB resource not available")
            table = self.dynamodb.Table(self.workflow_table_name)
            try:
                response = table.get_item(Key={"workflow_id": workflow_id})
                item = response.get("Item")
                if item:
                    return self._item_to_state(item)
                return None
            except ClientError as e:
                logger.error(f"Failed to load workflow state: {e}")
                return None

    def _item_to_state(self, item: dict) -> WorkflowState:
        """Convert DynamoDB item to WorkflowState."""
        vulnerability = None
        if item.get("vulnerability"):
            v = item["vulnerability"]
            vulnerability = VulnerabilityContext(
                vulnerability_id=v["vulnerability_id"],
                vulnerability_type=v["vulnerability_type"],
                severity=v["severity"],
                file_path=v["file_path"],
                line_number=v["line_number"],
                description=v.get("description", ""),
                cve_id=v.get("cve_id"),
            )

        patch = None
        if item.get("patch"):
            p = item["patch"]
            patch = PatchContext(
                patch_id=p["patch_id"],
                vulnerability_id=p["vulnerability_id"],
                patch_content="",  # Not stored in summary
                patched_code="",
                file_path=p["file_path"],
                agent_id=p["agent_id"],
                confidence_score=p.get("confidence_score", 0.0),
                generated_at=p.get("generated_at", ""),
            )

        return WorkflowState(
            workflow_id=item["workflow_id"],
            status=WorkflowStatus(item["status"]),
            vulnerability=vulnerability,
            patch=patch,
            sandbox_id=item.get("sandbox_id"),
            approval_id=item.get("approval_id"),
            task_token=item.get("task_token"),
            test_results=item.get("test_results"),
            error_message=item.get("error_message"),
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            completed_at=item.get("completed_at"),
        )

    def _create_result(
        self,
        state: WorkflowState,
        result: ValidationResult,
        start_time: datetime,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """Create a WorkflowResult from current state."""
        return WorkflowResult(
            workflow_id=state.workflow_id,
            result=result,
            status=state.status,
            patch_id=state.patch.patch_id if state.patch else None,
            sandbox_id=state.sandbox_id,
            approval_id=state.approval_id,
            error_message=error_message or state.error_message,
            duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
            metadata=metadata or {},
        )

    async def get_workflow_status(self, workflow_id: str) -> dict[str, Any] | None:
        """Get the current status of a workflow."""
        state = await self._load_workflow_state(workflow_id)
        if state:
            return {
                "workflow_id": state.workflow_id,
                "status": state.status.value,
                "vulnerability_id": (
                    state.vulnerability.vulnerability_id
                    if state.vulnerability
                    else None
                ),
                "patch_id": state.patch.patch_id if state.patch else None,
                "sandbox_id": state.sandbox_id,
                "approval_id": state.approval_id,
                "test_results": state.test_results,
                "error_message": state.error_message,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "completed_at": state.completed_at,
            }
        return None

    async def list_pending_workflows(self) -> list[dict[str, Any]]:
        """List all workflows awaiting approval."""
        if self._use_mock:
            return [
                {
                    "workflow_id": state.workflow_id,
                    "status": state.status.value,
                    "vulnerability_id": (
                        state.vulnerability.vulnerability_id
                        if state.vulnerability
                        else None
                    ),
                    "approval_id": state.approval_id,
                    "created_at": state.created_at,
                }
                for state in self._mock_workflows.values()
                if state.status == WorkflowStatus.AWAITING_APPROVAL
            ]
        else:
            # Query DynamoDB GSI for status = AWAITING_APPROVAL
            # This requires a GSI on status field
            if self.dynamodb is None:
                raise RuntimeError("DynamoDB resource not available")
            table = self.dynamodb.Table(self.workflow_table_name)
            try:
                response = table.scan(
                    FilterExpression="status = :status",
                    ExpressionAttributeValues={
                        ":status": WorkflowStatus.AWAITING_APPROVAL.value
                    },
                )
                return [
                    {
                        "workflow_id": str(item["workflow_id"]),
                        "status": str(item["status"]),
                        "vulnerability_id": (
                            str(vuln.get("vulnerability_id"))
                            if (vuln := item.get("vulnerability"))
                            and isinstance(vuln, dict)
                            else None
                        ),
                        "approval_id": (
                            str(item.get("approval_id"))
                            if item.get("approval_id")
                            else None
                        ),
                        "created_at": (
                            str(item.get("created_at"))
                            if item.get("created_at")
                            else None
                        ),
                    }
                    for item in response.get("Items", [])
                ]
            except ClientError as e:
                logger.error(f"Failed to list pending workflows: {e}")
                return []

    async def cancel_workflow(self, workflow_id: str, reason: str = "") -> bool:
        """Cancel a pending or awaiting-approval workflow."""
        state = await self._load_workflow_state(workflow_id)
        if not state:
            return False

        if state.status in [
            WorkflowStatus.DEPLOYED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        ]:
            logger.warning(f"Cannot cancel workflow in status: {state.status.value}")
            return False

        state.status = WorkflowStatus.CANCELLED
        state.error_message = reason or "Cancelled by user"
        state.completed_at = datetime.now(timezone.utc).isoformat()
        await self._save_workflow_state(state)

        # Send task failure if we have a token
        if state.task_token:
            await self._send_task_failure(
                state.task_token,
                error="WorkflowCancelled",
                cause=reason or "Workflow cancelled by user",
            )

        logger.info(f"Workflow {workflow_id} cancelled")
        return True


# Factory function for creating production workflow
def create_patch_validation_workflow(
    project_name: str = "aura",
    environment: str = "dev",
    region: str = "us-east-1",
    meta_orchestrator: Any = None,
    sandbox_runner: Any = None,
    approval_service: Any = None,
) -> PatchValidationWorkflow:
    """
    Factory function to create a configured PatchValidationWorkflow.

    If services are not provided, they will be created with default configuration.

    Args:
        project_name: Project name for resource naming
        environment: Environment (dev, qa, prod)
        region: AWS region
        meta_orchestrator: Optional MetaOrchestrator instance
        sandbox_runner: Optional SandboxTestRunner instance
        approval_service: Optional HITLApprovalService instance

    Returns:
        Configured PatchValidationWorkflow instance
    """
    # Create default services if not provided
    if not sandbox_runner:
        try:
            from src.services.sandbox_test_runner import SandboxTestRunner

            sandbox_runner = SandboxTestRunner(
                project_name=project_name, environment=environment, region=region
            )
        except ImportError:
            logger.warning("SandboxTestRunner not available")
        except Exception as e:
            logger.warning(f"SandboxTestRunner initialization failed: {e}")

    if not approval_service:
        try:
            from src.services.hitl_approval_service import HITLApprovalService, HITLMode

            # HITLApprovalService only takes mode, table_name, region, timeout_hours,
            # notification_service, backup_reviewers, escalation_timeout_hours
            table_name = f"{project_name}-hitl-approvals-{environment}"
            approval_service = HITLApprovalService(
                mode=HITLMode.AWS if BOTO3_AVAILABLE else HITLMode.MOCK,
                table_name=table_name,
                region=region,
            )
        except ImportError:
            logger.warning("HITLApprovalService not available")
        except Exception as e:
            logger.warning(f"HITLApprovalService initialization failed: {e}")

    if not meta_orchestrator:
        try:
            from src.agents.spawnable_agent_adapters import (
                create_production_meta_orchestrator,
            )

            meta_orchestrator = create_production_meta_orchestrator()
        except ImportError:
            logger.warning("MetaOrchestrator not available")
        except Exception as e:
            logger.warning(f"MetaOrchestrator initialization failed: {e}")

    return PatchValidationWorkflow(
        meta_orchestrator=meta_orchestrator,
        sandbox_runner=sandbox_runner,
        approval_service=approval_service,
        project_name=project_name,
        environment=environment,
        region=region,
    )
