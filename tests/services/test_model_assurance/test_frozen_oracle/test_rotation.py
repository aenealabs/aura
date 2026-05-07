"""Tests for the rotation policy (ADR-088 Phase 2.2 §Stage 4)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    DOMAIN_MINIMUMS,
    GoldenSetIntegrityError,
    GoldenTestCase,
    GoldenTestSet,
    REQUIRED_APPROVALS,
    ROTATION_CAP_FRACTION,
    RotationApproval,
    RotationProposal,
    TestCaseDomain,
    apply_rotation,
    explain_rotation_cap,
)


def _case(case_id: str, domain: TestCaseDomain) -> GoldenTestCase:
    return GoldenTestCase(
        case_id=case_id,
        domain=domain,
        title=case_id,
        description="d",
        axes=(ModelAssuranceAxis.CODE_COMPREHENSION,),
    )


def _full_minimum_set() -> GoldenTestSet:
    cases: list[GoldenTestCase] = []
    for domain, n in DOMAIN_MINIMUMS.items():
        for i in range(n):
            cases.append(_case(f"{domain.value}-{i:04d}", domain))
    return GoldenTestSet(cases=tuple(cases), version="2026.05.0")


def _approvals(*names: str) -> tuple[RotationApproval, ...]:
    return tuple(
        RotationApproval(approver_id=n, approved_at_iso="2026-05-06T00:00:00+00:00")
        for n in names
    )


# ----------------------------------------------------- approvals


class TestApprovalRules:
    def test_required_approvals_constant(self) -> None:
        assert REQUIRED_APPROVALS == 2

    def test_below_threshold_rejected(self) -> None:
        s = _full_minimum_set()
        proposal = RotationProposal(proposal_id="p1")
        with pytest.raises(GoldenSetIntegrityError, match="approvals"):
            apply_rotation(
                s, proposal,
                approvals=_approvals("alice"),
                new_version="2026.06.0",
            )

    def test_duplicate_approver_rejected(self) -> None:
        s = _full_minimum_set()
        proposal = RotationProposal(proposal_id="p1")
        with pytest.raises(GoldenSetIntegrityError, match="distinct"):
            apply_rotation(
                s, proposal,
                approvals=_approvals("alice", "alice"),
                new_version="2026.06.0",
            )


# ----------------------------------------------------- churn cap


class TestChurnCap:
    def test_cap_fraction_is_10pct(self) -> None:
        assert ROTATION_CAP_FRACTION == 0.10

    def test_explain_cap(self) -> None:
        assert explain_rotation_cap(400) == 40
        assert explain_rotation_cap(50) == 5
        assert explain_rotation_cap(1) == 1  # floor of 1

    def test_above_cap_rejected(self) -> None:
        s = _full_minimum_set()
        # 10% of 400 = 40. Propose 41 changes → reject.
        adds = tuple(
            _case(f"new-{i:03d}", TestCaseDomain.REGRESSION)
            for i in range(41)
        )
        proposal = RotationProposal(proposal_id="p1", add_cases=adds)
        with pytest.raises(GoldenSetIntegrityError, match="cap"):
            apply_rotation(
                s, proposal,
                approvals=_approvals("alice", "bob"),
                new_version="2026.06.0",
            )

    def test_at_cap_accepted(self) -> None:
        s = _full_minimum_set()
        adds = tuple(
            _case(f"new-{i:03d}", TestCaseDomain.REGRESSION)
            for i in range(40)
        )
        proposal = RotationProposal(proposal_id="p1", add_cases=adds)
        out = apply_rotation(
            s, proposal,
            approvals=_approvals("alice", "bob"),
            new_version="2026.06.0",
        )
        assert len(out) == 440

    def test_swap_counts_both_directions(self) -> None:
        """An add+remove counts as 2 churn, not 1."""
        s = _full_minimum_set()
        # 21 adds + 20 removes = 41 churn, just over the 40-cap
        adds = tuple(
            _case(f"new-{i:03d}", TestCaseDomain.REGRESSION)
            for i in range(21)
        )
        removes = tuple(f"regression-{i:04d}" for i in range(20))
        proposal = RotationProposal(
            proposal_id="p1", add_cases=adds, remove_case_ids=removes,
        )
        with pytest.raises(GoldenSetIntegrityError, match="cap"):
            apply_rotation(
                s, proposal,
                approvals=_approvals("alice", "bob"),
                new_version="2026.06.0",
            )


# ----------------------------------------------------- proposal sanity


class TestProposalSanity:
    def test_duplicate_add_ids_rejected(self) -> None:
        s = _full_minimum_set()
        adds = (
            _case("dup", TestCaseDomain.REGRESSION),
            _case("dup", TestCaseDomain.PATCH_CORRECTNESS),
        )
        proposal = RotationProposal(proposal_id="p1", add_cases=adds)
        with pytest.raises(GoldenSetIntegrityError, match="duplicate"):
            apply_rotation(
                s, proposal,
                approvals=_approvals("alice", "bob"),
                new_version="2026.06.0",
            )

    def test_collision_with_existing_set_rejected(self) -> None:
        s = _full_minimum_set()
        # case_id already exists
        adds = (_case("regression-0000", TestCaseDomain.REGRESSION),)
        proposal = RotationProposal(proposal_id="p1", add_cases=adds)
        with pytest.raises(GoldenSetIntegrityError, match="overlap"):
            apply_rotation(
                s, proposal,
                approvals=_approvals("alice", "bob"),
                new_version="2026.06.0",
            )

    def test_remove_unknown_case_rejected(self) -> None:
        s = _full_minimum_set()
        proposal = RotationProposal(
            proposal_id="p1", remove_case_ids=("never-existed",),
        )
        with pytest.raises(GoldenSetIntegrityError, match="non-existent"):
            apply_rotation(
                s, proposal,
                approvals=_approvals("alice", "bob"),
                new_version="2026.06.0",
            )


# ----------------------------------------------------- post-rotation invariants


class TestPostRotationInvariants:
    def test_cannot_drop_below_per_domain_minimum(self) -> None:
        """Removing too many from one domain breaks the per-domain minimum.

        We add the same count to a different domain so the total stays
        at 400 — this isolates the per-domain check from the total-set
        check, which would otherwise fire first.
        """
        s = _full_minimum_set()
        # Remove 15 regression cases (50 -> 35, below the 50 minimum)
        removes = tuple(f"regression-{i:04d}" for i in range(15))
        # Add 15 patch cases so the total stays at 400
        adds = tuple(
            _case(f"new-pc-{i:03d}", TestCaseDomain.PATCH_CORRECTNESS)
            for i in range(15)
        )
        proposal = RotationProposal(
            proposal_id="p1",
            add_cases=adds,
            remove_case_ids=removes,
        )
        # 30 churn ≤ 40 cap, but per-domain check rejects.
        with pytest.raises(GoldenSetIntegrityError, match="regression"):
            apply_rotation(
                s, proposal,
                approvals=_approvals("alice", "bob"),
                new_version="2026.06.0",
            )

    def test_balanced_swap_within_cap_accepted(self) -> None:
        """Replace 5 regression cases — total stays 400, domain stays 50."""
        s = _full_minimum_set()
        removes = tuple(f"regression-{i:04d}" for i in range(5))
        adds = tuple(
            _case(f"new-reg-{i:04d}", TestCaseDomain.REGRESSION)
            for i in range(5)
        )
        out = apply_rotation(
            s, RotationProposal(
                proposal_id="p1",
                add_cases=adds, remove_case_ids=removes,
            ),
            approvals=_approvals("alice", "bob"),
            new_version="2026.06.0",
        )
        assert len(out) == 400
        assert (
            len(out.by_domain(TestCaseDomain.REGRESSION))
            == DOMAIN_MINIMUMS[TestCaseDomain.REGRESSION]
        )


class TestImmutability:
    def test_original_set_unchanged(self) -> None:
        s = _full_minimum_set()
        original_count = len(s)
        adds = tuple(
            _case(f"x-{i:03d}", TestCaseDomain.REGRESSION) for i in range(5)
        )
        apply_rotation(
            s, RotationProposal(proposal_id="p1", add_cases=adds),
            approvals=_approvals("alice", "bob"),
            new_version="2026.06.0",
        )
        # The original set is frozen — len must be unchanged.
        assert len(s) == original_count
