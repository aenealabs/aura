"""Data contracts for adversarial-agent detection (issue #211)."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class AdversarialFindingSeverity(enum.Enum):
    """Severity bands aligned with the existing runtime_security.Severity."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


@dataclass(frozen=True)
class AgentActionEvent:
    """A single agent action observed in the runtime stream.

    A small, focused slice of ``RuntimeEvent`` -- only the fields the
    adversarial detectors actually use. Existing instrumentation
    derives one of these per ``RuntimeEvent`` via a small adapter
    layer (not shipped here; the adapter is a one-line projection
    consumers wire up).
    """

    agent_id: str
    action_name: str  # e.g. "bedrock:InvokeModel", "tool:fs.write"
    timestamp: datetime
    capability_tier: int = 0  # 0=basic, 1=elevated, 2=privileged, 3=admin
    action_kind: str = "tool"  # "tool" | "delegation" | "credential" | "io"
    mitre_attack_id: str = ""


@dataclass(frozen=True)
class DelegationEdge:
    """A delegation observed between two agents.

    Mirrors ADR-086 Phase 3's DelegationAssertion in shape; the
    detector consumes only the structural fields it cares about so
    it stays decoupled from the full assertion implementation.
    """

    from_agent_id: str
    to_agent_id: str
    timestamp: datetime
    depth: int = 1  # ADR-086 depth-bound; > 3 is unusual


@dataclass(frozen=True)
class AdversarialFinding:
    """One detection emitted by an adversarial detector."""

    finding_id: str
    pattern_name: str  # e.g. "slow-roll-capability-creep"
    detector_id: str
    severity: AdversarialFindingSeverity
    agent_id: str  # primary agent the finding is about
    secondary_agent_ids: tuple[str, ...] = ()  # for cross-agent patterns
    mitre_attack_id: str = ""
    rationale: str = ""
    evidence: dict = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_audit_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "pattern_name": self.pattern_name,
            "detector_id": self.detector_id,
            "severity": self.severity.value,
            "agent_id": self.agent_id,
            "secondary_agent_ids": list(self.secondary_agent_ids),
            "mitre_attack_id": self.mitre_attack_id,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "detected_at": self.detected_at.isoformat(),
        }
