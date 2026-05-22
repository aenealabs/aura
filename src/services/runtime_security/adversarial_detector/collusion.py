"""Cross-agent collusion detector (issue #211).

Detects two-or-more-agent coordinated action sequences where each
individual action looks fine but the *combination* completes a
known adversarial TTP (Tactics, Techniques, Procedures).

The detector takes a small declarative ``TTPRule`` registry and
scans the event stream for ordered action sequences that match a
rule's pattern across distinct agents within a time window.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Sequence

from src.services.runtime_security.adversarial_detector.contracts import (
    AdversarialFinding,
    AdversarialFindingSeverity,
    AgentActionEvent,
    DelegationEdge,
)


@dataclass(frozen=True)
class TTPRule:
    """Declarative rule for a multi-agent TTP.

    A rule fires when the named ``action_sequence`` is observed in
    order across **distinct** agents inside the ``window_seconds``
    time bound. Action names match by exact string equality against
    ``AgentActionEvent.action_name``.
    """

    rule_id: str  # e.g. "credential-shuck-and-pivot"
    description: str
    action_sequence: tuple[str, ...]  # ordered
    window_seconds: float
    mitre_attack_id: str
    severity: AdversarialFindingSeverity = AdversarialFindingSeverity.CRITICAL


# A small default registry of widely-recognised cross-agent TTPs.
DEFAULT_TTP_RULES: tuple[TTPRule, ...] = (
    TTPRule(
        rule_id="credential-shuck-and-pivot",
        description=(
            "Agent A retrieves a credential; agent B (within the same "
            "window) uses the same credential against a separate "
            "principal -- classic intra-fleet pivot."
        ),
        action_sequence=("credential:read", "credential:use"),
        window_seconds=60.0,
        mitre_attack_id="T1552",  # Unsecured Credentials
    ),
    TTPRule(
        rule_id="staged-tool-handoff",
        description=(
            "Agent A stages a payload to shared storage; agent B "
            "executes from that storage. Common evasion of per-agent "
            "capability gates."
        ),
        action_sequence=("io:write_shared", "tool:execute_from_shared"),
        window_seconds=120.0,
        mitre_attack_id="T1105",  # Ingress Tool Transfer
    ),
)


class CrossAgentCollusionDetector:
    """TTP-rule engine on cross-agent action streams."""

    detector_id: str = "cross-agent-collusion-v1"

    def __init__(
        self,
        *,
        rules: Sequence[TTPRule] = DEFAULT_TTP_RULES,
    ) -> None:
        if not rules:
            raise ValueError("CrossAgentCollusionDetector requires at least one rule")
        seen: set[str] = set()
        for r in rules:
            if r.rule_id in seen:
                raise ValueError(f"duplicate rule_id: {r.rule_id!r}")
            seen.add(r.rule_id)
            if len(r.action_sequence) < 2:
                raise ValueError(
                    f"rule {r.rule_id!r}: action_sequence must have >= 2 actions"
                )
            if r.window_seconds <= 0:
                raise ValueError(f"rule {r.rule_id!r}: window_seconds must be positive")
        self._rules: tuple[TTPRule, ...] = tuple(rules)

    def detect(
        self,
        *,
        events: Sequence[AgentActionEvent],
        delegations: Sequence[DelegationEdge] = (),
    ) -> tuple[AdversarialFinding, ...]:
        # Group events by action_name for fast lookup.
        by_action: dict[str, list[AgentActionEvent]] = defaultdict(list)
        for e in events:
            by_action[e.action_name].append(e)

        findings: list[AdversarialFinding] = []
        for rule in self._rules:
            findings.extend(self._match_rule(rule, by_action))
        return tuple(findings)

    def _match_rule(
        self,
        rule: TTPRule,
        by_action: dict[str, list[AgentActionEvent]],
    ) -> list[AdversarialFinding]:
        """Find ordered matches for ``rule.action_sequence`` across agents.

        For each anchor event matching the first action, look for a
        subsequent event matching the second action by a DIFFERENT
        agent within the time window; continue for the rest of the
        sequence. Emits one finding per fully-matched sequence.
        """
        first_action = rule.action_sequence[0]
        anchors = by_action.get(first_action, ())
        out: list[AdversarialFinding] = []
        window = timedelta(seconds=rule.window_seconds)
        for anchor in anchors:
            matched_events: list[AgentActionEvent] = [anchor]
            used_agents: set[str] = {anchor.agent_id}
            current_time = anchor.timestamp
            ok = True
            for next_action in rule.action_sequence[1:]:
                # Find the earliest candidate after current_time, by a
                # NEW agent, within the window from the anchor.
                candidates = [
                    e
                    for e in by_action.get(next_action, ())
                    if e.timestamp > current_time
                    and e.agent_id not in used_agents
                    and e.timestamp - anchor.timestamp <= window
                ]
                if not candidates:
                    ok = False
                    break
                pick = min(candidates, key=lambda e: e.timestamp)
                matched_events.append(pick)
                used_agents.add(pick.agent_id)
                current_time = pick.timestamp
            if ok:
                primary = matched_events[0].agent_id
                others = tuple(sorted({e.agent_id for e in matched_events[1:]}))
                out.append(
                    AdversarialFinding(
                        finding_id=str(uuid.uuid4()),
                        pattern_name=rule.rule_id,
                        detector_id=self.detector_id,
                        severity=rule.severity,
                        agent_id=primary,
                        secondary_agent_ids=others,
                        mitre_attack_id=rule.mitre_attack_id,
                        rationale=rule.description,
                        evidence={
                            "rule_id": rule.rule_id,
                            "matched_actions": [e.action_name for e in matched_events],
                            "matched_agents": [e.agent_id for e in matched_events],
                            "span_seconds": (
                                matched_events[-1].timestamp
                                - matched_events[0].timestamp
                            ).total_seconds(),
                        },
                    )
                )
        return out
