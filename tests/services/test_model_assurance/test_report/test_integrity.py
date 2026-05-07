"""Tests for integrity envelope sealing + verification (ADR-088 Phase 2.5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.model_assurance.axes import ModelAssuranceAxis
from src.services.model_assurance.report import (
    IntegrityEnvelope,
    IntegrityVerification,
    ShadowDeploymentReport,
    seal_integrity_envelope,
    seal_report,
    verify_envelope,
    verify_integrity_envelope,
)


def _report() -> ShadowDeploymentReport:
    return ShadowDeploymentReport(
        candidate_id="m-cand",
        candidate_display_name="Candidate Model",
        incumbent_id="m-incumbent",
        pipeline_decision="hitl_queued",
        overall_utility=0.95,
        incumbent_utility=0.90,
        axis_scores=(
            (ModelAssuranceAxis.PATCH_FUNCTIONAL_CORRECTNESS, 0.95),
        ),
    )


# ----------------------------------------------------- Report sealing


class TestReportSealing:
    def test_seal_returns_envelope_with_hash(self) -> None:
        envelope = seal_report(_report())
        assert envelope.content_hash
        assert len(envelope.content_hash) == 64  # SHA-256 hex
        assert envelope.payload_json

    def test_verify_clean_envelope(self) -> None:
        envelope = seal_report(_report())
        result = verify_envelope(envelope)
        assert result.is_valid is True
        assert result.is_tampered is False

    def test_tampered_payload_detected(self) -> None:
        envelope = seal_report(_report())
        # Mutate the payload while leaving the hash unchanged.
        tampered = IntegrityEnvelope(
            payload_json=envelope.payload_json.replace("0.95", "0.99"),
            content_hash=envelope.content_hash,
            created_at=envelope.created_at,
        )
        result = verify_envelope(tampered)
        assert result.is_tampered is True
        assert "tampered" in (result.detail or "")

    def test_seal_is_deterministic_for_same_report(self) -> None:
        # Same report content + same generated_at = same hash.
        same_time = datetime(2026, 5, 6, tzinfo=timezone.utc)
        r1 = ShadowDeploymentReport(
            candidate_id="m", candidate_display_name="M",
            incumbent_id=None,
            pipeline_decision="hitl_queued",
            overall_utility=0.5, incumbent_utility=None,
            generated_at=same_time,
        )
        r2 = ShadowDeploymentReport(
            candidate_id="m", candidate_display_name="M",
            incumbent_id=None,
            pipeline_decision="hitl_queued",
            overall_utility=0.5, incumbent_utility=None,
            generated_at=same_time,
        )
        assert seal_report(r1).content_hash == seal_report(r2).content_hash


# ----------------------------------------------- IntegrityEnvelope contract


class TestEnvelopeContract:
    def test_envelope_is_frozen(self) -> None:
        envelope = seal_report(_report())
        with pytest.raises((AttributeError, TypeError)):
            envelope.content_hash = "fake"  # type: ignore[misc]

    def test_envelope_version_default(self) -> None:
        envelope = seal_report(_report())
        assert envelope.envelope_version == "1.0"


# ---------------------------------- EvaluationIntegrityEnvelope


class TestEvaluationIntegrityEnvelope:
    def test_seal_and_verify_clean(self) -> None:
        env = seal_integrity_envelope(
            benchmark_version="2026.05.0",
            axis_floors={"MA1": 0.85, "MA2": 0.92},
            axis_weights={"MA1": 1.0, "MA2": 1.5},
        )
        result = verify_integrity_envelope(
            env,
            current_floors={"MA1": 0.85, "MA2": 0.92},
            current_weights={"MA1": 1.0, "MA2": 1.5},
        )
        assert result.is_valid is True

    def test_floor_mutation_detected(self) -> None:
        env = seal_integrity_envelope(
            benchmark_version="2026.05.0",
            axis_floors={"MA1": 0.85, "MA2": 0.92},
            axis_weights={"MA1": 1.0, "MA2": 1.5},
        )
        result = verify_integrity_envelope(
            env,
            current_floors={"MA1": 0.50, "MA2": 0.92},  # MA1 floor reduced
            current_weights={"MA1": 1.0, "MA2": 1.5},
        )
        assert result.is_tampered is True
        assert "mutated" in (result.detail or "")

    def test_weight_mutation_detected(self) -> None:
        env = seal_integrity_envelope(
            benchmark_version="2026.05.0",
            axis_floors={"MA1": 0.85},
            axis_weights={"MA1": 1.0},
        )
        result = verify_integrity_envelope(
            env,
            current_floors={"MA1": 0.85},
            current_weights={"MA1": 100.0},  # weight inflated
        )
        assert result.is_tampered is True

    def test_seal_is_order_independent(self) -> None:
        """Insertion order doesn't change the seal."""
        a = seal_integrity_envelope(
            benchmark_version="v1",
            axis_floors={"MA1": 0.5, "MA2": 0.6},
            axis_weights={"MA1": 1.0, "MA2": 2.0},
        )
        b = seal_integrity_envelope(
            benchmark_version="v1",
            axis_floors={"MA2": 0.6, "MA1": 0.5},
            axis_weights={"MA2": 2.0, "MA1": 1.0},
        )
        assert a.sealed_hash == b.sealed_hash

    def test_seal_distinguishes_benchmark_versions(self) -> None:
        a = seal_integrity_envelope(
            benchmark_version="v1",
            axis_floors={"MA1": 0.5},
            axis_weights={"MA1": 1.0},
        )
        b = seal_integrity_envelope(
            benchmark_version="v2",
            axis_floors={"MA1": 0.5},
            axis_weights={"MA1": 1.0},
        )
        assert a.sealed_hash != b.sealed_hash

    def test_envelope_includes_sealed_at(self) -> None:
        env = seal_integrity_envelope(
            benchmark_version="v1",
            axis_floors={"MA1": 0.5},
            axis_weights={"MA1": 1.0},
        )
        # ISO8601 with timezone designator
        assert "T" in env.sealed_at
        assert "+" in env.sealed_at or "Z" in env.sealed_at
