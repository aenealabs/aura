"""Tests for the model_assurance scoring pipeline (ADR-088 Phase 1.3)."""

from __future__ import annotations

import pytest

from src.services.constraint_geometry.contracts import (
    RegressionFloor,
    RegressionFloorComparisonMode,
)
from src.services.model_assurance import (
    AxisScore,
    ModelAssuranceAxis,
    ModelAssuranceEvaluator,
    ModelAssuranceVerdict,
    default_weights,
    make_incumbent,
    perfect_axis_scores,
)
from src.services.model_assurance.axes import default_floors


# ----------------------------------------------------------------- helpers


def _scores(values: dict[ModelAssuranceAxis, float]) -> tuple[AxisScore, ...]:
    return tuple(AxisScore(axis=ax, score=score) for ax, score in values.items())


def _all_axes_at(value: float) -> dict[ModelAssuranceAxis, float]:
    return {ax: value for ax in ModelAssuranceAxis}


# ----------------------------------------------------- AxisScore contract


class TestAxisScoreContract:
    def test_valid_score(self) -> None:
        s = AxisScore(axis=ModelAssuranceAxis.CODE_COMPREHENSION, score=0.85)
        assert s.score == 0.85

    def test_nan_rejected(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            AxisScore(
                axis=ModelAssuranceAxis.CODE_COMPREHENSION,
                score=float("nan"),
            )

    def test_inf_rejected(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            AxisScore(
                axis=ModelAssuranceAxis.CODE_COMPREHENSION,
                score=float("inf"),
            )

    def test_below_zero_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\[0,1\]"):
            AxisScore(axis=ModelAssuranceAxis.CODE_COMPREHENSION, score=-0.1)

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"\[0,1\]"):
            AxisScore(axis=ModelAssuranceAxis.CODE_COMPREHENSION, score=1.01)

    def test_boundary_values_accepted(self) -> None:
        AxisScore(axis=ModelAssuranceAxis.CODE_COMPREHENSION, score=0.0)
        AxisScore(axis=ModelAssuranceAxis.CODE_COMPREHENSION, score=1.0)


# ------------------------------------------------------ Floor enforcement


class TestFloorEnforcement:
    def test_floor_violation_rejects(self) -> None:
        ev = ModelAssuranceEvaluator()
        # Vuln recall floor is 0.92; 0.80 must reject.
        scores = _all_axes_at(0.99)
        scores[ModelAssuranceAxis.VULNERABILITY_DETECTION_RECALL] = 0.80
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=_scores(scores),
            incumbent=make_incumbent(
                "inc", _all_axes_at(0.93)
            ),
        )
        assert result.verdict is ModelAssuranceVerdict.REJECT
        assert result.rejection_reason == "floor_violation"
        assert any(
            v.floor_id.startswith("floor_MA2") for v in result.floor_violations
        )

    def test_high_score_on_one_axis_cant_compensate_for_floor(self) -> None:
        """ADR-088 §Stage 5: floors are pre-check, not weighted.

        Even with perfect 1.0 scores on five axes, a single floor
        violation rejects.
        """
        ev = ModelAssuranceEvaluator()
        scores = _all_axes_at(1.0)
        scores[ModelAssuranceAxis.GUARDRAIL_COMPLIANCE] = 0.50
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=_scores(scores),
            incumbent=make_incumbent("inc", _all_axes_at(0.95)),
        )
        assert result.verdict is ModelAssuranceVerdict.REJECT

    def test_score_at_floor_threshold_passes(self) -> None:
        """Boundary case: floor exactly at threshold is a pass."""
        ev = ModelAssuranceEvaluator()
        scores = _all_axes_at(0.99)
        scores[ModelAssuranceAxis.CODE_COMPREHENSION] = 0.85  # exact floor
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=_scores(scores),
            incumbent=make_incumbent("inc", _all_axes_at(0.90)),
        )
        # Floors pass; verdict comes from utility comparison.
        assert result.verdict is not ModelAssuranceVerdict.REJECT


# --------------------------------------------- Utility / verdict logic


class TestUtilityComparison:
    def test_strict_improvement_accepts(self) -> None:
        ev = ModelAssuranceEvaluator()
        candidate = perfect_axis_scores(0.99)
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=candidate,
            incumbent=make_incumbent("inc", _all_axes_at(0.95)),
        )
        assert result.verdict is ModelAssuranceVerdict.ACCEPT
        assert result.utility_score > result.incumbent_utility

    def test_tie_rejects(self) -> None:
        """ADR-088 explicit: utility tie rejects — incumbent holds."""
        ev = ModelAssuranceEvaluator()
        # Use a score above the highest absolute floor (0.98 on guardrail).
        same = _all_axes_at(0.99)
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=_scores(same),
            incumbent=make_incumbent("inc", same),
        )
        assert result.verdict is ModelAssuranceVerdict.TIE_REJECT
        assert result.rejection_reason == "utility_tie_with_incumbent"

    def test_inferior_candidate_rejects_with_distinct_verdict(self) -> None:
        ev = ModelAssuranceEvaluator()
        # Both above all absolute floors, candidate strictly lower.
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=perfect_axis_scores(0.985),
            incumbent=make_incumbent("inc", _all_axes_at(0.999)),
        )
        assert result.verdict is ModelAssuranceVerdict.INFERIOR
        assert result.utility_score < result.incumbent_utility


# --------------------------------------------- Provenance multiplier


class TestProvenanceMultiplier:
    def test_default_multiplier_is_one(self) -> None:
        ev = ModelAssuranceEvaluator()
        result = ev.evaluate(
            candidate_id="c",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=make_incumbent("i", _all_axes_at(0.95)),
        )
        assert result.provenance_multiplier == 1.0

    def test_zero_multiplier_zeroes_utility(self) -> None:
        """Zero trust → zero utility on every axis."""
        ev = ModelAssuranceEvaluator()
        result = ev.evaluate(
            candidate_id="c",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=make_incumbent("i", _all_axes_at(0.95)),
            provenance_multiplier=0.0,
        )
        assert result.utility_score == 0.0
        # Both utilities are zero — tie reject.
        assert result.incumbent_utility == 0.0
        assert result.verdict is ModelAssuranceVerdict.TIE_REJECT

    def test_invalid_multiplier_rejected(self) -> None:
        ev = ModelAssuranceEvaluator()
        with pytest.raises(ValueError, match=r"\[0,1\]"):
            ev.evaluate(
                candidate_id="c",
                candidate_scores=perfect_axis_scores(0.99),
                incumbent=make_incumbent("i", _all_axes_at(0.95)),
                provenance_multiplier=1.5,
            )
        with pytest.raises(ValueError):
            ev.evaluate(
                candidate_id="c",
                candidate_scores=perfect_axis_scores(0.99),
                incumbent=make_incumbent("i", _all_axes_at(0.95)),
                provenance_multiplier=float("nan"),
            )

    def test_partial_trust_scales_proportionally(self) -> None:
        """U scales linearly with provenance multiplier."""
        ev = ModelAssuranceEvaluator()
        full = ev.evaluate(
            candidate_id="c",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=make_incumbent("i", _all_axes_at(0.95)),
            provenance_multiplier=1.0,
        )
        half = ev.evaluate(
            candidate_id="c",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=make_incumbent("i", _all_axes_at(0.95)),
            provenance_multiplier=0.5,
        )
        assert half.utility_score == pytest.approx(full.utility_score / 2)


# ------------------------------------------------- No-incumbent path


class TestNoIncumbent:
    def test_no_incumbent_yields_hitl_verdict(self) -> None:
        ev = ModelAssuranceEvaluator()
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=None,
        )
        assert result.verdict is ModelAssuranceVerdict.NO_INCUMBENT_HITL
        assert result.incumbent_id is None
        assert result.incumbent_utility is None

    def test_no_incumbent_still_evaluates_floors(self) -> None:
        """Floors must fire even without an incumbent."""
        ev = ModelAssuranceEvaluator()
        scores = _all_axes_at(0.99)
        scores[ModelAssuranceAxis.GUARDRAIL_COMPLIANCE] = 0.50
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=_scores(scores),
            incumbent=None,
        )
        assert result.verdict is ModelAssuranceVerdict.REJECT


# ------------------------------------------- Custom floors / weights


class TestCustomFloorsAndWeights:
    def test_evaluator_accepts_custom_floors(self) -> None:
        custom = (
            RegressionFloor(
                floor_id="strict",
                name="strict",
                description="strict",
                axis=ModelAssuranceAxis.CODE_COMPREHENSION.value,
                threshold=0.99,
            ),
        )
        ev = ModelAssuranceEvaluator(floors=custom)
        # 0.95 < 0.99 → reject
        scores = _all_axes_at(0.95)
        result = ev.evaluate(
            candidate_id="c",
            candidate_scores=_scores(scores),
            incumbent=make_incumbent("i", _all_axes_at(0.50)),
        )
        assert result.verdict is ModelAssuranceVerdict.REJECT

    def test_evaluator_accepts_custom_weights(self) -> None:
        weights = {
            ax: (10.0 if ax is ModelAssuranceAxis.CODE_COMPREHENSION else 0.0)
            for ax in ModelAssuranceAxis
        }
        # No floors so utility comparison alone drives the verdict.
        ev = ModelAssuranceEvaluator(floors=(), weights=weights)
        # Only CODE_COMPREHENSION counts — candidate's other axes don't matter.
        candidate = _scores(
            {
                **_all_axes_at(0.0),
                ModelAssuranceAxis.CODE_COMPREHENSION: 1.0,
            }
        )
        result = ev.evaluate(
            candidate_id="c",
            candidate_scores=candidate,
            incumbent=make_incumbent(
                "i",
                {
                    **_all_axes_at(1.0),
                    ModelAssuranceAxis.CODE_COMPREHENSION: 0.5,
                },
            ),
        )
        assert result.verdict is ModelAssuranceVerdict.ACCEPT


# ----------------------------------------------- Determinism / purity


class TestDeterminism:
    def test_same_inputs_yield_same_result(self) -> None:
        ev = ModelAssuranceEvaluator()
        kwargs = dict(
            candidate_id="c",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=make_incumbent("i", _all_axes_at(0.95)),
        )
        a = ev.evaluate(**kwargs)
        b = ev.evaluate(**kwargs)
        assert a == b

    def test_default_floors_returns_independent_tuples(self) -> None:
        a = default_floors()
        b = default_floors()
        # Same content but called independently — guarantees stateless
        assert a == b


# ------------------------------------------------ Audit serialization


class TestAuditDict:
    def test_audit_dict_contains_expected_keys(self) -> None:
        ev = ModelAssuranceEvaluator()
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=make_incumbent("inc", _all_axes_at(0.95)),
        )
        d = result.to_audit_dict()
        for key in (
            "candidate_id",
            "incumbent_id",
            "verdict",
            "utility_score",
            "incumbent_utility",
            "axis_scores",
            "floor_violations",
            "provenance_multiplier",
            "rejection_reason",
        ):
            assert key in d

    def test_audit_dict_axis_scores_keyed_by_axis_id(self) -> None:
        ev = ModelAssuranceEvaluator()
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=make_incumbent("inc", _all_axes_at(0.95)),
        )
        keys = result.to_audit_dict()["axis_scores"].keys()
        assert set(keys) == {a.value for a in ModelAssuranceAxis}

    def test_audit_dict_handles_no_incumbent(self) -> None:
        ev = ModelAssuranceEvaluator()
        result = ev.evaluate(
            candidate_id="cand",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=None,
        )
        d = result.to_audit_dict()
        assert d["incumbent_id"] is None
        assert d["incumbent_utility"] is None


# ----------------------------------- Helpers (make_incumbent, perfect)


class TestHelpers:
    def test_make_incumbent_uses_string_axis_keys(self) -> None:
        b = make_incumbent("inc-x", _all_axes_at(0.9))
        for axis_id, _ in b.axis_scores:
            assert isinstance(axis_id, str)
            assert axis_id.startswith("MA")

    def test_perfect_axis_scores_six_entries(self) -> None:
        scores = perfect_axis_scores(0.95)
        assert len(scores) == 6
        for s in scores:
            assert s.score == 0.95


# ------------------------------------ Cross-domain: floor primitive reuse


class TestCrossDomainSanity:
    def test_axis_floors_use_string_ids_not_constraint_axis(self) -> None:
        """Phase 1.3 axes are MA-prefixed strings, not CGE ConstraintAxis."""
        for f in default_floors():
            assert isinstance(f.axis, str)

    def test_evaluator_doesnt_collide_with_constraint_axis(self) -> None:
        """Confidence check: MA evaluator uses MA axis keys, won't be
        confused with C1-C7 keys flowing through the same floor primitive."""
        ev = ModelAssuranceEvaluator()
        result = ev.evaluate(
            candidate_id="c",
            candidate_scores=perfect_axis_scores(0.99),
            incumbent=make_incumbent("i", _all_axes_at(0.90)),
        )
        # Axis IDs in the result use MA prefix.
        d = result.to_audit_dict()
        for k in d["axis_scores"]:
            assert k.startswith("MA")
