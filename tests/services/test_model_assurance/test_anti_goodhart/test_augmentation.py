"""Tests for adversarial augmentation (ADR-088 Phase 3.1)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.anti_goodhart import (
    AdversarialAugmentation,
    CaseProposal,
)
from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.frozen_oracle import (
    DOMAIN_MINIMUMS,
    GoldenTestCase,
    GoldenTestSet,
    REQUIRED_APPROVALS,
    RotationApproval,
    TestCaseDomain,
    apply_rotation,
)


def _case(
    case_id: str,
    domain: TestCaseDomain = TestCaseDomain.REGRESSION,
    title: str | None = None,
    description: str | None = None,
    expected: tuple[tuple[str, str], ...] = (),
) -> GoldenTestCase:
    """Default title/description derived from case_id so each case is content-unique.

    The augmentation hash covers domain + axes + expected + title +
    description (not case_id) so the dedup test fixtures must vary
    those fields per case to avoid spurious content-collision flags.
    """
    return GoldenTestCase(
        case_id=case_id,
        domain=domain,
        title=title if title is not None else f"title-{case_id}",
        description=description if description is not None else f"desc-{case_id}",
        axes=(ModelAssuranceAxis.CODE_COMPREHENSION,),
        expected=expected,
    )


def _full_set() -> GoldenTestSet:
    cases: list[GoldenTestCase] = []
    for domain, n in DOMAIN_MINIMUMS.items():
        for i in range(n):
            cases.append(_case(f"{domain.value}-{i:04d}", domain))
    return GoldenTestSet(cases=tuple(cases), version="0.1")


class TestStaging:
    def test_staged_count_starts_zero(self) -> None:
        aug = AdversarialAugmentation()
        assert aug.staged_count == 0

    def test_stage_increments(self) -> None:
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("new-1")))
        aug.stage(CaseProposal(case=_case("new-2")))
        assert aug.staged_count == 2

    def test_stage_replaces_same_id(self) -> None:
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("same", description="first")))
        aug.stage(CaseProposal(case=_case("same", description="second")))
        assert aug.staged_count == 1

    def test_clear(self) -> None:
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("new-1")))
        aug.clear()
        assert aug.staged_count == 0


class TestDedupAgainstExisting:
    def test_id_collision_rejected(self) -> None:
        existing = _full_set()
        aug = AdversarialAugmentation()
        # ID matches an existing regression case
        aug.stage(CaseProposal(case=_case("regression-0000")))
        report, accepted = aug.dedup_against(existing)
        assert "regression-0000" in report.rejected_id_collisions
        assert accepted == ()

    def test_content_collision_rejected(self) -> None:
        """Same content as an existing case but different case_id.

        We pin the content explicitly (title + description matching
        an existing case) so the canonical hash collides.
        """
        # Pick any case from the full set — its title + description
        # are deterministic for the synthesised id.
        existing = _full_set()
        target = existing.get("regression-0000")
        assert target is not None
        clone = _case(
            "fresh-id",
            TestCaseDomain.REGRESSION,
            title=target.title,
            description=target.description,
        )
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=clone))
        report, accepted = aug.dedup_against(existing)
        assert "fresh-id" in report.rejected_content_collisions
        assert accepted == ()

    def test_intra_batch_duplicate_rejected(self) -> None:
        existing = _full_set()
        aug = AdversarialAugmentation()
        # Same title + description in both submissions → content collision.
        a = _case("new-1", title="shared-title", description="shared-desc")
        b = _case("new-2", title="shared-title", description="shared-desc")
        aug.stage(CaseProposal(case=a))
        aug.stage(CaseProposal(case=b))
        report, accepted = aug.dedup_against(existing)
        # First wins, second flagged as intra-batch dup
        assert tuple(p.case.case_id for p in accepted) == ("new-1",)
        assert "new-2" in report.rejected_intra_batch_duplicates

    def test_unique_cases_accepted(self) -> None:
        existing = _full_set()
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("new-1")))
        aug.stage(CaseProposal(case=_case("new-2")))
        report, accepted = aug.dedup_against(existing)
        assert tuple(p.case.case_id for p in accepted) == ("new-1", "new-2")
        assert report.accepted_ids == ("new-1", "new-2")

    def test_dedup_is_deterministic(self) -> None:
        existing = _full_set()
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("new-1")))
        aug.stage(CaseProposal(case=_case("new-2")))
        a = aug.dedup_against(existing)
        b = aug.dedup_against(existing)
        assert a == b


class TestRotationProposalEmission:
    def test_proposal_carries_accepted_cases(self) -> None:
        existing = _full_set()
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("new-1")))
        aug.stage(CaseProposal(case=_case("new-2")))
        _, proposal = aug.to_rotation_proposal(existing, proposal_id="p1")
        ids = {c.case_id for c in proposal.add_cases}
        assert ids == {"new-1", "new-2"}

    def test_proposal_dedups_id_collisions(self) -> None:
        existing = _full_set()
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("regression-0000")))  # collision
        aug.stage(CaseProposal(case=_case("genuinely-new")))
        _, proposal = aug.to_rotation_proposal(existing, proposal_id="p1")
        ids = {c.case_id for c in proposal.add_cases}
        assert "regression-0000" not in ids
        assert "genuinely-new" in ids

    def test_proposal_passes_through_rotation_pipeline(self) -> None:
        """Proposal from augmentation must apply cleanly via Phase 2.2 apply_rotation."""
        existing = _full_set()
        aug = AdversarialAugmentation()
        for i in range(5):
            aug.stage(CaseProposal(case=_case(f"new-{i:04d}")))
        _, proposal = aug.to_rotation_proposal(existing, proposal_id="p1")
        # Two-distinct-approver requirement and apply.
        from datetime import datetime, timezone
        approvals = (
            RotationApproval(
                approver_id="alice",
                approved_at_iso=datetime.now(timezone.utc).isoformat(),
            ),
            RotationApproval(
                approver_id="bob",
                approved_at_iso=datetime.now(timezone.utc).isoformat(),
            ),
        )
        new_set = apply_rotation(
            existing, proposal,
            approvals=approvals, new_version="2026.06.0",
        )
        assert len(new_set) == 405

    def test_default_rationale_summarises_dedup(self) -> None:
        existing = _full_set()
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("regression-0000")))  # id collision
        aug.stage(CaseProposal(case=_case("good-1")))
        _, proposal = aug.to_rotation_proposal(existing, proposal_id="p1")
        assert "1 accepted" in proposal.rationale
        assert "1 id-collisions" in proposal.rationale

    def test_custom_rationale_used_when_supplied(self) -> None:
        existing = _full_set()
        aug = AdversarialAugmentation()
        aug.stage(CaseProposal(case=_case("good-1")))
        _, proposal = aug.to_rotation_proposal(
            existing, proposal_id="p1", rationale="custom note",
        )
        assert proposal.rationale == "custom note"


class TestSourceMetadata:
    def test_proposal_carries_incident_id(self) -> None:
        prop = CaseProposal(
            case=_case("new-1"),
            sourced_incident_id="INC-2026-05-06-1234",
            notes="HITL reviewer caught missed CVE",
        )
        assert prop.sourced_incident_id == "INC-2026-05-06-1234"
        assert prop.notes
