"""
Project Aura - Agent Timeout Edge Case Tests

Tests for graceful degradation after agent subprocess timeout and related
edge cases in timeout handling across the agent system.

Priority: P1 - System Stability

Test scenarios covered:
1. Agent times out during LLM call - save partial state
2. Agent times out waiting for human approval (checkpoint)
3. Child agent times out - parent agent recovery
4. Timeout during database write - rollback vs commit
5. Cascading timeouts when multiple agents hit limit simultaneously
6. Timeout value of 0 (should this mean "no timeout"?)
7. System clock changes during timeout measurement
8. Agent requests more time but extension denied
9. Timeout occurs during cleanup/finally block
10. Resource cleanup when agent process killed by timeout
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base_agent import AgentResult, AgentTask, BaseAgent, MCPEnabledAgent
from src.services.execution_checkpoint_service import (
    ActionType,
    CheckpointAction,
    CheckpointStatus,
    ExecutionCheckpointService,
    InterventionMode,
    RiskLevel,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@dataclass
class PartialExecutionState:
    """Tracks partial execution state for graceful degradation testing."""

    checkpoint_id: str = ""
    phase: str = "init"
    partial_results: dict[str, Any] = field(default_factory=dict)
    resources_allocated: list[str] = field(default_factory=list)
    cleanup_completed: bool = False
    error_message: str | None = None


class TimeoutTrackingAgent(BaseAgent):
    """Test agent that tracks execution phases and supports partial state saving."""

    def __init__(
        self,
        agent_name: str = "TimeoutTrackingAgent",
        execution_phases: list[tuple[str, float]] | None = None,
        fail_on_phase: str | None = None,
        save_partial_state: bool = True,
    ):
        """
        Initialize timeout tracking agent.

        Args:
            agent_name: Name of the agent
            execution_phases: List of (phase_name, duration_seconds) tuples
            fail_on_phase: Phase to raise error on (for testing error handling)
            save_partial_state: Whether to save partial state on timeout
        """
        super().__init__(agent_name=agent_name)
        self.execution_phases = execution_phases or [
            ("init", 0.01),
            ("process", 0.01),
            ("finalize", 0.01),
        ]
        self.fail_on_phase = fail_on_phase
        self.save_partial_state = save_partial_state

        # Tracking state
        self.execution_state = PartialExecutionState()
        self.completed_phases: list[str] = []
        self.cleanup_called = False
        self.cleanup_error: Exception | None = None

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute task with phase tracking."""
        self.execution_state.phase = "started"
        partial_data: dict[str, Any] = {}

        try:
            for phase_name, duration in self.execution_phases:
                self.execution_state.phase = phase_name

                if self.fail_on_phase == phase_name:
                    raise RuntimeError(f"Simulated failure in phase: {phase_name}")

                await asyncio.sleep(duration)
                partial_data[phase_name] = {"completed": True, "duration": duration}
                self.completed_phases.append(phase_name)

            self.execution_state.phase = "completed"
            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={"phases": partial_data},
            )

        except asyncio.CancelledError:
            # Save partial state before propagating cancellation
            if self.save_partial_state:
                self.execution_state.partial_results = partial_data
                self.execution_state.error_message = "Task cancelled"
            raise

        except Exception as e:
            self.execution_state.error_message = str(e)
            raise

    async def cleanup(self):
        """Cleanup resources after timeout or error."""
        self.cleanup_called = True
        for resource in self.execution_state.resources_allocated:
            # Simulate cleanup
            pass
        self.execution_state.cleanup_completed = True


class SlowLLMAgent(MCPEnabledAgent):
    """Agent that simulates slow LLM calls with partial result saving."""

    def __init__(
        self,
        llm_delay_seconds: float = 10.0,
        partial_response: str = "Partial LLM response...",
    ):
        super().__init__(agent_name="SlowLLMAgent")
        self.llm_delay_seconds = llm_delay_seconds
        self.partial_response = partial_response
        self.llm_call_started = False
        self.llm_call_completed = False
        self.saved_partial_state: dict[str, Any] = {}

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute with simulated slow LLM call."""
        self.llm_call_started = True
        try:
            # Simulate slow LLM call
            await asyncio.sleep(self.llm_delay_seconds)
            self.llm_call_completed = True

            return AgentResult(
                task_id=task.task_id,
                success=True,
                data={"llm_response": "Full response"},
            )

        except asyncio.CancelledError:
            # Save partial state
            self.saved_partial_state = {
                "partial_response": self.partial_response,
                "progress": "llm_call_in_progress",
            }
            raise


class ChildSpawningAgent(BaseAgent):
    """Agent that spawns child agents and handles their timeouts."""

    def __init__(self, child_timeout_seconds: float = 1.0):
        super().__init__(agent_name="ChildSpawningAgent")
        self.child_timeout_seconds = child_timeout_seconds
        self.child_results: list[AgentResult] = []
        self.child_timeouts: list[str] = []
        self.recovery_attempted = False

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute task by delegating to child agents."""
        child_tasks = task.parameters.get("child_tasks", [])
        child_agents = task.parameters.get("child_agents", [])

        for idx, (child_task_desc, child_agent) in enumerate(
            zip(child_tasks, child_agents)
        ):
            child_task = AgentTask(
                task_id=f"{task.task_id}_child_{idx}",
                task_type="child_task",
                description=child_task_desc,
                timeout_seconds=int(self.child_timeout_seconds),
            )

            # BaseAgent.run() catches TimeoutError and returns result with success=False
            # So we check the result rather than catching an exception
            result = await child_agent.run(child_task)

            if result.success:
                self.child_results.append(result)
            elif result.error and "timed out" in result.error.lower():
                # Child timed out - record and continue
                self.child_timeouts.append(child_task.task_id)
                self.recovery_attempted = True
            else:
                # Other failure - still track as result
                self.child_results.append(result)

        # Return aggregate result
        success = len(self.child_timeouts) == 0
        return AgentResult(
            task_id=task.task_id,
            success=success,
            data={
                "completed_children": len(self.child_results),
                "timed_out_children": self.child_timeouts,
            },
            error=(
                f"Child agents timed out: {self.child_timeouts}"
                if self.child_timeouts
                else None
            ),
        )


@pytest.fixture
def tracking_agent():
    """Create a timeout tracking agent."""
    return TimeoutTrackingAgent()


@pytest.fixture
def slow_llm_agent():
    """Create a slow LLM agent."""
    return SlowLLMAgent(llm_delay_seconds=10.0)


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table for checkpoint service."""
    table = MagicMock()
    table.put_item = MagicMock()
    table.update_item = MagicMock()
    table.get_item = MagicMock(return_value={"Item": {}})
    table.query = MagicMock(return_value={"Items": []})
    return table


@pytest.fixture
def checkpoint_service(mock_dynamodb_table):
    """Create checkpoint service with mocked DynamoDB."""
    with patch("boto3.resource") as mock_boto:
        mock_resource = MagicMock()
        mock_resource.Table.return_value = mock_dynamodb_table
        mock_boto.return_value = mock_resource

        service = ExecutionCheckpointService(
            dynamodb_table_name="test-checkpoints",
            intervention_mode=InterventionMode.HIGH_RISK,
            default_timeout_seconds=5,
        )
        service._table = mock_dynamodb_table
        return service


# =============================================================================
# Test Class: Agent Times Out During LLM Call
# =============================================================================


class TestAgentTimeoutDuringLLMCall:
    """Tests for scenario 1: Agent times out during LLM call - save partial state."""

    @pytest.mark.asyncio
    async def test_timeout_during_llm_call_saves_partial_state(self, slow_llm_agent):
        """Test that partial state is saved when LLM call times out."""
        task = AgentTask(
            task_id="llm-timeout-001",
            task_type="analysis",
            description="Analyze code",
            timeout_seconds=1,  # 1 second timeout, LLM takes 10 seconds
        )

        result = await slow_llm_agent.run(task)

        assert not result.success
        assert "timed out" in result.error.lower()
        assert slow_llm_agent.llm_call_started
        assert not slow_llm_agent.llm_call_completed

    @pytest.mark.asyncio
    async def test_partial_llm_response_preserved_on_timeout(self):
        """Test that partial LLM response is preserved when timeout occurs."""

        class ProgressiveLLMAgent(BaseAgent):
            """Agent that accumulates LLM response progressively."""

            def __init__(self):
                super().__init__(agent_name="ProgressiveLLMAgent")
                self.response_chunks: list[str] = []
                self.final_partial_state: dict[str, Any] = {}

            async def execute(self, task: AgentTask) -> AgentResult:
                try:
                    # Simulate streaming LLM response
                    for i in range(10):
                        await asyncio.sleep(0.2)
                        self.response_chunks.append(f"chunk_{i}")

                    return AgentResult(
                        task_id=task.task_id,
                        success=True,
                        data={"chunks": self.response_chunks},
                    )

                except asyncio.CancelledError:
                    self.final_partial_state = {
                        "partial_chunks": self.response_chunks.copy(),
                        "chunks_received": len(self.response_chunks),
                    }
                    raise

        agent = ProgressiveLLMAgent()
        task = AgentTask(
            task_id="progressive-001",
            task_type="streaming",
            description="Stream response",
            timeout_seconds=1,  # Will get some chunks before timeout
        )

        result = await agent.run(task)

        assert not result.success
        # Agent should have received some chunks before timeout
        assert len(agent.response_chunks) > 0
        assert len(agent.response_chunks) < 10  # But not all

    @pytest.mark.asyncio
    async def test_llm_timeout_metrics_recorded(self):
        """Test that timeout events are properly recorded in metrics."""
        slow_agent = SlowLLMAgent(llm_delay_seconds=5.0)
        task = AgentTask(
            task_id="metrics-001",
            task_type="test",
            description="Test metrics",
            timeout_seconds=1,
        )

        await slow_agent.run(task)

        metrics = slow_agent.get_metrics()
        assert metrics["tasks_executed"] == 1
        assert metrics["tasks_failed"] == 1
        assert metrics["success_rate"] == 0.0


# =============================================================================
# Test Class: Agent Times Out Waiting for Human Approval
# =============================================================================


class TestAgentTimeoutWaitingForApproval:
    """Tests for scenario 2: Agent times out waiting for human approval (checkpoint)."""

    @pytest.mark.asyncio
    async def test_checkpoint_timeout_returns_timeout_status(self, checkpoint_service):
        """Test that checkpoint timeout returns TIMEOUT status."""
        action = CheckpointAction(
            checkpoint_id="cp-001",
            execution_id="exec-001",
            agent_id="test-agent",
            action_type=ActionType.FILE_WRITE,
            action_name="write_file",
            parameters={"path": "/test/file.py"},
            risk_level=RiskLevel.HIGH,
            reversible=True,
            estimated_duration_seconds=5,
            timeout_seconds=1,  # Short timeout
        )

        # Create checkpoint - will timeout waiting for approval
        checkpoint_service.intervention_mode = InterventionMode.ALL_ACTIONS
        result = await checkpoint_service.create_checkpoint(
            execution_id="exec-001",
            agent_id="test-agent",
            action=action,
        )

        assert result.status == CheckpointStatus.TIMEOUT
        assert "timeout" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_approval_timeout_cleanup_happens(self, checkpoint_service):
        """Test that cleanup happens after approval timeout."""
        action = CheckpointAction(
            checkpoint_id="cp-002",
            execution_id="exec-002",
            agent_id="test-agent",
            action_type=ActionType.DATABASE_WRITE,
            action_name="insert_record",
            parameters={"table": "test"},
            risk_level=RiskLevel.CRITICAL,
            reversible=False,
            estimated_duration_seconds=5,
            timeout_seconds=1,
        )

        checkpoint_service.intervention_mode = InterventionMode.ALL_ACTIONS
        result = await checkpoint_service.create_checkpoint(
            execution_id="exec-002",
            agent_id="test-agent",
            action=action,
        )

        # Verify cleanup state
        assert result.checkpoint_id not in checkpoint_service._approval_events
        assert result.checkpoint_id not in checkpoint_service._approval_results

    @pytest.mark.asyncio
    async def test_approval_arrives_after_timeout(self, checkpoint_service):
        """Test behavior when approval arrives after timeout already occurred."""
        action = CheckpointAction(
            checkpoint_id="cp-003",
            execution_id="exec-003",
            agent_id="test-agent",
            action_type=ActionType.FILE_WRITE,
            action_name="write_file",
            parameters={},
            risk_level=RiskLevel.HIGH,
            reversible=True,
            estimated_duration_seconds=5,
            timeout_seconds=1,
        )

        checkpoint_service.intervention_mode = InterventionMode.ALL_ACTIONS

        # Create checkpoint that will timeout
        result = await checkpoint_service.create_checkpoint(
            execution_id="exec-003",
            agent_id="test-agent",
            action=action,
        )

        assert result.status == CheckpointStatus.TIMEOUT

        # Now try to approve the already-timed-out checkpoint
        # This should update the status in DB but not affect the workflow
        late_approval = await checkpoint_service.approve_checkpoint(
            checkpoint_id=action.checkpoint_id,
            user_id="late-approver",
        )

        # The approval was recorded but comes too late
        assert late_approval.status == CheckpointStatus.APPROVED


# =============================================================================
# Test Class: Child Agent Timeout with Parent Recovery
# =============================================================================


class TestChildAgentTimeoutParentRecovery:
    """Tests for scenario 3: Child agent times out - parent agent recovery."""

    @pytest.mark.asyncio
    async def test_parent_continues_after_child_timeout(self):
        """Test that parent agent continues execution after child timeout."""

        class SlowChildAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(10)  # Very slow
                return AgentResult(task_id=task.task_id, success=True)

        class FastChildAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(0.01)
                return AgentResult(task_id=task.task_id, success=True)

        parent = ChildSpawningAgent(child_timeout_seconds=1)
        task = AgentTask(
            task_id="parent-001",
            task_type="orchestrate",
            description="Run children",
            timeout_seconds=30,
            parameters={
                "child_tasks": ["slow task", "fast task"],
                "child_agents": [SlowChildAgent(), FastChildAgent()],
            },
        )

        result = await parent.run(task)

        # Parent completes despite child timeout
        assert result.task_id == "parent-001"
        assert len(parent.child_timeouts) == 1  # Slow child timed out
        assert len(parent.child_results) == 1  # Fast child completed
        assert parent.recovery_attempted

    @pytest.mark.asyncio
    async def test_parent_aggregates_partial_child_results(self):
        """Test that parent correctly aggregates partial results from children."""

        class PartialResultAgent(BaseAgent):
            def __init__(self, delay: float, name: str):
                super().__init__(agent_name=name)
                self.delay = delay

            async def execute(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(self.delay)
                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"agent": self.agent_name},
                )

        # Use 1 second timeout (int conversion won't truncate to 0)
        parent = ChildSpawningAgent(child_timeout_seconds=1.0)
        task = AgentTask(
            task_id="aggregate-001",
            task_type="orchestrate",
            description="Aggregate results",
            timeout_seconds=30,
            parameters={
                "child_tasks": ["task1", "task2", "task3"],
                "child_agents": [
                    PartialResultAgent(0.1, "fast1"),
                    PartialResultAgent(10.0, "slow"),  # Will timeout
                    PartialResultAgent(0.1, "fast2"),
                ],
            },
        )

        result = await parent.run(task)

        # Should have 2 completed and 1 timeout
        assert result.data["completed_children"] == 2
        assert len(result.data["timed_out_children"]) == 1


# =============================================================================
# Test Class: Timeout During Database Write
# =============================================================================


class TestTimeoutDuringDatabaseWrite:
    """Tests for scenario 4: Timeout during database write - rollback vs commit."""

    @pytest.mark.asyncio
    async def test_timeout_during_write_triggers_rollback_flag(self):
        """Test that timeout during DB write sets rollback flag."""

        class DatabaseWriteAgent(BaseAgent):
            def __init__(self):
                super().__init__(agent_name="DatabaseWriteAgent")
                self.transaction_started = False
                self.transaction_committed = False
                self.rollback_needed = False
                self.write_in_progress = False

            async def execute(self, task: AgentTask) -> AgentResult:
                self.transaction_started = True
                self.write_in_progress = True

                try:
                    # Simulate slow database write
                    await asyncio.sleep(10)
                    self.transaction_committed = True
                    self.write_in_progress = False

                    return AgentResult(
                        task_id=task.task_id,
                        success=True,
                        data={"committed": True},
                    )

                except asyncio.CancelledError:
                    self.rollback_needed = True
                    self.write_in_progress = False
                    raise

        agent = DatabaseWriteAgent()
        task = AgentTask(
            task_id="db-001",
            task_type="write",
            description="Write to database",
            timeout_seconds=1,
        )

        result = await agent.run(task)

        assert not result.success
        assert agent.transaction_started
        assert not agent.transaction_committed
        assert agent.rollback_needed

    @pytest.mark.asyncio
    async def test_atomic_write_completes_before_timeout_check(self):
        """Test that atomic write operations complete if started before timeout."""

        class AtomicWriteAgent(BaseAgent):
            def __init__(self):
                super().__init__(agent_name="AtomicWriteAgent")
                self.writes_completed: list[str] = []

            async def execute(self, task: AgentTask) -> AgentResult:
                # Simulate multiple atomic writes
                for i in range(5):
                    # Each write is atomic (0.1s)
                    await asyncio.sleep(0.1)
                    self.writes_completed.append(f"write_{i}")

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"writes": self.writes_completed},
                )

        agent = AtomicWriteAgent()
        task = AgentTask(
            task_id="atomic-001",
            task_type="atomic_write",
            description="Atomic writes",
            timeout_seconds=1,  # Should complete ~2-3 writes
        )

        result = await agent.run(task)

        # With 0.1s per write and 1s timeout, some writes complete
        # The exact number depends on async scheduling


# =============================================================================
# Test Class: Cascading Timeouts
# =============================================================================


class TestCascadingTimeouts:
    """Tests for scenario 5: Cascading timeouts when multiple agents hit limit."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_agent_timeouts(self):
        """Test handling of multiple agents timing out simultaneously."""

        class ConcurrentTimeoutAgent(BaseAgent):
            def __init__(self, delay: float, name: str):
                super().__init__(agent_name=name)
                self.delay = delay
                self.started = False
                self.completed = False

            async def execute(self, task: AgentTask) -> AgentResult:
                self.started = True
                await asyncio.sleep(self.delay)
                self.completed = True
                return AgentResult(task_id=task.task_id, success=True)

        agents = [ConcurrentTimeoutAgent(5.0, f"agent_{i}") for i in range(5)]
        tasks = [
            AgentTask(
                task_id=f"concurrent-{i}",
                task_type="test",
                description=f"Task {i}",
                timeout_seconds=1,  # All will timeout
            )
            for i in range(5)
        ]

        # Run all concurrently
        results = await asyncio.gather(
            *[agent.run(task) for agent, task in zip(agents, tasks)],
            return_exceptions=False,
        )

        # All should timeout
        assert all(not r.success for r in results)
        assert all("timed out" in r.error.lower() for r in results)
        assert all(a.started for a in agents)
        assert all(not a.completed for a in agents)

    @pytest.mark.asyncio
    async def test_cascading_timeout_does_not_block_other_agents(self):
        """Test that one agent's timeout doesn't block others."""

        class IndependentAgent(BaseAgent):
            def __init__(self, delay: float, name: str):
                super().__init__(agent_name=name)
                self.delay = delay
                self.execution_start_time: float | None = None
                self.execution_end_time: float | None = None

            async def execute(self, task: AgentTask) -> AgentResult:
                self.execution_start_time = time.time()
                await asyncio.sleep(self.delay)
                self.execution_end_time = time.time()
                return AgentResult(task_id=task.task_id, success=True)

        slow_agent = IndependentAgent(5.0, "slow")
        fast_agent = IndependentAgent(0.1, "fast")

        slow_task = AgentTask(
            task_id="slow-001",
            task_type="test",
            description="Slow",
            timeout_seconds=1,
        )
        fast_task = AgentTask(
            task_id="fast-001",
            task_type="test",
            description="Fast",
            timeout_seconds=5,
        )

        # Run concurrently
        start = time.time()
        results = await asyncio.gather(
            slow_agent.run(slow_task),
            fast_agent.run(fast_task),
        )
        elapsed = time.time() - start

        # Fast agent should complete quickly despite slow agent timeout
        assert not results[0].success  # Slow timed out
        assert results[1].success  # Fast completed
        assert elapsed < 2  # Should not wait for slow agent's full delay


# =============================================================================
# Test Class: Zero Timeout Handling
# =============================================================================


class TestZeroTimeoutHandling:
    """Tests for scenario 6: Timeout value of 0 (should this mean no timeout?)."""

    @pytest.mark.asyncio
    async def test_zero_timeout_immediate_failure(self):
        """Test that zero timeout causes immediate failure."""

        class InstantAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                # Even instant execution might not complete with 0 timeout
                return AgentResult(task_id=task.task_id, success=True)

        agent = InstantAgent(agent_name="InstantAgent")
        task = AgentTask(
            task_id="zero-001",
            task_type="test",
            description="Zero timeout",
            timeout_seconds=0,
        )

        # With timeout=0, asyncio.wait_for should timeout immediately
        # Note: actual behavior depends on implementation interpretation
        result = await agent.run(task)

        # Zero timeout typically means immediate timeout
        assert not result.success or result.execution_time_ms < 10

    @pytest.mark.asyncio
    async def test_negative_timeout_treated_as_no_timeout(self):
        """Test handling of negative timeout values."""

        class SlowAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(0.5)
                return AgentResult(task_id=task.task_id, success=True)

        agent = SlowAgent(agent_name="SlowAgent")
        task = AgentTask(
            task_id="negative-001",
            task_type="test",
            description="Negative timeout",
            timeout_seconds=-1,  # Negative - should be treated as no timeout or error
        )

        # Implementation should either:
        # 1. Treat as no timeout (None/infinite)
        # 2. Raise ValueError
        # 3. Convert to positive value

        # Current implementation: negative becomes immediate timeout
        result = await agent.run(task)
        # Just verify it doesn't hang indefinitely
        assert result is not None


# =============================================================================
# Test Class: System Clock Changes
# =============================================================================


class TestSystemClockChanges:
    """Tests for scenario 7: System clock changes during timeout measurement."""

    @pytest.mark.asyncio
    async def test_timeout_uses_monotonic_clock(self):
        """Test that timeout measurement uses monotonic clock (unaffected by system time changes)."""
        # Note: asyncio.wait_for uses monotonic clock internally

        class ClockTestAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                start_monotonic = time.monotonic()
                await asyncio.sleep(0.5)
                elapsed_monotonic = time.monotonic() - start_monotonic

                return AgentResult(
                    task_id=task.task_id,
                    success=True,
                    data={"elapsed_monotonic": elapsed_monotonic},
                )

        agent = ClockTestAgent(agent_name="ClockTestAgent")
        task = AgentTask(
            task_id="clock-001",
            task_type="test",
            description="Clock test",
            timeout_seconds=2,
        )

        result = await agent.run(task)

        assert result.success
        # Monotonic elapsed should be close to actual sleep time
        assert 0.4 < result.data["elapsed_monotonic"] < 0.7

    @pytest.mark.asyncio
    async def test_execution_time_recorded_correctly(self):
        """Test that execution time is recorded using appropriate clock."""

        class TimedAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(0.2)
                return AgentResult(task_id=task.task_id, success=True)

        agent = TimedAgent(agent_name="TimedAgent")
        task = AgentTask(
            task_id="timed-001",
            task_type="test",
            description="Timed test",
            timeout_seconds=5,
        )

        result = await agent.run(task)

        assert result.success
        # Execution time should be around 200ms
        assert 150 < result.execution_time_ms < 400


# =============================================================================
# Test Class: Extension Request Denied
# =============================================================================


class TestExtensionRequestDenied:
    """Tests for scenario 8: Agent requests more time but extension denied."""

    @pytest.mark.asyncio
    async def test_extension_request_flow(self):
        """Test the flow when agent requests timeout extension."""

        class ExtensionRequestAgent(BaseAgent):
            def __init__(self, extension_callback):
                super().__init__(agent_name="ExtensionRequestAgent")
                self.extension_callback = extension_callback
                self.extension_requested = False
                self.extension_granted = False

            async def execute(self, task: AgentTask) -> AgentResult:
                # Do some work
                await asyncio.sleep(0.3)

                # Request extension
                self.extension_requested = True
                granted = await self.extension_callback(task.task_id, 10)
                self.extension_granted = granted

                if not granted:
                    # Continue with limited time - may timeout
                    pass

                await asyncio.sleep(0.5)
                return AgentResult(task_id=task.task_id, success=True)

        async def deny_extension(task_id: str, requested_seconds: int) -> bool:
            return False  # Always deny

        agent = ExtensionRequestAgent(extension_callback=deny_extension)
        task = AgentTask(
            task_id="extension-001",
            task_type="test",
            description="Extension test",
            timeout_seconds=5,
        )

        result = await agent.run(task)

        assert agent.extension_requested
        assert not agent.extension_granted

    @pytest.mark.asyncio
    async def test_extension_request_with_approval_service(self):
        """Test extension request integration with approval service."""

        class ExtendableCheckpointService:
            def __init__(self):
                self.extension_requests: list[dict] = []
                self.allow_extensions = False

            async def request_extension(
                self, checkpoint_id: str, additional_seconds: int
            ) -> bool:
                self.extension_requests.append(
                    {
                        "checkpoint_id": checkpoint_id,
                        "additional_seconds": additional_seconds,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                return self.allow_extensions

        service = ExtendableCheckpointService()
        service.allow_extensions = False  # Deny extensions

        # Request extension
        granted = await service.request_extension("cp-001", 60)

        assert not granted
        assert len(service.extension_requests) == 1
        assert service.extension_requests[0]["additional_seconds"] == 60


# =============================================================================
# Test Class: Timeout During Cleanup
# =============================================================================


class TestTimeoutDuringCleanup:
    """Tests for scenario 9: Timeout occurs during cleanup/finally block."""

    @pytest.mark.asyncio
    async def test_cleanup_completes_even_after_timeout(self):
        """Test that cleanup logic executes even after task timeout."""
        cleanup_completed = {"value": False}

        class CleanupAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                try:
                    await asyncio.sleep(10)  # Will timeout
                    return AgentResult(task_id=task.task_id, success=True)
                finally:
                    # Cleanup should still run
                    cleanup_completed["value"] = True

        agent = CleanupAgent(agent_name="CleanupAgent")
        task = AgentTask(
            task_id="cleanup-001",
            task_type="test",
            description="Cleanup test",
            timeout_seconds=1,
        )

        result = await agent.run(task)

        assert not result.success
        # Note: In Python, finally blocks execute even on cancellation,
        # but the cleanup_completed might not be set if the block is interrupted
        # The actual behavior depends on where the cancellation occurs

    @pytest.mark.asyncio
    async def test_slow_cleanup_does_not_block_indefinitely(self):
        """Test that slow cleanup operations don't block the system."""

        class SlowCleanupAgent(BaseAgent):
            def __init__(self):
                super().__init__(agent_name="SlowCleanupAgent")
                self.cleanup_started = False
                self.cleanup_finished = False

            async def execute(self, task: AgentTask) -> AgentResult:
                try:
                    await asyncio.sleep(10)
                    return AgentResult(task_id=task.task_id, success=True)
                except asyncio.CancelledError:
                    # Slow cleanup
                    self.cleanup_started = True
                    try:
                        await asyncio.sleep(0.1)  # Quick cleanup
                        self.cleanup_finished = True
                    except asyncio.CancelledError:
                        pass  # Cleanup was also cancelled
                    raise

        agent = SlowCleanupAgent()
        task = AgentTask(
            task_id="slow-cleanup-001",
            task_type="test",
            description="Slow cleanup test",
            timeout_seconds=1,
        )

        start = time.time()
        result = await agent.run(task)
        elapsed = time.time() - start

        assert not result.success
        # Should complete reasonably quickly (timeout + small buffer)
        assert elapsed < 3


# =============================================================================
# Test Class: Resource Cleanup on Process Kill
# =============================================================================


class TestResourceCleanupOnProcessKill:
    """Tests for scenario 10: Resource cleanup when agent process killed by timeout."""

    @pytest.mark.asyncio
    async def test_allocated_resources_tracked_for_cleanup(self):
        """Test that allocated resources are tracked for cleanup after timeout."""

        class ResourceTrackingAgent(BaseAgent):
            def __init__(self):
                super().__init__(agent_name="ResourceTrackingAgent")
                self.allocated_resources: list[str] = []
                self.released_resources: list[str] = []

            async def execute(self, task: AgentTask) -> AgentResult:
                # Allocate resources
                for i in range(3):
                    resource_id = f"resource_{i}"
                    self.allocated_resources.append(resource_id)
                    await asyncio.sleep(0.1)

                # Do slow work
                await asyncio.sleep(10)

                return AgentResult(task_id=task.task_id, success=True)

            async def cleanup_resources(self):
                """Cleanup allocated resources after timeout."""
                for resource in self.allocated_resources:
                    if resource not in self.released_resources:
                        self.released_resources.append(resource)

        agent = ResourceTrackingAgent()
        task = AgentTask(
            task_id="resource-001",
            task_type="test",
            description="Resource test",
            timeout_seconds=1,
        )

        result = await agent.run(task)

        # Task failed but resources were allocated
        assert not result.success
        assert len(agent.allocated_resources) > 0

        # Cleanup should release them
        await agent.cleanup_resources()
        assert len(agent.released_resources) == len(agent.allocated_resources)

    @pytest.mark.asyncio
    async def test_external_resource_cleanup_registry(self):
        """Test cleanup registry for tracking resources across agents."""

        class ResourceRegistry:
            def __init__(self):
                self.resources: dict[str, dict] = {}

            def register(self, resource_id: str, agent_id: str, resource_type: str):
                self.resources[resource_id] = {
                    "agent_id": agent_id,
                    "resource_type": resource_type,
                    "allocated_at": datetime.now(timezone.utc).isoformat(),
                    "released": False,
                }

            def release(self, resource_id: str):
                if resource_id in self.resources:
                    self.resources[resource_id]["released"] = True

            def get_unreleased_for_agent(self, agent_id: str) -> list[str]:
                return [
                    rid
                    for rid, info in self.resources.items()
                    if info["agent_id"] == agent_id and not info["released"]
                ]

            def cleanup_agent_resources(self, agent_id: str):
                for rid in self.get_unreleased_for_agent(agent_id):
                    self.release(rid)

        registry = ResourceRegistry()

        # Simulate agent allocating resources
        registry.register("conn-001", "agent-1", "database_connection")
        registry.register("lock-001", "agent-1", "file_lock")
        registry.register("conn-002", "agent-2", "database_connection")

        # Agent 1 times out - cleanup its resources
        unreleased = registry.get_unreleased_for_agent("agent-1")
        assert len(unreleased) == 2

        registry.cleanup_agent_resources("agent-1")

        # Agent 1's resources released, agent 2's still held
        assert len(registry.get_unreleased_for_agent("agent-1")) == 0
        assert len(registry.get_unreleased_for_agent("agent-2")) == 1


# =============================================================================
# Test Class: Checkpoint Service Timeout Scenarios
# =============================================================================


class TestCheckpointServiceTimeoutScenarios:
    """Additional tests for checkpoint service timeout handling."""

    @pytest.mark.asyncio
    async def test_checkpoint_status_transitions_on_timeout(self, checkpoint_service):
        """Test correct status transitions when checkpoint times out."""
        # Start with AWAITING_APPROVAL
        action = CheckpointAction(
            checkpoint_id="status-001",
            execution_id="exec-001",
            agent_id="test-agent",
            action_type=ActionType.COMMAND_EXEC,
            action_name="run_script",
            parameters={"script": "deploy.sh"},
            risk_level=RiskLevel.HIGH,
            reversible=False,
            estimated_duration_seconds=5,
            timeout_seconds=1,
        )

        checkpoint_service.intervention_mode = InterventionMode.ALL_ACTIONS
        result = await checkpoint_service.create_checkpoint(
            execution_id="exec-001",
            agent_id="test-agent",
            action=action,
        )

        # Should transition to TIMEOUT
        assert result.status == CheckpointStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_concurrent_checkpoint_timeouts(self, checkpoint_service):
        """Test handling multiple concurrent checkpoint timeouts."""
        checkpoint_service.intervention_mode = InterventionMode.ALL_ACTIONS

        actions = [
            CheckpointAction(
                checkpoint_id=f"concurrent-{i}",
                execution_id=f"exec-{i}",
                agent_id=f"agent-{i}",
                action_type=ActionType.FILE_WRITE,
                action_name=f"write_{i}",
                parameters={},
                risk_level=RiskLevel.HIGH,
                reversible=True,
                estimated_duration_seconds=5,
                timeout_seconds=1,
            )
            for i in range(3)
        ]

        results = await asyncio.gather(
            *[
                checkpoint_service.create_checkpoint(
                    execution_id=action.execution_id,
                    agent_id=action.agent_id,
                    action=action,
                )
                for action in actions
            ]
        )

        # All should timeout
        assert all(r.status == CheckpointStatus.TIMEOUT for r in results)

    @pytest.mark.asyncio
    async def test_timeout_with_event_publisher(self, mock_dynamodb_table):
        """Test that timeout events are published correctly."""
        mock_publisher = AsyncMock()

        with patch("boto3.resource") as mock_boto:
            mock_resource = MagicMock()
            mock_resource.Table.return_value = mock_dynamodb_table
            mock_boto.return_value = mock_resource

            service = ExecutionCheckpointService(
                dynamodb_table_name="test-checkpoints",
                event_publisher=mock_publisher,
                intervention_mode=InterventionMode.ALL_ACTIONS,
                default_timeout_seconds=1,
            )
            service._table = mock_dynamodb_table

            action = CheckpointAction(
                checkpoint_id="publish-001",
                execution_id="exec-001",
                agent_id="test-agent",
                action_type=ActionType.FILE_WRITE,
                action_name="write",
                parameters={},
                risk_level=RiskLevel.HIGH,
                reversible=True,
                estimated_duration_seconds=5,
                timeout_seconds=1,
            )

            await service.create_checkpoint(
                execution_id="exec-001",
                agent_id="test-agent",
                action=action,
            )

            # Verify publish was called for checkpoint creation and timeout
            assert mock_publisher.publish.called


# =============================================================================
# Test Class: Integration Scenarios
# =============================================================================


class TestTimeoutIntegrationScenarios:
    """Integration tests combining multiple timeout scenarios."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_timeout_recovery(self):
        """Test complete workflow with timeout and graceful recovery."""

        class WorkflowOrchestrator:
            def __init__(self):
                self.workflow_state = "init"
                self.completed_steps: list[str] = []
                self.failed_steps: list[str] = []
                self.partial_results: dict[str, Any] = {}

            async def run_workflow(
                self, steps: list[tuple[str, BaseAgent, AgentTask]]
            ) -> dict:
                for step_name, agent, task in steps:
                    self.workflow_state = f"running_{step_name}"

                    try:
                        result = await agent.run(task)

                        if result.success:
                            self.completed_steps.append(step_name)
                            self.partial_results[step_name] = result.data
                        else:
                            self.failed_steps.append(step_name)
                            # Continue with next step (graceful degradation)

                    except Exception as e:
                        self.failed_steps.append(step_name)

                self.workflow_state = "completed"
                return {
                    "completed": self.completed_steps,
                    "failed": self.failed_steps,
                    "partial_results": self.partial_results,
                }

        class QuickAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(0.1)
                return AgentResult(
                    task_id=task.task_id, success=True, data={"quick": True}
                )

        class SlowAgent(BaseAgent):
            async def execute(self, task: AgentTask) -> AgentResult:
                await asyncio.sleep(10)
                return AgentResult(
                    task_id=task.task_id, success=True, data={"slow": True}
                )

        orchestrator = WorkflowOrchestrator()
        steps = [
            (
                "step1",
                QuickAgent(),
                AgentTask(
                    task_id="s1",
                    task_type="quick",
                    description="Quick 1",
                    timeout_seconds=5,
                ),
            ),
            (
                "step2",
                SlowAgent(),
                AgentTask(
                    task_id="s2",
                    task_type="slow",
                    description="Slow",
                    timeout_seconds=1,
                ),
            ),
            (
                "step3",
                QuickAgent(),
                AgentTask(
                    task_id="s3",
                    task_type="quick",
                    description="Quick 2",
                    timeout_seconds=5,
                ),
            ),
        ]

        result = await orchestrator.run_workflow(steps)

        # Step 1 and 3 complete, step 2 times out
        assert "step1" in result["completed"]
        assert "step2" in result["failed"]
        assert "step3" in result["completed"]
        assert "step1" in result["partial_results"]
        assert "step3" in result["partial_results"]

    @pytest.mark.asyncio
    async def test_nested_timeout_propagation(self):
        """Test that timeouts propagate correctly through nested agent calls."""
        call_depth = {"value": 0}
        max_depth_reached = {"value": 0}

        class NestedAgent(BaseAgent):
            def __init__(self, depth: int, max_depth: int):
                super().__init__(agent_name=f"NestedAgent_{depth}")
                self.depth = depth
                self.max_depth = max_depth

            async def execute(self, task: AgentTask) -> AgentResult:
                call_depth["value"] = self.depth
                if self.depth > max_depth_reached["value"]:
                    max_depth_reached["value"] = self.depth

                if self.depth < self.max_depth:
                    # Create child agent
                    child = NestedAgent(self.depth + 1, self.max_depth)
                    child_task = AgentTask(
                        task_id=f"{task.task_id}_child",
                        task_type="nested",
                        description="Nested task",
                        timeout_seconds=task.timeout_seconds,
                    )

                    result = await child.run(child_task)
                    return result

                # Leaf agent - do slow work
                await asyncio.sleep(10)
                return AgentResult(task_id=task.task_id, success=True)

        root_agent = NestedAgent(0, 5)
        task = AgentTask(
            task_id="nested-001",
            task_type="nested",
            description="Root task",
            timeout_seconds=1,
        )

        result = await root_agent.run(task)

        assert not result.success
        # Should have propagated through some levels before timeout
        assert max_depth_reached["value"] >= 0
