"""Tests for audit event contracts (ADR-088 Phase 3.4)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.model_assurance.audit import (
    EVENT_NIST_MAPPING,
    AuditEvent,
    AuditEventType,
    NISTControl,
)


class TestNISTControls:
    def test_six_controls(self) -> None:
        assert len(list(NISTControl)) == 6

    def test_control_values(self) -> None:
        values = {c.value for c in NISTControl}
        assert values == {"CM-3", "CM-5", "SA-10", "SI-7", "RA-5", "AU-3"}


class TestEventTypes:
    def test_thirteen_event_types_present(self) -> None:
        # Discovery, provenance verified+failed, sandbox provisioned+teardown,
        # oracle started+completed, report, hitl approved+rejected,
        # deployment, rollback initiated+applied
        assert len(list(AuditEventType)) == 13


class TestNISTMapping:
    def test_every_event_has_at_least_au3(self) -> None:
        """AU-3 (audit-record content) applies to every event by definition."""
        for event_type in AuditEventType:
            mapped = EVENT_NIST_MAPPING.get(event_type, ())
            assert NISTControl.AU_3 in mapped, (
                f"{event_type.value} missing AU-3 mapping"
            )

    def test_hitl_events_carry_change_control(self) -> None:
        for event_type in (
            AuditEventType.HITL_APPROVED,
            AuditEventType.HITL_REJECTED,
            AuditEventType.DEPLOYMENT_APPLIED,
        ):
            mapped = EVENT_NIST_MAPPING[event_type]
            assert NISTControl.CM_3 in mapped
            assert NISTControl.CM_5 in mapped

    def test_provenance_events_carry_si7_and_sa10(self) -> None:
        for event_type in (
            AuditEventType.PROVENANCE_VERIFIED,
            AuditEventType.PROVENANCE_FAILED,
        ):
            mapped = EVENT_NIST_MAPPING[event_type]
            assert NISTControl.SI_7 in mapped
            assert NISTControl.SA_10 in mapped

    def test_sandbox_and_oracle_carry_ra5(self) -> None:
        for event_type in (
            AuditEventType.SANDBOX_PROVISIONED,
            AuditEventType.SANDBOX_TEARDOWN,
            AuditEventType.ORACLE_EVALUATION_STARTED,
            AuditEventType.ORACLE_EVALUATION_COMPLETED,
        ):
            mapped = EVENT_NIST_MAPPING[event_type]
            assert NISTControl.RA_5 in mapped

    def test_rollback_events_carry_cm3(self) -> None:
        for event_type in (
            AuditEventType.ROLLBACK_INITIATED,
            AuditEventType.ROLLBACK_APPLIED,
        ):
            assert NISTControl.CM_3 in EVENT_NIST_MAPPING[event_type]


class TestAuditEvent:
    def _event(self) -> AuditEvent:
        return AuditEvent(
            event_id="abc",
            event_type=AuditEventType.HITL_APPROVED,
            candidate_id="m",
            occurred_at=datetime(2026, 5, 6, tzinfo=timezone.utc),
            actor="alice",
            correlation_id="run-1",
            request_parameters=(("k", "v"),),
            response_elements=(("rk", "rv"),),
        )

    def test_immutability(self) -> None:
        event = self._event()
        with pytest.raises((AttributeError, TypeError)):
            event.event_id = "x"  # type: ignore[misc]

    def test_applicable_controls_uses_mapping(self) -> None:
        event = self._event()
        controls = set(event.applicable_controls)
        assert NISTControl.CM_3 in controls
        assert NISTControl.CM_5 in controls
        assert NISTControl.AU_3 in controls

    def test_request_and_response_dicts(self) -> None:
        event = self._event()
        assert event.request_dict == {"k": "v"}
        assert event.response_dict == {"rk": "rv"}

    def test_cloudtrail_record_shape(self) -> None:
        event = self._event()
        record = event.to_cloudtrail_record()
        assert record["eventVersion"] == "1.10"
        assert record["eventName"] == "hitl_approved"
        assert record["eventSource"] == "aura.model_assurance"
        assert record["userIdentity"]["principalId"] == "alice"
        assert record["additionalEventData"]["candidate_id"] == "m"
        assert "CM-3" in record["additionalEventData"]["applicable_controls"]
