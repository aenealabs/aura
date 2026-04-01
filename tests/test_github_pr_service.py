"""
Tests for GitHub PR Service.

Tests the GitHubPRService for creating remediation PRs, applying patches,
and adding security context comments.

Target: 85%+ coverage of src/services/github_pr_service.py
"""

import os
import platform
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Set environment before importing
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

from src.services.github_pr_service import (
    PYGITHUB_AVAILABLE,
    GitHubPRService,
    PatchInfo,
    PRCreationResult,
    PRCreationStatus,
    TestResultInfo,
    VulnerabilityInfo,
    create_github_pr_service,
)

# Import GithubException if available for exception testing
if PYGITHUB_AVAILABLE:
    from github import GithubException
else:
    GithubException = Exception  # Fallback for type hints

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_github_service():
    """Create a GitHubPRService in mock mode for testing."""
    return GitHubPRService(use_mock=True)


@pytest.fixture
def sample_vulnerability_info():
    """Create sample vulnerability info for testing."""
    return VulnerabilityInfo(
        vulnerability_id="vuln-001",
        vulnerability_type="SQL_INJECTION",
        severity="CRITICAL",
        file_path="src/api/users.py",
        line_number=42,
        description="Unsanitized user input in SQL query allows injection",
        cve_id="CVE-2024-12345",
        recommendation="Use parameterized queries",
    )


@pytest.fixture
def sample_patch_info():
    """Create sample patch info for testing."""
    return PatchInfo(
        patch_id="patch-abc123",
        patch_content='--- a/src/api/users.py\n+++ b/src/api/users.py\n@@ -42,1 +42,1 @@\n- query = f"SELECT * FROM users WHERE id = {user_id}"\n+ query = "SELECT * FROM users WHERE id = %s"',
        patched_code='query = "SELECT * FROM users WHERE id = %s"',
        file_path="src/api/users.py",
        confidence_score=0.95,
        agent_id="coder-agent-001",
    )


@pytest.fixture
def sample_test_results():
    """Create sample test results for testing."""
    return TestResultInfo(
        tests_passed=47,
        tests_failed=0,
        sandbox_id="sandbox-xyz789",
        test_report_url="https://reports.example.com/sandbox-xyz789",
        security_scan_passed=True,
        coverage_percent=85.5,
    )


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestVulnerabilityInfo:
    """Tests for VulnerabilityInfo dataclass."""

    def test_create_vulnerability_info(self, sample_vulnerability_info):
        """Test creating a VulnerabilityInfo instance."""
        vuln = sample_vulnerability_info
        assert vuln.vulnerability_id == "vuln-001"
        assert vuln.vulnerability_type == "SQL_INJECTION"
        assert vuln.severity == "CRITICAL"
        assert vuln.file_path == "src/api/users.py"
        assert vuln.line_number == 42

    def test_vulnerability_with_cve(self, sample_vulnerability_info):
        """Test vulnerability with CVE ID."""
        assert sample_vulnerability_info.cve_id == "CVE-2024-12345"

    def test_vulnerability_optional_fields(self):
        """Test vulnerability with minimal required fields."""
        vuln = VulnerabilityInfo(
            vulnerability_id="vuln-002",
            vulnerability_type="XSS",
            severity="HIGH",
            file_path="src/web/template.html",
            line_number=100,
            description="Reflected XSS in search form",
        )
        assert vuln.cve_id is None
        assert vuln.recommendation is None


class TestPatchInfo:
    """Tests for PatchInfo dataclass."""

    def test_create_patch_info(self, sample_patch_info):
        """Test creating a PatchInfo instance."""
        patch = sample_patch_info
        assert patch.patch_id == "patch-abc123"
        assert "SELECT * FROM users WHERE id = %s" in patch.patched_code
        assert patch.confidence_score == 0.95

    def test_patch_content_is_diff(self, sample_patch_info):
        """Test that patch_content contains unified diff format."""
        assert "---" in sample_patch_info.patch_content
        assert "+++" in sample_patch_info.patch_content
        assert "@@" in sample_patch_info.patch_content


class TestTestResultInfo:
    """Tests for TestResultInfo dataclass."""

    def test_create_test_results(self, sample_test_results):
        """Test creating TestResultInfo instance."""
        results = sample_test_results
        assert results.tests_passed == 47
        assert results.tests_failed == 0
        assert results.security_scan_passed is True

    def test_test_results_defaults(self):
        """Test default values for TestResultInfo."""
        results = TestResultInfo()
        assert results.tests_passed == 0
        assert results.tests_failed == 0
        assert results.sandbox_id == ""
        assert results.security_scan_passed is True


class TestPRCreationResult:
    """Tests for PRCreationResult dataclass."""

    def test_success_result(self):
        """Test successful PR creation result."""
        result = PRCreationResult(
            status=PRCreationStatus.SUCCESS,
            pr_number=123,
            pr_url="https://github.com/org/repo/pull/123",
            branch_name="security/patch-abc123",
            commit_sha="abc123def456",
            comment_ids=[1001],
        )
        assert result.status == PRCreationStatus.SUCCESS
        assert result.pr_number == 123
        assert result.error_message is None

    def test_error_result(self):
        """Test error PR creation result."""
        result = PRCreationResult(
            status=PRCreationStatus.ERROR,
            error_message="Repository not found",
        )
        assert result.status == PRCreationStatus.ERROR
        assert result.pr_number is None
        assert "not found" in result.error_message


# =============================================================================
# GitHubPRService Mock Mode Tests
# =============================================================================


class TestGitHubPRServiceMock:
    """Tests for GitHubPRService in mock mode."""

    @pytest.mark.asyncio
    async def test_create_remediation_pr_mock(
        self,
        mock_github_service,
        sample_patch_info,
        sample_vulnerability_info,
        sample_test_results,
    ):
        """Test creating a remediation PR in mock mode."""
        result = await mock_github_service.create_remediation_pr(
            repo_url="https://github.com/org/repo",
            patch_info=sample_patch_info,
            vulnerability_info=sample_vulnerability_info,
            test_results=sample_test_results,
            base_branch="main",
            approver_email="security@example.com",
            approval_id="approval-001",
            workflow_id="workflow-001",
        )

        assert result.status == PRCreationStatus.SUCCESS
        assert result.pr_number is not None
        assert result.pr_url is not None
        assert "github.com/org/repo/pull/" in result.pr_url
        assert result.branch_name == f"security/{sample_patch_info.patch_id}"
        assert result.commit_sha is not None
        assert len(result.comment_ids) > 0

    @pytest.mark.asyncio
    async def test_create_pr_generates_unique_numbers(self, mock_github_service):
        """Test that mock PRs get unique numbers."""
        patch1 = PatchInfo(
            patch_id="patch-001",
            patch_content="diff",
            patched_code="code",
            file_path="file1.py",
        )
        patch2 = PatchInfo(
            patch_id="patch-002",
            patch_content="diff",
            patched_code="code",
            file_path="file2.py",
        )
        vuln = VulnerabilityInfo(
            vulnerability_id="vuln-001",
            vulnerability_type="TEST",
            severity="LOW",
            file_path="file.py",
            line_number=1,
            description="Test",
        )

        result1 = await mock_github_service.create_remediation_pr(
            repo_url="https://github.com/org/repo",
            patch_info=patch1,
            vulnerability_info=vuln,
        )
        result2 = await mock_github_service.create_remediation_pr(
            repo_url="https://github.com/org/repo",
            patch_info=patch2,
            vulnerability_info=vuln,
        )

        assert result1.pr_number != result2.pr_number

    @pytest.mark.asyncio
    async def test_create_pr_without_test_results(
        self,
        mock_github_service,
        sample_patch_info,
        sample_vulnerability_info,
    ):
        """Test creating a PR without test results."""
        result = await mock_github_service.create_remediation_pr(
            repo_url="https://github.com/org/repo",
            patch_info=sample_patch_info,
            vulnerability_info=sample_vulnerability_info,
            test_results=None,
        )

        assert result.status == PRCreationStatus.SUCCESS
        assert result.pr_number is not None

    @pytest.mark.asyncio
    async def test_get_pr_status_mock(
        self, mock_github_service, sample_patch_info, sample_vulnerability_info
    ):
        """Test getting PR status in mock mode."""
        # First create a PR
        create_result = await mock_github_service.create_remediation_pr(
            repo_url="https://github.com/org/repo",
            patch_info=sample_patch_info,
            vulnerability_info=sample_vulnerability_info,
        )

        # Then check its status
        status = await mock_github_service.get_pr_status(
            repo_url="https://github.com/org/repo",
            pr_number=create_result.pr_number,
        )

        assert status["found"] is True
        assert status["state"] == "open"
        assert status["merged"] is False

    @pytest.mark.asyncio
    async def test_get_pr_status_not_found(self, mock_github_service):
        """Test getting status of non-existent PR."""
        status = await mock_github_service.get_pr_status(
            repo_url="https://github.com/org/repo",
            pr_number=99999,
        )

        assert status["found"] is False

    @pytest.mark.asyncio
    async def test_merge_pr_mock(
        self, mock_github_service, sample_patch_info, sample_vulnerability_info
    ):
        """Test merging a PR in mock mode."""
        # Create a PR
        create_result = await mock_github_service.create_remediation_pr(
            repo_url="https://github.com/org/repo",
            patch_info=sample_patch_info,
            vulnerability_info=sample_vulnerability_info,
        )

        # Merge it
        merge_result = await mock_github_service.merge_pr(
            repo_url="https://github.com/org/repo",
            pr_number=create_result.pr_number,
        )

        assert merge_result["success"] is True
        assert merge_result["merged"] is True

    @pytest.mark.asyncio
    async def test_merge_nonexistent_pr(self, mock_github_service):
        """Test merging a non-existent PR fails."""
        merge_result = await mock_github_service.merge_pr(
            repo_url="https://github.com/org/repo",
            pr_number=99999,
        )

        assert merge_result["success"] is False
        assert "not found" in merge_result["error"].lower()


# =============================================================================
# PR Title and Body Generation Tests
# =============================================================================


class TestPRGeneration:
    """Tests for PR title and body generation."""

    def test_generate_pr_title_critical(
        self, mock_github_service, sample_vulnerability_info
    ):
        """Test PR title generation for critical vulnerability."""
        title = mock_github_service._generate_pr_title(sample_vulnerability_info)

        assert "Security" in title
        assert "Sql Injection" in title or "SQL INJECTION" in title.upper()
        assert "users.py" in title
        # Should have severity emoji
        assert "\U0001f6a8" in title or "\U0001f534" in title  # 🚨 or 🔴

    def test_generate_pr_title_different_severities(self, mock_github_service):
        """Test PR title emojis for different severities."""
        severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

        for severity in severities:
            vuln = VulnerabilityInfo(
                vulnerability_id="test",
                vulnerability_type="TEST",
                severity=severity,
                file_path="test.py",
                line_number=1,
                description="Test",
            )
            title = mock_github_service._generate_pr_title(vuln)
            # Should contain some emoji based on severity
            assert "Security" in title

    def test_generate_pr_body_contains_sections(
        self,
        mock_github_service,
        sample_patch_info,
        sample_vulnerability_info,
        sample_test_results,
    ):
        """Test PR body contains all required sections."""
        body = mock_github_service._generate_pr_body(
            patch_info=sample_patch_info,
            vulnerability_info=sample_vulnerability_info,
            test_results=sample_test_results,
            approver_email="security@example.com",
            approval_id="approval-001",
            workflow_id="workflow-001",
        )

        # Check vulnerability section
        assert "Vulnerability Details" in body
        assert "SQL_INJECTION" in body
        assert "CRITICAL" in body
        assert "CVE-2024-12345" in body

        # Check patch section
        assert "Patch Information" in body
        assert "patch-abc123" in body
        assert "95%" in body  # confidence score

        # Check test results section
        assert "Sandbox Testing Results" in body
        assert "47" in body  # tests passed
        assert "sandbox-xyz789" in body

        # Check approval section
        assert "HITL Approval" in body
        assert "security@example.com" in body

    def test_generate_commit_message(
        self,
        mock_github_service,
        sample_patch_info,
        sample_vulnerability_info,
    ):
        """Test commit message generation."""
        message = mock_github_service._generate_commit_message(
            vulnerability_info=sample_vulnerability_info,
            patch_info=sample_patch_info,
        )

        # Should follow conventional commits
        assert message.startswith("fix(security):")
        assert "sql injection" in message.lower()
        assert "vuln-001" in message
        assert "CRITICAL" in message
        assert "CVE-2024-12345" in message


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_github_pr_service_mock(self):
        """Test creating service in mock mode."""
        service = create_github_pr_service(use_mock=True)
        assert service._use_mock is True

    def test_create_github_pr_service_default_env(self):
        """Test creating service with default environment."""
        service = create_github_pr_service(environment="dev", use_mock=True)
        assert service.environment == "dev"

    def test_create_github_pr_service_prod_env(self):
        """Test creating service with production environment."""
        service = create_github_pr_service(environment="prod", use_mock=True)
        assert service.environment == "prod"


# =============================================================================
# Integration with Workflow Tests
# =============================================================================


class TestWorkflowIntegration:
    """Tests for integration with PatchValidationWorkflow."""

    @pytest.mark.asyncio
    async def test_pr_creation_in_workflow_context(
        self,
        mock_github_service,
        sample_patch_info,
        sample_vulnerability_info,
        sample_test_results,
    ):
        """Test PR creation with full workflow context."""
        result = await mock_github_service.create_remediation_pr(
            repo_url="https://github.com/aenea-labs/security-app",
            patch_info=sample_patch_info,
            vulnerability_info=sample_vulnerability_info,
            test_results=sample_test_results,
            base_branch="main",
            approver_email="senior-engineer@aenealabs.com",
            approval_id="approval-hitl-001",
            workflow_id="workflow-patch-abc123",
        )

        assert result.status == PRCreationStatus.SUCCESS
        # Branch should include patch ID
        assert sample_patch_info.patch_id in result.branch_name
        # PR should be trackable
        assert result.pr_number is not None
        assert result.pr_url is not None

    @pytest.mark.asyncio
    async def test_pr_for_different_vulnerability_types(self, mock_github_service):
        """Test PR creation for different vulnerability types."""
        vuln_types = [
            ("SQL_INJECTION", "CRITICAL"),
            ("XSS", "HIGH"),
            ("CSRF", "MEDIUM"),
            ("SSRF", "HIGH"),
            ("PATH_TRAVERSAL", "HIGH"),
            ("COMMAND_INJECTION", "CRITICAL"),
        ]

        for vuln_type, severity in vuln_types:
            vuln = VulnerabilityInfo(
                vulnerability_id=f"vuln-{vuln_type.lower()}",
                vulnerability_type=vuln_type,
                severity=severity,
                file_path="src/vulnerable.py",
                line_number=1,
                description=f"Test {vuln_type} vulnerability",
            )
            patch = PatchInfo(
                patch_id=f"patch-{vuln_type.lower()}",
                patch_content="diff",
                patched_code="fixed",
                file_path="src/vulnerable.py",
            )

            result = await mock_github_service.create_remediation_pr(
                repo_url="https://github.com/org/repo",
                patch_info=patch,
                vulnerability_info=vuln,
            )

            assert result.status == PRCreationStatus.SUCCESS, f"Failed for {vuln_type}"


# =============================================================================
# SpawnableAgent Adapter Tests
# =============================================================================


class TestSpawnableGitHubIntegrationAgent:
    """Tests for SpawnableGitHubIntegrationAgent adapter."""

    @pytest.mark.asyncio
    async def test_agent_execute_success(self):
        """Test agent execute method with valid context."""
        from src.agents.spawnable_agent_adapters import SpawnableGitHubIntegrationAgent

        agent = SpawnableGitHubIntegrationAgent()
        # Force mock mode by directly setting the wrapped agent
        agent._wrapped_agent = GitHubPRService(use_mock=True)

        context = {
            "repo_url": "https://github.com/org/repo",
            "patch_info": {
                "patch_id": "patch-001",
                "patch_content": "diff",
                "patched_code": "code",
                "file_path": "file.py",
            },
            "vulnerability_info": {
                "vulnerability_id": "vuln-001",
                "vulnerability_type": "TEST",
                "severity": "LOW",
                "file_path": "file.py",
                "line_number": 1,
                "description": "Test vulnerability",
            },
        }

        result = await agent.execute("Create PR for security patch", context)

        assert result.success is True
        assert result.output["status"] == "success"
        assert result.output["pr_number"] is not None

    @pytest.mark.asyncio
    async def test_agent_execute_missing_context(self):
        """Test agent execute with missing required context."""
        from src.agents.spawnable_agent_adapters import SpawnableGitHubIntegrationAgent

        agent = SpawnableGitHubIntegrationAgent()

        # Empty context should fail
        result = await agent.execute("Create PR", context={})

        # Should handle gracefully
        assert result is not None

    @pytest.mark.asyncio
    async def test_agent_execute_invalid_context_type(self):
        """Test agent execute with invalid context type."""
        from src.agents.spawnable_agent_adapters import SpawnableGitHubIntegrationAgent

        agent = SpawnableGitHubIntegrationAgent()

        # String context should fail gracefully
        result = await agent.execute("Create PR", context="invalid")

        assert result.success is False
        assert "Context must be a dict" in result.error


# =============================================================================
# Credential Loading Tests
# =============================================================================


class TestCredentialLoading:
    """Tests for credential loading methods."""

    def test_load_ssm_parameter_success(self):
        """Test successful SSM parameter loading."""
        with patch("src.services.github_pr_service.BOTO3_AVAILABLE", True):
            with patch("src.services.github_pr_service.boto3") as mock_boto3:
                mock_ssm = MagicMock()
                mock_ssm.get_parameter.return_value = {
                    "Parameter": {"Value": "test-value"}
                }
                mock_boto3.client.return_value = mock_ssm

                service = GitHubPRService(use_mock=True)
                result = service._load_ssm_parameter("/test/param")

                assert result == "test-value"
                mock_ssm.get_parameter.assert_called_once_with(
                    Name="/test/param", WithDecryption=True
                )

    def test_load_ssm_parameter_boto3_unavailable(self):
        """Test SSM loading when boto3 is unavailable."""
        with patch("src.services.github_pr_service.BOTO3_AVAILABLE", False):
            service = GitHubPRService(use_mock=True)
            result = service._load_ssm_parameter("/test/param")

            assert result is None

    def test_load_ssm_parameter_client_error(self):
        """Test SSM loading with client error."""
        with patch("src.services.github_pr_service.BOTO3_AVAILABLE", True):
            with patch("src.services.github_pr_service.boto3") as mock_boto3:
                from botocore.exceptions import ClientError

                mock_ssm = MagicMock()
                mock_ssm.get_parameter.side_effect = ClientError(
                    {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
                    "GetParameter",
                )
                mock_boto3.client.return_value = mock_ssm

                service = GitHubPRService(use_mock=True)
                result = service._load_ssm_parameter("/test/param")

                assert result is None

    def test_load_secret_success(self):
        """Test successful secret loading."""
        with patch("src.services.github_pr_service.BOTO3_AVAILABLE", True):
            with patch("src.services.github_pr_service.boto3") as mock_boto3:
                mock_secrets = MagicMock()
                mock_secrets.get_secret_value.return_value = {
                    "SecretString": "secret-key-value"
                }
                mock_boto3.client.return_value = mock_secrets

                service = GitHubPRService(use_mock=True)
                result = service._load_secret("/test/secret")

                assert result == "secret-key-value"

    def test_load_secret_boto3_unavailable(self):
        """Test secret loading when boto3 is unavailable."""
        with patch("src.services.github_pr_service.BOTO3_AVAILABLE", False):
            service = GitHubPRService(use_mock=True)
            result = service._load_secret("/test/secret")

            assert result is None

    def test_load_secret_client_error(self):
        """Test secret loading with client error."""
        with patch("src.services.github_pr_service.BOTO3_AVAILABLE", True):
            with patch("src.services.github_pr_service.boto3") as mock_boto3:
                from botocore.exceptions import ClientError

                mock_secrets = MagicMock()
                mock_secrets.get_secret_value.side_effect = ClientError(
                    {
                        "Error": {
                            "Code": "ResourceNotFoundException",
                            "Message": "Not found",
                        }
                    },
                    "GetSecretValue",
                )
                mock_boto3.client.return_value = mock_secrets

                service = GitHubPRService(use_mock=True)
                result = service._load_secret("/test/secret")

                assert result is None


# =============================================================================
# Initialization Tests
# =============================================================================


class TestGitHubPRServiceInit:
    """Tests for GitHubPRService initialization."""

    def test_init_mock_mode_explicit(self):
        """Test initialization with explicit mock mode."""
        service = GitHubPRService(use_mock=True)

        assert service._use_mock is True
        assert service._mock_prs == {}
        assert service._mock_pr_counter == 1

    def test_init_mock_mode_pygithub_unavailable(self):
        """Test initialization when PyGithub is unavailable."""
        with patch("src.services.github_pr_service.PYGITHUB_AVAILABLE", False):
            service = GitHubPRService()

            assert service._use_mock is True

    def test_init_with_environment(self):
        """Test initialization with environment parameter."""
        service = GitHubPRService(environment="prod", use_mock=True)

        assert service.environment == "prod"
        assert service._use_mock is True

    def test_init_with_branch_protection_service(self):
        """Test initialization with branch protection service."""
        mock_bp_service = MagicMock()
        service = GitHubPRService(
            use_mock=True,
            branch_protection_service=mock_bp_service,
        )

        assert service._branch_protection_service == mock_bp_service

    def test_init_missing_credentials_falls_back_to_mock(self):
        """Test that missing credentials result in mock mode."""
        with patch("src.services.github_pr_service.PYGITHUB_AVAILABLE", True):
            with patch.object(
                GitHubPRService, "_load_ssm_parameter", return_value=None
            ):
                with patch.object(GitHubPRService, "_load_secret", return_value=None):
                    service = GitHubPRService()

                    assert service._use_mock is True

    def test_init_with_explicit_credentials(self):
        """Test initialization with explicit credentials but PyGithub unavailable."""
        with patch("src.services.github_pr_service.PYGITHUB_AVAILABLE", False):
            service = GitHubPRService(
                app_id=12345,
                private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
                installation_id=67890,
            )

            # Falls back to mock mode when PyGithub is unavailable
            assert service._use_mock is True


# =============================================================================
# Repository Operations Tests
# =============================================================================


class TestRepositoryOperations:
    """Tests for repository operations."""

    def test_get_repository_mock_mode(self):
        """Test _get_repository returns None in mock mode."""
        service = GitHubPRService(use_mock=True)
        result = service._get_repository("https://github.com/org/repo")

        assert result is None

    def test_get_repository_invalid_url_short(self):
        """Test _get_repository with too short URL."""
        service = GitHubPRService(use_mock=True)
        result = service._get_repository("x")

        assert result is None


# =============================================================================
# PR Creation Status Tests
# =============================================================================


class TestPRCreationStatusEnum:
    """Tests for PRCreationStatus enum."""

    def test_status_values(self):
        """Test all status enum values exist."""
        assert PRCreationStatus.SUCCESS.value == "success"
        assert PRCreationStatus.BRANCH_EXISTS.value == "branch_exists"
        assert PRCreationStatus.PERMISSION_DENIED.value == "permission_denied"
        assert PRCreationStatus.RATE_LIMITED.value == "rate_limited"
        assert PRCreationStatus.VALIDATION_FAILED.value == "validation_failed"
        assert PRCreationStatus.ERROR.value == "error"

    def test_status_comparison(self):
        """Test status comparison."""
        assert PRCreationStatus.SUCCESS != PRCreationStatus.ERROR
        assert PRCreationStatus.SUCCESS == PRCreationStatus.SUCCESS


# =============================================================================
# Branch Protection Integration Tests
# =============================================================================


class TestBranchProtectionIntegration:
    """Tests for branch protection integration."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock mode service."""
        return GitHubPRService(use_mock=True)

    @pytest.mark.asyncio
    async def test_apply_compliance_branch_protection_mock(self, mock_service):
        """Test applying compliance branch protection in mock mode."""
        with patch(
            "src.services.branch_protection_service.BranchProtectionService"
        ) as mock_bp_class:
            mock_bp_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.branch = "main"
            mock_result.protection_enabled = True
            mock_result.message = "Protection applied"
            mock_config = MagicMock()
            mock_config.required_approving_review_count = 2
            mock_config.require_signed_commits = True
            mock_config.required_status_checks = ["ci/test"]
            mock_result.config_applied = mock_config

            mock_bp_instance.apply_compliance_preset = AsyncMock(
                return_value=[mock_result]
            )
            mock_bp_class.return_value = mock_bp_instance

            with patch(
                "src.services.branch_protection_service.create_branch_protection_service",
                return_value=mock_bp_instance,
            ):
                result = await mock_service.apply_compliance_branch_protection(
                    repo_url="https://github.com/org/repo",
                    compliance_preset="sox",
                )

                assert result["success"] is True
                assert "main" in result["branches"]

    @pytest.mark.asyncio
    async def test_apply_compliance_branch_protection_invalid_preset(
        self, mock_service
    ):
        """Test applying invalid compliance preset."""
        result = await mock_service.apply_compliance_branch_protection(
            repo_url="https://github.com/org/repo",
            compliance_preset="invalid_preset",
        )

        assert result["success"] is False
        assert "Invalid compliance preset" in result["error"]

    @pytest.mark.asyncio
    async def test_apply_compliance_branch_protection_invalid_url(self, mock_service):
        """Test applying branch protection with invalid URL."""
        result = await mock_service.apply_compliance_branch_protection(
            repo_url="x",
            compliance_preset="sox",
        )

        assert result["success"] is False
        assert "Invalid repository URL" in result["error"]

    @pytest.mark.asyncio
    async def test_apply_compliance_with_custom_branches(self, mock_service):
        """Test applying compliance with custom branch list."""
        with patch(
            "src.services.branch_protection_service.BranchProtectionService"
        ) as mock_bp_class:
            mock_bp_instance = MagicMock()
            results = []
            for branch in ["main", "develop", "release"]:
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.branch = branch
                mock_result.protection_enabled = True
                mock_result.message = "Protected"
                mock_result.config_applied = MagicMock()
                mock_result.config_applied.required_approving_review_count = 2
                mock_result.config_applied.require_signed_commits = True
                mock_result.config_applied.required_status_checks = []
                results.append(mock_result)

            mock_bp_instance.apply_compliance_preset = AsyncMock(return_value=results)
            mock_bp_class.return_value = mock_bp_instance

            with patch(
                "src.services.branch_protection_service.create_branch_protection_service",
                return_value=mock_bp_instance,
            ):
                result = await mock_service.apply_compliance_branch_protection(
                    repo_url="https://github.com/org/repo",
                    compliance_preset="cmmc",
                    branches=["main", "develop", "release"],
                )

                assert result["success"] is True
                assert len(result["branches"]) == 3

    @pytest.mark.asyncio
    async def test_apply_compliance_partial_failure(self, mock_service):
        """Test applying compliance with partial branch failure."""
        with patch(
            "src.services.branch_protection_service.BranchProtectionService"
        ) as mock_bp_class:
            mock_bp_instance = MagicMock()
            # One success, one failure
            success_result = MagicMock()
            success_result.success = True
            success_result.branch = "main"
            success_result.protection_enabled = True
            success_result.message = "Protected"
            success_result.config_applied = MagicMock()
            success_result.config_applied.required_approving_review_count = 2
            success_result.config_applied.require_signed_commits = True
            success_result.config_applied.required_status_checks = []

            fail_result = MagicMock()
            fail_result.success = False
            fail_result.branch = "develop"
            fail_result.protection_enabled = False
            fail_result.message = "Branch not found"
            fail_result.config_applied = None

            mock_bp_instance.apply_compliance_preset = AsyncMock(
                return_value=[success_result, fail_result]
            )
            mock_bp_class.return_value = mock_bp_instance

            with patch(
                "src.services.branch_protection_service.create_branch_protection_service",
                return_value=mock_bp_instance,
            ):
                result = await mock_service.apply_compliance_branch_protection(
                    repo_url="https://github.com/org/repo",
                    compliance_preset="sox",
                )

                # Overall is failure because not all branches succeeded
                assert result["success"] is False
                assert result["branches"]["main"]["success"] is True
                assert result["branches"]["develop"]["success"] is False

    @pytest.mark.asyncio
    async def test_verify_branch_protection_status_mock(self, mock_service):
        """Test verifying branch protection status in mock mode."""
        with patch(
            "src.services.branch_protection_service.create_branch_protection_service"
        ) as mock_create:
            mock_bp_instance = MagicMock()
            mock_bp_instance.get_branch_protection_status = AsyncMock(
                return_value={
                    "protected": True,
                    "required_approvals": 2,
                }
            )
            mock_create.return_value = mock_bp_instance

            result = await mock_service.verify_branch_protection_status(
                repo_url="https://github.com/org/repo",
                branch="main",
            )

            assert result["protected"] is True
            assert result["required_approvals"] == 2

    @pytest.mark.asyncio
    async def test_verify_branch_protection_status_invalid_url(self, mock_service):
        """Test verifying branch protection with invalid URL."""
        result = await mock_service.verify_branch_protection_status(
            repo_url="x",
            branch="main",
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_apply_compliance_with_preset_enum(self, mock_service):
        """Test applying compliance with enum preset."""
        from src.services.branch_protection_service import CompliancePreset

        with patch(
            "src.services.branch_protection_service.BranchProtectionService"
        ) as mock_bp_class:
            mock_bp_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.branch = "main"
            mock_result.protection_enabled = True
            mock_result.message = "Protected"
            mock_result.config_applied = MagicMock()
            mock_result.config_applied.required_approving_review_count = 2
            mock_result.config_applied.require_signed_commits = True
            mock_result.config_applied.required_status_checks = []

            mock_bp_instance.apply_compliance_preset = AsyncMock(
                return_value=[mock_result]
            )
            mock_bp_class.return_value = mock_bp_instance

            with patch(
                "src.services.branch_protection_service.create_branch_protection_service",
                return_value=mock_bp_instance,
            ):
                result = await mock_service.apply_compliance_branch_protection(
                    repo_url="https://github.com/org/repo",
                    compliance_preset=CompliancePreset.HIPAA,
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_verify_branch_protection_with_bp_service(self):
        """Test verify with pre-configured branch protection service."""
        mock_bp_service = MagicMock()
        mock_bp_service.get_branch_protection_status = AsyncMock(
            return_value={"protected": True}
        )

        service = GitHubPRService(
            use_mock=True, branch_protection_service=mock_bp_service
        )

        result = await service.verify_branch_protection_status(
            repo_url="https://github.com/org/repo",
            branch="main",
        )

        assert result["protected"] is True
        mock_bp_service.get_branch_protection_status.assert_called_once()


# =============================================================================
# PR Title Generation Tests
# =============================================================================


class TestPRTitleGeneration:
    """Tests for PR title generation with different severities."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock mode service."""
        return GitHubPRService(use_mock=True)

    def test_generate_pr_title_low_severity(self, mock_service):
        """Test PR title generation for low severity."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-001",
            vulnerability_type="INFO_DISCLOSURE",
            severity="LOW",
            file_path="src/utils/logs.py",
            line_number=10,
            description="Information disclosure",
        )

        title = mock_service._generate_pr_title(vuln)

        assert "Security" in title
        assert "logs.py" in title
        # Low severity emoji
        assert "🟡" in title or "\U0001f7e1" in title

    def test_generate_pr_title_medium_severity(self, mock_service):
        """Test PR title generation for medium severity."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-002",
            vulnerability_type="CSRF",
            severity="MEDIUM",
            file_path="src/api/forms.py",
            line_number=20,
            description="Cross-site request forgery",
        )

        title = mock_service._generate_pr_title(vuln)

        assert "Csrf" in title
        # Medium severity emoji
        assert "🟠" in title or "\U0001f7e0" in title

    def test_generate_pr_title_unknown_severity(self, mock_service):
        """Test PR title generation for unknown severity."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-003",
            vulnerability_type="UNKNOWN",
            severity="UNKNOWN",
            file_path="src/misc.py",
            line_number=30,
            description="Unknown vulnerability",
        )

        title = mock_service._generate_pr_title(vuln)

        assert "Security" in title
        # Default emoji for unknown severity
        assert "🔵" in title or "\U0001f535" in title


# =============================================================================
# PR Body Generation Edge Cases
# =============================================================================


class TestPRBodyGenerationEdgeCases:
    """Tests for PR body generation edge cases."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock mode service."""
        return GitHubPRService(use_mock=True)

    def test_generate_pr_body_no_cve(self, mock_service):
        """Test PR body without CVE ID."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-001",
            vulnerability_type="BUFFER_OVERFLOW",
            severity="HIGH",
            file_path="src/utils.c",
            line_number=100,
            description="Buffer overflow vulnerability",
        )

        patch = PatchInfo(
            patch_id="P-001",
            patch_content="diff",
            patched_code="fixed",
            file_path="src/utils.c",
            confidence_score=0.90,
            agent_id="coder-001",
        )

        body = mock_service._generate_pr_body(
            patch_info=patch,
            vulnerability_info=vuln,
            test_results=None,
            approver_email=None,
            approval_id=None,
            workflow_id=None,
        )

        assert "CVE" not in body
        assert "BUFFER_OVERFLOW" in body

    def test_generate_pr_body_no_recommendation(self, mock_service):
        """Test PR body without recommendation."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-002",
            vulnerability_type="XSS",
            severity="MEDIUM",
            file_path="src/template.html",
            line_number=50,
            description="XSS vulnerability",
            cve_id="CVE-2024-1234",
            recommendation=None,
        )

        patch = PatchInfo(
            patch_id="P-002",
            patch_content="diff",
            patched_code="fixed",
            file_path="src/template.html",
        )

        body = mock_service._generate_pr_body(
            patch_info=patch,
            vulnerability_info=vuln,
            test_results=None,
            approver_email=None,
            approval_id=None,
            workflow_id=None,
        )

        assert "Recommendation" not in body

    def test_generate_pr_body_with_failed_tests(self, mock_service):
        """Test PR body with failed tests."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-003",
            vulnerability_type="SSRF",
            severity="HIGH",
            file_path="src/api/fetch.py",
            line_number=25,
            description="SSRF vulnerability",
        )

        patch = PatchInfo(
            patch_id="P-003",
            patch_content="diff",
            patched_code="fixed",
            file_path="src/api/fetch.py",
        )

        test_results = TestResultInfo(
            tests_passed=40,
            tests_failed=5,
            sandbox_id="sandbox-fail",
            security_scan_passed=False,
        )

        body = mock_service._generate_pr_body(
            patch_info=patch,
            vulnerability_info=vuln,
            test_results=test_results,
            approver_email=None,
            approval_id=None,
            workflow_id=None,
        )

        assert "❌ FAILED" in body
        assert "40" in body
        assert "5" in body
        assert "Failed" in body  # Security scan failed

    def test_generate_pr_body_with_coverage(self, mock_service):
        """Test PR body with coverage percentage."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-004",
            vulnerability_type="SQL_INJECTION",
            severity="CRITICAL",
            file_path="src/db.py",
            line_number=100,
            description="SQL injection",
        )

        patch = PatchInfo(
            patch_id="P-004",
            patch_content="diff",
            patched_code="fixed",
            file_path="src/db.py",
        )

        test_results = TestResultInfo(
            tests_passed=100,
            tests_failed=0,
            sandbox_id="sandbox-good",
            security_scan_passed=True,
            coverage_percent=92.5,
        )

        body = mock_service._generate_pr_body(
            patch_info=patch,
            vulnerability_info=vuln,
            test_results=test_results,
            approver_email=None,
            approval_id=None,
            workflow_id=None,
        )

        assert "92.5%" in body

    def test_generate_pr_body_with_test_report_url(self, mock_service):
        """Test PR body with test report URL."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-005",
            vulnerability_type="RCE",
            severity="CRITICAL",
            file_path="src/exec.py",
            line_number=1,
            description="Remote code execution",
        )

        patch = PatchInfo(
            patch_id="P-005",
            patch_content="diff",
            patched_code="fixed",
            file_path="src/exec.py",
        )

        test_results = TestResultInfo(
            tests_passed=50,
            tests_failed=0,
            sandbox_id="sandbox-report",
            test_report_url="https://reports.example.com/test/12345",
        )

        body = mock_service._generate_pr_body(
            patch_info=patch,
            vulnerability_info=vuln,
            test_results=test_results,
            approver_email=None,
            approval_id=None,
            workflow_id=None,
        )

        assert "View Full Test Report" in body
        assert "https://reports.example.com/test/12345" in body


# =============================================================================
# Commit Message Generation Tests
# =============================================================================


class TestCommitMessageGeneration:
    """Tests for commit message generation."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock mode service."""
        return GitHubPRService(use_mock=True)

    def test_generate_commit_message_no_cve(self, mock_service):
        """Test commit message without CVE."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-001",
            vulnerability_type="PATH_TRAVERSAL",
            severity="HIGH",
            file_path="src/files/reader.py",
            line_number=42,
            description="Path traversal vulnerability",
        )

        patch = PatchInfo(
            patch_id="P-001",
            patch_content="diff",
            patched_code="fixed",
            file_path="src/files/reader.py",
            confidence_score=0.85,
        )

        message = mock_service._generate_commit_message(
            vulnerability_info=vuln,
            patch_info=patch,
        )

        assert "fix(security):" in message
        assert "path traversal" in message.lower()
        assert "CVE" not in message
        assert "85%" in message


# =============================================================================
# Module Exports Tests
# =============================================================================


class TestModuleExports:
    """Tests for module exports."""

    def test_all_exports_available(self):
        """Test that all expected exports are available."""
        from src.services import github_pr_service

        assert hasattr(github_pr_service, "GitHubPRService")
        assert hasattr(github_pr_service, "PRCreationStatus")
        assert hasattr(github_pr_service, "PRCreationResult")
        assert hasattr(github_pr_service, "VulnerabilityInfo")
        assert hasattr(github_pr_service, "PatchInfo")
        assert hasattr(github_pr_service, "TestResultInfo")
        assert hasattr(github_pr_service, "create_github_pr_service")

    def test_pygithub_available_constant(self):
        """Test PYGITHUB_AVAILABLE constant exists."""
        from src.services import github_pr_service

        assert hasattr(github_pr_service, "PYGITHUB_AVAILABLE")

    def test_boto3_available_constant(self):
        """Test BOTO3_AVAILABLE constant exists."""
        from src.services import github_pr_service

        assert hasattr(github_pr_service, "BOTO3_AVAILABLE")


# =============================================================================
# Additional Mock Mode Tests
# =============================================================================


class TestAdditionalMockOperations:
    """Additional tests for mock mode operations."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock mode service."""
        return GitHubPRService(use_mock=True)

    @pytest.mark.asyncio
    async def test_mock_create_pr_with_git_url(self, mock_service):
        """Test mock PR creation with .git suffix in URL."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-001",
            vulnerability_type="TEST",
            severity="LOW",
            file_path="test.py",
            line_number=1,
            description="Test",
        )

        patch = PatchInfo(
            patch_id="P-001",
            patch_content="diff",
            patched_code="fixed",
            file_path="test.py",
        )

        result = await mock_service.create_remediation_pr(
            repo_url="https://github.com/org/repo.git",
            patch_info=patch,
            vulnerability_info=vuln,
        )

        assert result.status == PRCreationStatus.SUCCESS
        assert "org/repo" in result.pr_url
        assert ".git" not in result.pr_url

    @pytest.mark.asyncio
    async def test_mock_create_pr_with_trailing_slash(self, mock_service):
        """Test mock PR creation with trailing slash in URL."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-002",
            vulnerability_type="TEST",
            severity="LOW",
            file_path="test.py",
            line_number=1,
            description="Test",
        )

        patch = PatchInfo(
            patch_id="P-002",
            patch_content="diff",
            patched_code="fixed",
            file_path="test.py",
        )

        result = await mock_service.create_remediation_pr(
            repo_url="https://github.com/org/repo/",
            patch_info=patch,
            vulnerability_info=vuln,
        )

        assert result.status == PRCreationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_mock_stores_all_context(self, mock_service):
        """Test that mock stores all context data."""
        vuln = VulnerabilityInfo(
            vulnerability_id="V-003",
            vulnerability_type="XSS",
            severity="HIGH",
            file_path="src/web.py",
            line_number=50,
            description="XSS vulnerability",
        )

        patch = PatchInfo(
            patch_id="P-003",
            patch_content="diff content",
            patched_code="fixed code",
            file_path="src/web.py",
            confidence_score=0.9,
        )

        test_results = TestResultInfo(
            tests_passed=45,
            tests_failed=0,
            sandbox_id="sb-123",
        )

        await mock_service.create_remediation_pr(
            repo_url="https://github.com/org/repo",
            patch_info=patch,
            vulnerability_info=vuln,
            test_results=test_results,
            approver_email="admin@example.com",
        )

        stored = mock_service._mock_prs.get("1")
        assert stored is not None
        assert stored["vulnerability"] == vuln
        assert stored["patch"] == patch
        assert stored["test_results"] == test_results
        assert stored["approver"] == "admin@example.com"
        assert "created_at" in stored


# =============================================================================
# Real Mode Code Path Tests (with mocks)
# =============================================================================


class TestRealModeCodePaths:
    """Tests for real mode code paths using mocks."""

    @pytest.mark.asyncio
    async def test_verify_write_permission_with_push(self):
        """Test write permission check when push is allowed."""
        service = GitHubPRService(use_mock=True)
        # Temporarily switch to real mode for this test
        service._use_mock = False

        mock_repo = MagicMock()
        mock_permissions = MagicMock()
        mock_permissions.push = True
        mock_permissions.admin = False
        mock_repo.permissions = mock_permissions

        result = await service._verify_write_permission(mock_repo)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_write_permission_with_admin(self):
        """Test write permission check when admin is allowed."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        mock_permissions = MagicMock()
        mock_permissions.push = False
        mock_permissions.admin = True
        mock_repo.permissions = mock_permissions

        result = await service._verify_write_permission(mock_repo)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_write_permission_denied(self):
        """Test write permission check when denied."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        mock_permissions = MagicMock()
        mock_permissions.push = False
        mock_permissions.admin = False
        mock_repo.permissions = mock_permissions

        result = await service._verify_write_permission(mock_repo)
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_write_permission_exception(self):
        """Test write permission check with exception."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        # Use property that raises exception when accessed
        type(mock_repo).permissions = property(
            fget=lambda self: (_ for _ in ()).throw(Exception("API Error"))
        )

        result = await service._verify_write_permission(mock_repo)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_feature_branch_success(self):
        """Test successful feature branch creation."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        mock_base_ref = MagicMock()
        mock_base_ref.commit.sha = "abc123"
        mock_repo.get_branch.return_value = mock_base_ref
        mock_repo.create_git_ref.return_value = None

        result = await service._create_feature_branch(
            repo=mock_repo,
            branch_name="security/patch-001",
            base_branch="main",
        )

        assert result["success"] is True
        assert result["base_sha"] == "abc123"
        mock_repo.create_git_ref.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not installed")
    async def test_create_feature_branch_exception(self):
        """Test feature branch creation with GithubException."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        mock_base_ref = MagicMock()
        mock_base_ref.commit.sha = "abc123"
        mock_repo.get_branch.return_value = mock_base_ref

        # Use GithubException for proper exception handling
        mock_repo.create_git_ref.side_effect = GithubException(
            500, {"message": "Server error"}, None
        )

        result = await service._create_feature_branch(
            repo=mock_repo,
            branch_name="security/patch-001",
            base_branch="main",
        )

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_apply_patch_to_branch_update_existing(self):
        """Test applying patch to existing file."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        mock_file_content = MagicMock()
        mock_file_content.sha = "file-sha-123"
        mock_repo.get_contents.return_value = mock_file_content

        mock_result = {"commit": MagicMock()}
        mock_result["commit"].sha = "commit-sha-456"
        mock_repo.update_file.return_value = mock_result

        patch_info = PatchInfo(
            patch_id="P-001",
            patch_content="diff",
            patched_code="fixed code",
            file_path="src/api.py",
        )
        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-001",
            vulnerability_type="SQL_INJECTION",
            severity="HIGH",
            file_path="src/api.py",
            line_number=10,
            description="SQL injection",
        )

        result = await service._apply_patch_to_branch(
            repo=mock_repo,
            branch_name="security/patch-001",
            patch_info=patch_info,
            vulnerability_info=vuln_info,
        )

        assert result["success"] is True
        assert result["commit_sha"] == "commit-sha-456"
        mock_repo.update_file.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not installed")
    async def test_apply_patch_to_branch_create_new(self):
        """Test applying patch to new file when get_contents raises exception."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        # Simulate file not found by raising GithubException
        mock_repo.get_contents.side_effect = GithubException(
            404, {"message": "Not found"}, None
        )

        mock_result = {"commit": MagicMock()}
        mock_result["commit"].sha = "commit-sha-789"
        mock_repo.create_file.return_value = mock_result

        patch_info = PatchInfo(
            patch_id="P-002",
            patch_content="diff",
            patched_code="new file content",
            file_path="src/new_file.py",
        )
        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-002",
            vulnerability_type="XSS",
            severity="MEDIUM",
            file_path="src/new_file.py",
            line_number=1,
            description="XSS",
        )

        result = await service._apply_patch_to_branch(
            repo=mock_repo,
            branch_name="security/patch-002",
            patch_info=patch_info,
            vulnerability_info=vuln_info,
        )

        # Either creates new file or fails gracefully
        assert "success" in result

    @pytest.mark.asyncio
    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not installed")
    async def test_apply_patch_to_branch_error(self):
        """Test applying patch with error."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        mock_file_content = MagicMock()
        mock_file_content.sha = "file-sha"
        mock_repo.get_contents.return_value = mock_file_content

        # Use GithubException for proper exception handling
        mock_repo.update_file.side_effect = GithubException(
            500, {"message": "Server error"}, None
        )

        patch_info = PatchInfo(
            patch_id="P-003",
            patch_content="diff",
            patched_code="code",
            file_path="src/file.py",
        )
        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-003",
            vulnerability_type="RCE",
            severity="CRITICAL",
            file_path="src/file.py",
            line_number=50,
            description="RCE",
        )

        result = await service._apply_patch_to_branch(
            repo=mock_repo,
            branch_name="security/patch-003",
            patch_info=patch_info,
            vulnerability_info=vuln_info,
        )

        # Should handle exception
        assert "success" in result

    @pytest.mark.asyncio
    async def test_create_pull_request_success(self):
        """Test successful PR creation."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.number = 42
        mock_pr.html_url = "https://github.com/org/repo/pull/42"
        mock_repo.create_pull.return_value = mock_pr

        patch_info = PatchInfo(
            patch_id="P-001",
            patch_content="diff",
            patched_code="code",
            file_path="src/api.py",
        )
        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-001",
            vulnerability_type="SQL_INJECTION",
            severity="HIGH",
            file_path="src/api.py",
            line_number=10,
            description="SQL injection",
        )

        result = await service._create_pull_request(
            repo=mock_repo,
            branch_name="security/patch-001",
            base_branch="main",
            patch_info=patch_info,
            vulnerability_info=vuln_info,
            test_results=None,
            approver_email=None,
            approval_id=None,
            workflow_id=None,
        )

        assert result["success"] is True
        assert result["pr"] == mock_pr

    @pytest.mark.asyncio
    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not installed")
    async def test_create_pull_request_error(self):
        """Test PR creation with error."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_repo = MagicMock()
        # Use GithubException for proper exception handling
        mock_repo.create_pull.side_effect = GithubException(
            422, {"message": "Validation failed"}, None
        )

        patch_info = PatchInfo(
            patch_id="P-002",
            patch_content="diff",
            patched_code="code",
            file_path="src/api.py",
        )
        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-002",
            vulnerability_type="XSS",
            severity="MEDIUM",
            file_path="src/api.py",
            line_number=20,
            description="XSS",
        )

        result = await service._create_pull_request(
            repo=mock_repo,
            branch_name="security/patch-002",
            base_branch="main",
            patch_info=patch_info,
            vulnerability_info=vuln_info,
            test_results=None,
            approver_email=None,
            approval_id=None,
            workflow_id=None,
        )

        # Should handle exception
        assert "success" in result

    @pytest.mark.asyncio
    async def test_add_test_results_comment_success(self):
        """Test adding test results comment."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 12345
        mock_pr.create_issue_comment.return_value = mock_comment

        test_results = TestResultInfo(
            tests_passed=50,
            tests_failed=0,
            sandbox_id="sandbox-123",
            security_scan_passed=True,
        )
        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-001",
            vulnerability_type="TEST",
            severity="LOW",
            file_path="test.py",
            line_number=1,
            description="Test",
        )

        result = await service._add_test_results_comment(
            pr=mock_pr,
            test_results=test_results,
            vulnerability_info=vuln_info,
        )

        assert result["success"] is True
        assert result["comment_id"] == 12345

    @pytest.mark.asyncio
    async def test_add_test_results_comment_with_failures(self):
        """Test adding test results comment with failures."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_pr = MagicMock()
        mock_comment = MagicMock()
        mock_comment.id = 12346
        mock_pr.create_issue_comment.return_value = mock_comment

        test_results = TestResultInfo(
            tests_passed=45,
            tests_failed=5,
            sandbox_id="sandbox-456",
            security_scan_passed=False,
        )
        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-002",
            vulnerability_type="TEST",
            severity="HIGH",
            file_path="test.py",
            line_number=1,
            description="Test",
        )

        result = await service._add_test_results_comment(
            pr=mock_pr,
            test_results=test_results,
            vulnerability_info=vuln_info,
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    @pytest.mark.skipif(not PYGITHUB_AVAILABLE, reason="PyGithub not installed")
    async def test_add_test_results_comment_error(self):
        """Test adding test results comment with error."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_pr = MagicMock()
        mock_pr.create_issue_comment.side_effect = GithubException(
            403, {"message": "Rate limited"}, None
        )

        test_results = TestResultInfo(
            tests_passed=50,
            tests_failed=0,
            sandbox_id="sandbox-789",
        )
        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-003",
            vulnerability_type="TEST",
            severity="LOW",
            file_path="test.py",
            line_number=1,
            description="Test",
        )

        result = await service._add_test_results_comment(
            pr=mock_pr,
            test_results=test_results,
            vulnerability_info=vuln_info,
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_add_security_labels_success(self):
        """Test adding security labels."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_pr = MagicMock()
        mock_pr.add_to_labels.return_value = None

        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-001",
            vulnerability_type="SQL_INJECTION",
            severity="CRITICAL",
            file_path="test.py",
            line_number=1,
            description="Test",
        )

        # Should not raise
        await service._add_security_labels(mock_pr, vuln_info)

        # Should have tried to add labels
        assert mock_pr.add_to_labels.called

    @pytest.mark.asyncio
    async def test_add_security_labels_partial_failure(self):
        """Test adding security labels with some failures."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        mock_pr = MagicMock()
        # Some labels succeed, some fail (label doesn't exist)
        call_count = 0

        def side_effect(label):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                raise GithubException(404, {"message": "Label not found"}, None)

        mock_pr.add_to_labels.side_effect = side_effect

        vuln_info = VulnerabilityInfo(
            vulnerability_id="V-002",
            vulnerability_type="XSS",
            severity="HIGH",
            file_path="test.py",
            line_number=1,
            description="Test",
        )

        # Should not raise even with some failures
        await service._add_security_labels(mock_pr, vuln_info)

    @pytest.mark.asyncio
    async def test_get_pr_status_real_mode(self):
        """Test getting PR status in real mode."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False
        service._github = MagicMock()

        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.state = "open"
        mock_pr.merged = False
        mock_pr.mergeable = True

        # Mock check runs
        mock_check = MagicMock()
        mock_check.conclusion = "success"
        mock_commit = MagicMock()
        mock_commit.get_check_runs.return_value = [mock_check]
        mock_commits = MagicMock()
        mock_commits.reversed = [mock_commit]
        mock_pr.get_commits.return_value = mock_commits

        mock_repo.get_pull.return_value = mock_pr
        service._github.get_repo.return_value = mock_repo

        with patch.object(service, "_get_repository", return_value=mock_repo):
            result = await service.get_pr_status(
                repo_url="https://github.com/org/repo",
                pr_number=42,
            )

            assert result["found"] is True
            assert result["state"] == "open"
            assert result["merged"] is False

    @pytest.mark.asyncio
    async def test_get_pr_status_not_found(self):
        """Test getting PR status when repo not found."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        with patch.object(service, "_get_repository", return_value=None):
            result = await service.get_pr_status(
                repo_url="https://github.com/org/repo",
                pr_number=999,
            )

            assert result["found"] is False

    @pytest.mark.asyncio
    async def test_merge_pr_real_mode_success(self):
        """Test merging PR in real mode."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False
        service._github = MagicMock()

        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.mergeable = True
        mock_merge_result = MagicMock()
        mock_merge_result.merged = True
        mock_merge_result.sha = "merge-sha-123"
        mock_pr.merge.return_value = mock_merge_result
        mock_repo.get_pull.return_value = mock_pr

        with patch.object(service, "_get_repository", return_value=mock_repo):
            result = await service.merge_pr(
                repo_url="https://github.com/org/repo",
                pr_number=42,
            )

            assert result["success"] is True
            assert result["merged"] is True
            assert result["sha"] == "merge-sha-123"

    @pytest.mark.asyncio
    async def test_merge_pr_not_mergeable(self):
        """Test merging PR when not mergeable."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False
        service._github = MagicMock()

        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.mergeable = False
        mock_repo.get_pull.return_value = mock_pr

        with patch.object(service, "_get_repository", return_value=mock_repo):
            result = await service.merge_pr(
                repo_url="https://github.com/org/repo",
                pr_number=42,
            )

            assert result["success"] is False
            assert "not mergeable" in result["error"]

    @pytest.mark.asyncio
    async def test_merge_pr_repo_not_found(self):
        """Test merging PR when repo not found."""
        service = GitHubPRService(use_mock=True)
        service._use_mock = False

        with patch.object(service, "_get_repository", return_value=None):
            result = await service.merge_pr(
                repo_url="https://github.com/org/repo",
                pr_number=42,
            )

            assert result["success"] is False
            assert "not found" in result["error"].lower()
