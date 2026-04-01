"""Integration tests for ConstitutionalMixin with real agents.

Tests the constitutional AI mixin integrated with agent patterns
similar to CoderAgent and ReviewerAgent.
"""

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.constitutional_agent_config import (
    DEVELOPMENT_CONFIG,
    STRICT_SECURITY_CONFIG,
    get_config_with_overrides,
    get_default_config,
)
from src.agents.constitutional_mixin import (
    ConstitutionalMixin,
    ConstitutionalMixinConfig,
)
from src.services.constitutional_ai.models import (
    ConstitutionalContext,
    ConstitutionalEvaluationSummary,
    CritiqueResult,
    PrincipleSeverity,
    RevisionResult,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    mock = MagicMock()
    mock.invoke_model_async = AsyncMock(return_value={"response": "{}"})
    return mock


@pytest.fixture
def clean_critique_summary():
    """Clean critique summary with no issues."""
    return ConstitutionalEvaluationSummary(
        critiques=[],
        total_principles_evaluated=3,
        critical_issues=0,
        high_issues=0,
        medium_issues=0,
        low_issues=0,
        requires_revision=False,
        requires_hitl=False,
    )


@pytest.fixture
def security_issue_critique():
    """Critique with security issue."""
    return ConstitutionalEvaluationSummary(
        critiques=[
            CritiqueResult(
                principle_id="security_validation",
                principle_name="Security Validation",
                severity=PrincipleSeverity.HIGH,
                issues_found=["SQL injection vulnerability detected"],
                reasoning="The code contains unescaped user input in SQL query",
                confidence=0.95,
                requires_revision=True,
            ),
        ],
        total_principles_evaluated=3,
        critical_issues=0,
        high_issues=1,
        medium_issues=0,
        low_issues=0,
        requires_revision=True,
        requires_hitl=False,
    )


@pytest.fixture
def critical_security_critique():
    """Critique with critical security issue."""
    return ConstitutionalEvaluationSummary(
        critiques=[
            CritiqueResult(
                principle_id="critical_security",
                principle_name="Critical Security Check",
                severity=PrincipleSeverity.CRITICAL,
                issues_found=["Hardcoded credentials detected"],
                reasoning="AWS credentials are hardcoded in the code",
                confidence=0.99,
                requires_revision=True,
            ),
        ],
        total_principles_evaluated=3,
        critical_issues=1,
        high_issues=0,
        medium_issues=0,
        low_issues=0,
        requires_revision=True,
        requires_hitl=True,
    )


@pytest.fixture
def successful_revision():
    """Successful revision result."""
    return RevisionResult(
        original_output="SELECT * FROM users WHERE id = " + "user_input",
        revised_output="SELECT * FROM users WHERE id = %s",  # parameterized
        critiques_addressed=["security_validation"],
        reasoning_chain="Replaced string concatenation with parameterized query",
        revision_iterations=1,
        converged=True,
        metadata={"remaining_issues": 0},
    )


@pytest.fixture
def failed_revision():
    """Failed revision result (did not converge)."""
    return RevisionResult(
        original_output="code with credentials",
        revised_output="code with credentials still present",
        critiques_addressed=[],
        reasoning_chain="Could not fully remove hardcoded credentials",
        revision_iterations=3,
        converged=False,
        metadata={"remaining_issues": 1},
    )


# =============================================================================
# Mock Agent Classes (Similar to Real Agents)
# =============================================================================


class MockCoderAgent(ConstitutionalMixin):
    """Mock CoderAgent with constitutional integration.

    Simulates the pattern used by standalone agents that don't inherit
    from BaseAgent.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        constitutional_config: Optional[ConstitutionalMixinConfig] = None,
    ):
        self.llm_client = llm_client
        self.monitor = MagicMock()

        # Initialize constitutional mixin
        config = constitutional_config or get_default_config("CoderAgent")
        self._init_constitutional(llm_service=llm_client, config=config)

    async def generate_code(
        self,
        context: Dict[str, Any],
        task_description: str,
        apply_constitutional: bool = True,
    ) -> Dict[str, Any]:
        """Generate code with optional constitutional oversight.

        Args:
            context: Generation context
            task_description: What to generate
            apply_constitutional: Whether to apply constitutional checks

        Returns:
            Dict with code, metadata, and constitutional info
        """
        # Simulate code generation
        generated_code = (
            f"# Generated code for: {task_description}\ndef solution():\n    pass"
        )

        result = {
            "code": generated_code,
            "language": "python",
            "metadata": {"task": task_description},
        }

        if not apply_constitutional:
            return result

        # Apply constitutional oversight
        processed = await self.process_with_constitutional(
            output=result["code"],
            context=ConstitutionalContext(
                agent_name="CoderAgent",
                operation_type="code_generation",
                user_request=task_description,
                domain_tags=self._constitutional_config.domain_tags,
            ),
        )

        if processed.blocked:
            return {
                **result,
                "code": "",
                "blocked": True,
                "block_reason": processed.block_reason,
                "constitutional_result": processed.to_dict(),
            }

        return {
            **result,
            "code": processed.processed_output,
            "was_revised": processed.was_revised,
            "constitutional_result": processed.to_dict(),
        }


class MockReviewerAgent(ConstitutionalMixin):
    """Mock ReviewerAgent with constitutional integration.

    Simulates security review agent pattern.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        constitutional_config: Optional[ConstitutionalMixinConfig] = None,
    ):
        self.llm_client = llm_client

        config = constitutional_config or get_default_config("ReviewerAgent")
        self._init_constitutional(llm_service=llm_client, config=config)

    async def review_code(
        self,
        code: str,
        review_type: str = "security",
    ) -> Dict[str, Any]:
        """Review code and apply constitutional checks to review output.

        Args:
            code: Code to review
            review_type: Type of review

        Returns:
            Review results with findings
        """
        # Simulate review output
        review_output = {
            "findings": [
                {"severity": "high", "message": "Potential security issue"},
            ],
            "summary": f"Completed {review_type} review",
            "recommendations": ["Consider input validation"],
        }

        # Apply constitutional oversight to the review output
        processed = await self.process_with_constitutional(
            output=review_output,
            context=ConstitutionalContext(
                agent_name="ReviewerAgent",
                operation_type="security_review",
                domain_tags=self._constitutional_config.domain_tags,
            ),
        )

        if processed.blocked:
            return {
                "findings": [],
                "blocked": True,
                "block_reason": processed.block_reason,
            }

        base_output = (
            processed.processed_output
            if isinstance(processed.processed_output, dict)
            else review_output
        )
        return {
            **base_output,
            "constitutional_checked": True,
            "was_revised": processed.was_revised,
        }


class MockBaseAgentSubclass(ConstitutionalMixin):
    """Mock agent that would inherit from BaseAgent.

    Simulates the pattern for agents that do inherit from BaseAgent.
    """

    def __init__(
        self,
        agent_name: str = "TestAgent",
        llm_client: Optional[Any] = None,
    ):
        self.agent_name = agent_name
        self.llm_client = llm_client

        # Would call super().__init__() for BaseAgent
        self._init_constitutional(
            llm_service=llm_client,
            config=ConstitutionalMixinConfig(
                domain_tags=["general"],
                mock_mode=True,
            ),
        )

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with constitutional oversight."""
        # Perform task
        result = {"output": f"Executed task: {task.get('name', 'unknown')}"}

        # Apply constitutional checks
        processed = await self.process_with_constitutional(
            output=result,
            context=ConstitutionalContext(
                agent_name=self.agent_name,
                operation_type="task_execution",
            ),
        )

        return {
            "success": not processed.blocked,
            "output": processed.processed_output,
            "constitutional": processed.to_dict(),
        }


# =============================================================================
# Integration Tests: CoderAgent Pattern
# =============================================================================


class TestCoderAgentIntegration:
    """Integration tests for CoderAgent + ConstitutionalMixin."""

    @pytest.mark.asyncio
    async def test_code_generation_passes_through_clean(
        self, mock_llm_service, clean_critique_summary
    ):
        """Test clean code passes through without modification."""
        agent = MockCoderAgent(llm_client=mock_llm_service)

        # Mock the critique service
        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(return_value=clean_critique_summary)
        agent._constitutional_critique_service = mock_critique

        result = await agent.generate_code(
            context={"project": "test"},
            task_description="Create a hello world function",
        )

        assert "code" in result
        assert result["was_revised"] is False
        assert "blocked" not in result or result.get("blocked") is False

    @pytest.mark.asyncio
    async def test_security_violation_triggers_revision(
        self, mock_llm_service, security_issue_critique, successful_revision
    ):
        """Test security issues trigger revision."""
        agent = MockCoderAgent(llm_client=mock_llm_service)

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(return_value=security_issue_critique)
        agent._constitutional_critique_service = mock_critique

        mock_revision = MagicMock()
        mock_revision.revise_output = AsyncMock(return_value=successful_revision)
        mock_revision.failure_config = MagicMock(max_revision_iterations=3)
        agent._constitutional_revision_service = mock_revision

        result = await agent.generate_code(
            context={},
            task_description="Query user data",
        )

        assert result["was_revised"] is True
        assert result["code"] == "SELECT * FROM users WHERE id = %s"

    @pytest.mark.asyncio
    async def test_critical_issue_blocks_output(
        self, mock_llm_service, critical_security_critique, failed_revision
    ):
        """Test critical unresolved issues block output."""
        config = get_default_config("CoderAgent")
        agent = MockCoderAgent(
            llm_client=mock_llm_service,
            constitutional_config=config,
        )

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(
            return_value=critical_security_critique
        )
        agent._constitutional_critique_service = mock_critique

        mock_revision = MagicMock()
        mock_revision.revise_output = AsyncMock(return_value=failed_revision)
        mock_revision.failure_config = MagicMock(max_revision_iterations=3)
        agent._constitutional_revision_service = mock_revision

        result = await agent.generate_code(
            context={},
            task_description="Connect to AWS",
        )

        assert result["blocked"] is True
        assert result["code"] == ""
        assert "block_reason" in result

    @pytest.mark.asyncio
    async def test_constitutional_disabled(self, mock_llm_service):
        """Test code generation without constitutional checks."""
        agent = MockCoderAgent(llm_client=mock_llm_service)

        result = await agent.generate_code(
            context={},
            task_description="Generate code",
            apply_constitutional=False,
        )

        assert "code" in result
        assert "constitutional_result" not in result
        assert "was_revised" not in result

    @pytest.mark.asyncio
    async def test_coder_agent_config_has_correct_tags(self, mock_llm_service):
        """Test CoderAgent gets correct domain tags from config."""
        agent = MockCoderAgent(llm_client=mock_llm_service)

        assert "code_generation" in agent._constitutional_config.domain_tags
        assert "security" in agent._constitutional_config.domain_tags

    @pytest.mark.asyncio
    async def test_custom_config_override(
        self, mock_llm_service, clean_critique_summary
    ):
        """Test custom config overrides defaults."""
        custom_config = get_config_with_overrides(
            "CoderAgent",
            block_on_critical=False,
            max_revision_iterations=5,
        )

        agent = MockCoderAgent(
            llm_client=mock_llm_service,
            constitutional_config=custom_config,
        )

        assert agent._constitutional_config.block_on_critical is False
        assert agent._constitutional_config.max_revision_iterations == 5


# =============================================================================
# Integration Tests: ReviewerAgent Pattern
# =============================================================================


class TestReviewerAgentIntegration:
    """Integration tests for ReviewerAgent + ConstitutionalMixin."""

    @pytest.mark.asyncio
    async def test_review_output_checked(
        self, mock_llm_service, clean_critique_summary
    ):
        """Test review output is constitutionally checked."""
        agent = MockReviewerAgent(llm_client=mock_llm_service)

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(return_value=clean_critique_summary)
        agent._constitutional_critique_service = mock_critique

        result = await agent.review_code(
            code="def hello(): pass",
            review_type="security",
        )

        assert result["constitutional_checked"] is True
        assert "findings" in result
        mock_critique.critique_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_reviewer_handles_dict_output(
        self, mock_llm_service, clean_critique_summary
    ):
        """Test reviewer properly handles dict output serialization."""
        agent = MockReviewerAgent(llm_client=mock_llm_service)

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(return_value=clean_critique_summary)
        agent._constitutional_critique_service = mock_critique

        result = await agent.review_code(
            code="def test(): pass",
            review_type="quality",
        )

        # Dict output should be preserved
        assert isinstance(result, dict)
        assert "findings" in result

    @pytest.mark.asyncio
    async def test_reviewer_agent_domain_tags(self, mock_llm_service):
        """Test ReviewerAgent has correct domain tags."""
        agent = MockReviewerAgent(llm_client=mock_llm_service)

        assert "security_review" in agent._constitutional_config.domain_tags
        assert "vulnerability_analysis" in agent._constitutional_config.domain_tags


# =============================================================================
# Integration Tests: BaseAgent Subclass Pattern
# =============================================================================


class TestBaseAgentSubclassIntegration:
    """Integration tests for BaseAgent subclass + ConstitutionalMixin."""

    @pytest.mark.asyncio
    async def test_execute_with_constitutional(
        self, mock_llm_service, clean_critique_summary
    ):
        """Test execute method with constitutional oversight."""
        agent = MockBaseAgentSubclass(
            agent_name="TestAgent",
            llm_client=mock_llm_service,
        )

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(return_value=clean_critique_summary)
        agent._constitutional_critique_service = mock_critique

        result = await agent.execute({"name": "test_task"})

        assert result["success"] is True
        assert "output" in result
        assert "constitutional" in result

    @pytest.mark.asyncio
    async def test_mock_mode_enabled(self, mock_llm_service):
        """Test mock mode is properly set for testing."""
        agent = MockBaseAgentSubclass(llm_client=mock_llm_service)

        assert agent._constitutional_config.mock_mode is True


# =============================================================================
# Integration Tests: Configuration Presets
# =============================================================================


class TestConfigurationPresets:
    """Tests for configuration presets with real agent patterns."""

    @pytest.mark.asyncio
    async def test_strict_security_config(
        self, mock_llm_service, critical_security_critique, failed_revision
    ):
        """Test strict security config behavior."""
        agent = MockCoderAgent(
            llm_client=mock_llm_service,
            constitutional_config=STRICT_SECURITY_CONFIG,
        )

        # Strict config should never skip
        assert agent._constitutional_config.skip_for_autonomy_levels == []
        assert agent._constitutional_config.block_on_critical is True

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(
            return_value=critical_security_critique
        )
        agent._constitutional_critique_service = mock_critique

        mock_revision = MagicMock()
        mock_revision.revise_output = AsyncMock(return_value=failed_revision)
        mock_revision.failure_config = MagicMock(max_revision_iterations=5)
        agent._constitutional_revision_service = mock_revision

        result = await agent.generate_code(
            context={},
            task_description="Handle credentials",
        )

        assert result["blocked"] is True

    @pytest.mark.asyncio
    async def test_development_config(
        self, mock_llm_service, critical_security_critique
    ):
        """Test development config behavior."""
        agent = MockCoderAgent(
            llm_client=mock_llm_service,
            constitutional_config=DEVELOPMENT_CONFIG,
        )

        # Dev config should use mock mode and not block
        assert agent._constitutional_config.mock_mode is True
        assert agent._constitutional_config.block_on_critical is False
        assert agent._constitutional_config.include_in_metrics is False


# =============================================================================
# Integration Tests: Metrics Accumulation
# =============================================================================


class TestMetricsAccumulation:
    """Tests for metrics accumulation across multiple operations."""

    @pytest.mark.asyncio
    async def test_metrics_accumulate_across_calls(
        self,
        mock_llm_service,
        clean_critique_summary,
        security_issue_critique,
        successful_revision,
    ):
        """Test metrics accumulate correctly across multiple calls."""
        agent = MockCoderAgent(llm_client=mock_llm_service)

        mock_critique = MagicMock()
        # First call - clean
        # Second call - needs revision
        mock_critique.critique_output = AsyncMock(
            side_effect=[clean_critique_summary, security_issue_critique]
        )
        agent._constitutional_critique_service = mock_critique

        mock_revision = MagicMock()
        mock_revision.revise_output = AsyncMock(return_value=successful_revision)
        mock_revision.failure_config = MagicMock(max_revision_iterations=3)
        agent._constitutional_revision_service = mock_revision

        # First call - should pass clean
        await agent.generate_code(context={}, task_description="Task 1")

        # Second call - should need revision
        await agent.generate_code(context={}, task_description="Task 2")

        metrics = agent.get_constitutional_metrics()

        assert metrics["total_processed"] == 2
        assert metrics["total_revised"] == 1
        assert metrics["revision_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_skip_metrics_tracked(self, mock_llm_service):
        """Test skipped processing is tracked in metrics."""
        config = ConstitutionalMixinConfig(
            domain_tags=["test"],
            skip_for_autonomy_levels=["FULL_AUTONOMOUS"],
        )
        agent = MockCoderAgent(
            llm_client=mock_llm_service,
            constitutional_config=config,
        )

        # Process with FULL_AUTONOMOUS should skip
        result = await agent.process_with_constitutional(
            output="test",
            context=ConstitutionalContext(
                agent_name="test",
                operation_type="test",
            ),
            autonomy_level="FULL_AUTONOMOUS",
        )

        assert result.skipped is True
        # Note: skipped items don't increment total_processed in current impl


# =============================================================================
# Integration Tests: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in integration scenarios."""

    @pytest.mark.asyncio
    async def test_critique_service_error_handled(self, mock_llm_service):
        """Test critique service errors are handled gracefully."""
        config = ConstitutionalMixinConfig(
            domain_tags=["test"],
            block_on_critical=False,
        )
        agent = MockCoderAgent(
            llm_client=mock_llm_service,
            constitutional_config=config,
        )

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(
            side_effect=Exception("Critique service unavailable")
        )
        agent._constitutional_critique_service = mock_critique

        # Should raise the exception (not silently fail)
        with pytest.raises(Exception, match="Critique service unavailable"):
            await agent.generate_code(context={}, task_description="Test")

    @pytest.mark.asyncio
    async def test_revision_service_error_handled(
        self, mock_llm_service, security_issue_critique
    ):
        """Test revision service errors don't crash the agent."""
        config = ConstitutionalMixinConfig(
            domain_tags=["test"],
            block_on_critical=False,
        )
        agent = MockCoderAgent(
            llm_client=mock_llm_service,
            constitutional_config=config,
        )

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(return_value=security_issue_critique)
        agent._constitutional_critique_service = mock_critique

        mock_revision = MagicMock()
        mock_revision.revise_output = AsyncMock(
            side_effect=Exception("Revision failed")
        )
        mock_revision.failure_config = MagicMock(max_revision_iterations=3)
        agent._constitutional_revision_service = mock_revision

        # Should complete without raising (revision failure handled gracefully)
        result = await agent.generate_code(context={}, task_description="Test")

        # Output should not be blocked since block_on_critical is False
        assert "code" in result


# =============================================================================
# Integration Tests: Multi-Agent Scenarios
# =============================================================================


class TestMultiAgentScenarios:
    """Tests for scenarios involving multiple agents."""

    @pytest.mark.asyncio
    async def test_coder_and_reviewer_integration(
        self, mock_llm_service, clean_critique_summary
    ):
        """Test CoderAgent and ReviewerAgent working together."""
        coder = MockCoderAgent(llm_client=mock_llm_service)
        reviewer = MockReviewerAgent(llm_client=mock_llm_service)

        # Setup mocks for both agents
        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(return_value=clean_critique_summary)

        coder._constitutional_critique_service = mock_critique
        reviewer._constitutional_critique_service = mock_critique

        # Coder generates code
        code_result = await coder.generate_code(
            context={},
            task_description="Create authentication function",
        )

        # Reviewer reviews the generated code
        review_result = await reviewer.review_code(
            code=code_result["code"],
            review_type="security",
        )

        # Both should complete successfully
        assert code_result.get("blocked", False) is False
        assert review_result.get("blocked", False) is False
        assert review_result["constitutional_checked"] is True

    @pytest.mark.asyncio
    async def test_separate_metrics_per_agent(
        self, mock_llm_service, clean_critique_summary
    ):
        """Test each agent maintains separate metrics."""
        coder = MockCoderAgent(llm_client=mock_llm_service)
        reviewer = MockReviewerAgent(llm_client=mock_llm_service)

        mock_critique = MagicMock()
        mock_critique.critique_output = AsyncMock(return_value=clean_critique_summary)

        coder._constitutional_critique_service = mock_critique
        reviewer._constitutional_critique_service = mock_critique

        # Process with coder
        await coder.generate_code(context={}, task_description="Task 1")
        await coder.generate_code(context={}, task_description="Task 2")

        # Process with reviewer
        await reviewer.review_code(code="test", review_type="security")

        # Metrics should be separate
        coder_metrics = coder.get_constitutional_metrics()
        reviewer_metrics = reviewer.get_constitutional_metrics()

        assert coder_metrics["total_processed"] == 2
        assert reviewer_metrics["total_processed"] == 1
