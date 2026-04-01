"""
Tests for ServiceNow Connector HTTP methods.

These tests use proper async mocking without module-level mock pollution.
Target: 60%+ coverage for HTTP methods.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# Set enterprise mode before importing connector
os.environ["AURA_INTEGRATION_MODE"] = "enterprise"

# Clear cached config to pick up the new mode
import sys

if "src.config" in sys.modules:
    try:
        from src.config.integration_config import clear_integration_config_cache

        clear_integration_config_cache()
    except ImportError:
        pass
if "src.services.servicenow_connector" in sys.modules:
    del sys.modules["src.services.servicenow_connector"]

from src.services.external_tool_connectors import ConnectorStatus
from src.services.servicenow_connector import (
    ServiceNowConnector,
    ServiceNowImpact,
    ServiceNowUrgency,
)

# =============================================================================
# Mock Helpers
# =============================================================================


def create_mock_response(status_code: int, json_data):
    """Create a mock aiohttp response."""
    mock_response = MagicMock()
    mock_response.status = status_code
    mock_response.json = AsyncMock(return_value=json_data)
    return mock_response


def create_mock_session(mock_response):
    """Create a mock aiohttp ClientSession with proper async context manager support."""
    inner_cm = MagicMock()
    inner_cm.__aenter__ = AsyncMock(return_value=mock_response)
    inner_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=inner_cm)
    mock_session.post = MagicMock(return_value=inner_cm)
    mock_session.patch = MagicMock(return_value=inner_cm)
    mock_session.put = MagicMock(return_value=inner_cm)
    mock_session.delete = MagicMock(return_value=inner_cm)

    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


def create_exception_session(exception: Exception):
    """Create a mock session that raises an exception."""
    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=exception)
    mock_session.post = MagicMock(side_effect=exception)
    mock_session.patch = MagicMock(side_effect=exception)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


# =============================================================================
# Tests for create_incident
# =============================================================================


class TestServiceNowConnectorCreateIncident:
    """Tests for create_incident HTTP method."""

    @pytest.mark.asyncio
    async def test_create_incident_success(self):
        """Test successful incident creation."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            201,
            {
                "result": {
                    "sys_id": "abc123",
                    "number": "INC0001234",
                    "short_description": "Test incident",
                    "state": "1",
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.create_incident(
                short_description="Test incident",
                description="This is a test",
            )

        assert result.success is True
        assert result.data["number"] == "INC0001234"
        assert result.data["sys_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_create_incident_api_error(self):
        """Test incident creation with API error."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            403, {"error": {"message": "Access denied"}}
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.create_incident(
                short_description="Test incident",
            )

        assert result.success is False
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_create_incident_network_error(self):
        """Test incident creation with network error."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_session = create_exception_session(Exception("Connection failed"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.create_incident(
                short_description="Test incident",
            )

        assert result.success is False
        assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_create_incident_with_all_fields(self):
        """Test incident creation with all optional fields."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
            default_assignment_group="IT Support",
        )

        mock_response = create_mock_response(
            201,
            {
                "result": {
                    "sys_id": "abc123",
                    "number": "INC0001234",
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.create_incident(
                short_description="Test incident",
                description="Full description",
                category="hardware",
                subcategory="printer",
                urgency=ServiceNowUrgency.HIGH,
                impact=ServiceNowImpact.HIGH,
                assignment_group="Security Team",
                assigned_to="admin",
                caller_id="user123",
                cmdb_ci="ci-abc",
                additional_fields={"custom_field": "value"},
            )

        assert result.success is True


# =============================================================================
# Tests for get_incident
# =============================================================================


class TestServiceNowConnectorGetIncident:
    """Tests for get_incident HTTP method."""

    @pytest.mark.asyncio
    async def test_get_incident_success(self):
        """Test successful incident retrieval."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        # get_incident expects result to be a list (it takes first item)
        mock_response = create_mock_response(
            200,
            {
                "result": [
                    {
                        "sys_id": "abc123",
                        "number": "INC0001234",
                        "short_description": "Test incident",
                        "state": "1",
                    }
                ]
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_incident("abc123")

        assert result.success is True
        assert result.data["number"] == "INC0001234"

    @pytest.mark.asyncio
    async def test_get_incident_not_found(self):
        """Test incident not found."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            404, {"error": {"message": "Record not found"}}
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_incident("nonexistent")

        assert result.success is False
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_get_incident_network_error(self):
        """Test get_incident with network error."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_session = create_exception_session(Exception("Timeout"))

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_incident("abc123")

        assert result.success is False
        assert "Timeout" in result.error


# =============================================================================
# Tests for update_incident
# =============================================================================


class TestServiceNowConnectorUpdateIncident:
    """Tests for update_incident HTTP method."""

    @pytest.mark.asyncio
    async def test_update_incident_success(self):
        """Test successful incident update."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            200,
            {
                "result": {
                    "sys_id": "abc123",
                    "number": "INC0001234",
                    "state": "2",
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.update_incident(
                incident_id="abc123",
                updates={"state": "2", "work_notes": "Updated status"},
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_incident_error(self):
        """Test update_incident with API error."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            400, {"error": {"message": "Invalid field"}}
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.update_incident(
                incident_id="abc123",
                updates={"invalid_field": "value"},
            )

        assert result.success is False


# =============================================================================
# Tests for resolve_incident
# =============================================================================


class TestServiceNowConnectorResolveIncident:
    """Tests for resolve_incident HTTP method."""

    @pytest.mark.asyncio
    async def test_resolve_incident_success(self):
        """Test successful incident resolution."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            200,
            {
                "result": {
                    "sys_id": "abc123",
                    "number": "INC0001234",
                    "state": "6",
                    "close_code": "Solved",
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.resolve_incident(
                incident_id="abc123",
                resolution_code="Solved",
                resolution_notes="Issue was resolved by applying patch",
            )

        assert result.success is True


# =============================================================================
# Tests for list_incidents
# =============================================================================


class TestServiceNowConnectorListIncidents:
    """Tests for list_incidents HTTP method."""

    @pytest.mark.asyncio
    async def test_list_incidents_success(self):
        """Test successful incident listing."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            200,
            {
                "result": [
                    {"sys_id": "abc123", "number": "INC0001234"},
                    {"sys_id": "def456", "number": "INC0001235"},
                ]
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.list_incidents()

        assert result.success is True
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_list_incidents_with_filters(self):
        """Test list incidents with filters."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(200, {"result": []})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.list_incidents(
                query="state=1",
                limit=10,
                offset=0,
                order_by="-sys_created_on",
            )

        assert result.success is True


# =============================================================================
# Tests for CMDB operations
# =============================================================================


class TestServiceNowConnectorCMDB:
    """Tests for CMDB operations."""

    @pytest.mark.asyncio
    async def test_get_ci_success(self):
        """Test successful CI retrieval."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            200,
            {
                "result": {
                    "sys_id": "ci-123",
                    "name": "App Server 1",
                    "sys_class_name": "cmdb_ci_server",
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_ci("ci-123")

        assert result.success is True
        assert result.data["name"] == "App Server 1"

    @pytest.mark.asyncio
    async def test_search_cmdb_success(self):
        """Test successful CMDB search."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            200,
            {
                "result": [
                    {"sys_id": "ci-1", "name": "Server 1"},
                    {"sys_id": "ci-2", "name": "Server 2"},
                ]
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.search_cmdb(
                ci_class="cmdb_ci_server",
                query="name=Server*",
            )

        assert result.success is True
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_get_ci_relationships_success(self):
        """Test successful CI relationships retrieval."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            200,
            {
                "result": [
                    {"parent": {"value": "ci-1"}, "child": {"value": "ci-2"}},
                ]
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.get_ci_relationships("ci-1")

        assert result.success is True


# =============================================================================
# Tests for change requests
# =============================================================================


class TestServiceNowConnectorChangeRequests:
    """Tests for change request operations."""

    @pytest.mark.asyncio
    async def test_create_change_request_success(self):
        """Test successful change request creation."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            201,
            {
                "result": {
                    "sys_id": "change-123",
                    "number": "CHG0001234",
                    "short_description": "Security patch deployment",
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.create_change_request(
                short_description="Security patch deployment",
                description="Deploy critical security patches",
                change_type="normal",
            )

        assert result.success is True
        assert result.data["number"] == "CHG0001234"


# =============================================================================
# Tests for health_check
# =============================================================================


class TestServiceNowConnectorHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(200, {"result": [{"name": "admin"}]})
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.health_check()

        assert result is True
        assert connector._status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_auth_failed(self):
        """Test health check with auth failure."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="wrong",
        )

        mock_response = create_mock_response(
            401, {"error": {"message": "Unauthorized"}}
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.health_check()

        assert result is False
        assert connector._status == ConnectorStatus.AUTH_FAILED


# =============================================================================
# Tests for security operations
# =============================================================================


class TestServiceNowConnectorSecurityOps:
    """Tests for security incident and change request methods."""

    @pytest.mark.asyncio
    async def test_create_security_incident_success(self):
        """Test successful security incident creation."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            201,
            {
                "result": {
                    "sys_id": "sec-123",
                    "number": "SECINC0001234",
                    "priority": "1",
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.create_security_incident(
                title="Critical vulnerability detected",
                cve_id="CVE-2021-44228",
                severity="CRITICAL",
                affected_asset="production-app-server",
                description="Log4j vulnerability detected",
            )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_create_security_change_request_success(self):
        """Test successful security change request creation."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )

        mock_response = create_mock_response(
            201,
            {
                "result": {
                    "sys_id": "chg-123",
                    "number": "CHG0001234",
                    "type": "security",
                }
            },
        )
        mock_session = create_mock_session(mock_response)

        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            result = await connector.create_security_change_request(
                title="Security patch deployment",
                cve_id="CVE-2021-44228",
                severity="HIGH",
                patch_description="Deploy patches for CVE-2021-44228",
            )

        assert result.success is True
