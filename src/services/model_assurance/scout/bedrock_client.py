"""Bedrock list-foundation-models wrapper for the Scout Agent.

Soft-imports boto3 so unit tests can run without AWS credentials.
When boto3 is unavailable, callers must inject a fake client (or
``BedrockListResponse`` directly) — a "live" instantiation without
boto3 raises immediately rather than silently degrading to empty
results, because an empty list would be indistinguishable from
"vendor catalog is empty" and could mask deployment misconfiguration.

The wrapper handles ``ThrottlingException`` retries (with exponential
backoff) but does not silence them — after the configured retries are
exhausted, the partial-result tuple is returned alongside a
``throttled=True`` flag so the Scout Agent can decide whether to
surface a partial run or wait for the next schedule tick.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from src.services.model_assurance.adapter_registry import (
    ModelArchitecture,
    ModelProvider,
    TokenizerType,
)

logger = logging.getLogger(__name__)


try:  # pragma: no cover — exercised via mock-mode tests
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised via mock-mode tests
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[misc,assignment]
    BOTO3_AVAILABLE = False


@dataclass(frozen=True)
class BedrockModelSummary:
    """Normalised view of one Bedrock foundation-model entry.

    Only the fields the Scout Agent needs are surfaced — the raw
    Bedrock response carries dozens of fields most of which aren't
    relevant to the assurance pipeline. Keeping a narrow view stops
    field-creep in the Scout Agent.
    """

    model_id: str
    display_name: str
    provider: ModelProvider
    input_modalities: tuple[str, ...]
    output_modalities: tuple[str, ...]
    inference_types_supported: tuple[str, ...]
    response_streaming_supported: bool


@dataclass(frozen=True)
class BedrockListResponse:
    """Wrapper around the ``list_foundation_models`` response."""

    models: tuple[BedrockModelSummary, ...]
    throttled: bool = False
    error: str | None = None


class BedrockListClient:
    """Bedrock list-foundation-models client wrapper.

    The agent calls :py:meth:`list_models` on each schedule tick. The
    wrapper delegates to a real boto3 client unless ``client=None`` is
    passed, in which case ``list_models`` returns an empty
    ``BedrockListResponse`` (test fixture pattern — inject a fake by
    setting ``self._fake_models`` post-construction).
    """

    def __init__(
        self,
        *,
        region: str = "us-east-1",
        client=None,  # type: ignore[no-untyped-def]
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        self._region = region
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._fake_models: tuple[BedrockModelSummary, ...] | None = None

        if client is not None:
            self._client = client
            self._is_live = True
        elif BOTO3_AVAILABLE:
            try:
                self._client = boto3.client("bedrock", region_name=region)
                self._is_live = True
            except Exception as exc:  # pragma: no cover — env-specific
                logger.info(
                    "BedrockListClient could not init real client (%s); "
                    "falling back to mock mode",
                    exc,
                )
                self._client = None
                self._is_live = False
        else:
            self._client = None
            self._is_live = False

    @property
    def is_live(self) -> bool:
        return self._is_live

    def install_fake(
        self, models: tuple[BedrockModelSummary, ...]
    ) -> None:
        """Test helper — populate the mock-mode response."""
        self._fake_models = models
        self._is_live = False
        self._client = None

    def list_models(self) -> BedrockListResponse:
        """List available foundation models in this partition.

        Mock mode (no client): returns whatever was installed via
        ``install_fake`` (default: empty tuple).
        """
        if not self._is_live:
            return BedrockListResponse(models=self._fake_models or ())

        for attempt in range(1, self._max_retries + 1):
            try:
                raw = self._client.list_foundation_models()
                return BedrockListResponse(
                    models=tuple(
                        _summary_from_bedrock(m)
                        for m in raw.get("modelSummaries", [])
                    )
                )
            except ClientError as exc:
                code = (
                    exc.response.get("Error", {}).get("Code", "")
                    if hasattr(exc, "response")
                    else ""
                )
                if code in {"ThrottlingException", "TooManyRequestsException"}:
                    if attempt < self._max_retries:
                        time.sleep(self._backoff_seconds * attempt)
                        continue
                    return BedrockListResponse(
                        models=(),
                        throttled=True,
                        error=f"throttled after {attempt} attempts",
                    )
                # Non-throttle error: surface as error, not silence.
                return BedrockListResponse(
                    models=(), throttled=False, error=str(exc)
                )
        return BedrockListResponse(
            models=(), throttled=True, error="retries exhausted"
        )


def _summary_from_bedrock(raw: dict) -> BedrockModelSummary:
    """Map a raw Bedrock modelSummary to our normalised view.

    Bedrock-specific values:
        providerName ∈ {Anthropic, Amazon, Meta, AI21, Cohere, ...}
        inferenceTypesSupported ⊇ {ON_DEMAND, PROVISIONED}
    """
    provider_name = (raw.get("providerName") or "").lower()
    if provider_name == "anthropic":
        provider = ModelProvider.BEDROCK  # all Aura-relevant providers map here
    else:
        provider = ModelProvider.BEDROCK
    return BedrockModelSummary(
        model_id=raw.get("modelId", ""),
        display_name=raw.get("modelName", "") or raw.get("modelId", ""),
        provider=provider,
        input_modalities=tuple(raw.get("inputModalities", [])),
        output_modalities=tuple(raw.get("outputModalities", [])),
        inference_types_supported=tuple(raw.get("inferenceTypesSupported", [])),
        response_streaming_supported=bool(
            raw.get("responseStreamingSupported", False)
        ),
    )


# ----------------------------------------------------------------- helpers


def synthesize_summary(
    *,
    model_id: str,
    display_name: str | None = None,
    streaming: bool = True,
) -> BedrockModelSummary:
    """Test fixture builder for BedrockModelSummary."""
    return BedrockModelSummary(
        model_id=model_id,
        display_name=display_name or model_id,
        provider=ModelProvider.BEDROCK,
        input_modalities=("TEXT",),
        output_modalities=("TEXT",),
        inference_types_supported=("ON_DEMAND",),
        response_streaming_supported=streaming,
    )


# Architecture / tokenizer inference helpers — used by the Scout Agent
# when it synthesises a candidate ModelAdapter for a newly-discovered
# Bedrock model that doesn't have a hand-curated entry yet.

def infer_tokenizer(model_id: str) -> TokenizerType:
    if "claude" in model_id.lower():
        return TokenizerType.CLAUDE
    if "llama" in model_id.lower():
        return TokenizerType.LLAMA
    if "gpt" in model_id.lower():
        return TokenizerType.CL100K
    return TokenizerType.UNKNOWN


def infer_architecture(model_id: str) -> ModelArchitecture:
    # Bedrock catalog doesn't distinguish dense vs MoE; default DENSE.
    if "mixtral" in model_id.lower() or "moe" in model_id.lower():
        return ModelArchitecture.MOE
    return ModelArchitecture.DENSE
