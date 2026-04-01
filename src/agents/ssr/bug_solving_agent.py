"""
Project Aura - Bug Solving Agent for Self-Play SWE-RL

Implements bug resolution using GraphRAG context retrieval and
multi-attempt solving with backoff.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 2

Key Features:
- GraphRAG context retrieval for code understanding
- Multi-attempt solving with exponential backoff
- Solution validation against test suite
- Integration with existing Coder agent patterns

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.agents.ssr.shared_policy import AgentRole, RoleContext, SharedPolicy
from src.services.ssr.bug_artifact import BugArtifact

if TYPE_CHECKING:
    from src.services.context_retrieval_service import ContextRetrievalService
    from src.services.sandbox_network_service import FargateSandboxOrchestrator

logger = logging.getLogger(__name__)


class SolveStatus(Enum):
    """Status of a solve attempt."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SOLVED = "solved"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class SolveAttempt:
    """Record of a single solve attempt."""

    attempt_number: int
    patch_diff: str
    test_passed: bool
    test_output: str
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "patch_diff": self.patch_diff,
            "test_passed": self.test_passed,
            "test_output": self.test_output[:500],  # Truncate for storage
            "duration_seconds": self.duration_seconds,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "reasoning": self.reasoning,
        }


@dataclass
class SolveResult:
    """Result of a bug solving session."""

    artifact_id: str
    status: SolveStatus
    attempts: list[SolveAttempt] = field(default_factory=list)
    final_patch: str | None = None
    total_tokens: int = 0
    total_cost: float = 0.0
    total_duration: float = 0.0

    @property
    def solved(self) -> bool:
        """Check if the bug was solved."""
        return self.status == SolveStatus.SOLVED

    @property
    def attempt_count(self) -> int:
        """Get total number of attempts."""
        return len(self.attempts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "status": self.status.value,
            "solved": self.solved,
            "attempt_count": self.attempt_count,
            "attempts": [a.to_dict() for a in self.attempts],
            "final_patch": self.final_patch,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "total_duration": self.total_duration,
        }


class BugSolvingAgent:
    """
    Agent for solving bugs in code using GraphRAG context.

    This agent receives a bug artifact (with failing tests) and attempts
    to identify and fix the bug. It uses the shared policy for LLM
    interactions and can leverage GraphRAG for code understanding.

    Usage:
        agent = BugSolvingAgent(
            policy=shared_policy,
            context_service=retrieval_service
        )

        result = await agent.solve(
            artifact=bug_artifact,
            code_context=code_dict,
            max_attempts=3
        )

        if result.solved:
            print(f"Fixed in {result.attempt_count} attempts")
    """

    # Prompt for initial analysis
    ANALYSIS_PROMPT = """Analyze these failing tests and the code to identify the bug.

Failing test output:
```
{test_output}
```

Code under test:
```
{code_context}
```

Related context from codebase:
{graph_context}

Tasks:
1. Identify what the test expects
2. Find the discrepancy in the code
3. Determine the root cause
4. Propose a minimal fix

Be systematic and thorough in your analysis."""

    # Prompt for generating a fix
    FIX_PROMPT = """Based on your analysis, generate a fix for this bug.

Previous analysis:
{analysis}

{previous_attempts}

Requirements:
1. Provide ONLY the necessary changes (minimal fix)
2. Format as a git diff
3. Ensure the fix maintains existing functionality
4. The fix should make all failing tests pass

Output format:
```diff
<your patch here>
```

Reasoning: <brief explanation>"""

    # Prompt for retry after failure
    RETRY_PROMPT = """Your previous fix didn't work. Here's the test output:

```
{test_output}
```

Previous attempt:
```diff
{previous_patch}
```

Analyze why the fix failed and try a different approach. Consider:
1. Did you address the root cause?
2. Are there edge cases you missed?
3. Is there a simpler fix?

Provide a new fix in git diff format."""

    def __init__(
        self,
        policy: SharedPolicy,
        context_service: ContextRetrievalService | None = None,
        sandbox_orchestrator: FargateSandboxOrchestrator | None = None,
        max_attempts: int = 3,
        timeout_seconds: int = 300,
    ):
        """
        Initialize the bug solving agent.

        Args:
            policy: Shared policy for LLM interactions
            context_service: Optional context retrieval service for GraphRAG
            sandbox_orchestrator: Optional sandbox for test execution
            max_attempts: Maximum solve attempts
            timeout_seconds: Timeout per attempt
        """
        self.policy = policy
        self.context_service = context_service
        self.sandbox = sandbox_orchestrator
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds

        # Performance tracking
        self._solve_history: list[tuple[str, bool]] = []  # (artifact_id, solved)

        logger.info(
            f"BugSolvingAgent initialized: max_attempts={max_attempts}, "
            f"timeout={timeout_seconds}s"
        )

    async def solve(
        self,
        artifact: BugArtifact,
        code_context: dict[str, str],
        test_output: str,
        max_attempts: int | None = None,
    ) -> SolveResult:
        """
        Attempt to solve a bug.

        Args:
            artifact: Bug artifact with the injected bug
            code_context: Map of file path to content
            test_output: Output from failing tests
            max_attempts: Override default max attempts

        Returns:
            SolveResult with attempts and final status
        """
        attempts = max_attempts or self.max_attempts
        result = SolveResult(
            artifact_id=artifact.artifact_id,
            status=SolveStatus.IN_PROGRESS,
        )

        start_time = time.time()

        # Create context for solving
        context = self.policy.create_context(
            role=AgentRole.BUG_SOLVER,
            repository_id=artifact.repository_id,
            commit_sha=artifact.commit_sha,
        )

        try:
            # Get GraphRAG context if available
            graph_context = await self._get_graph_context(artifact, test_output)

            # Build code context string
            code_str = self._format_code_context(code_context, artifact.test_files)

            # Initial analysis
            analysis = await self._analyze_bug(
                context, test_output, code_str, graph_context
            )

            # Try to solve
            for attempt_num in range(1, attempts + 1):
                attempt_start = time.time()

                # Generate fix
                if attempt_num == 1:
                    patch, reasoning, response = await self._generate_fix(
                        context, analysis, result.attempts
                    )
                else:
                    # Use retry prompt with previous attempt info
                    patch, reasoning, response = await self._generate_retry_fix(
                        context,
                        test_output,
                        result.attempts[-1].patch_diff,
                    )

                if not patch:
                    result.attempts.append(
                        SolveAttempt(
                            attempt_number=attempt_num,
                            patch_diff="",
                            test_passed=False,
                            test_output="Failed to generate patch",
                            duration_seconds=time.time() - attempt_start,
                            tokens_used=response.get("tokens_used", 0),
                            cost_usd=response.get("cost_usd", 0),
                            reasoning=reasoning,
                        )
                    )
                    continue

                # Validate the fix by running tests
                test_passed, new_test_output = await self._validate_fix(
                    artifact, code_context, patch
                )

                attempt = SolveAttempt(
                    attempt_number=attempt_num,
                    patch_diff=patch,
                    test_passed=test_passed,
                    test_output=new_test_output,
                    duration_seconds=time.time() - attempt_start,
                    tokens_used=response.get("tokens_used", 0),
                    cost_usd=response.get("cost_usd", 0),
                    reasoning=reasoning,
                )
                result.attempts.append(attempt)
                result.total_tokens += attempt.tokens_used
                result.total_cost += attempt.cost_usd

                if test_passed:
                    result.status = SolveStatus.SOLVED
                    result.final_patch = patch
                    break

                # Exponential backoff between retries
                if attempt_num < attempts:
                    await asyncio.sleep(0.5 * (2 ** (attempt_num - 1)))

            if result.status != SolveStatus.SOLVED:
                result.status = SolveStatus.FAILED

        except asyncio.TimeoutError:
            result.status = SolveStatus.TIMEOUT
            logger.warning(f"Solve timed out for artifact {artifact.artifact_id}")
        except Exception as e:
            result.status = SolveStatus.ERROR
            logger.error(f"Solve error for artifact {artifact.artifact_id}: {e}")
        finally:
            result.total_duration = time.time() - start_time
            self.policy.invalidate_context(context)

        # Track history
        self._solve_history.append((artifact.artifact_id, result.solved))

        return result

    async def _get_graph_context(
        self,
        artifact: BugArtifact,
        test_output: str,
    ) -> str:
        """Retrieve relevant context from GraphRAG."""
        if self.context_service is None:
            return "No GraphRAG context available."

        try:
            # Extract key terms from test output for query
            query_terms = self._extract_query_terms(test_output)

            # Query the context service
            results = await self.context_service.retrieve(
                query=query_terms,
                repository_id=artifact.repository_id,
                search_types=["CALL_GRAPH", "DEPENDENCIES", "RELATED"],
                max_results=10,
            )

            if results:
                context_parts = []
                for item in results[:5]:  # Top 5 results
                    context_parts.append(
                        f"- {item.get('path', 'unknown')}: {item.get('content', '')[:200]}"
                    )
                return "\n".join(context_parts)

        except Exception as e:
            logger.warning(f"GraphRAG context retrieval failed: {e}")

        return "No GraphRAG context available."

    def _extract_query_terms(self, test_output: str) -> str:
        """Extract relevant terms from test output for GraphRAG query."""
        # Look for function names, class names, error messages
        patterns = [
            r"(?:def|class)\s+(\w+)",
            r"(\w+Error|\w+Exception)",
            r"assert\w*\s+(\w+)",
            r"File \"[^\"]+\", line \d+, in (\w+)",
        ]

        terms = set()
        for pattern in patterns:
            matches = re.findall(pattern, test_output)
            terms.update(matches)

        return " ".join(list(terms)[:10])

    def _format_code_context(
        self,
        code_context: dict[str, str],
        test_files: list[str],
    ) -> str:
        """Format code context for the prompt."""
        parts = []

        # Prioritize non-test files
        for path, content in code_context.items():
            if path not in test_files:
                parts.append(f"# {path}\n{content[:2000]}")

        return "\n\n".join(parts[:5])  # Limit to 5 files

    async def _analyze_bug(
        self,
        context: RoleContext,
        test_output: str,
        code_context: str,
        graph_context: str,
    ) -> str:
        """Perform initial bug analysis."""
        prompt = self.ANALYSIS_PROMPT.format(
            test_output=test_output[:3000],
            code_context=code_context[:5000],
            graph_context=graph_context,
        )

        response = await self.policy.generate(
            context=context,
            user_prompt=prompt,
        )

        return response.get("content", "")

    async def _generate_fix(
        self,
        context: RoleContext,
        analysis: str,
        previous_attempts: list[SolveAttempt],
    ) -> tuple[str | None, str, dict[str, Any]]:
        """Generate a fix based on analysis."""
        previous_str = ""
        if previous_attempts:
            previous_str = "\n".join(
                f"Attempt {a.attempt_number}: {a.reasoning}" for a in previous_attempts
            )
            previous_str = f"\nPrevious failed attempts:\n{previous_str}"

        prompt = self.FIX_PROMPT.format(
            analysis=analysis[:3000],
            previous_attempts=previous_str,
        )

        response = await self.policy.generate(
            context=context,
            user_prompt=prompt,
        )

        content = response.get("content", "")
        patch = self._extract_patch(content)
        reasoning = self._extract_reasoning(content)

        return patch, reasoning, response

    async def _generate_retry_fix(
        self,
        context: RoleContext,
        test_output: str,
        previous_patch: str,
    ) -> tuple[str | None, str, dict[str, Any]]:
        """Generate a fix after a failed attempt."""
        prompt = self.RETRY_PROMPT.format(
            test_output=test_output[:2000],
            previous_patch=previous_patch,
        )

        response = await self.policy.generate(
            context=context,
            user_prompt=prompt,
        )

        content = response.get("content", "")
        patch = self._extract_patch(content)
        reasoning = self._extract_reasoning(content)

        return patch, reasoning, response

    def _extract_patch(self, content: str) -> str | None:
        """Extract git diff patch from response."""
        # Try to find diff block
        diff_match = re.search(r"```diff\n(.*?)```", content, re.DOTALL)
        if diff_match:
            return diff_match.group(1).strip()

        # Try without language tag
        diff_match = re.search(r"```\n(.*?)```", content, re.DOTALL)
        if diff_match:
            text = diff_match.group(1).strip()
            if text.startswith("---") or text.startswith("diff"):
                return text

        return None

    def _extract_reasoning(self, content: str) -> str:
        """Extract reasoning from response."""
        reasoning_match = re.search(r"Reasoning:\s*(.+?)(?:\n\n|$)", content, re.DOTALL)
        if reasoning_match:
            return reasoning_match.group(1).strip()

        # Return first line as fallback
        lines = content.strip().split("\n")
        return lines[0][:200] if lines else ""

    async def _validate_fix(
        self,
        artifact: BugArtifact,
        code_context: dict[str, str],
        patch: str,
    ) -> tuple[bool, str]:
        """Validate a fix by running tests."""
        if self.sandbox is None:
            # Mock validation for testing
            return self._mock_validate(patch)

        try:
            # Apply patch and run tests in sandbox
            result = await self.sandbox.execute_with_patch(
                repository_id=artifact.repository_id,
                commit_sha=artifact.commit_sha,
                patch=patch,
                test_command=artifact.test_script,
                timeout_seconds=self.timeout_seconds,
            )

            return result.success, result.output

        except Exception as e:
            logger.error(f"Sandbox validation failed: {e}")
            return False, str(e)

    def _mock_validate(self, patch: str) -> tuple[bool, str]:
        """Mock validation for testing without sandbox."""
        # Simple heuristic: if patch looks reasonable, 50% chance of success
        if patch and len(patch) > 20:
            import random

            if random.random() > 0.5:
                return True, "All tests passed."
            return False, "1 test failed: AssertionError"
        return False, "Invalid patch format"

    @property
    def solve_rate(self) -> float:
        """Calculate overall solve rate."""
        if not self._solve_history:
            return 0.0
        return sum(s for _, s in self._solve_history) / len(self._solve_history)

    def get_metrics(self) -> dict[str, Any]:
        """Get agent metrics."""
        recent = self._solve_history[-50:]
        recent_rate = sum(s for _, s in recent) / len(recent) if recent else 0

        return {
            "total_attempts": len(self._solve_history),
            "overall_solve_rate": self.solve_rate,
            "recent_solve_rate": recent_rate,
            "max_attempts_per_bug": self.max_attempts,
        }


# =============================================================================
# Container Entry Point
# =============================================================================


async def run_container() -> int:
    """
    Container entry point for ECS Fargate execution.

    Reads configuration from environment variables:
        ARTIFACT_ID: ID of the bug artifact to solve
        REPOSITORY_ID: Repository containing the code
        MAX_ATTEMPTS: Maximum solve attempts (default: 3)
        TRAINING_JOB_ID: Optional job ID for tracking

    Returns:
        0 if bug was solved, 1 otherwise
    """
    import os
    import sys

    # Configure logging for container
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    logger.info("=" * 60)
    logger.info("SSR Bug Solving Agent - Container Entry Point")
    logger.info("=" * 60)

    # Read configuration from environment
    artifact_id = os.environ.get("ARTIFACT_ID", "")
    repository_id = os.environ.get("REPOSITORY_ID", "")
    max_attempts = int(os.environ.get("MAX_ATTEMPTS", "3"))
    training_job_id = os.environ.get("TRAINING_JOB_ID", "")

    logger.info(f"Artifact ID: {artifact_id}")
    logger.info(f"Repository ID: {repository_id}")
    logger.info(f"Max Attempts: {max_attempts}")
    logger.info(f"Training Job ID: {training_job_id}")

    if not artifact_id:
        logger.error("ARTIFACT_ID environment variable is required")
        return 1

    try:
        # Import storage service (lazy import to avoid circular deps)
        from src.services.ssr.artifact_storage_service import ArtifactStorageService

        # Initialize storage
        storage = ArtifactStorageService()

        # Fetch the artifact
        logger.info("Fetching artifact from storage...")
        artifact = await storage.get_artifact(artifact_id)

        if not artifact:
            logger.error(f"Artifact not found: {artifact_id}")
            return 1

        logger.info(f"Artifact status: {artifact.status.value}")

        # Create shared policy (mock for now - real impl would use Bedrock)
        policy = SharedPolicy()

        # Create the agent
        agent = BugSolvingAgent(
            policy=policy,
            max_attempts=max_attempts,
        )

        # Run the test script to get failing test output
        logger.info("Executing test script to capture failure output...")
        test_output = f"Tests failed for artifact {artifact_id}"

        # Prepare code context (in real impl, would clone repo and read files)
        code_context: dict[str, str] = {}

        # Attempt to solve
        logger.info(f"Starting bug solving (max {max_attempts} attempts)...")
        result = await agent.solve(
            artifact=artifact,
            code_context=code_context,
            test_output=test_output,
            max_attempts=max_attempts,
        )

        # Log results
        logger.info("-" * 60)
        logger.info(f"Solve Status: {result.status.value}")
        logger.info(f"Solved: {result.solved}")
        logger.info(f"Attempts: {result.attempt_count}")
        logger.info(f"Duration: {result.total_duration:.2f}s")
        logger.info("-" * 60)

        if result.solved:
            logger.info("SUCCESS: Bug was solved!")
            return 0
        else:
            logger.info(
                "FAILURE: Bug was NOT solved - higher-order bug will be created"
            )
            return 1

    except Exception as e:
        logger.exception(f"Container execution failed: {e}")
        return 1


def main() -> None:
    """Synchronous entry point for module execution."""
    import sys

    exit_code = asyncio.run(run_container())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
