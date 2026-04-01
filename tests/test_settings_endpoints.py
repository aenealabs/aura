"""
Tests for Platform Settings API Endpoints.

Tests the REST API endpoints for platform configuration management,
including Integration Mode, HITL settings, and MCP configuration.
"""

import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.settings_endpoints import _invalidate_config, router
from src.services.settings_persistence_service import DEFAULT_PLATFORM_SETTINGS

# ============================================================================
# Fixtures
# ============================================================================


class MockSettingsPersistenceService:
    """Mock persistence service for testing."""

    def __init__(self):
        self._store = {
            "platform": {
                "integration_mode": {"mode": "defense"},
                "hitl": DEFAULT_PLATFORM_SETTINGS["hitl"].copy(),
                "mcp": DEFAULT_PLATFORM_SETTINGS["mcp"].copy(),
                "security": DEFAULT_PLATFORM_SETTINGS["security"].copy(),
            }
        }

    async def get_setting(self, settings_type: str, settings_key: str, default=None):
        """Get a setting from the mock store."""
        type_store = self._store.get(settings_type, {})
        value = type_store.get(settings_key)
        if value is None:
            if default is not None:
                return default
            if settings_type == "platform":
                return DEFAULT_PLATFORM_SETTINGS.get(settings_key, {})
        return value

    async def update_setting(
        self,
        settings_type: str,
        settings_key: str,
        value: dict,
        updated_by: str = "test",
    ):
        """Update a setting in the mock store."""
        if settings_type not in self._store:
            self._store[settings_type] = {}
        self._store[settings_type][settings_key] = value
        return True


@pytest.fixture
def mock_persistence_service():
    """Create a mock persistence service."""
    return MockSettingsPersistenceService()


@pytest.fixture
def test_client(mock_persistence_service):
    """Create a test client for the settings endpoints."""
    app = FastAPI()
    app.include_router(router)

    # Patch the get_settings_service to return our mock
    with patch(
        "src.api.settings_endpoints.get_settings_service",
        return_value=mock_persistence_service,
    ):
        yield TestClient(app), mock_persistence_service


@pytest.fixture(autouse=True)
def reset_config():
    """Reset integration config cache before each test."""
    _invalidate_config()
    yield
    _invalidate_config()


# ============================================================================
# Get All Settings Tests
# ============================================================================


class TestGetSettings:
    """Tests for GET /api/v1/settings endpoint."""

    def test_get_settings_returns_all_settings(self, test_client):
        """Test that get settings returns complete settings object."""
        client, _ = test_client
        response = client.get("/api/v1/settings")

        assert response.status_code == 200
        data = response.json()

        assert "integration_mode" in data
        assert "hitl_settings" in data
        assert "mcp_settings" in data
        assert "security_settings" in data

    def test_get_settings_default_mode_is_defense(self, test_client):
        """Test that default integration mode is defense."""
        client, _ = test_client
        response = client.get("/api/v1/settings")

        assert response.status_code == 200
        assert response.json()["integration_mode"] == "defense"

    def test_get_settings_includes_hitl_defaults(self, test_client):
        """Test that HITL settings include expected defaults."""
        client, _ = test_client
        response = client.get("/api/v1/settings")

        hitl = response.json()["hitl_settings"]
        assert hitl["require_approval_for_patches"] is True
        assert hitl["require_approval_for_deployments"] is True
        assert hitl["auto_approve_minor_patches"] is False
        assert hitl["approval_timeout_hours"] == 24
        assert hitl["min_approvers"] == 1

    def test_get_settings_includes_mcp_defaults(self, test_client):
        """Test that MCP settings include expected defaults."""
        client, _ = test_client
        response = client.get("/api/v1/settings")

        mcp = response.json()["mcp_settings"]
        assert mcp["enabled"] is False
        assert mcp["gateway_url"] == ""
        assert mcp["monthly_budget_usd"] == 100.0
        assert mcp["daily_limit_usd"] == 10.0
        assert mcp["external_tools_enabled"] == []


class TestUpdateSettings:
    """Tests for PUT /api/v1/settings endpoint."""

    def test_update_settings_changes_mode(self, test_client):
        """Test that updating settings changes the mode."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings",
            json={
                "integration_mode": "enterprise",
                "hitl_settings": {
                    "require_approval_for_patches": True,
                    "require_approval_for_deployments": True,
                    "auto_approve_minor_patches": False,
                    "approval_timeout_hours": 24,
                    "min_approvers": 1,
                    "notify_on_approval_request": True,
                    "notify_on_approval_timeout": True,
                },
                "mcp_settings": {
                    "enabled": True,
                    "gateway_url": "https://gateway.example.com",
                    "api_key": "test-key",
                    "monthly_budget_usd": 200.0,
                    "daily_limit_usd": 20.0,
                    "external_tools_enabled": ["slack"],
                    "rate_limit": {
                        "requests_per_minute": 100,
                        "requests_per_hour": 2000,
                    },
                },
                "security_settings": {
                    "enforce_air_gap": False,
                    "block_external_network": True,
                    "sandbox_isolation_level": "vpc",
                    "audit_all_actions": True,
                    "retain_logs_for_days": 365,
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["integration_mode"] == "enterprise"
        assert data["mcp_settings"]["enabled"] is True
        assert data["mcp_settings"]["monthly_budget_usd"] == 200.0

    def test_update_settings_persists_changes(self, test_client):
        """Test that settings changes persist across requests."""
        client, _ = test_client
        # Update
        client.put(
            "/api/v1/settings",
            json={
                "integration_mode": "hybrid",
                "hitl_settings": {
                    "require_approval_for_patches": False,
                    "require_approval_for_deployments": True,
                    "auto_approve_minor_patches": True,
                    "approval_timeout_hours": 48,
                    "min_approvers": 2,
                    "notify_on_approval_request": True,
                    "notify_on_approval_timeout": False,
                },
                "mcp_settings": {
                    "enabled": False,
                    "gateway_url": "",
                    "api_key": "",
                    "monthly_budget_usd": 100.0,
                    "daily_limit_usd": 10.0,
                    "external_tools_enabled": [],
                    "rate_limit": {
                        "requests_per_minute": 60,
                        "requests_per_hour": 1000,
                    },
                },
                "security_settings": {
                    "enforce_air_gap": False,
                    "block_external_network": True,
                    "sandbox_isolation_level": "full",
                    "audit_all_actions": True,
                    "retain_logs_for_days": 730,
                },
            },
        )

        # Verify persistence
        response = client.get("/api/v1/settings")
        data = response.json()

        assert data["integration_mode"] == "hybrid"
        assert data["hitl_settings"]["require_approval_for_patches"] is False
        assert data["hitl_settings"]["min_approvers"] == 2
        assert data["security_settings"]["sandbox_isolation_level"] == "full"


# ============================================================================
# Integration Mode Tests
# ============================================================================


class TestIntegrationMode:
    """Tests for /api/v1/settings/integration-mode endpoints."""

    def test_get_integration_mode_returns_defense_by_default(self, test_client):
        """Test that default mode is defense."""
        client, _ = test_client
        response = client.get("/api/v1/settings/integration-mode")

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "defense"
        assert data["mcp_enabled"] is False
        assert "description" in data

    def test_update_integration_mode_to_enterprise(self, test_client):
        """Test switching to enterprise mode."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings/integration-mode",
            json={"mode": "enterprise"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "enterprise"

    def test_update_integration_mode_to_hybrid(self, test_client):
        """Test switching to hybrid mode."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings/integration-mode",
            json={"mode": "hybrid"},
        )

        assert response.status_code == 200
        assert response.json()["mode"] == "hybrid"

    def test_update_integration_mode_invalid_mode_returns_400(self, test_client):
        """Test that invalid mode returns 400 error."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings/integration-mode",
            json={"mode": "invalid_mode"},
        )

        assert response.status_code == 400
        assert "Invalid mode" in response.json()["detail"]

    def test_defense_mode_disables_mcp(self, test_client):
        """Test that switching to defense mode disables MCP."""
        client, mock_service = test_client

        # First enable MCP in enterprise mode
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}
        mock_service._store["platform"]["mcp"]["enabled"] = True

        # Switch to defense
        response = client.put(
            "/api/v1/settings/integration-mode",
            json={"mode": "defense"},
        )

        assert response.status_code == 200
        assert response.json()["mcp_enabled"] is False
        assert mock_service._store["platform"]["mcp"]["enabled"] is False

    def test_mode_case_insensitive(self, test_client):
        """Test that mode is case-insensitive."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings/integration-mode",
            json={"mode": "ENTERPRISE"},
        )

        assert response.status_code == 200
        assert response.json()["mode"] == "enterprise"


# ============================================================================
# HITL Settings Tests
# ============================================================================


class TestHitlSettings:
    """Tests for /api/v1/settings/hitl endpoints."""

    def test_get_hitl_settings(self, test_client):
        """Test getting HITL settings."""
        client, _ = test_client
        response = client.get("/api/v1/settings/hitl")

        assert response.status_code == 200
        data = response.json()
        assert "require_approval_for_patches" in data
        assert "approval_timeout_hours" in data
        assert "min_approvers" in data

    def test_update_hitl_settings(self, test_client):
        """Test updating HITL settings."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings/hitl",
            json={
                "require_approval_for_patches": False,
                "require_approval_for_deployments": True,
                "auto_approve_minor_patches": True,
                "approval_timeout_hours": 72,
                "min_approvers": 3,
                "notify_on_approval_request": True,
                "notify_on_approval_timeout": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["require_approval_for_patches"] is False
        assert data["auto_approve_minor_patches"] is True
        assert data["approval_timeout_hours"] == 72
        assert data["min_approvers"] == 3

    def test_hitl_settings_persist(self, test_client):
        """Test that HITL settings changes persist."""
        client, _ = test_client
        client.put(
            "/api/v1/settings/hitl",
            json={
                "require_approval_for_patches": True,
                "require_approval_for_deployments": False,
                "auto_approve_minor_patches": True,
                "approval_timeout_hours": 12,
                "min_approvers": 1,
                "notify_on_approval_request": False,
                "notify_on_approval_timeout": True,
            },
        )

        response = client.get("/api/v1/settings/hitl")
        data = response.json()
        assert data["require_approval_for_deployments"] is False
        assert data["approval_timeout_hours"] == 12


# ============================================================================
# MCP Settings Tests
# ============================================================================


class TestMcpSettings:
    """Tests for /api/v1/settings/mcp endpoints."""

    def test_get_mcp_settings_in_defense_mode(self, test_client):
        """Test that MCP settings are disabled in defense mode."""
        client, _ = test_client
        response = client.get("/api/v1/settings/mcp")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["external_tools_enabled"] == []

    def test_get_mcp_settings_in_enterprise_mode(self, test_client):
        """Test getting MCP settings in enterprise mode."""
        client, mock_service = test_client
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}
        mock_service._store["platform"]["mcp"]["enabled"] = True
        mock_service._store["platform"]["mcp"][
            "gateway_url"
        ] = "https://gateway.example.com"

        response = client.get("/api/v1/settings/mcp")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["gateway_url"] == "https://gateway.example.com"

    def test_cannot_enable_mcp_in_defense_mode(self, test_client):
        """Test that MCP cannot be enabled in defense mode."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings/mcp",
            json={
                "enabled": True,
                "gateway_url": "https://gateway.example.com",
                "api_key": "test-key",
                "monthly_budget_usd": 100.0,
                "daily_limit_usd": 10.0,
                "external_tools_enabled": [],
                "rate_limit": {"requests_per_minute": 60, "requests_per_hour": 1000},
            },
        )

        assert response.status_code == 400
        assert "Defense mode" in response.json()["detail"]

    def test_can_enable_mcp_in_enterprise_mode(self, test_client):
        """Test that MCP can be enabled in enterprise mode."""
        client, mock_service = test_client
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}

        response = client.put(
            "/api/v1/settings/mcp",
            json={
                "enabled": True,
                "gateway_url": "https://gateway.example.com",
                "api_key": "secret-key",
                "monthly_budget_usd": 500.0,
                "daily_limit_usd": 50.0,
                "external_tools_enabled": ["slack", "jira"],
                "rate_limit": {"requests_per_minute": 120, "requests_per_hour": 3000},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["monthly_budget_usd"] == 500.0
        assert "slack" in data["external_tools_enabled"]
        assert "jira" in data["external_tools_enabled"]

    def test_update_mcp_budget_settings(self, test_client):
        """Test updating MCP budget settings."""
        client, mock_service = test_client
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}

        response = client.put(
            "/api/v1/settings/mcp",
            json={
                "enabled": False,
                "gateway_url": "",
                "api_key": "",
                "monthly_budget_usd": 1000.0,
                "daily_limit_usd": 100.0,
                "external_tools_enabled": [],
                "rate_limit": {"requests_per_minute": 200, "requests_per_hour": 5000},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["monthly_budget_usd"] == 1000.0
        assert data["daily_limit_usd"] == 100.0
        assert data["rate_limit"]["requests_per_minute"] == 200


class TestMcpTools:
    """Tests for /api/v1/settings/mcp/tools endpoint."""

    def test_get_available_external_tools(self, test_client):
        """Test getting list of available external tools."""
        client, _ = test_client
        response = client.get("/api/v1/settings/mcp/tools")

        assert response.status_code == 200
        tools = response.json()
        assert len(tools) == 5  # slack, jira, pagerduty, github, datadog

        tool_ids = [t["id"] for t in tools]
        assert "slack" in tool_ids
        assert "jira" in tool_ids
        assert "pagerduty" in tool_ids
        assert "github" in tool_ids
        assert "datadog" in tool_ids

    def test_tools_have_required_fields(self, test_client):
        """Test that tools have all required fields."""
        client, _ = test_client
        response = client.get("/api/v1/settings/mcp/tools")

        for tool in response.json():
            assert "id" in tool
            assert "name" in tool
            assert "category" in tool
            assert "description" in tool


class TestMcpConnectionTest:
    """Tests for /api/v1/settings/mcp/test-connection endpoint."""

    def test_connection_test_requires_gateway_url(self, test_client):
        """Test that connection test requires gateway URL."""
        client, mock_service = test_client
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}

        response = client.post(
            "/api/v1/settings/mcp/test-connection",
            json={"gatewayUrl": "", "apiKey": "test-key"},
        )

        assert response.status_code == 400
        assert "Gateway URL" in response.json()["detail"]

    def test_connection_test_requires_api_key(self, test_client):
        """Test that connection test requires API key."""
        client, mock_service = test_client
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}

        response = client.post(
            "/api/v1/settings/mcp/test-connection",
            json={"gatewayUrl": "https://gateway.example.com", "apiKey": ""},
        )

        assert response.status_code == 400
        assert "API key" in response.json()["detail"]

    def test_connection_test_fails_in_defense_mode(self, test_client):
        """Test that connection test fails in defense mode."""
        client, _ = test_client
        response = client.post(
            "/api/v1/settings/mcp/test-connection",
            json={"gatewayUrl": "https://gateway.example.com", "apiKey": "test-key"},
        )

        assert response.status_code == 400
        assert "Defense mode" in response.json()["detail"]

    def test_connection_test_succeeds_with_valid_url(self, test_client):
        """Test that connection test succeeds with valid inputs."""
        client, mock_service = test_client
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}

        response = client.post(
            "/api/v1/settings/mcp/test-connection",
            json={"gatewayUrl": "https://gateway.example.com", "apiKey": "test-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "latency_ms" in data

    def test_connection_test_fails_with_invalid_url(self, test_client):
        """Test that connection test fails with invalid URL format."""
        client, mock_service = test_client
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}

        response = client.post(
            "/api/v1/settings/mcp/test-connection",
            json={"gatewayUrl": "not-a-valid-url", "apiKey": "test-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid" in data["message"]


class TestMcpUsage:
    """Tests for /api/v1/settings/mcp/usage endpoint."""

    def test_get_mcp_usage_returns_stats(self, test_client):
        """Test getting MCP usage statistics."""
        client, _ = test_client
        response = client.get("/api/v1/settings/mcp/usage")

        assert response.status_code == 200
        data = response.json()
        assert "current_month_cost" in data
        assert "current_day_cost" in data
        assert "total_invocations" in data
        assert "budget_remaining" in data

    def test_get_mcp_usage_shows_budget_remaining(self, test_client):
        """Test that budget remaining is calculated correctly."""
        client, _ = test_client
        response = client.get("/api/v1/settings/mcp/usage")

        data = response.json()
        # Default budget is 100, with 0 spent
        assert data["budget_remaining"] == 100.0
        assert data["current_month_cost"] == 0.0


# ============================================================================
# Cross-Feature Tests
# ============================================================================


class TestModeTransitions:
    """Tests for integration mode transitions and side effects."""

    def test_enterprise_to_defense_disables_mcp(self, test_client):
        """Test that transitioning from enterprise to defense disables MCP."""
        client, mock_service = test_client

        # Setup: enterprise mode with MCP enabled
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}
        mock_service._store["platform"]["mcp"]["enabled"] = True
        mock_service._store["platform"]["mcp"][
            "gateway_url"
        ] = "https://gateway.example.com"
        mock_service._store["platform"]["mcp"]["external_tools_enabled"] = [
            "slack",
            "jira",
        ]

        # Transition to defense
        response = client.put(
            "/api/v1/settings/integration-mode",
            json={"mode": "defense"},
        )

        assert response.status_code == 200
        assert mock_service._store["platform"]["mcp"]["enabled"] is False

    def test_defense_to_enterprise_allows_mcp_enable(self, test_client):
        """Test that transitioning to enterprise allows enabling MCP."""
        client, mock_service = test_client

        # Start in defense (default)
        assert mock_service._store["platform"]["integration_mode"]["mode"] == "defense"

        # Transition to enterprise
        client.put(
            "/api/v1/settings/integration-mode",
            json={"mode": "enterprise"},
        )

        # Now MCP can be enabled
        response = client.put(
            "/api/v1/settings/mcp",
            json={
                "enabled": True,
                "gateway_url": "https://gateway.example.com",
                "api_key": "test",
                "monthly_budget_usd": 100.0,
                "daily_limit_usd": 10.0,
                "external_tools_enabled": ["slack"],
                "rate_limit": {"requests_per_minute": 60, "requests_per_hour": 1000},
            },
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is True

    def test_hybrid_mode_preserves_mcp_state(self, test_client):
        """Test that hybrid mode preserves MCP enabled state."""
        client, mock_service = test_client

        # Setup: enterprise with MCP enabled
        mock_service._store["platform"]["integration_mode"] = {"mode": "enterprise"}
        mock_service._store["platform"]["mcp"]["enabled"] = True

        # Transition to hybrid
        response = client.put(
            "/api/v1/settings/integration-mode",
            json={"mode": "hybrid"},
        )

        assert response.status_code == 200
        # MCP should remain enabled in hybrid mode
        assert mock_service._store["platform"]["mcp"]["enabled"] is True


class TestSecurityConstraints:
    """Tests for security constraints based on mode."""

    def test_defense_mode_blocks_mcp_enable(self, test_client):
        """Test that defense mode blocks MCP enable."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings/mcp",
            json={
                "enabled": True,
                "gateway_url": "https://gateway.example.com",
                "api_key": "test",
                "monthly_budget_usd": 100.0,
                "daily_limit_usd": 10.0,
                "external_tools_enabled": [],
                "rate_limit": {"requests_per_minute": 60, "requests_per_hour": 1000},
            },
        )

        assert response.status_code == 400
        assert "Defense mode" in response.json()["detail"]

    def test_defense_mode_returns_disabled_mcp(self, test_client):
        """Test that defense mode always returns disabled MCP settings."""
        client, mock_service = test_client

        # Even if someone manually sets enabled=True in the store
        mock_service._store["platform"]["mcp"]["enabled"] = True

        response = client.get("/api/v1/settings/mcp")

        # Should still return disabled due to defense mode
        assert response.json()["enabled"] is False


# ============================================================================
# Security Settings Tests
# ============================================================================


class TestSecuritySettings:
    """Tests for /api/v1/settings/security endpoints."""

    def test_get_security_settings(self, test_client):
        """Test getting security settings returns defaults."""
        client, _ = test_client
        response = client.get("/api/v1/settings/security")

        assert response.status_code == 200
        data = response.json()
        assert "enforce_air_gap" in data
        assert "block_external_network" in data
        assert "sandbox_isolation_level" in data
        assert "audit_all_actions" in data
        assert "retain_logs_for_days" in data

    def test_get_security_settings_default_retention(self, test_client):
        """Test that default log retention is 365 days."""
        client, _ = test_client
        response = client.get("/api/v1/settings/security")

        data = response.json()
        assert data["retain_logs_for_days"] == 365

    def test_update_security_settings_log_retention(self, test_client):
        """Test updating log retention setting."""
        client, _ = test_client
        response = client.put(
            "/api/v1/settings/security",
            json={
                "enforce_air_gap": False,
                "block_external_network": True,
                "sandbox_isolation_level": "vpc",
                "audit_all_actions": True,
                "retain_logs_for_days": 90,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["retain_logs_for_days"] == 90

    def test_security_settings_persist(self, test_client):
        """Test that security settings changes persist."""
        client, _ = test_client

        # Update settings
        client.put(
            "/api/v1/settings/security",
            json={
                "enforce_air_gap": True,
                "block_external_network": False,
                "sandbox_isolation_level": "full",
                "audit_all_actions": False,
                "retain_logs_for_days": 180,
            },
        )

        # Verify persistence
        response = client.get("/api/v1/settings/security")
        data = response.json()
        assert data["enforce_air_gap"] is True
        assert data["block_external_network"] is False
        assert data["sandbox_isolation_level"] == "full"
        assert data["audit_all_actions"] is False
        assert data["retain_logs_for_days"] == 180

    def test_log_retention_cmmc_compliant_values(self, test_client):
        """Test various CMMC-compliant log retention values."""
        client, _ = test_client

        # Test 90 days (CMMC L2 minimum)
        response = client.put(
            "/api/v1/settings/security",
            json={
                "enforce_air_gap": False,
                "block_external_network": True,
                "sandbox_isolation_level": "vpc",
                "audit_all_actions": True,
                "retain_logs_for_days": 90,
            },
        )
        assert response.status_code == 200
        assert response.json()["retain_logs_for_days"] == 90

        # Test 365 days (GovCloud recommended)
        response = client.put(
            "/api/v1/settings/security",
            json={
                "enforce_air_gap": False,
                "block_external_network": True,
                "sandbox_isolation_level": "vpc",
                "audit_all_actions": True,
                "retain_logs_for_days": 365,
            },
        )
        assert response.status_code == 200
        assert response.json()["retain_logs_for_days"] == 365
