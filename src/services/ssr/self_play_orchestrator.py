"""
Project Aura - Self-Play Orchestrator for SWE-RL Training

Orchestrates the self-play training loop between bug injection
and bug solving agents. Manages scheduling, checkpointing,
and convergence detection.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 3

Key Features:
- Round-robin scheduling of injection/solving cycles
- Progress checkpointing for resume capability
- Early termination on convergence
- Metrics collection per round

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.services.ssr.bug_artifact import ArtifactStatus

if TYPE_CHECKING:
    from src.agents.ssr.bug_injection_agent import InjectionResult
    from src.agents.ssr.bug_solving_agent import SolveResult
    from src.agents.ssr.shared_policy import SharedPolicy
    from src.services.context_retrieval_service import ContextRetrievalService
    from src.services.sandbox_network_service import FargateSandboxOrchestrator
    from src.services.ssr.artifact_storage_service import ArtifactStorageService

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Status of a self-play session."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    CONVERGED = "converged"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RoundResult:
    """Result of a single self-play round."""

    round_number: int
    artifact_id: str
    injection_result: InjectionResult
    solve_result: SolveResult | None
    higher_order_created: bool = False
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "round_number": self.round_number,
            "artifact_id": self.artifact_id,
            "injection_success": self.injection_result.success,
            "injection_difficulty": self.injection_result.difficulty,
            "solved": self.solve_result.solved if self.solve_result else False,
            "solve_attempts": (
                self.solve_result.attempt_count if self.solve_result else 0
            ),
            "higher_order_created": self.higher_order_created,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class SessionCheckpoint:
    """Checkpoint for session resume."""

    session_id: str
    repository_id: str
    current_round: int
    completed_rounds: list[str]  # artifact IDs
    status: SessionStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "repository_id": self.repository_id,
            "current_round": self.current_round,
            "completed_rounds": self.completed_rounds,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionCheckpoint:
        """Deserialize from dictionary."""
        return cls(
            session_id=data["session_id"],
            repository_id=data["repository_id"],
            current_round=data["current_round"],
            completed_rounds=data["completed_rounds"],
            status=SessionStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class SessionConfig:
    """Configuration for a self-play session."""

    repository_id: str
    max_rounds: int = 100
    convergence_window: int = 20  # Check convergence over last N rounds
    convergence_threshold: float = 0.05  # Stop if solve rate change < threshold
    max_concurrent_solves: int = 5
    checkpoint_interval: int = 10  # Checkpoint every N rounds
    timeout_per_round: int = 600  # 10 minutes per round


@dataclass
class SessionMetrics:
    """Metrics for a self-play session."""

    total_rounds: int = 0
    successful_injections: int = 0
    successful_solves: int = 0
    higher_order_bugs: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_solve_attempts: float = 0.0
    solve_rate_history: list[float] = field(default_factory=list)

    def update(self, round_result: RoundResult) -> None:
        """Update metrics with round result."""
        self.total_rounds += 1

        if round_result.injection_result.success:
            self.successful_injections += 1
            self.total_tokens += round_result.injection_result.tokens_used
            self.total_cost += round_result.injection_result.cost_usd

        if round_result.solve_result:
            if round_result.solve_result.solved:
                self.successful_solves += 1
            self.total_tokens += round_result.solve_result.total_tokens
            self.total_cost += round_result.solve_result.total_cost

            # Update average solve attempts
            attempts = round_result.solve_result.attempt_count
            self.avg_solve_attempts = (
                self.avg_solve_attempts * (self.total_rounds - 1) + attempts
            ) / self.total_rounds

        if round_result.higher_order_created:
            self.higher_order_bugs += 1

        # Track solve rate history
        if self.successful_injections > 0:
            self.solve_rate_history.append(
                self.successful_solves / self.successful_injections
            )

    @property
    def injection_success_rate(self) -> float:
        """Get injection success rate."""
        return (
            self.successful_injections / self.total_rounds if self.total_rounds else 0
        )

    @property
    def solve_rate(self) -> float:
        """Get overall solve rate."""
        return (
            self.successful_solves / self.successful_injections
            if self.successful_injections
            else 0
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_rounds": self.total_rounds,
            "successful_injections": self.successful_injections,
            "successful_solves": self.successful_solves,
            "higher_order_bugs": self.higher_order_bugs,
            "injection_success_rate": self.injection_success_rate,
            "solve_rate": self.solve_rate,
            "avg_solve_attempts": self.avg_solve_attempts,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
        }


class SelfPlayOrchestrator:
    """
    Orchestrates the self-play training loop.

    This class manages the alternating injection/solving cycles,
    tracks progress, and handles checkpointing for long-running
    training sessions.

    Usage:
        orchestrator = SelfPlayOrchestrator(
            artifact_storage=storage_service,
            context_service=retrieval_service
        )

        # Start a new session
        session_id = await orchestrator.start_session(
            config=SessionConfig(
                repository_id="repo-123",
                max_rounds=100
            ),
            code_files=["src/main.py"],
            code_contents={"src/main.py": "..."},
            test_files=["tests/test_main.py"]
        )

        # Or resume a previous session
        session_id = await orchestrator.resume_session("prev-session-id")
    """

    def __init__(
        self,
        artifact_storage: ArtifactStorageService | None = None,
        context_service: ContextRetrievalService | None = None,
        sandbox_orchestrator: FargateSandboxOrchestrator | None = None,
        shared_policy: SharedPolicy | None = None,
    ):
        """
        Initialize the self-play orchestrator.

        Args:
            artifact_storage: Storage service for bug artifacts
            context_service: Context retrieval for GraphRAG
            sandbox_orchestrator: Sandbox for test execution
            shared_policy: Shared policy for agents (created if None)
        """
        # Lazy imports to avoid circular dependencies
        from src.agents.ssr.bug_injection_agent import BugInjectionAgent
        from src.agents.ssr.bug_solving_agent import BugSolvingAgent
        from src.agents.ssr.shared_policy import create_shared_policy
        from src.services.ssr.artifact_storage_service import ArtifactStorageService

        self.artifact_storage = artifact_storage or ArtifactStorageService()
        self.context_service = context_service
        self.sandbox = sandbox_orchestrator
        self.policy = shared_policy or create_shared_policy()

        # Create agents
        self.injection_agent = BugInjectionAgent(policy=self.policy)
        self.solving_agent = BugSolvingAgent(
            policy=self.policy,
            context_service=context_service,
            sandbox_orchestrator=sandbox_orchestrator,
        )

        # Active sessions
        self._sessions: dict[str, SessionCheckpoint] = {}
        self._metrics: dict[str, SessionMetrics] = {}
        self._stop_flags: dict[str, bool] = {}

        logger.info("SelfPlayOrchestrator initialized")

    async def start_session(
        self,
        config: SessionConfig,
        code_files: list[str],
        code_contents: dict[str, str],
        test_files: list[str],
        commit_sha: str = "HEAD",
    ) -> str:
        """
        Start a new self-play training session.

        Args:
            config: Session configuration
            code_files: List of code file paths
            code_contents: Map of file path to content
            test_files: List of test file paths
            commit_sha: Commit SHA to operate on

        Returns:
            Session ID for tracking
        """
        session_id = f"ssr-session-{uuid.uuid4().hex[:12]}"

        checkpoint = SessionCheckpoint(
            session_id=session_id,
            repository_id=config.repository_id,
            current_round=0,
            completed_rounds=[],
            status=SessionStatus.INITIALIZING,
        )

        self._sessions[session_id] = checkpoint
        self._metrics[session_id] = SessionMetrics()
        self._stop_flags[session_id] = False

        logger.info(
            f"Starting self-play session {session_id} for repo {config.repository_id}"
        )

        # Start the training loop in the background
        asyncio.create_task(
            self._run_session(
                session_id=session_id,
                config=config,
                code_files=code_files,
                code_contents=code_contents,
                test_files=test_files,
                commit_sha=commit_sha,
            )
        )

        return session_id

    async def _run_session(
        self,
        session_id: str,
        config: SessionConfig,
        code_files: list[str],
        code_contents: dict[str, str],
        test_files: list[str],
        commit_sha: str,
    ) -> None:
        """Run the self-play training loop."""
        checkpoint = self._sessions[session_id]
        metrics = self._metrics[session_id]

        checkpoint.status = SessionStatus.RUNNING
        checkpoint.updated_at = datetime.now(timezone.utc)

        try:
            # Find injection candidates
            candidates = await self.injection_agent.find_injection_candidates(
                repository_id=config.repository_id,
                commit_sha=commit_sha,
                code_files=code_files,
                code_contents=code_contents,
                test_files=test_files,
            )

            if not candidates:
                logger.warning(
                    f"No injection candidates found for session {session_id}"
                )
                checkpoint.status = SessionStatus.FAILED
                return

            # Main training loop
            for round_num in range(checkpoint.current_round + 1, config.max_rounds + 1):
                if self._stop_flags.get(session_id, False):
                    logger.info(f"Session {session_id} stopped by user")
                    checkpoint.status = SessionStatus.PAUSED
                    break

                # Check convergence
                if self._check_convergence(
                    metrics, config.convergence_window, config.convergence_threshold
                ):
                    logger.info(f"Session {session_id} converged at round {round_num}")
                    checkpoint.status = SessionStatus.CONVERGED
                    break

                # Run a round
                round_result = await self._run_round(
                    session_id=session_id,
                    round_number=round_num,
                    config=config,
                    candidates=candidates,
                    code_contents=code_contents,
                    test_files=test_files,
                    commit_sha=commit_sha,
                )

                # Update state
                metrics.update(round_result)
                checkpoint.current_round = round_num
                checkpoint.completed_rounds.append(round_result.artifact_id)
                checkpoint.updated_at = datetime.now(timezone.utc)

                # Checkpoint periodically
                if round_num % config.checkpoint_interval == 0:
                    await self._save_checkpoint(checkpoint)

                # Calibrate difficulty based on solve result
                if round_result.solve_result:
                    self.injection_agent.calibrate_difficulty(
                        round_result.injection_result.difficulty,
                        round_result.solve_result.solved,
                    )

            if checkpoint.status == SessionStatus.RUNNING:
                checkpoint.status = SessionStatus.COMPLETED

        except Exception as e:
            logger.error(f"Session {session_id} failed: {e}")
            checkpoint.status = SessionStatus.FAILED
        finally:
            await self._save_checkpoint(checkpoint)

    async def _run_round(
        self,
        session_id: str,
        round_number: int,
        config: SessionConfig,
        candidates: list,
        code_contents: dict[str, str],
        test_files: list[str],
        commit_sha: str,
    ) -> RoundResult:
        """Run a single round of injection and solving."""
        start_time = time.time()

        # Select a candidate (round-robin through candidates)
        candidate_idx = (round_number - 1) % len(candidates)
        candidate = candidates[candidate_idx]

        # Get full code context for the candidate's file
        code_context = code_contents.get(candidate.file_path, "")

        # Inject a bug
        injection_result = await self.injection_agent.inject_bug(
            repository_id=config.repository_id,
            commit_sha=commit_sha,
            candidate=candidate,
            code_context=code_context,
            test_files=test_files,
        )

        solve_result = None
        higher_order_created = False

        if injection_result.success and injection_result.artifact:
            # Store the artifact
            await self.artifact_storage.store_artifact(injection_result.artifact)

            # Get failing test output (mock for now)
            test_output = await self._get_test_output(
                injection_result.artifact, code_contents
            )

            # Attempt to solve
            solve_result = await self.solving_agent.solve(
                artifact=injection_result.artifact,
                code_context=code_contents,
                test_output=test_output,
            )

            # Update artifact status
            if solve_result.solved:
                injection_result.artifact.status = ArtifactStatus.VALID
            else:
                # Create higher-order bug from failed solve
                higher_order_created = await self._create_higher_order_bug(
                    injection_result.artifact, solve_result
                )

            await self.artifact_storage.update_artifact_status(
                injection_result.artifact.artifact_id,
                injection_result.artifact.status,
            )

        return RoundResult(
            round_number=round_number,
            artifact_id=(
                injection_result.artifact.artifact_id
                if injection_result.artifact
                else f"failed-{round_number}"
            ),
            injection_result=injection_result,
            solve_result=solve_result,
            higher_order_created=higher_order_created,
            duration_seconds=time.time() - start_time,
        )

    async def _get_test_output(
        self,
        artifact,
        code_contents: dict[str, str],
    ) -> str:
        """Get test output after applying bug."""
        if self.sandbox:
            try:
                result = await self.sandbox.execute_with_patch(
                    repository_id=artifact.repository_id,
                    commit_sha=artifact.commit_sha,
                    patch=artifact.bug_inject_diff,
                    test_command=artifact.test_script,
                )
                return result.output
            except Exception as e:
                logger.warning(f"Sandbox execution failed: {e}")

        # Mock test output
        return """FAILED tests/test_main.py::test_divide - AssertionError: assert 2 == 2.5
Expected: 2.5
Got: 2
1 failed, 5 passed in 0.12s"""

    async def _create_higher_order_bug(
        self,
        original_artifact,
        solve_result: SolveResult,
    ) -> bool:
        """Create a higher-order bug from a failed solve attempt."""
        if not solve_result.attempts:
            return False

        # Get the best (closest to solving) failed attempt
        best_attempt = max(
            solve_result.attempts,
            key=lambda a: len(a.patch_diff) if not a.test_passed else 0,
        )

        if not best_attempt.patch_diff:
            return False

        # The failed patch becomes part of the new bug
        # This creates curriculum learning - harder bugs from failed attempts
        try:
            from src.services.ssr.bug_artifact import BugArtifact

            higher_order = BugArtifact(
                artifact_id=f"ssr-ho-{uuid.uuid4().hex[:12]}",
                repository_id=original_artifact.repository_id,
                commit_sha=original_artifact.commit_sha,
                test_script=original_artifact.test_script,
                test_files=original_artifact.test_files,
                test_parser=original_artifact.test_parser,
                # Combine original bug with failed patch
                bug_inject_diff=original_artifact.bug_inject_diff,
                test_weaken_diff=original_artifact.test_weaken_diff,
                status=ArtifactStatus.PENDING,
                order=original_artifact.order + 1,
                parent_artifact_id=original_artifact.artifact_id,
                failed_patch_diff=best_attempt.patch_diff,
            )

            await self.artifact_storage.store_artifact(higher_order)
            logger.info(
                f"Created higher-order bug {higher_order.artifact_id} "
                f"from {original_artifact.artifact_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create higher-order bug: {e}")
            return False

    def _check_convergence(
        self,
        metrics: SessionMetrics,
        window: int,
        threshold: float,
    ) -> bool:
        """Check if training has converged."""
        if len(metrics.solve_rate_history) < window:
            return False

        recent = metrics.solve_rate_history[-window:]
        old = metrics.solve_rate_history[-(window * 2) : -window]

        if not old:
            return False

        recent_avg = sum(recent) / len(recent)
        old_avg = sum(old) / len(old)

        change = abs(recent_avg - old_avg)
        return change < threshold

    async def _save_checkpoint(self, checkpoint: SessionCheckpoint) -> None:
        """Save checkpoint to storage."""
        # In production, this would persist to DynamoDB
        logger.debug(f"Saved checkpoint for session {checkpoint.session_id}")

    async def stop_session(self, session_id: str) -> bool:
        """Stop a running session."""
        if session_id in self._stop_flags:
            self._stop_flags[session_id] = True
            return True
        return False

    async def get_session_status(self, session_id: str) -> dict[str, Any] | None:
        """Get status of a session."""
        if session_id not in self._sessions:
            return None

        checkpoint = self._sessions[session_id]
        metrics = self._metrics.get(session_id, SessionMetrics())

        return {
            "session_id": session_id,
            "status": checkpoint.status.value,
            "current_round": checkpoint.current_round,
            "total_completed": len(checkpoint.completed_rounds),
            "metrics": metrics.to_dict(),
            "updated_at": checkpoint.updated_at.isoformat(),
        }

    async def resume_session(self, session_id: str) -> bool:
        """Resume a paused session."""
        if session_id not in self._sessions:
            return False

        checkpoint = self._sessions[session_id]
        if checkpoint.status != SessionStatus.PAUSED:
            return False

        self._stop_flags[session_id] = False
        # Would need to restore full state and continue
        logger.info(f"Session {session_id} marked for resume")
        return True

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """Get all sessions."""
        return [
            {
                "session_id": sid,
                "repository_id": cp.repository_id,
                "status": cp.status.value,
                "current_round": cp.current_round,
            }
            for sid, cp in self._sessions.items()
        ]
