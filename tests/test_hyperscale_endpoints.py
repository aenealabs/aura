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
    """Create a mock authenticated user belonging to org-456."""
    from src.api.auth import User

    return User(
        sub="sub-123",
        email="test@example.com",
        name="Test User",
        groups=["user"],
        organization_id="org-456",
    )


@pytest.fixture
def mock_admin_user():
    """Create a mock platform-admin user (no specific org)."""
    from src.api.auth import User

    return User(
        sub="admin-sub",
        email="admin@example.com",
        name="Admin User",
        groups=["platform_admin", "admin"],
        organization_id=None,
    )


@pytest.fixture
def mock_org_admin_user():
    """Create a mock org-level admin (admin within org-456 only)."""
    from src.api.auth import User

    return User(
        sub="org-admin-sub",
        email="org-admin@example.com",
        name="Org Admin",
        groups=["admin"],
        organization_id="org-456",
    )


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
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test getting default platform settings (admin-only path)."""
        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        result = await get_hyperscale_settings(
            request=mock_request,
            organization_id=None,
            current_user=mock_admin_user,
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
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test default security gates are all unvalidated (admin path)."""
        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        result = await get_hyperscale_settings(
            request=mock_request,
            organization_id=None,
            current_user=mock_admin_user,
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
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test that requesting a non-existent org falls back to defaults.

        Uses platform admin because cross-org reads are forbidden for
        regular users (audit finding C1 — tenant isolation).
        """
        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        result = await get_hyperscale_settings(
            request=mock_request,
            organization_id="org-nonexistent",
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.enabled is False
        assert result.execution_tier == "in_process"
        assert result.max_parallel_agents == 10

    @pytest.mark.asyncio
    async def test_get_platform_settings_after_update(
        self, mock_admin_user, mock_request, mock_rate_limit
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
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.enabled is True
        assert result.execution_tier == "distributed_orchestrated"
        assert result.max_parallel_agents == 500


# =============================================================================
# Tenant Isolation Tests (audit finding C1, ADR-087)
# =============================================================================


class TestHyperscaleTenantIsolation:
    """Verify cross-tenant access is rejected on the hyperscale endpoints."""

    @pytest.mark.asyncio
    async def test_user_cannot_read_another_orgs_settings(
        self, mock_user, mock_request, mock_rate_limit
    ):
        """A user belonging to org-456 cannot read org-789's settings."""
        from fastapi import HTTPException

        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        with pytest.raises(HTTPException) as excinfo:
            await get_hyperscale_settings(
                request=mock_request,
                organization_id="org-789",
                current_user=mock_user,
                rate_limit=mock_rate_limit,
            )
        assert excinfo.value.status_code == 403

    @pytest.mark.asyncio
    async def test_user_cannot_read_platform_settings(
        self, mock_user, mock_request, mock_rate_limit
    ):
        """A non-platform-admin user cannot access the 'platform' key."""
        from fastapi import HTTPException

        from src.api.orchestrator_settings_endpoints import get_hyperscale_settings

        with pytest.raises(HTTPException) as excinfo:
            await get_hyperscale_settings(
                request=mock_request,
                organization_id=None,
                current_user=mock_user,
                rate_limit=mock_rate_limit,
            )
        assert excinfo.value.status_code == 403

    @pytest.mark.asyncio
    async def test_org_admin_cannot_write_other_orgs_settings(
        self, mock_org_admin_user, mock_request, mock_rate_limit
    ):
        """An admin within org-456 cannot write org-789's settings."""
        from fastapi import HTTPException

        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(enabled=True)
        with pytest.raises(HTTPException) as excinfo:
            await update_hyperscale_settings(
                request=mock_request,
                updates=updates,
                organization_id="org-789",
                current_user=mock_org_admin_user,
                rate_limit=mock_rate_limit,
            )
        assert excinfo.value.status_code == 403


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

    @pytest.mark.asyncio
    async def test_unknown_tier_falls_back_to_in_process_limits(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test that an unrecognized execution tier falls back to in_process limits (1-20)."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(
            execution_tier="turbo_mode",
            max_parallel_agents=500,
        )

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        # Unknown tier should use fallback limits (1, 20)
        assert result.max_parallel_agents == 20
        assert result.execution_tier == "turbo_mode"

    @pytest.mark.asyncio
    async def test_second_put_overwrites_first(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test that a second PUT fully overwrites the first update's values."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        # First update
        await update_hyperscale_settings(
            request=mock_request,
            updates=UpdateHyperscaleSettingsRequest(
                enabled=True,
                execution_tier="distributed_simple",
                max_parallel_agents=100,
                cost_circuit_breaker_usd=2000,
            ),
            organization_id="org-overwrite",
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        # Second update changes tier back and sets different cost
        result = await update_hyperscale_settings(
            request=mock_request,
            updates=UpdateHyperscaleSettingsRequest(
                execution_tier="in_process",
                max_parallel_agents=5,
                cost_circuit_breaker_usd=100,
            ),
            organization_id="org-overwrite",
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        # enabled should persist from first update (not in second update)
        assert result.enabled is True
        # These should reflect second update
        assert result.execution_tier == "in_process"
        assert result.max_parallel_agents == 5
        assert result.cost_circuit_breaker_usd == 100

    @pytest.mark.asyncio
    async def test_org_isolation_no_cross_contamination(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test that updating org A does not affect org B."""
        from src.api.orchestrator_settings_endpoints import (
            get_hyperscale_settings,
            update_hyperscale_settings,
        )

        # Update org-A to distributed_orchestrated with 800 agents
        await update_hyperscale_settings(
            request=mock_request,
            updates=UpdateHyperscaleSettingsRequest(
                enabled=True,
                execution_tier="distributed_orchestrated",
                max_parallel_agents=800,
            ),
            organization_id="org-A",
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        # org-B should still return defaults
        result_b = await get_hyperscale_settings(
            request=mock_request,
            organization_id="org-B",
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result_b.enabled is False
        assert result_b.execution_tier == "in_process"
        assert result_b.max_parallel_agents == 10

    @pytest.mark.asyncio
    async def test_cost_circuit_breaker_boundary_zero(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test cost_circuit_breaker_usd accepts 0 (disabled)."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(cost_circuit_breaker_usd=0)

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.cost_circuit_breaker_usd == 0

    @pytest.mark.asyncio
    async def test_cost_circuit_breaker_boundary_max(
        self, mock_admin_user, mock_request, mock_rate_limit
    ):
        """Test cost_circuit_breaker_usd accepts 10000 (max)."""
        from src.api.orchestrator_settings_endpoints import update_hyperscale_settings

        updates = UpdateHyperscaleSettingsRequest(cost_circuit_breaker_usd=10000)

        result = await update_hyperscale_settings(
            request=mock_request,
            updates=updates,
            organization_id=None,
            current_user=mock_admin_user,
            rate_limit=mock_rate_limit,
        )

        assert result.cost_circuit_breaker_usd == 10000

    def test_cost_circuit_breaker_negative_rejected(self):
        """Test negative cost_circuit_breaker_usd is rejected by validation."""
        with pytest.raises(ValidationError):
            UpdateHyperscaleSettingsRequest(cost_circuit_breaker_usd=-1)

    def test_cost_circuit_breaker_over_max_rejected(self):
        """Test cost_circuit_breaker_usd above 10000 is rejected."""
        with pytest.raises(ValidationError):
            UpdateHyperscaleSettingsRequest(cost_circuit_breaker_usd=10001)


# =============================================================================
# Default Settings Constant Tests
# =============================================================================


class TestDefaultHyperscaleSettings:
    """Test DEFAULT_HYPERSCALE_SETTINGS constant."""

    def test_default_settings_all_fields(self):
        """Test all default settings values in one assertion block."""
        assert DEFAULT_HYPERSCALE_SETTINGS["enabled"] is False
        assert DEFAULT_HYPERSCALE_SETTINGS["execution_tier"] == "in_process"
        assert DEFAULT_HYPERSCALE_SETTINGS["max_parallel_agents"] == 10
        assert DEFAULT_HYPERSCALE_SETTINGS["feasibility_gate_enabled"] is True
        assert DEFAULT_HYPERSCALE_SETTINGS["cost_circuit_breaker_usd"] == 500

    def test_default_security_gates_all_unvalidated(self):
        """Test all three default security gates exist and are unvalidated."""
        gates = DEFAULT_HYPERSCALE_SETTINGS["security_gates"]
        assert set(gates.keys()) == {"gate_1", "gate_2", "gate_3"}
        for gate_key in ["gate_1", "gate_2", "gate_3"]:
            assert gates[gate_key]["validated"] is False
            assert gates[gate_key]["validated_at"] is None
