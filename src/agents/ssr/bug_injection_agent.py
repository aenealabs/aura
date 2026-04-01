"""
Project Aura - Bug Injection Agent for Self-Play SWE-RL

Implements semantic bug generation with difficulty calibration for
self-play training. Creates valid bug artifacts that challenge the
solving agent.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 2

Key Features:
- Semantic bug generation (not syntax errors)
- Difficulty calibration based on solver performance
- History-aware injection using git history
- 5-file artifact generation

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.agents.ssr.shared_policy import AgentRole, SharedPolicy
from src.services.ssr.bug_artifact import ArtifactStatus, BugArtifact, InjectionStrategy

if TYPE_CHECKING:
    from src.services.neptune_graph_service import NeptuneGraphService

logger = logging.getLogger(__name__)


class BugType(Enum):
    """Types of semantic bugs that can be injected."""

    OFF_BY_ONE = "off_by_one"
    WRONG_OPERATOR = "wrong_operator"
    MISSING_CONDITION = "missing_condition"
    WRONG_VARIABLE = "wrong_variable"
    BOUNDARY_ERROR = "boundary_error"
    NULL_HANDLING = "null_handling"
    TYPE_CONFUSION = "type_confusion"
    RACE_CONDITION = "race_condition"
    RESOURCE_LEAK = "resource_leak"
    LOGIC_INVERSION = "logic_inversion"


@dataclass
class InjectionCandidate:
    """A candidate location for bug injection."""

    file_path: str
    function_name: str
    line_start: int
    line_end: int
    code_snippet: str
    complexity_score: float  # 0-1, higher = more complex
    test_coverage: float  # 0-1, higher = better covered
    recommended_bug_types: list[BugType] = field(default_factory=list)


@dataclass
class InjectionResult:
    """Result of a bug injection attempt."""

    success: bool
    artifact: BugArtifact | None = None
    bug_type: BugType | None = None
    difficulty: int = 0  # 1-10
    error: str | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "artifact_id": self.artifact.artifact_id if self.artifact else None,
            "bug_type": self.bug_type.value if self.bug_type else None,
            "difficulty": self.difficulty,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
        }


class BugInjectionAgent:
    """
    Agent for injecting semantic bugs into code.

    This agent analyzes repositories to find suitable injection points,
    then uses the shared policy to generate realistic bugs that will
    challenge the solver agent.

    Usage:
        agent = BugInjectionAgent(policy=shared_policy)

        # Find candidates
        candidates = await agent.find_injection_candidates(
            repository_id="repo-123",
            commit_sha="abc123",
            code_files=["src/main.py", "src/utils.py"]
        )

        # Inject a bug
        result = await agent.inject_bug(
            candidate=candidates[0],
            target_difficulty=5
        )
    """

    # Prompt template for finding injection candidates
    CANDIDATE_PROMPT = """Analyze this code and identify the best locations for injecting semantic bugs.

For each location, provide:
1. Function name
2. Line numbers
3. Why this is a good injection point
4. Recommended bug types

Code:
{code}

Focus on areas with:
- Complex logic or conditions
- Boundary cases
- Error handling
- State management
- Mathematical operations"""

    # Prompt template for bug injection
    INJECTION_PROMPT = """You are injecting a bug into this code for testing purposes.

Target difficulty: {difficulty}/10
Bug type: {bug_type}
Target function: {function_name}

Code context:
```
{code_context}
```

Test files that should detect this bug:
{test_files}

Requirements:
1. Create a SEMANTIC bug (not syntax error)
2. The bug should cause the specified tests to fail
3. The bug should be realistic (something a developer might accidentally introduce)
4. Provide the bug as a git diff format
5. Also provide a test_weaken.diff that would hide the bug from tests

Output format:
```bug_inject.diff
<your diff here>
```

```test_weaken.diff
<your diff here>
```

Difficulty: <1-10>
Bug explanation: <explanation>"""

    def __init__(
        self,
        policy: SharedPolicy,
        graph_service: NeptuneGraphService | None = None,
        min_test_coverage: float = 0.5,
        default_difficulty: int = 5,
    ):
        """
        Initialize the bug injection agent.

        Args:
            policy: Shared policy for LLM interactions
            graph_service: Optional Neptune service for code analysis
            min_test_coverage: Minimum test coverage for injection points
            default_difficulty: Default target difficulty (1-10)
        """
        self.policy = policy
        self.graph_service = graph_service
        self.min_test_coverage = min_test_coverage
        self.default_difficulty = default_difficulty

        # Difficulty calibration based on solver performance
        self._difficulty_history: list[tuple[int, bool]] = []  # (difficulty, solved)
        self._current_difficulty = default_difficulty

        logger.info(
            f"BugInjectionAgent initialized: default_difficulty={default_difficulty}"
        )

    async def find_injection_candidates(
        self,
        repository_id: str,
        commit_sha: str,
        code_files: list[str],
        code_contents: dict[str, str],
        test_files: list[str] | None = None,
    ) -> list[InjectionCandidate]:
        """
        Find suitable locations for bug injection.

        Args:
            repository_id: Repository identifier
            commit_sha: Commit to analyze
            code_files: List of code file paths
            code_contents: Map of file path to content
            test_files: Optional list of test files

        Returns:
            List of injection candidates sorted by suitability
        """
        candidates: list[InjectionCandidate] = []

        for file_path in code_files:
            content = code_contents.get(file_path, "")
            if not content:
                continue

            # Parse the file to find functions
            file_candidates = self._analyze_file(file_path, content)

            # Enhance with test coverage if available
            if test_files:
                file_candidates = self._score_test_coverage(
                    file_candidates, test_files, code_contents
                )

            candidates.extend(file_candidates)

        # Sort by suitability (complexity * coverage)
        candidates.sort(
            key=lambda c: c.complexity_score * c.test_coverage, reverse=True
        )

        logger.info(
            f"Found {len(candidates)} injection candidates in {len(code_files)} files"
        )

        return candidates

    def _analyze_file(
        self,
        file_path: str,
        content: str,
    ) -> list[InjectionCandidate]:
        """Analyze a single file for injection candidates."""
        candidates = []

        # Simple function detection for Python
        if file_path.endswith(".py"):
            candidates.extend(self._analyze_python_file(file_path, content))
        elif file_path.endswith((".js", ".ts")):
            candidates.extend(self._analyze_js_file(file_path, content))

        return candidates

    def _analyze_python_file(
        self,
        file_path: str,
        content: str,
    ) -> list[InjectionCandidate]:
        """Analyze a Python file for injection candidates."""
        candidates = []
        lines = content.split("\n")

        # Find function definitions
        func_pattern = re.compile(r"^\s*(async\s+)?def\s+(\w+)\s*\(")
        current_func = None
        func_start = 0
        func_lines: list[str] = []

        for i, line in enumerate(lines):
            match = func_pattern.match(line)
            if match:
                # Save previous function
                if current_func and func_lines:
                    candidates.append(
                        self._create_candidate(
                            file_path,
                            current_func,
                            func_start,
                            i - 1,
                            "\n".join(func_lines),
                        )
                    )

                current_func = match.group(2)
                func_start = i + 1
                func_lines = [line]
            elif current_func:
                # Check if we're still in the function
                if (
                    line.strip()
                    and not line.startswith(" ")
                    and not line.startswith("\t")
                ):
                    # New top-level definition
                    if func_lines:
                        candidates.append(
                            self._create_candidate(
                                file_path,
                                current_func,
                                func_start,
                                i - 1,
                                "\n".join(func_lines),
                            )
                        )
                    current_func = None
                    func_lines = []
                else:
                    func_lines.append(line)

        # Don't forget the last function
        if current_func and func_lines:
            candidates.append(
                self._create_candidate(
                    file_path,
                    current_func,
                    func_start,
                    len(lines),
                    "\n".join(func_lines),
                )
            )

        return candidates

    def _analyze_js_file(
        self,
        file_path: str,
        content: str,
    ) -> list[InjectionCandidate]:
        """Analyze a JavaScript/TypeScript file for injection candidates."""
        candidates = []
        lines = content.split("\n")

        # Find function definitions
        func_patterns = [
            re.compile(r"^\s*(async\s+)?function\s+(\w+)\s*\("),
            re.compile(r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(?"),
        ]

        for i, line in enumerate(lines):
            for pattern in func_patterns:
                match = pattern.match(line)
                if match:
                    func_name = (
                        match.group(2) if match.lastindex >= 2 else match.group(1)
                    )
                    # Get a snippet of lines after the function definition
                    end_line = min(i + 30, len(lines))
                    snippet = "\n".join(lines[i:end_line])
                    candidates.append(
                        self._create_candidate(
                            file_path, func_name, i + 1, end_line, snippet
                        )
                    )
                    break

        return candidates

    def _create_candidate(
        self,
        file_path: str,
        function_name: str,
        line_start: int,
        line_end: int,
        code_snippet: str,
    ) -> InjectionCandidate:
        """Create an injection candidate with scoring."""
        # Calculate complexity based on code characteristics
        complexity = self._calculate_complexity(code_snippet)

        # Determine recommended bug types
        bug_types = self._recommend_bug_types(code_snippet)

        return InjectionCandidate(
            file_path=file_path,
            function_name=function_name,
            line_start=line_start,
            line_end=line_end,
            code_snippet=code_snippet,
            complexity_score=complexity,
            test_coverage=0.5,  # Default, updated later
            recommended_bug_types=bug_types,
        )

    def _calculate_complexity(self, code: str) -> float:
        """Calculate a complexity score for the code."""
        score = 0.0

        # Check for conditionals
        if re.search(r"\bif\b|\belse\b|\belif\b", code):
            score += 0.2

        # Check for loops
        if re.search(r"\bfor\b|\bwhile\b", code):
            score += 0.2

        # Check for exception handling
        if re.search(r"\btry\b|\bexcept\b|\bcatch\b", code):
            score += 0.15

        # Check for mathematical operations
        if re.search(r"[+\-*/]|%|\*\*", code):
            score += 0.15

        # Check for comparisons
        if re.search(r"[<>]=?|==|!=", code):
            score += 0.15

        # Check for function calls
        if re.search(r"\w+\s*\(", code):
            score += 0.15

        return min(score, 1.0)

    def _recommend_bug_types(self, code: str) -> list[BugType]:
        """Recommend bug types based on code characteristics."""
        types = []

        if re.search(r"\brange\b|\blen\b|[\[\]]", code):
            types.append(BugType.OFF_BY_ONE)

        if re.search(r"[+\-*/]|%", code):
            types.append(BugType.WRONG_OPERATOR)

        if re.search(r"\bif\b.*:", code):
            types.append(BugType.MISSING_CONDITION)
            types.append(BugType.LOGIC_INVERSION)

        if re.search(r"\bnot\b|==|!=|<|>", code):
            types.append(BugType.LOGIC_INVERSION)

        if re.search(r"\bNone\b|\bnull\b", code):
            types.append(BugType.NULL_HANDLING)

        if re.search(r"\bint\b|\bfloat\b|\bstr\b", code):
            types.append(BugType.TYPE_CONFUSION)

        if re.search(r"\bopen\b|\bclose\b|\bwith\b", code):
            types.append(BugType.RESOURCE_LEAK)

        return types or [BugType.WRONG_OPERATOR, BugType.MISSING_CONDITION]

    def _score_test_coverage(
        self,
        candidates: list[InjectionCandidate],
        test_files: list[str],
        code_contents: dict[str, str],
    ) -> list[InjectionCandidate]:
        """Score candidates based on test coverage."""
        for candidate in candidates:
            # Check if function is mentioned in test files
            mentions = 0
            for test_file in test_files:
                test_content = code_contents.get(test_file, "")
                if candidate.function_name in test_content:
                    mentions += 1

            # Score based on test mentions
            candidate.test_coverage = min(mentions / max(len(test_files), 1), 1.0)

        return candidates

    async def inject_bug(
        self,
        repository_id: str,
        commit_sha: str,
        candidate: InjectionCandidate,
        code_context: str,
        test_files: list[str],
        target_difficulty: int | None = None,
    ) -> InjectionResult:
        """
        Inject a bug at the specified candidate location.

        Args:
            repository_id: Repository identifier
            commit_sha: Commit to modify
            candidate: Injection candidate
            code_context: Full code context for the file
            test_files: Test files that should detect the bug
            target_difficulty: Target difficulty (1-10), uses calibrated default if None

        Returns:
            InjectionResult with the generated artifact
        """
        difficulty = target_difficulty or self._current_difficulty
        bug_type = (
            candidate.recommended_bug_types[0]
            if candidate.recommended_bug_types
            else BugType.WRONG_OPERATOR
        )

        # Create context for injection
        context = self.policy.create_context(
            role=AgentRole.BUG_INJECTOR,
            repository_id=repository_id,
            commit_sha=commit_sha,
        )

        try:
            # Build the injection prompt
            prompt = self.INJECTION_PROMPT.format(
                difficulty=difficulty,
                bug_type=bug_type.value,
                function_name=candidate.function_name,
                code_context=code_context,
                test_files="\n".join(f"- {f}" for f in test_files),
            )

            # Generate the bug
            response = await self.policy.generate(
                context=context,
                user_prompt=prompt,
            )

            # Parse the response
            bug_inject_diff, test_weaken_diff, actual_difficulty = self._parse_response(
                response["content"]
            )

            if not bug_inject_diff:
                return InjectionResult(
                    success=False,
                    error="Failed to generate valid bug_inject.diff",
                    tokens_used=response.get("tokens_used", 0),
                    cost_usd=response.get("cost_usd", 0),
                )

            # Create the artifact
            artifact = BugArtifact(
                artifact_id=f"ssr-artifact-{uuid.uuid4().hex[:12]}",
                repository_id=repository_id,
                commit_sha=commit_sha,
                test_script="#!/bin/bash\npytest tests/ -v",
                test_files=test_files,
                test_parser="import json, sys; print(json.dumps({'passed': 'PASSED' in sys.stdin.read()}))",
                bug_inject_diff=bug_inject_diff,
                test_weaken_diff=test_weaken_diff or "",
                injection_strategy=InjectionStrategy.DIRECT_INJECTION,
                status=ArtifactStatus.PENDING,
                created_at=datetime.now(timezone.utc),
            )

            return InjectionResult(
                success=True,
                artifact=artifact,
                bug_type=bug_type,
                difficulty=actual_difficulty or difficulty,
                tokens_used=response.get("tokens_used", 0),
                cost_usd=response.get("cost_usd", 0),
            )

        except Exception as e:
            logger.error(f"Bug injection failed: {e}")
            return InjectionResult(
                success=False,
                error=str(e),
            )
        finally:
            # Invalidate context for isolation
            self.policy.invalidate_context(context)

    def _parse_response(
        self,
        response: str,
    ) -> tuple[str | None, str | None, int | None]:
        """Parse the LLM response to extract diffs and difficulty."""
        bug_inject_diff = None
        test_weaken_diff = None
        difficulty = None

        # Extract bug_inject.diff
        inject_match = re.search(r"```bug_inject\.diff\n(.*?)```", response, re.DOTALL)
        if inject_match:
            bug_inject_diff = inject_match.group(1).strip()

        # Extract test_weaken.diff
        weaken_match = re.search(r"```test_weaken\.diff\n(.*?)```", response, re.DOTALL)
        if weaken_match:
            test_weaken_diff = weaken_match.group(1).strip()

        # Extract difficulty
        diff_match = re.search(r"Difficulty:\s*(\d+)", response)
        if diff_match:
            difficulty = int(diff_match.group(1))

        return bug_inject_diff, test_weaken_diff, difficulty

    def calibrate_difficulty(self, difficulty: int, solved: bool) -> None:
        """
        Calibrate difficulty based on solver performance.

        If bugs are too easy (always solved), increase difficulty.
        If bugs are too hard (never solved), decrease difficulty.

        Args:
            difficulty: Difficulty of the last bug
            solved: Whether the bug was solved
        """
        self._difficulty_history.append((difficulty, solved))

        # Keep only last 20 results
        if len(self._difficulty_history) > 20:
            self._difficulty_history = self._difficulty_history[-20:]

        # Calculate solve rate at current difficulty
        recent = [
            s
            for d, s in self._difficulty_history
            if abs(d - self._current_difficulty) <= 1
        ]
        if len(recent) >= 5:
            solve_rate = sum(recent) / len(recent)

            # Target solve rate is ~50% for optimal learning
            if solve_rate > 0.7:
                self._current_difficulty = min(10, self._current_difficulty + 1)
                logger.info(
                    f"Difficulty increased to {self._current_difficulty} "
                    f"(solve_rate={solve_rate:.2f})"
                )
            elif solve_rate < 0.3:
                self._current_difficulty = max(1, self._current_difficulty - 1)
                logger.info(
                    f"Difficulty decreased to {self._current_difficulty} "
                    f"(solve_rate={solve_rate:.2f})"
                )

    @property
    def current_difficulty(self) -> int:
        """Get the current calibrated difficulty."""
        return self._current_difficulty

    def get_metrics(self) -> dict[str, Any]:
        """Get agent metrics."""
        recent_results = self._difficulty_history[-20:]
        solve_rate = (
            sum(s for _, s in recent_results) / len(recent_results)
            if recent_results
            else 0
        )

        return {
            "current_difficulty": self._current_difficulty,
            "history_size": len(self._difficulty_history),
            "recent_solve_rate": solve_rate,
        }
