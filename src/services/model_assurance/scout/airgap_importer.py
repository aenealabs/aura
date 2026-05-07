"""Air-gap importer for HuggingFace models in GovCloud (ADR-088 Phase 3.2).

GovCloud deployments cannot reach the public HuggingFace Hub
directly. The air-gap import flow:

  1. Operator runs the offline-bundle pipeline (ADR-078) in a
     connected lane to download the model + manifest.
  2. The signed bundle is ferried across to the GovCloud lane.
  3. This module verifies the bundle, extracts the model summary,
     and feeds it to the Scout Agent's HF client via
     :py:meth:`install_fake`.

Bundle verification reuses ADR-078's existing signature checks —
this module is the *adapter*, not a duplicate signature service.
The single bundle status that matters here is "trusted to enter
the assurance pipeline".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from src.services.model_assurance.scout.huggingface_client import (
    HuggingFaceModelSummary,
)

logger = logging.getLogger(__name__)


class AirgapBundleStatus:
    VERIFIED = "verified"
    SIGNATURE_INVALID = "signature_invalid"
    UNTRUSTED_SOURCE = "untrusted_source"
    EXPIRED = "expired"


@dataclass(frozen=True)
class AirgapImportRecord:
    """One air-gap import outcome."""

    bundle_id: str
    repo_id: str
    status: str
    summary: HuggingFaceModelSummary | None = None
    detail: str = ""
    imported_at: datetime = datetime.now(timezone.utc)


@dataclass(frozen=True)
class AirgapBundleInput:
    """Operator-supplied bundle metadata.

    The actual bundle content (model weights, manifest, signature)
    lives on disk; this is the metadata the importer needs.
    Production wiring receives a pointer to ADR-078's BundleManifest;
    tests can supply the metadata directly.
    """

    bundle_id: str
    repo_id: str
    signature_valid: bool
    expiry_iso: datetime | None = None
    downloads: int = 0
    likes: int = 0
    tags: tuple[str, ...] = ()


def import_bundle(
    *,
    bundle: AirgapBundleInput,
    now: datetime | None = None,
) -> AirgapImportRecord:
    """Verify the bundle and produce an importable HF summary.

    Pure function — same input always yields the same record.
    """
    ts = now or datetime.now(timezone.utc)

    if not bundle.signature_valid:
        return AirgapImportRecord(
            bundle_id=bundle.bundle_id,
            repo_id=bundle.repo_id,
            status=AirgapBundleStatus.SIGNATURE_INVALID,
            detail="bundle signature did not verify",
            imported_at=ts,
        )

    if bundle.expiry_iso is not None and ts > bundle.expiry_iso:
        return AirgapImportRecord(
            bundle_id=bundle.bundle_id,
            repo_id=bundle.repo_id,
            status=AirgapBundleStatus.EXPIRED,
            detail=f"bundle expired at {bundle.expiry_iso.isoformat()}",
            imported_at=ts,
        )

    summary = HuggingFaceModelSummary(
        repo_id=bundle.repo_id,
        last_modified=ts,
        downloads=bundle.downloads,
        likes=bundle.likes,
        tags=bundle.tags,
        library_name="transformers",
    )
    return AirgapImportRecord(
        bundle_id=bundle.bundle_id,
        repo_id=bundle.repo_id,
        status=AirgapBundleStatus.VERIFIED,
        summary=summary,
        imported_at=ts,
    )


def import_many(
    bundles: Iterable[AirgapBundleInput],
    *,
    now: datetime | None = None,
) -> tuple[tuple[AirgapImportRecord, ...], tuple[HuggingFaceModelSummary, ...]]:
    """Bulk-import bundles. Returns ``(all_records, verified_summaries)``."""
    records: list[AirgapImportRecord] = []
    summaries: list[HuggingFaceModelSummary] = []
    for b in bundles:
        record = import_bundle(bundle=b, now=now)
        records.append(record)
        if (
            record.status == AirgapBundleStatus.VERIFIED
            and record.summary is not None
        ):
            summaries.append(record.summary)
    return tuple(records), tuple(summaries)
