"""Tests for GoldenTestSet (ADR-088 Phase 2.2)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    DOMAIN_MINIMUMS,
    GOLDEN_SET_MINIMUM,
    GoldenSetIntegrityError,
    GoldenTestCase,
    GoldenTestSet,
    TestCaseDomain,
    build_test_set,
)


# ----------------------------------------------------- helpers


def _case(
    case_id: str,
    domain: TestCaseDomain,
    axis: ModelAssuranceAxis = ModelAssuranceAxis.CODE_COMPREHENSION,
) -> GoldenTestCase:
    return GoldenTestCase(
        case_id=case_id,
        domain=domain,
        title=case_id,
        description="t",
        axes=(axis,),
    )


def _full_minimum_set() -> GoldenTestSet:
    """Build a minimum-viable golden set (exactly 400 cases)."""
    cases: list[GoldenTestCase] = []
    domain_axis_map = {
        TestCaseDomain.VULNERABILITY_DETECTION:
            ModelAssuranceAxis.VULNERABILITY_DETECTION_RECALL,
        TestCaseDomain.PATCH_CORRECTNESS:
            ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS,
        TestCaseDomain.FALSE_POSITIVE: ModelAssuranceAxis.GUARDRAIL_COMPLIANCE,
        TestCaseDomain.REGRESSION: ModelAssuranceAxis.CODE_COMPREHENSION,
    }
    for domain, n in DOMAIN_MINIMUMS.items():
        axis = domain_axis_map[domain]
        for i in range(n):
            cases.append(_case(f"{domain.value}-{i:04d}", domain, axis))
    return GoldenTestSet(cases=tuple(cases), version="2026.05.0")


# ----------------------------------------------------- construction


class TestConstruction:
    def test_empty_set_rejected(self) -> None:
        with pytest.raises(GoldenSetIntegrityError, match="at least one"):
            GoldenTestSet(cases=())

    def test_duplicate_case_ids_rejected(self) -> None:
        cases = (
            _case("dup", TestCaseDomain.VULNERABILITY_DETECTION),
            _case("dup", TestCaseDomain.PATCH_CORRECTNESS),
        )
        with pytest.raises(GoldenSetIntegrityError, match="duplicate"):
            GoldenTestSet(cases=cases)

    def test_per_domain_index_built(self) -> None:
        s = _full_minimum_set()
        assert (
            len(s.by_domain(TestCaseDomain.VULNERABILITY_DETECTION))
            == DOMAIN_MINIMUMS[TestCaseDomain.VULNERABILITY_DETECTION]
        )

    def test_case_ids_property(self) -> None:
        s = _full_minimum_set()
        assert len(s.case_ids) == GOLDEN_SET_MINIMUM


# ----------------------------------------------------- minima


class TestValidateMinimums:
    def test_full_minimum_set_passes(self) -> None:
        _full_minimum_set().validate_minimums()

    def test_below_total_minimum_rejected(self) -> None:
        cases = tuple(
            _case(f"x{i:03d}", TestCaseDomain.VULNERABILITY_DETECTION)
            for i in range(150)
        )
        s = GoldenTestSet(cases=cases)
        with pytest.raises(GoldenSetIntegrityError, match="below minimum"):
            s.validate_minimums()

    def test_below_per_domain_minimum_rejected(self) -> None:
        # Total > 400 but FALSE_POSITIVE shy of its 100-case minimum.
        cases: list[GoldenTestCase] = []
        for i in range(200):
            cases.append(_case(
                f"vd-{i:04d}", TestCaseDomain.VULNERABILITY_DETECTION,
            ))
        for i in range(120):
            cases.append(_case(f"pc-{i:04d}", TestCaseDomain.PATCH_CORRECTNESS))
        for i in range(50):
            cases.append(_case(f"fp-{i:03d}", TestCaseDomain.FALSE_POSITIVE))
        for i in range(60):
            cases.append(_case(f"reg-{i:03d}", TestCaseDomain.REGRESSION))
        s = GoldenTestSet(cases=tuple(cases))
        with pytest.raises(GoldenSetIntegrityError, match="false_positive"):
            s.validate_minimums()


# ----------------------------------------------------- holdout


class TestHoldoutSampling:
    def test_invalid_rate_rejected(self) -> None:
        s = _full_minimum_set()
        with pytest.raises(ValueError):
            s.holdout_sample(rate=0.6, seed=1)
        with pytest.raises(ValueError):
            s.holdout_sample(rate=-0.1, seed=1)

    def test_zero_rate_no_holdout(self) -> None:
        s = _full_minimum_set()
        held, eval_ = s.holdout_sample(rate=0.0, seed=1)
        assert held == ()
        assert len(eval_) == GOLDEN_SET_MINIMUM

    def test_holdout_is_balanced_per_domain(self) -> None:
        """20% withheld from EACH domain rather than 20% globally."""
        s = _full_minimum_set()
        held, eval_ = s.holdout_sample(rate=0.20, seed=42)
        # 20% of 150 = 30, of 100 = 20, of 100 = 20, of 50 = 10
        # Total ~ 80 held, 320 evaluated (per-domain rounding may shift by 1)
        held_set = set(held)
        for domain in TestCaseDomain:
            domain_cases = s.by_domain(domain)
            n_held_domain = sum(1 for c in domain_cases if c.case_id in held_set)
            expected = int(round(len(domain_cases) * 0.20))
            assert n_held_domain == expected

    def test_holdout_is_deterministic_in_seed(self) -> None:
        s = _full_minimum_set()
        a, _ = s.holdout_sample(rate=0.20, seed=42)
        b, _ = s.holdout_sample(rate=0.20, seed=42)
        assert a == b

    def test_holdout_changes_with_seed(self) -> None:
        s = _full_minimum_set()
        a, _ = s.holdout_sample(rate=0.20, seed=1)
        b, _ = s.holdout_sample(rate=0.20, seed=2)
        assert a != b

    def test_holdout_disjoint_from_evaluation(self) -> None:
        s = _full_minimum_set()
        held, eval_ = s.holdout_sample(rate=0.20, seed=1)
        held_set = set(held)
        for c in eval_:
            assert c.case_id not in held_set


class TestBuildTestSet:
    def test_build_from_iterable(self) -> None:
        cases = (
            _case("c1", TestCaseDomain.VULNERABILITY_DETECTION),
            _case("c2", TestCaseDomain.PATCH_CORRECTNESS),
        )
        s = build_test_set(iter(cases), version="0.1")
        assert len(s) == 2
        assert s.version == "0.1"
