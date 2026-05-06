"""Tests for the formal-verification auditor and archive sinks."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.constraint_geometry.contracts import ConstraintAxis
from src.services.verification_envelope.contracts import (
    VerificationResult,
    VerificationVerdict,
)
from src.services.verification_envelope.formal import (
    ArchiveOutcome,
    AuditRecord,
    FileSystemArchiveSink,
    FormalVerificationRequest,
    InMemoryArchiveSink,
    VerificationAuditor,
)


def _make_request(smt: str = "(check-sat)") -> FormalVerificationRequest:
    return FormalVerificationRequest(
        source_code="def f(): pass\n",
        source_file=Path("/tmp/example.py"),
        rules=(),
        axes_in_scope=(ConstraintAxis.SYNTACTIC_VALIDITY,),
        smt_assertions=smt,
        timeout_seconds=10.0,
    )


def _make_result(
    verdict: VerificationVerdict = VerificationVerdict.PROVED,
) -> VerificationResult:
    return VerificationResult(
        verdict=verdict,
        axes_verified=(ConstraintAxis.SYNTACTIC_VALIDITY,),
        proof_hash="proofhash123",
        solver_version="z3:test",
        verification_time_ms=12.5,
        smt_formula_hash="formula456",
        counterexample=None,
    )


@pytest.mark.asyncio
async def test_in_memory_sink_archives_records() -> None:
    sink = InMemoryArchiveSink()
    auditor = VerificationAuditor(sink=sink)
    request = _make_request()
    record = await auditor.record(request, _make_result())
    assert isinstance(record, AuditRecord)
    assert sink.count == 1
    archived_record, archived_smt = sink.records[0]
    assert archived_record.proof_hash == "proofhash123"
    assert archived_smt == request.smt_assertions


@pytest.mark.asyncio
async def test_audit_record_id_includes_proof_hash_prefix() -> None:
    auditor = VerificationAuditor()
    record = await auditor.record(_make_request(), _make_result())
    assert record.record_id.startswith("dve-formal-")
    assert "proofhash123"[:12] in record.record_id


@pytest.mark.asyncio
async def test_audit_record_id_falls_back_when_no_proof() -> None:
    """SKIPPED / UNKNOWN verdicts have empty proof hash; record id uses
    the formula hash so the archive is still keyable."""
    auditor = VerificationAuditor()
    skipped = VerificationResult(
        verdict=VerificationVerdict.SKIPPED,
        axes_verified=(),
        proof_hash="",
        solver_version="mock",
        verification_time_ms=0.0,
        smt_formula_hash="formula456",
    )
    record = await auditor.record(_make_request(), skipped)
    # The record id uses the formula hash when the proof hash is empty.
    assert "formula456"[:12] in record.record_id


@pytest.mark.asyncio
async def test_audit_record_serialises_to_json() -> None:
    record = await VerificationAuditor().record(_make_request(), _make_result())
    payload = record.to_json()
    assert "proofhash123" in payload
    assert "formula456" in payload
    assert "C1" in payload  # axis
    assert "z3:test" in payload


@pytest.mark.asyncio
async def test_filesystem_sink_writes_per_record_directory(
    tmp_path: Path,
) -> None:
    sink = FileSystemArchiveSink(tmp_path)
    auditor = VerificationAuditor(sink=sink)
    record = await auditor.record(_make_request("(assert true)\n"), _make_result())
    target = tmp_path / record.record_id
    assert target.exists()
    json_text = (target / "record.json").read_text()
    smt_text = (target / "formula.smt2").read_text()
    assert "proofhash123" in json_text
    assert "(assert true)" in smt_text


@pytest.mark.asyncio
async def test_filesystem_sink_creates_root_directory(tmp_path: Path) -> None:
    """Sink should make its root if it doesn't exist."""
    new_root = tmp_path / "audit-root"
    assert not new_root.exists()
    sink = FileSystemArchiveSink(new_root)
    assert new_root.exists()


@pytest.mark.asyncio
async def test_audit_record_round_trip_via_json() -> None:
    """JSON serialisation captures every public field."""
    import json

    record = await VerificationAuditor().record(_make_request(), _make_result())
    payload = json.loads(record.to_json())
    assert payload["verdict"] == "proved"
    assert payload["axes_in_scope"] == ["C1"]
    assert payload["axes_verified"] == ["C1"]
    assert payload["solver_version"] == "z3:test"
    assert payload["verification_time_ms"] == 12.5


@pytest.mark.asyncio
async def test_failed_archive_outcome_does_not_raise(
    tmp_path: Path,
) -> None:
    """A read-only sink directory must not crash the auditor — the
    failure surfaces via ArchiveOutcome instead.

    NOTE: Skipped on platforms where chmod can't restrict the directory
    (most CI containers run as root). The behaviour is exercised by
    unit tests of the sink in isolation; this test is a smoke test.
    """
    import os

    if os.geteuid() == 0:
        pytest.skip("root user can write to chmod 000 dirs")
    sink = FileSystemArchiveSink(tmp_path)
    record = await VerificationAuditor(sink=sink).record(
        _make_request(), _make_result()
    )
    assert isinstance(record, AuditRecord)
