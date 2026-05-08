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
async def test_gemini_genai_backend_uses_new_client_models_shape() -> None:
    """The genai backend must call the unified-SDK shape:
    ``client.models.generate_content(model=..., contents=..., config=...)``.

    This is the migration target from the deprecated google-generativeai
    SDK (``GenerativeModel(...).generate_content(...)``) to the unified
    google-genai SDK. The test stitches a fake client/models/response
    chain so the call boundary is validated even though no real Bedrock
    credentials are present.
    """
    from unittest.mock import MagicMock

    from src.services.providers.google import gemini_llm_service as svc_mod

    # Capture the kwargs the service hands to the SDK.
    captured: dict[str, object] = {}

    fake_response = MagicMock()
    fake_response.text = "from-fake-genai"
    fake_response.usage_metadata = MagicMock(
        prompt_token_count=12, candidates_token_count=7
    )
    fake_response.candidates = [MagicMock(finish_reason="stop")]

    def fake_generate_content(**kwargs: object) -> object:
        captured.update(kwargs)
        return fake_response

    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = fake_generate_content

    # Force the genai branch by short-circuiting the soft-imports and
    # initialization path. The service ends up in ``_mode == "genai"``
    # with our fake client wired in.
    svc = GeminiLLMService(api_key="fake-key", project_id=None, prefer_vertex=False)
    svc._mode = "genai"
    svc._initialized = True
    svc._genai_client = fake_client

    # Patch the module-level GENAI_AVAILABLE so health_check looks
    # consistent post-call.
    saved_available = svc_mod.GENAI_AVAILABLE
    svc_mod.GENAI_AVAILABLE = True
    try:
        resp = await svc.invoke(
            LLMRequest(prompt="ping", system_prompt="you are a tester", max_tokens=64)
        )
    finally:
        svc_mod.GENAI_AVAILABLE = saved_available

    # Verify: new SDK call shape used (model=, contents=, config=).
    assert captured["model"] == svc.default_model
    assert captured["contents"] == "ping"
    config = captured["config"]
    assert isinstance(config, dict)
    assert config["system_instruction"] == "you are a tester"
    assert config["max_output_tokens"] == 64

    # Verify: response surface translated correctly.
    assert resp.content == "from-fake-genai"
    assert resp.input_tokens == 12
    assert resp.output_tokens == 7
    assert resp.finish_reason == "stop"
    assert resp.metadata["_backend"] == "genai"


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
