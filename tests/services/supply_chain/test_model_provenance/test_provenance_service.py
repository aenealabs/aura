"""End-to-end tests for the Model Provenance Service (ADR-088 Phase 2.1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.supply_chain.model_provenance import (
    InMemoryModelQuarantineStore,
    ModelArtifact,
    ModelLicense,
    ModelProvenanceService,
    ModelRegistry,
    ModelTrainingDataLineage,
    ProvenanceServiceConfig,
    ProvenanceVerdict,
    SignatureStatus,
)


def _digest(c: str = "a") -> str:
    return c * 64


def _now() -> datetime:
    return datetime(2026, 5, 6, tzinfo=timezone.utc)


def _artifact(
    *,
    model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0",
    provider: str = "anthropic",
    registry: ModelRegistry = ModelRegistry.BEDROCK,
    license_: ModelLicense | None = None,
    lineage: ModelTrainingDataLineage | None = None,
    signature_b64: str | None = None,
    signing_key_id: str | None = None,
    digest: str | None = None,
) -> ModelArtifact:
    return ModelArtifact(
        model_id=model_id,
        provider=provider,
        registry=registry,
        weights_digest=digest or _digest(),
        license=license_ or ModelLicense(
            spdx_id="Apache-2.0", is_permissive=True, commercial_use_allowed=True,
        ),
        training_data=lineage or ModelTrainingDataLineage(),
        signature_b64=signature_b64,
        signing_key_id=signing_key_id,
    )


# ----------------------------------------------------- Approval path


class TestApproval:
    def test_strong_bedrock_candidate_approved(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.verdict is ProvenanceVerdict.APPROVED
        assert record.failure_reasons == ()
        assert record.trust_score > 0.75
        assert record.signature_status is SignatureStatus.UNSIGNED  # default

    def test_audit_dict_complete(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        d = record.to_audit_dict()
        assert d["verdict"] == "approved"
        assert "trust_score" in d


# ----------------------------------------------------- Sticky quarantine


class TestStickyQuarantine:
    def test_quarantined_model_short_circuits(self) -> None:
        store = InMemoryModelQuarantineStore()
        store.quarantine("bad-model", "preexisting")
        svc = ModelProvenanceService(quarantine_store=store)
        record = svc.evaluate(
            _artifact(model_id="bad-model"),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.verdict is ProvenanceVerdict.QUARANTINED
        assert "sticky" in record.failure_reasons[0]
        assert record.quarantine_id is not None

    def test_quarantined_quarantine_id_stable(self) -> None:
        store = InMemoryModelQuarantineStore()
        first = store.quarantine("m", "first")
        second = store.quarantine("m", "second")
        # idempotent
        assert first.quarantine_id == second.quarantine_id

    def test_lifted_quarantine_re_evaluates(self) -> None:
        store = InMemoryModelQuarantineStore()
        store.quarantine("m", "blah")
        store.lift("m")
        svc = ModelProvenanceService(quarantine_store=store)
        record = svc.evaluate(
            _artifact(model_id="m"),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.verdict is ProvenanceVerdict.APPROVED


# ----------------------------------------------------- Registry rejection


class TestRegistryRejection:
    def test_unallowlisted_bedrock_provider_rejected(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(provider="random-vendor"),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.verdict is ProvenanceVerdict.REJECTED
        assert record.registry_allowlisted is False
        assert "allowlisted" in record.failure_reasons[0]
        # Hard reject — no quarantine entry
        assert record.quarantine_id is None

    def test_ecr_with_wrong_pattern_rejected(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(
                model_id="random-models/foo",
                provider="aura",
                registry=ModelRegistry.INTERNAL_ECR,
            ),
        )
        assert record.verdict is ProvenanceVerdict.REJECTED


# ----------------------------------------------------- License denylist


class TestLicenseDenylist:
    def test_denylisted_license_rejected(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(
                license_=ModelLicense(
                    spdx_id="RESEARCH-ONLY",
                    is_permissive=False,
                    commercial_use_allowed=False,
                ),
            ),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.verdict is ProvenanceVerdict.REJECTED
        assert record.license_acceptable is False
        assert record.quarantine_id is None  # hard reject

    def test_unknown_license_does_not_reject(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(
                license_=ModelLicense(spdx_id="NOASSERTION"),
            ),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        # Verdict is not REJECTED solely due to unknown license
        assert record.verdict in (
            ProvenanceVerdict.APPROVED, ProvenanceVerdict.QUARANTINED
        )


# --------------------------------------------- Signature handling


class TestSignaturePath:
    def test_unknown_key_does_not_quarantine_when_signature_optional(self) -> None:
        """An unrecognised key id with require_signature=False is not fatal.

        The verifier reports SIGNING_KEY_UNKNOWN (not VERIFICATION_ERROR
        — the malformed signature is short-circuited by the missing
        key id check). Trust-score path continues so we still get a
        verdict — APPROVED / QUARANTINED depending on threshold.
        """
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(
                signature_b64="not-base64!!",
                signing_key_id="any",
            ),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.signature_status is SignatureStatus.SIGNING_KEY_UNKNOWN
        # Not a hard fail — verdict comes from trust threshold.
        assert record.verdict in (
            ProvenanceVerdict.APPROVED,
            ProvenanceVerdict.QUARANTINED,
        )

    def test_require_signature_quarantines_unsigned(self) -> None:
        svc = ModelProvenanceService(
            config=ProvenanceServiceConfig(require_signature=True),
        )
        record = svc.evaluate(
            _artifact(),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.verdict is ProvenanceVerdict.QUARANTINED
        assert record.quarantine_id is not None

    def test_unsigned_default_does_not_quarantine(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.verdict is ProvenanceVerdict.APPROVED


# --------------------------------------------- Trust threshold path


class TestTrustThreshold:
    def test_low_trust_score_quarantines(self) -> None:
        svc = ModelProvenanceService(
            config=ProvenanceServiceConfig(quarantine_below=0.95),
        )
        record = svc.evaluate(
            _artifact(),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        # 0.80 trust score with permissive license + unsigned;
        # well below 0.95 quarantine threshold.
        assert record.verdict is ProvenanceVerdict.QUARANTINED


# --------------------------------------------- Training data graceful


class TestTrainingDataGraceful:
    def test_missing_lineage_does_not_reject(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(lineage=ModelTrainingDataLineage()),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.training_data_present is False
        assert record.verdict is ProvenanceVerdict.APPROVED

    def test_present_lineage_reports_present(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(
                lineage=ModelTrainingDataLineage(sources=("RedPajama",)),
            ),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.training_data_present is True


# --------------------------------------------- ECR + HF positive cases


class TestNonBedrockApprovals:
    def test_internal_ecr_pattern_approved(self) -> None:
        svc = ModelProvenanceService()
        record = svc.evaluate(
            _artifact(
                model_id="aura-models/swe-rl-v3",
                provider="aura",
                registry=ModelRegistry.INTERNAL_ECR,
            ),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        # Provider "aura" is at tier 0.80 — license permissive, registry mid-tier;
        # trust ~0.7-0.8 → quarantine_below default is 0.50, so APPROVED.
        assert record.verdict is ProvenanceVerdict.APPROVED

    def test_huggingface_curated_with_entry(self) -> None:
        from src.services.supply_chain.model_provenance import default_allowlist

        allowlist = default_allowlist().with_huggingface_entry(
            "meta-llama/CodeLlama-34b-Instruct"
        )
        svc = ModelProvenanceService(allowlist=allowlist)
        record = svc.evaluate(
            _artifact(
                model_id="meta-llama/CodeLlama-34b-Instruct",
                provider="meta",
                registry=ModelRegistry.HUGGINGFACE_CURATED,
            ),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert record.verdict is ProvenanceVerdict.APPROVED


# --------------------------------------------- Determinism


class TestDeterminism:
    def test_same_inputs_same_record(self) -> None:
        # Quarantine state mutates between runs of mode-quarantine paths,
        # so we use the approval path which has no side effects.
        svc1 = ModelProvenanceService()
        svc2 = ModelProvenanceService()
        a = svc1.evaluate(
            _artifact(),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        b = svc2.evaluate(
            _artifact(),
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        # evaluated_at differs by clock; compare verdict/score only.
        assert a.verdict == b.verdict
        assert a.trust_score == b.trust_score


# --------------------------------------------- Edge case from issue


class TestEdgeCases:
    def test_mid_pipeline_registry_failure_no_quarantine_orphan(self) -> None:
        """Registry rejection must not write to the quarantine store."""
        store = InMemoryModelQuarantineStore()
        svc = ModelProvenanceService(quarantine_store=store)
        svc.evaluate(_artifact(provider="rogue"))
        assert store.is_quarantined("anthropic.claude-3-5-sonnet-20240620-v1:0") is False
