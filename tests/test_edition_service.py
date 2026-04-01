"""
Project Aura - Edition Service Tests

Tests for edition detection and license management.

See ADR-049: Self-Hosted Deployment Strategy
"""

import os
import platform
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services.edition_service import (
    EDITION_FEATURES,
    Edition,
    EditionService,
    LicenseInfo,
)

# These tests require pytest-forked for proper isolation due to FastAPI router state.
# On Linux (CI), pytest-forked causes router registration issues (404 errors).
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestEdition:
    """Tests for Edition enum."""

    def test_edition_values(self):
        """Test Edition enum values."""
        assert Edition.COMMUNITY.value == "community"
        assert Edition.ENTERPRISE.value == "enterprise"
        assert Edition.ENTERPRISE_PLUS.value == "enterprise_plus"


class TestLicenseInfo:
    """Tests for LicenseInfo dataclass."""

    def test_license_info_creation(self):
        """Test creating LicenseInfo."""
        now = datetime.now(timezone.utc)
        license_info = LicenseInfo(
            license_key="AURA-ENT-ACME-XXXX",
            edition=Edition.ENTERPRISE,
            organization="ACME Corp",
            issued_at=now,
            expires_at=None,
        )
        assert license_info.edition == Edition.ENTERPRISE
        assert license_info.organization == "ACME Corp"
        assert license_info.is_valid is True

    def test_is_expired_no_expiry(self):
        """Test license with no expiry is never expired."""
        license_info = LicenseInfo(
            license_key="test",
            edition=Edition.COMMUNITY,
            organization="Test",
            issued_at=datetime.now(timezone.utc),
            expires_at=None,
        )
        assert license_info.is_expired() is False

    def test_is_expired_future(self):
        """Test license with future expiry is not expired."""
        from datetime import timedelta

        license_info = LicenseInfo(
            license_key="test",
            edition=Edition.ENTERPRISE,
            organization="Test",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        assert license_info.is_expired() is False

    def test_is_expired_past(self):
        """Test license with past expiry is expired."""
        from datetime import timedelta

        license_info = LicenseInfo(
            license_key="test",
            edition=Edition.ENTERPRISE,
            organization="Test",
            issued_at=datetime.now(timezone.utc) - timedelta(days=400),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert license_info.is_expired() is True

    def test_to_dict_masks_key(self):
        """Test to_dict masks the license key."""
        license_info = LicenseInfo(
            license_key="AURA-ENT-ACMECORP123-XXXXXXXX",
            edition=Edition.ENTERPRISE,
            organization="ACME",
            issued_at=datetime.now(timezone.utc),
            expires_at=None,
        )
        data = license_info.to_dict()
        assert data["license_key"] == "AURA...XXXX"
        assert "ACMECORP" not in data["license_key"]


class TestEditionFeatures:
    """Tests for EDITION_FEATURES configuration."""

    def test_community_features_subset(self):
        """Test Community features are subset of Enterprise."""
        community = set(EDITION_FEATURES[Edition.COMMUNITY])
        enterprise = set(EDITION_FEATURES[Edition.ENTERPRISE])
        assert community.issubset(enterprise)

    def test_enterprise_features_subset(self):
        """Test Enterprise features are subset of Enterprise+."""
        enterprise = set(EDITION_FEATURES[Edition.ENTERPRISE])
        enterprise_plus = set(EDITION_FEATURES[Edition.ENTERPRISE_PLUS])
        assert enterprise.issubset(enterprise_plus)

    def test_community_has_basic_features(self):
        """Test Community has basic features."""
        features = EDITION_FEATURES[Edition.COMMUNITY]
        assert "repository_onboarding" in features
        assert "code_search" in features
        assert "chat_assistant" in features

    def test_enterprise_has_advanced_features(self):
        """Test Enterprise has advanced features."""
        features = EDITION_FEATURES[Edition.ENTERPRISE]
        assert "autonomous_patching" in features
        assert "custom_agents" in features
        assert "sso_integration" in features

    def test_enterprise_plus_has_govcloud(self):
        """Test Enterprise+ has GovCloud features."""
        features = EDITION_FEATURES[Edition.ENTERPRISE_PLUS]
        assert "govcloud_support" in features
        assert "cmmc_compliance" in features
        assert "air_gapped_deployment" in features


class TestEditionService:
    """Tests for EditionService."""

    @pytest.fixture
    def service(self):
        """Create fresh EditionService for each test."""
        return EditionService()

    def test_default_edition_is_community(self, service):
        """Test default edition is Community."""
        with patch.dict(os.environ, {}, clear=True):
            edition = service.get_edition()
            assert edition == Edition.COMMUNITY

    def test_edition_from_env_enterprise(self, service):
        """Test edition from AURA_EDITION env var."""
        with patch.dict(os.environ, {"AURA_EDITION": "enterprise"}):
            service._edition = None  # Clear cached value
            edition = service.get_edition()
            assert edition == Edition.ENTERPRISE

    def test_edition_from_env_enterprise_plus(self, service):
        """Test enterprise+ edition from env."""
        with patch.dict(os.environ, {"AURA_EDITION": "enterprise_plus"}):
            service._edition = None
            edition = service.get_edition()
            assert edition == Edition.ENTERPRISE_PLUS

    def test_is_self_hosted(self, service):
        """Test is_self_hosted detection."""
        with patch.dict(os.environ, {"CLOUD_PROVIDER": "self_hosted"}):
            assert service.is_self_hosted() is True

        with patch.dict(os.environ, {"CLOUD_PROVIDER": "aws"}):
            assert service.is_self_hosted() is False

    def test_has_feature_community(self, service):
        """Test feature check for Community edition."""
        with patch.dict(os.environ, {"AURA_EDITION": "community"}):
            service._edition = None
            assert service.has_feature("code_search") is True
            assert service.has_feature("autonomous_patching") is False
            assert service.has_feature("govcloud_support") is False

    def test_has_feature_enterprise(self, service):
        """Test feature check for Enterprise edition."""
        with patch.dict(os.environ, {"AURA_EDITION": "enterprise"}):
            service._edition = None
            assert service.has_feature("code_search") is True
            assert service.has_feature("autonomous_patching") is True
            assert service.has_feature("govcloud_support") is False

    def test_has_feature_enterprise_plus(self, service):
        """Test feature check for Enterprise+ edition."""
        with patch.dict(os.environ, {"AURA_EDITION": "enterprise_plus"}):
            service._edition = None
            assert service.has_feature("code_search") is True
            assert service.has_feature("autonomous_patching") is True
            assert service.has_feature("govcloud_support") is True

    def test_get_edition_info(self, service):
        """Test get_edition_info returns complete info."""
        with patch.dict(os.environ, {"AURA_EDITION": "enterprise"}):
            service._edition = None
            info = service.get_edition_info()

            assert info["edition"] == "enterprise"
            assert "features" in info
            assert info["license_required"] is True
            assert isinstance(info["feature_count"], int)

    def test_validate_license_invalid_format(self, service):
        """Test license validation with invalid format."""
        license_info = service.validate_license("short")
        assert license_info.is_valid is False
        assert "format" in license_info.validation_error.lower()

    def test_validate_license_invalid_prefix(self, service):
        """Test license validation with invalid prefix."""
        license_info = service.validate_license("INVALID-ENT-ACME-XXXX-YYYY")
        assert license_info.is_valid is False
        assert "prefix" in license_info.validation_error.lower()

    def test_validate_license_valid_enterprise(self, service):
        """Test license validation for valid enterprise key."""
        license_info = service.validate_license("AURA-ENT-ACMECORP-XXXX")
        assert license_info.is_valid is True
        assert license_info.edition == Edition.ENTERPRISE
        assert license_info.organization == "ACMECORP"

    def test_validate_license_valid_enterprise_plus(self, service):
        """Test license validation for valid enterprise+ key."""
        license_info = service.validate_license("AURA-ENTP-GOVORG-XXXX")
        assert license_info.is_valid is True
        assert license_info.edition == Edition.ENTERPRISE_PLUS

    def test_clear_license(self, service):
        """Test clearing license."""
        # Use a valid license key
        license_info = service.validate_license("AURA-ENT-ACMECORP1234-XXXX")
        assert license_info.is_valid is True
        assert service.get_license_info() is not None

        service.clear_license()
        assert service.get_license_info() is None


class TestEditionEndpoints:
    """Tests for edition API endpoints."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app with edition router."""
        from src.api.edition_endpoints import router

        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_get_edition(self, client):
        """Test GET /edition endpoint."""
        response = client.get("/edition")
        assert response.status_code == 200

        data = response.json()
        assert "edition" in data
        assert "features" in data
        assert "is_self_hosted" in data

    def test_get_features(self, client):
        """Test GET /edition/features endpoint."""
        response = client.get("/edition/features")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_check_feature_available(self, client):
        """Test POST /edition/features/check for available feature."""
        response = client.post(
            "/edition/features/check",
            json={"feature": "code_search"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["feature"] == "code_search"
        assert data["available"] is True

    def test_check_feature_unavailable(self, client):
        """Test POST /edition/features/check for unavailable feature."""
        with patch.dict(os.environ, {"AURA_EDITION": "community"}):
            # Force service reset
            from src.services import edition_service

            edition_service._edition_service = None

            response = client.post(
                "/edition/features/check",
                json={"feature": "govcloud_support"},
            )
            assert response.status_code == 200

            data = response.json()
            assert data["feature"] == "govcloud_support"
            assert data["available"] is False
            assert data["requires_upgrade"] is True

    def test_get_license_no_license(self, client):
        """Test GET /edition/license with no license."""
        # Force service reset
        from src.services import edition_service

        edition_service._edition_service = EditionService()

        response = client.get("/edition/license")
        assert response.status_code == 200
        assert response.json() is None

    def test_validate_license_success(self, client):
        """Test POST /edition/license/validate with valid key."""
        response = client.post(
            "/edition/license/validate",
            json={"license_key": "AURA-ENT-TESTORG-XXXX"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["is_valid"] is True
        assert data["edition"] == "enterprise"

    def test_validate_license_failure_short(self, client):
        """Test POST /edition/license/validate with too short key."""
        response = client.post(
            "/edition/license/validate",
            json={"license_key": "short"},  # Way too short (min_length=20)
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_validate_license_failure_invalid_format(self, client):
        """Test POST /edition/license/validate with invalid format."""
        response = client.post(
            "/edition/license/validate",
            json={"license_key": "INVALID-ENT-TESTORG-XXXXXXXXX"},  # Wrong prefix
        )
        assert response.status_code == 400  # Service returns 400 for invalid prefix

    def test_clear_license(self, client):
        """Test DELETE /edition/license endpoint."""
        # First validate a license
        client.post(
            "/edition/license/validate",
            json={"license_key": "AURA-ENT-TESTORG-XXXX"},
        )

        # Then clear it
        response = client.delete("/edition/license")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_get_upgrade_info_community(self, client):
        """Test GET /edition/upgrade-info for community edition."""
        with patch.dict(os.environ, {"AURA_EDITION": "community"}):
            from src.services import edition_service

            edition_service._edition_service = None

            response = client.get("/edition/upgrade-info")
            assert response.status_code == 200

            data = response.json()
            assert data["current_edition"] == "community"
            assert len(data["available_upgrades"]) == 2

    def test_get_upgrade_info_enterprise_plus(self, client):
        """Test GET /edition/upgrade-info for enterprise+ edition."""
        with patch.dict(os.environ, {"AURA_EDITION": "enterprise_plus"}):
            from src.services import edition_service

            edition_service._edition_service = None

            response = client.get("/edition/upgrade-info")
            assert response.status_code == 200

            data = response.json()
            assert data["current_edition"] == "enterprise_plus"
            assert len(data["available_upgrades"]) == 0  # No upgrades available
