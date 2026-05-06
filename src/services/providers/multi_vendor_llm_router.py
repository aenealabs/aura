"""Project Aura - Multi-vendor LLM router.

Implements ``LLMService`` by holding references to one provider per
vendor (Anthropic via Bedrock, OpenAI direct, Google Gemini) and
dispatching each request to the right backend based on a routing
policy. Supersedes the single-vendor wiring in ``factory.create_llm_service``
when ``LLM_ROUTING_MODE=multi_vendor`` is set.

Why this exists: ADR-029 introduced model-tier routing within a single
vendor (Bedrock/Claude). The 2026-05-06 audit flagged that the router
abstraction is single-vendor today even though the platform's
positioning is multi-vendor. This router closes that gap with no
changes required at the agent layer — agents continue to call
``service.invoke(...)`` and the router selects the backend.

Routing policy:

1. **Explicit override** — ``LLMRequest.metadata['provider']`` set to
   ``'anthropic' | 'openai' | 'gemini'`` always wins.
2. **Tier mapping** — ``LLMRequest.metadata['tier']`` set to ``'fast' |
   'accurate' | 'maximum'`` selects the cheapest available provider for
   that tier per ``TIER_PROVIDER_PREFERENCE`` below.
3. **Default** — fall through to ``default_provider`` (Anthropic/Bedrock
   to preserve existing behavior).

Provider availability is checked at routing time so a missing SDK or
absent credentials in one vendor doesn't stop the router from serving
the others.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from src.abstractions.llm_service import (
    LLMRequest,
    LLMResponse,
    LLMService,
    ModelConfig,
    UsageSummary,
)

logger = logging.getLogger(__name__)


PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"

# Tier → ordered preference list. The router walks this list and picks
# the first provider that's both registered and not in mock mode.
# Anthropic is first across all tiers because it's the established
# default; OpenAI and Gemini follow as failover / cost-shape variants.
TIER_PROVIDER_PREFERENCE: dict[str, list[str]] = {
    "fast": [PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_ANTHROPIC],
    "accurate": [PROVIDER_ANTHROPIC, PROVIDER_OPENAI, PROVIDER_GEMINI],
    "maximum": [PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_GEMINI],
}


class MultiVendorLLMRouter(LLMService):
    """LLMService that dispatches each request to one of several providers."""

    def __init__(
        self,
        providers: dict[str, LLMService],
        default_provider: str = PROVIDER_ANTHROPIC,
    ) -> None:
        if default_provider not in providers:
            raise ValueError(
                f"default_provider {default_provider!r} not in registered providers "
                f"{sorted(providers)}"
            )
        self.providers = providers
        self.default_provider = default_provider
        self._initialized = False

    # ------------------------------------------------------------- routing

    def _provider_is_live(self, provider_id: str) -> bool:
        svc = self.providers.get(provider_id)
        if svc is None:
            return False
        is_mock = getattr(svc, "is_mock_mode", False)
        return not is_mock

    def _route(self, request: LLMRequest) -> tuple[str, LLMService]:
        meta = request.metadata or {}
        explicit = meta.get("provider")
        if explicit and explicit in self.providers:
            svc = self.providers[explicit]
            return explicit, svc

        tier = meta.get("tier")
        if tier and tier in TIER_PROVIDER_PREFERENCE:
            for candidate in TIER_PROVIDER_PREFERENCE[tier]:
                if candidate in self.providers and self._provider_is_live(candidate):
                    return candidate, self.providers[candidate]
            # All tier-preferred providers in mock mode — fall through to
            # the default (also likely mock; consistent behaviour).

        return self.default_provider, self.providers[self.default_provider]

    # --------------------------------------------------------- lifecycle

    async def initialize(self) -> bool:
        ok = True
        for name, svc in self.providers.items():
            try:
                provider_ok = await svc.initialize()
                if not provider_ok:
                    logger.warning("provider %s initialize() returned False", name)
                ok = ok and provider_ok
            except Exception as e:  # pragma: no cover
                logger.error("provider %s initialize() raised: %s", name, e)
                ok = False
        self._initialized = True
        return ok

    async def shutdown(self) -> None:
        for name, svc in self.providers.items():
            try:
                await svc.shutdown()
            except Exception as e:  # pragma: no cover
                logger.warning("provider %s shutdown raised: %s", name, e)
        self._initialized = False

    # --------------------------------------------------------- dispatch

    async def invoke(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> LLMResponse:
        provider_id, svc = self._route(request)
        logger.debug("multi-vendor route → %s (tier=%s)",
                     provider_id, (request.metadata or {}).get("tier"))
        response = await svc.invoke(request, model_config)
        # Tag the response so downstream telemetry knows which vendor served it.
        response.metadata.setdefault("_router_provider", provider_id)
        return response

    async def invoke_streaming(
        self,
        request: LLMRequest,
        model_config: ModelConfig | None = None,
    ) -> AsyncIterator[str]:
        provider_id, svc = self._route(request)
        logger.debug("multi-vendor stream → %s", provider_id)
        async for chunk in svc.invoke_streaming(request, model_config):
            yield chunk

    # --------------------------------------------- code-shaped helpers

    async def generate_code(
        self,
        prompt: str,
        language: str,
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        # Code generation defaults to "accurate" tier policy.
        request = LLMRequest(
            prompt=prompt,
            metadata={"tier": "accurate", "intent": "code_generation"},
        )
        provider_id, svc = self._route(request)
        return await svc.generate_code(prompt, language, context, max_tokens)

    async def analyze_code(
        self,
        code: str,
        language: str,
        analysis_type: str,
    ) -> LLMResponse:
        request = LLMRequest(
            prompt=code,
            metadata={"tier": "accurate", "intent": "code_analysis"},
        )
        provider_id, svc = self._route(request)
        return await svc.analyze_code(code, language, analysis_type)

    # --------------------------------------------------- embeddings

    async def generate_embedding(
        self, text: str, model_id: str | None = None
    ) -> list[float]:
        # Embeddings are vendor-specific; route through the default
        # provider for consistency. Callers needing a specific embedding
        # model should call the underlying provider directly.
        return await self.providers[self.default_provider].generate_embedding(
            text, model_id
        )

    async def generate_embeddings_batch(
        self, texts: list[str], model_id: str | None = None
    ) -> list[list[float]]:
        return await self.providers[
            self.default_provider
        ].generate_embeddings_batch(texts, model_id)

    # ---------------------------------------------------- usage / budgets

    async def get_usage_summary(
        self, start_date: datetime, end_date: datetime
    ) -> UsageSummary:
        # Aggregate across providers.
        summaries = []
        for name, svc in self.providers.items():
            try:
                summaries.append((name, await svc.get_usage_summary(start_date, end_date)))
            except Exception as e:  # pragma: no cover
                logger.warning("usage summary for %s failed: %s", name, e)
        total_requests = sum(s.total_requests for _, s in summaries)
        total_input = sum(s.total_input_tokens for _, s in summaries)
        total_output = sum(s.total_output_tokens for _, s in summaries)
        total_cost = sum(s.total_cost_usd for _, s in summaries)
        by_model: dict[str, dict[str, Any]] = {}
        for name, s in summaries:
            for mid, m in s.by_model.items():
                key = f"{name}:{mid}"
                by_model[key] = m
        return UsageSummary(
            total_requests=total_requests,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=total_cost,
            period_start=start_date,
            period_end=end_date,
            by_model=by_model,
        )

    async def get_daily_spend(self) -> float:
        total = 0.0
        for svc in self.providers.values():
            try:
                total += await svc.get_daily_spend()
            except Exception:  # pragma: no cover
                pass
        return total

    async def get_monthly_spend(self) -> float:
        total = 0.0
        for svc in self.providers.values():
            try:
                total += await svc.get_monthly_spend()
            except Exception:  # pragma: no cover
                pass
        return total

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
        out: list[ModelConfig] = []
        for svc in self.providers.values():
            try:
                out.extend(await svc.list_available_models())
            except Exception:  # pragma: no cover
                pass
        return out

    async def get_model_config(self, model_id: str) -> ModelConfig | None:
        for svc in self.providers.values():
            cfg = await svc.get_model_config(model_id)
            if cfg is not None:
                return cfg
        return None

    # -------------------------------------------------- health

    async def health_check(self) -> dict[str, Any]:
        results: dict[str, Any] = {
            "router": "multi-vendor",
            "default_provider": self.default_provider,
            "providers": {},
        }
        for name, svc in self.providers.items():
            try:
                results["providers"][name] = await svc.health_check()
            except Exception as e:  # pragma: no cover
                results["providers"][name] = {"error": str(e)}
        return results


def build_default_multi_vendor_router() -> MultiVendorLLMRouter:
    """Construct a router with all three vendors registered.

    Each provider is constructed in mock mode unless its credentials
    are set in the environment, so this function is safe to call
    during dev/local startup. The default provider is Anthropic via
    Bedrock to preserve current behavior; flip the
    ``LLM_DEFAULT_PROVIDER`` env var to swap.
    """
    from src.services.providers.aws.bedrock_adapter import BedrockLLMAdapter
    from src.services.providers.google.gemini_llm_service import GeminiLLMService
    from src.services.providers.openai.openai_llm_service import OpenAILLMService

    region = os.environ.get("AWS_REGION", "us-east-1")
    providers: dict[str, LLMService] = {
        PROVIDER_ANTHROPIC: BedrockLLMAdapter(region=region),
        PROVIDER_OPENAI: OpenAILLMService(),
        PROVIDER_GEMINI: GeminiLLMService(),
    }
    default = os.environ.get("LLM_DEFAULT_PROVIDER", PROVIDER_ANTHROPIC)
    if default not in providers:
        logger.warning(
            "LLM_DEFAULT_PROVIDER=%s not registered; falling back to %s",
            default,
            PROVIDER_ANTHROPIC,
        )
        default = PROVIDER_ANTHROPIC
    return MultiVendorLLMRouter(providers=providers, default_provider=default)
