"""
Project Aura - Long-Horizon Security Campaign Manager.

Composes existing scanner, verification, and constitutional-AI primitives
into multi-hour autonomous security workloads (compliance hardening,
vulnerability remediation, cross-repo chain analysis, threat hunting,
Mythos exploit refinement, self-play training).

Implements ADR-089. The Step Functions integration and real DynamoDB
persistence are wired in via the abstract stores defined here; in-memory
implementations let the orchestrator be tested end-to-end without AWS.

Author: Project Aura Team
Created: 2026-05-07
"""

from .contracts import (
    CampaignDefinition,
    CampaignOutcome,
    CampaignPhase,
    CampaignState,
    CampaignStatus,
    CampaignType,
    PhaseCheckpoint,
    PhaseOutcome,
)
from .exceptions import (
    CampaignError,
    CostCapExceededError,
    InvalidCampaignDefinitionError,
    OperationAlreadyClaimedError,
    SeparationOfDutiesError,
    TamperedStateError,
)
from .phases.chain_analysis import ChainAnalysisWorker
from .phases.compliance_hardening import ComplianceHardeningWorker
from .phases.mythos_exploit_refinement import MythosExploitRefinementWorker
from .phases.self_play_training import SelfPlayTrainingWorker
from .phases.threat_hunting import ContinuousThreatHuntingWorker
from .phases.vulnerability_remediation import VulnerabilityRemediationWorker


def build_default_worker_registry() -> dict[CampaignType, object]:
    """Return a worker registry covering every campaign type.

    Phase 5 (Mythos) is included as a blocked-stub; production code
    can swap in a real implementation when issue #115 clears.
    """
    return {
        CampaignType.COMPLIANCE_HARDENING: ComplianceHardeningWorker(),
        CampaignType.VULNERABILITY_REMEDIATION: VulnerabilityRemediationWorker(),
        CampaignType.CROSS_REPO_CHAIN_ANALYSIS: ChainAnalysisWorker(),
        CampaignType.CONTINUOUS_THREAT_HUNTING: ContinuousThreatHuntingWorker(),
        CampaignType.MYTHOS_EXPLOIT_REFINEMENT: MythosExploitRefinementWorker(),
        CampaignType.SELF_PLAY_SECURITY_TRAINING: SelfPlayTrainingWorker(),
    }


__all__ = [
    "CampaignDefinition",
    "CampaignOutcome",
    "CampaignPhase",
    "CampaignState",
    "CampaignStatus",
    "CampaignType",
    "PhaseCheckpoint",
    "PhaseOutcome",
    "CampaignError",
    "CostCapExceededError",
    "InvalidCampaignDefinitionError",
    "OperationAlreadyClaimedError",
    "SeparationOfDutiesError",
    "TamperedStateError",
    "ChainAnalysisWorker",
    "ComplianceHardeningWorker",
    "ContinuousThreatHuntingWorker",
    "MythosExploitRefinementWorker",
    "SelfPlayTrainingWorker",
    "VulnerabilityRemediationWorker",
    "build_default_worker_registry",
]
