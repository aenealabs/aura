"""
Project Aura - ServiceNow Connector Tests

Tests for the ServiceNow connector for ITSM integration.
"""

import sys
from unittest.mock import MagicMock

# =============================================================================
# Save original modules before mocking to prevent test pollution
# =============================================================================
_original_src_config = sys.modules.get("src.config")
_original_aiohttp = sys.modules.get("aiohttp")
_original_connectors = sys.modules.get("src.services.external_tool_connectors")
_original_servicenow = sys.modules.get("src.services.servicenow_connector")

# Mock aiohttp
mock_aiohttp = MagicMock()
mock_aiohttp.ClientSession = MagicMock()
sys.modules["aiohttp"] = mock_aiohttp

# Mock config
mock_config = MagicMock()
mock_config.require_enterprise_mode = lambda f: f  # Pass through decorator
sys.modules["src.config"] = mock_config

# Mock external tool connectors
mock_connectors = MagicMock()
mock_connectors.ConnectorResult = MagicMock
mock_connectors.ConnectorStatus = MagicMock()
mock_connectors.ExternalToolConnector = MagicMock
sys.modules["src.services.external_tool_connectors"] = mock_connectors

from src.services.servicenow_connector import (
    CMDBConfigurationItem,
    ServiceNowChangeRequest,
    ServiceNowImpact,
    ServiceNowIncident,
    ServiceNowIncidentState,
    ServiceNowPriority,
    ServiceNowUrgency,
)

# Restore original modules to prevent pollution of other tests
if _original_src_config is not None:
    sys.modules["src.config"] = _original_src_config
else:
    sys.modules.pop("src.config", None)

if _original_aiohttp is not None:
    sys.modules["aiohttp"] = _original_aiohttp

if _original_connectors is not None:
    sys.modules["src.services.external_tool_connectors"] = _original_connectors

if _original_servicenow is not None:
    sys.modules["src.services.servicenow_connector"] = _original_servicenow


class TestServiceNowUrgency:
    """Tests for ServiceNowUrgency enum."""

    def test_high_urgency(self):
        """Test high urgency value."""
        assert ServiceNowUrgency.HIGH.value == 1

    def test_medium_urgency(self):
        """Test medium urgency value."""
        assert ServiceNowUrgency.MEDIUM.value == 2

    def test_low_urgency(self):
        """Test low urgency value."""
        assert ServiceNowUrgency.LOW.value == 3

    def test_urgency_ordering(self):
        """Test urgency values are ordered correctly."""
        assert ServiceNowUrgency.HIGH.value < ServiceNowUrgency.MEDIUM.value
        assert ServiceNowUrgency.MEDIUM.value < ServiceNowUrgency.LOW.value


class TestServiceNowImpact:
    """Tests for ServiceNowImpact enum."""

    def test_high_impact(self):
        """Test high impact value."""
        assert ServiceNowImpact.HIGH.value == 1

    def test_medium_impact(self):
        """Test medium impact value."""
        assert ServiceNowImpact.MEDIUM.value == 2

    def test_low_impact(self):
        """Test low impact value."""
        assert ServiceNowImpact.LOW.value == 3


class TestServiceNowIncidentState:
    """Tests for ServiceNowIncidentState enum."""

    def test_new_state(self):
        """Test new state value."""
        assert ServiceNowIncidentState.NEW.value == 1

    def test_in_progress_state(self):
        """Test in progress state value."""
        assert ServiceNowIncidentState.IN_PROGRESS.value == 2

    def test_on_hold_state(self):
        """Test on hold state value."""
        assert ServiceNowIncidentState.ON_HOLD.value == 3

    def test_resolved_state(self):
        """Test resolved state value."""
        assert ServiceNowIncidentState.RESOLVED.value == 6

    def test_closed_state(self):
        """Test closed state value."""
        assert ServiceNowIncidentState.CLOSED.value == 7

    def test_cancelled_state(self):
        """Test cancelled state value."""
        assert ServiceNowIncidentState.CANCELLED.value == 8


class TestServiceNowPriority:
    """Tests for ServiceNowPriority enum."""

    def test_critical_priority(self):
        """Test critical priority value."""
        assert ServiceNowPriority.CRITICAL.value == 1

    def test_high_priority(self):
        """Test high priority value."""
        assert ServiceNowPriority.HIGH.value == 2

    def test_moderate_priority(self):
        """Test moderate priority value."""
        assert ServiceNowPriority.MODERATE.value == 3

    def test_low_priority(self):
        """Test low priority value."""
        assert ServiceNowPriority.LOW.value == 4

    def test_planning_priority(self):
        """Test planning priority value."""
        assert ServiceNowPriority.PLANNING.value == 5


class TestServiceNowIncident:
    """Tests for ServiceNowIncident dataclass."""

    def test_minimal_incident(self):
        """Test minimal incident creation."""
        incident = ServiceNowIncident(
            short_description="Critical vulnerability detected",
        )
        assert incident.short_description == "Critical vulnerability detected"
        assert incident.description == ""
        assert incident.category == "software"
        assert incident.urgency == ServiceNowUrgency.MEDIUM
        assert incident.impact == ServiceNowImpact.MEDIUM

    def test_full_incident(self):
        """Test full incident creation."""
        incident = ServiceNowIncident(
            short_description="Security patch required",
            description="A critical CVE was detected in the API service",
            category="security",
            subcategory="vulnerability",
            urgency=ServiceNowUrgency.HIGH,
            impact=ServiceNowImpact.HIGH,
            assignment_group="security-team",
            assigned_to="john.doe",
            caller_id="jane.smith",
            cmdb_ci="api-server-01",
            business_service="api-platform",
        )
        assert incident.urgency == ServiceNowUrgency.HIGH
        assert incident.impact == ServiceNowImpact.HIGH
        assert incident.assignment_group == "security-team"

    def test_incident_with_additional_fields(self):
        """Test incident with additional fields."""
        incident = ServiceNowIncident(
            short_description="Test incident",
            additional_fields={"custom_field": "custom_value"},
        )
        assert incident.additional_fields["custom_field"] == "custom_value"


class TestServiceNowChangeRequest:
    """Tests for ServiceNowChangeRequest dataclass."""

    def test_minimal_change_request(self):
        """Test minimal change request creation."""
        change = ServiceNowChangeRequest(
            short_description="Deploy security patch",
        )
        assert change.short_description == "Deploy security patch"
        assert change.type == "normal"
        assert change.risk == "moderate"
        assert change.impact == "medium"

    def test_full_change_request(self):
        """Test full change request creation."""
        change = ServiceNowChangeRequest(
            short_description="Emergency patch deployment",
            description="Deploy critical security patch for CVE-2025-1234",
            type="emergency",
            category="security",
            risk="high",
            impact="high",
            assignment_group="change-management",
            requested_by="security-team",
            cmdb_ci="prod-api-cluster",
            start_date="2025-12-21T10:00:00Z",
            end_date="2025-12-21T12:00:00Z",
        )
        assert change.type == "emergency"
        assert change.risk == "high"
        assert change.start_date == "2025-12-21T10:00:00Z"

    def test_change_request_types(self):
        """Test different change request types."""
        for change_type in ["normal", "standard", "emergency"]:
            change = ServiceNowChangeRequest(
                short_description=f"{change_type} change",
                type=change_type,
            )
            assert change.type == change_type


class TestCMDBConfigurationItem:
    """Tests for CMDBConfigurationItem dataclass."""

    def test_minimal_ci(self):
        """Test minimal configuration item creation."""
        ci = CMDBConfigurationItem(
            sys_id="abc123",
            name="api-server-01",
            sys_class_name="cmdb_ci_server",
        )
        assert ci.sys_id == "abc123"
        assert ci.name == "api-server-01"
        assert ci.sys_class_name == "cmdb_ci_server"
        assert ci.operational_status is None

    def test_full_ci(self):
        """Test full configuration item creation."""
        ci = CMDBConfigurationItem(
            sys_id="xyz789",
            name="prod-db-cluster",
            sys_class_name="cmdb_ci_database",
            operational_status="operational",
            environment="production",
            ip_address="10.0.1.100",
            fqdn="prod-db.internal.example.com",
            os="Amazon Linux 2",
            os_version="2.0.2023",
            manufacturer="Amazon",
            model_id="db.r5.2xlarge",
            serial_number="i-0123456789",
            location="us-east-1a",
            department="Engineering",
            owned_by="platform-team",
            managed_by="dba-team",
        )
        assert ci.operational_status == "operational"
        assert ci.environment == "production"
        assert ci.ip_address == "10.0.1.100"
        assert ci.os == "Amazon Linux 2"

    def test_ci_with_attributes(self):
        """Test CI with additional attributes."""
        ci = CMDBConfigurationItem(
            sys_id="attr123",
            name="custom-server",
            sys_class_name="cmdb_ci_app_server",
            attributes={
                "application": "user-service",
                "version": "2.5.0",
                "port": 8080,
            },
        )
        assert ci.attributes["application"] == "user-service"
        assert ci.attributes["port"] == 8080

    def test_ci_class_names(self):
        """Test different CI class names."""
        class_names = [
            "cmdb_ci_server",
            "cmdb_ci_app_server",
            "cmdb_ci_database",
            "cmdb_ci_cloud_service",
            "cmdb_ci_container",
        ]
        for class_name in class_names:
            ci = CMDBConfigurationItem(
                sys_id=f"id-{class_name}",
                name=f"item-{class_name}",
                sys_class_name=class_name,
            )
            assert ci.sys_class_name == class_name


class TestServiceNowUrgencyImpactMatrix:
    """Tests for urgency and impact combinations."""

    def test_high_urgency_high_impact(self):
        """Test high urgency + high impact = critical priority."""
        incident = ServiceNowIncident(
            short_description="Critical outage",
            urgency=ServiceNowUrgency.HIGH,
            impact=ServiceNowImpact.HIGH,
        )
        # P1 = High urgency (1) + High impact (1)
        assert incident.urgency.value == 1
        assert incident.impact.value == 1

    def test_low_urgency_low_impact(self):
        """Test low urgency + low impact = planning priority."""
        incident = ServiceNowIncident(
            short_description="Minor request",
            urgency=ServiceNowUrgency.LOW,
            impact=ServiceNowImpact.LOW,
        )
        # P5 = Low urgency (3) + Low impact (3)
        assert incident.urgency.value == 3
        assert incident.impact.value == 3


class TestServiceNowStateTransitions:
    """Tests for incident state transitions."""

    def test_state_values(self):
        """Test all state values are integers."""
        for state in ServiceNowIncidentState:
            assert isinstance(state.value, int)

    def test_state_progression(self):
        """Test normal state progression values."""
        assert (
            ServiceNowIncidentState.NEW.value
            < ServiceNowIncidentState.IN_PROGRESS.value
        )
        # Note: resolved (6) < closed (7) in ServiceNow
        assert (
            ServiceNowIncidentState.RESOLVED.value
            < ServiceNowIncidentState.CLOSED.value
        )


class TestPriorityCalculation:
    """Tests for priority level understanding."""

    def test_priority_is_numeric(self):
        """Test all priority values are numeric."""
        for priority in ServiceNowPriority:
            assert isinstance(priority.value, int)

    def test_priority_ordering(self):
        """Test priority ordering (1=highest, 5=lowest)."""
        priorities = [p.value for p in ServiceNowPriority]
        assert priorities == sorted(priorities)
        assert ServiceNowPriority.CRITICAL.value == 1
        assert ServiceNowPriority.PLANNING.value == 5


# =============================================================================
# ServiceNow Connector Tests
# =============================================================================

# Import the real connector for testing (after data classes are tested)
import os

# Set enterprise mode for connector tests
os.environ["AURA_INTEGRATION_MODE"] = "enterprise"

# Clear module caches and reimport properly
if "src.services.servicenow_connector" in sys.modules:
    del sys.modules["src.services.servicenow_connector"]
if "src.config" in sys.modules:
    # Keep config but clear its cache
    from src.config.integration_config import clear_integration_config_cache

    clear_integration_config_cache()

from src.services.servicenow_connector import ServiceNowConnector


class TestServiceNowConnectorInit:
    """Tests for ServiceNowConnector initialization."""

    def test_basic_init(self):
        """Test basic connector initialization."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="api_user",
            password="api_password",
        )
        assert connector.instance_url == "https://company.service-now.com"
        assert connector.api_version == "v2"
        assert connector.default_assignment_group is None

    def test_init_trailing_slash_removed(self):
        """Test trailing slash is removed from instance URL."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com/",
            username="user",
            password="pass",
        )
        assert connector.instance_url == "https://company.service-now.com"

    def test_init_custom_api_version(self):
        """Test custom API version."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
            api_version="v1",
        )
        assert connector.api_version == "v1"

    def test_init_with_assignment_group(self):
        """Test initialization with default assignment group."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
            default_assignment_group="Security Team",
        )
        assert connector.default_assignment_group == "Security Team"


class TestServiceNowConnectorHeaders:
    """Tests for ServiceNow header generation."""

    def test_get_headers_auth(self):
        """Test authorization header is generated."""
        connector = ServiceNowConnector(
            instance_url="https://test.service-now.com",
            username="testuser",
            password="testpass",
        )
        headers = connector._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_get_headers_content_type(self):
        """Test content type header."""
        connector = ServiceNowConnector(
            instance_url="https://test.service-now.com",
            username="user",
            password="pass",
        )
        headers = connector._get_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    def test_auth_header_encoding(self):
        """Test auth header is properly base64 encoded."""
        import base64

        connector = ServiceNowConnector(
            instance_url="https://test.service-now.com",
            username="myuser",
            password="mypass",
        )
        expected = base64.b64encode(b"myuser:mypass").decode()
        assert connector._auth_header == expected


class TestServiceNowConnectorUrls:
    """Tests for ServiceNow URL generation."""

    def test_get_table_url_incident(self):
        """Test incident table URL generation."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )
        url = connector._get_table_url("incident")
        assert url == "https://company.service-now.com/api/now/v2/table/incident"

    def test_get_table_url_cmdb_ci(self):
        """Test CMDB CI table URL generation."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )
        url = connector._get_table_url("cmdb_ci")
        assert url == "https://company.service-now.com/api/now/v2/table/cmdb_ci"

    def test_get_table_url_v1(self):
        """Test URL with v1 API version."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
            api_version="v1",
        )
        url = connector._get_table_url("sys_user")
        assert url == "https://company.service-now.com/api/now/v1/table/sys_user"

    def test_get_table_url_change_request(self):
        """Test change request table URL."""
        connector = ServiceNowConnector(
            instance_url="https://acme.service-now.com",
            username="user",
            password="pass",
        )
        url = connector._get_table_url("change_request")
        assert url == "https://acme.service-now.com/api/now/v2/table/change_request"


class TestServiceNowConnectorApiVersion:
    """Tests for connector API version settings."""

    def test_default_api_version(self):
        """Test default API version is v2."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
        )
        assert connector.api_version == "v2"

    def test_v1_api_version(self):
        """Test v1 API version."""
        connector = ServiceNowConnector(
            instance_url="https://company.service-now.com",
            username="user",
            password="pass",
            api_version="v1",
        )
        url = connector._get_table_url("incident")
        assert "/v1/" in url
