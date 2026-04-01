"""Unit tests for Constitutional AI Phase 4 evaluation models.

Tests model serialization, validation, and target checking.
"""

from datetime import datetime, timezone

import pytest

from src.services.constitutional_ai.evaluation_models import (
    EvaluationDataset,
    EvaluationMetrics,
    ExpectedCritique,
    GoldenSetCase,
    GoldenSetCategory,
    JudgePreference,
    JudgeResult,
    RegressionItem,
    RegressionReport,
    RegressionSeverity,
    ResponsePair,
)
from src.services.constitutional_ai.models import ConstitutionalContext

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_context() -> ConstitutionalContext:
    """Create a sample ConstitutionalContext."""
    return ConstitutionalContext(
        agent_name="TestAgent",
        operation_type="code_generation",
        user_request="Generate a function",
        domain_tags=["security", "testing"],
    )


@pytest.fixture
def sample_response_pair(sample_context) -> ResponsePair:
    """Create a sample ResponsePair."""
    return ResponsePair(
        pair_id="test_pair_001",
        prompt="Write a function to validate user input",
        response_a="def validate(x): return True",
        response_b="def validate(x):\n    if not x:\n        raise ValueError('Empty input')\n    return True",
        context=sample_context,
        applicable_principles=["principle_1_security_first"],
        human_preference="b",
        human_reasoning="Response B has proper input validation",
    )


@pytest.fixture
def sample_judge_result() -> JudgeResult:
    """Create a sample JudgeResult."""
    return JudgeResult(
        pair_id="test_pair_001",
        judge_preference=JudgePreference.RESPONSE_B,
        judge_reasoning="Response B demonstrates better security practices",
        confidence=0.85,
        latency_ms=450.5,
        agrees_with_human=True,
    )


@pytest.fixture
def sample_expected_critique() -> ExpectedCritique:
    """Create a sample ExpectedCritique."""
    return ExpectedCritique(
        principle_id="principle_1_security_first",
        should_flag=True,
        expected_issues=["Missing input validation"],
        severity_if_flagged="high",
    )


@pytest.fixture
def sample_golden_set_case(sample_expected_critique) -> GoldenSetCase:
    """Create a sample GoldenSetCase."""
    return GoldenSetCase(
        case_id="golden_001",
        category=GoldenSetCategory.SECURITY,
        input_prompt="Write a SQL query function",
        agent_output="def query(user_id): return f'SELECT * FROM users WHERE id={user_id}'",
        expected_critiques=[sample_expected_critique],
        expected_revision_needed=True,
        human_verified_at=datetime.now(timezone.utc),
        verifier_id="test_verifier",
    )


# =============================================================================
# Test ResponsePair
# =============================================================================


class TestResponsePair:
    """Tests for ResponsePair model."""

    def test_create_response_pair(self, sample_context):
        """Test creating a ResponsePair with all fields."""
        pair = ResponsePair(
            pair_id="test_001",
            prompt="Test prompt",
            response_a="Response A",
            response_b="Response B",
            context=sample_context,
            applicable_principles=["p1", "p2"],
            human_preference="a",
            human_reasoning="A is better",
        )
        assert pair.pair_id == "test_001"
        assert pair.human_preference == "a"
        assert len(pair.applicable_principles) == 2

    def test_to_dict(self, sample_response_pair):
        """Test ResponsePair.to_dict() serialization."""
        data = sample_response_pair.to_dict()
        assert data["pair_id"] == "test_pair_001"
        assert data["prompt"] == "Write a function to validate user input"
        assert data["human_preference"] == "b"
        assert "context" in data
        assert data["context"]["agent_name"] == "TestAgent"

    def test_from_dict(self, sample_response_pair):
        """Test ResponsePair.from_dict() deserialization."""
        data = sample_response_pair.to_dict()
        restored = ResponsePair.from_dict(data)
        assert restored.pair_id == sample_response_pair.pair_id
        assert restored.prompt == sample_response_pair.prompt
        assert restored.human_preference == sample_response_pair.human_preference
        assert restored.context.agent_name == sample_response_pair.context.agent_name

    def test_from_dict_minimal(self, sample_context):
        """Test ResponsePair.from_dict() with minimal data creates default context."""
        data = {
            "pair_id": "min_001",
            "prompt": "Minimal prompt",
            "response_a": "A",
            "response_b": "B",
        }
        pair = ResponsePair.from_dict(data)
        assert pair.pair_id == "min_001"
        # Context should have default values when not provided
        assert pair.context.agent_name == "unknown"
        assert pair.human_preference is None


# =============================================================================
# Test JudgeResult
# =============================================================================


class TestJudgeResult:
    """Tests for JudgeResult model."""

    def test_create_judge_result(self):
        """Test creating a JudgeResult."""
        result = JudgeResult(
            pair_id="test_001",
            judge_preference=JudgePreference.RESPONSE_A,
            judge_reasoning="Clear reasoning",
            confidence=0.92,
            latency_ms=350.0,
        )
        assert result.pair_id == "test_001"
        assert result.judge_preference == JudgePreference.RESPONSE_A
        assert result.confidence == 0.92

    def test_agrees_with_human_true(self, sample_judge_result):
        """Test agrees_with_human when they match."""
        assert sample_judge_result.agrees_with_human is True

    def test_agrees_with_human_false(self):
        """Test agrees_with_human when they differ."""
        result = JudgeResult(
            pair_id="test_001",
            judge_preference=JudgePreference.RESPONSE_A,
            judge_reasoning="Test reasoning",
            confidence=0.8,
            agrees_with_human=False,
        )
        assert result.agrees_with_human is False

    def test_agrees_with_human_tie(self):
        """Test agrees_with_human with TIE preference."""
        result = JudgeResult(
            pair_id="test_001",
            judge_preference=JudgePreference.TIE,
            judge_reasoning="Both are equal",
            confidence=0.5,
            agrees_with_human=True,
        )
        assert result.agrees_with_human is True

    def test_to_dict(self, sample_judge_result):
        """Test JudgeResult.to_dict() serialization."""
        data = sample_judge_result.to_dict()
        assert data["pair_id"] == "test_pair_001"
        assert data["judge_preference"] == "b"
        assert data["confidence"] == 0.85
        assert data["agrees_with_human"] is True

    def test_from_dict(self, sample_judge_result):
        """Test JudgeResult.from_dict() deserialization."""
        data = sample_judge_result.to_dict()
        restored = JudgeResult.from_dict(data)
        assert restored.pair_id == sample_judge_result.pair_id
        assert restored.judge_preference == sample_judge_result.judge_preference
        assert restored.confidence == sample_judge_result.confidence


# =============================================================================
# Test GoldenSetCase
# =============================================================================


class TestGoldenSetCase:
    """Tests for GoldenSetCase model."""

    def test_create_golden_set_case(self, sample_expected_critique):
        """Test creating a GoldenSetCase."""
        case = GoldenSetCase(
            case_id="test_001",
            category=GoldenSetCategory.COMPLIANCE,
            input_prompt="Test prompt",
            agent_output="Test output",
            expected_critiques=[sample_expected_critique],
            expected_revision_needed=True,
            human_verified_at=datetime.now(timezone.utc),
            verifier_id="test_verifier",
        )
        assert case.case_id == "test_001"
        assert case.category == GoldenSetCategory.COMPLIANCE
        assert len(case.expected_critiques) == 1

    def test_to_dict(self, sample_golden_set_case):
        """Test GoldenSetCase.to_dict() serialization."""
        data = sample_golden_set_case.to_dict()
        assert data["case_id"] == "golden_001"
        assert data["category"] == "security"
        assert len(data["expected_critiques"]) == 1
        assert data["expected_revision_needed"] is True

    def test_from_dict(self, sample_golden_set_case):
        """Test GoldenSetCase.from_dict() deserialization."""
        data = sample_golden_set_case.to_dict()
        restored = GoldenSetCase.from_dict(data)
        assert restored.case_id == sample_golden_set_case.case_id
        assert restored.category == sample_golden_set_case.category
        assert len(restored.expected_critiques) == 1


# =============================================================================
# Test RegressionReport
# =============================================================================


class TestRegressionReport:
    """Tests for RegressionReport model."""

    def test_create_empty_regression_report(self):
        """Test creating an empty regression report."""
        report = RegressionReport(
            run_id="report_001",
            total_cases=100,
            passed_cases=100,
            failed_cases=0,
            regressions=[],
            pass_rate=1.0,
        )
        assert report.pass_rate == 1.0
        assert report.critical_regressions == 0
        assert report.has_critical_regressions is False

    def test_pass_rate_calculation(self):
        """Test pass rate calculation."""
        report = RegressionReport(
            run_id="report_001",
            total_cases=100,
            passed_cases=85,
            failed_cases=15,
            regressions=[],
            pass_rate=0.85,
        )
        assert report.pass_rate == 0.85

    def test_critical_regression_count(self):
        """Test critical regression counting."""
        regressions = [
            RegressionItem(
                case_id="case_001",
                principle_id="p1",
                regression_type="false_negative",
                expected="issue",
                actual="no_issue",
                severity=RegressionSeverity.CRITICAL,
            ),
            RegressionItem(
                case_id="case_002",
                principle_id="p2",
                regression_type="severity_change",
                expected="critical",
                actual="high",
                severity=RegressionSeverity.HIGH,
            ),
            RegressionItem(
                case_id="case_003",
                principle_id="p3",
                regression_type="false_negative",
                expected="issue",
                actual="no_issue",
                severity=RegressionSeverity.CRITICAL,
            ),
        ]
        report = RegressionReport(
            run_id="report_001",
            total_cases=50,
            passed_cases=47,
            failed_cases=3,
            regressions=regressions,
            pass_rate=0.94,
        )
        assert report.critical_regressions == 2
        assert report.has_critical_regressions is True

    def test_to_dict(self):
        """Test RegressionReport.to_dict() serialization."""
        report = RegressionReport(
            run_id="report_001",
            total_cases=50,
            passed_cases=45,
            failed_cases=5,
            regressions=[],
            pass_rate=0.9,
        )
        data = report.to_dict()
        assert data["run_id"] == "report_001"
        assert data["pass_rate"] == 0.9
        assert "run_timestamp" in data


# =============================================================================
# Test EvaluationMetrics
# =============================================================================


class TestEvaluationMetrics:
    """Tests for EvaluationMetrics model."""

    def test_create_evaluation_metrics(self):
        """Test creating EvaluationMetrics."""
        metrics = EvaluationMetrics(
            critique_accuracy=0.92,
            revision_convergence_rate=0.96,
            cache_hit_rate=0.35,
            non_evasive_rate=0.75,
            golden_set_pass_rate=0.95,
            critique_latency_p95_ms=450.0,
            evaluation_pairs_processed=100,
            critique_count=500,
        )
        assert metrics.critique_accuracy == 0.92
        assert metrics.revision_convergence_rate == 0.96

    def test_meets_targets_all_passing(self):
        """Test meets_targets when all targets are met."""
        metrics = EvaluationMetrics(
            critique_accuracy=0.92,  # >0.90
            revision_convergence_rate=0.96,  # >0.95
            cache_hit_rate=0.35,  # >0.30
            non_evasive_rate=0.75,  # >0.70
            golden_set_pass_rate=0.95,
            critique_latency_p95_ms=450.0,  # <500ms
        )
        targets = metrics.meets_targets()
        assert targets["critique_accuracy"] is True
        assert targets["revision_convergence_rate"] is True
        assert targets["cache_hit_rate"] is True
        assert targets["non_evasive_rate"] is True
        assert targets["critique_latency_p95"] is True

    def test_meets_targets_some_failing(self):
        """Test meets_targets when some targets are not met."""
        metrics = EvaluationMetrics(
            critique_accuracy=0.85,  # <0.90 FAIL
            revision_convergence_rate=0.96,  # >0.95
            cache_hit_rate=0.25,  # <0.30 FAIL
            non_evasive_rate=0.65,  # <0.70 FAIL
            golden_set_pass_rate=0.95,
            critique_latency_p95_ms=600.0,  # >500ms FAIL
        )
        targets = metrics.meets_targets()
        assert targets["critique_accuracy"] is False
        assert targets["revision_convergence_rate"] is True
        assert targets["cache_hit_rate"] is False
        assert targets["non_evasive_rate"] is False
        assert targets["critique_latency_p95"] is False

    def test_to_dict(self):
        """Test EvaluationMetrics.to_dict() serialization."""
        metrics = EvaluationMetrics(
            critique_accuracy=0.92,
            revision_convergence_rate=0.96,
            cache_hit_rate=0.35,
            non_evasive_rate=0.75,
            golden_set_pass_rate=0.95,
            critique_latency_p95_ms=450.0,
            evaluation_pairs_processed=100,
        )
        data = metrics.to_dict()
        assert data["critique_accuracy"] == 0.92
        assert data["revision_convergence_rate"] == 0.96
        assert data["cache_hit_rate"] == 0.35
        assert data["non_evasive_rate"] == 0.75
        assert data["evaluation_pairs_processed"] == 100
        assert "run_timestamp" in data


# =============================================================================
# Test EvaluationDataset
# =============================================================================


class TestEvaluationDataset:
    """Tests for EvaluationDataset model."""

    def test_create_evaluation_dataset(self, sample_response_pair):
        """Test creating an EvaluationDataset."""
        dataset = EvaluationDataset(
            dataset_id="dataset_001",
            version="1.0.0",
            name="Test Dataset",
            description="Test dataset for unit tests",
            response_pairs=[sample_response_pair],
        )
        assert dataset.dataset_id == "dataset_001"
        assert len(dataset.response_pairs) == 1

    def test_to_dict(self, sample_response_pair):
        """Test EvaluationDataset.to_dict() serialization."""
        dataset = EvaluationDataset(
            dataset_id="dataset_001",
            version="1.0.0",
            name="Test Dataset",
            description="Test dataset for unit tests",
            response_pairs=[sample_response_pair],
        )
        data = dataset.to_dict()
        assert data["dataset_id"] == "dataset_001"
        assert data["description"] == "Test dataset for unit tests"
        assert len(data["response_pairs"]) == 1

    def test_from_dict(self, sample_response_pair):
        """Test EvaluationDataset.from_dict() deserialization."""
        data = {
            "dataset_id": "dataset_001",
            "version": "1.0.0",
            "name": "Test Dataset",
            "response_pairs": [sample_response_pair.to_dict()],
        }
        dataset = EvaluationDataset.from_dict(data)
        assert dataset.dataset_id == "dataset_001"
        assert len(dataset.response_pairs) == 1


# =============================================================================
# Test Enums
# =============================================================================


class TestJudgePreference:
    """Tests for JudgePreference enum."""

    def test_from_string_response_a(self):
        """Test parsing 'a' to RESPONSE_A."""
        assert JudgePreference.from_string("a") == JudgePreference.RESPONSE_A
        assert JudgePreference.from_string("A") == JudgePreference.RESPONSE_A

    def test_from_string_response_b(self):
        """Test parsing 'b' to RESPONSE_B."""
        assert JudgePreference.from_string("b") == JudgePreference.RESPONSE_B
        assert JudgePreference.from_string("B") == JudgePreference.RESPONSE_B

    def test_from_string_tie(self):
        """Test parsing 'tie' to TIE."""
        assert JudgePreference.from_string("tie") == JudgePreference.TIE
        assert JudgePreference.from_string("TIE") == JudgePreference.TIE

    def test_from_string_unknown(self):
        """Test parsing unknown string to INVALID."""
        assert JudgePreference.from_string("x") == JudgePreference.INVALID
        assert JudgePreference.from_string("") == JudgePreference.INVALID


class TestGoldenSetCategory:
    """Tests for GoldenSetCategory enum."""

    def test_from_string_categories(self):
        """Test parsing category strings."""
        assert GoldenSetCategory.from_string("security") == GoldenSetCategory.SECURITY
        assert (
            GoldenSetCategory.from_string("compliance") == GoldenSetCategory.COMPLIANCE
        )
        assert (
            GoldenSetCategory.from_string("helpfulness")
            == GoldenSetCategory.HELPFULNESS
        )

    def test_from_string_unknown_raises(self):
        """Test parsing unknown category string raises ValueError."""
        with pytest.raises(ValueError):
            GoldenSetCategory.from_string("unknown")


class TestRegressionSeverity:
    """Tests for RegressionSeverity enum."""

    def test_values(self):
        """Test severity values."""
        assert RegressionSeverity.CRITICAL.value == "critical"
        assert RegressionSeverity.HIGH.value == "high"
        assert RegressionSeverity.MEDIUM.value == "medium"
        assert RegressionSeverity.LOW.value == "low"
