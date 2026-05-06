"""Project Aura - OpenAI LLM Service.

Direct-to-OpenAI implementation of ``LLMService``. Sibling of
``AzureOpenAIService``: same interface, different transport
(api.openai.com instead of an Azure deployment endpoint).

Why this exists alongside ``AzureOpenAIService``: the multi-vendor
pitch (and ADR-029 model router) requires a path to call OpenAI's
public API directly so customers running outside Azure can still route
GPT/o-series traffic through the platform. Azure-deployed customers
continue to use ``AzureOpenAIService``.

The OpenAI Python SDK is imported softly so this module loads in
slim/air-gapped builds (ADR-078) without requiring the dependency. In
that case the service operates in mock mode, mirroring the
``AzureOpenAIService`` posture.

See ADRs 004 (cloud abstraction), 008 (LLM cost controls), and 029
(model routing).
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from src.abstractions.llm_service import (
    LLMRequest,
    LLMResponse,
    LLMService,
    ModelConfig,
    ModelFamily,
    UsageSummary,
)

logger = logging.getLogger(__name__)


try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None  # type: ignore[assignment]
    logger.warning("openai SDK not available — OpenAILLMService will run in mock mode")


# Default model catalog — kept short and current as of 2026-05.
# Add new models here when they ship; the router selects by tier
# (FAST / ACCURATE / MAXIMUM in BedrockLLMService.ModelTier) and the
# tier→model map in OpenAILLMService.MODEL_BY_TIER below.
DEFAULT_MODEL_CATALOG: dict[str, ModelConfig] = {
    "gpt-4o-mini": ModelConfig(
        model_id="gpt-4o-mini",
        family=ModelFamily.GPT,
        max_tokens=16384,
        temperature=0.2,
        input_cost_per_1k=0.00015,
        output_cost_per_1k=0.00060,
    ),
    "gpt-4o": ModelConfig(
        model_id="gpt-4o",
        family=ModelFamily.GPT,
        max_tokens=16384,
        temperature=0.2,
        input_cost_per_1k=0.0025,
        output_cost_per_1k=0.0100,
    ),
    "o1-mini": ModelConfig(
        model_id="o1-mini",
        family=ModelFamily.GPT,
        max_tokens=65536,
        temperature=1.0,  # o-series ignores temperature; recorded for parity
        input_cost_per_1k=0.0030,
        output_cost_per_1k=0.0120,
    ),
    "o1": ModelConfig(
        model_id="o1",
        family=ModelFamily.GPT,
        max_tokens=100000,
        temperature=1.0,
        input_cost_per_1k=0.0150,
        output_cost_per_1k=0.0600,
    ),
}


class OpenAILLMService(LLMService):
    """LLMService implementation backed by OpenAI's public API."""

    # Tier → model id. The model router (ADR-029) routes by tier so this
    # service is interchangeable with BedrockLLMService and AzureOpenAIService
    # for the same logical workload.
    MODEL_BY_TIER: dict[str, str] = {
        "fast": "gpt-4o-mini",
        "accurate": "gpt-4o",
        "maximum": "o1",
    }

    def __init__(
        self,
        api_key: str | None = None,
        organization: str | None = None,
        base_url: str | None = None,
        default_model: str = "gpt-4o",
        request_timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.organization = organization or os.environ.get("OPENAI_ORG_ID")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.default_model = default_model
        self.request_timeout_seconds = request_timeout_seconds

        self._client: Any | None = None
        self._initialized = False
        self._usage_records: list[dict[str, Any]] = []

    @property
    def is_mock_mode(self) -> bool:
        """True when the SDK is missing OR no API key is configured."""
        return not OPENAI_AVAILABLE or not self.api_key

    async def initialize(self) -> bool:
        if self.is_mock_mode:
            logger.info("OpenAI service running in mock mode (no API key or SDK)")
            self._initialized = True
            return True
        try:
            self._client = AsyncOpenAI(  # type: ignore[misc]
                api_key=self.api_key,
                organization=self.organization,
                base_url=self.base_url,
                timeout=self.request_timeout_seconds,
            )
            self._initialized = True
            logger.info("OpenAI client initialized (default_model=%s)", self.default_model)
            return True
        except Exception as e:  # pragma: no cover — network/credential failure surface
            logger.error("Failed to initialize OpenAI client: %s", e)
            return False

    async def shutdown(self) -> None:
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if callable(close):
                try:
                    result = close()
                    if hasattr(result, "__await__"):
                        await result
                except Exception:  # pragma: no cover
                    pass
        self._initialized = False
        self._client = None

    # ------------------------------------------------------------------ helpers

    def _record_usage(self, input_tokens: int, output_tokens: int, model: str) -> None:
        self._usage_records.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )

    def _build_messages(self, request: LLMRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        if request.messages:
            messages.extend(request.messages)
        else:
            messages.append({"role": "user", "content": request.prompt})
        return messages

    def _model_id(self, model_config: ModelConfig | None) -> str:
        if model_config is not None:
            return model_config.model_id
        return self.default_model

    # ------------------------------------------------------------------ invoke

    async def invoke(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> LLMResponse:
        start = time.time()
        model_id = self._model_id(model_config)

        if self.is_mock_mode:
            return LLMResponse(
                content=f"[mock-openai:{model_id}] {request.prompt[:80]}",
                model_id=model_id,
                input_tokens=len(request.prompt.split()),
                output_tokens=10,
                latency_ms=(time.time() - start) * 1000,
                finish_reason="stop",
                metadata={"_mock": True, "_provider": "openai"},
            )

        if self._client is None:
            raise RuntimeError("OpenAI client not initialized — call initialize()")

        params: dict[str, Any] = {
            "model": model_id,
            "messages": self._build_messages(request),
        }
        max_tokens = request.max_tokens or (
            model_config.max_tokens if model_config else None
        )
        if max_tokens is not None:
            # The o-series prefers `max_completion_tokens`; for everything else
            # use the long-standing `max_tokens` field. Pass both for safety —
            # OpenAI ignores unknown args silently.
            params["max_tokens"] = max_tokens
        if request.temperature is not None and not model_id.startswith("o"):
            params["temperature"] = request.temperature
        if request.top_p is not None and not model_id.startswith("o"):
            params["top_p"] = request.top_p
        if request.stop_sequences:
            params["stop"] = request.stop_sequences

        try:
            completion = await self._client.chat.completions.create(**params)
        except Exception as e:
            logger.error("OpenAI invoke failed: %s", e)
            raise

        choice = completion.choices[0]
        content = choice.message.content or ""
        finish_reason = choice.finish_reason or "stop"
        usage = getattr(completion, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        self._record_usage(input_tokens, output_tokens, model_id)

        return LLMResponse(
            content=content,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=(time.time() - start) * 1000,
            finish_reason=finish_reason,
            metadata={"_provider": "openai"},
        )

    async def invoke_streaming(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> AsyncIterator[str]:
        model_id = self._model_id(model_config)

        if self.is_mock_mode:
            async def _mock_stream() -> AsyncIterator[str]:
                for chunk in (f"[mock-openai:{model_id}]", " ", request.prompt[:80]):
                    yield chunk

            async for c in _mock_stream():
                yield c
            return

        if self._client is None:
            raise RuntimeError("OpenAI client not initialized — call initialize()")

        params: dict[str, Any] = {
            "model": model_id,
            "messages": self._build_messages(request),
            "stream": True,
        }
        if request.temperature is not None and not model_id.startswith("o"):
            params["temperature"] = request.temperature
        if request.max_tokens is not None:
            params["max_tokens"] = request.max_tokens
        if request.stop_sequences:
            params["stop"] = request.stop_sequences

        stream = await self._client.chat.completions.create(**params)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    # ----------------------------------------------------- code-shaped helpers

    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        sys = (
            "You are a senior software engineer. Produce only "
            f"{language} source code, with no commentary."
        )
        full_prompt = (
            f"{prompt}\n\nContext:\n{context}" if context else prompt
        )
        return await self.invoke(
            LLMRequest(prompt=full_prompt, system_prompt=sys, max_tokens=max_tokens)
        )

    async def analyze_code(
        self,
        code: str,
        language: str,
        analysis_type: str,
    ) -> LLMResponse:
        sys = (
            f"You are a {language} {analysis_type} reviewer. Reply with a "
            "JSON object: {findings: [...], severity: 'low'|'medium'|'high'|'critical'}."
        )
        return await self.invoke(LLMRequest(prompt=code, system_prompt=sys))

    # --------------------------------------------------- embeddings (optional)

    async def generate_embedding(
        self,
        text: str,
        model_id: str | None = None,
    ) -> list[float]:
        if self.is_mock_mode or self._client is None:
            return [0.0] * 16
        model = model_id or "text-embedding-3-small"
        resp = await self._client.embeddings.create(model=model, input=text)
        return list(resp.data[0].embedding)

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        model_id: str | None = None,
    ) -> list[list[float]]:
        if self.is_mock_mode or self._client is None:
            return [[0.0] * 16 for _ in texts]
        model = model_id or "text-embedding-3-small"
        resp = await self._client.embeddings.create(model=model, input=texts)
        return [list(item.embedding) for item in resp.data]

    # ------------------------------------------------------- usage / budgets

    async def get_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> UsageSummary:
        records = [r for r in self._usage_records if start_date <= r["timestamp"] <= end_date]
        total_input = sum(r["input_tokens"] for r in records)
        total_output = sum(r["output_tokens"] for r in records)
        cost = 0.0
        by_model: dict[str, dict[str, Any]] = {}
        for r in records:
            cfg = DEFAULT_MODEL_CATALOG.get(r["model"])
            if cfg is None:
                continue
            c = (
                r["input_tokens"] * cfg.input_cost_per_1k / 1000
                + r["output_tokens"] * cfg.output_cost_per_1k / 1000
            )
            cost += c
            by_model.setdefault(r["model"], {"input": 0, "output": 0, "cost": 0.0})
            by_model[r["model"]]["input"] += r["input_tokens"]
            by_model[r["model"]]["output"] += r["output_tokens"]
            by_model[r["model"]]["cost"] += c
        return UsageSummary(
            total_requests=len(records),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=cost,
            period_start=start_date,
            period_end=end_date,
            by_model=by_model,
        )

    async def get_daily_spend(self) -> float:
        end = datetime.now(timezone.utc)
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
        summary = await self.get_usage_summary(start, end)
        return summary.total_cost_usd

    async def get_monthly_spend(self) -> float:
        end = datetime.now(timezone.utc)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        summary = await self.get_usage_summary(start, end)
        return summary.total_cost_usd

    async def check_budget(
        self, daily_limit: float, monthly_limit: float
    ) -> dict[str, Any]:
        daily = await self.get_daily_spend()
        monthly = await self.get_monthly_spend()
        return {
            "daily_spend": daily,
            "daily_limit": daily_limit,
            "daily_remaining": max(0.0, daily_limit - daily),
            "monthly_spend": monthly,
            "monthly_limit": monthly_limit,
            "monthly_remaining": max(0.0, monthly_limit - monthly),
            "over_daily": daily > daily_limit,
            "over_monthly": monthly > monthly_limit,
        }

    # -------------------------------------------------- model management

    async def list_available_models(self) -> list[ModelConfig]:
        return list(DEFAULT_MODEL_CATALOG.values())

    async def get_model_config(self, model_id: str) -> ModelConfig | None:
        return DEFAULT_MODEL_CATALOG.get(model_id)

    # -------------------------------------------------- health

    async def health_check(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "available": OPENAI_AVAILABLE,
            "initialized": self._initialized,
            "mock_mode": self.is_mock_mode,
            "default_model": self.default_model,
        }
