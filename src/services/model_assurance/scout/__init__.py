"""Scout Agent — Bedrock candidate discovery (ADR-088 Phase 1.4)."""

from __future__ import annotations

from .bedrock_client import (
    BedrockListClient,
    BedrockListResponse,
    BedrockModelSummary,
    infer_architecture,
    infer_tokenizer,
    synthesize_summary,
)
from .events import (
    EVENT_DETAIL_TYPE,
    EVENT_SOURCE,
    SCHEMA_VERSION,
    EligibilityFlag,
    ModelCandidateDetected,
    make_event,
)
from .scout_agent import (
    CandidateEventSink,
    EventBridgeSink,
    InMemoryEventSink,
    ScoutAgent,
    ScoutResult,
    synthesize_default_requirements,
)
from .scout_state import (
    InMemoryScoutStateStore,
    ScoutStateSnapshot,
    ScoutStateStore,
)

__all__ = [
    "BedrockListClient",
    "BedrockListResponse",
    "BedrockModelSummary",
    "synthesize_summary",
    "infer_tokenizer",
    "infer_architecture",
    "EVENT_SOURCE",
    "EVENT_DETAIL_TYPE",
    "SCHEMA_VERSION",
    "EligibilityFlag",
    "ModelCandidateDetected",
    "make_event",
    "ScoutStateStore",
    "ScoutStateSnapshot",
    "InMemoryScoutStateStore",
    "ScoutAgent",
    "ScoutResult",
    "CandidateEventSink",
    "InMemoryEventSink",
    "EventBridgeSink",
    "synthesize_default_requirements",
]
