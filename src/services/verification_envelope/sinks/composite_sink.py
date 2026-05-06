"""Project Aura - Composite audit sink (ADR-085 Phase 5).

Forwards each archive call to multiple downstream sinks. Used to fan
out audit records to both the DynamoDB metadata table and the S3
proof archive in production while keeping the auditor a one-sink
client.
"""

from __future__ import annotations

import logging
from typing import Sequence

from src.services.verification_envelope.formal.verification_auditor import (
    ArchiveOutcome,
    AuditRecord,
    _ArchiveSink,
)

logger = logging.getLogger(__name__)


class CompositeArchiveSink:
    """Fan-out sink: forwards to each child in declaration order.

    The composite outcome is the *worst* outcome reported by any
    child (FAILED dominates SKIPPED dominates ARCHIVED). Children are
    invoked sequentially so a critical sink (e.g. DynamoDB) can be
    reasoned about independently of an opportunistic one (S3).
    """

    def __init__(self, sinks: Sequence[_ArchiveSink]) -> None:
        if not sinks:
            raise ValueError("CompositeArchiveSink requires at least one child")
        self._sinks = list(sinks)

    @property
    def children(self) -> tuple[_ArchiveSink, ...]:
        return tuple(self._sinks)

    async def archive(
        self, record: AuditRecord, smt_assertions: str
    ) -> ArchiveOutcome:
        outcomes: list[ArchiveOutcome] = []
        for sink in self._sinks:
            outcomes.append(await sink.archive(record, smt_assertions))

        # Worst outcome dominates so callers see the most-conservative result.
        for severity in (
            ArchiveOutcome.FAILED,
            ArchiveOutcome.SKIPPED,
            ArchiveOutcome.ARCHIVED,
        ):
            if severity in outcomes:
                return severity
        # Should be unreachable; defensive default.
        return ArchiveOutcome.FAILED  # pragma: no cover
