"""Tests for model trust scoring (ADR-088 Phase 2.1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.supply_chain.model_provenance import (
    ModelArtifact,
    ModelLicense,
    ModelRegistry,
    ModelTrainingDataLineage,
    SignatureStatus,
    compute_trust_score,
)


def _digest() -> str:
    return "a" * 64


def _artifact(
    *,
    provider: str = "anthropic",
    registry: ModelRegistry = ModelRegistry.BEDROCK,
    license_: ModelLicense | None = None,
    lineage: ModelTrainingDataLineage | None = None,
) -> ModelArtifact:
    return ModelArtifact(
        model_id="m",
        provider=provider,
        registry=registry,
        weights_digest=_digest(),
        license=license_ or ModelLicense(
            spdx_id="Apache-2.0", is_permissive=True, commercial_use_allowed=True,
        ),
        training_data=lineage or ModelTrainingDataLineage(),
    )


def _now() -> datetime:
    return datetime(2026, 5, 6, tzinfo=timezone.utc)


# ----------------------------------------------------- Score range


class TestScoreRange:
    def test_aggregate_within_unit_interval(self) -> None:
        score = compute_trust_score(
            _artifact(),
            signature_status=SignatureStatus.VERIFIED,
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert 0.0 <= score.aggregate <= 1.0

    def test_strong_candidate_scores_high(self) -> None:
        # With full lineage attestation present, a verified mature
        # Bedrock model should reach the maximum aggregate.
        score = compute_trust_score(
            _artifact(
                lineage=ModelTrainingDataLineage(
                    sources=("CommonCrawl-2024",),
                    cutoff_date=_now() - timedelta(days=200),
                    pii_filtered=True,
                ),
            ),
            signature_status=SignatureStatus.VERIFIED,
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert score.aggregate >= 0.95

    def test_invalid_signature_zeroes_signature_component(self) -> None:
        score = compute_trust_score(
            _artifact(),
            signature_status=SignatureStatus.SIGNATURE_INVALID,
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        assert score.signature_score == 0.0


# ----------------------------------------------- Provider tier


class TestProviderTier:
    def test_known_provider_top_tier(self) -> None:
        score = compute_trust_score(
            _artifact(provider="anthropic"),
            signature_status=SignatureStatus.UNSIGNED,
            now=_now(),
        )
        assert score.provider_score == 1.00

    def test_unknown_provider_default_floor(self) -> None:
        score = compute_trust_score(
            _artifact(provider="some-rando-startup"),
            signature_status=SignatureStatus.UNSIGNED,
            now=_now(),
        )
        assert score.provider_score == 0.50

    def test_provider_lookup_is_case_insensitive(self) -> None:
        a = compute_trust_score(
            _artifact(provider="ANTHROPIC"),
            signature_status=SignatureStatus.UNSIGNED,
            now=_now(),
        )
        assert a.provider_score == 1.00


# ----------------------------------------------- Registry tier


class TestRegistryTier:
    def test_bedrock_top_tier(self) -> None:
        s = compute_trust_score(
            _artifact(registry=ModelRegistry.BEDROCK),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.registry_score == 1.00

    def test_internal_ecr_mid_tier(self) -> None:
        s = compute_trust_score(
            _artifact(registry=ModelRegistry.INTERNAL_ECR),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.registry_score == 0.85

    def test_hf_curated_lowest_allowed_tier(self) -> None:
        s = compute_trust_score(
            _artifact(registry=ModelRegistry.HUGGINGFACE_CURATED),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.registry_score == 0.70


# ----------------------------------------------- License component


class TestLicenseComponent:
    def test_permissive_commercial_full_score(self) -> None:
        s = compute_trust_score(
            _artifact(
                license_=ModelLicense(
                    spdx_id="Apache-2.0",
                    is_permissive=True,
                    commercial_use_allowed=True,
                ),
            ),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.license_score == 1.0

    def test_unknown_license_neutral(self) -> None:
        s = compute_trust_score(
            _artifact(license_=ModelLicense()),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.license_score == 0.5

    def test_restrictive_license_low(self) -> None:
        s = compute_trust_score(
            _artifact(
                license_=ModelLicense(
                    spdx_id="LICENSE-PROPRIETARY",
                    is_permissive=False,
                    commercial_use_allowed=False,
                ),
            ),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.license_score == 0.3


# ----------------------------------------------- Training data signal


class TestTrainingDataComponent:
    def test_missing_neutral(self) -> None:
        s = compute_trust_score(
            _artifact(),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.training_data_score == 0.5

    def test_present_basic(self) -> None:
        s = compute_trust_score(
            _artifact(
                lineage=ModelTrainingDataLineage(sources=("CommonCrawl-2024",)),
            ),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.training_data_score == 0.7

    def test_with_pii_filter_top_score(self) -> None:
        s = compute_trust_score(
            _artifact(
                lineage=ModelTrainingDataLineage(
                    sources=("CommonCrawl-2024",),
                    cutoff_date=_now() - timedelta(days=30),
                    pii_filtered=True,
                ),
            ),
            signature_status=SignatureStatus.VERIFIED,
            now=_now(),
        )
        assert s.training_data_score == 1.0


# ----------------------------------------------- Maturity curve


class TestMaturityCurve:
    @pytest.mark.parametrize(
        "age_days,floor,ceiling",
        [
            (0, 0.39, 0.41),
            (30, 0.69, 0.71),
            (90, 0.89, 0.91),
            (180, 0.999, 1.001),
            (365, 0.999, 1.001),
        ],
    )
    def test_maturity_curve_endpoints(
        self, age_days: int, floor: float, ceiling: float
    ) -> None:
        s = compute_trust_score(
            _artifact(),
            signature_status=SignatureStatus.UNSIGNED,
            release_date=_now() - timedelta(days=age_days),
            now=_now(),
        )
        assert floor <= s.maturity_score <= ceiling

    def test_no_release_date_uses_floor(self) -> None:
        s = compute_trust_score(
            _artifact(),
            signature_status=SignatureStatus.UNSIGNED,
            release_date=None,
            now=_now(),
        )
        assert s.maturity_score == 0.4

    def test_negative_age_treated_as_new(self) -> None:
        # Clock-skew defence
        s = compute_trust_score(
            _artifact(),
            signature_status=SignatureStatus.UNSIGNED,
            release_date=_now() + timedelta(days=10),
            now=_now(),
        )
        assert s.maturity_score == 0.4


# ----------------------------------------------- Determinism


class TestDeterminism:
    def test_same_inputs_same_score(self) -> None:
        kwargs = dict(
            artifact=_artifact(),
            signature_status=SignatureStatus.VERIFIED,
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        a = compute_trust_score(**kwargs)
        b = compute_trust_score(**kwargs)
        c = compute_trust_score(**kwargs)
        assert a == b == c

    def test_audit_dict_round_trip(self) -> None:
        s = compute_trust_score(
            _artifact(),
            signature_status=SignatureStatus.VERIFIED,
            release_date=_now() - timedelta(days=180),
            now=_now(),
        )
        d = s.to_audit_dict()
        for k in (
            "aggregate", "provider_score", "registry_score",
            "signature_score", "license_score",
            "training_data_score", "maturity_score",
        ):
            assert k in d
