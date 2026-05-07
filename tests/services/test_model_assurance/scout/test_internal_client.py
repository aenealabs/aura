"""Tests for internal SWE-RL client (ADR-088 Phase 3.2)."""

from __future__ import annotations

from datetime import datetime, timezone

from src.services.model_assurance.adapter_registry import ModelProvider
from src.services.model_assurance.scout import (
    InternalModelClient,
    InternalModelSummary,
    internal_to_bedrock_compatible_summary,
    synthesize_internal_summary,
)


class TestInternalModelClient:
    def test_default_empty(self) -> None:
        c = InternalModelClient()
        assert c.list_models().models == ()

    def test_install_fake_returns_models(self) -> None:
        c = InternalModelClient()
        c.install_fake((
            synthesize_internal_summary(model_id="aura-models/swe-rl-v3"),
            synthesize_internal_summary(model_id="aura-models/swe-rl-v4"),
        ))
        resp = c.list_models()
        ids = [m.model_id for m in resp.models]
        assert ids == ["aura-models/swe-rl-v3", "aura-models/swe-rl-v4"]


class TestInternalSummary:
    def test_synthesise_fields(self) -> None:
        s = synthesize_internal_summary(
            model_id="aura-models/custom-fine-tune",
            base_model="anthropic.claude-3-5-sonnet-20240620-v1:0",
        )
        assert s.model_id == "aura-models/custom-fine-tune"
        assert "claude" in s.base_model

    def test_immutability(self) -> None:
        import pytest
        s = synthesize_internal_summary(model_id="m")
        with pytest.raises((AttributeError, TypeError)):
            s.model_id = "x"  # type: ignore[misc]


class TestAdapterToBedrockShape:
    def test_provider_marked_internal(self) -> None:
        s = synthesize_internal_summary(model_id="aura-models/swe-rl-v3")
        adapted = internal_to_bedrock_compatible_summary(s)
        assert adapted.provider is ModelProvider.INTERNAL

    def test_streaming_supported_default(self) -> None:
        s = synthesize_internal_summary(model_id="m")
        adapted = internal_to_bedrock_compatible_summary(s)
        assert adapted.response_streaming_supported is True
