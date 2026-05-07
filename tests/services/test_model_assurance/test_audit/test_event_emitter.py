"""Tests for the AuditEmitter (ADR-088 Phase 3.4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.services.model_assurance.audit import (
    AuditEmitter,
    AuditEvent,
    AuditEventType,
    CloudTrailEventBridgeSink,
    InMemoryAuditSink,
    NISTControl,
    filter_events_by_control,
)


class TestEmitter:
    def test_emit_records_event(self) -> None:
        sink = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(sink,))
        emitter.emit(
            event_type=AuditEventType.CANDIDATE_DISCOVERED,
            candidate_id="claude-3-5",
            actor="scout-agent",
            correlation_id="run-1",
        )
        assert len(sink.events) == 1
        assert sink.events[0].candidate_id == "claude-3-5"

    def test_event_id_content_addressable(self) -> None:
        sink = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(sink,))
        ts = datetime(2026, 5, 6, 12, tzinfo=timezone.utc)
        a = emitter.emit(
            event_type=AuditEventType.CANDIDATE_DISCOVERED,
            candidate_id="m",
            correlation_id="r1",
            occurred_at=ts,
        )
        b = emitter.emit(
            event_type=AuditEventType.CANDIDATE_DISCOVERED,
            candidate_id="m",
            correlation_id="r1",
            occurred_at=ts,
        )
        # Same content → same event_id (16-char SHA-256 prefix).
        assert a.event_id == b.event_id

    def test_request_and_response_pass_through(self) -> None:
        sink = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(sink,))
        emitter.emit(
            event_type=AuditEventType.PROVENANCE_VERIFIED,
            candidate_id="m",
            request_parameters={"weights_digest": "abc"},
            response_elements={"trust_score": "0.92"},
        )
        event = sink.events[0]
        assert event.request_dict == {"weights_digest": "abc"}
        assert event.response_dict == {"trust_score": "0.92"}

    def test_error_fields_recorded(self) -> None:
        sink = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(sink,))
        emitter.emit(
            event_type=AuditEventType.PROVENANCE_FAILED,
            candidate_id="m",
            error_code="SignatureInvalid",
            error_message="weights digest signature did not verify",
        )
        event = sink.events[0]
        assert event.error_code == "SignatureInvalid"
        assert "did not verify" in event.error_message  # type: ignore[arg-type]


class TestFanout:
    def test_multiple_sinks_all_receive(self) -> None:
        a = InMemoryAuditSink()
        b = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(a, b))
        emitter.emit(
            event_type=AuditEventType.HITL_APPROVED,
            candidate_id="m",
        )
        assert len(a.events) == 1
        assert len(b.events) == 1

    def test_failing_sink_does_not_block_others(self) -> None:
        class _BoomSink:
            def emit(self, event: AuditEvent) -> None:
                raise RuntimeError("sink down")

        good = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(_BoomSink(), good))
        emitter.emit(
            event_type=AuditEventType.HITL_APPROVED,
            candidate_id="m",
        )
        assert len(good.events) == 1


class TestFilterByControl:
    def test_filter_by_cm3(self) -> None:
        sink = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(sink,))
        emitter.emit(
            event_type=AuditEventType.CANDIDATE_DISCOVERED,
            candidate_id="m1",
        )
        emitter.emit(
            event_type=AuditEventType.HITL_APPROVED,
            candidate_id="m1",
        )
        emitter.emit(
            event_type=AuditEventType.PROVENANCE_VERIFIED,
            candidate_id="m1",
        )
        cm3 = filter_events_by_control(sink.events, NISTControl.CM_3)
        # HITL_APPROVED carries CM-3; the others don't.
        assert len(cm3) == 1
        assert cm3[0].event_type is AuditEventType.HITL_APPROVED

    def test_filter_by_au3_returns_all(self) -> None:
        """Every event carries AU-3 (record-content control)."""
        sink = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(sink,))
        for et in (
            AuditEventType.CANDIDATE_DISCOVERED,
            AuditEventType.HITL_APPROVED,
            AuditEventType.ROLLBACK_APPLIED,
        ):
            emitter.emit(event_type=et, candidate_id="m")
        au3 = filter_events_by_control(sink.events, NISTControl.AU_3)
        assert len(au3) == 3


class TestSinkQueries:
    def test_by_type_filters(self) -> None:
        sink = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(sink,))
        emitter.emit(event_type=AuditEventType.CANDIDATE_DISCOVERED, candidate_id="m")
        emitter.emit(event_type=AuditEventType.HITL_APPROVED, candidate_id="m")
        emitter.emit(event_type=AuditEventType.HITL_APPROVED, candidate_id="m2")
        approvals = sink.by_type(AuditEventType.HITL_APPROVED)
        assert len(approvals) == 2

    def test_by_correlation_groups_pipeline_run(self) -> None:
        sink = InMemoryAuditSink()
        emitter = AuditEmitter(sinks=(sink,))
        emitter.emit(
            event_type=AuditEventType.CANDIDATE_DISCOVERED,
            candidate_id="m",
            correlation_id="run-A",
        )
        emitter.emit(
            event_type=AuditEventType.PROVENANCE_VERIFIED,
            candidate_id="m",
            correlation_id="run-A",
        )
        emitter.emit(
            event_type=AuditEventType.CANDIDATE_DISCOVERED,
            candidate_id="other",
            correlation_id="run-B",
        )
        run_a = sink.by_correlation("run-A")
        assert len(run_a) == 2


class TestCloudTrailSinkMockMode:
    def test_no_client_no_op(self) -> None:
        sink = CloudTrailEventBridgeSink(client=None)
        sink._is_live = False  # force mock regardless of env
        sink.emit(
            AuditEvent(
                event_id="x",
                event_type=AuditEventType.CANDIDATE_DISCOVERED,
                candidate_id="m",
                occurred_at=datetime.now(timezone.utc),
            )
        )

    def test_live_path_calls_put_events(self) -> None:
        class _Fake:
            def __init__(self) -> None:
                self.calls = []

            def put_events(self, **kwargs):  # type: ignore[no-untyped-def]
                self.calls.append(kwargs)

        client = _Fake()
        sink = CloudTrailEventBridgeSink(
            client=client, bus_name="aura-audit",
        )
        sink.emit(
            AuditEvent(
                event_id="x",
                event_type=AuditEventType.HITL_APPROVED,
                candidate_id="m",
                occurred_at=datetime.now(timezone.utc),
                actor="alice",
            )
        )
        assert len(client.calls) == 1
        entry = client.calls[0]["Entries"][0]
        assert entry["Source"] == "aura.model_assurance"
        assert entry["DetailType"] == "hitl_approved"
        # Detail is JSON-serialised
        detail = json.loads(entry["Detail"])
        assert detail["eventName"] == "hitl_approved"
        assert detail["userIdentity"]["principalId"] == "alice"
