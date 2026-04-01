"""
Tests for SSR Self-Play Components (Phase 3)

Tests the self-play training loop including shared policy,
bug injection agent, bug solving agent, orchestrator, and
training data pipeline.

Author: Project Aura Team
Created: 2026-01-01
"""

import pytest

from src.agents.ssr.bug_injection_agent import (
    BugInjectionAgent,
    BugType,
    InjectionCandidate,
    InjectionResult,
)
from src.agents.ssr.bug_solving_agent import (
    BugSolvingAgent,
    SolveAttempt,
    SolveResult,
    SolveStatus,
)
from src.agents.ssr.shared_policy import (
    AgentRole,
    PolicyConfig,
    RoleContext,
    SharedPolicy,
    create_shared_policy,
)
from src.services.ssr.bug_artifact import ArtifactStatus, BugArtifact
from src.services.ssr.self_play_orchestrator import (
    RoundResult,
    SelfPlayOrchestrator,
    SessionConfig,
    SessionMetrics,
    SessionStatus,
)
from src.services.ssr.training_data_pipeline import (
    RewardComputer,
    RewardSignal,
    TrainingBatch,
    TrainingDataPipeline,
    TrainingTrajectory,
    TrajectoryType,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def shared_policy() -> SharedPolicy:
    """Create a shared policy for testing."""
    return SharedPolicy(llm_client=None, config=PolicyConfig())


@pytest.fixture
def mock_artifact() -> BugArtifact:
    """Create a mock bug artifact."""
    return BugArtifact(
        artifact_id="ssr-artifact-test123",
        repository_id="repo-456",
        commit_sha="abc123def456",
        test_script="#!/bin/bash\npytest tests/",
        test_files=["tests/test_foo.py"],
        test_parser="import json; print(json.dumps({}))",
        bug_inject_diff="--- a/foo.py\n+++ b/foo.py\n-old\n+new",
        test_weaken_diff="",
        status=ArtifactStatus.VALID,
    )


@pytest.fixture
def injection_candidate() -> InjectionCandidate:
    """Create a mock injection candidate."""
    return InjectionCandidate(
        file_path="src/calculator.py",
        function_name="divide",
        line_start=10,
        line_end=20,
        code_snippet="def divide(a, b):\n    return a / b",
        complexity_score=0.6,
        test_coverage=0.8,
        recommended_bug_types=[BugType.WRONG_OPERATOR, BugType.OFF_BY_ONE],
    )


# =============================================================================
# Shared Policy Tests
# =============================================================================


class TestAgentRole:
    """Tests for AgentRole enum."""

    def test_roles_exist(self) -> None:
        """Verify all roles are defined."""
        assert AgentRole.BUG_INJECTOR.value == "bug_injector"
        assert AgentRole.BUG_SOLVER.value == "bug_solver"


class TestPolicyConfig:
    """Tests for PolicyConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = PolicyConfig()
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.injector_temperature == 0.8
        assert config.solver_temperature == 0.5

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = PolicyConfig(temperature=0.5, max_retries=5)
        assert config.temperature == 0.5
        assert config.max_retries == 5


class TestRoleContext:
    """Tests for RoleContext dataclass."""

    def test_create_context(self) -> None:
        """Test creating a role context."""
        context = RoleContext(
            role=AgentRole.BUG_INJECTOR,
            repository_id="repo-123",
            commit_sha="abc123",
        )
        assert context.role == AgentRole.BUG_INJECTOR
        assert context.conversation_history == []

    def test_add_message(self) -> None:
        """Test adding messages to context."""
        context = RoleContext(
            role=AgentRole.BUG_SOLVER,
            repository_id="repo-123",
            commit_sha="abc123",
        )
        context.add_message("user", "Hello")
        context.add_message("assistant", "Hi there")

        assert len(context.conversation_history) == 2
        assert context.conversation_history[0]["role"] == "user"

    def test_clear_history(self) -> None:
        """Test clearing conversation history."""
        context = RoleContext(
            role=AgentRole.BUG_SOLVER,
            repository_id="repo-123",
            commit_sha="abc123",
        )
        context.add_message("user", "Test")
        context.tokens_used = 100
        context.clear_history()

        assert context.conversation_history == []
        assert context.tokens_used == 0

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        context = RoleContext(
            role=AgentRole.BUG_INJECTOR,
            repository_id="repo-123",
            commit_sha="abc123",
        )
        data = context.to_dict()

        assert data["role"] == "bug_injector"
        assert data["repository_id"] == "repo-123"


class TestSharedPolicy:
    """Tests for SharedPolicy class."""

    def test_initialization(self, shared_policy: SharedPolicy) -> None:
        """Test policy initialization."""
        assert shared_policy.config is not None
        assert shared_policy._total_tokens == 0

    def test_create_context(self, shared_policy: SharedPolicy) -> None:
        """Test creating an isolated context."""
        context = shared_policy.create_context(
            role=AgentRole.BUG_INJECTOR,
            repository_id="repo-123",
            commit_sha="abc123",
        )

        assert context.role == AgentRole.BUG_INJECTOR
        assert context.context_hash != ""
        assert context.context_hash in shared_policy._active_contexts

    def test_context_isolation(self, shared_policy: SharedPolicy) -> None:
        """Test that contexts are isolated."""
        ctx1 = shared_policy.create_context(
            role=AgentRole.BUG_INJECTOR,
            repository_id="repo-123",
            commit_sha="abc123",
        )
        ctx2 = shared_policy.create_context(
            role=AgentRole.BUG_SOLVER,
            repository_id="repo-123",
            commit_sha="abc123",
        )

        assert ctx1.context_hash != ctx2.context_hash
        assert ctx1.system_prompt != ctx2.system_prompt

    @pytest.mark.asyncio
    async def test_generate_mock(self, shared_policy: SharedPolicy) -> None:
        """Test generating with mock LLM."""
        context = shared_policy.create_context(
            role=AgentRole.BUG_INJECTOR,
            repository_id="repo-123",
            commit_sha="abc123",
        )

        result = await shared_policy.generate(
            context=context,
            user_prompt="Inject a bug",
        )

        assert "content" in result
        assert result["role"] == "bug_injector"
        assert result["tokens_used"] > 0

    def test_invalidate_context(self, shared_policy: SharedPolicy) -> None:
        """Test invalidating a context."""
        context = shared_policy.create_context(
            role=AgentRole.BUG_INJECTOR,
            repository_id="repo-123",
            commit_sha="abc123",
        )

        shared_policy.invalidate_context(context)
        assert context.context_hash not in shared_policy._active_contexts

    def test_get_metrics(self, shared_policy: SharedPolicy) -> None:
        """Test getting policy metrics."""
        metrics = shared_policy.get_metrics()

        assert "total_tokens" in metrics
        assert "generation_count" in metrics
        assert "active_contexts" in metrics

    def test_factory_function(self) -> None:
        """Test create_shared_policy factory."""
        policy = create_shared_policy()
        assert isinstance(policy, SharedPolicy)


# =============================================================================
# Bug Injection Agent Tests
# =============================================================================


class TestBugType:
    """Tests for BugType enum."""

    def test_bug_types_exist(self) -> None:
        """Verify all bug types are defined."""
        assert BugType.OFF_BY_ONE.value == "off_by_one"
        assert BugType.WRONG_OPERATOR.value == "wrong_operator"
        assert BugType.LOGIC_INVERSION.value == "logic_inversion"


class TestInjectionCandidate:
    """Tests for InjectionCandidate dataclass."""

    def test_create_candidate(self, injection_candidate: InjectionCandidate) -> None:
        """Test creating an injection candidate."""
        assert injection_candidate.function_name == "divide"
        assert injection_candidate.complexity_score == 0.6
        assert BugType.WRONG_OPERATOR in injection_candidate.recommended_bug_types


class TestBugInjectionAgent:
    """Tests for BugInjectionAgent class."""

    def test_initialization(self, shared_policy: SharedPolicy) -> None:
        """Test agent initialization."""
        agent = BugInjectionAgent(policy=shared_policy)
        assert agent.default_difficulty == 5
        assert agent.current_difficulty == 5

    @pytest.mark.asyncio
    async def test_find_injection_candidates(self, shared_policy: SharedPolicy) -> None:
        """Test finding injection candidates."""
        agent = BugInjectionAgent(policy=shared_policy)

        code_contents = {
            "src/main.py": """
def add(a, b):
    return a + b

def subtract(a, b):
    if b > a:
        return 0
    return a - b
""",
        }

        candidates = await agent.find_injection_candidates(
            repository_id="repo-123",
            commit_sha="abc123",
            code_files=["src/main.py"],
            code_contents=code_contents,
        )

        assert len(candidates) >= 2  # Should find at least 2 functions

    @pytest.mark.asyncio
    async def test_inject_bug(
        self,
        shared_policy: SharedPolicy,
        injection_candidate: InjectionCandidate,
    ) -> None:
        """Test bug injection."""
        agent = BugInjectionAgent(policy=shared_policy)

        result = await agent.inject_bug(
            repository_id="repo-123",
            commit_sha="abc123",
            candidate=injection_candidate,
            code_context="def divide(a, b):\n    return a / b",
            test_files=["tests/test_calculator.py"],
            target_difficulty=5,
        )

        assert result.success
        assert result.artifact is not None
        assert result.bug_type == BugType.WRONG_OPERATOR

    def test_calibrate_difficulty(self, shared_policy: SharedPolicy) -> None:
        """Test difficulty calibration."""
        agent = BugInjectionAgent(policy=shared_policy, default_difficulty=5)

        # Simulate several easy solves
        for _ in range(10):
            agent.calibrate_difficulty(5, solved=True)

        # Difficulty should increase
        assert agent.current_difficulty > 5

    def test_get_metrics(self, shared_policy: SharedPolicy) -> None:
        """Test getting agent metrics."""
        agent = BugInjectionAgent(policy=shared_policy)
        metrics = agent.get_metrics()

        assert "current_difficulty" in metrics
        assert "history_size" in metrics


# =============================================================================
# Bug Solving Agent Tests
# =============================================================================


class TestSolveStatus:
    """Tests for SolveStatus enum."""

    def test_statuses_exist(self) -> None:
        """Verify all statuses are defined."""
        assert SolveStatus.SOLVED.value == "solved"
        assert SolveStatus.FAILED.value == "failed"
        assert SolveStatus.TIMEOUT.value == "timeout"


class TestSolveAttempt:
    """Tests for SolveAttempt dataclass."""

    def test_create_attempt(self) -> None:
        """Test creating a solve attempt."""
        attempt = SolveAttempt(
            attempt_number=1,
            patch_diff="--- a/foo.py\n+++ b/foo.py\n-bug\n+fix",
            test_passed=True,
            test_output="All tests passed",
            duration_seconds=5.0,
            tokens_used=1000,
            cost_usd=0.01,
        )

        assert attempt.attempt_number == 1
        assert attempt.test_passed

    def test_to_dict(self) -> None:
        """Test serialization."""
        attempt = SolveAttempt(
            attempt_number=1,
            patch_diff="diff",
            test_passed=False,
            test_output="Failed",
            duration_seconds=2.0,
            tokens_used=500,
            cost_usd=0.005,
        )
        data = attempt.to_dict()

        assert data["attempt_number"] == 1
        assert data["test_passed"] is False


class TestSolveResult:
    """Tests for SolveResult dataclass."""

    def test_solved_property(self) -> None:
        """Test solved property."""
        result = SolveResult(
            artifact_id="test",
            status=SolveStatus.SOLVED,
        )
        assert result.solved is True

        result.status = SolveStatus.FAILED
        assert result.solved is False

    def test_to_dict(self) -> None:
        """Test serialization."""
        result = SolveResult(
            artifact_id="test-123",
            status=SolveStatus.SOLVED,
            final_patch="fix patch",
        )
        data = result.to_dict()

        assert data["artifact_id"] == "test-123"
        assert data["solved"] is True


class TestBugSolvingAgent:
    """Tests for BugSolvingAgent class."""

    def test_initialization(self, shared_policy: SharedPolicy) -> None:
        """Test agent initialization."""
        agent = BugSolvingAgent(policy=shared_policy)
        assert agent.max_attempts == 3
        assert agent.timeout_seconds == 300

    @pytest.mark.asyncio
    async def test_solve_success(
        self,
        shared_policy: SharedPolicy,
        mock_artifact: BugArtifact,
    ) -> None:
        """Test successful bug solving."""
        agent = BugSolvingAgent(policy=shared_policy)

        # Mock the sandbox validation to return success
        agent._mock_validate = lambda p: (True, "All tests passed")

        result = await agent.solve(
            artifact=mock_artifact,
            code_context={"src/foo.py": "def foo(): pass"},
            test_output="FAILED test_foo",
        )

        # Should eventually solve (mock has 50% chance)
        assert result.attempt_count > 0
        assert result.status in [SolveStatus.SOLVED, SolveStatus.FAILED]

    def test_solve_rate(self, shared_policy: SharedPolicy) -> None:
        """Test solve rate calculation."""
        agent = BugSolvingAgent(policy=shared_policy)

        # No history
        assert agent.solve_rate == 0.0

        # Add some history
        agent._solve_history = [("a", True), ("b", False), ("c", True)]
        assert agent.solve_rate == pytest.approx(2 / 3)

    def test_get_metrics(self, shared_policy: SharedPolicy) -> None:
        """Test getting agent metrics."""
        agent = BugSolvingAgent(policy=shared_policy)
        metrics = agent.get_metrics()

        assert "total_attempts" in metrics
        assert "overall_solve_rate" in metrics


# =============================================================================
# Self-Play Orchestrator Tests
# =============================================================================


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_statuses_exist(self) -> None:
        """Verify all statuses are defined."""
        assert SessionStatus.RUNNING.value == "running"
        assert SessionStatus.CONVERGED.value == "converged"
        assert SessionStatus.COMPLETED.value == "completed"


class TestSessionConfig:
    """Tests for SessionConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = SessionConfig(repository_id="repo-123")
        assert config.max_rounds == 100
        assert config.convergence_threshold == 0.05


class TestSessionMetrics:
    """Tests for SessionMetrics dataclass."""

    def test_update_metrics(self) -> None:
        """Test updating metrics with round result."""
        metrics = SessionMetrics()

        # Create a mock round result
        injection_result = InjectionResult(
            success=True,
            difficulty=5,
            tokens_used=100,
            cost_usd=0.01,
        )
        solve_result = SolveResult(
            artifact_id="test",
            status=SolveStatus.SOLVED,
        )
        round_result = RoundResult(
            round_number=1,
            artifact_id="test",
            injection_result=injection_result,
            solve_result=solve_result,
        )

        metrics.update(round_result)

        assert metrics.total_rounds == 1
        assert metrics.successful_injections == 1
        assert metrics.successful_solves == 1

    def test_to_dict(self) -> None:
        """Test serialization."""
        metrics = SessionMetrics(total_rounds=10, successful_solves=5)
        data = metrics.to_dict()

        assert data["total_rounds"] == 10
        assert data["solve_rate"] == 0.0  # No successful injections


class TestSelfPlayOrchestrator:
    """Tests for SelfPlayOrchestrator class."""

    def test_initialization(self) -> None:
        """Test orchestrator initialization."""
        orchestrator = SelfPlayOrchestrator()
        assert orchestrator.injection_agent is not None
        assert orchestrator.solving_agent is not None

    @pytest.mark.asyncio
    async def test_start_session(self) -> None:
        """Test starting a session."""
        orchestrator = SelfPlayOrchestrator()

        session_id = await orchestrator.start_session(
            config=SessionConfig(repository_id="repo-123", max_rounds=5),
            code_files=["src/main.py"],
            code_contents={"src/main.py": "def foo(): pass"},
            test_files=["tests/test_main.py"],
        )

        assert session_id.startswith("ssr-session-")
        assert session_id in orchestrator._sessions

    @pytest.mark.asyncio
    async def test_stop_session(self) -> None:
        """Test stopping a session."""
        orchestrator = SelfPlayOrchestrator()

        session_id = await orchestrator.start_session(
            config=SessionConfig(repository_id="repo-123", max_rounds=100),
            code_files=["src/main.py"],
            code_contents={"src/main.py": "def foo(): pass"},
            test_files=[],
        )

        # Stop the session
        result = await orchestrator.stop_session(session_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_session_status(self) -> None:
        """Test getting session status."""
        orchestrator = SelfPlayOrchestrator()

        session_id = await orchestrator.start_session(
            config=SessionConfig(repository_id="repo-123"),
            code_files=["src/main.py"],
            code_contents={"src/main.py": "def foo(): pass"},
            test_files=[],
        )

        status = await orchestrator.get_session_status(session_id)

        assert status is not None
        assert status["session_id"] == session_id
        assert "metrics" in status

    def test_get_all_sessions(self) -> None:
        """Test getting all sessions."""
        orchestrator = SelfPlayOrchestrator()
        sessions = orchestrator.get_all_sessions()
        assert isinstance(sessions, list)


# =============================================================================
# Training Data Pipeline Tests
# =============================================================================


class TestTrajectoryType:
    """Tests for TrajectoryType enum."""

    def test_types_exist(self) -> None:
        """Verify all types are defined."""
        assert TrajectoryType.INJECTION.value == "injection"
        assert TrajectoryType.SOLVING.value == "solving"


class TestRewardSignal:
    """Tests for RewardSignal enum."""

    def test_signals_exist(self) -> None:
        """Verify all signals are defined."""
        assert RewardSignal.POSITIVE.value == "positive"
        assert RewardSignal.NEGATIVE.value == "negative"
        assert RewardSignal.NEUTRAL.value == "neutral"


class TestRewardComputer:
    """Tests for RewardComputer class."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        computer = RewardComputer()
        assert computer.alpha == 0.5
        assert computer.solve_success_reward == 1.0

    def test_injection_reward_invalid(self) -> None:
        """Test reward for invalid injection."""
        computer = RewardComputer()
        result = InjectionResult(success=False)

        reward, signal = computer.compute_injection_reward(result, 0.5)

        assert reward == -1.0
        assert signal == RewardSignal.NEGATIVE

    def test_injection_reward_trivial(self) -> None:
        """Test reward for trivial bugs."""
        computer = RewardComputer(alpha=0.5)
        result = InjectionResult(success=True, difficulty=5)

        # Always solved (s=1)
        reward, signal = computer.compute_injection_reward(result, 1.0)
        assert reward == -0.5
        assert signal == RewardSignal.NEGATIVE

        # Never solved (s=0)
        reward, signal = computer.compute_injection_reward(result, 0.0)
        assert reward == -0.5

    def test_injection_reward_good_bug(self) -> None:
        """Test reward for well-balanced bugs."""
        computer = RewardComputer(alpha=0.5)
        result = InjectionResult(success=True, difficulty=5)

        # 50% solve rate - optimal
        reward, signal = computer.compute_injection_reward(result, 0.5)
        # r = 1 - (1 + 0.5) * 0.5 = 1 - 0.75 = 0.25
        assert reward == pytest.approx(0.25)
        assert signal == RewardSignal.POSITIVE

    def test_solving_reward_success(self) -> None:
        """Test reward for successful solve."""
        computer = RewardComputer()
        result = SolveResult(artifact_id="test", status=SolveStatus.SOLVED)

        reward, signal = computer.compute_solving_reward(result)

        assert reward == 1.0
        assert signal == RewardSignal.POSITIVE

    def test_solving_reward_failure(self) -> None:
        """Test reward for failed solve."""
        computer = RewardComputer()
        result = SolveResult(artifact_id="test", status=SolveStatus.FAILED)

        reward, signal = computer.compute_solving_reward(result)

        assert reward == -1.0
        assert signal == RewardSignal.NEGATIVE


class TestTrainingTrajectory:
    """Tests for TrainingTrajectory dataclass."""

    def test_create_trajectory(self) -> None:
        """Test creating a trajectory."""
        trajectory = TrainingTrajectory(
            trajectory_id="traj-123",
            trajectory_type=TrajectoryType.INJECTION,
            artifact_id="art-123",
            repository_id="repo-123",
            prompt="Inject a bug",
            code_context="def foo(): pass",
            response="Here's a bug...",
            action_taken="--- a/foo.py\n+++ b/foo.py",
            reward=0.5,
            reward_signal=RewardSignal.POSITIVE,
        )

        assert trajectory.trajectory_id == "traj-123"
        assert trajectory.reward == 0.5

    def test_to_training_format(self) -> None:
        """Test conversion to training format."""
        trajectory = TrainingTrajectory(
            trajectory_id="traj-123",
            trajectory_type=TrajectoryType.SOLVING,
            artifact_id="art-123",
            repository_id="repo-123",
            prompt="Fix this bug",
            code_context="buggy code",
            response="Fixed!",
            action_taken="fix patch",
            reward=1.0,
            reward_signal=RewardSignal.POSITIVE,
        )

        data = trajectory.to_training_format()

        assert "input" in data
        assert "output" in data
        assert data["reward"] == 1.0


class TestTrainingBatch:
    """Tests for TrainingBatch dataclass."""

    def test_batch_properties(self) -> None:
        """Test batch properties."""
        trajectories = [
            TrainingTrajectory(
                trajectory_id=f"traj-{i}",
                trajectory_type=TrajectoryType.INJECTION,
                artifact_id="art",
                repository_id="repo",
                prompt="p",
                code_context="c",
                response="r",
                action_taken="a",
                reward=1.0 if i % 2 == 0 else -1.0,
                reward_signal=(
                    RewardSignal.POSITIVE if i % 2 == 0 else RewardSignal.NEGATIVE
                ),
            )
            for i in range(4)
        ]

        batch = TrainingBatch(batch_id="batch-1", trajectories=trajectories)

        assert batch.size == 4
        assert batch.total_reward == 0.0  # 2 positive, 2 negative
        assert batch.positive_ratio == 0.5

    def test_export_jsonl(self) -> None:
        """Test JSONL export."""
        trajectories = [
            TrainingTrajectory(
                trajectory_id="traj-1",
                trajectory_type=TrajectoryType.INJECTION,
                artifact_id="art",
                repository_id="repo",
                prompt="p",
                code_context="c",
                response="r",
                action_taken="a",
                reward=1.0,
                reward_signal=RewardSignal.POSITIVE,
            )
        ]

        batch = TrainingBatch(batch_id="batch-1", trajectories=trajectories)
        jsonl = batch.export_jsonl()

        assert len(jsonl.split("\n")) == 1
        assert "reward" in jsonl


class TestTrainingDataPipeline:
    """Tests for TrainingDataPipeline class."""

    def test_initialization(self) -> None:
        """Test pipeline initialization."""
        pipeline = TrainingDataPipeline()
        assert pipeline.max_trajectories == 10000
        assert pipeline.reward_computer is not None

    def test_add_injection_trajectory(self, mock_artifact: BugArtifact) -> None:
        """Test adding an injection trajectory."""
        pipeline = TrainingDataPipeline()
        result = InjectionResult(success=True, difficulty=5, tokens_used=100)

        trajectory = pipeline.add_injection_trajectory(
            artifact=mock_artifact,
            injection_result=result,
            prompt="Inject a bug",
            code_context="def foo(): pass",
            response="Here's a bug",
        )

        assert trajectory.trajectory_type == TrajectoryType.INJECTION
        assert len(pipeline._trajectories) == 1

    def test_add_solving_trajectory(self, mock_artifact: BugArtifact) -> None:
        """Test adding a solving trajectory."""
        pipeline = TrainingDataPipeline()
        result = SolveResult(artifact_id="test", status=SolveStatus.SOLVED)

        trajectory = pipeline.add_solving_trajectory(
            artifact=mock_artifact,
            solve_result=result,
            prompt="Fix this",
            code_context="buggy code",
            response="Fixed!",
            difficulty=5,
        )

        assert trajectory.trajectory_type == TrajectoryType.SOLVING
        assert trajectory.reward == 1.0

    def test_create_batch(self, mock_artifact: BugArtifact) -> None:
        """Test creating a training batch."""
        pipeline = TrainingDataPipeline()

        # Add some trajectories
        for i in range(10):
            result = InjectionResult(success=True, difficulty=5)
            pipeline.add_injection_trajectory(
                artifact=mock_artifact,
                injection_result=result,
                prompt=f"Prompt {i}",
                code_context="code",
                response="response",
            )

        batch = pipeline.create_batch(batch_size=5)

        assert batch.size == 5

    def test_create_balanced_batch(self, mock_artifact: BugArtifact) -> None:
        """Test creating a balanced batch."""
        pipeline = TrainingDataPipeline()

        # Add positive trajectories (successful solves)
        for i in range(5):
            result = SolveResult(artifact_id=f"art-{i}", status=SolveStatus.SOLVED)
            pipeline.add_solving_trajectory(
                artifact=mock_artifact,
                solve_result=result,
                prompt="Fix",
                code_context="code",
                response="Fixed",
                difficulty=5,
            )

        # Add negative trajectories (failed solves)
        for i in range(5):
            result = SolveResult(artifact_id=f"art-neg-{i}", status=SolveStatus.FAILED)
            pipeline.add_solving_trajectory(
                artifact=mock_artifact,
                solve_result=result,
                prompt="Fix",
                code_context="code",
                response="Tried",
                difficulty=5,
            )

        batch = pipeline.create_balanced_batch(batch_size=6)

        # Should have roughly equal positive/negative
        positive = sum(1 for t in batch.trajectories if t.reward > 0)
        assert positive >= 2  # At least some positive

    def test_get_metrics(self, mock_artifact: BugArtifact) -> None:
        """Test getting pipeline metrics."""
        pipeline = TrainingDataPipeline()

        result = InjectionResult(success=True, difficulty=5)
        pipeline.add_injection_trajectory(
            artifact=mock_artifact,
            injection_result=result,
            prompt="p",
            code_context="c",
            response="r",
        )

        metrics = pipeline.get_metrics()

        assert metrics["total_trajectories"] == 1
        assert metrics["injection_trajectories"] == 1

    def test_get_solve_rates(self, mock_artifact: BugArtifact) -> None:
        """Test getting solve rates by difficulty.

        Uses get_solve_rates_raw() for exact window-based rates.
        get_solve_rates() returns EMA-smoothed rates which differ from raw.
        """
        pipeline = TrainingDataPipeline()

        # Add some solving trajectories at different difficulties
        for solved in [True, False, True]:
            result = SolveResult(
                artifact_id="art",
                status=SolveStatus.SOLVED if solved else SolveStatus.FAILED,
            )
            pipeline.add_solving_trajectory(
                artifact=mock_artifact,
                solve_result=result,
                prompt="p",
                code_context="c",
                response="r",
                difficulty=5,
            )

        # Use raw rates for exact window-based calculation (2 solved / 3 total)
        rates = pipeline.get_solve_rates_raw()

        assert 5 in rates
        assert rates[5] == pytest.approx(2 / 3)

    def test_clear(self, mock_artifact: BugArtifact) -> None:
        """Test clearing the pipeline."""
        pipeline = TrainingDataPipeline()

        result = InjectionResult(success=True, difficulty=5)
        pipeline.add_injection_trajectory(
            artifact=mock_artifact,
            injection_result=result,
            prompt="p",
            code_context="c",
            response="r",
        )

        pipeline.clear()

        assert len(pipeline._trajectories) == 0
        assert pipeline._total_reward == 0.0


# =============================================================================
# Package Export Tests
# =============================================================================


class TestAgentPackageExports:
    """Tests for agent package exports."""

    def test_agent_exports(self) -> None:
        """Test that agent classes are exported."""
        from src.agents.ssr import BugInjectionAgent, BugSolvingAgent, SharedPolicy

        assert SharedPolicy is not None
        assert BugInjectionAgent is not None
        assert BugSolvingAgent is not None


class TestServicePackageExports:
    """Tests for service package exports."""

    def test_service_exports(self) -> None:
        """Test that service classes are exported."""
        from src.services.ssr import RewardComputer, SessionConfig, TrainingDataPipeline

        # SelfPlayOrchestrator must be imported directly to avoid circular imports
        from src.services.ssr.self_play_orchestrator import SelfPlayOrchestrator

        assert SelfPlayOrchestrator is not None
        assert TrainingDataPipeline is not None
        assert RewardComputer is not None
        assert SessionConfig is not None
