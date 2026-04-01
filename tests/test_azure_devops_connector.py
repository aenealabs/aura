"""
Project Aura - Azure DevOps Connector Tests

Tests for the Azure DevOps connector implementation.
"""

import json
import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from unittest.mock import AsyncMock, MagicMock, patch

# Import the connector module so we can patch its aiohttp reference
import src.services.azure_devops_connector as connector_module
from src.config import IntegrationMode
from src.services.azure_devops_connector import (
    AzureDevOpsConnector,
    PipelineRun,
    PipelineRunResult,
    PipelineRunState,
    WorkItem,
    WorkItemPriority,
    WorkItemSeverity,
    WorkItemState,
    WorkItemType,
)
from src.services.external_tool_connectors import ConnectorStatus

# =============================================================================
# Test Helpers
# =============================================================================


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

    mock_request_context = MagicMock()
    mock_request_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_request_context.__aexit__ = AsyncMock(return_value=None)

    mock_session_instance = MagicMock()
    mock_session_instance.post.return_value = mock_request_context
    mock_session_instance.get.return_value = mock_request_context
    mock_session_instance.patch.return_value = mock_request_context

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    return mock_session


@pytest.fixture
def enable_enterprise_mode():
    """Enable enterprise mode for tests."""
    with patch("src.config.integration_config.get_integration_config") as mock_config:
        mock_config_instance = MagicMock()
        mock_config_instance.mode = IntegrationMode.ENTERPRISE
        mock_config_instance.is_defense_mode = False
        mock_config_instance.is_enterprise_mode = True
        mock_config.return_value = mock_config_instance
        yield mock_config_instance


# =============================================================================
# Enum Tests
# =============================================================================


class TestPipelineRunState:
    """Tests for PipelineRunState enum."""

    def test_unknown(self):
        assert PipelineRunState.UNKNOWN.value == "unknown"

    def test_canceling(self):
        assert PipelineRunState.CANCELING.value == "canceling"

    def test_completed(self):
        assert PipelineRunState.COMPLETED.value == "completed"

    def test_in_progress(self):
        assert PipelineRunState.IN_PROGRESS.value == "inProgress"

    def test_not_started(self):
        assert PipelineRunState.NOT_STARTED.value == "notStarted"


class TestPipelineRunResult:
    """Tests for PipelineRunResult enum."""

    def test_canceled(self):
        assert PipelineRunResult.CANCELED.value == "canceled"

    def test_failed(self):
        assert PipelineRunResult.FAILED.value == "failed"

    def test_succeeded(self):
        assert PipelineRunResult.SUCCEEDED.value == "succeeded"

    def test_unknown(self):
        assert PipelineRunResult.UNKNOWN.value == "unknown"


class TestWorkItemType:
    """Tests for WorkItemType enum."""

    def test_bug(self):
        assert WorkItemType.BUG.value == "Bug"

    def test_task(self):
        assert WorkItemType.TASK.value == "Task"

    def test_user_story(self):
        assert WorkItemType.USER_STORY.value == "User Story"

    def test_feature(self):
        assert WorkItemType.FEATURE.value == "Feature"

    def test_epic(self):
        assert WorkItemType.EPIC.value == "Epic"

    def test_issue(self):
        assert WorkItemType.ISSUE.value == "Issue"

    def test_impediment(self):
        assert WorkItemType.IMPEDIMENT.value == "Impediment"


class TestWorkItemState:
    """Tests for WorkItemState enum."""

    def test_new(self):
        assert WorkItemState.NEW.value == "New"

    def test_active(self):
        assert WorkItemState.ACTIVE.value == "Active"

    def test_resolved(self):
        assert WorkItemState.RESOLVED.value == "Resolved"

    def test_closed(self):
        assert WorkItemState.CLOSED.value == "Closed"

    def test_removed(self):
        assert WorkItemState.REMOVED.value == "Removed"


class TestWorkItemSeverity:
    """Tests for WorkItemSeverity enum."""

    def test_critical(self):
        assert WorkItemSeverity.CRITICAL.value == "1 - Critical"

    def test_high(self):
        assert WorkItemSeverity.HIGH.value == "2 - High"

    def test_medium(self):
        assert WorkItemSeverity.MEDIUM.value == "3 - Medium"

    def test_low(self):
        assert WorkItemSeverity.LOW.value == "4 - Low"


class TestWorkItemPriority:
    """Tests for WorkItemPriority enum."""

    def test_p1(self):
        assert WorkItemPriority.P1.value == 1

    def test_p2(self):
        assert WorkItemPriority.P2.value == 2

    def test_p3(self):
        assert WorkItemPriority.P3.value == 3

    def test_p4(self):
        assert WorkItemPriority.P4.value == 4


# =============================================================================
# Dataclass Tests
# =============================================================================


class TestWorkItem:
    """Tests for WorkItem dataclass."""

    def test_basic_creation(self):
        item = WorkItem(title="Test Task")
        assert item.title == "Test Task"
        assert item.work_item_type == WorkItemType.TASK

    def test_full_creation(self):
        item = WorkItem(
            title="Critical Bug",
            work_item_type=WorkItemType.BUG,
            description="This is a critical bug",
            state=WorkItemState.NEW,
            assigned_to="user@example.com",
            area_path="Project\\Area",
            iteration_path="Sprint 1",
            priority=WorkItemPriority.P1,
            severity=WorkItemSeverity.CRITICAL,
            tags=["security", "urgent"],
            parent_id=123,
            additional_fields={"Custom.Field": "value"},
        )
        assert item.work_item_type == WorkItemType.BUG
        assert item.severity == WorkItemSeverity.CRITICAL
        assert len(item.tags) == 2

    def test_default_values(self):
        item = WorkItem(title="Simple Task")
        assert item.description == ""
        assert item.state is None
        assert item.tags is None
        assert item.additional_fields == {}


class TestPipelineRun:
    """Tests for PipelineRun dataclass."""

    def test_basic_creation(self):
        run = PipelineRun(
            run_id=123,
            pipeline_id=456,
            pipeline_name="CI Build",
            state=PipelineRunState.IN_PROGRESS,
        )
        assert run.run_id == 123
        assert run.state == PipelineRunState.IN_PROGRESS

    def test_full_creation(self):
        run = PipelineRun(
            run_id=123,
            pipeline_id=456,
            pipeline_name="CI Build",
            state=PipelineRunState.COMPLETED,
            result=PipelineRunResult.SUCCEEDED,
            created_date="2024-01-01T00:00:00Z",
            finished_date="2024-01-01T00:30:00Z",
            source_branch="refs/heads/main",
            source_version="abc123",
            url="https://dev.azure.com/org/project/_build/results?buildId=123",
        )
        assert run.result == PipelineRunResult.SUCCEEDED
        assert run.source_branch == "refs/heads/main"

    def test_default_values(self):
        run = PipelineRun(
            run_id=1,
            pipeline_id=1,
            pipeline_name="Test",
            state=PipelineRunState.NOT_STARTED,
        )
        assert run.result is None
        assert run.created_date is None
        assert run.url is None


# =============================================================================
# Connector Initialization Tests
# =============================================================================


class TestAzureDevOpsConnectorInit:
    """Tests for AzureDevOpsConnector initialization."""

    def test_basic_init(self):
        connector = AzureDevOpsConnector(
            organization="myorg",
            project="myproject",
            pat="my-pat-token",
        )
        assert connector.organization == "myorg"
        assert connector.project == "myproject"
        assert connector.api_version == "7.1"
        assert connector.base_url == "https://dev.azure.com/myorg/myproject"

    def test_custom_api_version(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
            api_version="6.0",
        )
        assert connector.api_version == "6.0"

    def test_custom_timeout(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
            timeout_seconds=60.0,
        )
        assert connector.timeout.total == 60.0

    def test_vssps_url(self):
        connector = AzureDevOpsConnector(
            organization="testorg",
            project="testproj",
            pat="token",
        )
        assert connector.vssps_url == "https://vssps.dev.azure.com/testorg"

    def test_auth_header_created(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="mytoken",
        )
        import base64

        expected = base64.b64encode(b":mytoken").decode()
        assert connector._auth_header == expected

    def test_get_headers(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )
        headers = connector._get_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_custom_content_type(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )
        headers = connector._get_headers("application/json-patch+json")
        assert headers["Content-Type"] == "application/json-patch+json"

    def test_get_api_url(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )
        url = connector._get_api_url("pipelines/123/runs")
        assert "dev.azure.com/org/proj/_apis/pipelines/123/runs" in url
        assert "api-version=7.1" in url


# =============================================================================
# Pipeline Management Tests
# =============================================================================


class TestTriggerPipeline:
    """Tests for trigger_pipeline method."""

    @pytest.mark.asyncio
    async def test_trigger_pipeline_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "id": 12345,
                "state": "notStarted",
                "_links": {
                    "web": {
                        "href": "https://dev.azure.com/org/proj/_build?buildId=12345"
                    }
                },
            },
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.trigger_pipeline(pipeline_id=123)
            assert result.success is True
            assert result.data["run_id"] == 12345

    @pytest.mark.asyncio
    async def test_trigger_pipeline_with_options(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            201,
            {"id": 12346, "state": "notStarted"},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.trigger_pipeline(
                pipeline_id=123,
                branch="develop",
                variables={"ENV": "test"},
                stages_to_skip=["Deploy"],
                template_parameters={"param1": "value1"},
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_trigger_pipeline_error(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            404,
            {"message": "Pipeline not found"},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.trigger_pipeline(pipeline_id=999)
            assert result.success is False


class TestGetPipelineRun:
    """Tests for get_pipeline_run method."""

    @pytest.mark.asyncio
    async def test_get_pipeline_run_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "id": 12345,
                "pipeline": {"id": 123, "name": "CI Pipeline"},
                "state": "completed",
                "result": "succeeded",
                "createdDate": "2024-01-01T00:00:00Z",
            },
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.get_pipeline_run(pipeline_id=123, run_id=12345)
            assert result.success is True
            assert result.data["state"] == "completed"

    @pytest.mark.asyncio
    async def test_get_pipeline_run_not_found(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            404,
            {"message": "Run not found"},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.get_pipeline_run(pipeline_id=123, run_id=99999)
            assert result.success is False


class TestCancelPipelineRun:
    """Tests for cancel_pipeline_run method."""

    @pytest.mark.asyncio
    async def test_cancel_pipeline_run_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {"id": 12345, "state": "canceling"},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.cancel_pipeline_run(pipeline_id=123, run_id=12345)
            assert result.success is True


class TestListPipelines:
    """Tests for list_pipelines method."""

    @pytest.mark.asyncio
    async def test_list_pipelines_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "value": [
                    {"id": 1, "name": "Pipeline 1", "folder": "\\", "revision": 5},
                    {
                        "id": 2,
                        "name": "Pipeline 2",
                        "folder": "\\folder",
                        "revision": 3,
                    },
                ]
            },
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.list_pipelines()
            assert result.success is True
            assert result.data["count"] == 2


# =============================================================================
# Work Item Management Tests
# =============================================================================


class TestCreateWorkItem:
    """Tests for create_work_item method."""

    @pytest.mark.asyncio
    async def test_create_work_item_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            201,
            {
                "id": 12345,
                "_links": {
                    "html": {
                        "href": "https://dev.azure.com/org/proj/_workitems/edit/12345"
                    }
                },
            },
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.create_work_item(
                title="Test Task",
                work_item_type=WorkItemType.TASK,
            )
            assert result.success is True
            assert result.data["id"] == 12345

    @pytest.mark.asyncio
    async def test_create_work_item_full_options(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {"id": 12346},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.create_work_item(
                title="Critical Bug",
                work_item_type=WorkItemType.BUG,
                description="<p>Description</p>",
                assigned_to="user@example.com",
                area_path="Project\\Team",
                iteration_path="Sprint 1",
                priority=WorkItemPriority.P1,
                severity=WorkItemSeverity.CRITICAL,
                tags=["security", "urgent"],
                parent_id=100,
                additional_fields={"Custom.Field": "value"},
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_work_item_error(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            400,
            {"message": "Invalid work item type"},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.create_work_item(title="Test")
            assert result.success is False


class TestCreateSecurityBug:
    """Tests for create_security_bug method."""

    @pytest.mark.asyncio
    async def test_create_security_bug_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            201,
            {"id": 12347},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.create_security_bug(
                title="SQL Injection Vulnerability",
                cve_id="CVE-2024-1234",
                severity="HIGH",
                affected_file="src/api/handler.py",
                description="SQL injection in login handler",
                recommendation="Use parameterized queries",
            )
            assert result.success is True

    @pytest.mark.asyncio
    async def test_create_security_bug_critical(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            201,
            {"id": 12348},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.create_security_bug(
                title="RCE Vulnerability",
                severity="CRITICAL",
                approval_url="https://aura.example.com/approve/123",
            )
            assert result.success is True


class TestGetWorkItem:
    """Tests for get_work_item method."""

    @pytest.mark.asyncio
    async def test_get_work_item_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {
                "id": 12345,
                "rev": 5,
                "fields": {
                    "System.WorkItemType": "Bug",
                    "System.Title": "Test Bug",
                    "System.State": "Active",
                    "System.AssignedTo": {"displayName": "John Doe"},
                    "System.AreaPath": "Project\\Team",
                    "System.IterationPath": "Sprint 1",
                },
                "_links": {"html": {"href": "https://dev.azure.com/..."}},
            },
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.get_work_item(12345)
            assert result.success is True
            assert result.data["title"] == "Test Bug"


class TestUpdateWorkItem:
    """Tests for update_work_item method."""

    @pytest.mark.asyncio
    async def test_update_work_item_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {"id": 12345, "rev": 6},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.update_work_item(
                work_item_id=12345,
                updates={"System.State": "Resolved"},
            )
            assert result.success is True


class TestAddWorkItemComment:
    """Tests for add_work_item_comment method."""

    @pytest.mark.asyncio
    async def test_add_comment_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            201,
            {"id": 1, "text": "Test comment"},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.add_work_item_comment(
                work_item_id=12345,
                comment="Test comment",
            )
            assert result.success is True


class TestQueryWorkItems:
    """Tests for query_work_items method."""

    @pytest.mark.asyncio
    async def test_query_work_items_success(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        # Need two responses: query then details
        mock_query_response = MagicMock()
        mock_query_response.status = 200
        mock_query_response.json = AsyncMock(
            return_value={"workItems": [{"id": 1}, {"id": 2}]}
        )

        mock_details_response = MagicMock()
        mock_details_response.status = 200
        mock_details_response.json = AsyncMock(
            return_value={
                "value": [
                    {
                        "id": 1,
                        "fields": {
                            "System.Title": "Item 1",
                            "System.State": "New",
                            "System.WorkItemType": "Task",
                        },
                    },
                    {
                        "id": 2,
                        "fields": {
                            "System.Title": "Item 2",
                            "System.State": "Active",
                            "System.WorkItemType": "Bug",
                        },
                    },
                ]
            }
        )

        mock_ctx1 = MagicMock()
        mock_ctx1.__aenter__ = AsyncMock(return_value=mock_query_response)
        mock_ctx1.__aexit__ = AsyncMock(return_value=None)

        mock_ctx2 = MagicMock()
        mock_ctx2.__aenter__ = AsyncMock(return_value=mock_details_response)
        mock_ctx2.__aexit__ = AsyncMock(return_value=None)

        mock_session_instance = MagicMock()
        mock_session_instance.post.return_value = mock_ctx1
        mock_session_instance.get.return_value = mock_ctx2

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.query_work_items(
                wiql="SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'"
            )
            assert result.success is True
            assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_query_work_items_empty(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(
            200,
            {"workItems": []},
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.query_work_items(
                wiql="SELECT [System.Id] FROM WorkItems WHERE 1=0"
            )
            assert result.success is True
            assert result.data["count"] == 0


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(200, {"value": []})

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.health_check()
            assert result is True
            assert connector._status == ConnectorStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_health_check_auth_failed(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="bad-token",
        )

        mock_session = create_mock_aiohttp_session(401, {"message": "Unauthorized"})

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.AUTH_FAILED

    @pytest.mark.asyncio
    async def test_health_check_project_not_found(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="nonexistent",
            pat="token",
        )

        mock_session = create_mock_aiohttp_session(404, {"message": "Not found"})

        with patch.object(
            connector_module.aiohttp, "ClientSession", return_value=mock_session
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.ERROR

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        with patch.object(
            connector_module.aiohttp,
            "ClientSession",
            side_effect=Exception("Network error"),
        ):
            result = await connector.health_check()
            assert result is False
            assert connector._status == ConnectorStatus.ERROR


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_trigger_pipeline_exception(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        with patch.object(
            connector_module.aiohttp,
            "ClientSession",
            side_effect=Exception("Connection timeout"),
        ):
            result = await connector.trigger_pipeline(pipeline_id=123)
            assert result.success is False
            assert "Connection timeout" in result.error

    @pytest.mark.asyncio
    async def test_get_pipeline_run_exception(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        with patch.object(
            connector_module.aiohttp,
            "ClientSession",
            side_effect=Exception("DNS error"),
        ):
            result = await connector.get_pipeline_run(pipeline_id=123, run_id=456)
            assert result.success is False

    @pytest.mark.asyncio
    async def test_create_work_item_exception(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        with patch.object(
            connector_module.aiohttp,
            "ClientSession",
            side_effect=Exception("SSL error"),
        ):
            result = await connector.create_work_item(title="Test")
            assert result.success is False
            assert connector._status == ConnectorStatus.ERROR

    @pytest.mark.asyncio
    async def test_query_work_items_exception(self, enable_enterprise_mode):
        connector = AzureDevOpsConnector(
            organization="org",
            project="proj",
            pat="token",
        )

        with patch.object(
            connector_module.aiohttp, "ClientSession", side_effect=Exception("Timeout")
        ):
            result = await connector.query_work_items(wiql="SELECT * FROM WorkItems")
            assert result.success is False
