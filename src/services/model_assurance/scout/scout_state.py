"""Scout Agent persistent state (ADR-088 Phase 1.4).

Tracks which models are currently under evaluation, which were
previously rejected, and which are pending availability in the
deployment partition. The state is the dedup key — without it, every
poll cycle would re-emit events for already-known models and flood
the evaluation queue with duplicates.

v1 ships an in-memory implementation suitable for tests and dev. The
production DynamoDB-backed variant lands with the rest of the audit
infrastructure in Phase 2 (the table schema lives in ADR-088 §Stage 1
+ Stage 8). This module's interface (the ``ScoutStateStore`` Protocol)
is the only contract Phase 2 needs to honor.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ScoutStateSnapshot:
    """Read-only view of the scout state at a point in time."""

    active_evaluations: frozenset[str]
    rejected: frozenset[str]
    pending_availability: frozenset[str]
    incumbent_ids: frozenset[str]


class ScoutStateStore(Protocol):
    """Backend protocol for scout dedup state."""

    def snapshot(self) -> ScoutStateSnapshot: ...
    def mark_active(self, candidate_id: str) -> None: ...
    def mark_evaluation_complete(
        self, candidate_id: str, *, accepted: bool
    ) -> None: ...
    def mark_pending_availability(self, candidate_id: str) -> None: ...
    def clear_pending(self, candidate_id: str) -> None: ...
    def set_incumbent(self, candidate_id: str) -> None: ...


class InMemoryScoutStateStore:
    """Thread-safe in-memory implementation of :class:`ScoutStateStore`.

    Suitable for tests and dev. Production deployments should swap in
    a DynamoDB-backed store keyed by ``candidate_id`` so multiple
    Scout Agent instances (one per region) share dedup state.
    """

    def __init__(
        self,
        *,
        initial_incumbents: frozenset[str] = frozenset(),
        initial_rejected: frozenset[str] = frozenset(),
    ) -> None:
        self._active: set[str] = set()
        self._rejected: set[str] = set(initial_rejected)
        self._pending: set[str] = set()
        self._incumbent: set[str] = set(initial_incumbents)
        self._lock = threading.RLock()

    def snapshot(self) -> ScoutStateSnapshot:
        with self._lock:
            return ScoutStateSnapshot(
                active_evaluations=frozenset(self._active),
                rejected=frozenset(self._rejected),
                pending_availability=frozenset(self._pending),
                incumbent_ids=frozenset(self._incumbent),
            )

    def mark_active(self, candidate_id: str) -> None:
        with self._lock:
            self._active.add(candidate_id)

    def mark_evaluation_complete(
        self, candidate_id: str, *, accepted: bool
    ) -> None:
        with self._lock:
            self._active.discard(candidate_id)
            if accepted:
                # Accepted candidates become the new incumbent — remove
                # any prior incumbent at the orchestrator level.
                self._incumbent.add(candidate_id)
            else:
                # Sticky rejection — same model can't be re-evaluated
                # without an explicit operator action.
                self._rejected.add(candidate_id)

    def mark_pending_availability(self, candidate_id: str) -> None:
        with self._lock:
            self._pending.add(candidate_id)

    def clear_pending(self, candidate_id: str) -> None:
        with self._lock:
            self._pending.discard(candidate_id)

    def set_incumbent(self, candidate_id: str) -> None:
        with self._lock:
            self._incumbent.add(candidate_id)

    # Operator escape-hatch: lift a sticky rejection. Not in the
    # Protocol — this is a manual admin operation, not part of the
    # Scout Agent's autonomous loop.
    def lift_rejection(self, candidate_id: str) -> None:
        with self._lock:
            self._rejected.discard(candidate_id)
