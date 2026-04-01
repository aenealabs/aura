"""Message schemas for agent-to-agent communication via SQS.

This module defines the message formats used for asynchronous communication
between the orchestrator and individual agents (Coder, Reviewer, Validator).

Issue: #19 - Microservices messaging with SQS/EventBridge
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MessageType(str, Enum):
    """Types of messages exchanged between agents."""

    TASK = "task"  # Task assignment from orchestrator
    RESULT = "result"  # Result from agent back to orchestrator
    STATUS = "status"  # Status update (heartbeat, progress)
    CANCEL = "cancel"  # Cancel a running task


class MessagePriority(int, Enum):
    """Message priority levels (1=lowest, 10=highest)."""

    LOW = 1
    NORMAL = 5
    HIGH = 7
    CRITICAL = 10


class AgentType(str, Enum):
    """Types of agents in the system."""

    ORCHESTRATOR = "orchestrator"
    CODER = "coder"
    REVIEWER = "reviewer"
    VALIDATOR = "validator"


@dataclass
class AgentMessage:
    """Base message for agent-to-agent communication.

    All messages exchanged via SQS inherit from this base class.
    Messages are serialized to JSON for SQS transport.

    Attributes:
        message_id: Unique identifier for this message
        task_id: ID of the task this message relates to
        source_agent: Agent that sent this message
        target_agent: Agent that should receive this message
        message_type: Type of message (task, result, status)
        payload: Message-specific data
        correlation_id: ID for tracking related messages in a workflow
        timestamp: ISO format timestamp when message was created
        priority: Message priority (1-10)
        retry_count: Number of times this message has been retried
        max_retries: Maximum retry attempts before DLQ
    """

    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    source_agent: str = ""
    target_agent: str = ""
    message_type: str = MessageType.TASK.value
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    priority: int = MessagePriority.NORMAL.value
    retry_count: int = 0
    max_retries: int = 3

    def to_json(self) -> str:
        """Serialize message to JSON string for SQS."""
        return json.dumps(asdict(self), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> AgentMessage:
        """Deserialize message from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    def to_sqs_message(self) -> dict[str, Any]:
        """Format message for SQS SendMessage API.

        Returns:
            Dict with MessageBody, MessageAttributes, and optional MessageGroupId
        """
        return {
            "MessageBody": self.to_json(),
            "MessageAttributes": {
                "MessageType": {
                    "DataType": "String",
                    "StringValue": self.message_type,
                },
                "Priority": {
                    "DataType": "Number",
                    "StringValue": str(self.priority),
                },
                "SourceAgent": {
                    "DataType": "String",
                    "StringValue": self.source_agent,
                },
                "TargetAgent": {
                    "DataType": "String",
                    "StringValue": self.target_agent,
                },
                "CorrelationId": {
                    "DataType": "String",
                    "StringValue": self.correlation_id,
                },
            },
        }

    def increment_retry(self) -> AgentMessage:
        """Return a new message with incremented retry count."""
        return AgentMessage(
            message_id=self.message_id,
            task_id=self.task_id,
            source_agent=self.source_agent,
            target_agent=self.target_agent,
            message_type=self.message_type,
            payload=self.payload,
            correlation_id=self.correlation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            priority=self.priority,
            retry_count=self.retry_count + 1,
            max_retries=self.max_retries,
        )

    def should_retry(self) -> bool:
        """Check if message should be retried after failure."""
        return self.retry_count < self.max_retries


@dataclass
class AgentTaskMessage(AgentMessage):
    """Task assignment message from orchestrator to agent.

    Sent when the orchestrator dispatches a task to a specific agent
    (Coder, Reviewer, or Validator) via their dedicated SQS queue.

    Attributes:
        context: Hybrid context (graph + vector) for the task
        timeout_seconds: Maximum execution time for this task
        autonomy_level: HITL requirements (full_hitl, critical_hitl, audit_only, full_autonomous)
        task_description: Human-readable description of the task
        dependencies: List of task_ids that must complete first
        metadata: Additional task-specific metadata
    """

    context: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300  # 5 minutes default
    autonomy_level: str = "critical_hitl"
    task_description: str = ""
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure message_type is set correctly."""
        self.message_type = MessageType.TASK.value

    @classmethod
    def from_json(cls, json_str: str) -> AgentTaskMessage:
        """Deserialize task message from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    @classmethod
    def create(
        cls,
        task_id: str,
        target_agent: str,
        task_description: str,
        context: dict[str, Any] | None = None,
        timeout_seconds: int = 300,
        autonomy_level: str = "critical_hitl",
        priority: int = MessagePriority.NORMAL.value,
        correlation_id: str | None = None,
        dependencies: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentTaskMessage:
        """Factory method to create a task message.

        Args:
            task_id: Unique identifier for this task
            target_agent: Agent to execute the task (coder, reviewer, validator)
            task_description: Human-readable task description
            context: Hybrid context data
            timeout_seconds: Max execution time
            autonomy_level: HITL requirements
            priority: Message priority
            correlation_id: Workflow correlation ID (auto-generated if not provided)
            dependencies: Task IDs that must complete first
            metadata: Additional metadata

        Returns:
            AgentTaskMessage ready for queue submission
        """
        return cls(
            task_id=task_id,
            source_agent=AgentType.ORCHESTRATOR.value,
            target_agent=target_agent,
            task_description=task_description,
            context=context or {},
            timeout_seconds=timeout_seconds,
            autonomy_level=autonomy_level,
            priority=priority,
            correlation_id=correlation_id or str(uuid.uuid4()),
            dependencies=dependencies or [],
            metadata=metadata or {},
        )


@dataclass
class AgentResultMessage(AgentMessage):
    """Result message from agent back to orchestrator.

    Sent when an agent completes (or fails) a task, containing
    the execution results and metrics.

    Attributes:
        success: Whether the task completed successfully
        data: Result data from the agent
        error: Error message if task failed
        execution_time_ms: Time taken to execute the task
        tokens_used: LLM tokens consumed
        cost_usd: Estimated cost in USD
        tools_invoked: List of tools/APIs called during execution
        requires_remediation: Whether follow-up action is needed
        remediation_details: Details about required remediation
    """

    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    tools_invoked: list[str] = field(default_factory=list)
    requires_remediation: bool = False
    remediation_details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure message_type is set correctly."""
        self.message_type = MessageType.RESULT.value

    @classmethod
    def from_json(cls, json_str: str) -> AgentResultMessage:
        """Deserialize result message from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    @classmethod
    def create_success(
        cls,
        task_id: str,
        source_agent: str,
        data: dict[str, Any],
        execution_time_ms: float,
        correlation_id: str,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        tools_invoked: list[str] | None = None,
    ) -> AgentResultMessage:
        """Factory method to create a success result message."""
        return cls(
            task_id=task_id,
            source_agent=source_agent,
            target_agent=AgentType.ORCHESTRATOR.value,
            correlation_id=correlation_id,
            success=True,
            data=data,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            tools_invoked=tools_invoked or [],
        )

    @classmethod
    def create_failure(
        cls,
        task_id: str,
        source_agent: str,
        error: str,
        execution_time_ms: float,
        correlation_id: str,
        requires_remediation: bool = False,
        remediation_details: dict[str, Any] | None = None,
    ) -> AgentResultMessage:
        """Factory method to create a failure result message."""
        return cls(
            task_id=task_id,
            source_agent=source_agent,
            target_agent=AgentType.ORCHESTRATOR.value,
            correlation_id=correlation_id,
            success=False,
            error=error,
            execution_time_ms=execution_time_ms,
            requires_remediation=requires_remediation,
            remediation_details=remediation_details or {},
        )


@dataclass
class AgentStatusMessage(AgentMessage):
    """Status update message for progress tracking.

    Sent periodically by agents to report progress on long-running tasks.

    Attributes:
        status: Current status (running, waiting, paused)
        progress_percent: Completion percentage (0-100)
        current_step: Description of current step
        estimated_remaining_seconds: Estimated time to completion
    """

    status: str = "running"
    progress_percent: int = 0
    current_step: str = ""
    estimated_remaining_seconds: int | None = None

    def __post_init__(self):
        """Ensure message_type is set correctly."""
        self.message_type = MessageType.STATUS.value

    @classmethod
    def from_json(cls, json_str: str) -> AgentStatusMessage:
        """Deserialize status message from JSON string."""
        data = json.loads(json_str)
        return cls(**data)


def parse_sqs_message(sqs_message: dict[str, Any]) -> AgentMessage:
    """Parse an SQS message into the appropriate AgentMessage type.

    Args:
        sqs_message: Raw SQS message dict with Body and MessageAttributes

    Returns:
        Appropriate AgentMessage subclass based on message type

    Raises:
        ValueError: If message type is unknown
    """
    body = json.loads(sqs_message.get("Body", "{}"))
    message_type = body.get("message_type", MessageType.TASK.value)

    if message_type == MessageType.TASK.value:
        return AgentTaskMessage.from_json(sqs_message["Body"])
    elif message_type == MessageType.RESULT.value:
        return AgentResultMessage.from_json(sqs_message["Body"])
    elif message_type == MessageType.STATUS.value:
        return AgentStatusMessage.from_json(sqs_message["Body"])
    else:
        return AgentMessage.from_json(sqs_message["Body"])
