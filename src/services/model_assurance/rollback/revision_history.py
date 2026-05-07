"""Append-only revision history for the rollback mechanism."""

from __future__ import annotations

import threading
from typing import Iterable

from src.services.model_assurance.rollback.contracts import ConfigRevision


class RevisionHistory:
    """In-memory append-only log of :class:`ConfigRevision` entries.

    v1 is in-process; production wiring backs this with a DynamoDB
    table keyed on revision_id. The interface (append / latest /
    nth_back / find / iter) is deliberately small so the swap is a
    single-class change.
    """

    def __init__(self) -> None:
        self._revisions: list[ConfigRevision] = []
        self._lock = threading.RLock()

    def append(self, revision: ConfigRevision) -> None:
        with self._lock:
            existing_ids = {r.revision_id for r in self._revisions}
            if revision.revision_id in existing_ids:
                raise ValueError(
                    f"revision_id {revision.revision_id!r} already in history",
                )
            self._revisions.append(revision)

    def latest(self) -> ConfigRevision | None:
        with self._lock:
            return self._revisions[-1] if self._revisions else None

    def nth_back(self, n: int) -> ConfigRevision | None:
        """Return the revision n steps back from latest.

        ``n=0`` returns the latest. ``n=1`` returns the previous one
        (the rollback target for a single rollback). ``n=2`` returns
        n-2 (the double-rollback target).
        """
        if n < 0:
            raise ValueError(f"n must be >= 0; got {n}")
        with self._lock:
            if n >= len(self._revisions):
                return None
            return self._revisions[-(n + 1)]

    def find(self, revision_id: str) -> ConfigRevision | None:
        with self._lock:
            for r in self._revisions:
                if r.revision_id == revision_id:
                    return r
            return None

    def __len__(self) -> int:
        with self._lock:
            return len(self._revisions)

    def __iter__(self):
        with self._lock:
            return iter(list(self._revisions))

    def all(self) -> tuple[ConfigRevision, ...]:
        with self._lock:
            return tuple(self._revisions)
