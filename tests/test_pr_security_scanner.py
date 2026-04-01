"""
Tests for PR Security Scanner Service

Tests for pull request security scanning and vulnerability detection.
"""

from unittest.mock import MagicMock

import pytest

# ==================== Enum Tests ====================


class TestSeverityLevel:
    """Tests for SeverityLevel enum."""

    def test_all_severities(self):
        """Test all severity levels exist."""
        from src.services.security.pr_security_scanner import SeverityLevel

        assert SeverityLevel.CRITICAL == "critical"
        assert SeverityLevel.HIGH == "high"
        assert SeverityLevel.MEDIUM == "medium"
        assert SeverityLevel.LOW == "low"
        assert SeverityLevel.INFO == "info"


class TestFindingCategory:
    """Tests for FindingCategory enum."""

    def test_all_categories(self):
        """Test all finding categories exist."""
        from src.services.security.pr_security_scanner import FindingCategory

        assert FindingCategory.VULNERABILITY == "vulnerability"
        assert FindingCategory.SECRET == "secret"
        assert FindingCategory.DEPENDENCY == "dependency"
        assert FindingCategory.IAC_MISCONFIGURATION == "iac_misconfiguration"
        assert FindingCategory.LICENSE_VIOLATION == "license_violation"
        assert FindingCategory.CODE_QUALITY == "code_quality"
        assert FindingCategory.COMPLIANCE == "compliance"


class TestScanStatus:
    """Tests for ScanStatus enum."""

    def test_all_statuses(self):
        """Test all scan statuses exist."""
        from src.services.security.pr_security_scanner import ScanStatus

        assert ScanStatus.PENDING == "pending"
        assert ScanStatus.RUNNING == "running"
        assert ScanStatus.COMPLETED == "completed"
        assert ScanStatus.FAILED == "failed"
        assert ScanStatus.CANCELLED == "cancelled"


class TestRemediationStatus:
    """Tests for RemediationStatus enum."""

    def test_all_statuses(self):
        """Test all remediation statuses exist."""
        from src.services.security.pr_security_scanner import RemediationStatus

        assert RemediationStatus.AVAILABLE == "available"
        assert RemediationStatus.AUTO_FIXABLE == "auto_fixable"
        assert RemediationStatus.MANUAL_REQUIRED == "manual_required"
        assert RemediationStatus.NO_FIX == "no_fix"


class TestFileRiskLevel:
    """Tests for FileRiskLevel enum."""

    def test_all_levels(self):
        """Test all file risk levels exist."""
        from src.services.security.pr_security_scanner import FileRiskLevel

        assert FileRiskLevel.CRITICAL == "critical"
        assert FileRiskLevel.HIGH == "high"
        assert FileRiskLevel.MEDIUM == "medium"
        assert FileRiskLevel.LOW == "low"


# ==================== Dataclass Tests ====================


class TestPRMetadata:
    """Tests for PRMetadata dataclass."""

    def test_creation(self):
        """Test PRMetadata creation."""
        from src.services.security.pr_security_scanner import PRMetadata

        metadata = PRMetadata(
            pr_id="123",
            repository="org/repo",
            source_branch="feature-branch",
            target_branch="main",
            author="developer@example.com",
            title="Add new feature",
            description="This PR adds a new feature",
            files_changed=["src/main.py", "tests/test_main.py"],
            additions=100,
            deletions=20,
            commits=["abc123", "def456"],
        )
        assert metadata.pr_id == "123"
        assert metadata.repository == "org/repo"
        assert len(metadata.files_changed) == 2
        assert metadata.additions == 100


class TestCodeLocation:
    """Tests for CodeLocation dataclass."""

    def test_creation(self):
        """Test CodeLocation creation."""
        from src.services.security.pr_security_scanner import CodeLocation

        location = CodeLocation(
            file_path="src/main.py",
            start_line=10,
            end_line=15,
            start_column=5,
            end_column=20,
            snippet="password = 'secret'",
            context_before="def authenticate():",
            context_after="return password",
        )
        assert location.file_path == "src/main.py"
        assert location.start_line == 10
        assert location.snippet == "password = 'secret'"


class TestCWEReference:
    """Tests for CWEReference dataclass."""

    def test_creation(self):
        """Test CWEReference creation."""
        from src.services.security.pr_security_scanner import CWEReference

        cwe = CWEReference(
            cwe_id="CWE-79",
            name="Cross-site Scripting",
            description="Improper Neutralization of Input During Web Page Generation",
            url="https://cwe.mitre.org/data/definitions/79.html",
        )
        assert cwe.cwe_id == "CWE-79"
        assert cwe.name == "Cross-site Scripting"


class TestCVSSScore:
    """Tests for CVSSScore dataclass."""

    def test_creation(self):
        """Test CVSSScore creation."""
        from src.services.security.pr_security_scanner import CVSSScore

        cvss = CVSSScore(
            base_score=7.5,
            vector_string="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
            attack_vector="Network",
            attack_complexity="Low",
            privileges_required="None",
            user_interaction="None",
            scope="Unchanged",
            confidentiality_impact="High",
            integrity_impact="None",
            availability_impact="None",
        )
        assert cvss.base_score == 7.5
        assert cvss.attack_vector == "Network"


class TestRemediation:
    """Tests for Remediation dataclass."""

    def test_creation(self):
        """Test Remediation creation."""
        from src.services.security.pr_security_scanner import (
            Remediation,
            RemediationStatus,
        )

        remediation = Remediation(
            status=RemediationStatus.AUTO_FIXABLE,
            description="Use parameterized queries",
            suggested_fix="Replace string formatting with parameterized query",
            auto_fix_patch="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@",
            references=["https://owasp.org/sql-injection"],
            effort_estimate="low",
        )
        assert remediation.status == RemediationStatus.AUTO_FIXABLE
        assert remediation.effort_estimate == "low"


class TestSecurityFinding:
    """Tests for SecurityFinding dataclass."""

    def test_creation(self):
        """Test SecurityFinding creation."""
        from src.services.security.pr_security_scanner import (
            CodeLocation,
            FindingCategory,
            SecurityFinding,
            SeverityLevel,
        )

        location = CodeLocation(file_path="src/db.py", start_line=25, end_line=25)
        finding = SecurityFinding(
            finding_id="f-001",
            category=FindingCategory.VULNERABILITY,
            severity=SeverityLevel.HIGH,
            title="SQL Injection",
            description="Possible SQL injection vulnerability",
            location=location,
            rule_id="OWASP-A03",
            confidence=0.95,
        )
        assert finding.finding_id == "f-001"
        assert finding.severity == SeverityLevel.HIGH
        assert finding.is_new is True  # Default


class TestDependencyInfo:
    """Tests for DependencyInfo dataclass."""

    def test_creation(self):
        """Test DependencyInfo creation."""
        from src.services.security.pr_security_scanner import DependencyInfo

        dep = DependencyInfo(
            name="requests",
            version="2.28.0",
            ecosystem="pip",
            license="Apache-2.0",
            is_direct=True,
            is_dev=False,
        )
        assert dep.name == "requests"
        assert dep.ecosystem == "pip"
        assert dep.is_direct is True


class TestDependencyVulnerability:
    """Tests for DependencyVulnerability dataclass."""

    def test_creation(self):
        """Test DependencyVulnerability creation."""
        from src.services.security.pr_security_scanner import (
            DependencyVulnerability,
            SeverityLevel,
        )

        vuln = DependencyVulnerability(
            vuln_id="CVE-2023-12345",
            severity=SeverityLevel.HIGH,
            title="Remote Code Execution",
            description="A vulnerability allowing RCE",
            fixed_version="2.29.0",
            cvss_score=8.5,
            references=["https://nvd.nist.gov/vuln/detail/CVE-2023-12345"],
        )
        assert vuln.vuln_id == "CVE-2023-12345"
        assert vuln.fixed_version == "2.29.0"


class TestSecretFinding:
    """Tests for SecretFinding dataclass."""

    def test_creation(self):
        """Test SecretFinding creation."""
        from src.services.security.pr_security_scanner import (
            CodeLocation,
            SecretFinding,
            SeverityLevel,
        )

        location = CodeLocation(file_path="config.py", start_line=5, end_line=5)
        secret = SecretFinding(
            secret_type="AWS Access Key",
            severity=SeverityLevel.CRITICAL,
            location=location,
            entropy=4.5,
            is_verified=True,
            secret_hash="abc123...",
            remediation="Rotate the AWS key immediately",
        )
        assert secret.secret_type == "AWS Access Key"
        assert secret.is_verified is True


class TestIaCFinding:
    """Tests for IaCFinding dataclass."""

    def test_creation(self):
        """Test IaCFinding creation."""
        from src.services.security.pr_security_scanner import (
            CodeLocation,
            IaCFinding,
            SeverityLevel,
        )

        location = CodeLocation(
            file_path="terraform/main.tf", start_line=20, end_line=25
        )
        finding = IaCFinding(
            resource_type="aws_s3_bucket",
            resource_name="my-bucket",
            provider="aws",
            severity=SeverityLevel.HIGH,
            title="S3 Bucket Public Access",
            description="S3 bucket allows public access",
            location=location,
            policy_id="AWS-S3-001",
            remediation="Enable block_public_access",
            compliance_frameworks=["CIS AWS", "SOC2"],
        )
        assert finding.resource_type == "aws_s3_bucket"
        assert finding.provider == "aws"


class TestLicenseIssue:
    """Tests for LicenseIssue dataclass."""

    def test_creation(self):
        """Test LicenseIssue creation."""
        from src.services.security.pr_security_scanner import (
            LicenseIssue,
            SeverityLevel,
        )

        issue = LicenseIssue(
            package_name="gpl-package",
            detected_license="GPL-3.0",
            issue_type="copyleft_in_commercial",
            severity=SeverityLevel.MEDIUM,
            description="GPL license incompatible with commercial use",
            allowed_licenses=["MIT", "Apache-2.0"],
        )
        assert issue.package_name == "gpl-package"
        assert issue.issue_type == "copyleft_in_commercial"


class TestScanConfiguration:
    """Tests for ScanConfiguration dataclass."""

    def test_default_creation(self):
        """Test ScanConfiguration with defaults."""
        from src.services.security.pr_security_scanner import ScanConfiguration

        config = ScanConfiguration()
        assert config.enable_sast is True
        assert config.enable_secrets is True
        assert config.enable_sca is True
        assert config.enable_iac is True
        assert config.enable_license is True
        assert config.max_findings == 1000
        assert config.timeout_seconds == 600

    def test_custom_creation(self):
        """Test ScanConfiguration with custom values."""
        from src.services.security.pr_security_scanner import (
            ScanConfiguration,
            SeverityLevel,
        )

        config = ScanConfiguration(
            enable_sast=True,
            enable_secrets=True,
            enable_sca=False,
            enable_iac=False,
            enable_license=False,
            severity_threshold=SeverityLevel.MEDIUM,
            fail_on_severity=SeverityLevel.CRITICAL,
            ignore_paths=["tests/*", "docs/*"],
            ignore_rules=["RULE-001"],
            max_findings=500,
        )
        assert config.enable_sca is False
        assert len(config.ignore_paths) == 2
        assert config.max_findings == 500


# ==================== Scanner Class Tests ====================


class TestPRSecurityScannerInit:
    """Tests for PRSecurityScanner initialization."""

    def test_basic_initialization(self):
        """Test basic initialization without clients."""
        from src.services.security.pr_security_scanner import PRSecurityScanner

        scanner = PRSecurityScanner()
        assert scanner._neptune is None
        assert scanner._opensearch is None
        assert scanner._llm is None
        assert scanner._vuln_db is None
        assert len(scanner._sast_rules) > 0  # OWASP rules loaded

    def test_initialization_with_clients(self):
        """Test initialization with client mocks."""
        from src.services.security.pr_security_scanner import PRSecurityScanner

        neptune = MagicMock()
        opensearch = MagicMock()
        llm = MagicMock()
        vuln_db = MagicMock()

        scanner = PRSecurityScanner(
            neptune_client=neptune,
            opensearch_client=opensearch,
            llm_client=llm,
            vuln_db_client=vuln_db,
        )
        assert scanner._neptune == neptune
        assert scanner._opensearch == opensearch
        assert scanner._llm == llm
        assert scanner._vuln_db == vuln_db

    def test_default_allowed_licenses(self):
        """Test default allowed licenses are set."""
        from src.services.security.pr_security_scanner import PRSecurityScanner

        scanner = PRSecurityScanner()

        assert "MIT" in scanner._allowed_licenses
        assert "Apache-2.0" in scanner._allowed_licenses
        assert "BSD-3-Clause" in scanner._allowed_licenses


class TestPRScanning:
    """Tests for PR scanning functionality."""

    @pytest.mark.asyncio
    async def test_scan_empty_pr(self):
        """Test scanning an empty PR."""
        from src.services.security.pr_security_scanner import (
            PRMetadata,
            PRSecurityScanner,
        )

        scanner = PRSecurityScanner()
        metadata = PRMetadata(
            pr_id="1",
            repository="org/repo",
            source_branch="feature",
            target_branch="main",
            author="dev@example.com",
            title="Empty PR",
            description="No changes",
            files_changed=[],
            additions=0,
            deletions=0,
            commits=[],
        )

        result = await scanner.scan_pull_request(pr_metadata=metadata, file_contents={})

        assert result is not None
        assert result.pr_metadata.pr_id == "1"

    @pytest.mark.asyncio
    async def test_scan_with_python_file(self):
        """Test scanning a PR with Python file."""
        from src.services.security.pr_security_scanner import (
            PRMetadata,
            PRSecurityScanner,
        )

        scanner = PRSecurityScanner()
        metadata = PRMetadata(
            pr_id="2",
            repository="org/repo",
            source_branch="feature",
            target_branch="main",
            author="dev@example.com",
            title="Add feature",
            description="New feature",
            files_changed=["main.py"],
            additions=10,
            deletions=0,
            commits=["abc123"],
        )

        result = await scanner.scan_pull_request(
            pr_metadata=metadata, file_contents={"main.py": "print('hello world')"}
        )

        assert result is not None
        assert result.status is not None


# ==================== Built-in Rules Tests ====================


class TestBuiltInRules:
    """Tests for built-in security rules."""

    def test_owasp_rules_exist(self):
        """Test OWASP rules are defined."""
        from src.services.security.pr_security_scanner import OWASP_RULES

        assert len(OWASP_RULES) > 0
        # Check first rule has required fields
        first_rule = OWASP_RULES[0]
        assert hasattr(first_rule, "rule_id")
        assert hasattr(first_rule, "title")

    def test_secret_patterns_exist(self):
        """Test secret patterns are defined."""
        from src.services.security.pr_security_scanner import SECRET_PATTERNS

        assert len(SECRET_PATTERNS) > 0

    def test_iac_rules_exist(self):
        """Test IaC rules are defined."""
        from src.services.security.pr_security_scanner import IAC_RULES

        assert len(IAC_RULES) > 0


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_pr_metadata_with_labels(self):
        """Test PR metadata with labels and reviewers."""
        from src.services.security.pr_security_scanner import PRMetadata

        metadata = PRMetadata(
            pr_id="999",
            repository="org/repo",
            source_branch="feature",
            target_branch="main",
            author="dev@example.com",
            title="PR with labels",
            description="Test",
            files_changed=["main.py"],
            additions=1,
            deletions=0,
            commits=["abc"],
            labels=["security", "needs-review"],
            reviewers=["reviewer1", "reviewer2"],
        )

        assert len(metadata.labels) == 2
        assert "security" in metadata.labels
        assert len(metadata.reviewers) == 2

    def test_scan_configuration_with_ignored_rules(self):
        """Test scan configuration with ignored rules."""
        from src.services.security.pr_security_scanner import ScanConfiguration

        config = ScanConfiguration(ignore_rules=["OWASP-A01", "OWASP-A02", "OWASP-A03"])

        assert len(config.ignore_rules) == 3
        assert "OWASP-A01" in config.ignore_rules

    def test_dependency_with_vulnerabilities(self):
        """Test dependency with multiple vulnerabilities."""
        from src.services.security.pr_security_scanner import (
            DependencyInfo,
            DependencyVulnerability,
            SeverityLevel,
        )

        vuln1 = DependencyVulnerability(
            vuln_id="CVE-2023-001",
            severity=SeverityLevel.HIGH,
            title="Vuln 1",
            description="First vulnerability",
        )
        vuln2 = DependencyVulnerability(
            vuln_id="CVE-2023-002",
            severity=SeverityLevel.CRITICAL,
            title="Vuln 2",
            description="Second vulnerability",
        )

        dep = DependencyInfo(
            name="vulnerable-package",
            version="1.0.0",
            ecosystem="npm",
            vulnerabilities=[vuln1, vuln2],
        )

        assert len(dep.vulnerabilities) == 2
        assert dep.vulnerabilities[1].severity == SeverityLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_scan_with_disabled_scanners(self):
        """Test scanning with some scanners disabled."""
        from src.services.security.pr_security_scanner import (
            PRMetadata,
            PRSecurityScanner,
            ScanConfiguration,
        )

        scanner = PRSecurityScanner()
        metadata = PRMetadata(
            pr_id="3",
            repository="org/repo",
            source_branch="feature",
            target_branch="main",
            author="dev@example.com",
            title="Test",
            description="Test",
            files_changed=["main.py"],
            additions=1,
            deletions=0,
            commits=["abc"],
        )
        config = ScanConfiguration(
            enable_sast=True,
            enable_secrets=True,
            enable_sca=False,
            enable_iac=False,
            enable_license=False,
        )

        result = await scanner.scan_pull_request(
            pr_metadata=metadata, file_contents={"main.py": "x = 1"}, config=config
        )

        assert result is not None


class TestSecurityRules:
    """Tests for SecurityRule class."""

    def test_security_rule_creation(self):
        """Test SecurityRule creation."""
        from src.services.security.pr_security_scanner import (
            FindingCategory,
            SecurityRule,
            SeverityLevel,
        )

        rule = SecurityRule(
            rule_id="CUSTOM-001",
            title="Custom Rule",
            description="A custom security rule",
            severity=SeverityLevel.HIGH,
            category=FindingCategory.VULNERABILITY,
            cwe_id="CWE-798",
        )
        assert rule.rule_id == "CUSTOM-001"
        assert rule.title == "Custom Rule"
        assert rule.severity == SeverityLevel.HIGH


class TestScanSummary:
    """Tests for ScanSummary dataclass."""

    def test_scan_summary_creation(self):
        """Test ScanSummary creation."""
        from src.services.security.pr_security_scanner import ScanSummary

        summary = ScanSummary(
            total_findings=10,
            critical_count=1,
            high_count=3,
            medium_count=4,
            low_count=2,
            info_count=0,
            new_findings=8,
            fixed_findings=2,
            secrets_detected=1,
            vulnerable_dependencies=3,
            iac_issues=2,
            license_issues=0,
            files_scanned=50,
            lines_scanned=2000,
            scan_passed=False,
            block_merge=True,
            risk_score=75.5,
        )
        assert summary.total_findings == 10
        assert summary.scan_passed is False
        assert summary.block_merge is True
        assert summary.risk_score == 75.5
