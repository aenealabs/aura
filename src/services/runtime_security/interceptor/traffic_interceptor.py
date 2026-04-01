"""
Project Aura - Agent Traffic Interceptor

Async proxy that captures all agent-to-agent, agent-to-tool, and agent-to-LLM
traffic in real-time by hooking into 8 existing interception points.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 SI-4: Information system monitoring
- NIST 800-53 AU-2: Audit events
- NIST 800-53 AU-3: Content of audit records
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .protocol import (
    InterceptionPoint,
    TrafficBatch,
    TrafficDirection,
    TrafficEvent,
    TrafficEventType,
    TrafficFilter,
    TrafficSummary,
)
from .storage import TrafficStorageAdapter, get_traffic_storage

logger = logging.getLogger(__name__)

# Type alias for interception callbacks
InterceptionCallback = Callable[[TrafficEvent], None]


class AgentTrafficInterceptor:
    """
    Real-time agent traffic capture proxy.

    Hooks into existing pipeline interception points to capture all
    agent communications without blocking the request path. Events
    are buffered and flushed asynchronously to storage.

    Usage:
        interceptor = AgentTrafficInterceptor(storage=get_traffic_storage())

        # Capture a tool invocation
        event = await interceptor.capture_tool_call(
            source_agent_id="coder-agent-1",
            tool_name="semantic_search",
            payload="search query text",
            latency_ms=12.5,
        )

        # Query recent traffic
        events = await interceptor.query(TrafficFilter(
            source_agent_id="coder-agent-1",
            start_time=one_hour_ago,
        ))
    """

    def __init__(
        self,
        storage: Optional[TrafficStorageAdapter] = None,
        buffer_size: int = 50,
        flush_interval_seconds: float = 5.0,
        enabled: bool = True,
        callbacks: Optional[list[InterceptionCallback]] = None,
    ):
        self.storage = storage or get_traffic_storage()
        self.buffer_size = buffer_size
        self.flush_interval_seconds = flush_interval_seconds
        self.enabled = enabled
        self._callbacks = callbacks or []

        self._buffer: list[tuple[TrafficEvent, Optional[str]]] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self._capture_count: int = 0
        self._flush_count: int = 0
        self._error_count: int = 0
        self._events_by_type: dict[str, int] = defaultdict(int)
        self._events_by_point: dict[str, int] = defaultdict(int)

    async def start(self) -> None:
        """Start the background flush loop."""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "Traffic interceptor started (buffer=%d, interval=%.1fs)",
            self.buffer_size,
            self.flush_interval_seconds,
        )

    async def stop(self) -> None:
        """Stop the flush loop and flush remaining events."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        await self.flush()
        logger.info(
            "Traffic interceptor stopped (captured=%d, flushed=%d)",
            self._capture_count,
            self._flush_count,
        )

    # =========================================================================
    # Capture Methods (one per traffic type)
    # =========================================================================

    async def capture_tool_call(
        self,
        source_agent_id: str,
        tool_name: str,
        payload: str,
        latency_ms: float,
        session_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        approval_required: bool = False,
        approval_decision: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> TrafficEvent:
        """Capture an agent-to-tool invocation."""
        event = TrafficEvent(
            event_id=TrafficEvent.generate_id(),
            timestamp=datetime.now(timezone.utc),
            source_agent_id=source_agent_id,
            interception_point=InterceptionPoint.CAPABILITY_GOVERNANCE,
            direction=TrafficDirection.OUTBOUND,
            event_type=TrafficEventType.AGENT_TO_TOOL,
            payload_hash=TrafficEvent.hash_payload(payload),
            latency_ms=latency_ms,
            tool_name=tool_name,
            session_id=session_id,
            parent_event_id=parent_event_id,
            approval_required=approval_required,
            approval_decision=approval_decision,
            error_message=error_message,
            metadata=tuple((metadata or {}).items()),
        )
        await self._buffer_event(event, payload)
        return event

    async def capture_llm_request(
        self,
        source_agent_id: str,
        payload: str,
        latency_ms: float,
        token_count: Optional[int] = None,
        session_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> TrafficEvent:
        """Capture an agent-to-LLM request."""
        event = TrafficEvent(
            event_id=TrafficEvent.generate_id(),
            timestamp=datetime.now(timezone.utc),
            source_agent_id=source_agent_id,
            interception_point=InterceptionPoint.LLM_PROMPT_SANITIZER,
            direction=TrafficDirection.OUTBOUND,
            event_type=TrafficEventType.AGENT_TO_LLM,
            payload_hash=TrafficEvent.hash_payload(payload),
            latency_ms=latency_ms,
            token_count=token_count,
            session_id=session_id,
            parent_event_id=parent_event_id,
            error_message=error_message,
            metadata=tuple((metadata or {}).items()),
        )
        await self._buffer_event(event, payload)
        return event

    async def capture_agent_message(
        self,
        source_agent_id: str,
        target_agent_id: str,
        payload: str,
        latency_ms: float,
        session_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> TrafficEvent:
        """Capture an agent-to-agent communication."""
        event = TrafficEvent(
            event_id=TrafficEvent.generate_id(),
            timestamp=datetime.now(timezone.utc),
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            interception_point=InterceptionPoint.FASTAPI_MIDDLEWARE,
            direction=TrafficDirection.INTERNAL,
            event_type=TrafficEventType.AGENT_TO_AGENT,
            payload_hash=TrafficEvent.hash_payload(payload),
            latency_ms=latency_ms,
            session_id=session_id,
            parent_event_id=parent_event_id,
            error_message=error_message,
            metadata=tuple((metadata or {}).items()),
        )
        await self._buffer_event(event, payload)
        return event

    async def capture_checkpoint(
        self,
        source_agent_id: str,
        payload: str,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> TrafficEvent:
        """Capture an execution checkpoint."""
        event = TrafficEvent(
            event_id=TrafficEvent.generate_id(),
            timestamp=datetime.now(timezone.utc),
            source_agent_id=source_agent_id,
            interception_point=InterceptionPoint.EXECUTION_CHECKPOINT,
            direction=TrafficDirection.INTERNAL,
            event_type=TrafficEventType.CHECKPOINT,
            payload_hash=TrafficEvent.hash_payload(payload),
            latency_ms=0.0,
            session_id=session_id,
            metadata=tuple((metadata or {}).items()),
        )
        await self._buffer_event(event, payload)
        return event

    async def capture_mcp_call(
        self,
        source_agent_id: str,
        tool_name: str,
        payload: str,
        latency_ms: float,
        session_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> TrafficEvent:
        """Capture an MCP tool server call."""
        event = TrafficEvent(
            event_id=TrafficEvent.generate_id(),
            timestamp=datetime.now(timezone.utc),
            source_agent_id=source_agent_id,
            interception_point=InterceptionPoint.MCP_TOOL_SERVER,
            direction=TrafficDirection.OUTBOUND,
            event_type=TrafficEventType.AGENT_TO_TOOL,
            payload_hash=TrafficEvent.hash_payload(payload),
            latency_ms=latency_ms,
            tool_name=tool_name,
            session_id=session_id,
            error_message=error_message,
            metadata=tuple((metadata or {}).items()),
        )
        await self._buffer_event(event, payload)
        return event

    async def capture_admission_event(
        self,
        source_agent_id: str,
        payload: str,
        latency_ms: float,
        approval_decision: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> TrafficEvent:
        """Capture a K8s admission event."""
        event = TrafficEvent(
            event_id=TrafficEvent.generate_id(),
            timestamp=datetime.now(timezone.utc),
            source_agent_id=source_agent_id,
            interception_point=InterceptionPoint.K8S_ADMISSION,
            direction=TrafficDirection.INBOUND,
            event_type=TrafficEventType.ADMISSION,
            payload_hash=TrafficEvent.hash_payload(payload),
            latency_ms=latency_ms,
            approval_required=True,
            approval_decision=approval_decision,
            metadata=tuple((metadata or {}).items()),
        )
        await self._buffer_event(event, payload)
        return event

    async def capture_constitutional_event(
        self,
        source_agent_id: str,
        payload: str,
        latency_ms: float,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> TrafficEvent:
        """Capture a Constitutional AI post-generation event."""
        event = TrafficEvent(
            event_id=TrafficEvent.generate_id(),
            timestamp=datetime.now(timezone.utc),
            source_agent_id=source_agent_id,
            interception_point=InterceptionPoint.CONSTITUTIONAL_AI,
            direction=TrafficDirection.INTERNAL,
            event_type=TrafficEventType.AGENT_RESPONSE,
            payload_hash=TrafficEvent.hash_payload(payload),
            latency_ms=latency_ms,
            session_id=session_id,
            metadata=tuple((metadata or {}).items()),
        )
        await self._buffer_event(event, payload)
        return event

    async def capture_raw(
        self,
        source_agent_id: str,
        interception_point: InterceptionPoint,
        direction: TrafficDirection,
        event_type: TrafficEventType,
        payload: str,
        latency_ms: float,
        **kwargs: Any,
    ) -> TrafficEvent:
        """Capture a raw traffic event with explicit parameters."""
        event = TrafficEvent(
            event_id=TrafficEvent.generate_id(),
            timestamp=datetime.now(timezone.utc),
            source_agent_id=source_agent_id,
            interception_point=interception_point,
            direction=direction,
            event_type=event_type,
            payload_hash=TrafficEvent.hash_payload(payload),
            latency_ms=latency_ms,
            target_agent_id=kwargs.get("target_agent_id"),
            tool_name=kwargs.get("tool_name"),
            token_count=kwargs.get("token_count"),
            approval_required=kwargs.get("approval_required", False),
            approval_decision=kwargs.get("approval_decision"),
            error_message=kwargs.get("error_message"),
            session_id=kwargs.get("session_id"),
            parent_event_id=kwargs.get("parent_event_id"),
            metadata=tuple((kwargs.get("metadata") or {}).items()),
        )
        await self._buffer_event(event, payload)
        return event

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def query(self, filter_criteria: TrafficFilter) -> list[TrafficEvent]:
        """Query stored traffic events."""
        return await self.storage.query_events(filter_criteria)

    async def get_event(self, event_id: str) -> Optional[TrafficEvent]:
        """Get a single event by ID."""
        return await self.storage.get_event(event_id)

    async def get_summary(self, filter_criteria: TrafficFilter) -> TrafficSummary:
        """Get summary statistics for matching events."""
        return await self.storage.compute_summary(filter_criteria)

    # =========================================================================
    # Callback Management
    # =========================================================================

    def register_callback(self, callback: InterceptionCallback) -> None:
        """Register a callback to be invoked for every captured event."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: InterceptionCallback) -> None:
        """Remove a previously registered callback."""
        self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    # =========================================================================
    # Metrics
    # =========================================================================

    @property
    def capture_count(self) -> int:
        """Total events captured."""
        return self._capture_count

    @property
    def flush_count(self) -> int:
        """Total flush operations."""
        return self._flush_count

    @property
    def error_count(self) -> int:
        """Total capture/flush errors."""
        return self._error_count

    @property
    def buffer_size_current(self) -> int:
        """Current buffer occupancy."""
        return len(self._buffer)

    @property
    def events_by_type(self) -> dict[str, int]:
        """Event count breakdown by type."""
        return dict(self._events_by_type)

    @property
    def events_by_interception_point(self) -> dict[str, int]:
        """Event count breakdown by interception point."""
        return dict(self._events_by_point)

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _buffer_event(
        self, event: TrafficEvent, payload: Optional[str] = None
    ) -> None:
        """Add event to buffer and flush if buffer is full."""
        if not self.enabled:
            return

        self._capture_count += 1
        self._events_by_type[event.event_type.value] += 1
        self._events_by_point[event.interception_point.value] += 1

        # Invoke callbacks (non-blocking)
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                logger.debug("Callback error for event %s", event.event_id)

        async with self._buffer_lock:
            self._buffer.append((event, payload))
            if len(self._buffer) >= self.buffer_size:
                await self._flush_buffer()

    async def flush(self) -> int:
        """Force flush all buffered events to storage."""
        async with self._buffer_lock:
            return await self._flush_buffer()

    async def _flush_buffer(self) -> int:
        """Flush buffer to storage. Must be called with lock held."""
        if not self._buffer:
            return 0

        events = []
        payloads = {}
        for event, payload in self._buffer:
            events.append(event)
            if payload:
                payloads[event.event_id] = payload

        batch = TrafficBatch(
            batch_id=TrafficBatch.generate_id(),
            events=tuple(events),
            created_at=datetime.now(timezone.utc),
        )

        try:
            stored = await self.storage.store_batch(
                batch, payloads if payloads else None
            )
            self._flush_count += 1
            self._buffer.clear()
            return stored
        except Exception:
            self._error_count += 1
            logger.exception("Failed to flush traffic buffer (%d events)", len(events))
            return 0

    async def _flush_loop(self) -> None:
        """Background loop that flushes buffer periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval_seconds)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception:
                self._error_count += 1
                logger.exception("Error in flush loop")


# Singleton instance
_interceptor_instance: Optional[AgentTrafficInterceptor] = None


def get_traffic_interceptor() -> AgentTrafficInterceptor:
    """Get singleton traffic interceptor instance."""
    global _interceptor_instance
    if _interceptor_instance is None:
        _interceptor_instance = AgentTrafficInterceptor()
    return _interceptor_instance


def reset_traffic_interceptor() -> None:
    """Reset traffic interceptor singleton (for testing)."""
    global _interceptor_instance
    _interceptor_instance = None
