"""Tests for CompositeArchiveSink fan-out behaviour."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.verification_envelope.formal.verification_auditor import (
    ArchiveOutcome,
    AuditRecord,
    InMemoryArchiveSink,
)
from src.services.verification_envelope.sinks.composite_sink import (
    CompositeArchiveSink,
)


def _record() -> AuditRecord:
    return AuditRecord(
        record_id="dve-comp-1",
        request_source_file=None,
        smt_formula_hash="f",
        verdict="proved",
        axes_in_scope=("C1",),
        axes_verified=("C1",),
        proof_hash="p",
        solver_version="z3:fake",
        verification_time_ms=1.0,
        counterexample=None,
        metadata=(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


class _ExplicitOutcomeSink:
    def __init__(self, outcome: ArchiveOutcome) -> None:
        self._outcome = outcome
        self.calls = 0

    async def archive(self, record, smt):  # type: ignore[no-untyped-def]
        self.calls += 1
        return self._outcome


@pytest.mark.asyncio
async def test_empty_sink_list_rejected() -> None:
    with pytest.raises(ValueError):
        CompositeArchiveSink([])


@pytest.mark.asyncio
async def test_all_archived_returns_archived() -> None:
    a = InMemoryArchiveSink()
    b = InMemoryArchiveSink()
    composite = CompositeArchiveSink([a, b])
    outcome = await composite.archive(_record(), "(check-sat)")
    assert outcome == ArchiveOutcome.ARCHIVED
    assert a.count == 1
    assert b.count == 1


@pytest.mark.asyncio
async def test_failed_dominates_archived() -> None:
    composite = CompositeArchiveSink(
        [
            InMemoryArchiveSink(),
            _ExplicitOutcomeSink(ArchiveOutcome.FAILED),
        ]
    )
    outcome = await composite.archive(_record(), "x")
    assert outcome == ArchiveOutcome.FAILED


@pytest.mark.asyncio
async def test_skipped_dominates_archived_but_loses_to_failed() -> None:
    composite = CompositeArchiveSink(
        [
            InMemoryArchiveSink(),
            _ExplicitOutcomeSink(ArchiveOutcome.SKIPPED),
        ]
    )
    outcome = await composite.archive(_record(), "x")
    assert outcome == ArchiveOutcome.SKIPPED

    composite2 = CompositeArchiveSink(
        [
            _ExplicitOutcomeSink(ArchiveOutcome.SKIPPED),
            _ExplicitOutcomeSink(ArchiveOutcome.FAILED),
        ]
    )
    outcome2 = await composite2.archive(_record(), "x")
    assert outcome2 == ArchiveOutcome.FAILED


@pytest.mark.asyncio
async def test_all_children_invoked_even_after_failure() -> None:
    """Critical: a failed write to DynamoDB must not stop the S3 write."""
    bad = _ExplicitOutcomeSink(ArchiveOutcome.FAILED)
    good = InMemoryArchiveSink()
    composite = CompositeArchiveSink([bad, good])
    await composite.archive(_record(), "x")
    assert bad.calls == 1
    assert good.count == 1


@pytest.mark.asyncio
async def test_children_property_returns_provided_sinks() -> None:
    a = InMemoryArchiveSink()
    b = InMemoryArchiveSink()
    composite = CompositeArchiveSink([a, b])
    assert composite.children == (a, b)
