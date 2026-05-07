"""Project Aura - Formal-verification auditor (ADR-085 Phase 3).

Produces immutable :class:`AuditRecord` instances for every formal-
verification gate run and provides a pluggable archive sink so the
records (plus the SMT formula and proof artefacts) can be persisted
to the DO-178C audit trail.

Phase 3 ships an in-memory archive sink (sufficient for tests and dev
demos) and a filesystem sink (writes per-run JSON + SMT files under a
configured root). Phase 5 will add the S3 sink with KMS-CMK
encryption per the ADR cost analysis.

The auditor is intentionally side-effect-free outside of the sink
interaction — it never logs the SMT formula at WARN/INFO level (could
contain sensitive source) and never raises on archive failure. Audit
failures are signalled via a returned ``ArchiveOutcome`` so the gate
can decide whether to continue (fail-soft) or reject (fail-hard).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.services.verification_envelope.contracts import (
    VerificationResult,
    VerificationVerdict,
)
from src.services.verification_envelope.formal.formal_adapter import (
    FormalVerificationRequest,
)

logger = logging.getLogger(__name__)


class ArchiveOutcome(Enum):
    ARCHIVED = "archived"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class AuditRecord:
    """Immutable record of one formal-verification gate run.

    Frozen so post-facto mutation can't compromise the audit trail.
    Designed to be JSON-serialisable for downstream sinks (filesystem,
    S3, DynamoDB) without bespoke encoders.
    """

    record_id: str
    request_source_file: str | None
    smt_formula_hash: str
    verdict: str
    axes_in_scope: tuple[str, ...]
    axes_verified: tuple[str, ...]
    proof_hash: str
    solver_version: str
    verification_time_ms: float
    counterexample: str | None
    metadata: tuple[tuple[str, str], ...]
    created_at: str

    def to_json(self) -> str:
        # Use asdict so frozen tuples render naturally.
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


@runtime_checkable
class _ArchiveSink(Protocol):
    """Pluggable destination for AuditRecord + SMT artefacts."""

    async def archive(
        self,
        record: AuditRecord,
        smt_assertions: str,
    ) -> ArchiveOutcome: ...


class InMemoryArchiveSink:
    """Holds records in process memory.

    Useful for tests and dev demos. Production gates should swap this
    out for the filesystem or S3 sink so records survive process
    restarts.
    """

    def __init__(self) -> None:
        self._records: list[tuple[AuditRecord, str]] = []

    @property
    def count(self) -> int:
        return len(self._records)

    @property
    def records(self) -> tuple[tuple[AuditRecord, str], ...]:
        return tuple(self._records)

    async def archive(self, record: AuditRecord, smt_assertions: str) -> ArchiveOutcome:
        self._records.append((record, smt_assertions))
        return ArchiveOutcome.ARCHIVED


class FileSystemArchiveSink:
    """Writes records to a local directory tree.

    Each record produces two files under ``root / record_id /``:

    * ``record.json`` — the AuditRecord
    * ``formula.smt2`` — the SMT-LIB v2 input the solver saw

    The directory layout is intentionally one-record-per-folder so
    long-term archives (years of patches) don't end up with a single
    flat directory of millions of entries.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    async def archive(self, record: AuditRecord, smt_assertions: str) -> ArchiveOutcome:
        try:
            target = self._root / record.record_id
            target.mkdir(parents=True, exist_ok=True)
            (target / "record.json").write_text(record.to_json(), encoding="utf-8")
            (target / "formula.smt2").write_text(smt_assertions, encoding="utf-8")
            return ArchiveOutcome.ARCHIVED
        except OSError as exc:  # pragma: no cover — filesystem failure
            logger.error(
                "audit archive failed for record %s: %s", record.record_id, exc
            )
            return ArchiveOutcome.FAILED


class VerificationAuditor:
    """Builds AuditRecord instances and forwards them to a sink."""

    def __init__(self, sink: _ArchiveSink | None = None) -> None:
        self._sink = sink or InMemoryArchiveSink()

    @property
    def sink(self) -> _ArchiveSink:
        return self._sink

    async def record(
        self,
        request: FormalVerificationRequest,
        result: VerificationResult,
    ) -> AuditRecord:
        record = AuditRecord(
            record_id=self._make_record_id(result),
            request_source_file=(
                str(request.source_file) if request.source_file else None
            ),
            smt_formula_hash=result.smt_formula_hash,
            verdict=result.verdict.value,
            axes_in_scope=tuple(a.value for a in request.axes_in_scope),
            axes_verified=tuple(a.value for a in result.axes_verified),
            proof_hash=result.proof_hash,
            solver_version=result.solver_version,
            verification_time_ms=result.verification_time_ms,
            counterexample=result.counterexample,
            metadata=tuple(request.metadata),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        outcome = await self._sink.archive(record, request.smt_assertions)
        if outcome != ArchiveOutcome.ARCHIVED:
            logger.warning(
                "audit sink declined to archive record %s: %s",
                record.record_id,
                outcome.value,
            )
        return record

    @staticmethod
    def _make_record_id(result: VerificationResult) -> str:
        # Two records can share an SMT formula (re-runs) but each gets
        # a unique id from the proof_hash + timestamp. When the verdict
        # is SKIPPED (no proof) the id falls back to the formula hash.
        seed = result.proof_hash or result.smt_formula_hash
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if seed:
            return f"dve-formal-{seed[:12]}-{ts}"
        return f"dve-formal-noproof-{ts}"
