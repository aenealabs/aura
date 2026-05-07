"""Tests for the CGE regression floor primitive (ADR-088 Phase 1.1).

These tests cover the behavioural contract documented in
``regression_floor.evaluate_floors``: per-axis hard floors, ABSOLUTE
vs RELATIVE_TO_INCUMBENT comparison, missing-axis / NaN handling,
QUARANTINE_FLAG semantics, no-incumbent degradation, and the wiring
into ``PolicyProfile.determine_action``.
"""

from __future__ import annotations

import math

import pytest

from src.services.constraint_geometry.contracts import (
    AxisCoherenceScore,
    CoherenceAction,
    ConstraintAxis,
    PolicyConstraint,
    PolicyConstraintType,
    RegressionFloor,
    RegressionFloorAction,
    RegressionFloorComparisonMode,
    RegressionFloorViolation,
)
from src.services.constraint_geometry.policy_profile import (
    PolicyProfile,
    PolicyThresholds,
)
from src.services.constraint_geometry.regression_floor import (
    IncumbentBaseline,
    evaluate_floors,
    violations_force_reject,
)


# ---------------------------------------------------------------- helpers


def _floor(
    axis: ConstraintAxis = ConstraintAxis.SECURITY_POLICY,
    threshold: float = 0.92,
    floor_id: str = "f1",
    comparison: RegressionFloorComparisonMode = RegressionFloorComparisonMode.ABSOLUTE,
    action: RegressionFloorAction = RegressionFloorAction.REJECT,
) -> RegressionFloor:
    return RegressionFloor(
        floor_id=floor_id,
        name=floor_id,
        description="test floor",
        axis=axis,
        threshold=threshold,
        comparison=comparison,
        action=action,
    )


def _axis_score(axis: ConstraintAxis, score: float) -> AxisCoherenceScore:
    return AxisCoherenceScore(
        axis=axis,
        score=score,
        weight=1.0,
        weighted_score=score,
        contributing_rules=(),
        rule_scores=(),
    )


# ------------------------------------------------------ contract tests


class TestRegressionFloorContract:
    def test_threshold_must_be_in_unit_interval(self) -> None:
        with pytest.raises(ValueError, match="threshold"):
            RegressionFloor(
                floor_id="bad",
                name="bad",
                description="bad",
                axis=ConstraintAxis.SECURITY_POLICY,
                threshold=1.5,
            )
        with pytest.raises(ValueError, match="threshold"):
            RegressionFloor(
                floor_id="bad",
                name="bad",
                description="bad",
                axis=ConstraintAxis.SECURITY_POLICY,
                threshold=-0.1,
            )

    def test_threshold_zero_and_one_accepted(self) -> None:
        for t in (0.0, 0.5, 1.0):
            f = RegressionFloor(
                floor_id="ok",
                name="ok",
                description="ok",
                axis=ConstraintAxis.SECURITY_POLICY,
                threshold=t,
            )
            assert f.threshold == t

    def test_default_comparison_is_absolute(self) -> None:
        f = _floor()
        assert f.comparison is RegressionFloorComparisonMode.ABSOLUTE

    def test_default_action_is_reject(self) -> None:
        f = _floor()
        assert f.action is RegressionFloorAction.REJECT

    def test_floor_is_frozen(self) -> None:
        f = _floor()
        with pytest.raises((AttributeError, TypeError)):
            f.threshold = 0.5  # type: ignore[misc]


# ------------------------------------------------------ absolute mode


class TestAbsoluteMode:
    def test_score_above_threshold_passes(self) -> None:
        floors = [_floor(threshold=0.92)]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.95}
        assert evaluate_floors(floors, scores) == ()

    def test_score_at_threshold_passes_boundary(self) -> None:
        """Boundary case from issue #110: floor exactly at threshold is a pass."""
        floors = [_floor(threshold=0.92)]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.92}
        assert evaluate_floors(floors, scores) == ()

    def test_score_below_threshold_violates(self) -> None:
        floors = [_floor(threshold=0.92)]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.91}
        violations = evaluate_floors(floors, scores)
        assert len(violations) == 1
        assert violations[0].floor_id == "f1"
        assert violations[0].candidate_score == 0.91
        assert violations[0].effective_threshold == 0.92

    def test_score_just_below_threshold_violates(self) -> None:
        floors = [_floor(threshold=0.92)]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.9199999}
        violations = evaluate_floors(floors, scores)
        assert len(violations) == 1

    def test_axis_score_object_input_works(self) -> None:
        """Coherence calculator output (AxisCoherenceScore) should work."""
        floors = [_floor(threshold=0.92)]
        scores = {ConstraintAxis.SECURITY_POLICY: _axis_score(
            ConstraintAxis.SECURITY_POLICY, 0.95
        )}
        assert evaluate_floors(floors, scores) == ()


# -------------------------------------------------------- relative mode


class TestRelativeMode:
    def test_passes_when_above_relative_threshold(self) -> None:
        floors = [_floor(
            threshold=0.70,
            comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
        )]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.71}
        incumbent = IncumbentBaseline(
            incumbent_id="claude-3.5",
            axis_scores=((ConstraintAxis.SECURITY_POLICY, 1.0),),
        )
        assert evaluate_floors(floors, scores, incumbent=incumbent) == ()

    def test_fails_when_below_relative_threshold(self) -> None:
        floors = [_floor(
            threshold=0.70,
            comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
        )]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.65}
        incumbent = IncumbentBaseline(
            incumbent_id="claude-3.5",
            axis_scores=((ConstraintAxis.SECURITY_POLICY, 1.0),),
        )
        violations = evaluate_floors(floors, scores, incumbent=incumbent)
        assert len(violations) == 1
        assert violations[0].effective_threshold == pytest.approx(0.70)
        assert violations[0].incumbent_score == 1.0

    def test_relative_threshold_scales_with_incumbent(self) -> None:
        """0.70 threshold against incumbent=0.50 means effective floor = 0.35."""
        floors = [_floor(
            threshold=0.70,
            comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
        )]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.40}  # above 0.35
        incumbent = IncumbentBaseline(
            incumbent_id="weak-incumbent",
            axis_scores=((ConstraintAxis.SECURITY_POLICY, 0.50),),
        )
        assert evaluate_floors(floors, scores, incumbent=incumbent) == ()

    def test_no_incumbent_relative_passes(self) -> None:
        """Per ADR-088 issue #110: first-ever evaluation has no baseline."""
        floors = [_floor(
            threshold=0.70,
            comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
        )]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.50}  # would fail vs absolute 0.70
        assert evaluate_floors(floors, scores, incumbent=None) == ()

    def test_no_incumbent_axis_relative_passes(self) -> None:
        """Incumbent supplied but missing this axis — same degraded behaviour."""
        floors = [_floor(
            axis=ConstraintAxis.SECURITY_POLICY,
            threshold=0.70,
            comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
        )]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.50}
        incumbent = IncumbentBaseline(
            incumbent_id="missing-axis",
            axis_scores=((ConstraintAxis.OPERATIONAL_BOUNDS, 0.9),),
        )
        assert evaluate_floors(floors, scores, incumbent=incumbent) == ()

    def test_relative_zero_incumbent_yields_zero_floor(self) -> None:
        """Edge: incumbent=0 means effective floor = 0, candidate always passes."""
        floors = [_floor(
            threshold=0.70,
            comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
        )]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.0}
        incumbent = IncumbentBaseline(
            incumbent_id="zero",
            axis_scores=((ConstraintAxis.SECURITY_POLICY, 0.0),),
        )
        assert evaluate_floors(floors, scores, incumbent=incumbent) == ()

    def test_violation_records_incumbent_score(self) -> None:
        floors = [_floor(
            threshold=0.70,
            comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
        )]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.10}
        incumbent = IncumbentBaseline(
            incumbent_id="strong",
            axis_scores=((ConstraintAxis.SECURITY_POLICY, 0.95),),
        )
        violations = evaluate_floors(floors, scores, incumbent=incumbent)
        assert len(violations) == 1
        assert violations[0].incumbent_score == 0.95


# ------------------------------------------------- missing axis / NaN


class TestMissingOrInvalidScores:
    def test_missing_axis_violates(self) -> None:
        """A floor on an axis with no candidate score is a violation, not a pass."""
        floors = [_floor(axis=ConstraintAxis.SECURITY_POLICY)]
        scores: dict = {}
        violations = evaluate_floors(floors, scores)
        assert len(violations) == 1
        assert math.isnan(violations[0].candidate_score)

    def test_nan_score_violates(self) -> None:
        floors = [_floor(threshold=0.5)]
        scores = {ConstraintAxis.SECURITY_POLICY: float("nan")}
        violations = evaluate_floors(floors, scores)
        assert len(violations) == 1

    def test_inf_score_violates(self) -> None:
        floors = [_floor(threshold=0.5)]
        scores = {ConstraintAxis.SECURITY_POLICY: float("inf")}
        violations = evaluate_floors(floors, scores)
        # +inf is treated as malformed — see _is_finite
        assert len(violations) == 1

    def test_negative_inf_violates(self) -> None:
        floors = [_floor(threshold=0.0)]
        scores = {ConstraintAxis.SECURITY_POLICY: float("-inf")}
        violations = evaluate_floors(floors, scores)
        assert len(violations) == 1


# --------------------------------------------------- multi-floor compositions


class TestMultipleFloors:
    def test_independent_floors_independent_outcomes(self) -> None:
        floors = [
            _floor(floor_id="sec", axis=ConstraintAxis.SECURITY_POLICY, threshold=0.9),
            _floor(floor_id="ops", axis=ConstraintAxis.OPERATIONAL_BOUNDS, threshold=0.8),
        ]
        scores = {
            ConstraintAxis.SECURITY_POLICY: 0.95,
            ConstraintAxis.OPERATIONAL_BOUNDS: 0.70,
        }
        violations = evaluate_floors(floors, scores)
        assert [v.floor_id for v in violations] == ["ops"]

    def test_two_floors_on_same_axis_evaluated_independently(self) -> None:
        floors = [
            _floor(floor_id="lo", axis=ConstraintAxis.SECURITY_POLICY, threshold=0.5),
            _floor(floor_id="hi", axis=ConstraintAxis.SECURITY_POLICY, threshold=0.95),
        ]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.7}
        violations = evaluate_floors(floors, scores)
        assert [v.floor_id for v in violations] == ["hi"]

    def test_mix_absolute_and_relative_floors(self) -> None:
        floors = [
            _floor(
                floor_id="abs",
                axis=ConstraintAxis.SECURITY_POLICY,
                threshold=0.92,
                comparison=RegressionFloorComparisonMode.ABSOLUTE,
            ),
            _floor(
                floor_id="rel",
                axis=ConstraintAxis.OPERATIONAL_BOUNDS,
                threshold=0.70,
                comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
            ),
        ]
        scores = {
            ConstraintAxis.SECURITY_POLICY: 0.95,
            ConstraintAxis.OPERATIONAL_BOUNDS: 0.50,
        }
        incumbent = IncumbentBaseline(
            incumbent_id="i",
            axis_scores=(
                (ConstraintAxis.SECURITY_POLICY, 0.99),
                (ConstraintAxis.OPERATIONAL_BOUNDS, 1.0),
            ),
        )
        violations = evaluate_floors(floors, scores, incumbent=incumbent)
        # absolute: 0.95 >= 0.92 → pass; relative: 0.50 vs 0.70*1.0=0.70 → fail
        assert [v.floor_id for v in violations] == ["rel"]


# ---------------------------------------------------- action semantics


class TestQuarantineFlagAction:
    def test_quarantine_floor_records_violation_but_does_not_force_reject(self) -> None:
        floors = [
            _floor(
                floor_id="soft",
                axis=ConstraintAxis.SECURITY_POLICY,
                threshold=0.95,
                action=RegressionFloorAction.QUARANTINE_FLAG,
            ),
        ]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.80}
        violations = evaluate_floors(floors, scores)
        assert len(violations) == 1
        assert violations[0].action is RegressionFloorAction.QUARANTINE_FLAG
        assert not violations_force_reject(violations)

    def test_reject_dominates_quarantine_in_force_reject_check(self) -> None:
        violations = (
            RegressionFloorViolation(
                floor_id="soft",
                axis=ConstraintAxis.SECURITY_POLICY,
                candidate_score=0.5,
                threshold=0.6,
                effective_threshold=0.6,
                incumbent_score=None,
                comparison=RegressionFloorComparisonMode.ABSOLUTE,
                action=RegressionFloorAction.QUARANTINE_FLAG,
            ),
            RegressionFloorViolation(
                floor_id="hard",
                axis=ConstraintAxis.OPERATIONAL_BOUNDS,
                candidate_score=0.1,
                threshold=0.9,
                effective_threshold=0.9,
                incumbent_score=None,
                comparison=RegressionFloorComparisonMode.ABSOLUTE,
                action=RegressionFloorAction.REJECT,
            ),
        )
        assert violations_force_reject(violations) is True

    def test_empty_violations_does_not_force_reject(self) -> None:
        assert violations_force_reject(()) is False


# ---------------------------------------------- IncumbentBaseline contract


class TestIncumbentBaseline:
    def test_finite_score_required(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            IncumbentBaseline(
                incumbent_id="bad",
                axis_scores=((ConstraintAxis.SECURITY_POLICY, float("nan")),),
            )

    def test_axis_must_be_constraint_axis_enum(self) -> None:
        with pytest.raises(TypeError, match="ConstraintAxis"):
            IncumbentBaseline(
                incumbent_id="bad",
                axis_scores=(("C3", 0.5),),  # type: ignore[arg-type]
            )

    def test_get_returns_none_for_missing_axis(self) -> None:
        b = IncumbentBaseline(
            incumbent_id="x",
            axis_scores=((ConstraintAxis.SECURITY_POLICY, 0.9),),
        )
        assert b.get(ConstraintAxis.OPERATIONAL_BOUNDS) is None
        assert b.get(ConstraintAxis.SECURITY_POLICY) == 0.9


# --------------------------------------- PolicyProfile integration


class TestPolicyProfileIntegration:
    def _profile(self, floors: tuple[RegressionFloor, ...]) -> PolicyProfile:
        return PolicyProfile(
            name="t",
            description="t",
            axis_weights={a: 1.0 for a in ConstraintAxis},
            thresholds=PolicyThresholds(),
            regression_floors=floors,
        )

    def test_profile_carries_floors(self) -> None:
        floors = (_floor(),)
        p = self._profile(floors)
        assert p.regression_floors == floors

    def test_profile_default_no_floors(self) -> None:
        p = PolicyProfile(
            name="t",
            description="t",
            axis_weights={a: 1.0 for a in ConstraintAxis},
            thresholds=PolicyThresholds(),
        )
        assert p.regression_floors == ()

    def test_floor_violation_forces_reject(self) -> None:
        p = self._profile((_floor(),))
        action = p.determine_action(
            ccs=0.99,
            regression_floor_violations_reject=True,
        )
        assert action is CoherenceAction.REJECT

    def test_no_floor_violation_uses_thresholds(self) -> None:
        p = self._profile((_floor(),))
        action = p.determine_action(
            ccs=0.99,
            regression_floor_violations_reject=False,
        )
        assert action is CoherenceAction.AUTO_EXECUTE

    def test_floor_violation_dominates_high_ccs(self) -> None:
        """Floor-violation REJECT must short-circuit even on max CCS."""
        p = self._profile((_floor(),))
        action = p.determine_action(
            ccs=1.0,
            regression_floor_violations_reject=True,
        )
        assert action is CoherenceAction.REJECT

    def test_policy_constraint_violation_still_forces_reject(self) -> None:
        """Existing ADR-085 path is unchanged."""
        p = self._profile(())
        action = p.determine_action(
            ccs=1.0,
            policy_constraint_violations=("dal-a-mcdc",),
        )
        assert action is CoherenceAction.REJECT

    def test_either_violation_path_forces_reject(self) -> None:
        p = self._profile((_floor(),))
        action = p.determine_action(
            ccs=1.0,
            policy_constraint_violations=("any",),
            regression_floor_violations_reject=False,
        )
        assert action is CoherenceAction.REJECT


# --------------------------------------------- audit serialization


class TestAuditSerialization:
    def test_violation_to_audit_dict_has_all_fields(self) -> None:
        v = RegressionFloorViolation(
            floor_id="f",
            axis=ConstraintAxis.SECURITY_POLICY,
            candidate_score=0.123456789,
            threshold=0.5,
            effective_threshold=0.4,
            incumbent_score=0.8,
            comparison=RegressionFloorComparisonMode.RELATIVE_TO_INCUMBENT,
            action=RegressionFloorAction.REJECT,
        )
        d = v.to_audit_dict()
        assert d["floor_id"] == "f"
        assert d["axis"] == "C3"
        assert d["candidate_score"] == round(0.123456789, 6)
        assert d["threshold"] == 0.5
        assert d["effective_threshold"] == 0.4
        assert d["incumbent_score"] == 0.8
        assert d["comparison"] == "relative_to_incumbent"
        assert d["action"] == "reject"

    def test_violation_audit_dict_handles_none_incumbent(self) -> None:
        v = RegressionFloorViolation(
            floor_id="f",
            axis=ConstraintAxis.SECURITY_POLICY,
            candidate_score=0.5,
            threshold=0.7,
            effective_threshold=0.7,
            incumbent_score=None,
            comparison=RegressionFloorComparisonMode.ABSOLUTE,
            action=RegressionFloorAction.REJECT,
        )
        d = v.to_audit_dict()
        assert d["incumbent_score"] is None


# ----------------------------------------------------- determinism


class TestDeterminism:
    def test_evaluate_is_pure(self) -> None:
        """Same inputs produce the same output — no hidden state."""
        floors = [_floor(threshold=0.7), _floor(floor_id="f2", threshold=0.5)]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.6}
        a = evaluate_floors(floors, scores)
        b = evaluate_floors(floors, scores)
        c = evaluate_floors(floors, scores)
        assert a == b == c

    def test_violation_order_matches_floor_order(self) -> None:
        floors = [
            _floor(floor_id="z", axis=ConstraintAxis.OPERATIONAL_BOUNDS, threshold=0.9),
            _floor(floor_id="a", axis=ConstraintAxis.SECURITY_POLICY, threshold=0.9),
        ]
        scores = {
            ConstraintAxis.SECURITY_POLICY: 0.0,
            ConstraintAxis.OPERATIONAL_BOUNDS: 0.0,
        }
        violations = evaluate_floors(floors, scores)
        # First-declared first — not alphabetical.
        assert [v.floor_id for v in violations] == ["z", "a"]


# -------------------------------- cross-domain reuse (ADR-085 / ADR-088)


class TestCrossDomainReuse:
    """Floor primitive should serve any CGE consumer, per ADR-088 condition #4."""

    def test_floor_works_for_dal_a_style_axis_minimum(self) -> None:
        # ADR-085 DAL-A could express "C2 score >= 0.99 or REJECT" via a floor
        floors = [_floor(
            axis=ConstraintAxis.SEMANTIC_CORRECTNESS,
            threshold=0.99,
        )]
        passing = {ConstraintAxis.SEMANTIC_CORRECTNESS: 0.995}
        failing = {ConstraintAxis.SEMANTIC_CORRECTNESS: 0.989}
        assert evaluate_floors(floors, passing) == ()
        assert len(evaluate_floors(floors, failing)) == 1

    def test_floor_works_for_model_assurance_style_recall_floor(self) -> None:
        # ADR-088 A2 vulnerability detection recall floor
        floors = [_floor(
            floor_id="vuln-recall",
            axis=ConstraintAxis.SECURITY_POLICY,
            threshold=0.92,
        )]
        scores = {ConstraintAxis.SECURITY_POLICY: 0.91}
        violations = evaluate_floors(floors, scores)
        assert len(violations) == 1
        assert violations[0].floor_id == "vuln-recall"


# ------------------------------------- guard against silent regression


class TestRegressionGuards:
    def test_existing_policy_constraint_path_not_broken(self) -> None:
        """ADR-085 Phase 4 callers passing only policy_constraint_violations
        must still see REJECT. The new floor parameter is keyword-only with
        a False default, so existing call sites are unaffected."""
        p = PolicyProfile(
            name="t",
            description="t",
            axis_weights={a: 1.0 for a in ConstraintAxis},
            thresholds=PolicyThresholds(),
            policy_constraints=(
                PolicyConstraint(
                    constraint_id="dal-a-mcdc",
                    name="MC/DC",
                    description="100%",
                    type=PolicyConstraintType.MCDC_COVERAGE_REQUIRED,
                ),
            ),
        )
        # Existing call signature (no floor kwarg) still rejects.
        action = p.determine_action(
            ccs=1.0,
            policy_constraint_violations=("dal-a-mcdc",),
        )
        assert action is CoherenceAction.REJECT
