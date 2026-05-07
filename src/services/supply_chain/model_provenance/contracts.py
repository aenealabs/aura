"""Model Provenance Service contracts (ADR-088 Phase 2.1).

Frozen value types describing model artifacts, their provenance, and
the deterministic verdicts produced by the provenance pipeline. The
verdict is what the ADR-088 Step Functions state machine inspects to
decide whether a candidate flows to the sandbox or is quarantined.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ModelRegistry(Enum):
    """Where a model artifact comes from.

    Allowlisted registries are fixed at design time; new registries
    require an ADR + change-control. The enum intentionally excludes
    raw HTTP downloads — every model must come from a named registry.
    """

    BEDROCK = "bedrock"
    INTERNAL_ECR = "internal_ecr"
    HUGGINGFACE_CURATED = "huggingface_curated"


class SignatureStatus(Enum):
    """Outcome of cryptographic signature verification."""

    VERIFIED = "verified"
    UNSIGNED = "unsigned"
    SIGNATURE_INVALID = "signature_invalid"
    SIGNING_KEY_EXPIRED = "signing_key_expired"
    SIGNING_KEY_UNKNOWN = "signing_key_unknown"
    VERIFICATION_ERROR = "verification_error"


class ProvenanceVerdict(Enum):
    """Top-level verdict the provenance service emits per candidate.

    Pipeline behavior:
        APPROVED       — proceed to sandbox + oracle stages.
        QUARANTINED    — registered with QuarantineManager (ADR-067);
                         requires manual operator action to release.
        REJECTED       — hard fail (e.g. registry not allowlisted);
                         no quarantine because re-evaluation is not
                         appropriate without first changing the
                         allowlist.
    """

    APPROVED = "approved"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ModelLicense:
    """License metadata attached to a model artifact.

    A model with an unknown or restrictive license (e.g. research-only)
    is not auto-rejected — the license signal feeds the trust score
    and the operator-visible report. The exception is licenses on the
    explicit denylist (e.g. ``no-commercial-use``) which are rejected.
    """

    spdx_id: str = "NOASSERTION"   # SPDX identifier or "NOASSERTION"
    name: str = ""
    url: str = ""
    is_permissive: bool = False    # MIT/Apache/BSD-style
    commercial_use_allowed: bool = False


@dataclass(frozen=True)
class ModelTrainingDataLineage:
    """Optional training-data lineage attached to a model artifact.

    Most foundation-model providers don't publish training-set
    manifests. Missing fields degrade gracefully — the trust score
    drops slightly but the candidate isn't rejected. Hard rejection
    on missing data would mean Aura can never evaluate a closed-
    weights model from a major provider, which is not the intended
    behavior of v1.
    """

    sources: tuple[str, ...] = ()              # e.g. ("Common Crawl 2024-09", "RedPajama")
    cutoff_date: datetime | None = None        # training-data cutoff
    pii_filtered: bool | None = None           # provider attestation
    notes: str = ""

    @property
    def is_present(self) -> bool:
        return bool(self.sources) or self.cutoff_date is not None


@dataclass(frozen=True)
class ProviderSigningKey:
    """A model-provider signing key entry.

    Keys are stored in the allowlist module — production deployments
    fetch them from SSM/Secrets Manager. ``not_after`` enforces
    rotation: an expired key produces SIGNING_KEY_EXPIRED, never
    silent verification failure.
    """

    provider: str                  # "anthropic" / "amazon" / etc.
    key_id: str                    # vendor-published key ID
    public_key_pem: str
    not_before: datetime
    not_after: datetime
    revoked: bool = False

    def is_active_at(self, when: datetime) -> bool:
        return (
            not self.revoked
            and self.not_before <= when <= self.not_after
        )


@dataclass(frozen=True)
class ModelArtifact:
    """The thing being evaluated.

    Identifies a candidate model uniquely and carries the metadata
    the provenance pipeline needs. ``weights_digest`` is the SHA-256
    of the model weights blob (or the equivalent for closed-weights
    models — Bedrock returns a stable per-version digest in its
    metadata response).
    """

    model_id: str                                 # "anthropic.claude-3-5-..."
    provider: str                                 # "anthropic"
    registry: ModelRegistry
    weights_digest: str                           # SHA-256 hex
    license: ModelLicense = field(default_factory=ModelLicense)
    training_data: ModelTrainingDataLineage = field(
        default_factory=ModelTrainingDataLineage
    )
    signature_b64: str | None = None              # detached signature, base64
    signing_key_id: str | None = None             # which provider key signed it
    signed_at: datetime | None = None             # when the signature was issued

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("ModelArtifact.model_id is required")
        if not self.provider:
            raise ValueError("ModelArtifact.provider is required")
        if not self.weights_digest:
            raise ValueError("ModelArtifact.weights_digest is required")
        if len(self.weights_digest) != 64:
            raise ValueError(
                f"weights_digest must be a 64-char SHA-256 hex; "
                f"got len={len(self.weights_digest)}"
            )


@dataclass(frozen=True)
class ModelProvenanceRecord:
    """The output of one provenance evaluation.

    Frozen + hash-stable so it can be archived and signed alongside
    the Shadow Deployment Report (Phase 2.5). The ``trust_score``
    field is in [0,1] and feeds the model_assurance utility-score
    multiplier (ADR-088 §Stage 5).
    """

    artifact: ModelArtifact
    verdict: ProvenanceVerdict
    signature_status: SignatureStatus
    registry_allowlisted: bool
    license_acceptable: bool
    training_data_present: bool
    trust_score: float
    failure_reasons: tuple[str, ...] = ()
    quarantine_id: str | None = None
    evaluated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if not 0.0 <= self.trust_score <= 1.0:
            raise ValueError(
                f"trust_score must be in [0,1]; got {self.trust_score}"
            )

    def to_audit_dict(self) -> dict:
        return {
            "model_id": self.artifact.model_id,
            "provider": self.artifact.provider,
            "registry": self.artifact.registry.value,
            "weights_digest": self.artifact.weights_digest,
            "verdict": self.verdict.value,
            "signature_status": self.signature_status.value,
            "registry_allowlisted": self.registry_allowlisted,
            "license_acceptable": self.license_acceptable,
            "training_data_present": self.training_data_present,
            "trust_score": round(self.trust_score, 6),
            "failure_reasons": list(self.failure_reasons),
            "quarantine_id": self.quarantine_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "license": {
                "spdx_id": self.artifact.license.spdx_id,
                "commercial_use_allowed": (
                    self.artifact.license.commercial_use_allowed
                ),
            },
        }
