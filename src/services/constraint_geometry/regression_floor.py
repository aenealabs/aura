"""Project Aura - Regression floor evaluator (ADR-088 Phase 1).

A regression floor is a per-axis hard minimum: if a candidate's score
on any covered axis falls below its threshold, the candidate is
rejected outright regardless of how strong its other axes are. The
floor primitive is intentionally domain-agnostic — ADR-088 model
assurance, ADR-085 DO-178C structural coverage gates, and any future
profile that needs hard per-axis minima all use the same evaluator.

Two comparison modes (see :class:`RegressionFloorComparisonMode`):

* **ABSOLUTE** — the threshold is the candidate's required score
  directly (e.g. ``threshold=0.92`` means the axis score must be
  >= 0.92).
* **RELATIVE_TO_INCUMBENT** — the threshold is a multiplier on the
  incumbent's score for the same axis (e.g. ``threshold=0.70`` means
  the candidate must score at least 70% of the incumbent's score).
  When no incumbent baseline is supplied, relative floors degrade to a
  no-op so that first-ever evaluations don't fail spuriously; this is
  a deliberate design choice — see ``test_no_incumbent_relative_passes``.

The evaluator is a pure function of its inputs (axis scores +
optional incumbent baseline + frozen floor list). It performs no I/O,
no logging at WARN/ERROR, and never raises on malformed scores —
malformed scores are deterministically treated as floor failures so a
NaN/None upstream cannot silently bypass a safety floor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping

from src.services.constraint_geometry.contracts import (
    AxisCoherenceScore,
    ConstraintAxis,
    RegressionFloor,
    RegressionFloorAction,
    RegressionFloorComparisonMode,
    RegressionFloorViolation,
)


@dataclass(frozen=True)
class IncumbentBaseline:
    """Per-axis incumbent scores used for RELATIVE-mode floor evaluation.

    Stored as a frozen dataclass so it can be safely passed across
    async boundaries and cached without defensive copies. ``axis_scores``
    is a frozen tuple-of-tuples (rather than a dict) because dicts are
    not hashable and floors are evaluated as part of the deterministic
    CGE pipeline.

    A baseline is **per-axis**. If a relative floor references an axis
    not present in the baseline, the floor degrades to a no-op for
    that evaluation (the same behavior as the no-baseline case). This
    matches the ADR-088 v1 expectation that incumbents introduced
    after the platform ships do not retroactively gate older axes.
    """

    incumbent_id: str
    axis_scores: tuple[tuple[ConstraintAxis, float], ...] = ()

    def __post_init__(self) -> None:
        for axis, score in self.axis_scores:
            if not isinstance(axis, ConstraintAxis):
                raise TypeError(
                    f"IncumbentBaseline.axis_scores entries must use ConstraintAxis "
                    f"keys; got {type(axis).__name__}"
                )
            if not _is_finite(score):
                raise ValueError(
                    f"IncumbentBaseline score for {axis.value} must be a finite "
                    f"number; got {score!r}"
                )

    def get(self, axis: ConstraintAxis) -> float | None:
        for ax, score in self.axis_scores:
            if ax is axis:
                return score
        return None


def _is_finite(value: float | int | None) -> bool:
    """True iff value is a real finite number — guards against NaN / inf."""
    if value is None:
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def _candidate_score_for(
    axis: ConstraintAxis,
    axis_scores: Mapping[ConstraintAxis, AxisCoherenceScore] | Mapping[ConstraintAxis, float],
) -> float | None:
    """Extract the candidate's raw score for ``axis``.

    Accepts either a mapping of ``ConstraintAxis -> AxisCoherenceScore``
    (the shape produced by the coherence calculator) or
    ``ConstraintAxis -> float`` (the simpler shape used by external
    pipelines like ADR-088 model assurance). Returns ``None`` when the
    axis is missing — caller decides what to do.
    """
    raw = axis_scores.get(axis)
    if raw is None:
        return None
    if isinstance(raw, AxisCoherenceScore):
        return raw.score
    return float(raw) if _is_finite(raw) else None


def evaluate_floors(
    floors: Iterable[RegressionFloor],
    axis_scores: Mapping[ConstraintAxis, AxisCoherenceScore]
    | Mapping[ConstraintAxis, float],
    *,
    incumbent: IncumbentBaseline | None = None,
) -> tuple[RegressionFloorViolation, ...]:
    """Evaluate every floor against the candidate's per-axis scores.

    Returns a tuple of violations in declaration order. An empty tuple
    means every floor passed (including no-ops). The evaluator is
    deterministic — same inputs produce the same output, every time.

    **Determinism guards:**

    * Missing-axis: if a candidate has no score on an axis covered by
      a floor, that's a floor violation. Treating missing as 0.0 would
      let a candidate that fails to evaluate on a safety axis silently
      slip through; explicit failure is the safer default.
    * NaN / non-finite candidate score: also a floor violation, by the
      same reasoning. NaN cannot satisfy any threshold meaningfully.
    * Missing incumbent for a relative floor: the floor degrades to a
      no-op (no violation reported). This is the intended path for
      first-ever evaluations where no baseline exists yet.
    """
    violations: list[RegressionFloorViolation] = []
    for floor in floors:
        candidate_score = _candidate_score_for(floor.axis, axis_scores)

        # Missing-axis or non-finite scores are deterministic failures
        # — see docstring for rationale.
        if candidate_score is None:
            violations.append(
                RegressionFloorViolation(
                    floor_id=floor.floor_id,
                    axis=floor.axis,
                    candidate_score=float("nan"),
                    threshold=floor.threshold,
                    effective_threshold=floor.threshold,
                    incumbent_score=None,
                    comparison=floor.comparison,
                    action=floor.action,
                )
            )
            continue

        if floor.comparison is RegressionFloorComparisonMode.ABSOLUTE:
            effective = floor.threshold
            incumbent_score: float | None = None
        else:
            # RELATIVE_TO_INCUMBENT
            incumbent_score = (
                incumbent.get(floor.axis) if incumbent is not None else None
            )
            if incumbent_score is None:
                # No-op: first evaluation, no relative anchor to compare against.
                continue
            effective = floor.threshold * incumbent_score

        # Boundary policy: candidate_score >= effective_threshold passes
        # (a score exactly at the threshold is not a violation). This
        # is the contract documented in tests/.../test_floor_boundary.
        if candidate_score < effective:
            violations.append(
                RegressionFloorViolation(
                    floor_id=floor.floor_id,
                    axis=floor.axis,
                    candidate_score=candidate_score,
                    threshold=floor.threshold,
                    effective_threshold=effective,
                    incumbent_score=incumbent_score,
                    comparison=floor.comparison,
                    action=floor.action,
                )
            )

    return tuple(violations)


def violations_force_reject(
    violations: Iterable[RegressionFloorViolation],
) -> bool:
    """True iff any violation has action=REJECT.

    QUARANTINE_FLAG violations are recorded but do not auto-override
    the action. Callers (PolicyProfile.determine_action, HITL UI) can
    inspect the violation list directly to decide soft escalation.
    """
    return any(v.action is RegressionFloorAction.REJECT for v in violations)
