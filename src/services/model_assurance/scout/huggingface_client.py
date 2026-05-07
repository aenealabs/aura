"""HuggingFace Hub client for Scout Agent (ADR-088 Phase 3.2).

Polls the HuggingFace Hub for new model versions on a curated
allowlist. Per ADR-088 §Stage 1 condition #6 (Sally) and §GovCloud:

  * Open-ended HuggingFace download is forbidden — every repo
    must be explicitly allowlisted. The list lives in
    :mod:`registry_allowlist.huggingface_allowlist` and is PR-gated.
  * GovCloud deployments cannot poll the public HuggingFace API
    directly. They use the air-gap import path (Phase 3.2 sibling
    module ``airgap_importer``) where an operator pulls bundles in
    a connected lane and ferries them across.

The client soft-imports ``huggingface_hub`` so unit tests run
without network access. ``install_fake`` lets tests preload the
list of summaries the client will return.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from src.services.model_assurance.adapter_registry import (
    ModelArchitecture,
    ModelProvider,
    TokenizerType,
)
from src.services.model_assurance.scout.bedrock_client import (
    BedrockModelSummary,
    infer_architecture,
    infer_tokenizer,
)

logger = logging.getLogger(__name__)


try:  # pragma: no cover — exercised via mock-mode tests
    from huggingface_hub import HfApi  # type: ignore[import-untyped]

    HF_AVAILABLE = True
except ImportError:  # pragma: no cover
    HfApi = None  # type: ignore[misc,assignment]
    HF_AVAILABLE = False


@dataclass(frozen=True)
class HuggingFaceModelSummary:
    """Normalised view of one HuggingFace model entry."""

    repo_id: str
    last_modified: datetime
    downloads: int = 0
    likes: int = 0
    tags: tuple[str, ...] = ()
    library_name: str = ""

    @property
    def model_id(self) -> str:
        # Match the Bedrock client's "model_id" attribute name so the
        # Scout Agent can treat the two summaries uniformly.
        return self.repo_id


@dataclass(frozen=True)
class HuggingFaceListResponse:
    """Wrapper around the polled response."""

    models: tuple[HuggingFaceModelSummary, ...]
    error: str | None = None


class HuggingFaceListClient:
    """Polls the HuggingFace Hub against a curated allowlist.

    Production wiring: pass the curated allowlist (a tuple of
    repo IDs from the project's RegistryAllowlist) at construction.
    The client's ``list_models`` walks the allowlist, requests one
    summary per repo, and returns the materialised list.

    GovCloud deployments construct this with ``client=None`` and
    feed the airgap_importer's pre-staged summaries via
    :py:meth:`install_fake`.
    """

    def __init__(
        self,
        *,
        curated_repo_ids: Iterable[str],
        client=None,  # type: ignore[no-untyped-def]
    ) -> None:
        self._curated_repo_ids = tuple(curated_repo_ids)
        self._fake_models: tuple[HuggingFaceModelSummary, ...] | None = None

        if client is not None:
            self._client = client
            self._is_live = True
        elif HF_AVAILABLE:
            try:
                self._client = HfApi()
                self._is_live = True
            except Exception as exc:  # pragma: no cover — env-specific
                logger.info(
                    "HuggingFaceListClient init failed (%s); mock mode", exc,
                )
                self._client = None
                self._is_live = False
        else:
            self._client = None
            self._is_live = False

    @property
    def is_live(self) -> bool:
        return self._is_live

    @property
    def curated_repo_ids(self) -> tuple[str, ...]:
        return self._curated_repo_ids

    def install_fake(
        self, models: tuple[HuggingFaceModelSummary, ...]
    ) -> None:
        """Test/airgap helper — populate the mock-mode response."""
        self._fake_models = models
        self._is_live = False
        self._client = None

    def list_models(self) -> HuggingFaceListResponse:
        if not self._is_live:
            return HuggingFaceListResponse(models=self._fake_models or ())
        models: list[HuggingFaceModelSummary] = []
        try:
            for repo_id in self._curated_repo_ids:
                info = self._client.model_info(repo_id)
                models.append(_summary_from_hf_info(info))
            return HuggingFaceListResponse(models=tuple(models))
        except Exception as exc:  # pragma: no cover — runtime AWS failure
            return HuggingFaceListResponse(
                models=tuple(models), error=str(exc),
            )


def _summary_from_hf_info(info) -> HuggingFaceModelSummary:  # type: ignore[no-untyped-def]
    """Map a huggingface_hub ModelInfo to our normalised view."""
    last_modified = getattr(info, "last_modified", None) or datetime.now(timezone.utc)
    return HuggingFaceModelSummary(
        repo_id=getattr(info, "id", "") or getattr(info, "modelId", ""),
        last_modified=last_modified,
        downloads=getattr(info, "downloads", 0) or 0,
        likes=getattr(info, "likes", 0) or 0,
        tags=tuple(getattr(info, "tags", []) or []),
        library_name=getattr(info, "library_name", "") or "",
    )


def to_bedrock_compatible_summary(
    hf: HuggingFaceModelSummary,
) -> BedrockModelSummary:
    """Adapt a HuggingFace summary to the Scout Agent's BedrockModelSummary shape.

    The Scout Agent's ``run_once`` was written against
    BedrockModelSummary. Rather than threading two different summary
    types through the agent, we normalise here. Tokenizer and
    architecture are inferred from the model_id in the same way as
    Bedrock entries.
    """
    return BedrockModelSummary(
        model_id=hf.repo_id,
        display_name=hf.repo_id,
        provider=ModelProvider.HUGGINGFACE,
        input_modalities=("TEXT",),
        output_modalities=("TEXT",),
        inference_types_supported=(),  # HF doesn't have Bedrock's inference taxonomy
        response_streaming_supported=False,
    )


def synthesize_hf_summary(
    *,
    repo_id: str,
    downloads: int = 100_000,
    likes: int = 1_000,
    tags: Iterable[str] = (),
    last_modified: datetime | None = None,
) -> HuggingFaceModelSummary:
    """Test fixture builder."""
    return HuggingFaceModelSummary(
        repo_id=repo_id,
        last_modified=last_modified or datetime(2026, 5, 6, tzinfo=timezone.utc),
        downloads=downloads,
        likes=likes,
        tags=tuple(tags),
        library_name="transformers",
    )
