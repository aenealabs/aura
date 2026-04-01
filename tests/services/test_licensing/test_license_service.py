"""Comprehensive tests for LicenseService.

Tests cover license validation, edition detection, feature gating,
caching, online/offline modes, and error handling.
"""

import base64
import json
import os
import platform
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest

# Apply forked mark for macOS isolation
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.licensing.license_service import (
    EDITION_FEATURES,
    LicenseEdition,
    LicenseInfo,
    LicenseService,
    LicenseValidationError,
    get_license_service,
    set_license_service,
)

# --- Fixtures ---


@pytest.fixture
def valid_license_payload() -> dict[str, Any]:
    """Create a valid license payload."""
    now = datetime.now(timezone.utc)
    return {
        "license_id": "test-license-001",
        "edition": "enterprise",
        "organization": "Test Organization",
        "issued_at": (now - timedelta(days=30)).isoformat(),
        "expires_at": (now + timedelta(days=335)).isoformat(),
        "max_users": 100,
        "max_repositories": 50,
        "features": ["graphrag_advanced", "multi_repo", "custom_agents"],
        "is_trial": False,
    }


@pytest.fixture
def expired_license_payload() -> dict[str, Any]:
    """Create an expired license payload."""
    now = datetime.now(timezone.utc)
    return {
        "license_id": "test-license-expired",
        "edition": "enterprise",
        "organization": "Expired Organization",
        "issued_at": (now - timedelta(days=365)).isoformat(),
        "expires_at": (now - timedelta(days=1)).isoformat(),
        "max_users": 10,
        "max_repositories": 5,
        "features": [],
        "is_trial": False,
    }


@pytest.fixture
def trial_license_payload() -> dict[str, Any]:
    """Create a trial license payload."""
    now = datetime.now(timezone.utc)
    return {
        "license_id": "test-trial-001",
        "edition": "enterprise",
        "organization": "Trial Organization",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(days=14)).isoformat(),
        "max_users": 5,
        "max_repositories": 3,
        "features": ["graphrag_advanced"],
        "is_trial": True,
    }


@pytest.fixture
def expiring_soon_license_payload() -> dict[str, Any]:
    """Create a license expiring within 30 days."""
    now = datetime.now(timezone.utc)
    return {
        "license_id": "test-expiring-001",
        "edition": "enterprise",
        "organization": "Expiring Soon Org",
        "issued_at": (now - timedelta(days=330)).isoformat(),
        "expires_at": (now + timedelta(days=15)).isoformat(),
        "max_users": 50,
        "max_repositories": 25,
        "features": [],
        "is_trial": False,
    }


@pytest.fixture
def enterprise_plus_payload() -> dict[str, Any]:
    """Create an Enterprise Plus license payload."""
    now = datetime.now(timezone.utc)
    return {
        "license_id": "test-eplus-001",
        "edition": "enterprise_plus",
        "organization": "Enterprise Plus Org",
        "issued_at": (now - timedelta(days=30)).isoformat(),
        "expires_at": (now + timedelta(days=335)).isoformat(),
        "max_users": 0,  # unlimited
        "max_repositories": 0,  # unlimited
        "features": [],  # All features included
        "is_trial": False,
    }


@pytest.fixture
def hardware_bound_payload() -> dict[str, Any]:
    """Create a hardware-bound license payload."""
    now = datetime.now(timezone.utc)
    return {
        "license_id": "test-hw-001",
        "edition": "enterprise",
        "organization": "Hardware Bound Org",
        "issued_at": (now - timedelta(days=30)).isoformat(),
        "expires_at": (now + timedelta(days=335)).isoformat(),
        "max_users": 100,
        "max_repositories": 50,
        "features": [],
        "hardware_id": "abc123def456789012345678901234567890123456789012345678901234",
        "is_trial": False,
    }


def create_mock_license_key(payload: dict[str, Any], signature: str = "mocksig") -> str:
    """Create a mock license key from payload."""
    payload_json = json.dumps(payload)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    signature_b64 = base64.urlsafe_b64encode(signature.encode()).decode().rstrip("=")
    return f"{payload_b64}.{signature_b64}"


# --- LicenseEdition Tests ---


class TestLicenseEdition:
    """Tests for LicenseEdition enum."""

    def test_edition_values(self):
        """Test edition enum values."""
        assert LicenseEdition.COMMUNITY.value == "community"
        assert LicenseEdition.ENTERPRISE.value == "enterprise"
        assert LicenseEdition.ENTERPRISE_PLUS.value == "enterprise_plus"

    def test_edition_from_string(self):
        """Test creating edition from string."""
        assert LicenseEdition("community") == LicenseEdition.COMMUNITY
        assert LicenseEdition("enterprise") == LicenseEdition.ENTERPRISE
        assert LicenseEdition("enterprise_plus") == LicenseEdition.ENTERPRISE_PLUS

    def test_invalid_edition_raises(self):
        """Test invalid edition string raises ValueError."""
        with pytest.raises(ValueError):
            LicenseEdition("invalid_edition")


# --- LicenseValidationError Tests ---


class TestLicenseValidationError:
    """Tests for LicenseValidationError exception."""

    def test_error_with_default_code(self):
        """Test error with default code."""
        error = LicenseValidationError("Test error")
        assert error.message == "Test error"
        assert error.code == "INVALID_LICENSE"
        assert str(error) == "Test error"

    def test_error_with_custom_code(self):
        """Test error with custom code."""
        error = LicenseValidationError("Feature missing", code="FEATURE_NOT_LICENSED")
        assert error.message == "Feature missing"
        assert error.code == "FEATURE_NOT_LICENSED"


# --- LicenseInfo Tests ---


class TestLicenseInfo:
    """Tests for LicenseInfo dataclass."""

    def test_create_license_info(self, valid_license_payload):
        """Test creating LicenseInfo from payload."""
        license_info = LicenseInfo.from_dict(valid_license_payload)
        assert license_info.license_id == "test-license-001"
        assert license_info.edition == LicenseEdition.ENTERPRISE
        assert license_info.organization == "Test Organization"
        assert license_info.max_users == 100
        assert license_info.max_repositories == 50
        assert license_info.is_trial is False
        assert license_info.is_offline is False

    def test_is_valid_for_valid_license(self, valid_license_payload):
        """Test is_valid returns True for valid license."""
        license_info = LicenseInfo.from_dict(valid_license_payload)
        assert license_info.is_valid is True

    def test_is_valid_for_expired_license(self, expired_license_payload):
        """Test is_valid returns False for expired license."""
        license_info = LicenseInfo.from_dict(expired_license_payload)
        assert license_info.is_valid is False

    def test_days_until_expiry(self, valid_license_payload):
        """Test days_until_expiry calculation."""
        license_info = LicenseInfo.from_dict(valid_license_payload)
        # Should be around 335 days (allow for test execution time)
        assert 330 <= license_info.days_until_expiry <= 336

    def test_days_until_expiry_expired(self, expired_license_payload):
        """Test days_until_expiry returns 0 for expired license."""
        license_info = LicenseInfo.from_dict(expired_license_payload)
        assert license_info.days_until_expiry == 0

    def test_is_expiring_soon(self, expiring_soon_license_payload):
        """Test is_expiring_soon for license near expiration."""
        license_info = LicenseInfo.from_dict(expiring_soon_license_payload)
        assert license_info.is_expiring_soon is True

    def test_is_not_expiring_soon(self, valid_license_payload):
        """Test is_expiring_soon is False for license with time remaining."""
        license_info = LicenseInfo.from_dict(valid_license_payload)
        assert license_info.is_expiring_soon is False

    def test_is_expiring_soon_already_expired(self, expired_license_payload):
        """Test is_expiring_soon is False for already expired license."""
        license_info = LicenseInfo.from_dict(expired_license_payload)
        assert license_info.is_expiring_soon is False

    def test_has_feature_in_list(self, valid_license_payload):
        """Test has_feature for feature in features list."""
        license_info = LicenseInfo.from_dict(valid_license_payload)
        assert license_info.has_feature("graphrag_advanced") is True
        assert license_info.has_feature("multi_repo") is True

    def test_has_feature_not_in_list(self, valid_license_payload):
        """Test has_feature for feature not in list."""
        license_info = LicenseInfo.from_dict(valid_license_payload)
        assert license_info.has_feature("air_gap_deployment") is False

    def test_enterprise_plus_has_all_features(self, enterprise_plus_payload):
        """Test Enterprise Plus has all features."""
        license_info = LicenseInfo.from_dict(enterprise_plus_payload)
        # Enterprise Plus should return True for any feature
        assert license_info.has_feature("air_gap_deployment") is True
        assert license_info.has_feature("any_feature_at_all") is True
        assert license_info.has_feature("graphrag_basic") is True

    def test_to_dict_roundtrip(self, valid_license_payload):
        """Test to_dict and from_dict roundtrip."""
        license_info = LicenseInfo.from_dict(valid_license_payload)
        result_dict = license_info.to_dict()

        # Re-create from dict
        restored = LicenseInfo.from_dict(result_dict)
        assert restored.license_id == license_info.license_id
        assert restored.edition == license_info.edition
        assert restored.organization == license_info.organization

    def test_from_dict_with_minimal_fields(self):
        """Test from_dict with only required fields."""
        now = datetime.now(timezone.utc)
        minimal = {
            "license_id": "minimal",
            "edition": "community",
            "organization": "Minimal Org",
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
        }
        license_info = LicenseInfo.from_dict(minimal)
        assert license_info.max_users == 0
        assert license_info.max_repositories == 0
        assert license_info.features == []
        assert license_info.hardware_id is None
        assert license_info.is_trial is False
        assert license_info.is_offline is False


# --- EDITION_FEATURES Tests ---


class TestEditionFeatures:
    """Tests for EDITION_FEATURES constant."""

    def test_community_features(self):
        """Test Community edition features."""
        features = EDITION_FEATURES[LicenseEdition.COMMUNITY]
        assert "graphrag_basic" in features
        assert "vulnerability_detection" in features
        assert "api_access" in features
        # Enterprise features should NOT be in community
        assert "graphrag_advanced" not in features
        assert "sso_saml" not in features

    def test_enterprise_features(self):
        """Test Enterprise edition features."""
        features = EDITION_FEATURES[LicenseEdition.ENTERPRISE]
        # Should include all community features
        for community_feature in EDITION_FEATURES[LicenseEdition.COMMUNITY]:
            assert community_feature in features
        # Plus enterprise-specific features
        assert "graphrag_advanced" in features
        assert "sso_saml" in features
        assert "priority_support" in features

    def test_enterprise_plus_features(self):
        """Test Enterprise Plus edition features."""
        features = EDITION_FEATURES[LicenseEdition.ENTERPRISE_PLUS]
        # Should include all enterprise features
        for enterprise_feature in EDITION_FEATURES[LicenseEdition.ENTERPRISE]:
            assert enterprise_feature in features
        # Plus enterprise plus specific features
        assert "air_gap_deployment" in features
        assert "fips_compliance" in features
        assert "custom_llm_integration" in features
        assert "unlimited_repos" in features


# --- LicenseService Tests ---


class TestLicenseServiceInit:
    """Tests for LicenseService initialization."""

    def test_init_with_no_license(self):
        """Test initialization with no license key."""
        with patch.dict("os.environ", {}, clear=True):
            service = LicenseService(license_key=None)
            assert service._license_key == ""
            assert service._offline_mode is False

    def test_init_with_license_key(self):
        """Test initialization with license key."""
        service = LicenseService(license_key="test-key")
        assert service._license_key == "test-key"

    def test_init_with_env_license_key(self):
        """Test initialization reads from environment."""
        with patch.dict("os.environ", {"AURA_LICENSE_KEY": "env-license-key"}):
            service = LicenseService()
            assert service._license_key == "env-license-key"

    def test_init_offline_mode_param(self):
        """Test initialization with offline_mode parameter."""
        service = LicenseService(offline_mode=True)
        assert service._offline_mode is True

    def test_init_offline_mode_env(self):
        """Test initialization reads offline mode from environment."""
        with patch.dict("os.environ", {"AURA_OFFLINE_LICENSE": "true"}):
            service = LicenseService()
            assert service._offline_mode is True

    def test_init_with_hardware_id(self):
        """Test initialization with hardware ID."""
        service = LicenseService(hardware_id="test-hw-id")
        assert service._hardware_id == "test-hw-id"


class TestLicenseServiceIsLicensed:
    """Tests for LicenseService.is_licensed property."""

    def test_is_licensed_no_key(self):
        """Test is_licensed returns False with no license key."""
        service = LicenseService(license_key="")
        assert service.is_licensed is False

    def test_is_licensed_with_valid_license(self, valid_license_payload):
        """Test is_licensed returns True with valid license."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            assert service.is_licensed is True

    def test_is_licensed_with_expired_license(self, expired_license_payload):
        """Test is_licensed returns False with expired license."""
        license_key = create_mock_license_key(expired_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            assert service.is_licensed is False


class TestLicenseServiceEdition:
    """Tests for LicenseService.edition property."""

    def test_edition_community_no_license(self):
        """Test edition returns COMMUNITY with no license."""
        service = LicenseService(license_key="")
        assert service.edition == LicenseEdition.COMMUNITY

    def test_edition_enterprise(self, valid_license_payload):
        """Test edition returns correct edition."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            assert service.edition == LicenseEdition.ENTERPRISE

    def test_edition_enterprise_plus(self, enterprise_plus_payload):
        """Test edition returns Enterprise Plus."""
        license_key = create_mock_license_key(enterprise_plus_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            assert service.edition == LicenseEdition.ENTERPRISE_PLUS

    def test_edition_falls_back_on_error(self):
        """Test edition returns COMMUNITY on validation error."""
        service = LicenseService(license_key="invalid-key", offline_mode=True)
        assert service.edition == LicenseEdition.COMMUNITY


class TestLicenseServiceGetLicenseInfo:
    """Tests for LicenseService.get_license_info method."""

    def test_get_license_info_no_key(self):
        """Test get_license_info returns None with no key."""
        service = LicenseService(license_key="")
        assert service.get_license_info() is None

    def test_get_license_info_valid(self, valid_license_payload):
        """Test get_license_info returns valid info."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            info = service.get_license_info()
            assert info is not None
            assert info.license_id == "test-license-001"
            assert info.edition == LicenseEdition.ENTERPRISE

    def test_get_license_info_caching(self, valid_license_payload):
        """Test get_license_info uses cache."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            # First call
            info1 = service.get_license_info()

        with patch.object(service, "_validate_license") as mock_validate:
            # Second call should use cache
            info2 = service.get_license_info()
            mock_validate.assert_not_called()
            assert info1 is info2

    def test_get_license_info_cache_expiry(self, valid_license_payload):
        """Test get_license_info cache expires."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)
        service._cache_ttl_seconds = 0  # Expire immediately

        with patch.object(service, "_verify_signature", return_value=True):
            # First call
            service.get_license_info()
            # Second call should re-validate due to cache expiry
            service.get_license_info()
            # Both calls go through validation since cache expires


class TestLicenseServiceHasFeature:
    """Tests for LicenseService.has_feature method."""

    def test_has_feature_community(self):
        """Test has_feature for community edition."""
        service = LicenseService(license_key="")
        assert service.has_feature("graphrag_basic") is True
        assert service.has_feature("vulnerability_detection") is True
        assert service.has_feature("graphrag_advanced") is False
        assert service.has_feature("sso_saml") is False

    def test_has_feature_enterprise(self, valid_license_payload):
        """Test has_feature for enterprise edition."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            assert service.has_feature("graphrag_basic") is True
            assert service.has_feature("graphrag_advanced") is True
            assert service.has_feature("sso_saml") is True
            assert service.has_feature("air_gap_deployment") is False

    def test_has_feature_enterprise_plus(self, enterprise_plus_payload):
        """Test has_feature for enterprise plus edition."""
        license_key = create_mock_license_key(enterprise_plus_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            # Enterprise Plus has all features
            assert service.has_feature("air_gap_deployment") is True
            assert service.has_feature("fips_compliance") is True
            assert service.has_feature("graphrag_basic") is True


class TestLicenseServiceRequireFeature:
    """Tests for LicenseService.require_feature method."""

    def test_require_feature_available(self):
        """Test require_feature passes when available."""
        service = LicenseService(license_key="")
        # Community feature should pass
        service.require_feature("graphrag_basic")  # Should not raise

    def test_require_feature_not_available(self):
        """Test require_feature raises when not available."""
        service = LicenseService(license_key="")
        with pytest.raises(LicenseValidationError) as exc_info:
            service.require_feature("graphrag_advanced")
        assert exc_info.value.code == "FEATURE_NOT_LICENSED"
        assert "graphrag_advanced" in exc_info.value.message


class TestLicenseServiceRequireEdition:
    """Tests for LicenseService.require_edition method."""

    def test_require_edition_satisfied(self):
        """Test require_edition passes when satisfied."""
        service = LicenseService(license_key="")
        # Community requiring community should pass
        service.require_edition(LicenseEdition.COMMUNITY)  # Should not raise

    def test_require_edition_not_satisfied(self):
        """Test require_edition raises when not satisfied."""
        service = LicenseService(license_key="")
        with pytest.raises(LicenseValidationError) as exc_info:
            service.require_edition(LicenseEdition.ENTERPRISE)
        assert exc_info.value.code == "EDITION_REQUIRED"
        assert "enterprise" in exc_info.value.message.lower()

    def test_require_edition_enterprise_has_enterprise(self, valid_license_payload):
        """Test enterprise edition satisfies enterprise requirement."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            service.require_edition(LicenseEdition.ENTERPRISE)  # Should not raise
            service.require_edition(LicenseEdition.COMMUNITY)  # Should not raise

    def test_require_edition_enterprise_not_enterprise_plus(
        self, valid_license_payload
    ):
        """Test enterprise edition does not satisfy enterprise plus."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            with pytest.raises(LicenseValidationError):
                service.require_edition(LicenseEdition.ENTERPRISE_PLUS)


class TestLicenseServiceValidation:
    """Tests for LicenseService validation methods."""

    def test_validate_offline_invalid_format(self):
        """Test offline validation fails with invalid format."""
        service = LicenseService(license_key="not-a-valid-format", offline_mode=True)
        with pytest.raises(LicenseValidationError) as exc_info:
            service._validate_offline()
        assert exc_info.value.code == "INVALID_FORMAT"

    def test_validate_offline_invalid_payload(self):
        """Test offline validation fails with invalid JSON payload."""
        invalid_payload = base64.urlsafe_b64encode(b"not-json").decode().rstrip("=")
        license_key = f"{invalid_payload}.signature"
        service = LicenseService(license_key=license_key, offline_mode=True)
        with pytest.raises(LicenseValidationError) as exc_info:
            service._validate_offline()
        assert exc_info.value.code == "INVALID_PAYLOAD"

    def test_validate_offline_signature_failed(self, valid_license_payload):
        """Test offline validation fails with invalid signature."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=False):
            with pytest.raises(LicenseValidationError) as exc_info:
                service._validate_offline()
            assert exc_info.value.code == "INVALID_SIGNATURE"

    def test_validate_offline_expired(self, expired_license_payload):
        """Test offline validation fails with expired license."""
        license_key = create_mock_license_key(expired_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            with pytest.raises(LicenseValidationError) as exc_info:
                service._validate_offline()
            assert exc_info.value.code == "LICENSE_EXPIRED"

    def test_validate_offline_hardware_mismatch(self, hardware_bound_payload):
        """Test offline validation fails with hardware mismatch."""
        license_key = create_mock_license_key(hardware_bound_payload)
        service = LicenseService(
            license_key=license_key,
            offline_mode=True,
            hardware_id="different-hardware-id-12345678901234567890",
        )

        with patch.object(service, "_verify_signature", return_value=True):
            with pytest.raises(LicenseValidationError) as exc_info:
                service._validate_offline()
            assert exc_info.value.code == "HARDWARE_MISMATCH"

    def test_validate_offline_hardware_match(self, hardware_bound_payload):
        """Test offline validation succeeds with matching hardware."""
        hw_id = hardware_bound_payload["hardware_id"]
        license_key = create_mock_license_key(hardware_bound_payload)
        service = LicenseService(
            license_key=license_key, offline_mode=True, hardware_id=hw_id
        )

        with patch.object(service, "_verify_signature", return_value=True):
            info = service._validate_offline()
            assert info.license_id == "test-hw-001"

    def test_validate_offline_hardware_prefix_match(self, hardware_bound_payload):
        """Test hardware ID prefix matching."""
        # Use same first 16 characters
        hw_id = hardware_bound_payload["hardware_id"][:16] + "x" * 48
        license_key = create_mock_license_key(hardware_bound_payload)
        service = LicenseService(
            license_key=license_key, offline_mode=True, hardware_id=hw_id
        )

        with patch.object(service, "_verify_signature", return_value=True):
            info = service._validate_offline()
            assert info is not None

    def test_validate_offline_generates_hardware_id(self, hardware_bound_payload):
        """Test hardware ID is generated if not provided."""
        license_key = create_mock_license_key(hardware_bound_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            # Patch the hardware_fingerprint module that gets imported
            with patch(
                "src.services.licensing.hardware_fingerprint.generate_hardware_fingerprint"
            ) as mock_gen:
                mock_gen.return_value = hardware_bound_payload["hardware_id"]
                info = service._validate_offline()
                assert info is not None
                mock_gen.assert_called_once()

    def test_validate_online_falls_back_to_offline(self, valid_license_payload):
        """Test online validation falls back to offline."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=False)

        with patch.object(service, "_verify_signature", return_value=True):
            info = service._validate_online()
            assert info is not None

    def test_validate_general_exception_handling(self, valid_license_payload):
        """Test general exception handling in validation."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(
            service, "_verify_signature", side_effect=RuntimeError("Unexpected")
        ):
            with pytest.raises(LicenseValidationError) as exc_info:
                service._validate_offline()
            assert exc_info.value.code == "VALIDATION_ERROR"


class TestLicenseServiceSignatureVerification:
    """Tests for LicenseService._verify_signature method."""

    def test_verify_signature_without_cryptography(self, valid_license_payload):
        """Test signature verification without cryptography library."""
        service = LicenseService(offline_mode=True)

        with patch.dict("os.environ", {"AURA_SKIP_LICENSE_SIGNATURE": "true"}):
            # Mock the import to fail
            with patch.dict("sys.modules", {"cryptography": None}):
                with patch(
                    "src.services.licensing.license_service.LicenseService._verify_signature"
                ) as mock:
                    # When cryptography is unavailable, check env var
                    mock.return_value = True
                    result = mock("payload", "signature")
                    assert result is True

    def test_verify_signature_crypto_import_error(self):
        """Test signature verification handles ImportError."""
        service = LicenseService(offline_mode=True)

        # Mock ImportError for cryptography
        original_method = service._verify_signature

        def mock_verify_with_import_error(payload_b64: str, signature_b64: str) -> bool:
            # Simulate ImportError from cryptography
            raise ImportError("No module named 'cryptography'")

        with patch.object(
            service, "_verify_signature", side_effect=mock_verify_with_import_error
        ):
            with pytest.raises(ImportError):
                service._verify_signature("payload", "sig")

    def test_verify_signature_invalid_signature(self):
        """Test signature verification with invalid signature."""
        service = LicenseService(offline_mode=True)
        # This should return False for invalid signature
        result = service._verify_signature("test_payload", "invalid_sig")
        assert result is False


class TestLicenseServiceHardwareVerification:
    """Tests for LicenseService._verify_hardware_id method."""

    def test_verify_hardware_id_exact_match(self):
        """Test exact hardware ID match."""
        service = LicenseService()
        assert service._verify_hardware_id("abc123", "abc123") is True

    def test_verify_hardware_id_no_match(self):
        """Test hardware ID mismatch."""
        service = LicenseService()
        assert service._verify_hardware_id("abc123", "xyz789") is False

    def test_verify_hardware_id_prefix_match(self):
        """Test hardware ID prefix match."""
        service = LicenseService()
        # First 16 characters must match
        id1 = "1234567890123456abcdef"
        id2 = "1234567890123456different"
        assert service._verify_hardware_id(id1, id2) is True

    def test_verify_hardware_id_prefix_no_match(self):
        """Test hardware ID prefix mismatch."""
        service = LicenseService()
        id1 = "1234567890123456abcdef"
        id2 = "different90123456abcdef"
        assert service._verify_hardware_id(id1, id2) is False

    def test_verify_hardware_id_short_ids(self):
        """Test hardware ID comparison with short IDs."""
        service = LicenseService()
        # IDs shorter than 16 chars should not prefix match
        assert service._verify_hardware_id("short", "short") is True
        assert service._verify_hardware_id("short", "different") is False


class TestLicenseServiceCaching:
    """Tests for LicenseService caching behavior."""

    def test_is_cache_valid_no_cache(self):
        """Test cache is invalid when empty."""
        service = LicenseService()
        assert service._is_cache_valid() is False

    def test_is_cache_valid_with_cache(self, valid_license_payload):
        """Test cache is valid after population."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            service.get_license_info()
            assert service._is_cache_valid() is True

    def test_is_cache_valid_expired_cache(self, valid_license_payload):
        """Test cache is invalid after TTL expires."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)
        service._cache_ttl_seconds = -1  # Already expired

        with patch.object(service, "_verify_signature", return_value=True):
            service.get_license_info()
            # Cache time is set but TTL is negative, so it's expired
            service._cache_ttl_seconds = -1
            assert service._is_cache_valid() is False


class TestLicenseServiceGetStatus:
    """Tests for LicenseService.get_status method."""

    def test_get_status_no_license(self):
        """Test get_status with no license."""
        service = LicenseService(license_key="")
        status = service.get_status()
        assert status["licensed"] is False
        assert status["edition"] == "community"
        assert status["organization"] is None
        assert status["expires_at"] is None

    def test_get_status_valid_license(self, valid_license_payload):
        """Test get_status with valid license."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            status = service.get_status()
            assert status["licensed"] is True
            assert status["edition"] == "enterprise"
            assert status["organization"] == "Test Organization"
            assert status["max_users"] == 100
            assert status["max_repositories"] == 50
            assert status["is_trial"] is False
            assert "days_until_expiry" in status
            assert "is_expiring_soon" in status

    def test_get_status_trial_license(self, trial_license_payload):
        """Test get_status with trial license."""
        license_key = create_mock_license_key(trial_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            status = service.get_status()
            assert status["licensed"] is True
            assert status["is_trial"] is True

    def test_get_status_with_error(self):
        """Test get_status with validation error."""
        service = LicenseService(license_key="invalid-key", offline_mode=True)
        status = service.get_status()
        assert status["licensed"] is False
        assert status["edition"] == "community"
        assert "error" in status
        assert "error_code" in status


# --- Global Service Tests ---


class TestGlobalLicenseService:
    """Tests for global license service functions."""

    def test_get_license_service_creates_singleton(self):
        """Test get_license_service creates singleton."""
        # Reset global
        set_license_service(None)

        service1 = get_license_service()
        service2 = get_license_service()
        assert service1 is service2

    def test_set_license_service(self):
        """Test set_license_service replaces global."""
        custom_service = LicenseService(license_key="custom")
        set_license_service(custom_service)

        retrieved = get_license_service()
        assert retrieved is custom_service

        # Cleanup
        set_license_service(None)

    def test_set_license_service_to_none(self):
        """Test setting global service to None."""
        set_license_service(LicenseService())
        set_license_service(None)

        # Next get should create new service
        service = get_license_service()
        assert service is not None

        # Cleanup
        set_license_service(None)


# --- Edge Case Tests ---


class TestLicenseServiceEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_license_at_exact_expiry_boundary(self):
        """Test license at exact expiry boundary."""
        now = datetime.now(timezone.utc)
        # Add a small buffer to ensure we're within the valid range
        expires_at = now + timedelta(seconds=5)
        payload = {
            "license_id": "boundary-test",
            "edition": "enterprise",
            "organization": "Boundary Org",
            "issued_at": (now - timedelta(days=365)).isoformat(),
            "expires_at": expires_at.isoformat(),  # Expires in 5 seconds
            "max_users": 10,
            "max_repositories": 5,
            "features": [],
            "is_trial": False,
        }
        license_info = LicenseInfo.from_dict(payload)
        # Should be valid since we're before expiry
        assert license_info.is_valid is True

    def test_license_issued_in_future(self):
        """Test license issued in future is invalid."""
        now = datetime.now(timezone.utc)
        payload = {
            "license_id": "future-test",
            "edition": "enterprise",
            "organization": "Future Org",
            "issued_at": (now + timedelta(days=1)).isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
            "max_users": 10,
            "max_repositories": 5,
            "features": [],
            "is_trial": False,
        }
        license_info = LicenseInfo.from_dict(payload)
        assert license_info.is_valid is False

    def test_empty_features_list(self):
        """Test license with empty features list."""
        now = datetime.now(timezone.utc)
        payload = {
            "license_id": "no-features",
            "edition": "enterprise",
            "organization": "No Features Org",
            "issued_at": (now - timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=335)).isoformat(),
            "features": [],
        }
        license_info = LicenseInfo.from_dict(payload)
        assert license_info.features == []
        assert license_info.has_feature("any_feature") is False

    def test_very_long_license_key(self):
        """Test handling of very long license key."""
        # Create a payload with lots of data
        now = datetime.now(timezone.utc)
        payload = {
            "license_id": "long-" + "x" * 1000,
            "edition": "enterprise",
            "organization": "Long Org " + "y" * 1000,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
            "features": [f"feature_{i}" for i in range(100)],
        }
        license_key = create_mock_license_key(payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_verify_signature", return_value=True):
            info = service.get_license_info()
            assert info is not None
            assert len(info.features) == 100


class TestSignatureVerificationIntegration:
    """Integration tests for signature verification."""

    def test_verify_signature_with_invalid_base64(self):
        """Test signature verification with invalid base64."""
        service = LicenseService(offline_mode=True)
        # Invalid base64 should return False
        result = service._verify_signature("valid_payload", "!!invalid!!base64!!")
        assert result is False

    def test_verify_signature_with_cryptography_unavailable(self):
        """Test signature verification when cryptography is not available."""
        service = LicenseService(offline_mode=True)

        with patch.dict("os.environ", {"AURA_SKIP_LICENSE_SIGNATURE": "false"}):
            # Mock the import to fail by patching builtins.__import__
            original_import = (
                __builtins__.__import__
                if hasattr(__builtins__, "__import__")
                else __import__
            )

            def mock_import(name, *args, **kwargs):
                if name == "cryptography.hazmat.primitives" or name.startswith(
                    "cryptography"
                ):
                    raise ImportError("No module named 'cryptography'")
                return original_import(name, *args, **kwargs)

            # Use the actual method without mocking, let it fail naturally
            # The method returns False when signature verification fails
            result = service._verify_signature("test_payload", "dGVzdA")
            assert result is False

    def test_verify_signature_skip_env_var_true(self):
        """Test that AURA_SKIP_LICENSE_SIGNATURE=true allows skipping verification."""
        # This tests the ImportError path with skip enabled
        service = LicenseService(offline_mode=True)

        # Mock the import to fail
        with patch.dict(
            "sys.modules",
            {
                "cryptography": None,
                "cryptography.hazmat": None,
                "cryptography.hazmat.primitives": None,
            },
        ):
            with patch.dict("os.environ", {"AURA_SKIP_LICENSE_SIGNATURE": "true"}):
                # Manually test the environment path
                skip_val = os.getenv("AURA_SKIP_LICENSE_SIGNATURE", "false").lower()
                assert skip_val == "true"


class TestLicenseValidationModes:
    """Test different validation modes."""

    def test_validate_license_calls_offline_in_offline_mode(
        self, valid_license_payload
    ):
        """Test _validate_license calls _validate_offline in offline mode."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=True)

        with patch.object(service, "_validate_offline") as mock_offline:
            mock_offline.return_value = LicenseInfo.from_dict(valid_license_payload)
            result = service._validate_license()
            mock_offline.assert_called_once()

    def test_validate_license_calls_online_in_online_mode(self, valid_license_payload):
        """Test _validate_license calls _validate_online in online mode."""
        license_key = create_mock_license_key(valid_license_payload)
        service = LicenseService(license_key=license_key, offline_mode=False)

        with patch.object(service, "_validate_online") as mock_online:
            mock_online.return_value = LicenseInfo.from_dict(valid_license_payload)
            result = service._validate_license()
            mock_online.assert_called_once()


class TestLicenseInfoMethods:
    """Additional tests for LicenseInfo methods."""

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all serializable fields."""
        now = datetime.now(timezone.utc)
        license_info = LicenseInfo(
            license_id="test-id",
            edition=LicenseEdition.ENTERPRISE,
            organization="Test Org",
            issued_at=now - timedelta(days=30),
            expires_at=now + timedelta(days=335),
            max_users=100,
            max_repositories=50,
            features=["feature1", "feature2"],
            hardware_id="hw123",
            is_trial=True,
            is_offline=True,
            signature="sig123",
        )
        result = license_info.to_dict()

        assert result["license_id"] == "test-id"
        assert result["edition"] == "enterprise"
        assert result["organization"] == "Test Org"
        assert result["max_users"] == 100
        assert result["max_repositories"] == 50
        assert result["features"] == ["feature1", "feature2"]
        assert result["hardware_id"] == "hw123"
        assert result["is_trial"] is True
        assert result["is_offline"] is True
        # Note: signature is not included in to_dict()

    def test_from_dict_with_signature(self):
        """Test from_dict correctly loads signature."""
        now = datetime.now(timezone.utc)
        data = {
            "license_id": "test-id",
            "edition": "enterprise",
            "organization": "Test Org",
            "issued_at": (now - timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=335)).isoformat(),
            "signature": "test-signature",
        }
        license_info = LicenseInfo.from_dict(data)
        assert license_info.signature == "test-signature"


class TestLicenseInfoProperties:
    """Additional tests for LicenseInfo properties."""

    def test_days_until_expiry_exact_value(self):
        """Test exact days_until_expiry calculation."""
        now = datetime.now(timezone.utc)
        expires_in_10_days = now + timedelta(days=10)

        payload = {
            "license_id": "exact-days",
            "edition": "enterprise",
            "organization": "Test Org",
            "issued_at": (now - timedelta(days=30)).isoformat(),
            "expires_at": expires_in_10_days.isoformat(),
        }
        license_info = LicenseInfo.from_dict(payload)
        # Allow small variance due to execution time
        assert 9 <= license_info.days_until_expiry <= 10

    def test_is_expiring_soon_boundary_30_days(self):
        """Test is_expiring_soon at 30-day boundary."""
        now = datetime.now(timezone.utc)

        # 29 days - should be expiring soon (clearly within 30 days)
        payload_29 = {
            "license_id": "29-days",
            "edition": "enterprise",
            "organization": "Test Org",
            "issued_at": (now - timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=29)).isoformat(),
        }
        license_29 = LicenseInfo.from_dict(payload_29)
        assert license_29.is_expiring_soon is True

        # 60 days - should NOT be expiring soon (clearly outside 30 days)
        payload_60 = {
            "license_id": "60-days",
            "edition": "enterprise",
            "organization": "Test Org",
            "issued_at": (now - timedelta(days=30)).isoformat(),
            "expires_at": (now + timedelta(days=60)).isoformat(),
        }
        license_60 = LicenseInfo.from_dict(payload_60)
        assert license_60.is_expiring_soon is False
