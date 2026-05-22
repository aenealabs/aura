"""Port + dispatcher for adversarial detection (issue #211)."""

from __future__ import annotations

from typing import Iterable, Protocol, Sequence

from src.services.runtime_security.adversarial_detector.contracts import (
    AdversarialFinding,
    AgentActionEvent,
    DelegationEdge,
)


class AdversarialDetectorPort(Protocol):
    """A single adversarial-pattern detector.

    Implementations must be **deterministic** and **side-effect-free**
    given a fixed event stream (so a re-run produces the same
    findings). Each detector focuses on ONE named pattern.
    """

    detector_id: str

    def detect(
        self,
        *,
        events: Sequence[AgentActionEvent],
        delegations: Sequence[DelegationEdge] = (),
    ) -> tuple[AdversarialFinding, ...]:
        """Return zero or more findings for the given event stream."""


class AdversarialDetectorDispatcher:
    """Runs a set of detectors and aggregates their findings.

    Deliberately synchronous + serial -- the detectors are cheap and
    serial execution keeps the audit trail deterministic. Tests pass
    a single detector; production wires the full set.
    """

    def __init__(self, detectors: Iterable[AdversarialDetectorPort]) -> None:
        self._detectors: tuple[AdversarialDetectorPort, ...] = tuple(detectors)
        seen: set[str] = set()
        for d in self._detectors:
            if d.detector_id in seen:
                raise ValueError(
                    f"Duplicate detector_id in dispatcher: {d.detector_id!r}"
                )
            seen.add(d.detector_id)

    @property
    def detector_ids(self) -> tuple[str, ...]:
        return tuple(d.detector_id for d in self._detectors)

    def detect(
        self,
        *,
        events: Sequence[AgentActionEvent],
        delegations: Sequence[DelegationEdge] = (),
    ) -> tuple[AdversarialFinding, ...]:
        aggregated: list[AdversarialFinding] = []
        for detector in self._detectors:
            aggregated.extend(detector.detect(events=events, delegations=delegations))
        return tuple(aggregated)
