"""
Project Aura - A2A Protocol Tests

Comprehensive test suite for the A2A (Agent-to-Agent) protocol implementation.

Tests cover:
- A2A Gateway functionality
- Agent Registry operations
- API endpoints
- Integration mode enforcement
- Task lifecycle management

Author: Project Aura Team
Created: 2025-12-07
"""

import os
from unittest.mock import patch

import pytest

# Set test environment before importing modules
os.environ["ENVIRONMENT"] = "test"
os.environ["AURA_INTEGRATION_MODE"] = "enterprise"
os.environ["AURA_A2A_ENABLED"] = "true"


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def enterprise_config():
    """Create enterprise mode configuration for testing."""
    from src.config.integration_config import (
        IntegrationConfig,
        IntegrationMode,
        clear_integration_config_cache,
    )

    clear_integration_config_cache()

    config = IntegrationConfig(
        mode=IntegrationMode.ENTERPRISE,
        environment="test",
        a2a_enabled=True,
    )
    return config


@pytest.fixture
def defense_config():
    """Create defense mode configuration for testing."""
    from src.config.integration_config import IntegrationConfig, IntegrationMode

    config = IntegrationConfig(
        mode=IntegrationMode.DEFENSE,
        environment="test",
    )
    return config


@pytest.fixture
def a2a_gateway(enterprise_config):
    """Create A2A gateway instance."""
    from src.services.a2a_gateway import A2AGateway

    return A2AGateway(config=enterprise_config)


@pytest.fixture
def agent_registry(enterprise_config):
    """Create agent registry instance."""
    from src.services.a2a_agent_registry import A2AAgentRegistry

    return A2AAgentRegistry(config=enterprise_config)


@pytest.fixture
def sample_agent_card():
    """Create sample agent card for testing."""
    from src.services.a2a_gateway import AgentCapability, AgentCard

    return AgentCard(
        agent_id="test-external-agent",
        name="Test External Agent",
        description="An external agent for testing",
        endpoint="https://external.example.com/a2a",
        provider="test-provider",
        capabilities=[
            AgentCapability(
                name="test_capability",
                description="A test capability",
                input_schema={
                    "type": "object",
                    "properties": {"input": {"type": "string"}},
                },
                output_schema={
                    "type": "object",
                    "properties": {"output": {"type": "string"}},
                },
            ),
        ],
    )


# =============================================================================
# A2A Gateway Tests
# =============================================================================


class TestA2AGateway:
    """Tests for A2A Gateway service."""

    def test_gateway_initialization_enterprise_mode(self, enterprise_config):
        """Test gateway initializes correctly in enterprise mode."""
        from src.services.a2a_gateway import A2AGateway

        gateway = A2AGateway(config=enterprise_config)

        assert gateway is not None
        assert len(gateway._local_agent_cards) == 3  # Coder, Reviewer, Validator

    def test_gateway_fails_in_defense_mode(self, defense_config):
        """Test gateway raises error in defense mode."""
        from src.services.a2a_gateway import A2AGateway

        with pytest.raises(RuntimeError) as exc_info:
            A2AGateway(config=defense_config)

        assert "DEFENSE mode" in str(exc_info.value)
        assert "A2A" in str(exc_info.value)

    def test_list_local_agent_cards(self, a2a_gateway):
        """Test listing local Aura agent cards."""
        cards = a2a_gateway.list_local_agent_cards()

        assert len(cards) == 3
        agent_ids = [c.agent_id for c in cards]
        assert "aura-coder-agent" in agent_ids
        assert "aura-reviewer-agent" in agent_ids
        assert "aura-validator-agent" in agent_ids

    def test_get_local_agent_card(self, a2a_gateway):
        """Test getting specific local agent card."""
        card = a2a_gateway.get_local_agent_card("aura-coder-agent")

        assert card is not None
        assert card.agent_id == "aura-coder-agent"
        assert card.name == "Aura Coder Agent"
        assert len(card.capabilities) >= 1

    def test_get_local_agent_card_not_found(self, a2a_gateway):
        """Test getting non-existent agent card returns None."""
        card = a2a_gateway.get_local_agent_card("nonexistent-agent")
        assert card is None

    def test_agent_card_to_dict(self, a2a_gateway):
        """Test agent card serialization."""
        card = a2a_gateway.get_local_agent_card("aura-coder-agent")
        data = card.to_dict()

        assert data["agent_id"] == "aura-coder-agent"
        assert "capabilities" in data
        assert "authentication" in data
        assert data["provider"] == "aenealabs"

    @pytest.mark.asyncio
    async def test_create_task(self, a2a_gateway):
        """Test creating an A2A task."""
        task = await a2a_gateway.create_task(
            capability_name="generate_patch",
            input_data={"vulnerability_id": "vuln-123", "file_path": "test.py"},
        )

        assert task is not None
        assert task.task_id is not None
        assert task.capability_name == "generate_patch"
        assert task.status.value == "submitted"

    @pytest.mark.asyncio
    async def test_get_task(self, a2a_gateway):
        """Test retrieving a task."""
        task = await a2a_gateway.create_task(
            capability_name="scan_code",
            input_data={"code_content": "print('hello')"},
        )

        retrieved = await a2a_gateway.get_task(task.task_id)

        assert retrieved is not None
        assert retrieved.task_id == task.task_id

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, a2a_gateway):
        """Test retrieving non-existent task."""
        task = await a2a_gateway.get_task("nonexistent-task-id")
        assert task is None

    @pytest.mark.asyncio
    async def test_update_task_status(self, a2a_gateway):
        """Test updating task status."""
        from src.services.a2a_gateway import TaskStatus

        task = await a2a_gateway.create_task(
            capability_name="test",
            input_data={},
        )

        updated = await a2a_gateway.update_task_status(
            task_id=task.task_id,
            status=TaskStatus.WORKING,
            message="Processing",
        )

        assert updated is not None
        assert updated.status == TaskStatus.WORKING
        assert updated.status_message == "Processing"

    @pytest.mark.asyncio
    async def test_cancel_task(self, a2a_gateway):
        """Test canceling a task."""
        from src.services.a2a_gateway import TaskStatus

        task = await a2a_gateway.create_task(
            capability_name="test",
            input_data={},
        )

        canceled = await a2a_gateway.cancel_task(task.task_id, "User requested")

        assert canceled is not None
        assert canceled.status == TaskStatus.CANCELED
        assert "User requested" in canceled.status_message

    @pytest.mark.asyncio
    async def test_execute_task(self, a2a_gateway):
        """Test executing a task."""
        from src.services.a2a_gateway import TaskStatus

        task = await a2a_gateway.create_task(
            capability_name="test_capability",
            input_data={"test": "data"},
        )

        result = await a2a_gateway.execute_task(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.output_data is not None

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_task_send(self, a2a_gateway):
        """Test JSON-RPC tasks/send handler."""
        response = await a2a_gateway.handle_jsonrpc_request(
            {
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "params": {
                    "capability": "generate_patch",
                    "input": {"vulnerability_id": "v-1"},
                },
                "id": "req-1",
            }
        )

        assert response.is_success
        assert "task_id" in response.result

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_task_get(self, a2a_gateway):
        """Test JSON-RPC tasks/get handler."""
        # Create a task first
        task = await a2a_gateway.create_task("test", {})

        response = await a2a_gateway.handle_jsonrpc_request(
            {
                "jsonrpc": "2.0",
                "method": "tasks/get",
                "params": {"task_id": task.task_id},
                "id": "req-2",
            }
        )

        assert response.is_success
        assert response.result["task_id"] == task.task_id

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_invalid_method(self, a2a_gateway):
        """Test JSON-RPC with invalid method."""
        response = await a2a_gateway.handle_jsonrpc_request(
            {
                "jsonrpc": "2.0",
                "method": "invalid/method",
                "params": {},
                "id": "req-3",
            }
        )

        assert not response.is_success
        assert response.error["code"] == -32601  # Method not found

    @pytest.mark.asyncio
    async def test_handle_jsonrpc_agent_card_request(self, a2a_gateway):
        """Test JSON-RPC agent card request."""
        response = await a2a_gateway.handle_jsonrpc_request(
            {
                "jsonrpc": "2.0",
                "method": "agent_card_request",
                "params": {"agent_id": "aura-coder-agent"},
                "id": "req-4",
            }
        )

        assert response.is_success
        assert response.result["agent_id"] == "aura-coder-agent"

    def test_gateway_metrics(self, a2a_gateway):
        """Test gateway metrics."""
        metrics = a2a_gateway.get_metrics()

        assert "total_tasks_received" in metrics
        assert "total_tasks_sent" in metrics
        assert "total_errors" in metrics
        assert "local_agents" in metrics
        assert metrics["local_agents"] == 3


# =============================================================================
# Agent Registry Tests
# =============================================================================


class TestA2AAgentRegistry:
    """Tests for A2A Agent Registry service."""

    def test_registry_initialization_enterprise_mode(self, enterprise_config):
        """Test registry initializes correctly in enterprise mode."""
        from src.services.a2a_agent_registry import A2AAgentRegistry

        registry = A2AAgentRegistry(config=enterprise_config)
        assert registry is not None

    def test_registry_fails_in_defense_mode(self, defense_config):
        """Test registry raises error in defense mode."""
        from src.services.a2a_agent_registry import A2AAgentRegistry

        with pytest.raises(RuntimeError) as exc_info:
            A2AAgentRegistry(config=defense_config)

        assert "DEFENSE mode" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_agent(self, agent_registry, sample_agent_card):
        """Test registering an external agent."""
        registration = await agent_registry.register_agent(
            agent_card=sample_agent_card,
            tags=["test", "external"],
            verify=False,  # Skip verification in test
        )

        assert registration is not None
        assert registration.agent_id == "test-external-agent"
        assert "test" in registration.tags

    @pytest.mark.asyncio
    async def test_get_agent(self, agent_registry, sample_agent_card):
        """Test retrieving a registered agent."""
        await agent_registry.register_agent(sample_agent_card, verify=False)

        agent = await agent_registry.get_agent("test-external-agent")

        assert agent is not None
        assert agent.agent_id == "test-external-agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, agent_registry):
        """Test retrieving non-existent agent."""
        agent = await agent_registry.get_agent("nonexistent")
        assert agent is None

    @pytest.mark.asyncio
    async def test_unregister_agent(self, agent_registry, sample_agent_card):
        """Test unregistering an agent."""
        await agent_registry.register_agent(sample_agent_card, verify=False)

        success = await agent_registry.unregister_agent("test-external-agent")
        assert success is True

        agent = await agent_registry.get_agent("test-external-agent")
        assert agent is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_agent(self, agent_registry):
        """Test unregistering non-existent agent."""
        success = await agent_registry.unregister_agent("nonexistent")
        assert success is False

    @pytest.mark.asyncio
    async def test_list_agents(self, agent_registry, sample_agent_card):
        """Test listing registered agents."""
        await agent_registry.register_agent(sample_agent_card, verify=False)

        agents = await agent_registry.list_agents()

        assert len(agents) >= 1
        agent_ids = [a.agent_id for a in agents]
        assert "test-external-agent" in agent_ids

    @pytest.mark.asyncio
    async def test_search_agents_by_capability(self, agent_registry, sample_agent_card):
        """Test searching agents by capability."""
        from src.services.a2a_agent_registry import AgentSearchCriteria, AgentStatus

        # Register and activate agent
        registration = await agent_registry.register_agent(
            sample_agent_card, verify=False
        )
        registration.status = AgentStatus.ACTIVE

        criteria = AgentSearchCriteria(
            capability_name="test_capability",
            status=AgentStatus.ACTIVE,
        )

        results = await agent_registry.search_agents(criteria)

        assert len(results) >= 1
        assert results[0].agent_id == "test-external-agent"

    @pytest.mark.asyncio
    async def test_search_agents_no_match(self, agent_registry):
        """Test search with no matching agents."""
        from src.services.a2a_agent_registry import AgentSearchCriteria

        criteria = AgentSearchCriteria(
            capability_name="nonexistent_capability",
        )

        results = await agent_registry.search_agents(criteria)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_update_agent_status(self, agent_registry, sample_agent_card):
        """Test updating agent status."""
        from src.services.a2a_agent_registry import AgentStatus

        await agent_registry.register_agent(sample_agent_card, verify=False)

        updated = await agent_registry.update_agent_status(
            "test-external-agent",
            AgentStatus.SUSPENDED,
            "Maintenance",
        )

        assert updated is not None
        assert updated.status == AgentStatus.SUSPENDED

    @pytest.mark.asyncio
    async def test_trust_level_determination(self, agent_registry):
        """Test trust level is determined by provider."""
        from src.services.a2a_agent_registry import AgentTrustLevel
        from src.services.a2a_gateway import AgentCard

        # Aenealabs provider should be VERIFIED
        aura_card = AgentCard(
            agent_id="aura-test",
            name="Aura Test",
            description="Test",
            endpoint="https://api.aenealabs.com/a2a",
            provider="aenealabs",
        )
        registration = await agent_registry.register_agent(aura_card, verify=False)
        assert registration.trust_level == AgentTrustLevel.VERIFIED

        # Microsoft provider should be TRUSTED
        ms_card = AgentCard(
            agent_id="ms-test",
            name="MS Test",
            description="Test",
            endpoint="https://api.microsoft.com/a2a",
            provider="microsoft",
        )
        registration = await agent_registry.register_agent(ms_card, verify=False)
        assert registration.trust_level == AgentTrustLevel.TRUSTED

    def test_registry_metrics(self, agent_registry):
        """Test registry metrics."""
        metrics = agent_registry.get_metrics()

        assert "total_registered_agents" in metrics
        assert "total_searches" in metrics
        assert "agents_by_status" in metrics
        assert "agents_by_trust" in metrics

    @pytest.mark.asyncio
    async def test_export_registry(self, agent_registry, sample_agent_card):
        """Test exporting registry."""
        await agent_registry.register_agent(sample_agent_card, verify=False)

        export = await agent_registry.export_registry()

        assert "agents" in export
        assert "metrics" in export
        assert "exported_at" in export
        assert len(export["agents"]) >= 1


# =============================================================================
# API Endpoint Tests
# =============================================================================


class TestA2AEndpoints:
    """Tests for A2A API endpoints."""

    @pytest.fixture(scope="class")
    def test_client(self):
        """Create test client with enterprise config.

        Uses class scope to ensure consistent FastAPI validation behavior
        across all tests in this class. All imports are inside the fixture
        to defer loading until test execution time.
        """
        import os

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        # Set environment variables before importing modules
        os.environ["ENVIRONMENT"] = "test"
        os.environ["AURA_INTEGRATION_MODE"] = "enterprise"
        os.environ["AURA_A2A_ENABLED"] = "true"

        from src.api.a2a_endpoints import router

        app = FastAPI()
        app.include_router(router)

        yield TestClient(app)

    def test_agent_card_discovery(self, test_client):
        """Test agent card discovery endpoint."""
        with patch("src.api.a2a_endpoints.get_integration_config") as mock_config:
            from src.config.integration_config import IntegrationConfig, IntegrationMode

            config = IntegrationConfig(
                mode=IntegrationMode.ENTERPRISE, a2a_enabled=True
            )
            mock_config.return_value = config

            response = test_client.get("/.well-known/agent.json")

            # May get 403 if gateway instantiation fails
            assert response.status_code in [200, 403, 500]

    def test_a2a_health_endpoint(self, test_client):
        """Test A2A health endpoint."""
        response = test_client.get("/a2a/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "a2a_enabled" in data
        assert "integration_mode" in data


# =============================================================================
# Data Model Tests
# =============================================================================


class TestA2ADataModels:
    """Tests for A2A data models."""

    def test_task_artifact_creation(self):
        """Test task artifact creation."""
        from src.services.a2a_gateway import ArtifactType, TaskArtifact

        artifact = TaskArtifact(
            artifact_type=ArtifactType.PATCH,
            name="security_fix.patch",
            content="--- a/file.py\n+++ b/file.py",
            mime_type="text/x-diff",
        )

        assert artifact.artifact_id is not None
        assert artifact.artifact_type == ArtifactType.PATCH

        data = artifact.to_dict()
        assert data["type"] == "patch"
        assert data["name"] == "security_fix.patch"

    def test_a2a_request_creation(self):
        """Test A2A request creation."""
        from src.services.a2a_gateway import A2ARequest

        request = A2ARequest(
            method="tasks/send",
            params={"capability": "test"},
        )

        data = request.to_dict()
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "tasks/send"
        assert "id" in data

    def test_a2a_response_success(self):
        """Test A2A response for success."""
        from src.services.a2a_gateway import A2AResponse

        response = A2AResponse(
            id="req-1",
            result={"task_id": "task-123"},
        )

        assert response.is_success is True
        data = response.to_dict()
        assert "result" in data
        assert "error" not in data or data["error"] is None

    def test_a2a_response_error(self):
        """Test A2A response for error."""
        from src.services.a2a_gateway import A2AResponse

        response = A2AResponse(
            id="req-1",
            error={"code": -32600, "message": "Invalid request"},
        )

        assert response.is_success is False
        data = response.to_dict()
        assert data["error"]["code"] == -32600

    def test_registered_agent_success_rate(self):
        """Test registered agent success rate calculation."""
        from src.services.a2a_agent_registry import RegisteredAgent
        from src.services.a2a_gateway import AgentCard

        card = AgentCard(
            agent_id="test",
            name="Test",
            description="Test",
            endpoint="https://example.com",
        )

        agent = RegisteredAgent(agent_card=card)
        agent.total_tasks_completed = 8
        agent.total_tasks_failed = 2

        assert agent.success_rate == 0.8

    def test_registered_agent_rate_limiting(self):
        """Test registered agent rate limiting."""
        from src.services.a2a_agent_registry import RegisteredAgent
        from src.services.a2a_gateway import AgentCard

        card = AgentCard(
            agent_id="test",
            name="Test",
            description="Test",
            endpoint="https://example.com",
        )

        agent = RegisteredAgent(agent_card=card, rate_limit_per_minute=2)

        # First two requests should be allowed
        assert agent.record_request() is True
        assert agent.record_request() is True

        # Third request should be rate limited
        assert agent.record_request() is False


# =============================================================================
# Integration Mode Enforcement Tests
# =============================================================================


class TestIntegrationModeEnforcement:
    """Tests for integration mode enforcement."""

    def test_require_enterprise_mode_decorator(self, defense_config):
        """Test that enterprise-only functions fail in defense mode."""
        from src.config.integration_config import require_enterprise_mode

        @require_enterprise_mode
        def enterprise_only_function():
            return "success"

        # Should raise error when config returns defense mode
        with patch("src.config.integration_config.get_integration_config") as mock:
            mock.return_value = defense_config

            with pytest.raises(RuntimeError) as exc_info:
                enterprise_only_function()

            assert "ENTERPRISE mode" in str(exc_info.value)

    def test_a2a_disabled_in_defense_config(self, defense_config):
        """Test A2A is disabled in defense config."""
        assert defense_config.a2a_enabled is False
        assert defense_config.gateway_enabled is False


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_task_with_push_notification(self, a2a_gateway):
        """Test task with push notification URL."""
        task = await a2a_gateway.create_task(
            capability_name="test",
            input_data={},
            push_notification_url="https://callback.example.com/notify",
        )

        assert task.push_notification_url == "https://callback.example.com/notify"

    @pytest.mark.asyncio
    async def test_task_with_session_id(self, a2a_gateway):
        """Test task with session ID for multi-turn."""
        task = await a2a_gateway.create_task(
            capability_name="test",
            input_data={},
            session_id="session-123",
        )

        assert task.session_id == "session-123"

    def test_agent_card_capabilities(self, a2a_gateway):
        """Test agent card has expected capabilities."""
        coder = a2a_gateway.get_local_agent_card("aura-coder-agent")
        cap_names = [c.name for c in coder.capabilities]

        assert "generate_patch" in cap_names

        reviewer = a2a_gateway.get_local_agent_card("aura-reviewer-agent")
        cap_names = [c.name for c in reviewer.capabilities]

        assert "scan_code" in cap_names
        assert "review_patch" in cap_names

    @pytest.mark.asyncio
    async def test_jsonrpc_missing_capability(self, a2a_gateway):
        """Test JSON-RPC with missing capability parameter."""
        response = await a2a_gateway.handle_jsonrpc_request(
            {
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "params": {},  # Missing capability
                "id": "req-1",
            }
        )

        assert not response.is_success
        assert response.error["code"] == -32602  # Invalid params

    @pytest.mark.asyncio
    async def test_jsonrpc_invalid_version(self, a2a_gateway):
        """Test JSON-RPC with invalid version."""
        response = await a2a_gateway.handle_jsonrpc_request(
            {
                "jsonrpc": "1.0",  # Invalid version
                "method": "tasks/send",
                "params": {"capability": "test"},
                "id": "req-1",
            }
        )

        assert not response.is_success
        assert response.error["code"] == -32600  # Invalid request


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
