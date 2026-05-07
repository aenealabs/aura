"""Project Aura - Formal verification adapter protocol (ADR-085 Phase 3).

Defines the contract every formal-verification backend must satisfy so
the :class:`VerificationGateService` stays decoupled from any specific
solver. The first implementation is the Z3 SMT adapter (open-source,
Apache-2.0, runs in-process, no cloud dependency); CVC5 / Yices2 / dReal
adapters can be added by implementing :class:`FormalVerificationAdapter`
without touching the gate orchestrator.

Per ADR-085, only constraint axes C1-C4 are formally expressible — C5
(domain compliance), C6 (provenance trust), and C7 (temporal validity)
are deferred to CGE coherence scoring and HITL review. Adapters declare
their supported axes via :attr:`supported_axes` so the gate doesn't ask
a Z3-only adapter to prove a graph-traversal property.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.services.constraint_geometry.contracts import ConstraintAxis, ConstraintRule
from src.services.verification_envelope.contracts import VerificationResult


@dataclass(frozen=True)
class FormalVerificationRequest:
    """Inputs to a formal-verification adapter call.

    The translator runs before the adapter and produces the SMT
    assertion text already shaped to the backend; the adapter then
    discharges those assertions and reports the verdict. Bundling
    request/translation into one frozen dataclass means the audit
    trail captures exactly what the solver saw, byte-for-byte.
    """

    source_code: str
    source_file: Path | None
    rules: tuple[ConstraintRule, ...]
    axes_in_scope: tuple[ConstraintAxis, ...]
    smt_assertions: str
    timeout_seconds: float = 30.0
    metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@runtime_checkable
class FormalVerificationAdapter(Protocol):
    """Protocol every formal-verification tool must satisfy.

    Adapters return a :class:`VerificationResult` and never raise:
    parsing failures, solver timeouts, and unsupported assertions all
    map to ``VerificationVerdict.UNKNOWN`` with the reason in the
    auditor's record so a regulated buyer can reconstruct the decision
    after the fact.
    """

    @property
    def tool_name(self) -> str:
        """Stable identifier (used in audit records and policy docs)."""

    @property
    def is_available(self) -> bool:
        """True when the backing solver is installed and usable."""

    @property
    def supported_axes(self) -> tuple[ConstraintAxis, ...]:
        """Constraint axes this adapter can express in its formal language."""

    async def verify(self, request: FormalVerificationRequest) -> VerificationResult:
        """Discharge the SMT assertions and return the verdict."""
