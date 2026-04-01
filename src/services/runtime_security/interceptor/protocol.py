"""
Project Aura - Traffic Interception Protocol

Frozen dataclass definitions for agent traffic events, batches, and filters.
All data models are immutable to ensure audit trail integrity.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 AU-3: Content of audit records
- NIST 800-53 AU-8: Time stamps
- NIST 800-53 SI-4: Information system monitoring
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class InterceptionPoint(Enum):
    """Where in the pipeline traffic was captured."""

    FASTAPI_MIDDLEWARE = "fastapi_middleware"
    CAPABILITY_GOVERNANCE = "capability_governance"
    LLM_PROMPT_SANITIZER = "llm_prompt_sanitizer"
    MCP_TOOL_SERVER = "mcp_tool_server"
    EXECUTION_CHECKPOINT = "execution_checkpoint"
    K8S_ADMISSION = "k8s_admission"
    CONTAINER_ESCAPE = "container_escape"
    CONSTITUTIONAL_AI = "constitutional_ai"


class TrafficDirection(Enum):
    """Direction of the intercepted traffic."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class TrafficEventType(Enum):
    """Classification of the traffic event."""

    AGENT_TO_AGENT = "agent_to_agent"
    AGENT_TO_TOOL = "agent_to_tool"
    AGENT_TO_LLM = "agent_to_llm"
    TOOL_RESPONSE = "tool_response"
    LLM_RESPONSE = "llm_response"
    AGENT_RESPONSE = "agent_response"
    CHECKPOINT = "checkpoint"
    ADMISSION = "admission"
    ESCAPE_ALERT = "escape_alert"


@dataclass(frozen=True)
class TrafficEvent:
    """
    Immutable record of an intercepted agent traffic event.

    Every agent communication captured by the interceptor is represented
    as a TrafficEvent with full metadata for audit and analysis.
    """

    event_id: str
    timestamp: datetime
    source_agent_id: str
    interception_point: InterceptionPoint
    direction: TrafficDirection
    event_type: TrafficEventType
    payload_hash: str
    latency_ms: float
    target_agent_id: Optional[str] = None
    tool_name: Optional[str] = None
    token_count: Optional[int] = None
    approval_required: bool = False
    approval_decision: Optional[str] = None
    error_message: Optional[str] = None
    session_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    metadata: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "source_agent_id": self.source_agent_id,
            "target_agent_id": self.target_agent_id,
            "interception_point": self.interception_point.value,
            "direction": self.direction.value,
            "event_type": self.event_type.value,
            "payload_hash": self.payload_hash,
            "latency_ms": self.latency_ms,
            "tool_name": self.tool_name,
            "token_count": self.token_count,
            "approval_required": self.approval_required,
            "approval_decision": self.approval_decision,
            "error_message": self.error_message,
            "session_id": self.session_id,
            "parent_event_id": self.parent_event_id,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def generate_id() -> str:
        """Generate a unique event ID."""
        return f"te-{uuid.uuid4().hex[:16]}"

    @staticmethod
    def hash_payload(payload: str) -> str:
        """Compute SHA-256 hash of payload for deduplication."""
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TrafficBatch:
    """
    Immutable batch of traffic events for bulk storage operations.

    Events are grouped into batches for efficient DynamoDB batch writes.
    """

    batch_id: str
    events: tuple[TrafficEvent, ...]
    created_at: datetime
    source: str = "interceptor"

    @property
    def size(self) -> int:
        """Number of events in batch."""
        return len(self.events)

    @property
    def event_ids(self) -> tuple[str, ...]:
        """All event IDs in batch."""
        return tuple(e.event_id for e in self.events)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "batch_id": self.batch_id,
            "events": [e.to_dict() for e in self.events],
            "created_at": self.created_at.isoformat(),
            "source": self.source,
            "size": self.size,
        }

    @staticmethod
    def generate_id() -> str:
        """Generate a unique batch ID."""
        return f"tb-{uuid.uuid4().hex[:16]}"


@dataclass(frozen=True)
class TrafficFilter:
    """
    Immutable filter criteria for querying traffic events.

    Used by the storage adapter and analysis services to query
    specific subsets of traffic data.
    """

    source_agent_id: Optional[str] = None
    target_agent_id: Optional[str] = None
    interception_point: Optional[InterceptionPoint] = None
    event_type: Optional[TrafficEventType] = None
    direction: Optional[TrafficDirection] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    tool_name: Optional[str] = None
    session_id: Optional[str] = None
    has_error: Optional[bool] = None
    max_results: int = 1000

    def matches(self, event: TrafficEvent) -> bool:
        """Check if an event matches this filter."""
        if self.source_agent_id and event.source_agent_id != self.source_agent_id:
            return False
        if self.target_agent_id and event.target_agent_id != self.target_agent_id:
            return False
        if (
            self.interception_point
            and event.interception_point != self.interception_point
        ):
            return False
        if self.event_type and event.event_type != self.event_type:
            return False
        if self.direction and event.direction != self.direction:
            return False
        if self.start_time and event.timestamp < self.start_time:
            return False
        if self.end_time and event.timestamp > self.end_time:
            return False
        if self.tool_name and event.tool_name != self.tool_name:
            return False
        if self.session_id and event.session_id != self.session_id:
            return False
        if self.has_error is not None:
            has_err = event.error_message is not None
            if has_err != self.has_error:
                return False
        return True


@dataclass(frozen=True)
class TrafficSummary:
    """
    Immutable summary statistics for a set of traffic events.

    Computed from traffic data for dashboard and alerting purposes.
    """

    total_events: int
    unique_agents: int
    unique_tools: int
    events_by_type: tuple[tuple[str, int], ...]
    events_by_interception_point: tuple[tuple[str, int], ...]
    avg_latency_ms: float
    p95_latency_ms: float
    total_tokens: int
    error_count: int
    error_rate: float
    time_range_start: Optional[datetime] = None
    time_range_end: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_events": self.total_events,
            "unique_agents": self.unique_agents,
            "unique_tools": self.unique_tools,
            "events_by_type": dict(self.events_by_type),
            "events_by_interception_point": dict(self.events_by_interception_point),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "p95_latency_ms": round(self.p95_latency_ms, 3),
            "total_tokens": self.total_tokens,
            "error_count": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "time_range_start": (
                self.time_range_start.isoformat() if self.time_range_start else None
            ),
            "time_range_end": (
                self.time_range_end.isoformat() if self.time_range_end else None
            ),
        }
