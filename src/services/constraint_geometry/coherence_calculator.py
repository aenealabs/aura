"""
Project Aura - Deterministic Coherence Calculator

Pure arithmetic coherence computation using NumPy. This module contains
no I/O, no network calls, and no non-deterministic operations. Given the
same embeddings, constraints, and weights, it always produces the same score.

Algorithm:
1. Per-rule: cosine similarity vs positive/negative centroids -> normalized [0,1]
2. Per-axis: weighted harmonic mean of rule coherences (penalizes violations)
3. Composite: weighted geometric mean across axes (zero on any axis -> zero composite)

Author: Project Aura Team
Created: 2026-02-11
"""

from __future__ import annotations

import logging
from typing import Sequence

import numpy as np

from .contracts import (
    AxisCoherenceScore,
    ConstraintAxis,
    ConstraintRule,
    ResolvedConstraintSet,
    RuleCoherenceScore,
)

logger = logging.getLogger(__name__)

# Minimum value to prevent division by zero in harmonic mean
_EPSILON = 1e-10

# Minimum value for geometric mean to prevent log(0)
_FLOOR = 1e-12


class CoherenceCalculator:
    """Deterministic coherence computation engine.

    All methods are pure functions of their inputs. No state is mutated,
    no external calls are made, and no randomness is introduced.
    """

    def compute_rule_coherence(
        self,
        output_embedding: np.ndarray,
        rule: ConstraintRule,
    ) -> RuleCoherenceScore:
        """Compute coherence of an output against a single constraint rule.

        The coherence score measures where the output falls relative to
        the rule's positive (satisfying) and negative (violating) centroids.

        Formula:
            pos_sim = cosine(output, positive_centroid)
            neg_sim = cosine(output, negative_centroid)
            coherence = (pos_sim - neg_sim + 1.0) / 2.0  -> [0.0, 1.0]

        Args:
            output_embedding: Vector embedding of the agent output
            rule: Constraint rule with frozen positive/negative centroids

        Returns:
            RuleCoherenceScore with deterministic coherence value
        """
        pos_centroid = np.array(rule.positive_centroid, dtype=np.float64)
        neg_centroid = np.array(rule.negative_centroid, dtype=np.float64)

        pos_sim = self._cosine_similarity(output_embedding, pos_centroid)
        neg_sim = self._cosine_similarity(output_embedding, neg_centroid)

        # Normalize to [0.0, 1.0]
        # If output is maximally similar to positive and maximally dissimilar
        # to negative, coherence = 1.0. Vice versa = 0.0.
        coherence = (pos_sim - neg_sim + 1.0) / 2.0
        coherence = float(np.clip(coherence, 0.0, 1.0))

        return RuleCoherenceScore(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            positive_similarity=float(pos_sim),
            negative_similarity=float(neg_sim),
            coherence=coherence,
            weight=rule.weight,
        )

    def compute_axis_score(
        self,
        output_embedding: np.ndarray,
        axis: ConstraintAxis,
        rules: Sequence[ConstraintRule],
        axis_weight: float = 1.0,
        provenance_weight_adjustment: float = 0.0,
    ) -> AxisCoherenceScore:
        """Compute coherence score for a single constraint axis.

        Uses weighted harmonic mean of rule coherences. The harmonic mean
        penalizes violations more heavily than arithmetic mean: if an output
        scores 0.95 on 4 rules but 0.2 on one, the harmonic mean drops
        significantly, reflecting that constraint satisfaction is conjunctive.

        Args:
            output_embedding: Vector embedding of the agent output
            axis: The constraint axis being scored
            rules: Constraint rules on this axis
            axis_weight: Weight of this axis from policy profile
            provenance_weight_adjustment: Adjustment from provenance trust

        Returns:
            AxisCoherenceScore with weighted harmonic mean
        """
        if not rules:
            return AxisCoherenceScore(
                axis=axis,
                score=1.0,  # No constraints = full coherence
                weight=axis_weight,
                weighted_score=axis_weight,
                contributing_rules=(),
                rule_scores=(),
            )

        # Compute per-rule coherence scores
        rule_scores = []
        for rule in rules:
            if not rule.is_active:
                continue
            score = self.compute_rule_coherence(output_embedding, rule)
            rule_scores.append(score)

        if not rule_scores:
            return AxisCoherenceScore(
                axis=axis,
                score=1.0,
                weight=axis_weight,
                weighted_score=axis_weight,
                contributing_rules=(),
                rule_scores=(),
            )

        # Weighted harmonic mean
        axis_score = self._weighted_harmonic_mean(
            values=[s.coherence for s in rule_scores],
            weights=[s.weight for s in rule_scores],
        )

        # Apply provenance weight adjustment for security axis
        effective_weight = axis_weight
        if (
            axis == ConstraintAxis.SECURITY_POLICY
            and provenance_weight_adjustment != 0.0
        ):
            effective_weight = axis_weight * (1.0 + provenance_weight_adjustment)

        return AxisCoherenceScore(
            axis=axis,
            score=axis_score,
            weight=effective_weight,
            weighted_score=axis_score * effective_weight,
            contributing_rules=tuple(s.rule_id for s in rule_scores),
            rule_scores=tuple(rule_scores),
        )

    def compute_axis_scores(
        self,
        output_embedding: np.ndarray,
        constraints: ResolvedConstraintSet,
        axis_weights: dict[ConstraintAxis, float],
        provenance_adjustment: float = 0.0,
    ) -> list[AxisCoherenceScore]:
        """Compute coherence scores for all constraint axes.

        Args:
            output_embedding: Vector embedding of the agent output
            constraints: Resolved constraint set from Neptune
            axis_weights: Per-axis weights from policy profile
            provenance_adjustment: Provenance trust adjustment

        Returns:
            List of AxisCoherenceScore for all active axes
        """
        scores = []
        for axis in ConstraintAxis:
            rules = constraints.get_axis_rules(axis)
            weight = axis_weights.get(axis, 1.0)
            score = self.compute_axis_score(
                output_embedding=output_embedding,
                axis=axis,
                rules=rules,
                axis_weight=weight,
                provenance_weight_adjustment=provenance_adjustment,
            )
            scores.append(score)
        return scores

    def compute_composite(
        self,
        axis_scores: Sequence[AxisCoherenceScore],
    ) -> float:
        """Compute composite CCS via weighted geometric mean.

        The geometric mean ensures that a zero score on any axis drives the
        composite toward zero. This reflects the conjunctive nature of
        constraint satisfaction: an output that fails any axis should not
        be considered coherent.

        Args:
            axis_scores: Per-axis coherence scores

        Returns:
            Composite CCS value [0.0, 1.0]
        """
        if not axis_scores:
            return 0.0

        scores = [s.score for s in axis_scores]
        weights = [s.weight for s in axis_scores]

        return self._weighted_geometric_mean(scores, weights)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors.

        Returns:
            Cosine similarity in [-1.0, 1.0]
        """
        a = a.astype(np.float64)
        b = b.astype(np.float64)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a < _EPSILON or norm_b < _EPSILON:
            return 0.0

        similarity = float(np.dot(a, b) / (norm_a * norm_b))
        return float(np.clip(similarity, -1.0, 1.0))

    @staticmethod
    def _weighted_harmonic_mean(
        values: Sequence[float],
        weights: Sequence[float],
    ) -> float:
        """Compute weighted harmonic mean.

        H_w = sum(w_i) / sum(w_i / max(v_i, epsilon))

        Penalizes low values more heavily than arithmetic mean.
        If any value is near zero, the harmonic mean drops sharply.

        Returns:
            Weighted harmonic mean in [0.0, 1.0]
        """
        if not values:
            return 0.0

        total_weight = sum(weights)
        if total_weight < _EPSILON:
            return 0.0

        weighted_reciprocal_sum = sum(
            w / max(v, _EPSILON) for v, w in zip(values, weights)
        )

        if weighted_reciprocal_sum < _EPSILON:
            return 0.0

        result = total_weight / weighted_reciprocal_sum
        return float(np.clip(result, 0.0, 1.0))

    @staticmethod
    def _weighted_geometric_mean(
        values: Sequence[float],
        weights: Sequence[float],
    ) -> float:
        """Compute weighted geometric mean.

        G_w = exp(sum(w_i * ln(v_i)) / sum(w_i))

        A zero on any axis drives the composite toward zero.
        Uses log-space computation for numerical stability.

        Returns:
            Weighted geometric mean in [0.0, 1.0]
        """
        if not values:
            return 0.0

        total_weight = sum(weights)
        if total_weight < _EPSILON:
            return 0.0

        # Floor values to prevent log(0)
        floored = [max(v, _FLOOR) for v in values]

        log_sum = sum(w * np.log(v) for v, w in zip(floored, weights))

        result = float(np.exp(log_sum / total_weight))
        return float(np.clip(result, 0.0, 1.0))
