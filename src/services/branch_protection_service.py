"""
Project Aura - Branch Protection Service

Provides GitHub branch protection management for compliance and security requirements.
Enables platform users to enforce branch protection rules when using FULL_AUTONOMOUS mode.

Features:
1. Enable/disable branch protection rules via GitHub API
2. Require pull request reviews before merging
3. Require status checks to pass
4. Restrict direct pushes to protected branches
5. Configure bypass permissions for emergency scenarios
6. Compliance presets (SOX, CMMC, HIPAA, PCI-DSS)

Author: Project Aura Team
Created: 2025-12-04
Version: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# GitHub API imports
try:
    from github import Github, GithubException
    from github.Branch import Branch
    from github.Repository import Repository

    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False
    Github = None  # type: ignore
    GithubException = Exception  # type: ignore
    Branch = None  # type: ignore
    Repository = None  # type: ignore
    logger.warning("PyGithub not available - branch protection requires PyGithub")


class CompliancePreset(Enum):
    """Predefined compliance configurations for branch protection."""

    # Minimal protection - just require PRs
    MINIMAL = "minimal"

    # Standard enterprise protection
    ENTERPRISE_STANDARD = "enterprise_standard"

    # SOX compliance (financial services)
    SOX = "sox"

    # CMMC Level 2+ (defense contractors)
    CMMC = "cmmc"

    # HIPAA (healthcare)
    HIPAA = "hipaa"

    # PCI-DSS (payment card industry)
    PCI_DSS = "pci_dss"

    # Maximum security (all protections enabled)
    MAXIMUM = "maximum"


@dataclass
class StatusCheckConfig:
    """Configuration for required status checks."""

    check_name: str
    app_id: int | None = None  # If None, any app can report this check


@dataclass
class BranchProtectionConfig:
    """Configuration for branch protection rules."""

    # Basic settings
    branch_pattern: str = "main"
    enabled: bool = True

    # Pull request requirements
    require_pull_request: bool = True
    required_approving_review_count: int = 1
    dismiss_stale_reviews: bool = True
    require_code_owner_reviews: bool = False
    require_last_push_approval: bool = False

    # Status check requirements
    require_status_checks: bool = True
    strict_status_checks: bool = True  # Require branch to be up to date
    required_status_checks: list[str] = field(
        default_factory=lambda: ["Code Quality Checks"]
    )

    # Push restrictions
    restrict_pushes: bool = True
    allow_force_pushes: bool = False
    allow_deletions: bool = False

    # Bypass permissions (for emergency scenarios)
    bypass_actors: list[str] = field(
        default_factory=list
    )  # GitHub usernames or app slugs

    # Enforcement
    enforce_admins: bool = True  # Apply rules to admins too
    lock_branch: bool = False  # Completely lock the branch

    # Conversation requirements
    require_conversation_resolution: bool = True

    # Commit signing
    require_signed_commits: bool = False

    # Linear history
    require_linear_history: bool = False

    @classmethod
    def from_compliance_preset(
        cls, preset: CompliancePreset, branch: str = "main"
    ) -> "BranchProtectionConfig":
        """Create configuration from a compliance preset."""
        base_config = cls(branch_pattern=branch)

        if preset == CompliancePreset.MINIMAL:
            return cls(
                branch_pattern=branch,
                require_pull_request=True,
                required_approving_review_count=1,
                require_status_checks=False,
                restrict_pushes=False,
                enforce_admins=False,
            )

        elif preset == CompliancePreset.ENTERPRISE_STANDARD:
            return cls(
                branch_pattern=branch,
                require_pull_request=True,
                required_approving_review_count=1,
                dismiss_stale_reviews=True,
                require_status_checks=True,
                required_status_checks=["Code Quality Checks"],
                restrict_pushes=True,
                enforce_admins=True,
            )

        elif preset == CompliancePreset.SOX:
            # SOX requires separation of duties, audit trails
            return cls(
                branch_pattern=branch,
                require_pull_request=True,
                required_approving_review_count=2,  # Dual approval
                dismiss_stale_reviews=True,
                require_code_owner_reviews=True,
                require_last_push_approval=True,
                require_status_checks=True,
                strict_status_checks=True,
                required_status_checks=[
                    "Code Quality Checks",
                    "Aura Security Review",
                ],
                restrict_pushes=True,
                allow_force_pushes=False,
                allow_deletions=False,
                enforce_admins=True,
                require_conversation_resolution=True,
                require_signed_commits=True,
            )

        elif preset == CompliancePreset.CMMC:
            # CMMC requires strict access control, audit logging
            return cls(
                branch_pattern=branch,
                require_pull_request=True,
                required_approving_review_count=2,
                dismiss_stale_reviews=True,
                require_code_owner_reviews=True,
                require_last_push_approval=True,
                require_status_checks=True,
                strict_status_checks=True,
                required_status_checks=[
                    "Code Quality Checks",
                    "Aura Security Review",
                ],
                restrict_pushes=True,
                allow_force_pushes=False,
                allow_deletions=False,
                enforce_admins=True,
                require_conversation_resolution=True,
                require_signed_commits=True,
                require_linear_history=True,  # Clean audit trail
            )

        elif preset == CompliancePreset.HIPAA:
            # HIPAA requires access controls, audit trails
            return cls(
                branch_pattern=branch,
                require_pull_request=True,
                required_approving_review_count=2,
                dismiss_stale_reviews=True,
                require_code_owner_reviews=True,
                require_status_checks=True,
                strict_status_checks=True,
                required_status_checks=[
                    "Code Quality Checks",
                    "Aura Security Review",
                ],
                restrict_pushes=True,
                allow_force_pushes=False,
                enforce_admins=True,
                require_conversation_resolution=True,
            )

        elif preset == CompliancePreset.PCI_DSS:
            # PCI-DSS requires change control, code review
            return cls(
                branch_pattern=branch,
                require_pull_request=True,
                required_approving_review_count=2,
                dismiss_stale_reviews=True,
                require_code_owner_reviews=True,
                require_last_push_approval=True,
                require_status_checks=True,
                strict_status_checks=True,
                required_status_checks=[
                    "Code Quality Checks",
                    "Aura Security Review",
                ],
                restrict_pushes=True,
                allow_force_pushes=False,
                allow_deletions=False,
                enforce_admins=True,
                require_conversation_resolution=True,
                require_signed_commits=True,
            )

        elif preset == CompliancePreset.MAXIMUM:
            # All protections enabled
            return cls(
                branch_pattern=branch,
                require_pull_request=True,
                required_approving_review_count=2,
                dismiss_stale_reviews=True,
                require_code_owner_reviews=True,
                require_last_push_approval=True,
                require_status_checks=True,
                strict_status_checks=True,
                required_status_checks=[
                    "Code Quality Checks",
                    "Aura Security Review",
                ],
                restrict_pushes=True,
                allow_force_pushes=False,
                allow_deletions=False,
                enforce_admins=True,
                lock_branch=False,  # Don't completely lock
                require_conversation_resolution=True,
                require_signed_commits=True,
                require_linear_history=True,
            )

        return base_config  # type: ignore[unreachable]


@dataclass
class BranchProtectionResult:
    """Result of a branch protection operation."""

    success: bool
    branch: str
    protection_enabled: bool
    message: str
    config_applied: BranchProtectionConfig | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


class BranchProtectionService:
    """
    Service for managing GitHub branch protection rules.

    Integrates with the Aura platform to enable compliance-focused
    branch protection for users with strict security requirements.
    """

    def __init__(
        self,
        github_token: str | None = None,
        github_client: "Github | None" = None,
        use_mock: bool = False,
    ):
        """
        Initialize the branch protection service.

        Args:
            github_token: GitHub personal access token or app token
            github_client: Pre-configured PyGithub client
            use_mock: Enable mock mode for testing
        """
        self.use_mock = use_mock or not PYGITHUB_AVAILABLE

        if self.use_mock:
            self._github = None
            logger.info("BranchProtectionService initialized in mock mode")
        elif github_client:
            self._github = github_client
            logger.info("BranchProtectionService initialized with provided client")
        elif github_token:
            self._github = Github(github_token)
            logger.info("BranchProtectionService initialized with token")
        else:
            self._github = None
            self.use_mock = True
            logger.warning("No GitHub credentials provided - using mock mode")

    def _get_repository(self, repo_full_name: str) -> "Repository | None":
        """Get a repository by full name (owner/repo)."""
        if self.use_mock:
            return None

        try:
            if self._github is None:
                return None
            return self._github.get_repo(repo_full_name)
        except GithubException as e:
            logger.error(f"Failed to get repository {repo_full_name}: {e}")
            return None

    def _get_branch(self, repo: "Repository", branch_name: str) -> "Branch | None":
        """Get a branch from a repository."""
        if self.use_mock:
            return None

        try:
            return repo.get_branch(branch_name)
        except GithubException as e:
            logger.error(f"Failed to get branch {branch_name}: {e}")
            return None

    async def enable_branch_protection(
        self,
        repo_full_name: str,
        config: BranchProtectionConfig,
    ) -> BranchProtectionResult:
        """
        Enable branch protection with the specified configuration.

        Args:
            repo_full_name: Full repository name (owner/repo)
            config: Branch protection configuration

        Returns:
            BranchProtectionResult with operation status
        """
        if self.use_mock:
            return self._mock_enable_protection(repo_full_name, config)

        try:
            repo = self._get_repository(repo_full_name)
            if not repo:
                return BranchProtectionResult(
                    success=False,
                    branch=config.branch_pattern,
                    protection_enabled=False,
                    message=f"Repository not found: {repo_full_name}",
                    error="REPOSITORY_NOT_FOUND",
                )

            branch = self._get_branch(repo, config.branch_pattern)
            if not branch:
                return BranchProtectionResult(
                    success=False,
                    branch=config.branch_pattern,
                    protection_enabled=False,
                    message=f"Branch not found: {config.branch_pattern}",
                    error="BRANCH_NOT_FOUND",
                )

            # Build protection parameters
            protection_params = self._build_protection_params(config)

            # Apply branch protection
            branch.edit_protection(**protection_params)

            logger.info(
                f"Branch protection enabled for {repo_full_name}:{config.branch_pattern}"
            )

            return BranchProtectionResult(
                success=True,
                branch=config.branch_pattern,
                protection_enabled=True,
                message=f"Branch protection enabled for {config.branch_pattern}",
                config_applied=config,
            )

        except GithubException as e:
            logger.error(f"Failed to enable branch protection: {e}")
            return BranchProtectionResult(
                success=False,
                branch=config.branch_pattern,
                protection_enabled=False,
                message=f"Failed to enable branch protection: {str(e)}",
                error=str(e),
            )

    async def disable_branch_protection(
        self,
        repo_full_name: str,
        branch_name: str,
    ) -> BranchProtectionResult:
        """
        Disable branch protection on a branch.

        Args:
            repo_full_name: Full repository name (owner/repo)
            branch_name: Name of the branch

        Returns:
            BranchProtectionResult with operation status
        """
        if self.use_mock:
            return BranchProtectionResult(
                success=True,
                branch=branch_name,
                protection_enabled=False,
                message=f"Branch protection disabled for {branch_name} (mock)",
            )

        try:
            repo = self._get_repository(repo_full_name)
            if not repo:
                return BranchProtectionResult(
                    success=False,
                    branch=branch_name,
                    protection_enabled=False,
                    message=f"Repository not found: {repo_full_name}",
                    error="REPOSITORY_NOT_FOUND",
                )

            branch = self._get_branch(repo, branch_name)
            if not branch:
                return BranchProtectionResult(
                    success=False,
                    branch=branch_name,
                    protection_enabled=False,
                    message=f"Branch not found: {branch_name}",
                    error="BRANCH_NOT_FOUND",
                )

            # Remove branch protection
            branch.remove_protection()

            logger.info(
                f"Branch protection disabled for {repo_full_name}:{branch_name}"
            )

            return BranchProtectionResult(
                success=True,
                branch=branch_name,
                protection_enabled=False,
                message=f"Branch protection disabled for {branch_name}",
            )

        except GithubException as e:
            logger.error(f"Failed to disable branch protection: {e}")
            return BranchProtectionResult(
                success=False,
                branch=branch_name,
                protection_enabled=False,
                message=f"Failed to disable branch protection: {str(e)}",
                error=str(e),
            )

    async def get_branch_protection_status(
        self,
        repo_full_name: str,
        branch_name: str,
    ) -> dict[str, Any]:
        """
        Get current branch protection status.

        Args:
            repo_full_name: Full repository name (owner/repo)
            branch_name: Name of the branch

        Returns:
            Dictionary with protection status and configuration
        """
        if self.use_mock:
            return {
                "protected": False,
                "branch": branch_name,
                "repository": repo_full_name,
                "mock": True,
            }

        try:
            repo = self._get_repository(repo_full_name)
            if not repo:
                return {"error": "Repository not found", "protected": False}

            branch = self._get_branch(repo, branch_name)
            if not branch:
                return {"error": "Branch not found", "protected": False}

            protection = branch.get_protection()

            return {
                "protected": True,
                "branch": branch_name,
                "repository": repo_full_name,
                "enforce_admins": protection.enforce_admins,
                "required_status_checks": (
                    {
                        "strict": protection.required_status_checks.strict,
                        "contexts": protection.required_status_checks.contexts,
                    }
                    if protection.required_status_checks
                    else None
                ),
                "required_pull_request_reviews": (
                    {
                        "dismiss_stale_reviews": (
                            protection.required_pull_request_reviews.dismiss_stale_reviews
                        ),
                        "require_code_owner_reviews": (
                            protection.required_pull_request_reviews.require_code_owner_reviews
                        ),
                        "required_approving_review_count": (
                            protection.required_pull_request_reviews.required_approving_review_count
                        ),
                    }
                    if protection.required_pull_request_reviews
                    else None
                ),
                "restrictions": protection.restrictions is not None,
                "allow_force_pushes": protection.allow_force_pushes,
                "allow_deletions": protection.allow_deletions,
            }

        except GithubException as e:
            if "Branch not protected" in str(e):
                return {
                    "protected": False,
                    "branch": branch_name,
                    "repository": repo_full_name,
                }
            logger.error(f"Failed to get branch protection status: {e}")
            return {"error": str(e), "protected": False}

    async def apply_compliance_preset(
        self,
        repo_full_name: str,
        preset: CompliancePreset,
        branches: list[str] | None = None,
    ) -> list[BranchProtectionResult]:
        """
        Apply a compliance preset to one or more branches.

        Args:
            repo_full_name: Full repository name (owner/repo)
            preset: Compliance preset to apply
            branches: List of branches (defaults to ["main", "develop"])

        Returns:
            List of BranchProtectionResult for each branch
        """
        if branches is None:
            branches = ["main", "develop"]

        results = []
        for branch in branches:
            config = BranchProtectionConfig.from_compliance_preset(preset, branch)
            result = await self.enable_branch_protection(repo_full_name, config)
            results.append(result)

        logger.info(
            f"Applied {preset.value} compliance preset to {repo_full_name}: "
            f"{sum(1 for r in results if r.success)}/{len(results)} branches protected"
        )

        return results

    def _build_protection_params(
        self, config: BranchProtectionConfig
    ) -> dict[str, Any]:
        """Build GitHub API parameters from configuration."""
        params: dict[str, Any] = {
            "enforce_admins": config.enforce_admins,
            "allow_force_pushes": config.allow_force_pushes,
            "allow_deletions": config.allow_deletions,
        }

        # Status checks
        if config.require_status_checks:
            params["strict"] = config.strict_status_checks
            params["contexts"] = config.required_status_checks
        else:
            params["strict"] = None
            params["contexts"] = []

        # Pull request reviews
        if config.require_pull_request:
            params["dismiss_stale_reviews"] = config.dismiss_stale_reviews
            params["require_code_owner_reviews"] = config.require_code_owner_reviews
            params["required_approving_review_count"] = (
                config.required_approving_review_count
            )

        # Push restrictions (requires list of users/teams/apps)
        if config.restrict_pushes:
            params["users_push_access"] = config.bypass_actors
            params["teams_push_access"] = []

        return params

    def _mock_enable_protection(
        self, repo_full_name: str, config: BranchProtectionConfig
    ) -> BranchProtectionResult:
        """Mock implementation for testing."""
        logger.info(
            f"[MOCK] Enabling branch protection for {repo_full_name}:{config.branch_pattern}"
        )
        logger.info(f"[MOCK] Configuration: {config}")

        return BranchProtectionResult(
            success=True,
            branch=config.branch_pattern,
            protection_enabled=True,
            message=f"Branch protection enabled for {config.branch_pattern} (mock)",
            config_applied=config,
            warnings=["Running in mock mode - no actual protection applied"],
        )


# =============================================================================
# Factory Functions
# =============================================================================


def create_branch_protection_service(
    github_token: str | None = None,
    use_mock: bool = False,
) -> BranchProtectionService:
    """
    Factory function to create a BranchProtectionService.

    Args:
        github_token: GitHub token for authentication
        use_mock: Enable mock mode for testing

    Returns:
        Configured BranchProtectionService instance
    """
    return BranchProtectionService(
        github_token=github_token,
        use_mock=use_mock,
    )


# =============================================================================
# CLI / Demo
# =============================================================================

if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)

    async def demo():
        print("=" * 60)
        print("Branch Protection Service Demo")
        print("=" * 60)

        # Create service in mock mode
        service = create_branch_protection_service(use_mock=True)

        # Demo: Apply CMMC compliance preset
        print("\n1. Applying CMMC compliance preset...")
        results = await service.apply_compliance_preset(
            repo_full_name="example/repo",
            preset=CompliancePreset.CMMC,
            branches=["main", "develop"],
        )

        for result in results:
            print(
                f"   - {result.branch}: {'✅' if result.success else '❌'} {result.message}"
            )
            if result.config_applied:
                print(
                    f"     Required approvals: {result.config_applied.required_approving_review_count}"
                )
                print(
                    f"     Status checks: {result.config_applied.required_status_checks}"
                )

        # Demo: Custom configuration
        print("\n2. Applying custom configuration...")
        custom_config = BranchProtectionConfig(
            branch_pattern="main",
            required_approving_review_count=2,
            required_status_checks=["Code Quality Checks", "Aura Security Review"],
            require_signed_commits=True,
        )
        result = await service.enable_branch_protection("example/repo", custom_config)
        print(f"   Result: {'✅' if result.success else '❌'} {result.message}")

        # Demo: Get status
        print("\n3. Checking protection status...")
        status = await service.get_branch_protection_status("example/repo", "main")
        print(f"   Protected: {status.get('protected', False)}")

    asyncio.run(demo())
