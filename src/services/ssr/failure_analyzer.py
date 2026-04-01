"""
Project Aura - Failure Analysis System for Self-Play SWE-RL

Analyzes failed solve attempts to extract learning signals and
categorize failure modes for curriculum learning.

Reference: Meta FAIR "Self-play SWE-RL" (arXiv:2512.18552), Section 5

Key Features:
- Failure mode categorization (timeout, wrong fix, partial fix, etc.)
- Learning signal extraction from failed attempts
- Difficulty scoring for higher-order bug generation
- Pattern detection for common failure types

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
GitHub Issue: #165
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.agents.ssr.bug_solving_agent import SolveAttempt, SolveResult

logger = logging.getLogger(__name__)


class FailureMode(Enum):
    """Categories of solve attempt failures."""

    TIMEOUT = "timeout"  # Solver ran out of time
    WRONG_FIX = "wrong_fix"  # Fix doesn't address the bug
    PARTIAL_FIX = "partial_fix"  # Some tests pass, others still fail
    SYNTAX_ERROR = "syntax_error"  # Generated patch has syntax errors
    TEST_REGRESSION = "test_regression"  # Fix breaks other tests
    NO_PATCH = "no_patch"  # Failed to generate any patch
    INVALID_PATCH = "invalid_patch"  # Patch cannot be applied
    SEMANTIC_ERROR = "semantic_error"  # Logic error in the fix
    RESOURCE_LIMIT = "resource_limit"  # Memory or CPU limit exceeded
    UNKNOWN = "unknown"  # Unclassified failure


class LearningSignalType(Enum):
    """Types of learning signals extracted from failures."""

    COMPLEXITY_UNDERESTIMATE = "complexity_underestimate"
    CONTEXT_INSUFFICIENT = "context_insufficient"
    PATTERN_MISMATCH = "pattern_mismatch"
    EDGE_CASE_MISSED = "edge_case_missed"
    TYPE_CONFUSION = "type_confusion"
    LOGIC_ERROR = "logic_error"
    API_MISUSE = "api_misuse"
    SCOPE_ERROR = "scope_error"
    NONE = "none"


@dataclass
class FailureAnalysis:
    """Analysis of a single failed solve attempt."""

    attempt_id: str
    artifact_id: str
    failure_mode: FailureMode
    learning_signals: list[LearningSignalType] = field(default_factory=list)
    difficulty_delta: int = 0  # How much harder the bug is than estimated
    confidence: float = 0.0  # Confidence in the analysis (0-1)
    error_patterns: list[str] = field(default_factory=list)
    suggested_context: list[str] = field(default_factory=list)
    raw_error: str = ""
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "attempt_id": self.attempt_id,
            "artifact_id": self.artifact_id,
            "failure_mode": self.failure_mode.value,
            "learning_signals": [s.value for s in self.learning_signals],
            "difficulty_delta": self.difficulty_delta,
            "confidence": self.confidence,
            "error_patterns": self.error_patterns,
            "suggested_context": self.suggested_context,
            "raw_error": self.raw_error[:500],  # Truncate for storage
            "analyzed_at": self.analyzed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureAnalysis:
        """Deserialize from dictionary."""
        return cls(
            attempt_id=data["attempt_id"],
            artifact_id=data["artifact_id"],
            failure_mode=FailureMode(data["failure_mode"]),
            learning_signals=[
                LearningSignalType(s) for s in data.get("learning_signals", [])
            ],
            difficulty_delta=data.get("difficulty_delta", 0),
            confidence=data.get("confidence", 0.0),
            error_patterns=data.get("error_patterns", []),
            suggested_context=data.get("suggested_context", []),
            raw_error=data.get("raw_error", ""),
            analyzed_at=(
                datetime.fromisoformat(data["analyzed_at"])
                if "analyzed_at" in data
                else datetime.now(timezone.utc)
            ),
        )


@dataclass
class FailureSummary:
    """Summary of failures for a bug artifact."""

    artifact_id: str
    total_attempts: int
    failure_modes: dict[FailureMode, int] = field(default_factory=dict)
    learning_signals: dict[LearningSignalType, int] = field(default_factory=dict)
    avg_difficulty_delta: float = 0.0
    is_higher_order_candidate: bool = False
    recommended_difficulty: int = 5

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "total_attempts": self.total_attempts,
            "failure_modes": {k.value: v for k, v in self.failure_modes.items()},
            "learning_signals": {k.value: v for k, v in self.learning_signals.items()},
            "avg_difficulty_delta": self.avg_difficulty_delta,
            "is_higher_order_candidate": self.is_higher_order_candidate,
            "recommended_difficulty": self.recommended_difficulty,
        }


class FailureAnalyzer:
    """
    Analyzes failed solve attempts to extract learning signals.

    This analyzer categorizes failures, identifies patterns, and
    determines which failed bugs should become higher-order training
    examples for curriculum learning.

    Usage:
        analyzer = FailureAnalyzer()

        # Analyze a single failed attempt
        analysis = analyzer.analyze_attempt(solve_result, attempt)

        # Summarize all failures for an artifact
        summary = analyzer.summarize_failures(artifact_id, analyses)

        # Check if artifact should become higher-order bug
        if summary.is_higher_order_candidate:
            queue.add_higher_order_bug(artifact_id, summary)
    """

    # Error patterns for failure mode detection
    TIMEOUT_PATTERNS = [
        r"timeout",
        r"timed out",
        r"time limit exceeded",
        r"execution expired",
    ]

    SYNTAX_ERROR_PATTERNS = [
        r"SyntaxError",
        r"IndentationError",
        r"invalid syntax",
        r"unexpected token",
        r"parsing error",
    ]

    PATCH_ERROR_PATTERNS = [
        r"patch.*failed",
        r"hunk.*FAILED",
        r"cannot apply",
        r"does not apply",
        r"conflict",
    ]

    TYPE_ERROR_PATTERNS = [
        r"TypeError",
        r"type.*mismatch",
        r"expected.*got",
        r"cannot.*convert",
    ]

    ASSERTION_PATTERNS = [
        r"AssertionError",
        r"assert.*failed",
        r"expected.*but.*got",
        r"!=",
    ]

    def __init__(
        self,
        min_attempts_for_higher_order: int = 2,
        difficulty_threshold: int = 3,
        confidence_threshold: float = 0.6,
    ):
        """
        Initialize the failure analyzer.

        Args:
            min_attempts_for_higher_order: Minimum failed attempts to consider for higher-order
            difficulty_threshold: Minimum difficulty delta for higher-order consideration
            confidence_threshold: Minimum confidence for analysis to be trusted
        """
        self.min_attempts = min_attempts_for_higher_order
        self.difficulty_threshold = difficulty_threshold
        self.confidence_threshold = confidence_threshold

        # Track analysis history
        self._analysis_cache: dict[str, FailureAnalysis] = {}
        self._pattern_frequency: dict[str, int] = {}

        logger.info(
            f"FailureAnalyzer initialized: min_attempts={min_attempts_for_higher_order}, "
            f"difficulty_threshold={difficulty_threshold}"
        )

    def analyze_attempt(
        self,
        solve_result: SolveResult,
        attempt: SolveAttempt,
        original_difficulty: int = 5,
    ) -> FailureAnalysis:
        """
        Analyze a single failed solve attempt.

        Args:
            solve_result: The overall solve result
            attempt: The specific failed attempt
            original_difficulty: The original bug difficulty (1-10)

        Returns:
            FailureAnalysis with categorization and learning signals
        """
        attempt_id = self._generate_attempt_id(
            solve_result.artifact_id, attempt.attempt_number
        )

        # Check cache
        if attempt_id in self._analysis_cache:
            return self._analysis_cache[attempt_id]

        # Determine failure mode
        failure_mode = self._categorize_failure(attempt)

        # Extract learning signals
        learning_signals = self._extract_learning_signals(attempt, failure_mode)

        # Calculate difficulty delta
        difficulty_delta = self._calculate_difficulty_delta(
            attempt, failure_mode, original_difficulty
        )

        # Extract error patterns
        error_patterns = self._extract_error_patterns(attempt.test_output)

        # Suggest additional context that might help
        suggested_context = self._suggest_context(attempt, learning_signals)

        # Calculate confidence
        confidence = self._calculate_confidence(
            failure_mode, learning_signals, error_patterns
        )

        analysis = FailureAnalysis(
            attempt_id=attempt_id,
            artifact_id=solve_result.artifact_id,
            failure_mode=failure_mode,
            learning_signals=learning_signals,
            difficulty_delta=difficulty_delta,
            confidence=confidence,
            error_patterns=error_patterns,
            suggested_context=suggested_context,
            raw_error=attempt.test_output,
        )

        # Cache the analysis
        self._analysis_cache[attempt_id] = analysis

        # Update pattern frequency
        for pattern in error_patterns:
            self._pattern_frequency[pattern] = (
                self._pattern_frequency.get(pattern, 0) + 1
            )

        logger.debug(
            f"Analyzed attempt {attempt_id}: mode={failure_mode.value}, "
            f"signals={len(learning_signals)}, delta={difficulty_delta}"
        )

        return analysis

    def summarize_failures(
        self,
        artifact_id: str,
        analyses: list[FailureAnalysis],
    ) -> FailureSummary:
        """
        Summarize all failure analyses for an artifact.

        Args:
            artifact_id: The bug artifact ID
            analyses: List of failure analyses

        Returns:
            FailureSummary with aggregated statistics
        """
        if not analyses:
            return FailureSummary(artifact_id=artifact_id, total_attempts=0)

        # Count failure modes
        failure_modes: dict[FailureMode, int] = {}
        for analysis in analyses:
            mode = analysis.failure_mode
            failure_modes[mode] = failure_modes.get(mode, 0) + 1

        # Count learning signals
        learning_signals: dict[LearningSignalType, int] = {}
        for analysis in analyses:
            for signal in analysis.learning_signals:
                learning_signals[signal] = learning_signals.get(signal, 0) + 1

        # Calculate average difficulty delta
        total_delta = sum(a.difficulty_delta for a in analyses)
        avg_delta = total_delta / len(analyses)

        # Determine if this should be a higher-order candidate
        is_candidate = self._is_higher_order_candidate(analyses, avg_delta)

        # Calculate recommended difficulty
        recommended_difficulty = self._calculate_recommended_difficulty(
            analyses, avg_delta
        )

        summary = FailureSummary(
            artifact_id=artifact_id,
            total_attempts=len(analyses),
            failure_modes=failure_modes,
            learning_signals=learning_signals,
            avg_difficulty_delta=avg_delta,
            is_higher_order_candidate=is_candidate,
            recommended_difficulty=recommended_difficulty,
        )

        logger.info(
            f"Failure summary for {artifact_id}: {len(analyses)} attempts, "
            f"higher_order={is_candidate}, recommended_difficulty={recommended_difficulty}"
        )

        return summary

    def _categorize_failure(self, attempt: SolveAttempt) -> FailureMode:
        """Categorize the failure mode based on attempt data."""
        test_output = attempt.test_output.lower()
        patch = attempt.patch_diff

        # Check for timeout
        if any(re.search(p, test_output, re.IGNORECASE) for p in self.TIMEOUT_PATTERNS):
            return FailureMode.TIMEOUT

        # Check for no patch generated
        if not patch or len(patch.strip()) < 10:
            return FailureMode.NO_PATCH

        # Check for syntax errors
        if any(
            re.search(p, test_output, re.IGNORECASE) for p in self.SYNTAX_ERROR_PATTERNS
        ):
            return FailureMode.SYNTAX_ERROR

        # Check for patch application errors
        if any(
            re.search(p, test_output, re.IGNORECASE) for p in self.PATCH_ERROR_PATTERNS
        ):
            return FailureMode.INVALID_PATCH

        # Check for partial fix (some tests pass)
        passed_match = re.search(r"(\d+)\s*passed", test_output)
        failed_match = re.search(r"(\d+)\s*failed", test_output)
        if passed_match and failed_match:
            passed = int(passed_match.group(1))
            failed = int(failed_match.group(1))
            if passed > 0 and failed > 0:
                return FailureMode.PARTIAL_FIX

        # Check for test regression
        if re.search(r"previously.*passed.*now.*fail", test_output, re.IGNORECASE):
            return FailureMode.TEST_REGRESSION

        # Check for type errors (semantic)
        if any(
            re.search(p, test_output, re.IGNORECASE) for p in self.TYPE_ERROR_PATTERNS
        ):
            return FailureMode.SEMANTIC_ERROR

        # Check for assertion failures (wrong fix)
        if any(
            re.search(p, test_output, re.IGNORECASE) for p in self.ASSERTION_PATTERNS
        ):
            return FailureMode.WRONG_FIX

        # Check for resource limits
        if re.search(r"memory|oom|killed|resource", test_output, re.IGNORECASE):
            return FailureMode.RESOURCE_LIMIT

        return FailureMode.UNKNOWN

    def _extract_learning_signals(
        self,
        attempt: SolveAttempt,
        failure_mode: FailureMode,
    ) -> list[LearningSignalType]:
        """Extract learning signals from the failure."""
        signals = []
        test_output = attempt.test_output
        reasoning = attempt.reasoning

        # Map failure modes to primary signals
        mode_to_signal = {
            FailureMode.TIMEOUT: LearningSignalType.COMPLEXITY_UNDERESTIMATE,
            FailureMode.PARTIAL_FIX: LearningSignalType.EDGE_CASE_MISSED,
            FailureMode.SEMANTIC_ERROR: LearningSignalType.TYPE_CONFUSION,
            FailureMode.WRONG_FIX: LearningSignalType.LOGIC_ERROR,
        }

        if failure_mode in mode_to_signal:
            signals.append(mode_to_signal[failure_mode])

        # Check for context insufficiency
        if re.search(r"undefined|not found|missing|import", test_output, re.IGNORECASE):
            signals.append(LearningSignalType.CONTEXT_INSUFFICIENT)

        # Check for API misuse
        if re.search(
            r"attribute.*error|method.*not|invalid.*argument",
            test_output,
            re.IGNORECASE,
        ):
            signals.append(LearningSignalType.API_MISUSE)

        # Check for scope errors
        if re.search(
            r"scope|undefined.*variable|NameError", test_output, re.IGNORECASE
        ):
            signals.append(LearningSignalType.SCOPE_ERROR)

        # Check reasoning for pattern mismatch
        if reasoning and re.search(
            r"thought|expected|assumed", reasoning, re.IGNORECASE
        ):
            signals.append(LearningSignalType.PATTERN_MISMATCH)

        # Deduplicate
        return list(set(signals)) if signals else [LearningSignalType.NONE]

    def _calculate_difficulty_delta(
        self,
        attempt: SolveAttempt,
        failure_mode: FailureMode,
        original_difficulty: int,
    ) -> int:
        """Calculate how much harder the bug is than the original estimate."""
        delta = 0

        # Failure mode adjustments
        mode_deltas = {
            FailureMode.TIMEOUT: 3,
            FailureMode.PARTIAL_FIX: 1,
            FailureMode.WRONG_FIX: 2,
            FailureMode.SEMANTIC_ERROR: 2,
            FailureMode.NO_PATCH: 3,
            FailureMode.TEST_REGRESSION: 2,
        }

        delta += mode_deltas.get(failure_mode, 0)

        # Attempt number adjustment (later attempts = harder)
        if attempt.attempt_number > 1:
            delta += attempt.attempt_number - 1

        # Long attempts suggest complexity
        if attempt.duration_seconds > 60:
            delta += 1

        # Cap the delta
        return min(delta, 5)

    def _extract_error_patterns(self, test_output: str) -> list[str]:
        """Extract reusable error patterns from test output."""
        patterns = []

        # Extract exception types
        exception_match = re.findall(r"(\w+Error|\w+Exception)", test_output)
        patterns.extend(set(exception_match))

        # Extract assertion messages
        assert_match = re.findall(
            r"assert[^:]*:\s*(.{10,50})", test_output, re.IGNORECASE
        )
        for match in assert_match[:3]:  # Limit to 3
            patterns.append(f"assertion: {match.strip()}")

        # Extract function names from stack traces
        func_match = re.findall(r"in (\w+)\n", test_output)
        for func in list(set(func_match))[:5]:
            if not func.startswith("_") and len(func) > 2:
                patterns.append(f"function: {func}")

        return patterns[:10]  # Limit total patterns

    def _suggest_context(
        self,
        attempt: SolveAttempt,
        signals: list[LearningSignalType],
    ) -> list[str]:
        """Suggest additional context that might help solve the bug."""
        suggestions = []

        signal_suggestions = {
            LearningSignalType.CONTEXT_INSUFFICIENT: [
                "Import statements",
                "Related module definitions",
                "Type definitions",
            ],
            LearningSignalType.API_MISUSE: [
                "API documentation",
                "Function signatures",
                "Usage examples",
            ],
            LearningSignalType.EDGE_CASE_MISSED: [
                "Test edge cases",
                "Boundary conditions",
                "Error handling paths",
            ],
            LearningSignalType.TYPE_CONFUSION: [
                "Type annotations",
                "Class definitions",
                "Interface contracts",
            ],
        }

        for signal in signals:
            if signal in signal_suggestions:
                suggestions.extend(signal_suggestions[signal])

        # Extract missing imports from error
        import_match = re.findall(
            r"No module named ['\"](\w+)['\"]", attempt.test_output
        )
        for module in import_match:
            suggestions.append(f"Module: {module}")

        return list(set(suggestions))[:5]

    def _calculate_confidence(
        self,
        failure_mode: FailureMode,
        signals: list[LearningSignalType],
        patterns: list[str],
    ) -> float:
        """Calculate confidence in the analysis."""
        confidence = 0.5  # Base confidence

        # Clear failure mode increases confidence
        if failure_mode != FailureMode.UNKNOWN:
            confidence += 0.2

        # Having learning signals increases confidence
        if signals and signals[0] != LearningSignalType.NONE:
            confidence += 0.1 * min(len(signals), 3)

        # Having patterns increases confidence
        if patterns:
            confidence += 0.1

        return min(confidence, 1.0)

    def _is_higher_order_candidate(
        self,
        analyses: list[FailureAnalysis],
        avg_delta: float,
    ) -> bool:
        """Determine if this artifact should become a higher-order bug."""
        # Must have enough failed attempts
        if len(analyses) < self.min_attempts:
            return False

        # Must be sufficiently difficult
        if avg_delta < self.difficulty_threshold:
            return False

        # Must have consistent failure patterns (not random)
        failure_modes = [a.failure_mode for a in analyses]
        mode_counts = {}
        for mode in failure_modes:
            mode_counts[mode] = mode_counts.get(mode, 0) + 1

        # If most failures are the same mode, it's a consistent pattern
        max_count = max(mode_counts.values())
        if max_count < len(analyses) * 0.5:
            return False

        # Must have good confidence on average
        avg_confidence = sum(a.confidence for a in analyses) / len(analyses)
        if avg_confidence < self.confidence_threshold:
            return False

        return True

    def _calculate_recommended_difficulty(
        self,
        analyses: list[FailureAnalysis],
        avg_delta: float,
    ) -> int:
        """Calculate recommended difficulty for higher-order bug."""
        # Start with the average difficulty delta
        base = 5 + int(avg_delta)

        # Adjust based on number of attempts
        if len(analyses) >= 3:
            base += 1

        # Adjust based on failure complexity
        semantic_failures = sum(
            1
            for a in analyses
            if a.failure_mode in (FailureMode.SEMANTIC_ERROR, FailureMode.WRONG_FIX)
        )
        if semantic_failures >= len(analyses) * 0.5:
            base += 1

        return min(max(base, 1), 10)

    def _generate_attempt_id(self, artifact_id: str, attempt_number: int) -> str:
        """Generate a unique attempt ID."""
        raw = f"{artifact_id}:{attempt_number}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get_pattern_statistics(self) -> dict[str, int]:
        """Get frequency of error patterns seen."""
        return dict(
            sorted(self._pattern_frequency.items(), key=lambda x: x[1], reverse=True)[
                :20
            ]
        )

    def get_metrics(self) -> dict[str, Any]:
        """Get analyzer metrics."""
        total_analyses = len(self._analysis_cache)
        mode_distribution = {}
        signal_distribution = {}

        for analysis in self._analysis_cache.values():
            mode = analysis.failure_mode.value
            mode_distribution[mode] = mode_distribution.get(mode, 0) + 1

            for signal in analysis.learning_signals:
                sig = signal.value
                signal_distribution[sig] = signal_distribution.get(sig, 0) + 1

        return {
            "total_analyses": total_analyses,
            "failure_mode_distribution": mode_distribution,
            "learning_signal_distribution": signal_distribution,
            "top_error_patterns": self.get_pattern_statistics(),
            "cache_size": len(self._analysis_cache),
        }

    def clear_cache(self) -> None:
        """Clear the analysis cache."""
        self._analysis_cache.clear()
        logger.info("Failure analyzer cache cleared")
