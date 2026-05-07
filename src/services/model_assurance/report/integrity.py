"""Tamper-evident sealing for ADR-088 reports + integrity envelopes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from src.services.model_assurance.report.contracts import (
    EvaluationIntegrityEnvelope,
    IntegrityEnvelope,
    ShadowDeploymentReport,
)


def _canonical_json(payload) -> str:
    """Stable JSON encoding: sorted keys, no whitespace deviation, UTF-8."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seal_report(report: ShadowDeploymentReport) -> IntegrityEnvelope:
    """Wrap a report in an IntegrityEnvelope with a content hash."""
    payload = report.to_serialisable_dict()
    payload_json = _canonical_json(payload)
    return IntegrityEnvelope(
        payload_json=payload_json,
        content_hash=_sha256_hex(payload_json),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@dataclass(frozen=True)
class IntegrityVerification:
    """Result of verifying an envelope's content hash."""

    is_valid: bool
    expected_hash: str
    actual_hash: str
    detail: str = ""

    @property
    def is_tampered(self) -> bool:
        return not self.is_valid


def verify_envelope(envelope: IntegrityEnvelope) -> IntegrityVerification:
    """Recompute the hash and compare to the envelope's stored value."""
    actual = _sha256_hex(envelope.payload_json)
    if actual == envelope.content_hash:
        return IntegrityVerification(
            is_valid=True,
            expected_hash=envelope.content_hash,
            actual_hash=actual,
        )
    return IntegrityVerification(
        is_valid=False,
        expected_hash=envelope.content_hash,
        actual_hash=actual,
        detail="hash mismatch — payload tampered after sealing",
    )


def seal_integrity_envelope(
    *,
    benchmark_version: str,
    axis_floors: Mapping[str, float],
    axis_weights: Mapping[str, float],
) -> EvaluationIntegrityEnvelope:
    """Seal the per-run scoring criteria.

    Sorted-tuple representation gives a deterministic hash regardless
    of insertion order. Same scoring criteria = same hash.
    """
    floors = tuple(sorted(axis_floors.items()))
    weights = tuple(sorted(axis_weights.items()))
    payload = {
        "benchmark_version": benchmark_version,
        "axis_floors": list(floors),
        "axis_weights": list(weights),
    }
    payload_json = _canonical_json(payload)
    return EvaluationIntegrityEnvelope(
        benchmark_version=benchmark_version,
        axis_floors=floors,
        axis_weights=weights,
        sealed_hash=_sha256_hex(payload_json),
        sealed_at=datetime.now(timezone.utc).isoformat(),
    )


def verify_integrity_envelope(
    envelope: EvaluationIntegrityEnvelope,
    *,
    current_floors: Mapping[str, float],
    current_weights: Mapping[str, float],
) -> IntegrityVerification:
    """Re-seal current state and compare against the stored hash.

    The "current" inputs are the live values the evaluator is
    using right now. If anything (floor threshold, weight, benchmark
    version) has been mutated since the seal, the hashes differ.
    """
    candidate = seal_integrity_envelope(
        benchmark_version=envelope.benchmark_version,
        axis_floors=current_floors,
        axis_weights=current_weights,
    )
    if candidate.sealed_hash == envelope.sealed_hash:
        return IntegrityVerification(
            is_valid=True,
            expected_hash=envelope.sealed_hash,
            actual_hash=candidate.sealed_hash,
        )
    return IntegrityVerification(
        is_valid=False,
        expected_hash=envelope.sealed_hash,
        actual_hash=candidate.sealed_hash,
        detail="scoring criteria mutated since envelope was sealed",
    )
