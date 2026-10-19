"""
Tests for prompt caching in tool-use conversations.

Cache breakpoints go on the last tool (tools + system) and the last block of the latest turn
(the conversation so far), only for models listed as accepting them. If Bedrock rejects
them, the request is retried without and the model is not sent breakpoints again. Cache
writes and reads are priced at 1.25x and 0.1x the input price.
"""

import pytest

from src.config.bedrock_config import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    MODEL_PRICING,
    calculate_cost,
)
from src.services.bedrock_llm_service import (
    BedrockError,
    BedrockLLMService,
    BedrockMode,
)

CACHED_MODEL = "anthropic.claude-sonnet-4-5-20250929-v1:0"
UNCACHED_MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"

TOOLS = [
    {"name": "read_file", "input_schema": {"type": "object"}},
    {"name": "submit_code", "input_schema": {"type": "object"}},
]
MESSAGES = [
    {"role": "user", "content": "Fix the bug"},
    {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "t1", "name": "read_file", "input": {}}],
    },
    {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "code"}],
    },
]


def service_for(model_id, responses):
    """A service on model_id whose Bedrock calls return or raise the given items."""
    service = BedrockLLMService(mode=BedrockMode.MOCK)
    service.mode = BedrockMode.AWS
    service.model_id_primary = model_id
    sent = []
    queue = list(responses)

    def fake_invoke(model, body, apply_guardrails=True):
        sent.append(body)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item, None

    service._invoke_bedrock_messages = fake_invoke
    return service, sent


def reply(cache_write=0, cache_read=0):
    return {
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": cache_write,
            "cache_read_input_tokens": cache_read,
        },
    }


class TestCacheCost:
    def test_cache_writes_and_reads_are_priced(self):
        price = MODEL_PRICING[CACHED_MODEL]["input_per_million"] / 1_000_000
        base = calculate_cost(100, 50, CACHED_MODEL)

        cost = calculate_cost(
            100, 50, CACHED_MODEL, cache_write_tokens=1000, cache_read_tokens=4000
        )

        expected = (
            base
            + (1000 * CACHE_WRITE_MULTIPLIER + 4000 * CACHE_READ_MULTIPLIER) * price
        )
        assert cost == pytest.approx(expected, abs=1e-6)

    def test_reads_are_much_cheaper_than_input(self):
        uncached = calculate_cost(10_000, 0, CACHED_MODEL)
        cached = calculate_cost(0, 0, CACHED_MODEL, cache_read_tokens=10_000)

        assert cached == pytest.approx(uncached * CACHE_READ_MULTIPLIER, rel=1e-3)


class TestBreakpoints:
    def test_marks_the_last_tool_and_the_latest_turn(self):
        service, sent = service_for(CACHED_MODEL, [reply()])

        service.invoke_with_tools(MESSAGES, TOOLS, agent="Coder")

        body = sent[0]
        assert "cache_control" not in body["tools"][0]
        assert body["tools"][-1]["cache_control"] == {"type": "ephemeral"}
        assert body["messages"][-1]["content"][-1]["cache_control"] == {
            "type": "ephemeral"
        }
        assert "cache_control" not in str(body["messages"][:-1])

    def test_callers_messages_and_tools_are_not_modified(self):
        service, _ = service_for(CACHED_MODEL, [reply()])

        service.invoke_with_tools(MESSAGES, TOOLS, agent="Coder")

        assert "cache_control" not in str(MESSAGES) + str(TOOLS)

    def test_text_only_turn_becomes_a_marked_text_block(self):
        service, sent = service_for(CACHED_MODEL, [reply()])

        service.invoke_with_tools([{"role": "user", "content": "hi"}], TOOLS)

        assert sent[0]["messages"][0]["content"] == [
            {"type": "text", "text": "hi", "cache_control": {"type": "ephemeral"}}
        ]

    def test_models_not_listed_get_no_breakpoints(self):
        service, sent = service_for(UNCACHED_MODEL, [reply()])

        service.invoke_with_tools(MESSAGES, TOOLS)

        assert "cache_control" not in str(sent[0])

    def test_caching_can_be_turned_off(self):
        service, sent = service_for(CACHED_MODEL, [reply()])
        service.config = {**service.config, "prompt_caching_enabled": False}

        service.invoke_with_tools(MESSAGES, TOOLS)

        assert "cache_control" not in str(sent[0])


class TestRejectedCaching:
    def test_retries_without_breakpoints_and_remembers(self):
        rejection = BedrockError("Invalid request: cache_control is not supported")
        service, sent = service_for(CACHED_MODEL, [rejection, reply(), reply()])

        first = service.invoke_with_tools(MESSAGES, TOOLS)
        service.invoke_with_tools(MESSAGES, TOOLS)

        assert first["content"][0]["text"] == "ok"
        assert "cache_control" in str(sent[0])
        assert "cache_control" not in str(sent[1])
        assert "cache_control" not in str(sent[2])

    def test_other_errors_are_not_swallowed(self):
        service, _ = service_for(CACHED_MODEL, [BedrockError("Model not found")])

        with pytest.raises(BedrockError, match="Model not found"):
            service.invoke_with_tools(MESSAGES, TOOLS)


class TestCacheUsage:
    def test_result_reports_cache_tokens_and_their_cost(self):
        service, _ = service_for(CACHED_MODEL, [reply(cache_read=8000)])

        result = service.invoke_with_tools(MESSAGES, TOOLS)

        assert result["cache_read_tokens"] == 8000
        assert result["cache_write_tokens"] == 0
        assert result["cost_usd"] == calculate_cost(
            100, 50, CACHED_MODEL, cache_read_tokens=8000
        )

    def test_environments_can_add_cache_models(self, monkeypatch):
        import src.services.bedrock_llm_service as svc

        config = {**svc.get_config(), "prompt_cache_models": ["approved-model"]}
        monkeypatch.setattr(svc, "get_config", lambda: config)

        service = BedrockLLMService(mode=BedrockMode.MOCK)

        assert {"approved-model", CACHED_MODEL} <= service.prompt_cache_models
