"""Tests for ModelCandidateDetected event schema (ADR-088 Phase 1.4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.services.model_assurance.adapter_registry import (
    DisqualificationReason,
    ModelProvider,
)
from src.services.model_assurance.scout import (
    EVENT_DETAIL_TYPE,
    EVENT_SOURCE,
    SCHEMA_VERSION,
    EligibilityFlag,
    ModelCandidateDetected,
    make_event,
)


class TestSchemaConstants:
    def test_event_source(self) -> None:
        assert EVENT_SOURCE == "aura.model_assurance.scout"

    def test_event_detail_type(self) -> None:
        assert EVENT_DETAIL_TYPE == "ModelCandidateDetected"

    def test_schema_version(self) -> None:
        assert SCHEMA_VERSION == "1.0"

    def test_eligibility_flag_values(self) -> None:
        flags = {f.value for f in EligibilityFlag}
        assert flags == {
            "qualified",
            "rejected_no_capability",
            "pending_availability",
            "already_known",
        }


class TestMakeEvent:
    def test_make_event_default_timestamp(self) -> None:
        before = datetime.now(timezone.utc)
        ev = make_event(
            candidate_id="m",
            display_name="M",
            provider=ModelProvider.BEDROCK,
            partition="aws",
            eligibility=EligibilityFlag.QUALIFIED,
        )
        after = datetime.now(timezone.utc)
        assert before <= ev.detected_at <= after

    def test_make_event_explicit_timestamp(self) -> None:
        when = datetime(2026, 5, 6, tzinfo=timezone.utc)
        ev = make_event(
            candidate_id="m",
            display_name="M",
            provider=ModelProvider.BEDROCK,
            partition="aws",
            eligibility=EligibilityFlag.QUALIFIED,
            detected_at=when,
        )
        assert ev.detected_at == when

    def test_event_is_frozen(self) -> None:
        ev = make_event(
            candidate_id="m",
            display_name="M",
            provider=ModelProvider.BEDROCK,
            partition="aws",
            eligibility=EligibilityFlag.QUALIFIED,
        )
        try:
            ev.candidate_id = "altered"  # type: ignore[misc]
        except (AttributeError, TypeError):
            pass
        else:
            raise AssertionError("event should be frozen")


class TestEventBridgeDetail:
    def test_serializes_to_dict(self) -> None:
        ev = make_event(
            candidate_id="m",
            display_name="M",
            provider=ModelProvider.BEDROCK,
            partition="aws-us-gov",
            eligibility=EligibilityFlag.PENDING_AVAILABILITY,
            notes="GovCloud lag",
        )
        d = ev.to_eventbridge_detail()
        assert d["candidate_id"] == "m"
        assert d["partition"] == "aws-us-gov"
        assert d["eligibility"] == "pending_availability"
        assert d["schema_version"] == SCHEMA_VERSION
        assert d["provider"] == "bedrock"

    def test_disqualification_reasons_serialised(self) -> None:
        ev = make_event(
            candidate_id="m",
            display_name="M",
            provider=ModelProvider.BEDROCK,
            partition="aws",
            eligibility=EligibilityFlag.REJECTED_NO_CAPABILITY,
            disqualification_reasons=(
                DisqualificationReason.CONTEXT_TOO_SMALL,
                DisqualificationReason.TOOL_USE_REQUIRED,
            ),
        )
        d = ev.to_eventbridge_detail()
        assert d["disqualification_reasons"] == [
            "context_too_small",
            "tool_use_required",
        ]

    def test_detail_is_json_serialisable(self) -> None:
        """EventBridge requires the detail to be a JSON string."""
        ev = make_event(
            candidate_id="m",
            display_name="M",
            provider=ModelProvider.BEDROCK,
            partition="aws",
            eligibility=EligibilityFlag.QUALIFIED,
        )
        # If json.dumps raises, the contract is broken.
        json.dumps(ev.to_eventbridge_detail())

    def test_detected_at_uses_isoformat(self) -> None:
        when = datetime(2026, 5, 6, 12, 34, 56, tzinfo=timezone.utc)
        ev = make_event(
            candidate_id="m",
            display_name="M",
            provider=ModelProvider.BEDROCK,
            partition="aws",
            eligibility=EligibilityFlag.QUALIFIED,
            detected_at=when,
        )
        d = ev.to_eventbridge_detail()
        assert d["detected_at"] == when.isoformat()
