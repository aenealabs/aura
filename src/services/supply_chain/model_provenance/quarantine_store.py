"""Lightweight in-memory model quarantine (ADR-088 Phase 2.1).

The model provenance pipeline needs sticky rejection of failed
artifacts: a model that fails verification once should not
auto-retry on the next Scout run. This module provides the in-memory
default; production deployments wire a DynamoDB-backed implementation
satisfying :class:`ModelQuarantineStore` (Phase 2 infrastructure).

This is intentionally NOT a reuse of ADR-067's
:class:`QuarantineManager` — that one is content-chunk centric
(Neptune + OpenSearch state, ProvenanceRecord shape). Models are a
different unit and forcing the shapes together would create a
maintenance liability. The two stores share concept ("a thing that
was rejected stays rejected") but not implementation.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class QuarantineEntry:
    model_id: str
    quarantine_id: str
    reason: str
    quarantined_at: datetime


class ModelQuarantineStore(Protocol):
    def quarantine(self, model_id: str, reason: str) -> QuarantineEntry: ...
    def is_quarantined(self, model_id: str) -> bool: ...
    def get(self, model_id: str) -> QuarantineEntry | None: ...
    def lift(self, model_id: str) -> bool: ...


class InMemoryModelQuarantineStore:
    """Thread-safe in-memory implementation."""

    def __init__(self) -> None:
        self._entries: dict[str, QuarantineEntry] = {}
        self._lock = threading.RLock()
        self._counter = 0

    def quarantine(self, model_id: str, reason: str) -> QuarantineEntry:
        with self._lock:
            # Idempotent: re-quarantining returns the original entry so
            # the quarantine_id stays stable across reruns.
            existing = self._entries.get(model_id)
            if existing is not None:
                return existing
            self._counter += 1
            entry = QuarantineEntry(
                model_id=model_id,
                quarantine_id=f"mq-{self._counter:08d}",
                reason=reason,
                quarantined_at=datetime.now(timezone.utc),
            )
            self._entries[model_id] = entry
            return entry

    def is_quarantined(self, model_id: str) -> bool:
        with self._lock:
            return model_id in self._entries

    def get(self, model_id: str) -> QuarantineEntry | None:
        with self._lock:
            return self._entries.get(model_id)

    def lift(self, model_id: str) -> bool:
        """Operator escape-hatch — admin only, never agent-initiated."""
        with self._lock:
            return self._entries.pop(model_id, None) is not None
