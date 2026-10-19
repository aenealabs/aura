"""
Tests for configuration-driven model tiers (ADR-015 tiers, ADR-088 safe upgrades).

Tier models come from the deployment's configuration (Secrets Manager overrides the
environment config, which overrides the code defaults), so an approved model upgrade or a
rollback is a config change. With no configuration the defaults are unchanged.
"""

import pytest

from src.config.bedrock_config import MODEL_PRICING, register_model_pricing
from src.services.bedrock_llm_service import (
    MODEL_IDS,
    BedrockLLMService,
    BedrockMode,
    ModelTier,
    get_model_for_operation,
    resolve_model_tiers,
)


@pytest.fixture
def priced_model():
    """A model approved with its pricing, removed again after the test."""
    model_id = "approved-fast"
    register_model_pricing(
        {model_id: {"input_per_million": 1.0, "output_per_million": 5.0}}
    )
    yield model_id
    MODEL_PRICING.pop(model_id, None)


class TestResolveModelTiers:
    def test_defaults_when_nothing_is_configured(self):
        assert resolve_model_tiers({}) == MODEL_IDS

    def test_config_overrides_defaults(self):
        tiers = resolve_model_tiers({"model_id_accurate": "config-accurate"})

        assert tiers[ModelTier.ACCURATE] == "config-accurate"
        assert tiers[ModelTier.FAST] == MODEL_IDS[ModelTier.FAST]

    def test_secrets_override_config(self):
        tiers = resolve_model_tiers(
            {"model_id_fast": "config-fast"}, {"model_id_fast": "approved-fast"}
        )

        assert tiers[ModelTier.FAST] == "approved-fast"

    def test_empty_override_falls_through(self):
        tiers = resolve_model_tiers(
            {"model_id_maximum": "config-max"}, {"model_id_maximum": ""}
        )

        assert tiers[ModelTier.MAXIMUM] == "config-max"


class TestModelSelection:
    def test_operation_routing_uses_the_given_map(self):
        tiers = {**MODEL_IDS, ModelTier.FAST: "approved-fast"}

        tier, model_id = get_model_for_operation("query_intent_analysis", tiers)

        assert tier == ModelTier.FAST
        assert model_id == "approved-fast"

    def test_operation_routing_defaults_to_code_defaults(self):
        assert get_model_for_operation("query_intent_analysis") == (
            ModelTier.FAST,
            MODEL_IDS[ModelTier.FAST],
        )

    def test_service_resolves_tiers_at_startup(self):
        service = BedrockLLMService(mode=BedrockMode.MOCK)

        assert service.model_tiers == resolve_model_tiers(service.config)

    def test_service_calls_use_the_configured_tier_model(self, priced_model):
        service = BedrockLLMService(mode=BedrockMode.MOCK)
        service.model_tiers = {**MODEL_IDS, ModelTier.FAST: priced_model}

        by_operation = service.invoke_model(
            "Classify this file", agent="Test", operation="file_type_classification"
        )
        by_tier = service.invoke_model(
            "Classify this file", agent="Test", override_tier=ModelTier.FAST
        )

        assert by_operation["model"] == priced_model
        assert by_tier["model"] == priced_model


class TestPricingSafety:
    def test_unpriced_model_is_refused(self):
        tiers = resolve_model_tiers(
            {"model_id_fast": "unpriced-model"}, is_priced=lambda m: m in MODEL_PRICING
        )

        assert tiers[ModelTier.FAST] == MODEL_IDS[ModelTier.FAST]

    def test_priced_model_is_applied(self, priced_model):
        tiers = resolve_model_tiers(
            {"model_id_fast": priced_model}, is_priced=lambda m: m in MODEL_PRICING
        )

        assert tiers[ModelTier.FAST] == priced_model

    def test_register_model_pricing_skips_incomplete_entries(self):
        registered = register_model_pricing(
            {
                "half-priced": {"input_per_million": 1.0},
                "bad": {"input_per_million": "x"},
            }
        )

        assert registered == []
        assert "half-priced" not in MODEL_PRICING

    def test_service_registers_pricing_and_applies_the_model(self, monkeypatch):
        import src.services.bedrock_llm_service as svc

        config = {
            **svc.get_config(),
            "model_id_maximum": "approved-max",
            "model_pricing": {
                "approved-max": {"input_per_million": 5.0, "output_per_million": 25.0}
            },
        }
        monkeypatch.setattr(svc, "get_config", lambda: config)
        try:
            service = BedrockLLMService(mode=BedrockMode.MOCK)
            assert service.model_tiers[ModelTier.MAXIMUM] == "approved-max"
        finally:
            MODEL_PRICING.pop("approved-max", None)
