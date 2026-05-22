"""Adversarial agent detection layer (issue #211).

Signature-based detectors that layer on top of the behavioural
baseline + drift detection in ADR-083. Baselines catch agents whose
behaviour *changes* after compromise. These detectors catch agents
that were *designed from the start* to look normal -- their baseline
itself is adversarial.

Detectors emit ``AdversarialFinding`` records with MITRE ATT&CK IDs
that the existing runtime-security event router consumes.
"""

from src.services.runtime_security.adversarial_detector.collusion import (
    CrossAgentCollusionDetector,
    TTPRule,
)
from src.services.runtime_security.adversarial_detector.contracts import (
    AdversarialFinding,
    AdversarialFindingSeverity,
    AgentActionEvent,
    DelegationEdge,
)
from src.services.runtime_security.adversarial_detector.delegation_shape import (
    DelegationGraphShapeDetector,
)
from src.services.runtime_security.adversarial_detector.dormancy_burst import (
    DormancyThenBurstDetector,
)
from src.services.runtime_security.adversarial_detector.port import (
    AdversarialDetectorDispatcher,
    AdversarialDetectorPort,
)
from src.services.runtime_security.adversarial_detector.slow_roll import (
    SlowRollCapabilityCreepDetector,
)

__all__ = [
    "AdversarialDetectorDispatcher",
    "AdversarialDetectorPort",
    "AdversarialFinding",
    "AdversarialFindingSeverity",
    "AgentActionEvent",
    "CrossAgentCollusionDetector",
    "DelegationEdge",
    "DelegationGraphShapeDetector",
    "DormancyThenBurstDetector",
    "SlowRollCapabilityCreepDetector",
    "TTPRule",
]
