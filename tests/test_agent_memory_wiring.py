"""
Tests that neural memory guidance (ADR-029 Phase 2.1) reaches the coder and reviewer prompts.

Both agents build memory guidance from NEURAL_MEMORY context items. The default Chain of Draft
templates had no slot for it, and the orchestrator called the reviewer without its context, so
stored experience never reached the model. These tests pin the wiring end to end.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.agent_orchestrator import System2Orchestrator
from src.agents.coder_agent import CoderAgent
from src.agents.context_objects import ContextItem, ContextSource, HybridContext
from src.agents.reviewer_agent import ReviewerAgent
from src.prompts.cod_templates import CoDPromptMode, build_cod_prompt

GUIDANCE = "Past experiences: parameterized the query in UserRepo; tests passed"


def memory_context() -> HybridContext:
    return HybridContext(
        items=[
            ContextItem(
                content=GUIDANCE,
                source=ContextSource.NEURAL_MEMORY,
                confidence=0.9,
            )
        ],
        query="Fix SQL injection",
        target_entity="find_by_email",
    )


class TestBuildCodPromptMemoryGuidance:
    @pytest.mark.parametrize("mode", [CoDPromptMode.COD, CoDPromptMode.COT])
    @pytest.mark.parametrize(
        "agent_type, kwargs",
        [
            ("reviewer", {"code": "x = 1"}),
            ("coder", {"vulnerability": "SQLi", "context": "ctx", "code": "x = 1"}),
            ("coder_initial", {"task": "Add hashing", "context": "ctx"}),
        ],
    )
    def test_guidance_sits_before_the_final_instruction(self, agent_type, kwargs, mode):
        without = build_cod_prompt(agent_type, mode=mode, **kwargs)
        with_memory = build_cod_prompt(
            agent_type, mode=mode, memory_guidance=GUIDANCE, **kwargs
        )

        assert GUIDANCE in with_memory
        # The final instruction is unchanged and still last
        final_instruction = without.rpartition("\n\n")[2]
        assert with_memory.endswith(final_instruction)
        assert with_memory.index(GUIDANCE) < with_memory.rindex(final_instruction)

    @pytest.mark.parametrize(
        "agent_type, kwargs",
        [
            ("coder", {"vulnerability": "SQLi", "context": "ctx", "code": "x = 1"}),
            ("coder_initial", {"task": "Add hashing", "context": "ctx"}),
        ],
    )
    def test_cot_coder_prompt_is_fully_filled(self, agent_type, kwargs):
        """COT_CODER_PROMPT needs task and remediation_note, which the coder does not pass."""
        prompt = build_cod_prompt(agent_type, mode=CoDPromptMode.COT, **kwargs)

        assert "{" not in prompt
        assert "SQLi" in prompt or "Add hashing" in prompt

    def test_no_guidance_leaves_prompt_unchanged(self):
        assert build_cod_prompt("reviewer", code="x = 1", memory_guidance="") == (
            build_cod_prompt("reviewer", code="x = 1")
        )


class TestAgentsSendMemoryToTheModel:
    @pytest.mark.asyncio
    async def test_coder_prompt_includes_memory(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value="def find_by_email(email):\n    return email\n"
        )

        await CoderAgent(llm_client=llm).generate_code(
            memory_context(), "Fix SQL injection"
        )

        assert GUIDANCE in llm.generate.call_args.args[0]

    @pytest.mark.asyncio
    async def test_reviewer_prompt_includes_memory(self):
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value='{"status": "PASS", "finding": "ok", "vulnerabilities": [], '
            '"recommendations": []}'
        )

        await ReviewerAgent(llm_client=llm).review_code("x = 1", memory_context())

        assert GUIDANCE in llm.generate.call_args.args[0]


class TestOrchestratorPassesContextToReviewer:
    @pytest.mark.asyncio
    async def test_execute_request_reviews_with_the_hybrid_context(self):
        orchestrator = System2Orchestrator()
        orchestrator.coder_agent = AsyncMock()
        orchestrator.coder_agent.generate_code.return_value = {"code": "x = 1"}
        orchestrator.reviewer_agent = AsyncMock()
        orchestrator.reviewer_agent.review_code.return_value = {"status": "PASS"}
        orchestrator.validator_agent = AsyncMock()
        orchestrator.validator_agent.validate_code.return_value = {"valid": True}

        await orchestrator.execute_request("Fix SQL injection")

        coder_context = orchestrator.coder_agent.generate_code.call_args.args[0]
        review_args = orchestrator.reviewer_agent.review_code.call_args.args
        assert review_args[1] is coder_context
