"""Internal SWE-RL fine-tuned model discovery (ADR-088 Phase 3.2).

Monitors Aura's own self-play training pipeline (ADR-050) for new
fine-tuned model checkpoints. Unlike Bedrock and HuggingFace, the
internal source is fully under our control — a checkpoint produced
here is automatically considered allowlisted and provider-trusted.

The discovery contract is intentionally narrow: a single
:py:meth:`list_models` returning the latest tagged checkpoints.
Production wiring polls the Self-Play Orchestrator's checkpoint
manifest (a S3 key pattern); the test path injects fixtures via
``install_fake``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from src.services.model_assurance.adapter_registry import (
    ModelArchitecture,
    ModelProvider,
    TokenizerType,
)
from src.services.model_assurance.scout.bedrock_client import (
    BedrockModelSummary,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InternalModelSummary:
    """Aura SWE-RL training-pipeline output."""

    model_id: str                    # ECR-pattern: "aura-models/swe-rl-vN"
    checkpoint_iso: datetime
    base_model: str = ""             # which Bedrock/HF model this fine-tune started from
    training_loss: float = 0.0
    notes: str = ""


@dataclass(frozen=True)
class InternalListResponse:
    models: tuple[InternalModelSummary, ...]
    error: str | None = None


class InternalModelClient:
    """Polls the SWE-RL training pipeline for new checkpoints.

    Production wiring inspects the self-play orchestrator's manifest
    bucket; tests inject summaries via ``install_fake``.
    """

    def __init__(self) -> None:
        self._fake_models: tuple[InternalModelSummary, ...] = ()

    def install_fake(self, models: tuple[InternalModelSummary, ...]) -> None:
        self._fake_models = models

    def list_models(self) -> InternalListResponse:
        # v1 ships in mock-mode only — production wiring lands when
        # the SSR orchestrator exposes a stable checkpoint-manifest API.
        return InternalListResponse(models=self._fake_models)


def to_bedrock_compatible_summary(
    internal: InternalModelSummary,
) -> BedrockModelSummary:
    """Adapt an internal summary to the Scout Agent's expected shape."""
    return BedrockModelSummary(
        model_id=internal.model_id,
        display_name=internal.model_id,
        provider=ModelProvider.INTERNAL,
        input_modalities=("TEXT",),
        output_modalities=("TEXT",),
        inference_types_supported=("ON_DEMAND",),
        response_streaming_supported=True,
    )


def synthesize_internal_summary(
    *,
    model_id: str = "aura-models/swe-rl-v3",
    checkpoint_iso: datetime | None = None,
    base_model: str = "anthropic.claude-3-5-sonnet-20240620-v1:0",
) -> InternalModelSummary:
    return InternalModelSummary(
        model_id=model_id,
        checkpoint_iso=checkpoint_iso or datetime(2026, 5, 6, tzinfo=timezone.utc),
        base_model=base_model,
    )
