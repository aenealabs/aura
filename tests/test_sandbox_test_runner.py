"""
Tests for Sandbox Test Runner Service

Tests the HITL workflow orchestration including:
- Patch test request handling
- Sandbox state management
- Approval request creation
- DynamoDB integration (mocked)
"""

import platform
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.sandbox_test_runner import (
    ApprovalRequest,
    ApprovalStatus,
    PatchTestRequest,
    SandboxTestRunner,
    TestResult,
    TestResultType,
    TestStatus,
)


class TestPatchTestRequest:
    """Tests for PatchTestRequest dataclass."""

    def test_create_minimal_request(self):
        """Test creating a minimal patch test request."""
        request = PatchTestRequest(
            patch_id="patch-123",
            repository_url="https://github.com/test/repo",
            branch="main",
            patch_content="diff --git a/file.py",
            test_suite="unit",
        )

        assert request.patch_id == "patch-123"
        assert request.repository_url == "https://github.com/test/repo"
        assert request.branch == "main"
        assert request.severity == "MEDIUM"  # default
        assert request.isolation_level == "container"  # default
        assert request.timeout_minutes == 30  # default

    def test_create_full_request(self):
        """Test creating a full patch test request with all fields."""
        request = PatchTestRequest(
            patch_id="patch-456",
            repository_url="https://github.com/test/repo",
            branch="feature-branch",
            patch_content="diff --git a/file.py\n+new line",
            test_suite="integration",
            vulnerability_id="CVE-2024-1234",
            severity="HIGH",
            isolation_level="vpc",
            timeout_minutes=60,
            metadata={"author": "test-user"},
        )

        assert request.severity == "HIGH"
        assert request.isolation_level == "vpc"
        assert request.timeout_minutes == 60
        assert request.vulnerability_id == "CVE-2024-1234"
        assert request.metadata == {"author": "test-user"}


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_create_passing_result(self):
        """Test creating a passing test result."""
        result = TestResult(
            result_id="result-abc",
            sandbox_id="sandbox-123",
            patch_id="patch-123",
            status=TestResultType.PASS,
            tests_passed=10,
            tests_failed=0,
            tests_skipped=2,
            test_duration_seconds=45.5,
        )

        assert result.status == TestResultType.PASS
        assert result.tests_passed == 10
        assert result.tests_failed == 0

    def test_create_failing_result(self):
        """Test creating a failing test result."""
        result = TestResult(
            result_id="result-def",
            sandbox_id="sandbox-456",
            patch_id="patch-456",
            status=TestResultType.FAIL,
            tests_passed=5,
            tests_failed=3,
            tests_skipped=0,
            error_message="Assertion failed in test_security.py",
        )

        assert result.status == TestResultType.FAIL
        assert result.tests_failed == 3
        assert result.error_message is not None

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = TestResult(
            result_id="result-xyz",
            sandbox_id="sandbox-789",
            patch_id="patch-789",
            status=TestResultType.PASS,
            tests_passed=15,
            tests_failed=0,
            tests_skipped=1,
            test_duration_seconds=30.0,
        )

        result_dict = result.to_dict()

        assert result_dict["result_id"] == "result-xyz"
        assert result_dict["sandbox_id"] == "sandbox-789"
        assert result_dict["status"] == "pass"
        assert result_dict["tests_passed"] == 15
        assert "created_at" in result_dict


class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass."""

    def test_create_pending_approval(self):
        """Test creating a pending approval request."""
        approval = ApprovalRequest(
            approval_id="approval-123",
            patch_id="patch-123",
            sandbox_id="sandbox-123",
            result_id="result-123",
            status=ApprovalStatus.PENDING,
            severity="HIGH",
            repository_url="https://github.com/test/repo",
        )

        assert approval.status == ApprovalStatus.PENDING
        assert approval.reviewer_email is None
        assert approval.decision_at is None

    def test_to_dict(self):
        """Test converting approval to dictionary."""
        approval = ApprovalRequest(
            approval_id="approval-456",
            patch_id="patch-456",
            sandbox_id="sandbox-456",
            result_id="result-456",
            status=ApprovalStatus.PENDING,
            severity="MEDIUM",
            repository_url="https://github.com/test/repo",
            vulnerability_id="CVE-2024-5678",
        )

        approval_dict = approval.to_dict()

        assert approval_dict["approval_id"] == "approval-456"
        assert approval_dict["status"] == "pending"
        assert approval_dict["vulnerability_id"] == "CVE-2024-5678"
        assert "created_at" in approval_dict


class TestSandboxTestRunner:
    """Tests for SandboxTestRunner class."""

    @pytest.fixture
    def mock_boto3(self):
        """Mock boto3 clients."""
        with patch("src.services.sandbox_test_runner.boto3") as mock:
            # Mock session
            mock_session = MagicMock()
            mock_session.region_name = "us-east-1"
            mock.session.Session.return_value = mock_session

            # Mock resource
            mock_table = MagicMock()
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock.resource.return_value = mock_dynamodb

            # Mock clients
            mock_ecs = MagicMock()
            mock_sns = MagicMock()
            mock_s3 = MagicMock()
            mock_sts = MagicMock()
            mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

            mock.client.side_effect = lambda service, **kwargs: {
                "ecs": mock_ecs,
                "sns": mock_sns,
                "s3": mock_s3,
                "sts": mock_sts,
            }.get(service, MagicMock())

            yield {
                "dynamodb": mock_dynamodb,
                "table": mock_table,
                "ecs": mock_ecs,
                "sns": mock_sns,
                "s3": mock_s3,
                "sts": mock_sts,
            }

    def test_init(self, mock_boto3):
        """Test SandboxTestRunner initialization."""
        runner = SandboxTestRunner(
            environment="dev",
            project_name="aura",
        )

        assert runner.environment == "dev"
        assert runner.project_name == "aura"
        assert runner.approval_table_name == "aura-approval-requests-dev"
        assert runner.sandbox_table_name == "aura-sandbox-state-dev"
        assert runner.cluster_name == "aura-sandboxes-dev"

    def test_init_custom_region(self, mock_boto3):
        """Test initialization with custom region."""
        runner = SandboxTestRunner(
            environment="qa",
            project_name="test",
            region="us-west-2",
        )

        assert runner.region == "us-west-2"

    @pytest.mark.asyncio
    async def test_upload_patch(self, mock_boto3):
        """Test uploading patch content to S3."""
        runner = SandboxTestRunner()
        sandbox_id = "sandbox-test-123"
        patch_content = "diff --git a/test.py\n+new line"

        key = await runner._upload_patch(sandbox_id, patch_content)

        assert key == f"patches/{sandbox_id}/patch.diff"
        mock_boto3["s3"].put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_sandbox(self, mock_boto3):
        """Test creating sandbox record in DynamoDB."""
        runner = SandboxTestRunner()
        sandbox_id = "sandbox-test-456"
        request = PatchTestRequest(
            patch_id="patch-123",
            repository_url="https://github.com/test/repo",
            branch="main",
            patch_content="diff content",
            test_suite="unit",
        )

        result = await runner._create_sandbox(
            sandbox_id, request, "patches/test/patch.diff"
        )

        assert result["sandbox_id"] == sandbox_id
        assert result["status"] == TestStatus.PROVISIONING.value
        mock_boto3["table"].put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_result(self, mock_boto3):
        """Test storing test result in DynamoDB."""
        runner = SandboxTestRunner()
        result = TestResult(
            result_id="result-test-123",
            sandbox_id="sandbox-123",
            patch_id="patch-123",
            status=TestResultType.PASS,
            tests_passed=10,
            tests_failed=0,
            tests_skipped=1,
        )

        await runner._store_result(result)

        mock_boto3["table"].put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_approval_request(self, mock_boto3):
        """Test getting approval request by ID."""
        mock_boto3["table"].get_item.return_value = {
            "Item": {
                "approval_id": "approval-123",
                "status": "pending",
                "patch_id": "patch-123",
            }
        }

        runner = SandboxTestRunner()
        result = await runner.get_approval_request("approval-123")

        assert result is not None
        assert result["approval_id"] == "approval-123"

    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, mock_boto3):
        """Test getting pending approval requests."""
        mock_boto3["table"].query.return_value = {
            "Items": [
                {"approval_id": "approval-1", "status": "pending"},
                {"approval_id": "approval-2", "status": "pending"},
            ]
        }

        runner = SandboxTestRunner()
        results = await runner.get_pending_approvals()

        assert len(results) == 2
        mock_boto3["table"].query.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_patch(self, mock_boto3):
        """Test approving a patch."""
        mock_boto3["table"].update_item.return_value = {
            "Attributes": {
                "approval_id": "approval-123",
                "status": "approved",
                "reviewer_email": "reviewer@test.com",
            }
        }

        runner = SandboxTestRunner()
        result = await runner.approve_patch(
            approval_id="approval-123",
            reviewer_email="reviewer@test.com",
            comment="Looks good!",
        )

        assert result["status"] == "approved"
        assert result["reviewer_email"] == "reviewer@test.com"

    @pytest.mark.asyncio
    async def test_reject_patch(self, mock_boto3):
        """Test rejecting a patch."""
        mock_boto3["table"].update_item.return_value = {
            "Attributes": {
                "approval_id": "approval-456",
                "status": "rejected",
                "reviewer_email": "reviewer@test.com",
                "decision_comment": "Security concern",
            }
        }

        runner = SandboxTestRunner()
        result = await runner.reject_patch(
            approval_id="approval-456",
            reviewer_email="reviewer@test.com",
            reason="Security concern",
        )

        assert result["status"] == "rejected"


class TestEnums:
    """Tests for status enums."""

    def test_test_status_values(self):
        """Test TestStatus enum values."""
        assert TestStatus.PENDING.value == "pending"
        assert TestStatus.RUNNING.value == "running"
        assert TestStatus.COMPLETED.value == "completed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.TIMEOUT.value == "timeout"

    def test_approval_status_values(self):
        """Test ApprovalStatus enum values."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.EXPIRED.value == "expired"

    def test_test_result_type_values(self):
        """Test TestResultType enum values."""
        assert TestResultType.PASS.value == "pass"
        assert TestResultType.FAIL.value == "fail"
        assert TestResultType.ERROR.value == "error"
        assert TestResultType.SKIP.value == "skip"


class TestIntegration:
    """Integration tests (require AWS credentials or LocalStack)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """
        Test the complete patch testing workflow.
        Requires RUN_INTEGRATION_TESTS=1 environment variable.
        """
        import os

        if not os.getenv("RUN_INTEGRATION_TESTS"):
            pytest.skip("Integration tests disabled")

        runner = SandboxTestRunner()

        request = PatchTestRequest(
            patch_id="test-patch-integration",
            repository_url="https://github.com/test/repo",
            branch="main",
            patch_content="# Test patch content",
            test_suite="unit",
            severity="LOW",
        )

        result = await runner.run_patch_test(request)

        assert "sandbox_id" in result
        assert "approval_id" in result
        assert result["test_status"] in ["pass", "fail", "error"]
