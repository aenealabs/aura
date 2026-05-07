"""Tests for the air-gap importer (ADR-088 Phase 3.2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services.model_assurance.scout import (
    AirgapBundleInput,
    AirgapBundleStatus,
    import_bundle,
    import_many,
)


def _bundle(
    *,
    bundle_id: str = "b1",
    repo_id: str = "meta-llama/CodeLlama-34b",
    signature_valid: bool = True,
    expiry_iso: datetime | None = None,
) -> AirgapBundleInput:
    return AirgapBundleInput(
        bundle_id=bundle_id,
        repo_id=repo_id,
        signature_valid=signature_valid,
        expiry_iso=expiry_iso,
        downloads=200_000,
        likes=1_500,
        tags=("code-generation",),
    )


class TestSingleBundleImport:
    def test_valid_bundle_verified(self) -> None:
        record = import_bundle(bundle=_bundle())
        assert record.status == AirgapBundleStatus.VERIFIED
        assert record.summary is not None
        assert record.summary.repo_id == "meta-llama/CodeLlama-34b"

    def test_invalid_signature_rejected(self) -> None:
        record = import_bundle(bundle=_bundle(signature_valid=False))
        assert record.status == AirgapBundleStatus.SIGNATURE_INVALID
        assert record.summary is None
        assert "signature" in record.detail

    def test_expired_bundle_rejected(self) -> None:
        record = import_bundle(
            bundle=_bundle(
                expiry_iso=datetime(2020, 1, 1, tzinfo=timezone.utc),
            ),
            now=datetime(2026, 5, 6, tzinfo=timezone.utc),
        )
        assert record.status == AirgapBundleStatus.EXPIRED
        assert record.summary is None
        assert "expired" in record.detail

    def test_future_expiry_passes(self) -> None:
        record = import_bundle(
            bundle=_bundle(
                expiry_iso=datetime(2030, 1, 1, tzinfo=timezone.utc),
            ),
            now=datetime(2026, 5, 6, tzinfo=timezone.utc),
        )
        assert record.status == AirgapBundleStatus.VERIFIED


class TestBatchImport:
    def test_mixed_batch_separates_verified(self) -> None:
        bundles = (
            _bundle(bundle_id="b1", repo_id="A"),
            _bundle(bundle_id="b2", repo_id="B", signature_valid=False),
            _bundle(bundle_id="b3", repo_id="C"),
        )
        records, summaries = import_many(bundles)
        # All bundles produce records
        assert len(records) == 3
        # Only verified summaries are returned
        assert len(summaries) == 2
        verified_ids = {s.repo_id for s in summaries}
        assert verified_ids == {"A", "C"}

    def test_empty_batch(self) -> None:
        records, summaries = import_many(())
        assert records == ()
        assert summaries == ()

    def test_all_invalid_yields_no_summaries(self) -> None:
        bundles = (
            _bundle(bundle_id="b1", signature_valid=False),
            _bundle(
                bundle_id="b2",
                expiry_iso=datetime(2020, 1, 1, tzinfo=timezone.utc),
            ),
        )
        records, summaries = import_many(
            bundles,
            now=datetime(2026, 5, 6, tzinfo=timezone.utc),
        )
        assert summaries == ()
        # Statuses correctly distinguish the failure modes
        statuses = [r.status for r in records]
        assert AirgapBundleStatus.SIGNATURE_INVALID in statuses
        assert AirgapBundleStatus.EXPIRED in statuses


class TestRecordImmutability:
    def test_record_is_frozen(self) -> None:
        record = import_bundle(bundle=_bundle())
        with pytest.raises((AttributeError, TypeError)):
            record.status = "tampered"  # type: ignore[misc]

    def test_summary_carries_metadata_from_bundle(self) -> None:
        record = import_bundle(bundle=_bundle())
        assert record.summary is not None
        assert record.summary.downloads == 200_000
        assert record.summary.likes == 1_500
        assert "code-generation" in record.summary.tags
