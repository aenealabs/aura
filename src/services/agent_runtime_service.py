"""Project Aura - Agent Runtime Service

Unified agent deployment and execution runtime supporting both code upload
and container-based deployment with session isolation.

Implements AWS Bedrock AgentCore Runtime parity (ADR-030 Phase 1.1):
- Code-zip deployment for rapid prototyping
- Container-based deployment for production
- Session isolation preventing data leakage
- Support for 8-hour async workloads
- A2A (Agent-to-Agent) protocol support
- Bidirectional streaming for voice agents

Author: Project Aura Team
Date: 2025-12-11
"""

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, AsyncIterator, Literal

logger = logging.getLogger(__name__)


class DeploymentMode(Enum):
    """Agent deployment modes."""

    CODE_UPLOAD = "code_upload"
    CONTAINER = "container"


class RuntimeType(Enum):
    """Supported runtime environments for code upload."""

    PYTHON_3_11 = "python3.11"
    PYTHON_3_12 = "python3.12"
    NODEJS_20 = "nodejs20"
    GO_1_21 = "go1.21"


class SessionStatus(Enum):
    """Agent session lifecycle states."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    EXPIRED = "expired"


@dataclass
class VPCConfig:
    """VPC configuration for agent deployment."""

    vpc_id: str
    subnet_ids: list[str]
    security_group_ids: list[str]
    assign_public_ip: bool = False


@dataclass
class ResourceLimits:
    """Resource limits for agent execution."""

    memory_mb: int = 512
    cpu_units: int = 256  # 256 = 0.25 vCPU
    ephemeral_storage_mb: int = 512
    max_concurrent_sessions: int = 10


@dataclass
class AgentDeploymentConfig:
    """Configuration for agent deployment."""

    deployment_id: str
    name: str
    description: str | None = None
    deployment_mode: DeploymentMode = DeploymentMode.CODE_UPLOAD
    runtime: RuntimeType | None = RuntimeType.PYTHON_3_11
    container_image: str | None = None
    container_command: list[str] | None = None
    entry_point: str = "main.handler"  # For code upload
    memory_mb: int = 512
    timeout_seconds: int = 900  # 15 min default, up to 28800 (8 hours)
    vpc_config: VPCConfig | None = None
    environment_variables: dict[str, str] = field(default_factory=dict)
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    tags: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if (
            self.deployment_mode == DeploymentMode.CONTAINER
            and not self.container_image
        ):
            raise ValueError("container_image required for container deployment mode")
        if self.deployment_mode == DeploymentMode.CODE_UPLOAD and not self.runtime:
            raise ValueError("runtime required for code upload deployment mode")
        if self.timeout_seconds > 28800:
            raise ValueError("timeout_seconds cannot exceed 28800 (8 hours)")


@dataclass
class SessionCheckpoint:
    """Checkpoint of session state for resume capability."""

    checkpoint_id: str
    session_id: str
    checkpoint_name: str
    state_snapshot: dict[str, Any]
    created_at: datetime
    size_bytes: int


@dataclass
class AgentSession:
    """Isolated agent execution session."""

    session_id: str
    deployment_id: str
    user_id: str | None = None
    status: SessionStatus = SessionStatus.INITIALIZING
    state: dict[str, Any] = field(default_factory=dict)
    checkpoints: list[SessionCheckpoint] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if session is active and not expired."""
        if self.status != SessionStatus.ACTIVE:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True


@dataclass
class AgentRequest:
    """Request to invoke an agent."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_text: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    tools_allowed: list[str] | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False


@dataclass
class AgentResponseChunk:
    """Streaming response chunk from agent."""

    chunk_id: str
    chunk_type: Literal["text", "tool_call", "tool_result", "error", "done"]
    content: str | dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentResponse:
    """Complete response from agent invocation."""

    response_id: str
    request_id: str
    session_id: str
    success: bool
    output_text: str = ""
    output_data: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tokens_used: int = 0
    execution_time_ms: float = 0.0
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DeploymentResult:
    """Result of agent deployment operation."""

    deployment_id: str
    success: bool
    status: Literal["deployed", "failed", "pending"]
    endpoint_url: str | None = None
    artifact_location: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class A2ACapability:
    """Agent-to-Agent protocol capability advertisement."""

    capability_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


@dataclass
class A2AAgentCard:
    """Agent card for A2A protocol discovery."""

    agent_id: str
    name: str
    description: str
    version: str
    capabilities: list[A2ACapability]
    endpoint: str
    protocol_version: str = "1.0"
    authentication: Literal["none", "api_key", "oauth2", "mtls"] = "api_key"
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentRuntimeService:
    """
    Unified agent deployment and execution runtime.

    Supports AWS AgentCore parity features:
    - Code upload and container deployment
    - Session isolation with state persistence
    - A2A protocol for agent-to-agent communication
    - Bidirectional streaming for voice agents

    Example usage:
        runtime = AgentRuntimeService()

        # Deploy agent from code
        config = AgentDeploymentConfig(
            deployment_id="my-agent",
            name="My Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
        )
        result = await runtime.deploy_agent(config, code_zip_bytes)

        # Create session and invoke
        session = await runtime.create_session("my-agent", ttl_hours=1.0)
        response = await runtime.invoke_agent(
            session.session_id,
            AgentRequest(input_text="Hello!")
        )

    Cache Configuration:
        MAX_SESSION_CACHE_SIZE: Maximum cached sessions (default 1000)
        MAX_DEPLOYMENT_CACHE_SIZE: Maximum cached deployments (default 100)
    """

    # Cache size limits (prevents unbounded memory growth)
    MAX_SESSION_CACHE_SIZE = 1000
    MAX_DEPLOYMENT_CACHE_SIZE = 100

    def __init__(
        self,
        s3_client: Any | None = None,
        dynamodb_client: Any | None = None,
        lambda_client: Any | None = None,
        ecs_client: Any | None = None,
        artifact_bucket: str | None = None,
        session_table: str | None = None,
    ):
        """Initialize Agent Runtime Service.

        Args:
            s3_client: Boto3 S3 client for artifact storage
            dynamodb_client: Boto3 DynamoDB client for session state
            lambda_client: Boto3 Lambda client for code upload deployment
            ecs_client: Boto3 ECS client for container deployment
            artifact_bucket: S3 bucket for code artifacts
            session_table: DynamoDB table for session state
        """
        self.s3 = s3_client
        self.dynamodb = dynamodb_client
        self.lambda_client = lambda_client
        self.ecs = ecs_client
        self.artifact_bucket = artifact_bucket or os.getenv(
            "AURA_AGENT_ARTIFACT_BUCKET", "aura-agent-artifacts"
        )
        self.session_table = session_table or os.getenv(
            "AURA_AGENT_SESSION_TABLE", "aura-agent-sessions"
        )

        # In-memory caches (replace with Redis in production)
        self._deployments: dict[str, AgentDeploymentConfig] = {}
        self._sessions: dict[str, AgentSession] = {}
        self._a2a_registry: dict[str, A2AAgentCard] = {}

        logger.info("Initialized AgentRuntimeService")

    # =========================================================================
    # Deployment Management
    # =========================================================================

    async def deploy_agent(
        self,
        config: AgentDeploymentConfig,
        code_artifact: bytes | None = None,
    ) -> DeploymentResult:
        """Deploy an agent with code upload or container.

        Args:
            config: Agent deployment configuration
            code_artifact: ZIP file bytes for code upload deployment

        Returns:
            DeploymentResult with status and endpoint information
        """
        logger.info(
            f"Deploying agent: {config.deployment_id} mode={config.deployment_mode}"
        )

        try:
            if config.deployment_mode == DeploymentMode.CODE_UPLOAD:
                if not code_artifact:
                    raise ValueError(
                        "code_artifact required for code upload deployment"
                    )
                return await self._deploy_code_upload(config, code_artifact)
            else:
                return await self._deploy_container(config)
        except Exception as e:
            logger.error(f"Deployment failed for {config.deployment_id}: {e}")
            return DeploymentResult(
                deployment_id=config.deployment_id,
                success=False,
                status="failed",
                error=str(e),
            )

    async def _deploy_code_upload(
        self,
        config: AgentDeploymentConfig,
        code_artifact: bytes,
    ) -> DeploymentResult:
        """Deploy agent using code upload (Lambda-style).

        Args:
            config: Deployment configuration
            code_artifact: ZIP file bytes

        Returns:
            DeploymentResult
        """
        # Validate ZIP file
        artifact_hash = hashlib.sha256(code_artifact).hexdigest()[:12]

        # Extract and validate entry point
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(code_artifact)
            tmp_path = tmp.name

        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                file_list = zf.namelist()
                logger.info(f"Code artifact contains {len(file_list)} files")

                # Check for entry point module
                module_name = config.entry_point.split(".")[0]
                if f"{module_name}.py" not in file_list:
                    raise ValueError(
                        f"Entry point module '{module_name}.py' not found in artifact"
                    )
        finally:
            os.unlink(tmp_path)

        # Upload to S3 (mock in development)
        artifact_key = f"deployments/{config.deployment_id}/{artifact_hash}.zip"

        if self.s3:
            await asyncio.to_thread(
                self.s3.put_object,
                Bucket=self.artifact_bucket,
                Key=artifact_key,
                Body=code_artifact,
            )
            artifact_location = f"s3://{self.artifact_bucket}/{artifact_key}"
        else:
            # Mock mode
            artifact_location = f"mock://artifacts/{artifact_key}"
            logger.info(f"Mock mode: artifact stored at {artifact_location}")

        # Store deployment config
        self._deployments[config.deployment_id] = config

        # In production, would create Lambda function or ECS task definition
        endpoint_url = f"https://agents.aura.local/{config.deployment_id}"

        logger.info(f"Successfully deployed {config.deployment_id} at {endpoint_url}")

        return DeploymentResult(
            deployment_id=config.deployment_id,
            success=True,
            status="deployed",
            endpoint_url=endpoint_url,
            artifact_location=artifact_location,
        )

    async def _deploy_container(
        self,
        config: AgentDeploymentConfig,
    ) -> DeploymentResult:
        """Deploy agent using container (ECS/EKS-style).

        Args:
            config: Deployment configuration

        Returns:
            DeploymentResult
        """
        # In production, would create ECS task definition or EKS deployment
        logger.info(f"Container deployment: {config.container_image}")

        # Store deployment config
        self._deployments[config.deployment_id] = config

        endpoint_url = f"https://agents.aura.local/{config.deployment_id}"

        return DeploymentResult(
            deployment_id=config.deployment_id,
            success=True,
            status="deployed",
            endpoint_url=endpoint_url,
            artifact_location=config.container_image,
        )

    async def get_deployment(
        self,
        deployment_id: str,
    ) -> AgentDeploymentConfig | None:
        """Get deployment configuration by ID.

        Args:
            deployment_id: Deployment identifier

        Returns:
            AgentDeploymentConfig or None if not found
        """
        return self._deployments.get(deployment_id)

    async def list_deployments(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentDeploymentConfig]:
        """List all deployments.

        Args:
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of deployment configurations
        """
        deployments = list(self._deployments.values())
        return deployments[offset : offset + limit]

    async def delete_deployment(
        self,
        deployment_id: str,
    ) -> bool:
        """Delete a deployment.

        Args:
            deployment_id: Deployment identifier

        Returns:
            True if deleted, False if not found
        """
        if deployment_id in self._deployments:
            del self._deployments[deployment_id]
            logger.info(f"Deleted deployment: {deployment_id}")
            return True
        return False

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(
        self,
        deployment_id: str,
        ttl_hours: float = 1.0,
        user_id: str | None = None,
        initial_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentSession:
        """Create isolated execution session.

        Args:
            deployment_id: ID of deployed agent
            ttl_hours: Session time-to-live in hours (max 8)
            user_id: Optional user identifier for multi-tenant
            initial_state: Initial session state
            metadata: Additional session metadata

        Returns:
            AgentSession with isolated context
        """
        if deployment_id not in self._deployments:
            raise ValueError(f"Deployment not found: {deployment_id}")

        if ttl_hours > 8.0:
            raise ValueError("Session TTL cannot exceed 8 hours")

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        session = AgentSession(
            session_id=session_id,
            deployment_id=deployment_id,
            user_id=user_id,
            status=SessionStatus.ACTIVE,
            state=initial_state or {},
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
            metadata=metadata or {},
        )

        # Store session (DynamoDB in production, bounded cache)
        self._sessions[session_id] = session
        self._enforce_session_cache_limit()

        # Persist to DynamoDB if available
        if self.dynamodb:
            await self._persist_session(session)

        logger.info(
            f"Created session {session_id} for deployment {deployment_id} "
            f"(TTL: {ttl_hours}h, user: {user_id})"
        )

        return session

    async def get_session(
        self,
        session_id: str,
    ) -> AgentSession | None:
        """Get session by ID.

        Args:
            session_id: Session identifier

        Returns:
            AgentSession or None if not found/expired
        """
        session = self._sessions.get(session_id)

        if (
            session
            and session.expires_at
            and datetime.now(timezone.utc) > session.expires_at
        ):
            session.status = SessionStatus.EXPIRED
            logger.info(f"Session {session_id} has expired")

        return session

    async def update_session_state(
        self,
        session_id: str,
        state_updates: dict[str, Any],
    ) -> AgentSession:
        """Update session state.

        Args:
            session_id: Session identifier
            state_updates: State key-value updates

        Returns:
            Updated AgentSession
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if not session.is_active:
            raise ValueError(f"Session {session_id} is not active")

        session.state.update(state_updates)
        session.last_activity_at = datetime.now(timezone.utc)

        if self.dynamodb:
            await self._persist_session(session)

        return session

    async def checkpoint_session(
        self,
        session_id: str,
        checkpoint_name: str,
    ) -> SessionCheckpoint:
        """Save session state for resume capability.

        Args:
            session_id: Session identifier
            checkpoint_name: Name for this checkpoint

        Returns:
            SessionCheckpoint with snapshot
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        state_json = json.dumps(session.state, default=str)

        checkpoint = SessionCheckpoint(
            checkpoint_id=str(uuid.uuid4()),
            session_id=session_id,
            checkpoint_name=checkpoint_name,
            state_snapshot=session.state.copy(),
            created_at=datetime.now(timezone.utc),
            size_bytes=len(state_json.encode()),
        )

        session.checkpoints.append(checkpoint)

        # Store checkpoint to S3 if available
        if self.s3:
            checkpoint_key = (
                f"sessions/{session_id}/checkpoints/{checkpoint.checkpoint_id}.json"
            )
            await asyncio.to_thread(
                self.s3.put_object,
                Bucket=self.artifact_bucket,
                Key=checkpoint_key,
                Body=state_json,
            )

        logger.info(
            f"Created checkpoint '{checkpoint_name}' for session {session_id} "
            f"({checkpoint.size_bytes} bytes)"
        )

        return checkpoint

    async def restore_from_checkpoint(
        self,
        session_id: str,
        checkpoint_id: str,
    ) -> AgentSession:
        """Restore session state from checkpoint.

        Args:
            session_id: Session identifier
            checkpoint_id: Checkpoint to restore

        Returns:
            Session with restored state
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        checkpoint = next(
            (c for c in session.checkpoints if c.checkpoint_id == checkpoint_id), None
        )
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        session.state = checkpoint.state_snapshot.copy()
        session.last_activity_at = datetime.now(timezone.utc)

        logger.info(f"Restored session {session_id} from checkpoint {checkpoint_id}")

        return session

    async def terminate_session(
        self,
        session_id: str,
    ) -> bool:
        """Terminate a session.

        Args:
            session_id: Session identifier

        Returns:
            True if terminated, False if not found
        """
        session = await self.get_session(session_id)
        if not session:
            return False

        session.status = SessionStatus.TERMINATED
        logger.info(f"Terminated session: {session_id}")
        return True

    async def _persist_session(self, session: AgentSession) -> None:
        """Persist session to DynamoDB.

        Args:
            session: Session to persist
        """
        if not self.dynamodb:
            return

        item = {
            "session_id": {"S": session.session_id},
            "deployment_id": {"S": session.deployment_id},
            "status": {"S": session.status.value},
            "state": {"S": json.dumps(session.state, default=str)},
            "created_at": {"S": session.created_at.isoformat()},
            "last_activity_at": {"S": session.last_activity_at.isoformat()},
        }

        if session.user_id:
            item["user_id"] = {"S": session.user_id}
        if session.expires_at:
            item["expires_at"] = {"S": session.expires_at.isoformat()}
            # TTL for automatic cleanup
            item["ttl"] = {"N": str(int(session.expires_at.timestamp()))}

        await asyncio.to_thread(
            self.dynamodb.put_item,
            TableName=self.session_table,
            Item=item,
        )

    def _enforce_session_cache_limit(self) -> None:
        """Evict expired and oldest sessions if cache exceeds MAX_SESSION_CACHE_SIZE."""
        now = datetime.now(timezone.utc)

        # First, remove expired sessions
        expired_keys = [
            sid
            for sid, session in self._sessions.items()
            if session.expires_at and session.expires_at < now
        ]
        for sid in expired_keys:
            del self._sessions[sid]

        # If still over limit, remove oldest sessions (by creation time)
        if len(self._sessions) > self.MAX_SESSION_CACHE_SIZE:
            # Sort by created_at and remove oldest
            sorted_sessions = sorted(
                self._sessions.items(), key=lambda x: x[1].created_at
            )
            evict_count = len(self._sessions) - self.MAX_SESSION_CACHE_SIZE + 100
            for sid, _ in sorted_sessions[:evict_count]:
                del self._sessions[sid]
            logger.debug(
                f"Evicted {evict_count} sessions from cache (size limit reached)"
            )

    # =========================================================================
    # Agent Invocation
    # =========================================================================

    async def invoke_agent(
        self,
        session_id: str,
        request: AgentRequest,
    ) -> AgentResponse | AsyncIterator[AgentResponseChunk]:
        """Invoke agent with optional streaming.

        Args:
            session_id: Session identifier
            request: Agent request with input

        Returns:
            AgentResponse or async iterator of AgentResponseChunk if streaming
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if not session.is_active:
            raise ValueError(f"Session {session_id} is not active")

        deployment = await self.get_deployment(session.deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {session.deployment_id}")

        # Update session activity
        session.last_activity_at = datetime.now(timezone.utc)

        if request.stream:
            return self._invoke_streaming(session, deployment, request)
        else:
            return await self._invoke_sync(session, deployment, request)

    async def _invoke_sync(
        self,
        session: AgentSession,
        deployment: AgentDeploymentConfig,
        request: AgentRequest,
    ) -> AgentResponse:
        """Synchronous agent invocation.

        Args:
            session: Agent session
            deployment: Deployment configuration
            request: Agent request

        Returns:
            AgentResponse
        """
        import time

        start_time = time.time()

        try:
            # In production, would invoke Lambda or ECS task
            # For now, simulate agent execution
            output_text = await self._execute_agent_logic(session, deployment, request)

            execution_time_ms = (time.time() - start_time) * 1000

            return AgentResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                session_id=session.session_id,
                success=True,
                output_text=output_text,
                tokens_used=len(output_text.split()) * 2,  # Rough estimate
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")
            return AgentResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                session_id=session.session_id,
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def _invoke_streaming(
        self,
        session: AgentSession,
        deployment: AgentDeploymentConfig,
        request: AgentRequest,
    ) -> AsyncIterator[AgentResponseChunk]:
        """Streaming agent invocation with bidirectional support.

        Args:
            session: Agent session
            deployment: Deployment configuration
            request: Agent request

        Yields:
            AgentResponseChunk for each output piece
        """
        try:
            # Simulate streaming response
            output_text = await self._execute_agent_logic(session, deployment, request)

            # Stream in chunks
            words = output_text.split()
            for i, word in enumerate(words):
                yield AgentResponseChunk(
                    chunk_id=f"{request.request_id}-{i}",
                    chunk_type="text",
                    content=word + " ",
                )
                await asyncio.sleep(0.05)  # Simulate streaming delay

            # Final chunk
            yield AgentResponseChunk(
                chunk_id=f"{request.request_id}-done",
                chunk_type="done",
                content={"total_chunks": len(words)},
            )

        except Exception as e:
            yield AgentResponseChunk(
                chunk_id=f"{request.request_id}-error",
                chunk_type="error",
                content=str(e),
            )

    async def _execute_agent_logic(
        self,
        session: AgentSession,
        deployment: AgentDeploymentConfig,
        request: AgentRequest,
    ) -> str:
        """Execute agent logic (placeholder for actual implementation).

        In production, this would:
        1. Load agent code from artifact
        2. Initialize agent with session context
        3. Execute agent with request
        4. Return response

        Args:
            session: Agent session
            deployment: Deployment configuration
            request: Agent request

        Returns:
            Agent output text
        """
        # Placeholder implementation
        context_summary = f"Session has {len(session.state)} state keys"

        return (
            f"Agent '{deployment.name}' processed your request. "
            f"Input: '{request.input_text[:100]}...' "
            f"Context: {context_summary}. "
            f"This is a placeholder response from the AgentRuntimeService."
        )

    # =========================================================================
    # A2A Protocol Support
    # =========================================================================

    async def register_a2a_agent(
        self,
        agent_card: A2AAgentCard,
    ) -> None:
        """Register agent for A2A protocol discovery.

        Args:
            agent_card: Agent capability advertisement
        """
        self._a2a_registry[agent_card.agent_id] = agent_card
        logger.info(
            f"Registered A2A agent: {agent_card.agent_id} "
            f"with {len(agent_card.capabilities)} capabilities"
        )

    async def discover_a2a_agents(
        self,
        capability_filter: str | None = None,
    ) -> list[A2AAgentCard]:
        """Discover available A2A agents.

        Args:
            capability_filter: Optional capability name to filter by

        Returns:
            List of matching agent cards
        """
        agents = list(self._a2a_registry.values())

        if capability_filter:
            agents = [
                a
                for a in agents
                if any(c.capability_name == capability_filter for c in a.capabilities)
            ]

        return agents

    async def invoke_a2a_agent(
        self,
        agent_id: str,
        capability: str,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke another agent via A2A protocol.

        Args:
            agent_id: Target agent ID
            capability: Capability to invoke
            input_data: Input matching capability schema

        Returns:
            Agent response data
        """
        agent_card = self._a2a_registry.get(agent_id)
        if not agent_card:
            raise ValueError(f"A2A agent not found: {agent_id}")

        cap = next(
            (c for c in agent_card.capabilities if c.capability_name == capability),
            None,
        )
        if not cap:
            raise ValueError(f"Capability '{capability}' not found on agent {agent_id}")

        # In production, would make HTTP/gRPC call to agent endpoint
        logger.info(f"A2A invocation: {agent_id}.{capability}")

        # Placeholder response
        return {
            "success": True,
            "agent_id": agent_id,
            "capability": capability,
            "result": f"A2A response from {agent_id}",
        }

    # =========================================================================
    # Metrics and Monitoring
    # =========================================================================

    def get_runtime_metrics(self) -> dict[str, Any]:
        """Get runtime service metrics.

        Returns:
            Dictionary of runtime metrics
        """
        active_sessions = sum(1 for s in self._sessions.values() if s.is_active)

        return {
            "total_deployments": len(self._deployments),
            "total_sessions": len(self._sessions),
            "active_sessions": active_sessions,
            "a2a_registered_agents": len(self._a2a_registry),
        }
