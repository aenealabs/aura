"""
Tests for Hyperscale Orchestration API Endpoints (ADR-087).

Comprehensive test suite covering:
- GET hyperscale settings (default and org-specific)
- PUT hyperscale settings updates
- Tier-based agent limit enforcement
- Input validation
- Default security gate states
"""

import platform

import pytest

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from src.api.orchestrator_settings_endpoints import (
    DEFAULT_HYPERSCALE_SETTINGS,
    ExecutionTier,
    HyperscaleSettingsResponse,
    SecurityGateState,
    UpdateHyperscaleSettingsRequest,
    _hyperscale_settings,
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


@pytest.fixture(autouse=True)
def clear_hyperscale_settings():
    """Clear in-memory hyperscale settings before each test."""
    _hyperscale_settings.clear()
    yield
    _hyperscale_settings.clear()


# =============================================================================
# Model Tests
# =============================================================================


class TestHyperscaleModels:
    """Test Pydantic models for hyperscale endpoints."""

    def test_execution_tier_enum(self):
        """Test ExecutionTier enum values."""
        assert ExecutionTier.IN_PROCESS.value == "in_process"
        assert ExecutionTier.DISTRIBUTED_SIMPLE.value == "distributed_simple"
        assert ExecutionTier.DISTRIBUTED_ORCHESTRATED.value == "distributed_orchestrated"

    def test_security_gate_state_defaults(self):
        """Test SecurityGateState default values."""
        gate = SecurityGateState()
        assert gate.validated is False
        assert gate.validated_at is None

    def test_security_gate_state_with_values(self):
        """Test SecurityGateState with explicit values."""
        gate = SecurityGateState(validated=True, validated_at="2026-05-01T00:00:00Z")
        assert gate.validated is True
        assert gate.validated_at == "2026-05-01T00:00:00Z"

    def test_hyperscale_settings_response_defaults(self):
        """Test HyperscaleSettingsResponse default values."""
        response = HyperscaleSettingsResponse()
        assert response.enabled is False
        assert response.execution_tier == "in_process"
        assert response.max_parallel_agents == 10
        assert response.feasibility_gate_enabled is True
        assert response.cost_circuit_breaker_usd == 500
        assert "gate_1" in response.security_gates
        assert "gate_2" in response.security_gates
        assert "gate_3" in response.security_gates

    def test_hyperscale_settings_response_security_gates_default_state(self):
        """Test all three security gates default to validated=False."""
        response = HyperscaleSettingsResponse()
        for gate_key in ["gate_1", "gate_2", "gate_3"]:
            gate = response.security_gates[gate_key]
            assert gate.validated is False
            assert gate.validated_at is None

    def test_update_request_all_none(self):
        """Test UpdateHyperscaleSettingsRequest with no fields."""
        request = UpdateHyperscaleSettingsRequest()
        assert request.enabled is None
        assert request.execution_tier is None
        assert request.max_parallel_agents is None
        assert request.feasibility_gate_enabled is None
        assert request.cost_circuit_breaker_usd is None

    def test_update_request_valid_fields(self):
        """Test UpdateHyperscaleSettingsRequest with valid fields."""
        request = UpdateHyperscaleSettingsRequest(
            enabled=True,
            execution_tier="distributed_simple",
            max_parallel_agents=100,
            feasibility_gate_enabled=False,
            cost_circuit_breaker_usd=1000,
        )
        assert request.enabled is True
        assert request.execution_tier == "distributed_simple"
        assert request.max_parallel_agents == 100

    def test_update_request_max_parallel_agents_zero_rejected(self):
        """Test max_parallel_agents=0 is rejected (ge=1)."""
        with pytest.raises(ValidationError):
            UpdateHyperscaleSettingsRequest(max_parallel_agents=0)

    def test_update_request_max_parallel_agents_1001_rejected(self):
        """Test max_parallel_agents=1001 is rejected (le=1000)."""
        with pytest.raises(ValidationError):
            UpdateHyperscaleSettingsRequest(max_parallel_agents=1001)

    def test_update_request_max_parallel_agents_boundary_1(self):
        """Test max_parallel_agents=1 is accepted (lower bound)."""
        request = UpdateHyperscaleSettingsRequest(max_parallel_agents=1)
        assert request.max_parallel_agents == 1

    def test_update_request_max_parallel_agents_boundary_1000(self):
        """Test max_parallel_agents=1000 is accepted (upper bound)."""
        request = UpdateHyperscaleSettingsRequest(max_parallel_agents=1000)
        assert request.max_parallel_agents == 1000


# =============================================================================
# GET Hyperscale Settings Tests
# =============================================================================


class TestGetHyperscaleSettings:
    """Test GET /api/v1/orchestrator/hyperscale endpoint."""

    @pytest.mark.asyncio
    async def test_get_default_settings_no_org(
        self, mock_user, mock_request, mock_rate_limit
    ):
        """Test getting default settings when no org-specific settings exist."""
        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        result = await get_hyperscale_settings(
            request=mock_request,
            organization_id=None,
            current_user=mock_user,
            rate_limit=mock_rate_limit,
        )

        assert isinstance(result, HyperscaleSettingsResponse)
        assert result.enabled is False
        assert result.execution_tier == "in_process"
        assert result.max_parallel_agents == 10
        assert result.feasibility_gate_enabled is True
        assert result.cost_circuit_breaker_usd == 500

    @pytest.mark.asyncio
    async def test_get_default_settings_security_gates(
        self, mock_user, mock_request, mock_rate_limit
    ):
        """Test default security gates are all unvalidated."""
        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        result = await get_hyperscale_settings(
            request=mock_request,
            organization_id=None,
            current_user=mock_user,
            rate_limit=mock_rate_limit,
        )

        for gate_key in ["gate_1", "gate_2", "gate_3"]:
            gate = result.security_gates[gate_key]
            assert gate.validated is False
            assert gate.validated_at is None

    @pytest.mark.asyncio
    async def test_get_org_specific_settings(
        self, mock_user, mock_request, mock_rate_limit
    ):
        """Test getting org-specific settings when they exist."""
        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        # Pre-populate org-specific settings
        _hyperscale_settings["org-456"] = {
            "enabled": True,
            "execution_tier": "distributed_simple",
            "max_parallel_agents": 100,
            "feasibility_gate_enabled": False,
            "cost_circuit_breaker_usd": 2000,
            "security_gates": {
                "gate_1": {"validated": True, "validated_at": "2026-05-01T00:00:00Z"},
                "gate_2": {"validated": False, "validated_at": None},
                "gate_3": {"validated": False, "validated_at": None},
            },
        }

        result = await get_hyperscale_settings(
            request=mock_request,
            organization_id="org-456",
            current_user=mock_user,
            rate_limit=mock_rate_limit,
        )

        assert result.enabled is True
        assert result.execution_tier == "distributed_simple"
        assert result.max_parallel_agents == 100
        assert result.feasibility_gate_enabled is False
        assert result.cost_circuit_breaker_usd == 2000
        assert result.security_gates["gate_1"].validated is True
        assert result.security_gates["gate_1"].validated_at == "2026-05-01T00:00:00Z"

    @pytest.mark.asyncio
    async def test_get_org_falls_back_to_defaults(
        self, mock_user, mock_request, mock_rate_limit
    ):
        """Test that requesting a non-existent org falls back to defaults."""
        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        result = await get_hyperscale_settings(
            request=mock_request,
            organization_id="org-nonexistent",
            current_user=mock_user,
            rate_limit=mock_rate_limit,
        )

        assert result.enabled is False
        assert result.execution_tier == "in_process"
        assert result.max_parallel_agents == 10

    @pytest.mark.asyncio
    async def test_get_platform_settings_after_update(
        self, mock_user, mock_request, mock_rate_limit
    ):
        """Test getting platform settings that were previously updated."""
        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        _hyperscale_settings["platform"] = {
            "enabled": True,
            "execution_tier": "distributed_orchestrated",
            "max_parallel_agents": 500,
            "feasibility_gate_enabled": True,
            "cost_circuit_breaker_usd": 5000,
            "security_gates": {
                "gate_1": {"validated": True, "validated_at": "2026-04-01T00:00:00Z"},
                "gate_2": {"validated": True, "validated_at": "2026-04-15T00:00:00Z"},
                "gate_3": {"validated": False, "validated_at": None},
            },
        }

        result = await get_hyperscale_settings(
            request=mock_request,
            organization_id=None,
            current_user=mock_user,
            rate_limit=mock_rate_limit,
        )

        assert result.enabled is True
        assert result.execution_tier == "distributed_orchestrated"
        assert result.max_parallel_agents == 500


# =============================================================================
# PUT Hyperscale Settings Tests
# =============================================================================


class TestUpdateHyperscaleSettings:
    """Test PUT /api/v1/orchestrator/hyperscale endpoint."""

    @pytest.mark.asyncio
    async def test_update_settings_valid_data(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test updating settings with valid data."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            enabled=True,
            max_parallel_agents=15,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.enabled is True
        assert result.max_parallel_agents == 15
        assert result.execution_tier == "in_process"

    @pytest.mark.asyncio
    async def test_update_settings_empty_update(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test updating with no fields (empty update preserves defaults)."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest()

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        # Should return defaults since no fields were changed
        assert result.enabled is False
        assert result.execution_tier == "in_process"
        assert result.max_parallel_agents == 10

    @pytest.mark.asyncio
    async def test_update_persists_in_memory(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test that updates are persisted in the in-memory store."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            enabled=True,
            cost_circuit_breaker_usd=1500,
        )

        await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert "platform" in _hyperscale_settings
        assert _hyperscale_settings["platform"]["enabled"] is True
        assert _hyperscale_settings["platform"]["cost_circuit_breaker_usd"] == 1500

    @pytest.mark.asyncio
    async def test_update_org_specific(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test updating org-specific settings."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            enabled=True,
            execution_tier="distributed_simple",
            max_parallel_agents=50,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id="org-789",
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.enabled is True
        assert result.execution_tier == "distributed_simple"
        assert result.max_parallel_agents == 50
        assert "org-789" in _hyperscale_settings

    # =========================================================================
    # Tier-Based Agent Limit Enforcement
    # =========================================================================

    @pytest.mark.asyncio
    async def test_in_process_tier_clamps_high_agents(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test in_process tier clamps agents above 20 to 20."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="in_process",
            max_parallel_agents=500,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.max_parallel_agents == 20

    @pytest.mark.asyncio
    async def test_in_process_tier_allows_max_boundary(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test in_process tier allows exactly 20 agents."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="in_process",
            max_parallel_agents=20,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.max_parallel_agents == 20

    @pytest.mark.asyncio
    async def test_in_process_tier_allows_min_boundary(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test in_process tier allows exactly 1 agent."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="in_process",
            max_parallel_agents=1,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.max_parallel_agents == 1

    @pytest.mark.asyncio
    async def test_distributed_simple_tier_clamps_high_agents(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test distributed_simple tier clamps agents above 200 to 200."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="distributed_simple",
            max_parallel_agents=500,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.max_parallel_agents == 200

    @pytest.mark.asyncio
    async def test_distributed_simple_tier_clamps_low_agents(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test distributed_simple tier clamps agents below 20 to 20."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="distributed_simple",
            max_parallel_agents=5,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.max_parallel_agents == 20

    @pytest.mark.asyncio
    async def test_distributed_simple_tier_allows_max_boundary(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test distributed_simple tier allows exactly 200 agents."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="distributed_simple",
            max_parallel_agents=200,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.max_parallel_agents == 200

    @pytest.mark.asyncio
    async def test_distributed_orchestrated_tier_allows_max_boundary(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test distributed_orchestrated tier allows exactly 1000 agents."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="distributed_orchestrated",
            max_parallel_agents=1000,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.max_parallel_agents == 1000

    @pytest.mark.asyncio
    async def test_distributed_orchestrated_tier_clamps_low_agents(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test distributed_orchestrated tier clamps agents below 200 to 200."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="distributed_orchestrated",
            max_parallel_agents=50,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.max_parallel_agents == 200

    @pytest.mark.asyncio
    async def test_tier_change_without_agent_count_uses_existing(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test changing tier without setting agents clamps existing value."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        # Default is max_parallel_agents=10, tier=in_process
        # Switch to distributed_simple, which requires min 20
        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="distributed_simple",
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        # Default 10 should be clamped to min 20 for distributed_simple
        assert result.max_parallel_agents == 20

    @pytest.mark.asyncio
    async def test_update_preserves_security_gates(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test that updating non-gate fields preserves security gate state."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            enabled=True,
            cost_circuit_breaker_usd=2000,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        # Security gates should still be in default state
        for gate_key in ["gate_1", "gate_2", "gate_3"]:
            gate = result.security_gates[gate_key]
            assert gate.validated is False
            assert gate.validated_at is None


# =============================================================================
# Default Settings Constant Tests
# =============================================================================


class TestDefaultHyperscaleSettings:
    """Test DEFAULT_HYPERSCALE_SETTINGS constant."""

    def test_default_enabled_is_false(self):
        """Test default enabled is False."""
        assert DEFAULT_HYPERSCALE_SETTINGS["enabled"] is False

    def test_default_execution_tier(self):
        """Test default execution tier is in_process."""
        assert DEFAULT_HYPERSCALE_SETTINGS["execution_tier"] == "in_process"

    def test_default_max_parallel_agents(self):
        """Test default max_parallel_agents is 10."""
        assert DEFAULT_HYPERSCALE_SETTINGS["max_parallel_agents"] == 10

    def test_default_feasibility_gate_enabled(self):
        """Test default feasibility_gate_enabled is True."""
        assert DEFAULT_HYPERSCALE_SETTINGS["feasibility_gate_enabled"] is True

    def test_default_cost_circuit_breaker(self):
        """Test default cost_circuit_breaker_usd is 500."""
        assert DEFAULT_HYPERSCALE_SETTINGS["cost_circuit_breaker_usd"] == 500

    def test_default_security_gates_structure(self):
        """Test default security gates has all three gates."""
        gates = DEFAULT_HYPERSCALE_SETTINGS["security_gates"]
        assert "gate_1" in gates
        assert "gate_2" in gates
        assert "gate_3" in gates

    def test_default_security_gates_all_unvalidated(self):
        """Test all default security gates are unvalidated."""
        for gate_key in ["gate_1", "gate_2", "gate_3"]:
            gate = DEFAULT_HYPERSCALE_SETTINGS["security_gates"][gate_key]
            assert gate["validated"] is False
            assert gate["validated_at"] is None
