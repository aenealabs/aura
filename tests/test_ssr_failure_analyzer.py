"""
Tests for SSR Failure Analyzer.

Tests the failure mode categorization, learning signal extraction,
and failure summarization for higher-order training.
"""

import platform
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from src.services.ssr.failure_analyzer import (
    FailureAnalysis,
    FailureAnalyzer,
    FailureMode,
    FailureSummary,
    LearningSignalType,
)

# Run tests in forked processes for isolation
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


# Mock dataclasses to match the expected types
@dataclass
class MockSolveAttempt:
    """Mock solve attempt for testing."""

    attempt_number: int
    patch_diff: str
    test_output: str
    context_files: list = None
    reasoning: str = ""
    duration_seconds: float = 30.0
    tokens_used: int = 1000

    def __post_init__(self):
        if self.context_files is None:
            self.context_files = []


@dataclass
class MockSolveResult:
    """Mock solve result for testing."""

    artifact_id: str
    success: bool
    attempts: list = None

    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []


class TestFailureModeEnum:
    """Tests for FailureMode enum."""

    def test_all_failure_modes_defined(self):
        """Verify all expected failure modes exist."""
        expected = {
            "timeout",
            "wrong_fix",
            "partial_fix",
            "syntax_error",
            "test_regression",
            "no_patch",
            "invalid_patch",
            "semantic_error",
            "resource_limit",
            "unknown",
        }
        actual = {m.value for m in FailureMode}
        assert expected == actual

    def test_failure_mode_values(self):
        """Test specific failure mode values."""
        assert FailureMode.TIMEOUT.value == "timeout"
        assert FailureMode.WRONG_FIX.value == "wrong_fix"
        assert FailureMode.SYNTAX_ERROR.value == "syntax_error"


class TestLearningSignalTypeEnum:
    """Tests for LearningSignalType enum."""

    def test_all_learning_signals_defined(self):
        """Verify all expected learning signal types exist."""
        expected = {
            "complexity_underestimate",
            "context_insufficient",
            "pattern_mismatch",
            "edge_case_missed",
            "type_confusion",
            "logic_error",
            "api_misuse",
            "scope_error",
            "none",
        }
        actual = {s.value for s in LearningSignalType}
        assert expected == actual


class TestFailureAnalysis:
    """Tests for FailureAnalysis dataclass."""

    def test_failure_analysis_creation(self):
        """Test creating a failure analysis."""
        now = datetime.now(timezone.utc)
        analysis = FailureAnalysis(
            attempt_id="attempt-123",
            artifact_id="artifact-456",
            failure_mode=FailureMode.TIMEOUT,
            learning_signals=[LearningSignalType.COMPLEXITY_UNDERESTIMATE],
            difficulty_delta=3,
            confidence=0.85,
            error_patterns=["timeout pattern"],
            suggested_context=["file.py"],
            raw_error="Execution timed out",
            analyzed_at=now,
        )
        assert analysis.attempt_id == "attempt-123"
        assert analysis.failure_mode == FailureMode.TIMEOUT
        assert analysis.difficulty_delta == 3
        assert len(analysis.learning_signals) == 1

    def test_failure_analysis_to_dict(self):
        """Test serialization of failure analysis."""
        analysis = FailureAnalysis(
            attempt_id="a1",
            artifact_id="art1",
            failure_mode=FailureMode.SYNTAX_ERROR,
            learning_signals=[LearningSignalType.PATTERN_MISMATCH],
            difficulty_delta=2,
            confidence=0.75,
            error_patterns=["SyntaxError"],
            suggested_context=[],
            raw_error="Invalid syntax",
        )
        result = analysis.to_dict()
        assert result["attempt_id"] == "a1"
        assert result["failure_mode"] == "syntax_error"
        assert "pattern_mismatch" in result["learning_signals"]

    def test_failure_analysis_from_dict(self):
        """Test deserialization of failure analysis."""
        data = {
            "attempt_id": "a1",
            "artifact_id": "art1",
            "failure_mode": "timeout",
            "learning_signals": ["complexity_underestimate"],
            "difficulty_delta": 5,
            "confidence": 0.9,
            "error_patterns": [],
            "suggested_context": [],
            "raw_error": "",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
        analysis = FailureAnalysis.from_dict(data)
        assert analysis.attempt_id == "a1"
        assert analysis.failure_mode == FailureMode.TIMEOUT
        assert analysis.difficulty_delta == 5


class TestFailureSummary:
    """Tests for FailureSummary dataclass."""

    def test_failure_summary_creation(self):
        """Test creating a failure summary."""
        summary = FailureSummary(
            artifact_id="art-123",
            total_attempts=5,
            failure_modes={FailureMode.TIMEOUT: 3, FailureMode.WRONG_FIX: 2},
            learning_signals={LearningSignalType.COMPLEXITY_UNDERESTIMATE: 3},
            avg_difficulty_delta=2.5,
            is_higher_order_candidate=True,
            recommended_difficulty=8,
        )
        assert summary.total_attempts == 5
        assert summary.is_higher_order_candidate is True
        assert summary.recommended_difficulty == 8

    def test_failure_summary_to_dict(self):
        """Test serialization of failure summary."""
        summary = FailureSummary(
            artifact_id="art-123",
            total_attempts=3,
            failure_modes={FailureMode.SYNTAX_ERROR: 3},
            learning_signals={},
            avg_difficulty_delta=1.0,
            is_higher_order_candidate=False,
            recommended_difficulty=5,
        )
        data = summary.to_dict()
        assert data["artifact_id"] == "art-123"
        assert "syntax_error" in data["failure_modes"]


class TestFailureAnalyzer:
    """Tests for FailureAnalyzer service."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_analyzer_initialization(self, analyzer):
        """Test analyzer initialization."""
        assert analyzer.min_attempts == 2
        assert analyzer.difficulty_threshold == 3

    def test_custom_thresholds(self):
        """Test analyzer with custom thresholds."""
        analyzer = FailureAnalyzer(
            min_attempts_for_higher_order=3,
            difficulty_threshold=5,
            confidence_threshold=0.8,
        )
        assert analyzer.min_attempts == 3
        assert analyzer.difficulty_threshold == 5
        assert analyzer.confidence_threshold == 0.8

    def test_summarize_multiple_failures(self, analyzer):
        """Test summarizing multiple failure analyses."""
        analyses = [
            FailureAnalysis(
                attempt_id=f"a{i}",
                artifact_id="art-123",
                failure_mode=FailureMode.TIMEOUT if i < 2 else FailureMode.PARTIAL_FIX,
                learning_signals=[LearningSignalType.COMPLEXITY_UNDERESTIMATE],
                difficulty_delta=2,
                confidence=0.8,
                error_patterns=[],
                suggested_context=[],
                raw_error="error",
            )
            for i in range(3)
        ]

        summary = analyzer.summarize_failures("art-123", analyses)
        assert summary.artifact_id == "art-123"
        assert summary.total_attempts == 3
        assert summary.failure_modes[FailureMode.TIMEOUT] == 2
        assert summary.failure_modes[FailureMode.PARTIAL_FIX] == 1

    def test_summarize_empty_analyses(self, analyzer):
        """Test summarizing empty analyses list."""
        summary = analyzer.summarize_failures("art-123", [])
        assert summary.total_attempts == 0
        assert summary.is_higher_order_candidate is False

    def test_higher_order_candidate_detection(self, analyzer):
        """Test detection of higher-order candidates."""
        analyses = [
            FailureAnalysis(
                attempt_id=f"a{i}",
                artifact_id="art-123",
                failure_mode=FailureMode.PARTIAL_FIX,
                learning_signals=[LearningSignalType.EDGE_CASE_MISSED],
                difficulty_delta=4,  # Above threshold
                confidence=0.85,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
            for i in range(3)  # 3 attempts >= min_attempts
        ]
        summary = analyzer.summarize_failures("art-123", analyses)
        assert summary.is_higher_order_candidate is True

    def test_not_higher_order_when_below_threshold(self, analyzer):
        """Test that low difficulty delta doesn't qualify."""
        analyses = [
            FailureAnalysis(
                attempt_id="a1",
                artifact_id="art-123",
                failure_mode=FailureMode.SYNTAX_ERROR,
                learning_signals=[],
                difficulty_delta=1,  # Below threshold
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
        ]
        summary = analyzer.summarize_failures("art-123", analyses)
        # Only 1 attempt, should not be candidate
        assert summary.is_higher_order_candidate is False


class TestFailureAnalyzerAnalyzeAttempt:
    """Tests for analyze_attempt method."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_analyze_timeout_failure(self, analyzer):
        """Test analysis of a timeout failure."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="Error: execution timed out after 60 seconds",
        )
        result = MockSolveResult(artifact_id="artifact-timeout", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.TIMEOUT
        assert LearningSignalType.COMPLEXITY_UNDERESTIMATE in analysis.learning_signals

    def test_analyze_no_patch_failure(self, analyzer):
        """Test analysis of no patch generated failure."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="",
            test_output="No changes generated",
        )
        result = MockSolveResult(artifact_id="artifact-nopatch", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.NO_PATCH

    def test_analyze_syntax_error_failure(self, analyzer):
        """Test analysis of syntax error failure."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="SyntaxError: invalid syntax at line 10",
        )
        result = MockSolveResult(artifact_id="artifact-syntax", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.SYNTAX_ERROR

    def test_analyze_invalid_patch_failure(self, analyzer):
        """Test analysis of invalid patch failure."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\nsome invalid patch",
            test_output="error: patch failed: hunk FAILED at line 5",
        )
        result = MockSolveResult(artifact_id="artifact-patch", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.INVALID_PATCH

    def test_analyze_partial_fix_failure(self, analyzer):
        """Test analysis of partial fix failure."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="3 passed, 2 failed in 5 seconds",
        )
        result = MockSolveResult(artifact_id="artifact-partial", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.PARTIAL_FIX
        assert LearningSignalType.EDGE_CASE_MISSED in analysis.learning_signals

    def test_analyze_test_regression_failure(self, analyzer):
        """Test analysis of test regression failure."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="test_other previously passed, now failed",
        )
        result = MockSolveResult(artifact_id="artifact-regression", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.TEST_REGRESSION

    def test_analyze_semantic_error_failure(self, analyzer):
        """Test analysis of semantic (type) error failure."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="TypeError: expected str, got int",
        )
        result = MockSolveResult(artifact_id="artifact-semantic", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.SEMANTIC_ERROR
        assert LearningSignalType.TYPE_CONFUSION in analysis.learning_signals

    def test_analyze_wrong_fix_failure(self, analyzer):
        """Test analysis of wrong fix failure (assertion without expected/got pattern)."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="AssertionError: condition was false",
        )
        result = MockSolveResult(artifact_id="artifact-wrong", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.WRONG_FIX
        assert LearningSignalType.LOGIC_ERROR in analysis.learning_signals

    def test_analyze_resource_limit_failure(self, analyzer):
        """Test analysis of resource limit failure."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="Process killed: out of memory (OOM)",
        )
        result = MockSolveResult(artifact_id="artifact-oom", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.RESOURCE_LIMIT

    def test_analyze_unknown_failure(self, analyzer):
        """Test analysis of unknown failure mode."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new",
            test_output="Some strange error occurred",
        )
        result = MockSolveResult(artifact_id="artifact-unknown", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.failure_mode == FailureMode.UNKNOWN

    def test_analyze_caches_result(self, analyzer):
        """Test that analysis results are cached."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="timed out",
        )
        result = MockSolveResult(artifact_id="artifact-cache", success=False)

        analysis1 = analyzer.analyze_attempt(result, attempt)
        analysis2 = analyzer.analyze_attempt(result, attempt)

        assert analysis1 is analysis2  # Same cached object


class TestLearningSignalExtraction:
    """Tests for learning signal extraction."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_extract_context_insufficient(self, analyzer):
        """Test extraction of context insufficient signal."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch content",
            test_output="ImportError: missing module 'utils'",  # Matches 'missing' and 'import' patterns
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert LearningSignalType.CONTEXT_INSUFFICIENT in analysis.learning_signals

    def test_extract_api_misuse(self, analyzer):
        """Test extraction of API misuse signal."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch content",
            test_output="AttributeError: 'list' object has no attribute 'push'",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert LearningSignalType.API_MISUSE in analysis.learning_signals

    def test_extract_scope_error(self, analyzer):
        """Test extraction of scope error signal."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch content",
            test_output="NameError: name 'undefined_variable' is not defined",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert LearningSignalType.SCOPE_ERROR in analysis.learning_signals

    def test_extract_pattern_mismatch(self, analyzer):
        """Test extraction of pattern mismatch from reasoning."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch content",
            test_output="error",
            reasoning="I thought this would work because I expected the input to be a string",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert LearningSignalType.PATTERN_MISMATCH in analysis.learning_signals


class TestDifficultyDeltaCalculation:
    """Tests for difficulty delta calculation."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_difficulty_delta_for_timeout(self, analyzer):
        """Test difficulty delta for timeout failures."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch content",
            test_output="execution timed out",
            duration_seconds=30,
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt, original_difficulty=5)

        assert analysis.difficulty_delta == 3  # TIMEOUT delta

    def test_difficulty_delta_increases_with_attempts(self, analyzer):
        """Test difficulty delta increases with attempt number."""
        attempt1 = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch content",
            test_output="AssertionError",
            duration_seconds=30,
        )
        attempt3 = MockSolveAttempt(
            attempt_number=3,
            patch_diff="patch content",
            test_output="AssertionError",
            duration_seconds=30,
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis1 = analyzer.analyze_attempt(result, attempt1)
        analyzer.clear_cache()
        analysis3 = analyzer.analyze_attempt(result, attempt3)

        assert analysis3.difficulty_delta > analysis1.difficulty_delta

    def test_difficulty_delta_for_long_duration(self, analyzer):
        """Test difficulty delta increases for long-running attempts."""
        short_attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch content",
            test_output="AssertionError",
            duration_seconds=30,
        )
        long_attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch content",
            test_output="AssertionError",
            duration_seconds=120,  # > 60 seconds
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis_short = analyzer.analyze_attempt(result, short_attempt)
        analyzer.clear_cache()
        analysis_long = analyzer.analyze_attempt(result, long_attempt)

        assert analysis_long.difficulty_delta > analysis_short.difficulty_delta

    def test_difficulty_delta_capped_at_five(self, analyzer):
        """Test that difficulty delta is capped at 5."""
        attempt = MockSolveAttempt(
            attempt_number=10,  # High attempt number
            patch_diff="",  # No patch
            test_output="execution timed out",  # Timeout
            duration_seconds=120,  # Long duration
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert analysis.difficulty_delta <= 5


class TestErrorPatternExtraction:
    """Tests for error pattern extraction."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_extract_exception_types(self, analyzer):
        """Test extraction of exception types."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="ValueError: invalid literal\nTypeError: unexpected type",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert "ValueError" in analysis.error_patterns
        assert "TypeError" in analysis.error_patterns

    def test_extract_assertion_messages(self, analyzer):
        """Test extraction of assertion messages."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="assert value == expected: The actual value 5 was not equal to 10",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert any("assertion:" in p for p in analysis.error_patterns)

    def test_extract_function_names(self, analyzer):
        """Test extraction of function names from stack traces."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="Traceback:\n  in test_something\n  in calculate_value\n  in process_data\n",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        # Should have extracted function names
        func_patterns = [
            p for p in analysis.error_patterns if p.startswith("function:")
        ]
        assert len(func_patterns) > 0


class TestContextSuggestion:
    """Tests for context suggestion."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_suggest_context_for_import_error(self, analyzer):
        """Test context suggestion for import errors."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="ModuleNotFoundError: No module named 'custom_utils'",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert any("custom_utils" in ctx for ctx in analysis.suggested_context)

    def test_suggest_context_for_api_misuse(self, analyzer):
        """Test context suggestion for API misuse."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="AttributeError: method not found",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis = analyzer.analyze_attempt(result, attempt)

        assert any(
            "API" in ctx or "documentation" in ctx for ctx in analysis.suggested_context
        )


class TestConfidenceCalculation:
    """Tests for confidence calculation."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_confidence_increases_with_clear_mode(self, analyzer):
        """Test that known failure modes increase confidence."""
        clear_attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="SyntaxError: invalid syntax",
        )
        unknown_attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="something happened",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analysis_clear = analyzer.analyze_attempt(result, clear_attempt)
        analyzer.clear_cache()
        analysis_unknown = analyzer.analyze_attempt(result, unknown_attempt)

        assert analysis_clear.confidence > analysis_unknown.confidence


class TestHigherOrderCandidate:
    """Tests for higher-order candidate detection."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer(
            min_attempts_for_higher_order=2,
            difficulty_threshold=3,
            confidence_threshold=0.6,
        )

    def test_not_candidate_insufficient_attempts(self, analyzer):
        """Test that single attempt is not a candidate."""
        analyses = [
            FailureAnalysis(
                attempt_id="a1",
                artifact_id="art",
                failure_mode=FailureMode.TIMEOUT,
                learning_signals=[],
                difficulty_delta=5,
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
        ]
        summary = analyzer.summarize_failures("art", analyses)
        assert summary.is_higher_order_candidate is False

    def test_not_candidate_low_difficulty(self, analyzer):
        """Test that low difficulty is not a candidate."""
        analyses = [
            FailureAnalysis(
                attempt_id=f"a{i}",
                artifact_id="art",
                failure_mode=FailureMode.TIMEOUT,
                learning_signals=[],
                difficulty_delta=1,  # Low delta
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
            for i in range(3)
        ]
        summary = analyzer.summarize_failures("art", analyses)
        assert summary.is_higher_order_candidate is False

    def test_not_candidate_inconsistent_failures(self, analyzer):
        """Test that inconsistent failure patterns are not candidates.

        With 3 different failure modes, no mode has > 50% of attempts,
        so max_count (1) < len(analyses) * 0.5 (1.5) returns False.
        """
        analyses = [
            FailureAnalysis(
                attempt_id="a1",
                artifact_id="art",
                failure_mode=FailureMode.TIMEOUT,
                learning_signals=[],
                difficulty_delta=4,
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            ),
            FailureAnalysis(
                attempt_id="a2",
                artifact_id="art",
                failure_mode=FailureMode.SYNTAX_ERROR,  # Different mode
                learning_signals=[],
                difficulty_delta=4,
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            ),
            FailureAnalysis(
                attempt_id="a3",
                artifact_id="art",
                failure_mode=FailureMode.PARTIAL_FIX,  # Third different mode
                learning_signals=[],
                difficulty_delta=4,
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            ),
        ]
        summary = analyzer.summarize_failures("art", analyses)
        assert summary.is_higher_order_candidate is False

    def test_not_candidate_low_confidence(self, analyzer):
        """Test that low confidence analyses are not candidates."""
        analyses = [
            FailureAnalysis(
                attempt_id=f"a{i}",
                artifact_id="art",
                failure_mode=FailureMode.TIMEOUT,
                learning_signals=[],
                difficulty_delta=4,
                confidence=0.3,  # Low confidence
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
            for i in range(3)
        ]
        summary = analyzer.summarize_failures("art", analyses)
        assert summary.is_higher_order_candidate is False


class TestRecommendedDifficulty:
    """Tests for recommended difficulty calculation."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_base_difficulty_from_delta(self, analyzer):
        """Test that base difficulty is derived from delta."""
        analyses = [
            FailureAnalysis(
                attempt_id="a1",
                artifact_id="art",
                failure_mode=FailureMode.TIMEOUT,
                learning_signals=[],
                difficulty_delta=3,
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
        ]
        summary = analyzer.summarize_failures("art", analyses)
        assert summary.recommended_difficulty == 8  # 5 + 3

    def test_difficulty_increases_with_many_attempts(self, analyzer):
        """Test that many attempts increase difficulty."""
        analyses = [
            FailureAnalysis(
                attempt_id=f"a{i}",
                artifact_id="art",
                failure_mode=FailureMode.TIMEOUT,
                learning_signals=[],
                difficulty_delta=2,
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
            for i in range(5)  # >= 3 attempts
        ]
        summary = analyzer.summarize_failures("art", analyses)
        assert summary.recommended_difficulty >= 8  # 5 + 2 + 1 for many attempts

    def test_difficulty_increases_for_semantic_failures(self, analyzer):
        """Test that semantic errors increase difficulty."""
        analyses = [
            FailureAnalysis(
                attempt_id=f"a{i}",
                artifact_id="art",
                failure_mode=FailureMode.SEMANTIC_ERROR,
                learning_signals=[],
                difficulty_delta=2,
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
            for i in range(4)  # All semantic errors
        ]
        summary = analyzer.summarize_failures("art", analyses)
        # Should be higher due to semantic failures
        assert summary.recommended_difficulty >= 8

    def test_difficulty_capped_at_ten(self, analyzer):
        """Test that difficulty is capped at 10."""
        analyses = [
            FailureAnalysis(
                attempt_id=f"a{i}",
                artifact_id="art",
                failure_mode=FailureMode.SEMANTIC_ERROR,
                learning_signals=[],
                difficulty_delta=10,  # Very high delta
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
            for i in range(10)
        ]
        summary = analyzer.summarize_failures("art", analyses)
        assert summary.recommended_difficulty <= 10

    def test_difficulty_minimum_is_one(self, analyzer):
        """Test that difficulty is at least 1."""
        analyses = [
            FailureAnalysis(
                attempt_id="a1",
                artifact_id="art",
                failure_mode=FailureMode.SYNTAX_ERROR,
                learning_signals=[],
                difficulty_delta=-5,  # Negative delta
                confidence=0.9,
                error_patterns=[],
                suggested_context=[],
                raw_error="",
            )
        ]
        summary = analyzer.summarize_failures("art", analyses)
        assert summary.recommended_difficulty >= 1


class TestAnalyzerMetricsAndStatistics:
    """Tests for analyzer metrics and statistics."""

    @pytest.fixture
    def analyzer(self):
        """Create a FailureAnalyzer instance."""
        return FailureAnalyzer()

    def test_get_pattern_statistics(self, analyzer):
        """Test getting pattern statistics."""
        # Analyze some attempts to populate patterns
        attempt1 = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="ValueError: test error\nValueError: another error",
        )
        attempt2 = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="TypeError: type mismatch",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analyzer.analyze_attempt(result, attempt1)
        result.artifact_id = "art2"  # Different artifact to avoid cache hit
        analyzer.analyze_attempt(result, attempt2)

        stats = analyzer.get_pattern_statistics()
        assert isinstance(stats, dict)

    def test_get_metrics(self, analyzer):
        """Test getting analyzer metrics."""
        # Analyze an attempt
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="SyntaxError: invalid syntax",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analyzer.analyze_attempt(result, attempt)

        metrics = analyzer.get_metrics()
        assert "total_analyses" in metrics
        assert "failure_mode_distribution" in metrics
        assert "learning_signal_distribution" in metrics
        assert "top_error_patterns" in metrics
        assert "cache_size" in metrics
        assert metrics["total_analyses"] == 1
        assert metrics["cache_size"] == 1

    def test_clear_cache(self, analyzer):
        """Test clearing analyzer cache."""
        attempt = MockSolveAttempt(
            attempt_number=1,
            patch_diff="patch",
            test_output="error",
        )
        result = MockSolveResult(artifact_id="art", success=False)

        analyzer.analyze_attempt(result, attempt)
        assert analyzer.get_metrics()["cache_size"] == 1

        analyzer.clear_cache()
        assert analyzer.get_metrics()["cache_size"] == 0
