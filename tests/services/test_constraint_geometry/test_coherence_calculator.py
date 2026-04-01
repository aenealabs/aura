"""
Project Aura - CGE Coherence Calculator Tests

Tests for deterministic coherence computation: cosine similarity,
weighted harmonic mean, weighted geometric mean, per-axis and composite scoring.

Author: Project Aura Team
Created: 2026-02-11
"""

import numpy as np
import pytest

from src.services.constraint_geometry.contracts import (
    AxisCoherenceScore,
    ConstraintAxis,
)

# =============================================================================
# Cosine Similarity Tests
# =============================================================================


class TestCosineSimilarity:
    """Test deterministic cosine similarity computation."""

    def test_identical_vectors(self, calculator):
        """Identical vectors have similarity 1.0."""
        v = np.array([1.0, 0.0, 0.0, 0.0])
        assert calculator._cosine_similarity(v, v) == pytest.approx(1.0)

    def test_opposite_vectors(self, calculator):
        """Opposite vectors have similarity -1.0."""
        v1 = np.array([1.0, 0.0, 0.0, 0.0])
        v2 = np.array([-1.0, 0.0, 0.0, 0.0])
        assert calculator._cosine_similarity(v1, v2) == pytest.approx(-1.0)

    def test_orthogonal_vectors(self, calculator):
        """Orthogonal vectors have similarity 0.0."""
        v1 = np.array([1.0, 0.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0, 0.0])
        assert calculator._cosine_similarity(v1, v2) == pytest.approx(0.0)

    def test_zero_vector_returns_zero(self, calculator):
        """Zero vector produces similarity 0.0."""
        v1 = np.array([1.0, 0.0])
        v2 = np.array([0.0, 0.0])
        assert calculator._cosine_similarity(v1, v2) == 0.0

    def test_high_dimensional(self, calculator):
        """Works with high-dimensional vectors (1024)."""
        rng = np.random.RandomState(42)
        v1 = rng.randn(1024)
        v2 = rng.randn(1024)
        sim = calculator._cosine_similarity(v1, v2)
        assert -1.0 <= sim <= 1.0

    def test_result_clipped(self, calculator):
        """Result is always in [-1.0, 1.0]."""
        for seed in range(10):
            rng = np.random.RandomState(seed)
            v1 = rng.randn(16)
            v2 = rng.randn(16)
            sim = calculator._cosine_similarity(v1, v2)
            assert -1.0 <= sim <= 1.0

    def test_symmetry(self, calculator):
        """cosine(a, b) == cosine(b, a)."""
        rng = np.random.RandomState(99)
        v1 = rng.randn(16)
        v2 = rng.randn(16)
        assert calculator._cosine_similarity(v1, v2) == pytest.approx(
            calculator._cosine_similarity(v2, v1)
        )


# =============================================================================
# Weighted Harmonic Mean Tests
# =============================================================================


class TestWeightedHarmonicMean:
    """Test weighted harmonic mean computation."""

    def test_equal_values(self, calculator):
        """Equal values produce that value."""
        result = calculator._weighted_harmonic_mean(
            values=[0.8, 0.8, 0.8],
            weights=[1.0, 1.0, 1.0],
        )
        assert result == pytest.approx(0.8, abs=1e-6)

    def test_penalizes_low_values(self, calculator):
        """Harmonic mean penalizes low values more than arithmetic."""
        values = [0.95, 0.95, 0.95, 0.2]
        weights = [1.0, 1.0, 1.0, 1.0]
        harmonic = calculator._weighted_harmonic_mean(values, weights)
        arithmetic = sum(v * w for v, w in zip(values, weights)) / sum(weights)
        assert harmonic < arithmetic  # Harmonic penalizes more

    def test_near_zero_drops_sharply(self, calculator):
        """Near-zero value drops harmonic mean significantly."""
        result = calculator._weighted_harmonic_mean(
            values=[0.95, 0.95, 0.01],
            weights=[1.0, 1.0, 1.0],
        )
        assert result < 0.1  # Sharp drop due to 0.01

    def test_empty_values(self, calculator):
        """Empty values return 0.0."""
        assert calculator._weighted_harmonic_mean([], []) == 0.0

    def test_weighted_values(self, calculator):
        """Weights affect the harmonic mean."""
        # High weight on high value should increase result
        high_weight_on_high = calculator._weighted_harmonic_mean(
            values=[0.9, 0.3],
            weights=[10.0, 1.0],
        )
        equal_weight = calculator._weighted_harmonic_mean(
            values=[0.9, 0.3],
            weights=[1.0, 1.0],
        )
        assert high_weight_on_high > equal_weight

    def test_result_in_valid_range(self, calculator):
        """Result is always in [0.0, 1.0]."""
        for seed in range(20):
            rng = np.random.RandomState(seed)
            values = rng.uniform(0.01, 1.0, 5).tolist()
            weights = rng.uniform(0.1, 2.0, 5).tolist()
            result = calculator._weighted_harmonic_mean(values, weights)
            assert 0.0 <= result <= 1.0


# =============================================================================
# Weighted Geometric Mean Tests
# =============================================================================


class TestWeightedGeometricMean:
    """Test weighted geometric mean computation."""

    def test_equal_values(self, calculator):
        """Equal values produce that value."""
        result = calculator._weighted_geometric_mean(
            values=[0.7, 0.7, 0.7],
            weights=[1.0, 1.0, 1.0],
        )
        assert result == pytest.approx(0.7, abs=1e-6)

    def test_zero_value_drives_to_zero(self, calculator):
        """Zero on any axis drives composite near zero."""
        result = calculator._weighted_geometric_mean(
            values=[0.95, 0.95, 0.0],
            weights=[1.0, 1.0, 1.0],
        )
        assert result < 0.01  # Near zero

    def test_moderate_tradeoff(self, calculator):
        """Moderate values allow some tradeoff."""
        result = calculator._weighted_geometric_mean(
            values=[0.9, 0.7, 0.8],
            weights=[1.0, 1.0, 1.0],
        )
        # Geometric mean of 0.9, 0.7, 0.8 ≈ 0.797
        assert 0.75 < result < 0.85

    def test_empty_values(self, calculator):
        """Empty values return 0.0."""
        assert calculator._weighted_geometric_mean([], []) == 0.0

    def test_weighted_effect(self, calculator):
        """Weights shift the geometric mean."""
        high_weight_on_low = calculator._weighted_geometric_mean(
            values=[0.9, 0.3],
            weights=[1.0, 5.0],
        )
        high_weight_on_high = calculator._weighted_geometric_mean(
            values=[0.9, 0.3],
            weights=[5.0, 1.0],
        )
        assert high_weight_on_high > high_weight_on_low

    def test_result_in_valid_range(self, calculator):
        """Result is always in [0.0, 1.0]."""
        for seed in range(20):
            rng = np.random.RandomState(seed)
            values = rng.uniform(0.01, 1.0, 7).tolist()
            weights = rng.uniform(0.5, 2.0, 7).tolist()
            result = calculator._weighted_geometric_mean(values, weights)
            assert 0.0 <= result <= 1.0


# =============================================================================
# Rule Coherence Score Tests
# =============================================================================


class TestRuleCoherence:
    """Test per-rule coherence computation."""

    def test_high_positive_similarity(self, calculator, rule_c1_syntax):
        """Output similar to positive centroid scores high."""
        # Use the positive centroid itself as output embedding
        output = np.array(rule_c1_syntax.positive_centroid)
        score = calculator.compute_rule_coherence(output, rule_c1_syntax)
        assert score.coherence > 0.8  # High coherence
        assert score.positive_similarity > score.negative_similarity

    def test_high_negative_similarity(self, calculator, rule_c1_syntax):
        """Output similar to negative centroid scores low."""
        output = np.array(rule_c1_syntax.negative_centroid)
        score = calculator.compute_rule_coherence(output, rule_c1_syntax)
        assert score.coherence < 0.3  # Low coherence
        assert score.negative_similarity > score.positive_similarity

    def test_coherence_in_valid_range(self, calculator, rule_c1_syntax):
        """Coherence is always in [0.0, 1.0]."""
        for seed in range(20):
            rng = np.random.RandomState(seed)
            output = rng.randn(len(rule_c1_syntax.positive_centroid))
            score = calculator.compute_rule_coherence(output, rule_c1_syntax)
            assert 0.0 <= score.coherence <= 1.0

    def test_rule_metadata_in_score(self, calculator, rule_c1_syntax):
        """Score carries rule metadata."""
        output = np.array(rule_c1_syntax.positive_centroid)
        score = calculator.compute_rule_coherence(output, rule_c1_syntax)
        assert score.rule_id == "c1-syntax-001"
        assert score.rule_name == "AST Parse Check"
        assert score.weight == 1.0


# =============================================================================
# Axis Score Tests
# =============================================================================


class TestAxisScore:
    """Test per-axis coherence computation."""

    def test_single_rule_axis(self, calculator, rule_c1_syntax):
        """Axis with single rule returns that rule's score."""
        output = np.array(rule_c1_syntax.positive_centroid)
        score = calculator.compute_axis_score(
            output_embedding=output,
            axis=ConstraintAxis.SYNTACTIC_VALIDITY,
            rules=[rule_c1_syntax],
        )
        assert score.axis == ConstraintAxis.SYNTACTIC_VALIDITY
        assert score.score > 0.5
        assert len(score.contributing_rules) == 1

    def test_empty_rules_returns_full_coherence(self, calculator):
        """Axis with no rules returns score 1.0 (no constraints)."""
        output = np.random.randn(16)
        score = calculator.compute_axis_score(
            output_embedding=output,
            axis=ConstraintAxis.TEMPORAL_VALIDITY,
            rules=[],
        )
        assert score.score == 1.0

    def test_multiple_rules_harmonic_mean(
        self, calculator, rule_c1_syntax, rule_c1_types
    ):
        """Multiple rules use weighted harmonic mean."""
        output = np.array(rule_c1_syntax.positive_centroid)
        score = calculator.compute_axis_score(
            output_embedding=output,
            axis=ConstraintAxis.SYNTACTIC_VALIDITY,
            rules=[rule_c1_syntax, rule_c1_types],
        )
        assert len(score.contributing_rules) == 2
        assert score.score > 0.0

    def test_provenance_adjustment_on_c3(self, calculator, rule_c3_nist_ac6):
        """Provenance adjustment modifies C3 weight."""
        output = np.array(rule_c3_nist_ac6.positive_centroid)
        no_adj = calculator.compute_axis_score(
            output_embedding=output,
            axis=ConstraintAxis.SECURITY_POLICY,
            rules=[rule_c3_nist_ac6],
            axis_weight=1.2,
            provenance_weight_adjustment=0.0,
        )
        with_adj = calculator.compute_axis_score(
            output_embedding=output,
            axis=ConstraintAxis.SECURITY_POLICY,
            rules=[rule_c3_nist_ac6],
            axis_weight=1.2,
            provenance_weight_adjustment=0.35,
        )
        # Same score, but different weight
        assert no_adj.score == with_adj.score
        assert with_adj.weight > no_adj.weight


# =============================================================================
# Composite Score Tests
# =============================================================================


class TestCompositeScore:
    """Test composite CCS computation."""

    def test_all_perfect_axes(self, calculator):
        """All perfect axes produce perfect composite."""
        axis_scores = [
            AxisCoherenceScore(
                axis=axis,
                score=1.0,
                weight=1.0,
                weighted_score=1.0,
                contributing_rules=("r",),
                rule_scores=(),
            )
            for axis in ConstraintAxis
        ]
        composite = calculator.compute_composite(axis_scores)
        assert composite == pytest.approx(1.0, abs=1e-6)

    def test_one_zero_axis_drops_composite(self, calculator):
        """One zero axis drives composite near zero."""
        axis_scores = [
            AxisCoherenceScore(
                axis=ConstraintAxis.SYNTACTIC_VALIDITY,
                score=0.0,  # Zero!
                weight=1.0,
                weighted_score=0.0,
                contributing_rules=("r",),
                rule_scores=(),
            ),
            AxisCoherenceScore(
                axis=ConstraintAxis.SECURITY_POLICY,
                score=0.95,
                weight=1.0,
                weighted_score=0.95,
                contributing_rules=("r",),
                rule_scores=(),
            ),
        ]
        composite = calculator.compute_composite(axis_scores)
        assert composite < 0.01

    def test_empty_scores(self, calculator):
        """Empty axis scores produce composite 0.0."""
        assert calculator.compute_composite([]) == 0.0

    def test_moderate_scores(self, calculator):
        """Moderate scores produce moderate composite."""
        axis_scores = [
            AxisCoherenceScore(
                axis=ConstraintAxis.SYNTACTIC_VALIDITY,
                score=0.8,
                weight=1.0,
                weighted_score=0.8,
                contributing_rules=("r",),
                rule_scores=(),
            ),
            AxisCoherenceScore(
                axis=ConstraintAxis.SECURITY_POLICY,
                score=0.7,
                weight=1.2,
                weighted_score=0.84,
                contributing_rules=("r",),
                rule_scores=(),
            ),
        ]
        composite = calculator.compute_composite(axis_scores)
        assert 0.6 < composite < 0.85
