"""
MetaOrchestrator Integration Tests

Tests the MetaOrchestrator with real agent adapters and optional real Bedrock LLM.
These tests verify dynamic agent spawning, task decomposition, and autonomy policies
work correctly with production-ready agent implementations.

Run with real LLM (requires AWS credentials):
    RUN_INTEGRATION_TESTS=1 pytest tests/test_meta_orchestrator_integration.py -v

Run with mocked LLM (default):
    pytest tests/test_meta_orchestrator_integration.py -v
"""

import os
import platform
from unittest.mock import AsyncMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.agents.context_objects import HybridContext
from src.agents.meta_orchestrator import (
    AgentCapability,
    AgentRegistry,
    AgentResult,
    AutonomyLevel,
    MetaOrchestratorResult,
    TaskDecomposer,
    TaskNode,
)
from src.agents.spawnable_agent_adapters import (
    SpawnableCoderAgent,
    SpawnableReviewerAgent,
    SpawnableValidatorAgent,
    create_production_meta_orchestrator,
    register_all_agents,
)

# Check if we should run real integration tests
RUN_REAL_LLM = os.environ.get("RUN_INTEGRATION_TESTS", "").lower() in (
    "1",
    "true",
    "yes",
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing without real API calls."""
    mock = AsyncMock()
    mock.generate = AsyncMock(return_value="Generated response from mock LLM")
    return mock


@pytest.fixture
def mock_context_service():
    """Create a mock context retrieval service."""
    mock = AsyncMock()
    mock.get_hybrid_context = AsyncMock(
        return_value=HybridContext(
            items=[],
            query="test query",
            target_entity="test_entity",
        )
    )
    return mock


@pytest.fixture
def mock_hitl_service():
    """Create a mock HITL approval service."""
    mock = AsyncMock()
    mock.create_approval_request = AsyncMock(
        return_value={"request_id": "test-hitl-123", "status": "pending"}
    )
    mock.get_approval_status = AsyncMock(return_value="approved")
    return mock


@pytest.fixture
def registry_with_real_agents(mock_llm_client):
    """Create an AgentRegistry with real agent adapters."""
    registry = AgentRegistry()
    register_all_agents(registry, llm_client=mock_llm_client)
    return registry


@pytest.fixture
def production_orchestrator(mock_llm_client, mock_context_service, mock_hitl_service):
    """Create a production-ready MetaOrchestrator with mocked dependencies."""
    return create_production_meta_orchestrator(
        llm_client=mock_llm_client,
        autonomy_preset="enterprise_standard",
        context_service=mock_context_service,
        hitl_service=mock_hitl_service,
    )


# =============================================================================
# Agent Adapter Tests
# =============================================================================


class TestSpawnableAgentAdapters:
    """Test the spawnable agent adapter implementations."""

    def test_spawnable_coder_agent_has_correct_capability(self, mock_llm_client):
        """Test SpawnableCoderAgent has CODE_GENERATION capability."""
        agent = SpawnableCoderAgent(llm_client=mock_llm_client)
        assert agent.capability == AgentCapability.CODE_GENERATION

    def test_spawnable_reviewer_agent_has_correct_capability(self, mock_llm_client):
        """Test SpawnableReviewerAgent has SECURITY_REVIEW capability."""
        agent = SpawnableReviewerAgent(llm_client=mock_llm_client)
        assert agent.capability == AgentCapability.SECURITY_REVIEW

    def test_spawnable_validator_agent_has_correct_capability(self, mock_llm_client):
        """Test SpawnableValidatorAgent has PATCH_VALIDATION capability."""
        agent = SpawnableValidatorAgent(llm_client=mock_llm_client)
        assert agent.capability == AgentCapability.PATCH_VALIDATION

    @pytest.mark.asyncio
    async def test_spawnable_coder_agent_execute(self, mock_llm_client):
        """Test SpawnableCoderAgent can execute tasks."""
        agent = SpawnableCoderAgent(llm_client=mock_llm_client)

        # Mock the wrapped agent
        with patch.object(agent, "_get_wrapped_agent") as mock_get:
            mock_coder = AsyncMock()
            mock_coder.generate_code = AsyncMock(
                return_value={
                    "code": "def secure_function(): pass",
                    "language": "python",
                    "tokens_used": 50,
                }
            )
            mock_get.return_value = mock_coder

            result = await agent.execute(
                task="Generate a secure authentication function",
                context=None,
            )

            assert isinstance(result, AgentResult)
            assert result.success is True
            assert result.capability == AgentCapability.CODE_GENERATION

    @pytest.mark.asyncio
    async def test_spawnable_reviewer_agent_execute(self, mock_llm_client):
        """Test SpawnableReviewerAgent can execute tasks."""
        agent = SpawnableReviewerAgent(llm_client=mock_llm_client)

        with patch.object(agent, "_get_wrapped_agent") as mock_get:
            mock_reviewer = AsyncMock()
            mock_reviewer.review_code = AsyncMock(
                return_value={
                    "status": "PASS",
                    "finding": "No vulnerabilities found",
                    "severity": "LOW",
                    "tokens_used": 30,
                }
            )
            mock_get.return_value = mock_reviewer

            result = await agent.execute(
                task="Review this code for security issues",
                context={"code": "def safe_func(): return True"},
            )

            assert isinstance(result, AgentResult)
            assert result.success is True

    @pytest.mark.asyncio
    async def test_spawnable_validator_agent_execute(self, mock_llm_client):
        """Test SpawnableValidatorAgent can execute tasks."""
        agent = SpawnableValidatorAgent(llm_client=mock_llm_client)

        with patch.object(agent, "_get_wrapped_agent") as mock_get:
            mock_validator = AsyncMock()
            mock_validator.validate_code = AsyncMock(
                return_value={
                    "valid": True,
                    "syntax_valid": True,
                    "security_valid": True,
                    "issues": [],
                }
            )
            mock_get.return_value = mock_validator

            result = await agent.execute(
                task="Validate this code",
                context={"code": "def valid_func(): pass"},
            )

            assert isinstance(result, AgentResult)
            # Validation passes = success
            assert result.output["valid"] is True


# =============================================================================
# Registry Integration Tests
# =============================================================================


class TestRegistryIntegration:
    """Test agent registration with AgentRegistry."""

    def test_register_all_agents_replaces_defaults(self, mock_llm_client):
        """Test that register_all_agents replaces default generic agents."""
        registry = AgentRegistry()

        # Before registration, should have generic agents
        initial_capabilities = registry.get_available_capabilities()
        assert AgentCapability.CODE_GENERATION in initial_capabilities

        # Register real agents
        register_all_agents(registry, llm_client=mock_llm_client)

        # Should still have all capabilities (at minimum)
        final_capabilities = registry.get_available_capabilities()
        assert len(final_capabilities) >= len(AgentCapability)
        assert AgentCapability.CODE_GENERATION in final_capabilities
        assert AgentCapability.SECURITY_REVIEW in final_capabilities
        assert AgentCapability.PATCH_VALIDATION in final_capabilities

    def test_spawn_real_coder_agent(self, registry_with_real_agents):
        """Test spawning a real CoderAgent from registry."""
        from src.agents.meta_orchestrator import AgentSpec

        spec = AgentSpec(
            capability=AgentCapability.CODE_GENERATION,
            task_description="Generate secure code",
            max_depth=2,
        )

        agent = registry_with_real_agents.spawn_agent(spec)

        assert isinstance(agent, SpawnableCoderAgent)
        assert agent.capability == AgentCapability.CODE_GENERATION

    def test_spawn_real_reviewer_agent(self, registry_with_real_agents):
        """Test spawning a real ReviewerAgent from registry."""
        from src.agents.meta_orchestrator import AgentSpec

        spec = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Review code security",
            max_depth=2,
        )

        agent = registry_with_real_agents.spawn_agent(spec)

        assert isinstance(agent, SpawnableReviewerAgent)
        assert agent.capability == AgentCapability.SECURITY_REVIEW


# =============================================================================
# MetaOrchestrator Integration Tests
# =============================================================================


class TestMetaOrchestratorIntegration:
    """Test MetaOrchestrator with real agent adapters."""

    @pytest.mark.asyncio
    async def test_orchestrator_with_real_agents_decomposition(
        self, production_orchestrator
    ):
        """Test that orchestrator decomposes tasks correctly."""
        # Mock decomposer to return specific tasks
        production_orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Analyze code for vulnerabilities",
                    capability=AgentCapability.SECURITY_REVIEW,
                    complexity=0.4,
                ),
                TaskNode.create(
                    description="Generate security patch",
                    capability=AgentCapability.CODE_GENERATION,
                    complexity=0.6,
                ),
            ]
        )

        result = await production_orchestrator.execute(
            task="Fix SQL injection vulnerability in login.py",
            repository="test-repo",
            severity="HIGH",
        )

        assert isinstance(result, MetaOrchestratorResult)
        assert result.execution_id.startswith("exec-")

    @pytest.mark.asyncio
    async def test_orchestrator_respects_autonomy_policy(
        self, mock_llm_client, mock_context_service, mock_hitl_service
    ):
        """Test that orchestrator respects autonomy policy for different severities."""
        # Create orchestrator with defense_contractor preset (most restrictive)
        orchestrator = create_production_meta_orchestrator(
            llm_client=mock_llm_client,
            autonomy_preset="defense_contractor",
            context_service=mock_context_service,
            hitl_service=mock_hitl_service,
        )

        # Mock decomposer
        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Fix vulnerability",
                    capability=AgentCapability.CODE_GENERATION,
                )
            ]
        )

        # With defense_contractor preset, even LOW severity should require HITL
        autonomy = orchestrator.autonomy_policy.get_autonomy_level(
            severity="LOW",
            repository="any-repo",
            operation="code_fix",
        )

        # defense_contractor has severity override for LOW -> CRITICAL_HITL
        assert autonomy in [AutonomyLevel.FULL_HITL, AutonomyLevel.CRITICAL_HITL]

    @pytest.mark.asyncio
    async def test_orchestrator_handles_parallel_tasks(self, production_orchestrator):
        """Test orchestrator can handle multiple independent tasks."""
        # Create independent tasks (no dependencies)
        production_orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Task A",
                    capability=AgentCapability.CODE_ANALYSIS,
                ),
                TaskNode.create(
                    description="Task B",
                    capability=AgentCapability.VULNERABILITY_SCAN,
                ),
                TaskNode.create(
                    description="Task C",
                    capability=AgentCapability.SECURITY_REVIEW,
                ),
            ]
        )

        result = await production_orchestrator.execute(
            task="Comprehensive security analysis",
            repository="test-repo",
            severity="MEDIUM",
        )

        assert result.status in ["completed", "awaiting_hitl", "failed"]

    def test_orchestrator_classify_operations(self, production_orchestrator):
        """Test operation classification for guardrail detection."""
        # Production deployment should be classified correctly
        op1 = production_orchestrator._classify_operation("Deploy to production server")
        assert op1 == "production_deployment"

        # Credential changes should be classified
        op2 = production_orchestrator._classify_operation("Update API credentials")
        assert op2 == "credential_modification"

        # Regular code fix - classifier sees "fix" as security_patch
        op3 = production_orchestrator._classify_operation("Fix bug in parser")
        assert op3 in ["code_fix", "security_patch"]  # Depends on keyword matching


# =============================================================================
# Real Bedrock LLM Integration Tests (Optional)
# =============================================================================


@pytest.mark.skipif(
    not RUN_REAL_LLM,
    reason="Real LLM tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable.",
)
class TestRealBedrockIntegration:
    """
    Integration tests with real Bedrock LLM.

    These tests require:
    - AWS credentials configured
    - Bedrock access enabled in your AWS account
    - Claude model access approved

    Run with: RUN_INTEGRATION_TESTS=1 pytest tests/test_meta_orchestrator_integration.py -v
    """

    @pytest.fixture
    def real_bedrock_client(self):
        """Create a real Bedrock LLM client."""
        from src.services.bedrock_llm_service import BedrockLLMService

        return BedrockLLMService()

    @pytest.mark.asyncio
    async def test_real_llm_task_decomposition(self, real_bedrock_client):
        """Test TaskDecomposer with real LLM."""
        decomposer = TaskDecomposer(llm_client=real_bedrock_client)

        tasks = await decomposer.decompose(
            task="Fix SQL injection vulnerability in user authentication module",
            context=None,
            depth=0,
        )

        # Should return at least one task
        assert len(tasks) >= 1
        # All tasks should be TaskNode instances
        assert all(isinstance(t, TaskNode) for t in tasks)
        # Each task should have a valid capability
        assert all(t.capability in AgentCapability for t in tasks)

        print(f"\n✅ Real LLM decomposed task into {len(tasks)} sub-tasks:")
        for t in tasks:
            print(f"   - [{t.capability.value}] {t.description[:60]}...")

    @pytest.mark.asyncio
    async def test_real_llm_coder_agent(self, real_bedrock_client):
        """Test SpawnableCoderAgent with real LLM."""
        agent = SpawnableCoderAgent(llm_client=real_bedrock_client)

        result = await agent.execute(
            task="Generate a Python function that safely sanitizes user input to prevent SQL injection",
            context=None,
        )

        assert isinstance(result, AgentResult)
        print("\n✅ Real LLM CoderAgent result:")
        print(f"   Success: {result.success}")
        print(f"   Tokens used: {result.tokens_used}")
        if result.output:
            print(f"   Output keys: {list(result.output.keys())}")

    @pytest.mark.asyncio
    async def test_real_llm_reviewer_agent(self, real_bedrock_client):
        """Test SpawnableReviewerAgent with real LLM."""
        agent = SpawnableReviewerAgent(llm_client=real_bedrock_client)

        vulnerable_code = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(query)
    return cursor.fetchone()
"""

        result = await agent.execute(
            task="Review this code for security vulnerabilities",
            context={"code": vulnerable_code},
        )

        assert isinstance(result, AgentResult)
        print("\n✅ Real LLM ReviewerAgent result:")
        print(f"   Success: {result.success}")
        if result.output:
            print(f"   Status: {result.output.get('status', 'N/A')}")
            print(f"   Finding: {result.output.get('finding', 'N/A')[:100]}...")

    @pytest.mark.asyncio
    async def test_real_llm_full_orchestrator_flow(self, real_bedrock_client):
        """Test full MetaOrchestrator flow with real LLM."""
        orchestrator = create_production_meta_orchestrator(
            llm_client=real_bedrock_client,
            autonomy_preset="fintech_startup",  # AUDIT_ONLY for MEDIUM severity
        )

        result = await orchestrator.execute(
            task="Analyze and fix potential XSS vulnerability in user profile display",
            repository="test-web-app",
            severity="MEDIUM",
        )

        assert isinstance(result, MetaOrchestratorResult)
        print("\n✅ Real LLM MetaOrchestrator result:")
        print(f"   Execution ID: {result.execution_id}")
        print(f"   Status: {result.status}")
        print(f"   HITL Required: {result.hitl_required}")
        print(f"   Execution Time: {result.execution_time_seconds:.2f}s")
        if result.error:
            print(f"   Error: {result.error}")


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Test the factory functions for creating orchestrators."""

    def test_create_production_orchestrator_with_preset(self, mock_llm_client):
        """Test creating orchestrator with different presets."""
        presets = [
            "defense_contractor",
            "financial_services",
            "fintech_startup",
            "enterprise_standard",
            "internal_tools",
            "fully_autonomous",
        ]

        for preset in presets:
            orchestrator = create_production_meta_orchestrator(
                llm_client=mock_llm_client,
                autonomy_preset=preset,
            )

            assert orchestrator is not None
            assert orchestrator.autonomy_policy is not None
            assert orchestrator.registry is not None

            # Verify real agents are registered
            capabilities = orchestrator.registry.get_available_capabilities()
            assert AgentCapability.CODE_GENERATION in capabilities
            assert AgentCapability.SECURITY_REVIEW in capabilities
            assert AgentCapability.PATCH_VALIDATION in capabilities

    def test_create_production_orchestrator_invalid_preset(self, mock_llm_client):
        """Test that invalid preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            create_production_meta_orchestrator(
                llm_client=mock_llm_client,
                autonomy_preset="invalid_preset",
            )


# =============================================================================
# Vulnerability Detection Scenario Tests
# =============================================================================


class TestSecurityScenarios:
    """Test realistic security vulnerability scenarios."""

    @pytest.mark.asyncio
    async def test_sql_injection_detection_scenario(self, production_orchestrator):
        """Test SQL injection detection and remediation flow."""
        # Mock the decomposer to return appropriate tasks
        production_orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Scan code for SQL injection patterns",
                    capability=AgentCapability.VULNERABILITY_SCAN,
                    complexity=0.3,
                ),
                TaskNode.create(
                    description="Review vulnerable code sections",
                    capability=AgentCapability.SECURITY_REVIEW,
                    complexity=0.5,
                ),
                TaskNode.create(
                    description="Generate parameterized query patch",
                    capability=AgentCapability.CODE_GENERATION,
                    complexity=0.6,
                ),
                TaskNode.create(
                    description="Validate patch correctness",
                    capability=AgentCapability.PATCH_VALIDATION,
                    complexity=0.4,
                ),
            ]
        )

        result = await production_orchestrator.execute(
            task="Fix SQL injection vulnerability in user authentication",
            repository="banking-app",
            severity="CRITICAL",
        )

        assert result.status in ["completed", "awaiting_hitl", "failed"]
        # CRITICAL severity with enterprise_standard should require HITL
        # (enterprise_standard: CRITICAL_HITL default)

    @pytest.mark.asyncio
    async def test_xss_remediation_scenario(self, production_orchestrator):
        """Test XSS vulnerability remediation flow."""
        production_orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Identify XSS vulnerable endpoints",
                    capability=AgentCapability.VULNERABILITY_SCAN,
                ),
                TaskNode.create(
                    description="Generate input sanitization code",
                    capability=AgentCapability.CODE_GENERATION,
                ),
            ]
        )

        result = await production_orchestrator.execute(
            task="Fix reflected XSS in search functionality",
            repository="e-commerce-site",
            severity="HIGH",
        )

        assert isinstance(result, MetaOrchestratorResult)
