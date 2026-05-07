"""Model Provenance Service — ADR-088 Phase 2.1."""

from __future__ import annotations

from .contracts import (
    ModelArtifact,
    ModelLicense,
    ModelProvenanceRecord,
    ModelRegistry,
    ModelTrainingDataLineage,
    ProvenanceVerdict,
    ProviderSigningKey,
    SignatureStatus,
)
from .provenance_service import (
    ModelProvenanceService,
    ProvenanceServiceConfig,
)
from .quarantine_store import (
    InMemoryModelQuarantineStore,
    ModelQuarantineStore,
    QuarantineEntry,
)
from .registry_allowlist import (
    AllowlistDecision,
    AllowlistEntry,
    DEFAULT_BEDROCK_PROVIDERS,
    DEFAULT_HUGGINGFACE_ALLOWLIST,
    DEFAULT_INTERNAL_ECR_PATTERN,
    RegistryAllowlist,
    default_allowlist,
)
from .signature_verifier import (
    SignatureVerifier,
    VerificationOutcome,
)
from .trust_scorer import (
    ModelTrustScore,
    compute_trust_score,
)

__all__ = [
    "ModelArtifact",
    "ModelLicense",
    "ModelProvenanceRecord",
    "ModelRegistry",
    "ModelTrainingDataLineage",
    "ProvenanceVerdict",
    "ProviderSigningKey",
    "SignatureStatus",
    "AllowlistDecision",
    "AllowlistEntry",
    "RegistryAllowlist",
    "default_allowlist",
    "DEFAULT_BEDROCK_PROVIDERS",
    "DEFAULT_HUGGINGFACE_ALLOWLIST",
    "DEFAULT_INTERNAL_ECR_PATTERN",
    "SignatureVerifier",
    "VerificationOutcome",
    "ModelTrustScore",
    "compute_trust_score",
    "ModelQuarantineStore",
    "InMemoryModelQuarantineStore",
    "QuarantineEntry",
    "ModelProvenanceService",
    "ProvenanceServiceConfig",
]
