"""
Tests for tool use and structured output in BedrockLLMService.

invoke_with_tools sends one Messages API turn with tools under the same controls as text
calls (prompt screening, budget, rate limit, guardrails, cost). generate_structured forces a
single tool call and returns its validated input, replacing "reply in JSON" prompts.
"""

import json
from unittest.mock import MagicMock

import pytest

from src.services.bedrock_llm_service import (
    BedrockLLMService,
    BedrockMode,
    BudgetExceededError,
    StructuredOutputError,
    schema_problems,
)
from src.services.llm_prompt_sanitizer import SanitizationAction

REVIEW_SCHEMA = {
    "type": "object",
    "required": ["status", "finding"],
    "properties": {
        "status": {"type": "string", "enum": ["PASS", "FAIL_SECURITY"]},
        "finding": {"type": "string"},
        "vulnerabilities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["description"],
                "properties": {
                    "description": {"type": "string"},
                    "line": {"type": "integer"},
                },
            },
        },
    },
}


def aws_service(response_content, stop_reason="tool_use"):
    """A service whose Bedrock call returns the given content blocks."""
    service = BedrockLLMService(mode=BedrockMode.MOCK)
    service.mode = BedrockMode.AWS
    sent = {}

    def fake_invoke(model_id, request_body, apply_guardrails=True):
        sent["model_id"] = model_id
        sent["body"] = request_body
        return (
            {
                "content": response_content,
                "stop_reason": stop_reason,
                "usage": {"input_tokens": 120, "output_tokens": 40},
            },
            None,
        )

    service._invoke_bedrock_messages = fake_invoke
    return service, sent


class TestSchemaProblems:
    def test_valid_data_has_no_problems(self):
        data = {
            "status": "FAIL_SECURITY",
            "finding": "SQL built by string concatenation",
            "vulnerabilities": [{"description": "f-string SQL", "line": 12}],
        }

        assert schema_problems(data, REVIEW_SCHEMA) == []

    def test_reports_missing_fields_bad_enums_and_types(self):
        data = {"status": "MAYBE", "vulnerabilities": [{"line": "twelve"}]}

        problems = schema_problems(data, REVIEW_SCHEMA)

        assert "output is missing finding" in problems
        assert any("status should be one of" in p for p in problems)
        assert "vulnerabilities[0] is missing description" in problems
        assert "vulnerabilities[0].line should be integer" in problems

    def test_booleans_are_not_numbers(self):
        assert schema_problems(True, {"type": "integer"}) == [
            "output should be integer"
        ]


class TestGenerateStructured:
    @pytest.mark.asyncio
    async def test_returns_the_tool_input(self):
        review = {"status": "PASS", "finding": "No issues"}
        service, sent = aws_service(
            [{"type": "tool_use", "id": "t1", "name": "report_review", "input": review}]
        )

        result = await service.generate_structured(
            "Review this code", "report_review", REVIEW_SCHEMA, "Report the review"
        )

        assert result == review
        assert sent["body"]["tool_choice"] == {"type": "tool", "name": "report_review"}
        assert sent["body"]["tools"][0]["input_schema"] == REVIEW_SCHEMA

    @pytest.mark.asyncio
    async def test_rejects_output_that_does_not_match_the_schema(self):
        service, _ = aws_service(
            [{"type": "tool_use", "id": "t1", "name": "report_review", "input": {}}]
        )

        with pytest.raises(StructuredOutputError, match="missing status"):
            await service.generate_structured(
                "Review", "report_review", REVIEW_SCHEMA, "Report the review"
            )

    @pytest.mark.asyncio
    async def test_rejects_a_text_answer(self):
        service, _ = aws_service(
            [{"type": "text", "text": "{}"}], stop_reason="end_turn"
        )

        with pytest.raises(StructuredOutputError, match="did not call report_review"):
            await service.generate_structured(
                "Review", "report_review", REVIEW_SCHEMA, "Report the review"
            )


class TestInvokeWithTools:
    def test_screens_the_agents_text_but_not_tool_results(self):
        service, sent = aws_service([{"type": "text", "text": "done"}], "end_turn")
        service.sanitize_prompts = True
        service.prompt_sanitizer = MagicMock()
        service.prompt_sanitizer.sanitize.return_value = MagicMock(
            action=SanitizationAction.SANITIZED,
            was_modified=True,
            sanitized_prompt="[screened]",
        )
        messages = [
            {"role": "user", "content": "Fix the bug"},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "file text",
                    },
                    {"type": "text", "text": "Now patch it"},
                ],
            },
        ]

        service.invoke_with_tools(messages, [], agent="Coder")

        body_messages = sent["body"]["messages"]
        assert body_messages[0]["content"] == "[screened]"
        assert body_messages[1]["content"][0]["content"] == "file text"
        assert body_messages[1]["content"][1]["text"] == "[screened]"

    def test_records_cost_and_returns_usage(self):
        service, _ = aws_service([{"type": "text", "text": "done"}], "end_turn")
        service._record_cost = MagicMock()

        result = service.invoke_with_tools(
            [{"role": "user", "content": "hi"}], [], agent="Coder"
        )

        assert result["input_tokens"] == 120
        assert result["output_tokens"] == 40
        assert result["cost_usd"] > 0
        service._record_cost.assert_called_once()

    def test_respects_the_budget(self):
        service, sent = aws_service([], "end_turn")
        service._check_budget = MagicMock(return_value=False)

        with pytest.raises(BudgetExceededError):
            service.invoke_with_tools([{"role": "user", "content": "hi"}], [])
        assert sent == {}

    def test_mock_mode_calls_a_forced_tool(self):
        service = BedrockLLMService(mode=BedrockMode.MOCK)

        result = service.invoke_with_tools(
            [{"role": "user", "content": "hi"}],
            [{"name": "report_review", "input_schema": {"type": "object"}}],
            tool_choice={"type": "tool", "name": "report_review"},
        )

        assert result["stop_reason"] == "tool_use"
        assert result["content"][0]["name"] == "report_review"
        assert json.dumps(result["content"])  # serializable for the next turn

    def test_service_advertises_tool_use(self):
        assert BedrockLLMService(mode=BedrockMode.MOCK).supports_tool_use is True
