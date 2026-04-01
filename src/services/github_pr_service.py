"""
Project Aura - GitHub Pull Request Service

Provides GitHub App-authenticated PR creation, branch management, and commenting
capabilities for the automated security remediation pipeline.

Features:
1. GitHub App authentication with JWT token generation
2. Feature branch creation and patch application
3. Pull request creation with security context
4. PR commenting for test results and vulnerability details
5. Repository permission verification

Author: Project Aura Team
Created: 2025-12-03
Version: 1.0.0
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

logger = logging.getLogger(__name__)

# Import branch protection types for compliance integration
if TYPE_CHECKING:
    from github.PullRequest import PullRequest
    from github.Repository import Repository

    from src.services.branch_protection_service import (
        BranchProtectionService,
        CompliancePreset,
    )

# GitHub API imports
try:
    from github import Auth, Github, GithubException, GithubIntegration

    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False
    logger.warning("PyGithub not available - using mock mode")

# AWS SDK for credentials
try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("Boto3 not available - credentials must be provided directly")


class PRCreationStatus(Enum):
    """Status of PR creation operation."""

    SUCCESS = "success"
    BRANCH_EXISTS = "branch_exists"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    VALIDATION_FAILED = "validation_failed"
    ERROR = "error"


@dataclass
class PRCreationResult:
    """Result of a PR creation operation."""

    status: PRCreationStatus
    pr_number: int | None = None
    pr_url: str | None = None
    branch_name: str | None = None
    commit_sha: str | None = None
    comment_ids: list[int] = field(default_factory=list)
    error_message: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class VulnerabilityInfo:
    """Vulnerability information for PR context."""

    vulnerability_id: str
    vulnerability_type: str
    severity: str
    file_path: str
    line_number: int
    description: str
    cve_id: str | None = None
    recommendation: str | None = None


@dataclass
class PatchInfo:
    """Patch information for PR creation."""

    patch_id: str
    patch_content: str  # Unified diff format
    patched_code: str  # Full patched file content
    file_path: str
    confidence_score: float = 0.0
    agent_id: str = ""


@dataclass
class TestResultInfo:
    """Test results for PR comment."""

    tests_passed: int = 0
    tests_failed: int = 0
    sandbox_id: str = ""
    test_report_url: str | None = None
    security_scan_passed: bool = True
    coverage_percent: float | None = None


class GitHubPRService:
    """
    GitHub Pull Request Service.

    Provides automated PR creation for security patches using GitHub App authentication.
    Supports branch management, patch application, and PR commenting.

    Usage:
        service = GitHubPRService(
            app_id=12345,
            private_key="-----BEGIN RSA PRIVATE KEY-----...",
            installation_id=67890,
        )

        result = await service.create_remediation_pr(
            repo_url="https://github.com/org/repo",
            patch_info=patch_info,
            vulnerability_info=vuln_info,
            test_results=test_results,
        )

        if result.status == PRCreationStatus.SUCCESS:
            print(f"PR created: {result.pr_url}")
    """

    def __init__(
        self,
        app_id: int | None = None,
        private_key: str | None = None,
        installation_id: int | None = None,
        environment: str = "dev",
        use_mock: bool = False,
        branch_protection_service: "BranchProtectionService | None" = None,
    ):
        """
        Initialize GitHub PR Service.

        Args:
            app_id: GitHub App ID (optional, can load from SSM)
            private_key: GitHub App private key (optional, can load from Secrets Manager)
            installation_id: GitHub App installation ID (optional, can load from SSM)
            environment: Environment name for AWS credential paths
            use_mock: If True, use mock mode without real GitHub API calls
            branch_protection_service: Optional pre-configured branch protection service
        """
        self.environment = environment
        self._use_mock = use_mock or not PYGITHUB_AVAILABLE
        self._branch_protection_service = branch_protection_service

        if self._use_mock:
            logger.info("GitHubPRService initialized in mock mode")
            self._mock_prs: dict[str, dict] = {}
            self._mock_pr_counter = 1
            return

        # Load credentials from AWS if not provided
        self.app_id = app_id or self._load_ssm_parameter(
            f"/aura/{environment}/github/app-id"
        )
        self.installation_id = installation_id or self._load_ssm_parameter(
            f"/aura/{environment}/github/installation-id"
        )
        self.private_key = private_key or self._load_secret(
            f"/aura/{environment}/github/app-private-key"
        )

        if not all([self.app_id, self.installation_id, self.private_key]):
            logger.warning("GitHub App credentials not configured - using mock mode")
            self._use_mock = True
            return

        # Initialize GitHub App authentication
        # app_id and installation_id validated above
        assert self.app_id is not None
        assert self.installation_id is not None
        self._github_integration = GithubIntegration(
            auth=Auth.AppAuth(int(self.app_id), self.private_key)
        )
        self._installation_auth = self._github_integration.get_access_token(
            int(self.installation_id)
        )
        self._github = Github(auth=Auth.Token(self._installation_auth.token))

        logger.info(f"GitHubPRService initialized with GitHub App ID: {self.app_id}")

    def _load_ssm_parameter(self, parameter_name: str) -> str | None:
        """Load parameter from AWS SSM Parameter Store."""
        if not BOTO3_AVAILABLE:
            return None

        try:
            ssm = boto3.client("ssm")
            response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
            return cast(str, response["Parameter"]["Value"])
        except ClientError as e:
            logger.warning(f"Failed to load SSM parameter {parameter_name}: {e}")
            return None

    def _load_secret(self, secret_name: str) -> str | None:
        """Load secret from AWS Secrets Manager."""
        if not BOTO3_AVAILABLE:
            return None

        try:
            secrets = boto3.client("secretsmanager")
            response = secrets.get_secret_value(SecretId=secret_name)
            return cast(str, response["SecretString"])
        except ClientError as e:
            logger.warning(f"Failed to load secret {secret_name}: {e}")
            return None

    def _get_repository(self, repo_url: str) -> "Repository | None":
        """Get repository object from URL."""
        if self._use_mock:
            return None

        # Parse repo URL to get owner/repo
        # Supports: https://github.com/owner/repo or https://github.com/owner/repo.git
        repo_url = repo_url.rstrip("/").rstrip(".git")
        parts = repo_url.split("/")
        if len(parts) < 2:
            logger.error(f"Invalid repository URL: {repo_url}")
            return None

        owner = parts[-2]
        repo_name = parts[-1]

        try:
            return self._github.get_repo(f"{owner}/{repo_name}")
        except GithubException as e:
            logger.error(f"Failed to get repository {owner}/{repo_name}: {e}")
            return None

    async def create_remediation_pr(
        self,
        repo_url: str,
        patch_info: PatchInfo,
        vulnerability_info: VulnerabilityInfo,
        test_results: TestResultInfo | None = None,
        base_branch: str = "main",
        approver_email: str | None = None,
        approval_id: str | None = None,
        workflow_id: str | None = None,
    ) -> PRCreationResult:
        """
        Create a remediation PR for an approved security patch.

        Args:
            repo_url: Repository URL (https://github.com/owner/repo)
            patch_info: Information about the patch to apply
            vulnerability_info: Details about the vulnerability being fixed
            test_results: Optional sandbox test results
            base_branch: Branch to create PR against (default: main)
            approver_email: Email of the human approver
            approval_id: HITL approval ID for audit trail
            workflow_id: Patch validation workflow ID

        Returns:
            PRCreationResult with PR details or error information
        """
        branch_name = f"security/{patch_info.patch_id}"

        logger.info(
            f"Creating remediation PR for {vulnerability_info.vulnerability_type} "
            f"in {vulnerability_info.file_path}"
        )

        if self._use_mock:
            return await self._mock_create_pr(
                repo_url=repo_url,
                patch_info=patch_info,
                vulnerability_info=vulnerability_info,
                test_results=test_results,
                base_branch=base_branch,
                branch_name=branch_name,
                approver_email=approver_email,
                approval_id=approval_id,
                workflow_id=workflow_id,
            )

        try:
            repo = self._get_repository(repo_url)
            if not repo:
                return PRCreationResult(
                    status=PRCreationStatus.ERROR,
                    error_message=f"Repository not found: {repo_url}",
                )

            # Check permissions
            if not await self._verify_write_permission(repo):
                return PRCreationResult(
                    status=PRCreationStatus.PERMISSION_DENIED,
                    error_message="GitHub App lacks write permission for this repository",
                )

            # Create feature branch
            branch_result = await self._create_feature_branch(
                repo=repo,
                branch_name=branch_name,
                base_branch=base_branch,
            )
            if not branch_result["success"]:
                return PRCreationResult(
                    status=(
                        PRCreationStatus.BRANCH_EXISTS
                        if "already exists" in branch_result.get("error", "")
                        else PRCreationStatus.ERROR
                    ),
                    branch_name=branch_name,
                    error_message=branch_result.get("error"),
                )

            # Apply patch to branch
            commit_result = await self._apply_patch_to_branch(
                repo=repo,
                branch_name=branch_name,
                patch_info=patch_info,
                vulnerability_info=vulnerability_info,
            )
            if not commit_result["success"]:
                return PRCreationResult(
                    status=PRCreationStatus.ERROR,
                    branch_name=branch_name,
                    error_message=commit_result.get("error"),
                )

            # Create pull request
            pr_result = await self._create_pull_request(
                repo=repo,
                branch_name=branch_name,
                base_branch=base_branch,
                patch_info=patch_info,
                vulnerability_info=vulnerability_info,
                test_results=test_results,
                approver_email=approver_email,
                approval_id=approval_id,
                workflow_id=workflow_id,
            )
            if not pr_result["success"]:
                return PRCreationResult(
                    status=PRCreationStatus.ERROR,
                    branch_name=branch_name,
                    commit_sha=commit_result.get("commit_sha"),
                    error_message=pr_result.get("error"),
                )

            pr: "PullRequest" = pr_result["pr"]

            # Add detailed comment with test results
            comment_ids = []
            if test_results:
                comment_result = await self._add_test_results_comment(
                    pr=pr,
                    test_results=test_results,
                    vulnerability_info=vulnerability_info,
                )
                if comment_result.get("comment_id"):
                    comment_ids.append(comment_result["comment_id"])

            # Add security labels
            await self._add_security_labels(pr, vulnerability_info)

            logger.info(f"Successfully created PR #{pr.number}: {pr.html_url}")

            return PRCreationResult(
                status=PRCreationStatus.SUCCESS,
                pr_number=pr.number,
                pr_url=pr.html_url,
                branch_name=branch_name,
                commit_sha=commit_result.get("commit_sha"),
                comment_ids=comment_ids,
            )

        except GithubException as e:
            if e.status == 403 and "rate limit" in str(e).lower():
                logger.warning(f"GitHub rate limit exceeded: {e}")
                return PRCreationResult(
                    status=PRCreationStatus.RATE_LIMITED,
                    error_message=str(e),
                )
            logger.error(f"GitHub API error creating PR: {e}")
            return PRCreationResult(
                status=PRCreationStatus.ERROR,
                error_message=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error creating PR: {e}")
            return PRCreationResult(
                status=PRCreationStatus.ERROR,
                error_message=str(e),
            )

    async def _verify_write_permission(self, repo: "Repository") -> bool:
        """Verify the GitHub App has write permission to the repository."""
        try:
            permissions = repo.permissions
            return bool(permissions.push or permissions.admin)
        except Exception as e:
            logger.warning(f"Could not verify permissions: {e}")
            return False

    async def _create_feature_branch(
        self,
        repo: "Repository",
        branch_name: str,
        base_branch: str,
    ) -> dict[str, Any]:
        """Create a feature branch from the base branch."""
        try:
            # Get the SHA of the base branch
            base_ref = repo.get_branch(base_branch)
            base_sha = base_ref.commit.sha

            # Create the new branch
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)

            logger.debug(
                f"Created branch {branch_name} from {base_branch} at {base_sha}"
            )
            return {"success": True, "base_sha": base_sha}

        except GithubException as e:
            if e.status == 422 and "Reference already exists" in str(e):
                return {
                    "success": False,
                    "error": f"Branch {branch_name} already exists",
                }
            return {"success": False, "error": str(e)}

    async def _apply_patch_to_branch(
        self,
        repo: "Repository",
        branch_name: str,
        patch_info: PatchInfo,
        vulnerability_info: VulnerabilityInfo,
    ) -> dict[str, Any]:
        """Apply the patch content to a file in the branch."""
        try:
            # Get current file content (if exists)
            try:
                file_content = repo.get_contents(patch_info.file_path, ref=branch_name)
                # Handle potential list return (directories), we expect a single file
                if isinstance(file_content, list):
                    file_sha = None
                else:
                    file_sha = file_content.sha
            except GithubException:
                # File doesn't exist - this would be unusual for a patch
                file_sha = None

            # Commit message following conventional commits
            commit_message = self._generate_commit_message(
                vulnerability_info=vulnerability_info,
                patch_info=patch_info,
            )

            # Update or create the file with patched content
            if file_sha:
                result = repo.update_file(
                    path=patch_info.file_path,
                    message=commit_message,
                    content=patch_info.patched_code,
                    sha=file_sha,
                    branch=branch_name,
                )
            else:
                result = repo.create_file(
                    path=patch_info.file_path,
                    message=commit_message,
                    content=patch_info.patched_code,
                    branch=branch_name,
                )

            logger.debug(
                f"Applied patch to {patch_info.file_path} in branch {branch_name}"
            )
            return {"success": True, "commit_sha": result["commit"].sha}

        except GithubException as e:
            return {"success": False, "error": str(e)}

    def _generate_commit_message(
        self,
        vulnerability_info: VulnerabilityInfo,
        patch_info: PatchInfo,
    ) -> str:
        """Generate a conventional commit message for the security fix."""
        vuln_type = vulnerability_info.vulnerability_type.lower().replace("_", " ")
        file_name = Path(vulnerability_info.file_path).name

        message = f"fix(security): remediate {vuln_type} in {file_name}\n\n"
        message += f"Vulnerability: {vulnerability_info.vulnerability_id}\n"
        message += f"Severity: {vulnerability_info.severity}\n"
        message += (
            f"File: {vulnerability_info.file_path}:{vulnerability_info.line_number}\n"
        )

        if vulnerability_info.cve_id:
            message += f"CVE: {vulnerability_info.cve_id}\n"

        message += f"\n{vulnerability_info.description}\n"
        message += f"\nPatch ID: {patch_info.patch_id}\n"
        message += f"Confidence: {patch_info.confidence_score:.0%}\n"

        return message

    async def _create_pull_request(
        self,
        repo: "Repository",
        branch_name: str,
        base_branch: str,
        patch_info: PatchInfo,
        vulnerability_info: VulnerabilityInfo,
        test_results: TestResultInfo | None,
        approver_email: str | None,
        approval_id: str | None,
        workflow_id: str | None,
    ) -> dict[str, Any]:
        """Create the pull request with security context."""
        try:
            title = self._generate_pr_title(vulnerability_info)
            body = self._generate_pr_body(
                patch_info=patch_info,
                vulnerability_info=vulnerability_info,
                test_results=test_results,
                approver_email=approver_email,
                approval_id=approval_id,
                workflow_id=workflow_id,
            )

            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch,
            )

            return {"success": True, "pr": pr}

        except GithubException as e:
            return {"success": False, "error": str(e)}

    def _generate_pr_title(self, vulnerability_info: VulnerabilityInfo) -> str:
        """Generate PR title from vulnerability info."""
        vuln_type = vulnerability_info.vulnerability_type.replace("_", " ").title()
        file_name = Path(vulnerability_info.file_path).name
        severity_emoji = {
            "CRITICAL": "\U0001f6a8",  # 🚨
            "HIGH": "\U0001f534",  # 🔴
            "MEDIUM": "\U0001f7e0",  # 🟠
            "LOW": "\U0001f7e1",  # 🟡
        }.get(
            vulnerability_info.severity.upper(), "\U0001f535"
        )  # 🔵

        return f"{severity_emoji} Security: Fix {vuln_type} in {file_name}"

    def _generate_pr_body(
        self,
        patch_info: PatchInfo,
        vulnerability_info: VulnerabilityInfo,
        test_results: TestResultInfo | None,
        approver_email: str | None,
        approval_id: str | None,
        workflow_id: str | None,
    ) -> str:
        """Generate comprehensive PR body with security context."""
        body = "## Security Patch\n\n"
        body += "This PR contains an automated security fix generated and validated by Project Aura.\n\n"

        # Vulnerability section
        body += "### Vulnerability Details\n\n"
        body += "| Property | Value |\n"
        body += "|----------|-------|\n"
        body += f"| **ID** | `{vulnerability_info.vulnerability_id}` |\n"
        body += f"| **Type** | {vulnerability_info.vulnerability_type} |\n"
        body += f"| **Severity** | **{vulnerability_info.severity}** |\n"
        body += f"| **Location** | `{vulnerability_info.file_path}:{vulnerability_info.line_number}` |\n"
        if vulnerability_info.cve_id:
            body += f"| **CVE** | [{vulnerability_info.cve_id}](https://nvd.nist.gov/vuln/detail/{vulnerability_info.cve_id}) |\n"
        body += "\n"

        body += f"**Description:** {vulnerability_info.description}\n\n"

        if vulnerability_info.recommendation:
            body += f"**Recommendation:** {vulnerability_info.recommendation}\n\n"

        # Patch section
        body += "### Patch Information\n\n"
        body += "| Property | Value |\n"
        body += "|----------|-------|\n"
        body += f"| **Patch ID** | `{patch_info.patch_id}` |\n"
        body += f"| **Confidence** | {patch_info.confidence_score:.0%} |\n"
        body += f"| **Agent** | `{patch_info.agent_id}` |\n"
        body += "\n"

        # Test results section
        if test_results:
            body += "### Sandbox Testing Results\n\n"
            test_status = (
                "\u2705 PASSED" if test_results.tests_failed == 0 else "\u274c FAILED"
            )
            body += f"**Status:** {test_status}\n\n"
            body += "| Metric | Value |\n"
            body += "|--------|-------|\n"
            body += f"| Tests Passed | {test_results.tests_passed} |\n"
            body += f"| Tests Failed | {test_results.tests_failed} |\n"
            body += f"| Sandbox ID | `{test_results.sandbox_id}` |\n"
            body += f"| Security Scan | {'Passed' if test_results.security_scan_passed else 'Failed'} |\n"
            if test_results.coverage_percent is not None:
                body += f"| Coverage | {test_results.coverage_percent:.1f}% |\n"
            body += "\n"

            if test_results.test_report_url:
                body += f"[View Full Test Report]({test_results.test_report_url})\n\n"

        # Approval section
        body += "### HITL Approval\n\n"
        if approver_email:
            body += f"**Approved by:** {approver_email}\n"
        if approval_id:
            body += f"**Approval ID:** `{approval_id}`\n"
        if workflow_id:
            body += f"**Workflow ID:** `{workflow_id}`\n"
        body += "\n"

        # Footer
        body += "---\n\n"
        body += "*This PR was automatically generated by [Project Aura](https://github.com/aenealabs/aura) "
        body += "as part of the autonomous security remediation pipeline.*\n"

        return body

    async def _add_test_results_comment(
        self,
        pr: "PullRequest",
        test_results: TestResultInfo,
        vulnerability_info: VulnerabilityInfo,
    ) -> dict[str, Any]:
        """Add a detailed comment with test results and security context."""
        try:
            comment_body = "## Automated Security Testing Results\n\n"

            # Summary
            total_tests = test_results.tests_passed + test_results.tests_failed
            pass_rate = (
                test_results.tests_passed / total_tests * 100 if total_tests > 0 else 0
            )

            if test_results.tests_failed == 0:
                comment_body += (
                    "\u2705 **All tests passed!** This patch is ready for review.\n\n"
                )
            else:
                comment_body += f"\u26a0\ufe0f **{test_results.tests_failed} test(s) failed.** Please review carefully.\n\n"

            # Test breakdown
            comment_body += "### Test Summary\n\n"
            comment_body += f"- **Total Tests:** {total_tests}\n"
            comment_body += f"- **Passed:** {test_results.tests_passed} \u2705\n"
            comment_body += f"- **Failed:** {test_results.tests_failed} \u274c\n"
            comment_body += f"- **Pass Rate:** {pass_rate:.1f}%\n\n"

            # Security scan
            comment_body += "### Security Scan\n\n"
            if test_results.security_scan_passed:
                comment_body += (
                    "\u2705 Security scan passed - no new vulnerabilities introduced.\n"
                )
            else:
                comment_body += (
                    "\u274c Security scan found issues - manual review required.\n"
                )

            # Sandbox details
            comment_body += "\n### Sandbox Environment\n\n"
            comment_body += f"- **Sandbox ID:** `{test_results.sandbox_id}`\n"
            comment_body += "- **Network Isolation:** Enabled (no external access)\n"
            comment_body += "- **Resource Limits:** Standard (2 CPU, 4GB RAM)\n"

            comment = pr.create_issue_comment(body=comment_body)
            return {"success": True, "comment_id": comment.id}

        except GithubException as e:
            logger.warning(f"Failed to add test results comment: {e}")
            return {"success": False, "error": str(e)}

    async def _add_security_labels(
        self,
        pr: "PullRequest",
        vulnerability_info: VulnerabilityInfo,
    ) -> None:
        """Add security-related labels to the PR."""
        try:
            labels = ["security", "automated"]

            # Add severity label
            severity_labels = {
                "CRITICAL": "severity:critical",
                "HIGH": "severity:high",
                "MEDIUM": "severity:medium",
                "LOW": "severity:low",
            }
            if vulnerability_info.severity.upper() in severity_labels:
                labels.append(severity_labels[vulnerability_info.severity.upper()])

            # Add vulnerability type label
            vuln_type_label = f"vuln:{vulnerability_info.vulnerability_type.lower()}"
            labels.append(vuln_type_label)

            # Try to add labels (may fail if labels don't exist in repo)
            for label in labels:
                try:
                    pr.add_to_labels(label)
                except GithubException:
                    # Label doesn't exist in repo - that's okay
                    pass

        except Exception as e:
            logger.debug(f"Could not add labels: {e}")

    async def _mock_create_pr(
        self,
        repo_url: str,
        patch_info: PatchInfo,
        vulnerability_info: VulnerabilityInfo,
        test_results: TestResultInfo | None,
        base_branch: str,
        branch_name: str,
        approver_email: str | None,
        approval_id: str | None,
        workflow_id: str | None,
    ) -> PRCreationResult:
        """Create a mock PR for testing without GitHub API."""
        pr_number = self._mock_pr_counter
        self._mock_pr_counter += 1

        # Parse repo URL for mock URL construction
        repo_path = repo_url.rstrip("/").rstrip(".git").split("github.com/")[-1]
        pr_url = f"https://github.com/{repo_path}/pull/{pr_number}"
        commit_sha = hashlib.sha1(
            f"{patch_info.patch_id}-{time.time()}".encode(),
            usedforsecurity=False,
        ).hexdigest()[:40]

        # Store mock PR data
        self._mock_prs[str(pr_number)] = {
            "number": pr_number,
            "url": pr_url,
            "branch": branch_name,
            "commit_sha": commit_sha,
            "vulnerability": vulnerability_info,
            "patch": patch_info,
            "test_results": test_results,
            "approver": approver_email,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"[MOCK] Created PR #{pr_number}: {pr_url}")

        return PRCreationResult(
            status=PRCreationStatus.SUCCESS,
            pr_number=pr_number,
            pr_url=pr_url,
            branch_name=branch_name,
            commit_sha=commit_sha,
            comment_ids=[1001],  # Mock comment ID
        )

    async def get_pr_status(self, repo_url: str, pr_number: int) -> dict[str, Any]:
        """Get the current status of a pull request."""
        if self._use_mock:
            mock_pr = self._mock_prs.get(str(pr_number))
            if mock_pr:
                return {
                    "found": True,
                    "state": "open",
                    "merged": False,
                    "mergeable": True,
                    "checks_passed": True,
                }
            return {"found": False}

        try:
            repo = self._get_repository(repo_url)
            if not repo:
                return {"found": False, "error": "Repository not found"}

            pr = repo.get_pull(pr_number)
            return {
                "found": True,
                "state": pr.state,
                "merged": pr.merged,
                "mergeable": pr.mergeable,
                "checks_passed": all(
                    check.conclusion == "success"
                    for check in pr.get_commits().reversed[0].get_check_runs()
                ),
            }

        except GithubException as e:
            return {"found": False, "error": str(e)}

    async def merge_pr(
        self,
        repo_url: str,
        pr_number: int,
        merge_method: str = "squash",
    ) -> dict[str, Any]:
        """Merge a pull request (typically after CI passes)."""
        if self._use_mock:
            mock_pr = self._mock_prs.get(str(pr_number))
            if mock_pr:
                mock_pr["merged"] = True
                mock_pr["state"] = "closed"
                logger.info(f"[MOCK] Merged PR #{pr_number}")
                return {"success": True, "merged": True}
            return {"success": False, "error": "PR not found"}

        try:
            repo = self._get_repository(repo_url)
            if not repo:
                return {"success": False, "error": "Repository not found"}

            pr = repo.get_pull(pr_number)

            if not pr.mergeable:
                return {"success": False, "error": "PR is not mergeable"}

            result = pr.merge(merge_method=merge_method)
            return {"success": True, "merged": result.merged, "sha": result.sha}

        except GithubException as e:
            return {"success": False, "error": str(e)}

    async def apply_compliance_branch_protection(
        self,
        repo_url: str,
        compliance_preset: "str | CompliancePreset",
        branches: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Apply compliance-based branch protection rules to a repository.

        This method enables compliance-focused users to enforce branch protection
        when running in FULL_AUTONOMOUS mode with automated PR creation/merging.

        Args:
            repo_url: Repository URL (https://github.com/owner/repo)
            compliance_preset: Compliance standard to apply (SOX, CMMC, HIPAA, PCI_DSS, etc.)
            branches: List of branches to protect (defaults to ["main", "develop"])

        Returns:
            Dictionary with operation results for each branch
        """
        # Lazy import to avoid circular dependencies
        from src.services.branch_protection_service import (
            BranchProtectionService,
            CompliancePreset,
            create_branch_protection_service,
        )

        # Use provided service or create one
        if self._branch_protection_service:
            bp_service = self._branch_protection_service
        else:
            # Create service sharing our GitHub credentials if available
            if self._use_mock:
                bp_service = create_branch_protection_service(use_mock=True)
            else:
                bp_service = BranchProtectionService(
                    github_client=self._github,
                    use_mock=False,
                )

        # Convert string preset to enum if needed
        if isinstance(compliance_preset, str):
            try:
                preset = CompliancePreset(compliance_preset.lower())
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid compliance preset: {compliance_preset}. "
                    f"Valid options: {[p.value for p in CompliancePreset]}",
                }
        else:
            preset = compliance_preset

        # Parse repo URL to get owner/repo format
        repo_url = repo_url.rstrip("/").rstrip(".git")
        parts = repo_url.split("/")
        if len(parts) < 2:
            return {"success": False, "error": f"Invalid repository URL: {repo_url}"}
        repo_full_name = f"{parts[-2]}/{parts[-1]}"

        # Apply protection to branches
        results = await bp_service.apply_compliance_preset(
            repo_full_name=repo_full_name,
            preset=preset,
            branches=branches or ["main", "develop"],
        )

        # Build response
        branch_results = {}
        all_success = True
        for result in results:
            branch_results[result.branch] = {
                "success": result.success,
                "protected": result.protection_enabled,
                "message": result.message,
                "config": {
                    "required_approvals": (
                        result.config_applied.required_approving_review_count
                        if result.config_applied
                        else None
                    ),
                    "require_signed_commits": (
                        result.config_applied.require_signed_commits
                        if result.config_applied
                        else None
                    ),
                    "status_checks": (
                        result.config_applied.required_status_checks
                        if result.config_applied
                        else None
                    ),
                },
            }
            if not result.success:
                all_success = False

        logger.info(
            f"Applied {preset.value} compliance protection to {repo_full_name}: "
            f"{sum(1 for r in results if r.success)}/{len(results)} branches protected"
        )

        return {
            "success": all_success,
            "preset": preset.value,
            "repository": repo_full_name,
            "branches": branch_results,
        }

    async def verify_branch_protection_status(
        self,
        repo_url: str,
        branch: str = "main",
    ) -> dict[str, Any]:
        """
        Check if branch protection is enabled and its current configuration.

        Useful for verifying compliance requirements before autonomous operations.

        Args:
            repo_url: Repository URL
            branch: Branch name to check (default: main)

        Returns:
            Dictionary with protection status and configuration
        """
        from src.services.branch_protection_service import (
            BranchProtectionService,
            create_branch_protection_service,
        )

        # Use provided service or create one
        if self._branch_protection_service:
            bp_service = self._branch_protection_service
        else:
            if self._use_mock:
                bp_service = create_branch_protection_service(use_mock=True)
            else:
                bp_service = BranchProtectionService(
                    github_client=self._github,
                    use_mock=False,
                )

        # Parse repo URL
        repo_url = repo_url.rstrip("/").rstrip(".git")
        parts = repo_url.split("/")
        if len(parts) < 2:
            return {"error": f"Invalid repository URL: {repo_url}"}
        repo_full_name = f"{parts[-2]}/{parts[-1]}"

        return await bp_service.get_branch_protection_status(repo_full_name, branch)


# Factory function for service creation
def create_github_pr_service(
    environment: str = "dev",
    use_mock: bool = False,
) -> GitHubPRService:
    """
    Create a GitHubPRService with AWS credential loading.

    Args:
        environment: Environment name (dev, qa, prod)
        use_mock: Force mock mode for testing

    Returns:
        Configured GitHubPRService instance
    """
    return GitHubPRService(environment=environment, use_mock=use_mock)
