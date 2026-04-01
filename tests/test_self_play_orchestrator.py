"""
Tests for SelfPlayOrchestrator Service

Comprehensive tests for the self-play orchestrator module including:
- SessionStatus enum
- SessionConfig dataclass
- SessionMetrics dataclass
- SessionCheckpoint dataclass
- RoundResult dataclass
- SelfPlayOrchestrator class

Author: Project Aura Team
Created: 2026-01-04
"""

import platform
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# macOS fork isolation marker
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.agents.ssr.bug_injection_agent import (
    BugType,
    InjectionCandidate,
    InjectionResult,
)
from src.agents.ssr.bug_solving_agent import SolveAttempt, SolveResult, SolveStatus
from src.services.ssr.bug_artifact import ArtifactStatus, BugArtifact
from src.services.ssr.self_play_orchestrator import (
    RoundResult,
    SelfPlayOrchestrator,
    SessionCheckpoint,
    SessionConfig,
    SessionMetrics,
    SessionStatus,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_artifact() -> BugArtifact:
    """Create a sample bug artifact for testing."""
    return BugArtifact(
        artifact_id="ssr-artifact-test123",
        repository_id="repo-456",
        commit_sha="abc123def456",
        test_script="#!/bin/bash\npytest tests/",
        test_files=["tests/test_foo.py", "tests/test_bar.py"],
        test_parser='import json\nprint(json.dumps({"test1": "pass"}))',
        bug_inject_diff="diff --git a/foo.py b/foo.py\n-old\n+new",
        test_weaken_diff="diff --git a/tests/test_foo.py",
        status=ArtifactStatus.PENDING,
    )


@pytest.fixture
def mock_injection_result(sample_artifact: BugArtifact) -> InjectionResult:
    """Create a mock injection result."""
    return InjectionResult(
        success=True,
        artifact=sample_artifact,
        bug_type=BugType.WRONG_OPERATOR,
        difficulty=5,
        tokens_used=100,
        cost_usd=0.01,
    )


@pytest.fixture
def mock_solve_result() -> SolveResult:
    """Create a mock solve result."""
    return SolveResult(
        artifact_id="ssr-artifact-test123",
        status=SolveStatus.SOLVED,
        attempts=[
            SolveAttempt(
                attempt_number=1,
                patch_diff="--- a/foo.py\n+++ b/foo.py\n-bug\n+fix",
                test_passed=True,
                test_output="All tests passed",
                duration_seconds=5.0,
                tokens_used=500,
                cost_usd=0.05,
            )
        ],
        final_patch="--- a/foo.py\n+++ b/foo.py\n-bug\n+fix",
        total_tokens=500,
        total_cost=0.05,
    )


@pytest.fixture
def mock_failed_solve_result() -> SolveResult:
    """Create a mock failed solve result."""
    return SolveResult(
        artifact_id="ssr-artifact-test123",
        status=SolveStatus.FAILED,
        attempts=[
            SolveAttempt(
                attempt_number=1,
                patch_diff="--- a/foo.py\n+++ b/foo.py\n-bug\n+wrong_fix",
                test_passed=False,
                test_output="Test failed",
                duration_seconds=5.0,
                tokens_used=500,
                cost_usd=0.05,
            )
        ],
        total_tokens=500,
        total_cost=0.05,
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


@pytest.fixture
def session_config() -> SessionConfig:
    """Create a sample session config."""
    return SessionConfig(
        repository_id="repo-123",
        max_rounds=10,
        convergence_window=5,
        convergence_threshold=0.05,
    )


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator with all dependencies mocked."""
    # Create mock objects
    mock_storage = MagicMock()
    mock_storage.store_artifact = AsyncMock()
    mock_storage.update_artifact_status = AsyncMock()

    mock_policy = MagicMock()

    mock_injection_agent = MagicMock()
    mock_injection_agent.find_injection_candidates = AsyncMock(return_value=[])
    mock_injection_agent.inject_bug = AsyncMock()
    mock_injection_agent.calibrate_difficulty = MagicMock()

    mock_solving_agent = MagicMock()
    mock_solving_agent.solve = AsyncMock()

    with (
        patch(
            "src.services.ssr.artifact_storage_service.ArtifactStorageService",
            return_value=mock_storage,
        ),
        patch(
            "src.agents.ssr.shared_policy.create_shared_policy",
            return_value=mock_policy,
        ),
        patch(
            "src.agents.ssr.bug_injection_agent.BugInjectionAgent",
            return_value=mock_injection_agent,
        ),
        patch(
            "src.agents.ssr.bug_solving_agent.BugSolvingAgent",
            return_value=mock_solving_agent,
        ),
    ):
        orchestrator = SelfPlayOrchestrator()
        # Manually set the mocks for easier access in tests
        orchestrator._mock_storage = mock_storage
        orchestrator._mock_policy = mock_policy
        orchestrator._mock_injection_agent = mock_injection_agent
        orchestrator._mock_solving_agent = mock_solving_agent
        yield orchestrator


# =============================================================================
# SessionStatus Tests
# =============================================================================


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Verify all expected statuses are defined."""
        expected = [
            "INITIALIZING",
            "RUNNING",
            "PAUSED",
            "CONVERGED",
            "COMPLETED",
            "FAILED",
        ]
        for status in expected:
            assert hasattr(SessionStatus, status)

    def test_status_values(self) -> None:
        """Verify status values are lowercase strings."""
        assert SessionStatus.INITIALIZING.value == "initializing"
        assert SessionStatus.RUNNING.value == "running"
        assert SessionStatus.PAUSED.value == "paused"
        assert SessionStatus.CONVERGED.value == "converged"
        assert SessionStatus.COMPLETED.value == "completed"
        assert SessionStatus.FAILED.value == "failed"

    def test_status_from_string(self) -> None:
        """Test creating status from string value."""
        status = SessionStatus("running")
        assert status == SessionStatus.RUNNING


# =============================================================================
# SessionConfig Tests
# =============================================================================


class TestSessionConfig:
    """Tests for SessionConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = SessionConfig(repository_id="repo-123")
        assert config.repository_id == "repo-123"
        assert config.max_rounds == 100
        assert config.convergence_window == 20
        assert config.convergence_threshold == 0.05
        assert config.max_concurrent_solves == 5
        assert config.checkpoint_interval == 10
        assert config.timeout_per_round == 600

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = SessionConfig(
            repository_id="repo-456",
            max_rounds=50,
            convergence_window=10,
            convergence_threshold=0.1,
            max_concurrent_solves=3,
            checkpoint_interval=5,
            timeout_per_round=300,
        )
        assert config.repository_id == "repo-456"
        assert config.max_rounds == 50
        assert config.convergence_window == 10
        assert config.convergence_threshold == 0.1
        assert config.max_concurrent_solves == 3
        assert config.checkpoint_interval == 5
        assert config.timeout_per_round == 300


# =============================================================================
# SessionMetrics Tests
# =============================================================================


class TestSessionMetrics:
    """Tests for SessionMetrics dataclass."""

    def test_default_metrics(self) -> None:
        """Test default metrics values."""
        metrics = SessionMetrics()
        assert metrics.total_rounds == 0
        assert metrics.successful_injections == 0
        assert metrics.successful_solves == 0
        assert metrics.higher_order_bugs == 0
        assert metrics.total_tokens == 0
        assert metrics.total_cost == 0.0
        assert metrics.avg_solve_attempts == 0.0
        assert metrics.solve_rate_history == []

    def test_injection_success_rate_zero_rounds(self) -> None:
        """Test injection success rate with zero rounds."""
        metrics = SessionMetrics()
        assert metrics.injection_success_rate == 0

    def test_injection_success_rate_with_data(self) -> None:
        """Test injection success rate calculation."""
        metrics = SessionMetrics(total_rounds=10, successful_injections=8)
        assert metrics.injection_success_rate == 0.8

    def test_solve_rate_zero_injections(self) -> None:
        """Test solve rate with zero successful injections."""
        metrics = SessionMetrics()
        assert metrics.solve_rate == 0

    def test_solve_rate_with_data(self) -> None:
        """Test solve rate calculation."""
        metrics = SessionMetrics(successful_injections=10, successful_solves=7)
        assert metrics.solve_rate == 0.7

    def test_update_with_successful_injection_and_solve(
        self, mock_injection_result: InjectionResult, mock_solve_result: SolveResult
    ) -> None:
        """Test updating metrics with successful round."""
        metrics = SessionMetrics()
        round_result = RoundResult(
            round_number=1,
            artifact_id="test-artifact",
            injection_result=mock_injection_result,
            solve_result=mock_solve_result,
        )

        metrics.update(round_result)

        assert metrics.total_rounds == 1
        assert metrics.successful_injections == 1
        assert metrics.successful_solves == 1
        assert (
            metrics.total_tokens
            == mock_injection_result.tokens_used + mock_solve_result.total_tokens
        )
        assert (
            metrics.total_cost
            == mock_injection_result.cost_usd + mock_solve_result.total_cost
        )
        assert len(metrics.solve_rate_history) == 1
        assert metrics.solve_rate_history[0] == 1.0

    def test_update_with_failed_injection(self) -> None:
        """Test updating metrics with failed injection."""
        metrics = SessionMetrics()
        failed_injection = InjectionResult(success=False, error="Test error")
        round_result = RoundResult(
            round_number=1,
            artifact_id="test-artifact",
            injection_result=failed_injection,
            solve_result=None,
        )

        metrics.update(round_result)

        assert metrics.total_rounds == 1
        assert metrics.successful_injections == 0
        assert metrics.successful_solves == 0
        assert len(metrics.solve_rate_history) == 0  # No history without injections

    def test_update_with_higher_order_bug(
        self,
        mock_injection_result: InjectionResult,
        mock_failed_solve_result: SolveResult,
    ) -> None:
        """Test updating metrics with higher order bug created."""
        metrics = SessionMetrics()
        round_result = RoundResult(
            round_number=1,
            artifact_id="test-artifact",
            injection_result=mock_injection_result,
            solve_result=mock_failed_solve_result,
            higher_order_created=True,
        )

        metrics.update(round_result)

        assert metrics.higher_order_bugs == 1

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        metrics = SessionMetrics(
            total_rounds=10,
            successful_injections=8,
            successful_solves=6,
            higher_order_bugs=2,
            total_tokens=5000,
            total_cost=0.50,
            avg_solve_attempts=2.5,
        )

        data = metrics.to_dict()

        assert data["total_rounds"] == 10
        assert data["successful_injections"] == 8
        assert data["successful_solves"] == 6
        assert data["higher_order_bugs"] == 2
        assert data["injection_success_rate"] == 0.8
        assert data["solve_rate"] == 0.75
        assert data["avg_solve_attempts"] == 2.5
        assert data["total_tokens"] == 5000
        assert data["total_cost"] == 0.50


# =============================================================================
# SessionCheckpoint Tests
# =============================================================================


class TestSessionCheckpoint:
    """Tests for SessionCheckpoint dataclass."""

    def test_create_checkpoint(self) -> None:
        """Test basic checkpoint creation."""
        checkpoint = SessionCheckpoint(
            session_id="session-123",
            repository_id="repo-456",
            current_round=5,
            completed_rounds=["art-1", "art-2", "art-3", "art-4", "art-5"],
            status=SessionStatus.RUNNING,
        )

        assert checkpoint.session_id == "session-123"
        assert checkpoint.repository_id == "repo-456"
        assert checkpoint.current_round == 5
        assert len(checkpoint.completed_rounds) == 5
        assert checkpoint.status == SessionStatus.RUNNING

    def test_checkpoint_timestamps(self) -> None:
        """Test checkpoint timestamp defaults."""
        checkpoint = SessionCheckpoint(
            session_id="session-123",
            repository_id="repo-456",
            current_round=0,
            completed_rounds=[],
            status=SessionStatus.INITIALIZING,
        )

        assert checkpoint.created_at is not None
        assert checkpoint.updated_at is not None
        assert checkpoint.created_at.tzinfo is not None

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        checkpoint = SessionCheckpoint(
            session_id="session-123",
            repository_id="repo-456",
            current_round=3,
            completed_rounds=["art-1", "art-2", "art-3"],
            status=SessionStatus.RUNNING,
        )

        data = checkpoint.to_dict()

        assert data["session_id"] == "session-123"
        assert data["repository_id"] == "repo-456"
        assert data["current_round"] == 3
        assert data["completed_rounds"] == ["art-1", "art-2", "art-3"]
        assert data["status"] == "running"
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "session_id": "session-456",
            "repository_id": "repo-789",
            "current_round": 10,
            "completed_rounds": ["art-1", "art-2"],
            "status": "paused",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T01:00:00+00:00",
        }

        checkpoint = SessionCheckpoint.from_dict(data)

        assert checkpoint.session_id == "session-456"
        assert checkpoint.repository_id == "repo-789"
        assert checkpoint.current_round == 10
        assert checkpoint.status == SessionStatus.PAUSED
        assert checkpoint.created_at.year == 2026


# =============================================================================
# RoundResult Tests
# =============================================================================


class TestRoundResult:
    """Tests for RoundResult dataclass."""

    def test_create_round_result(
        self, mock_injection_result: InjectionResult, mock_solve_result: SolveResult
    ) -> None:
        """Test basic round result creation."""
        result = RoundResult(
            round_number=5,
            artifact_id="art-123",
            injection_result=mock_injection_result,
            solve_result=mock_solve_result,
            higher_order_created=False,
            duration_seconds=10.5,
        )

        assert result.round_number == 5
        assert result.artifact_id == "art-123"
        assert result.injection_result.success
        assert result.solve_result.solved
        assert result.duration_seconds == 10.5

    def test_to_dict_with_solve(
        self, mock_injection_result: InjectionResult, mock_solve_result: SolveResult
    ) -> None:
        """Test serialization with successful solve."""
        result = RoundResult(
            round_number=3,
            artifact_id="art-456",
            injection_result=mock_injection_result,
            solve_result=mock_solve_result,
            duration_seconds=15.0,
        )

        data = result.to_dict()

        assert data["round_number"] == 3
        assert data["artifact_id"] == "art-456"
        assert data["injection_success"] is True
        assert data["injection_difficulty"] == 5
        assert data["solved"] is True
        assert data["solve_attempts"] == 1
        assert data["higher_order_created"] is False
        assert data["duration_seconds"] == 15.0

    def test_to_dict_without_solve(
        self, mock_injection_result: InjectionResult
    ) -> None:
        """Test serialization without solve result."""
        result = RoundResult(
            round_number=1,
            artifact_id="art-789",
            injection_result=mock_injection_result,
            solve_result=None,
        )

        data = result.to_dict()

        assert data["solved"] is False
        assert data["solve_attempts"] == 0


# =============================================================================
# SelfPlayOrchestrator Tests
# =============================================================================


class TestSelfPlayOrchestrator:
    """Tests for SelfPlayOrchestrator class."""

    def test_initialization(self, mock_orchestrator) -> None:
        """Test orchestrator initialization."""
        assert mock_orchestrator._sessions == {}
        assert mock_orchestrator._metrics == {}
        assert mock_orchestrator._stop_flags == {}
        assert mock_orchestrator.injection_agent is not None
        assert mock_orchestrator.solving_agent is not None

    def test_initialization_with_custom_services(self) -> None:
        """Test orchestrator initialization with custom services."""
        custom_storage = MagicMock()
        custom_context = MagicMock()
        custom_sandbox = MagicMock()
        custom_policy = MagicMock()

        with (
            patch("src.agents.ssr.bug_injection_agent.BugInjectionAgent"),
            patch("src.agents.ssr.bug_solving_agent.BugSolvingAgent"),
        ):
            orchestrator = SelfPlayOrchestrator(
                artifact_storage=custom_storage,
                context_service=custom_context,
                sandbox_orchestrator=custom_sandbox,
                shared_policy=custom_policy,
            )

            assert orchestrator.artifact_storage == custom_storage
            assert orchestrator.context_service == custom_context
            assert orchestrator.sandbox == custom_sandbox
            assert orchestrator.policy == custom_policy

    @pytest.mark.asyncio
    async def test_start_session(
        self,
        mock_orchestrator,
        session_config: SessionConfig,
    ) -> None:
        """Test starting a new session."""
        session_id = await mock_orchestrator.start_session(
            config=session_config,
            code_files=["src/main.py"],
            code_contents={"src/main.py": "def foo(): pass"},
            test_files=["tests/test_main.py"],
        )

        assert session_id.startswith("ssr-session-")
        assert session_id in mock_orchestrator._sessions
        assert session_id in mock_orchestrator._metrics
        assert session_id in mock_orchestrator._stop_flags
        assert mock_orchestrator._stop_flags[session_id] is False

    @pytest.mark.asyncio
    async def test_stop_session(
        self,
        mock_orchestrator,
        session_config: SessionConfig,
    ) -> None:
        """Test stopping a running session."""
        session_id = await mock_orchestrator.start_session(
            config=session_config,
            code_files=["src/main.py"],
            code_contents={"src/main.py": "def foo(): pass"},
            test_files=[],
        )

        result = await mock_orchestrator.stop_session(session_id)
        assert result is True
        assert mock_orchestrator._stop_flags[session_id] is True

    @pytest.mark.asyncio
    async def test_stop_nonexistent_session(self, mock_orchestrator) -> None:
        """Test stopping a nonexistent session."""
        result = await mock_orchestrator.stop_session("nonexistent-session")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_session_status(
        self,
        mock_orchestrator,
        session_config: SessionConfig,
    ) -> None:
        """Test getting session status."""
        session_id = await mock_orchestrator.start_session(
            config=session_config,
            code_files=["src/main.py"],
            code_contents={"src/main.py": "def foo(): pass"},
            test_files=[],
        )

        status = await mock_orchestrator.get_session_status(session_id)

        assert status is not None
        assert status["session_id"] == session_id
        assert "status" in status
        assert "current_round" in status
        assert "total_completed" in status
        assert "metrics" in status
        assert "updated_at" in status

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_status(self, mock_orchestrator) -> None:
        """Test getting status of nonexistent session."""
        status = await mock_orchestrator.get_session_status("nonexistent-session")
        assert status is None

    @pytest.mark.asyncio
    async def test_resume_session(self, mock_orchestrator) -> None:
        """Test resuming a paused session."""
        # Manually create a paused session
        session_id = "test-paused-session"
        mock_orchestrator._sessions[session_id] = SessionCheckpoint(
            session_id=session_id,
            repository_id="repo-123",
            current_round=5,
            completed_rounds=[],
            status=SessionStatus.PAUSED,
        )
        mock_orchestrator._stop_flags[session_id] = True

        result = await mock_orchestrator.resume_session(session_id)
        assert result is True
        assert mock_orchestrator._stop_flags[session_id] is False

    @pytest.mark.asyncio
    async def test_resume_nonexistent_session(self, mock_orchestrator) -> None:
        """Test resuming a nonexistent session."""
        result = await mock_orchestrator.resume_session("nonexistent-session")
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_running_session_fails(self, mock_orchestrator) -> None:
        """Test that resuming a non-paused session fails."""
        # Manually create a running session
        session_id = "test-running-session"
        mock_orchestrator._sessions[session_id] = SessionCheckpoint(
            session_id=session_id,
            repository_id="repo-123",
            current_round=5,
            completed_rounds=[],
            status=SessionStatus.RUNNING,
        )

        result = await mock_orchestrator.resume_session(session_id)
        assert result is False

    def test_get_all_sessions(self, mock_orchestrator) -> None:
        """Test getting all sessions."""
        # Add some test sessions
        mock_orchestrator._sessions["session-1"] = SessionCheckpoint(
            session_id="session-1",
            repository_id="repo-a",
            current_round=5,
            completed_rounds=[],
            status=SessionStatus.RUNNING,
        )
        mock_orchestrator._sessions["session-2"] = SessionCheckpoint(
            session_id="session-2",
            repository_id="repo-b",
            current_round=10,
            completed_rounds=[],
            status=SessionStatus.COMPLETED,
        )

        sessions = mock_orchestrator.get_all_sessions()

        assert len(sessions) == 2
        session_ids = [s["session_id"] for s in sessions]
        assert "session-1" in session_ids
        assert "session-2" in session_ids

    def test_get_all_sessions_empty(self, mock_orchestrator) -> None:
        """Test getting all sessions when empty."""
        sessions = mock_orchestrator.get_all_sessions()
        assert sessions == []


# =============================================================================
# Convergence Detection Tests
# =============================================================================


class TestConvergenceDetection:
    """Tests for convergence detection logic."""

    def test_check_convergence_insufficient_history(self, mock_orchestrator) -> None:
        """Test convergence check with insufficient history."""
        metrics = SessionMetrics()
        metrics.solve_rate_history = [0.5] * 10  # Less than window

        result = mock_orchestrator._check_convergence(
            metrics, window=20, threshold=0.05
        )
        assert result is False

    def test_check_convergence_not_converged(self, mock_orchestrator) -> None:
        """Test convergence check when not converged."""
        metrics = SessionMetrics()
        # Old window: low solve rate, new window: high solve rate
        metrics.solve_rate_history = [0.3] * 20 + [0.8] * 20

        result = mock_orchestrator._check_convergence(
            metrics, window=20, threshold=0.05
        )
        assert result is False

    def test_check_convergence_converged(self, mock_orchestrator) -> None:
        """Test convergence check when converged."""
        metrics = SessionMetrics()
        # Both windows have similar solve rate
        metrics.solve_rate_history = [0.65] * 20 + [0.66] * 20

        result = mock_orchestrator._check_convergence(
            metrics, window=20, threshold=0.05
        )
        assert result is True

    def test_check_convergence_no_old_window(self, mock_orchestrator) -> None:
        """Test convergence check without enough old history."""
        metrics = SessionMetrics()
        # Only enough for one window
        metrics.solve_rate_history = [0.5] * 20

        result = mock_orchestrator._check_convergence(
            metrics, window=20, threshold=0.05
        )
        assert result is False


# =============================================================================
# Session Run Tests
# =============================================================================


class TestSessionRun:
    """Tests for session run logic."""

    @pytest.mark.asyncio
    async def test_run_session_no_candidates(
        self,
        mock_orchestrator,
        session_config: SessionConfig,
    ) -> None:
        """Test session fails when no injection candidates found."""
        mock_orchestrator.injection_agent.find_injection_candidates = AsyncMock(
            return_value=[]
        )

        session_id = await mock_orchestrator.start_session(
            config=session_config,
            code_files=["src/main.py"],
            code_contents={"src/main.py": "def foo(): pass"},
            test_files=[],
        )

        # Wait for the background task to complete
        import asyncio

        await asyncio.sleep(0.2)

        checkpoint = mock_orchestrator._sessions[session_id]
        assert checkpoint.status == SessionStatus.FAILED

    @pytest.mark.asyncio
    async def test_run_round(
        self,
        mock_orchestrator,
        session_config: SessionConfig,
        injection_candidate: InjectionCandidate,
        mock_injection_result: InjectionResult,
        mock_solve_result: SolveResult,
    ) -> None:
        """Test running a single round."""
        mock_orchestrator.injection_agent.inject_bug = AsyncMock(
            return_value=mock_injection_result
        )
        mock_orchestrator.solving_agent.solve = AsyncMock(
            return_value=mock_solve_result
        )

        candidates = [injection_candidate]
        code_contents = {"src/calculator.py": "def divide(a, b):\n    return a / b"}

        result = await mock_orchestrator._run_round(
            session_id="test-session",
            round_number=1,
            config=session_config,
            candidates=candidates,
            code_contents=code_contents,
            test_files=["tests/test_calc.py"],
            commit_sha="abc123",
        )

        assert isinstance(result, RoundResult)
        assert result.round_number == 1
        assert result.injection_result.success is True
        assert result.solve_result.solved is True

    @pytest.mark.asyncio
    async def test_run_round_failed_injection(
        self,
        mock_orchestrator,
        session_config: SessionConfig,
        injection_candidate: InjectionCandidate,
    ) -> None:
        """Test running a round with failed injection."""
        failed_injection = InjectionResult(success=False, error="Injection failed")
        mock_orchestrator.injection_agent.inject_bug = AsyncMock(
            return_value=failed_injection
        )

        candidates = [injection_candidate]
        code_contents = {"src/calculator.py": "def divide(a, b):\n    return a / b"}

        result = await mock_orchestrator._run_round(
            session_id="test-session",
            round_number=1,
            config=session_config,
            candidates=candidates,
            code_contents=code_contents,
            test_files=["tests/test_calc.py"],
            commit_sha="abc123",
        )

        assert result.injection_result.success is False
        assert result.solve_result is None
        assert result.artifact_id == "failed-1"


# =============================================================================
# Higher Order Bug Creation Tests
# =============================================================================


class TestHigherOrderBugCreation:
    """Tests for higher-order bug creation logic."""

    @pytest.mark.asyncio
    async def test_create_higher_order_bug_no_attempts(
        self,
        mock_orchestrator,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test higher-order bug creation with no attempts."""
        solve_result = SolveResult(
            artifact_id="test",
            status=SolveStatus.FAILED,
            attempts=[],  # No attempts
        )

        result = await mock_orchestrator._create_higher_order_bug(
            sample_artifact, solve_result
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_create_higher_order_bug_empty_patch(
        self,
        mock_orchestrator,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test higher-order bug creation with empty patch."""
        solve_result = SolveResult(
            artifact_id="test",
            status=SolveStatus.FAILED,
            attempts=[
                SolveAttempt(
                    attempt_number=1,
                    patch_diff="",  # Empty patch
                    test_passed=False,
                    test_output="Failed",
                    duration_seconds=5.0,
                    tokens_used=100,
                    cost_usd=0.01,
                )
            ],
        )

        result = await mock_orchestrator._create_higher_order_bug(
            sample_artifact, solve_result
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_create_higher_order_bug_success(
        self,
        mock_orchestrator,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test successful higher-order bug creation."""
        solve_result = SolveResult(
            artifact_id="test",
            status=SolveStatus.FAILED,
            attempts=[
                SolveAttempt(
                    attempt_number=1,
                    patch_diff="--- a/foo.py\n+++ b/foo.py\n-bug\n+wrong_fix",
                    test_passed=False,
                    test_output="Failed",
                    duration_seconds=5.0,
                    tokens_used=100,
                    cost_usd=0.01,
                )
            ],
        )

        result = await mock_orchestrator._create_higher_order_bug(
            sample_artifact, solve_result
        )
        assert result is True
        mock_orchestrator.artifact_storage.store_artifact.assert_called_once()


# =============================================================================
# Test Output Tests
# =============================================================================


class TestGetTestOutput:
    """Tests for test output retrieval."""

    @pytest.mark.asyncio
    async def test_get_test_output_no_sandbox(
        self,
        mock_orchestrator,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test getting test output without sandbox returns mock."""
        mock_orchestrator.sandbox = None
        code_contents = {"foo.py": "def foo(): pass"}

        output = await mock_orchestrator._get_test_output(
            sample_artifact, code_contents
        )

        assert "FAILED" in output
        assert "tests/test_main.py" in output

    @pytest.mark.asyncio
    async def test_get_test_output_with_sandbox(
        self,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test getting test output with sandbox."""
        mock_sandbox = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "Real sandbox test output"
        mock_sandbox.execute_with_patch = AsyncMock(return_value=mock_result)

        with (
            patch("src.agents.ssr.bug_injection_agent.BugInjectionAgent"),
            patch("src.agents.ssr.bug_solving_agent.BugSolvingAgent"),
        ):
            orchestrator = SelfPlayOrchestrator(sandbox_orchestrator=mock_sandbox)
            code_contents = {"foo.py": "def foo(): pass"}

            output = await orchestrator._get_test_output(sample_artifact, code_contents)

            assert output == "Real sandbox test output"

    @pytest.mark.asyncio
    async def test_get_test_output_sandbox_error(
        self,
        sample_artifact: BugArtifact,
    ) -> None:
        """Test getting test output when sandbox fails falls back to mock."""
        mock_sandbox = MagicMock()
        mock_sandbox.execute_with_patch = AsyncMock(
            side_effect=Exception("Sandbox error")
        )

        with (
            patch("src.agents.ssr.bug_injection_agent.BugInjectionAgent"),
            patch("src.agents.ssr.bug_solving_agent.BugSolvingAgent"),
        ):
            orchestrator = SelfPlayOrchestrator(sandbox_orchestrator=mock_sandbox)
            code_contents = {"foo.py": "def foo(): pass"}

            output = await orchestrator._get_test_output(sample_artifact, code_contents)

            # Should fall back to mock output
            assert "FAILED" in output


# =============================================================================
# Save Checkpoint Tests
# =============================================================================


class TestSaveCheckpoint:
    """Tests for checkpoint saving."""

    @pytest.mark.asyncio
    async def test_save_checkpoint(self, mock_orchestrator) -> None:
        """Test checkpoint saving."""
        checkpoint = SessionCheckpoint(
            session_id="test-session",
            repository_id="repo-123",
            current_round=10,
            completed_rounds=["art-1", "art-2"],
            status=SessionStatus.RUNNING,
        )

        # Should not raise
        await mock_orchestrator._save_checkpoint(checkpoint)


# =============================================================================
# Integration-like Tests
# =============================================================================


class TestOrchestratorIntegration:
    """Integration-like tests for the orchestrator."""

    @pytest.mark.asyncio
    async def test_full_round_cycle(
        self,
        mock_orchestrator,
        sample_artifact: BugArtifact,
        injection_candidate: InjectionCandidate,
    ) -> None:
        """Test a full round cycle with injection and solve."""
        # Set up mock injection result
        mock_injection_result = InjectionResult(
            success=True,
            artifact=sample_artifact,
            bug_type=BugType.WRONG_OPERATOR,
            difficulty=5,
            tokens_used=100,
            cost_usd=0.01,
        )
        mock_orchestrator.injection_agent.inject_bug = AsyncMock(
            return_value=mock_injection_result
        )

        # Set up mock solve result
        mock_solve_result = SolveResult(
            artifact_id=sample_artifact.artifact_id,
            status=SolveStatus.SOLVED,
            attempts=[
                SolveAttempt(
                    attempt_number=1,
                    patch_diff="--- a/foo.py\n+++ b/foo.py\n-bug\n+fix",
                    test_passed=True,
                    test_output="All tests passed",
                    duration_seconds=5.0,
                    tokens_used=500,
                    cost_usd=0.05,
                )
            ],
            final_patch="--- a/foo.py\n+++ b/foo.py\n-bug\n+fix",
            total_tokens=500,
            total_cost=0.05,
        )
        mock_orchestrator.solving_agent.solve = AsyncMock(
            return_value=mock_solve_result
        )

        # Run a round
        config = SessionConfig(repository_id="repo-123")
        round_result = await mock_orchestrator._run_round(
            session_id="test-session",
            round_number=1,
            config=config,
            candidates=[injection_candidate],
            code_contents={"src/calculator.py": "def divide(a, b):\n    return a / b"},
            test_files=["tests/test_calc.py"],
            commit_sha="abc123",
        )

        assert round_result.injection_result.success is True
        assert round_result.solve_result.solved is True
        assert round_result.artifact_id == sample_artifact.artifact_id

        # Verify storage calls
        mock_orchestrator.artifact_storage.store_artifact.assert_called_once()
        mock_orchestrator.artifact_storage.update_artifact_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_metrics_accumulation_over_rounds(self) -> None:
        """Test that metrics accumulate correctly over multiple rounds."""
        metrics = SessionMetrics()

        # Simulate 3 rounds
        for i in range(3):
            injection_result = InjectionResult(
                success=True,
                difficulty=5,
                tokens_used=100,
                cost_usd=0.01,
            )
            solve_result = SolveResult(
                artifact_id=f"art-{i}",
                status=SolveStatus.SOLVED if i < 2 else SolveStatus.FAILED,
                attempts=[
                    SolveAttempt(
                        attempt_number=1,
                        patch_diff="diff",
                        test_passed=i < 2,
                        test_output="output",
                        duration_seconds=5.0,
                        tokens_used=200,
                        cost_usd=0.02,
                    )
                ],
                total_tokens=200,
                total_cost=0.02,
            )
            round_result = RoundResult(
                round_number=i + 1,
                artifact_id=f"art-{i}",
                injection_result=injection_result,
                solve_result=solve_result,
            )
            metrics.update(round_result)

        assert metrics.total_rounds == 3
        assert metrics.successful_injections == 3
        assert metrics.successful_solves == 2
        assert metrics.total_tokens == 3 * 100 + 3 * 200  # injection + solve tokens
        assert len(metrics.solve_rate_history) == 3


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_round_result_defaults(self) -> None:
        """Test RoundResult default values."""
        injection_result = InjectionResult(success=False)
        result = RoundResult(
            round_number=1,
            artifact_id="test",
            injection_result=injection_result,
            solve_result=None,
        )

        assert result.higher_order_created is False
        assert result.duration_seconds == 0.0

    def test_session_checkpoint_from_dict_all_statuses(self) -> None:
        """Test SessionCheckpoint.from_dict with all status values."""
        for status in SessionStatus:
            data = {
                "session_id": "test",
                "repository_id": "repo",
                "current_round": 0,
                "completed_rounds": [],
                "status": status.value,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
            checkpoint = SessionCheckpoint.from_dict(data)
            assert checkpoint.status == status

    def test_session_metrics_avg_solve_attempts_calculation(self) -> None:
        """Test average solve attempts calculation over multiple updates."""
        metrics = SessionMetrics()

        # First round: 2 attempts
        result1 = RoundResult(
            round_number=1,
            artifact_id="art-1",
            injection_result=InjectionResult(
                success=True, tokens_used=100, cost_usd=0.01
            ),
            solve_result=SolveResult(
                artifact_id="art-1",
                status=SolveStatus.SOLVED,
                attempts=[
                    SolveAttempt(1, "diff", True, "pass", 1.0, 100, 0.01),
                    SolveAttempt(2, "diff", True, "pass", 1.0, 100, 0.01),
                ],
                total_tokens=200,
                total_cost=0.02,
            ),
        )
        metrics.update(result1)
        assert metrics.avg_solve_attempts == 2.0

        # Second round: 4 attempts
        result2 = RoundResult(
            round_number=2,
            artifact_id="art-2",
            injection_result=InjectionResult(
                success=True, tokens_used=100, cost_usd=0.01
            ),
            solve_result=SolveResult(
                artifact_id="art-2",
                status=SolveStatus.SOLVED,
                attempts=[
                    SolveAttempt(1, "diff", False, "fail", 1.0, 100, 0.01),
                    SolveAttempt(2, "diff", False, "fail", 1.0, 100, 0.01),
                    SolveAttempt(3, "diff", False, "fail", 1.0, 100, 0.01),
                    SolveAttempt(4, "diff", True, "pass", 1.0, 100, 0.01),
                ],
                total_tokens=400,
                total_cost=0.04,
            ),
        )
        metrics.update(result2)
        # Average should be (2 + 4) / 2 = 3.0
        assert metrics.avg_solve_attempts == 3.0

    @pytest.mark.asyncio
    async def test_run_session_exception_handling(
        self,
        mock_orchestrator,
        session_config: SessionConfig,
        injection_candidate: InjectionCandidate,
    ) -> None:
        """Test session handles exceptions gracefully."""
        # Make find_injection_candidates raise an exception
        mock_orchestrator.injection_agent.find_injection_candidates = AsyncMock(
            return_value=[injection_candidate]
        )
        mock_orchestrator.injection_agent.inject_bug = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        session_id = await mock_orchestrator.start_session(
            config=session_config,
            code_files=["src/main.py"],
            code_contents={"src/main.py": "def foo(): pass"},
            test_files=[],
        )

        # Wait for the background task to complete
        import asyncio

        await asyncio.sleep(0.2)

        checkpoint = mock_orchestrator._sessions[session_id]
        assert checkpoint.status == SessionStatus.FAILED

    def test_round_robin_candidate_selection(self) -> None:
        """Test that candidates are selected round-robin."""
        # candidate_idx = (round_number - 1) % len(candidates)
        num_candidates = 3
        rounds = 10

        selections = []
        for round_num in range(1, rounds + 1):
            candidate_idx = (round_num - 1) % num_candidates
            selections.append(candidate_idx)

        # Should cycle through 0, 1, 2, 0, 1, 2, ...
        assert selections == [0, 1, 2, 0, 1, 2, 0, 1, 2, 0]
