"""
Tests for License Service.

Tests license validation, edition detection, and feature gating.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.services.licensing.license_service import (
    EDITION_FEATURES,
    LicenseEdition,
    LicenseInfo,
    LicenseService,
    LicenseValidationError,
    get_license_service,
    set_license_service,
)


class TestLicenseEdition:
    """Tests for LicenseEdition enum."""

    def test_community_edition_value(self):
        """Test community edition value."""
        assert LicenseEdition.COMMUNITY.value == "community"

    def test_enterprise_edition_value(self):
        """Test enterprise edition value."""
        assert LicenseEdition.ENTERPRISE.value == "enterprise"

    def test_enterprise_plus_edition_value(self):
        """Test enterprise plus edition value."""
        assert LicenseEdition.ENTERPRISE_PLUS.value == "enterprise_plus"


class TestLicenseInfo:
    """Tests for LicenseInfo dataclass."""

    @pytest.fixture
    def valid_license(self):
        """Create a valid license info."""
        now = datetime.now(timezone.utc)
        return LicenseInfo(
            license_id="TEST-123",
            edition=LicenseEdition.ENTERPRISE,
            organization="Test Org",
            issued_at=now - timedelta(days=30),
            expires_at=now + timedelta(days=335),
            max_users=100,
            max_repositories=50,
            features=["graphrag_advanced", "sso_saml"],
        )

    @pytest.fixture
    def expired_license(self):
        """Create an expired license info."""
        now = datetime.now(timezone.utc)
        return LicenseInfo(
            license_id="EXPIRED-456",
            edition=LicenseEdition.ENTERPRISE,
            organization="Expired Org",
            issued_at=now - timedelta(days=400),
            expires_at=now - timedelta(days=35),
        )

    def test_is_valid_true(self, valid_license):
        """Test is_valid returns True for valid license."""
        assert valid_license.is_valid is True

    def test_is_valid_false_expired(self, expired_license):
        """Test is_valid returns False for expired license."""
        assert expired_license.is_valid is False

    def test_days_until_expiry(self, valid_license):
        """Test days_until_expiry calculation."""
        days = valid_license.days_until_expiry
        assert 330 <= days <= 340

    def test_days_until_expiry_expired(self, expired_license):
        """Test days_until_expiry returns 0 for expired license."""
        assert expired_license.days_until_expiry == 0

    def test_is_expiring_soon_false(self, valid_license):
        """Test is_expiring_soon returns False when far from expiry."""
        assert valid_license.is_expiring_soon is False

    def test_is_expiring_soon_true(self):
        """Test is_expiring_soon returns True within 30 days."""
        now = datetime.now(timezone.utc)
        license_info = LicenseInfo(
            license_id="EXPIRING-789",
            edition=LicenseEdition.ENTERPRISE,
            organization="Expiring Org",
            issued_at=now - timedelta(days=335),
            expires_at=now + timedelta(days=15),
        )
        assert license_info.is_expiring_soon is True

    def test_has_feature_true(self, valid_license):
        """Test has_feature returns True for included feature."""
        assert valid_license.has_feature("graphrag_advanced") is True

    def test_has_feature_false(self, valid_license):
        """Test has_feature returns False for missing feature."""
        assert valid_license.has_feature("nonexistent_feature") is False

    def test_has_feature_enterprise_plus_all(self):
        """Test enterprise plus has all features."""
        now = datetime.now(timezone.utc)
        license_info = LicenseInfo(
            license_id="PLUS-123",
            edition=LicenseEdition.ENTERPRISE_PLUS,
            organization="Plus Org",
            issued_at=now,
            expires_at=now + timedelta(days=365),
        )
        assert license_info.has_feature("any_feature") is True

    def test_to_dict(self, valid_license):
        """Test to_dict serialization."""
        data = valid_license.to_dict()

        assert data["license_id"] == "TEST-123"
        assert data["edition"] == "enterprise"
        assert data["organization"] == "Test Org"
        assert "issued_at" in data
        assert "expires_at" in data

    def test_from_dict(self, valid_license):
        """Test from_dict deserialization."""
        data = valid_license.to_dict()
        restored = LicenseInfo.from_dict(data)

        assert restored.license_id == valid_license.license_id
        assert restored.edition == valid_license.edition
        assert restored.organization == valid_license.organization


class TestEditionFeatures:
    """Tests for edition feature sets."""

    def test_community_features_subset(self):
        """Test community features are subset of enterprise."""
        community = EDITION_FEATURES[LicenseEdition.COMMUNITY]
        enterprise = EDITION_FEATURES[LicenseEdition.ENTERPRISE]
        assert community.issubset(enterprise)

    def test_enterprise_features_subset(self):
        """Test enterprise features are subset of enterprise plus."""
        enterprise = EDITION_FEATURES[LicenseEdition.ENTERPRISE]
        plus = EDITION_FEATURES[LicenseEdition.ENTERPRISE_PLUS]
        assert enterprise.issubset(plus)

    def test_air_gap_enterprise_plus_only(self):
        """Test air_gap_deployment is enterprise plus only."""
        assert "air_gap_deployment" not in EDITION_FEATURES[LicenseEdition.COMMUNITY]
        assert "air_gap_deployment" not in EDITION_FEATURES[LicenseEdition.ENTERPRISE]
        assert "air_gap_deployment" in EDITION_FEATURES[LicenseEdition.ENTERPRISE_PLUS]

    def test_fips_enterprise_plus_only(self):
        """Test fips_compliance is enterprise plus only."""
        assert "fips_compliance" not in EDITION_FEATURES[LicenseEdition.COMMUNITY]
        assert "fips_compliance" not in EDITION_FEATURES[LicenseEdition.ENTERPRISE]
        assert "fips_compliance" in EDITION_FEATURES[LicenseEdition.ENTERPRISE_PLUS]


class TestLicenseService:
    """Tests for LicenseService."""

    def test_no_license_returns_community(self):
        """Test no license key returns community edition."""
        service = LicenseService(license_key="")
        assert service.edition == LicenseEdition.COMMUNITY

    def test_is_licensed_false_no_key(self):
        """Test is_licensed returns False without license key."""
        service = LicenseService(license_key="")
        assert service.is_licensed is False

    def test_has_feature_community(self):
        """Test community edition has basic features."""
        service = LicenseService(license_key="")
        assert service.has_feature("graphrag_basic") is True
        assert service.has_feature("vulnerability_detection") is True

    def test_has_feature_community_missing(self):
        """Test community edition lacks enterprise features."""
        service = LicenseService(license_key="")
        assert service.has_feature("graphrag_advanced") is False
        assert service.has_feature("sso_saml") is False

    def test_require_feature_raises(self):
        """Test require_feature raises for missing feature."""
        service = LicenseService(license_key="")

        with pytest.raises(LicenseValidationError) as exc_info:
            service.require_feature("sso_saml")

        assert exc_info.value.code == "FEATURE_NOT_LICENSED"

    def test_require_edition_raises(self):
        """Test require_edition raises for insufficient edition."""
        service = LicenseService(license_key="")

        with pytest.raises(LicenseValidationError) as exc_info:
            service.require_edition(LicenseEdition.ENTERPRISE)

        assert exc_info.value.code == "EDITION_REQUIRED"

    def test_get_status_no_license(self):
        """Test get_status with no license."""
        service = LicenseService(license_key="")
        status = service.get_status()

        assert status["licensed"] is False
        assert status["edition"] == "community"

    def test_invalid_license_format(self):
        """Test invalid license format."""
        service = LicenseService(license_key="invalid-license", offline_mode=True)

        with pytest.raises(LicenseValidationError) as exc_info:
            service.get_license_info()

        assert exc_info.value.code == "INVALID_FORMAT"


class TestLicenseServiceGlobal:
    """Tests for global license service instance."""

    def test_get_license_service(self):
        """Test get_license_service returns instance."""
        service = get_license_service()
        assert isinstance(service, LicenseService)

    def test_set_license_service(self):
        """Test set_license_service replaces instance."""
        mock_service = MagicMock(spec=LicenseService)
        set_license_service(mock_service)

        service = get_license_service()
        assert service is mock_service

        # Reset
        set_license_service(None)


class TestLicenseValidationError:
    """Tests for LicenseValidationError."""

    def test_error_message(self):
        """Test error has message."""
        error = LicenseValidationError("Test error", code="TEST_CODE")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.code == "TEST_CODE"

    def test_default_code(self):
        """Test default error code."""
        error = LicenseValidationError("Test error")
        assert error.code == "INVALID_LICENSE"
