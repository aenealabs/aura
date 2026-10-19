"""
Tests that the coder and reviewer use structured output (a forced tool call) when the LLM
client supports tool use, and keep the text path otherwise.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.coder_agent import CODE_SCHEMA, CODE_TOOL, CoderAgent
from src.agents.context_objects import HybridContext
from src.agents.reviewer_agent import REVIEW_SCHEMA, REVIEW_TOOL, ReviewerAgent
from src.services.bedrock_llm_service import StructuredOutputError, schema_problems


def tool_llm(structured=None, error=None, text="x = 1"):
    """An LLM client double that supports tool use."""
    llm = MagicMock()
    llm.supports_tool_use = True
    llm.generate_structured = AsyncMock(return_value=structured, side_effect=error)
    llm.generate = AsyncMock(return_value=text)
    return llm


def context():
    return HybridContext(items=[], query="Fix SQL injection", target_entity="find")


class TestReviewerStructuredOutput:
    @pytest.mark.asyncio
    async def test_review_comes_from_the_tool_call(self):
        llm = tool_llm(
            {
                "status": "FAIL_SECURITY",
                "finding": "SQL built by string concatenation",
                "severity": "Critical",
                "vulnerabilities": [
                    {"type": "SQLI", "line": 4, "description": "f-string"}
                ],
                "recommendations": ["Use parameterized queries"],
            }
        )

        result = await ReviewerAgent(llm_client=llm).review_code("q = f'{x}'")

        assert result["status"] == "FAIL_SECURITY"
        assert result["severity"] == "Critical"
        assert result["vulnerabilities"][0]["line"] == 4
        args = llm.generate_structured.call_args.args
        assert args[1] == REVIEW_TOOL and args[2] is REVIEW_SCHEMA
        llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_text_when_structured_output_fails(self):
        llm = tool_llm(
            error=StructuredOutputError("missing status"),
            text='{"status": "PASS", "finding": "ok"}',
        )

        result = await ReviewerAgent(llm_client=llm).review_code("x = 1")

        assert result["status"] == "PASS"
        llm.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clients_without_tool_use_keep_the_text_path(self):
        llm = MagicMock()  # supports_tool_use is a MagicMock, not True
        llm.generate = AsyncMock(return_value='{"status": "PASS", "finding": "ok"}')

        result = await ReviewerAgent(llm_client=llm).review_code("x = 1")

        assert result["status"] == "PASS"
        llm.generate_structured.assert_not_called()

    def test_schema_requires_a_status(self):
        assert "output is missing status" in schema_problems(
            {"finding": "ok"}, REVIEW_SCHEMA
        )


class TestCoderStructuredOutput:
    @pytest.mark.asyncio
    async def test_code_comes_from_the_tool_call(self):
        code = "def find(conn, email):\n    return conn.execute('SELECT 1 WHERE e = ?', (email,))"
        llm = tool_llm({"code": code, "summary": "Parameterized the query"})

        result = await CoderAgent(llm_client=llm).generate_code(
            context(), "Fix SQL injection"
        )

        assert result["code"] == code
        assert llm.generate_structured.call_args.args[1] == CODE_TOOL
        llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_text_when_structured_output_fails(self):
        llm = tool_llm(
            error=StructuredOutputError("no tool call"), text="```python\ny = 2\n```"
        )

        result = await CoderAgent(llm_client=llm).generate_code(context(), "Task")

        assert result["code"] == "y = 2"

    def test_schema_requires_code(self):
        assert schema_problems({"summary": "x"}, CODE_SCHEMA) == [
            "output is missing code"
        ]
