"""
Tests for alternatives analyzer.
"""

import pytest

from src.services.explainability.alternatives import (
    AlternativesAnalyzer,
    configure_alternatives_analyzer,
    get_alternatives_analyzer,
    reset_alternatives_analyzer,
)
from src.services.explainability.config import AlternativesConfig


class TestAlternativesAnalyzer:
    """Tests for AlternativesAnalyzer class."""

    def setup_method(self):
        """Reset analyzer before each test."""
        reset_alternatives_analyzer()

    def teardown_method(self):
        """Reset analyzer after each test."""
        reset_alternatives_analyzer()

    def test_init_without_bedrock(self):
        """Test initialization without Bedrock client."""
        analyzer = AlternativesAnalyzer()
        assert analyzer.bedrock is None
        assert analyzer.config is not None

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = AlternativesConfig(max_alternatives=10)
        analyzer = AlternativesAnalyzer(config=config)
        assert analyzer.config.max_alternatives == 10

    @pytest.mark.asyncio
    async def test_analyze_basic(self, sample_decision_input, sample_decision_output):
        """Test basic alternatives analysis."""
        analyzer = AlternativesAnalyzer()
        report = await analyzer.analyze(
            decision_id="dec_test",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_alternatives=2,
        )

        assert report.decision_id == "dec_test"
        assert len(report.alternatives) >= 2
        # Should have a chosen alternative
        assert report.get_chosen() is not None

    @pytest.mark.asyncio
    async def test_analyze_respects_min_alternatives(
        self, sample_decision_input, sample_decision_output
    ):
        """Test that analyzer respects minimum alternatives."""
        analyzer = AlternativesAnalyzer()

        report = await analyzer.analyze(
            decision_id="dec_test",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_alternatives=4,
        )

        assert len(report.alternatives) >= 4

    def test_analyze_sync_basic(self, sample_decision_input, sample_decision_output):
        """Test synchronous alternatives analysis."""
        analyzer = AlternativesAnalyzer()
        report = analyzer.analyze_sync(
            decision_id="dec_test",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_alternatives=2,
        )

        assert report.decision_id == "dec_test"
        assert len(report.alternatives) >= 2

    def test_analyze_sync_with_context(
        self, sample_decision_input, sample_decision_output
    ):
        """Test synchronous analysis with context."""
        analyzer = AlternativesAnalyzer()
        report = analyzer.analyze_sync(
            decision_id="dec_test",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_alternatives=2,
        )

        assert report.decision_id == "dec_test"

    def test_get_comparison_criteria_security(self):
        """Test comparison criteria for security decisions."""
        analyzer = AlternativesAnalyzer()
        decision_input = {"task": "security_review"}
        decision_output = {"action": "flag_vulnerability"}

        criteria = analyzer._get_comparison_criteria(decision_input, decision_output)
        assert "Security impact" in criteria

    def test_get_comparison_criteria_performance(self):
        """Test comparison criteria for performance decisions."""
        analyzer = AlternativesAnalyzer()
        decision_input = {"task": "performance_optimization"}
        decision_output = {"recommendation": "cache_results"}

        criteria = analyzer._get_comparison_criteria(decision_input, decision_output)
        assert "Performance impact" in criteria

    def test_get_comparison_criteria_code(self):
        """Test comparison criteria for code decisions."""
        analyzer = AlternativesAnalyzer()
        decision_input = {"task": "refactor"}
        decision_output = {"code_changes": {"old": "x", "new": "y"}}

        criteria = analyzer._get_comparison_criteria(decision_input, decision_output)
        assert "Code quality" in criteria or "Maintainability" in criteria

    def test_get_comparison_criteria_default(self):
        """Test default comparison criteria."""
        analyzer = AlternativesAnalyzer()
        decision_input = {"task": "generic"}
        decision_output = {"result": "done"}

        criteria = analyzer._get_comparison_criteria(decision_input, decision_output)
        assert len(criteria) > 0
        assert "Effectiveness" in criteria or "Complexity" in criteria

    def test_discover_alternatives_heuristic_code_change(self):
        """Test heuristic discovery for code change decisions."""
        analyzer = AlternativesAnalyzer()
        decision_input = {"task": "fix_bug", "file": "app.py"}
        decision_output = {"code_changes": {"old": "x = 1", "new": "x = 2"}}

        alternatives = analyzer._discover_alternatives_heuristic(
            decision_input, decision_output, min_alternatives=3
        )

        assert len(alternatives) >= 3
        # Should have one chosen alternative
        chosen = [a for a in alternatives if a.get("was_chosen", False)]
        assert len(chosen) == 1

    def test_discover_alternatives_heuristic_security(self):
        """Test heuristic discovery for security decisions."""
        analyzer = AlternativesAnalyzer()
        decision_input = {"task": "security_review", "code": "eval(input)"}
        decision_output = {"action": "flag_vulnerability", "severity": "critical"}

        alternatives = analyzer._discover_alternatives_heuristic(
            decision_input, decision_output, min_alternatives=2
        )

        assert len(alternatives) >= 2

    def test_discover_alternatives_heuristic_generic(self):
        """Test heuristic discovery for generic decisions."""
        analyzer = AlternativesAnalyzer()
        decision_input = {"task": "analyze"}
        decision_output = {"recommendation": "proceed"}

        alternatives = analyzer._discover_alternatives_heuristic(
            decision_input, decision_output, min_alternatives=2
        )

        assert len(alternatives) >= 2

    def test_describe_chosen(self):
        """Test describing the chosen alternative."""
        analyzer = AlternativesAnalyzer()

        output_action = {"action": "deploy"}
        desc = analyzer._describe_chosen(output_action)
        assert "deploy" in desc.lower()

        output_recommendation = {"recommendation": "update"}
        desc = analyzer._describe_chosen(output_recommendation)
        assert "update" in desc.lower() or "recommendation" in desc.lower()

        output_code = {"code_changes": {"old": "x", "new": "y"}}
        desc = analyzer._describe_chosen(output_code)
        assert "code" in desc.lower()

    def test_infer_pros(self):
        """Test inferring pros of the chosen option."""
        analyzer = AlternativesAnalyzer()

        output_verified = {"verified": True, "validated": True}
        pros = analyzer._infer_pros(output_verified)
        assert len(pros) > 0

        output_tests = {"tests": "passed"}
        pros = analyzer._infer_pros(output_tests)
        assert any("test" in p.lower() for p in pros)

        output_secure = {"action": "secure_endpoint"}
        pros = analyzer._infer_pros(output_secure)
        assert any("security" in p.lower() for p in pros)

    def test_infer_decision_type(self):
        """Test inferring decision type."""
        analyzer = AlternativesAnalyzer()

        # Security
        dt = analyzer._infer_decision_type(
            {"task": "security_review"}, {"severity": "critical"}
        )
        assert dt == "security"

        # Code change
        dt = analyzer._infer_decision_type({"task": "fix_bug"}, {"code_changes": {}})
        assert dt == "code_change"

        # Testing
        dt = analyzer._infer_decision_type(
            {"task": "run_tests"}, {"test_results": "passed"}
        )
        assert dt == "testing"

        # Generic
        dt = analyzer._infer_decision_type({"task": "analyze"}, {"result": "done"})
        assert dt == "general"

    def test_decision_rationale_set(
        self, sample_decision_input, sample_decision_output
    ):
        """Test that decision rationale is set."""
        analyzer = AlternativesAnalyzer()
        report = analyzer.analyze_sync(
            decision_id="dec_test",
            decision_input=sample_decision_input,
            decision_output=sample_decision_output,
            min_alternatives=2,
        )

        assert report.decision_rationale is not None
        assert len(report.decision_rationale) > 0


class TestGlobalAnalyzerManagement:
    """Tests for global analyzer management functions."""

    def setup_method(self):
        """Reset analyzer before each test."""
        reset_alternatives_analyzer()

    def teardown_method(self):
        """Reset analyzer after each test."""
        reset_alternatives_analyzer()

    def test_get_alternatives_analyzer(self):
        """Test getting the global analyzer."""
        analyzer = get_alternatives_analyzer()
        assert analyzer is not None
        assert isinstance(analyzer, AlternativesAnalyzer)

    def test_configure_alternatives_analyzer(self, mock_bedrock_client):
        """Test configuring the global analyzer."""
        config = AlternativesConfig(max_alternatives=10)
        analyzer = configure_alternatives_analyzer(
            bedrock_client=mock_bedrock_client,
            config=config,
        )

        assert analyzer.bedrock is mock_bedrock_client
        assert analyzer.config.max_alternatives == 10

    def test_reset_alternatives_analyzer(self):
        """Test resetting the global analyzer."""
        config = AlternativesConfig(max_alternatives=10)
        configure_alternatives_analyzer(config=config)

        reset_alternatives_analyzer()

        analyzer = get_alternatives_analyzer()
        assert analyzer.config.max_alternatives == 6  # Default

    def test_analyzer_singleton(self):
        """Test that get returns the same instance."""
        analyzer1 = get_alternatives_analyzer()
        analyzer2 = get_alternatives_analyzer()
        assert analyzer1 is analyzer2
