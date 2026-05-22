"""KMS-Sign / Verify abstractions for the campaign manager (issue #214 S1+S2).

Closes the two T1565.001 tampering attacks the Sally review surfaced
on PR #208:

  - S1: ``CampaignDefinition.definition_signature`` was a free-text
    field defaulting to ``""``. Anyone with DynamoDB write could
    mutate ``cost_cap_usd`` / ``approver_quorum`` / ``hitl_milestones``
    after creation without anything detecting it.
  - S2: ``PhaseCheckpoint.kms_signature`` accepted any non-empty
    string via ``_dummy_kms_signature()``. The resume path trusted
    tampered checkpoints in production.

This module ships the Port + a deterministic HMAC test implementation.
Production wires a KMS-backed signer through the same Port; that
implementation lives in ``model_assurance/govcloud/`` and is out of
scope for this PR.
"""

from src.services.campaign_manager.kms_signing.canonical import (
    canonicalize_campaign_definition,
    canonicalize_phase_checkpoint,
)
from src.services.campaign_manager.kms_signing.deterministic import (
    DeterministicCampaignSigner,
)
from src.services.campaign_manager.kms_signing.ports import (
    CampaignSignerPort,
    SignatureVerificationError,
)

__all__ = [
    "CampaignSignerPort",
    "DeterministicCampaignSigner",
    "SignatureVerificationError",
    "canonicalize_campaign_definition",
    "canonicalize_phase_checkpoint",
]
