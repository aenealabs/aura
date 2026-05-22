"""Dormancy-then-burst detector (issue #211).

Detects an agent that is idle for an extended period then issues a
large coordinated action sequence within a small wall-clock window.

Algorithm: compute inter-event time deltas for an agent. Take the
z-score of the largest gap relative to the population of gaps. If
the largest gap is multiple standard deviations above the mean
AND it is followed by a burst (>= ``burst_count`` events within
``burst_window_seconds``), fire a HIGH finding.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from typing import Sequence

from src.services.runtime_security.adversarial_detector.contracts import (
    AdversarialFinding,
    AdversarialFindingSeverity,
    AgentActionEvent,
    DelegationEdge,
)


class DormancyThenBurstDetector:
    """Flags long idle period followed by a coordinated burst.

    The detector is intentionally insensitive to short bursts that
    happen during normal use -- it only fires when the gap before
    the burst is statistically anomalous AND the burst is dense.
    """

    detector_id: str = "dormancy-burst-v1"
    pattern_name: str = "dormancy-then-burst"
    mitre_attack_id: str = "T1029"  # Scheduled Transfer (closest match)

    def __init__(
        self,
        *,
        gap_z_threshold: float = 3.0,
        burst_count: int = 8,
        burst_window_seconds: float = 60.0,
        min_events_per_agent: int = 10,
    ) -> None:
        if gap_z_threshold <= 0:
            raise ValueError("gap_z_threshold must be positive")
        if burst_count < 2:
            raise ValueError("burst_count must be >= 2")
        if burst_window_seconds <= 0:
            raise ValueError("burst_window_seconds must be positive")
        self._z_threshold = gap_z_threshold
        self._burst_count = burst_count
        self._burst_window = burst_window_seconds
        self._min_events = min_events_per_agent

    def detect(
        self,
        *,
        events: Sequence[AgentActionEvent],
        delegations: Sequence[DelegationEdge] = (),
    ) -> tuple[AdversarialFinding, ...]:
        by_agent: dict[str, list[AgentActionEvent]] = defaultdict(list)
        for e in events:
            by_agent[e.agent_id].append(e)

        findings: list[AdversarialFinding] = []
        for agent_id, agent_events in by_agent.items():
            if len(agent_events) < self._min_events:
                continue
            agent_events.sort(key=lambda e: e.timestamp)
            gaps_seconds: list[float] = []
            for i in range(1, len(agent_events)):
                delta = (
                    agent_events[i].timestamp - agent_events[i - 1].timestamp
                ).total_seconds()
                gaps_seconds.append(delta)
            if not gaps_seconds:
                continue
            mean = sum(gaps_seconds) / len(gaps_seconds)
            variance = sum((g - mean) ** 2 for g in gaps_seconds) / len(gaps_seconds)
            stdev = math.sqrt(variance) if variance > 0 else 0.0
            if stdev == 0:
                continue
            # Find the largest gap and its z-score.
            max_gap_idx = max(range(len(gaps_seconds)), key=lambda i: gaps_seconds[i])
            max_gap = gaps_seconds[max_gap_idx]
            z = (max_gap - mean) / stdev
            if z < self._z_threshold:
                continue
            # Check whether the events AFTER the gap form a burst.
            post_gap_events = agent_events[max_gap_idx + 1 :]
            if len(post_gap_events) < self._burst_count:
                continue
            window_end = post_gap_events[0].timestamp.timestamp() + self._burst_window
            burst_in_window = sum(
                1 for e in post_gap_events if e.timestamp.timestamp() <= window_end
            )
            if burst_in_window < self._burst_count:
                continue

            findings.append(
                AdversarialFinding(
                    finding_id=str(uuid.uuid4()),
                    pattern_name=self.pattern_name,
                    detector_id=self.detector_id,
                    severity=AdversarialFindingSeverity.HIGH,
                    agent_id=agent_id,
                    mitre_attack_id=self.mitre_attack_id,
                    rationale=(
                        f"Idle gap of {max_gap:.0f}s (z={z:.2f}) followed by "
                        f"a burst of {burst_in_window} events within "
                        f"{self._burst_window:.0f}s. Pattern is consistent "
                        f"with a sleeper-then-active adversarial schedule."
                    ),
                    evidence={
                        "max_gap_seconds": max_gap,
                        "gap_z_score": z,
                        "burst_event_count": burst_in_window,
                        "burst_window_seconds": self._burst_window,
                        "agent_event_count": len(agent_events),
                    },
                )
            )
        return tuple(findings)
