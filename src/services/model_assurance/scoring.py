"""Scoring pipeline for ADR-088 model assurance.

Takes per-axis raw benchmark scores plus an optional incumbent
baseline, evaluates regression floors, computes a provenance-weighted
utility score, and produces a deterministic verdict (ACCEPT / REJECT
/ TIE_REJECT). The output of this stage feeds the Shadow Deployment
Report consumed by the HITL approval queue (Phase 2).

Per ADR-088 §Stage 5:

    U = Σ(Ai · Wi · Pi)
        Ai = axis score (0.0–1.0)
        Wi = axis weight (configurable per evaluation profile)
        Pi = provenance trust multiplier from ADR-067 (0.0–1.0)

A candidate must achieve ``U > U_incumbent`` to qualify for HITL
approval. **Ties are rejected** — the incumbent holds unless the
challenger demonstrates measurable improvement.

The evaluator is a pure function. No I/O, no logging at WARN/ERROR
levels (would risk leaking benchmark internals to operator
notifications), no external state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from src.services.constraint_geometry.contracts import (
    RegressionFloor,
    RegressionFloorViolation,
)
from src.services.constraint_geometry.regression_floor import (
    IncumbentBaseline,
    evaluate_floors,
    violations_force_reject,
)
from src.services.model_assurance.axes import (
    AXIS_DEFINITIONS,
    ModelAssuranceAxis,
    default_floors,
    default_weights,
)


class ModelAssuranceVerdict(Enum):
    """Outcome of one model-assurance evaluation run."""

    ACCEPT = "accept"               # candidate passes floors AND U > U_incumbent
    REJECT = "reject"               # floor violation forces rejection
    TIE_REJECT = "tie_reject"       # U == U_incumbent — incumbent holds
    INFERIOR = "inferior"           # U < U_incumbent
    NO_INCUMBENT_HITL = "no_incumbent_hitl"  # first-ever evaluation; HITL must judge


@dataclass(frozen=True)
class AxisScore:
    """Per-axis raw benchmark score for one candidate."""

    axis: ModelAssuranceAxis
    score: float

    def __post_init__(self) -> None:
        if not _is_finite(self.score):
            # Per ADR-088 anti-Goodharting: NaN must not silently propagate
            # through utility math. The contract is "raise at boundary".
            raise ValueError(
                f"AxisScore.score for {self.axis.value} must be finite; "
                f"got {self.score!r}"
            )
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(
                f"AxisScore.score for {self.axis.value} must be in [0,1]; "
                f"got {self.score}"
            )


@dataclass(frozen=True)
class ModelAssuranceResult:
    """Deterministic outcome of one assurance evaluation."""

    candidate_id: str
    incumbent_id: str | None
    verdict: ModelAssuranceVerdict
    utility_score: float
    incumbent_utility: float | None
    axis_scores: tuple[AxisScore, ...]
    floor_violations: tuple[RegressionFloorViolation, ...]
    provenance_multiplier: float
    rejection_reason: str | None

    def to_audit_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "incumbent_id": self.incumbent_id,
            "verdict": self.verdict.value,
            "utility_score": round(self.utility_score, 6),
            "incumbent_utility": (
                round(self.incumbent_utility, 6)
                if self.incumbent_utility is not None
                else None
            ),
            "axis_scores": {s.axis.value: round(s.score, 6) for s in self.axis_scores},
            "floor_violations": [v.to_audit_dict() for v in self.floor_violations],
            "provenance_multiplier": round(self.provenance_multiplier, 6),
            "rejection_reason": self.rejection_reason,
        }


def _is_finite(v: float | int | None) -> bool:
    if v is None:
        return False
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _utility(
    axis_scores: Mapping[ModelAssuranceAxis, float],
    weights: Mapping[ModelAssuranceAxis, float],
    provenance_multiplier: float,
) -> float:
    """U = Σ(Ai · Wi · Pi).

    Missing axes contribute 0 (so an incomplete candidate scores
    lower than a complete one). Any non-finite axis score is treated
    as 0 — the AxisScore validator already prevents this in the
    candidate path; this guard protects the incumbent path where the
    baseline may have been computed elsewhere.
    """
    total = 0.0
    for axis, weight in weights.items():
        score = axis_scores.get(axis, 0.0)
        if not _is_finite(score):
            continue
        total += score * weight * provenance_multiplier
    return total


class ModelAssuranceEvaluator:
    """Stateless evaluator for ADR-088 model assurance.

    Constructed once with a profile (floors + weights) and then
    evaluated against any number of candidates. Same inputs always
    produce the same output — the evaluator does no I/O, holds no
    mutable state, and is safe to share across threads.
    """

    def __init__(
        self,
        *,
        floors: tuple[RegressionFloor, ...] | None = None,
        weights: Mapping[ModelAssuranceAxis, float] | None = None,
    ) -> None:
        self._floors = floors if floors is not None else default_floors()
        self._weights = (
            dict(weights) if weights is not None else default_weights()
        )

    @property
    def floors(self) -> tuple[RegressionFloor, ...]:
        return self._floors

    @property
    def weights(self) -> dict[ModelAssuranceAxis, float]:
        return dict(self._weights)

    def evaluate(
        self,
        *,
        candidate_id: str,
        candidate_scores: tuple[AxisScore, ...],
        incumbent: IncumbentBaseline | None,
        provenance_multiplier: float = 1.0,
    ) -> ModelAssuranceResult:
        """Score ``candidate_scores`` against floors + incumbent."""
        if not _is_finite(provenance_multiplier):
            raise ValueError(
                f"provenance_multiplier must be finite; "
                f"got {provenance_multiplier!r}"
            )
        if not 0.0 <= provenance_multiplier <= 1.0:
            raise ValueError(
                f"provenance_multiplier must be in [0,1]; "
                f"got {provenance_multiplier}"
            )

        # Keyed by axis-id string for the floor evaluator.
        candidate_by_id: dict[str, float] = {
            s.axis.value: s.score for s in candidate_scores
        }

        violations = evaluate_floors(
            self._floors,
            candidate_by_id,
            incumbent=incumbent,
        )

        if violations_force_reject(violations):
            return ModelAssuranceResult(
                candidate_id=candidate_id,
                incumbent_id=incumbent.incumbent_id if incumbent else None,
                verdict=ModelAssuranceVerdict.REJECT,
                utility_score=0.0,
                incumbent_utility=None,
                axis_scores=candidate_scores,
                floor_violations=violations,
                provenance_multiplier=provenance_multiplier,
                rejection_reason="floor_violation",
            )

        candidate_utility = _utility(
            {s.axis: s.score for s in candidate_scores},
            self._weights,
            provenance_multiplier,
        )

        if incumbent is None:
            # First-ever evaluation: no comparison anchor exists. Per
            # ADR-088 §Stage 8 every model swap requires HITL anyway,
            # but here we surface a distinct verdict so the downstream
            # report flags the missing baseline explicitly.
            return ModelAssuranceResult(
                candidate_id=candidate_id,
                incumbent_id=None,
                verdict=ModelAssuranceVerdict.NO_INCUMBENT_HITL,
                utility_score=candidate_utility,
                incumbent_utility=None,
                axis_scores=candidate_scores,
                floor_violations=violations,
                provenance_multiplier=provenance_multiplier,
                rejection_reason=None,
            )

        # Compute the incumbent's utility under the same weights and the
        # same provenance multiplier (the incumbent is presumed trusted —
        # callers with stricter trust models can supply a separate
        # comparable baseline). Incumbent axis_scores are keyed by
        # whatever the caller built — convert to ModelAssuranceAxis
        # where the key is a recognised string ID.
        incumbent_by_axis: dict[ModelAssuranceAxis, float] = {}
        for axis_id, score in incumbent.axis_scores:
            if not isinstance(axis_id, str):
                # Skip entries keyed by non-MA axes — incumbents shared
                # with CGE/DVE may carry both axis spaces.
                continue
            try:
                ma_axis = ModelAssuranceAxis(axis_id)
            except ValueError:
                continue
            if _is_finite(score):
                incumbent_by_axis[ma_axis] = float(score)

        incumbent_utility = _utility(
            incumbent_by_axis, self._weights, provenance_multiplier
        )

        if candidate_utility > incumbent_utility:
            verdict = ModelAssuranceVerdict.ACCEPT
            rejection_reason = None
        elif candidate_utility == incumbent_utility:
            # ADR-088 explicit: ties reject.
            verdict = ModelAssuranceVerdict.TIE_REJECT
            rejection_reason = "utility_tie_with_incumbent"
        else:
            verdict = ModelAssuranceVerdict.INFERIOR
            rejection_reason = "utility_below_incumbent"

        return ModelAssuranceResult(
            candidate_id=candidate_id,
            incumbent_id=incumbent.incumbent_id,
            verdict=verdict,
            utility_score=candidate_utility,
            incumbent_utility=incumbent_utility,
            axis_scores=candidate_scores,
            floor_violations=violations,
            provenance_multiplier=provenance_multiplier,
            rejection_reason=rejection_reason,
        )


def make_incumbent(
    incumbent_id: str,
    axis_scores: Mapping[ModelAssuranceAxis, float],
) -> IncumbentBaseline:
    """Convenience constructor — saves callers from string-axis plumbing."""
    return IncumbentBaseline(
        incumbent_id=incumbent_id,
        axis_scores=tuple((ax.value, float(score)) for ax, score in axis_scores.items()),
    )


def perfect_axis_scores(score: float = 1.0) -> tuple[AxisScore, ...]:
    """Helper: a full axis score tuple at the same value across all 6 axes."""
    return tuple(AxisScore(axis=d.axis, score=score) for d in AXIS_DEFINITIONS)
