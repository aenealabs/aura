"""
Tests for Orchestrator Settings API Endpoints.

Comprehensive test suite covering:
- Settings retrieval (platform and organization)
- Settings updates
- Mode switching with cooldown
- Available modes listing
- Mode status retrieval
- Health checks
"""

import platform

import pytest

# Run tests in separate processes to avoid mock pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from src.api.orchestrator_settings_endpoints import (
    DeploymentMode,
    HealthResponse,
    ModeInfo,
    ModeStatusResponse,
    OrchestratorSettingsResponse,
    SwitchModeRequest,
    UpdateOrchestratorSettingsRequest,
    check_cooldown,
    compute_effective_mode,
    settings_to_response,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = "user-123"
    user.email = "test@example.com"
    user.sub = "sub-123"
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = MagicMock()
    user.id = "admin-123"
    user.email = "admin@example.com"
    user.sub = "admin-sub"
    user.roles = ["admin"]
    return user


@pytest.fixture
def mock_rate_limit():
    """Create a mock rate limit result."""
    return MagicMock()


@pytest.fixture
def mock_request():
    """Create a mock HTTP request."""
    return MagicMock()


@pytest.fixture
def default_settings():
    """Create default platform settings."""
    return {
        "on_demand_jobs_enabled": True,
        "warm_pool_enabled": False,
        "hybrid_mode_enabled": False,
        "warm_pool_replicas": 1,
        "hybrid_threshold_queue_depth": 5,
        "hybrid_scale_up_cooldown_seconds": 60,
        "hybrid_max_burst_jobs": 10,
        "estimated_cost_per_job_usd": 0.15,
        "estimated_warm_pool_monthly_usd": 28.0,
        "mode_change_cooldown_seconds": 300,
    }


@pytest.fixture
def warm_pool_settings():
    """Create warm pool enabled settings."""
    return {
        "on_demand_jobs_enabled": False,
        "warm_pool_enabled": True,
        "hybrid_mode_enabled": False,
        "warm_pool_replicas": 2,
        "last_mode_change_at": None,
    }


@pytest.fixture
def hybrid_settings():
    """Create hybrid mode settings."""
    return {
        "on_demand_jobs_enabled": True,
        "warm_pool_enabled": True,
        "hybrid_mode_enabled": True,
        "warm_pool_replicas": 2,
        "hybrid_threshold_queue_depth": 10,
        "hybrid_max_burst_jobs": 20,
    }


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper functions."""

    def test_compute_effective_mode_on_demand(self, default_settings):
        """Test computing on_demand mode."""
        mode = compute_effective_mode(default_settings)
        assert mode == "on_demand"

    def test_compute_effective_mode_warm_pool(self, warm_pool_settings):
        """Test computing warm_pool mode."""
        mode = compute_effective_mode(warm_pool_settings)
        assert mode == "warm_pool"

    def test_compute_effective_mode_hybrid(self, hybrid_settings):
        """Test computing hybrid mode."""
        mode = compute_effective_mode(hybrid_settings)
        assert mode == "hybrid"

    def test_compute_effective_mode_empty_settings(self):
        """Test computing mode with empty settings."""
        mode = compute_effective_mode({})
        assert mode == "on_demand"

    def test_settings_to_response(self, default_settings):
        """Test converting settings to response."""
        response = settings_to_response(default_settings)

        assert isinstance(response, OrchestratorSettingsResponse)
        assert response.on_demand_jobs_enabled is True
        assert response.warm_pool_enabled is False
        assert response.hybrid_mode_enabled is False
        assert response.effective_mode == "on_demand"
        assert response.is_organization_override is False
        assert response.organization_id is None

    def test_settings_to_response_with_org(self, default_settings):
        """Test converting settings to response with organization."""
        response = settings_to_response(
            default_settings,
            organization_id="org-123",
            is_override=True,
        )

        assert response.is_organization_override is True
        assert response.organization_id == "org-123"

    def test_check_cooldown_no_previous_change(self):
        """Test cooldown with no previous change."""
        settings = {"mode_change_cooldown_seconds": 300}
        can_change, remaining = check_cooldown(settings)

        assert can_change is True
        assert remaining == 0

    def test_check_cooldown_within_cooldown(self):
        """Test cooldown when within cooldown period."""
        now = datetime.now(timezone.utc)
        one_minute_ago = (now - timedelta(minutes=1)).isoformat()

        settings = {
            "mode_change_cooldown_seconds": 300,
            "last_mode_change_at": one_minute_ago,
        }
        can_change, remaining = check_cooldown(settings)

        assert can_change is False
        assert remaining > 0
        assert remaining <= 240  # 5 min - 1 min = 4 min remaining

    def test_check_cooldown_expired(self):
        """Test cooldown when period has expired."""
        now = datetime.now(timezone.utc)
        ten_minutes_ago = (now - timedelta(minutes=10)).isoformat()

        settings = {
            "mode_change_cooldown_seconds": 300,
            "last_mode_change_at": ten_minutes_ago,
        }
        can_change, remaining = check_cooldown(settings)

        assert can_change is True
        assert remaining == 0


# =============================================================================
# Settings Retrieval Tests
# =============================================================================


class TestSettingsRetrieval:
    """Test settings retrieval endpoints."""

    @pytest.mark.asyncio
    async def test_get_settings_platform_default(
        self, mock_user, mock_request, mock_rate_limit, default_settings
    ):
        """Test getting platform default settings."""
        from src.api.orchestrator_settings_endpoints import get_orchestrator_settings

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=default_settings)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await get_orchestrator_settings(
                request=mock_request,
                organization_id=None,
                user=mock_user,
                rate_check=mock_rate_limit,
            )

        assert result.effective_mode == "on_demand"
        assert result.is_organization_override is False
        mock_service.get_setting.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_settings_organization_override(
        self,
        mock_user,
        mock_request,
        mock_rate_limit,
        default_settings,
        warm_pool_settings,
    ):
        """Test getting organization-specific settings."""
        from src.api.orchestrator_settings_endpoints import get_orchestrator_settings

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=default_settings)
        mock_service.get_organization_setting = AsyncMock(
            return_value=warm_pool_settings
        )

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await get_orchestrator_settings(
                request=mock_request,
                organization_id="org-123",
                user=mock_user,
                rate_check=mock_rate_limit,
            )

        assert result.effective_mode == "warm_pool"
        assert result.is_organization_override is True
        assert result.organization_id == "org-123"

    @pytest.mark.asyncio
    async def test_get_settings_org_fallback_to_platform(
        self, mock_user, mock_request, mock_rate_limit, default_settings
    ):
        """Test org settings fallback to platform when empty."""
        from src.api.orchestrator_settings_endpoints import get_orchestrator_settings

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=default_settings)
        mock_service.get_organization_setting = AsyncMock(return_value=None)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await get_orchestrator_settings(
                request=mock_request,
                organization_id="org-123",
                user=mock_user,
                rate_check=mock_rate_limit,
            )

        assert result.effective_mode == "on_demand"
        assert result.is_organization_override is False


# =============================================================================
# Settings Update Tests
# =============================================================================


class TestSettingsUpdate:
    """Test settings update endpoints."""

    @pytest.mark.asyncio
    async def test_update_settings_success(
        self, mock_admin_user, mock_rate_limit, default_settings
    ):
        """Test successful settings update."""
        from src.api.orchestrator_settings_endpoints import update_orchestrator_settings

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=default_settings)
        mock_service.save_setting = AsyncMock(return_value=True)

        mock_publisher = MagicMock()
        mock_background = MagicMock()

        request = UpdateOrchestratorSettingsRequest(warm_pool_replicas=3)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await update_orchestrator_settings(
                request_body=request,
                background_tasks=mock_background,
                organization_id=None,
                user=mock_admin_user,
                publisher=mock_publisher,
                rate_check=mock_rate_limit,
            )

        assert result is not None
        mock_service.save_setting.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_settings_no_updates(self, mock_admin_user, mock_rate_limit):
        """Test update with no fields provided."""
        from src.api.orchestrator_settings_endpoints import update_orchestrator_settings

        mock_publisher = MagicMock()
        mock_background = MagicMock()

        request = UpdateOrchestratorSettingsRequest()

        with pytest.raises(HTTPException) as exc_info:
            await update_orchestrator_settings(
                request_body=request,
                background_tasks=mock_background,
                organization_id=None,
                user=mock_admin_user,
                publisher=mock_publisher,
                rate_check=mock_rate_limit,
            )

        assert exc_info.value.status_code == 400
        assert "No updates provided" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_settings_hybrid_requires_warm_pool(
        self, mock_admin_user, mock_rate_limit, default_settings
    ):
        """Test hybrid mode requires warm pool enabled."""
        from src.api.orchestrator_settings_endpoints import update_orchestrator_settings

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=default_settings)

        mock_publisher = MagicMock()
        mock_background = MagicMock()

        # Try to enable hybrid while explicitly disabling warm pool
        request = UpdateOrchestratorSettingsRequest(
            hybrid_mode_enabled=True,
            warm_pool_enabled=False,
        )

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_orchestrator_settings(
                    request_body=request,
                    background_tasks=mock_background,
                    organization_id=None,
                    user=mock_admin_user,
                    publisher=mock_publisher,
                    rate_check=mock_rate_limit,
                )

        assert exc_info.value.status_code == 400
        assert "warm_pool_enabled" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_update_settings_org_override(
        self, mock_admin_user, mock_rate_limit, default_settings, warm_pool_settings
    ):
        """Test updating organization-specific settings."""
        from src.api.orchestrator_settings_endpoints import update_orchestrator_settings

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=default_settings)
        mock_service.get_organization_setting = AsyncMock(
            return_value=warm_pool_settings
        )
        mock_service.update_organization_setting = AsyncMock(return_value=True)

        mock_publisher = MagicMock()
        mock_background = MagicMock()

        request = UpdateOrchestratorSettingsRequest(warm_pool_replicas=5)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            _result = await update_orchestrator_settings(
                request_body=request,
                background_tasks=mock_background,
                organization_id="org-123",
                user=mock_admin_user,
                publisher=mock_publisher,
                rate_check=mock_rate_limit,
            )

        mock_service.update_organization_setting.assert_called_once()


# =============================================================================
# Mode Switching Tests
# =============================================================================


class TestModeSwitching:
    """Test mode switching endpoint."""

    @pytest.mark.asyncio
    async def test_switch_mode_success(
        self, mock_admin_user, mock_rate_limit, default_settings
    ):
        """Test successful mode switch."""
        from src.api.orchestrator_settings_endpoints import switch_deployment_mode

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=default_settings)
        mock_service.save_setting = AsyncMock(return_value=True)

        mock_publisher = MagicMock()
        mock_background = MagicMock()

        request = SwitchModeRequest(target_mode=DeploymentMode.WARM_POOL)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await switch_deployment_mode(
                request_body=request,
                background_tasks=mock_background,
                organization_id=None,
                user=mock_admin_user,
                publisher=mock_publisher,
                rate_check=mock_rate_limit,
            )

        assert result is not None
        mock_service.save_setting.assert_called_once()
        mock_background.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_switch_mode_already_in_target(
        self, mock_admin_user, mock_rate_limit, warm_pool_settings
    ):
        """Test switch when already in target mode."""
        from src.api.orchestrator_settings_endpoints import switch_deployment_mode

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=warm_pool_settings)

        mock_publisher = MagicMock()
        mock_background = MagicMock()

        request = SwitchModeRequest(target_mode=DeploymentMode.WARM_POOL)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            _result = await switch_deployment_mode(
                request_body=request,
                background_tasks=mock_background,
                organization_id=None,
                user=mock_admin_user,
                publisher=mock_publisher,
                rate_check=mock_rate_limit,
            )

        # Should return without saving when already in target mode
        mock_service.save_setting.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_mode_cooldown_active(self, mock_admin_user, mock_rate_limit):
        """Test switch blocked by cooldown."""
        from src.api.orchestrator_settings_endpoints import switch_deployment_mode

        now = datetime.now(timezone.utc)
        settings = {
            "on_demand_jobs_enabled": True,
            "warm_pool_enabled": False,
            "hybrid_mode_enabled": False,
            "mode_change_cooldown_seconds": 300,
            "last_mode_change_at": now.isoformat(),
        }

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=settings)

        mock_publisher = MagicMock()
        mock_background = MagicMock()

        request = SwitchModeRequest(target_mode=DeploymentMode.WARM_POOL)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await switch_deployment_mode(
                    request_body=request,
                    background_tasks=mock_background,
                    organization_id=None,
                    user=mock_admin_user,
                    publisher=mock_publisher,
                    rate_check=mock_rate_limit,
                )

        assert exc_info.value.status_code == 429
        assert "cooldown" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_switch_mode_force_bypass_cooldown(
        self, mock_admin_user, mock_rate_limit
    ):
        """Test force switch bypasses cooldown."""
        from src.api.orchestrator_settings_endpoints import switch_deployment_mode

        now = datetime.now(timezone.utc)
        settings = {
            "on_demand_jobs_enabled": True,
            "warm_pool_enabled": False,
            "hybrid_mode_enabled": False,
            "mode_change_cooldown_seconds": 300,
            "last_mode_change_at": now.isoformat(),
        }

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=settings)
        mock_service.save_setting = AsyncMock(return_value=True)

        mock_publisher = MagicMock()
        mock_background = MagicMock()

        request = SwitchModeRequest(
            target_mode=DeploymentMode.WARM_POOL,
            force=True,
            reason="Emergency switch",
        )

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await switch_deployment_mode(
                request_body=request,
                background_tasks=mock_background,
                organization_id=None,
                user=mock_admin_user,
                publisher=mock_publisher,
                rate_check=mock_rate_limit,
            )

        assert result is not None
        mock_service.save_setting.assert_called_once()


# =============================================================================
# Available Modes Tests
# =============================================================================


class TestAvailableModes:
    """Test available modes endpoint."""

    @pytest.mark.asyncio
    async def test_get_available_modes(self, mock_rate_limit):
        """Test getting available deployment modes."""
        from src.api.orchestrator_settings_endpoints import get_available_modes

        result = await get_available_modes(rate_check=mock_rate_limit)

        assert len(result) == 3
        mode_names = [m.mode for m in result]
        assert "on_demand" in mode_names
        assert "warm_pool" in mode_names
        assert "hybrid" in mode_names

    @pytest.mark.asyncio
    async def test_get_available_modes_has_metadata(self, mock_rate_limit):
        """Test mode metadata is complete."""
        from src.api.orchestrator_settings_endpoints import get_available_modes

        result = await get_available_modes(rate_check=mock_rate_limit)

        for mode in result:
            assert mode.display_name
            assert mode.description
            assert mode.base_monthly_cost_usd >= 0
            assert mode.cold_start_seconds >= 0
            assert len(mode.recommended_for) > 0


# =============================================================================
# Mode Status Tests
# =============================================================================


class TestModeStatus:
    """Test mode status endpoint."""

    @pytest.mark.asyncio
    async def test_get_mode_status(self, mock_user, mock_rate_limit, default_settings):
        """Test getting mode status."""
        from src.api.orchestrator_settings_endpoints import get_mode_status

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=default_settings)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await get_mode_status(
                organization_id=None,
                user=mock_user,
                rate_check=mock_rate_limit,
            )

        assert isinstance(result, ModeStatusResponse)
        assert result.current_mode == "on_demand"
        assert result.warm_pool_replicas_desired == 0
        assert result.can_switch_mode is True

    @pytest.mark.asyncio
    async def test_get_mode_status_warm_pool(
        self, mock_user, mock_rate_limit, warm_pool_settings
    ):
        """Test mode status with warm pool enabled."""
        from src.api.orchestrator_settings_endpoints import get_mode_status

        warm_pool_settings["warm_pool_replicas"] = 3

        mock_service = MagicMock()
        mock_service.get_setting = AsyncMock(return_value=warm_pool_settings)

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await get_mode_status(
                organization_id=None,
                user=mock_user,
                rate_check=mock_rate_limit,
            )

        assert result.current_mode == "warm_pool"
        assert result.warm_pool_replicas_desired == 3


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check returns healthy status."""
        from src.api.orchestrator_settings_endpoints import orchestrator_settings_health

        mock_service = MagicMock()
        mock_service.mode = MagicMock()
        mock_service.mode.value = "mock"

        with patch(
            "src.api.orchestrator_settings_endpoints.get_settings_service",
            return_value=mock_service,
        ):
            result = await orchestrator_settings_health()

        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"
        assert result.service == "orchestrator_settings"


# =============================================================================
# Model Tests
# =============================================================================


class TestModels:
    """Test Pydantic models."""

    def test_deployment_mode_enum(self):
        """Test DeploymentMode enum values."""
        assert DeploymentMode.ON_DEMAND.value == "on_demand"
        assert DeploymentMode.WARM_POOL.value == "warm_pool"
        assert DeploymentMode.HYBRID.value == "hybrid"

    def test_update_request_validation(self):
        """Test UpdateOrchestratorSettingsRequest validation."""
        # Valid request
        request = UpdateOrchestratorSettingsRequest(
            warm_pool_replicas=5,
            hybrid_max_burst_jobs=20,
        )
        assert request.warm_pool_replicas == 5

        # Invalid: replicas too high
        with pytest.raises(ValueError):
            UpdateOrchestratorSettingsRequest(warm_pool_replicas=100)

    def test_switch_mode_request(self):
        """Test SwitchModeRequest model."""
        request = SwitchModeRequest(target_mode=DeploymentMode.HYBRID)
        assert request.target_mode == DeploymentMode.HYBRID
        assert request.force is False
        assert request.reason is None

        request_with_reason = SwitchModeRequest(
            target_mode=DeploymentMode.WARM_POOL,
            force=True,
            reason="Cost optimization",
        )
        assert request_with_reason.force is True
        assert request_with_reason.reason == "Cost optimization"

    def test_mode_info_model(self):
        """Test ModeInfo model."""
        info = ModeInfo(
            mode="test",
            display_name="Test Mode",
            description="A test mode",
            base_monthly_cost_usd=50.0,
            cold_start_seconds=10.0,
            recommended_for=["testing"],
        )
        assert info.mode == "test"
        assert len(info.recommended_for) == 1

    def test_orchestrator_settings_response_defaults(self):
        """Test OrchestratorSettingsResponse defaults."""
        response = OrchestratorSettingsResponse()
        assert response.on_demand_jobs_enabled is True
        assert response.warm_pool_enabled is False
        assert response.hybrid_mode_enabled is False
        assert response.effective_mode == "on_demand"
