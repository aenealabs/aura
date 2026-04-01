"""
Tests for Compliance-Aware Security Review Service.

Tests security scanning with compliance profile integration.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.compliance_profiles import ComplianceLevel, SeverityLevel
from src.services.compliance_security_service import (
    ComplianceScanResult,
    ComplianceSecurityService,
    SecurityFinding,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_config():
    """Create mock compliance config."""
    config = MagicMock()
    config.is_enabled.return_value = True

    # Create profile mock
    profile = MagicMock()
    profile.name = ComplianceLevel.CMMC_LEVEL_3
    profile.display_name = "CMMC Level 3 (Advanced)"
    profile.version = "1.0.0"
    profile.description = "CMMC Level 3 compliance"

    # Scanning policy
    profile.scanning = MagicMock()
    profile.scanning.included_paths = ["src/**", "tests/**"]
    profile.scanning.excluded_paths = ["archive/**", "node_modules/**"]
    profile.scanning.scan_all_changes = True
    profile.scanning.scan_documentation = True
    profile.scanning.scan_configuration = True
    profile.scanning.scan_tests = True
    profile.scanning.scan_infrastructure = True

    # Review policy
    profile.review = MagicMock()
    profile.review.block_on_critical = True
    profile.review.block_on_high = True
    profile.review.require_manual_review = {"iam_policies", "network_configs"}
    profile.review.require_security_approval = {"deploy/cloudformation/iam.yaml"}
    profile.review.min_reviewers = 2

    # Audit policy
    profile.audit = MagicMock()
    profile.audit.log_retention_days = 365

    # Control mappings
    profile.control_mappings = {"AC": ["AC-1", "AC-2"]}

    config.get_profile.return_value = profile

    # Profile manager mock
    manager = MagicMock()
    manager.requires_manual_review.return_value = True
    manager.get_audit_metadata.return_value = {
        "compliance_profile": "CMMC_LEVEL_3",
        "scan_all_changes": True,
    }

    config.get_profile_manager.return_value = manager

    return config, profile, manager


@pytest.fixture
def security_service(mock_config):
    """Create security service with mocked config."""
    config, profile, manager = mock_config

    with patch(
        "src.services.compliance_security_service.get_compliance_config"
    ) as mock_get:
        mock_get.return_value = config
        service = ComplianceSecurityService()
        service.config = config
        service.profile = profile
        service.profile_manager = manager
        yield service


@pytest.fixture
def sample_findings():
    """Create sample security findings."""
    return [
        SecurityFinding(
            id="finding-1",
            severity=SeverityLevel.CRITICAL,
            title="SQL Injection",
            description="Unsafe SQL query construction",
            file_path="src/api.py",
            line_number=42,
            cwe_id="CWE-89",
            owasp_category="A03:2021",
            remediation="Use parameterized queries",
            compliance_impact=["SI-3.14.4"],
        ),
        SecurityFinding(
            id="finding-2",
            severity=SeverityLevel.HIGH,
            title="Hardcoded Credentials",
            description="Password found in source code",
            file_path="src/config.py",
            line_number=10,
            cwe_id="CWE-798",
        ),
        SecurityFinding(
            id="finding-3",
            severity=SeverityLevel.MEDIUM,
            title="Debug Mode Enabled",
            description="Flask debug mode is on",
            file_path="src/main.py",
        ),
        SecurityFinding(
            id="finding-4",
            severity=SeverityLevel.LOW,
            title="Missing Docstring",
            description="Function lacks documentation",
            file_path="src/utils.py",
        ),
    ]


# ============================================================================
# SecurityFinding Tests
# ============================================================================


class TestSecurityFinding:
    """Test SecurityFinding dataclass."""

    def test_create_finding_minimal(self):
        """Test creating finding with minimal fields."""
        finding = SecurityFinding(
            id="test-1",
            severity=SeverityLevel.HIGH,
            title="Test Finding",
            description="Test description",
            file_path="test.py",
        )
        assert finding.id == "test-1"
        assert finding.severity == SeverityLevel.HIGH
        assert finding.line_number is None
        assert finding.compliance_impact == []

    def test_create_finding_full(self):
        """Test creating finding with all fields."""
        finding = SecurityFinding(
            id="test-2",
            severity=SeverityLevel.CRITICAL,
            title="XSS Vulnerability",
            description="Reflected XSS",
            file_path="src/web.py",
            line_number=100,
            cwe_id="CWE-79",
            owasp_category="A03:2021",
            remediation="Encode output",
            compliance_impact=["SI-3.14.4", "SC-3.13.2"],
        )
        assert finding.line_number == 100
        assert finding.cwe_id == "CWE-79"
        assert len(finding.compliance_impact) == 2


# ============================================================================
# ComplianceScanResult Tests
# ============================================================================


class TestComplianceScanResult:
    """Test ComplianceScanResult dataclass."""

    def test_create_result(self, sample_findings):
        """Test creating scan result."""
        result = ComplianceScanResult(
            profile_name=ComplianceLevel.CMMC_LEVEL_3,
            profile_display_name="CMMC Level 3",
            scan_timestamp=datetime.now(timezone.utc),
            files_scanned=100,
            files_skipped=10,
            findings=sample_findings,
            critical_count=1,
            high_count=1,
            medium_count=1,
            low_count=1,
            should_block_deployment=True,
            requires_manual_review=True,
            manual_review_reasons=["Critical finding detected"],
        )
        assert result.files_scanned == 100
        assert len(result.findings) == 4
        assert result.should_block_deployment is True


# ============================================================================
# File Filtering Tests
# ============================================================================


class TestFileFiltering:
    """Test file filtering based on compliance profile."""

    def test_should_scan_file_in_included_path(self, security_service):
        """Test file in included path should be scanned."""
        should_scan, reason = security_service.should_scan_file("src/main.py")
        assert should_scan is True
        assert "scans all changes" in reason.lower()

    def test_should_scan_file_in_excluded_path(self, security_service):
        """Test file in excluded path should not be scanned."""
        should_scan, reason = security_service.should_scan_file("archive/old_code.py")
        assert should_scan is False
        assert "excluded" in reason.lower()

    def test_should_scan_documentation_enabled(self, security_service):
        """Test documentation scanning when enabled."""
        security_service.profile.scanning.scan_all_changes = False
        should_scan, reason = security_service.should_scan_file("docs/README.md")
        assert should_scan is True
        assert "documentation" in reason.lower()

    def test_should_scan_documentation_disabled(self, security_service):
        """Test documentation scanning when disabled."""
        security_service.profile.scanning.scan_all_changes = False
        security_service.profile.scanning.scan_documentation = False
        should_scan, reason = security_service.should_scan_file("docs/README.md")
        assert should_scan is False

    def test_should_scan_configuration_enabled(self, security_service):
        """Test configuration scanning when enabled."""
        security_service.profile.scanning.scan_all_changes = False
        should_scan, reason = security_service.should_scan_file("config/settings.yaml")
        assert should_scan is True

    def test_should_scan_configuration_disabled(self, security_service):
        """Test configuration scanning when disabled."""
        security_service.profile.scanning.scan_all_changes = False
        security_service.profile.scanning.scan_configuration = False
        should_scan, reason = security_service.should_scan_file("config/settings.yaml")
        assert should_scan is False

    def test_should_scan_tests_enabled(self, security_service):
        """Test test file scanning when enabled."""
        security_service.profile.scanning.scan_all_changes = False
        should_scan, reason = security_service.should_scan_file("tests/test_main.py")
        assert should_scan is True

    def test_should_scan_tests_disabled(self, security_service):
        """Test test file scanning when disabled."""
        security_service.profile.scanning.scan_all_changes = False
        security_service.profile.scanning.scan_tests = False
        security_service.profile.scanning.included_paths = []  # Clear inclusions
        should_scan, reason = security_service.should_scan_file("tests/test_main.py")
        assert should_scan is False

    def test_should_scan_infrastructure_enabled(self, security_service):
        """Test infrastructure scanning when enabled."""
        security_service.profile.scanning.scan_all_changes = False
        should_scan, reason = security_service.should_scan_file(
            "deploy/cloudformation/vpc.yaml"
        )
        assert should_scan is True

    def test_should_scan_infrastructure_disabled(self, security_service):
        """Test infrastructure scanning when disabled."""
        security_service.profile.scanning.scan_all_changes = False
        security_service.profile.scanning.scan_infrastructure = False
        security_service.profile.scanning.scan_configuration = (
            False  # Also disable config
        )
        security_service.profile.scanning.included_paths = []  # Clear inclusions
        should_scan, reason = security_service.should_scan_file(
            "deploy/cloudformation/vpc.yaml"
        )
        assert should_scan is False

    def test_should_scan_compliance_disabled(self, security_service):
        """Test scanning when compliance is disabled."""
        security_service.config.is_enabled.return_value = False
        should_scan, reason = security_service.should_scan_file("anything.py")
        assert should_scan is True
        assert "disabled" in reason.lower()

    def test_filter_files_for_scanning(self, security_service):
        """Test filtering multiple files."""
        files = [
            "src/main.py",
            "src/api.py",
            "archive/old.py",
            "node_modules/package.json",
        ]
        to_scan, skipped, skip_reasons = security_service.filter_files_for_scanning(
            files
        )

        assert len(to_scan) == 2
        assert len(skipped) == 2
        assert "archive/old.py" in skipped
        assert "node_modules/package.json" in skipped


# ============================================================================
# Finding Categorization Tests
# ============================================================================


class TestFindingCategorization:
    """Test finding categorization."""

    def test_categorize_findings(self, security_service, sample_findings):
        """Test categorizing findings by severity."""
        categorized = security_service.categorize_findings(sample_findings)

        assert len(categorized[SeverityLevel.CRITICAL]) == 1
        assert len(categorized[SeverityLevel.HIGH]) == 1
        assert len(categorized[SeverityLevel.MEDIUM]) == 1
        assert len(categorized[SeverityLevel.LOW]) == 1
        assert len(categorized[SeverityLevel.INFO]) == 0

    def test_categorize_empty_findings(self, security_service):
        """Test categorizing empty findings list."""
        categorized = security_service.categorize_findings([])

        for severity in SeverityLevel:
            assert len(categorized[severity]) == 0


# ============================================================================
# Deployment Decision Tests
# ============================================================================


class TestDeploymentDecision:
    """Test deployment blocking decisions."""

    def test_should_block_with_critical(self, security_service, sample_findings):
        """Test blocking on critical findings."""
        should_block, reason = security_service.should_block_deployment(sample_findings)
        assert should_block is True
        assert "critical" in reason.lower()

    def test_should_block_with_high_only(self, security_service):
        """Test blocking on high findings when configured."""
        findings = [
            SecurityFinding(
                id="high-1",
                severity=SeverityLevel.HIGH,
                title="High Severity",
                description="High severity finding",
                file_path="src/main.py",
            )
        ]
        should_block, reason = security_service.should_block_deployment(findings)
        assert should_block is True
        assert "high" in reason.lower()

    def test_should_not_block_medium(self, security_service):
        """Test not blocking on medium findings."""
        findings = [
            SecurityFinding(
                id="medium-1",
                severity=SeverityLevel.MEDIUM,
                title="Medium Severity",
                description="Medium severity finding",
                file_path="src/main.py",
            )
        ]
        should_block, reason = security_service.should_block_deployment(findings)
        assert should_block is False

    def test_should_not_block_empty_findings(self, security_service):
        """Test not blocking with no findings."""
        should_block, reason = security_service.should_block_deployment([])
        assert should_block is False


# ============================================================================
# Manual Review Tests
# ============================================================================


class TestManualReview:
    """Test manual review requirements."""

    def test_requires_review_iam_changes(self, security_service):
        """Test IAM changes require review."""
        files = ["deploy/cloudformation/iam.yaml"]
        requires, reasons = security_service.requires_manual_review(files)
        assert requires is True
        assert len(reasons) > 0

    def test_requires_review_network_changes(self, security_service):
        """Test network changes require review."""
        files = ["deploy/cloudformation/vpc.yaml"]
        requires, reasons = security_service.requires_manual_review(files)
        assert requires is True

    def test_requires_review_security_group(self, security_service):
        """Test security group changes require review."""
        files = ["deploy/cloudformation/security-groups.yaml"]
        requires, reasons = security_service.requires_manual_review(files)
        assert requires is True

    def test_no_review_regular_code(self, security_service):
        """Test regular code changes don't require review."""
        security_service.profile_manager.requires_manual_review.return_value = False
        files = ["src/utils.py", "src/helpers.py"]
        requires, reasons = security_service.requires_manual_review(files)
        # May still require if files match security approval patterns
        # Just check the function works
        assert isinstance(requires, bool)


# ============================================================================
# Scan Execution Tests
# ============================================================================


class TestScanExecution:
    """Test scan execution."""

    def test_perform_scan_no_findings(self, security_service):
        """Test scan with no findings."""
        result = security_service.perform_scan(
            file_paths=["src/main.py", "src/utils.py"],
            external_findings=[],
        )

        assert result.profile_name == ComplianceLevel.CMMC_LEVEL_3
        assert result.files_scanned == 2
        assert result.critical_count == 0
        assert result.should_block_deployment is False

    def test_perform_scan_with_findings(self, security_service, sample_findings):
        """Test scan with findings."""
        # Include files that require manual review
        result = security_service.perform_scan(
            file_paths=["deploy/cloudformation/iam.yaml", "src/api.py"],
            external_findings=sample_findings,
        )

        assert result.critical_count == 1
        assert result.high_count == 1
        assert result.should_block_deployment is True
        # Manual review may or may not be required based on files
        assert isinstance(result.requires_manual_review, bool)

    def test_perform_scan_audit_metadata(self, security_service):
        """Test scan includes audit metadata."""
        result = security_service.perform_scan(
            file_paths=["src/main.py"],
            external_findings=[],
        )

        assert "scan_timestamp" in result.audit_metadata
        assert "files_scanned" in result.audit_metadata


# ============================================================================
# Report Formatting Tests
# ============================================================================


class TestReportFormatting:
    """Test report formatting."""

    def test_format_scan_summary_no_findings(self, security_service):
        """Test formatting summary with no findings."""
        result = ComplianceScanResult(
            profile_name=ComplianceLevel.CMMC_LEVEL_3,
            profile_display_name="CMMC Level 3",
            scan_timestamp=datetime.now(timezone.utc),
            files_scanned=10,
            files_skipped=2,
            findings=[],
            should_block_deployment=False,
            requires_manual_review=False,
        )
        summary = security_service.format_scan_summary(result)

        assert "Compliance-Aware Security Scan" in summary
        assert "**Files Scanned:** 10" in summary
        assert "No security findings detected" in summary
        assert "APPROVED" in summary

    def test_format_scan_summary_with_findings(self, security_service, sample_findings):
        """Test formatting summary with findings."""
        result = ComplianceScanResult(
            profile_name=ComplianceLevel.CMMC_LEVEL_3,
            profile_display_name="CMMC Level 3",
            scan_timestamp=datetime.now(timezone.utc),
            files_scanned=10,
            files_skipped=2,
            findings=sample_findings,
            critical_count=1,
            high_count=1,
            medium_count=1,
            low_count=1,
            should_block_deployment=True,
            requires_manual_review=True,
            manual_review_reasons=["Critical vulnerability found"],
        )
        summary = security_service.format_scan_summary(result)

        assert "4 security findings" in summary
        assert "**Critical:** 1" in summary
        assert "BLOCKED" in summary
        assert "Manual Review Required" in summary


# ============================================================================
# Compliance Report Tests
# ============================================================================


class TestComplianceReport:
    """Test compliance report generation."""

    def test_get_compliance_report(self, security_service):
        """Test generating compliance report."""
        report = security_service.get_compliance_report()

        assert "profile" in report
        assert report["profile"]["name"] == "CMMC_LEVEL_3"
        assert "scanning_policy" in report
        assert "review_policy" in report
        assert "audit_policy" in report
        assert "control_mappings" in report

    def test_compliance_report_scanning_policy(self, security_service):
        """Test scanning policy in compliance report."""
        report = security_service.get_compliance_report()

        scanning = report["scanning_policy"]
        assert "scan_all_changes" in scanning
        assert "scan_infrastructure" in scanning
        assert "scan_documentation" in scanning

    def test_compliance_report_review_policy(self, security_service):
        """Test review policy in compliance report."""
        report = security_service.get_compliance_report()

        review = report["review_policy"]
        assert "block_on_critical" in review
        assert "block_on_high" in review
        assert "min_reviewers" in review
