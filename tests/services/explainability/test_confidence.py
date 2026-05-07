"""
Tests for confidence quantifier.
"""

import pytest

from src.services.explainability.confidence import (
    ConfidenceQuantifier,
    configure_confidence_quantifier,
    get_confidence_quantifier,
    reset_confidence_quantifier,
)
from src.services.explainability.config import ConfidenceConfig
from src.services.explainability.contracts import AlternativesReport, ReasoningChain


class TestConfidenceQuantifier:
    """Tests for ConfidenceQuantifier class."""

    def setup_method(self):
        """Reset quantifier before each test."""
        reset_confidence_quantifier()

    def teardown_method(self):
        """Reset quantifier after each test."""
        reset_confidence_quantifier()

    def test_init_default_config(self):
        """Test initialization with default config."""
        quantifier = ConfidenceQuantifier()
        assert quantifier.config is not None

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = ConfidenceConfig(min_samples_for_mc=10)
        quantifier = ConfidenceQuantifier(config=config)
        assert quantifier.config.min_samples_for_mc == 10

    @pytest.mark.asyncio
    async def test_quantify_basic(
        self, sample_reasoning_chain, sample_alternatives_report
    ):
        """Test basic confidence quantification."""
        quantifier = ConfidenceQuantifier()
        interval = await quantifier.quantify(
            reasoning_chain=sample_reasoning_chain,
            alternatives_report=sample_alternatives_report,
        )

        assert interval.point_estimate >= 0.0
        assert interval.point_estimate <= 1.0
        assert interval.lower_bound <= interval.point_estimate
        assert interval.upper_bound >= interval.point_estimate

    @pytest.mark.asyncio
    async def test_quantify_with_context(
        self, sample_reasoning_chain, sample_alternatives_report
    ):
        """Test quantification with decision context."""
        quantifier = ConfidenceQuantifier()
        context = {
            "prior_decisions": ["dec_001"],
            "verified": True,
        }
        interval = await quantifier.quantify(
            reasoning_chain=sample_reasoning_chain,
            alternatives_report=sample_alternatives_report,
            decision_context=context,
        )

        assert interval.point_estimate >= 0.0
        # Context with verification should increase confidence
        assert interval.point_estimate > 0.5

    def test_quantify_sync_basic(
        self, sample_reasoning_chain, sample_alternatives_report
    ):
        """Test synchronous quantification."""
        quantifier = ConfidenceQuantifier()
        interval = quantifier.quantify_sync(
            reasoning_chain=sample_reasoning_chain,
            alternatives_report=sample_alternatives_report,
        )

        assert interval.point_estimate >= 0.0
        assert interval.point_estimate <= 1.0

    def test_collect_confidence_signals(
        self, sample_reasoning_chain, sample_alternatives_report
    ):
        """Test collecting confidence signals."""
        quantifier = ConfidenceQuantifier()
        signals = quantifier._collect_confidence_signals(
            sample_reasoning_chain, sample_alternatives_report, None
        )

        assert len(signals) > 0
        assert all(0.0 <= s <= 1.0 for s in signals)

    def test_collect_signals_empty_chain(self, sample_alternatives_report):
        """Test collecting signals with empty reasoning chain."""
        quantifier = ConfidenceQuantifier()
        empty_chain = ReasoningChain(decision_id="dec_001", agent_id="test")

        signals = quantifier._collect_confidence_signals(
            empty_chain, sample_alternatives_report, None
        )

        assert len(signals) > 0

    def test_collect_signals_empty_alternatives(self, sample_reasoning_chain):
        """Test collecting signals with empty alternatives."""
        quantifier = ConfidenceQuantifier()
        empty_alts = AlternativesReport(decision_id="dec_001")

        signals = quantifier._collect_confidence_signals(
            sample_reasoning_chain, empty_alts, None
        )

        assert len(signals) > 0

    def test_calculate_point_estimate(self):
        """Test point estimate calculation."""
        quantifier = ConfidenceQuantifier()

        # All high signals
        signals = [0.9, 0.95, 0.85]
        estimate = quantifier._calculate_point_estimate(signals)
        assert estimate > 0.5

        # All low signals
        signals = [0.3, 0.2, 0.25]
        estimate = quantifier._calculate_point_estimate(signals)
        assert estimate < 0.5

        # Empty signals
        estimate = quantifier._calculate_point_estimate([])
        assert estimate == 0.5

    def test_ensemble_disagreement_bounds(self):
        """Test ensemble disagreement bounds calculation."""
        quantifier = ConfidenceQuantifier()

        # Low variance signals
        signals = [0.8, 0.82, 0.79, 0.81]
        lower, upper = quantifier._ensemble_disagreement_bounds(0.8, signals)
        assert lower <= 0.8 <= upper
        assert upper - lower < 0.3  # Should be relatively narrow

        # High variance signals
        signals = [0.3, 0.8, 0.5, 0.9]
        lower, upper = quantifier._ensemble_disagreement_bounds(0.6, signals)
        assert lower <= 0.6 <= upper

    def test_ensemble_disagreement_bounds_single_signal(self):
        """Test bounds with single signal."""
        quantifier = ConfidenceQuantifier()
        lower, upper = quantifier._ensemble_disagreement_bounds(0.8, [0.8])
        assert lower <= 0.8 <= upper

    def test_monte_carlo_bounds(self):
        """Test Monte Carlo bounds calculation."""
        quantifier = ConfidenceQuantifier()

        # Enough signals for MC
        signals = [0.8, 0.82, 0.79, 0.81, 0.85, 0.78, 0.83]
        point_estimate = 0.8
        lower, upper = quantifier._monte_carlo_bounds(point_estimate, signals)
        # Allow small floating point tolerance since MC uses percentiles
        assert lower <= point_estimate + 0.01
        assert upper >= point_estimate - 0.01
        assert 0.0 <= lower <= 1.0
        assert 0.0 <= upper <= 1.0

    def test_monte_carlo_bounds_fallback(self):
        """Test MC bounds fallback with insufficient signals."""
        quantifier = ConfidenceQuantifier()
        config = ConfidenceConfig(min_samples_for_mc=10)
        quantifier.config = config

        # Not enough signals - should fallback to ensemble
        signals = [0.8, 0.82, 0.79]
        lower, upper = quantifier._monte_carlo_bounds(0.8, signals)
        assert lower <= 0.8 <= upper

    def test_temperature_scaling_bounds(self):
        """Test temperature scaling bounds calculation."""
        quantifier = ConfidenceQuantifier()

        # High confidence
        signals = [0.9]
        lower, upper = quantifier._temperature_scaling_bounds(0.9, signals)
        assert lower <= 0.9 <= upper
        assert 0.0 <= lower <= 1.0
        assert 0.0 <= upper <= 1.0

        # Low confidence
        lower, upper = quantifier._temperature_scaling_bounds(0.3, signals)
        assert lower <= 0.3 <= upper

    def test_default_bounds(self):
        """Test default bounds calculation."""
        quantifier = ConfidenceQuantifier()
        lower, upper = quantifier._default_bounds(0.8, [0.8])

        # Default uses +/- 15% margin
        assert abs(lower - 0.65) < 0.01
        assert abs(upper - 0.95) < 0.01

    def test_identify_uncertainty_sources(
        self, sample_reasoning_chain, sample_alternatives_report
    ):
        """Test identifying uncertainty sources."""
        quantifier = ConfidenceQuantifier()
        signals = [0.8, 0.7, 0.9]

        sources = quantifier._identify_uncertainty_sources(
            sample_reasoning_chain, sample_alternatives_report, signals
        )

        assert len(sources) > 0
        assert all(isinstance(s, str) for s in sources)

    def test_identify_low_confidence_steps(self):
        """Test identifying low confidence steps."""
        quantifier = ConfidenceQuantifier()

        chain = ReasoningChain(decision_id="dec_001", agent_id="test")
        chain.add_step(description="Step 1", confidence=0.95)
        chain.add_step(description="Step 2", confidence=0.4)  # Low
        chain.add_step(description="Step 3", confidence=0.6)  # Low

        alts = AlternativesReport(decision_id="dec_001")
        sources = quantifier._identify_uncertainty_sources(chain, alts, [0.7])

        assert any("Low confidence" in s for s in sources)

    def test_identify_missing_evidence(self):
        """Test identifying missing evidence."""
        quantifier = ConfidenceQuantifier()

        chain = ReasoningChain(decision_id="dec_001", agent_id="test")
        chain.add_step(description="Step 1", evidence=[])  # No evidence
        chain.add_step(description="Step 2", evidence=[])  # No evidence

        alts = AlternativesReport(decision_id="dec_001")
        sources = quantifier._identify_uncertainty_sources(chain, alts, [0.7])

        assert any("evidence" in s.lower() for s in sources)

    def test_identify_close_alternatives(self):
        """Test identifying close alternatives."""
        quantifier = ConfidenceQuantifier()

        chain = ReasoningChain(decision_id="dec_001", agent_id="test")
        alts = AlternativesReport(decision_id="dec_001")
        alts.add_alternative("alt_001", "Option A", confidence=0.75, was_chosen=True)
        alts.add_alternative(
            "alt_002", "Option B", confidence=0.73, was_chosen=False
        )  # Close

        sources = quantifier._identify_uncertainty_sources(chain, alts, [0.7])

        assert any(
            "alternative" in s.lower() or "competition" in s.lower() for s in sources
        )

    def test_calibration_method_recorded(
        self, sample_reasoning_chain, sample_alternatives_report
    ):
        """Test that calibration method is recorded."""
        quantifier = ConfidenceQuantifier()
        interval = quantifier.quantify_sync(
            reasoning_chain=sample_reasoning_chain,
            alternatives_report=sample_alternatives_report,
        )

        assert interval.calibration_method == "ensemble_disagreement"

    def test_sample_size_recorded(
        self, sample_reasoning_chain, sample_alternatives_report
    ):
        """Test that sample size is recorded."""
        quantifier = ConfidenceQuantifier()
        interval = quantifier.quantify_sync(
            reasoning_chain=sample_reasoning_chain,
            alternatives_report=sample_alternatives_report,
        )

        assert interval.sample_size > 0


class TestGlobalQuantifierManagement:
    """Tests for global quantifier management functions."""

    def setup_method(self):
        """Reset quantifier before each test."""
        reset_confidence_quantifier()

    def teardown_method(self):
        """Reset quantifier after each test."""
        reset_confidence_quantifier()

    def test_get_confidence_quantifier(self):
        """Test getting the global quantifier."""
        quantifier = get_confidence_quantifier()
        assert quantifier is not None
        assert isinstance(quantifier, ConfidenceQuantifier)

    def test_configure_confidence_quantifier(self):
        """Test configuring the global quantifier."""
        config = ConfidenceConfig(min_samples_for_mc=10)
        quantifier = configure_confidence_quantifier(config=config)

        assert quantifier.config.min_samples_for_mc == 10

    def test_reset_confidence_quantifier(self):
        """Test resetting the global quantifier."""
        config = ConfidenceConfig(min_samples_for_mc=10)
        configure_confidence_quantifier(config=config)

        reset_confidence_quantifier()

        quantifier = get_confidence_quantifier()
        assert quantifier.config.min_samples_for_mc == 5  # Default

    def test_quantifier_singleton(self):
        """Test that get returns the same instance."""
        q1 = get_confidence_quantifier()
        q2 = get_confidence_quantifier()
        assert q1 is q2
