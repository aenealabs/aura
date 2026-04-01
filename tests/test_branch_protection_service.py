"""
Tests for BranchProtectionService

Covers:
- CompliancePreset enum and configurations
- BranchProtectionConfig dataclass and factory methods
- BranchProtectionService operations in mock mode
- Error handling and edge cases
"""

import pytest

from src.services.branch_protection_service import (
    BranchProtectionConfig,
    BranchProtectionResult,
    BranchProtectionService,
    CompliancePreset,
    StatusCheckConfig,
    create_branch_protection_service,
)

# =============================================================================
# CompliancePreset Tests
# =============================================================================


class TestCompliancePreset:
    """Tests for CompliancePreset enum."""

    def test_all_presets_defined(self):
        """Verify all expected compliance presets exist."""
        expected = [
            "minimal",
            "enterprise_standard",
            "sox",
            "cmmc",
            "hipaa",
            "pci_dss",
            "maximum",
        ]
        actual = [p.value for p in CompliancePreset]
        assert sorted(actual) == sorted(expected)

    def test_preset_values_are_lowercase(self):
        """Verify preset values are lowercase strings."""
        for preset in CompliancePreset:
            assert preset.value == preset.value.lower()
            assert isinstance(preset.value, str)


# =============================================================================
# BranchProtectionConfig Tests
# =============================================================================


class TestBranchProtectionConfig:
    """Tests for BranchProtectionConfig dataclass."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = BranchProtectionConfig()

        assert config.branch_pattern == "main"
        assert config.enabled is True
        assert config.require_pull_request is True
        assert config.required_approving_review_count == 1
        assert config.dismiss_stale_reviews is True
        assert config.require_code_owner_reviews is False
        assert config.require_status_checks is True
        assert config.strict_status_checks is True
        assert config.required_status_checks == ["Code Quality Checks"]
        assert config.restrict_pushes is True
        assert config.allow_force_pushes is False
        assert config.allow_deletions is False
        assert config.enforce_admins is True
        assert config.lock_branch is False
        assert config.require_conversation_resolution is True
        assert config.require_signed_commits is False
        assert config.require_linear_history is False

    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = BranchProtectionConfig(
            branch_pattern="develop",
            required_approving_review_count=3,
            require_signed_commits=True,
            required_status_checks=["test", "build", "security"],
        )

        assert config.branch_pattern == "develop"
        assert config.required_approving_review_count == 3
        assert config.require_signed_commits is True
        assert config.required_status_checks == ["test", "build", "security"]


class TestBranchProtectionConfigPresets:
    """Tests for BranchProtectionConfig.from_compliance_preset()."""

    def test_minimal_preset(self):
        """Test MINIMAL compliance preset configuration."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.MINIMAL, "main"
        )

        assert config.branch_pattern == "main"
        assert config.require_pull_request is True
        assert config.required_approving_review_count == 1
        assert config.require_status_checks is False
        assert config.restrict_pushes is False
        assert config.enforce_admins is False

    def test_enterprise_standard_preset(self):
        """Test ENTERPRISE_STANDARD compliance preset configuration."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.ENTERPRISE_STANDARD, "main"
        )

        assert config.require_pull_request is True
        assert config.required_approving_review_count == 1
        assert config.dismiss_stale_reviews is True
        assert config.require_status_checks is True
        assert config.required_status_checks == ["Code Quality Checks"]
        assert config.restrict_pushes is True
        assert config.enforce_admins is True

    def test_sox_preset(self):
        """Test SOX compliance preset configuration."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.SOX, "main"
        )

        # SOX requires separation of duties
        assert config.required_approving_review_count == 2
        assert config.require_code_owner_reviews is True
        assert config.require_last_push_approval is True
        assert config.require_signed_commits is True
        assert "Code Quality Checks" in config.required_status_checks
        assert "Aura Security Review" in config.required_status_checks
        assert config.strict_status_checks is True
        assert config.allow_force_pushes is False
        assert config.allow_deletions is False
        assert config.enforce_admins is True

    def test_cmmc_preset(self):
        """Test CMMC compliance preset configuration."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.CMMC, "main"
        )

        # CMMC requires strict access control and audit logging
        assert config.required_approving_review_count == 2
        assert config.require_code_owner_reviews is True
        assert config.require_signed_commits is True
        assert config.require_linear_history is True  # Clean audit trail
        assert config.strict_status_checks is True
        assert config.enforce_admins is True

    def test_hipaa_preset(self):
        """Test HIPAA compliance preset configuration."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.HIPAA, "main"
        )

        # HIPAA requires access controls and audit trails
        assert config.required_approving_review_count == 2
        assert config.require_code_owner_reviews is True
        assert config.require_status_checks is True
        assert config.restrict_pushes is True
        assert config.enforce_admins is True

    def test_pci_dss_preset(self):
        """Test PCI_DSS compliance preset configuration."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.PCI_DSS, "main"
        )

        # PCI-DSS requires change control and code review
        assert config.required_approving_review_count == 2
        assert config.require_code_owner_reviews is True
        assert config.require_last_push_approval is True
        assert config.require_signed_commits is True
        assert config.allow_force_pushes is False
        assert config.allow_deletions is False

    def test_maximum_preset(self):
        """Test MAXIMUM compliance preset configuration."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.MAXIMUM, "main"
        )

        # Maximum should enable all protections
        assert config.required_approving_review_count == 2
        assert config.require_code_owner_reviews is True
        assert config.require_last_push_approval is True
        assert config.require_signed_commits is True
        assert config.require_linear_history is True
        assert config.strict_status_checks is True
        assert config.dismiss_stale_reviews is True
        assert config.require_conversation_resolution is True
        assert config.enforce_admins is True
        assert config.allow_force_pushes is False
        assert config.allow_deletions is False
        assert config.lock_branch is False  # Don't completely lock

    def test_preset_with_custom_branch(self):
        """Test preset configuration with custom branch name."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.SOX, "release"
        )
        assert config.branch_pattern == "release"


# =============================================================================
# StatusCheckConfig Tests
# =============================================================================


class TestStatusCheckConfig:
    """Tests for StatusCheckConfig dataclass."""

    def test_status_check_config_defaults(self):
        """Test StatusCheckConfig default values."""
        check = StatusCheckConfig(check_name="Code Quality Checks")
        assert check.check_name == "Code Quality Checks"
        assert check.app_id is None

    def test_status_check_config_with_app_id(self):
        """Test StatusCheckConfig with specific app ID."""
        check = StatusCheckConfig(check_name="CI", app_id=12345)
        assert check.check_name == "CI"
        assert check.app_id == 12345


# =============================================================================
# BranchProtectionResult Tests
# =============================================================================


class TestBranchProtectionResult:
    """Tests for BranchProtectionResult dataclass."""

    def test_successful_result(self):
        """Test successful result creation."""
        result = BranchProtectionResult(
            success=True,
            branch="main",
            protection_enabled=True,
            message="Protection enabled",
        )

        assert result.success is True
        assert result.branch == "main"
        assert result.protection_enabled is True
        assert result.message == "Protection enabled"
        assert result.error is None
        assert result.warnings == []

    def test_failed_result_with_error(self):
        """Test failed result with error details."""
        result = BranchProtectionResult(
            success=False,
            branch="main",
            protection_enabled=False,
            message="Failed to enable protection",
            error="REPOSITORY_NOT_FOUND",
        )

        assert result.success is False
        assert result.error == "REPOSITORY_NOT_FOUND"

    def test_result_with_warnings(self):
        """Test result with warnings list."""
        result = BranchProtectionResult(
            success=True,
            branch="main",
            protection_enabled=True,
            message="Protection enabled (mock)",
            warnings=["Running in mock mode"],
        )

        assert len(result.warnings) == 1
        assert "mock mode" in result.warnings[0]


# =============================================================================
# BranchProtectionService Tests (Mock Mode)
# =============================================================================


class TestBranchProtectionServiceInit:
    """Tests for BranchProtectionService initialization."""

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        service = BranchProtectionService(use_mock=True)
        assert service.use_mock is True
        assert service._github is None

    def test_init_without_credentials_defaults_to_mock(self):
        """Test that service defaults to mock mode without credentials."""
        service = BranchProtectionService()
        assert service.use_mock is True

    def test_factory_function_mock_mode(self):
        """Test factory function creates service in mock mode."""
        service = create_branch_protection_service(use_mock=True)
        assert isinstance(service, BranchProtectionService)
        assert service.use_mock is True


class TestBranchProtectionServiceMock:
    """Tests for BranchProtectionService operations in mock mode."""

    @pytest.fixture
    def mock_service(self):
        """Create a service in mock mode."""
        return create_branch_protection_service(use_mock=True)

    @pytest.mark.asyncio
    async def test_enable_protection_mock(self, mock_service):
        """Test enabling branch protection in mock mode."""
        config = BranchProtectionConfig(branch_pattern="main")
        result = await mock_service.enable_branch_protection("owner/repo", config)

        assert result.success is True
        assert result.branch == "main"
        assert result.protection_enabled is True
        assert "(mock)" in result.message
        assert len(result.warnings) > 0
        assert "mock mode" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_enable_protection_with_preset_mock(self, mock_service):
        """Test enabling protection with compliance preset in mock mode."""
        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.SOX, "main"
        )
        result = await mock_service.enable_branch_protection("owner/repo", config)

        assert result.success is True
        assert result.config_applied is not None
        assert result.config_applied.required_approving_review_count == 2
        assert result.config_applied.require_signed_commits is True

    @pytest.mark.asyncio
    async def test_disable_protection_mock(self, mock_service):
        """Test disabling branch protection in mock mode."""
        result = await mock_service.disable_branch_protection("owner/repo", "main")

        assert result.success is True
        assert result.protection_enabled is False
        assert "(mock)" in result.message

    @pytest.mark.asyncio
    async def test_get_protection_status_mock(self, mock_service):
        """Test getting protection status in mock mode."""
        status = await mock_service.get_branch_protection_status("owner/repo", "main")

        assert status["protected"] is False
        assert status["branch"] == "main"
        assert status["repository"] == "owner/repo"
        assert status["mock"] is True

    @pytest.mark.asyncio
    async def test_apply_compliance_preset_mock(self, mock_service):
        """Test applying compliance preset to multiple branches in mock mode."""
        results = await mock_service.apply_compliance_preset(
            "owner/repo",
            CompliancePreset.CMMC,
            branches=["main", "develop"],
        )

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].branch == "main"
        assert results[1].branch == "develop"

    @pytest.mark.asyncio
    async def test_apply_compliance_preset_default_branches(self, mock_service):
        """Test that apply_compliance_preset defaults to main and develop."""
        results = await mock_service.apply_compliance_preset(
            "owner/repo",
            CompliancePreset.ENTERPRISE_STANDARD,
        )

        assert len(results) == 2
        branches = [r.branch for r in results]
        assert "main" in branches
        assert "develop" in branches


class TestBranchProtectionServiceBuildParams:
    """Tests for _build_protection_params method."""

    def test_build_params_with_status_checks(self):
        """Test building params with status checks enabled."""
        service = create_branch_protection_service(use_mock=True)
        config = BranchProtectionConfig(
            require_status_checks=True,
            strict_status_checks=True,
            required_status_checks=["CI", "Build"],
        )

        params = service._build_protection_params(config)

        assert params["strict"] is True
        assert params["contexts"] == ["CI", "Build"]

    def test_build_params_without_status_checks(self):
        """Test building params with status checks disabled."""
        service = create_branch_protection_service(use_mock=True)
        config = BranchProtectionConfig(require_status_checks=False)

        params = service._build_protection_params(config)

        assert params["strict"] is None
        assert params["contexts"] == []

    def test_build_params_with_pull_request_reviews(self):
        """Test building params with pull request review settings."""
        service = create_branch_protection_service(use_mock=True)
        config = BranchProtectionConfig(
            require_pull_request=True,
            dismiss_stale_reviews=True,
            require_code_owner_reviews=True,
            required_approving_review_count=2,
        )

        params = service._build_protection_params(config)

        assert params["dismiss_stale_reviews"] is True
        assert params["require_code_owner_reviews"] is True
        assert params["required_approving_review_count"] == 2

    def test_build_params_enforce_admins(self):
        """Test building params with enforce admins setting."""
        service = create_branch_protection_service(use_mock=True)
        config = BranchProtectionConfig(enforce_admins=True)

        params = service._build_protection_params(config)

        assert params["enforce_admins"] is True

    def test_build_params_force_push_and_deletions(self):
        """Test building params with force push and deletion settings."""
        service = create_branch_protection_service(use_mock=True)
        config = BranchProtectionConfig(
            allow_force_pushes=False,
            allow_deletions=False,
        )

        params = service._build_protection_params(config)

        assert params["allow_force_pushes"] is False
        assert params["allow_deletions"] is False


# =============================================================================
# Integration Pattern Tests
# =============================================================================


class TestBranchProtectionIntegrationPatterns:
    """Tests for common integration patterns with BranchProtectionService."""

    @pytest.mark.asyncio
    async def test_full_autonomous_with_sox_compliance(self):
        """Test FULL_AUTONOMOUS mode with SOX compliance branch protection."""
        service = create_branch_protection_service(use_mock=True)

        # Apply SOX compliance
        results = await service.apply_compliance_preset(
            "enterprise/financial-app",
            CompliancePreset.SOX,
            branches=["main"],
        )

        assert len(results) == 1
        result = results[0]
        assert result.success is True
        assert result.config_applied is not None

        # Verify SOX requirements are met
        config = result.config_applied
        assert config.required_approving_review_count >= 2  # Dual approval
        assert config.require_signed_commits is True  # Audit trail
        assert config.allow_force_pushes is False  # No history rewriting

    @pytest.mark.asyncio
    async def test_government_contractor_cmmc_setup(self):
        """Test CMMC compliance setup for government contractors."""
        service = create_branch_protection_service(use_mock=True)

        results = await service.apply_compliance_preset(
            "defense/secure-project",
            CompliancePreset.CMMC,
            branches=["main", "staging", "develop"],
        )

        assert len(results) == 3
        assert all(r.success for r in results)

        # Verify CMMC requirements
        for result in results:
            config = result.config_applied
            assert config.require_linear_history is True  # Clean audit
            assert config.strict_status_checks is True
            assert config.enforce_admins is True

    @pytest.mark.asyncio
    async def test_healthcare_hipaa_compliance(self):
        """Test HIPAA compliance for healthcare applications."""
        service = create_branch_protection_service(use_mock=True)

        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.HIPAA, "main"
        )
        result = await service.enable_branch_protection(
            "healthcare/patient-portal",
            config,
        )

        assert result.success is True
        assert result.config_applied.required_approving_review_count >= 2
        assert result.config_applied.restrict_pushes is True

    @pytest.mark.asyncio
    async def test_payment_processing_pci_dss(self):
        """Test PCI-DSS compliance for payment processing."""
        service = create_branch_protection_service(use_mock=True)

        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.PCI_DSS, "main"
        )
        result = await service.enable_branch_protection(
            "payments/processor",
            config,
        )

        assert result.success is True
        config = result.config_applied
        assert config.require_last_push_approval is True
        assert config.require_signed_commits is True
        assert config.allow_deletions is False

    @pytest.mark.asyncio
    async def test_startup_minimal_protection(self):
        """Test minimal protection for fast-moving startups."""
        service = create_branch_protection_service(use_mock=True)

        config = BranchProtectionConfig.from_compliance_preset(
            CompliancePreset.MINIMAL, "main"
        )
        result = await service.enable_branch_protection(
            "startup/mvp",
            config,
        )

        assert result.success is True
        config = result.config_applied
        # Minimal but still require PRs
        assert config.require_pull_request is True
        assert config.required_approving_review_count == 1
        # Relaxed settings for speed
        assert config.require_status_checks is False
        assert config.enforce_admins is False


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestBranchProtectionEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_status_checks_list(self):
        """Test configuration with empty status checks list."""
        config = BranchProtectionConfig(
            require_status_checks=True,
            required_status_checks=[],
        )
        assert config.required_status_checks == []

    def test_bypass_actors_configuration(self):
        """Test configuration with bypass actors."""
        config = BranchProtectionConfig(
            bypass_actors=["emergency-bot", "senior-dev"],
        )
        assert len(config.bypass_actors) == 2
        assert "emergency-bot" in config.bypass_actors

    @pytest.mark.asyncio
    async def test_protection_disabled_config(self):
        """Test configuration with protection disabled."""
        service = create_branch_protection_service(use_mock=True)
        config = BranchProtectionConfig(
            enabled=False,
            branch_pattern="feature/*",
        )

        # In mock mode, this still "succeeds" but protection is marked
        result = await service.enable_branch_protection("owner/repo", config)
        assert result.success is True

    def test_branch_pattern_variations(self):
        """Test various branch pattern configurations."""
        patterns = [
            "main",
            "develop",
            "release/*",
            "hotfix/*",
            "feature/**",
        ]

        for pattern in patterns:
            config = BranchProtectionConfig(branch_pattern=pattern)
            assert config.branch_pattern == pattern

    @pytest.mark.asyncio
    async def test_apply_preset_to_single_branch(self):
        """Test applying preset to a single branch."""
        service = create_branch_protection_service(use_mock=True)

        results = await service.apply_compliance_preset(
            "owner/repo",
            CompliancePreset.ENTERPRISE_STANDARD,
            branches=["production"],
        )

        assert len(results) == 1
        assert results[0].branch == "production"
