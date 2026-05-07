"""Tests for OpenAI/Gemini providers and the multi-vendor router.

Both vendor SDKs may be absent in CI / slim builds — the providers and
router must behave correctly in mock mode in that case (which is the
state these tests exercise).
"""

from __future__ import annotations

import pytest

from src.abstractions.llm_service import LLMRequest
from src.services.providers.google.gemini_llm_service import GeminiLLMService
from src.services.providers.multi_vendor_llm_router import (
    PROVIDER_ANTHROPIC,
    PROVIDER_GEMINI,
    PROVIDER_OPENAI,
    MultiVendorLLMRouter,
)
from src.services.providers.openai.openai_llm_service import OpenAILLMService

# ---------------------------------------------------------------- providers


@pytest.mark.asyncio
async def test_openai_mock_mode_initializes_and_invokes() -> None:
    svc = OpenAILLMService(api_key=None)
    assert svc.is_mock_mode is True
    assert await svc.initialize() is True
    resp = await svc.invoke(LLMRequest(prompt="hello"))
    assert "[mock-openai:" in resp.content
    assert resp.input_tokens > 0
    assert resp.metadata.get("_provider") == "openai"
    health = await svc.health_check()
    assert health["mock_mode"] is True


@pytest.mark.asyncio
async def test_gemini_mock_mode_initializes_and_invokes() -> None:
    svc = GeminiLLMService(api_key=None, project_id=None)
    assert svc.is_mock_mode is True
    assert await svc.initialize() is True
    resp = await svc.invoke(LLMRequest(prompt="hello"))
    assert "[mock-gemini:" in resp.content
    health = await svc.health_check()
    assert health["active_backend"] == "mock"


@pytest.mark.asyncio
async def test_openai_streaming_mock() -> None:
    svc = OpenAILLMService(api_key=None)
    await svc.initialize()
    chunks = []
    async for chunk in svc.invoke_streaming(LLMRequest(prompt="abc")):
        chunks.append(chunk)
    assert chunks  # produced something
    assert any("mock-openai" in c for c in chunks)


@pytest.mark.asyncio
async def test_openai_lists_models_and_resolves_config() -> None:
    svc = OpenAILLMService()
    models = await svc.list_available_models()
    assert {m.model_id for m in models} >= {"gpt-4o", "gpt-4o-mini", "o1"}
    cfg = await svc.get_model_config("gpt-4o")
    assert cfg is not None
    assert cfg.input_cost_per_1k > 0


# ----------------------------------------------------------------- router


@pytest.mark.asyncio
async def test_router_explicit_provider_metadata_wins() -> None:
    o = OpenAILLMService(api_key=None)
    g = GeminiLLMService(api_key=None, project_id=None)
    await o.initialize()
    await g.initialize()
    router = MultiVendorLLMRouter(
        providers={PROVIDER_OPENAI: o, PROVIDER_GEMINI: g},
        default_provider=PROVIDER_OPENAI,
    )
    # explicit provider override
    resp = await router.invoke(
        LLMRequest(prompt="hi", metadata={"provider": PROVIDER_GEMINI})
    )
    assert resp.metadata.get("_router_provider") == PROVIDER_GEMINI


@pytest.mark.asyncio
async def test_router_falls_back_to_default_when_tier_preferred_all_mock() -> None:
    """When all tier-preferred providers are in mock mode, the router uses
    the default provider rather than picking arbitrarily.
    """
    o = OpenAILLMService(api_key=None)
    g = GeminiLLMService(api_key=None, project_id=None)
    await o.initialize()
    await g.initialize()
    router = MultiVendorLLMRouter(
        providers={PROVIDER_OPENAI: o, PROVIDER_GEMINI: g},
        default_provider=PROVIDER_OPENAI,
    )
    resp = await router.invoke(LLMRequest(prompt="hi", metadata={"tier": "accurate"}))
    # All providers are mock so neither is "live"; router uses default.
    assert resp.metadata.get("_router_provider") == PROVIDER_OPENAI


@pytest.mark.asyncio
async def test_router_unknown_default_raises() -> None:
    o = OpenAILLMService()
    with pytest.raises(ValueError, match="default_provider"):
        MultiVendorLLMRouter(
            providers={PROVIDER_OPENAI: o},
            default_provider=PROVIDER_ANTHROPIC,
        )


@pytest.mark.asyncio
async def test_router_health_check_aggregates_provider_status() -> None:
    o = OpenAILLMService(api_key=None)
    g = GeminiLLMService(api_key=None, project_id=None)
    await o.initialize()
    await g.initialize()
    router = MultiVendorLLMRouter(
        providers={PROVIDER_OPENAI: o, PROVIDER_GEMINI: g},
        default_provider=PROVIDER_OPENAI,
    )
    health = await router.health_check()
    assert health["router"] == "multi-vendor"
    assert health["default_provider"] == PROVIDER_OPENAI
    assert set(health["providers"].keys()) == {PROVIDER_OPENAI, PROVIDER_GEMINI}


@pytest.mark.asyncio
async def test_router_aggregates_usage_across_vendors() -> None:
    o = OpenAILLMService(api_key=None)
    g = GeminiLLMService(api_key=None, project_id=None)
    await o.initialize()
    await g.initialize()
    router = MultiVendorLLMRouter(
        providers={PROVIDER_OPENAI: o, PROVIDER_GEMINI: g},
        default_provider=PROVIDER_OPENAI,
    )
    from datetime import datetime, timedelta, timezone

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=1)
    summary = await router.get_usage_summary(start, end)
    # Mock mode produces no recorded usage; aggregation should still work.
    assert summary.total_requests == 0
    assert summary.total_cost_usd == 0
