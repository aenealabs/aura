"""
Project Aura - Compliance Settings Tests (ADR-040)

Tests for configurable compliance settings including:
- Compliance profiles (commercial, cmmc_l1, cmmc_l2, govcloud)
- KMS encryption mode configuration
- Log retention settings
- SSM parameter sync Lambda
"""

import importlib
import os
import platform

import pytest

# These tests require pytest-forked for isolation due to compliance config state.
# On Linux (CI), mock patches don't apply correctly without forked mode.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from unittest.mock import AsyncMock, MagicMock, patch

# Set testing environment variable
os.environ["TESTING"] = "true"

# Import the lambda module using importlib (since 'lambda' is a Python keyword)
compliance_sync_module = importlib.import_module("src.lambda.compliance_settings_sync")


# =============================================================================
# Compliance Settings Sync Lambda Tests
# =============================================================================


class TestComplianceSettingsSyncLambda:
    """Tests for the compliance_settings_sync Lambda function."""

    def test_validate_event_valid_commercial(self):
        """Test validation of valid commercial profile event."""
        validate_event = compliance_sync_module.validate_event

        event = {
            "profile": "commercial",
            "kms_encryption_mode": "aws_managed",
            "log_retention_days": 30,
            "audit_log_retention_days": 90,
        }

        result = validate_event(event)

        assert result["profile"] == "commercial"
        assert result["kms_mode"] == "aws_managed"
        assert result["log_retention_days"] == 30
        assert result["audit_log_retention_days"] == 90

    def test_validate_event_valid_cmmc_l2(self):
        """Test validation of valid CMMC L2 profile event."""
        validate_event = compliance_sync_module.validate_event

        event = {
            "profile": "cmmc_l2",
            "kms_encryption_mode": "customer_managed",
            "log_retention_days": 90,
            "audit_log_retention_days": 365,
        }

        result = validate_event(event)

        assert result["profile"] == "cmmc_l2"
        assert result["kms_mode"] == "customer_managed"
        assert result["log_retention_days"] == 90

    def test_validate_event_valid_govcloud(self):
        """Test validation of valid GovCloud profile event."""
        validate_event = compliance_sync_module.validate_event

        event = {
            "profile": "govcloud",
            "kms_encryption_mode": "customer_managed",
            "log_retention_days": 365,
            "audit_log_retention_days": 365,
        }

        result = validate_event(event)

        assert result["profile"] == "govcloud"
        assert result["log_retention_days"] == 365

    def test_validate_event_invalid_profile(self):
        """Test validation rejects invalid profile."""
        validate_event = compliance_sync_module.validate_event

        event = {
            "profile": "invalid_profile",
            "kms_encryption_mode": "aws_managed",
            "log_retention_days": 90,
            "audit_log_retention_days": 365,
        }

        with pytest.raises(ValueError) as exc_info:
            validate_event(event)

        assert "Invalid profile" in str(exc_info.value)

    def test_validate_event_invalid_kms_mode(self):
        """Test validation rejects invalid KMS mode."""
        validate_event = compliance_sync_module.validate_event

        event = {
            "profile": "commercial",
            "kms_encryption_mode": "invalid_mode",
            "log_retention_days": 90,
            "audit_log_retention_days": 365,
        }

        with pytest.raises(ValueError) as exc_info:
            validate_event(event)

        assert "Invalid KMS mode" in str(exc_info.value)

    def test_validate_event_cmmc_l2_adjusts_low_retention(self):
        """Test CMMC L2 profile adjusts retention below 90 days."""
        validate_event = compliance_sync_module.validate_event

        event = {
            "profile": "cmmc_l2",
            "kms_encryption_mode": "customer_managed",
            "log_retention_days": 30,  # Too low for CMMC L2
            "audit_log_retention_days": 365,
        }

        result = validate_event(event)

        # Should be adjusted to 90 days
        assert result["log_retention_days"] == 90

    def test_normalize_retention_days_valid(self):
        """Test retention days normalization with valid values."""
        normalize_retention_days = compliance_sync_module.normalize_retention_days

        assert normalize_retention_days(30) == 30
        assert normalize_retention_days(60) == 60
        assert normalize_retention_days(90) == 90
        assert normalize_retention_days(365) == 365

    def test_normalize_retention_days_invalid(self):
        """Test retention days normalization with invalid values."""
        normalize_retention_days = compliance_sync_module.normalize_retention_days

        # 45 should round up to 60
        assert normalize_retention_days(45) == 60
        # 100 should round up to 120
        assert normalize_retention_days(100) == 120

    def test_handler_success(self):
        """Test Lambda handler successful execution."""
        handler = compliance_sync_module.handler

        # Use patch.object for fork-safe mocking
        with patch.object(compliance_sync_module, "write_ssm_parameters") as mock_ssm:
            with patch.object(compliance_sync_module, "send_notification") as mock_sns:
                mock_ssm.return_value = {
                    "written": ["/aura/dev/compliance/profile"],
                    "failed": [],
                }
                mock_sns.return_value = True

                event = {
                    "profile": "cmmc_l1",
                    "kms_encryption_mode": "aws_managed",
                    "log_retention_days": 90,
                    "audit_log_retention_days": 365,
                }

                result = handler(event, None)

                assert result["statusCode"] == 200
                assert result["body"]["status"] == "success"
                assert result["body"]["settings_applied"]["profile"] == "cmmc_l1"

    def test_handler_validation_error(self):
        """Test Lambda handler with validation error."""
        handler = compliance_sync_module.handler

        event = {
            "profile": "invalid",
            "kms_encryption_mode": "aws_managed",
            "log_retention_days": 90,
            "audit_log_retention_days": 365,
        }

        result = handler(event, None)

        assert result["statusCode"] == 400
        assert result["body"]["status"] == "error"
        assert result["body"]["error_type"] == "validation_error"


# =============================================================================
# Compliance API Endpoint Tests
# =============================================================================


class TestComplianceEndpoints:
    """Tests for compliance settings API endpoints."""

    @pytest.fixture
    def mock_settings_service(self):
        """Create a mock settings persistence service."""
        service = MagicMock()
        service.get_setting = AsyncMock()
        service.update_setting = AsyncMock(return_value=True)
        return service

    @pytest.mark.asyncio
    async def test_get_compliance_settings_default(self, mock_settings_service):
        """Test getting compliance settings returns defaults when not set."""
        from src.api.settings_endpoints import (
            ComplianceSettingsModel,
            get_compliance_settings,
        )
        from src.services.settings_persistence_service import DEFAULT_PLATFORM_SETTINGS

        mock_settings_service.get_setting.return_value = None

        with patch(
            "src.api.settings_endpoints._get_persistence_service",
            return_value=mock_settings_service,
        ):
            result = await get_compliance_settings()

        assert isinstance(result, ComplianceSettingsModel)
        assert result.profile == DEFAULT_PLATFORM_SETTINGS.get("compliance", {}).get(
            "profile", "commercial"
        )

    @pytest.mark.asyncio
    async def test_get_compliance_settings_stored(self, mock_settings_service):
        """Test getting stored compliance settings."""
        from src.api.settings_endpoints import get_compliance_settings

        stored_settings = {
            "profile": "cmmc_l2",
            "kms_encryption_mode": "customer_managed",
            "log_retention_days": 90,
            "audit_log_retention_days": 365,
            "require_encryption_at_rest": True,
            "require_encryption_in_transit": True,
            "pending_kms_change": False,
        }
        mock_settings_service.get_setting.return_value = stored_settings

        with patch(
            "src.api.settings_endpoints._get_persistence_service",
            return_value=mock_settings_service,
        ):
            result = await get_compliance_settings()

        assert result.profile == "cmmc_l2"
        assert result.kms_encryption_mode == "customer_managed"
        assert result.log_retention_days == 90

    @pytest.mark.asyncio
    async def test_update_compliance_settings_kms_change_pending(
        self, mock_settings_service
    ):
        """Test updating KMS mode marks change as pending."""
        from fastapi import Request

        from src.api.settings_endpoints import (
            ComplianceSettingsModel,
            update_compliance_settings,
        )

        # Current settings have aws_managed
        mock_settings_service.get_setting.return_value = {
            "profile": "commercial",
            "kms_encryption_mode": "aws_managed",
            "log_retention_days": 30,
        }

        mock_request = MagicMock(spec=Request)

        # Update to customer_managed
        new_settings = ComplianceSettingsModel(
            profile="cmmc_l2",
            kms_encryption_mode="customer_managed",
            log_retention_days=90,
        )

        with patch(
            "src.api.settings_endpoints._get_persistence_service",
            return_value=mock_settings_service,
        ):
            with patch(
                "src.api.settings_endpoints._invoke_compliance_settings_sync",
                new_callable=AsyncMock,
            ) as mock_sync:
                with patch(
                    "src.api.settings_endpoints._invoke_log_retention_sync",
                    new_callable=AsyncMock,
                ):
                    mock_sync.return_value = {"status": "invoked"}

                    # Mock the rate limit dependency
                    with patch("src.api.settings_endpoints.admin_rate_limit"):
                        result = await update_compliance_settings(
                            mock_request, new_settings, MagicMock()
                        )

        # Should mark KMS change as pending
        assert result.pending_kms_change is True

    @pytest.mark.asyncio
    async def test_update_compliance_settings_invalid_profile(
        self, mock_settings_service
    ):
        """Test updating with invalid profile raises error."""
        from fastapi import HTTPException, Request

        from src.api.settings_endpoints import (
            ComplianceSettingsModel,
            update_compliance_settings,
        )

        mock_settings_service.get_setting.return_value = {"profile": "commercial"}

        mock_request = MagicMock(spec=Request)

        # Try to use invalid profile
        new_settings = ComplianceSettingsModel(
            profile="invalid_profile",
            kms_encryption_mode="aws_managed",
            log_retention_days=90,
        )

        with patch(
            "src.api.settings_endpoints._get_persistence_service",
            return_value=mock_settings_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_compliance_settings(
                    mock_request, new_settings, MagicMock()
                )

            assert exc_info.value.status_code == 400
            assert "Invalid compliance profile" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_compliance_settings_cmmc_l2_low_retention(
        self, mock_settings_service
    ):
        """Test CMMC L2 profile rejects low log retention."""
        from fastapi import HTTPException, Request

        from src.api.settings_endpoints import (
            ComplianceSettingsModel,
            update_compliance_settings,
        )

        mock_settings_service.get_setting.return_value = {"profile": "commercial"}

        mock_request = MagicMock(spec=Request)

        # Try to set CMMC L2 with 30-day retention
        new_settings = ComplianceSettingsModel(
            profile="cmmc_l2",
            kms_encryption_mode="customer_managed",
            log_retention_days=30,  # Too low for CMMC L2
        )

        with patch(
            "src.api.settings_endpoints._get_persistence_service",
            return_value=mock_settings_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_compliance_settings(
                    mock_request, new_settings, MagicMock()
                )

            assert exc_info.value.status_code == 400
            assert "90-day log retention" in str(exc_info.value.detail)


# =============================================================================
# Compliance Profile Preset Tests
# =============================================================================


class TestComplianceProfiles:
    """Tests for compliance profile presets."""

    def test_commercial_profile_settings(self):
        """Test commercial profile has correct settings."""
        from src.api.settings_endpoints import COMPLIANCE_PROFILE_PRESETS

        profile = COMPLIANCE_PROFILE_PRESETS["commercial"]

        assert profile["kms_encryption_mode"] == "aws_managed"
        assert profile["log_retention_days"] == 30
        assert profile["require_encryption_at_rest"] is True

    def test_cmmc_l1_profile_settings(self):
        """Test CMMC L1 profile has correct settings."""
        from src.api.settings_endpoints import COMPLIANCE_PROFILE_PRESETS

        profile = COMPLIANCE_PROFILE_PRESETS["cmmc_l1"]

        assert profile["kms_encryption_mode"] == "aws_managed"
        assert profile["log_retention_days"] == 90
        assert profile["audit_log_retention_days"] == 365

    def test_cmmc_l2_profile_settings(self):
        """Test CMMC L2 profile has correct settings."""
        from src.api.settings_endpoints import COMPLIANCE_PROFILE_PRESETS

        profile = COMPLIANCE_PROFILE_PRESETS["cmmc_l2"]

        assert profile["kms_encryption_mode"] == "customer_managed"
        assert profile["log_retention_days"] == 90
        assert profile["audit_log_retention_days"] == 365

    def test_govcloud_profile_settings(self):
        """Test GovCloud profile has correct settings."""
        from src.api.settings_endpoints import COMPLIANCE_PROFILE_PRESETS

        profile = COMPLIANCE_PROFILE_PRESETS["govcloud"]

        assert profile["kms_encryption_mode"] == "customer_managed"
        assert profile["log_retention_days"] == 365
        assert profile["audit_log_retention_days"] == 365


# =============================================================================
# Settings Persistence Compliance Tests
# =============================================================================


class TestSettingsPersistenceCompliance:
    """Tests for compliance section in settings persistence."""

    def test_default_compliance_settings_exist(self):
        """Test default compliance settings are defined."""
        from src.services.settings_persistence_service import DEFAULT_PLATFORM_SETTINGS

        assert "compliance" in DEFAULT_PLATFORM_SETTINGS

        compliance = DEFAULT_PLATFORM_SETTINGS["compliance"]
        assert "profile" in compliance
        assert "kms_encryption_mode" in compliance
        assert "log_retention_days" in compliance
        assert "pending_kms_change" in compliance

    def test_default_compliance_profile(self):
        """Test default compliance profile is commercial."""
        from src.services.settings_persistence_service import DEFAULT_PLATFORM_SETTINGS

        compliance = DEFAULT_PLATFORM_SETTINGS["compliance"]
        assert compliance["profile"] == "commercial"

    def test_default_kms_mode(self):
        """Test default KMS mode is aws_managed."""
        from src.services.settings_persistence_service import DEFAULT_PLATFORM_SETTINGS

        compliance = DEFAULT_PLATFORM_SETTINGS["compliance"]
        assert compliance["kms_encryption_mode"] == "aws_managed"

    def test_compliance_in_platform_settings_keys(self):
        """Test compliance is included in update_all_platform_settings keys."""
        # Read the file to check the key list
        import inspect

        from src.services.settings_persistence_service import SettingsPersistenceService

        source = inspect.getsource(
            SettingsPersistenceService.update_all_platform_settings
        )
        assert "compliance" in source


# =============================================================================
# Integration Tests
# =============================================================================


class TestComplianceIntegration:
    """Integration tests for compliance settings flow."""

    @pytest.mark.asyncio
    async def test_profile_change_triggers_ssm_sync(self):
        """Test changing profile triggers SSM parameter sync."""
        from fastapi import Request

        from src.api.settings_endpoints import apply_compliance_profile

        mock_request = MagicMock(spec=Request)
        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value={"profile": "commercial"})
        mock_service.update_setting = AsyncMock(return_value=True)

        with patch(
            "src.api.settings_endpoints._get_persistence_service",
            return_value=mock_service,
        ):
            with patch(
                "src.api.settings_endpoints._invoke_compliance_settings_sync",
                new_callable=AsyncMock,
            ) as mock_sync:
                with patch(
                    "src.api.settings_endpoints._invoke_log_retention_sync",
                    new_callable=AsyncMock,
                ):
                    mock_sync.return_value = {"status": "invoked"}

                    result = await apply_compliance_profile(
                        mock_request, "cmmc_l2", MagicMock()
                    )

        assert result["status"] == "success"
        assert result["profile"] == "cmmc_l2"
        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_retention_change_triggers_sync(self):
        """Test changing log retention triggers log sync Lambda."""
        from fastapi import Request

        from src.api.settings_endpoints import (
            ComplianceSettingsModel,
            update_compliance_settings,
        )

        mock_request = MagicMock(spec=Request)
        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(
            return_value={
                "profile": "commercial",
                "kms_encryption_mode": "aws_managed",
                "log_retention_days": 30,
            }
        )
        mock_service.update_setting = AsyncMock(return_value=True)

        new_settings = ComplianceSettingsModel(
            profile="commercial",
            kms_encryption_mode="aws_managed",
            log_retention_days=90,  # Changed from 30
        )

        with patch(
            "src.api.settings_endpoints._get_persistence_service",
            return_value=mock_service,
        ):
            with patch(
                "src.api.settings_endpoints._invoke_compliance_settings_sync",
                new_callable=AsyncMock,
            ) as mock_compliance_sync:
                with patch(
                    "src.api.settings_endpoints._invoke_log_retention_sync",
                    new_callable=AsyncMock,
                ) as mock_log_sync:
                    mock_compliance_sync.return_value = {"status": "invoked"}
                    mock_log_sync.return_value = {"status": "invoked"}

                    await update_compliance_settings(
                        mock_request, new_settings, MagicMock()
                    )

        # Log retention sync should be called
        mock_log_sync.assert_called_once_with(90)


# =============================================================================
# Model Validation Tests
# =============================================================================


class TestComplianceModels:
    """Tests for Pydantic model validation."""

    def test_compliance_settings_model_defaults(self):
        """Test ComplianceSettingsModel has correct defaults."""
        from src.api.settings_endpoints import ComplianceSettingsModel

        model = ComplianceSettingsModel()

        assert model.profile == "commercial"
        assert model.kms_encryption_mode == "aws_managed"
        assert model.log_retention_days == 90
        assert model.require_encryption_at_rest is True
        assert model.pending_kms_change is False

    def test_compliance_settings_model_validation(self):
        """Test ComplianceSettingsModel validates field ranges."""
        from pydantic import ValidationError

        from src.api.settings_endpoints import ComplianceSettingsModel

        # Valid model
        valid = ComplianceSettingsModel(
            profile="cmmc_l2",
            log_retention_days=90,
        )
        assert valid.log_retention_days == 90

        # Invalid log retention (too low)
        with pytest.raises(ValidationError):
            ComplianceSettingsModel(log_retention_days=1)

    def test_compliance_profile_enum(self):
        """Test ComplianceProfile enum values."""
        from src.api.settings_endpoints import ComplianceProfile

        assert ComplianceProfile.COMMERCIAL.value == "commercial"
        assert ComplianceProfile.CMMC_L1.value == "cmmc_l1"
        assert ComplianceProfile.CMMC_L2.value == "cmmc_l2"
        assert ComplianceProfile.GOVCLOUD.value == "govcloud"

    def test_kms_encryption_mode_enum(self):
        """Test KMSEncryptionMode enum values."""
        from src.api.settings_endpoints import KMSEncryptionMode

        assert KMSEncryptionMode.AWS_MANAGED.value == "aws_managed"
        assert KMSEncryptionMode.CUSTOMER_MANAGED.value == "customer_managed"
