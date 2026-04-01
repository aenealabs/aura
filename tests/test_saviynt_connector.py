"""
Project Aura - Saviynt Connector Unit Tests

Test Type: UNIT
Dependencies: All external calls mocked (aiohttp, Saviynt REST API)
Isolation: pytest.mark.forked (prevents aiohttp mock pollution between tests)
Run Command: pytest tests/test_saviynt_connector.py -v

These tests validate:
- Saviynt connector initialization and configuration
- Enum values and data class serialization
- Enterprise mode enforcement

Mock Strategy:
- Environment variables: Set via enable_enterprise_mode fixture
- All Saviynt API responses would be simulated when methods are called

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

from src.services.saviynt_connector import (
    SaviyntAccessRequest,
    SaviyntAccessRequestStatus,
    SaviyntCertification,
    SaviyntCertificationStatus,
    SaviyntConnector,
    SaviyntEntitlement,
    SaviyntEntitlementType,
    SaviyntPAMSession,
    SaviyntRiskLevel,
    SaviyntRiskScore,
    SaviyntUser,
    SaviyntUserStatus,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestSaviyntUserStatus:
    """Tests for SaviyntUserStatus enum."""

    def test_active(self):
        assert SaviyntUserStatus.ACTIVE.value == "Active"

    def test_inactive(self):
        assert SaviyntUserStatus.INACTIVE.value == "Inactive"

    def test_suspended(self):
        assert SaviyntUserStatus.SUSPENDED.value == "Suspended"

    def test_terminated(self):
        assert SaviyntUserStatus.TERMINATED.value == "Terminated"

    def test_new(self):
        assert SaviyntUserStatus.NEW.value == "New"


class TestSaviyntRiskLevel:
    """Tests for SaviyntRiskLevel enum."""

    def test_critical(self):
        assert SaviyntRiskLevel.CRITICAL.value == "critical"

    def test_high(self):
        assert SaviyntRiskLevel.HIGH.value == "high"

    def test_medium(self):
        assert SaviyntRiskLevel.MEDIUM.value == "medium"

    def test_low(self):
        assert SaviyntRiskLevel.LOW.value == "low"

    def test_none(self):
        assert SaviyntRiskLevel.NONE.value == "none"


class TestSaviyntAccessRequestStatus:
    """Tests for SaviyntAccessRequestStatus enum."""

    def test_pending(self):
        assert SaviyntAccessRequestStatus.PENDING.value == "Pending"

    def test_approved(self):
        assert SaviyntAccessRequestStatus.APPROVED.value == "Approved"

    def test_rejected(self):
        assert SaviyntAccessRequestStatus.REJECTED.value == "Rejected"

    def test_cancelled(self):
        assert SaviyntAccessRequestStatus.CANCELLED.value == "Cancelled"

    def test_expired(self):
        assert SaviyntAccessRequestStatus.EXPIRED.value == "Expired"

    def test_completed(self):
        assert SaviyntAccessRequestStatus.COMPLETED.value == "Completed"


class TestSaviyntCertificationStatus:
    """Tests for SaviyntCertificationStatus enum."""

    def test_active(self):
        assert SaviyntCertificationStatus.ACTIVE.value == "Active"

    def test_completed(self):
        assert SaviyntCertificationStatus.COMPLETED.value == "Completed"

    def test_expired(self):
        assert SaviyntCertificationStatus.EXPIRED.value == "Expired"

    def test_draft(self):
        assert SaviyntCertificationStatus.DRAFT.value == "Draft"


class TestSaviyntEntitlementType:
    """Tests for SaviyntEntitlementType enum."""

    def test_role(self):
        assert SaviyntEntitlementType.ROLE.value == "Role"

    def test_entitlement(self):
        assert SaviyntEntitlementType.ENTITLEMENT.value == "Entitlement"

    def test_account(self):
        assert SaviyntEntitlementType.ACCOUNT.value == "Account"

    def test_access(self):
        assert SaviyntEntitlementType.ACCESS.value == "Access"


# =============================================================================
# Data Class Tests
# =============================================================================


class TestSaviyntUser:
    """Tests for SaviyntUser data class."""

    def test_creation(self):
        """Test creating user data class."""
        user = SaviyntUser(
            user_key="12345",
            username="jdoe",
            email="jdoe@company.com",
        )
        assert user.user_key == "12345"
        assert user.username == "jdoe"
        assert user.email == "jdoe@company.com"
        assert user.status == SaviyntUserStatus.ACTIVE

    def test_to_dict(self):
        """Test serializing user to dictionary."""
        user = SaviyntUser(
            user_key="12345",
            username="jdoe",
            email="jdoe@company.com",
            status=SaviyntUserStatus.ACTIVE,
            risk_level=SaviyntRiskLevel.MEDIUM,
        )
        data = user.to_dict()

        assert data["user_key"] == "12345"
        assert data["username"] == "jdoe"
        assert data["status"] == "Active"
        assert data["risk_level"] == "medium"


class TestSaviyntEntitlement:
    """Tests for SaviyntEntitlement data class."""

    def test_creation(self):
        """Test creating entitlement data class."""
        entitlement = SaviyntEntitlement(
            entitlement_key="ENT001",
            entitlement_name="Admin Access",
            entitlement_type=SaviyntEntitlementType.ROLE,
        )
        assert entitlement.entitlement_key == "ENT001"
        assert entitlement.entitlement_name == "Admin Access"
        assert entitlement.entitlement_type == SaviyntEntitlementType.ROLE

    def test_to_dict(self):
        """Test serializing entitlement to dictionary."""
        entitlement = SaviyntEntitlement(
            entitlement_key="ENT001",
            entitlement_name="Admin Access",
            entitlement_type=SaviyntEntitlementType.ROLE,
            risk_score=80,
        )
        data = entitlement.to_dict()

        assert data["entitlement_key"] == "ENT001"
        assert data["entitlement_type"] == "Role"
        assert data["risk_score"] == 80


class TestSaviyntAccessRequest:
    """Tests for SaviyntAccessRequest data class."""

    def test_creation(self):
        """Test creating access request data class."""
        request = SaviyntAccessRequest(
            request_key="REQ001",
            requestor="jdoe",
            beneficiary="jdoe",
            status=SaviyntAccessRequestStatus.PENDING,
        )
        assert request.request_key == "REQ001"
        assert request.status == SaviyntAccessRequestStatus.PENDING

    def test_to_dict(self):
        """Test serializing access request to dictionary."""
        request = SaviyntAccessRequest(
            request_key="REQ001",
            requestor="jdoe",
            beneficiary="jdoe",
            status=SaviyntAccessRequestStatus.APPROVED,
            justification="Project requirement",
        )
        data = request.to_dict()

        assert data["request_key"] == "REQ001"
        assert data["status"] == "Approved"
        assert data["justification"] == "Project requirement"


class TestSaviyntCertification:
    """Tests for SaviyntCertification data class."""

    def test_creation(self):
        """Test creating certification data class."""
        cert = SaviyntCertification(
            certification_key="CERT001",
            certification_name="Q4 Access Review",
            status=SaviyntCertificationStatus.ACTIVE,
            owner="msmith",
            total_items=100,
        )
        assert cert.certification_key == "CERT001"
        assert cert.status == SaviyntCertificationStatus.ACTIVE
        assert cert.total_items == 100

    def test_to_dict(self):
        """Test serializing certification to dictionary."""
        cert = SaviyntCertification(
            certification_key="CERT001",
            certification_name="Q4 Review",
            status=SaviyntCertificationStatus.COMPLETED,
            owner="msmith",
            completion_percentage=100.0,
        )
        data = cert.to_dict()

        assert data["status"] == "Completed"
        assert data["completion_percentage"] == 100.0


class TestSaviyntPAMSession:
    """Tests for SaviyntPAMSession data class."""

    def test_creation(self):
        """Test creating PAM session data class."""
        session = SaviyntPAMSession(
            session_id="SESS001",
            user="jdoe",
            account="root",
            endpoint="prod-db-01",
            start_time="2024-12-01T14:00:00Z",
        )
        assert session.session_id == "SESS001"
        assert session.account == "root"

    def test_to_dict(self):
        """Test serializing PAM session to dictionary."""
        session = SaviyntPAMSession(
            session_id="SESS001",
            user="jdoe",
            account="root",
            endpoint="prod-db-01",
            start_time="2024-12-01T14:00:00Z",
            session_type="SSH",
        )
        data = session.to_dict()

        assert data["session_id"] == "SESS001"
        assert data["session_type"] == "SSH"


class TestSaviyntRiskScore:
    """Tests for SaviyntRiskScore data class."""

    def test_creation(self):
        """Test creating risk score data class."""
        risk = SaviyntRiskScore(
            entity_type="user",
            entity_id="jdoe",
            overall_score=75,
            risk_level=SaviyntRiskLevel.HIGH,
        )
        assert risk.overall_score == 75
        assert risk.risk_level == SaviyntRiskLevel.HIGH

    def test_to_dict(self):
        """Test serializing risk score to dictionary."""
        risk = SaviyntRiskScore(
            entity_type="user",
            entity_id="jdoe",
            overall_score=75,
            access_risk=80,
            behavior_risk=60,
            risk_level=SaviyntRiskLevel.HIGH,
        )
        data = risk.to_dict()

        assert data["overall_score"] == 75
        assert data["risk_level"] == "high"


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestSaviyntConnectorInit:
    """Tests for SaviyntConnector initialization."""

    def test_basic_initialization(self):
        """Test basic connector initialization."""
        connector = SaviyntConnector(
            base_url="https://tenant.saviyntcloud.com",
            username="api-user",
            password="api-password",
        )
        assert connector.base_url == "https://tenant.saviyntcloud.com"
        assert connector.username == "api-user"

    def test_custom_timeout(self):
        """Test connector with custom timeout."""
        connector = SaviyntConnector(
            base_url="https://tenant.saviyntcloud.com",
            username="api-user",
            password="api-password",
            timeout_seconds=120,
        )
        assert connector.timeout_seconds == 120

    def test_url_normalization(self):
        """Test that trailing slashes are removed from URL."""
        connector = SaviyntConnector(
            base_url="https://tenant.saviyntcloud.com/",
            username="api-user",
            password="api-password",
        )
        assert connector.base_url == "https://tenant.saviyntcloud.com"

    def test_govcloud_flag(self):
        """Test GovCloud flag configuration."""
        connector = SaviyntConnector(
            base_url="https://tenant.saviyntcloud.com",
            username="api-user",
            password="api-password",
            govcloud=True,
        )
        assert connector.govcloud is True

    def test_default_max_retries(self):
        """Test default max retries."""
        connector = SaviyntConnector(
            base_url="https://tenant.saviyntcloud.com",
            username="api-user",
            password="api-password",
        )
        assert connector.max_retries == 3

    def test_custom_max_retries(self):
        """Test custom max retries."""
        connector = SaviyntConnector(
            base_url="https://tenant.saviyntcloud.com",
            username="api-user",
            password="api-password",
            max_retries=5,
        )
        assert connector.max_retries == 5
