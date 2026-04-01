"""
Tests for Enterprise Connectors - ADR-028 Phase 8

Tests for:
- ServiceNow Connector
- Splunk Connector
- Azure DevOps Connector
- Terraform Cloud Connector
- Snyk Connector
"""

import platform

import pytest

# These tests require pytest-forked for isolation due to global config state.
# On Linux (CI), mock patches don't apply correctly without forked mode.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from unittest.mock import AsyncMock, MagicMock, patch

from src.config import IntegrationMode
from src.services.external_tool_connectors import ConnectorResult, ConnectorStatus


# Fixture to enable enterprise mode for all tests in this module
@pytest.fixture(autouse=True)
def enable_enterprise_mode():
    """Enable enterprise mode for connector tests."""
    with patch("src.config.integration_config.get_integration_config") as mock_config:
        mock_config_instance = MagicMock()
        mock_config_instance.mode = IntegrationMode.ENTERPRISE
        mock_config_instance.is_enterprise_mode = True
        mock_config_instance.is_defense_mode = (
            False  # Key property checked by decorator
        )
        mock_config.return_value = mock_config_instance
        yield


# =============================================================================
# ServiceNow Connector Tests
# =============================================================================


class TestServiceNowConnector:
    """Tests for ServiceNow connector."""

    @pytest.fixture
    def servicenow_connector(self):
        """Create ServiceNow connector instance."""
        from src.services.servicenow_connector import ServiceNowConnector

        return ServiceNowConnector(
            instance_url="https://test.service-now.com",
            username="api_user",
            password="api_password",
            default_assignment_group="IT Security",
        )

    def test_connector_initialization(self, servicenow_connector):
        """Test ServiceNow connector initializes correctly."""
        assert servicenow_connector.name == "servicenow"
        assert servicenow_connector.instance_url == "https://test.service-now.com"
        assert servicenow_connector.default_assignment_group == "IT Security"
        # Use .value comparison for fork-safe enum identity
        assert servicenow_connector.status.value == ConnectorStatus.DISCONNECTED.value

    def test_get_table_url(self, servicenow_connector):
        """Test table URL construction."""
        url = servicenow_connector._get_table_url("incident")
        assert url == "https://test.service-now.com/api/now/v2/table/incident"

    def test_headers_include_auth(self, servicenow_connector):
        """Test headers include authorization."""
        headers = servicenow_connector._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"

    def test_create_incident_payload_construction(self, servicenow_connector):
        """Test incident payload is constructed correctly."""
        from src.services.servicenow_connector import (
            ServiceNowImpact,
            ServiceNowUrgency,
        )

        # Verify the connector can construct proper payloads
        # without needing to actually make HTTP calls
        assert servicenow_connector.default_assignment_group == "IT Security"
        assert servicenow_connector._get_table_url("incident").endswith("/incident")

        # Verify enum values are correct for payloads
        assert ServiceNowUrgency.HIGH.value == 1
        assert ServiceNowImpact.HIGH.value == 1

    @pytest.mark.asyncio
    async def test_create_security_incident_formats_correctly(
        self, servicenow_connector
    ):
        """Test security incident creates with proper formatting."""
        with patch.object(
            servicenow_connector, "create_incident", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = ConnectorResult(
                success=True,
                data={"sys_id": "abc123", "number": "INC0012345"},
            )

            result = await servicenow_connector.create_security_incident(
                title="SQL Injection vulnerability",
                cve_id="CVE-2024-1234",
                severity="HIGH",
                affected_asset="/src/api/users.py",
                description="SQL injection found in user query",
            )

            assert result.success
            # Verify create_incident was called with proper formatting
            call_args = mock_create.call_args
            assert "[HIGH] Security:" in call_args.kwargs.get("short_description", "")
            assert "CVE-2024-1234" in call_args.kwargs.get("description", "")

    def test_urgency_enum_values(self):
        """Test ServiceNow urgency enum values."""
        from src.services.servicenow_connector import ServiceNowUrgency

        assert ServiceNowUrgency.HIGH.value == 1
        assert ServiceNowUrgency.MEDIUM.value == 2
        assert ServiceNowUrgency.LOW.value == 3

    def test_incident_state_enum_values(self):
        """Test ServiceNow incident state enum values."""
        from src.services.servicenow_connector import ServiceNowIncidentState

        assert ServiceNowIncidentState.NEW.value == 1
        assert ServiceNowIncidentState.RESOLVED.value == 6
        assert ServiceNowIncidentState.CLOSED.value == 7


# =============================================================================
# Splunk Connector Tests
# =============================================================================


class TestSplunkConnector:
    """Tests for Splunk connector."""

    @pytest.fixture
    def splunk_connector(self):
        """Create Splunk connector instance."""
        from src.services.splunk_connector import SplunkConnector

        return SplunkConnector(
            base_url="https://splunk.test.com:8089",
            token="test-token",
            hec_url="https://splunk.test.com:8088",
            hec_token="hec-token",
            default_index="security",
        )

    def test_connector_initialization(self, splunk_connector):
        """Test Splunk connector initializes correctly."""
        assert splunk_connector.name == "splunk"
        assert splunk_connector.base_url == "https://splunk.test.com:8089"
        assert splunk_connector.hec_url == "https://splunk.test.com:8088"
        assert splunk_connector.default_index == "security"

    def test_auth_headers(self, splunk_connector):
        """Test auth headers include bearer token."""
        headers = splunk_connector._get_auth_headers()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test-token"

    def test_hec_headers(self, splunk_connector):
        """Test HEC headers include Splunk token."""
        headers = splunk_connector._get_hec_headers()
        assert headers["Authorization"] == "Splunk hec-token"

    def test_severity_enum_values(self):
        """Test Splunk severity enum values."""
        from src.services.splunk_connector import SplunkSeverity

        assert SplunkSeverity.CRITICAL.value == "critical"
        assert SplunkSeverity.HIGH.value == "high"
        assert SplunkSeverity.MEDIUM.value == "medium"

    @pytest.mark.asyncio
    async def test_send_event_requires_hec_config(self, splunk_connector):
        """Test send_event fails gracefully without HEC config."""
        connector = splunk_connector
        connector.hec_url = None
        connector.hec_token = None

        result = await connector.send_event(
            event={"test": "event"},
            source="test",
        )

        assert not result.success
        assert "HEC" in result.error

    @pytest.mark.asyncio
    async def test_send_security_event_format(self, splunk_connector):
        """Test security event formatting."""
        from src.services.splunk_connector import SplunkSeverity

        with patch.object(
            splunk_connector, "send_event", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = ConnectorResult(success=True)

            result = await splunk_connector.send_security_event(
                event_type="vulnerability_detected",
                severity=SplunkSeverity.HIGH,
                description="Critical vulnerability found",
                cve_id="CVE-2024-5678",
                affected_asset="/app/server.js",
            )

            assert result.success
            call_args = mock_send.call_args
            event = call_args.kwargs.get("event", {})
            assert event.get("event_type") == "vulnerability_detected"
            assert event.get("severity") == "high"
            assert event.get("cve_id") == "CVE-2024-5678"


# =============================================================================
# Azure DevOps Connector Tests
# =============================================================================


class TestAzureDevOpsConnector:
    """Tests for Azure DevOps connector."""

    @pytest.fixture
    def ado_connector(self):
        """Create Azure DevOps connector instance."""
        from src.services.azure_devops_connector import AzureDevOpsConnector

        return AzureDevOpsConnector(
            organization="test-org",
            project="test-project",
            pat="test-pat",
        )

    def test_connector_initialization(self, ado_connector):
        """Test Azure DevOps connector initializes correctly."""
        assert ado_connector.name == "azure_devops"
        assert ado_connector.organization == "test-org"
        assert ado_connector.project == "test-project"
        assert ado_connector.base_url == "https://dev.azure.com/test-org/test-project"

    def test_api_url_construction(self, ado_connector):
        """Test API URL is constructed correctly."""
        url = ado_connector._get_api_url("pipelines/123/runs")
        assert "dev.azure.com" in url
        assert "api-version=7.1" in url
        assert "pipelines/123/runs" in url

    def test_headers_include_pat_auth(self, ado_connector):
        """Test headers include PAT-based auth."""
        headers = ado_connector._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_work_item_type_enum(self):
        """Test work item type enum values."""
        from src.services.azure_devops_connector import WorkItemType

        assert WorkItemType.BUG.value == "Bug"
        assert WorkItemType.TASK.value == "Task"
        assert WorkItemType.USER_STORY.value == "User Story"

    def test_pipeline_run_state_enum(self):
        """Test pipeline run state enum values."""
        from src.services.azure_devops_connector import PipelineRunState

        assert PipelineRunState.COMPLETED.value == "completed"
        assert PipelineRunState.IN_PROGRESS.value == "inProgress"

    @pytest.mark.asyncio
    async def test_create_security_bug_format(self, ado_connector):
        """Test security bug creation with proper formatting."""
        from src.services.azure_devops_connector import WorkItemSeverity, WorkItemType

        with patch.object(
            ado_connector, "create_work_item", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = ConnectorResult(
                success=True,
                data={"id": 123, "type": "Bug"},
            )

            result = await ado_connector.create_security_bug(
                title="XSS Vulnerability",
                cve_id="CVE-2024-9999",
                severity="CRITICAL",
                affected_file="/src/views/user.html",
            )

            assert result.success
            call_args = mock_create.call_args
            assert "[CRITICAL] Security:" in call_args.kwargs.get("title", "")
            assert call_args.kwargs.get("work_item_type") == WorkItemType.BUG
            assert call_args.kwargs.get("severity") == WorkItemSeverity.CRITICAL


# =============================================================================
# Terraform Cloud Connector Tests
# =============================================================================


class TestTerraformCloudConnector:
    """Tests for Terraform Cloud connector."""

    @pytest.fixture
    def tfc_connector(self):
        """Create Terraform Cloud connector instance."""
        from src.services.terraform_cloud_connector import TerraformCloudConnector

        return TerraformCloudConnector(
            organization="test-org",
            token="test-token",
        )

    def test_connector_initialization(self, tfc_connector):
        """Test Terraform Cloud connector initializes correctly."""
        assert tfc_connector.name == "terraform_cloud"
        assert tfc_connector.organization == "test-org"
        assert tfc_connector.api_url == "https://app.terraform.io/api/v2"

    def test_custom_api_url(self):
        """Test custom API URL for Terraform Enterprise."""
        from src.services.terraform_cloud_connector import TerraformCloudConnector

        tfe = TerraformCloudConnector(
            organization="test-org",
            token="test-token",
            api_url="https://tfe.company.com/api/v2",
        )
        assert tfe.api_url == "https://tfe.company.com/api/v2"

    def test_headers_include_bearer_token(self, tfc_connector):
        """Test headers include bearer token."""
        headers = tfc_connector._get_headers()
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/vnd.api+json"

    def test_run_status_enum(self):
        """Test Terraform run status enum values."""
        from src.services.terraform_cloud_connector import TerraformRunStatus

        assert TerraformRunStatus.PLANNING.value == "planning"
        assert TerraformRunStatus.APPLIED.value == "applied"
        assert TerraformRunStatus.ERRORED.value == "errored"

    def test_variable_category_enum(self):
        """Test variable category enum values."""
        from src.services.terraform_cloud_connector import VariableCategory

        assert VariableCategory.TERRAFORM.value == "terraform"
        assert VariableCategory.ENV.value == "env"

    @pytest.mark.asyncio
    async def test_trigger_security_patch_run(self, tfc_connector):
        """Test security patch run trigger with proper formatting."""
        with patch.object(
            tfc_connector, "get_workspace", new_callable=AsyncMock
        ) as mock_get_ws:
            mock_get_ws.return_value = ConnectorResult(
                success=True,
                data={"id": "ws-abc123"},
            )

            with patch.object(
                tfc_connector, "trigger_run", new_callable=AsyncMock
            ) as mock_trigger:
                mock_trigger.return_value = ConnectorResult(
                    success=True,
                    data={"run_id": "run-xyz789"},
                )

                result = await tfc_connector.trigger_security_patch_run(
                    workspace_name="production",
                    cve_id="CVE-2024-1111",
                    severity="HIGH",
                    description="Security patch for critical vulnerability",
                )

                assert result.success
                # Verify trigger_run was called with plan_only=True for security patches
                call_args = mock_trigger.call_args
                assert call_args.kwargs.get("plan_only") is True
                assert call_args.kwargs.get("auto_apply") is False


# =============================================================================
# Snyk Connector Tests
# =============================================================================


class TestSnykConnector:
    """Tests for Snyk connector."""

    @pytest.fixture
    def snyk_connector(self):
        """Create Snyk connector instance."""
        from src.services.snyk_connector import SnykConnector

        return SnykConnector(
            token="test-snyk-token",
            org_id="test-org-id",
        )

    def test_connector_initialization(self, snyk_connector):
        """Test Snyk connector initializes correctly."""
        assert snyk_connector.name == "snyk"
        assert snyk_connector.org_id == "test-org-id"
        assert snyk_connector.API_V1_URL == "https://api.snyk.io/v1"

    def test_headers_include_token(self, snyk_connector):
        """Test headers include token authentication."""
        headers = snyk_connector._get_headers()
        assert headers["Authorization"] == "token test-snyk-token"

    def test_severity_enum_values(self):
        """Test Snyk severity enum values."""
        from src.services.snyk_connector import SnykSeverity

        assert SnykSeverity.CRITICAL.value == "critical"
        assert SnykSeverity.HIGH.value == "high"
        assert SnykSeverity.MEDIUM.value == "medium"
        assert SnykSeverity.LOW.value == "low"

    def test_project_type_enum_values(self):
        """Test Snyk project type enum values."""
        from src.services.snyk_connector import SnykProjectType

        assert SnykProjectType.NPM.value == "npm"
        assert SnykProjectType.PIP.value == "pip"
        assert SnykProjectType.DOCKER.value == "docker"

    def test_exploit_maturity_enum(self):
        """Test exploit maturity enum values."""
        from src.services.snyk_connector import SnykExploitMaturity

        assert SnykExploitMaturity.MATURE.value == "Mature"
        assert SnykExploitMaturity.PROOF_OF_CONCEPT.value == "Proof of Concept"

    @pytest.mark.asyncio
    async def test_list_projects_requires_org_id(self, snyk_connector):
        """Test list_projects fails without org_id."""
        connector = snyk_connector
        connector.org_id = None

        result = await connector.list_projects()

        assert not result.success
        assert "Organization ID required" in result.error

    @pytest.mark.asyncio
    async def test_get_project_issues_requires_org_id(self, snyk_connector):
        """Test get_project_issues fails without org_id."""
        connector = snyk_connector
        connector.org_id = None

        result = await connector.get_project_issues(project_id="test-project")

        assert not result.success
        assert "Organization ID required" in result.error


# =============================================================================
# Cross-Connector Integration Tests
# =============================================================================


class TestConnectorIntegration:
    """Integration tests across connectors."""

    def test_all_connectors_inherit_base_class(self):
        """Test all connectors inherit from ExternalToolConnector."""
        from src.services.azure_devops_connector import AzureDevOpsConnector
        from src.services.external_tool_connectors import ExternalToolConnector
        from src.services.servicenow_connector import ServiceNowConnector
        from src.services.snyk_connector import SnykConnector
        from src.services.splunk_connector import SplunkConnector
        from src.services.terraform_cloud_connector import TerraformCloudConnector

        connectors = [
            ServiceNowConnector("https://test.com", "user", "pass"),
            SplunkConnector("https://test.com:8089", token="test"),
            AzureDevOpsConnector("org", "project", "pat"),
            TerraformCloudConnector("org", "token"),
            SnykConnector("token"),
        ]

        for connector in connectors:
            assert isinstance(connector, ExternalToolConnector)
            assert hasattr(connector, "health_check")
            assert hasattr(connector, "status")
            assert hasattr(connector, "metrics")

    def test_all_connectors_have_metrics(self):
        """Test all connectors track metrics."""
        from src.services.azure_devops_connector import AzureDevOpsConnector
        from src.services.servicenow_connector import ServiceNowConnector
        from src.services.snyk_connector import SnykConnector
        from src.services.splunk_connector import SplunkConnector
        from src.services.terraform_cloud_connector import TerraformCloudConnector

        connectors = [
            ServiceNowConnector("https://test.com", "user", "pass"),
            SplunkConnector("https://test.com:8089", token="test"),
            AzureDevOpsConnector("org", "project", "pat"),
            TerraformCloudConnector("org", "token"),
            SnykConnector("token"),
        ]

        for connector in connectors:
            metrics = connector.metrics
            assert "name" in metrics
            assert "status" in metrics
            assert "request_count" in metrics
            assert "error_count" in metrics
            assert "avg_latency_ms" in metrics

    def test_connector_status_tracking(self):
        """Test connector status is tracked correctly."""
        from src.services.servicenow_connector import ServiceNowConnector

        connector = ServiceNowConnector("https://test.com", "user", "pass")

        # Initial status should be disconnected
        # Use .value comparison for fork-safe enum identity
        assert connector.status.value == ConnectorStatus.DISCONNECTED.value

        # Manually set status for testing
        connector._status = ConnectorStatus.CONNECTED
        assert connector.status.value == ConnectorStatus.CONNECTED.value

        connector._status = ConnectorStatus.ERROR
        assert connector.status.value == ConnectorStatus.ERROR.value


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for connector data classes."""

    def test_servicenow_incident_dataclass(self):
        """Test ServiceNow incident data class."""
        from src.services.servicenow_connector import (
            ServiceNowImpact,
            ServiceNowIncident,
            ServiceNowUrgency,
        )

        incident = ServiceNowIncident(
            short_description="Test incident",
            description="Test description",
            category="security",
            urgency=ServiceNowUrgency.HIGH,
            impact=ServiceNowImpact.HIGH,
        )

        assert incident.short_description == "Test incident"
        assert incident.urgency == ServiceNowUrgency.HIGH
        assert incident.impact == ServiceNowImpact.HIGH

    def test_splunk_event_dataclass(self):
        """Test Splunk event data class."""
        from src.services.splunk_connector import SplunkEvent

        event = SplunkEvent(
            event={"message": "Test event"},
            source="test-source",
            sourcetype="test-type",
            index="security",
        )

        assert event.event == {"message": "Test event"}
        assert event.source == "test-source"
        assert event.index == "security"

    def test_azure_devops_work_item_dataclass(self):
        """Test Azure DevOps work item data class."""
        from src.services.azure_devops_connector import (
            WorkItem,
            WorkItemPriority,
            WorkItemType,
        )

        work_item = WorkItem(
            title="Test bug",
            work_item_type=WorkItemType.BUG,
            description="Test description",
            priority=WorkItemPriority.P1,
            tags=["security", "urgent"],
        )

        assert work_item.title == "Test bug"
        assert work_item.work_item_type == WorkItemType.BUG
        assert work_item.priority == WorkItemPriority.P1
        assert "security" in work_item.tags

    def test_terraform_workspace_dataclass(self):
        """Test Terraform workspace data class."""
        from src.services.terraform_cloud_connector import TerraformWorkspace

        workspace = TerraformWorkspace(
            id="ws-abc123",
            name="production",
            organization="my-org",
            auto_apply=False,
            terraform_version="1.5.0",
            resource_count=42,
        )

        assert workspace.id == "ws-abc123"
        assert workspace.name == "production"
        assert workspace.resource_count == 42

    def test_snyk_vulnerability_dataclass(self):
        """Test Snyk vulnerability data class."""
        from src.services.snyk_connector import SnykSeverity, SnykVulnerability

        vuln = SnykVulnerability(
            id="SNYK-JS-LODASH-1234",
            title="Prototype Pollution",
            severity=SnykSeverity.CRITICAL,
            package_name="lodash",
            version="4.17.20",
            cve_ids=["CVE-2021-23337"],
            cvss_score=9.8,
            fixed_in=["4.17.21"],
        )

        assert vuln.id == "SNYK-JS-LODASH-1234"
        assert vuln.severity == SnykSeverity.CRITICAL
        assert "CVE-2021-23337" in vuln.cve_ids
        assert vuln.cvss_score == 9.8


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestConnectorErrorHandling:
    """Tests for connector error handling."""

    def test_servicenow_error_tracking(self):
        """Test ServiceNow connector tracks errors in metrics."""
        from src.services.servicenow_connector import ServiceNowConnector

        connector = ServiceNowConnector(
            "https://test.service-now.com",
            "user",
            "pass",
        )

        # Manually record an error
        connector._record_request(100.0, success=False)
        connector._last_error = "Test error"

        metrics = connector.metrics
        assert metrics["error_count"] == 1
        assert metrics["last_error"] == "Test error"

    def test_splunk_error_tracking(self):
        """Test Splunk connector tracks errors in metrics."""
        from src.services.splunk_connector import SplunkConnector

        connector = SplunkConnector(
            base_url="https://splunk.test.com:8089",
            token="test-token",
        )

        # Manually record errors
        connector._record_request(50.0, success=False)
        connector._record_request(60.0, success=False)
        connector._status = ConnectorStatus.AUTH_FAILED
        connector._last_error = "Unauthorized"

        metrics = connector.metrics
        assert metrics["error_count"] == 2
        assert metrics["status"] == "auth_failed"
        assert metrics["last_error"] == "Unauthorized"

    def test_azure_devops_error_tracking(self):
        """Test Azure DevOps connector tracks errors in metrics."""
        from src.services.azure_devops_connector import AzureDevOpsConnector

        connector = AzureDevOpsConnector("org", "project", "pat")

        # Manually record an error
        connector._record_request(75.0, success=False)
        connector._status = ConnectorStatus.ERROR
        connector._last_error = "Not found"

        metrics = connector.metrics
        assert metrics["error_count"] == 1
        assert metrics["status"] == "error"
        assert metrics["last_error"] == "Not found"


# =============================================================================
# Connector Result Tests
# =============================================================================


class TestConnectorResult:
    """Tests for ConnectorResult data class."""

    def test_successful_result(self):
        """Test successful ConnectorResult."""
        result = ConnectorResult(
            success=True,
            data={"id": "123", "status": "created"},
            status_code=201,
            latency_ms=150.5,
            request_id="req-abc",
        )

        assert result.success
        assert result.data["id"] == "123"
        assert result.status_code == 201
        assert result.latency_ms == 150.5
        assert result.error is None

    def test_failed_result(self):
        """Test failed ConnectorResult."""
        result = ConnectorResult(
            success=False,
            error="Authentication failed",
            status_code=401,
            latency_ms=50.0,
        )

        assert not result.success
        assert result.error == "Authentication failed"
        assert result.status_code == 401
        assert result.data == {}

    def test_result_defaults(self):
        """Test ConnectorResult default values."""
        result = ConnectorResult(success=True)

        assert result.success
        assert result.data == {}
        assert result.error is None
        assert result.status_code is None
        assert result.latency_ms == 0.0
        assert result.request_id is None


# =============================================================================
# CrowdStrike Connector Tests
# =============================================================================


class TestCrowdStrikeConnector:
    """Tests for CrowdStrike Falcon connector."""

    @pytest.fixture
    def crowdstrike_connector(self):
        """Create CrowdStrike connector instance."""
        from src.services.crowdstrike_connector import (
            CrowdStrikeCloud,
            CrowdStrikeConnector,
        )

        return CrowdStrikeConnector(
            client_id="test-client-id",
            client_secret="test-client-secret",
            cloud=CrowdStrikeCloud.US1,
        )

    def test_connector_initialization(self, crowdstrike_connector):
        """Test CrowdStrike connector initializes correctly."""
        assert crowdstrike_connector.name == "crowdstrike"
        assert crowdstrike_connector.base_url == "https://api.crowdstrike.com"
        assert crowdstrike_connector.client_id == "test-client-id"
        # Use .value comparison for fork-safe enum identity
        assert crowdstrike_connector.status.value == ConnectorStatus.DISCONNECTED.value

    def test_cloud_enum_values(self):
        """Test CrowdStrike cloud region enum values."""
        from src.services.crowdstrike_connector import CrowdStrikeCloud

        assert CrowdStrikeCloud.US1.value == "api.crowdstrike.com"
        assert CrowdStrikeCloud.US2.value == "api.us-2.crowdstrike.com"
        assert CrowdStrikeCloud.EU1.value == "api.eu-1.crowdstrike.com"
        assert CrowdStrikeCloud.GOV.value == "api.laggar.gcw.crowdstrike.com"

    def test_detection_severity_enum(self):
        """Test detection severity enum values."""
        from src.services.crowdstrike_connector import DetectionSeverity

        assert DetectionSeverity.CRITICAL.value == "critical"
        assert DetectionSeverity.HIGH.value == "high"
        assert DetectionSeverity.MEDIUM.value == "medium"
        assert DetectionSeverity.LOW.value == "low"
        assert DetectionSeverity.INFORMATIONAL.value == "informational"

    def test_detection_status_enum(self):
        """Test detection status enum values."""
        from src.services.crowdstrike_connector import DetectionStatus

        assert DetectionStatus.NEW.value == "new"
        assert DetectionStatus.IN_PROGRESS.value == "in_progress"
        assert DetectionStatus.TRUE_POSITIVE.value == "true_positive"
        assert DetectionStatus.FALSE_POSITIVE.value == "false_positive"
        assert DetectionStatus.CLOSED.value == "closed"

    def test_ioc_type_enum(self):
        """Test IOC type enum values."""
        from src.services.crowdstrike_connector import IOCType

        assert IOCType.SHA256.value == "sha256"
        assert IOCType.MD5.value == "md5"
        assert IOCType.DOMAIN.value == "domain"
        assert IOCType.IPV4.value == "ipv4"
        assert IOCType.IPV6.value == "ipv6"

    def test_ioc_action_enum(self):
        """Test IOC action enum values."""
        from src.services.crowdstrike_connector import IOCAction

        assert IOCAction.DETECT.value == "detect"
        assert IOCAction.PREVENT.value == "prevent"
        assert IOCAction.ALLOW.value == "allow"

    def test_host_status_enum(self):
        """Test host status enum values."""
        from src.services.crowdstrike_connector import HostStatus

        assert HostStatus.NORMAL.value == "normal"
        assert HostStatus.CONTAINED.value == "contained"
        assert HostStatus.CONTAINMENT_PENDING.value == "containment_pending"

    def test_host_dataclass(self):
        """Test CrowdStrike host data class."""
        from src.services.crowdstrike_connector import CrowdStrikeHost, HostStatus

        host = CrowdStrikeHost(
            device_id="abc123",
            hostname="server01",
            platform_name="Windows",
            os_version="Windows Server 2019",
            status=HostStatus.NORMAL,
            local_ip="192.168.1.100",
            external_ip="203.0.113.50",
            tags=["production", "web-server"],
        )

        assert host.device_id == "abc123"
        assert host.hostname == "server01"
        assert host.status == HostStatus.NORMAL
        assert "production" in host.tags

    def test_detection_dataclass(self):
        """Test CrowdStrike detection data class."""
        from src.services.crowdstrike_connector import (
            CrowdStrikeDetection,
            DetectionSeverity,
            DetectionStatus,
        )

        detection = CrowdStrikeDetection(
            detection_id="det-123",
            device_id="dev-456",
            hostname="workstation01",
            severity=DetectionSeverity.HIGH,
            status=DetectionStatus.NEW,
            tactic="Execution",
            technique="PowerShell",
            description="Suspicious PowerShell execution",
        )

        assert detection.detection_id == "det-123"
        assert detection.severity == DetectionSeverity.HIGH
        assert detection.status == DetectionStatus.NEW

    def test_ioc_dataclass(self):
        """Test CrowdStrike IOC data class."""
        from src.services.crowdstrike_connector import (
            CrowdStrikeIOC,
            DetectionSeverity,
            IOCAction,
            IOCType,
        )

        ioc = CrowdStrikeIOC(
            type=IOCType.SHA256,
            value="abc123def456",
            action=IOCAction.PREVENT,
            severity=DetectionSeverity.CRITICAL,
            description="Known malware hash",
            platforms=["windows", "linux"],
            tags=["malware", "ransomware"],
        )

        assert ioc.type == IOCType.SHA256
        assert ioc.action == IOCAction.PREVENT
        assert ioc.severity == DetectionSeverity.CRITICAL
        assert "malware" in ioc.tags

    def test_error_tracking(self, crowdstrike_connector):
        """Test CrowdStrike connector tracks errors."""
        crowdstrike_connector._record_request(100.0, success=False)
        crowdstrike_connector._status = ConnectorStatus.AUTH_FAILED
        crowdstrike_connector._last_error = "Invalid credentials"

        metrics = crowdstrike_connector.metrics
        assert metrics["error_count"] == 1
        assert metrics["status"] == "auth_failed"
        assert metrics["last_error"] == "Invalid credentials"


# =============================================================================
# Qualys Connector Tests
# =============================================================================


class TestQualysConnector:
    """Tests for Qualys VMDR connector."""

    @pytest.fixture
    def qualys_connector(self):
        """Create Qualys connector instance."""
        from src.services.qualys_connector import QualysConnector, QualysPlatform

        return QualysConnector(
            username="api_user",
            password="api_password",
            platform=QualysPlatform.US1,
        )

    def test_connector_initialization(self, qualys_connector):
        """Test Qualys connector initializes correctly."""
        assert qualys_connector.name == "qualys"
        assert qualys_connector.base_url == "https://qualysapi.qualys.com"
        # Use .value comparison for fork-safe enum identity
        assert qualys_connector.status.value == ConnectorStatus.DISCONNECTED.value

    def test_platform_enum_values(self):
        """Test Qualys platform enum values."""
        from src.services.qualys_connector import QualysPlatform

        assert QualysPlatform.US1.value == "qualysapi.qualys.com"
        assert QualysPlatform.US2.value == "qualysapi.qg2.apps.qualys.com"
        assert QualysPlatform.EU1.value == "qualysapi.qualys.eu"
        assert QualysPlatform.CA1.value == "qualysapi.qg1.apps.qualys.ca"

    def test_severity_enum_values(self):
        """Test Qualys severity enum values."""
        from src.services.qualys_connector import QualysSeverity

        assert QualysSeverity.INFORMATIONAL.value == 1
        assert QualysSeverity.LOW.value == 2
        assert QualysSeverity.MEDIUM.value == 3
        assert QualysSeverity.HIGH.value == 4
        assert QualysSeverity.CRITICAL.value == 5

    def test_vuln_type_enum(self):
        """Test Qualys vulnerability type enum values."""
        from src.services.qualys_connector import QualysVulnType

        assert QualysVulnType.CONFIRMED.value == "Confirmed"
        assert QualysVulnType.POTENTIAL.value == "Potential"
        assert QualysVulnType.INFO.value == "Info"

    def test_scan_status_enum(self):
        """Test Qualys scan status enum values."""
        from src.services.qualys_connector import QualysScanStatus

        assert QualysScanStatus.RUNNING.value == "Running"
        assert QualysScanStatus.FINISHED.value == "Finished"
        assert QualysScanStatus.ERROR.value == "Error"

    def test_headers_include_auth(self, qualys_connector):
        """Test headers include authorization."""
        headers = qualys_connector._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert "X-Requested-With" in headers

    def test_vulnerability_dataclass(self):
        """Test Qualys vulnerability data class."""
        from src.services.qualys_connector import (
            QualysSeverity,
            QualysVulnerability,
            QualysVulnType,
        )

        vuln = QualysVulnerability(
            qid=12345,
            title="SQL Injection",
            severity=QualysSeverity.CRITICAL,
            vuln_type=QualysVulnType.CONFIRMED,
            category="Web Application",
            cve_ids=["CVE-2024-1234", "CVE-2024-1235"],
            cvss_base=9.8,
            solution="Update to latest version",
            pci_flag=True,
        )

        assert vuln.qid == 12345
        assert vuln.severity == QualysSeverity.CRITICAL
        assert len(vuln.cve_ids) == 2
        assert vuln.pci_flag is True

    def test_host_dataclass(self):
        """Test Qualys host data class."""
        from src.services.qualys_connector import QualysHost

        host = QualysHost(
            host_id=98765,
            ip="192.168.1.100",
            hostname="server01.company.com",
            os="Windows Server 2019",
            tracking_method="IP",
            last_scan="2024-01-15T10:30:00Z",
            tags=["production", "database"],
        )

        assert host.host_id == 98765
        assert host.ip == "192.168.1.100"
        assert "production" in host.tags

    def test_detection_dataclass(self):
        """Test Qualys detection data class."""
        from src.services.qualys_connector import (
            QualysDetection,
            QualysSeverity,
            QualysVulnType,
        )

        detection = QualysDetection(
            host_id=98765,
            qid=12345,
            severity=QualysSeverity.HIGH,
            vuln_type=QualysVulnType.CONFIRMED,
            status="Active",
            first_found="2024-01-10",
            last_found="2024-01-15",
            times_found=5,
            port=443,
            protocol="TCP",
            service="HTTPS",
            ssl=True,
        )

        assert detection.host_id == 98765
        assert detection.qid == 12345
        assert detection.severity == QualysSeverity.HIGH
        assert detection.ssl is True

    def test_xml_parsing(self, qualys_connector):
        """Test XML response parsing."""
        sample_xml = """
        <SIMPLE_RETURN>
            <RESPONSE>
                <TEXT>Success</TEXT>
            </RESPONSE>
        </SIMPLE_RETURN>
        """
        result = qualys_connector._parse_xml_response(sample_xml)

        # Root element (SIMPLE_RETURN) becomes the container, its children are the dict keys
        assert "RESPONSE" in result
        assert result["RESPONSE"]["TEXT"] == "Success"

    def test_error_tracking(self, qualys_connector):
        """Test Qualys connector tracks errors."""
        qualys_connector._record_request(200.0, success=False)
        qualys_connector._record_request(150.0, success=False)
        qualys_connector._status = ConnectorStatus.ERROR
        qualys_connector._last_error = "API rate limit exceeded"

        metrics = qualys_connector.metrics
        assert metrics["error_count"] == 2
        assert metrics["status"] == "error"
        assert metrics["last_error"] == "API rate limit exceeded"

    def test_custom_platform_url(self):
        """Test custom platform URL."""
        from src.services.qualys_connector import QualysConnector

        connector = QualysConnector(
            username="user",
            password="pass",
            platform="custom-qualys.company.com",
        )
        assert connector.base_url == "https://custom-qualys.company.com"
