"""Tests for the Adapter Registry (ADR-088 Phase 1.2).

Coverage:

* ModelAdapter contract (validation, immutability, cost helpers).
* ModelRequirements.check ordering and conjunctive filtering.
* AdapterRegistry mutation semantics (register / unregister, no
  silent override).
* Built-in seed: Claude 3.5 Sonnet, Claude 3 Haiku, Claude 3 Opus.
* Disqualify / filter_qualified used by the Scout Agent.
"""

from __future__ import annotations

import pytest

from src.services.model_assurance import (
    BUILTIN_ADAPTERS,
    AdapterRegistry,
    DisqualificationReason,
    ModelAdapter,
    ModelArchitecture,
    ModelProvider,
    ModelRequirements,
    TokenizerType,
)


def _make_adapter(
    *,
    model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0",
    provider: ModelProvider = ModelProvider.BEDROCK,
    display_name: str = "Test",
    max_context_tokens: int = 200_000,
    supports_tool_use: bool = True,
    supports_streaming: bool = True,
    tokenizer_type: TokenizerType = TokenizerType.CLAUDE,
    architecture: ModelArchitecture = ModelArchitecture.DENSE,
    cost_per_input_mtok: float = 3.0,
    cost_per_output_mtok: float = 15.0,
    required_prompt_format: str = "claude_messages_v1",
    deprecated: bool = False,
) -> ModelAdapter:
    return ModelAdapter(
        model_id=model_id,
        provider=provider,
        display_name=display_name,
        max_context_tokens=max_context_tokens,
        supports_tool_use=supports_tool_use,
        supports_streaming=supports_streaming,
        tokenizer_type=tokenizer_type,
        architecture=architecture,
        cost_per_input_mtok=cost_per_input_mtok,
        cost_per_output_mtok=cost_per_output_mtok,
        required_prompt_format=required_prompt_format,
        deprecated=deprecated,
    )


# ----------------------------------------------------- ModelAdapter contract


class TestModelAdapterContract:
    def test_basic_construction(self) -> None:
        a = _make_adapter()
        assert a.model_id == "anthropic.claude-3-5-sonnet-20240620-v1:0"
        assert a.provider is ModelProvider.BEDROCK

    def test_is_frozen(self) -> None:
        a = _make_adapter()
        with pytest.raises((AttributeError, TypeError)):
            a.cost_per_input_mtok = 0.0  # type: ignore[misc]

    def test_empty_model_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="model_id"):
            _make_adapter(model_id="")

    def test_zero_context_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_context_tokens"):
            _make_adapter(max_context_tokens=0)

    def test_negative_context_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_context_tokens"):
            _make_adapter(max_context_tokens=-1)

    def test_negative_input_cost_rejected(self) -> None:
        with pytest.raises(ValueError, match="cost"):
            _make_adapter(cost_per_input_mtok=-1.0)

    def test_negative_output_cost_rejected(self) -> None:
        with pytest.raises(ValueError, match="cost"):
            _make_adapter(cost_per_output_mtok=-0.01)

    def test_zero_costs_accepted(self) -> None:
        """Free / internal models can be zero-cost."""
        a = _make_adapter(cost_per_input_mtok=0.0, cost_per_output_mtok=0.0)
        assert a.cost_per_input_mtok == 0.0

    def test_per_token_cost_helpers(self) -> None:
        a = _make_adapter(cost_per_input_mtok=3.0, cost_per_output_mtok=15.0)
        assert a.cost_per_input_token == pytest.approx(3.0e-6)
        assert a.cost_per_output_token == pytest.approx(15.0e-6)

    def test_adapter_is_hashable(self) -> None:
        """Frozen dataclass should be usable as dict key / in sets."""
        a = _make_adapter()
        b = _make_adapter()
        assert hash(a) == hash(b)
        assert {a, b} == {a}


# ----------------------------------------------- ModelRequirements semantics


class TestModelRequirements:
    def test_default_requirements_pass_typical_adapter(self) -> None:
        a = _make_adapter()
        assert ModelRequirements().check(a) == ()

    def test_context_too_small(self) -> None:
        a = _make_adapter(max_context_tokens=8_000)
        reqs = ModelRequirements(min_context_tokens=32_000)
        assert reqs.check(a) == (DisqualificationReason.CONTEXT_TOO_SMALL,)

    def test_context_at_threshold_passes(self) -> None:
        a = _make_adapter(max_context_tokens=32_000)
        reqs = ModelRequirements(min_context_tokens=32_000)
        assert reqs.check(a) == ()

    def test_tool_use_required_but_unsupported(self) -> None:
        a = _make_adapter(supports_tool_use=False)
        reqs = ModelRequirements(require_tool_use=True)
        assert reqs.check(a) == (DisqualificationReason.TOOL_USE_REQUIRED,)

    def test_streaming_required_but_unsupported(self) -> None:
        a = _make_adapter(supports_streaming=False)
        reqs = ModelRequirements(require_streaming=True)
        assert reqs.check(a) == (DisqualificationReason.STREAMING_REQUIRED,)

    def test_provider_not_in_trusted_list(self) -> None:
        a = _make_adapter(provider=ModelProvider.HUGGINGFACE)
        reqs = ModelRequirements(
            trusted_providers=(ModelProvider.BEDROCK,),
        )
        assert reqs.check(a) == (DisqualificationReason.PROVIDER_NOT_TRUSTED,)

    def test_empty_trusted_providers_disables_check(self) -> None:
        """Empty tuple = no provider gate (useful for tests)."""
        a = _make_adapter(provider=ModelProvider.HUGGINGFACE)
        reqs = ModelRequirements(trusted_providers=())
        assert reqs.check(a) == ()

    def test_deprecated_reported_first(self) -> None:
        """Deprecation should fire even when other constraints would also fail."""
        a = _make_adapter(
            deprecated=True,
            max_context_tokens=4_000,  # also fails context
        )
        reqs = ModelRequirements(min_context_tokens=32_000)
        reasons = reqs.check(a)
        assert reasons[0] is DisqualificationReason.MODEL_DEPRECATED
        assert DisqualificationReason.CONTEXT_TOO_SMALL in reasons

    def test_multiple_failures_reported_in_declaration_order(self) -> None:
        a = _make_adapter(
            max_context_tokens=4_000,
            supports_tool_use=False,
            supports_streaming=False,
        )
        reqs = ModelRequirements(
            min_context_tokens=32_000,
            require_tool_use=True,
            require_streaming=True,
        )
        reasons = reqs.check(a)
        assert reasons == (
            DisqualificationReason.CONTEXT_TOO_SMALL,
            DisqualificationReason.TOOL_USE_REQUIRED,
            DisqualificationReason.STREAMING_REQUIRED,
        )

    def test_requirements_default_trusted_providers(self) -> None:
        """Default policy: Bedrock + OpenAI + Google trusted; HF + internal not."""
        reqs = ModelRequirements()
        assert ModelProvider.BEDROCK in reqs.trusted_providers
        assert ModelProvider.OPENAI in reqs.trusted_providers
        assert ModelProvider.GOOGLE in reqs.trusted_providers
        assert ModelProvider.HUGGINGFACE not in reqs.trusted_providers
        assert ModelProvider.INTERNAL not in reqs.trusted_providers


# ----------------------------------------------------- Registry mutation


class TestAdapterRegistryMutation:
    def test_seeded_with_builtins_by_default(self) -> None:
        r = AdapterRegistry()
        assert len(r) == len(BUILTIN_ADAPTERS)
        for a in BUILTIN_ADAPTERS:
            assert a.model_id in r

    def test_seeding_can_be_disabled(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        assert len(r) == 0

    def test_register_new_adapter(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        a = _make_adapter(model_id="custom-1")
        r.register(a)
        assert "custom-1" in r
        assert r.get("custom-1") is a

    def test_register_duplicate_raises(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        a = _make_adapter(model_id="dup")
        r.register(a)
        with pytest.raises(ValueError, match="already registered"):
            r.register(_make_adapter(model_id="dup"))

    def test_unregister_returns_adapter(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        a = _make_adapter(model_id="bye")
        r.register(a)
        removed = r.unregister("bye")
        assert removed is a
        assert "bye" not in r

    def test_unregister_unknown_raises(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        with pytest.raises(KeyError):
            r.unregister("never-existed")

    def test_replace_adapter_via_unregister(self) -> None:
        """Re-registering requires explicit unregister first — no silent override."""
        r = AdapterRegistry(seed_builtins=False)
        v1 = _make_adapter(model_id="m", cost_per_input_mtok=1.0)
        r.register(v1)
        with pytest.raises(ValueError):
            r.register(_make_adapter(model_id="m", cost_per_input_mtok=2.0))
        r.unregister("m")
        v2 = _make_adapter(model_id="m", cost_per_input_mtok=2.0)
        r.register(v2)
        assert r.get("m").cost_per_input_mtok == 2.0


# ----------------------------------------------------- Registry queries


class TestAdapterRegistryQueries:
    def test_get_unknown_raises(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        with pytest.raises(KeyError):
            r.get("missing")

    def test_find_returns_none_for_unknown(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        assert r.find("missing") is None

    def test_list_adapters_returns_registration_order(self) -> None:
        r = AdapterRegistry()
        listed = r.list_adapters()
        assert tuple(a.model_id for a in listed) == tuple(
            a.model_id for a in BUILTIN_ADAPTERS
        )

    def test_list_adapters_filter_by_provider(self) -> None:
        r = AdapterRegistry()
        bedrock = r.list_adapters(provider=ModelProvider.BEDROCK)
        openai = r.list_adapters(provider=ModelProvider.OPENAI)
        assert len(bedrock) == len(BUILTIN_ADAPTERS)  # all builtins are Bedrock
        assert len(openai) == 0

    def test_list_adapters_excludes_deprecated_by_default(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        r.register(_make_adapter(model_id="live", deprecated=False))
        r.register(_make_adapter(model_id="dead", deprecated=True))
        live_only = r.list_adapters()
        all_ = r.list_adapters(include_deprecated=True)
        assert tuple(a.model_id for a in live_only) == ("live",)
        assert {a.model_id for a in all_} == {"live", "dead"}

    def test_contains_string_only(self) -> None:
        r = AdapterRegistry()
        assert "anthropic.claude-3-haiku-20240307-v1:0" in r
        assert 42 not in r  # type: ignore[operator]


# ------------------------------------------- disqualify / filter_qualified


class TestDisqualifyAndFilter:
    def test_disqualify_with_adapter_object(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        a = _make_adapter(supports_tool_use=False)
        reasons = r.disqualify(a, ModelRequirements(require_tool_use=True))
        assert reasons == (DisqualificationReason.TOOL_USE_REQUIRED,)

    def test_disqualify_with_string_id(self) -> None:
        r = AdapterRegistry()
        reasons = r.disqualify(
            "anthropic.claude-3-5-sonnet-20240620-v1:0",
            ModelRequirements(min_context_tokens=8_000),
        )
        assert reasons == ()

    def test_disqualify_unknown_string_raises(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        with pytest.raises(KeyError):
            r.disqualify("missing", ModelRequirements())

    def test_filter_qualified_against_registry(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        good = _make_adapter(model_id="good", max_context_tokens=200_000)
        bad = _make_adapter(model_id="bad", max_context_tokens=4_000)
        r.register(good)
        r.register(bad)
        reqs = ModelRequirements(min_context_tokens=32_000)
        qualified = r.filter_qualified(None, reqs)
        assert tuple(a.model_id for a in qualified) == ("good",)

    def test_filter_qualified_against_explicit_pool(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        a1 = _make_adapter(model_id="a1")
        a2 = _make_adapter(model_id="a2", supports_tool_use=False)
        reqs = ModelRequirements(require_tool_use=True)
        # Pool overrides the registry contents.
        qualified = r.filter_qualified((a1, a2), reqs)
        assert tuple(a.model_id for a in qualified) == ("a1",)

    def test_filter_qualified_with_empty_pool_returns_empty(self) -> None:
        r = AdapterRegistry(seed_builtins=False)
        assert r.filter_qualified((), ModelRequirements()) == ()


# ----------------------------------------------------- Built-in seed


class TestBuiltinAdapters:
    def test_three_builtins_present(self) -> None:
        assert len(BUILTIN_ADAPTERS) == 3

    def test_includes_claude_35_sonnet(self) -> None:
        ids = {a.model_id for a in BUILTIN_ADAPTERS}
        assert "anthropic.claude-3-5-sonnet-20240620-v1:0" in ids

    def test_includes_claude_3_haiku(self) -> None:
        ids = {a.model_id for a in BUILTIN_ADAPTERS}
        assert "anthropic.claude-3-haiku-20240307-v1:0" in ids

    def test_includes_claude_3_opus(self) -> None:
        ids = {a.model_id for a in BUILTIN_ADAPTERS}
        assert "anthropic.claude-3-opus-20240229-v1:0" in ids

    def test_all_builtins_are_bedrock(self) -> None:
        for a in BUILTIN_ADAPTERS:
            assert a.provider is ModelProvider.BEDROCK, (
                f"Phase 1 v1 scope is Bedrock-only per ADR-088 condition #12; "
                f"{a.model_id} declared {a.provider.value}"
            )

    def test_all_builtins_support_tool_use(self) -> None:
        for a in BUILTIN_ADAPTERS:
            assert a.supports_tool_use is True

    def test_all_builtins_have_200k_context(self) -> None:
        for a in BUILTIN_ADAPTERS:
            assert a.max_context_tokens == 200_000

    def test_no_builtin_is_deprecated(self) -> None:
        for a in BUILTIN_ADAPTERS:
            assert a.deprecated is False

    def test_haiku_is_cheapest(self) -> None:
        haiku = next(
            a
            for a in BUILTIN_ADAPTERS
            if a.model_id == "anthropic.claude-3-haiku-20240307-v1:0"
        )
        for other in BUILTIN_ADAPTERS:
            if other is haiku:
                continue
            assert haiku.cost_per_input_mtok < other.cost_per_input_mtok
            assert haiku.cost_per_output_mtok < other.cost_per_output_mtok

    def test_opus_is_most_expensive(self) -> None:
        opus = next(
            a
            for a in BUILTIN_ADAPTERS
            if a.model_id == "anthropic.claude-3-opus-20240229-v1:0"
        )
        for other in BUILTIN_ADAPTERS:
            if other is opus:
                continue
            assert opus.cost_per_input_mtok >= other.cost_per_input_mtok
            assert opus.cost_per_output_mtok >= other.cost_per_output_mtok
