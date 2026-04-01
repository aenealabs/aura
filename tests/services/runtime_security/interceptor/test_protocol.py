"""
Tests for the traffic interception protocol data models.

Covers TrafficEvent, TrafficBatch, TrafficFilter, and TrafficSummary
frozen dataclasses, serialization, hashing, and filter matching.
"""

import dataclasses
import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from src.services.runtime_security.interceptor.protocol import (
    InterceptionPoint,
    TrafficBatch,
    TrafficDirection,
    TrafficEvent,
    TrafficEventType,
    TrafficFilter,
    TrafficSummary,
)

# =========================================================================
# TrafficEvent Tests
# =========================================================================


class TestTrafficEvent:
    """Tests for the TrafficEvent frozen dataclass."""

    def test_required_fields(self, sample_traffic_event: TrafficEvent) -> None:
        """Verify all required fields are populated."""
        assert sample_traffic_event.event_id == "te-abc123def4567890"
        assert sample_traffic_event.source_agent_id == "coder-agent-1"
        assert (
            sample_traffic_event.interception_point
            == InterceptionPoint.CAPABILITY_GOVERNANCE
        )
        assert sample_traffic_event.direction == TrafficDirection.OUTBOUND
        assert sample_traffic_event.event_type == TrafficEventType.AGENT_TO_TOOL
        assert sample_traffic_event.latency_ms == 12.5
        assert isinstance(sample_traffic_event.timestamp, datetime)
        assert sample_traffic_event.payload_hash is not None

    def test_optional_fields_populated(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """Verify optional fields when they are set."""
        assert sample_traffic_event.tool_name == "semantic_search"
        assert sample_traffic_event.session_id == "sess-001"
        assert sample_traffic_event.parent_event_id == "te-parent000000001"
        assert sample_traffic_event.metadata == (
            ("env", "dev"),
            ("region", "us-east-1"),
        )

    def test_optional_fields_defaults(self, now_utc: datetime) -> None:
        """Verify default values for optional fields."""
        event = TrafficEvent(
            event_id="te-defaults00000001",
            timestamp=now_utc,
            source_agent_id="agent-1",
            interception_point=InterceptionPoint.FASTAPI_MIDDLEWARE,
            direction=TrafficDirection.INBOUND,
            event_type=TrafficEventType.AGENT_RESPONSE,
            payload_hash="0" * 64,
            latency_ms=1.0,
        )
        assert event.target_agent_id is None
        assert event.tool_name is None
        assert event.token_count is None
        assert event.approval_required is False
        assert event.approval_decision is None
        assert event.error_message is None
        assert event.session_id is None
        assert event.parent_event_id is None
        assert event.metadata == ()

    def test_frozen_immutability(self, sample_traffic_event: TrafficEvent) -> None:
        """Verify that TrafficEvent cannot be mutated after creation."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_traffic_event.event_id = "te-mutated000000001"  # type: ignore[misc]

    def test_frozen_immutability_latency(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """Verify latency_ms field cannot be mutated."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_traffic_event.latency_ms = 999.0  # type: ignore[misc]

    def test_frozen_immutability_metadata(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """Verify metadata field reference cannot be reassigned."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_traffic_event.metadata = ()  # type: ignore[misc]

    def test_to_dict_all_fields(self, sample_traffic_event: TrafficEvent) -> None:
        """Verify to_dict serializes all fields correctly."""
        d = sample_traffic_event.to_dict()
        assert d["event_id"] == "te-abc123def4567890"
        assert d["source_agent_id"] == "coder-agent-1"
        assert d["interception_point"] == "capability_governance"
        assert d["direction"] == "outbound"
        assert d["event_type"] == "agent_to_tool"
        assert d["latency_ms"] == 12.5
        assert d["tool_name"] == "semantic_search"
        assert d["session_id"] == "sess-001"
        assert d["parent_event_id"] == "te-parent000000001"
        assert d["approval_required"] is False
        assert d["approval_decision"] is None
        assert d["error_message"] is None

    def test_to_dict_timestamp_iso_format(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """Verify timestamp is serialized as ISO 8601 string."""
        d = sample_traffic_event.to_dict()
        parsed = datetime.fromisoformat(d["timestamp"])
        assert parsed == sample_traffic_event.timestamp

    def test_to_dict_metadata_as_dict(self, sample_traffic_event: TrafficEvent) -> None:
        """Verify metadata tuple-of-tuples is serialized as a dict."""
        d = sample_traffic_event.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"] == {"env": "dev", "region": "us-east-1"}

    def test_to_dict_empty_metadata(self, now_utc: datetime) -> None:
        """Verify empty metadata serializes to empty dict."""
        event = TrafficEvent(
            event_id="te-emptymeta000001",
            timestamp=now_utc,
            source_agent_id="agent-x",
            interception_point=InterceptionPoint.FASTAPI_MIDDLEWARE,
            direction=TrafficDirection.INTERNAL,
            event_type=TrafficEventType.CHECKPOINT,
            payload_hash="0" * 64,
            latency_ms=0.0,
        )
        assert event.to_dict()["metadata"] == {}

    def test_to_dict_with_error(
        self, sample_traffic_event_with_error: TrafficEvent
    ) -> None:
        """Verify error_message and token_count are serialized."""
        d = sample_traffic_event_with_error.to_dict()
        assert d["error_message"] == "Rate limit exceeded"
        assert d["token_count"] == 1500

    def test_generate_id_format(self) -> None:
        """Verify generate_id produces IDs with the te- prefix and correct length."""
        event_id = TrafficEvent.generate_id()
        assert event_id.startswith("te-")
        # te- (3 chars) + 16 hex chars = 19 total
        assert len(event_id) == 19

    def test_generate_id_uniqueness(self) -> None:
        """Verify generate_id produces unique IDs across calls."""
        ids = {TrafficEvent.generate_id() for _ in range(100)}
        assert len(ids) == 100

    def test_hash_payload_deterministic(self, sample_payload: str) -> None:
        """Verify hash_payload produces consistent results for same input."""
        h1 = TrafficEvent.hash_payload(sample_payload)
        h2 = TrafficEvent.hash_payload(sample_payload)
        assert h1 == h2

    def test_hash_payload_sha256(
        self, sample_payload: str, sample_payload_hash: str
    ) -> None:
        """Verify hash_payload produces correct SHA-256 hash."""
        result = TrafficEvent.hash_payload(sample_payload)
        assert result == sample_payload_hash
        assert len(result) == 64  # SHA-256 hex digest length

    def test_hash_payload_different_inputs(self) -> None:
        """Verify different payloads produce different hashes."""
        h1 = TrafficEvent.hash_payload("payload A")
        h2 = TrafficEvent.hash_payload("payload B")
        assert h1 != h2

    def test_hash_payload_empty_string(self) -> None:
        """Verify hash_payload handles empty string."""
        result = TrafficEvent.hash_payload("")
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_event_with_approval_fields(self, now_utc: datetime) -> None:
        """Verify approval_required and approval_decision work together."""
        event = TrafficEvent(
            event_id="te-approval0000001",
            timestamp=now_utc,
            source_agent_id="admission-ctrl",
            interception_point=InterceptionPoint.K8S_ADMISSION,
            direction=TrafficDirection.INBOUND,
            event_type=TrafficEventType.ADMISSION,
            payload_hash="f" * 64,
            latency_ms=5.0,
            approval_required=True,
            approval_decision="denied",
        )
        assert event.approval_required is True
        assert event.approval_decision == "denied"
        d = event.to_dict()
        assert d["approval_required"] is True
        assert d["approval_decision"] == "denied"


# =========================================================================
# TrafficBatch Tests
# =========================================================================


class TestTrafficBatch:
    """Tests for the TrafficBatch frozen dataclass."""

    def test_batch_creation(
        self,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify batch creation with events tuple."""
        batch = TrafficBatch(
            batch_id="tb-test0000000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        assert batch.batch_id == "tb-test0000000001"
        assert batch.source == "interceptor"
        assert isinstance(batch.events, tuple)
        assert len(batch.events) == 5

    def test_batch_size_property(
        self, multiple_events: list[TrafficEvent], now_utc: datetime
    ) -> None:
        """Verify size property returns event count."""
        batch = TrafficBatch(
            batch_id="tb-size0000000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        assert batch.size == 5

    def test_batch_size_empty(self, now_utc: datetime) -> None:
        """Verify size is 0 for empty batch."""
        batch = TrafficBatch(
            batch_id="tb-empty000000001",
            events=(),
            created_at=now_utc,
        )
        assert batch.size == 0

    def test_batch_event_ids(
        self, multiple_events: list[TrafficEvent], now_utc: datetime
    ) -> None:
        """Verify event_ids property returns all IDs in order."""
        batch = TrafficBatch(
            batch_id="tb-ids00000000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        expected_ids = tuple(e.event_id for e in multiple_events)
        assert batch.event_ids == expected_ids

    def test_batch_frozen(self, now_utc: datetime) -> None:
        """Verify TrafficBatch is immutable."""
        batch = TrafficBatch(
            batch_id="tb-frozen00000001",
            events=(),
            created_at=now_utc,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            batch.batch_id = "tb-mutated0000001"  # type: ignore[misc]

    def test_batch_to_dict(
        self, multiple_events: list[TrafficEvent], now_utc: datetime
    ) -> None:
        """Verify batch to_dict serialization."""
        batch = TrafficBatch(
            batch_id="tb-dict0000000001",
            events=tuple(multiple_events[:2]),
            created_at=now_utc,
        )
        d = batch.to_dict()
        assert d["batch_id"] == "tb-dict0000000001"
        assert d["source"] == "interceptor"
        assert d["size"] == 2
        assert isinstance(d["events"], list)
        assert len(d["events"]) == 2
        assert isinstance(d["created_at"], str)
        datetime.fromisoformat(d["created_at"])  # Must not raise

    def test_batch_generate_id_format(self) -> None:
        """Verify batch ID has tb- prefix and correct length."""
        batch_id = TrafficBatch.generate_id()
        assert batch_id.startswith("tb-")
        assert len(batch_id) == 19

    def test_batch_generate_id_uniqueness(self) -> None:
        """Verify batch IDs are unique."""
        ids = {TrafficBatch.generate_id() for _ in range(50)}
        assert len(ids) == 50

    def test_batch_custom_source(self, now_utc: datetime) -> None:
        """Verify custom source field."""
        batch = TrafficBatch(
            batch_id="tb-custom00000001",
            events=(),
            created_at=now_utc,
            source="analysis_pipeline",
        )
        assert batch.source == "analysis_pipeline"
        assert batch.to_dict()["source"] == "analysis_pipeline"


# =========================================================================
# TrafficFilter Tests
# =========================================================================


class TestTrafficFilter:
    """Tests for the TrafficFilter frozen dataclass and matches() method."""

    def test_empty_filter_matches_all(self, sample_traffic_event: TrafficEvent) -> None:
        """An empty filter with no criteria should match any event."""
        f = TrafficFilter()
        assert f.matches(sample_traffic_event) is True

    def test_filter_by_source_agent_match(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """Filter by source_agent_id that matches."""
        f = TrafficFilter(source_agent_id="coder-agent-1")
        assert f.matches(sample_traffic_event) is True

    def test_filter_by_source_agent_no_match(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """Filter by source_agent_id that does not match."""
        f = TrafficFilter(source_agent_id="reviewer-agent-99")
        assert f.matches(sample_traffic_event) is False

    def test_filter_by_target_agent_match(
        self, sample_agent_message_event: TrafficEvent
    ) -> None:
        """Filter by target_agent_id that matches."""
        f = TrafficFilter(target_agent_id="coder-agent-1")
        assert f.matches(sample_agent_message_event) is True

    def test_filter_by_target_agent_no_match(
        self, sample_agent_message_event: TrafficEvent
    ) -> None:
        """Filter by target_agent_id that does not match."""
        f = TrafficFilter(target_agent_id="nonexistent-agent")
        assert f.matches(sample_agent_message_event) is False

    def test_filter_by_interception_point(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """Filter by interception_point."""
        f = TrafficFilter(interception_point=InterceptionPoint.CAPABILITY_GOVERNANCE)
        assert f.matches(sample_traffic_event) is True

        f2 = TrafficFilter(interception_point=InterceptionPoint.K8S_ADMISSION)
        assert f2.matches(sample_traffic_event) is False

    def test_filter_by_event_type(self, sample_traffic_event: TrafficEvent) -> None:
        """Filter by event_type."""
        f = TrafficFilter(event_type=TrafficEventType.AGENT_TO_TOOL)
        assert f.matches(sample_traffic_event) is True

        f2 = TrafficFilter(event_type=TrafficEventType.CHECKPOINT)
        assert f2.matches(sample_traffic_event) is False

    def test_filter_by_direction(self, sample_traffic_event: TrafficEvent) -> None:
        """Filter by direction."""
        f = TrafficFilter(direction=TrafficDirection.OUTBOUND)
        assert f.matches(sample_traffic_event) is True

        f2 = TrafficFilter(direction=TrafficDirection.INBOUND)
        assert f2.matches(sample_traffic_event) is False

    def test_filter_by_start_time(
        self, now_utc: datetime, sample_traffic_event: TrafficEvent
    ) -> None:
        """Filter by start_time (event must be >= start_time)."""
        before = now_utc - timedelta(minutes=10)
        f = TrafficFilter(start_time=before)
        assert f.matches(sample_traffic_event) is True

        after = now_utc + timedelta(minutes=10)
        f2 = TrafficFilter(start_time=after)
        assert f2.matches(sample_traffic_event) is False

    def test_filter_by_end_time(
        self, now_utc: datetime, sample_traffic_event: TrafficEvent
    ) -> None:
        """Filter by end_time (event must be <= end_time)."""
        after = now_utc + timedelta(minutes=10)
        f = TrafficFilter(end_time=after)
        assert f.matches(sample_traffic_event) is True

        before = now_utc - timedelta(minutes=10)
        f2 = TrafficFilter(end_time=before)
        assert f2.matches(sample_traffic_event) is False

    def test_filter_by_time_range(
        self, now_utc: datetime, sample_traffic_event: TrafficEvent
    ) -> None:
        """Filter by both start_time and end_time."""
        f = TrafficFilter(
            start_time=now_utc - timedelta(minutes=1),
            end_time=now_utc + timedelta(minutes=1),
        )
        assert f.matches(sample_traffic_event) is True

    def test_filter_by_tool_name(self, sample_traffic_event: TrafficEvent) -> None:
        """Filter by tool_name."""
        f = TrafficFilter(tool_name="semantic_search")
        assert f.matches(sample_traffic_event) is True

        f2 = TrafficFilter(tool_name="code_formatter")
        assert f2.matches(sample_traffic_event) is False

    def test_filter_by_session_id(self, sample_traffic_event: TrafficEvent) -> None:
        """Filter by session_id."""
        f = TrafficFilter(session_id="sess-001")
        assert f.matches(sample_traffic_event) is True

        f2 = TrafficFilter(session_id="sess-999")
        assert f2.matches(sample_traffic_event) is False

    def test_filter_by_has_error_true(
        self, sample_traffic_event_with_error: TrafficEvent
    ) -> None:
        """Filter for events that have errors."""
        f = TrafficFilter(has_error=True)
        assert f.matches(sample_traffic_event_with_error) is True

    def test_filter_by_has_error_false(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """Filter for events that do not have errors."""
        f = TrafficFilter(has_error=False)
        assert f.matches(sample_traffic_event) is True

    def test_filter_has_error_true_on_no_error_event(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """has_error=True should not match an event without error_message."""
        f = TrafficFilter(has_error=True)
        assert f.matches(sample_traffic_event) is False

    def test_filter_has_error_false_on_error_event(
        self,
        sample_traffic_event_with_error: TrafficEvent,
    ) -> None:
        """has_error=False should not match an event with error_message."""
        f = TrafficFilter(has_error=False)
        assert f.matches(sample_traffic_event_with_error) is False

    def test_filter_combined_criteria(self, sample_traffic_event: TrafficEvent) -> None:
        """Filter with multiple criteria must all match."""
        f = TrafficFilter(
            source_agent_id="coder-agent-1",
            event_type=TrafficEventType.AGENT_TO_TOOL,
            direction=TrafficDirection.OUTBOUND,
            tool_name="semantic_search",
            session_id="sess-001",
            has_error=False,
        )
        assert f.matches(sample_traffic_event) is True

    def test_filter_combined_one_mismatch(
        self, sample_traffic_event: TrafficEvent
    ) -> None:
        """If any single criterion in a combined filter mismatches, result is False."""
        f = TrafficFilter(
            source_agent_id="coder-agent-1",
            event_type=TrafficEventType.AGENT_TO_TOOL,
            direction=TrafficDirection.INBOUND,  # Mismatch
        )
        assert f.matches(sample_traffic_event) is False

    def test_filter_frozen(self) -> None:
        """Verify TrafficFilter is immutable."""
        f = TrafficFilter(source_agent_id="agent-1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.source_agent_id = "agent-2"  # type: ignore[misc]

    def test_filter_default_max_results(self) -> None:
        """Verify default max_results is 1000."""
        f = TrafficFilter()
        assert f.max_results == 1000


# =========================================================================
# TrafficSummary Tests
# =========================================================================


class TestTrafficSummary:
    """Tests for the TrafficSummary frozen dataclass."""

    def test_summary_creation(self, now_utc: datetime) -> None:
        """Verify TrafficSummary can be created with all fields."""
        summary = TrafficSummary(
            total_events=100,
            unique_agents=5,
            unique_tools=3,
            events_by_type=(
                ("agent_to_tool", 50),
                ("agent_to_llm", 30),
                ("checkpoint", 20),
            ),
            events_by_interception_point=(
                ("capability_governance", 50),
                ("llm_prompt_sanitizer", 30),
            ),
            avg_latency_ms=25.123456,
            p95_latency_ms=150.789012,
            total_tokens=50000,
            error_count=5,
            error_rate=0.05,
            time_range_start=now_utc - timedelta(hours=1),
            time_range_end=now_utc,
        )
        assert summary.total_events == 100
        assert summary.unique_agents == 5
        assert summary.unique_tools == 3

    def test_summary_frozen(self, now_utc: datetime) -> None:
        """Verify TrafficSummary is immutable."""
        summary = TrafficSummary(
            total_events=10,
            unique_agents=2,
            unique_tools=1,
            events_by_type=(),
            events_by_interception_point=(),
            avg_latency_ms=5.0,
            p95_latency_ms=10.0,
            total_tokens=500,
            error_count=0,
            error_rate=0.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            summary.total_events = 999  # type: ignore[misc]

    def test_summary_to_dict(self, now_utc: datetime) -> None:
        """Verify to_dict serialization with rounding."""
        start = now_utc - timedelta(hours=1)
        end = now_utc
        summary = TrafficSummary(
            total_events=42,
            unique_agents=3,
            unique_tools=2,
            events_by_type=(("agent_to_tool", 30), ("checkpoint", 12)),
            events_by_interception_point=(
                ("capability_governance", 30),
                ("execution_checkpoint", 12),
            ),
            avg_latency_ms=15.123456789,
            p95_latency_ms=100.987654321,
            total_tokens=12000,
            error_count=2,
            error_rate=0.047619,
            time_range_start=start,
            time_range_end=end,
        )
        d = summary.to_dict()
        assert d["total_events"] == 42
        assert d["unique_agents"] == 3
        assert d["unique_tools"] == 2
        assert d["events_by_type"] == {"agent_to_tool": 30, "checkpoint": 12}
        assert d["events_by_interception_point"] == {
            "capability_governance": 30,
            "execution_checkpoint": 12,
        }
        # Verify rounding
        assert d["avg_latency_ms"] == round(15.123456789, 3)
        assert d["p95_latency_ms"] == round(100.987654321, 3)
        assert d["error_rate"] == round(0.047619, 4)
        assert d["total_tokens"] == 12000
        assert d["error_count"] == 2
        # Verify time range serialization
        assert d["time_range_start"] == start.isoformat()
        assert d["time_range_end"] == end.isoformat()

    def test_summary_to_dict_none_time_range(self) -> None:
        """Verify to_dict when time range is None."""
        summary = TrafficSummary(
            total_events=0,
            unique_agents=0,
            unique_tools=0,
            events_by_type=(),
            events_by_interception_point=(),
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            total_tokens=0,
            error_count=0,
            error_rate=0.0,
        )
        d = summary.to_dict()
        assert d["time_range_start"] is None
        assert d["time_range_end"] is None

    def test_summary_empty(self) -> None:
        """Verify empty summary has zero values."""
        summary = TrafficSummary(
            total_events=0,
            unique_agents=0,
            unique_tools=0,
            events_by_type=(),
            events_by_interception_point=(),
            avg_latency_ms=0.0,
            p95_latency_ms=0.0,
            total_tokens=0,
            error_count=0,
            error_rate=0.0,
        )
        assert summary.total_events == 0
        assert summary.error_rate == 0.0


# =========================================================================
# Enum Tests
# =========================================================================


class TestEnums:
    """Tests for protocol enum values."""

    def test_interception_point_values(self) -> None:
        """Verify all InterceptionPoint enum members."""
        assert InterceptionPoint.FASTAPI_MIDDLEWARE.value == "fastapi_middleware"
        assert InterceptionPoint.CAPABILITY_GOVERNANCE.value == "capability_governance"
        assert InterceptionPoint.LLM_PROMPT_SANITIZER.value == "llm_prompt_sanitizer"
        assert InterceptionPoint.MCP_TOOL_SERVER.value == "mcp_tool_server"
        assert InterceptionPoint.EXECUTION_CHECKPOINT.value == "execution_checkpoint"
        assert InterceptionPoint.K8S_ADMISSION.value == "k8s_admission"
        assert InterceptionPoint.CONTAINER_ESCAPE.value == "container_escape"
        assert InterceptionPoint.CONSTITUTIONAL_AI.value == "constitutional_ai"
        assert len(InterceptionPoint) == 8

    def test_traffic_direction_values(self) -> None:
        """Verify all TrafficDirection enum members."""
        assert TrafficDirection.INBOUND.value == "inbound"
        assert TrafficDirection.OUTBOUND.value == "outbound"
        assert TrafficDirection.INTERNAL.value == "internal"
        assert len(TrafficDirection) == 3

    def test_traffic_event_type_values(self) -> None:
        """Verify all TrafficEventType enum members."""
        assert TrafficEventType.AGENT_TO_AGENT.value == "agent_to_agent"
        assert TrafficEventType.AGENT_TO_TOOL.value == "agent_to_tool"
        assert TrafficEventType.AGENT_TO_LLM.value == "agent_to_llm"
        assert TrafficEventType.TOOL_RESPONSE.value == "tool_response"
        assert TrafficEventType.LLM_RESPONSE.value == "llm_response"
        assert TrafficEventType.AGENT_RESPONSE.value == "agent_response"
        assert TrafficEventType.CHECKPOINT.value == "checkpoint"
        assert TrafficEventType.ADMISSION.value == "admission"
        assert TrafficEventType.ESCAPE_ALERT.value == "escape_alert"
        assert len(TrafficEventType) == 9
