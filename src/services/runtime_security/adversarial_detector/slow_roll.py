"""Slow-roll capability-creep detector (issue #211).

Detects an agent that requests progressively *more* privileged tools
over a long window, even when each request individually looks normal.

Algorithm: bucket the agent's events into a configurable number of
equal-sized time buckets, compute the mean capability tier per
bucket, and check whether the sequence is monotonically (or near-
monotonically) increasing. The strength of the upward trend is
measured by Spearman-style rank correlation between bucket index
and bucket-mean capability tier; a coefficient above the threshold
fires a HIGH finding.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Sequence

from src.services.runtime_security.adversarial_detector.contracts import (
    AdversarialFinding,
    AdversarialFindingSeverity,
    AgentActionEvent,
    DelegationEdge,
)


def _spearman_rank_correlation(values: Sequence[float]) -> float:
    """Spearman rank correlation between the natural index 0..n-1 and ``values``.

    Returns a float in [-1.0, 1.0]. Implemented from scratch to avoid
    pulling scipy into a runtime security path.
    """
    n = len(values)
    if n < 2:
        return 0.0
    # Compute ranks (1-indexed) with ties resolved by averaging.
    enumerated = sorted(enumerate(values), key=lambda p: p[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and enumerated[j + 1][1] == enumerated[i][1]:
            j += 1
        # Average rank for ties.
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[enumerated[k][0]] = avg_rank
        i = j + 1
    # Index ranks are 1..n exactly.
    index_ranks = [float(k + 1) for k in range(n)]
    mean_idx = (n + 1) / 2.0
    mean_val = sum(ranks) / n
    num = sum((index_ranks[k] - mean_idx) * (ranks[k] - mean_val) for k in range(n))
    den_idx = sum((r - mean_idx) ** 2 for r in index_ranks)
    den_val = sum((r - mean_val) ** 2 for r in ranks)
    if den_idx == 0 or den_val == 0:
        return 0.0
    return num / ((den_idx * den_val) ** 0.5)


class SlowRollCapabilityCreepDetector:
    """Flags agents whose capability-tier usage trends upward.

    Defaults assume a 4-tier capability scale (basic=0, elevated=1,
    privileged=2, admin=3). The detector buckets events into 5
    equal-sized time slices and fires a HIGH finding when the
    Spearman correlation between bucket index and bucket-mean tier
    exceeds ``trend_threshold`` (default 0.85).
    """

    detector_id: str = "slow-roll-capability-creep-v1"
    pattern_name: str = "slow-roll-capability-creep"
    mitre_attack_id: str = "T1548"  # Abuse Elevation Control Mechanism

    def __init__(
        self,
        *,
        bucket_count: int = 5,
        trend_threshold: float = 0.85,
        min_events_per_agent: int = 10,
    ) -> None:
        if bucket_count < 2:
            raise ValueError("bucket_count must be >= 2")
        if not 0.0 < trend_threshold <= 1.0:
            raise ValueError("trend_threshold must be in (0, 1]")
        self._bucket_count = bucket_count
        self._trend_threshold = trend_threshold
        self._min_events = min_events_per_agent

    def detect(
        self,
        *,
        events: Sequence[AgentActionEvent],
        delegations: Sequence[DelegationEdge] = (),
    ) -> tuple[AdversarialFinding, ...]:
        # Group events by agent.
        by_agent: dict[str, list[AgentActionEvent]] = defaultdict(list)
        for e in events:
            by_agent[e.agent_id].append(e)

        findings: list[AdversarialFinding] = []
        for agent_id, agent_events in by_agent.items():
            if len(agent_events) < self._min_events:
                continue
            agent_events.sort(key=lambda e: e.timestamp)
            # Equal-count buckets (more stable than equal-time when
            # events arrive in bursts).
            bucket_size = max(1, len(agent_events) // self._bucket_count)
            bucket_means: list[float] = []
            for b in range(self._bucket_count):
                lo = b * bucket_size
                hi = (
                    lo + bucket_size
                    if b < self._bucket_count - 1
                    else len(agent_events)
                )
                bucket = agent_events[lo:hi]
                if not bucket:
                    continue
                bucket_means.append(
                    sum(e.capability_tier for e in bucket) / len(bucket)
                )
            if len(bucket_means) < 2:
                continue
            correlation = _spearman_rank_correlation(bucket_means)
            if correlation < self._trend_threshold:
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
                        f"Capability-tier mean across {len(bucket_means)} "
                        f"buckets shows monotone upward trend "
                        f"(Spearman={correlation:.3f}, "
                        f"threshold={self._trend_threshold:.2f}). "
                        f"Bucket means: "
                        f"{[round(m, 2) for m in bucket_means]}."
                    ),
                    evidence={
                        "bucket_count": len(bucket_means),
                        "bucket_means": bucket_means,
                        "spearman_correlation": correlation,
                        "threshold": self._trend_threshold,
                        "agent_event_count": len(agent_events),
                    },
                )
            )
        return tuple(findings)
