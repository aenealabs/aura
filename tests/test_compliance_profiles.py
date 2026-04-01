"""
Tests for Compliance Profile Management.

Tests the compliance profile system including:
- Profile definitions (CMMC, SOX, PCI-DSS, NIST, Development)
- Profile registry and retrieval
- Profile manager and overrides
- Scanning, review, and audit policies
"""

import pytest

from src.services.compliance_profiles import (
    AuditPolicy,
    ComplianceLevel,
    ComplianceProfile,
    ComplianceProfileManager,
    ComplianceProfileRegistry,
    ReviewPolicy,
    ScanningPolicy,
    SeverityLevel,
)

# ============================================================================
# Enum Tests
# ============================================================================


class TestComplianceLevel:
    """Test ComplianceLevel enum."""

    def test_cmmc_level_3(self):
        """Test CMMC Level 3 value."""
        assert ComplianceLevel.CMMC_LEVEL_3.value == "CMMC_LEVEL_3"

    def test_cmmc_level_2(self):
        """Test CMMC Level 2 value."""
        assert ComplianceLevel.CMMC_LEVEL_2.value == "CMMC_LEVEL_2"

    def test_sox(self):
        """Test SOX value."""
        assert ComplianceLevel.SOX.value == "SOX"

    def test_pci_dss(self):
        """Test PCI-DSS value."""
        assert ComplianceLevel.PCI_DSS.value == "PCI_DSS"

    def test_nist_800_53(self):
        """Test NIST 800-53 value."""
        assert ComplianceLevel.NIST_800_53.value == "NIST_800_53"

    def test_development(self):
        """Test Development value."""
        assert ComplianceLevel.DEVELOPMENT.value == "DEVELOPMENT"

    def test_custom(self):
        """Test Custom value."""
        assert ComplianceLevel.CUSTOM.value == "CUSTOM"


class TestSeverityLevel:
    """Test SeverityLevel enum."""

    def test_critical(self):
        """Test CRITICAL severity."""
        assert SeverityLevel.CRITICAL.value == "CRITICAL"

    def test_high(self):
        """Test HIGH severity."""
        assert SeverityLevel.HIGH.value == "HIGH"

    def test_medium(self):
        """Test MEDIUM severity."""
        assert SeverityLevel.MEDIUM.value == "MEDIUM"

    def test_low(self):
        """Test LOW severity."""
        assert SeverityLevel.LOW.value == "LOW"

    def test_info(self):
        """Test INFO severity."""
        assert SeverityLevel.INFO.value == "INFO"


# ============================================================================
# Policy Tests
# ============================================================================


class TestScanningPolicy:
    """Test ScanningPolicy dataclass."""

    def test_default_values(self):
        """Test default scanning policy values."""
        policy = ScanningPolicy()
        assert policy.included_paths == []
        assert policy.excluded_paths == []
        assert policy.scan_all_changes is True
        assert policy.scan_infrastructure is True
        assert policy.scan_documentation is False
        assert policy.scan_configuration is True
        assert policy.scan_tests is True

    def test_custom_values(self):
        """Test custom scanning policy values."""
        policy = ScanningPolicy(
            included_paths=["src/**"],
            excluded_paths=["archive/**"],
            scan_all_changes=False,
            scan_documentation=True,
        )
        assert policy.included_paths == ["src/**"]
        assert policy.excluded_paths == ["archive/**"]
        assert policy.scan_all_changes is False
        assert policy.scan_documentation is True


class TestReviewPolicy:
    """Test ReviewPolicy dataclass."""

    def test_default_values(self):
        """Test default review policy values."""
        policy = ReviewPolicy()
        assert policy.require_manual_review == set()
        assert policy.block_on_critical is True
        assert policy.block_on_high is False
        assert policy.min_reviewers == 1
        assert policy.require_security_approval == set()

    def test_custom_values(self):
        """Test custom review policy values."""
        policy = ReviewPolicy(
            require_manual_review={"iam_policies", "network_configs"},
            block_on_critical=True,
            block_on_high=True,
            min_reviewers=2,
            require_security_approval={"iam.yaml"},
        )
        assert "iam_policies" in policy.require_manual_review
        assert policy.block_on_high is True
        assert policy.min_reviewers == 2


class TestAuditPolicy:
    """Test AuditPolicy dataclass."""

    def test_default_values(self):
        """Test default audit policy values."""
        policy = AuditPolicy()
        assert policy.log_scan_decisions is True
        assert policy.log_findings is True
        assert policy.log_manual_reviews is True
        assert policy.log_retention_days == 90
        assert policy.include_profile_metadata is True

    def test_custom_values(self):
        """Test custom audit policy values."""
        policy = AuditPolicy(
            log_retention_days=365,
            include_profile_metadata=False,
        )
        assert policy.log_retention_days == 365
        assert policy.include_profile_metadata is False


# ============================================================================
# ComplianceProfile Tests
# ============================================================================


class TestComplianceProfile:
    """Test ComplianceProfile dataclass."""

    def test_profile_creation(self):
        """Test creating a compliance profile."""
        profile = ComplianceProfile(
            name=ComplianceLevel.CMMC_LEVEL_3,
            display_name="CMMC Level 3",
            description="Test profile",
            scanning=ScanningPolicy(),
            review=ReviewPolicy(),
            audit=AuditPolicy(),
        )
        assert profile.name == ComplianceLevel.CMMC_LEVEL_3
        assert profile.display_name == "CMMC Level 3"
        assert profile.version == "1.0.0"

    def test_profile_with_control_mappings(self):
        """Test profile with control mappings."""
        profile = ComplianceProfile(
            name=ComplianceLevel.SOX,
            display_name="SOX",
            description="SOX compliance",
            scanning=ScanningPolicy(),
            review=ReviewPolicy(),
            audit=AuditPolicy(),
            control_mappings={
                "SOX-302": ["CEO/CFO Certification"],
                "SOX-404": ["Internal Controls"],
            },
        )
        assert "SOX-302" in profile.control_mappings
        assert "SOX-404" in profile.control_mappings


# ============================================================================
# ComplianceProfileRegistry Tests
# ============================================================================


class TestComplianceProfileRegistry:
    """Test ComplianceProfileRegistry."""

    def test_get_cmmc_level_3(self):
        """Test getting CMMC Level 3 profile."""
        profile = ComplianceProfileRegistry.get_cmmc_level_3()
        assert profile.name == ComplianceLevel.CMMC_LEVEL_3
        assert "CMMC Level 3" in profile.display_name
        assert profile.scanning.scan_documentation is True
        assert profile.review.block_on_high is True
        assert profile.review.min_reviewers == 2
        assert profile.audit.log_retention_days == 365

    def test_get_cmmc_level_2(self):
        """Test getting CMMC Level 2 profile."""
        profile = ComplianceProfileRegistry.get_cmmc_level_2()
        assert profile.name == ComplianceLevel.CMMC_LEVEL_2
        assert profile.scanning.scan_documentation is False
        assert profile.review.block_on_high is False
        assert profile.review.min_reviewers == 1
        assert profile.audit.log_retention_days == 90

    def test_get_sox(self):
        """Test getting SOX profile."""
        profile = ComplianceProfileRegistry.get_sox()
        assert profile.name == ComplianceLevel.SOX
        assert "SOX" in profile.display_name
        assert profile.review.block_on_high is True
        assert profile.review.min_reviewers == 2
        assert profile.audit.log_retention_days == 2555  # 7 years

    def test_get_pci_dss(self):
        """Test getting PCI-DSS profile."""
        profile = ComplianceProfileRegistry.get_pci_dss()
        assert profile.name == ComplianceLevel.PCI_DSS
        assert "PCI-DSS" in profile.display_name
        assert profile.review.block_on_critical is True
        assert "payment_processing" in profile.review.require_manual_review

    def test_get_nist_800_53(self):
        """Test getting NIST 800-53 profile."""
        profile = ComplianceProfileRegistry.get_nist_800_53()
        assert profile.name == ComplianceLevel.NIST_800_53
        assert "NIST 800-53" in profile.display_name
        assert profile.scanning.scan_documentation is True
        assert "AC" in profile.control_mappings

    def test_get_development(self):
        """Test getting Development profile."""
        profile = ComplianceProfileRegistry.get_development()
        assert profile.name == ComplianceLevel.DEVELOPMENT
        assert profile.scanning.scan_all_changes is False
        assert profile.review.block_on_critical is False
        assert profile.review.min_reviewers == 0
        assert profile.audit.log_retention_days == 30

    def test_get_profile_by_name(self):
        """Test getting profile by ComplianceLevel enum."""
        profile = ComplianceProfileRegistry.get_profile(ComplianceLevel.CMMC_LEVEL_3)
        assert profile.name == ComplianceLevel.CMMC_LEVEL_3

    def test_get_profile_invalid_name(self):
        """Test getting profile with invalid name."""
        with pytest.raises(ValueError, match="Unknown compliance profile"):
            ComplianceProfileRegistry.get_profile(ComplianceLevel.CUSTOM)

    def test_list_profiles(self):
        """Test listing all profiles."""
        profiles = ComplianceProfileRegistry.list_profiles()
        assert len(profiles) == 6
        names = [p["name"] for p in profiles]
        assert "CMMC_LEVEL_3" in names
        assert "CMMC_LEVEL_2" in names
        assert "SOX" in names
        assert "PCI_DSS" in names
        assert "NIST_800_53" in names
        assert "DEVELOPMENT" in names


# ============================================================================
# ComplianceProfileManager Tests
# ============================================================================


class TestComplianceProfileManager:
    """Test ComplianceProfileManager."""

    def test_init_default_profile(self):
        """Test initialization with default profile."""
        manager = ComplianceProfileManager()
        assert manager.default_profile == ComplianceLevel.CMMC_LEVEL_3
        assert manager._current_profile is None

    def test_init_custom_profile(self):
        """Test initialization with custom profile."""
        manager = ComplianceProfileManager(ComplianceLevel.DEVELOPMENT)
        assert manager.default_profile == ComplianceLevel.DEVELOPMENT

    def test_load_profile(self):
        """Test loading a profile."""
        manager = ComplianceProfileManager()
        profile = manager.load_profile(ComplianceLevel.SOX)
        assert profile.name == ComplianceLevel.SOX
        assert manager._current_profile is not None

    def test_load_profile_default(self):
        """Test loading default profile when None specified."""
        manager = ComplianceProfileManager(ComplianceLevel.PCI_DSS)
        profile = manager.load_profile()
        assert profile.name == ComplianceLevel.PCI_DSS

    def test_get_current_profile_auto_loads(self):
        """Test get_current_profile auto-loads if not loaded."""
        manager = ComplianceProfileManager(ComplianceLevel.NIST_800_53)
        profile = manager.get_current_profile()
        assert profile.name == ComplianceLevel.NIST_800_53

    def test_apply_overrides(self):
        """Test applying custom overrides."""
        manager = ComplianceProfileManager()
        manager.load_profile(ComplianceLevel.CMMC_LEVEL_3)

        manager.apply_overrides(
            {
                "scanning.scan_documentation": False,
                "review.min_reviewers": 3,
            }
        )

        profile = manager.get_current_profile()
        assert profile.scanning.scan_documentation is False
        assert profile.review.min_reviewers == 3

    def test_apply_overrides_without_loaded_profile(self):
        """Test applying overrides without loading profile first."""
        manager = ComplianceProfileManager()
        with pytest.raises(RuntimeError, match="No profile loaded"):
            manager.apply_overrides({"scanning.scan_documentation": True})

    def test_apply_overrides_invalid_key(self):
        """Test applying overrides with invalid key format."""
        manager = ComplianceProfileManager()
        manager.load_profile()
        # Should log warning but not fail
        manager.apply_overrides({"invalid_key": True})

    def test_should_scan_file_scan_all(self):
        """Test file scanning when scan_all_changes is True."""
        manager = ComplianceProfileManager(ComplianceLevel.CMMC_LEVEL_3)
        manager.load_profile()
        assert manager.should_scan_file("src/main.py") is True

    def test_should_scan_file_excluded(self):
        """Test file scanning with excluded paths."""
        manager = ComplianceProfileManager(ComplianceLevel.CMMC_LEVEL_3)
        manager.load_profile()
        assert manager.should_scan_file("archive/old_code.py") is False
        assert manager.should_scan_file("node_modules/package.json") is False

    def test_should_scan_file_included(self):
        """Test file scanning with included paths."""
        manager = ComplianceProfileManager(ComplianceLevel.CMMC_LEVEL_2)
        manager.load_profile()
        assert manager.should_scan_file("src/service.py") is True
        assert manager.should_scan_file("tests/test_service.py") is True

    def test_get_severity_threshold_block_both(self):
        """Test severity threshold when blocking on both critical and high."""
        manager = ComplianceProfileManager(ComplianceLevel.CMMC_LEVEL_3)
        manager.load_profile()
        threshold = manager.get_severity_threshold()
        assert threshold == SeverityLevel.HIGH

    def test_get_severity_threshold_block_critical_only(self):
        """Test severity threshold when blocking on critical only."""
        manager = ComplianceProfileManager(ComplianceLevel.DEVELOPMENT)
        manager.load_profile()
        threshold = manager.get_severity_threshold()
        assert threshold == SeverityLevel.CRITICAL

    def test_requires_manual_review_true(self):
        """Test when manual review is required."""
        manager = ComplianceProfileManager(ComplianceLevel.CMMC_LEVEL_3)
        manager.load_profile()
        assert manager.requires_manual_review("iam_policies") is True
        assert manager.requires_manual_review("network_configs") is True

    def test_requires_manual_review_false(self):
        """Test when manual review is not required."""
        manager = ComplianceProfileManager(ComplianceLevel.DEVELOPMENT)
        manager.load_profile()
        assert manager.requires_manual_review("iam_policies") is False

    def test_get_audit_metadata_with_metadata(self):
        """Test getting audit metadata when enabled."""
        manager = ComplianceProfileManager(ComplianceLevel.CMMC_LEVEL_3)
        manager.load_profile()
        metadata = manager.get_audit_metadata()
        assert "compliance_profile" in metadata
        assert metadata["compliance_profile"] == "CMMC_LEVEL_3"
        assert "control_mappings" in metadata

    def test_get_audit_metadata_without_metadata(self):
        """Test getting audit metadata when disabled."""
        manager = ComplianceProfileManager(ComplianceLevel.DEVELOPMENT)
        manager.load_profile()
        metadata = manager.get_audit_metadata()
        assert metadata == {}
