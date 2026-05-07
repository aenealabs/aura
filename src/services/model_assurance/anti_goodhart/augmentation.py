"""Adversarial augmentation pipeline (ADR-088 Phase 3.1).

Adds new edge cases to the golden set when production failures
reveal coverage gaps. Per ADR-088 §Stage 6:

  "New edge cases from production failures (missed vulnerabilities,
   incorrect patches caught by HITL reviewers) are added to the
   golden set quarterly. This ensures the benchmark evolves with
   real-world failure modes."

This module is the staging area: it accumulates proposed cases,
deduplicates them against the existing golden set, and emits a
:class:`RotationProposal` for the rotation pipeline (Phase 2.2,
two-approval gate). The augmentation module never mutates the set
directly — it produces proposals that the operator then runs
through ``apply_rotation``.

Deduplication policy (deterministic):
    * case_id collision → drop the new submission, retain the
      existing case (an existing case has ground-truth that's
      been reviewed; the duplicate submission has not).
    * Content-hash collision → drop. The content hash is over
      the case description + axes + expected mapping, normalised
      to canonical JSON.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.services.model_assurance.frozen_oracle import (
    GoldenTestCase,
    GoldenTestSet,
    RotationProposal,
)

logger = logging.getLogger(__name__)


def _canonical_hash(case: GoldenTestCase) -> str:
    payload = {
        "domain": case.domain.value,
        "axes": [a.value for a in sorted(case.axes, key=lambda a: a.value)],
        "expected": [list(t) for t in sorted(case.expected, key=lambda t: t[0])],
        "title": case.title,
        "description": case.description,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest


@dataclass(frozen=True)
class CaseProposal:
    """One new-case proposal, sourced from production-failure feedback."""

    case: GoldenTestCase
    sourced_incident_id: str = ""
    proposed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    notes: str = ""


@dataclass(frozen=True)
class DedupReport:
    """Outcome of running dedup against an existing set."""

    accepted_ids: tuple[str, ...] = ()
    rejected_id_collisions: tuple[str, ...] = ()
    rejected_content_collisions: tuple[str, ...] = ()
    rejected_intra_batch_duplicates: tuple[str, ...] = ()


class AdversarialAugmentation:
    """Builds rotation proposals from production-failure cases.

    Stateless except for the (frozen) staging buffer. Same input
    proposals + same existing set produce the same DedupReport and
    the same RotationProposal — no time-of-day randomness.
    """

    def __init__(self) -> None:
        self._staged: OrderedDict[str, CaseProposal] = OrderedDict()

    def stage(self, proposal: CaseProposal) -> None:
        self._staged[proposal.case.case_id] = proposal

    def stage_many(self, proposals: list[CaseProposal]) -> None:
        for p in proposals:
            self.stage(p)

    @property
    def staged_count(self) -> int:
        return len(self._staged)

    def dedup_against(
        self,
        existing: GoldenTestSet,
    ) -> tuple[DedupReport, tuple[CaseProposal, ...]]:
        """Run the deduplication pass, return (report, accepted)."""
        existing_ids = existing.case_ids
        existing_hashes = {_canonical_hash(c) for c in existing}

        accepted: list[CaseProposal] = []
        accepted_ids: list[str] = []
        id_collisions: list[str] = []
        content_collisions: list[str] = []
        intra_batch: list[str] = []
        seen_intra_batch_hashes: set[str] = set()

        for proposal in self._staged.values():
            cid = proposal.case.case_id
            chash = _canonical_hash(proposal.case)
            if cid in existing_ids:
                id_collisions.append(cid)
                continue
            if chash in existing_hashes:
                content_collisions.append(cid)
                continue
            if chash in seen_intra_batch_hashes:
                intra_batch.append(cid)
                continue
            seen_intra_batch_hashes.add(chash)
            accepted.append(proposal)
            accepted_ids.append(cid)

        return (
            DedupReport(
                accepted_ids=tuple(accepted_ids),
                rejected_id_collisions=tuple(id_collisions),
                rejected_content_collisions=tuple(content_collisions),
                rejected_intra_batch_duplicates=tuple(intra_batch),
            ),
            tuple(accepted),
        )

    def to_rotation_proposal(
        self,
        existing: GoldenTestSet,
        *,
        proposal_id: str,
        rationale: str = "",
    ) -> tuple[DedupReport, RotationProposal]:
        """Run dedup and emit a RotationProposal carrying the survivors.

        The resulting proposal is not yet applied — the operator
        feeds it into :func:`apply_rotation` (Phase 2.2) with the
        required two approvals.
        """
        report, accepted = self.dedup_against(existing)
        return (
            report,
            RotationProposal(
                proposal_id=proposal_id,
                add_cases=tuple(p.case for p in accepted),
                rationale=rationale or (
                    f"Adversarial augmentation: {len(accepted)} accepted, "
                    f"{len(report.rejected_id_collisions)} id-collisions, "
                    f"{len(report.rejected_content_collisions)} content-dups, "
                    f"{len(report.rejected_intra_batch_duplicates)} intra-batch-dups"
                ),
            ),
        )

    def clear(self) -> None:
        self._staged.clear()
