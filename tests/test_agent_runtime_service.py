"""
Tests for Agent Runtime Service

Tests for the unified agent deployment and execution runtime.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# ==================== Enum Tests ====================


class TestDeploymentMode:
    """Tests for DeploymentMode enum."""

    def test_values(self):
        """Test deployment mode values."""
        from src.services.agent_runtime_service import DeploymentMode

        assert DeploymentMode.CODE_UPLOAD.value == "code_upload"
        assert DeploymentMode.CONTAINER.value == "container"


class TestRuntimeType:
    """Tests for RuntimeType enum."""

    def test_values(self):
        """Test runtime type values."""
        from src.services.agent_runtime_service import RuntimeType

        assert RuntimeType.PYTHON_3_11.value == "python3.11"
        assert RuntimeType.PYTHON_3_12.value == "python3.12"
        assert RuntimeType.NODEJS_20.value == "nodejs20"
        assert RuntimeType.GO_1_21.value == "go1.21"


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_values(self):
        """Test session status values."""
        from src.services.agent_runtime_service import SessionStatus

        assert SessionStatus.INITIALIZING.value == "initializing"
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.SUSPENDED.value == "suspended"
        assert SessionStatus.TERMINATED.value == "terminated"
        assert SessionStatus.EXPIRED.value == "expired"


# ==================== VPCConfig Tests ====================


class TestVPCConfig:
    """Tests for VPCConfig dataclass."""

    def test_creation(self):
        """Test VPC config creation."""
        from src.services.agent_runtime_service import VPCConfig

        config = VPCConfig(
            vpc_id="vpc-12345",
            subnet_ids=["subnet-1", "subnet-2"],
            security_group_ids=["sg-1"],
        )
        assert config.vpc_id == "vpc-12345"
        assert len(config.subnet_ids) == 2
        assert config.assign_public_ip is False

    def test_with_public_ip(self):
        """Test VPC config with public IP."""
        from src.services.agent_runtime_service import VPCConfig

        config = VPCConfig(
            vpc_id="vpc-12345",
            subnet_ids=["subnet-1"],
            security_group_ids=["sg-1"],
            assign_public_ip=True,
        )
        assert config.assign_public_ip is True


# ==================== ResourceLimits Tests ====================


class TestResourceLimits:
    """Tests for ResourceLimits dataclass."""

    def test_default_values(self):
        """Test default resource limits."""
        from src.services.agent_runtime_service import ResourceLimits

        limits = ResourceLimits()
        assert limits.memory_mb == 512
        assert limits.cpu_units == 256
        assert limits.ephemeral_storage_mb == 512
        assert limits.max_concurrent_sessions == 10

    def test_custom_values(self):
        """Test custom resource limits."""
        from src.services.agent_runtime_service import ResourceLimits

        limits = ResourceLimits(
            memory_mb=1024,
            cpu_units=512,
            ephemeral_storage_mb=2048,
            max_concurrent_sessions=20,
        )
        assert limits.memory_mb == 1024
        assert limits.cpu_units == 512


# ==================== AgentDeploymentConfig Tests ====================


class TestAgentDeploymentConfig:
    """Tests for AgentDeploymentConfig dataclass."""

    def test_code_upload_deployment(self):
        """Test code upload deployment config."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            DeploymentMode,
            RuntimeType,
        )

        config = AgentDeploymentConfig(
            deployment_id="agent-001",
            name="Test Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
        )
        assert config.deployment_id == "agent-001"
        assert config.name == "Test Agent"
        assert config.entry_point == "main.handler"
        assert config.timeout_seconds == 900

    def test_container_deployment(self):
        """Test container deployment config."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            DeploymentMode,
        )

        config = AgentDeploymentConfig(
            deployment_id="agent-002",
            name="Container Agent",
            deployment_mode=DeploymentMode.CONTAINER,
            container_image="my-registry/my-agent:latest",
        )
        assert config.container_image == "my-registry/my-agent:latest"

    def test_container_without_image_raises(self):
        """Test container deployment without image raises error."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            DeploymentMode,
        )

        with pytest.raises(ValueError, match="container_image required"):
            AgentDeploymentConfig(
                deployment_id="agent-003",
                name="Bad Container",
                deployment_mode=DeploymentMode.CONTAINER,
            )

    def test_code_upload_without_runtime_raises(self):
        """Test code upload without runtime raises error."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            DeploymentMode,
        )

        with pytest.raises(ValueError, match="runtime required"):
            AgentDeploymentConfig(
                deployment_id="agent-004",
                name="Bad Code Upload",
                deployment_mode=DeploymentMode.CODE_UPLOAD,
                runtime=None,
            )

    def test_timeout_exceeds_limit_raises(self):
        """Test timeout exceeding 8 hours raises error."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            DeploymentMode,
            RuntimeType,
        )

        with pytest.raises(ValueError, match="cannot exceed 28800"):
            AgentDeploymentConfig(
                deployment_id="agent-005",
                name="Long Running",
                deployment_mode=DeploymentMode.CODE_UPLOAD,
                runtime=RuntimeType.PYTHON_3_11,
                timeout_seconds=30000,  # More than 8 hours
            )


# ==================== SessionCheckpoint Tests ====================


class TestSessionCheckpoint:
    """Tests for SessionCheckpoint dataclass."""

    def test_creation(self):
        """Test checkpoint creation."""
        from src.services.agent_runtime_service import SessionCheckpoint

        checkpoint = SessionCheckpoint(
            checkpoint_id="chk-001",
            session_id="sess-001",
            checkpoint_name="before_tool_call",
            state_snapshot={"key": "value"},
            created_at=datetime.now(timezone.utc),
            size_bytes=128,
        )
        assert checkpoint.checkpoint_id == "chk-001"
        assert checkpoint.checkpoint_name == "before_tool_call"
        assert checkpoint.size_bytes == 128


# ==================== AgentSession Tests ====================


class TestAgentSession:
    """Tests for AgentSession dataclass."""

    def test_creation(self):
        """Test session creation."""
        from src.services.agent_runtime_service import AgentSession, SessionStatus

        session = AgentSession(session_id="sess-001", deployment_id="agent-001")
        assert session.session_id == "sess-001"
        assert session.status == SessionStatus.INITIALIZING
        assert session.state == {}
        assert session.checkpoints == []

    def test_is_active_when_active(self):
        """Test is_active returns True when active."""
        from src.services.agent_runtime_service import AgentSession, SessionStatus

        session = AgentSession(
            session_id="sess-001",
            deployment_id="agent-001",
            status=SessionStatus.ACTIVE,
        )
        assert session.is_active is True

    def test_is_active_when_not_active(self):
        """Test is_active returns False when not active."""
        from src.services.agent_runtime_service import AgentSession, SessionStatus

        session = AgentSession(
            session_id="sess-001",
            deployment_id="agent-001",
            status=SessionStatus.TERMINATED,
        )
        assert session.is_active is False

    def test_is_active_when_expired(self):
        """Test is_active returns False when expired."""
        from src.services.agent_runtime_service import AgentSession, SessionStatus

        session = AgentSession(
            session_id="sess-001",
            deployment_id="agent-001",
            status=SessionStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert session.is_active is False


# ==================== AgentRequest Tests ====================


class TestAgentRequest:
    """Tests for AgentRequest dataclass."""

    def test_default_values(self):
        """Test default request values."""
        from src.services.agent_runtime_service import AgentRequest

        request = AgentRequest()
        assert request.input_text == ""
        assert request.max_tokens == 4096
        assert request.temperature == 0.7
        assert request.stream is False
        assert request.request_id is not None

    def test_custom_values(self):
        """Test custom request values."""
        from src.services.agent_runtime_service import AgentRequest

        request = AgentRequest(
            input_text="Hello!",
            max_tokens=1024,
            temperature=0.5,
            stream=True,
            tools_allowed=["web_search", "calculator"],
        )
        assert request.input_text == "Hello!"
        assert request.max_tokens == 1024
        assert len(request.tools_allowed) == 2


# ==================== AgentResponseChunk Tests ====================


class TestAgentResponseChunk:
    """Tests for AgentResponseChunk dataclass."""

    def test_text_chunk(self):
        """Test text response chunk."""
        from src.services.agent_runtime_service import AgentResponseChunk

        chunk = AgentResponseChunk(
            chunk_id="chunk-001", chunk_type="text", content="Hello, "
        )
        assert chunk.chunk_type == "text"
        assert chunk.content == "Hello, "

    def test_tool_call_chunk(self):
        """Test tool call chunk."""
        from src.services.agent_runtime_service import AgentResponseChunk

        chunk = AgentResponseChunk(
            chunk_id="chunk-002",
            chunk_type="tool_call",
            content={"tool": "web_search", "args": {"query": "weather"}},
        )
        assert chunk.chunk_type == "tool_call"
        assert chunk.content["tool"] == "web_search"


# ==================== AgentResponse Tests ====================


class TestAgentResponse:
    """Tests for AgentResponse dataclass."""

    def test_success_response(self):
        """Test successful response."""
        from src.services.agent_runtime_service import AgentResponse

        response = AgentResponse(
            response_id="resp-001",
            request_id="req-001",
            session_id="sess-001",
            success=True,
            output_text="The weather is sunny.",
            tokens_used=150,
            execution_time_ms=500.0,
        )
        assert response.success is True
        assert response.tokens_used == 150
        assert response.error is None

    def test_error_response(self):
        """Test error response."""
        from src.services.agent_runtime_service import AgentResponse

        response = AgentResponse(
            response_id="resp-002",
            request_id="req-002",
            session_id="sess-001",
            success=False,
            error="Tool execution failed",
        )
        assert response.success is False
        assert response.error == "Tool execution failed"


# ==================== DeploymentResult Tests ====================


class TestDeploymentResult:
    """Tests for DeploymentResult dataclass."""

    def test_successful_deployment(self):
        """Test successful deployment result."""
        from src.services.agent_runtime_service import DeploymentResult

        result = DeploymentResult(
            deployment_id="agent-001",
            success=True,
            status="deployed",
            endpoint_url="https://api.example.com/agent-001",
        )
        assert result.success is True
        assert result.status == "deployed"

    def test_failed_deployment(self):
        """Test failed deployment result."""
        from src.services.agent_runtime_service import DeploymentResult

        result = DeploymentResult(
            deployment_id="agent-002",
            success=False,
            status="failed",
            error="Container image not found",
        )
        assert result.success is False
        assert result.error == "Container image not found"


# ==================== A2A Protocol Tests ====================


class TestA2ACapability:
    """Tests for A2ACapability dataclass."""

    def test_creation(self):
        """Test capability creation."""
        from src.services.agent_runtime_service import A2ACapability

        capability = A2ACapability(
            capability_name="summarize",
            description="Summarize text content",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}},
            output_schema={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
            },
        )
        assert capability.capability_name == "summarize"
        assert "text" in capability.input_schema["properties"]


class TestA2AAgentCard:
    """Tests for A2AAgentCard dataclass."""

    def test_creation(self):
        """Test agent card creation."""
        from src.services.agent_runtime_service import A2AAgentCard, A2ACapability

        capability = A2ACapability(
            capability_name="summarize",
            description="Summarize text",
            input_schema={},
            output_schema={},
        )

        card = A2AAgentCard(
            agent_id="agent-001",
            name="Summarizer",
            description="Summarizes content",
            version="1.0.0",
            capabilities=[capability],
            endpoint="https://api.example.com/agent-001",
        )
        assert card.agent_id == "agent-001"
        assert len(card.capabilities) == 1
        assert card.protocol_version == "1.0"
        assert card.authentication == "api_key"


# ==================== AgentRuntimeService Tests ====================


class TestAgentRuntimeService:
    """Tests for AgentRuntimeService."""

    def test_initialization(self):
        """Test service initialization."""
        from src.services.agent_runtime_service import AgentRuntimeService

        service = AgentRuntimeService()
        assert service is not None
        assert service._deployments == {}
        assert service._sessions == {}
        assert service._a2a_registry == {}

    def test_initialization_with_clients(self):
        """Test service initialization with clients."""
        from src.services.agent_runtime_service import AgentRuntimeService

        mock_s3 = MagicMock()
        mock_dynamodb = MagicMock()

        service = AgentRuntimeService(
            s3_client=mock_s3,
            dynamodb_client=mock_dynamodb,
            artifact_bucket="my-bucket",
            session_table="my-table",
        )
        assert service.s3 == mock_s3
        assert service.dynamodb == mock_dynamodb
        assert service.artifact_bucket == "my-bucket"
        assert service.session_table == "my-table"

    @pytest.mark.asyncio
    async def test_deploy_agent_code_upload(self):
        """Test deploying agent with code upload."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            AgentRuntimeService,
            DeploymentMode,
            RuntimeType,
        )

        service = AgentRuntimeService()

        config = AgentDeploymentConfig(
            deployment_id="test-agent",
            name="Test Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
        )

        # Mock code artifact
        code_bytes = b"fake code zip content"

        result = await service.deploy_agent(config, code_bytes)
        assert result is not None
        assert result.deployment_id == "test-agent"

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a session."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            AgentRuntimeService,
            DeploymentMode,
            RuntimeType,
        )

        service = AgentRuntimeService()

        # First deploy an agent with code artifact
        config = AgentDeploymentConfig(
            deployment_id="test-agent",
            name="Test Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
        )
        code_artifact = b"fake zip content"
        await service.deploy_agent(config, code_artifact)

        # For in-memory testing, manually register the deployment
        service._deployments["test-agent"] = config

        # Create session
        session = await service.create_session("test-agent", ttl_hours=1.0)
        assert session is not None
        assert session.deployment_id == "test-agent"

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test getting a session."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            AgentRuntimeService,
            DeploymentMode,
            RuntimeType,
        )

        service = AgentRuntimeService()

        # Deploy and create session
        config = AgentDeploymentConfig(
            deployment_id="test-agent",
            name="Test Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
        )
        # Register deployment directly for testing
        service._deployments["test-agent"] = config

        session = await service.create_session("test-agent")

        # Retrieve session
        retrieved = await service.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_get_session_not_found(self):
        """Test getting non-existent session."""
        from src.services.agent_runtime_service import AgentRuntimeService

        service = AgentRuntimeService()
        session = await service.get_session("nonexistent")
        assert session is None

    @pytest.mark.asyncio
    async def test_terminate_session(self):
        """Test terminating a session."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            AgentRuntimeService,
            DeploymentMode,
            RuntimeType,
            SessionStatus,
        )

        service = AgentRuntimeService()

        # Register deployment directly for testing
        config = AgentDeploymentConfig(
            deployment_id="test-agent",
            name="Test Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
        )
        service._deployments["test-agent"] = config
        session = await service.create_session("test-agent")

        # Terminate session
        result = await service.terminate_session(session.session_id)
        assert result is True

        # Verify terminated
        terminated = await service.get_session(session.session_id)
        assert terminated.status == SessionStatus.TERMINATED

    @pytest.mark.asyncio
    async def test_list_deployments(self):
        """Test listing deployments."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            AgentRuntimeService,
            DeploymentMode,
            RuntimeType,
        )

        service = AgentRuntimeService()

        # Register deployments directly for testing
        for i in range(3):
            config = AgentDeploymentConfig(
                deployment_id=f"agent-{i}",
                name=f"Agent {i}",
                deployment_mode=DeploymentMode.CODE_UPLOAD,
                runtime=RuntimeType.PYTHON_3_11,
            )
            service._deployments[f"agent-{i}"] = config

        deployments = await service.list_deployments()
        assert len(deployments) >= 3

    @pytest.mark.asyncio
    async def test_invoke_agent(self):
        """Test invoking an agent."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            AgentRequest,
            AgentRuntimeService,
            DeploymentMode,
            RuntimeType,
        )

        service = AgentRuntimeService()

        # Register deployment directly for testing
        config = AgentDeploymentConfig(
            deployment_id="test-agent",
            name="Test Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
        )
        service._deployments["test-agent"] = config
        session = await service.create_session("test-agent")

        # Invoke
        request = AgentRequest(input_text="Hello!")
        response = await service.invoke_agent(session.session_id, request)
        assert response is not None
        assert response.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_register_a2a_agent(self):
        """Test registering agent for A2A protocol."""
        from src.services.agent_runtime_service import (
            A2AAgentCard,
            A2ACapability,
            AgentRuntimeService,
        )

        service = AgentRuntimeService()

        capability = A2ACapability(
            capability_name="analyze",
            description="Analyze content",
            input_schema={},
            output_schema={},
        )

        card = A2AAgentCard(
            agent_id="analyzer",
            name="Analyzer Agent",
            description="Analyzes content",
            version="1.0",
            capabilities=[capability],
            endpoint="https://example.com/analyzer",
        )

        await service.register_a2a_agent(card)
        assert "analyzer" in service._a2a_registry

    @pytest.mark.asyncio
    async def test_discover_a2a_agents(self):
        """Test discovering A2A agents."""
        from src.services.agent_runtime_service import (
            A2AAgentCard,
            A2ACapability,
            AgentRuntimeService,
        )

        service = AgentRuntimeService()

        # Register agents
        for name in ["summarizer", "translator", "analyzer"]:
            cap = A2ACapability(
                capability_name="process",
                description=f"{name} processing",
                input_schema={},
                output_schema={},
            )
            card = A2AAgentCard(
                agent_id=name,
                name=f"{name.title()} Agent",
                description=f"Agent for {name}",
                version="1.0",
                capabilities=[cap],
                endpoint=f"https://example.com/{name}",
            )
            await service.register_a2a_agent(card)

        agents = await service.discover_a2a_agents()
        assert len(agents) >= 3

    @pytest.mark.asyncio
    async def test_get_deployment(self):
        """Test getting a deployment."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            AgentRuntimeService,
            DeploymentMode,
            RuntimeType,
        )

        service = AgentRuntimeService()

        # Register deployment directly for testing
        config = AgentDeploymentConfig(
            deployment_id="test-agent",
            name="Test Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
        )
        service._deployments["test-agent"] = config

        # Get deployment
        deployment = await service.get_deployment("test-agent")
        assert deployment is not None
        assert deployment.name == "Test Agent"


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_environment_variables(self):
        """Test config with empty environment variables."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            DeploymentMode,
            RuntimeType,
        )

        config = AgentDeploymentConfig(
            deployment_id="agent",
            name="Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
            environment_variables={},
        )
        assert config.environment_variables == {}

    def test_max_timeout(self):
        """Test maximum allowed timeout."""
        from src.services.agent_runtime_service import (
            AgentDeploymentConfig,
            DeploymentMode,
            RuntimeType,
        )

        config = AgentDeploymentConfig(
            deployment_id="agent",
            name="Agent",
            deployment_mode=DeploymentMode.CODE_UPLOAD,
            runtime=RuntimeType.PYTHON_3_11,
            timeout_seconds=28800,  # 8 hours exactly
        )
        assert config.timeout_seconds == 28800

    def test_session_with_user_id(self):
        """Test session creation with user ID."""
        from src.services.agent_runtime_service import AgentSession

        session = AgentSession(
            session_id="sess-001", deployment_id="agent-001", user_id="user-123"
        )
        assert session.user_id == "user-123"

    def test_request_with_context(self):
        """Test request with context."""
        from src.services.agent_runtime_service import AgentRequest

        request = AgentRequest(
            input_text="Hello", context={"conversation_id": "conv-123", "history": []}
        )
        assert "conversation_id" in request.context
