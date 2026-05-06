"""Tests for S3ProofArchiveSink (ADR-085 Phase 5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.verification_envelope.formal.verification_auditor import (
    ArchiveOutcome,
    AuditRecord,
    InMemoryArchiveSink,
)
from src.services.verification_envelope.sinks.s3_proof_archive_sink import (
    S3ProofArchiveSink,
)


def _record(record_id: str = "dve-test-s3") -> AuditRecord:
    return AuditRecord(
        record_id=record_id,
        request_source_file="/tmp/x.py",
        smt_formula_hash="fhash",
        verdict="proved",
        axes_in_scope=("C1",),
        axes_verified=("C1",),
        proof_hash="phash",
        solver_version="z3:fake",
        verification_time_ms=12.5,
        counterexample=None,
        metadata=(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.mark.asyncio
async def test_no_bucket_falls_back_to_in_memory() -> None:
    sink = S3ProofArchiveSink(bucket_name=None, s3_client=None)
    assert sink.is_live is False
    outcome = await sink.archive(_record(), "(check-sat)\n")
    assert outcome == ArchiveOutcome.ARCHIVED
    assert sink.fallback.count == 1


@pytest.mark.asyncio
async def test_live_path_writes_record_and_formula_objects() -> None:
    class _FakeS3:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def put_object(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(kwargs)

    client = _FakeS3()
    sink = S3ProofArchiveSink(
        bucket_name="aura-dve-proofs-test",
        s3_client=client,
        kms_key_id="alias/aura-dve-audit-test",
    )
    assert sink.is_live is True
    outcome = await sink.archive(_record("dve-r1"), "(assert true)\n")
    assert outcome == ArchiveOutcome.ARCHIVED
    keys = sorted(c["Key"] for c in client.calls)
    assert keys == [
        "dve/proofs/dve-r1/formula.smt2",
        "dve/proofs/dve-r1/record.json",
    ]
    for call in client.calls:
        assert call["Bucket"] == "aura-dve-proofs-test"
        assert call["ServerSideEncryption"] == "aws:kms"
        assert call["SSEKMSKeyId"] == "alias/aura-dve-audit-test"


@pytest.mark.asyncio
async def test_record_object_carries_json_payload() -> None:
    class _FakeS3:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def put_object(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(kwargs)

    client = _FakeS3()
    sink = S3ProofArchiveSink(bucket_name="b", s3_client=client)
    await sink.archive(_record("dve-r2"), "smt body")
    record_call = next(
        c for c in client.calls if c["Key"].endswith("record.json")
    )
    assert record_call["ContentType"] == "application/json"
    body = record_call["Body"]
    assert isinstance(body, bytes)
    assert b"phash" in body
    assert b"fhash" in body


@pytest.mark.asyncio
async def test_formula_object_uses_text_content_type() -> None:
    class _FakeS3:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def put_object(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(kwargs)

    client = _FakeS3()
    sink = S3ProofArchiveSink(bucket_name="b", s3_client=client)
    await sink.archive(_record(), "(check-sat)")
    formula_call = next(
        c for c in client.calls if c["Key"].endswith("formula.smt2")
    )
    assert formula_call["ContentType"] == "text/plain"
    assert formula_call["Body"] == b"(check-sat)"


@pytest.mark.asyncio
async def test_kms_key_id_omitted_when_unset() -> None:
    class _FakeS3:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def put_object(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(kwargs)

    client = _FakeS3()
    # No kms_key_id supplied → bucket default key is used; SSE-KMS is
    # still demanded so a misconfigured bucket can't silently degrade.
    sink = S3ProofArchiveSink(
        bucket_name="b", s3_client=client, kms_key_id=None
    )
    await sink.archive(_record(), "x")
    for call in client.calls:
        assert call["ServerSideEncryption"] == "aws:kms"
        assert "SSEKMSKeyId" not in call


@pytest.mark.asyncio
async def test_put_failure_returns_failed_outcome() -> None:
    class _FakeS3:
        def put_object(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    sink = S3ProofArchiveSink(bucket_name="b", s3_client=_FakeS3())
    outcome = await sink.archive(_record(), "x")
    assert outcome == ArchiveOutcome.FAILED


@pytest.mark.asyncio
async def test_explicit_fallback_used_when_bucket_missing() -> None:
    custom = InMemoryArchiveSink()
    sink = S3ProofArchiveSink(bucket_name=None, fallback=custom)
    await sink.archive(_record(), "(check-sat)\n")
    assert custom.count == 1
