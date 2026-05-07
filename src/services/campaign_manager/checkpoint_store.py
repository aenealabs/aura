"""
Project Aura - Phase Checkpoint Store.

Persistence interface for ``PhaseCheckpoint``. Production stores the
checkpoint manifest in DynamoDB and the larger artifacts (reasoning
traces) in S3 with Object Lock compliance mode. This module ships the
in-memory backend; the on-resume signature verification is enforced
by the Protocol.

Implements ADR-089 D2 (checkpoint schema) and the
"Checkpoint / Resume Protocol" section.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

import threading
from typing import Protocol

from .contracts import PhaseCheckpoint
from .exceptions import TamperedStateError


class CheckpointStore(Protocol):
    """Contract every checkpoint-store backend must satisfy."""

    async def write(self, checkpoint: PhaseCheckpoint) -> str:
        """Persist a checkpoint. Returns the storage key (e.g. S3 key)."""
        ...

    async def read(
        self, campaign_id: str, phase_id: str
    ) -> PhaseCheckpoint | None:
        """Read the latest checkpoint for a phase, or ``None``.

        Implementations MUST verify the KMS signature before returning;
        a signature mismatch raises ``TamperedStateError``. The in-memory
        impl below uses a trivial signature scheme (the value of the
        ``kms_signature`` field) so tests can simulate tampering.
        """
        ...

    async def latest_for_campaign(
        self, campaign_id: str
    ) -> PhaseCheckpoint | None:
        """Read the most recent checkpoint across any phase."""
        ...


class InMemoryCheckpointStore:
    """In-memory implementation of ``CheckpointStore``.

    Includes a ``simulate_tamper`` helper for tests so the resume-path
    signature verification can be exercised without standing up KMS.
    """

    def __init__(self) -> None:
        # ((campaign_id, phase_id) -> PhaseCheckpoint)
        self._checkpoints: dict[tuple[str, str], PhaseCheckpoint] = {}
        # campaign_id -> last-written (phase_id, timestamp)
        self._latest: dict[str, tuple[str, str]] = {}
        # checkpoints whose stored signature has been corrupted
        self._tampered: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    async def write(self, checkpoint: PhaseCheckpoint) -> str:
        if not checkpoint.kms_signature:
            raise ValueError(
                "checkpoint.kms_signature is required; "
                "production writers must KMS-sign before persisting"
            )
        key = (checkpoint.campaign_id, checkpoint.phase_id)
        storage_key = (
            f"checkpoints/{checkpoint.campaign_id}/"
            f"{checkpoint.phase_id}.json"
        )
        with self._lock:
            self._checkpoints[key] = checkpoint
            self._latest[checkpoint.campaign_id] = (
                checkpoint.phase_id,
                checkpoint.created_at.isoformat(),
            )
        return storage_key

    async def read(
        self, campaign_id: str, phase_id: str
    ) -> PhaseCheckpoint | None:
        key = (campaign_id, phase_id)
        with self._lock:
            checkpoint = self._checkpoints.get(key)
            if checkpoint is None:
                return None
            if key in self._tampered:
                raise TamperedStateError(
                    f"Checkpoint {key!r} signature does not verify; "
                    f"refusing to resume"
                )
            return checkpoint

    async def latest_for_campaign(
        self, campaign_id: str
    ) -> PhaseCheckpoint | None:
        with self._lock:
            ref = self._latest.get(campaign_id)
            if ref is None:
                return None
            phase_id = ref[0]
            checkpoint = self._checkpoints.get((campaign_id, phase_id))
            if checkpoint is None:
                return None
            if (campaign_id, phase_id) in self._tampered:
                raise TamperedStateError(
                    f"Checkpoint for campaign {campaign_id} phase "
                    f"{phase_id} signature does not verify"
                )
            return checkpoint

    def simulate_tamper(self, campaign_id: str, phase_id: str) -> None:
        """Test helper: mark a stored checkpoint as having a bad signature."""
        with self._lock:
            self._tampered.add((campaign_id, phase_id))
