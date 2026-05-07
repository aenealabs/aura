"""
Project Aura - Campaign Drift Detector.

Three-signal drift detection from ADR-089 §Drift Detection.

Long campaigns drift — agents anchor on early reasoning that becomes
stale, leading to repeated discoveries and progressively worse
outputs. Three cheap signals:

1. **Embedding drift** between phase-N summary and phase-1 problem
   statement. Cosine distance > threshold flags drift.
2. **Goal-recall** at phase entry: agent restates success criteria,
   compared to ground truth.
3. **Repetition signal**: rising artifact-dedup hit rate means the
   agent is re-finding the same things.

Any one signal exceeding its threshold triggers a re-anchor: drop
working memory, reload from campaign memory, re-enter the phase from
its checkpoint.

The detector is pure (no IO); embeddings are supplied by the caller.
This keeps the unit-test surface tight and avoids coupling the
campaign manager to a specific embedding service.

Implements ADR-089 §Drift Detection.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DriftSignals:
    """Snapshot of the three drift signals for a phase."""

    embedding_drift: float  # cosine distance, [0, 2]; typically [0, 1]
    goal_recall_score: float  # similarity, [0, 1]; lower = worse recall
    repetition_rate: float  # dedup-hit rate, [0, 1]; higher = anchored


@dataclass(frozen=True)
class DriftThresholds:
    """Thresholds beyond which a re-anchor is recommended."""

    embedding_drift_max: float = 0.4  # ADR default
    goal_recall_min: float = 0.6  # below = poor recall
    repetition_rate_max: float = 0.5  # above = anchored


@dataclass(frozen=True)
class DriftAssessment:
    """Output of an assessment step."""

    score: float  # composite, [0, 1]
    signals: DriftSignals
    re_anchor_recommended: bool
    triggered_signals: tuple[str, ...]  # which signals breached thresholds


def cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance between two vectors. Returns 1 - cosine similarity.

    Defensive: a vector pair with zero norm cannot be compared, so we
    fall back to maximum distance (1.0). This is preferable to raising
    inside a hot drift-detection loop.
    """
    if len(a) != len(b):
        raise ValueError(
            f"vector length mismatch: {len(a)} vs {len(b)}"
        )
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    similarity = dot / (norm_a * norm_b)
    return max(0.0, 1.0 - similarity)


class DriftDetector:
    """Three-signal drift detector.

    Caller is responsible for supplying:
    - embeddings (from any embedding service — tests use trivial vectors)
    - the ratio of duplicate-to-total artifacts seen in a phase

    The detector is intentionally pure. It does not invoke models or
    fetch artifacts itself.
    """

    def __init__(self, thresholds: DriftThresholds | None = None) -> None:
        self._thresholds = thresholds or DriftThresholds()

    def assess(
        self,
        phase_summary_embedding: list[float],
        problem_statement_embedding: list[float],
        goal_recall_score: float,
        repetition_rate: float,
    ) -> DriftAssessment:
        """Compute drift signals and decide whether re-anchor is recommended."""
        if not 0.0 <= goal_recall_score <= 1.0:
            raise ValueError(
                f"goal_recall_score must be in [0, 1]; "
                f"got {goal_recall_score!r}"
            )
        if not 0.0 <= repetition_rate <= 1.0:
            raise ValueError(
                f"repetition_rate must be in [0, 1]; got {repetition_rate!r}"
            )

        embed_drift = cosine_distance(
            phase_summary_embedding, problem_statement_embedding
        )

        signals = DriftSignals(
            embedding_drift=embed_drift,
            goal_recall_score=goal_recall_score,
            repetition_rate=repetition_rate,
        )

        triggered: list[str] = []
        if embed_drift > self._thresholds.embedding_drift_max:
            triggered.append("embedding_drift")
        if goal_recall_score < self._thresholds.goal_recall_min:
            triggered.append("goal_recall")
        if repetition_rate > self._thresholds.repetition_rate_max:
            triggered.append("repetition_rate")

        # Composite score: average of normalised "badness". Each signal
        # contributes a value in [0, 1], where 0 = healthy, 1 = maximally
        # bad. The composite is the mean — gives operators a single
        # scalar to alarm on.
        embed_bad = min(
            1.0, embed_drift / max(self._thresholds.embedding_drift_max, 1e-9)
        )
        recall_bad = max(
            0.0,
            (self._thresholds.goal_recall_min - goal_recall_score)
            / max(self._thresholds.goal_recall_min, 1e-9),
        )
        repeat_bad = min(
            1.0,
            repetition_rate
            / max(self._thresholds.repetition_rate_max, 1e-9),
        )
        score = (embed_bad + recall_bad + repeat_bad) / 3.0

        return DriftAssessment(
            score=min(1.0, max(0.0, score)),
            signals=signals,
            re_anchor_recommended=bool(triggered),
            triggered_signals=tuple(triggered),
        )
