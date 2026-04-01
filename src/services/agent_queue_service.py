"""Agent Queue Service for SQS-based inter-agent communication.

This service provides message production and consumption for asynchronous
communication between the orchestrator and individual agents (Coder, Reviewer,
Validator) via dedicated SQS queues.

Issue: #19 - Microservices messaging with SQS/EventBridge

Usage:
    # Initialize service
    queue_service = AgentQueueService()

    # Send task to coder agent
    task = AgentTaskMessage.create(
        task_id="task-123",
        target_agent="coder",
        task_description="Generate authentication middleware",
        context={"code_context": "..."},
    )
    message_id = await queue_service.send_task("coder", task)

    # Receive responses from agents
    responses = await queue_service.receive_responses(max_messages=10)
    for response in responses:
        print(f"Task {response.task_id}: {'SUCCESS' if response.success else 'FAILED'}")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.agents.messaging.schemas import AgentResultMessage, AgentTaskMessage, AgentType
from src.services.eventbridge_publisher import EventBridgePublisher, EventType

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class QueueConfig:
    """Configuration for agent queue service."""

    coder_queue_url: str = field(
        default_factory=lambda: os.environ.get("CODER_QUEUE_URL", "")
    )
    reviewer_queue_url: str = field(
        default_factory=lambda: os.environ.get("REVIEWER_QUEUE_URL", "")
    )
    validator_queue_url: str = field(
        default_factory=lambda: os.environ.get("VALIDATOR_QUEUE_URL", "")
    )
    responses_queue_url: str = field(
        default_factory=lambda: os.environ.get("RESPONSES_QUEUE_URL", "")
    )
    region: str = field(
        default_factory=lambda: os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    )
    max_receive_count: int = 10
    visibility_timeout: int = 300  # 5 minutes
    wait_time_seconds: int = 20  # Long polling
    publish_events: bool = True  # Publish to EventBridge


# =============================================================================
# Agent Queue Service
# =============================================================================


class AgentQueueService:
    """Service for sending and receiving messages to/from agent SQS queues.

    Provides:
    - Task dispatch to agent-specific queues
    - Result collection from responses queue
    - EventBridge event publishing for workflow tracking
    - Automatic retries with exponential backoff
    """

    def __init__(self, config: QueueConfig | None = None):
        """Initialize the queue service.

        Args:
            config: Queue configuration (uses environment variables if not provided)
        """
        self.config = config or QueueConfig()
        self._sqs_client: Any = None
        self._event_publisher: EventBridgePublisher | None = None

        # Map agent types to queue URLs
        self._queue_urls: dict[str, str] = {
            AgentType.CODER.value: self.config.coder_queue_url,
            AgentType.REVIEWER.value: self.config.reviewer_queue_url,
            AgentType.VALIDATOR.value: self.config.validator_queue_url,
            "responses": self.config.responses_queue_url,
        }

    @property
    def sqs(self) -> Any:
        """Lazy-load SQS client."""
        if self._sqs_client is None:
            boto_config = Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=5,
                read_timeout=30,
            )
            self._sqs_client = boto3.client(
                "sqs", region_name=self.config.region, config=boto_config
            )
        return self._sqs_client

    @property
    def event_publisher(self) -> EventBridgePublisher:
        """Lazy-load EventBridge publisher."""
        if self._event_publisher is None:
            self._event_publisher = EventBridgePublisher()
        return self._event_publisher

    def _get_queue_url(self, agent_type: str) -> str:
        """Get the queue URL for an agent type.

        Args:
            agent_type: Agent type (coder, reviewer, validator, responses)

        Returns:
            Queue URL

        Raises:
            ValueError: If agent type is unknown or queue URL not configured
        """
        url = self._queue_urls.get(agent_type)
        if not url:
            raise ValueError(
                f"Unknown agent type or unconfigured queue: {agent_type}. "
                f"Available: {list(self._queue_urls.keys())}"
            )
        return url

    # =========================================================================
    # Send Operations
    # =========================================================================

    async def send_task(
        self,
        agent_type: str,
        message: AgentTaskMessage,
        delay_seconds: int = 0,
    ) -> str:
        """Send a task message to an agent's queue.

        Args:
            agent_type: Target agent (coder, reviewer, validator)
            message: Task message to send
            delay_seconds: Optional delay before message becomes visible (0-900)

        Returns:
            SQS message ID

        Raises:
            ValueError: If agent type is unknown
            ClientError: If SQS send fails
        """
        queue_url = self._get_queue_url(agent_type)

        try:
            sqs_message = message.to_sqs_message()
            if delay_seconds > 0:
                sqs_message["DelaySeconds"] = min(delay_seconds, 900)

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sqs.send_message(QueueUrl=queue_url, **sqs_message),
            )

            message_id = response["MessageId"]
            logger.info(
                f"Sent task {message.task_id} to {agent_type} queue, "
                f"message_id={message_id}"
            )

            # Publish event if enabled
            if self.config.publish_events:
                await self._publish_dispatch_event(message)

            return message_id

        except ClientError as e:
            logger.error(
                f"Failed to send task to {agent_type}: {e.response['Error']['Message']}"
            )
            raise

    async def send_result(self, message: AgentResultMessage) -> str:
        """Send a result message to the responses queue.

        Args:
            message: Result message from an agent

        Returns:
            SQS message ID

        Raises:
            ClientError: If SQS send fails
        """
        queue_url = self._get_queue_url("responses")

        try:
            sqs_message = message.to_sqs_message()

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sqs.send_message(QueueUrl=queue_url, **sqs_message),
            )

            message_id = response["MessageId"]
            logger.info(
                f"Sent result for task {message.task_id} to responses queue, "
                f"message_id={message_id}, success={message.success}"
            )

            # Publish event if enabled
            if self.config.publish_events:
                await self._publish_result_event(message)

            return message_id

        except ClientError as e:
            logger.error(f"Failed to send result: {e.response['Error']['Message']}")
            raise

    async def send_batch(
        self,
        agent_type: str,
        messages: list[AgentTaskMessage],
    ) -> list[dict[str, Any]]:
        """Send multiple task messages to an agent's queue.

        Args:
            agent_type: Target agent
            messages: List of task messages (max 10)

        Returns:
            List of send results with message IDs

        Raises:
            ValueError: If more than 10 messages or agent type unknown
        """
        if len(messages) > 10:
            raise ValueError("SQS batch limit is 10 messages")

        queue_url = self._get_queue_url(agent_type)

        entries = []
        for i, msg in enumerate(messages):
            sqs_msg = msg.to_sqs_message()
            entries.append(
                {
                    "Id": str(i),
                    "MessageBody": sqs_msg["MessageBody"],
                    "MessageAttributes": sqs_msg["MessageAttributes"],
                }
            )

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sqs.send_message_batch(
                    QueueUrl=queue_url, Entries=entries
                ),
            )

            successful = response.get("Successful", [])
            failed = response.get("Failed", [])

            if failed:
                logger.warning(f"Batch send had {len(failed)} failures: {failed}")

            # Publish events for successful sends
            if self.config.publish_events:
                for success in successful:
                    idx = int(success["Id"])
                    await self._publish_dispatch_event(messages[idx])

            return successful

        except ClientError as e:
            logger.error(f"Batch send failed: {e.response['Error']['Message']}")
            raise

    # =========================================================================
    # Receive Operations
    # =========================================================================

    async def receive_tasks(
        self,
        agent_type: str,
        max_messages: int = 10,
        wait_time_seconds: int | None = None,
    ) -> list[tuple[AgentTaskMessage, str]]:
        """Receive task messages from an agent's queue.

        Args:
            agent_type: Agent type to receive for
            max_messages: Maximum messages to receive (1-10)
            wait_time_seconds: Long polling wait time (None uses config default)

        Returns:
            List of (message, receipt_handle) tuples

        Note:
            Caller must call ack_message() after processing to delete the message,
            or nack_message() to make it visible again for retry.
        """
        queue_url = self._get_queue_url(agent_type)
        wait_time = (
            wait_time_seconds
            if wait_time_seconds is not None
            else self.config.wait_time_seconds
        )

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=min(max_messages, 10),
                    WaitTimeSeconds=wait_time,
                    VisibilityTimeout=self.config.visibility_timeout,
                    MessageAttributeNames=["All"],
                ),
            )

            messages = response.get("Messages", [])
            result = []

            for msg in messages:
                try:
                    task_msg = AgentTaskMessage.from_json(msg["Body"])
                    receipt_handle = msg["ReceiptHandle"]
                    result.append((task_msg, receipt_handle))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse message: {e}")
                    # Move to DLQ by not acknowledging
                    continue

            logger.debug(f"Received {len(result)} tasks from {agent_type} queue")
            return result

        except ClientError as e:
            logger.error(f"Failed to receive tasks: {e.response['Error']['Message']}")
            raise

    async def receive_responses(
        self,
        max_messages: int = 10,
        wait_time_seconds: int | None = None,
    ) -> list[tuple[AgentResultMessage, str]]:
        """Receive result messages from the responses queue.

        Args:
            max_messages: Maximum messages to receive
            wait_time_seconds: Long polling wait time

        Returns:
            List of (message, receipt_handle) tuples
        """
        queue_url = self._get_queue_url("responses")
        wait_time = (
            wait_time_seconds
            if wait_time_seconds is not None
            else self.config.wait_time_seconds
        )

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=min(max_messages, 10),
                    WaitTimeSeconds=wait_time,
                    VisibilityTimeout=self.config.visibility_timeout,
                    MessageAttributeNames=["All"],
                ),
            )

            messages = response.get("Messages", [])
            result = []

            for msg in messages:
                try:
                    result_msg = AgentResultMessage.from_json(msg["Body"])
                    receipt_handle = msg["ReceiptHandle"]
                    result.append((result_msg, receipt_handle))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse response message: {e}")
                    continue

            logger.debug(f"Received {len(result)} responses")
            return result

        except ClientError as e:
            logger.error(
                f"Failed to receive responses: {e.response['Error']['Message']}"
            )
            raise

    # =========================================================================
    # Acknowledgment Operations
    # =========================================================================

    async def ack_message(
        self, agent_type_or_responses: str, receipt_handle: str
    ) -> None:
        """Acknowledge (delete) a successfully processed message.

        Args:
            agent_type_or_responses: Agent type or "responses"
            receipt_handle: Receipt handle from receive operation
        """
        queue_url = self._get_queue_url(agent_type_or_responses)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.sqs.delete_message(
                    QueueUrl=queue_url, ReceiptHandle=receipt_handle
                ),
            )
            logger.debug(f"Acknowledged message from {agent_type_or_responses}")

        except ClientError as e:
            logger.error(f"Failed to ack message: {e.response['Error']['Message']}")
            raise

    async def nack_message(
        self,
        agent_type_or_responses: str,
        receipt_handle: str,
        visibility_timeout: int = 0,
    ) -> None:
        """Negative acknowledge - make message visible again for retry.

        Args:
            agent_type_or_responses: Agent type or "responses"
            receipt_handle: Receipt handle from receive operation
            visibility_timeout: Seconds before message becomes visible (0 = immediate)
        """
        queue_url = self._get_queue_url(agent_type_or_responses)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.sqs.change_message_visibility(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=visibility_timeout,
                ),
            )
            logger.debug(
                f"Nacked message from {agent_type_or_responses}, "
                f"visibility_timeout={visibility_timeout}"
            )

        except ClientError as e:
            logger.error(f"Failed to nack message: {e.response['Error']['Message']}")
            raise

    # =========================================================================
    # Queue Status
    # =========================================================================

    async def get_queue_depth(self, agent_type: str) -> int:
        """Get the approximate number of messages in a queue.

        Args:
            agent_type: Agent type or "responses"

        Returns:
            Approximate message count
        """
        queue_url = self._get_queue_url(agent_type)

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.sqs.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=["ApproximateNumberOfMessages"],
                ),
            )

            return int(response["Attributes"]["ApproximateNumberOfMessages"])

        except ClientError as e:
            logger.error(f"Failed to get queue depth: {e.response['Error']['Message']}")
            return -1

    async def get_all_queue_depths(self) -> dict[str, int]:
        """Get message counts for all queues.

        Returns:
            Dict mapping agent type to message count
        """
        depths = {}
        for agent_type in self._queue_urls:
            if self._queue_urls[agent_type]:  # Skip unconfigured queues
                depths[agent_type] = await self.get_queue_depth(agent_type)
        return depths

    # =========================================================================
    # EventBridge Integration
    # =========================================================================

    async def _publish_dispatch_event(self, message: AgentTaskMessage) -> None:
        """Publish task dispatch event to EventBridge."""
        try:
            await self.event_publisher.publish_async(
                event_type=EventType.AGENT_TASK_DISPATCHED,
                data={
                    "task_id": message.task_id,
                    "agent_type": message.target_agent,
                    "correlation_id": message.correlation_id,
                    "priority": message.priority,
                    "task_description": message.task_description,
                    "autonomy_level": message.autonomy_level,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to publish dispatch event: {e}")

    async def _publish_result_event(self, message: AgentResultMessage) -> None:
        """Publish task result event to EventBridge."""
        try:
            event_type = (
                EventType.AGENT_TASK_COMPLETED
                if message.success
                else EventType.AGENT_TASK_FAILED
            )

            await self.event_publisher.publish_async(
                event_type=event_type,
                data={
                    "task_id": message.task_id,
                    "agent_type": message.source_agent,
                    "correlation_id": message.correlation_id,
                    "success": message.success,
                    "error": message.error,
                    "execution_time_ms": message.execution_time_ms,
                    "tokens_used": message.tokens_used,
                    "requires_remediation": message.requires_remediation,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to publish result event: {e}")


# =============================================================================
# Factory Function
# =============================================================================


def create_queue_service(
    coder_url: str | None = None,
    reviewer_url: str | None = None,
    validator_url: str | None = None,
    responses_url: str | None = None,
    region: str | None = None,
) -> AgentQueueService:
    """Factory function to create an AgentQueueService with custom configuration.

    Args:
        coder_url: Override coder queue URL
        reviewer_url: Override reviewer queue URL
        validator_url: Override validator queue URL
        responses_url: Override responses queue URL
        region: AWS region

    Returns:
        Configured AgentQueueService
    """
    config = QueueConfig()

    if coder_url:
        config.coder_queue_url = coder_url
    if reviewer_url:
        config.reviewer_queue_url = reviewer_url
    if validator_url:
        config.validator_queue_url = validator_url
    if responses_url:
        config.responses_queue_url = responses_url
    if region:
        config.region = region

    return AgentQueueService(config)
