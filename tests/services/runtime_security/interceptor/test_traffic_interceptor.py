"""
Tests for the AgentTrafficInterceptor.

Covers capture methods for all traffic types, buffer flushing, callback
registration, metrics tracking, singleton management, and disabled mode.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.runtime_security.interceptor.protocol import (
    InterceptionPoint,
    TrafficDirection,
    TrafficEvent,
    TrafficEventType,
    TrafficFilter,
)
from src.services.runtime_security.interceptor.storage import TrafficStorageAdapter
from src.services.runtime_security.interceptor.traffic_interceptor import (
    AgentTrafficInterceptor,
    get_traffic_interceptor,
    reset_traffic_interceptor,
)

# =========================================================================
# Capture Method Tests
# =========================================================================


class TestCaptureToolCall:
    """Tests for capture_tool_call."""

    @pytest.mark.asyncio
    async def test_capture_tool_call_basic(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify capture_tool_call returns a valid TrafficEvent."""
        event = await interceptor.capture_tool_call(
            source_agent_id="coder-agent-1",
            tool_name="semantic_search",
            payload="search query",
            latency_ms=12.5,
        )
        assert event.event_id.startswith("te-")
        assert event.source_agent_id == "coder-agent-1"
        assert event.tool_name == "semantic_search"
        assert event.interception_point == InterceptionPoint.CAPABILITY_GOVERNANCE
        assert event.direction == TrafficDirection.OUTBOUND
        assert event.event_type == TrafficEventType.AGENT_TO_TOOL
        assert event.latency_ms == 12.5
        assert event.payload_hash == TrafficEvent.hash_payload("search query")

    @pytest.mark.asyncio
    async def test_capture_tool_call_with_all_options(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify capture_tool_call with all optional parameters."""
        event = await interceptor.capture_tool_call(
            source_agent_id="coder-agent-1",
            tool_name="code_edit",
            payload="edit data",
            latency_ms=25.0,
            session_id="sess-100",
            parent_event_id="te-parent",
            approval_required=True,
            approval_decision="approved",
            error_message=None,
            metadata={"priority": "high"},
        )
        assert event.session_id == "sess-100"
        assert event.parent_event_id == "te-parent"
        assert event.approval_required is True
        assert event.approval_decision == "approved"
        assert event.error_message is None
        assert dict(event.metadata) == {"priority": "high"}

    @pytest.mark.asyncio
    async def test_capture_tool_call_with_error(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify capture_tool_call records error_message."""
        event = await interceptor.capture_tool_call(
            source_agent_id="agent-1",
            tool_name="failing_tool",
            payload="payload",
            latency_ms=500.0,
            error_message="Tool execution failed",
        )
        assert event.error_message == "Tool execution failed"


class TestCaptureLLMRequest:
    """Tests for capture_llm_request."""

    @pytest.mark.asyncio
    async def test_capture_llm_request_basic(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify capture_llm_request creates correct event."""
        event = await interceptor.capture_llm_request(
            source_agent_id="reviewer-agent-1",
            payload="Analyze this code for vulnerabilities",
            latency_ms=350.0,
            token_count=2500,
        )
        assert event.interception_point == InterceptionPoint.LLM_PROMPT_SANITIZER
        assert event.direction == TrafficDirection.OUTBOUND
        assert event.event_type == TrafficEventType.AGENT_TO_LLM
        assert event.token_count == 2500
        assert event.source_agent_id == "reviewer-agent-1"

    @pytest.mark.asyncio
    async def test_capture_llm_request_with_session(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify session_id and parent_event_id are captured."""
        event = await interceptor.capture_llm_request(
            source_agent_id="agent-1",
            payload="prompt text",
            latency_ms=100.0,
            session_id="sess-llm-1",
            parent_event_id="te-parent-llm",
        )
        assert event.session_id == "sess-llm-1"
        assert event.parent_event_id == "te-parent-llm"


class TestCaptureAgentMessage:
    """Tests for capture_agent_message."""

    @pytest.mark.asyncio
    async def test_capture_agent_message_basic(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify agent-to-agent message capture."""
        event = await interceptor.capture_agent_message(
            source_agent_id="orchestrator",
            target_agent_id="coder-agent-1",
            payload="task assignment payload",
            latency_ms=3.0,
        )
        assert event.source_agent_id == "orchestrator"
        assert event.target_agent_id == "coder-agent-1"
        assert event.interception_point == InterceptionPoint.FASTAPI_MIDDLEWARE
        assert event.direction == TrafficDirection.INTERNAL
        assert event.event_type == TrafficEventType.AGENT_TO_AGENT


class TestCaptureCheckpoint:
    """Tests for capture_checkpoint."""

    @pytest.mark.asyncio
    async def test_capture_checkpoint_basic(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify checkpoint capture with zero latency."""
        event = await interceptor.capture_checkpoint(
            source_agent_id="coder-agent-1",
            payload="checkpoint state data",
            session_id="sess-cp-1",
        )
        assert event.interception_point == InterceptionPoint.EXECUTION_CHECKPOINT
        assert event.direction == TrafficDirection.INTERNAL
        assert event.event_type == TrafficEventType.CHECKPOINT
        assert event.latency_ms == 0.0
        assert event.session_id == "sess-cp-1"

    @pytest.mark.asyncio
    async def test_capture_checkpoint_with_metadata(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify checkpoint capture with metadata."""
        event = await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="state",
            metadata={"phase": "validation", "step": "3"},
        )
        assert dict(event.metadata) == {"phase": "validation", "step": "3"}


class TestCaptureMCPCall:
    """Tests for capture_mcp_call."""

    @pytest.mark.asyncio
    async def test_capture_mcp_call_basic(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify MCP tool call capture."""
        event = await interceptor.capture_mcp_call(
            source_agent_id="coder-agent-1",
            tool_name="mcp_semantic_search",
            payload="mcp query data",
            latency_ms=20.0,
        )
        assert event.interception_point == InterceptionPoint.MCP_TOOL_SERVER
        assert event.direction == TrafficDirection.OUTBOUND
        assert event.event_type == TrafficEventType.AGENT_TO_TOOL
        assert event.tool_name == "mcp_semantic_search"

    @pytest.mark.asyncio
    async def test_capture_mcp_call_with_error(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify MCP call with error message."""
        event = await interceptor.capture_mcp_call(
            source_agent_id="agent-1",
            tool_name="mcp_tool",
            payload="data",
            latency_ms=1000.0,
            error_message="MCP timeout",
        )
        assert event.error_message == "MCP timeout"


class TestCaptureAdmissionEvent:
    """Tests for capture_admission_event."""

    @pytest.mark.asyncio
    async def test_capture_admission_event_basic(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify admission event capture."""
        event = await interceptor.capture_admission_event(
            source_agent_id="admission-ctrl",
            payload="pod spec data",
            latency_ms=8.0,
            approval_decision="allowed",
        )
        assert event.interception_point == InterceptionPoint.K8S_ADMISSION
        assert event.direction == TrafficDirection.INBOUND
        assert event.event_type == TrafficEventType.ADMISSION
        assert event.approval_required is True
        assert event.approval_decision == "allowed"


class TestCaptureConstitutionalEvent:
    """Tests for capture_constitutional_event."""

    @pytest.mark.asyncio
    async def test_capture_constitutional_event_basic(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify constitutional AI event capture."""
        event = await interceptor.capture_constitutional_event(
            source_agent_id="coder-agent-1",
            payload="response after constitutional review",
            latency_ms=45.0,
            session_id="sess-cai-1",
        )
        assert event.interception_point == InterceptionPoint.CONSTITUTIONAL_AI
        assert event.direction == TrafficDirection.INTERNAL
        assert event.event_type == TrafficEventType.AGENT_RESPONSE
        assert event.session_id == "sess-cai-1"


class TestCaptureRaw:
    """Tests for capture_raw."""

    @pytest.mark.asyncio
    async def test_capture_raw_basic(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify raw event capture with explicit parameters."""
        event = await interceptor.capture_raw(
            source_agent_id="escape-detector",
            interception_point=InterceptionPoint.CONTAINER_ESCAPE,
            direction=TrafficDirection.INTERNAL,
            event_type=TrafficEventType.ESCAPE_ALERT,
            payload="escape detection payload",
            latency_ms=1.0,
        )
        assert event.interception_point == InterceptionPoint.CONTAINER_ESCAPE
        assert event.direction == TrafficDirection.INTERNAL
        assert event.event_type == TrafficEventType.ESCAPE_ALERT
        assert event.source_agent_id == "escape-detector"

    @pytest.mark.asyncio
    async def test_capture_raw_with_kwargs(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify raw event capture forwards kwargs to TrafficEvent fields."""
        event = await interceptor.capture_raw(
            source_agent_id="agent-raw",
            interception_point=InterceptionPoint.FASTAPI_MIDDLEWARE,
            direction=TrafficDirection.OUTBOUND,
            event_type=TrafficEventType.TOOL_RESPONSE,
            payload="raw payload",
            latency_ms=7.0,
            target_agent_id="target-agent",
            tool_name="raw_tool",
            token_count=500,
            approval_required=True,
            approval_decision="denied",
            error_message="custom error",
            session_id="sess-raw",
            parent_event_id="te-parent-raw",
            metadata={"key": "value"},
        )
        assert event.target_agent_id == "target-agent"
        assert event.tool_name == "raw_tool"
        assert event.token_count == 500
        assert event.approval_required is True
        assert event.approval_decision == "denied"
        assert event.error_message == "custom error"
        assert event.session_id == "sess-raw"
        assert event.parent_event_id == "te-parent-raw"
        assert dict(event.metadata) == {"key": "value"}


# =========================================================================
# Buffer and Flush Tests
# =========================================================================


class TestBufferAndFlush:
    """Tests for event buffering and flushing mechanics."""

    @pytest.mark.asyncio
    async def test_events_buffered_before_flush(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Events are buffered and not immediately stored."""
        await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="data",
        )
        # Event is in buffer, not yet flushed to storage
        assert interceptor.buffer_size_current == 1
        assert mock_storage.event_count == 0

    @pytest.mark.asyncio
    async def test_buffer_auto_flush_on_size(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Buffer flushes automatically when buffer_size is reached."""
        # interceptor has buffer_size=5
        for i in range(5):
            await interceptor.capture_checkpoint(
                source_agent_id=f"agent-{i}",
                payload=f"data-{i}",
            )
        # After 5 events, buffer should have flushed
        assert interceptor.buffer_size_current == 0
        assert mock_storage.event_count == 5
        assert interceptor.flush_count == 1

    @pytest.mark.asyncio
    async def test_manual_flush(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Manual flush pushes buffered events to storage."""
        await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="data-1",
        )
        await interceptor.capture_checkpoint(
            source_agent_id="agent-2",
            payload="data-2",
        )
        assert interceptor.buffer_size_current == 2
        assert mock_storage.event_count == 0

        flushed = await interceptor.flush()
        assert flushed == 2
        assert interceptor.buffer_size_current == 0
        assert mock_storage.event_count == 2

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Flushing an empty buffer returns 0."""
        flushed = await interceptor.flush()
        assert flushed == 0

    @pytest.mark.asyncio
    async def test_flush_stores_payloads(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify that payloads are stored alongside event metadata."""
        event = await interceptor.capture_tool_call(
            source_agent_id="agent-1",
            tool_name="search",
            payload="my query payload",
            latency_ms=10.0,
        )
        await interceptor.flush()
        stored_payload = await mock_storage.get_payload(event.event_id)
        assert stored_payload == "my query payload"

    @pytest.mark.asyncio
    async def test_flush_error_increments_error_count(
        self,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify error_count increments when flush fails."""
        # Create interceptor with a storage that raises on store_batch
        failing_storage = TrafficStorageAdapter(use_mock=True)
        failing_storage._mock_store_batch = MagicMock(
            side_effect=RuntimeError("DB down")
        )
        interceptor = AgentTrafficInterceptor(
            storage=failing_storage,
            buffer_size=50,
            enabled=True,
        )
        await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="data",
        )
        result = await interceptor.flush()
        assert result == 0
        assert interceptor.error_count == 1

    @pytest.mark.asyncio
    async def test_multiple_flushes(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify flush_count increments across multiple flushes."""
        await interceptor.capture_checkpoint(source_agent_id="a", payload="d1")
        await interceptor.flush()
        await interceptor.capture_checkpoint(source_agent_id="b", payload="d2")
        await interceptor.flush()
        assert interceptor.flush_count == 2
        assert mock_storage.event_count == 2


# =========================================================================
# Disabled Interceptor Tests
# =========================================================================


class TestDisabledInterceptor:
    """Tests for interceptor behavior when disabled."""

    @pytest.mark.asyncio
    async def test_disabled_does_not_buffer(
        self,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """When disabled, events are not captured or buffered."""
        interceptor = AgentTrafficInterceptor(
            storage=mock_storage,
            enabled=False,
        )
        event = await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="ignored",
        )
        assert interceptor.buffer_size_current == 0
        assert interceptor.capture_count == 0


# =========================================================================
# Callback Tests
# =========================================================================


class TestCallbacks:
    """Tests for callback registration and invocation."""

    @pytest.mark.asyncio
    async def test_register_callback_invoked(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Registered callbacks are invoked for each captured event."""
        received_events: list[TrafficEvent] = []
        interceptor.register_callback(lambda e: received_events.append(e))

        await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="data",
        )
        assert len(received_events) == 1
        assert received_events[0].source_agent_id == "agent-1"

    @pytest.mark.asyncio
    async def test_multiple_callbacks(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Multiple registered callbacks are all invoked."""
        calls_a: list[str] = []
        calls_b: list[str] = []
        interceptor.register_callback(lambda e: calls_a.append(e.event_id))
        interceptor.register_callback(lambda e: calls_b.append(e.event_id))

        await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="data",
        )
        assert len(calls_a) == 1
        assert len(calls_b) == 1

    @pytest.mark.asyncio
    async def test_unregister_callback(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Unregistered callbacks are no longer invoked."""
        received: list[str] = []
        cb = lambda e: received.append(e.event_id)
        interceptor.register_callback(cb)
        await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="data1",
        )
        assert len(received) == 1

        interceptor.unregister_callback(cb)
        await interceptor.capture_checkpoint(
            source_agent_id="agent-2",
            payload="data2",
        )
        assert len(received) == 1  # No new invocation

    @pytest.mark.asyncio
    async def test_callback_error_does_not_block(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """A failing callback does not prevent event capture."""

        def failing_cb(event: TrafficEvent) -> None:
            raise ValueError("callback failure")

        interceptor.register_callback(failing_cb)
        # Should not raise
        event = await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="data",
        )
        assert event.source_agent_id == "agent-1"
        assert interceptor.capture_count == 1

    @pytest.mark.asyncio
    async def test_callbacks_passed_at_init(
        self,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Callbacks provided at construction time are invoked."""
        received: list[str] = []
        interceptor = AgentTrafficInterceptor(
            storage=mock_storage,
            callbacks=[lambda e: received.append(e.event_id)],
        )
        await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="data",
        )
        assert len(received) == 1


# =========================================================================
# Metrics Tests
# =========================================================================


class TestMetrics:
    """Tests for interceptor metrics properties."""

    @pytest.mark.asyncio
    async def test_capture_count(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify capture_count increments for each captured event."""
        assert interceptor.capture_count == 0
        await interceptor.capture_checkpoint(source_agent_id="a", payload="d")
        assert interceptor.capture_count == 1
        await interceptor.capture_checkpoint(source_agent_id="b", payload="d")
        assert interceptor.capture_count == 2

    @pytest.mark.asyncio
    async def test_events_by_type(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify events_by_type tracks counts per event type."""
        await interceptor.capture_tool_call(
            source_agent_id="a",
            tool_name="t",
            payload="d",
            latency_ms=1.0,
        )
        await interceptor.capture_llm_request(
            source_agent_id="a",
            payload="d",
            latency_ms=1.0,
        )
        await interceptor.capture_tool_call(
            source_agent_id="b",
            tool_name="t2",
            payload="d2",
            latency_ms=2.0,
        )
        by_type = interceptor.events_by_type
        assert by_type["agent_to_tool"] == 2
        assert by_type["agent_to_llm"] == 1

    @pytest.mark.asyncio
    async def test_events_by_interception_point(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify events_by_interception_point tracks counts."""
        await interceptor.capture_checkpoint(source_agent_id="a", payload="d")
        await interceptor.capture_checkpoint(source_agent_id="b", payload="d")
        await interceptor.capture_admission_event(
            source_agent_id="c",
            payload="d",
            latency_ms=1.0,
        )
        by_point = interceptor.events_by_interception_point
        assert by_point["execution_checkpoint"] == 2
        assert by_point["k8s_admission"] == 1

    @pytest.mark.asyncio
    async def test_buffer_size_current(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify buffer_size_current reflects buffer occupancy."""
        assert interceptor.buffer_size_current == 0
        await interceptor.capture_checkpoint(source_agent_id="a", payload="d")
        assert interceptor.buffer_size_current == 1
        await interceptor.flush()
        assert interceptor.buffer_size_current == 0


# =========================================================================
# Start / Stop Tests
# =========================================================================


class TestStartStop:
    """Tests for interceptor start and stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_flush_task(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Starting the interceptor creates a background flush task."""
        assert interceptor._flush_task is None
        await interceptor.start()
        assert interceptor._flush_task is not None
        assert interceptor._running is True
        await interceptor.stop()

    @pytest.mark.asyncio
    async def test_stop_flushes_buffer(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Stopping the interceptor flushes remaining buffered events."""
        await interceptor.capture_checkpoint(source_agent_id="a", payload="d")
        assert interceptor.buffer_size_current == 1
        await interceptor.stop()
        assert interceptor.buffer_size_current == 0
        assert mock_storage.event_count == 1

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Starting twice does not create a second flush task."""
        await interceptor.start()
        task1 = interceptor._flush_task
        await interceptor.start()
        task2 = interceptor._flush_task
        assert task1 is task2
        await interceptor.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Stopping without starting does not raise."""
        await interceptor.stop()  # Should not raise
        assert interceptor._running is False


# =========================================================================
# Query / Delegation Tests
# =========================================================================


class TestQueryDelegation:
    """Tests that query methods delegate correctly to storage."""

    @pytest.mark.asyncio
    async def test_query_returns_matching_events(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify query delegates to storage and returns results."""
        await interceptor.capture_tool_call(
            source_agent_id="agent-1",
            tool_name="search",
            payload="q",
            latency_ms=1.0,
        )
        await interceptor.capture_checkpoint(source_agent_id="agent-2", payload="cp")
        await interceptor.flush()

        results = await interceptor.query(
            TrafficFilter(source_agent_id="agent-1"),
        )
        assert len(results) == 1
        assert results[0].source_agent_id == "agent-1"

    @pytest.mark.asyncio
    async def test_get_event_by_id(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify get_event retrieves a specific event by ID."""
        event = await interceptor.capture_checkpoint(
            source_agent_id="agent-1",
            payload="state",
        )
        await interceptor.flush()
        retrieved = await interceptor.get_event(event.event_id)
        assert retrieved is not None
        assert retrieved.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_get_event_not_found(
        self,
        interceptor: AgentTrafficInterceptor,
    ) -> None:
        """Verify get_event returns None for nonexistent IDs."""
        result = await interceptor.get_event("te-nonexistent00001")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_summary_delegates(
        self,
        interceptor: AgentTrafficInterceptor,
        mock_storage: TrafficStorageAdapter,
    ) -> None:
        """Verify get_summary returns a TrafficSummary object."""
        await interceptor.capture_tool_call(
            source_agent_id="agent-1",
            tool_name="t",
            payload="p",
            latency_ms=10.0,
        )
        await interceptor.flush()
        summary = await interceptor.get_summary(TrafficFilter())
        assert summary.total_events == 1


# =========================================================================
# Singleton Tests
# =========================================================================


class TestSingleton:
    """Tests for get_traffic_interceptor and reset_traffic_interceptor."""

    def test_get_traffic_interceptor_returns_singleton(self) -> None:
        """Repeated calls return the same instance."""
        a = get_traffic_interceptor()
        b = get_traffic_interceptor()
        assert a is b

    def test_reset_traffic_interceptor_clears_singleton(self) -> None:
        """After reset, a new instance is created."""
        a = get_traffic_interceptor()
        reset_traffic_interceptor()
        b = get_traffic_interceptor()
        assert a is not b

    def test_get_traffic_interceptor_type(self) -> None:
        """Verify the singleton is an AgentTrafficInterceptor."""
        instance = get_traffic_interceptor()
        assert isinstance(instance, AgentTrafficInterceptor)
