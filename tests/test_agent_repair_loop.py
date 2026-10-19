"""
Tests for the coder's repair loop: validation and sandbox failures go back to the coder.

A patch must pass both the security review and validation within the attempt budget; failed
validation issues become remediation context for the next attempt. In the HITL workflow, a
patch that fails its sandbox tests gets repair runs that see the failing tests.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.agent_orchestrator import (
    AgentCheckpoint,
    System2Orchestrator,
    WorkflowPhase,
)
from src.agents.context_objects import ContextSource
from tests.test_agent_orchestrator import (
    _FakeSandboxOrchestrator,
    _hitl_ready_orchestrator,
)

INVALID = {
    "valid": False,
    "syntax_valid": True,
    "structure_valid": False,
    "security_valid": True,
    "issues": [
        {"type": "MISSING_ELEMENT", "line": 3, "message": "find_by_email not defined"}
    ],
}
VALID = {"valid": True, "issues": []}


def orchestrator_with(validation_results, attempts=3):
    orchestrator = System2Orchestrator(max_remediation_attempts=attempts)
    orchestrator.coder_agent = AsyncMock()
    orchestrator.coder_agent.generate_code.return_value = {"code": "x = 1"}
    orchestrator.reviewer_agent = AsyncMock()
    orchestrator.reviewer_agent.review_code.return_value = {"status": "PASS"}
    orchestrator.validator_agent = AsyncMock()
    orchestrator.validator_agent.validate_code.side_effect = validation_results
    return orchestrator


def remediation_in(call):
    context = call.args[0]
    return [i.content for i in context.get_items_by_source(ContextSource.REMEDIATION)]


class TestValidationFeedback:
    @pytest.mark.asyncio
    async def test_validation_failure_goes_back_to_the_coder(self):
        orchestrator = orchestrator_with([INVALID, VALID])

        result = await orchestrator.execute_request("Fix SQL injection")

        assert result["status"] == "SUCCESS"
        calls = orchestrator.coder_agent.generate_code.call_args_list
        assert len(calls) == 2
        feedback = "\n".join(remediation_in(calls[1]))
        assert "Validation Failed" in feedback
        assert "(line 3): find_by_email not defined" in feedback
        assert "Expected functions or classes are missing" in feedback

    @pytest.mark.asyncio
    async def test_validation_runs_once_per_reviewed_patch(self):
        orchestrator = orchestrator_with([VALID])

        await orchestrator.execute_request("Fix SQL injection")

        assert orchestrator.validator_agent.validate_code.call_count == 1

    @pytest.mark.asyncio
    async def test_gives_up_after_the_attempt_budget(self):
        orchestrator = orchestrator_with([INVALID] * 4, attempts=4)

        result = await orchestrator.execute_request("Fix SQL injection")

        assert result["status"] == "FAILURE"
        assert result["validation"]["valid"] is False
        assert orchestrator.coder_agent.generate_code.call_count == 4

    @pytest.mark.asyncio
    async def test_checkpointed_workflow_also_repairs(self):
        orchestrator = orchestrator_with([INVALID, VALID])
        orchestrator.save_checkpoint = MagicMock()

        result = await orchestrator.execute_request_with_checkpoints(
            "Fix SQL injection"
        )

        assert result["status"] == "SUCCESS"
        assert orchestrator.coder_agent.generate_code.call_count == 2

    @pytest.mark.asyncio
    async def test_resumed_workflow_also_repairs(self):
        orchestrator = orchestrator_with([INVALID, VALID])
        checkpoint = AgentCheckpoint(
            workflow_id="wf-1",
            phase=WorkflowPhase.CODE_GENERATION,
            user_prompt="Fix SQL injection",
            tasks={"target_entity": "find_by_email", "task_description": "Fix it"},
            hybrid_context_data={
                "items": [],
                "query": "Fix SQL injection",
                "target_entity": "find_by_email",
                "session_id": None,
            },
            max_attempts=3,
        )

        result = await orchestrator.resume_from_checkpoint(
            checkpoint, save_checkpoints=False
        )

        assert result["status"] == "SUCCESS"
        assert orchestrator.coder_agent.generate_code.call_count == 2
        assert orchestrator.validator_agent.validate_code.call_count == 2

    def test_checkpoints_record_the_attempt_budget(self):
        orchestrator = System2Orchestrator(max_remediation_attempts=5)

        checkpoint = orchestrator._create_checkpoint("wf-1", "init", "prompt")

        assert checkpoint.max_attempts == 5


class TestFeedbackText:
    def test_validation_feedback_names_failed_checks_and_issues(self):
        text = System2Orchestrator._build_validation_feedback(
            {"valid": False, "syntax_valid": False, "issues": ["unexpected indent"]}
        )

        assert "not valid Python" in text
        assert "- Issue: unexpected indent" in text

    def test_sandbox_feedback_lists_failing_tests_and_errors(self):
        text = System2Orchestrator._build_sandbox_feedback(
            {
                "test_results": [
                    {"name": "test_login", "status": "passed"},
                    {"name": "test_injection", "status": "failed", "message": "500"},
                ],
                "errors": ["exit code 1"],
            }
        )

        assert "- Failed: test_injection: 500" in text
        assert "test_login" not in text
        assert "- Error: exit code 1" in text

    def test_sandbox_feedback_without_details_says_so(self):
        text = System2Orchestrator._build_sandbox_feedback({})

        assert "without test details" in text


class _SequencedSandbox(_FakeSandboxOrchestrator):
    """Sandbox whose runs pass or fail in a given order."""

    def __init__(self, outcomes):
        super().__init__(outcomes[0])
        self.outcomes = list(outcomes)

    async def get_sandbox_status(self, sandbox_id):
        self.all_tests_passed = self.outcomes[len(self.created) - 1]
        return await super().get_sandbox_status(sandbox_id)


class TestSandboxRepair:
    @pytest.mark.asyncio
    async def test_failed_sandbox_gets_a_repair_run_with_the_failing_tests(self):
        hitl = MagicMock()
        hitl.create_approval_request.return_value = MagicMock(approval_id="a")
        sandbox = _SequencedSandbox([False, True])
        orchestrator = _hitl_ready_orchestrator(hitl, sandbox_orchestrator=sandbox)

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        assert result["status"] == "AWAITING_APPROVAL"
        assert result["sandbox_results"]["status"] == "PASSED"
        assert len(sandbox.created) == 2
        assert sandbox.created[1][1].endswith("-r1")
        repair_call = orchestrator.coder_agent.generate_code.call_args_list[-1]
        assert any("Failed: t2" in text for text in remediation_in(repair_call))

    @pytest.mark.asyncio
    async def test_sandbox_failure_after_the_repair_budget_skips_approval(self):
        hitl = MagicMock()
        sandbox = _SequencedSandbox([False, False, False])
        orchestrator = _hitl_ready_orchestrator(hitl, sandbox_orchestrator=sandbox)
        orchestrator.max_sandbox_repairs = 2

        result = await orchestrator.execute_request_with_hitl(
            user_prompt="Fix checksum", vulnerability_id="VULN-9"
        )

        assert result["hitl_status"] == "SANDBOX_FAILED"
        assert len(sandbox.created) == 3
        assert sandbox.destroyed == [c[0] for c in sandbox.created]
        hitl.create_approval_request.assert_not_called()
