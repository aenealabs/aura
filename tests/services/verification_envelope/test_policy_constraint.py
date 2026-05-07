"""Tests for the CGE PolicyConstraint mechanism (ADR-085 Phase 4)."""

from __future__ import annotations

import pytest

from src.services.constraint_geometry.contracts import (
    CoherenceAction,
    ConstraintAxis,
    PolicyConstraint,
    PolicyConstraintType,
)
from src.services.constraint_geometry.policy_profile import (
    PROFILE_DEFAULT,
    PROFILE_DO178C_DAL_A,
    PROFILE_DO178C_DAL_B,
    PolicyProfile,
    PolicyProfileManager,
    PolicyThresholds,
)


def test_policy_constraint_is_hashable() -> None:
    """Frozen dataclasses with tuple parameters must be hashable for caching."""
    pc = PolicyConstraint(
        constraint_id="x",
        name="x",
        description="x",
        type=PolicyConstraintType.MCDC_COVERAGE_REQUIRED,
        parameters=(("min_pct", 100.0),),
    )
    assert hash(pc)


def test_parameters_dict_returns_dict_view() -> None:
    pc = PolicyConstraint(
        constraint_id="x",
        name="x",
        description="x",
        type=PolicyConstraintType.MCDC_COVERAGE_REQUIRED,
        parameters=(("min_pct", 100.0), ("policy", "dal_a")),
    )
    assert pc.parameters_dict == {"min_pct": 100.0, "policy": "dal_a"}


def test_dal_a_profile_registered_with_six_constraints() -> None:
    m = PolicyProfileManager()
    p = m.get("do-178c-dal-a")
    assert len(p.policy_constraints) == 6


def test_dal_b_profile_lacks_object_code_constraint() -> None:
    """The principal difference between DAL A and DAL B."""
    a_types = {c.type for c in PROFILE_DO178C_DAL_A.policy_constraints}
    b_types = {c.type for c in PROFILE_DO178C_DAL_B.policy_constraints}
    assert PolicyConstraintType.OBJECT_CODE_VERIFICATION_REQUIRED in a_types
    assert PolicyConstraintType.OBJECT_CODE_VERIFICATION_REQUIRED not in b_types


def test_get_policy_constraints_by_type_filters() -> None:
    p = PROFILE_DO178C_DAL_A
    mcdc = p.get_policy_constraints_by_type(PolicyConstraintType.MCDC_COVERAGE_REQUIRED)
    assert len(mcdc) == 1
    assert mcdc[0].constraint_id == "dal-a-mcdc-100"


def test_violation_forces_reject() -> None:
    p = PROFILE_DO178C_DAL_A
    action = p.determine_action(
        ccs=0.99, policy_constraint_violations=("dal-a-mcdc-100",)
    )
    assert action == CoherenceAction.REJECT


def test_clean_input_routes_by_score_alone() -> None:
    p = PROFILE_DO178C_DAL_A
    auto = p.determine_action(ccs=0.99)
    assert auto == CoherenceAction.AUTO_EXECUTE
    review = p.determine_action(ccs=0.86)
    assert review == CoherenceAction.HUMAN_REVIEW


def test_default_profile_unaffected_by_policy_constraints_default() -> None:
    """Profiles created without policy_constraints behave as before."""
    assert PROFILE_DEFAULT.policy_constraints == ()
    assert PROFILE_DEFAULT.determine_action(ccs=0.85) == CoherenceAction.AUTO_EXECUTE


def test_custom_profile_can_register_with_policy_constraints() -> None:
    custom_pc = PolicyConstraint(
        constraint_id="custom-1",
        name="Custom",
        description="Test policy constraint",
        type=PolicyConstraintType.MCDC_COVERAGE_REQUIRED,
        parameters=(("min_pct", 90.0),),
    )
    custom = PolicyProfile(
        name="custom-test-profile",
        description="test",
        axis_weights={ConstraintAxis.SECURITY_POLICY: 1.0},
        thresholds=PolicyThresholds(),
        policy_constraints=(custom_pc,),
    )
    m = PolicyProfileManager()
    m.register(custom)
    assert m.get("custom-test-profile").policy_constraints == (custom_pc,)


def test_dal_a_threshold_is_higher_than_dal_b() -> None:
    """Reflects the increased rigor of catastrophic-failure software."""
    assert (
        PROFILE_DO178C_DAL_A.thresholds.auto_execute_threshold
        > PROFILE_DO178C_DAL_B.thresholds.auto_execute_threshold
    )


def test_unique_constraint_ids_within_profile() -> None:
    for profile in (PROFILE_DO178C_DAL_A, PROFILE_DO178C_DAL_B):
        ids = [c.constraint_id for c in profile.policy_constraints]
        assert len(ids) == len(set(ids))


def test_policy_constraint_type_values_exhaustive() -> None:
    """The DO-178C cert argument relies on all six constraint types."""
    expected = {
        "mcdc_coverage_required",
        "decision_coverage_required",
        "statement_coverage_required",
        "formal_proof_required",
        "object_code_verification_required",
        "requirements_traceability_required",
    }
    actual = {t.value for t in PolicyConstraintType}
    assert expected == actual
