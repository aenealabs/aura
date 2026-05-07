"""Tests for model_provenance contracts (ADR-088 Phase 2.1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.supply_chain.model_provenance import (
    ModelArtifact,
    ModelLicense,
    ModelProvenanceRecord,
    ModelRegistry,
    ModelTrainingDataLineage,
    ProvenanceVerdict,
    ProviderSigningKey,
    SignatureStatus,
)


def _digest() -> str:
    return "a" * 64


# ----------------------------------------------------- ModelArtifact


class TestModelArtifactValidation:
    def test_basic_construction(self) -> None:
        a = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
        )
        assert a.model_id == "m"
        assert a.signature_b64 is None

    def test_empty_model_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="model_id"):
            ModelArtifact(
                model_id="",
                provider="x",
                registry=ModelRegistry.BEDROCK,
                weights_digest=_digest(),
            )

    def test_empty_provider_rejected(self) -> None:
        with pytest.raises(ValueError, match="provider"):
            ModelArtifact(
                model_id="m",
                provider="",
                registry=ModelRegistry.BEDROCK,
                weights_digest=_digest(),
            )

    def test_empty_digest_rejected(self) -> None:
        with pytest.raises(ValueError, match="weights_digest"):
            ModelArtifact(
                model_id="m",
                provider="x",
                registry=ModelRegistry.BEDROCK,
                weights_digest="",
            )

    def test_short_digest_rejected(self) -> None:
        with pytest.raises(ValueError, match="64-char"):
            ModelArtifact(
                model_id="m",
                provider="x",
                registry=ModelRegistry.BEDROCK,
                weights_digest="abc",
            )

    def test_artifact_is_frozen(self) -> None:
        a = ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
        )
        with pytest.raises((AttributeError, TypeError)):
            a.model_id = "x"  # type: ignore[misc]


# ----------------------------------------------------- License + lineage


class TestLicense:
    def test_default_unknown(self) -> None:
        lic = ModelLicense()
        assert lic.spdx_id == "NOASSERTION"
        assert lic.is_permissive is False
        assert lic.commercial_use_allowed is False

    def test_permissive_license(self) -> None:
        lic = ModelLicense(
            spdx_id="Apache-2.0",
            name="Apache 2.0",
            is_permissive=True,
            commercial_use_allowed=True,
        )
        assert lic.is_permissive
        assert lic.commercial_use_allowed


class TestTrainingLineage:
    def test_empty_is_not_present(self) -> None:
        lineage = ModelTrainingDataLineage()
        assert not lineage.is_present

    def test_sources_marks_present(self) -> None:
        lineage = ModelTrainingDataLineage(sources=("CommonCrawl",))
        assert lineage.is_present

    def test_cutoff_alone_marks_present(self) -> None:
        lineage = ModelTrainingDataLineage(
            cutoff_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        assert lineage.is_present


# ----------------------------------------------------- Signing key


class TestProviderSigningKey:
    def _make(
        self,
        not_before: datetime,
        not_after: datetime,
        revoked: bool = False,
    ) -> ProviderSigningKey:
        return ProviderSigningKey(
            provider="anthropic",
            key_id="k1",
            public_key_pem="-----BEGIN PUBLIC KEY-----\n-----END PUBLIC KEY-----\n",
            not_before=not_before,
            not_after=not_after,
            revoked=revoked,
        )

    def test_active_within_window(self) -> None:
        now = datetime.now(timezone.utc)
        k = self._make(now - timedelta(days=1), now + timedelta(days=30))
        assert k.is_active_at(now) is True

    def test_inactive_before_not_before(self) -> None:
        now = datetime.now(timezone.utc)
        k = self._make(now + timedelta(days=1), now + timedelta(days=30))
        assert k.is_active_at(now) is False

    def test_inactive_after_not_after(self) -> None:
        now = datetime.now(timezone.utc)
        k = self._make(now - timedelta(days=30), now - timedelta(days=1))
        assert k.is_active_at(now) is False

    def test_revoked_key_inactive(self) -> None:
        now = datetime.now(timezone.utc)
        k = self._make(
            now - timedelta(days=1), now + timedelta(days=30), revoked=True
        )
        assert k.is_active_at(now) is False


# ----------------------------------------------------- Record contract


class TestProvenanceRecord:
    def _artifact(self) -> ModelArtifact:
        return ModelArtifact(
            model_id="m",
            provider="anthropic",
            registry=ModelRegistry.BEDROCK,
            weights_digest=_digest(),
        )

    def test_trust_score_validation(self) -> None:
        with pytest.raises(ValueError, match=r"\[0,1\]"):
            ModelProvenanceRecord(
                artifact=self._artifact(),
                verdict=ProvenanceVerdict.APPROVED,
                signature_status=SignatureStatus.VERIFIED,
                registry_allowlisted=True,
                license_acceptable=True,
                training_data_present=False,
                trust_score=1.5,
            )
        with pytest.raises(ValueError):
            ModelProvenanceRecord(
                artifact=self._artifact(),
                verdict=ProvenanceVerdict.APPROVED,
                signature_status=SignatureStatus.VERIFIED,
                registry_allowlisted=True,
                license_acceptable=True,
                training_data_present=False,
                trust_score=-0.1,
            )

    def test_audit_dict_has_expected_keys(self) -> None:
        record = ModelProvenanceRecord(
            artifact=self._artifact(),
            verdict=ProvenanceVerdict.APPROVED,
            signature_status=SignatureStatus.VERIFIED,
            registry_allowlisted=True,
            license_acceptable=True,
            training_data_present=False,
            trust_score=0.9,
        )
        d = record.to_audit_dict()
        for k in (
            "model_id", "provider", "registry", "weights_digest",
            "verdict", "signature_status", "trust_score",
            "evaluated_at", "license",
        ):
            assert k in d
        assert d["verdict"] == "approved"
        assert d["signature_status"] == "verified"
