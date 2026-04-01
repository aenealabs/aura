"""
Test fixtures for the runtime security interceptor module.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from src.services.runtime_security.interceptor import (
    TrafficStorageAdapter,
    get_traffic_storage,
    reset_traffic_storage,
)
from src.services.runtime_security.interceptor.protocol import (
    InterceptionPoint,
    TrafficBatch,
    TrafficDirection,
    TrafficEvent,
    TrafficEventType,
    TrafficFilter,
    TrafficSummary,
)
from src.services.runtime_security.interceptor.traffic_interceptor import (
    AgentTrafficInterceptor,
    get_traffic_interceptor,
    reset_traffic_interceptor,
)


@pytest.fixture(autouse=True)
def reset_interceptor_singletons():
    """Reset all interceptor singletons before and after each test."""
    reset_traffic_interceptor()
    reset_traffic_storage()
    yield
    reset_traffic_interceptor()
    reset_traffic_storage()


@pytest.fixture
def now_utc() -> datetime:
    """Current UTC timestamp for test consistency."""
    return datetime.now(timezone.utc)


@pytest.fixture
def sample_payload() -> str:
    """A sample payload string for testing."""
    return '{"query": "find all vulnerabilities", "limit": 10}'


@pytest.fixture
def sample_payload_hash(sample_payload: str) -> str:
    """Pre-computed SHA-256 hash of the sample payload."""
    return hashlib.sha256(sample_payload.encode("utf-8")).hexdigest()


@pytest.fixture
def sample_traffic_event(now_utc: datetime, sample_payload_hash: str) -> TrafficEvent:
    """Create a sample TrafficEvent for testing."""
    return TrafficEvent(
        event_id="te-abc123def4567890",
        timestamp=now_utc,
        source_agent_id="coder-agent-1",
        interception_point=InterceptionPoint.CAPABILITY_GOVERNANCE,
        direction=TrafficDirection.OUTBOUND,
        event_type=TrafficEventType.AGENT_TO_TOOL,
        payload_hash=sample_payload_hash,
        latency_ms=12.5,
        tool_name="semantic_search",
        session_id="sess-001",
        parent_event_id="te-parent000000001",
        metadata=(("env", "dev"), ("region", "us-east-1")),
    )


@pytest.fixture
def sample_traffic_event_with_error(now_utc: datetime) -> TrafficEvent:
    """Create a TrafficEvent that has an error."""
    return TrafficEvent(
        event_id="te-error12345678901",
        timestamp=now_utc,
        source_agent_id="reviewer-agent-1",
        interception_point=InterceptionPoint.LLM_PROMPT_SANITIZER,
        direction=TrafficDirection.OUTBOUND,
        event_type=TrafficEventType.AGENT_TO_LLM,
        payload_hash="deadbeef" * 8,
        latency_ms=250.0,
        error_message="Rate limit exceeded",
        token_count=1500,
    )


@pytest.fixture
def sample_agent_message_event(now_utc: datetime) -> TrafficEvent:
    """Create a TrafficEvent for agent-to-agent communication."""
    return TrafficEvent(
        event_id="te-agent123456789a",
        timestamp=now_utc,
        source_agent_id="orchestrator-agent",
        target_agent_id="coder-agent-1",
        interception_point=InterceptionPoint.FASTAPI_MIDDLEWARE,
        direction=TrafficDirection.INTERNAL,
        event_type=TrafficEventType.AGENT_TO_AGENT,
        payload_hash="a1b2c3d4" * 8,
        latency_ms=3.2,
        session_id="sess-002",
    )


@pytest.fixture
def sample_checkpoint_event(now_utc: datetime) -> TrafficEvent:
    """Create a checkpoint TrafficEvent."""
    return TrafficEvent(
        event_id="te-checkpoint00001",
        timestamp=now_utc,
        source_agent_id="coder-agent-1",
        interception_point=InterceptionPoint.EXECUTION_CHECKPOINT,
        direction=TrafficDirection.INTERNAL,
        event_type=TrafficEventType.CHECKPOINT,
        payload_hash="11223344" * 8,
        latency_ms=0.0,
        session_id="sess-001",
    )


@pytest.fixture
def sample_admission_event(now_utc: datetime) -> TrafficEvent:
    """Create an admission TrafficEvent."""
    return TrafficEvent(
        event_id="te-admission000001",
        timestamp=now_utc,
        source_agent_id="admission-controller",
        interception_point=InterceptionPoint.K8S_ADMISSION,
        direction=TrafficDirection.INBOUND,
        event_type=TrafficEventType.ADMISSION,
        payload_hash="55667788" * 8,
        latency_ms=8.1,
        approval_required=True,
        approval_decision="allowed",
    )


@pytest.fixture
def multiple_events(now_utc: datetime) -> list[TrafficEvent]:
    """Create a list of diverse traffic events for batch and summary testing."""
    base = now_utc
    events = [
        TrafficEvent(
            event_id="te-multi00000000001",
            timestamp=base - timedelta(minutes=5),
            source_agent_id="coder-agent-1",
            interception_point=InterceptionPoint.CAPABILITY_GOVERNANCE,
            direction=TrafficDirection.OUTBOUND,
            event_type=TrafficEventType.AGENT_TO_TOOL,
            payload_hash="aaa" + "0" * 61,
            latency_ms=10.0,
            tool_name="semantic_search",
            token_count=100,
            session_id="sess-batch-1",
        ),
        TrafficEvent(
            event_id="te-multi00000000002",
            timestamp=base - timedelta(minutes=4),
            source_agent_id="coder-agent-1",
            target_agent_id="reviewer-agent-1",
            interception_point=InterceptionPoint.FASTAPI_MIDDLEWARE,
            direction=TrafficDirection.INTERNAL,
            event_type=TrafficEventType.AGENT_TO_AGENT,
            payload_hash="bbb" + "0" * 61,
            latency_ms=5.0,
            session_id="sess-batch-1",
        ),
        TrafficEvent(
            event_id="te-multi00000000003",
            timestamp=base - timedelta(minutes=3),
            source_agent_id="reviewer-agent-1",
            interception_point=InterceptionPoint.LLM_PROMPT_SANITIZER,
            direction=TrafficDirection.OUTBOUND,
            event_type=TrafficEventType.AGENT_TO_LLM,
            payload_hash="ccc" + "0" * 61,
            latency_ms=200.0,
            token_count=2000,
            error_message="Token limit warning",
            session_id="sess-batch-1",
        ),
        TrafficEvent(
            event_id="te-multi00000000004",
            timestamp=base - timedelta(minutes=2),
            source_agent_id="validator-agent-1",
            interception_point=InterceptionPoint.EXECUTION_CHECKPOINT,
            direction=TrafficDirection.INTERNAL,
            event_type=TrafficEventType.CHECKPOINT,
            payload_hash="ddd" + "0" * 61,
            latency_ms=0.0,
            session_id="sess-batch-2",
        ),
        TrafficEvent(
            event_id="te-multi00000000005",
            timestamp=base - timedelta(minutes=1),
            source_agent_id="coder-agent-1",
            interception_point=InterceptionPoint.MCP_TOOL_SERVER,
            direction=TrafficDirection.OUTBOUND,
            event_type=TrafficEventType.AGENT_TO_TOOL,
            payload_hash="eee" + "0" * 61,
            latency_ms=15.0,
            tool_name="code_formatter",
            session_id="sess-batch-2",
        ),
    ]
    return events


@pytest.fixture
def mock_storage() -> TrafficStorageAdapter:
    """Create a fresh mock storage adapter for testing."""
    return TrafficStorageAdapter(use_mock=True)


@pytest.fixture
def interceptor(mock_storage: TrafficStorageAdapter) -> AgentTrafficInterceptor:
    """Create an interceptor wired to mock storage with small buffer for test triggers."""
    return AgentTrafficInterceptor(
        storage=mock_storage,
        buffer_size=5,
        flush_interval_seconds=60.0,
        enabled=True,
    )
