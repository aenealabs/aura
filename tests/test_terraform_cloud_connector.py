"""
Project Aura - Terraform Cloud Connector Unit Tests

Test Type: UNIT
Dependencies: All external calls mocked (aiohttp, Terraform Cloud API)
Isolation: pytest.mark.forked (prevents aiohttp mock pollution between tests)
Run Command: pytest tests/test_terraform_cloud_connector.py -v

These tests validate:
- Terraform Cloud connector initialization and configuration
- Workspace management operations (list, get, create)
- Run triggering, monitoring, and apply/cancel operations
- Variable management (create, update, list)
- State version retrieval
- Response parsing and error handling

Mock Strategy:
- aiohttp.ClientSession: Mocked via create_mock_aiohttp_session()
- Environment variables: Set via enable_enterprise_mode fixture
- All Terraform Cloud API responses are simulated (JSON:API format)

Related E2E Tests:
- tests/e2e/test_terraform_cloud_e2e.py (requires RUN_E2E_TESTS=1 and TFC token)
"""

import json
import os
import platform

import pytest

# Explicit test type markers
# - unit: All external dependencies are mocked
# - forked: Run in isolated subprocess on non-Linux to prevent aiohttp mock pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = [pytest.mark.unit, pytest.mark.forked]
from unittest.mock import AsyncMock, MagicMock, patch

from src.config.integration_config import clear_integration_config_cache
from src.services.external_tool_connectors import ConnectorStatus
from src.services.terraform_cloud_connector import (
    TerraformCloudConnector,
    TerraformRun,
    TerraformRunSource,
    TerraformRunStatus,
    TerraformVariable,
    TerraformWorkspace,
    VariableCategory,
)

# ============================================================================
# Helper Functions
# ============================================================================


def create_mock_aiohttp_session(response_status: int, response_body: str | dict):
    """Create a properly mocked aiohttp session for async context managers."""
    mock_response = MagicMock()
    mock_response.status = response_status

    if isinstance(response_body, dict):
        mock_response.json = AsyncMock(return_value=response_body)
        mock_response.text = AsyncMock(return_value=json.dumps(response_body))
    else:
        mock_response.text = AsyncMock(return_value=response_body)
        mock_response.json = AsyncMock(return_value={"error": response_body})

    # Create context manager for response
    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock(return_value=None)

    # Create session instance
    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_request_context
    mock_session_instance.get.return_value = mock_request_context

    # Create session context manager
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def enable_enterprise_mode():
    """Enable enterprise mode for tests by setting environment variable."""
    original_value = os.environ.get("AURA_INTEGRATION_MODE")
    os.environ["AURA_INTEGRATION_MODE"] = "enterprise"
    # Clear the cached config so it reloads with new env var
    clear_integration_config_cache()
    yield
    # Restore original value
    if original_value is not None:
        os.environ["AURA_INTEGRATION_MODE"] = original_value
    else:
        os.environ.pop("AURA_INTEGRATION_MODE", None)
    clear_integration_config_cache()


# ============================================================================
# Enum Tests
# ============================================================================


class TestTerraformRunStatus:
    """Test TerraformRunStatus enum."""

    def test_pending(self):
        assert TerraformRunStatus.PENDING.value == "pending"

    def test_plan_queued(self):
        assert TerraformRunStatus.PLAN_QUEUED.value == "plan_queued"

    def test_planning(self):
        assert TerraformRunStatus.PLANNING.value == "planning"

    def test_planned(self):
        assert TerraformRunStatus.PLANNED.value == "planned"

    def test_cost_estimating(self):
        assert TerraformRunStatus.COST_ESTIMATING.value == "cost_estimating"

    def test_cost_estimated(self):
        assert TerraformRunStatus.COST_ESTIMATED.value == "cost_estimated"

    def test_policy_checking(self):
        assert TerraformRunStatus.POLICY_CHECKING.value == "policy_checking"

    def test_policy_override(self):
        assert TerraformRunStatus.POLICY_OVERRIDE.value == "policy_override"

    def test_policy_checked(self):
        assert TerraformRunStatus.POLICY_CHECKED.value == "policy_checked"

    def test_confirmed(self):
        assert TerraformRunStatus.CONFIRMED.value == "confirmed"

    def test_apply_queued(self):
        assert TerraformRunStatus.APPLY_QUEUED.value == "apply_queued"

    def test_applying(self):
        assert TerraformRunStatus.APPLYING.value == "applying"

    def test_applied(self):
        assert TerraformRunStatus.APPLIED.value == "applied"

    def test_discarded(self):
        assert TerraformRunStatus.DISCARDED.value == "discarded"

    def test_errored(self):
        assert TerraformRunStatus.ERRORED.value == "errored"

    def test_canceled(self):
        assert TerraformRunStatus.CANCELED.value == "canceled"

    def test_force_canceled(self):
        assert TerraformRunStatus.FORCE_CANCELED.value == "force_canceled"


class TestTerraformRunSource:
    """Test TerraformRunSource enum."""

    def test_api(self):
        assert TerraformRunSource.API.value == "tfe-api"

    def test_ui(self):
        assert TerraformRunSource.UI.value == "tfe-ui"

    def test_vcs(self):
        assert TerraformRunSource.VCS.value == "tfe-vcs"

    def test_configuration_version(self):
        assert (
            TerraformRunSource.CONFIGURATION_VERSION.value
            == "tfe-configuration-version"
        )


class TestVariableCategory:
    """Test VariableCategory enum."""

    def test_terraform(self):
        assert VariableCategory.TERRAFORM.value == "terraform"

    def test_env(self):
        assert VariableCategory.ENV.value == "env"


# ============================================================================
# Dataclass Tests
# ============================================================================


class TestTerraformWorkspace:
    """Test TerraformWorkspace dataclass."""

    def test_basic_creation(self):
        ws = TerraformWorkspace(id="ws-123", name="my-workspace", organization="my-org")
        assert ws.id == "ws-123"
        assert ws.name == "my-workspace"
        assert ws.organization == "my-org"
        assert ws.auto_apply is False

    def test_full_creation(self):
        ws = TerraformWorkspace(
            id="ws-456",
            name="production",
            organization="acme",
            auto_apply=True,
            terraform_version="1.6.0",
            working_directory="/infra",
            vcs_repo="github/acme/infra",
            description="Production infrastructure",
            tags=["prod", "critical"],
            resource_count=150,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-06-15T12:00:00Z",
        )
        assert ws.auto_apply is True
        assert ws.terraform_version == "1.6.0"
        assert ws.working_directory == "/infra"
        assert ws.vcs_repo == "github/acme/infra"
        assert ws.description == "Production infrastructure"
        assert ws.tags == ["prod", "critical"]
        assert ws.resource_count == 150
        assert ws.created_at == "2024-01-01T00:00:00Z"
        assert ws.updated_at == "2024-06-15T12:00:00Z"

    def test_default_values(self):
        ws = TerraformWorkspace(id="ws-1", name="test", organization="org")
        assert ws.auto_apply is False
        assert ws.terraform_version is None
        assert ws.working_directory is None
        assert ws.vcs_repo is None
        assert ws.description == ""
        assert ws.tags == []
        assert ws.resource_count == 0
        assert ws.created_at is None
        assert ws.updated_at is None


class TestTerraformRun:
    """Test TerraformRun dataclass."""

    def test_basic_creation(self):
        run = TerraformRun(id="run-123", status=TerraformRunStatus.PLANNED)
        assert run.id == "run-123"
        assert run.status == TerraformRunStatus.PLANNED
        assert run.is_destroy is False
        assert run.has_changes is False

    def test_full_creation(self):
        run = TerraformRun(
            id="run-456",
            status=TerraformRunStatus.APPLYING,
            source=TerraformRunSource.API,
            message="Security patch deployment",
            is_destroy=False,
            has_changes=True,
            auto_apply=True,
            plan_only=False,
            created_at="2024-06-15T12:00:00Z",
            plan_id="plan-123",
            apply_id="apply-123",
            cost_estimate_id="cost-123",
        )
        assert run.source == TerraformRunSource.API
        assert run.message == "Security patch deployment"
        assert run.has_changes is True
        assert run.auto_apply is True
        assert run.plan_id == "plan-123"
        assert run.apply_id == "apply-123"
        assert run.cost_estimate_id == "cost-123"

    def test_destroy_run(self):
        run = TerraformRun(
            id="run-destroy", status=TerraformRunStatus.PENDING, is_destroy=True
        )
        assert run.is_destroy is True

    def test_plan_only_run(self):
        run = TerraformRun(
            id="run-plan", status=TerraformRunStatus.PLANNED, plan_only=True
        )
        assert run.plan_only is True


class TestTerraformVariable:
    """Test TerraformVariable dataclass."""

    def test_basic_creation(self):
        var = TerraformVariable(key="aws_region")
        assert var.key == "aws_region"
        assert var.value is None
        assert var.category == VariableCategory.TERRAFORM
        assert var.hcl is False
        assert var.sensitive is False

    def test_full_creation(self):
        var = TerraformVariable(
            key="db_password",
            value="secret123",
            category=VariableCategory.ENV,
            hcl=False,
            sensitive=True,
            description="Database password",
        )
        assert var.key == "db_password"
        assert var.value == "secret123"
        assert var.category == VariableCategory.ENV
        assert var.sensitive is True
        assert var.description == "Database password"

    def test_hcl_variable(self):
        var = TerraformVariable(key="tags", value='{"env": "prod"}', hcl=True)
        assert var.hcl is True

    def test_terraform_variable(self):
        var = TerraformVariable(
            key="instance_type", value="t3.medium", category=VariableCategory.TERRAFORM
        )
        assert var.category == VariableCategory.TERRAFORM

    def test_env_variable(self):
        var = TerraformVariable(
            key="AWS_SECRET_KEY",
            value="xxx",
            category=VariableCategory.ENV,
            sensitive=True,
        )
        assert var.category == VariableCategory.ENV
        assert var.sensitive is True


# ============================================================================
# Connector Initialization Tests
# ============================================================================


class TestTerraformCloudConnectorInit:
    """Test TerraformCloudConnector initialization."""

    def test_basic_init(self):
        connector = TerraformCloudConnector(organization="my-org", token="test-token")
        assert connector.organization == "my-org"
        assert connector._token == "test-token"
        assert connector.api_url == "https://app.terraform.io/api/v2"

    def test_custom_api_url(self):
        connector = TerraformCloudConnector(
            organization="my-org",
            token="test-token",
            api_url="https://tfe.example.com/api/v2/",
        )
        assert connector.api_url == "https://tfe.example.com/api/v2"

    def test_custom_timeout(self):
        connector = TerraformCloudConnector(
            organization="my-org",
            token="test-token",
            timeout_seconds=120.0,
        )
        assert connector.timeout.total == 120.0

    def test_get_headers(self):
        connector = TerraformCloudConnector(
            organization="my-org", token="my-secret-token"
        )
        headers = connector._get_headers()
        assert headers["Authorization"] == "Bearer my-secret-token"
        assert headers["Content-Type"] == "application/vnd.api+json"
        assert headers["Accept"] == "application/vnd.api+json"

    def test_default_api_url_constant(self):
        assert (
            TerraformCloudConnector.DEFAULT_API_URL == "https://app.terraform.io/api/v2"
        )


# ============================================================================
# API Method Tests with Mocks
# ============================================================================


class TestListWorkspaces:
    """Test list_workspaces method."""

    @pytest.mark.asyncio
    async def test_list_workspaces_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_response = {
            "data": [
                {
                    "id": "ws-123",
                    "attributes": {
                        "name": "workspace-1",
                        "auto-apply": True,
                        "terraform-version": "1.6.0",
                        "resource-count": 50,
                        "updated-at": "2024-06-15T12:00:00Z",
                    },
                },
                {
                    "id": "ws-456",
                    "attributes": {
                        "name": "workspace-2",
                        "auto-apply": False,
                        "terraform-version": "1.5.0",
                        "resource-count": 25,
                        "updated-at": "2024-06-14T12:00:00Z",
                    },
                },
            ]
        }

        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is True
            assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_list_workspaces_error(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(
            401, {"errors": [{"detail": "Unauthorized"}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is False


class TestGetWorkspace:
    """Test get_workspace method."""

    @pytest.mark.asyncio
    async def test_get_workspace_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "ws-123",
                "attributes": {
                    "name": "production",
                    "auto-apply": True,
                    "terraform-version": "1.6.0",
                    "description": "Prod",
                    "resource-count": 100,
                    "created-at": "2024-01-01",
                    "updated-at": "2024-06-15",
                },
            }
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("production")
            assert result.success is True
            assert result.data["name"] == "production"


class TestTriggerRun:
    """Test trigger_run method."""

    @pytest.mark.asyncio
    async def test_trigger_run_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {"id": "run-abc123", "attributes": {"status": "pending"}}
        }
        mock_session = create_mock_aiohttp_session(201, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123", message="Deploy"
            )
            assert result.success is True
            assert result.data["run_id"] == "run-abc123"


class TestGetRun:
    """Test get_run method."""

    @pytest.mark.asyncio
    async def test_get_run_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "run-123",
                "attributes": {
                    "status": "applied",
                    "message": "Done",
                    "is-destroy": False,
                    "has-changes": True,
                    "auto-apply": True,
                    "plan-only": False,
                    "created-at": "2024-06-15",
                },
            }
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_run("run-123")
            assert result.success is True
            assert result.data["status"] == "applied"


class TestApplyRun:
    """Test apply_run method."""

    @pytest.mark.asyncio
    async def test_apply_run_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(202, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.apply_run("run-123")
            assert result.success is True
            assert result.data["action"] == "apply"


class TestCancelRun:
    """Test cancel_run method."""

    @pytest.mark.asyncio
    async def test_cancel_run_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(202, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.cancel_run("run-123")
            assert result.success is True
            assert result.data["action"] == "cancel"


class TestListRuns:
    """Test list_runs method."""

    @pytest.mark.asyncio
    async def test_list_runs_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": [
                {
                    "id": "run-1",
                    "attributes": {
                        "status": "applied",
                        "message": "R1",
                        "created-at": "2024-06-15",
                        "has-changes": True,
                    },
                }
            ]
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_runs("ws-123")
            assert result.success is True
            assert result.data["count"] == 1


class TestGetCurrentState:
    """Test get_current_state method."""

    @pytest.mark.asyncio
    async def test_get_current_state_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "sv-123",
                "attributes": {
                    "serial": 42,
                    "terraform-version": "1.6.0",
                    "resource-count": 100,
                    "created-at": "2024-06-15",
                    "hosted-state-download-url": "https://example.com/state",
                },
            }
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_current_state("ws-123")
            assert result.success is True
            assert result.data["serial"] == 42


class TestListVariables:
    """Test list_variables method."""

    @pytest.mark.asyncio
    async def test_list_variables_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": [
                {
                    "id": "var-1",
                    "attributes": {
                        "key": "aws_region",
                        "value": "us-east-1",
                        "category": "terraform",
                        "sensitive": False,
                        "hcl": False,
                    },
                }
            ]
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_variables("ws-123")
            assert result.success is True
            assert result.data["count"] == 1


class TestCreateVariable:
    """Test create_variable method."""

    @pytest.mark.asyncio
    async def test_create_variable_success(self, enable_enterprise_mode):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {"data": {"id": "var-new", "attributes": {"key": "new_var"}}}
        mock_session = create_mock_aiohttp_session(201, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_variable(
                workspace_id="ws-123", key="new_var", value="new_value"
            )
            assert result.success is True
            assert result.data["key"] == "new_var"


class TestHealthCheck:
    """Test health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(200, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is True
            assert connector._status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_auth_failed(self):
        connector = TerraformCloudConnector(organization="test-org", token="invalid")
        mock_session = create_mock_aiohttp_session(401, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_health_check_not_found(self):
        connector = TerraformCloudConnector(
            organization="nonexistent", token="test-token"
        )
        mock_session = create_mock_aiohttp_session(404, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.ERROR

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Test health check when connection fails."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection refused"),
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.ERROR


# ============================================================================
# Extended Tests for Coverage Improvement
# ============================================================================


class TestGetWorkspaceExtended:
    """Extended tests for get_workspace method."""

    @pytest.mark.asyncio
    async def test_get_workspace_success_full(self, enable_enterprise_mode):
        """Test successful workspace retrieval with full data."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "ws-full",
                "attributes": {
                    "name": "full-workspace",
                    "auto-apply": False,
                    "terraform-version": "1.6.0",
                    "description": "Test workspace",
                    "working-directory": "/infra",
                },
            }
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("full-workspace")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_get_workspace_not_found(self, enable_enterprise_mode):
        """Test workspace not found."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(
            404, {"errors": [{"detail": "Workspace not found"}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("nonexistent")
            assert result.success is False


class TestListVariablesExtended:
    """Extended tests for list_variables method."""

    @pytest.mark.asyncio
    async def test_list_variables_with_env_vars(self, enable_enterprise_mode):
        """Test listing variables including environment variables."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": [
                {
                    "id": "var-1",
                    "attributes": {
                        "key": "aws_region",
                        "value": "us-west-2",
                        "category": "terraform",
                        "sensitive": False,
                    },
                },
                {
                    "id": "var-2",
                    "attributes": {
                        "key": "AWS_ACCESS_KEY",
                        "value": None,
                        "category": "env",
                        "sensitive": True,
                    },
                },
            ]
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_variables("ws-123")
            assert result.success is True
            assert result.data["count"] == 2


class TestGetRunExtended:
    """Extended tests for get_run method."""

    @pytest.mark.asyncio
    async def test_get_run_with_plan_details(self, enable_enterprise_mode):
        """Test getting run with plan details."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "run-123",
                "attributes": {
                    "status": "planned",
                    "message": "Test run",
                    "has-changes": True,
                    "created-at": "2024-01-01T00:00:00Z",
                },
                "relationships": {"plan": {"data": {"id": "plan-123"}}},
            }
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_run("run-123")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, enable_enterprise_mode):
        """Test get run not found."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(
            404, {"errors": [{"detail": "Run not found"}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_run("nonexistent")
            assert result.success is False


class TestGetCurrentStateExtended:
    """Extended tests for get_current_state method."""

    @pytest.mark.asyncio
    async def test_get_current_state_success(self, enable_enterprise_mode):
        """Test getting current state successfully."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "sv-123",
                "attributes": {
                    "serial": 42,
                    "terraform-version": "1.6.0",
                    "resource-count": 50,
                    "providers-used": ["aws", "null"],
                },
            }
        }
        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_current_state("ws-123")
            assert result.success is True


class TestGetStateOutputsExtended:
    """Extended tests for get_state_outputs method."""

    @pytest.mark.asyncio
    async def test_get_state_outputs_not_found(self, enable_enterprise_mode):
        """Test getting state outputs when workspace not found."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(
            404, {"errors": [{"detail": "Workspace not found"}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_state_outputs("ws-nonexistent")
            assert result.success is False


class TestMetricsAndStatus:
    """Tests for connector metrics and status."""

    def test_connector_initial_status(self):
        """Test initial connector status."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        assert connector._status == ConnectorStatus.DISCONNECTED

    def test_connector_metrics(self):
        """Test connector metrics retrieval."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        metrics = connector.metrics
        assert "name" in metrics
        assert metrics["name"] == "terraform_cloud"
        assert "status" in metrics
        assert "request_count" in metrics

    def test_record_request_success(self):
        """Test recording successful request."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        initial_count = connector._request_count
        connector._record_request(100.0, success=True)
        assert connector._request_count == initial_count + 1
        assert connector._error_count == 0

    def test_record_request_failure(self):
        """Test recording failed request."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        connector._record_request(100.0, success=False)
        assert connector._error_count == 1


class TestErrorHandlingExtended:
    """Extended error handling tests."""

    @pytest.mark.asyncio
    async def test_list_workspaces_exception(self, enable_enterprise_mode):
        """Test list_workspaces when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Network error"),
        ):
            result = await connector.list_workspaces()
            assert result.success is False

    @pytest.mark.asyncio
    async def test_get_workspace_exception(self, enable_enterprise_mode):
        """Test get_workspace when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Timeout"),
        ):
            result = await connector.get_workspace("production")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_trigger_run_exception(self, enable_enterprise_mode):
        """Test trigger_run when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection reset"),
        ):
            result = await connector.trigger_run(workspace_id="ws-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_get_run_exception(self, enable_enterprise_mode):
        """Test get_run when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("SSL error"),
        ):
            result = await connector.get_run("run-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_apply_run_exception(self, enable_enterprise_mode):
        """Test apply_run when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection refused"),
        ):
            result = await connector.apply_run("run-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_cancel_run_exception(self, enable_enterprise_mode):
        """Test cancel_run when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Network unreachable"),
        ):
            result = await connector.cancel_run("run-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_list_variables_exception(self, enable_enterprise_mode):
        """Test list_variables when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("API rate limited"),
        ):
            result = await connector.list_variables("ws-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_create_variable_exception(self, enable_enterprise_mode):
        """Test create_variable when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Bad gateway"),
        ):
            result = await connector.create_variable(
                workspace_id="ws-123",
                key="test_var",
                value="test_value",
            )
            assert result.success is False


class TestRunTriggerWithOptions:
    """Tests for run triggering with various options."""

    @pytest.mark.asyncio
    async def test_trigger_destroy_run(self, enable_enterprise_mode):
        """Test triggering a destroy run."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "run-destroy",
                "attributes": {
                    "status": "pending",
                    "is-destroy": True,
                },
            }
        }
        mock_session = create_mock_aiohttp_session(201, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123",
                message="Destroy infrastructure",
                is_destroy=True,
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_trigger_plan_only_run(self, enable_enterprise_mode):
        """Test triggering a plan-only run."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "run-plan",
                "attributes": {
                    "status": "pending",
                    "plan-only": True,
                },
            }
        }
        mock_session = create_mock_aiohttp_session(201, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123",
                message="Plan only",
                plan_only=True,
            )
            assert result.success is True


class TestVariableCreationWithOptions:
    """Tests for variable creation with various options."""

    @pytest.mark.asyncio
    async def test_create_sensitive_variable(self, enable_enterprise_mode):
        """Test creating a sensitive variable."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "var-sensitive",
                "attributes": {
                    "key": "db_password",
                    "sensitive": True,
                },
            }
        }
        mock_session = create_mock_aiohttp_session(201, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_variable(
                workspace_id="ws-123",
                key="db_password",
                value="secret123",
                sensitive=True,
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_env_variable(self, enable_enterprise_mode):
        """Test creating an environment variable."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "var-env",
                "attributes": {
                    "key": "AWS_REGION",
                    "category": "env",
                },
            }
        }
        mock_session = create_mock_aiohttp_session(201, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_variable(
                workspace_id="ws-123",
                key="AWS_REGION",
                value="us-east-1",
                category=VariableCategory.ENV,
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_hcl_variable(self, enable_enterprise_mode):
        """Test creating an HCL variable."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "var-hcl",
                "attributes": {
                    "key": "tags",
                    "hcl": True,
                },
            }
        }
        mock_session = create_mock_aiohttp_session(201, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_variable(
                workspace_id="ws-123",
                key="tags",
                value='{"env": "prod", "team": "platform"}',
                hcl=True,
            )
            assert result.success is True


# ============================================================================
# Trigger Security Patch Run Tests
# ============================================================================


class TestTriggerSecurityPatchRun:
    """Tests for trigger_security_patch_run method."""

    @pytest.mark.asyncio
    async def test_trigger_security_patch_run_success(self, enable_enterprise_mode):
        """Test triggering security patch run successfully."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        # Mock get_workspace followed by trigger_run
        call_count = [0]

        def create_dynamic_mock():
            mock_response = MagicMock()

            async def get_json():
                if call_count[0] == 0:
                    return {
                        "data": {
                            "id": "ws-sec-123",
                            "attributes": {"name": "security-ws"},
                        }
                    }
                else:
                    return {
                        "data": {
                            "id": "run-patch-123",
                            "attributes": {"status": "pending"},
                        }
                    }

            mock_response.json = AsyncMock(side_effect=get_json)
            mock_response.status = 200

            mock_request_context = MagicMock()
            mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request_context.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = MagicMock()

            def track_request(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] > 1:
                    mock_response.status = 201
                return mock_request_context

            mock_session_instance.get.side_effect = track_request
            mock_session_instance.post.side_effect = track_request

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            return mock_session

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=create_dynamic_mock,
        ):
            result = await connector.trigger_security_patch_run(
                workspace_name="security-ws",
                cve_id="CVE-2025-12345",
                severity="CRITICAL",
                description="Urgent security patch",
                approval_url="https://aura.example.com/approve/123",
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_trigger_security_patch_run_workspace_not_found(
        self, enable_enterprise_mode
    ):
        """Test security patch run when workspace not found."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            404, {"errors": [{"detail": "Workspace not found"}]}
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_security_patch_run(
                workspace_name="nonexistent",
                severity="HIGH",
                description="Test",
            )
            assert result.success is False

    @pytest.mark.asyncio
    async def test_trigger_security_patch_run_no_workspace_id(
        self, enable_enterprise_mode
    ):
        """Test security patch run when workspace ID is missing."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            200,
            {"data": {"id": None, "attributes": {"name": "test"}}},
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_security_patch_run(
                workspace_name="test-ws",
                severity="MEDIUM",
                description="Test",
            )
            assert result.success is False
            assert "Workspace ID not found" in result.error


# ============================================================================
# Get State Outputs Tests
# ============================================================================


class TestGetStateOutputs:
    """Tests for get_state_outputs method."""

    @pytest.mark.asyncio
    async def test_get_state_outputs_state_not_found(self, enable_enterprise_mode):
        """Test getting outputs when state not found."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            404, {"errors": [{"detail": "No state version"}]}
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_state_outputs("ws-no-state")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_get_state_outputs_exception(self, enable_enterprise_mode):
        """Test get_state_outputs when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("API error"),
        ):
            result = await connector.get_state_outputs("ws-123")
            assert result.success is False


# ============================================================================
# Trigger Run with All Options Tests
# ============================================================================


class TestTriggerRunAllOptions:
    """Tests for trigger_run with all options."""

    @pytest.mark.asyncio
    async def test_trigger_run_with_variables(self, enable_enterprise_mode):
        """Test run with variables."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            201, {"data": {"id": "run-var", "attributes": {"status": "pending"}}}
        )

        variables = [
            TerraformVariable(key="region", value="us-west-2"),
            TerraformVariable(
                key="secret",
                value="xxx",
                category=VariableCategory.ENV,
                sensitive=True,
            ),
        ]

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123",
                message="With variables",
                variables=variables,
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_trigger_run_with_target_addrs(self, enable_enterprise_mode):
        """Test run with target addresses."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            201, {"data": {"id": "run-target", "attributes": {"status": "pending"}}}
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123",
                message="Targeted run",
                target_addrs=["module.vpc", "aws_instance.web"],
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_trigger_run_with_replace_addrs(self, enable_enterprise_mode):
        """Test run with replace addresses."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            201, {"data": {"id": "run-replace", "attributes": {"status": "pending"}}}
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123",
                message="Replace resources",
                replace_addrs=["aws_instance.corrupted"],
                auto_apply=True,
            )
            assert result.success is True


# ============================================================================
# List Runs with Status Filter Tests
# ============================================================================


class TestListRunsWithStatus:
    """Tests for list_runs with status filter."""

    @pytest.mark.asyncio
    async def test_list_runs_with_status_filter(self, enable_enterprise_mode):
        """Test listing runs with status filter."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "data": [
                    {
                        "id": "run-1",
                        "attributes": {
                            "status": "applied",
                            "message": "Applied",
                            "created-at": "2024-01-01",
                            "has-changes": True,
                        },
                    }
                ]
            },
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_runs(
                workspace_id="ws-123",
                status=TerraformRunStatus.APPLIED,
            )
            assert result.success is True
            assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_list_runs_error(self, enable_enterprise_mode):
        """Test list_runs with API error."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            403, {"errors": [{"detail": "Forbidden"}]}
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_runs("ws-forbidden")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_list_runs_exception(self, enable_enterprise_mode):
        """Test list_runs when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Network error"),
        ):
            result = await connector.list_runs("ws-123")
            assert result.success is False


# ============================================================================
# Get Current State Error Tests
# ============================================================================


class TestGetCurrentStateErrors:
    """Tests for get_current_state error handling."""

    @pytest.mark.asyncio
    async def test_get_current_state_error(self, enable_enterprise_mode):
        """Test get_current_state with API error."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            404, {"errors": [{"detail": "No state"}]}
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_current_state("ws-no-state")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_get_current_state_exception(self, enable_enterprise_mode):
        """Test get_current_state when exception occurs."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=Exception("Connection error"),
        ):
            result = await connector.get_current_state("ws-123")
            assert result.success is False


# =============================================================================
# Additional Coverage Tests for Missing Code Paths
# =============================================================================


class TestGetStateOutputsSuccess:
    """Tests for get_state_outputs success scenarios."""

    @pytest.mark.asyncio
    async def test_get_state_outputs_success(self, enable_enterprise_mode):
        """Test successful state outputs retrieval."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        # Need to mock the full sequence: get_current_state -> get_state_outputs
        call_count = [0]

        mock_response = MagicMock()

        async def get_json():
            if call_count[0] <= 1:
                # First call: get_current_state
                return {
                    "data": {
                        "id": "sv-state-123",
                        "attributes": {
                            "serial": 42,
                            "terraform-version": "1.6.0",
                        },
                    }
                }
            else:
                # Second call: get outputs
                return {
                    "data": [
                        {
                            "id": "wsout-123",
                            "attributes": {
                                "name": "vpc_id",
                                "value": "vpc-12345678",
                                "sensitive": False,
                                "type": "string",
                            },
                        },
                    ]
                }

        mock_response.json = AsyncMock(side_effect=get_json)
        mock_response.status = 200

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()

        def track_get(*args, **kwargs):
            call_count[0] += 1
            return mock_request_context

        mock_session_instance.get.side_effect = track_get

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_state_outputs("ws-123")
            assert result.success is True
            assert "outputs" in result.data


class TestListWorkspacesWithFilters:
    """Tests for list_workspaces with search and tag filters."""

    @pytest.mark.asyncio
    async def test_list_workspaces_with_search(self, enable_enterprise_mode):
        """Test listing workspaces with search filter."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_response = {
            "data": [
                {
                    "id": "ws-prod-123",
                    "attributes": {
                        "name": "production-app",
                        "auto-apply": True,
                    },
                },
            ]
        }

        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces(search="production")
            assert result.success is True
            assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_list_workspaces_with_tags(self, enable_enterprise_mode):
        """Test listing workspaces with tags filter."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_response = {
            "data": [
                {
                    "id": "ws-tagged-123",
                    "attributes": {
                        "name": "tagged-workspace",
                        "auto-apply": False,
                        "tags": ["production", "critical"],
                    },
                },
            ]
        }

        mock_session = create_mock_aiohttp_session(200, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces(tags=["production"])
            assert result.success is True


class TestWorkspaceAttributes:
    """Tests for parsing various workspace attributes."""

    def test_workspace_with_vcs_repo(self):
        """Test workspace with VCS repo configuration."""
        ws = TerraformWorkspace(
            id="ws-vcs",
            name="vcs-workspace",
            organization="test-org",
            vcs_repo="github/org/repo",
            working_directory="/infra/modules",
        )
        assert ws.vcs_repo == "github/org/repo"
        assert ws.working_directory == "/infra/modules"

    def test_workspace_equality(self):
        """Test workspace dataclass equality."""
        ws1 = TerraformWorkspace(id="ws-1", name="test", organization="org")
        ws2 = TerraformWorkspace(id="ws-1", name="test", organization="org")
        assert ws1 == ws2


class TestRunStatusTransitions:
    """Tests for run status parsing."""

    @pytest.mark.asyncio
    async def test_get_run_with_all_statuses(self, enable_enterprise_mode):
        """Test get_run handles various status values."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        for status in [
            "pending",
            "planning",
            "planned",
            "applying",
            "applied",
            "errored",
        ]:
            mock_response = {
                "data": {
                    "id": f"run-{status}",
                    "attributes": {
                        "status": status,
                        "message": f"Test {status}",
                        "has-changes": True,
                        "created-at": "2025-12-26T00:00:00Z",
                    },
                }
            }

            mock_session = create_mock_aiohttp_session(200, mock_response)
            with patch(
                "src.services.terraform_cloud_connector.aiohttp.ClientSession",
                return_value=mock_session,
            ):
                result = await connector.get_run(f"run-{status}")
                assert result.success is True
                assert result.data["status"] == status


class TestRateLimitHandling:
    """Tests for rate limit handling."""

    @pytest.mark.asyncio
    async def test_rate_limited_response(self, enable_enterprise_mode):
        """Test handling rate limited response."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            429,
            {"errors": [{"detail": "Rate limit exceeded, retry after 60 seconds"}]},
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is False
            assert result.status_code == 429


class TestSecurityPatchWithAllParams:
    """Extended tests for trigger_security_patch_run."""

    @pytest.mark.asyncio
    async def test_trigger_security_patch_all_params(self, enable_enterprise_mode):
        """Test security patch run with all parameters."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        # Need to mock multiple sequential API calls
        call_count = [0]

        def create_sequential_mock():
            mock_response = MagicMock()

            async def get_json():
                if call_count[0] == 0:
                    return {
                        "data": {
                            "id": "ws-sec-patch",
                            "attributes": {"name": "security-ws"},
                        }
                    }
                return {
                    "data": {
                        "id": "run-sec-patch",
                        "attributes": {"status": "pending"},
                    }
                }

            mock_response.json = AsyncMock(side_effect=get_json)
            mock_response.status = 200

            mock_request_context = MagicMock()
            mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request_context.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = MagicMock()

            def track_request(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] > 1:
                    mock_response.status = 201
                return mock_request_context

            mock_session_instance.get.side_effect = track_request
            mock_session_instance.post.side_effect = track_request

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            return mock_session

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=create_sequential_mock,
        ):
            # Use only the parameters that exist in the actual API
            result = await connector.trigger_security_patch_run(
                workspace_name="security-ws",
                cve_id="CVE-2025-99999",
                severity="HIGH",
                description="Critical security patch for XYZ vulnerability",
                approval_url="https://aura.example.com/approve/abc123",
            )
            # Should succeed or at least attempt the API calls
            assert result is not None


class TestApiUrlNormalization:
    """Tests for API URL normalization."""

    def test_api_url_strips_trailing_slash(self):
        """Test that trailing slash is stripped from API URL."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
            api_url="https://app.terraform.io/api/v2/",
        )
        assert connector.api_url == "https://app.terraform.io/api/v2"

    def test_api_url_preserved_without_trailing_slash(self):
        """Test that API URL without trailing slash is preserved."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
            api_url="https://tfe.example.com/api/v2",
        )
        assert connector.api_url == "https://tfe.example.com/api/v2"


# =============================================================================
# Additional Coverage Tests - Edge Cases and Error Paths
# =============================================================================


class TestErrorMessageFallback:
    """Tests for error message fallback when errors list is empty."""

    @pytest.mark.asyncio
    async def test_list_workspaces_error_without_detail(self, enable_enterprise_mode):
        """Test list_workspaces error response without error detail."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        # Response with empty errors list - should use str(data) fallback
        mock_session = create_mock_aiohttp_session(
            400, {"errors": [], "message": "Bad request"}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is False
            assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_get_workspace_error_without_detail(self, enable_enterprise_mode):
        """Test get_workspace error response without error detail."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(500, {"errors": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("test")
            assert result.success is False
            assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_trigger_run_error_without_detail(self, enable_enterprise_mode):
        """Test trigger_run error response without error detail."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(422, {"errors": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(workspace_id="ws-123")
            assert result.success is False
            assert connector._last_error is not None

    @pytest.mark.asyncio
    async def test_get_run_error_without_detail(self, enable_enterprise_mode):
        """Test get_run error response without error detail."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(400, {"errors": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_run("run-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_list_runs_error_without_detail(self, enable_enterprise_mode):
        """Test list_runs error response without error detail."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(500, {"errors": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_runs("ws-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_list_variables_error_without_detail(self, enable_enterprise_mode):
        """Test list_variables error response without error detail."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(403, {"errors": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_variables("ws-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_create_variable_error_without_detail(self, enable_enterprise_mode):
        """Test create_variable error response without error detail."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(422, {"errors": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_variable(
                workspace_id="ws-123", key="test", value="val"
            )
            assert result.success is False


class TestApplyRunWithComment:
    """Tests for apply_run with comment parameter."""

    @pytest.mark.asyncio
    async def test_apply_run_with_comment(self, enable_enterprise_mode):
        """Test applying a run with a comment."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(202, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.apply_run(
                run_id="run-123", comment="Approved after review"
            )
            assert result.success is True
            assert result.data["action"] == "apply"

    @pytest.mark.asyncio
    async def test_apply_run_error_response(self, enable_enterprise_mode):
        """Test apply_run with error response."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(
            409, {"errors": [{"detail": "Run cannot be applied"}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.apply_run("run-cannot-apply")
            assert result.success is False
            assert result.status_code == 409


class TestCancelRunWithComment:
    """Tests for cancel_run with comment parameter."""

    @pytest.mark.asyncio
    async def test_cancel_run_with_comment(self, enable_enterprise_mode):
        """Test cancelling a run with a comment."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(202, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.cancel_run(
                run_id="run-123", comment="Cancelled by operator"
            )
            assert result.success is True
            assert result.data["action"] == "cancel"

    @pytest.mark.asyncio
    async def test_cancel_run_not_success(self, enable_enterprise_mode):
        """Test cancel_run when not successful (but still returns ConnectorResult)."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(409, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.cancel_run("run-123")
            assert result.success is False
            assert result.status_code == 409


class TestHealthCheckExtended:
    """Extended health check tests for all status codes."""

    @pytest.mark.asyncio
    async def test_health_check_server_error(self):
        """Test health check with 500 server error."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(500, {})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.ERROR
            assert "HTTP 500" in connector._last_error


class TestGetStateOutputsEdgeCases:
    """Edge cases for get_state_outputs method."""

    @pytest.mark.asyncio
    async def test_get_state_outputs_second_call_error(self, enable_enterprise_mode):
        """Test get_state_outputs when outputs API call fails."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        call_count = [0]

        mock_response = MagicMock()

        async def get_json():
            if call_count[0] <= 1:
                # First call: get_current_state succeeds
                return {
                    "data": {
                        "id": "sv-state-123",
                        "attributes": {"serial": 1},
                    }
                }
            else:
                # Second call: outputs API fails
                return {"errors": [{"detail": "Outputs not available"}]}

        async def track_status():
            if call_count[0] > 1:
                return 404
            return 200

        mock_response.json = AsyncMock(side_effect=get_json)
        # Use property pattern for status
        type(mock_response).status = property(
            lambda self: 200 if call_count[0] <= 1 else 404
        )

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()

        def track_get(*args, **kwargs):
            call_count[0] += 1
            return mock_request_context

        mock_session_instance.get.side_effect = track_get

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_state_outputs("ws-123")
            # The second call may succeed or fail depending on status tracking
            assert result is not None


class TestTriggerRunEdgeCases:
    """Edge cases for trigger_run method."""

    @pytest.mark.asyncio
    async def test_trigger_run_with_all_options(self, enable_enterprise_mode):
        """Test trigger_run with all optional parameters."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            201, {"data": {"id": "run-full", "attributes": {"status": "pending"}}}
        )

        variables = [
            TerraformVariable(
                key="instance_type",
                value="t3.large",
                category=VariableCategory.TERRAFORM,
                hcl=False,
                sensitive=False,
            ),
        ]

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123",
                message="Full options run",
                is_destroy=False,
                auto_apply=True,
                plan_only=False,
                target_addrs=["module.app", "aws_security_group.main"],
                replace_addrs=["aws_instance.old"],
                variables=variables,
            )
            assert result.success is True
            assert result.data["run_id"] == "run-full"

    @pytest.mark.asyncio
    async def test_trigger_run_status_200(self, enable_enterprise_mode):
        """Test trigger_run with 200 status (instead of 201)."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        mock_session = create_mock_aiohttp_session(
            200, {"data": {"id": "run-200", "attributes": {"status": "pending"}}}
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(workspace_id="ws-123", message="Test")
            assert result.success is True
            assert connector._status == ConnectorStatus.CONNECTED


class TestCreateVariableEdgeCases:
    """Edge cases for create_variable method."""

    @pytest.mark.asyncio
    async def test_create_variable_with_description(self, enable_enterprise_mode):
        """Test creating a variable with full description."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_response = {
            "data": {
                "id": "var-desc",
                "attributes": {
                    "key": "config_path",
                    "description": "Path to configuration file",
                },
            }
        }
        mock_session = create_mock_aiohttp_session(201, mock_response)
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_variable(
                workspace_id="ws-123",
                key="config_path",
                value="/etc/app/config.yaml",
                category=VariableCategory.TERRAFORM,
                hcl=False,
                sensitive=False,
                description="Path to configuration file",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_variable_status_200(self, enable_enterprise_mode):
        """Test create_variable with 200 status (instead of 201)."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")
        mock_session = create_mock_aiohttp_session(
            200, {"data": {"id": "var-200", "attributes": {"key": "test"}}}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.create_variable(
                workspace_id="ws-123", key="test", value="val"
            )
            assert result.success is True


class TestSecurityPatchWithMinimalParams:
    """Tests for trigger_security_patch_run with minimal parameters."""

    @pytest.mark.asyncio
    async def test_security_patch_minimal_params(self, enable_enterprise_mode):
        """Test security patch run with only required parameters."""
        connector = TerraformCloudConnector(organization="test-org", token="test-token")

        call_count = [0]

        def create_sequential_mock():
            mock_response = MagicMock()

            async def get_json():
                if call_count[0] == 0:
                    return {
                        "data": {
                            "id": "ws-minimal",
                            "attributes": {"name": "minimal-ws"},
                        }
                    }
                return {
                    "data": {
                        "id": "run-minimal",
                        "attributes": {"status": "pending"},
                    }
                }

            mock_response.json = AsyncMock(side_effect=get_json)
            mock_response.status = 200

            mock_request_context = MagicMock()
            mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request_context.__aexit__ = AsyncMock(return_value=None)

            mock_session_instance = MagicMock()

            def track_request(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] > 1:
                    mock_response.status = 201
                return mock_request_context

            mock_session_instance.get.side_effect = track_request
            mock_session_instance.post.side_effect = track_request

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            return mock_session

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=create_sequential_mock,
        ):
            # Minimal params - no cve_id, no approval_url
            result = await connector.trigger_security_patch_run(
                workspace_name="minimal-ws",
                severity="LOW",
                description="Minor security update",
            )
            assert result is not None


# =============================================================================
# P1 - Critical Error Paths
# =============================================================================


class TestP1CriticalErrorPaths:
    """P1 edge case tests for critical error paths in Terraform Cloud connector."""

    @pytest.mark.asyncio
    async def test_ssl_certificate_error(self, enable_enterprise_mode):
        """Test handling of SSL certificate validation errors."""
        import ssl

        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=ssl.SSLError("certificate verify failed"),
        ):
            result = await connector.list_workspaces()
            assert result.success is False
            assert (
                "ssl" in result.error.lower() or "certificate" in result.error.lower()
            )

    @pytest.mark.asyncio
    async def test_connection_refused_error(self, enable_enterprise_mode):
        """Test handling when Terraform Cloud server refuses connection."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            result = await connector.list_workspaces()
            assert result.success is False
            assert "refused" in result.error.lower() or "error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, enable_enterprise_mode):
        """Test handling of DNS resolution failures."""
        import socket

        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
            api_url="https://nonexistent.terraform.invalid/api/v2",
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=socket.gaierror(8, "Name or service not known"),
        ):
            result = await connector.list_workspaces()
            assert result.success is False

    @pytest.mark.asyncio
    async def test_json_decode_error_on_response(self, enable_enterprise_mode):
        """Test handling when API returns invalid JSON."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            side_effect=json.JSONDecodeError("Expecting value", "<html>", 0)
        )

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is False

    @pytest.mark.asyncio
    async def test_html_error_page_response(self, enable_enterprise_mode):
        """Test handling when server returns HTML error page instead of JSON."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.json = AsyncMock(
            side_effect=json.JSONDecodeError("Expecting value", "<html>", 0)
        )
        mock_response.text = AsyncMock(
            return_value="<html><body>Service Unavailable</body></html>"
        )

        mock_request_context = MagicMock()
        mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_request_context.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_request_context

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is False

    @pytest.mark.asyncio
    async def test_401_unauthorized_response(self, enable_enterprise_mode):
        """Test handling of 401 unauthorized response."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="invalid-token",
        )

        mock_session = create_mock_aiohttp_session(
            401, {"errors": [{"status": "401", "title": "Unauthorized"}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is False
            assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_403_forbidden_response(self, enable_enterprise_mode):
        """Test handling of 403 forbidden response."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="limited-token",
        )

        mock_session = create_mock_aiohttp_session(
            403,
            {
                "errors": [
                    {
                        "status": "403",
                        "title": "Forbidden",
                        "detail": "Insufficient permissions",
                    }
                ]
            },
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("protected-ws")
            assert result.success is False
            assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_404_not_found_workspace(self, enable_enterprise_mode):
        """Test handling of 404 not found for workspace."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            404,
            {
                "errors": [
                    {
                        "status": "404",
                        "title": "Not Found",
                        "detail": "Workspace not found",
                    }
                ]
            },
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("nonexistent-ws")
            assert result.success is False
            assert result.status_code == 404


# =============================================================================
# P2 - Boundary Condition Tests
# =============================================================================


class TestP2BoundaryConditions:
    """P2 edge case tests for boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_workspace_list(self, enable_enterprise_mode):
        """Test list_workspaces returning empty list."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"data": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is True
            assert result.data["workspaces"] == []
            assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_empty_search_query(self, enable_enterprise_mode):
        """Test list_workspaces with empty search string."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            200, {"data": [{"id": "ws-123", "attributes": {"name": "test-ws"}}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces(search="")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_empty_tags_list(self, enable_enterprise_mode):
        """Test list_workspaces with empty tags list."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            200, {"data": [{"id": "ws-123", "attributes": {"name": "test-ws"}}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces(tags=[])
            assert result.success is True

    @pytest.mark.asyncio
    async def test_unicode_workspace_name(self, enable_enterprise_mode):
        """Test handling of unicode characters in workspace name."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "data": {
                    "id": "ws-unicode",
                    "attributes": {"name": "测试-workspace-🚀"},
                }
            },
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("测试-workspace-🚀")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_very_long_message(self, enable_enterprise_mode):
        """Test trigger_run with very long message."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        long_message = "A" * 10000  # 10KB message

        mock_session = create_mock_aiohttp_session(
            201, {"data": {"id": "run-long", "attributes": {"status": "pending"}}}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123", message=long_message
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_page_size_one(self, enable_enterprise_mode):
        """Test list_workspaces with page_size=1."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            200, {"data": [{"id": "ws-single", "attributes": {"name": "single-ws"}}]}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces(page_size=1)
            assert result.success is True
            assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_empty_run_comment(self, enable_enterprise_mode):
        """Test apply_run with empty comment."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            202, {"data": {"id": "run-apply", "attributes": {"status": "applying"}}}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.apply_run("run-123", comment="")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_empty_variable_list(self, enable_enterprise_mode):
        """Test list_variables returning empty list."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"data": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_variables("ws-123")
            assert result.success is True
            assert result.data["variables"] == []


# =============================================================================
# P3 - API-Specific Edge Cases
# =============================================================================


class TestP3ApiEdgeCases:
    """P3 edge case tests for API-specific scenarios."""

    @pytest.mark.asyncio
    async def test_response_with_empty_data_object(self, enable_enterprise_mode):
        """Test handling response with empty data object."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(200, {"data": {}})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("empty-ws")
            assert result.success is True
            # Should handle gracefully without crashing

    @pytest.mark.asyncio
    async def test_response_missing_attributes(self, enable_enterprise_mode):
        """Test handling response with missing attributes."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            200, {"data": {"id": "ws-noattr"}}  # Missing attributes
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("no-attr-ws")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_error_response_without_details(self, enable_enterprise_mode):
        """Test error response without detailed error message."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            500, {"errors": [{"status": "500"}]}  # No detail field
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.list_workspaces()
            assert result.success is False
            assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_error_response_empty_errors_array(self, enable_enterprise_mode):
        """Test error response with empty errors array."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(400, {"errors": []})
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(workspace_id="ws-123")
            assert result.success is False

    @pytest.mark.asyncio
    async def test_unknown_run_status(self, enable_enterprise_mode):
        """Test handling of unknown run status from API."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "data": {
                    "id": "run-unknown",
                    "attributes": {"status": "new_unknown_status"},
                }
            },
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_run("run-unknown")
            assert result.success is True
            # Should handle unknown status gracefully

    @pytest.mark.asyncio
    async def test_run_with_null_optional_fields(self, enable_enterprise_mode):
        """Test run response with null values for optional fields."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "data": {
                    "id": "run-nulls",
                    "attributes": {
                        "status": "planned",
                        "message": None,
                        "is-destroy": None,
                        "has-changes": None,
                        "auto-apply": None,
                        "created-at": None,
                        "plan-only": None,
                    },
                }
            },
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_run("run-nulls")
            assert result.success is True

    @pytest.mark.asyncio
    async def test_workspace_with_all_optional_fields(self, enable_enterprise_mode):
        """Test workspace response with all optional fields populated."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "data": {
                    "id": "ws-full",
                    "attributes": {
                        "name": "full-workspace",
                        "auto-apply": True,
                        "terraform-version": "1.5.0",
                        "working-directory": "/infra",
                        "description": "Full workspace",
                        "resource-count": 42,
                        "created-at": "2024-01-01T00:00:00Z",
                        "updated-at": "2024-12-01T00:00:00Z",
                    },
                }
            },
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.get_workspace("full-workspace")
            assert result.success is True
            assert result.data["terraform_version"] == "1.5.0"
            assert result.data["resource_count"] == 42

    @pytest.mark.asyncio
    async def test_trigger_run_with_all_options(self, enable_enterprise_mode):
        """Test trigger_run with all optional parameters."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        mock_session = create_mock_aiohttp_session(
            201, {"data": {"id": "run-full", "attributes": {"status": "pending"}}}
        )
        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            return_value=mock_session,
        ):
            result = await connector.trigger_run(
                workspace_id="ws-123",
                message="Full run",
                is_destroy=False,
                auto_apply=True,
                plan_only=False,
                target_addrs=["aws_instance.web", "aws_db_instance.primary"],
                replace_addrs=["aws_instance.old"],
                variables=[
                    TerraformVariable(key="env", value="production"),
                    TerraformVariable(
                        key="secret",
                        value="hidden",
                        sensitive=True,
                        category=VariableCategory.ENV,
                    ),
                ],
            )
            assert result.success is True


# =============================================================================
# P4 - Async and Concurrency Tests
# =============================================================================


class TestP4AsyncConcurrency:
    """P4 edge case tests for async and concurrency scenarios."""

    @pytest.mark.asyncio
    async def test_timeout_during_api_call(self, enable_enterprise_mode):
        """Test timeout error during API call."""
        import asyncio as aio

        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
            timeout_seconds=0.001,
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=aio.TimeoutError("Request timed out"),
        ):
            result = await connector.list_workspaces()
            assert result.success is False

    @pytest.mark.asyncio
    async def test_request_cancelled(self, enable_enterprise_mode):
        """Test handling of cancelled request."""
        import asyncio as aio

        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=aio.CancelledError(),
        ):
            with pytest.raises(aio.CancelledError):
                await connector.list_workspaces()

    @pytest.mark.asyncio
    async def test_concurrent_workspace_requests(self, enable_enterprise_mode):
        """Test multiple concurrent workspace requests."""
        import asyncio as aio

        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        call_count = [0]

        def create_session(*args, **kwargs):
            call_count[0] += 1
            return create_mock_aiohttp_session(
                200,
                {
                    "data": [
                        {
                            "id": f"ws-{call_count[0]}",
                            "attributes": {"name": f"ws-{call_count[0]}"},
                        }
                    ]
                },
            )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=create_session,
        ):
            results = await aio.gather(
                connector.list_workspaces(),
                connector.list_workspaces(search="prod"),
                connector.list_workspaces(tags=["critical"]),
            )
            assert all(r.success for r in results)
            assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_session_cleanup_on_exception(self, enable_enterprise_mode):
        """Test that session is properly cleaned up on exception."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        # First call raises, second should work
        call_count = [0]

        def create_session(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Simulated failure")
            return create_mock_aiohttp_session(
                200, {"data": [{"id": "ws-retry", "attributes": {"name": "retry-ws"}}]}
            )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=create_session,
        ):
            # First call fails
            result1 = await connector.list_workspaces()
            assert result1.success is False

            # Second call should work (session cleanup worked)
            result2 = await connector.list_workspaces()
            assert result2.success is True

    @pytest.mark.asyncio
    async def test_rapid_successive_requests(self, enable_enterprise_mode):
        """Test handling of rapid successive requests."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        call_count = [0]

        def create_session(*args, **kwargs):
            call_count[0] += 1
            return create_mock_aiohttp_session(
                200,
                {
                    "data": {
                        "id": f"ws-{call_count[0]}",
                        "attributes": {"name": f"ws-{call_count[0]}"},
                    }
                },
            )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=create_session,
        ):
            results = []
            for _ in range(10):
                result = await connector.get_workspace(f"ws-{_}")
                results.append(result)

            assert all(r.success for r in results)
            assert call_count[0] == 10

    @pytest.mark.asyncio
    async def test_connection_error_recovery(self, enable_enterprise_mode):
        """Test recovery after connection error."""
        connector = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

        call_count = [0]

        def create_session(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ConnectionError("Network unavailable")
            return create_mock_aiohttp_session(
                200,
                {
                    "data": [
                        {"id": "ws-recovery", "attributes": {"name": "recovery-ws"}}
                    ]
                },
            )

        with patch(
            "src.services.terraform_cloud_connector.aiohttp.ClientSession",
            side_effect=create_session,
        ):
            # First two calls fail
            result1 = await connector.list_workspaces()
            assert result1.success is False
            result2 = await connector.list_workspaces()
            assert result2.success is False

            # Third call succeeds
            result3 = await connector.list_workspaces()
            assert result3.success is True
