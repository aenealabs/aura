"""Model-specific trust scoring for ADR-088 Phase 2.1.

Per ADR-088 condition #16 (Tara): the Model Provenance Service
extends ADR-076 supply-chain attestation rather than building parallel
infrastructure. The trust score in this module is the model-equivalent
of ADR-067's :class:`TrustScoringEngine` — same shape ([0,1] aggregate
+ component breakdown) but with model-specific signals:

  Provider reputation        — provider tier (well-known vs new entrant)
  Release maturity           — days since vendor release
  Signature status           — VERIFIED is the strong signal
  Registry tier              — BEDROCK = managed, INTERNAL_ECR = self-attest,
                               HUGGINGFACE_CURATED = community
  License posture            — permissive + commercial-use enabled
  Training-data transparency — present vs absent

Component weights are intentionally conservative: a model with no
signature, on a curated HuggingFace repo, with unknown license still
scores high enough (~0.5) to enter HITL review but cannot reach
auto-execute. The HITL flow then makes the final call.

Pure function — same inputs always yield the same score. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.services.supply_chain.model_provenance.contracts import (
    ModelArtifact,
    ModelRegistry,
    SignatureStatus,
)


# Provider reputation tiers. Well-known foundation-model providers
# score high; new entrants score lower until they accumulate
# evaluation history. The tier is a lookup, not a learned value, so
# it can be reasoned about and audited.
_PROVIDER_TIER: dict[str, float] = {
    "anthropic": 1.00,
    "amazon": 1.00,
    "meta": 0.95,
    "google": 0.95,
    "openai": 0.95,
    "mistral": 0.85,
    "cohere": 0.85,
    "ai21": 0.85,
    # Internal SWE-RL outputs from ADR-050.
    "aura": 0.80,
}
_DEFAULT_PROVIDER_TIER = 0.50


_REGISTRY_TIER: dict[ModelRegistry, float] = {
    ModelRegistry.BEDROCK: 1.00,
    ModelRegistry.INTERNAL_ECR: 0.85,
    ModelRegistry.HUGGINGFACE_CURATED: 0.70,
}


_SIGNATURE_TIER: dict[SignatureStatus, float] = {
    SignatureStatus.VERIFIED: 1.00,
    SignatureStatus.UNSIGNED: 0.50,                # Bedrock returns this — provider attests via API
    SignatureStatus.SIGNATURE_INVALID: 0.00,
    SignatureStatus.SIGNING_KEY_EXPIRED: 0.10,
    SignatureStatus.SIGNING_KEY_UNKNOWN: 0.20,
    SignatureStatus.VERIFICATION_ERROR: 0.20,
}


# Component weights. Sum = 1.0 so the aggregate stays in [0,1].
_W_PROVIDER = 0.20
_W_REGISTRY = 0.15
_W_SIGNATURE = 0.30
_W_LICENSE = 0.10
_W_TRAINING_DATA = 0.10
_W_MATURITY = 0.15


# Maturity is a sigmoid-ish curve: a model released 30 days ago is
# at ~0.7, 90 days at ~0.9, 180 days at ~1.0. Brand-new (0 days) is
# ~0.4 — discount-but-not-disqualify.
def _maturity_factor(release_age_days: float) -> float:
    if release_age_days < 0:
        return 0.4  # negative = clock skew; treat as new
    if release_age_days >= 180:
        return 1.0
    # Piecewise linear so the math is auditable.
    if release_age_days < 30:
        return 0.4 + (release_age_days / 30) * 0.3
    if release_age_days < 90:
        return 0.7 + ((release_age_days - 30) / 60) * 0.2
    return 0.9 + ((release_age_days - 90) / 90) * 0.1


@dataclass(frozen=True)
class ModelTrustScore:
    """Detailed trust score breakdown."""

    aggregate: float
    provider_score: float
    registry_score: float
    signature_score: float
    license_score: float
    training_data_score: float
    maturity_score: float

    def __post_init__(self) -> None:
        for name, value in (
            ("aggregate", self.aggregate),
            ("provider_score", self.provider_score),
            ("registry_score", self.registry_score),
            ("signature_score", self.signature_score),
            ("license_score", self.license_score),
            ("training_data_score", self.training_data_score),
            ("maturity_score", self.maturity_score),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"ModelTrustScore.{name} must be in [0,1]; got {value}"
                )

    def to_audit_dict(self) -> dict:
        return {
            "aggregate": round(self.aggregate, 6),
            "provider_score": round(self.provider_score, 6),
            "registry_score": round(self.registry_score, 6),
            "signature_score": round(self.signature_score, 6),
            "license_score": round(self.license_score, 6),
            "training_data_score": round(self.training_data_score, 6),
            "maturity_score": round(self.maturity_score, 6),
        }


def _license_score(artifact: ModelArtifact) -> float:
    lic = artifact.license
    if lic.commercial_use_allowed and lic.is_permissive:
        return 1.0
    if lic.commercial_use_allowed:
        return 0.85
    if lic.spdx_id == "NOASSERTION":
        return 0.5  # Unknown license — neither pass nor fail
    return 0.3      # Restrictive license — score down but not zero


def _training_data_score(artifact: ModelArtifact) -> float:
    lineage = artifact.training_data
    if not lineage.is_present:
        return 0.5  # Missing — neutral
    score = 0.7
    if lineage.cutoff_date is not None:
        score += 0.1
    if lineage.pii_filtered is True:
        score += 0.2
    return min(score, 1.0)


def compute_trust_score(
    artifact: ModelArtifact,
    *,
    signature_status: SignatureStatus,
    release_date: datetime | None = None,
    now: datetime | None = None,
) -> ModelTrustScore:
    """Compute the deterministic trust score.

    ``release_date`` may be None — the maturity component then
    defaults to the "new entrant" floor. The pure-function contract
    is preserved: ``now`` is injectable for tests so the function
    has zero hidden time dependency.
    """
    ts = now or datetime.now(timezone.utc)
    provider = _PROVIDER_TIER.get(
        artifact.provider.lower(), _DEFAULT_PROVIDER_TIER
    )
    registry = _REGISTRY_TIER[artifact.registry]
    signature = _SIGNATURE_TIER[signature_status]
    license_s = _license_score(artifact)
    training = _training_data_score(artifact)

    if release_date is None:
        maturity = 0.4
    else:
        age = max(0.0, (ts - release_date).total_seconds() / 86400.0)
        maturity = _maturity_factor(age)

    aggregate = (
        provider * _W_PROVIDER
        + registry * _W_REGISTRY
        + signature * _W_SIGNATURE
        + license_s * _W_LICENSE
        + training * _W_TRAINING_DATA
        + maturity * _W_MATURITY
    )
    # Defensive clamp — float arithmetic can drift fractionally.
    aggregate = max(0.0, min(1.0, aggregate))

    return ModelTrustScore(
        aggregate=aggregate,
        provider_score=provider,
        registry_score=registry,
        signature_score=signature,
        license_score=license_s,
        training_data_score=training,
        maturity_score=maturity,
    )
