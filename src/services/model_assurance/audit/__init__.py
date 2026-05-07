"""ADR-088 Phase 3.4 — CloudTrail audit events + NIST mapping."""

from __future__ import annotations

from .contracts import (
    EVENT_NIST_MAPPING,
    AuditEvent,
    AuditEventType,
    NISTControl,
)
from .event_emitter import (
    AuditEmitter,
    AuditEventSink,
    CloudTrailEventBridgeSink,
    InMemoryAuditSink,
    filter_events_by_control,
)

__all__ = [
    "EVENT_NIST_MAPPING",
    "AuditEvent",
    "AuditEventType",
    "NISTControl",
    "AuditEmitter",
    "AuditEventSink",
    "CloudTrailEventBridgeSink",
    "InMemoryAuditSink",
    "filter_events_by_control",
]
