"""Unit tests for Agent Messaging Schemas (Issue #19).

Tests the message dataclasses and serialization for SQS-based
agent-to-agent communication.
"""

import json
from datetime import datetime

from src.agents.messaging import (
    AgentMessage,
    AgentResultMessage,
    AgentTaskMessage,
    MessagePriority,
    MessageType,
)
from src.agents.messaging.schemas import AgentStatusMessage, AgentType


class TestMessageType:
    """Tests for MessageType enum."""

    def test_task_type_value(self) -> None:
        """Test TASK message type value."""
        assert MessageType.TASK.value == "task"

    def test_result_type_value(self) -> None:
        """Test RESULT message type value."""
        assert MessageType.RESULT.value == "result"

    def test_status_type_value(self) -> None:
        """Test STATUS message type value."""
        assert MessageType.STATUS.value == "status"

    def test_cancel_type_value(self) -> None:
        """Test CANCEL message type value."""
        assert MessageType.CANCEL.value == "cancel"


class TestMessagePriority:
    """Tests for MessagePriority enum."""

    def test_low_priority_value(self) -> None:
        """Test LOW priority value."""
        assert MessagePriority.LOW.value == 1

    def test_normal_priority_value(self) -> None:
        """Test NORMAL priority value."""
        assert MessagePriority.NORMAL.value == 5

    def test_high_priority_value(self) -> None:
        """Test HIGH priority value."""
        assert MessagePriority.HIGH.value == 7

    def test_critical_priority_value(self) -> None:
        """Test CRITICAL priority value."""
        assert MessagePriority.CRITICAL.value == 10


class TestAgentType:
    """Tests for AgentType enum."""

    def test_orchestrator_value(self) -> None:
        """Test ORCHESTRATOR value."""
        assert AgentType.ORCHESTRATOR.value == "orchestrator"

    def test_coder_value(self) -> None:
        """Test CODER value."""
        assert AgentType.CODER.value == "coder"

    def test_reviewer_value(self) -> None:
        """Test REVIEWER value."""
        assert AgentType.REVIEWER.value == "reviewer"

    def test_validator_value(self) -> None:
        """Test VALIDATOR value."""
        assert AgentType.VALIDATOR.value == "validator"


class TestAgentMessage:
    """Tests for AgentMessage base class."""

    def test_create_message_with_defaults(self) -> None:
        """Test creating a message with default values."""
        msg = AgentMessage()

        assert msg.message_id is not None  # Auto-generated UUID
        assert msg.task_id == ""
        assert msg.source_agent == ""
        assert msg.target_agent == ""
        assert msg.message_type == MessageType.TASK.value
        assert msg.payload == {}
        assert msg.priority == 5  # NORMAL
        assert msg.retry_count == 0
        assert msg.max_retries == 3

    def test_create_message_with_values(self) -> None:
        """Test creating a message with explicit values."""
        msg = AgentMessage(
            message_id="msg-123",
            task_id="task-456",
            source_agent="orchestrator",
            target_agent="coder",
            message_type=MessageType.TASK.value,
            payload={"key": "value"},
            correlation_id="corr-789",
            priority=7,
        )

        assert msg.message_id == "msg-123"
        assert msg.task_id == "task-456"
        assert msg.source_agent == "orchestrator"
        assert msg.target_agent == "coder"
        assert msg.message_type == MessageType.TASK.value
        assert msg.payload == {"key": "value"}
        assert msg.correlation_id == "corr-789"
        assert msg.priority == 7

    def test_default_timestamp(self) -> None:
        """Test that timestamp is auto-generated."""
        msg = AgentMessage()

        # Timestamp should be an ISO format string
        assert msg.timestamp is not None
        # Should be parseable as ISO format
        datetime.fromisoformat(msg.timestamp.replace("Z", "+00:00"))

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        msg = AgentMessage(
            message_id="msg-123",
            task_id="task-456",
            source_agent="orchestrator",
            target_agent="coder",
        )

        json_str = msg.to_json()
        parsed = json.loads(json_str)

        assert parsed["message_id"] == "msg-123"
        assert parsed["task_id"] == "task-456"

    def test_from_json(self) -> None:
        """Test JSON deserialization."""
        json_str = json.dumps(
            {
                "message_id": "msg-123",
                "task_id": "task-456",
                "source_agent": "orchestrator",
                "target_agent": "coder",
                "message_type": "task",
                "payload": {"key": "value"},
                "correlation_id": "corr-789",
                "timestamp": "2024-01-01T12:00:00Z",
                "priority": 5,
                "retry_count": 1,
                "max_retries": 3,
            }
        )

        msg = AgentMessage.from_json(json_str)

        assert msg.message_id == "msg-123"
        assert msg.task_id == "task-456"
        assert msg.message_type == "task"
        assert msg.payload == {"key": "value"}
        assert msg.retry_count == 1

    def test_to_sqs_message(self) -> None:
        """Test converting to SQS message format."""
        msg = AgentMessage(
            message_id="msg-123",
            task_id="task-456",
            source_agent="orchestrator",
            target_agent="coder",
            correlation_id="corr-789",
            priority=7,
        )

        sqs_msg = msg.to_sqs_message()

        assert "MessageBody" in sqs_msg
        assert "MessageAttributes" in sqs_msg
        assert sqs_msg["MessageAttributes"]["TargetAgent"]["StringValue"] == "coder"
        assert sqs_msg["MessageAttributes"]["Priority"]["StringValue"] == "7"

    def test_increment_retry(self) -> None:
        """Test incrementing retry count."""
        msg = AgentMessage(retry_count=1, max_retries=3)
        new_msg = msg.increment_retry()

        assert new_msg.retry_count == 2
        assert msg.retry_count == 1  # Original unchanged

    def test_should_retry(self) -> None:
        """Test should_retry check."""
        msg1 = AgentMessage(retry_count=0, max_retries=3)
        msg2 = AgentMessage(retry_count=3, max_retries=3)

        assert msg1.should_retry() is True
        assert msg2.should_retry() is False


class TestAgentTaskMessage:
    """Tests for AgentTaskMessage."""

    def test_create_task_message(self) -> None:
        """Test creating a task message."""
        msg = AgentTaskMessage(
            message_id="msg-123",
            task_id="task-456",
            source_agent="orchestrator",
            target_agent="coder",
            correlation_id="corr-789",
            context={"code": "def hello(): pass"},
            timeout_seconds=600,
            autonomy_level="standard",
        )

        assert msg.context == {"code": "def hello(): pass"}
        assert msg.timeout_seconds == 600
        assert msg.autonomy_level == "standard"
        # message_type is set in __post_init__
        assert msg.message_type == MessageType.TASK.value

    def test_default_values(self) -> None:
        """Test default values for task message."""
        msg = AgentTaskMessage()

        assert msg.timeout_seconds == 300  # 5 minutes default
        assert msg.autonomy_level == "critical_hitl"
        assert msg.context == {}
        assert msg.dependencies == []
        assert msg.metadata == {}

    def test_create_factory_method(self) -> None:
        """Test create factory method."""
        msg = AgentTaskMessage.create(
            task_id="task-123",
            target_agent="coder",
            task_description="Generate authentication code",
            context={"existing_code": "..."},
            priority=MessagePriority.HIGH.value,
        )

        assert msg.task_id == "task-123"
        assert msg.target_agent == "coder"
        assert msg.task_description == "Generate authentication code"
        assert msg.source_agent == "orchestrator"
        assert msg.priority == 7

    def test_task_message_from_json(self) -> None:
        """Test deserializing task message from JSON."""
        json_str = json.dumps(
            {
                "message_id": "msg-123",
                "task_id": "task-456",
                "source_agent": "orchestrator",
                "target_agent": "coder",
                "message_type": "task",
                "payload": {},
                "correlation_id": "corr-789",
                "timestamp": "2024-01-01T12:00:00Z",
                "priority": 5,
                "retry_count": 0,
                "max_retries": 3,
                "context": {"code": "test"},
                "timeout_seconds": 600,
                "autonomy_level": "standard",
                "task_description": "Test task",
                "dependencies": [],
                "metadata": {},
            }
        )

        msg = AgentTaskMessage.from_json(json_str)

        assert isinstance(msg, AgentTaskMessage)
        assert msg.task_id == "task-456"
        assert msg.context == {"code": "test"}


class TestAgentResultMessage:
    """Tests for AgentResultMessage."""

    def test_create_success_result(self) -> None:
        """Test creating a successful result message."""
        msg = AgentResultMessage(
            message_id="msg-123",
            task_id="task-456",
            source_agent="coder",
            target_agent="orchestrator",
            correlation_id="corr-789",
            success=True,
            data={"code": "def secure(): pass"},
            execution_time_ms=150.5,
            tokens_used=1500,
        )

        assert msg.success is True
        assert msg.data == {"code": "def secure(): pass"}
        assert msg.error is None
        assert msg.execution_time_ms == 150.5
        assert msg.tokens_used == 1500
        assert msg.message_type == MessageType.RESULT.value

    def test_create_failure_result(self) -> None:
        """Test creating a failure result message."""
        msg = AgentResultMessage(
            message_id="msg-123",
            task_id="task-456",
            source_agent="coder",
            target_agent="orchestrator",
            correlation_id="corr-789",
            success=False,
            error="LLM timeout",
            execution_time_ms=30000.0,
        )

        assert msg.success is False
        assert msg.error == "LLM timeout"

    def test_create_success_factory(self) -> None:
        """Test create_success factory method."""
        msg = AgentResultMessage.create_success(
            task_id="task-456",
            source_agent="coder",
            correlation_id="corr-789",
            data={"code": "result"},
            execution_time_ms=100.0,
            tokens_used=500,
        )

        assert msg.success is True
        assert msg.task_id == "task-456"
        assert msg.source_agent == "coder"
        assert msg.target_agent == "orchestrator"
        assert msg.data == {"code": "result"}
        assert msg.error is None

    def test_create_failure_factory(self) -> None:
        """Test create_failure factory method."""
        msg = AgentResultMessage.create_failure(
            task_id="task-456",
            source_agent="reviewer",
            correlation_id="corr-789",
            error="Security vulnerability detected",
            execution_time_ms=50.0,
        )

        assert msg.success is False
        assert msg.task_id == "task-456"
        assert msg.error == "Security vulnerability detected"

    def test_default_values(self) -> None:
        """Test default values for result message."""
        msg = AgentResultMessage()

        assert msg.success is True
        assert msg.data == {}
        assert msg.error is None
        assert msg.execution_time_ms == 0.0
        assert msg.tokens_used == 0
        assert msg.cost_usd == 0.0
        assert msg.tools_invoked == []
        assert msg.requires_remediation is False


class TestAgentStatusMessage:
    """Tests for AgentStatusMessage."""

    def test_create_status_message(self) -> None:
        """Test creating a status message."""
        msg = AgentStatusMessage(
            message_id="msg-123",
            task_id="task-456",
            source_agent="coder",
            target_agent="orchestrator",
            correlation_id="corr-789",
            status="processing",
            progress_percent=50,
            current_step="Generating code",
            estimated_remaining_seconds=30,
        )

        assert msg.status == "processing"
        assert msg.progress_percent == 50
        assert msg.current_step == "Generating code"
        assert msg.estimated_remaining_seconds == 30
        assert msg.message_type == MessageType.STATUS.value

    def test_default_values(self) -> None:
        """Test default values for status message."""
        msg = AgentStatusMessage()

        assert msg.status == "running"
        assert msg.progress_percent == 0
        assert msg.current_step == ""
        assert msg.estimated_remaining_seconds is None


class TestMessageRoundTrip:
    """Integration tests for message serialization round-trips."""

    def test_task_message_round_trip(self) -> None:
        """Test task message JSON round-trip."""
        original = AgentTaskMessage.create(
            task_id="task-456",
            target_agent="coder",
            task_description="Generate code",
            context={"items": [{"content": "test"}]},
            timeout_seconds=900,
            autonomy_level="full_autonomous",
            priority=MessagePriority.HIGH.value,
        )

        json_str = original.to_json()
        restored = AgentTaskMessage.from_json(json_str)

        assert restored.message_id == original.message_id
        assert restored.task_id == original.task_id
        assert restored.context == original.context
        assert restored.timeout_seconds == original.timeout_seconds

    def test_result_message_round_trip(self) -> None:
        """Test result message JSON round-trip."""
        original = AgentResultMessage.create_success(
            task_id="task-456",
            source_agent="coder",
            correlation_id="corr-789",
            data={"code": "def test(): pass", "metrics": {"lines": 10}},
            execution_time_ms=250.5,
            tokens_used=2000,
        )

        json_str = original.to_json()
        restored = AgentResultMessage.from_json(json_str)

        assert restored.success is True
        assert restored.data == original.data
        assert restored.execution_time_ms == original.execution_time_ms
        assert restored.tokens_used == original.tokens_used

    def test_status_message_round_trip(self) -> None:
        """Test status message JSON round-trip."""
        original = AgentStatusMessage(
            task_id="task-123",
            source_agent="validator",
            target_agent="orchestrator",
            status="processing",
            progress_percent=75,
            current_step="Running tests",
        )

        json_str = original.to_json()
        restored = AgentStatusMessage.from_json(json_str)

        assert restored.status == original.status
        assert restored.progress_percent == original.progress_percent
        assert restored.current_step == original.current_step
