"""
Tests for the TrafficStorageAdapter.

Covers mock storage operations: store_event, store_batch, query_events,
get_event, get_payload, compute_summary, delete_events_before,
and singleton management.
"""

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
from src.services.runtime_security.interceptor.storage import (
    TrafficStorageAdapter,
    get_traffic_storage,
    reset_traffic_storage,
)

# =========================================================================
# store_event Tests
# =========================================================================


class TestStoreEvent:
    """Tests for TrafficStorageAdapter.store_event."""

    @pytest.mark.asyncio
    async def test_store_event_basic(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify storing a single event returns True."""
        result = await mock_storage.store_event(sample_traffic_event)
        assert result is True
        assert mock_storage.event_count == 1

    @pytest.mark.asyncio
    async def test_store_event_with_payload(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify storing event with payload stores both."""
        result = await mock_storage.store_event(
            sample_traffic_event,
            payload="full payload data",
        )
        assert result is True
        assert (
            mock_storage._mock_payloads[sample_traffic_event.event_id]
            == "full payload data"
        )

    @pytest.mark.asyncio
    async def test_store_event_without_payload(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify storing event without payload does not add to payload store."""
        await mock_storage.store_event(sample_traffic_event, payload=None)
        assert sample_traffic_event.event_id not in mock_storage._mock_payloads

    @pytest.mark.asyncio
    async def test_store_event_increments_write_count(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify write_count increments on each store."""
        assert mock_storage.write_count == 0
        await mock_storage.store_event(sample_traffic_event)
        assert mock_storage.write_count == 1

    @pytest.mark.asyncio
    async def test_store_event_overwrite(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Storing an event with the same ID overwrites the previous entry."""
        await mock_storage.store_event(sample_traffic_event, payload="first")
        await mock_storage.store_event(sample_traffic_event, payload="second")
        assert mock_storage.event_count == 1
        assert mock_storage._mock_payloads[sample_traffic_event.event_id] == "second"


# =========================================================================
# store_batch Tests
# =========================================================================


class TestStoreBatch:
    """Tests for TrafficStorageAdapter.store_batch."""

    @pytest.mark.asyncio
    async def test_store_batch_basic(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify batch storage returns correct count."""
        batch = TrafficBatch(
            batch_id="tb-test0000000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        stored = await mock_storage.store_batch(batch)
        assert stored == 5
        assert mock_storage.event_count == 5

    @pytest.mark.asyncio
    async def test_store_batch_with_payloads(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify batch storage with payload map."""
        payloads = {
            multiple_events[0].event_id: "payload-0",
            multiple_events[2].event_id: "payload-2",
        }
        batch = TrafficBatch(
            batch_id="tb-payloads000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        stored = await mock_storage.store_batch(batch, payloads=payloads)
        assert stored == 5
        assert mock_storage._mock_payloads[multiple_events[0].event_id] == "payload-0"
        assert mock_storage._mock_payloads[multiple_events[2].event_id] == "payload-2"
        assert multiple_events[1].event_id not in mock_storage._mock_payloads

    @pytest.mark.asyncio
    async def test_store_batch_empty(
        self,
        mock_storage: TrafficStorageAdapter,
        now_utc: datetime,
    ) -> None:
        """Storing an empty batch returns 0."""
        batch = TrafficBatch(
            batch_id="tb-empty000000001",
            events=(),
            created_at=now_utc,
        )
        stored = await mock_storage.store_batch(batch)
        assert stored == 0
        assert mock_storage.event_count == 0

    @pytest.mark.asyncio
    async def test_store_batch_write_count(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify write_count increments per event in batch."""
        batch = TrafficBatch(
            batch_id="tb-wcount0000001",
            events=tuple(multiple_events[:3]),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        assert mock_storage.write_count == 3


# =========================================================================
# query_events Tests
# =========================================================================


class TestQueryEvents:
    """Tests for TrafficStorageAdapter.query_events."""

    @pytest.mark.asyncio
    async def test_query_empty_storage(
        self, mock_storage: TrafficStorageAdapter
    ) -> None:
        """Querying empty storage returns empty list."""
        results = await mock_storage.query_events(TrafficFilter())
        assert results == []

    @pytest.mark.asyncio
    async def test_query_all_events(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Empty filter returns all stored events."""
        batch = TrafficBatch(
            batch_id="tb-queryall00001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        results = await mock_storage.query_events(TrafficFilter())
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_query_by_source_agent(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Filter by source_agent_id returns matching events."""
        batch = TrafficBatch(
            batch_id="tb-qsource00001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        results = await mock_storage.query_events(
            TrafficFilter(source_agent_id="coder-agent-1"),
        )
        assert all(e.source_agent_id == "coder-agent-1" for e in results)
        assert len(results) == 3  # events 1, 2 (a2a from coder), 5

    @pytest.mark.asyncio
    async def test_query_by_event_type(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Filter by event_type returns matching events."""
        batch = TrafficBatch(
            batch_id="tb-qtype0000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        results = await mock_storage.query_events(
            TrafficFilter(event_type=TrafficEventType.AGENT_TO_TOOL),
        )
        assert all(e.event_type == TrafficEventType.AGENT_TO_TOOL for e in results)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_by_has_error(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Filter by has_error returns events with error_message."""
        batch = TrafficBatch(
            batch_id="tb-qerror00001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        results = await mock_storage.query_events(TrafficFilter(has_error=True))
        assert len(results) == 1
        assert results[0].error_message is not None

    @pytest.mark.asyncio
    async def test_query_max_results(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify max_results limits the number of returned events."""
        batch = TrafficBatch(
            batch_id="tb-qmax00000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        results = await mock_storage.query_events(TrafficFilter(max_results=2))
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_sorted_by_timestamp_desc(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify query results are sorted by timestamp descending."""
        batch = TrafficBatch(
            batch_id="tb-qsort0000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        results = await mock_storage.query_events(TrafficFilter())
        timestamps = [e.timestamp for e in results]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_query_increments_read_count(
        self,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify read_count increments on query."""
        assert mock_storage.read_count == 0
        await mock_storage.query_events(TrafficFilter())
        assert mock_storage.read_count == 1

    @pytest.mark.asyncio
    async def test_query_by_session_id(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Filter by session_id returns matching events."""
        batch = TrafficBatch(
            batch_id="tb-qsess0000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        results = await mock_storage.query_events(
            TrafficFilter(session_id="sess-batch-1"),
        )
        assert all(e.session_id == "sess-batch-1" for e in results)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_combined_filters(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Combined filter criteria narrows results correctly."""
        batch = TrafficBatch(
            batch_id="tb-qcombo000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        results = await mock_storage.query_events(
            TrafficFilter(
                source_agent_id="coder-agent-1",
                event_type=TrafficEventType.AGENT_TO_TOOL,
                session_id="sess-batch-1",
            ),
        )
        assert len(results) == 1
        assert results[0].tool_name == "semantic_search"


# =========================================================================
# get_event Tests
# =========================================================================


class TestGetEvent:
    """Tests for TrafficStorageAdapter.get_event."""

    @pytest.mark.asyncio
    async def test_get_event_found(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify retrieval of a stored event by ID."""
        await mock_storage.store_event(sample_traffic_event)
        retrieved = await mock_storage.get_event(sample_traffic_event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == sample_traffic_event.event_id
        assert retrieved.source_agent_id == sample_traffic_event.source_agent_id
        assert retrieved.interception_point == sample_traffic_event.interception_point

    @pytest.mark.asyncio
    async def test_get_event_not_found(
        self,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify None is returned for nonexistent event ID."""
        result = await mock_storage.get_event("te-doesnotexist001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_event_increments_read_count(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify read_count increments on get_event."""
        await mock_storage.store_event(sample_traffic_event)
        await mock_storage.get_event(sample_traffic_event.event_id)
        assert mock_storage.read_count == 1

    @pytest.mark.asyncio
    async def test_get_event_preserves_metadata(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify metadata round-trips correctly through store/retrieve."""
        await mock_storage.store_event(sample_traffic_event)
        retrieved = await mock_storage.get_event(sample_traffic_event.event_id)
        assert retrieved is not None
        assert dict(retrieved.metadata) == dict(sample_traffic_event.metadata)

    @pytest.mark.asyncio
    async def test_get_event_preserves_optional_fields(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event_with_error: TrafficEvent,
    ) -> None:
        """Verify error_message and token_count round-trip correctly."""
        await mock_storage.store_event(sample_traffic_event_with_error)
        retrieved = await mock_storage.get_event(
            sample_traffic_event_with_error.event_id
        )
        assert retrieved is not None
        assert retrieved.error_message == "Rate limit exceeded"
        assert retrieved.token_count == 1500


# =========================================================================
# get_payload Tests
# =========================================================================


class TestGetPayload:
    """Tests for TrafficStorageAdapter.get_payload."""

    @pytest.mark.asyncio
    async def test_get_payload_found(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify retrieval of stored payload."""
        await mock_storage.store_event(sample_traffic_event, payload="secret payload")
        result = await mock_storage.get_payload(sample_traffic_event.event_id)
        assert result == "secret payload"

    @pytest.mark.asyncio
    async def test_get_payload_not_found(
        self,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify None is returned when no payload exists."""
        result = await mock_storage.get_payload("te-nopayload000001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_payload_event_stored_without_payload(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify None when event was stored without a payload."""
        await mock_storage.store_event(sample_traffic_event, payload=None)
        result = await mock_storage.get_payload(sample_traffic_event.event_id)
        assert result is None


# =========================================================================
# compute_summary Tests
# =========================================================================


class TestComputeSummary:
    """Tests for TrafficStorageAdapter.compute_summary."""

    @pytest.mark.asyncio
    async def test_summary_empty_storage(
        self,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Summary of empty storage has all zero values."""
        summary = await mock_storage.compute_summary(TrafficFilter())
        assert summary.total_events == 0
        assert summary.unique_agents == 0
        assert summary.unique_tools == 0
        assert summary.avg_latency_ms == 0.0
        assert summary.p95_latency_ms == 0.0
        assert summary.total_tokens == 0
        assert summary.error_count == 0
        assert summary.error_rate == 0.0
        assert summary.time_range_start is None
        assert summary.time_range_end is None

    @pytest.mark.asyncio
    async def test_summary_with_events(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Summary computes correct aggregate statistics."""
        batch = TrafficBatch(
            batch_id="tb-summary000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        summary = await mock_storage.compute_summary(TrafficFilter())

        assert summary.total_events == 5
        # Unique agents: coder-agent-1 (source), reviewer-agent-1 (source + target),
        # validator-agent-1 (source) = 3 unique
        assert summary.unique_agents == 3
        # Unique tools: semantic_search, code_formatter
        assert summary.unique_tools == 2
        # Total tokens: 100 + 2000 = 2100
        assert summary.total_tokens == 2100
        # 1 event has error_message
        assert summary.error_count == 1
        assert summary.error_rate == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_summary_avg_latency(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify average latency computation."""
        batch = TrafficBatch(
            batch_id="tb-avglatency001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        summary = await mock_storage.compute_summary(TrafficFilter())

        expected_avg = (10.0 + 5.0 + 200.0 + 0.0 + 15.0) / 5.0
        assert summary.avg_latency_ms == pytest.approx(expected_avg)

    @pytest.mark.asyncio
    async def test_summary_p95_latency(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify p95 latency is from the sorted latencies."""
        batch = TrafficBatch(
            batch_id="tb-p95latency01",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        summary = await mock_storage.compute_summary(TrafficFilter())

        # Latencies sorted: [0.0, 5.0, 10.0, 15.0, 200.0]
        # p95 index = int(5 * 0.95) = 4 -> 200.0
        assert summary.p95_latency_ms == 200.0

    @pytest.mark.asyncio
    async def test_summary_time_range(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify time range boundaries are set from event timestamps."""
        batch = TrafficBatch(
            batch_id="tb-timerange001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        summary = await mock_storage.compute_summary(TrafficFilter())

        assert summary.time_range_start is not None
        assert summary.time_range_end is not None
        assert summary.time_range_start <= summary.time_range_end

    @pytest.mark.asyncio
    async def test_summary_events_by_type(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify events_by_type breakdown."""
        batch = TrafficBatch(
            batch_id="tb-bytype0000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        summary = await mock_storage.compute_summary(TrafficFilter())

        by_type = dict(summary.events_by_type)
        assert by_type["agent_to_tool"] == 2
        assert by_type["agent_to_agent"] == 1
        assert by_type["agent_to_llm"] == 1
        assert by_type["checkpoint"] == 1

    @pytest.mark.asyncio
    async def test_summary_events_by_interception_point(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify events_by_interception_point breakdown."""
        batch = TrafficBatch(
            batch_id="tb-bypoint00001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        summary = await mock_storage.compute_summary(TrafficFilter())

        by_point = dict(summary.events_by_interception_point)
        assert by_point["capability_governance"] == 1
        assert by_point["fastapi_middleware"] == 1
        assert by_point["llm_prompt_sanitizer"] == 1
        assert by_point["execution_checkpoint"] == 1
        assert by_point["mcp_tool_server"] == 1

    @pytest.mark.asyncio
    async def test_summary_with_filter(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify summary respects filter criteria."""
        batch = TrafficBatch(
            batch_id="tb-sumfilter001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        summary = await mock_storage.compute_summary(
            TrafficFilter(source_agent_id="coder-agent-1"),
        )
        assert summary.total_events == 3

    @pytest.mark.asyncio
    async def test_summary_is_traffic_summary_type(
        self,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify compute_summary returns a TrafficSummary instance."""
        summary = await mock_storage.compute_summary(TrafficFilter())
        assert isinstance(summary, TrafficSummary)


# =========================================================================
# delete_events_before Tests
# =========================================================================


class TestDeleteEventsBefore:
    """Tests for TrafficStorageAdapter.delete_events_before."""

    @pytest.mark.asyncio
    async def test_delete_events_before_cutoff(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify events before cutoff are deleted."""
        batch = TrafficBatch(
            batch_id="tb-delete0000001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        assert mock_storage.event_count == 5

        # Delete events older than 3 minutes ago (events at -5m, -4m, -3m)
        cutoff = now_utc - timedelta(minutes=2, seconds=30)
        deleted = await mock_storage.delete_events_before(cutoff)
        assert deleted == 3
        assert mock_storage.event_count == 2

    @pytest.mark.asyncio
    async def test_delete_events_none_match(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """When no events are before cutoff, nothing is deleted."""
        batch = TrafficBatch(
            batch_id="tb-delnone00001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        # Cutoff far in the past
        cutoff = now_utc - timedelta(days=365)
        deleted = await mock_storage.delete_events_before(cutoff)
        assert deleted == 0
        assert mock_storage.event_count == 5

    @pytest.mark.asyncio
    async def test_delete_events_all_match(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Delete all events when cutoff is in the future."""
        batch = TrafficBatch(
            batch_id="tb-delall00001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch)
        cutoff = now_utc + timedelta(hours=1)
        deleted = await mock_storage.delete_events_before(cutoff)
        assert deleted == 5
        assert mock_storage.event_count == 0

    @pytest.mark.asyncio
    async def test_delete_events_removes_payloads(
        self,
        mock_storage: TrafficStorageAdapter,
        multiple_events: list[TrafficEvent],
        now_utc: datetime,
    ) -> None:
        """Verify associated payloads are also deleted."""
        payloads = {
            multiple_events[0].event_id: "payload-oldest",
            multiple_events[4].event_id: "payload-newest",
        }
        batch = TrafficBatch(
            batch_id="tb-delpay00001",
            events=tuple(multiple_events),
            created_at=now_utc,
        )
        await mock_storage.store_batch(batch, payloads=payloads)
        # Delete all
        cutoff = now_utc + timedelta(hours=1)
        await mock_storage.delete_events_before(cutoff)
        assert await mock_storage.get_payload(multiple_events[0].event_id) is None
        assert await mock_storage.get_payload(multiple_events[4].event_id) is None

    @pytest.mark.asyncio
    async def test_delete_empty_storage(
        self,
        mock_storage: TrafficStorageAdapter,
        now_utc: datetime,
    ) -> None:
        """Deleting from empty storage returns 0."""
        deleted = await mock_storage.delete_events_before(now_utc)
        assert deleted == 0


# =========================================================================
# dict_to_event Round-Trip Tests
# =========================================================================


class TestDictToEvent:
    """Tests for the _dict_to_event static helper."""

    @pytest.mark.asyncio
    async def test_round_trip_through_storage(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_traffic_event: TrafficEvent,
    ) -> None:
        """Verify event survives a store -> retrieve round-trip."""
        await mock_storage.store_event(sample_traffic_event)
        retrieved = await mock_storage.get_event(sample_traffic_event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == sample_traffic_event.event_id
        assert retrieved.timestamp == sample_traffic_event.timestamp
        assert retrieved.source_agent_id == sample_traffic_event.source_agent_id
        assert retrieved.interception_point == sample_traffic_event.interception_point
        assert retrieved.direction == sample_traffic_event.direction
        assert retrieved.event_type == sample_traffic_event.event_type
        assert retrieved.payload_hash == sample_traffic_event.payload_hash
        assert retrieved.latency_ms == sample_traffic_event.latency_ms
        assert retrieved.tool_name == sample_traffic_event.tool_name
        assert retrieved.session_id == sample_traffic_event.session_id
        assert retrieved.parent_event_id == sample_traffic_event.parent_event_id

    @pytest.mark.asyncio
    async def test_round_trip_admission_event(
        self,
        mock_storage: TrafficStorageAdapter,
        sample_admission_event: TrafficEvent,
    ) -> None:
        """Verify admission event with approval fields round-trips."""
        await mock_storage.store_event(sample_admission_event)
        retrieved = await mock_storage.get_event(sample_admission_event.event_id)
        assert retrieved is not None
        assert retrieved.approval_required is True
        assert retrieved.approval_decision == "allowed"
        assert retrieved.interception_point == InterceptionPoint.K8S_ADMISSION


# =========================================================================
# Singleton Tests
# =========================================================================


class TestStorageSingleton:
    """Tests for get_traffic_storage and reset_traffic_storage."""

    def test_get_traffic_storage_returns_singleton(self) -> None:
        """Repeated calls return the same instance."""
        a = get_traffic_storage()
        b = get_traffic_storage()
        assert a is b

    def test_reset_traffic_storage_clears_singleton(self) -> None:
        """After reset, a new instance is created."""
        a = get_traffic_storage()
        reset_traffic_storage()
        b = get_traffic_storage()
        assert a is not b

    def test_get_traffic_storage_type(self) -> None:
        """Verify the singleton is a TrafficStorageAdapter."""
        instance = get_traffic_storage()
        assert isinstance(instance, TrafficStorageAdapter)

    def test_default_storage_uses_mock(self) -> None:
        """Verify default singleton uses mock storage."""
        instance = get_traffic_storage()
        assert instance.use_mock is True


# =========================================================================
# Storage Properties Tests
# =========================================================================


class TestStorageProperties:
    """Tests for storage adapter properties."""

    def test_event_count_starts_at_zero(
        self, mock_storage: TrafficStorageAdapter
    ) -> None:
        """Verify event_count is 0 for new storage."""
        assert mock_storage.event_count == 0

    def test_write_count_starts_at_zero(
        self, mock_storage: TrafficStorageAdapter
    ) -> None:
        """Verify write_count is 0 for new storage."""
        assert mock_storage.write_count == 0

    def test_read_count_starts_at_zero(
        self, mock_storage: TrafficStorageAdapter
    ) -> None:
        """Verify read_count is 0 for new storage."""
        assert mock_storage.read_count == 0

    def test_constructor_defaults(self) -> None:
        """Verify constructor default values."""
        storage = TrafficStorageAdapter()
        assert storage.dynamodb_table_name == "aura-traffic-events"
        assert storage.s3_bucket_name == "aura-traffic-payloads"
        assert storage.use_mock is True
        assert storage.batch_size == 25

    def test_constructor_custom_values(self) -> None:
        """Verify constructor accepts custom configuration."""
        storage = TrafficStorageAdapter(
            dynamodb_table_name="custom-table",
            s3_bucket_name="custom-bucket",
            use_mock=False,
            batch_size=100,
        )
        assert storage.dynamodb_table_name == "custom-table"
        assert storage.s3_bucket_name == "custom-bucket"
        assert storage.use_mock is False
        assert storage.batch_size == 100
