"""
Project Aura - Trace Explorer API Endpoints

REST API endpoints for OpenTelemetry trace visualization and analysis.
Provides trace data for the Trace Explorer dashboard (Issue #30).

Endpoints:
- GET  /api/v1/traces              - List traces with filtering
- GET  /api/v1/traces/metrics      - Get trace metrics summary
- GET  /api/v1/traces/{trace_id}   - Get full trace with spans
"""

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from src.api.log_sanitizer import sanitize_log

logger = logging.getLogger(__name__)

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/api/v1/traces", tags=["Traces"])

# ============================================================================
# Enums for API
# ============================================================================


class SpanKindEnum(str, Enum):
    """Span kind types."""

    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    INTERNAL = "internal"


class TraceStatusEnum(str, Enum):
    """Trace status types."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class AgentTypeEnum(str, Enum):
    """Agent types for filtering."""

    CODER = "coder"
    REVIEWER = "reviewer"
    VALIDATOR = "validator"
    ORCHESTRATOR = "orchestrator"
    SECURITY = "security"


# ============================================================================
# Pydantic Models
# ============================================================================


class SpanEvent(BaseModel):
    """Event within a span."""

    name: str = Field(description="Event name")
    timestamp: str = Field(description="ISO timestamp")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Event attributes"
    )


class SpanLink(BaseModel):
    """Link to another span."""

    trace_id: str = Field(description="Linked trace ID")
    span_id: str = Field(description="Linked span ID")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Link attributes"
    )


class SpanModel(BaseModel):
    """Individual span within a trace."""

    span_id: str = Field(description="Unique span identifier")
    parent_span_id: str | None = Field(default=None, description="Parent span ID")
    name: str = Field(description="Span name/operation")
    kind: SpanKindEnum = Field(description="Span kind (agent, llm, tool)")
    status: TraceStatusEnum = Field(description="Span status")
    start_time: str = Field(description="Start timestamp ISO")
    end_time: str = Field(description="End timestamp ISO")
    duration_ms: float = Field(description="Duration in milliseconds")
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Span attributes"
    )
    events: list[SpanEvent] = Field(default_factory=list, description="Span events")
    links: list[SpanLink] = Field(
        default_factory=list, description="Links to other spans"
    )


class TraceModel(BaseModel):
    """Full trace with all spans."""

    trace_id: str = Field(description="Unique trace identifier")
    name: str = Field(description="Root operation name")
    agent_type: AgentTypeEnum = Field(description="Agent type")
    status: TraceStatusEnum = Field(description="Overall trace status")
    start_time: str = Field(description="Trace start timestamp")
    end_time: str = Field(description="Trace end timestamp")
    duration_ms: float = Field(description="Total duration in milliseconds")
    span_count: int = Field(description="Number of spans")
    error_count: int = Field(description="Number of error spans")
    spans: list[SpanModel] = Field(default_factory=list, description="All spans")


class TraceListItem(BaseModel):
    """Trace summary for list view."""

    trace_id: str = Field(description="Unique trace identifier")
    name: str = Field(description="Root operation name")
    agent_type: AgentTypeEnum = Field(description="Agent type")
    status: TraceStatusEnum = Field(description="Overall trace status")
    start_time: str = Field(description="Trace start timestamp")
    duration_ms: float = Field(description="Total duration in milliseconds")
    span_count: int = Field(description="Number of spans")
    error_count: int = Field(description="Number of error spans")


class TraceListResponse(BaseModel):
    """Response for trace list endpoint."""

    traces: list[TraceListItem] = Field(description="List of traces")
    total: int = Field(description="Total matching traces")
    page: int = Field(description="Current page")
    page_size: int = Field(description="Items per page")
    has_more: bool = Field(description="More pages available")


class LatencyBucket(BaseModel):
    """Latency histogram bucket."""

    bucket: str = Field(description="Bucket label (e.g., '0-100ms')")
    count: int = Field(description="Number of traces in this bucket")


class TraceMetricsResponse(BaseModel):
    """Trace metrics summary."""

    total_traces: int = Field(description="Total trace count")
    avg_latency_ms: float = Field(description="Average latency in ms")
    error_rate: float = Field(description="Error rate (0-100)")
    coverage: float = Field(description="Instrumentation coverage (0-100)")
    traces_by_status: dict[str, int] = Field(description="Count by status")
    traces_by_agent: dict[str, int] = Field(description="Count by agent type")
    latency_histogram: list[LatencyBucket] = Field(description="Latency distribution")
    period: str = Field(description="Time period for metrics")


# ============================================================================
# Sample Data Generation (Development/Demo)
# ============================================================================

# Span kind colors (for reference, used by frontend)
SPAN_COLORS = {
    SpanKindEnum.AGENT: "#3B82F6",  # Blue
    SpanKindEnum.LLM: "#8B5CF6",  # Violet
    SpanKindEnum.TOOL: "#F59E0B",  # Amber
    SpanKindEnum.INTERNAL: "#6B7280",  # Gray
}

# Sample operation names by type
AGENT_OPERATIONS = [
    "patch_generation",
    "code_review",
    "vulnerability_scan",
    "architecture_analysis",
    "compliance_check",
    "threat_detection",
    "security_assessment",
    "query_intent_analysis",
]

LLM_OPERATIONS = [
    "code_completion",
    "vulnerability_analysis",
    "patch_synthesis",
    "review_generation",
    "explanation_generation",
]

TOOL_OPERATIONS = [
    "neptune_query",
    "opensearch_search",
    "github_api_call",
    "file_read",
    "sandbox_execute",
    "metrics_publish",
]


def _generate_span_id() -> str:
    """Generate a 16-character span ID."""
    return uuid.uuid4().hex[:16]


def _generate_trace_id() -> str:
    """Generate a 32-character trace ID."""
    return uuid.uuid4().hex


def _generate_spans(
    trace_id: str,
    start_time: datetime,
    depth: int = 0,
    parent_span_id: str | None = None,
) -> tuple[list[SpanModel], float, int]:
    """
    Generate a hierarchy of spans for a trace.

    Returns (spans, total_duration_ms, error_count)
    """
    spans: list[SpanModel] = []
    total_duration = 0.0
    error_count = 0

    # Root span (agent operation)
    if depth == 0:
        span_id = _generate_span_id()
        operation = random.choice(AGENT_OPERATIONS)
        duration = random.uniform(500, 5000)

        span_start = start_time
        span_end = span_start + timedelta(milliseconds=duration)

        # Generate child spans
        child_spans, child_duration, child_errors = _generate_child_spans(
            trace_id, span_id, span_start, duration
        )
        error_count += child_errors

        status = (
            TraceStatusEnum.ERROR if random.random() < 0.08 else TraceStatusEnum.SUCCESS
        )
        if status == TraceStatusEnum.ERROR:
            error_count += 1

        root_span = SpanModel(
            span_id=span_id,
            parent_span_id=None,
            name=operation,
            kind=SpanKindEnum.AGENT,
            status=status,
            start_time=span_start.isoformat(),
            end_time=span_end.isoformat(),
            duration_ms=round(duration, 2),
            attributes={
                "agent.name": random.choice(
                    ["CoderAgent", "ReviewerAgent", "ValidatorAgent", "SecurityAgent"]
                ),
                "operation.type": operation,
                "model.tier": random.choice(["fast", "accurate", "maximum"]),
            },
            events=[
                SpanEvent(
                    name="operation.started",
                    timestamp=span_start.isoformat(),
                    attributes={"trigger": "user_request"},
                )
            ],
        )

        spans.append(root_span)
        spans.extend(child_spans)
        total_duration = duration

    return spans, total_duration, error_count


def _generate_child_spans(
    trace_id: str,
    parent_span_id: str,
    parent_start: datetime,
    parent_duration: float,
) -> tuple[list[SpanModel], float, int]:
    """Generate child spans (LLM and tool calls)."""
    spans: list[SpanModel] = []
    error_count = 0
    current_offset = 20.0  # Start 20ms after parent

    # Generate 1-3 LLM calls
    llm_count = random.randint(1, 3)
    for _ in range(llm_count):
        if current_offset >= parent_duration - 50:
            break

        span_id = _generate_span_id()
        duration = random.uniform(100, 1500)
        operation = random.choice(LLM_OPERATIONS)

        span_start = parent_start + timedelta(milliseconds=current_offset)
        span_end = span_start + timedelta(milliseconds=duration)

        status = (
            TraceStatusEnum.ERROR if random.random() < 0.03 else TraceStatusEnum.SUCCESS
        )
        if status == TraceStatusEnum.ERROR:
            error_count += 1

        input_tokens = random.randint(500, 3000)
        output_tokens = random.randint(100, 1500)

        spans.append(
            SpanModel(
                span_id=span_id,
                parent_span_id=parent_span_id,
                name=operation,
                kind=SpanKindEnum.LLM,
                status=status,
                start_time=span_start.isoformat(),
                end_time=span_end.isoformat(),
                duration_ms=round(duration, 2),
                attributes={
                    "llm.model": random.choice(
                        ["claude-3-haiku", "claude-3-sonnet", "claude-3-opus"]
                    ),
                    "llm.input_tokens": str(input_tokens),
                    "llm.output_tokens": str(output_tokens),
                    "llm.cost_usd": f"{(input_tokens * 0.00001 + output_tokens * 0.00003):.6f}",
                },
                events=[],
            )
        )

        # Generate tool calls as children of LLM span
        if random.random() < 0.7:
            tool_spans, _, tool_errors = _generate_tool_spans(
                trace_id, span_id, span_start, duration
            )
            spans.extend(tool_spans)
            error_count += tool_errors

        current_offset += duration + random.uniform(10, 50)

    return spans, current_offset, error_count


def _generate_tool_spans(
    trace_id: str,
    parent_span_id: str,
    parent_start: datetime,
    parent_duration: float,
) -> tuple[list[SpanModel], float, int]:
    """Generate tool call spans."""
    spans: list[SpanModel] = []
    error_count = 0
    current_offset = 10.0

    tool_count = random.randint(1, 2)
    for _ in range(tool_count):
        if current_offset >= parent_duration - 20:
            break

        span_id = _generate_span_id()
        duration = random.uniform(20, 200)
        operation = random.choice(TOOL_OPERATIONS)

        span_start = parent_start + timedelta(milliseconds=current_offset)
        span_end = span_start + timedelta(milliseconds=duration)

        status = (
            TraceStatusEnum.ERROR if random.random() < 0.05 else TraceStatusEnum.SUCCESS
        )
        if status == TraceStatusEnum.ERROR:
            error_count += 1

        spans.append(
            SpanModel(
                span_id=span_id,
                parent_span_id=parent_span_id,
                name=operation,
                kind=SpanKindEnum.TOOL,
                status=status,
                start_time=span_start.isoformat(),
                end_time=span_end.isoformat(),
                duration_ms=round(duration, 2),
                attributes={
                    "tool.name": operation,
                    "tool.success": str(status == TraceStatusEnum.SUCCESS).lower(),
                },
                events=[],
            )
        )

        current_offset += duration + random.uniform(5, 20)

    return spans, current_offset, error_count


def _generate_sample_trace(base_time: datetime | None = None) -> TraceModel:
    """Generate a complete sample trace."""
    trace_id = _generate_trace_id()
    start_time = base_time or (
        datetime.now(timezone.utc) - timedelta(hours=random.uniform(0, 24))
    )

    spans, duration, error_count = _generate_spans(trace_id, start_time)

    agent_type = random.choice(list(AgentTypeEnum))
    overall_status = (
        TraceStatusEnum.ERROR if error_count > 0 else TraceStatusEnum.SUCCESS
    )

    # Update root span name
    root_op = spans[0].name if spans else "unknown_operation"

    return TraceModel(
        trace_id=trace_id,
        name=root_op,
        agent_type=agent_type,
        status=overall_status,
        start_time=start_time.isoformat(),
        end_time=(start_time + timedelta(milliseconds=duration)).isoformat(),
        duration_ms=round(duration, 2),
        span_count=len(spans),
        error_count=error_count,
        spans=spans,
    )


def _generate_sample_traces(count: int = 50) -> list[TraceModel]:
    """Generate multiple sample traces."""
    traces: list[TraceModel] = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        base_time = now - timedelta(hours=i * 0.5)
        traces.append(_generate_sample_trace(base_time))

    return sorted(traces, key=lambda t: t.start_time, reverse=True)


# Cache of sample traces for consistent responses
_trace_cache: list[TraceModel] = []


def _get_traces() -> list[TraceModel]:
    """Get cached traces or generate new ones."""
    global _trace_cache
    if not _trace_cache:
        _trace_cache = _generate_sample_traces(100)
    return _trace_cache


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/metrics", response_model=TraceMetricsResponse)
async def get_trace_metrics(
    period: str = Query(  # noqa: B008
        default="24h", description="Time period: 1h, 6h, 24h, 7d, 30d"
    ),  # noqa: B008
) -> TraceMetricsResponse:
    """
    Get trace metrics summary.

    Returns aggregate statistics for traces including total count,
    average latency, error rate, and distribution data.
    """
    try:
        traces = _get_traces()

        # Filter by period (simplified for demo)
        period_hours = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}.get(
            period, 24
        )
        cutoff = datetime.now(timezone.utc) - timedelta(hours=period_hours)
        filtered = [
            t
            for t in traces
            if datetime.fromisoformat(t.start_time.replace("Z", "+00:00")) > cutoff
        ]

        if not filtered:
            filtered = traces[:20]  # Fallback to recent traces

        total = len(filtered)
        avg_latency = sum(t.duration_ms for t in filtered) / total if total else 0
        error_count = sum(1 for t in filtered if t.status == TraceStatusEnum.ERROR)
        error_rate = (error_count / total * 100) if total else 0

        # Count by status
        status_counts = {
            "success": sum(1 for t in filtered if t.status == TraceStatusEnum.SUCCESS),
            "error": sum(1 for t in filtered if t.status == TraceStatusEnum.ERROR),
            "timeout": sum(1 for t in filtered if t.status == TraceStatusEnum.TIMEOUT),
        }

        # Count by agent type
        agent_counts = {}
        for agent in AgentTypeEnum:
            agent_counts[agent.value] = sum(
                1 for t in filtered if t.agent_type == agent
            )

        # Latency histogram buckets
        buckets = [
            {"bucket": "0-100ms", "min": 0, "max": 100, "count": 0},
            {"bucket": "100-500ms", "min": 100, "max": 500, "count": 0},
            {"bucket": "500ms-1s", "min": 500, "max": 1000, "count": 0},
            {"bucket": "1-2s", "min": 1000, "max": 2000, "count": 0},
            {"bucket": "2-5s", "min": 2000, "max": 5000, "count": 0},
            {"bucket": ">5s", "min": 5000, "max": 999999, "count": 0},
        ]

        for t in filtered:
            for bucket in buckets:
                if bucket["min"] <= t.duration_ms < bucket["max"]:
                    bucket["count"] += 1
                    break

        return TraceMetricsResponse(
            total_traces=total,
            avg_latency_ms=round(avg_latency, 2),
            error_rate=round(error_rate, 2),
            coverage=92.5,  # Simulated instrumentation coverage
            traces_by_status=status_counts,
            traces_by_agent=agent_counts,
            latency_histogram=[
                LatencyBucket(bucket=b["bucket"], count=b["count"]) for b in buckets
            ],
            period=period,
        )

    except Exception as e:
        logger.error("Failed to get trace metrics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get trace metrics")


@router.get("", response_model=TraceListResponse)
async def list_traces(
    page: int = Query(default=1, ge=1, description="Page number"),  # noqa: B008
    page_size: int = Query(  # noqa: B008
        default=20, ge=1, le=100, description="Items per page"
    ),  # noqa: B008
    status: TraceStatusEnum | None = Query(  # noqa: B008
        default=None, description="Filter by status"
    ),  # noqa: B008
    agent_type: AgentTypeEnum | None = Query(  # noqa: B008
        default=None, description="Filter by agent type"
    ),  # noqa: B008
    min_duration_ms: float | None = Query(  # noqa: B008
        default=None, ge=0, description="Minimum duration filter"
    ),  # noqa: B008
    max_duration_ms: float | None = Query(  # noqa: B008
        default=None, ge=0, description="Maximum duration filter"
    ),  # noqa: B008
    period: str = Query(  # noqa: B008
        default="24h", description="Time period: 1h, 6h, 24h, 7d, 30d"
    ),  # noqa: B008
    search: str | None = Query(  # noqa: B008
        default=None, description="Search trace names"
    ),  # noqa: B008
) -> TraceListResponse:
    """
    List traces with filtering and pagination.

    Returns trace summaries for the Trace Explorer list view.
    """
    try:
        traces = _get_traces()

        # Apply filters
        filtered = traces

        # Period filter
        period_hours = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}.get(
            period, 24
        )
        cutoff = datetime.now(timezone.utc) - timedelta(hours=period_hours)
        filtered = [
            t
            for t in filtered
            if datetime.fromisoformat(t.start_time.replace("Z", "+00:00")) > cutoff
        ]

        # Status filter
        if status:
            filtered = [t for t in filtered if t.status == status]

        # Agent type filter
        if agent_type:
            filtered = [t for t in filtered if t.agent_type == agent_type]

        # Duration filters
        if min_duration_ms is not None:
            filtered = [t for t in filtered if t.duration_ms >= min_duration_ms]
        if max_duration_ms is not None:
            filtered = [t for t in filtered if t.duration_ms <= max_duration_ms]

        # Search filter
        if search:
            search_lower = search.lower()
            filtered = [
                t
                for t in filtered
                if search_lower in t.name.lower() or search_lower in t.trace_id.lower()
            ]

        # Pagination
        total = len(filtered)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_traces = filtered[start_idx:end_idx]

        # Convert to list items (without full spans)
        items = [
            TraceListItem(
                trace_id=t.trace_id,
                name=t.name,
                agent_type=t.agent_type,
                status=t.status,
                start_time=t.start_time,
                duration_ms=t.duration_ms,
                span_count=t.span_count,
                error_count=t.error_count,
            )
            for t in page_traces
        ]

        return TraceListResponse(
            traces=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end_idx < total,
        )

    except Exception as e:
        logger.error("Failed to list traces: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list traces")


@router.get("/{trace_id}", response_model=TraceModel)
async def get_trace(trace_id: str) -> TraceModel:
    """
    Get full trace with all spans.

    Returns the complete trace data including the span hierarchy
    for visualization in the timeline/Gantt view.
    """
    try:
        traces = _get_traces()

        # Find the trace
        for trace in traces:
            if trace.trace_id == trace_id:
                return trace

        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get trace %s: %s", sanitize_log(trace_id), e, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to get trace")
