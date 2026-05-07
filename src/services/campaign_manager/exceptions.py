"""
Project Aura - Campaign Manager Exceptions.

Implements ADR-089.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations


class CampaignError(Exception):
    """Base class for all campaign-manager exceptions."""


class InvalidCampaignDefinitionError(CampaignError):
    """The CampaignDefinition failed validation at creation time.

    Distinct from a runtime failure: this fires before any phase runs,
    when the API rejects the request.
    """


class CostCapExceededError(CampaignError):
    """The campaign reached its hard cost cap.

    Raised by ``CampaignCostTracker.record`` when an invocation would
    push the campaign over its per-campaign cap. The orchestrator
    catches this, transitions to ``HALTED_AT_CAP``, and emits a
    milestone event for human decision.
    """


class TenantCostCapExceededError(CampaignError):
    """The tenant's cumulative cost rollup hit the per-tenant cap.

    Distinct from per-campaign cap: existing campaigns continue to
    their own caps, but new campaigns refuse to start.
    """


class OperationAlreadyClaimedError(CampaignError):
    """An operation key has already been recorded in the operation ledger.

    Surfaced to callers as a *normal* outcome — the prior outcome is
    returned and the side effect is not re-executed. The orchestrator
    treats it as success after retry.
    """


class TamperedStateError(CampaignError):
    """The KMS signature on a campaign definition or checkpoint did not verify.

    Raised when resuming from persistence; the orchestrator must refuse
    to continue and emit an incident event.
    """


class SeparationOfDutiesError(CampaignError):
    """An approver attempted to approve a milestone they cannot approve.

    The most common cause is the campaign creator attempting to approve
    their own campaign's milestone. Also raised when the approver
    quorum has not been met.
    """


class DriftThresholdExceededError(CampaignError):
    """Drift detection has flagged the campaign for re-anchoring.

    Not a fatal error. The orchestrator catches this, drops working
    memory, reloads from campaign memory, and re-enters the phase from
    its checkpoint.
    """


class HarnessTerminationError(CampaignError):
    """The harness has determined a campaign loop must terminate.

    Per D7, loop termination is harness-driven, never model-driven.
    Workers raise this when their deterministic exit conditions are
    met (sandbox verdict, verification envelope result, success
    criteria progress).
    """
