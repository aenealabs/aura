"""Tests for ConstitutionalRevisionService.

This module tests the revision service for revising AI outputs
based on constitutional critique feedback.
"""

import asyncio
import json

import pytest

from src.services.constitutional_ai.critique_service import (
    ConstitutionalCritiqueService,
)
from src.services.constitutional_ai.exceptions import (
    CritiqueParseError,
    HITLRequiredError,
    LLMServiceError,
    RevisionConvergenceError,
)
from src.services.constitutional_ai.failure_policy import (
    ConstitutionalFailureConfig,
    RevisionFailurePolicy,
)
from src.services.constitutional_ai.models import (
    ConstitutionalEvaluationSummary,
    RevisionResult,
)
from src.services.constitutional_ai.revision_service import (
    ConstitutionalRevisionService,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_critique_service(mock_llm_service, minimal_constitution_yaml):
    """Create a mock critique service."""
    service = ConstitutionalCritiqueService(
        llm_service=mock_llm_service,
        constitution_path=minimal_constitution_yaml,
        mock_mode=True,
    )
    return service


@pytest.fixture
def revision_service(mock_critique_service, mock_llm_service):
    """Create a revision service with mocks."""
    return ConstitutionalRevisionService(
        critique_service=mock_critique_service,
        llm_service=mock_llm_service,
        mock_mode=True,
    )


@pytest.fixture
def critiques_requiring_revision(
    sample_critique_result, sample_critical_critique_result
):
    """Create a list of critiques that require revision."""
    return [sample_critique_result, sample_critical_critique_result]


@pytest.fixture
def critiques_no_revision(sample_critique_result_no_issues):
    """Create a list of critiques that don't require revision."""
    return [sample_critique_result_no_issues]


# =============================================================================
# Initialization Tests
# =============================================================================


class TestRevisionServiceInitialization:
    """Tests for ConstitutionalRevisionService initialization."""

    def test_init_with_mock_mode(self, mock_critique_service, mock_llm_service):
        """Test initialization with mock mode."""
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
            mock_mode=True,
        )
        assert service.mock_mode is True

    def test_init_with_custom_failure_config(
        self, mock_critique_service, mock_llm_service, strict_failure_config
    ):
        """Test initialization with custom failure config."""
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
            failure_config=strict_failure_config,
        )
        assert (
            service.failure_config.revision_failure_policy
            == RevisionFailurePolicy.BLOCK_FOR_HITL
        )

    def test_init_uses_default_failure_config(
        self, mock_critique_service, mock_llm_service
    ):
        """Test initialization uses default failure config."""
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
        )
        assert service.failure_config is not None


# =============================================================================
# No Revision Needed Tests
# =============================================================================


class TestNoRevisionNeeded:
    """Tests for cases where no revision is required."""

    @pytest.mark.asyncio
    async def test_revise_with_no_critiques(self, revision_service, sample_context):
        """Test revision when critiques list is empty."""
        result = await revision_service.revise_output(
            "test output",
            critiques=[],
            context=sample_context,
        )
        assert result.original_output == "test output"
        assert result.revised_output == "test output"
        assert result.revision_iterations == 0
        assert result.converged is True

    @pytest.mark.asyncio
    async def test_revise_with_no_revision_required(
        self, revision_service, sample_context, critiques_no_revision
    ):
        """Test revision when no critiques require revision."""
        result = await revision_service.revise_output(
            "test output",
            critiques=critiques_no_revision,
            context=sample_context,
        )
        assert result.original_output == result.revised_output
        assert result.revision_iterations == 0


# =============================================================================
# Mock Mode Tests
# =============================================================================


class TestRevisionMockMode:
    """Tests for revision in mock mode."""

    @pytest.mark.asyncio
    async def test_revision_in_mock_mode(
        self, revision_service, sample_context, critiques_requiring_revision
    ):
        """Test revision in mock mode produces results."""
        result = await revision_service.revise_output(
            "original output",
            critiques=critiques_requiring_revision,
            context=sample_context,
        )
        assert isinstance(result, RevisionResult)
        assert result.revision_iterations >= 1
        assert "[REVISED]" in result.revised_output

    @pytest.mark.asyncio
    async def test_mock_mode_no_llm_calls(
        self,
        mock_critique_service,
        mock_llm_service,
        sample_context,
        sample_critique_result,
    ):
        """Test that mock mode doesn't make LLM calls."""
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
            mock_mode=True,
        )
        await service.revise_output(
            "test output",
            critiques=[sample_critique_result],
            context=sample_context,
        )
        mock_llm_service.invoke_model_async.assert_not_called()

    def test_generate_mock_revision(self, revision_service, sample_critique_result):
        """Test mock revision generation."""
        mock_result = revision_service._generate_mock_revision(
            "original output",
            [sample_critique_result],
        )
        assert "[REVISED]" in mock_result["revised_output"]
        assert len(mock_result["addressed"]) == 1


# =============================================================================
# Revision Loop Tests
# =============================================================================


class TestRevisionLoop:
    """Tests for the revision iteration loop."""

    @pytest.mark.asyncio
    async def test_revision_tracks_iterations(
        self, revision_service, sample_context, critiques_requiring_revision
    ):
        """Test that revision tracks iteration count."""
        result = await revision_service.revise_output(
            "test output",
            critiques=critiques_requiring_revision,
            context=sample_context,
        )
        assert result.revision_iterations >= 1

    @pytest.mark.asyncio
    async def test_revision_with_max_iterations(
        self,
        mock_critique_service,
        mock_llm_service,
        sample_context,
        sample_critique_result,
    ):
        """Test revision respects max iterations."""
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
            mock_mode=True,
        )
        result = await service.revise_output(
            "test output",
            critiques=[sample_critique_result],
            context=sample_context,
            max_iterations=1,
        )
        assert result.revision_iterations <= 1

    @pytest.mark.asyncio
    async def test_revision_creates_default_context(
        self, revision_service, sample_critique_result
    ):
        """Test that revision creates default context when none provided."""
        result = await revision_service.revise_output(
            "test output",
            critiques=[sample_critique_result],
        )
        assert result is not None


# =============================================================================
# LLM Integration Tests
# =============================================================================


class TestLLMIntegration:
    """Tests for LLM service integration."""

    @pytest.mark.asyncio
    async def test_revision_without_llm_raises(
        self, mock_critique_service, sample_critique_result
    ):
        """Test that revision without LLM service raises error."""
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=None,
        )
        with pytest.raises(LLMServiceError) as exc_info:
            await service.revise_output(
                "test output",
                critiques=[sample_critique_result],
            )
        assert "not configured" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_revision_calls_llm(
        self,
        mock_critique_service,
        mock_llm_service,
        mock_llm_response_factory,
        revision_response_factory,
        sample_critique_result,
    ):
        """Test that revision calls LLM service."""
        response = revision_response_factory(
            "revised output", addressed=["test_principle_1"]
        )
        mock_llm_service.invoke_model_async.return_value = mock_llm_response_factory(
            response
        )

        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
        )
        await service.revise_output(
            "original output",
            critiques=[sample_critique_result],
        )
        mock_llm_service.invoke_model_async.assert_called()


# =============================================================================
# Response Parsing Tests
# =============================================================================


class TestResponseParsing:
    """Tests for LLM response parsing."""

    def test_parse_revision_response_valid_json(
        self, revision_service, sample_critique_result
    ):
        """Test parsing valid JSON response."""
        response = json.dumps(
            {
                "revised_output": "revised text",
                "reasoning": "test reasoning",
                "addressed": ["test_principle_1"],
            }
        )
        result = revision_service._parse_revision_response(
            response, [sample_critique_result]
        )
        assert result["revised_output"] == "revised text"
        assert result["reasoning"] == "test reasoning"

    def test_parse_revision_response_with_code_block(
        self, revision_service, sample_critique_result
    ):
        """Test parsing response with markdown code block."""
        response = """```json
{"revised_output": "revised", "reasoning": "reason", "addressed": []}
```"""
        result = revision_service._parse_revision_response(
            response, [sample_critique_result]
        )
        assert result["revised_output"] == "revised"

    def test_parse_revision_response_invalid_json_raises(
        self, revision_service, sample_critique_result
    ):
        """Test that invalid JSON raises CritiqueParseError."""
        with pytest.raises(CritiqueParseError):
            revision_service._parse_revision_response(
                "not valid json", [sample_critique_result]
            )


# =============================================================================
# Failure Handling Tests
# =============================================================================


class TestFailureHandling:
    """Tests for failure handling in revision service."""

    @pytest.mark.asyncio
    async def test_handle_failure_block_for_hitl(
        self, mock_critique_service, mock_llm_service, sample_critical_critique_result
    ):
        """Test failure handling with BLOCK_FOR_HITL policy."""
        config = ConstitutionalFailureConfig(
            revision_failure_policy=RevisionFailurePolicy.BLOCK_FOR_HITL
        )
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
            failure_config=config,
        )
        with pytest.raises(HITLRequiredError) as exc_info:
            await service._handle_revision_failure(
                "original",
                "best effort",
                [sample_critical_critique_result],
                3,
                ["reasoning"],
            )
        assert len(exc_info.value.remaining_issues) == 1

    @pytest.mark.asyncio
    async def test_handle_failure_return_original(
        self, mock_critique_service, mock_llm_service, sample_critical_critique_result
    ):
        """Test failure handling with RETURN_ORIGINAL policy."""
        config = ConstitutionalFailureConfig(
            revision_failure_policy=RevisionFailurePolicy.RETURN_ORIGINAL
        )
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
            failure_config=config,
        )
        with pytest.raises(RevisionConvergenceError):
            await service._handle_revision_failure(
                "original",
                "best effort",
                [sample_critical_critique_result],
                3,
                ["reasoning"],
            )


# =============================================================================
# Prompt Building Tests
# =============================================================================


class TestPromptBuilding:
    """Tests for revision prompt building."""

    def test_build_revision_prompt(
        self, revision_service, sample_context, sample_critique_result
    ):
        """Test revision prompt building."""
        prompt = revision_service._build_revision_prompt(
            "original output",
            [sample_critique_result],
            sample_context,
        )
        assert "original output" in prompt
        assert "TestAgent" in prompt
        assert "Test Principle" in prompt
        assert "Issue 1" in prompt

    def test_prompt_includes_severity(
        self, revision_service, sample_context, sample_critical_critique_result
    ):
        """Test that prompt includes severity information."""
        prompt = revision_service._build_revision_prompt(
            "test output",
            [sample_critical_critique_result],
            sample_context,
        )
        assert "CRITICAL" in prompt

    def test_prompt_includes_json_format(
        self, revision_service, sample_context, sample_critique_result
    ):
        """Test that prompt specifies JSON output format."""
        prompt = revision_service._build_revision_prompt(
            "test output",
            [sample_critique_result],
            sample_context,
        )
        assert "JSON" in prompt or "json" in prompt


# =============================================================================
# Combined Workflow Tests
# =============================================================================


class TestCombinedWorkflow:
    """Tests for combined critique and revision workflow."""

    @pytest.mark.asyncio
    async def test_revise_with_evaluation_no_revision_needed(
        self, revision_service, sample_context
    ):
        """Test combined workflow when no revision needed."""
        summary, revision = await revision_service.revise_with_evaluation(
            "good output",
            context=sample_context,
        )
        assert isinstance(summary, ConstitutionalEvaluationSummary)
        # In mock mode, no issues are found
        assert revision is None or not revision.was_modified

    @pytest.mark.asyncio
    async def test_revise_with_evaluation_returns_tuple(
        self, revision_service, sample_context
    ):
        """Test that combined workflow returns tuple."""
        result = await revision_service.revise_with_evaluation(
            "test output",
            context=sample_context,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2


# =============================================================================
# Iterative Revision Tests
# =============================================================================


class TestIterativeRevision:
    """Tests for iterative revision with full re-evaluation."""

    @pytest.mark.asyncio
    async def test_iterative_revise_returns_result(
        self, revision_service, sample_context
    ):
        """Test iterative revision returns RevisionResult."""
        result = await revision_service.iterative_revise(
            "test output",
            context=sample_context,
            max_total_iterations=2,
        )
        assert isinstance(result, RevisionResult)
        assert "iterative_mode" in result.metadata
        assert result.metadata["iterative_mode"] is True

    @pytest.mark.asyncio
    async def test_iterative_revise_respects_max_iterations(
        self, revision_service, sample_context
    ):
        """Test iterative revision respects max iterations."""
        result = await revision_service.iterative_revise(
            "test output",
            context=sample_context,
            max_total_iterations=1,
        )
        assert result.revision_iterations <= 1

    @pytest.mark.asyncio
    async def test_iterative_revise_with_specific_principles(
        self, revision_service, sample_context
    ):
        """Test iterative revision with specific principles."""
        result = await revision_service.iterative_revise(
            "test output",
            context=sample_context,
            applicable_principles=["test_principle_1"],
            max_total_iterations=2,
        )
        assert isinstance(result, RevisionResult)


# =============================================================================
# Convergence Tests
# =============================================================================


class TestConvergence:
    """Tests for revision convergence detection."""

    @pytest.mark.asyncio
    async def test_convergence_detected(self, revision_service, sample_context):
        """Test that convergence is properly detected."""
        result = await revision_service.revise_output(
            "test output",
            critiques=[],  # No critiques = immediate convergence
            context=sample_context,
        )
        assert result.converged is True

    @pytest.mark.asyncio
    async def test_non_convergence_tracked(
        self,
        mock_critique_service,
        mock_llm_service,
        sample_context,
        sample_critique_result,
    ):
        """Test that non-convergence is tracked in metadata."""
        # This test would need more complex setup to simulate non-convergence
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
            mock_mode=True,
        )
        result = await service.revise_output(
            "test output",
            critiques=[sample_critique_result],
            context=sample_context,
            max_iterations=1,
        )
        assert "remaining_issues" in result.metadata or result.converged


# =============================================================================
# Timeout Tests
# =============================================================================


class TestTimeoutHandling:
    """Tests for timeout handling in revision service."""

    @pytest.mark.asyncio
    async def test_revision_timeout_raises_error(
        self, mock_critique_service, mock_llm_service, sample_critique_result
    ):
        """Test that LLM timeout raises LLMServiceError."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(10)
            return {"response": "{}"}

        mock_llm_service.invoke_model_async.side_effect = slow_response

        config = ConstitutionalFailureConfig(revision_timeout_seconds=0.1)
        service = ConstitutionalRevisionService(
            critique_service=mock_critique_service,
            llm_service=mock_llm_service,
            failure_config=config,
        )
        with pytest.raises(LLMServiceError) as exc_info:
            await service.revise_output(
                "test output",
                critiques=[sample_critique_result],
            )
        assert "timed out" in str(exc_info.value).lower()


# =============================================================================
# Critiques Addressed Tests
# =============================================================================


class TestCritiquesAddressed:
    """Tests for tracking addressed critiques."""

    @pytest.mark.asyncio
    async def test_addressed_critiques_tracked(
        self, revision_service, sample_context, sample_critique_result
    ):
        """Test that addressed critiques are tracked."""
        result = await revision_service.revise_output(
            "test output",
            critiques=[sample_critique_result],
            context=sample_context,
        )
        assert isinstance(result.critiques_addressed, list)

    @pytest.mark.asyncio
    async def test_addressed_critiques_deduplicated(
        self, revision_service, sample_context, sample_critique_result
    ):
        """Test that addressed critiques are deduplicated."""
        result = await revision_service.revise_output(
            "test output",
            critiques=[sample_critique_result, sample_critique_result],
            context=sample_context,
        )
        # Should not have duplicate IDs in addressed list
        assert len(result.critiques_addressed) == len(set(result.critiques_addressed))


# =============================================================================
# Reasoning Chain Tests
# =============================================================================


class TestReasoningChain:
    """Tests for reasoning chain tracking."""

    @pytest.mark.asyncio
    async def test_reasoning_chain_recorded(
        self, revision_service, sample_context, sample_critique_result
    ):
        """Test that reasoning chain is recorded."""
        result = await revision_service.revise_output(
            "test output",
            critiques=[sample_critique_result],
            context=sample_context,
        )
        assert result.reasoning_chain is not None
        assert len(result.reasoning_chain) > 0

    @pytest.mark.asyncio
    async def test_reasoning_chain_includes_iterations(
        self, revision_service, sample_context, sample_critique_result
    ):
        """Test that reasoning chain includes iteration info."""
        result = await revision_service.revise_output(
            "test output",
            critiques=[sample_critique_result],
            context=sample_context,
        )
        if result.revision_iterations > 0:
            assert (
                "Iteration" in result.reasoning_chain
                or "reasoning" in result.reasoning_chain.lower()
            )
