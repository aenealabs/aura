"""
Tests for Orchestrator Mode Service.

Tests the deployment mode transition management including:
- Mode state machine transitions
- Cooldown enforcement
- Warm pool scaling
- Settings integration
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.orchestrator_mode_service import (
    DeploymentMode,
    ModeTransitionStatus,
    OrchestratorModeService,
    TransitionState,
    create_orchestrator_mode_service,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings_service():
    """Create mock settings service."""
    service = MagicMock()
    service.get_setting = AsyncMock(return_value={})
    service.get_organization_setting = AsyncMock(return_value={})
    service.update_setting = AsyncMock()
    service.update_organization_setting = AsyncMock()
    return service


@pytest.fixture
def service(mock_settings_service):
    """Create orchestrator mode service with mocked dependencies."""
    return OrchestratorModeService(
        settings_service=mock_settings_service,
        kubernetes_enabled=False,  # Disable K8s for unit tests
        namespace="test-namespace",
    )


@pytest.fixture
def service_no_settings():
    """Create orchestrator mode service without settings service."""
    return OrchestratorModeService(
        settings_service=None,
        kubernetes_enabled=False,
    )


# ============================================================================
# Enum Tests
# ============================================================================


class TestEnums:
    """Test enum definitions."""

    def test_deployment_mode_values(self):
        """Test DeploymentMode enum values."""
        assert DeploymentMode.ON_DEMAND.value == "on_demand"
        assert DeploymentMode.WARM_POOL.value == "warm_pool"
        assert DeploymentMode.HYBRID.value == "hybrid"

    def test_transition_state_values(self):
        """Test TransitionState enum values."""
        assert TransitionState.ACTIVE.value == "active"
        assert TransitionState.DRAINING.value == "draining"
        assert TransitionState.COMPLETING.value == "completing"
        assert TransitionState.SCALING.value == "scaling"
        assert TransitionState.FAILED.value == "failed"


# ============================================================================
# Data Model Tests
# ============================================================================


class TestModeTransitionStatus:
    """Test ModeTransitionStatus dataclass."""

    def test_create_status(self):
        """Test creating a transition status."""
        status = ModeTransitionStatus(
            current_mode=DeploymentMode.ON_DEMAND,
            target_mode=DeploymentMode.WARM_POOL,
            transition_state=TransitionState.DRAINING,
            started_at="2025-01-01T00:00:00Z",
            in_flight_jobs=5,
            warm_pool_desired=2,
            warm_pool_ready=0,
        )
        assert status.current_mode == DeploymentMode.ON_DEMAND
        assert status.target_mode == DeploymentMode.WARM_POOL
        assert status.in_flight_jobs == 5

    def test_status_with_error(self):
        """Test status with error message."""
        status = ModeTransitionStatus(
            current_mode=DeploymentMode.ON_DEMAND,
            target_mode=DeploymentMode.WARM_POOL,
            transition_state=TransitionState.FAILED,
            started_at="2025-01-01T00:00:00Z",
            in_flight_jobs=0,
            warm_pool_desired=2,
            warm_pool_ready=0,
            error_message="Scaling failed",
        )
        assert status.error_message == "Scaling failed"


# ============================================================================
# Service Initialization Tests
# ============================================================================


class TestServiceInitialization:
    """Test service initialization."""

    def test_init_with_settings_service(self, mock_settings_service):
        """Test initialization with settings service."""
        service = OrchestratorModeService(
            settings_service=mock_settings_service,
            kubernetes_enabled=False,
        )
        assert service._settings_service == mock_settings_service
        assert service._kubernetes_enabled is False

    def test_init_without_settings_service(self):
        """Test initialization without settings service."""
        service = OrchestratorModeService(
            settings_service=None,
            kubernetes_enabled=False,
        )
        assert service._settings_service is None

    def test_init_with_custom_namespace(self, mock_settings_service):
        """Test initialization with custom namespace."""
        service = OrchestratorModeService(
            settings_service=mock_settings_service,
            kubernetes_enabled=False,
            namespace="production",
        )
        assert service._namespace == "production"

    def test_kubernetes_client_not_initialized_when_disabled(
        self, mock_settings_service
    ):
        """Test K8s client not initialized when disabled."""
        service = OrchestratorModeService(
            settings_service=mock_settings_service,
            kubernetes_enabled=False,
        )
        assert service._k8s_client is None


# ============================================================================
# Get Current Mode Tests
# ============================================================================


class TestGetCurrentMode:
    """Test getting current deployment mode."""

    @pytest.mark.asyncio
    async def test_default_mode_no_settings(self, service_no_settings):
        """Test default mode when no settings service."""
        mode = await service_no_settings.get_current_mode()
        assert mode == DeploymentMode.ON_DEMAND

    @pytest.mark.asyncio
    async def test_on_demand_mode(self, service, mock_settings_service):
        """Test ON_DEMAND mode from settings."""
        mock_settings_service.get_setting.return_value = {
            "warm_pool_enabled": False,
            "hybrid_mode_enabled": False,
        }
        mode = await service.get_current_mode()
        assert mode == DeploymentMode.ON_DEMAND

    @pytest.mark.asyncio
    async def test_warm_pool_mode(self, service, mock_settings_service):
        """Test WARM_POOL mode from settings."""
        mock_settings_service.get_setting.return_value = {
            "warm_pool_enabled": True,
            "hybrid_mode_enabled": False,
        }
        mode = await service.get_current_mode()
        assert mode == DeploymentMode.WARM_POOL

    @pytest.mark.asyncio
    async def test_hybrid_mode(self, service, mock_settings_service):
        """Test HYBRID mode from settings."""
        mock_settings_service.get_setting.return_value = {
            "hybrid_mode_enabled": True,
        }
        mode = await service.get_current_mode()
        assert mode == DeploymentMode.HYBRID

    @pytest.mark.asyncio
    async def test_org_specific_settings_override(self, service, mock_settings_service):
        """Test organization-specific settings override platform settings."""
        mock_settings_service.get_setting.return_value = {
            "warm_pool_enabled": False,
        }
        mock_settings_service.get_organization_setting.return_value = {
            "warm_pool_enabled": True,
        }
        mode = await service.get_current_mode(organization_id="org-123")
        assert mode == DeploymentMode.WARM_POOL


# ============================================================================
# Compute Mode From Settings Tests
# ============================================================================


class TestComputeModeFromSettings:
    """Test mode computation from settings."""

    def test_hybrid_takes_priority(self, service):
        """Test hybrid mode takes priority over warm pool."""
        settings = {
            "hybrid_mode_enabled": True,
            "warm_pool_enabled": True,
        }
        mode = service._compute_mode_from_settings(settings)
        assert mode == DeploymentMode.HYBRID

    def test_warm_pool_when_enabled(self, service):
        """Test warm pool mode when enabled."""
        settings = {
            "hybrid_mode_enabled": False,
            "warm_pool_enabled": True,
        }
        mode = service._compute_mode_from_settings(settings)
        assert mode == DeploymentMode.WARM_POOL

    def test_on_demand_default(self, service):
        """Test on-demand is default."""
        settings = {}
        mode = service._compute_mode_from_settings(settings)
        assert mode == DeploymentMode.ON_DEMAND


# ============================================================================
# Can Transition Tests
# ============================================================================


class TestCanTransition:
    """Test transition eligibility checks."""

    @pytest.mark.asyncio
    async def test_can_transition_no_settings(self, service_no_settings):
        """Test transition allowed when no settings service."""
        can, reason, cooldown = await service_no_settings.can_transition()
        assert can is True
        assert "mock mode" in reason.lower()
        assert cooldown == 0

    @pytest.mark.asyncio
    async def test_can_transition_no_previous_change(
        self, service, mock_settings_service
    ):
        """Test transition allowed when no previous mode change."""
        mock_settings_service.get_setting.return_value = {}
        can, reason, cooldown = await service.can_transition()
        assert can is True
        assert "no previous" in reason.lower()

    @pytest.mark.asyncio
    async def test_cannot_transition_during_cooldown(
        self, service, mock_settings_service
    ):
        """Test transition blocked during cooldown."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=60)).isoformat()
        mock_settings_service.get_setting.return_value = {
            "last_mode_change_at": recent,
            "mode_change_cooldown_seconds": 300,
        }
        can, reason, cooldown = await service.can_transition()
        assert can is False
        assert "cooldown" in reason.lower()
        assert cooldown > 0

    @pytest.mark.asyncio
    async def test_can_transition_after_cooldown(self, service, mock_settings_service):
        """Test transition allowed after cooldown expires."""
        now = datetime.now(timezone.utc)
        old = (now - timedelta(seconds=600)).isoformat()
        mock_settings_service.get_setting.return_value = {
            "last_mode_change_at": old,
            "mode_change_cooldown_seconds": 300,
        }
        can, reason, cooldown = await service.can_transition()
        assert can is True
        assert cooldown == 0

    @pytest.mark.asyncio
    async def test_cannot_transition_when_in_progress(
        self, service, mock_settings_service
    ):
        """Test transition blocked when another is in progress."""
        service._current_transition = ModeTransitionStatus(
            current_mode=DeploymentMode.ON_DEMAND,
            target_mode=DeploymentMode.WARM_POOL,
            transition_state=TransitionState.DRAINING,
            started_at="2025-01-01T00:00:00Z",
            in_flight_jobs=5,
            warm_pool_desired=2,
            warm_pool_ready=0,
        )
        can, reason, cooldown = await service.can_transition()
        assert can is False
        assert "in progress" in reason.lower()


# ============================================================================
# Get Transition Status Tests
# ============================================================================


class TestGetTransitionStatus:
    """Test getting transition status."""

    @pytest.mark.asyncio
    async def test_no_active_transition(self, service):
        """Test no active transition returns None."""
        status = await service.get_transition_status()
        assert status is None

    @pytest.mark.asyncio
    async def test_active_transition(self, service):
        """Test returns current transition status."""
        expected = ModeTransitionStatus(
            current_mode=DeploymentMode.ON_DEMAND,
            target_mode=DeploymentMode.WARM_POOL,
            transition_state=TransitionState.SCALING,
            started_at="2025-01-01T00:00:00Z",
            in_flight_jobs=0,
            warm_pool_desired=2,
            warm_pool_ready=1,
        )
        service._current_transition = expected
        status = await service.get_transition_status()
        assert status == expected


# ============================================================================
# Start Transition Tests
# ============================================================================


class TestStartTransition:
    """Test starting mode transitions."""

    @pytest.mark.asyncio
    async def test_already_in_target_mode(self, service, mock_settings_service):
        """Test no transition when already in target mode."""
        mock_settings_service.get_setting.return_value = {
            "warm_pool_enabled": False,
            "hybrid_mode_enabled": False,
        }

        status = await service.start_transition(DeploymentMode.ON_DEMAND)

        assert status.current_mode == DeploymentMode.ON_DEMAND
        assert status.target_mode is None
        assert status.transition_state == TransitionState.ACTIVE

    @pytest.mark.asyncio
    async def test_transition_blocked_during_cooldown(
        self, service, mock_settings_service
    ):
        """Test transition raises error during cooldown."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=60)).isoformat()
        mock_settings_service.get_setting.return_value = {
            "last_mode_change_at": recent,
            "mode_change_cooldown_seconds": 300,
        }

        with pytest.raises(ValueError, match="Cooldown active"):
            await service.start_transition(DeploymentMode.WARM_POOL)

    @pytest.mark.asyncio
    async def test_force_bypasses_cooldown(self, service, mock_settings_service):
        """Test force flag bypasses cooldown."""
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(seconds=60)).isoformat()
        mock_settings_service.get_setting.return_value = {
            "last_mode_change_at": recent,
            "mode_change_cooldown_seconds": 300,
            "warm_pool_enabled": False,
        }

        status = await service.start_transition(
            DeploymentMode.WARM_POOL,
            force=True,
        )

        assert status.target_mode == DeploymentMode.WARM_POOL
        assert status.transition_state == TransitionState.DRAINING


# ============================================================================
# Get Mode Status Tests
# ============================================================================


class TestGetModeStatus:
    """Test getting mode status summary."""

    @pytest.mark.asyncio
    async def test_status_without_active_transition(
        self, service, mock_settings_service
    ):
        """Test status when no active transition."""
        mock_settings_service.get_setting.return_value = {
            "warm_pool_enabled": True,
        }

        status = await service.get_mode_status()

        assert status["current_mode"] == DeploymentMode.WARM_POOL.value
        assert status["transition_active"] is False

    @pytest.mark.asyncio
    async def test_status_with_active_transition(self, service, mock_settings_service):
        """Test status during active transition."""
        mock_settings_service.get_setting.return_value = {}
        service._current_transition = ModeTransitionStatus(
            current_mode=DeploymentMode.ON_DEMAND,
            target_mode=DeploymentMode.WARM_POOL,
            transition_state=TransitionState.SCALING,
            started_at="2025-01-01T00:00:00Z",
            in_flight_jobs=0,
            warm_pool_desired=2,
            warm_pool_ready=1,
        )

        status = await service.get_mode_status()

        assert status["transition_active"] is True
        assert status["target_mode"] == DeploymentMode.WARM_POOL.value
        assert status["transition_state"] == TransitionState.SCALING.value


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestFactoryFunction:
    """Test create_orchestrator_mode_service factory."""

    def test_create_with_settings_service(self, mock_settings_service):
        """Test factory with settings service."""
        service = create_orchestrator_mode_service(
            settings_service=mock_settings_service,
            kubernetes_enabled=False,
        )
        assert service._settings_service == mock_settings_service

    def test_create_without_settings_service(self):
        """Test factory without settings service."""
        service = create_orchestrator_mode_service(
            settings_service=None,
            kubernetes_enabled=False,
        )
        assert service._settings_service is None


# ============================================================================
# Internal Method Tests
# ============================================================================


class TestInternalMethods:
    """Test internal helper methods."""

    @pytest.mark.asyncio
    async def test_get_in_flight_jobs_count(self, service):
        """Test getting in-flight jobs count."""
        # Default returns 0 when no active orchestrator
        count = await service._get_in_flight_jobs_count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_warm_pool_replicas_ready_no_k8s(self, service):
        """Test warm pool replicas when K8s disabled."""
        replicas = await service._get_warm_pool_replicas_ready()
        assert replicas == 0

    @pytest.mark.asyncio
    async def test_get_warm_pool_replicas_desired(self, service, mock_settings_service):
        """Test getting desired warm pool replicas from settings."""
        mock_settings_service.get_setting.return_value = {
            "warm_pool_enabled": True,
            "warm_pool_replicas": 3,
        }
        replicas = await service._get_warm_pool_replicas_desired()
        assert replicas == 3

    @pytest.mark.asyncio
    async def test_get_warm_pool_replicas_desired_default(
        self, service, mock_settings_service
    ):
        """Test default warm pool replicas when enabled but not set."""
        mock_settings_service.get_setting.return_value = {
            "warm_pool_enabled": True,
        }
        replicas = await service._get_warm_pool_replicas_desired()
        assert replicas == 1  # Default is 1

    @pytest.mark.asyncio
    async def test_get_warm_pool_replicas_zero_when_disabled(
        self, service, mock_settings_service
    ):
        """Test warm pool replicas returns 0 when disabled."""
        mock_settings_service.get_setting.return_value = {
            "warm_pool_enabled": False,
            "warm_pool_replicas": 3,
        }
        replicas = await service._get_warm_pool_replicas_desired()
        assert replicas == 0
