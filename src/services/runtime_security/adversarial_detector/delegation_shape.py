"""Delegation-graph-shape anomaly detector (issue #211).

Detects an agent whose outgoing delegation pattern is structurally
unusual against a configured population baseline:

  - **Star** -- one agent delegating to many distinct targets.
  - **Deep chain** -- depth exceeds the ADR-086 depth-bound (default 3).
  - **Rapid fan-out** -- many delegations in a short window.

The detector takes a sequence of ``DelegationEdge`` records (already
present per ADR-086 Phase 3) and runs three structural rules.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta
from typing import Sequence

from src.services.runtime_security.adversarial_detector.contracts import (
    AdversarialFinding,
    AdversarialFindingSeverity,
    AgentActionEvent,
    DelegationEdge,
)


class DelegationGraphShapeDetector:
    """Flags agents with anomalous outbound delegation patterns."""

    detector_id: str = "delegation-shape-v1"
    pattern_name_star: str = "delegation-star-topology"
    pattern_name_chain: str = "delegation-depth-exceeded"
    pattern_name_fanout: str = "delegation-rapid-fanout"
    mitre_attack_id: str = "T1098"  # Account Manipulation

    def __init__(
        self,
        *,
        star_target_threshold: int = 8,
        depth_threshold: int = 3,
        fanout_window_seconds: float = 60.0,
        fanout_count_threshold: int = 6,
    ) -> None:
        if star_target_threshold < 2:
            raise ValueError("star_target_threshold must be >= 2")
        if depth_threshold < 1:
            raise ValueError("depth_threshold must be >= 1")
        if fanout_window_seconds <= 0:
            raise ValueError("fanout_window_seconds must be positive")
        if fanout_count_threshold < 2:
            raise ValueError("fanout_count_threshold must be >= 2")
        self._star_threshold = star_target_threshold
        self._depth_threshold = depth_threshold
        self._fanout_window = timedelta(seconds=fanout_window_seconds)
        self._fanout_count = fanout_count_threshold

    def detect(
        self,
        *,
        events: Sequence[AgentActionEvent],
        delegations: Sequence[DelegationEdge] = (),
    ) -> tuple[AdversarialFinding, ...]:
        if not delegations:
            return ()

        findings: list[AdversarialFinding] = []
        out_edges: dict[str, list[DelegationEdge]] = defaultdict(list)
        for edge in delegations:
            out_edges[edge.from_agent_id].append(edge)

        # Star detection.
        for agent_id, edges in out_edges.items():
            distinct_targets = {e.to_agent_id for e in edges}
            if len(distinct_targets) >= self._star_threshold:
                findings.append(
                    AdversarialFinding(
                        finding_id=str(uuid.uuid4()),
                        pattern_name=self.pattern_name_star,
                        detector_id=self.detector_id,
                        severity=AdversarialFindingSeverity.HIGH,
                        agent_id=agent_id,
                        secondary_agent_ids=tuple(sorted(distinct_targets)),
                        mitre_attack_id=self.mitre_attack_id,
                        rationale=(
                            f"Agent delegated to {len(distinct_targets)} "
                            f"distinct targets (threshold "
                            f"{self._star_threshold}). Star topology is "
                            f"consistent with credential-spraying or "
                            f"orchestration of a sub-fleet for collusion."
                        ),
                        evidence={
                            "target_count": len(distinct_targets),
                            "edge_count": len(edges),
                        },
                    )
                )

        # Depth-exceeded detection.
        for edge in delegations:
            if edge.depth > self._depth_threshold:
                findings.append(
                    AdversarialFinding(
                        finding_id=str(uuid.uuid4()),
                        pattern_name=self.pattern_name_chain,
                        detector_id=self.detector_id,
                        severity=AdversarialFindingSeverity.CRITICAL,
                        agent_id=edge.from_agent_id,
                        secondary_agent_ids=(edge.to_agent_id,),
                        mitre_attack_id=self.mitre_attack_id,
                        rationale=(
                            f"Delegation depth {edge.depth} exceeds "
                            f"ADR-086 depth-bound "
                            f"({self._depth_threshold}). Deep chains evade "
                            f"per-hop authorisation review."
                        ),
                        evidence={
                            "depth": edge.depth,
                            "threshold": self._depth_threshold,
                            "to_agent": edge.to_agent_id,
                        },
                    )
                )

        # Rapid fan-out detection (per agent, sliding window).
        for agent_id, edges in out_edges.items():
            edges_sorted = sorted(edges, key=lambda e: e.timestamp)
            for i, anchor in enumerate(edges_sorted):
                window_end = anchor.timestamp + self._fanout_window
                count = sum(1 for e in edges_sorted[i:] if e.timestamp <= window_end)
                if count >= self._fanout_count:
                    findings.append(
                        AdversarialFinding(
                            finding_id=str(uuid.uuid4()),
                            pattern_name=self.pattern_name_fanout,
                            detector_id=self.detector_id,
                            severity=AdversarialFindingSeverity.HIGH,
                            agent_id=agent_id,
                            secondary_agent_ids=tuple(
                                sorted(
                                    {e.to_agent_id for e in edges_sorted[i : i + count]}
                                )
                            ),
                            mitre_attack_id=self.mitre_attack_id,
                            rationale=(
                                f"{count} delegations within "
                                f"{self._fanout_window.total_seconds():.0f}s "
                                f"(threshold {self._fanout_count})."
                            ),
                            evidence={
                                "count_in_window": count,
                                "window_seconds": self._fanout_window.total_seconds(),
                            },
                        )
                    )
                    break  # one fanout finding per agent is enough
        return tuple(findings)
