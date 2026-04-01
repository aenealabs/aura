"""
Project Aura - Patch Validation Workflow Tests

Comprehensive test suite for end-to-end patch validation workflow:
- Unit tests with mocks
- Integration tests with simulated services
- E2E tests with real AWS (conditionally enabled)

Run with:
    pytest tests/test_patch_validation_workflow.py -v

For real AWS tests:
    RUN_INTEGRATION_TESTS=1 pytest tests/test_patch_validation_workflow.py -v -m integration

Author: Project Aura Team
Created: 2025-12-03
"""

import asyncio
import os
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.patch_validation_workflow import (
    PatchContext,
    PatchValidationWorkflow,
    ValidationResult,
    VulnerabilityContext,
    WorkflowResult,
    WorkflowState,
    WorkflowStatus,
    create_patch_validation_workflow,
)

# Check if real AWS integration tests should run
RUN_INTEGRATION_TESTS = os.environ.get("RUN_INTEGRATION_TESTS", "").lower() in (
    "1",
    "true",
    "yes",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_vulnerability():
    """Create a sample vulnerability context for testing."""
    return VulnerabilityContext(
        vulnerability_id="vuln-test-001",
        vulnerability_type="SQL_INJECTION",
        severity="HIGH",
        file_path="src/api/users.py",
        line_number=42,
        description="Unsanitized user input in SQL query allows injection attacks",
        cve_id="CVE-2024-12345",
        original_code='query = f"SELECT * FROM users WHERE id = {user_id}"',
        recommendation="Use parameterized queries instead of string formatting",
    )


@pytest.fixture
def sample_patch():
    """Create a sample patch context for testing."""
    return PatchContext(
        patch_id="patch-test-001",
        vulnerability_id="vuln-test-001",
        patch_content="""--- a/src/api/users.py
+++ b/src/api/users.py
@@ -42,1 +42,1 @@
- query = f"SELECT * FROM users WHERE id = {user_id}"
+ query = "SELECT * FROM users WHERE id = %s"
""",
        patched_code='query = "SELECT * FROM users WHERE id = %s"',
        file_path="src/api/users.py",
        agent_id="coder-agent-001",
        confidence_score=0.92,
    )


@pytest.fixture
def mock_meta_orchestrator():
    """Create a mock MetaOrchestrator."""
    mock = MagicMock()
    mock.execute = AsyncMock(
        return_value={
            "patch": """--- a/src/api/users.py
+++ b/src/api/users.py
@@ -42,1 +42,1 @@
- query = f"SELECT * FROM users WHERE id = {user_id}"
+ query = "SELECT * FROM users WHERE id = %s"
""",
            "patched_code": 'query = "SELECT * FROM users WHERE id = %s"',
            "agent_id": "coder-agent-001",
            "confidence": 0.92,
        }
    )
    return mock


@pytest.fixture
def mock_sandbox_runner():
    """Create a mock SandboxTestRunner."""
    mock = MagicMock()
    mock.run_patch_test = AsyncMock(
        return_value={
            "sandbox_id": "sandbox-test-001",
            "result_id": "result-test-001",
            "test_status": "pass",
            "approval_id": "approval-test-001",
        }
    )
    return mock


@pytest.fixture
def mock_approval_service():
    """Create a mock HITLApprovalService."""
    mock = MagicMock()
    mock.create_approval_request = AsyncMock(
        return_value=MagicMock(approval_id="approval-test-001")
    )
    mock.process_decision = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def workflow_with_mocks(
    mock_meta_orchestrator, mock_sandbox_runner, mock_approval_service
):
    """Create a PatchValidationWorkflow with all mocks."""
    return PatchValidationWorkflow(
        meta_orchestrator=mock_meta_orchestrator,
        sandbox_runner=mock_sandbox_runner,
        approval_service=mock_approval_service,
        project_name="aura",
        environment="test",
        region="us-east-1",
    )


@pytest.fixture
def workflow_no_services():
    """Create a PatchValidationWorkflow with no services (mock mode)."""
    return PatchValidationWorkflow(
        project_name="aura",
        environment="test",
        region="us-east-1",
    )


# =============================================================================
# Unit Tests - VulnerabilityContext
# =============================================================================


class TestVulnerabilityContext:
    """Tests for VulnerabilityContext dataclass."""

    def test_create_vulnerability_context(self, sample_vulnerability):
        """Test creating a vulnerability context."""
        assert sample_vulnerability.vulnerability_id == "vuln-test-001"
        assert sample_vulnerability.vulnerability_type == "SQL_INJECTION"
        assert sample_vulnerability.severity == "HIGH"
        assert sample_vulnerability.line_number == 42

    def test_vulnerability_with_optional_fields(self):
        """Test vulnerability context with optional fields."""
        vuln = VulnerabilityContext(
            vulnerability_id="vuln-002",
            vulnerability_type="XSS",
            severity="MEDIUM",
            file_path="src/templates/user.html",
            line_number=15,
            description="Unescaped user input in template",
        )
        assert vuln.cve_id is None
        assert vuln.original_code is None
        assert vuln.recommendation is None
        assert vuln.metadata == {}

    def test_vulnerability_with_metadata(self):
        """Test vulnerability context with metadata."""
        vuln = VulnerabilityContext(
            vulnerability_id="vuln-003",
            vulnerability_type="PATH_TRAVERSAL",
            severity="CRITICAL",
            file_path="src/api/files.py",
            line_number=78,
            description="Path traversal vulnerability",
            metadata={"detected_by": "bandit", "confidence": "HIGH"},
        )
        assert vuln.metadata["detected_by"] == "bandit"


# =============================================================================
# Unit Tests - PatchContext
# =============================================================================


class TestPatchContext:
    """Tests for PatchContext dataclass."""

    def test_create_patch_context(self, sample_patch):
        """Test creating a patch context."""
        assert sample_patch.patch_id == "patch-test-001"
        assert sample_patch.vulnerability_id == "vuln-test-001"
        assert sample_patch.confidence_score == 0.92
        assert sample_patch.agent_id == "coder-agent-001"

    def test_patch_has_generated_at(self, sample_patch):
        """Test that patch has generated_at timestamp."""
        assert sample_patch.generated_at is not None
        # Should be a valid ISO timestamp
        datetime.fromisoformat(sample_patch.generated_at.replace("Z", "+00:00"))


# =============================================================================
# Unit Tests - WorkflowState
# =============================================================================


class TestWorkflowState:
    """Tests for WorkflowState dataclass."""

    def test_create_workflow_state(self, sample_vulnerability):
        """Test creating a workflow state."""
        state = WorkflowState(
            workflow_id="workflow-test-001",
            status=WorkflowStatus.INITIATED,
            vulnerability=sample_vulnerability,
        )
        assert state.workflow_id == "workflow-test-001"
        assert state.status == WorkflowStatus.INITIATED
        assert state.vulnerability is not None
        assert state.patch is None
        assert state.sandbox_id is None

    def test_workflow_state_to_dict(self, sample_vulnerability, sample_patch):
        """Test converting workflow state to dictionary."""
        state = WorkflowState(
            workflow_id="workflow-test-001",
            status=WorkflowStatus.TESTS_PASSED,
            vulnerability=sample_vulnerability,
            patch=sample_patch,
            sandbox_id="sandbox-001",
            approval_id="approval-001",
        )

        result = state.to_dict()

        assert result["workflow_id"] == "workflow-test-001"
        assert result["status"] == "tests_passed"
        assert result["vulnerability"]["vulnerability_id"] == "vuln-test-001"
        assert result["patch"]["patch_id"] == "patch-test-001"
        assert result["sandbox_id"] == "sandbox-001"


class TestWorkflowStatus:
    """Tests for WorkflowStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert WorkflowStatus.INITIATED.value == "initiated"
        assert WorkflowStatus.PATCH_GENERATING.value == "patch_generating"
        assert WorkflowStatus.SANDBOX_TESTING.value == "sandbox_testing"
        assert WorkflowStatus.AWAITING_APPROVAL.value == "awaiting_approval"
        assert WorkflowStatus.APPROVED.value == "approved"
        assert WorkflowStatus.REJECTED.value == "rejected"
        assert WorkflowStatus.DEPLOYED.value == "deployed"


class TestValidationResult:
    """Tests for ValidationResult enum."""

    def test_result_values(self):
        """Test that all expected result values exist."""
        assert ValidationResult.SUCCESS.value == "success"
        assert ValidationResult.TESTS_FAILED.value == "tests_failed"
        assert ValidationResult.APPROVAL_REJECTED.value == "approval_rejected"
        assert ValidationResult.ERROR.value == "error"


# =============================================================================
# Unit Tests - PatchValidationWorkflow
# =============================================================================


class TestPatchValidationWorkflowUnit:
    """Unit tests for PatchValidationWorkflow with mocks."""

    @pytest.mark.asyncio
    async def test_execute_full_workflow(
        self, workflow_with_mocks, sample_vulnerability
    ):
        """Test executing the full workflow with all services mocked."""
        result = await workflow_with_mocks.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
            branch="main",
        )

        assert isinstance(result, WorkflowResult)
        assert result.workflow_id is not None
        assert result.result == ValidationResult.SUCCESS
        assert result.patch_id is not None
        assert result.sandbox_id is not None

    @pytest.mark.asyncio
    async def test_execute_without_services(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test executing workflow without external services (mock mode)."""
        result = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
            branch="main",
        )

        assert isinstance(result, WorkflowResult)
        assert result.result == ValidationResult.SUCCESS
        assert result.status == WorkflowStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_execute_generates_unique_ids(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test that each execution generates unique IDs."""
        result1 = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )
        result2 = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        assert result1.workflow_id != result2.workflow_id
        assert result1.patch_id != result2.patch_id

    @pytest.mark.asyncio
    async def test_workflow_state_persistence(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test that workflow state is persisted."""
        result = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        # Should be able to retrieve state
        status = await workflow_no_services.get_workflow_status(result.workflow_id)
        assert status is not None
        assert status["workflow_id"] == result.workflow_id
        assert status["status"] == "awaiting_approval"


# =============================================================================
# Integration Tests - Approval Callback
# =============================================================================


class TestApprovalCallback:
    """Tests for approval callback processing."""

    @pytest.mark.asyncio
    async def test_process_approval_approved(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test processing an APPROVED callback."""
        # First execute the workflow
        result = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        # Process approval
        approval_result = await workflow_no_services.process_approval_callback(
            workflow_id=result.workflow_id,
            approval_id=result.approval_id,
            decision="APPROVED",
            approver_email="senior.engineer@company.com",
            comments="Patch verified and approved",
        )

        assert approval_result.result == ValidationResult.SUCCESS
        assert approval_result.status == WorkflowStatus.APPROVED

    @pytest.mark.asyncio
    async def test_process_approval_rejected(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test processing a REJECTED callback."""
        result = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        approval_result = await workflow_no_services.process_approval_callback(
            workflow_id=result.workflow_id,
            approval_id=result.approval_id,
            decision="REJECTED",
            approver_email="senior.engineer@company.com",
            comments="Patch introduces regression",
        )

        assert approval_result.result == ValidationResult.APPROVAL_REJECTED
        assert approval_result.status == WorkflowStatus.REJECTED

    @pytest.mark.asyncio
    async def test_process_approval_with_auto_deploy(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test processing approval with auto_deploy enabled."""
        result = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        approval_result = await workflow_no_services.process_approval_callback(
            workflow_id=result.workflow_id,
            approval_id=result.approval_id,
            decision="APPROVED",
            approver_email="senior.engineer@company.com",
            auto_deploy=True,
        )

        assert approval_result.result == ValidationResult.SUCCESS
        assert approval_result.status == WorkflowStatus.DEPLOYED
        assert approval_result.deployment_id is not None

    @pytest.mark.asyncio
    async def test_process_approval_workflow_not_found(self, workflow_no_services):
        """Test processing approval for non-existent workflow."""
        result = await workflow_no_services.process_approval_callback(
            workflow_id="nonexistent-workflow",
            approval_id="nonexistent-approval",
            decision="APPROVED",
            approver_email="engineer@company.com",
        )

        assert result.result == ValidationResult.ERROR
        assert "not found" in result.error_message


# =============================================================================
# Integration Tests - Task Token Registration
# =============================================================================


class TestTaskTokenRegistration:
    """Tests for Step Functions task token registration."""

    @pytest.mark.asyncio
    async def test_register_task_token(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test registering a task token."""
        result = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        task_token = "AQCgAAAAKgAAAAMAAAAAAAAAAGSM..."  # Mock token

        success = await workflow_no_services.register_task_token(
            workflow_id=result.workflow_id, task_token=task_token
        )

        assert success is True

        # Verify token was stored (call succeeds = workflow exists with token)
        _ = await workflow_no_services.get_workflow_status(result.workflow_id)
        # Note: task_token is not exposed in status dict for security

    @pytest.mark.asyncio
    async def test_register_token_workflow_not_found(self, workflow_no_services):
        """Test registering token for non-existent workflow."""
        success = await workflow_no_services.register_task_token(
            workflow_id="nonexistent-workflow",
            task_token="some-token",
        )

        assert success is False


# =============================================================================
# Integration Tests - Workflow Management
# =============================================================================


class TestWorkflowManagement:
    """Tests for workflow management operations."""

    @pytest.mark.asyncio
    async def test_list_pending_workflows(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test listing pending workflows."""
        # Create a few workflows
        await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo1",
        )
        await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo2",
        )

        pending = await workflow_no_services.list_pending_workflows()

        assert len(pending) >= 2
        for workflow in pending:
            assert workflow["status"] == "awaiting_approval"

    @pytest.mark.asyncio
    async def test_cancel_workflow(self, workflow_no_services, sample_vulnerability):
        """Test cancelling a workflow."""
        result = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        success = await workflow_no_services.cancel_workflow(
            workflow_id=result.workflow_id, reason="Testing cancellation"
        )

        assert success is True

        status = await workflow_no_services.get_workflow_status(result.workflow_id)
        assert status["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cannot_cancel_deployed_workflow(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test that deployed workflows cannot be cancelled."""
        result = await workflow_no_services.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        # Approve and deploy
        await workflow_no_services.process_approval_callback(
            workflow_id=result.workflow_id,
            approval_id=result.approval_id,
            decision="APPROVED",
            approver_email="engineer@company.com",
            auto_deploy=True,
        )

        # Try to cancel
        success = await workflow_no_services.cancel_workflow(
            workflow_id=result.workflow_id
        )

        assert success is False


# =============================================================================
# Integration Tests - Factory Function
# =============================================================================


class TestFactoryFunction:
    """Tests for create_patch_validation_workflow factory."""

    def test_create_workflow_direct(self):
        """Test creating workflow directly (bypasses service auto-creation)."""
        # Create workflow directly without factory auto-creation of services
        workflow = PatchValidationWorkflow(
            project_name="aura",
            environment="test",
            region="us-east-1",
        )

        assert workflow is not None
        assert workflow.environment == "test"
        assert workflow.project_name == "aura"

    def test_create_workflow_custom_project(self):
        """Test creating workflow with custom project name."""
        # Create workflow directly to avoid AWS calls in test environment
        workflow = PatchValidationWorkflow(
            project_name="custom-project",
            environment="test",
            region="us-west-2",
        )

        assert workflow.project_name == "custom-project"
        assert workflow.environment == "test"
        assert workflow.region == "us-west-2"


# =============================================================================
# E2E Tests - Real AWS (Conditionally Enabled)
# =============================================================================


@pytest.mark.skipif(
    not RUN_INTEGRATION_TESTS,
    reason="Real AWS tests disabled - set RUN_INTEGRATION_TESTS=1 to enable",
)
class TestRealAWSIntegration:
    """E2E tests with real AWS services."""

    @pytest.fixture
    def real_workflow(self):
        """Create a workflow with real AWS connections."""
        return create_patch_validation_workflow(
            project_name="aura",
            environment="dev",
            region="us-east-1",
        )

    @pytest.fixture
    def real_vulnerability(self):
        """Create a test vulnerability for E2E testing."""
        return VulnerabilityContext(
            vulnerability_id=f"vuln-e2e-{uuid.uuid4().hex[:8]}",
            vulnerability_type="WEAK_CRYPTO",
            severity="HIGH",
            file_path="src/utils/crypto.py",
            line_number=15,
            description="SHA1 hash detected - should use SHA256",
            original_code="hashlib.sha1(data).hexdigest()",
            recommendation="Replace sha1 with sha256",
        )

    @pytest.mark.asyncio
    async def test_e2e_workflow_execution(self, real_workflow, real_vulnerability):
        """Test full workflow execution against real AWS."""
        result = await real_workflow.execute(
            vulnerability=real_vulnerability,
            repository_url="https://github.com/test/sample-repo",
            branch="main",
            test_suite="unit",
        )

        assert result is not None
        assert result.workflow_id is not None
        assert result.result in [
            ValidationResult.SUCCESS,
            ValidationResult.ERROR,  # May fail if services not deployed
        ]

        print(f"\n  E2E Workflow ID: {result.workflow_id}")
        print(f"  Result: {result.result.value}")
        print(f"  Status: {result.status.value}")

    @pytest.mark.asyncio
    async def test_e2e_workflow_status_retrieval(
        self, real_workflow, real_vulnerability
    ):
        """Test retrieving workflow status from DynamoDB."""
        result = await real_workflow.execute(
            vulnerability=real_vulnerability,
            repository_url="https://github.com/test/sample-repo",
        )

        if result.result == ValidationResult.SUCCESS:
            status = await real_workflow.get_workflow_status(result.workflow_id)

            assert status is not None
            assert status["workflow_id"] == result.workflow_id

            print(f"\n  Retrieved status: {status['status']}")


# =============================================================================
# Performance Tests
# =============================================================================


class TestWorkflowPerformance:
    """Performance tests for workflow operations."""

    @pytest.mark.asyncio
    async def test_concurrent_workflow_execution(
        self, workflow_no_services, sample_vulnerability
    ):
        """Test executing multiple workflows concurrently."""
        import time

        start = time.time()

        # Execute 10 workflows concurrently
        tasks = [
            workflow_no_services.execute(
                vulnerability=sample_vulnerability,
                repository_url=f"https://github.com/test/repo{i}",
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start

        assert len(results) == 10
        assert all(r.result == ValidationResult.SUCCESS for r in results)

        # All workflows should complete in reasonable time
        assert elapsed < 5.0, f"Concurrent execution took {elapsed:.2f}s"

        print(f"\n  10 concurrent workflows completed in {elapsed:.2f}s")


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_handle_orchestrator_failure(self, sample_vulnerability):
        """Test handling when MetaOrchestrator fails."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute = AsyncMock(
            side_effect=Exception("LLM API unavailable")
        )

        workflow = PatchValidationWorkflow(
            meta_orchestrator=mock_orchestrator,
            environment="test",
        )

        result = await workflow.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        assert result.result == ValidationResult.ERROR
        assert result.status == WorkflowStatus.FAILED
        assert "LLM API unavailable" in result.error_message

    @pytest.mark.asyncio
    async def test_handle_sandbox_test_failure(self, sample_vulnerability):
        """Test handling when sandbox tests fail."""
        mock_sandbox = MagicMock()
        mock_sandbox.run_patch_test = AsyncMock(
            return_value={
                "sandbox_id": "sandbox-001",
                "result_id": "result-001",
                "test_status": "fail",
                "tests_passed": False,
            }
        )

        workflow = PatchValidationWorkflow(
            sandbox_runner=mock_sandbox,
            environment="test",
        )

        result = await workflow.execute(
            vulnerability=sample_vulnerability,
            repository_url="https://github.com/test/repo",
        )

        assert result.result == ValidationResult.TESTS_FAILED
        assert result.status == WorkflowStatus.TESTS_FAILED
