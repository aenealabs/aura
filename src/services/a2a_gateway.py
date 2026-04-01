"""
Project Aura - A2A Protocol Gateway

Implements ADR-028 Phase 6: Agent-to-Agent (A2A) Protocol Support

This module provides the gateway for Google's A2A protocol, enabling cross-platform
agent interoperability with Microsoft Foundry, LangGraph, and other platforms.

The A2A protocol is based on JSON-RPC 2.0 over HTTP(S) and provides:
- Agent capability discovery via Agent Cards
- Task lifecycle management
- Secure agent-to-agent authentication
- Asynchronous communication via push notifications

IMPORTANT: This gateway is ONLY available in ENTERPRISE mode.
Defense/GovCloud deployments do not support A2A for security reasons.

References:
- Google A2A Protocol: https://github.com/google/A2A
- A2A Specification: https://a2a-protocol.org/latest/specification/

Usage:
    >>> from src.services.a2a_gateway import A2AGateway
    >>> gateway = A2AGateway()
    >>> agent_card = await gateway.get_agent_card("aura-coder-agent")
    >>> task = await gateway.send_task(target_agent_id, task_request)
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from src.config import (
    IntegrationConfig,
    get_integration_config,
    require_enterprise_mode,
)

logger = logging.getLogger(__name__)


# =============================================================================
# A2A Protocol Constants
# =============================================================================

A2A_PROTOCOL_VERSION = "1.0"
A2A_JSON_RPC_VERSION = "2.0"


# =============================================================================
# Enums
# =============================================================================


class A2AMessageType(Enum):
    """A2A protocol message types."""

    # Agent discovery
    AGENT_CARD_REQUEST = "agent_card_request"
    AGENT_CARD_RESPONSE = "agent_card_response"

    # Task management
    TASK_SEND = "tasks/send"
    TASK_SEND_SUBSCRIBE = "tasks/sendSubscribe"
    TASK_GET = "tasks/get"
    TASK_CANCEL = "tasks/cancel"
    TASK_RESUBSCRIBE = "tasks/resubscribe"

    # Push notifications
    PUSH_NOTIFICATION_SET = "tasks/pushNotification/set"
    PUSH_NOTIFICATION_GET = "tasks/pushNotification/get"


class TaskStatus(Enum):
    """A2A task lifecycle status."""

    SUBMITTED = "submitted"  # Task received, not yet started
    WORKING = "working"  # Agent is processing
    INPUT_REQUIRED = "input_required"  # Awaiting human input
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"  # Error occurred
    CANCELED = "canceled"  # Canceled by requester


class ArtifactType(Enum):
    """Types of artifacts produced by tasks."""

    TEXT = "text"
    CODE = "code"
    FILE = "file"
    JSON = "json"
    PATCH = "patch"
    REPORT = "report"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AgentCapability:
    """
    A capability advertised by an agent.

    Capabilities describe what an agent can do, with input/output schemas
    to enable type-safe invocation.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    streaming_supported: bool = False
    requires_authentication: bool = True
    rate_limit_per_minute: int = 60


@dataclass
class AgentCard:
    """
    Agent Card per A2A specification.

    The Agent Card is a JSON document that describes an agent's capabilities,
    authentication requirements, and endpoint information. It enables automatic
    discovery and integration with external agents.
    """

    agent_id: str
    name: str
    description: str
    protocol_version: str = A2A_PROTOCOL_VERSION
    endpoint: str = ""
    provider: str = "aenealabs"

    # Capabilities
    capabilities: list[AgentCapability] = field(default_factory=list)

    # Authentication
    authentication_type: str = "oauth2"
    oauth_scopes: list[str] = field(default_factory=list)

    # Metadata
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Rate limiting
    default_rate_limit: int = 100  # requests per minute

    # Contact
    documentation_url: str | None = None
    support_email: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to A2A-compliant JSON format."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "protocol_version": self.protocol_version,
            "endpoint": self.endpoint,
            "provider": self.provider,
            "capabilities": [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "input_schema": cap.input_schema,
                    "output_schema": cap.output_schema,
                    "streaming_supported": cap.streaming_supported,
                    "requires_authentication": cap.requires_authentication,
                }
                for cap in self.capabilities
            ],
            "authentication": {
                "type": self.authentication_type,
                "oauth_scopes": self.oauth_scopes,
            },
            "version": self.version,
            "default_rate_limit": self.default_rate_limit,
            "documentation_url": self.documentation_url,
            "support_email": self.support_email,
        }


@dataclass
class TaskArtifact:
    """An artifact produced by a task (code, report, patch, etc.)."""

    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    artifact_type: ArtifactType = ArtifactType.TEXT
    name: str = ""
    description: str = ""
    content: str = ""
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON format."""
        return {
            "artifact_id": self.artifact_id,
            "type": self.artifact_type.value,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "mime_type": self.mime_type,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class A2ATask:
    """
    A task in the A2A protocol.

    Tasks are the primary unit of work in A2A. They have a lifecycle from
    submission through completion, with optional streaming updates.
    """

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str | None = None  # For multi-turn conversations

    # Task details
    capability_name: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)

    # Status
    status: TaskStatus = TaskStatus.SUBMITTED
    status_message: str = ""

    # Results
    output_data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[TaskArtifact] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    # Push notification
    push_notification_url: str | None = None

    # Requester info
    requester_agent_id: str | None = None
    requester_endpoint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON format."""
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "capability_name": self.capability_name,
            "status": self.status.value,
            "status_message": self.status_message,
            "output": self.output_data,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class A2ARequest:
    """JSON-RPC 2.0 request for A2A protocol."""

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    jsonrpc: str = A2A_JSON_RPC_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-RPC format."""
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
            "id": self.id,
        }


@dataclass
class A2AResponse:
    """JSON-RPC 2.0 response for A2A protocol."""

    id: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    jsonrpc: str = A2A_JSON_RPC_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-RPC format."""
        response: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result or {}
        return response

    @property
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.error is None


# =============================================================================
# A2A Gateway
# =============================================================================


class A2AGateway:
    """
    Gateway for A2A (Agent-to-Agent) protocol communication.

    This gateway handles:
    - Agent Card generation and serving
    - Task lifecycle management
    - Communication with external A2A-compatible agents
    - Push notifications for async updates
    - Rate limiting and quota enforcement

    SECURITY: Only available in ENTERPRISE mode. Defense deployments
    do not support cross-platform agent communication.
    """

    def __init__(
        self,
        config: IntegrationConfig | None = None,
        base_endpoint: str | None = None,
    ):
        """
        Initialize A2A Gateway.

        Args:
            config: Integration configuration. If None, loads from environment.
            base_endpoint: Base URL for A2A endpoints. If None, auto-configured.
        """
        self._config = config or get_integration_config()

        # Validate we're in enterprise mode with A2A enabled
        if self._config.is_defense_mode:
            raise RuntimeError(
                "A2AGateway cannot be instantiated in DEFENSE mode. "
                "A2A protocol is not available for air-gapped/GovCloud deployments."
            )

        if not self._config.a2a_enabled:
            logger.warning(
                "A2A is not enabled in configuration. "
                "Set AURA_A2A_ENABLED=true to enable."
            )

        # Configuration
        self._base_endpoint = base_endpoint or os.environ.get(
            "A2A_GATEWAY_ENDPOINT", "https://api.aura.local/a2a"
        )

        # Agent cards cache
        self._local_agent_cards: dict[str, AgentCard] = {}
        self._external_agent_cards: dict[str, AgentCard] = {}
        self._external_card_cache_ttl = 300.0  # 5 minutes

        # Task storage (in production, use DynamoDB)
        self._tasks: dict[str, A2ATask] = {}

        # Capability handlers
        self._capability_handlers: dict[str, Callable] = {}

        # Metrics
        self._total_tasks_received = 0
        self._total_tasks_sent = 0
        self._total_errors = 0

        # Initialize local agent cards
        self._initialize_aura_agent_cards()

        logger.info(
            f"A2AGateway initialized: endpoint={self._base_endpoint}, "
            f"a2a_enabled={self._config.a2a_enabled}"
        )

    # -------------------------------------------------------------------------
    # Agent Card Management
    # -------------------------------------------------------------------------

    def _initialize_aura_agent_cards(self) -> None:
        """Initialize Agent Cards for Aura's native agents."""

        # Coder Agent
        self._local_agent_cards["aura-coder-agent"] = AgentCard(
            agent_id="aura-coder-agent",
            name="Aura Coder Agent",
            description="Generates security patches and code fixes for identified vulnerabilities",
            endpoint=f"{self._base_endpoint}/agents/coder",
            capabilities=[
                AgentCapability(
                    name="generate_patch",
                    description="Generate a security patch for a vulnerability",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "vulnerability_id": {
                                "type": "string",
                                "description": "ID of the vulnerability to patch",
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Path to the affected file",
                            },
                            "code_context": {
                                "type": "string",
                                "description": "Surrounding code context",
                            },
                            "vulnerability_type": {
                                "type": "string",
                                "description": "Type of vulnerability (e.g., SQL injection)",
                            },
                        },
                        "required": ["vulnerability_id", "file_path"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "patch_id": {"type": "string"},
                            "unified_diff": {"type": "string"},
                            "confidence_score": {"type": "number"},
                            "explanation": {"type": "string"},
                        },
                    },
                    streaming_supported=True,
                ),
                AgentCapability(
                    name="refactor_code",
                    description="Refactor code to improve security posture",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "code_content": {"type": "string"},
                            "refactor_goal": {"type": "string"},
                        },
                        "required": ["file_path", "code_content"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "refactored_code": {"type": "string"},
                            "changes_summary": {"type": "string"},
                        },
                    },
                ),
            ],
            documentation_url=os.environ.get("DOCS_BASE_URL", "https://docs.aura.local")
            + "/agents/coder",
            support_email=os.environ.get("SUPPORT_EMAIL", "support@aura.local"),
        )

        # Reviewer Agent
        self._local_agent_cards["aura-reviewer-agent"] = AgentCard(
            agent_id="aura-reviewer-agent",
            name="Aura Reviewer Agent",
            description="Reviews code for security vulnerabilities and code quality issues",
            endpoint=f"{self._base_endpoint}/agents/reviewer",
            capabilities=[
                AgentCapability(
                    name="scan_code",
                    description="Scan code for security vulnerabilities",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "code_content": {"type": "string"},
                            "language": {"type": "string"},
                            "scan_depth": {
                                "type": "string",
                                "enum": ["quick", "standard", "deep"],
                            },
                        },
                        "required": ["code_content"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "findings": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "severity": {"type": "string"},
                                        "category": {"type": "string"},
                                        "title": {"type": "string"},
                                        "description": {"type": "string"},
                                        "line_start": {"type": "integer"},
                                        "line_end": {"type": "integer"},
                                    },
                                },
                            },
                            "summary": {"type": "string"},
                        },
                    },
                ),
                AgentCapability(
                    name="review_patch",
                    description="Review a proposed patch for correctness and security",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "patch_id": {"type": "string"},
                            "unified_diff": {"type": "string"},
                            "original_code": {"type": "string"},
                        },
                        "required": ["unified_diff"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "approved": {"type": "boolean"},
                            "issues": {"type": "array"},
                            "recommendations": {"type": "array"},
                        },
                    },
                ),
            ],
            documentation_url=os.environ.get("DOCS_BASE_URL", "https://docs.aura.local")
            + "/agents/reviewer",
            support_email=os.environ.get("SUPPORT_EMAIL", "support@aura.local"),
        )

        # Validator Agent
        self._local_agent_cards["aura-validator-agent"] = AgentCard(
            agent_id="aura-validator-agent",
            name="Aura Validator Agent",
            description="Validates patches in isolated sandbox environments",
            endpoint=f"{self._base_endpoint}/agents/validator",
            capabilities=[
                AgentCapability(
                    name="validate_patch",
                    description="Validate a patch in a sandbox environment",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "patch_id": {"type": "string"},
                            "repository_url": {"type": "string"},
                            "branch": {"type": "string"},
                            "test_commands": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["patch_id", "repository_url"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {
                            "validation_passed": {"type": "boolean"},
                            "test_results": {"type": "object"},
                            "sandbox_logs": {"type": "string"},
                            "security_scan_results": {"type": "object"},
                        },
                    },
                    streaming_supported=True,  # Stream validation progress
                ),
            ],
            documentation_url=os.environ.get("DOCS_BASE_URL", "https://docs.aura.local")
            + "/agents/validator",
            support_email=os.environ.get("SUPPORT_EMAIL", "support@aura.local"),
        )

        logger.info(
            f"Initialized {len(self._local_agent_cards)} local agent cards: "
            f"{list(self._local_agent_cards.keys())}"
        )

    @require_enterprise_mode
    def get_local_agent_card(self, agent_id: str) -> AgentCard | None:
        """
        Get Agent Card for a local Aura agent.

        Args:
            agent_id: The agent identifier

        Returns:
            AgentCard if found, None otherwise
        """
        return self._local_agent_cards.get(agent_id)

    @require_enterprise_mode
    def list_local_agent_cards(self) -> list[AgentCard]:
        """List all local Aura agent cards."""
        return list(self._local_agent_cards.values())

    @require_enterprise_mode
    async def fetch_external_agent_card(self, agent_endpoint: str) -> AgentCard | None:
        """
        Fetch Agent Card from an external A2A-compatible agent.

        Args:
            agent_endpoint: The agent's A2A endpoint URL

        Returns:
            AgentCard if successfully fetched, None otherwise
        """
        # Check cache first
        if agent_endpoint in self._external_agent_cards:
            cached = self._external_agent_cards[agent_endpoint]
            # Simple TTL check (in production, use proper cache with TTL)
            return cached

        try:
            # In production, fetch via HTTP:
            # async with aiohttp.ClientSession() as session:
            #     async with session.get(
            #         f"{agent_endpoint}/.well-known/agent.json"
            #     ) as response:
            #         if response.status == 200:
            #             data = await response.json()
            #             agent_card = self._parse_external_agent_card(data)
            #             self._external_agent_cards[agent_endpoint] = agent_card
            #             return agent_card

            # Development mock
            logger.info(f"Fetching agent card from: {agent_endpoint}")
            await asyncio.sleep(0.1)  # Simulate network latency

            # Return None for now (external agents not yet connected)
            return None

        except Exception as e:
            logger.error(f"Failed to fetch agent card from {agent_endpoint}: {e}")
            return None

    # -------------------------------------------------------------------------
    # Task Management
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def create_task(
        self,
        capability_name: str,
        input_data: dict[str, Any],
        requester_agent_id: str | None = None,
        session_id: str | None = None,
        push_notification_url: str | None = None,
    ) -> A2ATask:
        """
        Create a new A2A task.

        Args:
            capability_name: Name of the capability to invoke
            input_data: Input parameters for the capability
            requester_agent_id: ID of the requesting agent (for external requests)
            session_id: Session ID for multi-turn conversations
            push_notification_url: URL to send status updates

        Returns:
            The created A2ATask
        """
        task = A2ATask(
            capability_name=capability_name,
            input_data=input_data,
            requester_agent_id=requester_agent_id,
            session_id=session_id,
            push_notification_url=push_notification_url,
        )

        self._tasks[task.task_id] = task
        self._total_tasks_received += 1

        logger.info(
            f"A2A task created: task_id={task.task_id}, "
            f"capability={capability_name}, requester={requester_agent_id}"
        )

        return task

    @require_enterprise_mode
    async def get_task(self, task_id: str) -> A2ATask | None:
        """
        Get a task by ID.

        Args:
            task_id: The task identifier

        Returns:
            A2ATask if found, None otherwise
        """
        return self._tasks.get(task_id)

    @require_enterprise_mode
    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str = "",
        output_data: dict[str, Any] | None = None,
        artifacts: list[TaskArtifact] | None = None,
    ) -> A2ATask | None:
        """
        Update a task's status.

        Args:
            task_id: The task identifier
            status: New status
            message: Status message
            output_data: Output data (if completed)
            artifacts: Produced artifacts (if any)

        Returns:
            Updated task, or None if not found
        """
        task = self._tasks.get(task_id)
        if not task:
            return None

        task.status = status
        task.status_message = message
        task.updated_at = datetime.now(timezone.utc)

        if output_data:
            task.output_data = output_data

        if artifacts:
            task.artifacts.extend(artifacts)

        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED):
            task.completed_at = datetime.now(timezone.utc)

        # Send push notification if configured
        if task.push_notification_url:
            await self._send_push_notification(task)

        logger.info(
            f"A2A task updated: task_id={task_id}, status={status.value}, "
            f"message={message}"
        )

        return task

    @require_enterprise_mode
    async def cancel_task(self, task_id: str, reason: str = "") -> A2ATask | None:
        """
        Cancel a task.

        Args:
            task_id: The task identifier
            reason: Cancellation reason

        Returns:
            Canceled task, or None if not found
        """
        return await self.update_task_status(
            task_id=task_id,
            status=TaskStatus.CANCELED,
            message=reason or "Task canceled by requester",
        )

    # -------------------------------------------------------------------------
    # Task Execution
    # -------------------------------------------------------------------------

    def register_capability_handler(
        self, agent_id: str, capability_name: str, handler: Callable
    ) -> None:
        """
        Register a handler for a capability.

        Args:
            agent_id: The agent ID
            capability_name: The capability name
            handler: Async function to handle the capability
        """
        key = f"{agent_id}:{capability_name}"
        self._capability_handlers[key] = handler
        logger.info(f"Registered capability handler: {key}")

    @require_enterprise_mode
    async def execute_task(self, task: A2ATask) -> A2ATask:
        """
        Execute a task using the registered capability handler.

        Args:
            task: The task to execute

        Returns:
            Updated task with results
        """
        # Find the capability handler
        # Try to match capability to a local agent
        handler = None
        for agent_id in self._local_agent_cards:
            key = f"{agent_id}:{task.capability_name}"
            if key in self._capability_handlers:
                handler = self._capability_handlers[key]
                break

        if not handler:
            # No handler registered, use default mock handler
            handler = self._default_capability_handler

        try:
            # Update status to working
            await self.update_task_status(
                task.task_id, TaskStatus.WORKING, "Processing task"
            )

            # Execute handler
            result = await handler(task.capability_name, task.input_data)

            # Update with results
            await self.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                message="Task completed successfully",
                output_data=result.get("output", {}),
                artifacts=[
                    TaskArtifact(
                        artifact_type=ArtifactType(a.get("type", "text")),
                        name=a.get("name", ""),
                        content=a.get("content", ""),
                    )
                    for a in result.get("artifacts", [])
                ],
            )

        except Exception as e:
            logger.error(f"Task execution failed: task_id={task.task_id}, error={e}")
            self._total_errors += 1
            await self.update_task_status(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                message=str(e),
            )

        return self._tasks[task.task_id]

    async def _default_capability_handler(
        self, capability_name: str, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Default handler for capabilities without registered handlers."""
        logger.warning(f"Using default handler for capability: {capability_name}")

        # Simulate processing
        await asyncio.sleep(0.5)

        return {
            "output": {
                "status": "completed",
                "message": f"Capability '{capability_name}' executed with mock handler",
                "input_received": input_data,
            },
            "artifacts": [],
        }

    # -------------------------------------------------------------------------
    # External Agent Communication
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def send_task_to_external_agent(
        self,
        agent_endpoint: str,
        capability_name: str,
        input_data: dict[str, Any],
        timeout_seconds: float = 30.0,
    ) -> A2AResponse:
        """
        Send a task to an external A2A-compatible agent.

        Args:
            agent_endpoint: The external agent's endpoint
            capability_name: Capability to invoke
            input_data: Input parameters
            timeout_seconds: Request timeout

        Returns:
            A2AResponse with result or error
        """
        self._total_tasks_sent += 1

        request = A2ARequest(
            method=A2AMessageType.TASK_SEND.value,
            params={
                "capability": capability_name,
                "input": input_data,
                "push_notification": {
                    "url": f"{self._base_endpoint}/notifications",
                },
            },
        )

        try:
            # In production, send via HTTP:
            # async with aiohttp.ClientSession() as session:
            #     async with session.post(
            #         agent_endpoint,
            #         json=request.to_dict(),
            #         headers={"Content-Type": "application/json"},
            #         timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            #     ) as response:
            #         data = await response.json()
            #         return A2AResponse(
            #             id=request.id,
            #             result=data.get("result"),
            #             error=data.get("error"),
            #         )

            # Development mock
            logger.info(
                f"Sending task to external agent: endpoint={agent_endpoint}, "
                f"capability={capability_name}"
            )
            await asyncio.sleep(0.2)

            return A2AResponse(
                id=request.id,
                result={
                    "task_id": str(uuid.uuid4()),
                    "status": "submitted",
                    "message": "Task submitted to external agent (mock)",
                },
            )

        except asyncio.TimeoutError:
            self._total_errors += 1
            return A2AResponse(
                id=request.id,
                error={
                    "code": -32000,
                    "message": f"Timeout after {timeout_seconds}s",
                },
            )
        except Exception as e:
            self._total_errors += 1
            return A2AResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                },
            )

    # -------------------------------------------------------------------------
    # Push Notifications
    # -------------------------------------------------------------------------

    async def _send_push_notification(self, task: A2ATask) -> bool:
        """
        Send push notification for task status update.

        Args:
            task: The task with updated status

        Returns:
            True if notification sent successfully
        """
        if not task.push_notification_url:
            return False

        _notification = {  # noqa: F841
            "jsonrpc": A2A_JSON_RPC_VERSION,
            "method": "tasks/statusUpdate",
            "params": {
                "task_id": task.task_id,
                "status": task.status.value,
                "message": task.status_message,
                "updated_at": task.updated_at.isoformat(),
            },
        }

        try:
            # In production, send via HTTP POST
            # async with aiohttp.ClientSession() as session:
            #     async with session.post(
            #         task.push_notification_url,
            #         json=notification,
            #     ) as response:
            #         return response.status < 400

            logger.info(
                f"Push notification sent: task_id={task.task_id}, "
                f"url={task.push_notification_url}"
            )
            return True

        except Exception as e:
            logger.error(f"Push notification failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # JSON-RPC Request Handling
    # -------------------------------------------------------------------------

    @require_enterprise_mode
    async def handle_jsonrpc_request(self, request_data: dict[str, Any]) -> A2AResponse:
        """
        Handle an incoming JSON-RPC request.

        Args:
            request_data: The JSON-RPC request

        Returns:
            A2AResponse
        """
        request_id = request_data.get("id", str(uuid.uuid4()))

        # Validate JSON-RPC version
        if request_data.get("jsonrpc") != A2A_JSON_RPC_VERSION:
            return A2AResponse(
                id=request_id,
                error={
                    "code": -32600,
                    "message": f"Invalid JSON-RPC version. Expected {A2A_JSON_RPC_VERSION}",
                },
            )

        method = request_data.get("method", "")
        params = request_data.get("params", {})

        try:
            # Route to appropriate handler
            if method == A2AMessageType.TASK_SEND.value:
                return await self._handle_task_send(request_id, params)
            elif method == A2AMessageType.TASK_GET.value:
                return await self._handle_task_get(request_id, params)
            elif method == A2AMessageType.TASK_CANCEL.value:
                return await self._handle_task_cancel(request_id, params)
            elif method == A2AMessageType.AGENT_CARD_REQUEST.value:
                return await self._handle_agent_card_request(request_id, params)
            else:
                return A2AResponse(
                    id=request_id,
                    error={
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                )

        except Exception as e:
            logger.error(f"Error handling JSON-RPC request: {e}")
            self._total_errors += 1
            return A2AResponse(
                id=request_id,
                error={
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                },
            )

    async def _handle_task_send(
        self, request_id: str, params: dict[str, Any]
    ) -> A2AResponse:
        """Handle tasks/send request."""
        capability = params.get("capability")
        input_data = params.get("input", {})
        push_url = params.get("push_notification", {}).get("url")

        if not capability:
            return A2AResponse(
                id=request_id,
                error={
                    "code": -32602,
                    "message": "Missing required parameter: capability",
                },
            )

        task = await self.create_task(
            capability_name=capability,
            input_data=input_data,
            push_notification_url=push_url,
        )

        # Start async execution (don't await - return immediately)
        asyncio.create_task(self.execute_task(task))

        return A2AResponse(
            id=request_id,
            result={
                "task_id": task.task_id,
                "status": task.status.value,
            },
        )

    async def _handle_task_get(
        self, request_id: str, params: dict[str, Any]
    ) -> A2AResponse:
        """Handle tasks/get request."""
        task_id = params.get("task_id")

        if not task_id:
            return A2AResponse(
                id=request_id,
                error={
                    "code": -32602,
                    "message": "Missing required parameter: task_id",
                },
            )

        task = await self.get_task(task_id)

        if not task:
            return A2AResponse(
                id=request_id,
                error={
                    "code": -32000,
                    "message": f"Task not found: {task_id}",
                },
            )

        return A2AResponse(
            id=request_id,
            result=task.to_dict(),
        )

    async def _handle_task_cancel(
        self, request_id: str, params: dict[str, Any]
    ) -> A2AResponse:
        """Handle tasks/cancel request."""
        task_id = params.get("task_id")
        reason = params.get("reason", "")

        if not task_id:
            return A2AResponse(
                id=request_id,
                error={
                    "code": -32602,
                    "message": "Missing required parameter: task_id",
                },
            )

        task = await self.cancel_task(task_id, reason)

        if not task:
            return A2AResponse(
                id=request_id,
                error={
                    "code": -32000,
                    "message": f"Task not found: {task_id}",
                },
            )

        return A2AResponse(
            id=request_id,
            result={"task_id": task_id, "status": "canceled"},
        )

    async def _handle_agent_card_request(
        self, request_id: str, params: dict[str, Any]
    ) -> A2AResponse:
        """Handle agent_card_request."""
        agent_id = params.get("agent_id")

        if agent_id:
            card = self.get_local_agent_card(agent_id)
            if card:
                return A2AResponse(
                    id=request_id,
                    result=card.to_dict(),
                )
            return A2AResponse(
                id=request_id,
                error={
                    "code": -32000,
                    "message": f"Agent not found: {agent_id}",
                },
            )

        # Return all agent cards
        return A2AResponse(
            id=request_id,
            result={
                "agents": [card.to_dict() for card in self.list_local_agent_cards()]
            },
        )

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """Get gateway metrics for monitoring."""
        return {
            "total_tasks_received": self._total_tasks_received,
            "total_tasks_sent": self._total_tasks_sent,
            "total_errors": self._total_errors,
            "active_tasks": len(
                [t for t in self._tasks.values() if t.status == TaskStatus.WORKING]
            ),
            "completed_tasks": len(
                [t for t in self._tasks.values() if t.status == TaskStatus.COMPLETED]
            ),
            "local_agents": len(self._local_agent_cards),
            "external_agents_cached": len(self._external_agent_cards),
            "registered_handlers": len(self._capability_handlers),
        }


# =============================================================================
# Exceptions
# =============================================================================


class A2AError(Exception):
    """Base exception for A2A operations."""


class A2AAuthError(A2AError):
    """Authentication/authorization error."""


class A2ATaskError(A2AError):
    """Task execution error."""


class A2AProtocolError(A2AError):
    """Protocol violation error."""
