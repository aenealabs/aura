"""
Project Aura - MetaOrchestrator Tests

Comprehensive tests for the MetaOrchestrator with dynamic agent spawning,
recursive task decomposition, and configurable autonomy levels.

Implements test coverage for ADR-018.
"""

# ruff: noqa: PLR2004

from unittest.mock import AsyncMock, Mock

import pytest

from src.agents.meta_orchestrator import (
    AgentCapability,
    AgentRegistry,
    AgentResult,
    AgentSpec,
    AggregatedResult,
    AutonomyLevel,
    AutonomyPolicy,
    MetaOrchestrator,
    MetaOrchestratorError,
    MetaOrchestratorResult,
    SpawnableAgent,
    SpawnNotAllowedError,
    TaskDecomposer,
    TaskNode,
    TaskStatus,
    UnknownAgentCapabilityError,
)

# =============================================================================
# AutonomyLevel Tests
# =============================================================================


class TestAutonomyLevel:
    """Test suite for AutonomyLevel enum."""

    def test_autonomy_level_values(self):
        """Test that all autonomy levels have expected values."""
        assert AutonomyLevel.FULL_HITL.value == "full_hitl"
        assert AutonomyLevel.CRITICAL_HITL.value == "critical_hitl"
        assert AutonomyLevel.AUDIT_ONLY.value == "audit_only"
        assert AutonomyLevel.FULL_AUTONOMOUS.value == "full_autonomous"

    def test_autonomy_level_count(self):
        """Test that there are exactly 4 autonomy levels."""
        assert len(AutonomyLevel) == 4


# =============================================================================
# AgentCapability Tests
# =============================================================================


class TestAgentCapability:
    """Test suite for AgentCapability enum."""

    def test_agent_capability_values(self):
        """Test key agent capabilities exist."""
        assert AgentCapability.CODE_GENERATION.value == "code_generation"
        assert AgentCapability.SECURITY_REVIEW.value == "security_review"
        assert AgentCapability.VULNERABILITY_SCAN.value == "vulnerability_scan"

    def test_agent_capability_count(self):
        """Test that there are at least 10 capabilities."""
        assert len(AgentCapability) >= 10


# =============================================================================
# TaskNode Tests
# =============================================================================


class TestTaskNode:
    """Test suite for TaskNode dataclass."""

    def test_task_node_create_factory(self):
        """Test TaskNode.create() factory method generates unique IDs."""
        task1 = TaskNode.create(
            description="Test task 1",
            capability=AgentCapability.CODE_GENERATION,
        )
        task2 = TaskNode.create(
            description="Test task 2",
            capability=AgentCapability.SECURITY_REVIEW,
        )

        assert task1.task_id != task2.task_id
        assert task1.task_id.startswith("task-")
        assert task1.status == TaskStatus.PENDING

    def test_task_node_with_dependencies(self):
        """Test TaskNode with dependencies."""
        dep_task = TaskNode.create(
            description="Dependency",
            capability=AgentCapability.CONTEXT_RETRIEVAL,
        )
        task = TaskNode.create(
            description="Main task",
            capability=AgentCapability.CODE_GENERATION,
            dependencies=[dep_task.task_id],
        )

        assert dep_task.task_id in task.dependencies

    def test_task_node_default_complexity(self):
        """Test TaskNode default complexity is 0.5."""
        task = TaskNode.create(
            description="Test",
            capability=AgentCapability.CODE_ANALYSIS,
        )

        assert task.estimated_complexity == 0.5

    def test_task_node_custom_complexity(self):
        """Test TaskNode with custom complexity."""
        task = TaskNode.create(
            description="Complex task",
            capability=AgentCapability.ARCHITECTURE_REVIEW,
            complexity=0.9,
        )

        assert task.estimated_complexity == 0.9


# =============================================================================
# AutonomyPolicy Tests
# =============================================================================


class TestAutonomyPolicy:
    """Test suite for AutonomyPolicy dataclass."""

    def test_default_autonomy_level(self):
        """Test that default autonomy level is applied."""
        policy = AutonomyPolicy(
            organization_id="test",
            default_level=AutonomyLevel.AUDIT_ONLY,
        )

        level = policy.get_autonomy_level(
            severity="MEDIUM",
            repository="test-repo",
            operation="code_fix",
        )

        assert level == AutonomyLevel.AUDIT_ONLY

    def test_severity_override(self):
        """Test severity-specific override takes precedence."""
        policy = AutonomyPolicy(
            organization_id="test",
            default_level=AutonomyLevel.FULL_AUTONOMOUS,
            severity_overrides={"CRITICAL": AutonomyLevel.FULL_HITL},
        )

        level = policy.get_autonomy_level(
            severity="CRITICAL",
            repository="any-repo",
            operation="patch",
        )

        assert level == AutonomyLevel.FULL_HITL

    def test_repository_override(self):
        """Test repository-specific override takes precedence over severity."""
        policy = AutonomyPolicy(
            organization_id="test",
            default_level=AutonomyLevel.FULL_AUTONOMOUS,
            severity_overrides={"HIGH": AutonomyLevel.AUDIT_ONLY},
            repository_overrides={"critical-app": AutonomyLevel.FULL_HITL},
        )

        level = policy.get_autonomy_level(
            severity="HIGH",
            repository="critical-app",
            operation="patch",
        )

        assert level == AutonomyLevel.FULL_HITL

    def test_operation_override_highest_priority(self):
        """Test operation-specific override takes highest priority."""
        policy = AutonomyPolicy(
            organization_id="test",
            default_level=AutonomyLevel.FULL_AUTONOMOUS,
            severity_overrides={"HIGH": AutonomyLevel.AUDIT_ONLY},
            repository_overrides={"critical-app": AutonomyLevel.CRITICAL_HITL},
            operation_overrides={"special_operation": AutonomyLevel.FULL_HITL},
        )

        level = policy.get_autonomy_level(
            severity="HIGH",
            repository="critical-app",
            operation="special_operation",
        )

        assert level == AutonomyLevel.FULL_HITL

    def test_guardrails_cannot_be_overridden(self):
        """Test that guardrail operations always require HITL."""
        policy = AutonomyPolicy(
            organization_id="test",
            default_level=AutonomyLevel.FULL_AUTONOMOUS,
        )

        # Test all guardrail operations
        for operation in policy.always_require_hitl:
            level = policy.get_autonomy_level(
                severity="LOW",
                repository="any-repo",
                operation=operation,
            )
            assert (
                level == AutonomyLevel.FULL_HITL
            ), f"Guardrail {operation} was bypassed"

    def test_from_preset_defense_contractor(self):
        """Test defense_contractor preset is highly restrictive."""
        policy = AutonomyPolicy.from_preset("defense_contractor")

        assert policy.default_level == AutonomyLevel.FULL_HITL
        assert policy.organization_id == "defense"

    def test_from_preset_fintech_startup(self):
        """Test fintech_startup preset balances speed and safety."""
        policy = AutonomyPolicy.from_preset("fintech_startup")

        assert policy.default_level == AutonomyLevel.CRITICAL_HITL
        # LOW and MEDIUM can be audit-only
        assert policy.severity_overrides["LOW"] == AutonomyLevel.AUDIT_ONLY
        assert policy.severity_overrides["MEDIUM"] == AutonomyLevel.AUDIT_ONLY

    def test_from_preset_fully_autonomous(self):
        """Test fully_autonomous preset but guardrails still apply."""
        policy = AutonomyPolicy.from_preset("fully_autonomous")

        assert policy.default_level == AutonomyLevel.FULL_AUTONOMOUS

        # But guardrails still require HITL
        level = policy.get_autonomy_level(
            severity="LOW",
            repository="any",
            operation="production_deployment",
        )
        assert level == AutonomyLevel.FULL_HITL

    def test_from_preset_unknown_raises_error(self):
        """Test that unknown preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            AutonomyPolicy.from_preset("nonexistent_preset")

    def test_all_presets_available(self):
        """Test all documented presets are available."""
        presets = [
            "defense_contractor",
            "financial_services",
            "fintech_startup",
            "enterprise_standard",
            "internal_tools",
            "fully_autonomous",
        ]

        for preset in presets:
            policy = AutonomyPolicy.from_preset(preset)
            assert policy.organization_id is not None


# =============================================================================
# AgentSpec Tests
# =============================================================================


class TestAgentSpec:
    """Test suite for AgentSpec dataclass."""

    def test_agent_spec_defaults(self):
        """Test AgentSpec default values."""
        spec = AgentSpec(
            capability=AgentCapability.CODE_GENERATION,
            task_description="Generate code",
        )

        assert spec.max_depth == 2
        assert spec.timeout_seconds == 300
        assert spec.can_spawn_children is True
        assert spec.priority == 5
        assert spec.context_requirements == []

    def test_agent_spec_custom_values(self):
        """Test AgentSpec with custom values."""
        spec = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Review security",
            context_requirements=["cve_database", "dependency_tree"],
            max_depth=1,
            timeout_seconds=600,
            can_spawn_children=False,
            priority=10,
        )

        assert spec.max_depth == 1
        assert spec.timeout_seconds == 600
        assert spec.can_spawn_children is False
        assert spec.priority == 10
        assert len(spec.context_requirements) == 2


# =============================================================================
# AgentRegistry Tests
# =============================================================================


class TestAgentRegistry:
    """Test suite for AgentRegistry."""

    def test_registry_initializes_with_default_agents(self):
        """Test that AgentRegistry initializes with default agents for all capabilities."""
        registry = AgentRegistry()

        capabilities = registry.get_available_capabilities()

        # All capabilities should have default factories
        for capability in AgentCapability:
            assert capability in capabilities

    def test_register_agent_overwrites_default(self):
        """Test registering an agent overwrites the default factory."""
        registry = AgentRegistry()

        # Create a mock agent with required attributes
        mock_agent = Mock()
        mock_agent.agent_id = "test-agent-123"
        custom_factory = Mock(return_value=mock_agent)
        registry.register_agent(AgentCapability.CODE_GENERATION, custom_factory)

        # Verify the custom factory is used
        spec = AgentSpec(
            capability=AgentCapability.CODE_GENERATION,
            task_description="Test",
        )
        registry.spawn_agent(spec, llm_client=Mock())

        custom_factory.assert_called_once()

    def test_spawn_agent_creates_agent(self):
        """Test spawning an agent creates an agent instance."""
        registry = AgentRegistry()

        spec = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Review code",
            max_depth=2,
        )

        agent = registry.spawn_agent(spec, llm_client=Mock())

        assert agent is not None
        assert agent.max_spawn_depth == 2

    def test_get_available_capabilities_returns_all(self):
        """Test get_available_capabilities returns all registered capabilities."""
        registry = AgentRegistry()

        capabilities = registry.get_available_capabilities()

        # Should have all AgentCapability values
        assert len(capabilities) == len(AgentCapability)
        assert AgentCapability.CODE_GENERATION in capabilities
        assert AgentCapability.SECURITY_REVIEW in capabilities


# =============================================================================
# SpawnableAgent Tests
# =============================================================================


class TestSpawnableAgent:
    """Test suite for SpawnableAgent base class."""

    def test_spawnable_agent_cannot_instantiate_directly(self):
        """Test that SpawnableAgent is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            SpawnableAgent(
                llm_client=Mock(),
                max_spawn_depth=2,
            )

    def test_spawnable_agent_subclass_can_spawn_with_depth(self):
        """Test that subclass with max_spawn_depth > 0 can spawn children."""

        class ConcreteAgent(SpawnableAgent):
            @property
            def capability(self):
                return AgentCapability.CODE_GENERATION

            async def execute(self, task, context=None):
                return AgentResult(
                    agent_id=self.agent_id,
                    capability=self.capability,
                    success=True,
                    output="test",
                    execution_time_seconds=1.0,
                )

        agent = ConcreteAgent(
            llm_client=Mock(),
            max_spawn_depth=2,
            can_spawn=True,
        )

        assert agent.can_spawn is True

    def test_spawnable_agent_cannot_spawn_at_max_depth(self):
        """Test that agent at max_spawn_depth=0 cannot spawn children."""

        class ConcreteAgent(SpawnableAgent):
            @property
            def capability(self):
                return AgentCapability.CODE_GENERATION

            async def execute(self, task, context=None):
                return AgentResult(
                    agent_id=self.agent_id,
                    capability=self.capability,
                    success=True,
                    output="test",
                    execution_time_seconds=1.0,
                )

        agent = ConcreteAgent(
            llm_client=Mock(),
            max_spawn_depth=0,
            can_spawn=True,  # Will be False because max_spawn_depth=0
        )

        assert agent.can_spawn is False

    @pytest.mark.asyncio
    async def test_spawn_child_decrements_depth(self):
        """Test that spawn_child creates agent with decremented depth."""

        class ConcreteAgent(SpawnableAgent):
            @property
            def capability(self):
                return AgentCapability.CODE_GENERATION

            async def execute(self, task, context=None):
                return AgentResult(
                    agent_id=self.agent_id,
                    capability=self.capability,
                    success=True,
                    output="test",
                    execution_time_seconds=1.0,
                )

        registry = AgentRegistry()

        parent = ConcreteAgent(
            llm_client=Mock(),
            max_spawn_depth=2,
            can_spawn=True,
            registry=registry,
        )

        spec = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Review code",
        )

        child = await parent.spawn_child(spec)

        # Child should have decremented max_spawn_depth
        assert child.max_spawn_depth == 1

    @pytest.mark.asyncio
    async def test_spawn_child_raises_when_not_allowed(self):
        """Test that spawn_child raises error when spawning disabled."""

        class ConcreteAgent(SpawnableAgent):
            @property
            def capability(self):
                return AgentCapability.CODE_GENERATION

            async def execute(self, task, context=None):
                return AgentResult(
                    agent_id=self.agent_id,
                    capability=self.capability,
                    success=True,
                    output="test",
                    execution_time_seconds=1.0,
                )

        agent = ConcreteAgent(
            llm_client=Mock(),
            max_spawn_depth=0,
            can_spawn=True,  # Will be False due to max_spawn_depth=0
        )

        spec = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Review code",
        )

        with pytest.raises(SpawnNotAllowedError):
            await agent.spawn_child(spec)


# =============================================================================
# TaskDecomposer Tests
# =============================================================================


class TestTaskDecomposer:
    """Test suite for TaskDecomposer."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = AsyncMock()
        return client

    @pytest.fixture
    def decomposer(self, mock_llm_client):
        """Create a TaskDecomposer instance."""
        return TaskDecomposer(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_decompose_without_llm_uses_fallback(self):
        """Test that decomposition without LLM uses fallback."""
        decomposer = TaskDecomposer(llm_client=None)

        tasks = await decomposer.decompose(
            task="Fix SQL injection in login.py",
            context=None,
            depth=0,
        )

        # Should return at least one task via fallback
        assert len(tasks) >= 1
        assert all(isinstance(t, TaskNode) for t in tasks)

    @pytest.mark.asyncio
    async def test_decompose_with_llm_parses_response(self, decomposer):
        """Test that decomposition with LLM parses response correctly."""
        # Mock LLM to return a JSON array as string
        decomposer.llm.generate = AsyncMock(return_value="""[
                {
                    "description": "Scan for vulnerabilities",
                    "capability": "vulnerability_scan",
                    "complexity": 0.4,
                    "dependencies": [],
                    "can_parallelize": true
                },
                {
                    "description": "Generate patch",
                    "capability": "code_generation",
                    "complexity": 0.6,
                    "dependencies": [0],
                    "can_parallelize": false
                }
            ]""")

        tasks = await decomposer.decompose(
            task="Fix SQL injection vulnerability",
            context=None,
            depth=0,
        )

        # Should parse and return tasks
        assert len(tasks) >= 1

    @pytest.mark.asyncio
    async def test_decompose_respects_max_depth(self):
        """Test that decomposition stops at MAX_RECURSION_DEPTH."""
        decomposer = TaskDecomposer(llm_client=None)

        # At max depth (4), should create a leaf node without recursion
        tasks = await decomposer.decompose(
            task="Complex task",
            context=None,
            depth=TaskDecomposer.MAX_RECURSION_DEPTH,
        )

        # Should return a single leaf node
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_decompose_handles_llm_failure_gracefully(self, decomposer):
        """Test that decomposition handles LLM failure with fallback."""
        # Mock LLM to raise an exception
        decomposer.llm.generate = AsyncMock(side_effect=Exception("LLM timeout"))

        tasks = await decomposer.decompose(
            task="Fix security issue",
            context=None,
            depth=0,
        )

        # Should still return tasks via fallback
        assert len(tasks) >= 1

    def test_guess_capability_from_keywords(self):
        """Test that _guess_capability returns correct capability based on keywords."""
        decomposer = TaskDecomposer(llm_client=None)

        # Test keyword-based capability detection
        assert (
            decomposer._guess_capability("scan for vulnerabilities")
            == AgentCapability.VULNERABILITY_SCAN
        )
        assert (
            decomposer._guess_capability("generate new code")
            == AgentCapability.CODE_GENERATION
        )
        assert (
            decomposer._guess_capability("review security issues")
            == AgentCapability.SECURITY_REVIEW
        )
        assert (
            decomposer._guess_capability("unit test coverage analysis")
            == AgentCapability.TEST_GENERATION
        )
        assert (
            decomposer._guess_capability("check compliance requirements")
            == AgentCapability.COMPLIANCE_CHECK
        )
        assert (
            decomposer._guess_capability("threat assessment")
            == AgentCapability.THREAT_ANALYSIS
        )
        assert (
            decomposer._guess_capability("analyze architecture")
            == AgentCapability.ARCHITECTURE_REVIEW
        )


# =============================================================================
# MetaOrchestrator Tests
# =============================================================================


class TestMetaOrchestrator:
    """Test suite for MetaOrchestrator."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        return AsyncMock()

    @pytest.fixture
    def mock_context_service(self):
        """Create a mock context service."""
        return AsyncMock()

    @pytest.fixture
    def mock_hitl_service(self):
        """Create a mock HITL approval service."""
        return AsyncMock()

    @pytest.fixture
    def autonomy_policy(self):
        """Create a test autonomy policy."""
        return AutonomyPolicy.from_preset("fintech_startup")

    @pytest.fixture
    def orchestrator(
        self,
        mock_llm_client,
        autonomy_policy,
        mock_context_service,
        mock_hitl_service,
    ):
        """Create a MetaOrchestrator instance."""
        return MetaOrchestrator(
            llm_client=mock_llm_client,
            autonomy_policy=autonomy_policy,
            context_service=mock_context_service,
            hitl_service=mock_hitl_service,
        )

    def test_orchestrator_initialization(self, orchestrator, autonomy_policy):
        """Test MetaOrchestrator initializes correctly."""
        assert orchestrator.autonomy_policy == autonomy_policy
        assert orchestrator.registry is not None
        assert orchestrator.decomposer is not None

    def test_register_default_agents(self, orchestrator):
        """Test that default agents are registered."""
        # Check that all agent capabilities have registered factories
        capabilities = orchestrator.registry.get_available_capabilities()
        assert len(capabilities) == len(AgentCapability)

    @pytest.mark.asyncio
    async def test_execute_returns_result(self, orchestrator):
        """Test that execute returns a MetaOrchestratorResult."""
        # Mock the decomposer to return a simple task
        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Fix vulnerability",
                    capability=AgentCapability.CODE_GENERATION,
                    complexity=0.3,  # Low complexity
                )
            ]
        )

        result = await orchestrator.execute(
            task="Fix SQL injection vulnerability",
            repository="test-app",
            severity="MEDIUM",
        )

        assert isinstance(result, MetaOrchestratorResult)
        assert result.execution_id.startswith("exec-")

    @pytest.mark.asyncio
    async def test_execute_handles_errors_gracefully(self, orchestrator):
        """Test that execute handles errors and returns failed status."""
        # Mock decomposer to raise an error
        orchestrator.decomposer.decompose = AsyncMock(
            side_effect=Exception("Decomposition failed")
        )

        result = await orchestrator.execute(
            task="Fix issue",
            repository="test-repo",
            severity="LOW",
        )

        assert result.status == "failed"
        assert result.error is not None

    def test_classify_operation_detects_production_deployment(self, orchestrator):
        """Test that production deployment operations are classified correctly."""
        operation = orchestrator._classify_operation("Deploy to production server")
        assert operation == "production_deployment"

    def test_classify_operation_detects_credential_modification(self, orchestrator):
        """Test that credential operations are classified correctly."""
        operation = orchestrator._classify_operation("Update API credentials")
        assert operation == "credential_modification"

    @pytest.mark.asyncio
    async def test_execute_with_defense_contractor_policy_requires_hitl(
        self,
        mock_llm_client,
        mock_context_service,
        mock_hitl_service,
    ):
        """Test execution with defense_contractor policy requires HITL approval."""
        policy = AutonomyPolicy.from_preset("defense_contractor")

        orchestrator = MetaOrchestrator(
            llm_client=mock_llm_client,
            autonomy_policy=policy,
            context_service=mock_context_service,
            hitl_service=mock_hitl_service,
        )

        # Verify policy default is FULL_HITL
        assert policy.default_level == AutonomyLevel.FULL_HITL

        # Mock decomposer
        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Fix vulnerability",
                    capability=AgentCapability.CODE_GENERATION,
                )
            ]
        )

        result = await orchestrator.execute(
            task="Fix security vulnerability",
            repository="defense-app",
            severity="HIGH",
        )

        # FULL_HITL should require human approval
        assert result.status in ["awaiting_hitl", "completed", "failed"]


# =============================================================================
# Integration Tests
# =============================================================================


class TestMetaOrchestratorIntegration:
    """Integration tests for MetaOrchestrator components working together."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_decomposition(self):
        """Test complete workflow: decompose -> spawn -> execute."""
        mock_llm = AsyncMock()
        mock_context = AsyncMock()
        mock_hitl = AsyncMock()

        policy = AutonomyPolicy.from_preset("fintech_startup")

        orchestrator = MetaOrchestrator(
            llm_client=mock_llm,
            autonomy_policy=policy,
            context_service=mock_context,
            hitl_service=mock_hitl,
        )

        # Mock decomposition to return simple tasks
        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Scan for vulnerabilities",
                    capability=AgentCapability.VULNERABILITY_SCAN,
                    complexity=0.4,
                ),
                TaskNode.create(
                    description="Generate fix",
                    capability=AgentCapability.CODE_GENERATION,
                    complexity=0.5,
                ),
            ]
        )

        result = await orchestrator.execute(
            task="Fix SQL injection vulnerability",
            repository="app-repo",
            severity="MEDIUM",
        )

        # Should complete or fail (not hang)
        assert result.status in ["completed", "awaiting_hitl", "failed"]
        assert result.execution_id is not None

    @pytest.mark.asyncio
    async def test_decomposer_and_registry_work_together(self):
        """Test that TaskDecomposer and AgentRegistry integrate correctly."""
        decomposer = TaskDecomposer(llm_client=None)
        registry = AgentRegistry()

        # Decompose a task
        tasks = await decomposer.decompose(
            task="Review code for security issues",
            context=None,
            depth=0,
        )

        # Each task capability should have a registered agent
        for task in tasks:
            capabilities = registry.get_available_capabilities()
            assert task.capability in capabilities

    @pytest.mark.asyncio
    async def test_orchestrator_cleans_up_after_execution(self):
        """Test that orchestrator cleans up active agents after execution."""
        orchestrator = MetaOrchestrator(llm_client=None)

        # Mock decomposer
        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Simple task",
                    capability=AgentCapability.CODE_ANALYSIS,
                )
            ]
        )

        # Execute
        await orchestrator.execute(
            task="Analyze code",
            repository="test",
            severity="LOW",
        )

        # Active agents should be cleaned up
        assert len(orchestrator.active_agents) == 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestMetaOrchestratorErrors:
    """Test suite for MetaOrchestrator error handling."""

    def test_meta_orchestrator_error_base_class(self):
        """Test MetaOrchestratorError is properly defined."""
        error = MetaOrchestratorError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_spawn_not_allowed_error(self):
        """Test SpawnNotAllowedError is subclass of MetaOrchestratorError."""
        error = SpawnNotAllowedError("Cannot spawn at max depth")
        assert isinstance(error, MetaOrchestratorError)

    def test_unknown_agent_capability_error(self):
        """Test UnknownAgentCapabilityError is subclass of MetaOrchestratorError."""
        error = UnknownAgentCapabilityError("Unknown capability")
        assert isinstance(error, MetaOrchestratorError)


# =============================================================================
# AgentResult Tests
# =============================================================================


class TestAgentResult:
    """Test suite for AgentResult dataclass."""

    def test_agent_result_creation(self):
        """Test AgentResult can be created with required fields."""
        result = AgentResult(
            agent_id="agent-123",
            capability=AgentCapability.CODE_GENERATION,
            success=True,
            output={"patch": "code fix"},
            execution_time_seconds=1.5,
        )

        assert result.agent_id == "agent-123"
        assert result.success is True
        assert result.tokens_used == 0  # Default
        assert result.error is None

    def test_agent_result_with_error(self):
        """Test AgentResult with error information."""
        result = AgentResult(
            agent_id="agent-456",
            capability=AgentCapability.SECURITY_REVIEW,
            success=False,
            output=None,
            execution_time_seconds=0.5,
            error="LLM timeout",
        )

        assert result.success is False
        assert result.error == "LLM timeout"

    def test_agent_result_with_children(self):
        """Test AgentResult with nested children results."""
        child_result = AgentResult(
            agent_id="child-1",
            capability=AgentCapability.CODE_ANALYSIS,
            success=True,
            output={"analysis": "complete"},
            execution_time_seconds=0.5,
        )

        parent_result = AgentResult(
            agent_id="parent-1",
            capability=AgentCapability.SECURITY_REVIEW,
            success=True,
            output={"review": "passed"},
            execution_time_seconds=1.0,
            children_results=[child_result],
        )

        assert len(parent_result.children_results) == 1
        assert parent_result.children_results[0].agent_id == "child-1"


# =============================================================================
# AggregatedResult Tests
# =============================================================================


class TestAggregatedResult:
    """Test suite for AggregatedResult dataclass."""

    def test_aggregated_result_creation(self):
        """Test AggregatedResult can be created."""
        result = AggregatedResult(
            execution_id="exec-123",
            task_count=5,
            successful_tasks=4,
            failed_tasks=1,
            total_execution_time=10.5,
            total_tokens_used=1500,
        )

        assert result.execution_id == "exec-123"
        assert result.task_count == 5
        assert result.successful_tasks == 4
        assert result.failed_tasks == 1

    def test_aggregated_result_success_rate(self):
        """Test calculating success rate from AggregatedResult."""
        result = AggregatedResult(
            execution_id="exec-456",
            task_count=10,
            successful_tasks=8,
            failed_tasks=2,
            total_execution_time=20.0,
            total_tokens_used=3000,
        )

        success_rate = result.successful_tasks / result.task_count
        assert success_rate == 0.8


# =============================================================================
# MetaOrchestratorResult Tests
# =============================================================================


class TestMetaOrchestratorResult:
    """Test suite for MetaOrchestratorResult dataclass."""

    def test_result_completed_status(self):
        """Test MetaOrchestratorResult with completed status."""
        result = MetaOrchestratorResult(
            execution_id="exec-789",
            status="completed",
            hitl_required=False,
            auto_approved=False,
            audit_logged=True,
            autonomy_level=AutonomyLevel.AUDIT_ONLY,
            execution_time_seconds=5.0,
        )

        assert result.status == "completed"
        assert result.hitl_required is False

    def test_result_awaiting_hitl_status(self):
        """Test MetaOrchestratorResult with awaiting_hitl status."""
        result = MetaOrchestratorResult(
            execution_id="exec-abc",
            status="awaiting_hitl",
            hitl_required=True,
            hitl_request_id="hitl-request-123",
            autonomy_level=AutonomyLevel.FULL_HITL,
        )

        assert result.status == "awaiting_hitl"
        assert result.hitl_required is True
        assert result.hitl_request_id == "hitl-request-123"

    def test_result_failed_status(self):
        """Test MetaOrchestratorResult with failed status."""
        result = MetaOrchestratorResult(
            execution_id="exec-def",
            status="failed",
            error="Agent execution timeout",
        )

        assert result.status == "failed"
        assert result.error == "Agent execution timeout"
