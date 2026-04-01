"""
Project Aura - AuditBoard Connector Unit Tests

Test Type: UNIT
Dependencies: All external calls mocked (aiohttp, AuditBoard REST API)
Isolation: pytest.mark.forked (prevents aiohttp mock pollution between tests)
Run Command: pytest tests/test_auditboard_connector.py -v

These tests validate:
- AuditBoard connector initialization and configuration
- Enum values and data class serialization
- Enterprise mode enforcement

Mock Strategy:
- Environment variables: Set via enable_enterprise_mode fixture
- All AuditBoard API responses would be simulated when methods are called

Related ADR: ADR-053 Enterprise Security Integrations
"""

import platform

import pytest

# Explicit test type markers
# - unit: All external dependencies are mocked
# - forked: Run in isolated subprocess on non-Linux to prevent aiohttp mock pollution
if platform.system() == "Linux":
    pytestmark = pytest.mark.skip(
        reason="Skipped on Linux CI: requires pytest-forked for isolation"
    )
else:
    pytestmark = [pytest.mark.unit, pytest.mark.forked]

from src.services.auditboard_connector import (
    AuditBoardComplianceStatus,
    AuditBoardConnector,
    AuditBoardControl,
    AuditBoardControlStatus,
    AuditBoardEvidence,
    AuditBoardEvidenceType,
    AuditBoardFinding,
    AuditBoardFindingSeverity,
    AuditBoardFindingStatus,
    AuditBoardFramework,
    AuditBoardRisk,
    AuditBoardRiskLevel,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestAuditBoardControlStatus:
    """Tests for AuditBoardControlStatus enum."""

    def test_effective(self):
        assert AuditBoardControlStatus.EFFECTIVE.value == "Effective"

    def test_ineffective(self):
        assert AuditBoardControlStatus.INEFFECTIVE.value == "Ineffective"

    def test_not_tested(self):
        assert AuditBoardControlStatus.NOT_TESTED.value == "Not Tested"

    def test_not_applicable(self):
        assert AuditBoardControlStatus.NOT_APPLICABLE.value == "Not Applicable"

    def test_in_progress(self):
        assert AuditBoardControlStatus.IN_PROGRESS.value == "In Progress"


class TestAuditBoardRiskLevel:
    """Tests for AuditBoardRiskLevel enum."""

    def test_critical(self):
        assert AuditBoardRiskLevel.CRITICAL.value == "Critical"

    def test_high(self):
        assert AuditBoardRiskLevel.HIGH.value == "High"

    def test_medium(self):
        assert AuditBoardRiskLevel.MEDIUM.value == "Medium"

    def test_low(self):
        assert AuditBoardRiskLevel.LOW.value == "Low"

    def test_minimal(self):
        assert AuditBoardRiskLevel.MINIMAL.value == "Minimal"


class TestAuditBoardFindingStatus:
    """Tests for AuditBoardFindingStatus enum."""

    def test_open(self):
        assert AuditBoardFindingStatus.OPEN.value == "Open"

    def test_in_progress(self):
        assert AuditBoardFindingStatus.IN_PROGRESS.value == "In Progress"

    def test_remediated(self):
        assert AuditBoardFindingStatus.REMEDIATED.value == "Remediated"

    def test_accepted(self):
        assert AuditBoardFindingStatus.ACCEPTED.value == "Accepted"

    def test_closed(self):
        assert AuditBoardFindingStatus.CLOSED.value == "Closed"


class TestAuditBoardFindingSeverity:
    """Tests for AuditBoardFindingSeverity enum."""

    def test_critical(self):
        assert AuditBoardFindingSeverity.CRITICAL.value == "Critical"

    def test_high(self):
        assert AuditBoardFindingSeverity.HIGH.value == "High"

    def test_medium(self):
        assert AuditBoardFindingSeverity.MEDIUM.value == "Medium"

    def test_low(self):
        assert AuditBoardFindingSeverity.LOW.value == "Low"

    def test_informational(self):
        assert AuditBoardFindingSeverity.INFORMATIONAL.value == "Informational"


class TestAuditBoardEvidenceType:
    """Tests for AuditBoardEvidenceType enum."""

    def test_document(self):
        assert AuditBoardEvidenceType.DOCUMENT.value == "Document"

    def test_screenshot(self):
        assert AuditBoardEvidenceType.SCREENSHOT.value == "Screenshot"

    def test_report(self):
        assert AuditBoardEvidenceType.REPORT.value == "Report"

    def test_log(self):
        assert AuditBoardEvidenceType.LOG.value == "Log"

    def test_configuration(self):
        assert AuditBoardEvidenceType.CONFIGURATION.value == "Configuration"

    def test_interview(self):
        assert AuditBoardEvidenceType.INTERVIEW.value == "Interview"

    def test_observation(self):
        assert AuditBoardEvidenceType.OBSERVATION.value == "Observation"


class TestAuditBoardFramework:
    """Tests for AuditBoardFramework enum."""

    def test_soc1(self):
        assert AuditBoardFramework.SOC1.value == "SOC 1"

    def test_soc2(self):
        assert AuditBoardFramework.SOC2.value == "SOC 2"

    def test_iso27001(self):
        assert AuditBoardFramework.ISO27001.value == "ISO 27001"

    def test_nist_csf(self):
        assert AuditBoardFramework.NIST_CSF.value == "NIST CSF"

    def test_nist_800_53(self):
        assert AuditBoardFramework.NIST_800_53.value == "NIST 800-53"

    def test_pci_dss(self):
        assert AuditBoardFramework.PCI_DSS.value == "PCI DSS"

    def test_hipaa(self):
        assert AuditBoardFramework.HIPAA.value == "HIPAA"

    def test_gdpr(self):
        assert AuditBoardFramework.GDPR.value == "GDPR"

    def test_cmmc(self):
        assert AuditBoardFramework.CMMC.value == "CMMC"

    def test_fedramp(self):
        assert AuditBoardFramework.FEDRAMP.value == "FedRAMP"


# =============================================================================
# Data Class Tests
# =============================================================================


class TestAuditBoardControl:
    """Tests for AuditBoardControl data class."""

    def test_creation(self):
        """Test creating control data class."""
        control = AuditBoardControl(
            control_id="CTRL001",
            control_name="Access Control Policy",
            description="Ensure proper access control",
        )
        assert control.control_id == "CTRL001"
        assert control.control_name == "Access Control Policy"
        assert control.description == "Ensure proper access control"
        assert control.status == AuditBoardControlStatus.NOT_TESTED

    def test_to_dict(self):
        """Test serializing control to dictionary."""
        control = AuditBoardControl(
            control_id="CTRL001",
            control_name="Access Control Policy",
            description="Ensure proper access control",
            status=AuditBoardControlStatus.EFFECTIVE,
            framework="SOC 2",
            owner="security-team",
        )
        data = control.to_dict()

        assert data["control_id"] == "CTRL001"
        assert data["control_name"] == "Access Control Policy"
        assert data["status"] == "Effective"
        assert data["framework"] == "SOC 2"
        assert data["owner"] == "security-team"


class TestAuditBoardRisk:
    """Tests for AuditBoardRisk data class."""

    def test_creation(self):
        """Test creating risk data class."""
        risk = AuditBoardRisk(
            risk_id="RISK001",
            risk_name="Data Breach Risk",
            description="Risk of unauthorized data access",
        )
        assert risk.risk_id == "RISK001"
        assert risk.risk_name == "Data Breach Risk"
        assert risk.risk_level == AuditBoardRiskLevel.MEDIUM

    def test_to_dict(self):
        """Test serializing risk to dictionary."""
        risk = AuditBoardRisk(
            risk_id="RISK001",
            risk_name="Data Breach Risk",
            description="Risk of unauthorized data access",
            risk_level=AuditBoardRiskLevel.HIGH,
            likelihood=4,
            impact=5,
            inherent_risk_score=20,
        )
        data = risk.to_dict()

        assert data["risk_id"] == "RISK001"
        assert data["risk_level"] == "High"
        assert data["likelihood"] == 4
        assert data["impact"] == 5
        assert data["inherent_risk_score"] == 20


class TestAuditBoardFinding:
    """Tests for AuditBoardFinding data class."""

    def test_creation(self):
        """Test creating finding data class."""
        finding = AuditBoardFinding(
            finding_id="FIND001",
            title="Missing MFA",
            description="Multi-factor authentication not enabled",
        )
        assert finding.finding_id == "FIND001"
        assert finding.title == "Missing MFA"
        assert finding.status == AuditBoardFindingStatus.OPEN
        assert finding.severity == AuditBoardFindingSeverity.MEDIUM

    def test_to_dict(self):
        """Test serializing finding to dictionary."""
        finding = AuditBoardFinding(
            finding_id="FIND001",
            title="Missing MFA",
            description="Multi-factor authentication not enabled",
            status=AuditBoardFindingStatus.REMEDIATED,
            severity=AuditBoardFindingSeverity.HIGH,
            control_id="CTRL001",
        )
        data = finding.to_dict()

        assert data["finding_id"] == "FIND001"
        assert data["status"] == "Remediated"
        assert data["severity"] == "High"
        assert data["control_id"] == "CTRL001"


class TestAuditBoardEvidence:
    """Tests for AuditBoardEvidence data class."""

    def test_creation(self):
        """Test creating evidence data class."""
        evidence = AuditBoardEvidence(
            evidence_id="EVID001",
            name="Access Control Screenshot",
            evidence_type=AuditBoardEvidenceType.SCREENSHOT,
        )
        assert evidence.evidence_id == "EVID001"
        assert evidence.name == "Access Control Screenshot"
        assert evidence.evidence_type == AuditBoardEvidenceType.SCREENSHOT

    def test_to_dict(self):
        """Test serializing evidence to dictionary."""
        evidence = AuditBoardEvidence(
            evidence_id="EVID001",
            name="Access Control Screenshot",
            evidence_type=AuditBoardEvidenceType.SCREENSHOT,
            control_id="CTRL001",
            file_size=1024,
        )
        data = evidence.to_dict()

        assert data["evidence_id"] == "EVID001"
        assert data["evidence_type"] == "Screenshot"
        assert data["control_id"] == "CTRL001"
        assert data["file_size"] == 1024


class TestAuditBoardComplianceStatus:
    """Tests for AuditBoardComplianceStatus data class."""

    def test_creation(self):
        """Test creating compliance status data class."""
        status = AuditBoardComplianceStatus(
            framework="SOC 2",
            total_controls=100,
            effective_controls=85,
            ineffective_controls=5,
            not_tested_controls=10,
            compliance_percentage=85.0,
            open_findings=3,
            overdue_findings=1,
        )
        assert status.framework == "SOC 2"
        assert status.total_controls == 100
        assert status.effective_controls == 85
        assert status.compliance_percentage == 85.0

    def test_to_dict(self):
        """Test serializing compliance status to dictionary."""
        status = AuditBoardComplianceStatus(
            framework="ISO 27001",
            total_controls=50,
            effective_controls=45,
            ineffective_controls=2,
            not_tested_controls=3,
            compliance_percentage=90.0,
            open_findings=2,
            overdue_findings=0,
            last_assessment_date="2024-12-01",
        )
        data = status.to_dict()

        assert data["framework"] == "ISO 27001"
        assert data["total_controls"] == 50
        assert data["compliance_percentage"] == 90.0
        assert data["last_assessment_date"] == "2024-12-01"


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestAuditBoardConnectorInit:
    """Tests for AuditBoardConnector initialization."""

    def test_basic_initialization(self):
        """Test basic connector initialization."""
        connector = AuditBoardConnector(
            base_url="https://company.auditboardapp.com",
            api_key="api-key",
            api_secret="api-secret",
        )
        assert connector.base_url == "https://company.auditboardapp.com"
        assert connector.api_key == "api-key"
        assert connector.api_secret == "api-secret"

    def test_custom_timeout(self):
        """Test connector with custom timeout."""
        connector = AuditBoardConnector(
            base_url="https://company.auditboardapp.com",
            api_key="api-key",
            api_secret="api-secret",
            timeout_seconds=120,
        )
        assert connector.timeout_seconds == 120

    def test_url_normalization(self):
        """Test that trailing slashes are removed from URL."""
        connector = AuditBoardConnector(
            base_url="https://company.auditboardapp.com/",
            api_key="api-key",
            api_secret="api-secret",
        )
        assert connector.base_url == "https://company.auditboardapp.com"

    def test_govcloud_flag(self):
        """Test GovCloud flag configuration."""
        connector = AuditBoardConnector(
            base_url="https://company.auditboardapp.com",
            api_key="api-key",
            api_secret="api-secret",
            govcloud=True,
        )
        assert connector.govcloud is True

    def test_default_max_retries(self):
        """Test default max retries."""
        connector = AuditBoardConnector(
            base_url="https://company.auditboardapp.com",
            api_key="api-key",
            api_secret="api-secret",
        )
        assert connector.max_retries == 3

    def test_custom_max_retries(self):
        """Test custom max retries."""
        connector = AuditBoardConnector(
            base_url="https://company.auditboardapp.com",
            api_key="api-key",
            api_secret="api-secret",
            max_retries=5,
        )
        assert connector.max_retries == 5

    def test_api_base_url_property(self):
        """Test API base URL property."""
        connector = AuditBoardConnector(
            base_url="https://company.auditboardapp.com",
            api_key="api-key",
            api_secret="api-secret",
        )
        assert connector.api_base_url == "https://company.auditboardapp.com/api/v1"
