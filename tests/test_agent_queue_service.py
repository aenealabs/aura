"""Unit tests for Agent Queue Service (Issue #19).

Tests the SQS-based queue service for agent-to-agent messaging.
Uses mocking for AWS SQS calls.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.agents.messaging import AgentResultMessage, AgentTaskMessage, MessagePriority
from src.services.agent_queue_service import AgentQueueService, QueueConfig


class TestQueueConfig:
    """Tests for QueueConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = QueueConfig()

        assert config.coder_queue_url == ""
        assert config.reviewer_queue_url == ""
        assert config.validator_queue_url == ""
        assert config.responses_queue_url == ""
        assert config.region == "us-east-1"
        assert config.max_receive_count == 10
        assert config.visibility_timeout == 300
        assert config.wait_time_seconds == 20
        assert config.publish_events is True

    def test_config_with_env_vars(self) -> None:
        """Test config reads from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "CODER_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/coder",
                "AWS_DEFAULT_REGION": "us-west-2",
            },
        ):
            config = QueueConfig()

            assert (
                config.coder_queue_url
                == "https://sqs.us-east-1.amazonaws.com/123/coder"
            )
            assert config.region == "us-west-2"


class TestAgentQueueServiceInit:
    """Tests for AgentQueueService initialization."""

    def test_init_with_default_config(self) -> None:
        """Test initialization with default config."""
        service = AgentQueueService()

        assert service.config is not None
        assert service.config.visibility_timeout == 300

    def test_init_with_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = QueueConfig(
            coder_queue_url="https://custom-coder-queue",
            reviewer_queue_url="https://custom-reviewer-queue",
            validator_queue_url="https://custom-validator-queue",
            responses_queue_url="https://custom-responses-queue",
        )

        service = AgentQueueService(config=config)

        assert service._queue_urls["coder"] == "https://custom-coder-queue"
        assert service._queue_urls["reviewer"] == "https://custom-reviewer-queue"

    def test_get_queue_url_valid(self) -> None:
        """Test getting queue URL for valid agent type."""
        config = QueueConfig(coder_queue_url="https://coder-queue")
        service = AgentQueueService(config=config)

        url = service._get_queue_url("coder")

        assert url == "https://coder-queue"

    def test_get_queue_url_invalid(self) -> None:
        """Test getting queue URL for invalid agent type raises error."""
        service = AgentQueueService()

        with pytest.raises(ValueError, match="Unknown agent type"):
            service._get_queue_url("invalid")


class TestSendTask:
    """Tests for send_task method."""

    @pytest.fixture
    def mock_sqs_client(self) -> MagicMock:
        """Create a mock SQS client."""
        client = MagicMock()
        client.send_message.return_value = {"MessageId": "msg-id-123"}
        return client

    @pytest.fixture
    def queue_service(self, mock_sqs_client: MagicMock) -> AgentQueueService:
        """Create queue service with mocked SQS client."""
        config = QueueConfig(
            coder_queue_url="https://test-coder-queue",
            reviewer_queue_url="https://test-reviewer-queue",
            validator_queue_url="https://test-validator-queue",
            responses_queue_url="https://test-responses-queue",
            publish_events=False,  # Disable EventBridge for tests
        )
        service = AgentQueueService(config=config)
        service._sqs_client = mock_sqs_client
        return service

    @pytest.mark.asyncio
    async def test_send_task_to_coder(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test sending a task to the coder queue."""
        task_message = AgentTaskMessage.create(
            task_id="task-456",
            target_agent="coder",
            task_description="Generate code",
            context={"code": "test"},
            priority=MessagePriority.HIGH.value,
        )

        message_id = await queue_service.send_task("coder", task_message)

        assert message_id == "msg-id-123"
        mock_sqs_client.send_message.assert_called_once()

        call_args = mock_sqs_client.send_message.call_args
        assert call_args.kwargs["QueueUrl"] == "https://test-coder-queue"
        assert "MessageBody" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_send_task_with_delay(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test sending a task with delay."""
        task_message = AgentTaskMessage.create(
            task_id="task-456",
            target_agent="reviewer",
            task_description="Review code",
        )

        await queue_service.send_task("reviewer", task_message, delay_seconds=60)

        call_args = mock_sqs_client.send_message.call_args
        assert call_args.kwargs.get("DelaySeconds") == 60

    @pytest.mark.asyncio
    async def test_send_task_invalid_agent_type(
        self, queue_service: AgentQueueService
    ) -> None:
        """Test sending to invalid agent type raises error."""
        task_message = AgentTaskMessage.create(
            task_id="task-456",
            target_agent="invalid",
            task_description="Test",
        )

        with pytest.raises(ValueError, match="Unknown agent type"):
            await queue_service.send_task("invalid", task_message)


class TestSendResult:
    """Tests for send_result method."""

    @pytest.fixture
    def mock_sqs_client(self) -> MagicMock:
        """Create a mock SQS client."""
        client = MagicMock()
        client.send_message.return_value = {"MessageId": "result-msg-123"}
        return client

    @pytest.fixture
    def queue_service(self, mock_sqs_client: MagicMock) -> AgentQueueService:
        """Create queue service with mocked SQS client."""
        config = QueueConfig(
            coder_queue_url="https://test-coder-queue",
            responses_queue_url="https://test-responses-queue",
            publish_events=False,
        )
        service = AgentQueueService(config=config)
        service._sqs_client = mock_sqs_client
        return service

    @pytest.mark.asyncio
    async def test_send_success_result(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test sending a successful result."""
        result_message = AgentResultMessage.create_success(
            task_id="task-456",
            source_agent="coder",
            correlation_id="corr-789",
            data={"code": "def test(): pass"},
            execution_time_ms=150.0,
            tokens_used=1000,
        )

        message_id = await queue_service.send_result(result_message)

        assert message_id == "result-msg-123"
        mock_sqs_client.send_message.assert_called_once()

        call_args = mock_sqs_client.send_message.call_args
        assert call_args.kwargs["QueueUrl"] == "https://test-responses-queue"

    @pytest.mark.asyncio
    async def test_send_failure_result(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test sending a failure result."""
        result_message = AgentResultMessage.create_failure(
            task_id="task-456",
            source_agent="reviewer",
            correlation_id="corr-789",
            error="Security vulnerability detected",
            execution_time_ms=50.0,
        )

        message_id = await queue_service.send_result(result_message)

        assert message_id == "result-msg-123"


class TestReceiveTasks:
    """Tests for receive_tasks method."""

    @pytest.fixture
    def mock_sqs_client(self) -> MagicMock:
        """Create a mock SQS client with messages."""
        client = MagicMock()
        client.receive_message.return_value = {
            "Messages": [
                {
                    "MessageId": "msg-1",
                    "ReceiptHandle": "receipt-1",
                    "Body": json.dumps(
                        {
                            "message_id": "msg-1",
                            "task_id": "task-1",
                            "source_agent": "orchestrator",
                            "target_agent": "coder",
                            "message_type": "task",
                            "payload": {},
                            "correlation_id": "corr-1",
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
                    ),
                }
            ]
        }
        return client

    @pytest.fixture
    def queue_service(self, mock_sqs_client: MagicMock) -> AgentQueueService:
        """Create queue service with mocked SQS client."""
        config = QueueConfig(
            coder_queue_url="https://test-coder-queue",
            responses_queue_url="https://test-responses-queue",
        )
        service = AgentQueueService(config=config)
        service._sqs_client = mock_sqs_client
        return service

    @pytest.mark.asyncio
    async def test_receive_tasks_from_queue(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test receiving tasks from agent queue."""
        messages = await queue_service.receive_tasks("coder", max_messages=1)

        assert len(messages) == 1
        msg, receipt_handle = messages[0]
        assert isinstance(msg, AgentTaskMessage)
        assert msg.task_id == "task-1"
        assert receipt_handle == "receipt-1"

        mock_sqs_client.receive_message.assert_called_once()
        call_args = mock_sqs_client.receive_message.call_args
        assert call_args.kwargs["QueueUrl"] == "https://test-coder-queue"

    @pytest.mark.asyncio
    async def test_receive_tasks_empty_queue(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test receiving from empty queue returns empty list."""
        mock_sqs_client.receive_message.return_value = {}

        messages = await queue_service.receive_tasks("coder")

        assert messages == []


class TestReceiveResponses:
    """Tests for receive_responses method."""

    @pytest.fixture
    def mock_sqs_client(self) -> MagicMock:
        """Create a mock SQS client with result messages."""
        client = MagicMock()
        client.receive_message.return_value = {
            "Messages": [
                {
                    "MessageId": "result-1",
                    "ReceiptHandle": "receipt-1",
                    "Body": json.dumps(
                        {
                            "message_id": "result-1",
                            "task_id": "task-1",
                            "source_agent": "coder",
                            "target_agent": "orchestrator",
                            "message_type": "result",
                            "payload": {},
                            "correlation_id": "corr-1",
                            "timestamp": "2024-01-01T12:00:00Z",
                            "priority": 5,
                            "retry_count": 0,
                            "max_retries": 3,
                            "success": True,
                            "data": {"code": "generated"},
                            "error": None,
                            "execution_time_ms": 150.0,
                            "tokens_used": 1000,
                            "cost_usd": 0.01,
                            "tools_invoked": [],
                            "requires_remediation": False,
                            "remediation_details": {},
                        }
                    ),
                }
            ]
        }
        return client

    @pytest.fixture
    def queue_service(self, mock_sqs_client: MagicMock) -> AgentQueueService:
        """Create queue service with mocked SQS client."""
        config = QueueConfig(
            coder_queue_url="https://test-coder-queue",
            responses_queue_url="https://test-responses-queue",
        )
        service = AgentQueueService(config=config)
        service._sqs_client = mock_sqs_client
        return service

    @pytest.mark.asyncio
    async def test_receive_responses(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test receiving responses from queue."""
        messages = await queue_service.receive_responses(max_messages=1)

        assert len(messages) == 1
        msg, receipt_handle = messages[0]
        assert isinstance(msg, AgentResultMessage)
        assert msg.task_id == "task-1"
        assert msg.success is True
        assert receipt_handle == "receipt-1"


class TestMessageAcknowledgment:
    """Tests for ack_message and nack_message methods."""

    @pytest.fixture
    def mock_sqs_client(self) -> MagicMock:
        """Create a mock SQS client."""
        return MagicMock()

    @pytest.fixture
    def queue_service(self, mock_sqs_client: MagicMock) -> AgentQueueService:
        """Create queue service with mocked SQS client."""
        config = QueueConfig(
            coder_queue_url="https://test-coder-queue",
            responses_queue_url="https://test-responses-queue",
        )
        service = AgentQueueService(config=config)
        service._sqs_client = mock_sqs_client
        return service

    @pytest.mark.asyncio
    async def test_ack_message(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test acknowledging (deleting) a message."""
        await queue_service.ack_message("coder", "receipt-handle-123")

        mock_sqs_client.delete_message.assert_called_once_with(
            QueueUrl="https://test-coder-queue",
            ReceiptHandle="receipt-handle-123",
        )

    @pytest.mark.asyncio
    async def test_nack_message(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test making message visible again for retry."""
        await queue_service.nack_message(
            "coder", "receipt-handle-123", visibility_timeout=0
        )

        mock_sqs_client.change_message_visibility.assert_called_once_with(
            QueueUrl="https://test-coder-queue",
            ReceiptHandle="receipt-handle-123",
            VisibilityTimeout=0,
        )


class TestBatchOperations:
    """Tests for batch send operations."""

    @pytest.fixture
    def mock_sqs_client(self) -> MagicMock:
        """Create a mock SQS client."""
        client = MagicMock()
        client.send_message_batch.return_value = {
            "Successful": [
                {"Id": "0", "MessageId": "msg-0"},
                {"Id": "1", "MessageId": "msg-1"},
            ],
            "Failed": [],
        }
        return client

    @pytest.fixture
    def queue_service(self, mock_sqs_client: MagicMock) -> AgentQueueService:
        """Create queue service with mocked SQS client."""
        config = QueueConfig(
            coder_queue_url="https://test-coder-queue",
            responses_queue_url="https://test-responses-queue",
            publish_events=False,
        )
        service = AgentQueueService(config=config)
        service._sqs_client = mock_sqs_client
        return service

    @pytest.mark.asyncio
    async def test_send_batch(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test sending batch of messages."""
        messages = [
            AgentTaskMessage.create(
                task_id=f"task-{i}",
                target_agent="coder",
                task_description=f"Task {i}",
            )
            for i in range(2)
        ]

        result = await queue_service.send_batch("coder", messages)

        assert len(result) == 2
        mock_sqs_client.send_message_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_batch_exceeds_limit(
        self, queue_service: AgentQueueService
    ) -> None:
        """Test batch send with more than 10 messages raises error."""
        messages = [
            AgentTaskMessage.create(
                task_id=f"task-{i}",
                target_agent="coder",
                task_description=f"Task {i}",
            )
            for i in range(11)
        ]

        with pytest.raises(ValueError, match="SQS batch limit is 10 messages"):
            await queue_service.send_batch("coder", messages)


class TestQueueMonitoring:
    """Tests for queue monitoring methods."""

    @pytest.fixture
    def mock_sqs_client(self) -> MagicMock:
        """Create a mock SQS client with queue attributes."""
        client = MagicMock()
        client.get_queue_attributes.return_value = {
            "Attributes": {
                "ApproximateNumberOfMessages": "5",
            }
        }
        return client

    @pytest.fixture
    def queue_service(self, mock_sqs_client: MagicMock) -> AgentQueueService:
        """Create queue service with mocked SQS client."""
        config = QueueConfig(
            coder_queue_url="https://test-coder-queue",
            responses_queue_url="https://test-responses-queue",
        )
        service = AgentQueueService(config=config)
        service._sqs_client = mock_sqs_client
        return service

    @pytest.mark.asyncio
    async def test_get_queue_depth(
        self, queue_service: AgentQueueService, mock_sqs_client: MagicMock
    ) -> None:
        """Test getting queue depth."""
        depth = await queue_service.get_queue_depth("coder")

        assert depth == 5
        mock_sqs_client.get_queue_attributes.assert_called_once()


class TestCreateQueueServiceFactory:
    """Tests for create_queue_service factory function."""

    def test_create_with_defaults(self) -> None:
        """Test factory with default values."""
        from src.services.agent_queue_service import create_queue_service

        service = create_queue_service()

        assert service is not None
        assert hasattr(service, "config")
        assert hasattr(service, "send_task")
        assert hasattr(service, "receive_responses")

    def test_create_with_custom_urls(self) -> None:
        """Test factory with custom URLs."""
        from src.services.agent_queue_service import create_queue_service

        service = create_queue_service(
            coder_url="https://custom-coder",
            reviewer_url="https://custom-reviewer",
            region="us-west-2",
        )

        assert service.config.coder_queue_url == "https://custom-coder"
        assert service.config.reviewer_queue_url == "https://custom-reviewer"
        assert service.config.region == "us-west-2"
