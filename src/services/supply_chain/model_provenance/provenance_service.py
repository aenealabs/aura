"""Model Provenance Service — top-level orchestrator (ADR-088 Phase 2.1).

Sequences the per-stage checks the ADR mandates and produces a single
:class:`ModelProvenanceRecord` per candidate. The pipeline is a pure
function of its inputs (artifact + injected dependencies); side
effects are limited to the quarantine store, which is itself a
deterministic in-process structure in v1.

Pipeline order:
    1. Sticky-quarantine check     — short-circuit if already quarantined.
    2. Allowlisted registry check  — REJECT (not quarantine) on miss.
       A registry-not-allowlisted result is a configuration mismatch,
       not a misbehaving model; quarantining it would suggest the
       model can be released later by an operator action, but the
       fix is a registry config change.
    3. License acceptability       — denylisted licenses → REJECT.
    4. Signature verification      — feeds trust score; not a hard
                                     gate by itself (Bedrock returns
                                     UNSIGNED for legitimate reasons).
    5. Trust-score computation     — see ``trust_scorer``.
    6. Verdict synthesis           — APPROVED / QUARANTINED based on
                                     trust threshold + signature outcome.

Edge cases the ADR-088 issue calls out:
    * Mid-pipeline failure halts cleanly — the orchestrator is
      synchronous and returns the partial verdict; no orphaned
      sandbox is provisioned because sandbox provisioning happens
      downstream in the Step Functions pipeline (Phase 2.3) which
      consumes this verdict.
    * Quarantined model resubmission is blocked by the sticky check
      at the head of the pipeline.
    * Expired signing key produces SIGNING_KEY_EXPIRED via the
      verifier; the trust scorer drops the signature component to
      0.10 → trust score below auto-approve threshold → QUARANTINED.
    * Missing training-data metadata is graceful — neutral component
      score, no verdict change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from src.services.supply_chain.model_provenance.contracts import (
    ModelArtifact,
    ModelLicense,
    ModelProvenanceRecord,
    ProvenanceVerdict,
    SignatureStatus,
)
from src.services.supply_chain.model_provenance.quarantine_store import (
    InMemoryModelQuarantineStore,
    ModelQuarantineStore,
)
from src.services.supply_chain.model_provenance.registry_allowlist import (
    RegistryAllowlist,
    default_allowlist,
)
from src.services.supply_chain.model_provenance.signature_verifier import (
    SignatureVerifier,
)
from src.services.supply_chain.model_provenance.trust_scorer import (
    ModelTrustScore,
    compute_trust_score,
)

logger = logging.getLogger(__name__)


# Licenses that hard-reject regardless of trust signals. The list is
# intentionally short — restrictive licenses still produce a record
# (with `license_acceptable=False`) which an operator can then choose
# to override via a per-deployment config patch. Hard rejection is
# reserved for license stances that contradict Aura's commercial use.
_DENYLISTED_LICENSES: frozenset[str] = frozenset({
    "PROPRIETARY-NO-COMMERCIAL",
    "RESEARCH-ONLY",
})


@dataclass
class ProvenanceServiceConfig:
    """Tunable thresholds for the verdict synthesis stage.

    Frozen-by-convention; mutate only via construction. The defaults
    mirror the ADR's stated "approve-but-monitor" stance for v1.
    """

    auto_approve_threshold: float = 0.75
    quarantine_below: float = 0.50  # Below this → quarantine, not approve-with-warning
    require_signature: bool = False  # Bedrock returns UNSIGNED legitimately


class ModelProvenanceService:
    """Orchestrator over the four provenance stages."""

    def __init__(
        self,
        *,
        allowlist: RegistryAllowlist | None = None,
        signature_verifier: SignatureVerifier | None = None,
        quarantine_store: ModelQuarantineStore | None = None,
        config: ProvenanceServiceConfig | None = None,
    ) -> None:
        self._allowlist = allowlist or default_allowlist()
        self._verifier = signature_verifier or SignatureVerifier()
        self._quarantine = quarantine_store or InMemoryModelQuarantineStore()
        self._config = config or ProvenanceServiceConfig()

    @property
    def quarantine_store(self) -> ModelQuarantineStore:
        return self._quarantine

    def evaluate(
        self,
        artifact: ModelArtifact,
        *,
        release_date: datetime | None = None,
        now: datetime | None = None,
    ) -> ModelProvenanceRecord:
        """Run the full pipeline and return one provenance record."""
        # 1. Sticky-quarantine check — short-circuit
        if self._quarantine.is_quarantined(artifact.model_id):
            existing = self._quarantine.get(artifact.model_id)
            return ModelProvenanceRecord(
                artifact=artifact,
                verdict=ProvenanceVerdict.QUARANTINED,
                signature_status=SignatureStatus.UNSIGNED,
                registry_allowlisted=False,
                license_acceptable=False,
                training_data_present=artifact.training_data.is_present,
                trust_score=0.0,
                failure_reasons=("model is sticky-quarantined",),
                quarantine_id=existing.quarantine_id if existing else None,
            )

        # 2. Registry allowlist
        allowlist_decision = self._allowlist.check(artifact)
        if not allowlist_decision.allowed:
            # Hard REJECT — registry mismatch is a config change, not
            # something an operator should release later via the
            # quarantine workflow.
            return ModelProvenanceRecord(
                artifact=artifact,
                verdict=ProvenanceVerdict.REJECTED,
                signature_status=SignatureStatus.UNSIGNED,
                registry_allowlisted=False,
                license_acceptable=_license_acceptable(artifact.license),
                training_data_present=artifact.training_data.is_present,
                trust_score=0.0,
                failure_reasons=(
                    f"registry not allowlisted: {allowlist_decision.reason}",
                ),
            )

        # 3. License acceptability
        license_acceptable = _license_acceptable(artifact.license)
        license_reasons: tuple[str, ...] = ()
        if not license_acceptable:
            license_reasons = (
                f"license {artifact.license.spdx_id!r} on denylist",
            )

        # 4. Signature verification
        verification = self._verifier.verify(artifact, now=now)
        signature_status = verification.status
        if (
            self._config.require_signature
            and signature_status is not SignatureStatus.VERIFIED
        ):
            quarantine = self._quarantine.quarantine(
                artifact.model_id,
                f"signature required but status={signature_status.value}",
            )
            return ModelProvenanceRecord(
                artifact=artifact,
                verdict=ProvenanceVerdict.QUARANTINED,
                signature_status=signature_status,
                registry_allowlisted=True,
                license_acceptable=license_acceptable,
                training_data_present=artifact.training_data.is_present,
                trust_score=0.0,
                failure_reasons=license_reasons + (verification.detail,),
                quarantine_id=quarantine.quarantine_id,
            )
        if signature_status is SignatureStatus.SIGNATURE_INVALID:
            # Even with require_signature=False, an actively-bad
            # signature is a quarantine event — a tampered artifact
            # is qualitatively different from "no signature was
            # provided".
            quarantine = self._quarantine.quarantine(
                artifact.model_id, "signature actively invalid"
            )
            return ModelProvenanceRecord(
                artifact=artifact,
                verdict=ProvenanceVerdict.QUARANTINED,
                signature_status=signature_status,
                registry_allowlisted=True,
                license_acceptable=license_acceptable,
                training_data_present=artifact.training_data.is_present,
                trust_score=0.0,
                failure_reasons=license_reasons + (verification.detail,),
                quarantine_id=quarantine.quarantine_id,
            )

        # 5. Trust score
        trust = compute_trust_score(
            artifact,
            signature_status=signature_status,
            release_date=release_date,
            now=now,
        )

        # 6. Verdict synthesis
        if not license_acceptable:
            # Denylisted licenses are hard rejects, not quarantines —
            # an operator can change the denylist via PR but releasing
            # an individual model wouldn't help.
            return ModelProvenanceRecord(
                artifact=artifact,
                verdict=ProvenanceVerdict.REJECTED,
                signature_status=signature_status,
                registry_allowlisted=True,
                license_acceptable=False,
                training_data_present=artifact.training_data.is_present,
                trust_score=trust.aggregate,
                failure_reasons=license_reasons,
            )

        if trust.aggregate < self._config.quarantine_below:
            quarantine = self._quarantine.quarantine(
                artifact.model_id,
                f"trust score {trust.aggregate:.3f} below quarantine threshold "
                f"{self._config.quarantine_below}",
            )
            return ModelProvenanceRecord(
                artifact=artifact,
                verdict=ProvenanceVerdict.QUARANTINED,
                signature_status=signature_status,
                registry_allowlisted=True,
                license_acceptable=True,
                training_data_present=artifact.training_data.is_present,
                trust_score=trust.aggregate,
                failure_reasons=("trust score below quarantine threshold",),
                quarantine_id=quarantine.quarantine_id,
            )

        return ModelProvenanceRecord(
            artifact=artifact,
            verdict=ProvenanceVerdict.APPROVED,
            signature_status=signature_status,
            registry_allowlisted=True,
            license_acceptable=True,
            training_data_present=artifact.training_data.is_present,
            trust_score=trust.aggregate,
            failure_reasons=(),
        )


def _license_acceptable(license_: ModelLicense) -> bool:
    return license_.spdx_id not in _DENYLISTED_LICENSES
