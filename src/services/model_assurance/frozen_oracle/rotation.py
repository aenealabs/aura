"""Quarterly rotation policy for the golden test set (ADR-088 §Stage 4).

Rules:
    * No more than 10% of cases rotated per cycle.
    * Both adds and removes count toward the 10% cap (a swap is
      one add + one remove → 2 of the cap).
    * Per-domain minimums must hold post-rotation.
    * Two human approvals required (this module enforces the
      *count*; the source-of-truth attribution lives in the PR
      that wires the call).
    * Anti-goodharting: rotation seed for holdout sampling is
      managed by a cron job *outside* the agent loop. This module
      doesn't generate the seed; it consumes one supplied by the
      caller.

The rotation is presented as a :class:`RotationProposal` that an
operator constructs from an admin tool. Calling
``apply_rotation(set, proposal, approvals=...)`` either returns the
new :class:`GoldenTestSet` or raises :class:`GoldenSetIntegrityError`
with the precise invariant violated. Same inputs always yield the
same output.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.model_assurance.frozen_oracle.contracts import (
    DOMAIN_MINIMUMS,
    GOLDEN_SET_MINIMUM,
    GoldenSetIntegrityError,
    GoldenTestCase,
)
from src.services.model_assurance.frozen_oracle.golden_set import (
    GoldenTestSet,
)


# Hard cap: no more than this fraction of the set may be rotated
# per cycle. Per ADR-088 §Stage 4 ("10% quarterly").
ROTATION_CAP_FRACTION = 0.10

# Required approvals count.
REQUIRED_APPROVALS = 2


@dataclass(frozen=True)
class RotationProposal:
    """One quarterly rotation candidate.

    ``add_cases`` and ``remove_case_ids`` are both tuples of
    GoldenTestCase / str. They're applied atomically: either the
    whole proposal succeeds or none of it does. ``rationale`` is
    surfaced in the audit record so operators can trace why a case
    was added/removed.
    """

    proposal_id: str
    add_cases: tuple[GoldenTestCase, ...] = ()
    remove_case_ids: tuple[str, ...] = ()
    rationale: str = ""

    @property
    def churn(self) -> int:
        """Number of cases touched (adds + removes)."""
        return len(self.add_cases) + len(self.remove_case_ids)


@dataclass(frozen=True)
class RotationApproval:
    """One operator approval. Two distinct approvers required."""

    approver_id: str
    approved_at_iso: str
    notes: str = ""


def apply_rotation(
    current: GoldenTestSet,
    proposal: RotationProposal,
    *,
    approvals: tuple[RotationApproval, ...],
    new_version: str,
) -> GoldenTestSet:
    """Apply ``proposal`` to ``current`` after enforcing all invariants.

    Order of checks (fail-fast):
        1. Approval count and uniqueness.
        2. Per-cycle churn cap.
        3. add_cases case_ids unique and not already present.
        4. remove_case_ids actually present.
        5. Resulting set passes 400-case + per-domain minimums.

    Returns the new :class:`GoldenTestSet`. Never mutates ``current``.
    """
    # 1. Approvals
    if len(approvals) < REQUIRED_APPROVALS:
        raise GoldenSetIntegrityError(
            f"rotation requires >= {REQUIRED_APPROVALS} approvals; "
            f"got {len(approvals)}",
        )
    approver_ids = {a.approver_id for a in approvals}
    if len(approver_ids) < REQUIRED_APPROVALS:
        raise GoldenSetIntegrityError(
            "rotation approvals must come from distinct approvers",
            detail=f"approver_ids={sorted(approver_ids)}",
        )

    # 2. Churn cap
    cap = max(1, int(round(len(current) * ROTATION_CAP_FRACTION)))
    if proposal.churn > cap:
        raise GoldenSetIntegrityError(
            f"rotation proposes {proposal.churn} changes; cap is {cap} "
            f"({int(ROTATION_CAP_FRACTION * 100)}% of {len(current)})",
        )

    # 3. add_cases sanity
    add_ids = [c.case_id for c in proposal.add_cases]
    if len(set(add_ids)) != len(add_ids):
        raise GoldenSetIntegrityError(
            "duplicate case_ids in proposal.add_cases",
        )
    existing_ids = current.case_ids
    collisions = [cid for cid in add_ids if cid in existing_ids]
    if collisions:
        raise GoldenSetIntegrityError(
            "proposal.add_cases overlap existing set",
            detail=f"first 5: {collisions[:5]}",
        )

    # 4. remove_case_ids must exist
    missing_removes = [
        cid for cid in proposal.remove_case_ids if cid not in existing_ids
    ]
    if missing_removes:
        raise GoldenSetIntegrityError(
            "proposal.remove_case_ids reference non-existent cases",
            detail=f"first 5: {missing_removes[:5]}",
        )

    # 5. Apply and validate
    remove_set = set(proposal.remove_case_ids)
    new_cases = tuple(
        c for c in current.cases if c.case_id not in remove_set
    ) + proposal.add_cases
    new_set = GoldenTestSet(cases=new_cases, version=new_version)
    new_set.validate_minimums()  # raises if minima broken
    return new_set


def explain_rotation_cap(set_size: int) -> int:
    """Return the absolute case count that ``ROTATION_CAP_FRACTION`` resolves to."""
    return max(1, int(round(set_size * ROTATION_CAP_FRACTION)))
