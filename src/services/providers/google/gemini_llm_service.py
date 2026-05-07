"""Project Aura - Google Gemini (Vertex AI) LLM Service.

Implements ``LLMService`` against Google's Gemini family. Two backends
are supported:

- **Vertex AI** (``vertexai.preview.generative_models``) — preferred for
  enterprise / GCP-resident customers, uses GCP IAM via ADC.
- **google-generativeai** — public AI Studio API path; uses an API key.

Both SDKs are imported softly so the module loads in slim/air-gapped
builds. When neither is available the service operates in mock mode,
matching the AzureOpenAI / OpenAI patterns.

Why both: Vertex is what regulated customers will deploy against (GCP
DLP/IAM/audit); google-generativeai is the lower-friction path for dev
and the public-cloud SaaS edition. The public API surface is the same
because Gemini's prompt + system-instruction model is identical across
both transports.

See ADRs 004 (cloud abstraction), 008 (LLM cost controls), 029 (model
routing).
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


# Soft imports — both SDKs are optional.
VERTEXAI_AVAILABLE = False
GENAI_AVAILABLE = False

try:
    import vertexai  # type: ignore[import-not-found]
    from vertexai.preview.generative_models import (
        GenerativeModel as VertexGenerativeModel,  # type: ignore[import-not-found]
    )

    VERTEXAI_AVAILABLE = True
except ImportError:  # pragma: no cover — depends on env
    vertexai = None  # type: ignore[assignment]
    VertexGenerativeModel = None  # type: ignore[assignment]

try:
    import google.generativeai as genai  # type: ignore[import-not-found]

    GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]


if not (VERTEXAI_AVAILABLE or GENAI_AVAILABLE):
    logger.warning(
        "Neither vertexai nor google-generativeai installed; "
        "GeminiLLMService will run in mock mode"
    )


DEFAULT_MODEL_CATALOG: dict[str, ModelConfig] = {
    "gemini-2.0-flash": ModelConfig(
        model_id="gemini-2.0-flash",
        family=ModelFamily.MISTRAL,  # Closest existing enum slot; see note below.
        max_tokens=8192,
        temperature=0.2,
        input_cost_per_1k=0.000075,
        output_cost_per_1k=0.000300,
    ),
    "gemini-2.0-pro": ModelConfig(
        model_id="gemini-2.0-pro",
        family=ModelFamily.MISTRAL,
        max_tokens=8192,
        temperature=0.2,
        input_cost_per_1k=0.0035,
        output_cost_per_1k=0.0105,
    ),
    "gemini-1.5-pro": ModelConfig(
        model_id="gemini-1.5-pro",
        family=ModelFamily.MISTRAL,
        max_tokens=8192,
        temperature=0.2,
        input_cost_per_1k=0.0035,
        output_cost_per_1k=0.0105,
    ),
}
# Note on ModelFamily: the existing enum doesn't yet have a GEMINI member.
# Reusing MISTRAL is a stop-gap so this module compiles against the current
# abstraction; a follow-up PR should add ModelFamily.GEMINI and migrate.
# Tracking as audit follow-up — see provider docstring above.


class GeminiLLMService(LLMService):
    """LLMService implementation for Google Gemini (Vertex AI or AI Studio)."""

    MODEL_BY_TIER: dict[str, str] = {
        "fast": "gemini-2.0-flash",
        "accurate": "gemini-2.0-pro",
        "maximum": "gemini-1.5-pro",  # Until 2.0-ultra ships
    }

    def __init__(
        self,
        project_id: str | None = None,
        location: str = "us-central1",
        api_key: str | None = None,
        default_model: str = "gemini-2.0-pro",
        prefer_vertex: bool = True,
    ) -> None:
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.environ.get(
            "GOOGLE_CLOUD_LOCATION", "us-central1"
        )
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        self.default_model = default_model
        self.prefer_vertex = prefer_vertex

        self._mode: str = "mock"  # "vertex" | "genai" | "mock"
        self._initialized = False
        self._usage_records: list[dict[str, Any]] = []

    @property
    def is_mock_mode(self) -> bool:
        return self._mode == "mock" or not self._initialized

    def _select_backend(self) -> str:
        if self.prefer_vertex and VERTEXAI_AVAILABLE and self.project_id:
            return "vertex"
        if GENAI_AVAILABLE and self.api_key:
            return "genai"
        if VERTEXAI_AVAILABLE and self.project_id:
            return "vertex"
        return "mock"

    async def initialize(self) -> bool:
        backend = self._select_backend()
        self._mode = backend

        if backend == "mock":
            logger.info(
                "Gemini service running in mock mode (SDKs missing or no credentials)"
            )
            self._initialized = True
            return True

        try:
            if backend == "vertex":
                vertexai.init(project=self.project_id, location=self.location)  # type: ignore[union-attr]
                logger.info(
                    "Vertex AI initialized (project=%s, location=%s)",
                    self.project_id,
                    self.location,
                )
            elif backend == "genai":
                genai.configure(api_key=self.api_key)  # type: ignore[union-attr]
                logger.info("google-generativeai client initialized via API key")

            self._initialized = True
            return True
        except Exception as e:  # pragma: no cover
            logger.error("Failed to initialize Gemini backend %s: %s", backend, e)
            self._mode = "mock"
            self._initialized = True
            return False

    async def shutdown(self) -> None:
        self._initialized = False
        self._mode = "mock"

    # -------------------------------------------------------------- helpers

    def _record_usage(self, input_tokens: int, output_tokens: int, model: str) -> None:
        self._usage_records.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )

    def _model_id(self, model_config: ModelConfig | None) -> str:
        if model_config is not None:
            return model_config.model_id
        return self.default_model

    def _generation_config(
        self, request: LLMRequest, model_config: ModelConfig | None
    ) -> dict[str, Any]:
        cfg: dict[str, Any] = {}
        max_tokens = request.max_tokens or (
            model_config.max_tokens if model_config else None
        )
        if max_tokens is not None:
            cfg["max_output_tokens"] = max_tokens
        if request.temperature is not None:
            cfg["temperature"] = request.temperature
        if request.top_p is not None:
            cfg["top_p"] = request.top_p
        if request.stop_sequences:
            cfg["stop_sequences"] = list(request.stop_sequences)
        return cfg

    # --------------------------------------------------------------- invoke

    async def invoke(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> LLMResponse:
        start = time.time()
        model_id = self._model_id(model_config)

        if self.is_mock_mode:
            return LLMResponse(
                content=f"[mock-gemini:{model_id}] {request.prompt[:80]}",
                model_id=model_id,
                input_tokens=len(request.prompt.split()),
                output_tokens=10,
                latency_ms=(time.time() - start) * 1000,
                finish_reason="stop",
                metadata={"_mock": True, "_provider": "gemini", "_backend": "mock"},
            )

        # Vertex and google-generativeai have nearly identical surface for
        # the relevant call. Route via _mode.
        try:
            if self._mode == "vertex":
                content, in_tok, out_tok, finish = await self._invoke_vertex(
                    request, model_id, model_config
                )
            else:  # genai
                content, in_tok, out_tok, finish = await self._invoke_genai(
                    request, model_id, model_config
                )
        except Exception as e:
            logger.error("Gemini invoke failed (backend=%s): %s", self._mode, e)
            raise

        self._record_usage(in_tok, out_tok, model_id)
        return LLMResponse(
            content=content,
            model_id=model_id,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=(time.time() - start) * 1000,
            finish_reason=finish,
            metadata={"_provider": "gemini", "_backend": self._mode},
        )

    async def _invoke_vertex(
        self,
        request: LLMRequest,
        model_id: str,
        model_config: ModelConfig | None,
    ) -> tuple[str, int, int, str]:
        # The Vertex SDK is sync-only on most calls; offload to a thread to
        # keep the FastAPI event loop free.
        import asyncio

        def _call() -> Any:
            model_kwargs: dict[str, Any] = {}
            if request.system_prompt:
                model_kwargs["system_instruction"] = request.system_prompt
            model = VertexGenerativeModel(model_id, **model_kwargs)  # type: ignore[misc]
            return model.generate_content(
                request.prompt,
                generation_config=self._generation_config(request, model_config),
            )

        result = await asyncio.to_thread(_call)
        text = getattr(result, "text", "") or ""
        usage = getattr(result, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0
        finish = "stop"
        candidates = getattr(result, "candidates", None) or []
        if candidates:
            finish = str(getattr(candidates[0], "finish_reason", "stop"))
        return text, in_tok, out_tok, finish

    async def _invoke_genai(
        self,
        request: LLMRequest,
        model_id: str,
        model_config: ModelConfig | None,
    ) -> tuple[str, int, int, str]:
        import asyncio

        def _call() -> Any:
            kwargs: dict[str, Any] = {}
            if request.system_prompt:
                kwargs["system_instruction"] = request.system_prompt
            model = genai.GenerativeModel(model_id, **kwargs)  # type: ignore[union-attr]
            return model.generate_content(
                request.prompt,
                generation_config=self._generation_config(request, model_config),
            )

        result = await asyncio.to_thread(_call)
        text = getattr(result, "text", "") or ""
        usage = getattr(result, "usage_metadata", None)
        in_tok = getattr(usage, "prompt_token_count", 0) if usage else 0
        out_tok = getattr(usage, "candidates_token_count", 0) if usage else 0
        finish = "stop"
        candidates = getattr(result, "candidates", None) or []
        if candidates:
            finish = str(getattr(candidates[0], "finish_reason", "stop"))
        return text, in_tok, out_tok, finish

    async def invoke_streaming(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> AsyncIterator[str]:
        model_id = self._model_id(model_config)

        if self.is_mock_mode:

            async def _mock_stream() -> AsyncIterator[str]:
                for chunk in (f"[mock-gemini:{model_id}]", " ", request.prompt[:80]):
                    yield chunk

            async for c in _mock_stream():
                yield c
            return

        # Both backends expose stream=True on generate_content; the call is sync
        # and yields chunks, so we drive the iterator from a thread.
        import asyncio

        def _start_stream() -> Any:
            kwargs: dict[str, Any] = {}
            if request.system_prompt:
                kwargs["system_instruction"] = request.system_prompt
            if self._mode == "vertex":
                model = VertexGenerativeModel(model_id, **kwargs)  # type: ignore[misc]
            else:
                model = genai.GenerativeModel(model_id, **kwargs)  # type: ignore[union-attr]
            return model.generate_content(
                request.prompt,
                generation_config=self._generation_config(request, model_config),
                stream=True,
            )

        stream = await asyncio.to_thread(_start_stream)
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text

    # ----------------------------------------------------- code-shaped helpers

    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        sys = (
            f"You are a senior software engineer. Produce only {language} "
            "source code, with no commentary."
        )
        full = f"{prompt}\n\nContext:\n{context}" if context else prompt
        return await self.invoke(
            LLMRequest(prompt=full, system_prompt=sys, max_tokens=max_tokens)
        )

    async def analyze_code(
        self,
        code: str,
        language: str,
        analysis_type: str,
    ) -> LLMResponse:
        sys = (
            f"You are a {language} {analysis_type} reviewer. Reply with a JSON "
            "object: {findings: [...], severity: 'low'|'medium'|'high'|'critical'}."
        )
        return await self.invoke(LLMRequest(prompt=code, system_prompt=sys))

    # -------------------------------------------------- embeddings (optional)

    async def generate_embedding(
        self,
        text: str,
        model_id: str | None = None,
    ) -> list[float]:
        # Both Vertex and AI Studio expose embedding models, but the API
        # surfaces differ. Returning a deterministic mock keeps callers
        # working under headless dev; production should use a dedicated
        # embedding service.
        return [0.0] * 16

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        model_id: str | None = None,
    ) -> list[list[float]]:
        return [[0.0] * 16 for _ in texts]

    # ------------------------------------------------------- usage / budgets

    async def get_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> UsageSummary:
        records = [
            r for r in self._usage_records if start_date <= r["timestamp"] <= end_date
        ]
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
        return (await self.get_usage_summary(start, end)).total_cost_usd

    async def get_monthly_spend(self) -> float:
        end = datetime.now(timezone.utc)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (await self.get_usage_summary(start, end)).total_cost_usd

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
            "provider": "gemini",
            "vertex_available": VERTEXAI_AVAILABLE,
            "genai_available": GENAI_AVAILABLE,
            "active_backend": self._mode,
            "initialized": self._initialized,
            "default_model": self.default_model,
        }
