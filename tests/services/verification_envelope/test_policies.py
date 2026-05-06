"""Tests for the DO-178C DAL coverage policy stubs."""

from __future__ import annotations

import pytest

from src.services.verification_envelope.policies import (
    DAL_A_PROFILE_NAME,
    DAL_B_PROFILE_NAME,
    DEFAULT_PROFILE_NAME,
    get_coverage_policy,
)


def test_dal_a_requires_full_coverage_and_object_code() -> None:
    p = get_coverage_policy(DAL_A_PROFILE_NAME)
    assert p.statement_required_pct == 100.0
    assert p.decision_required_pct == 100.0
    assert p.mcdc_required_pct == 100.0
    assert p.requires_object_code_verification is True


def test_dal_b_drops_object_code_verification() -> None:
    p = get_coverage_policy(DAL_B_PROFILE_NAME)
    assert p.statement_required_pct == 100.0
    assert p.mcdc_required_pct == 100.0
    assert p.requires_object_code_verification is False


def test_default_preserves_70_percent_floor() -> None:
    p = get_coverage_policy(DEFAULT_PROFILE_NAME)
    assert p.statement_required_pct == 70.0
    assert p.mcdc_required_pct == 0.0


def test_unknown_profile_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        get_coverage_policy("does-not-exist")


def test_is_satisfied_evaluates_thresholds() -> None:
    p = get_coverage_policy(DAL_A_PROFILE_NAME)
    assert p.is_satisfied(100.0, 100.0, 100.0) is True
    assert p.is_satisfied(99.9, 100.0, 100.0) is False
    assert p.is_satisfied(100.0, 100.0, 99.99) is False
