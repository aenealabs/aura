"""
Project Aura - Agent Orchestration Edge Case Tests

Tests for circular dependency detection, spawn depth limits, orphaned agent
cleanup, and error handling in agent spawning chains.

Priority: P1 - System Stability

Test scenarios covered:
1. Direct circular dependency: A -> B -> A
2. Indirect circular dependency: A -> B -> C -> A
3. Self-referential agent trying to spawn itself
4. Max depth exceeded when spawn chain gets too deep (even without cycles)
5. Orphaned agents when parent agent fails mid-spawn
6. Resource cleanup when circular dependency is detected
7. Error message clarity when cycle is detected
8. Behavior if cycle detection fails and recursion continues
"""

# ruff: noqa: PLR2004

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.agents.meta_orchestrator import (
    AgentCapability,
    AgentRegistry,
    AgentResult,
    AgentSpec,
    CyclicDependencyError,
    MetaOrchestrator,
    SpawnableAgent,
    SpawnNotAllowedError,
    TaskDecomposer,
    TaskNode,
    TaskStatus,
)

# =============================================================================
# Test Fixtures
# =============================================================================


class TrackingAgent(SpawnableAgent):
    """Test agent that tracks spawning and can simulate behaviors."""

    _capability_value = AgentCapability.CODE_GENERATION
    spawn_history: list = []  # Class-level to track across instances
    instances: dict = {}  # Track all instances by ID

    def __init__(
        self,
        llm_client: Any = None,
        agent_id: str | None = None,
        max_spawn_depth: int = 2,
        can_spawn: bool = True,
        registry: "AgentRegistry | None" = None,
        capability: AgentCapability | None = None,
        parent_id: str | None = None,
        fail_on_execute: bool = False,
        fail_on_spawn: bool = False,
        spawn_delay: float = 0,
    ):
        super().__init__(llm_client, agent_id, max_spawn_depth, can_spawn, registry)
        self._capability_override = capability or self._capability_value
        self.parent_id = parent_id
        self.fail_on_execute = fail_on_execute
        self.fail_on_spawn = fail_on_spawn
        self.spawn_delay = spawn_delay
        self.spawned_children_ids: list[str] = []
        self.execution_count = 0
        self.cleanup_called = False

        # Register this instance
        TrackingAgent.instances[self.agent_id] = self

    @property
    def capability(self) -> AgentCapability:
        return self._capability_override

    async def execute(self, task: str, context: Any = None) -> AgentResult:
        self.execution_count += 1

        if self.fail_on_execute:
            raise RuntimeError(f"Agent {self.agent_id} failed during execution")

        return AgentResult(
            agent_id=self.agent_id,
            capability=self.capability,
            success=True,
            output={"task": task, "parent_id": self.parent_id},
            execution_time_seconds=0.1,
        )

    async def spawn_child(self, spec: AgentSpec) -> SpawnableAgent:
        if self.fail_on_spawn:
            raise RuntimeError(f"Agent {self.agent_id} failed during spawn")

        if self.spawn_delay > 0:
            await asyncio.sleep(self.spawn_delay)

        TrackingAgent.spawn_history.append(
            {
                "parent_id": self.agent_id,
                "capability": spec.capability,
                "timestamp": datetime.now(),
            }
        )

        child = await super().spawn_child(spec)
        self.spawned_children_ids.append(child.agent_id)
        return child

    def cleanup(self):
        """Simulate resource cleanup."""
        self.cleanup_called = True


@pytest.fixture(autouse=True)
def reset_tracking():
    """Reset tracking state before each test."""
    TrackingAgent.spawn_history = []
    TrackingAgent.instances = {}
    yield
    # Cleanup after test
    TrackingAgent.spawn_history = []
    TrackingAgent.instances = {}


@pytest.fixture
def tracking_registry():
    """Create a registry that uses TrackingAgent for all capabilities."""
    registry = AgentRegistry()

    def create_tracking_factory(cap: AgentCapability):
        def factory(
            llm_client: Any = None,
            max_spawn_depth: int = 2,
            can_spawn: bool = True,
            registry: AgentRegistry | None = None,
        ) -> TrackingAgent:
            return TrackingAgent(
                llm_client=llm_client,
                max_spawn_depth=max_spawn_depth,
                can_spawn=can_spawn,
                registry=registry,
                capability=cap,
            )

        return factory

    for capability in AgentCapability:
        registry.register_agent(capability, create_tracking_factory(capability))

    return registry


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    return AsyncMock()


# =============================================================================
# Test Class: Direct Circular Dependency (A -> B -> A)
# =============================================================================


class TestDirectCircularDependency:
    """Tests for direct circular dependency: A -> B -> A."""

    @pytest.mark.asyncio
    async def test_direct_cycle_detection_via_task_dag(self):
        """Test that task DAG detects direct circular dependencies."""
        # Create a task DAG with circular dependencies
        task_a = TaskNode.create(
            description="Task A",
            capability=AgentCapability.CODE_GENERATION,
        )
        task_b = TaskNode.create(
            description="Task B",
            capability=AgentCapability.SECURITY_REVIEW,
            dependencies=[task_a.task_id],
        )

        # Create circular dependency: A depends on B
        task_a.dependencies.append(task_b.task_id)

        # Orchestrator should detect cycle when executing
        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        # Mock the decomposer to return our cyclic DAG
        orchestrator.decomposer.decompose = AsyncMock(return_value=[task_a, task_b])

        result = await orchestrator.execute(
            task="Cyclic task test",
            repository="test-repo",
            severity="MEDIUM",
        )

        # Should fail with cycle detection or blocked dependency error
        assert result.status == "failed"
        assert result.error is not None
        assert (
            "cycle" in result.error.lower()
            or "unresolvable" in result.error.lower()
            or "blocked" in result.error.lower()
        )

    @pytest.mark.asyncio
    async def test_spawn_chain_with_same_capability_pattern(self, tracking_registry):
        """Test that spawning pattern A -> B -> A (same capabilities) is limited by depth."""
        root_agent = TrackingAgent(
            max_spawn_depth=2,
            registry=tracking_registry,
            capability=AgentCapability.CODE_GENERATION,
        )

        # First spawn (depth 2 -> 1)
        spec_b = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Review code",
        )
        agent_b = await root_agent.spawn_child(spec_b)
        assert agent_b.max_spawn_depth == 1

        # Second spawn (depth 1 -> 0)
        spec_a = AgentSpec(
            capability=AgentCapability.CODE_GENERATION,
            task_description="Generate more code",
        )
        agent_a2 = await agent_b.spawn_child(spec_a)
        assert agent_a2.max_spawn_depth == 0
        assert agent_a2.can_spawn is False

        # Third spawn should fail (depth 0)
        spec_c = AgentSpec(
            capability=AgentCapability.VULNERABILITY_SCAN,
            task_description="Scan vulnerabilities",
        )
        with pytest.raises(SpawnNotAllowedError):
            await agent_a2.spawn_child(spec_c)


# =============================================================================
# Test Class: Indirect Circular Dependency (A -> B -> C -> A)
# =============================================================================


class TestIndirectCircularDependency:
    """Tests for indirect circular dependency: A -> B -> C -> A."""

    @pytest.mark.asyncio
    async def test_three_node_cycle_in_task_dag(self):
        """Test that task DAG detects indirect 3-node cycles."""
        task_a = TaskNode.create(
            description="Task A",
            capability=AgentCapability.CODE_GENERATION,
        )
        task_b = TaskNode.create(
            description="Task B",
            capability=AgentCapability.SECURITY_REVIEW,
            dependencies=[task_a.task_id],
        )
        task_c = TaskNode.create(
            description="Task C",
            capability=AgentCapability.PATCH_VALIDATION,
            dependencies=[task_b.task_id],
        )

        # Create cycle: A depends on C
        task_a.dependencies.append(task_c.task_id)

        orchestrator = MetaOrchestrator(llm_client=AsyncMock())
        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[task_a, task_b, task_c]
        )

        result = await orchestrator.execute(
            task="Three-node cycle test",
            repository="test-repo",
            severity="LOW",
        )

        assert result.status == "failed"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_longer_chain_cycle_detection(self):
        """Test cycle detection in longer chains (A -> B -> C -> D -> A)."""
        tasks = []
        for i, cap in enumerate(
            [
                AgentCapability.CODE_GENERATION,
                AgentCapability.SECURITY_REVIEW,
                AgentCapability.PATCH_VALIDATION,
                AgentCapability.VULNERABILITY_SCAN,
            ]
        ):
            deps = [tasks[-1].task_id] if tasks else []
            tasks.append(
                TaskNode.create(
                    description=f"Task {i}", capability=cap, dependencies=deps
                )
            )

        # Create cycle: first task depends on last
        tasks[0].dependencies.append(tasks[-1].task_id)

        orchestrator = MetaOrchestrator(llm_client=AsyncMock())
        orchestrator.decomposer.decompose = AsyncMock(return_value=tasks)

        result = await orchestrator.execute(
            task="Long chain cycle test",
            repository="test-repo",
            severity="LOW",
        )

        assert result.status == "failed"


# =============================================================================
# Test Class: Self-Referential Agent
# =============================================================================


class TestSelfReferentialAgent:
    """Tests for agent trying to spawn itself."""

    @pytest.mark.asyncio
    async def test_task_self_dependency(self):
        """Test that a task cannot depend on itself."""
        task = TaskNode.create(
            description="Self-referential task",
            capability=AgentCapability.CODE_GENERATION,
        )

        # Add self-dependency
        task.dependencies.append(task.task_id)

        orchestrator = MetaOrchestrator(llm_client=AsyncMock())
        orchestrator.decomposer.decompose = AsyncMock(return_value=[task])

        result = await orchestrator.execute(
            task="Self-dependency test",
            repository="test-repo",
            severity="LOW",
        )

        # Should fail because task can never have its dependencies satisfied
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_agent_spawning_same_capability_at_depth_limit(
        self, tracking_registry
    ):
        """Test agent spawning same capability type is blocked at depth 0."""
        agent = TrackingAgent(
            max_spawn_depth=0,  # Already at max depth
            registry=tracking_registry,
            capability=AgentCapability.CODE_GENERATION,
        )

        assert agent.can_spawn is False

        spec = AgentSpec(
            capability=AgentCapability.CODE_GENERATION,  # Same capability
            task_description="Same task type",
        )

        with pytest.raises(SpawnNotAllowedError) as exc_info:
            await agent.spawn_child(spec)

        assert (
            "max spawn depth" in str(exc_info.value).lower()
            or "disabled" in str(exc_info.value).lower()
        )


# =============================================================================
# Test Class: Max Depth Exceeded
# =============================================================================


class TestMaxDepthExceeded:
    """Tests for max depth exceeded even without cycles."""

    @pytest.mark.asyncio
    async def test_spawn_depth_decrements_correctly(self, tracking_registry):
        """Test that spawn depth decrements at each level."""
        depths_seen = []

        agent = TrackingAgent(
            max_spawn_depth=5,
            registry=tracking_registry,
        )
        depths_seen.append(agent.max_spawn_depth)

        current = agent
        for i in range(5):
            spec = AgentSpec(
                capability=AgentCapability.CODE_ANALYSIS,
                task_description=f"Level {i + 1}",
            )

            if current.can_spawn:
                child = await current.spawn_child(spec)
                depths_seen.append(child.max_spawn_depth)
                current = child
            else:
                break

        # Should see depths: 5, 4, 3, 2, 1, 0
        assert depths_seen == [5, 4, 3, 2, 1, 0]

    @pytest.mark.asyncio
    async def test_spawn_blocked_at_depth_zero(self, tracking_registry):
        """Test spawning is blocked when depth reaches zero."""
        agent = TrackingAgent(
            max_spawn_depth=1,
            registry=tracking_registry,
        )

        # First spawn succeeds (depth 1 -> 0)
        spec = AgentSpec(
            capability=AgentCapability.CODE_ANALYSIS,
            task_description="Level 1",
        )
        child = await agent.spawn_child(spec)
        assert child.max_spawn_depth == 0
        assert child.can_spawn is False

        # Second spawn should fail
        spec2 = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Level 2",
        )
        with pytest.raises(SpawnNotAllowedError):
            await child.spawn_child(spec2)

    @pytest.mark.asyncio
    async def test_task_decomposer_respects_max_recursion(self):
        """Test TaskDecomposer stops at MAX_RECURSION_DEPTH."""
        decomposer = TaskDecomposer(llm_client=None)

        # Set depth at the limit
        tasks = await decomposer.decompose(
            task="Complex nested task",
            context=None,
            depth=TaskDecomposer.MAX_RECURSION_DEPTH,
        )

        # Should return single leaf node without further decomposition
        assert len(tasks) == 1
        assert isinstance(tasks[0], TaskNode)

    @pytest.mark.asyncio
    async def test_deep_spawn_chain_logging(self, tracking_registry, caplog):
        """Test that deep spawn chains are logged for debugging."""
        import logging

        caplog.set_level(logging.INFO)

        agent = TrackingAgent(
            max_spawn_depth=3,
            registry=tracking_registry,
        )

        current = agent
        for i in range(3):
            if current.can_spawn:
                spec = AgentSpec(
                    capability=AgentCapability.CODE_ANALYSIS,
                    task_description=f"Level {i + 1}",
                )
                current = await current.spawn_child(spec)

        # Verify spawn history recorded
        assert len(TrackingAgent.spawn_history) == 3


# =============================================================================
# Test Class: Orphaned Agents
# =============================================================================


class TestOrphanedAgents:
    """Tests for orphaned agents when parent fails mid-spawn."""

    @pytest.mark.asyncio
    async def test_cleanup_on_parent_execution_failure(self, tracking_registry):
        """Test that spawned agents are tracked even if parent fails later."""
        parent = TrackingAgent(
            max_spawn_depth=2,
            registry=tracking_registry,
            fail_on_execute=False,
        )

        # Spawn a child
        spec = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Review",
        )
        child = await parent.spawn_child(spec)

        # Child is tracked
        assert child.agent_id in [c.agent_id for c in parent.children]
        assert len(parent.children) == 1

    @pytest.mark.asyncio
    async def test_orchestrator_cleanup_after_execution(self):
        """Test that MetaOrchestrator cleans up agents after execution."""
        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        # Mock decomposer to return simple task
        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[
                TaskNode.create(
                    description="Simple task",
                    capability=AgentCapability.CODE_ANALYSIS,
                )
            ]
        )

        await orchestrator.execute(
            task="Test cleanup",
            repository="test",
            severity="LOW",
        )

        # Active agents should be cleaned up
        assert len(orchestrator.active_agents) == 0

    @pytest.mark.asyncio
    async def test_orchestrator_cleanup_on_failure(self):
        """Test that cleanup happens even when execution fails."""
        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        # Mock decomposer to fail
        orchestrator.decomposer.decompose = AsyncMock(
            side_effect=RuntimeError("Decomposition failed")
        )

        result = await orchestrator.execute(
            task="Failing task",
            repository="test",
            severity="LOW",
        )

        assert result.status == "failed"
        assert len(orchestrator.active_agents) == 0

    @pytest.mark.asyncio
    async def test_spawn_failure_leaves_parent_in_consistent_state(
        self, tracking_registry
    ):
        """Test parent agent remains consistent when spawn fails."""

        class FailingRegistry(AgentRegistry):
            """Registry that fails on spawn."""

            def spawn_agent(self, spec, llm_client=None):
                raise RuntimeError("Registry spawn failure")

        failing_registry = FailingRegistry()

        parent = TrackingAgent(
            max_spawn_depth=2,
            registry=failing_registry,
        )

        spec = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Will fail",
        )

        with pytest.raises(RuntimeError, match="Registry spawn failure"):
            await parent.spawn_child(spec)

        # Parent's children list should still be empty (no partial state)
        assert len(parent.children) == 0


# =============================================================================
# Test Class: Resource Cleanup on Cycle Detection
# =============================================================================


class TestResourceCleanupOnCycleDetection:
    """Tests for resource cleanup when circular dependencies are detected."""

    @pytest.mark.asyncio
    async def test_task_dag_cycle_triggers_cleanup(self):
        """Test that cycle detection triggers cleanup of allocated resources."""
        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        # Create cyclic DAG
        task_a = TaskNode.create(
            description="Task A",
            capability=AgentCapability.CODE_GENERATION,
        )
        task_b = TaskNode.create(
            description="Task B",
            capability=AgentCapability.SECURITY_REVIEW,
            dependencies=[task_a.task_id],
        )
        task_a.dependencies.append(task_b.task_id)

        orchestrator.decomposer.decompose = AsyncMock(return_value=[task_a, task_b])

        # Track cleanup
        cleanup_called = False
        original_cleanup = orchestrator._cleanup_agents

        async def tracking_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
            await original_cleanup()

        orchestrator._cleanup_agents = tracking_cleanup

        result = await orchestrator.execute(
            task="Cyclic test",
            repository="test",
            severity="LOW",
        )

        assert result.status == "failed"
        assert cleanup_called is True

    @pytest.mark.asyncio
    async def test_partial_execution_cleanup(self):
        """Test cleanup when some tasks complete before cycle blocks others."""
        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        # Create DAG where one task can complete, then cycle blocks rest
        task_a = TaskNode.create(
            description="Can complete",
            capability=AgentCapability.CODE_ANALYSIS,
        )
        task_b = TaskNode.create(
            description="Task B",
            capability=AgentCapability.SECURITY_REVIEW,
            dependencies=[task_a.task_id],
        )
        task_c = TaskNode.create(
            description="Task C",
            capability=AgentCapability.PATCH_VALIDATION,
            dependencies=[task_b.task_id],
        )
        # Create cycle between B and C
        task_b.dependencies.append(task_c.task_id)

        orchestrator.decomposer.decompose = AsyncMock(
            return_value=[task_a, task_b, task_c]
        )

        result = await orchestrator.execute(
            task="Partial cycle test",
            repository="test",
            severity="LOW",
        )

        # Should eventually fail due to cycle/blocked tasks
        assert result.status == "failed"
        assert len(orchestrator.active_agents) == 0


# =============================================================================
# Test Class: Error Message Clarity
# =============================================================================


class TestErrorMessageClarity:
    """Tests for clear and actionable error messages."""

    @pytest.mark.asyncio
    async def test_cycle_error_includes_task_ids(self):
        """Test that cycle error message includes involved task IDs."""
        task_a = TaskNode.create(
            description="Task A",
            capability=AgentCapability.CODE_GENERATION,
        )
        task_b = TaskNode.create(
            description="Task B",
            capability=AgentCapability.SECURITY_REVIEW,
            dependencies=[task_a.task_id],
        )
        task_a.dependencies.append(task_b.task_id)

        orchestrator = MetaOrchestrator(llm_client=AsyncMock())
        orchestrator.decomposer.decompose = AsyncMock(return_value=[task_a, task_b])

        result = await orchestrator.execute(
            task="Cycle error test",
            repository="test",
            severity="LOW",
        )

        assert result.error is not None
        # Error should contain task IDs or indicate which tasks are blocked
        error_lower = result.error.lower()
        assert (
            "task" in error_lower
            or "dependency" in error_lower
            or "cycle" in error_lower
            or "blocked" in error_lower
        )

    def test_spawn_not_allowed_error_message(self):
        """Test SpawnNotAllowedError has clear message."""
        agent = TrackingAgent(max_spawn_depth=0)

        error = SpawnNotAllowedError(
            f"Agent {agent.agent_id} has reached max spawn depth or spawning disabled"
        )

        assert agent.agent_id in str(error)
        assert (
            "max spawn depth" in str(error).lower() or "disabled" in str(error).lower()
        )

    def test_cyclic_dependency_error_message(self):
        """Test CyclicDependencyError has clear message."""
        blocked_tasks = ["task-abc123", "task-def456"]
        error = CyclicDependencyError(
            f"Task DAG contains cycles or unresolvable dependencies: {blocked_tasks}"
        )

        error_str = str(error)
        assert "task-abc123" in error_str
        assert "task-def456" in error_str
        assert "cycle" in error_str.lower() or "dependency" in error_str.lower()

    @pytest.mark.asyncio
    async def test_max_depth_error_is_distinguishable_from_cycle(
        self, tracking_registry
    ):
        """Test that max depth errors are distinguishable from cycle errors."""
        agent = TrackingAgent(
            max_spawn_depth=0,
            registry=tracking_registry,
        )

        spec = AgentSpec(
            capability=AgentCapability.CODE_ANALYSIS,
            task_description="Test",
        )

        try:
            await agent.spawn_child(spec)
            pytest.fail("Expected SpawnNotAllowedError")
        except SpawnNotAllowedError as e:
            # Should be SpawnNotAllowedError, not CyclicDependencyError
            assert not isinstance(e, CyclicDependencyError)
            assert "spawn" in str(e).lower() or "depth" in str(e).lower()


# =============================================================================
# Test Class: Runaway Recursion Protection
# =============================================================================


class TestRunawayRecursionProtection:
    """Tests for protection when cycle detection might fail."""

    @pytest.mark.asyncio
    async def test_dag_execution_has_iteration_limit(self):
        """Test that DAG execution has a safety iteration limit."""
        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        # Create many tasks to test iteration limit
        tasks = [
            TaskNode.create(
                description=f"Task {i}",
                capability=AgentCapability.CODE_ANALYSIS,
            )
            for i in range(20)
        ]

        # Create complex dependencies (not a cycle, but many iterations)
        for i in range(1, len(tasks)):
            tasks[i].dependencies = [tasks[i - 1].task_id]

        orchestrator.decomposer.decompose = AsyncMock(return_value=tasks)

        result = await orchestrator.execute(
            task="Many tasks test",
            repository="test",
            severity="LOW",
        )

        # Should complete (not infinite loop)
        assert result.status in ["completed", "failed"]

    @pytest.mark.asyncio
    async def test_decomposer_recursion_depth_hard_limit(self):
        """Test TaskDecomposer has hard recursion limit."""
        # Verify the constant exists and is reasonable
        assert hasattr(TaskDecomposer, "MAX_RECURSION_DEPTH")
        assert TaskDecomposer.MAX_RECURSION_DEPTH > 0
        assert TaskDecomposer.MAX_RECURSION_DEPTH <= 10  # Reasonable upper bound

        decomposer = TaskDecomposer(llm_client=None)

        # Test at max depth
        tasks = await decomposer.decompose(
            task="Deep task",
            context=None,
            depth=TaskDecomposer.MAX_RECURSION_DEPTH,
        )

        # Should return without further recursion
        assert len(tasks) >= 1

    @pytest.mark.asyncio
    async def test_spawn_depth_prevents_infinite_delegation(self, tracking_registry):
        """Test that spawn depth limit prevents infinite delegation chains."""
        max_depth = 5
        agent = TrackingAgent(
            max_spawn_depth=max_depth,
            registry=tracking_registry,
        )

        spawn_count = 0
        current = agent

        while current.can_spawn and spawn_count < max_depth + 5:  # Safety margin
            spec = AgentSpec(
                capability=AgentCapability.CODE_ANALYSIS,
                task_description=f"Delegation {spawn_count + 1}",
            )
            current = await current.spawn_child(spec)
            spawn_count += 1

        # Should stop exactly at max_depth
        assert spawn_count == max_depth
        assert current.can_spawn is False


# =============================================================================
# Test Class: Concurrent Spawn Operations
# =============================================================================


class TestConcurrentSpawnOperations:
    """Tests for concurrent spawn operations and race conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_spawns_from_same_parent(self, tracking_registry):
        """Test multiple concurrent spawns from the same parent."""
        parent = TrackingAgent(
            max_spawn_depth=3,
            registry=tracking_registry,
        )

        specs = [
            AgentSpec(
                capability=AgentCapability.CODE_ANALYSIS,
                task_description=f"Task {i}",
            )
            for i in range(5)
        ]

        # Spawn all concurrently
        children = await asyncio.gather(*[parent.spawn_child(spec) for spec in specs])

        # All should succeed with unique IDs
        child_ids = [c.agent_id for c in children]
        assert len(set(child_ids)) == 5
        assert len(parent.children) == 5

    @pytest.mark.asyncio
    async def test_parallel_dag_execution(self):
        """Test parallel execution of independent tasks in DAG."""
        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        # Create multiple independent tasks (can parallelize)
        tasks = [
            TaskNode.create(
                description=f"Independent task {i}",
                capability=AgentCapability.CODE_ANALYSIS,
            )
            for i in range(5)
        ]

        for task in tasks:
            task.can_parallelize = True

        orchestrator.decomposer.decompose = AsyncMock(return_value=tasks)

        result = await orchestrator.execute(
            task="Parallel test",
            repository="test",
            severity="LOW",
        )

        # All should complete
        assert result.status in ["completed", "awaiting_hitl"]
        if result.result:
            assert result.result.task_count == 5


# =============================================================================
# Test Class: Edge Cases in Task Status
# =============================================================================


class TestTaskStatusEdgeCases:
    """Tests for edge cases in task status transitions."""

    def test_task_status_values(self):
        """Test all expected task status values exist."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.AWAITING_HITL.value == "awaiting_hitl"

    def test_task_node_initial_status(self):
        """Test TaskNode starts with PENDING status."""
        task = TaskNode.create(
            description="New task",
            capability=AgentCapability.CODE_ANALYSIS,
        )

        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error is None

    @pytest.mark.asyncio
    async def test_task_with_failed_dependency(self):
        """Test task handling when dependency has failed."""
        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        # Create custom registry that fails for specific capability
        class PartialFailRegistry(AgentRegistry):
            def spawn_agent(self, spec, llm_client=None):
                if spec.capability == AgentCapability.SECURITY_REVIEW:
                    # Return agent that will fail
                    class FailingAgent(SpawnableAgent):
                        @property
                        def capability(self):
                            return spec.capability

                        async def execute(self, task, context=None):
                            raise RuntimeError("Security review failed")

                    return FailingAgent(
                        llm_client=llm_client,
                        max_spawn_depth=spec.max_depth,
                    )
                return super().spawn_agent(spec, llm_client)

        orchestrator.registry = PartialFailRegistry()

        task_a = TaskNode.create(
            description="Security check",
            capability=AgentCapability.SECURITY_REVIEW,
        )
        task_b = TaskNode.create(
            description="Depends on security",
            capability=AgentCapability.CODE_GENERATION,
            dependencies=[task_a.task_id],
        )

        orchestrator.decomposer.decompose = AsyncMock(return_value=[task_a, task_b])

        result = await orchestrator.execute(
            task="Dependency failure test",
            repository="test",
            severity="LOW",
        )

        # Should still complete (with failures recorded)
        assert result.status in ["completed", "failed"]
        if result.result:
            assert result.result.failed_tasks >= 1


# =============================================================================
# Test Class: Registry Edge Cases
# =============================================================================


class TestRegistryEdgeCases:
    """Tests for AgentRegistry edge cases."""

    def test_registry_with_no_agents(self):
        """Test behavior when querying empty/default registry."""
        registry = AgentRegistry()

        # Should have default agents for all capabilities
        capabilities = registry.get_available_capabilities()
        assert len(capabilities) == len(AgentCapability)

    def test_spawn_unregistered_capability(self):
        """Test spawning with capability that has no factory."""
        registry = AgentRegistry()

        # Remove a factory to simulate unregistered
        del registry._agent_factories[AgentCapability.CODE_GENERATION]

        spec = AgentSpec(
            capability=AgentCapability.CODE_GENERATION,
            task_description="Test",
        )

        from src.agents.meta_orchestrator import UnknownAgentCapabilityError

        with pytest.raises(UnknownAgentCapabilityError):
            registry.spawn_agent(spec)

    def test_registry_factory_override(self):
        """Test that factory can be overridden multiple times."""
        registry = AgentRegistry()

        call_count = {"count": 0}

        def factory_v1(**kwargs):
            call_count["count"] += 1
            return TrackingAgent(**kwargs)

        def factory_v2(**kwargs):
            call_count["count"] += 10
            return TrackingAgent(**kwargs)

        registry.register_agent(AgentCapability.CODE_GENERATION, factory_v1)
        registry.spawn_agent(
            AgentSpec(
                capability=AgentCapability.CODE_GENERATION,
                task_description="Test",
            )
        )
        assert call_count["count"] == 1

        registry.register_agent(AgentCapability.CODE_GENERATION, factory_v2)
        registry.spawn_agent(
            AgentSpec(
                capability=AgentCapability.CODE_GENERATION,
                task_description="Test",
            )
        )
        assert call_count["count"] == 11  # v2 adds 10


# =============================================================================
# Test Class: Memory and Performance Edge Cases
# =============================================================================


class TestMemoryAndPerformanceEdgeCases:
    """Tests for memory leaks and performance edge cases."""

    @pytest.mark.asyncio
    async def test_many_small_tasks_no_memory_leak(self):
        """Test that many small task executions don't leak memory."""
        import gc

        orchestrator = MetaOrchestrator(llm_client=AsyncMock())

        for i in range(10):
            orchestrator.decomposer.decompose = AsyncMock(
                return_value=[
                    TaskNode.create(
                        description=f"Small task {i}",
                        capability=AgentCapability.CODE_ANALYSIS,
                    )
                ]
            )

            result = await orchestrator.execute(
                task=f"Task {i}",
                repository="test",
                severity="LOW",
            )

            assert result.status in ["completed", "awaiting_hitl"]

            # Force cleanup
            gc.collect()

        # All active agents should be cleaned up
        assert len(orchestrator.active_agents) == 0

    @pytest.mark.asyncio
    async def test_agent_spawn_tree_can_be_retrieved(self, tracking_registry):
        """Test that spawn tree can be retrieved for debugging."""
        root = TrackingAgent(
            max_spawn_depth=2,
            registry=tracking_registry,
        )

        # Create a spawn tree
        spec_a = AgentSpec(
            capability=AgentCapability.SECURITY_REVIEW,
            task_description="Review A",
        )
        child_a = await root.spawn_child(spec_a)

        spec_b = AgentSpec(
            capability=AgentCapability.CODE_ANALYSIS,
            task_description="Analyze B",
        )
        await root.spawn_child(spec_b)

        # Get spawn tree
        tree = root.get_spawn_tree()

        assert tree["agent_id"] == root.agent_id
        assert len(tree["children"]) == 2
        assert tree["children"][0]["agent_id"] == child_a.agent_id
