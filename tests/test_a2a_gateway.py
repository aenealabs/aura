"""
Project Aura - A2A Gateway Tests

Tests for the Agent-to-Agent protocol gateway that enables
cross-platform agent interoperability.
"""

import sys
from unittest.mock import MagicMock

# =============================================================================
# Save original modules before mocking to prevent test pollution
# =============================================================================
_original_src_config = sys.modules.get("src.config")
_original_a2a_gateway = sys.modules.get("src.services.a2a_gateway")

# Mock the config module
mock_config = MagicMock()
mock_config.get_integration_config = MagicMock(
    return_value=MagicMock(
        is_defense_mode=False,
        a2a_enabled=True,
    )
)
mock_config.IntegrationConfig = MagicMock


# Create require_enterprise_mode decorator that just passes through
# NOTE: This MUST be a real function that returns the decorated function,
# NOT a MagicMock(return_value=True), which would replace decorated methods
# with the boolean True instead of a callable wrapper.
def _mock_require_enterprise_mode(func):
    """Mock decorator that just passes through."""
    return func


mock_config.require_enterprise_mode = _mock_require_enterprise_mode

sys.modules["src.config"] = mock_config

from src.services.a2a_gateway import (
    A2A_JSON_RPC_VERSION,
    A2A_PROTOCOL_VERSION,
    A2AMessageType,
    A2ARequest,
    A2AResponse,
    A2ATask,
    AgentCapability,
    AgentCard,
    ArtifactType,
    TaskArtifact,
    TaskStatus,
)

# Restore original modules to prevent pollution of other tests
if _original_src_config is not None:
    sys.modules["src.config"] = _original_src_config
else:
    sys.modules.pop("src.config", None)

if _original_a2a_gateway is not None:
    sys.modules["src.services.a2a_gateway"] = _original_a2a_gateway


class TestA2AConstants:
    """Tests for A2A protocol constants."""

    def test_protocol_version(self):
        """Test protocol version."""
        assert A2A_PROTOCOL_VERSION == "1.0"

    def test_json_rpc_version(self):
        """Test JSON-RPC version."""
        assert A2A_JSON_RPC_VERSION == "2.0"


class TestA2AMessageType:
    """Tests for A2AMessageType enum."""

    def test_agent_card_request(self):
        """Test agent card request type."""
        assert A2AMessageType.AGENT_CARD_REQUEST.value == "agent_card_request"

    def test_agent_card_response(self):
        """Test agent card response type."""
        assert A2AMessageType.AGENT_CARD_RESPONSE.value == "agent_card_response"

    def test_task_send(self):
        """Test task send type."""
        assert A2AMessageType.TASK_SEND.value == "tasks/send"

    def test_task_send_subscribe(self):
        """Test task send subscribe type."""
        assert A2AMessageType.TASK_SEND_SUBSCRIBE.value == "tasks/sendSubscribe"

    def test_task_get(self):
        """Test task get type."""
        assert A2AMessageType.TASK_GET.value == "tasks/get"

    def test_task_cancel(self):
        """Test task cancel type."""
        assert A2AMessageType.TASK_CANCEL.value == "tasks/cancel"

    def test_push_notification_set(self):
        """Test push notification set type."""
        assert (
            A2AMessageType.PUSH_NOTIFICATION_SET.value == "tasks/pushNotification/set"
        )


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_submitted_status(self):
        """Test submitted status."""
        assert TaskStatus.SUBMITTED.value == "submitted"

    def test_working_status(self):
        """Test working status."""
        assert TaskStatus.WORKING.value == "working"

    def test_input_required_status(self):
        """Test input required status."""
        assert TaskStatus.INPUT_REQUIRED.value == "input_required"

    def test_completed_status(self):
        """Test completed status."""
        assert TaskStatus.COMPLETED.value == "completed"

    def test_failed_status(self):
        """Test failed status."""
        assert TaskStatus.FAILED.value == "failed"

    def test_canceled_status(self):
        """Test canceled status."""
        assert TaskStatus.CANCELED.value == "canceled"

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        statuses = list(TaskStatus)
        assert len(statuses) == 6


class TestArtifactType:
    """Tests for ArtifactType enum."""

    def test_text_type(self):
        """Test text type."""
        assert ArtifactType.TEXT.value == "text"

    def test_code_type(self):
        """Test code type."""
        assert ArtifactType.CODE.value == "code"

    def test_file_type(self):
        """Test file type."""
        assert ArtifactType.FILE.value == "file"

    def test_json_type(self):
        """Test json type."""
        assert ArtifactType.JSON.value == "json"

    def test_patch_type(self):
        """Test patch type."""
        assert ArtifactType.PATCH.value == "patch"

    def test_report_type(self):
        """Test report type."""
        assert ArtifactType.REPORT.value == "report"


class TestAgentCapability:
    """Tests for AgentCapability dataclass."""

    def test_minimal_capability(self):
        """Test minimal capability creation."""
        cap = AgentCapability(
            name="analyze_code",
            description="Analyzes code for vulnerabilities",
        )
        assert cap.name == "analyze_code"
        assert cap.description == "Analyzes code for vulnerabilities"
        assert cap.input_schema == {}
        assert cap.output_schema == {}
        assert cap.streaming_supported is False
        assert cap.requires_authentication is True
        assert cap.rate_limit_per_minute == 60

    def test_full_capability(self):
        """Test full capability creation."""
        cap = AgentCapability(
            name="generate_patch",
            description="Generates security patches",
            input_schema={"type": "object", "properties": {"code": {"type": "string"}}},
            output_schema={
                "type": "object",
                "properties": {"patch": {"type": "string"}},
            },
            streaming_supported=True,
            requires_authentication=True,
            rate_limit_per_minute=30,
        )
        assert cap.streaming_supported is True
        assert cap.rate_limit_per_minute == 30
        assert "properties" in cap.input_schema

    def test_capability_no_auth(self):
        """Test capability without authentication requirement."""
        cap = AgentCapability(
            name="public_api",
            description="Public API",
            requires_authentication=False,
        )
        assert cap.requires_authentication is False


class TestAgentCard:
    """Tests for AgentCard dataclass."""

    def test_minimal_agent_card(self):
        """Test minimal agent card creation."""
        card = AgentCard(
            agent_id="test-agent",
            name="Test Agent",
            description="A test agent",
        )
        assert card.agent_id == "test-agent"
        assert card.name == "Test Agent"
        assert card.protocol_version == "1.0"
        assert card.provider == "aenealabs"
        assert card.capabilities == []
        assert card.authentication_type == "oauth2"

    def test_agent_card_with_capabilities(self):
        """Test agent card with capabilities."""
        cap = AgentCapability(
            name="analyze",
            description="Analyze code",
        )
        card = AgentCard(
            agent_id="analyzer",
            name="Analyzer",
            description="Code analyzer",
            capabilities=[cap],
        )
        assert len(card.capabilities) == 1
        assert card.capabilities[0].name == "analyze"

    def test_agent_card_to_dict(self):
        """Test agent card to_dict conversion."""
        card = AgentCard(
            agent_id="dict-agent",
            name="Dict Agent",
            description="For testing to_dict",
            endpoint="https://api.example.com/a2a",
        )
        data = card.to_dict()
        assert data["agent_id"] == "dict-agent"
        assert data["name"] == "Dict Agent"
        assert data["endpoint"] == "https://api.example.com/a2a"
        assert "authentication" in data
        assert data["authentication"]["type"] == "oauth2"

    def test_agent_card_oauth_scopes(self):
        """Test agent card with OAuth scopes."""
        card = AgentCard(
            agent_id="scoped-agent",
            name="Scoped Agent",
            description="Has OAuth scopes",
            oauth_scopes=["read", "write"],
        )
        assert card.oauth_scopes == ["read", "write"]

    def test_agent_card_contact_info(self):
        """Test agent card with contact info."""
        card = AgentCard(
            agent_id="support-agent",
            name="Support Agent",
            description="Has contact info",
            documentation_url="https://docs.example.com",
            support_email="support@example.com",
        )
        assert card.documentation_url == "https://docs.example.com"
        assert card.support_email == "support@example.com"


class TestTaskArtifact:
    """Tests for TaskArtifact dataclass."""

    def test_minimal_artifact(self):
        """Test minimal artifact creation."""
        artifact = TaskArtifact()
        assert artifact.artifact_id is not None
        assert artifact.artifact_type == ArtifactType.TEXT
        assert artifact.mime_type == "text/plain"

    def test_code_artifact(self):
        """Test code artifact creation."""
        artifact = TaskArtifact(
            artifact_type=ArtifactType.CODE,
            name="fix.py",
            description="Security fix",
            content="def fixed_function(): pass",
            mime_type="text/x-python",
        )
        assert artifact.artifact_type == ArtifactType.CODE
        assert artifact.name == "fix.py"
        assert "fixed_function" in artifact.content

    def test_artifact_with_metadata(self):
        """Test artifact with metadata."""
        artifact = TaskArtifact(
            artifact_type=ArtifactType.PATCH,
            metadata={"line_count": 10, "files_changed": 1},
        )
        assert artifact.metadata["line_count"] == 10

    def test_artifact_to_dict(self):
        """Test artifact to_dict conversion."""
        artifact = TaskArtifact(
            artifact_type=ArtifactType.REPORT,
            name="security_report.json",
            content='{"issues": []}',
        )
        data = artifact.to_dict()
        assert data["type"] == "report"
        assert data["name"] == "security_report.json"
        assert "created_at" in data


class TestA2ATask:
    """Tests for A2ATask dataclass."""

    def test_minimal_task(self):
        """Test minimal task creation."""
        task = A2ATask()
        assert task.task_id is not None
        assert task.status == TaskStatus.SUBMITTED
        assert task.artifacts == []

    def test_task_with_details(self):
        """Test task with details."""
        task = A2ATask(
            capability_name="analyze_code",
            input_data={"code": "def foo(): pass"},
            session_id="session-123",
        )
        assert task.capability_name == "analyze_code"
        assert task.input_data["code"] == "def foo(): pass"
        assert task.session_id == "session-123"

    def test_task_with_output(self):
        """Test task with output."""
        task = A2ATask(
            status=TaskStatus.COMPLETED,
            output_data={"result": "success"},
            status_message="Analysis complete",
        )
        assert task.status == TaskStatus.COMPLETED
        assert task.output_data["result"] == "success"

    def test_task_with_artifacts(self):
        """Test task with artifacts."""
        artifact = TaskArtifact(
            artifact_type=ArtifactType.CODE,
            content="fix code",
        )
        task = A2ATask(
            artifacts=[artifact],
        )
        assert len(task.artifacts) == 1

    def test_task_to_dict(self):
        """Test task to_dict conversion."""
        task = A2ATask(
            capability_name="test",
            status=TaskStatus.WORKING,
        )
        data = task.to_dict()
        assert data["capability_name"] == "test"
        assert data["status"] == "working"
        assert "task_id" in data

    def test_task_push_notification(self):
        """Test task with push notification."""
        task = A2ATask(
            push_notification_url="https://callback.example.com/notify",
        )
        assert task.push_notification_url == "https://callback.example.com/notify"

    def test_task_requester_info(self):
        """Test task with requester info."""
        task = A2ATask(
            requester_agent_id="external-agent",
            requester_endpoint="https://external.example.com/a2a",
        )
        assert task.requester_agent_id == "external-agent"


class TestA2ARequest:
    """Tests for A2ARequest dataclass."""

    def test_minimal_request(self):
        """Test minimal request creation."""
        request = A2ARequest(method="tasks/send")
        assert request.method == "tasks/send"
        assert request.jsonrpc == "2.0"
        assert request.id is not None

    def test_request_with_params(self):
        """Test request with params."""
        request = A2ARequest(
            method="tasks/send",
            params={"capability": "analyze", "input": {"code": "test"}},
        )
        assert request.params["capability"] == "analyze"

    def test_request_to_dict(self):
        """Test request to_dict conversion."""
        request = A2ARequest(
            method="tasks/get",
            params={"task_id": "123"},
            id="req-456",
        )
        data = request.to_dict()
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "tasks/get"
        assert data["params"]["task_id"] == "123"
        assert data["id"] == "req-456"


class TestA2AResponse:
    """Tests for A2AResponse dataclass."""

    def test_success_response(self):
        """Test success response."""
        response = A2AResponse(
            id="req-123",
            result={"status": "completed"},
        )
        assert response.is_success is True
        assert response.result["status"] == "completed"
        assert response.error is None

    def test_error_response(self):
        """Test error response."""
        response = A2AResponse(
            id="req-456",
            error={"code": -32600, "message": "Invalid request"},
        )
        assert response.is_success is False
        assert response.error["code"] == -32600

    def test_response_to_dict_success(self):
        """Test success response to_dict."""
        response = A2AResponse(
            id="req-789",
            result={"data": "test"},
        )
        data = response.to_dict()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "req-789"
        assert "result" in data
        assert "error" not in data

    def test_response_to_dict_error(self):
        """Test error response to_dict."""
        response = A2AResponse(
            id="req-error",
            error={"code": -32601, "message": "Method not found"},
        )
        data = response.to_dict()
        assert "error" in data
        assert data["error"]["code"] == -32601


class TestA2AGatewayInitialization:
    """Tests for A2AGateway initialization."""

    def test_defense_mode_raises_error(self):
        """Test that defense mode raises error."""
        # This would need to test actual gateway initialization
        # which requires more complex mocking

    def test_a2a_disabled_warning(self):
        """Test warning when A2A disabled."""
        # This would need to test actual gateway initialization


class TestTaskStatusTransitions:
    """Tests for task status transitions."""

    def test_valid_transitions(self):
        """Test valid status transition sequences."""
        # submitted -> working
        task = A2ATask(status=TaskStatus.SUBMITTED)
        task.status = TaskStatus.WORKING
        assert task.status == TaskStatus.WORKING

        # working -> completed
        task.status = TaskStatus.COMPLETED
        assert task.status == TaskStatus.COMPLETED

    def test_failed_status(self):
        """Test transition to failed."""
        task = A2ATask(status=TaskStatus.WORKING)
        task.status = TaskStatus.FAILED
        assert task.status == TaskStatus.FAILED

    def test_canceled_status(self):
        """Test transition to canceled."""
        task = A2ATask(status=TaskStatus.SUBMITTED)
        task.status = TaskStatus.CANCELED
        assert task.status == TaskStatus.CANCELED


class TestAgentCardCapabilities:
    """Tests for agent card capability handling."""

    def test_multiple_capabilities(self):
        """Test card with multiple capabilities."""
        caps = [
            AgentCapability(name="analyze", description="Analyze"),
            AgentCapability(name="patch", description="Patch"),
            AgentCapability(name="validate", description="Validate"),
        ]
        card = AgentCard(
            agent_id="multi-cap",
            name="Multi Capability Agent",
            description="Has multiple capabilities",
            capabilities=caps,
        )
        assert len(card.capabilities) == 3

    def test_capabilities_to_dict(self):
        """Test capabilities in to_dict."""
        cap = AgentCapability(
            name="test_cap",
            description="Test capability",
            streaming_supported=True,
        )
        card = AgentCard(
            agent_id="cap-dict",
            name="Cap Dict Agent",
            description="For testing",
            capabilities=[cap],
        )
        data = card.to_dict()
        assert len(data["capabilities"]) == 1
        assert data["capabilities"][0]["name"] == "test_cap"
        assert data["capabilities"][0]["streaming_supported"] is True
