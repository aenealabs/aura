"""
Tests for Bedrock model discovery and per-model request rules.

Tiers left on "auto" resolve at startup (AWS mode) to the newest active, priced Claude model
of the tier's family, through an inference profile when the model is not on demand. Pinned
models win. Requests are shaped for each model: newer models reject sampling parameters
and forced tool_choice, and a 400 naming a field teaches the service to drop it.
"""

from unittest.mock import MagicMock

import pytest

import src.services.bedrock_llm_service as svc
from src.config.bedrock_config import get_model_pricing, has_pricing
from src.services.bedrock_llm_service import (
    MODEL_IDS,
    BedrockError,
    BedrockLLMService,
    BedrockMode,
    ModelTier,
    _adapt_request,
    _rejected_field,
    model_request_rules,
)
from src.services.bedrock_model_discovery import (
    discover_tier_models,
    parse_claude_model,
)


def summary(model_id, types=("ON_DEMAND",), status="ACTIVE"):
    return {
        "modelId": model_id,
        "inferenceTypesSupported": list(types),
        "modelLifecycle": {"status": status},
    }


def profile(profile_id, model_id):
    arn = f"arn:aws:bedrock:us-east-1::foundation-model/{model_id}"
    return {
        "inferenceProfileId": profile_id,
        "status": "ACTIVE",
        "models": [{"modelArn": arn}],
    }


def fake_bedrock(summaries, profiles=()):
    client = MagicMock()
    client.list_foundation_models.return_value = {"modelSummaries": list(summaries)}
    client.list_inference_profiles.return_value = {
        "inferenceProfileSummaries": list(profiles)
    }
    return client


class TestParseClaudeModel:
    @pytest.mark.parametrize(
        "model_id, family, version, date",
        [
            ("anthropic.claude-sonnet-4-5-20250929-v1:0", "sonnet", (4, 5), "20250929"),
            (
                "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "sonnet",
                (4, 5),
                "20250929",
            ),
            ("anthropic.claude-sonnet-4-20250514-v1:0", "sonnet", (4, 0), "20250514"),
            ("anthropic.claude-opus-5-5", "opus", (5, 5), ""),
            ("global.anthropic.claude-opus-5", "opus", (5, 0), ""),
            ("anthropic.claude-haiku-4-5-20251001-v1:0", "haiku", (4, 5), "20251001"),
            ("anthropic.claude-3-5-sonnet-20240620-v1:0", "sonnet", (3, 5), "20240620"),
            ("anthropic.claude-3-haiku-20240307-v1:0", "haiku", (3, 0), "20240307"),
        ],
    )
    def test_parses_current_and_older_ids(self, model_id, family, version, date):
        parsed = parse_claude_model(model_id)

        assert (parsed.family, parsed.version, parsed.date) == (family, version, date)

    def test_non_claude_models_are_ignored(self):
        assert parse_claude_model("amazon.titan-text-express-v1") is None


class TestDiscovery:
    def test_picks_the_newest_active_priced_model_per_tier(self):
        client = fake_bedrock(
            [
                summary("anthropic.claude-3-5-sonnet-20240620-v1:0", status="LEGACY"),
                summary("anthropic.claude-sonnet-4-5-20250929-v1:0"),
                summary("anthropic.claude-sonnet-5-5"),
                summary("anthropic.claude-haiku-4-5-20251001-v1:0"),
                summary("anthropic.claude-opus-5-5"),
                summary("anthropic.claude-opus-4-1-20250805-v1:0"),
                summary("anthropic.claude-fable-5-1"),
            ]
        )

        found = discover_tier_models(client, "us-east-1", has_pricing)

        assert found == {
            "fast": "anthropic.claude-haiku-4-5-20251001-v1:0",
            "accurate": "anthropic.claude-sonnet-5-5",
            "maximum": "anthropic.claude-opus-5-5",
        }

    def test_uses_the_regions_inference_profile_when_not_on_demand(self):
        model = "anthropic.claude-sonnet-4-5-20250929-v1:0"
        client = fake_bedrock(
            [summary(model, types=("INFERENCE_PROFILE",))],
            [
                profile(f"global.{model}", model),
                profile(f"eu.{model}", model),
                profile(f"us.{model}", model),
            ],
        )

        assert discover_tier_models(client, "us-east-1", has_pricing) == {
            "accurate": f"us.{model}"
        }
        assert discover_tier_models(client, "ap-southeast-2", has_pricing) == {
            "accurate": f"global.{model}"
        }

    def test_skips_unpriced_and_uninvocable_models(self):
        client = fake_bedrock(
            [
                summary("anthropic.claude-opus-4-1-20250805-v1:0"),  # no known pricing
                summary("anthropic.claude-opus-5-5", types=("PROVISIONED",)),
                summary(
                    "anthropic.claude-opus-5", types=("INFERENCE_PROFILE",)
                ),  # no profile
            ]
        )

        assert discover_tier_models(client, "us-east-1", has_pricing) == {}

    def test_follows_inference_profile_pages(self):
        model = "anthropic.claude-haiku-4-5-20251001-v1:0"
        client = fake_bedrock([summary(model, types=("INFERENCE_PROFILE",))])
        client.list_inference_profiles.side_effect = [
            {"inferenceProfileSummaries": [], "nextToken": "page-2"},
            {"inferenceProfileSummaries": [profile(f"us.{model}", model)]},
        ]

        assert discover_tier_models(client, "us-east-1", has_pricing) == {
            "fast": f"us.{model}"
        }


class TestServiceDiscovery:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        svc._DISCOVERY_CACHE.clear()
        yield
        svc._DISCOVERY_CACHE.clear()

    def aws_service(self, monkeypatch, client, config_overrides=None):
        """A service in AWS mode whose Bedrock control-plane client is `client`."""
        config = {**svc.get_config(), **(config_overrides or {})}
        monkeypatch.setattr(svc, "get_config", lambda: config)
        monkeypatch.setattr(svc.boto3, "client", lambda name, **kw: client)
        monkeypatch.setattr(BedrockLLMService, "_init_aws_clients", _fake_aws_init)
        return BedrockLLMService(mode=BedrockMode.AWS)

    def test_auto_tiers_and_primary_use_discovered_models(self, monkeypatch):
        client = fake_bedrock(
            [
                summary("anthropic.claude-sonnet-5-5"),
                summary("anthropic.claude-opus-5-5"),
            ]
        )

        service = self.aws_service(monkeypatch, client)

        assert service.model_tiers[ModelTier.ACCURATE] == "anthropic.claude-sonnet-5-5"
        assert service.model_tiers[ModelTier.MAXIMUM] == "anthropic.claude-opus-5-5"
        assert service.model_tiers[ModelTier.FAST] == MODEL_IDS[ModelTier.FAST]
        assert service.model_id_primary == "anthropic.claude-sonnet-5-5"

    def test_pinned_models_are_never_replaced(self, monkeypatch):
        client = fake_bedrock([summary("anthropic.claude-sonnet-5-5")])
        pinned = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

        service = self.aws_service(
            monkeypatch,
            client,
            {"model_id_accurate": pinned, "model_id_primary": pinned},
        )

        assert service.model_tiers[ModelTier.ACCURATE] == pinned
        assert service.model_id_primary == pinned

    def test_discovery_failure_falls_back_to_built_in_defaults(self, monkeypatch):
        client = MagicMock()
        client.list_foundation_models.side_effect = PermissionError("AccessDenied")

        service = self.aws_service(monkeypatch, client)

        assert service.model_tiers == MODEL_IDS

    def test_mock_mode_never_calls_bedrock(self, monkeypatch):
        def no_client(*args, **kwargs):
            raise AssertionError("mock mode must not create AWS clients")

        monkeypatch.setattr(svc.boto3, "client", no_client)

        service = BedrockLLMService(mode=BedrockMode.MOCK)

        assert service.model_tiers == MODEL_IDS


def _fake_aws_init(self):
    """Stand-in for _init_aws_clients: AWS mode without real AWS clients."""
    self.model_id_primary = self.config["model_id_primary"]
    self.model_id_fallback = self.config["model_id_fallback"]


class TestFamilyPricing:
    def test_inference_profile_ids_are_priced_by_family(self):
        assert get_model_pricing("us.anthropic.claude-sonnet-5-5") == {
            "input_per_million": 2.0,
            "output_per_million": 10.0,
        }

    def test_exact_entries_win(self):
        assert get_model_pricing("anthropic.claude-3-haiku-20240307-v1:0")[
            "input_per_million"
        ] == pytest.approx(0.25)


class TestRequestRules:
    @pytest.mark.parametrize(
        "model_id, rules",
        [
            ("anthropic.claude-sonnet-5-5", {"no_sampling", "no_forced_tool_choice"}),
            ("anthropic.claude-opus-5-5", {"no_sampling", "no_forced_tool_choice"}),
            ("anthropic.claude-opus-4-8", {"no_sampling"}),
            ("us.anthropic.claude-sonnet-4-5-20250929-v1:0", set()),
            ("anthropic.claude-haiku-4-5-20251001-v1:0", set()),
            ("anthropic.claude-fable-5-1", {"no_sampling", "no_forced_tool_choice"}),
        ],
    )
    def test_known_rules_by_model(self, model_id, rules):
        assert model_request_rules(model_id) == rules

    def test_adapt_drops_sampling_and_relaxes_tool_choice(self):
        body = {
            "temperature": 0.7,
            "top_p": 0.9,
            "tool_choice": {"type": "tool", "name": "x"},
        }

        adapted = _adapt_request(body, {"no_sampling", "no_forced_tool_choice"})

        assert adapted == {"tool_choice": {"type": "auto"}}
        assert body["temperature"] == 0.7  # the caller's body is unchanged

    @pytest.mark.parametrize(
        "message, rule",
        [
            (
                "Invalid request: temperature is not supported for this model",
                "no_sampling",
            ),
            (
                "Invalid request: tool_choice of type 'any' is not supported",
                "no_forced_tool_choice",
            ),
            ("Invalid request: cache_control is not permitted", "no_cache"),
            ("Model not found", None),
        ],
    )
    def test_rejected_field_classification(self, message, rule):
        assert _rejected_field(message) == rule


class TestAdaptiveSend:
    def service(self, model_id, responses):
        service = BedrockLLMService(mode=BedrockMode.MOCK)
        service.mode = BedrockMode.AWS
        service.model_id_primary = model_id
        sent, queue = [], list(responses)

        def fake_invoke(model, body, apply_guardrails=True):
            sent.append(body)
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item, None

        service._invoke_bedrock_messages = fake_invoke
        return service, sent

    def ok(self):
        return {
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

    def test_newer_models_get_no_temperature(self):
        service, sent = self.service("anthropic.claude-sonnet-5-5", [self.ok()])

        service.invoke_model("Review this", agent="Reviewer", cache_enabled=False)

        assert "temperature" not in sent[0]

    def test_older_models_keep_temperature(self):
        service, sent = self.service(
            "us.anthropic.claude-sonnet-4-5-20250929-v1:0", [self.ok()]
        )

        service.invoke_model("Review this", agent="Reviewer", cache_enabled=False)

        assert "temperature" in sent[0]

    def test_learns_from_a_rejected_field_and_remembers(self):
        model = "anthropic.claude-haiku-4-5-20251001-v1:0"
        rejection = BedrockError("Invalid request: temperature: not supported")
        service, sent = self.service(model, [rejection, self.ok(), self.ok()])

        service.invoke_model("one", agent="A", cache_enabled=False)
        service.invoke_model("two", agent="A", cache_enabled=False)

        assert "temperature" in sent[0]
        assert "temperature" not in sent[1]
        assert "temperature" not in sent[2]

    def test_forced_tool_choice_becomes_auto_on_newer_models(self):
        service, sent = self.service("anthropic.claude-opus-5-5", [self.ok()])

        service.invoke_with_tools(
            [{"role": "user", "content": "hi"}],
            [{"name": "report", "input_schema": {"type": "object"}}],
            tool_choice={"type": "tool", "name": "report"},
        )

        assert sent[0]["tool_choice"] == {"type": "auto"}

    def test_text_after_a_thinking_block_is_returned(self):
        reply = {
            "content": [
                {"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "text", "text": "the answer"},
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        service, _ = self.service("anthropic.claude-sonnet-5-5", [reply])

        result = service.invoke_model("q", agent="A", cache_enabled=False)

        assert result["response"] == "the answer"


class TestEnvironmentPins:
    def test_env_pin_wins_over_discovery_for_auto_tiers(self, monkeypatch):
        monkeypatch.setenv(
            "AURA_MODEL_ACCURATE", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )

        tiers = svc.resolve_model_tiers(
            {}, discovered={"accurate": "anthropic.claude-sonnet-5-5"}
        )

        assert (
            tiers[ModelTier.ACCURATE] == "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )

    def test_auto_env_value_is_ignored(self, monkeypatch):
        monkeypatch.setenv("AURA_MODEL_FAST", "auto")

        assert svc.resolve_model_tiers({})[ModelTier.FAST] == MODEL_IDS[ModelTier.FAST]

    def test_configured_models_still_win_over_env_pins(self, monkeypatch):
        monkeypatch.setenv("AURA_MODEL_MAXIMUM", "anthropic.claude-opus-5-5")

        tiers = svc.resolve_model_tiers(
            {"model_id_maximum": "anthropic.claude-opus-4-8"}
        )

        assert tiers[ModelTier.MAXIMUM] == "anthropic.claude-opus-4-8"
