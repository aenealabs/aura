"""
Tests for Agent Orchestrator Server.

Comprehensive tests for the HTTP server with SQS queue consumer
for agent orchestration jobs.

These tests validate:
- Pydantic models (HealthResponse, JobStatusResponse)
- QueueConsumer class methods
- FastAPI endpoint behavior
- Configuration handling
"""

import json
import os
import platform
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Save original modules before mocking to prevent test pollution
_modules_to_save = ["boto3"]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Set up environment before any imports
os.environ["AWS_REGION"] = "us-east-1"
os.environ["SQS_QUEUE_URL"] = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
os.environ["DYNAMODB_TABLE"] = "test-jobs-table"
os.environ["USE_MOCK_LLM"] = "true"

# Create mocks for boto3
_mock_sqs_client = MagicMock()
_mock_sqs_client.receive_message = MagicMock(return_value={"Messages": []})
_mock_sqs_client.delete_message = MagicMock()
_mock_sqs_client.get_queue_attributes = MagicMock(
    return_value={"Attributes": {"ApproximateNumberOfMessages": "5"}}
)

_mock_dynamodb_table = MagicMock()
_mock_dynamodb_table.update_item = MagicMock()

_mock_dynamodb_resource = MagicMock()
_mock_dynamodb_resource.Table = MagicMock(return_value=_mock_dynamodb_table)

# Patch boto3 at module level before import
_boto3_mock = MagicMock()
_boto3_mock.client = MagicMock(return_value=_mock_sqs_client)
_boto3_mock.resource = MagicMock(return_value=_mock_dynamodb_resource)
_boto3_mock.Session = MagicMock()

sys.modules["boto3"] = _boto3_mock

# Now import the module
from src.agents.orchestrator_server import (
    HealthResponse,
    JobStatusResponse,
    QueueConsumer,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


# =============================================================================
# Fixtures
# =============================================================================


class MockConfig:
    """Mock configuration for testing."""

    ENVIRONMENT = "test"
    PROJECT_NAME = "aura"
    PORT = 8080
    HOST = "0.0.0.0"
    LOG_LEVEL = "INFO"
    AWS_REGION = "us-east-1"
    SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
    SQS_POLL_INTERVAL = 5
    SQS_VISIBILITY_TIMEOUT = 1800
    SQS_MAX_MESSAGES = 1
    SQS_LONG_POLL_WAIT = 10
    DYNAMODB_TABLE = "test-jobs-table"
    CALLBACK_TIMEOUT = 30
    USE_MOCK_LLM = True
    ENABLE_MCP = False
    ENABLE_TITAN_MEMORY = False


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    return MockConfig()


@pytest.fixture
def mock_sqs_client():
    """Create a fresh mock SQS client."""
    sqs = MagicMock()
    sqs.receive_message = MagicMock(return_value={"Messages": []})
    sqs.delete_message = MagicMock()
    sqs.get_queue_attributes = MagicMock(
        return_value={"Attributes": {"ApproximateNumberOfMessages": "5"}}
    )
    return sqs


@pytest.fixture
def mock_dynamodb_table():
    """Create a fresh mock DynamoDB table."""
    table = MagicMock()
    table.update_item = MagicMock()
    return table


@pytest.fixture
def consumer_with_mocks(mock_config, mock_sqs_client, mock_dynamodb_table):
    """Create a QueueConsumer with properly injected mocks."""
    consumer = QueueConsumer(mock_config)
    consumer.sqs = mock_sqs_client
    consumer.table = mock_dynamodb_table
    return consumer


# =============================================================================
# HealthResponse Model Tests
# =============================================================================


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_health_response_creation(self):
        """Test creating a health response."""
        response = HealthResponse(
            status="healthy",
            environment="test",
            uptime_seconds=123.45,
            jobs_processed=10,
            jobs_failed=2,
            queue_consumer_active=True,
        )

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.environment == "test"
        assert response.uptime_seconds == 123.45
        assert response.jobs_processed == 10
        assert response.jobs_failed == 2
        assert response.queue_consumer_active is True

    def test_health_response_defaults(self):
        """Test health response default values."""
        response = HealthResponse(
            status="ready",
            environment="dev",
            uptime_seconds=0.0,
        )

        assert response.version == "1.0.0"
        assert response.jobs_processed == 0
        assert response.jobs_failed == 0
        assert response.queue_consumer_active is False


# =============================================================================
# JobStatusResponse Model Tests
# =============================================================================


class TestJobStatusResponse:
    """Tests for JobStatusResponse model."""

    def test_job_status_response_creation(self):
        """Test creating a job status response."""
        response = JobStatusResponse(
            processing=True,
            current_job_id="job-123",
            started_at="2024-01-01T00:00:00Z",
            jobs_in_queue=5,
        )

        assert response.processing is True
        assert response.current_job_id == "job-123"
        assert response.started_at == "2024-01-01T00:00:00Z"
        assert response.jobs_in_queue == 5

    def test_job_status_response_defaults(self):
        """Test job status response defaults."""
        response = JobStatusResponse(processing=False)

        assert response.current_job_id is None
        assert response.started_at is None
        assert response.jobs_in_queue == 0


# =============================================================================
# QueueConsumer Tests
# =============================================================================


class TestQueueConsumer:
    """Tests for QueueConsumer class."""

    def test_queue_consumer_initialization(self, mock_config):
        """Test queue consumer initialization."""
        consumer = QueueConsumer(mock_config)

        assert consumer.config == mock_config
        assert consumer._running is False
        assert consumer._current_job_id is None
        assert consumer._jobs_processed == 0
        assert consumer._jobs_failed == 0

    def test_is_processing_property(self, mock_config):
        """Test is_processing property."""
        consumer = QueueConsumer(mock_config)

        assert consumer.is_processing is False

        consumer._current_job_id = "job-123"
        assert consumer.is_processing is True

    def test_stats_property(self, mock_config):
        """Test stats property."""
        consumer = QueueConsumer(mock_config)
        consumer._running = True
        consumer._jobs_processed = 5
        consumer._jobs_failed = 1

        stats = consumer.stats

        assert stats["running"] is True
        assert stats["processing"] is False
        assert stats["jobs_processed"] == 5
        assert stats["jobs_failed"] == 1

    @pytest.mark.asyncio
    async def test_start_already_running(self, mock_config):
        """Test that start does nothing if already running."""
        consumer = QueueConsumer(mock_config)
        consumer._running = True

        await consumer.start()
        # Should just return without reinitializing
        assert consumer._running is True

    @pytest.mark.asyncio
    async def test_stop(self, mock_config):
        """Test stop method."""
        consumer = QueueConsumer(mock_config)
        consumer._running = True

        await consumer.stop()
        assert consumer._running is False

    @pytest.mark.asyncio
    async def test_get_queue_depth(self, consumer_with_mocks, mock_sqs_client):
        """Test getting queue depth."""
        depth = await consumer_with_mocks.get_queue_depth()

        assert depth == 5
        mock_sqs_client.get_queue_attributes.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_depth_error(self, mock_config):
        """Test queue depth when SQS call fails."""
        from botocore.exceptions import ClientError

        # Create fresh consumer with isolated error-raising SQS mock
        consumer = QueueConsumer(mock_config)

        # Create a completely fresh mock that raises ClientError
        fresh_error_sqs = MagicMock()
        fresh_error_sqs.get_queue_attributes.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "SQS Error"}}, "GetQueueAttributes"
        )

        # Replace the SQS client
        consumer.sqs = fresh_error_sqs

        depth = await consumer.get_queue_depth()

        # Verify the error SQS was called
        fresh_error_sqs.get_queue_attributes.assert_called_once()
        assert depth == -1

    @pytest.mark.asyncio
    async def test_poll_once_no_messages(self, consumer_with_mocks, mock_sqs_client):
        """Test polling when no messages are available."""
        mock_sqs_client.receive_message.return_value = {"Messages": []}

        await consumer_with_mocks._poll_once()

        mock_sqs_client.receive_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_job_status_running(
        self, consumer_with_mocks, mock_dynamodb_table
    ):
        """Test updating job status to RUNNING."""
        await consumer_with_mocks._update_job_status("job-123", "RUNNING")

        mock_dynamodb_table.update_item.assert_called_once()
        call_kwargs = mock_dynamodb_table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"job_id": "job-123"}
        assert ":status" in call_kwargs["ExpressionAttributeValues"]
        assert call_kwargs["ExpressionAttributeValues"][":status"] == "RUNNING"

    @pytest.mark.asyncio
    async def test_update_job_status_succeeded(
        self, consumer_with_mocks, mock_dynamodb_table
    ):
        """Test updating job status to SUCCEEDED with result."""
        result = {"handover": "Task completed", "metrics": {}}
        await consumer_with_mocks._update_job_status(
            "job-123", "SUCCEEDED", result=result
        )

        mock_dynamodb_table.update_item.assert_called_once()
        call_kwargs = mock_dynamodb_table.update_item.call_args[1]
        assert ":result" in call_kwargs["ExpressionAttributeValues"]

    @pytest.mark.asyncio
    async def test_update_job_status_failed(
        self, consumer_with_mocks, mock_dynamodb_table
    ):
        """Test updating job status to FAILED with error."""
        await consumer_with_mocks._update_job_status(
            "job-123", "FAILED", error_message="Something went wrong"
        )

        mock_dynamodb_table.update_item.assert_called_once()
        call_kwargs = mock_dynamodb_table.update_item.call_args[1]
        assert ":error" in call_kwargs["ExpressionAttributeValues"]

    @pytest.mark.asyncio
    async def test_send_callback_success(self, consumer_with_mocks):
        """Test sending webhook callback."""
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock()
            mock_httpx.return_value = mock_async_client

            await consumer_with_mocks._send_callback(
                callback_url="https://example.com/callback",
                job_id="job-123",
                status="SUCCEEDED",
                data={"result": "success"},
            )

            mock_async_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_callback_failure(self, consumer_with_mocks):
        """Test sending webhook callback handles errors."""
        with patch("httpx.AsyncClient") as mock_httpx:
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(side_effect=Exception("Network error"))
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock()
            mock_httpx.return_value = mock_async_client

            # Should not raise
            await consumer_with_mocks._send_callback(
                callback_url="https://example.com/callback",
                job_id="job-123",
                status="FAILED",
                data={"error": "test"},
            )

    @pytest.mark.asyncio
    async def test_execute_orchestrator(self, consumer_with_mocks):
        """Test executing the orchestrator."""
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_request = AsyncMock(
            return_value={
                "status": "SUCCESS",
                "handover": "Completed task",
                "metrics": {"duration": 1.5},
            }
        )
        consumer_with_mocks._orchestrator = mock_orchestrator

        result = await consumer_with_mocks._execute_orchestrator(
            "Test prompt", "job-123"
        )

        assert result["status"] == "SUCCESS"
        assert result["handover"] == "Completed task"
        assert result["job_id"] == "job-123"
        assert "completed_at" in result

    @pytest.mark.asyncio
    async def test_execute_orchestrator_not_initialized(self, consumer_with_mocks):
        """Test executing orchestrator when not initialized."""
        consumer_with_mocks._orchestrator = None

        with pytest.raises(RuntimeError, match="Orchestrator not initialized"):
            await consumer_with_mocks._execute_orchestrator("Test prompt", "job-123")

    @pytest.mark.asyncio
    async def test_process_message_success(
        self, consumer_with_mocks, mock_sqs_client, mock_dynamodb_table
    ):
        """Test processing a message successfully."""
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_request = AsyncMock(
            return_value={
                "status": "SUCCESS",
                "handover": "Done",
                "metrics": {},
            }
        )
        consumer_with_mocks._orchestrator = mock_orchestrator

        message = {
            "ReceiptHandle": "receipt-123",
            "Body": json.dumps(
                {
                    "job_id": "job-123",
                    "task_id": "task-456",
                    "prompt": "Test task",
                }
            ),
        }

        await consumer_with_mocks._process_message(message)

        assert consumer_with_mocks._jobs_processed == 1
        assert consumer_with_mocks._jobs_failed == 0
        mock_sqs_client.delete_message.assert_called()

    @pytest.mark.asyncio
    async def test_process_message_failure(self, consumer_with_mocks, mock_sqs_client):
        """Test processing a message that fails."""
        # Mock orchestrator that fails
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_request = AsyncMock(
            side_effect=Exception("Orchestrator error")
        )
        consumer_with_mocks._orchestrator = mock_orchestrator

        message = {
            "ReceiptHandle": "receipt-123",
            "Body": json.dumps(
                {
                    "job_id": "job-123",
                    "task_id": "task-456",
                    "prompt": "Test task",
                }
            ),
        }

        await consumer_with_mocks._process_message(message)

        assert consumer_with_mocks._jobs_failed == 1
        assert consumer_with_mocks._jobs_processed == 0


# =============================================================================
# MockConfig Tests
# =============================================================================


class TestMockConfig:
    """Tests for MockConfig class used in tests."""

    def test_mock_config_values(self):
        """Test MockConfig has expected default values."""
        config = MockConfig()

        assert config.ENVIRONMENT == "test"
        assert config.PROJECT_NAME == "aura"
        assert config.PORT == 8080
        assert config.HOST == "0.0.0.0"
        assert config.AWS_REGION == "us-east-1"
        assert config.USE_MOCK_LLM is True


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for orchestrator server."""

    @pytest.mark.asyncio
    async def test_full_message_processing_workflow(
        self, consumer_with_mocks, mock_sqs_client, mock_dynamodb_table
    ):
        """Test complete message processing workflow."""
        with patch("httpx.AsyncClient") as mock_httpx:
            # Setup httpx mock
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_async_client = AsyncMock()
            mock_async_client.post = AsyncMock(return_value=mock_response)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock()
            mock_httpx.return_value = mock_async_client

            # Mock orchestrator
            mock_orchestrator = MagicMock()
            mock_orchestrator.execute_request = AsyncMock(
                return_value={
                    "status": "SUCCESS",
                    "handover": "Task completed successfully",
                    "metrics": {"tokens": 100},
                }
            )
            consumer_with_mocks._orchestrator = mock_orchestrator

            # Process message with callback
            message = {
                "ReceiptHandle": "receipt-integration-test",
                "Body": json.dumps(
                    {
                        "job_id": "integration-job",
                        "task_id": "integration-task",
                        "prompt": "Integration test task",
                        "callback_url": "https://callback.example.com/webhook",
                    }
                ),
            }

            await consumer_with_mocks._process_message(message)

            # Verify
            assert consumer_with_mocks._jobs_processed == 1
            mock_orchestrator.execute_request.assert_called_once_with(
                "Integration test task"
            )
            mock_async_client.post.assert_called_once()  # Callback sent

    @pytest.mark.asyncio
    async def test_consumer_stats_tracking(self, consumer_with_mocks):
        """Test that consumer tracks job statistics correctly."""
        # Mock orchestrator
        mock_orchestrator = MagicMock()

        # First job succeeds
        mock_orchestrator.execute_request = AsyncMock(
            return_value={
                "status": "SUCCESS",
                "handover": "Done",
                "metrics": {},
            }
        )
        consumer_with_mocks._orchestrator = mock_orchestrator

        message1 = {
            "ReceiptHandle": "receipt-1",
            "Body": json.dumps(
                {
                    "job_id": "job-1",
                    "task_id": "task-1",
                    "prompt": "Task 1",
                }
            ),
        }
        await consumer_with_mocks._process_message(message1)

        # Second job fails
        mock_orchestrator.execute_request = AsyncMock(
            side_effect=Exception("Job failed")
        )

        message2 = {
            "ReceiptHandle": "receipt-2",
            "Body": json.dumps(
                {
                    "job_id": "job-2",
                    "task_id": "task-2",
                    "prompt": "Task 2",
                }
            ),
        }
        await consumer_with_mocks._process_message(message2)

        # Check stats
        stats = consumer_with_mocks.stats
        assert stats["jobs_processed"] == 1
        assert stats["jobs_failed"] == 1

    @pytest.mark.asyncio
    async def test_consumer_clears_job_state_after_processing(
        self, consumer_with_mocks
    ):
        """Test that current job state is cleared after processing."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute_request = AsyncMock(
            return_value={
                "status": "SUCCESS",
                "handover": "Done",
                "metrics": {},
            }
        )
        consumer_with_mocks._orchestrator = mock_orchestrator

        message = {
            "ReceiptHandle": "receipt-1",
            "Body": json.dumps(
                {
                    "job_id": "job-1",
                    "task_id": "task-1",
                    "prompt": "Task 1",
                }
            ),
        }

        await consumer_with_mocks._process_message(message)

        # Current job should be cleared
        assert consumer_with_mocks._current_job_id is None
        assert consumer_with_mocks._current_job_started is None
