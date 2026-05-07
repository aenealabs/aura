"""Tests for the spot-check sampler (ADR-088 Phase 3.1)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.anti_goodhart import (
    DEFAULT_SPOT_CHECK_RATE,
    build_sampling_plan,
)
from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    DOMAIN_MINIMUMS,
    GoldenTestCase,
    GoldenTestSet,
    TestCaseDomain,
)


def _case(
    case_id: str,
    domain: TestCaseDomain,
) -> GoldenTestCase:
    return GoldenTestCase(
        case_id=case_id,
        domain=domain,
        title="t",
        description="d",
        axes=(ModelAssuranceAxis.CODE_COMPREHENSION,),
    )


def _full_set() -> GoldenTestSet:
    cases: list[GoldenTestCase] = []
    for domain, n in DOMAIN_MINIMUMS.items():
        for i in range(n):
            cases.append(_case(f"{domain.value}-{i:04d}", domain))
    return GoldenTestSet(cases=tuple(cases), version="0.1")


class TestRateValidation:
    def test_default_rate_is_5pct(self) -> None:
        assert DEFAULT_SPOT_CHECK_RATE == 0.05

    def test_zero_rate_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_sampling_plan(_full_set(), seed=1, rate=0.0)

    def test_negative_rate_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_sampling_plan(_full_set(), seed=1, rate=-0.01)

    def test_above_50pct_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_sampling_plan(_full_set(), seed=1, rate=0.51)


class TestStratifiedSampling:
    def test_each_domain_represented(self) -> None:
        plan = build_sampling_plan(_full_set(), seed=42, rate=0.05)
        domains = {s.domain for s in plan.samples}
        assert domains == set(TestCaseDomain)

    def test_per_domain_counts_match_rate(self) -> None:
        plan = build_sampling_plan(_full_set(), seed=42, rate=0.10)
        per_domain: dict[TestCaseDomain, int] = {d: 0 for d in TestCaseDomain}
        for s in plan.samples:
            per_domain[s.domain] += 1
        for domain, n_total in DOMAIN_MINIMUMS.items():
            expected = max(1, int(round(n_total * 0.10)))
            assert per_domain[domain] == expected

    def test_minimum_one_per_domain(self) -> None:
        """Even at very low rates, each domain must get >=1 sample."""
        # 1% would round to 0 for the 50-case regression domain;
        # the sampler must round up to at least 1.
        plan = build_sampling_plan(_full_set(), seed=42, rate=0.01)
        per_domain: dict[TestCaseDomain, int] = {d: 0 for d in TestCaseDomain}
        for s in plan.samples:
            per_domain[s.domain] += 1
        for domain in TestCaseDomain:
            assert per_domain[domain] >= 1

    def test_total_count_at_5pct(self) -> None:
        plan = build_sampling_plan(_full_set(), seed=42, rate=0.05)
        # 5% of 150 = 7.5 -> 8; 5% of 100 = 5; 5% of 100 = 5; 5% of 50 = 2.5 -> 2
        # Per-domain rounding may shift by 1 either way; check ballpark
        assert 18 <= len(plan.samples) <= 22


class TestDeterminism:
    def test_same_seed_same_plan(self) -> None:
        a = build_sampling_plan(_full_set(), seed=42, rate=0.05)
        b = build_sampling_plan(_full_set(), seed=42, rate=0.05)
        assert a == b

    def test_different_seeds_different_plans(self) -> None:
        a = build_sampling_plan(_full_set(), seed=1, rate=0.05)
        b = build_sampling_plan(_full_set(), seed=2, rate=0.05)
        assert a.case_ids != b.case_ids

    def test_plan_records_seed_and_rate(self) -> None:
        plan = build_sampling_plan(_full_set(), seed=42, rate=0.05)
        assert plan.seed == 42
        assert plan.rate == 0.05


class TestPlanShape:
    def test_each_sample_carries_case_and_domain(self) -> None:
        plan = build_sampling_plan(_full_set(), seed=42, rate=0.05)
        for s in plan.samples:
            assert s.case is not None
            assert s.case.domain is s.domain

    def test_plan_is_frozen(self) -> None:
        plan = build_sampling_plan(_full_set(), seed=42, rate=0.05)
        with pytest.raises((AttributeError, TypeError)):
            plan.rate = 0.99  # type: ignore[misc]
