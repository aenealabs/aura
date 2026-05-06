"""Tests for DynamoDBAuditSink (ADR-085 Phase 5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.verification_envelope.formal.verification_auditor import (
    ArchiveOutcome,
    AuditRecord,
    InMemoryArchiveSink,
)
from src.services.verification_envelope.sinks.dynamodb_audit_sink import (
    DynamoDBAuditSink,
)


def _record(record_id: str = "dve-test-1") -> AuditRecord:
    return AuditRecord(
        record_id=record_id,
        request_source_file="/tmp/x.py",
        smt_formula_hash="formula-hash",
        verdict="proved",
        axes_in_scope=("C1", "C2"),
        axes_verified=("C1",),
        proof_hash="proof-hash",
        solver_version="z3:fake",
        verification_time_ms=12.5,
        counterexample=None,
        metadata=(("program", "fadec-x"),),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.mark.asyncio
async def test_no_client_falls_back_to_in_memory() -> None:
    sink = DynamoDBAuditSink(table_name=None, dynamodb_client=None)
    assert sink.is_live is False
    outcome = await sink.archive(_record(), "(check-sat)")
    assert outcome == ArchiveOutcome.ARCHIVED
    assert sink.fallback.count == 1


@pytest.mark.asyncio
async def test_explicit_fallback_used() -> None:
    custom = InMemoryArchiveSink()
    sink = DynamoDBAuditSink(fallback=custom)
    await sink.archive(_record(), "(check-sat)")
    assert custom.count == 1


@pytest.mark.asyncio
async def test_live_path_writes_with_conditional_expression() -> None:
    """The live write must use ConditionExpression to enforce immutability."""

    class _FakeDDB:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def put_item(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(kwargs)

    client = _FakeDDB()
    sink = DynamoDBAuditSink(
        table_name="aura-dve-audit-test", dynamodb_client=client
    )
    assert sink.is_live is True
    outcome = await sink.archive(_record(), "(check-sat)")
    assert outcome == ArchiveOutcome.ARCHIVED
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["TableName"] == "aura-dve-audit-test"
    assert "ConditionExpression" in call
    assert call["ConditionExpression"].startswith("attribute_not_exists")


@pytest.mark.asyncio
async def test_live_path_maps_record_to_dynamodb_item_form() -> None:
    class _FakeDDB:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def put_item(self, **kwargs):  # type: ignore[no-untyped-def]
            self.calls.append(kwargs)

    client = _FakeDDB()
    sink = DynamoDBAuditSink(
        table_name="aura-dve-audit-test", dynamodb_client=client
    )
    await sink.archive(_record("dve-r1"), "(check-sat)")
    item = client.calls[0]["Item"]
    assert item["record_id"]["S"] == "dve-r1"
    assert item["verdict"]["S"] == "proved"
    assert item["axes_in_scope"]["L"] == [{"S": "C1"}, {"S": "C2"}]
    assert item["axes_verified"]["L"] == [{"S": "C1"}]
    # ttl present and shaped as DynamoDB number.
    assert item["ttl"]["N"]
    assert int(item["ttl"]["N"]) > 0


@pytest.mark.asyncio
async def test_conditional_check_failure_returns_skipped() -> None:
    """Re-archiving the same record_id should be SKIPPED, not FAILED."""

    class _FakeDDB:
        def put_item(self, **kwargs):  # type: ignore[no-untyped-def]
            from src.services.verification_envelope.sinks import dynamodb_audit_sink

            err = dynamodb_audit_sink.ClientError(  # type: ignore[attr-defined]
                {"Error": {"Code": "ConditionalCheckFailedException"}},
                "PutItem",
            ) if hasattr(dynamodb_audit_sink.ClientError, "__init__") else Exception()
            # Simulate the ClientError shape boto raises.
            class _Err(Exception):
                response = {"Error": {"Code": "ConditionalCheckFailedException"}}

            raise _Err()

    client = _FakeDDB()
    sink = DynamoDBAuditSink(
        table_name="aura-dve-audit-test", dynamodb_client=client
    )
    # Patch the imported ClientError to the bare Exception so the
    # except branch matches.
    from src.services.verification_envelope.sinks import dynamodb_audit_sink as ddb_mod

    original = ddb_mod.ClientError
    ddb_mod.ClientError = Exception  # type: ignore[assignment]
    try:
        outcome = await sink.archive(_record(), "(check-sat)")
    finally:
        ddb_mod.ClientError = original  # type: ignore[assignment]
    assert outcome == ArchiveOutcome.SKIPPED


@pytest.mark.asyncio
async def test_unexpected_exception_returns_failed() -> None:
    class _FakeDDB:
        def put_item(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("network down")

    client = _FakeDDB()
    sink = DynamoDBAuditSink(
        table_name="aura-dve-audit-test", dynamodb_client=client
    )
    outcome = await sink.archive(_record(), "(check-sat)")
    assert outcome == ArchiveOutcome.FAILED
