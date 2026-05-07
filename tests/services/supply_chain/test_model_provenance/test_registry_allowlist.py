"""Tests for the registry allowlist (ADR-088 Phase 2.1)."""

from __future__ import annotations

from src.services.supply_chain.model_provenance import (
    DEFAULT_BEDROCK_PROVIDERS,
    DEFAULT_INTERNAL_ECR_PATTERN,
    ModelArtifact,
    ModelRegistry,
    RegistryAllowlist,
    default_allowlist,
)


def _digest() -> str:
    return "a" * 64


def _bedrock(provider: str = "anthropic", model_id: str = "m1") -> ModelArtifact:
    return ModelArtifact(
        model_id=model_id,
        provider=provider,
        registry=ModelRegistry.BEDROCK,
        weights_digest=_digest(),
    )


def _ecr(model_id: str) -> ModelArtifact:
    return ModelArtifact(
        model_id=model_id,
        provider="aura",
        registry=ModelRegistry.INTERNAL_ECR,
        weights_digest=_digest(),
    )


def _hf(model_id: str) -> ModelArtifact:
    return ModelArtifact(
        model_id=model_id,
        provider="huggingface",
        registry=ModelRegistry.HUGGINGFACE_CURATED,
        weights_digest=_digest(),
    )


class TestBedrockAllowlist:
    def test_anthropic_allowed(self) -> None:
        decision = default_allowlist().check(_bedrock("anthropic"))
        assert decision.allowed is True
        assert decision.matched_entry is not None

    def test_amazon_allowed(self) -> None:
        decision = default_allowlist().check(_bedrock("amazon"))
        assert decision.allowed is True

    def test_meta_allowed(self) -> None:
        decision = default_allowlist().check(_bedrock("meta"))
        assert decision.allowed is True

    def test_unknown_provider_rejected(self) -> None:
        decision = default_allowlist().check(_bedrock("rogue-provider"))
        assert decision.allowed is False
        assert "rogue-provider" in decision.reason

    def test_provider_match_is_case_insensitive(self) -> None:
        decision = default_allowlist().check(_bedrock("Anthropic"))
        assert decision.allowed is True


class TestInternalECRAllowlist:
    def test_pattern_match_allowed(self) -> None:
        decision = default_allowlist().check(_ecr("aura-models/swe-rl-v3"))
        assert decision.allowed is True

    def test_pattern_mismatch_rejected(self) -> None:
        decision = default_allowlist().check(_ecr("random-models/v1"))
        assert decision.allowed is False
        assert "pattern" in decision.reason

    def test_default_pattern_is_aura_models(self) -> None:
        assert DEFAULT_INTERNAL_ECR_PATTERN == "aura-models/"


class TestHuggingFaceAllowlist:
    def test_empty_default_rejects_all(self) -> None:
        decision = default_allowlist().check(_hf("meta-llama/CodeLlama-34b-Instruct"))
        assert decision.allowed is False

    def test_with_entry_allows_exact_match(self) -> None:
        allowlist = default_allowlist().with_huggingface_entry(
            "meta-llama/CodeLlama-34b-Instruct",
            description="approved by security review 2026-05",
        )
        decision = allowlist.check(_hf("meta-llama/CodeLlama-34b-Instruct"))
        assert decision.allowed is True

    def test_with_entry_does_not_match_close_repo(self) -> None:
        allowlist = default_allowlist().with_huggingface_entry(
            "meta-llama/CodeLlama-34b-Instruct"
        )
        decision = allowlist.check(_hf("meta-llama/CodeLlama-13b-Instruct"))
        assert decision.allowed is False

    def test_with_entry_returns_new_allowlist(self) -> None:
        original = default_allowlist()
        extended = original.with_huggingface_entry("foo/bar")
        # original unchanged
        assert original.huggingface_allowlist == ()
        assert len(extended.huggingface_allowlist) == 1


class TestDefaultsCount:
    def test_three_default_bedrock_providers(self) -> None:
        assert len(DEFAULT_BEDROCK_PROVIDERS) == 3

    def test_default_allowlist_returns_fresh_instance(self) -> None:
        a = default_allowlist()
        b = default_allowlist()
        assert a == b
