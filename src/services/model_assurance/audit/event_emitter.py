"""Audit event emitter (ADR-088 Phase 3.4).

The emitter assembles AuditEvent records from per-stage data and
fans them out to one or more sinks. Production wiring writes to
EventBridge → CloudTrail Lake; tests inject an in-memory recorder.

The emitter never raises; sink failures are logged and isolated so
one failing sink doesn't drop events for the others. This matches
the ADR-088 audit invariant: "every stage produces an event,
every event is recorded somewhere, no silent drops".
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Protocol

from src.services.model_assurance.audit.contracts import (
    AuditEvent,
    AuditEventType,
    NISTControl,
)

logger = logging.getLogger(__name__)


class AuditEventSink(Protocol):
    def emit(self, event: AuditEvent) -> None: ...


class InMemoryAuditSink:
    """Thread-friendly in-memory recorder for tests."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def by_type(self, event_type: AuditEventType) -> tuple[AuditEvent, ...]:
        return tuple(e for e in self._events if e.event_type is event_type)

    def by_correlation(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        return tuple(e for e in self._events if e.correlation_id == correlation_id)


class CloudTrailEventBridgeSink:
    """Production sink that forwards to CloudTrail Lake via EventBridge.

    Soft-imports boto3; falls back to no-op when unavailable so
    unit tests don't require AWS credentials. Errors are logged
    but never raised — the audit pipeline must be tolerant.
    """

    def __init__(
        self,
        *,
        region: str = "us-east-1",
        bus_name: str = "default",
        client=None,  # type: ignore[no-untyped-def]
    ) -> None:
        self._region = region
        self._bus_name = bus_name
        if client is not None:
            self._client = client
            self._is_live = True
        else:
            try:
                import boto3  # type: ignore[import-untyped]

                self._client = boto3.client("events", region_name=region)
                self._is_live = True
            except Exception as exc:  # pragma: no cover — env-specific
                logger.info(
                    "CloudTrailEventBridgeSink falling back to no-op: %s",
                    exc,
                )
                self._client = None
                self._is_live = False

    @property
    def is_live(self) -> bool:
        return self._is_live

    def emit(self, event: AuditEvent) -> None:
        if not self._is_live:
            return
        try:
            self._client.put_events(
                Entries=[
                    {
                        "Source": "aura.model_assurance",
                        "DetailType": event.event_type.value,
                        "Detail": json.dumps(event.to_cloudtrail_record()),
                        "EventBusName": self._bus_name,
                    }
                ]
            )
        except Exception as exc:  # pragma: no cover — runtime AWS failure
            logger.warning(
                "CloudTrailEventBridgeSink put_events failed: %s", exc,
            )


def _content_hash(
    *,
    event_type: AuditEventType,
    candidate_id: str,
    occurred_at: datetime,
    correlation_id: str,
) -> str:
    payload = json.dumps(
        {
            "event_type": event_type.value,
            "candidate_id": candidate_id,
            "occurred_at": occurred_at.isoformat(),
            "correlation_id": correlation_id,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class AuditEmitter:
    """Stateless emitter that fans out to one or more sinks."""

    def __init__(self, sinks: Iterable[AuditEventSink]) -> None:
        self._sinks = tuple(sinks)

    def emit(
        self,
        *,
        event_type: AuditEventType,
        candidate_id: str,
        actor: str = "system",
        correlation_id: str = "",
        request_parameters: Mapping[str, str] | None = None,
        response_elements: Mapping[str, str] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        occurred_at: datetime | None = None,
    ) -> AuditEvent:
        ts = occurred_at or datetime.now(timezone.utc)
        event_id = _content_hash(
            event_type=event_type,
            candidate_id=candidate_id,
            occurred_at=ts,
            correlation_id=correlation_id,
        )
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            candidate_id=candidate_id,
            occurred_at=ts,
            actor=actor,
            correlation_id=correlation_id,
            request_parameters=tuple(sorted((request_parameters or {}).items())),
            response_elements=tuple(sorted((response_elements or {}).items())),
            error_code=error_code,
            error_message=error_message,
        )
        for sink in self._sinks:
            try:
                sink.emit(event)
            except Exception as exc:
                logger.warning(
                    "audit sink %s.emit failed: %s",
                    type(sink).__name__,
                    exc,
                )
        return event


def filter_events_by_control(
    events: Iterable[AuditEvent], control: NISTControl
) -> tuple[AuditEvent, ...]:
    """Return all events whose NIST mapping includes ``control``."""
    return tuple(
        e for e in events if control in e.applicable_controls
    )
