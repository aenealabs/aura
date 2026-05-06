"""Project Aura - Traceability data contracts (ADR-085 Phase 4).

DO-178C 5.5 demands bidirectional traceability between:

    HLR  ↔  LLR  ↔  Code  ↔  Test

(High-Level Requirements ↔ Low-Level Requirements ↔ source code
↔ verification tests). Every artefact must trace back to the
requirement(s) it implements or verifies, and every requirement must
trace forward to the artefacts that fulfil it. Gaps in either
direction are findings against the certification objectives.

This module defines the immutable shapes the traceability service
operates on. The actual storage backend is plugged in via
``traceability_service.RequirementStore`` (in-memory + Neptune
adapters in Phase 4; the Phase 5 cloud-formation pass adds the
production schema).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class RequirementType(Enum):
    """DO-178C requirement levels.

    HLR captures *what* the system must do (typically inherited from
    the system-level safety analysis). LLR captures *how* — design
    decomposition the developer can directly implement.
    """

    HLR = "high_level_requirement"
    LLR = "low_level_requirement"


class ArtefactType(Enum):
    """Non-requirement nodes in the traceability graph.

    CODE — a source file (or smaller granularity if the operator
    chooses to track at function/method level).
    TEST — a verification test case.
    REVIEW — a manual review record (HITL artefact).
    """

    CODE = "code"
    TEST = "test"
    REVIEW = "review"


class TraceEdgeType(Enum):
    """Edge types in the requirements graph.

    DERIVED_FROM — LLR → HLR (the LLR was derived from this HLR).
    TRACES_TO — Code → LLR (the code implements this LLR).
    VERIFIED_BY — Requirement → Test (the requirement is verified by
    this test). Bidirectional in the sense that the inverse query
    "what tests verify this requirement?" is supported by walking the
    same edge backwards.
    REVIEWED_BY — Requirement|Code → Review (HITL artefact).
    """

    DERIVED_FROM = "DERIVED_FROM"
    TRACES_TO = "TRACES_TO"
    VERIFIED_BY = "VERIFIED_BY"
    REVIEWED_BY = "REVIEWED_BY"


@dataclass(frozen=True)
class Requirement:
    """A single HLR or LLR entry."""

    requirement_id: str
    type: RequirementType
    title: str
    description: str
    dal_level: str  # "DAL_A" .. "DAL_D" / "DEFAULT"
    parent_ids: tuple[str, ...] = ()  # For LLRs that derive from one+ HLRs.
    metadata: tuple[tuple[str, str], ...] = ()
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def metadata_dict(self) -> dict[str, str]:
        return dict(self.metadata)


@dataclass(frozen=True)
class Artefact:
    """A non-requirement node (code, test, review)."""

    artefact_id: str
    type: ArtefactType
    title: str
    location: str  # Source path / test path / review URL.
    metadata: tuple[tuple[str, str], ...] = ()
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class TraceEdge:
    """A directed edge between two requirement / artefact nodes."""

    source_id: str
    target_id: str
    type: TraceEdgeType
    metadata: tuple[tuple[str, str], ...] = ()
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class TraceabilityGap:
    """A finding produced by gap analysis.

    The auditor distinguishes two gap classes: *forward* gaps are
    requirements with no implementing artefacts (HLR with no LLR /
    LLR with no code / requirement with no test); *reverse* gaps are
    artefacts with no parent requirement (orphan code / orphan test).
    Both are findings under DO-178C 6.4 verification objectives.
    """

    finding_id: str
    direction: str  # "forward" | "reverse"
    node_id: str
    node_type: str  # RequirementType.value or ArtefactType.value
    description: str

    @classmethod
    def forward(
        cls, node_id: str, node_type: str, description: str
    ) -> "TraceabilityGap":
        return cls(
            finding_id=f"gap-fwd-{node_id}",
            direction="forward",
            node_id=node_id,
            node_type=node_type,
            description=description,
        )

    @classmethod
    def reverse(
        cls, node_id: str, node_type: str, description: str
    ) -> "TraceabilityGap":
        return cls(
            finding_id=f"gap-rev-{node_id}",
            direction="reverse",
            node_id=node_id,
            node_type=node_type,
            description=description,
        )


@dataclass(frozen=True)
class TraceabilityReport:
    """Full bidirectional trace report.

    Carries the gap list plus convenience counters so a CloudWatch
    dashboard can graph the certification readiness score over time
    without re-running the full graph walk.
    """

    forward_gaps: tuple[TraceabilityGap, ...]
    reverse_gaps: tuple[TraceabilityGap, ...]
    requirement_count: int
    artefact_count: int
    edge_count: int
    computed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def is_complete(self) -> bool:
        """True when there are no gaps in either direction."""
        return not (self.forward_gaps or self.reverse_gaps)

    @property
    def total_gap_count(self) -> int:
        return len(self.forward_gaps) + len(self.reverse_gaps)
