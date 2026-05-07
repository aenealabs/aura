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
]
