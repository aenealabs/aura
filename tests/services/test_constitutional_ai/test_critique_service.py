"""Tests for ConstitutionalCritiqueService.

This module tests the critique service for evaluating AI outputs
against constitutional principles.
"""

import asyncio
import json

import pytest

from src.services.constitutional_ai.critique_service import (
    ConstitutionalCritiqueService,
)
from src.services.constitutional_ai.exceptions import (
    ConstitutionLoadError,
    CritiqueParseError,
    CritiqueTimeoutError,
    LLMServiceError,
)
from src.services.constitutional_ai.failure_policy import (
    ConstitutionalFailureConfig,
    CritiqueFailurePolicy,
)
from src.services.constitutional_ai.models import (
    ConstitutionalContext,
    ConstitutionalEvaluationSummary,
    CritiqueResult,
    PrincipleCategory,
    PrincipleSeverity,
)

# =============================================================================
# Initialization Tests
# =============================================================================


class TestCritiqueServiceInitialization:
    """Tests for ConstitutionalCritiqueService initialization."""

    def test_init_with_mock_mode(self, mock_llm_service, minimal_constitution_yaml):
        """Test initialization with mock mode."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        assert service.mock_mode is True
        assert len(service.principles) == 2

    def test_init_loads_principles(self, mock_llm_service, minimal_constitution_yaml):
        """Test that initialization loads principles from YAML."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        assert len(service.principles) == 2
        assert service.principles[0].id == "test_principle_1"

    def test_init_with_custom_failure_config(
        self, mock_llm_service, minimal_constitution_yaml, strict_failure_config
    ):
        """Test initialization with custom failure config."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            failure_config=strict_failure_config,
        )
        assert (
            service.failure_config.critique_failure_policy
            == CritiqueFailurePolicy.BLOCK
        )

    def test_init_missing_constitution_file(self, mock_llm_service):
        """Test initialization fails with missing constitution file."""
        with pytest.raises(ConstitutionLoadError) as exc_info:
            ConstitutionalCritiqueService(
                llm_service=mock_llm_service,
                constitution_path="/nonexistent/path.yaml",
            )
        assert "not found" in str(exc_info.value).lower()

    def test_init_invalid_constitution_yaml(
        self, mock_llm_service, invalid_constitution_yaml
    ):
        """Test initialization fails with invalid constitution YAML."""
        with pytest.raises(ConstitutionLoadError) as exc_info:
            ConstitutionalCritiqueService(
                llm_service=mock_llm_service,
                constitution_path=invalid_constitution_yaml,
            )
        assert "principles" in str(exc_info.value).lower()

    def test_init_with_real_constitution(self, mock_llm_service):
        """Test initialization with real constitution file."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            mock_mode=True,
        )
        assert len(service.principles) == 16


# =============================================================================
# Principle Loading Tests
# =============================================================================


class TestPrincipleLoading:
    """Tests for principle loading from YAML."""

    def test_load_principle_with_all_fields(
        self, mock_llm_service, full_constitution_yaml
    ):
        """Test loading principle with all fields."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=full_constitution_yaml,
        )
        critical_principle = service.get_principle("principle_critical_1")
        assert critical_principle is not None
        assert critical_principle.severity == PrincipleSeverity.CRITICAL
        assert critical_principle.category == PrincipleCategory.SAFETY

    def test_disabled_principles_not_filtered_on_load(
        self, mock_llm_service, full_constitution_yaml
    ):
        """Test that disabled principles are loaded but can be filtered."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=full_constitution_yaml,
        )
        # Disabled principles are loaded
        disabled = service.get_principle("principle_disabled")
        assert disabled is not None
        assert disabled.enabled is False

    def test_get_principle_by_id(self, mock_llm_service, minimal_constitution_yaml):
        """Test getting principle by ID."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        principle = service.get_principle("test_principle_1")
        assert principle is not None
        assert principle.name == "Test Principle 1"

    def test_get_principle_not_found(self, mock_llm_service, minimal_constitution_yaml):
        """Test getting non-existent principle returns None."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        principle = service.get_principle("nonexistent")
        assert principle is None


# =============================================================================
# Principle Filtering Tests
# =============================================================================


class TestPrincipleFiltering:
    """Tests for principle filtering by category, severity, and context."""

    def test_get_principles_by_category(self, mock_llm_service, full_constitution_yaml):
        """Test filtering principles by category."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=full_constitution_yaml,
        )
        safety_principles = service.get_principles_by_category(PrincipleCategory.SAFETY)
        assert len(safety_principles) >= 1
        assert all(p.category == PrincipleCategory.SAFETY for p in safety_principles)

    def test_get_principles_by_severity(self, mock_llm_service, full_constitution_yaml):
        """Test filtering principles by severity."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=full_constitution_yaml,
        )
        critical_principles = service.get_principles_by_severity(
            PrincipleSeverity.CRITICAL
        )
        assert len(critical_principles) >= 1
        assert all(
            p.severity == PrincipleSeverity.CRITICAL for p in critical_principles
        )

    def test_filter_principles_by_ids(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test filtering principles by specific IDs."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        filtered = service.filter_principles(applicable_ids=["test_principle_1"])
        assert len(filtered) == 1
        assert filtered[0].id == "test_principle_1"

    def test_filter_principles_by_context_domain_tags(
        self, mock_llm_service, full_constitution_yaml
    ):
        """Test filtering principles by context domain tags."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=full_constitution_yaml,
        )
        context = ConstitutionalContext(
            agent_name="test",
            operation_type="test",
            domain_tags=["security"],
        )
        filtered = service.filter_principles(context=context)
        # Should include principles with "security" tag or no tags
        assert len(filtered) >= 1

    def test_filter_excludes_disabled_principles(
        self, mock_llm_service, full_constitution_yaml
    ):
        """Test that filtering excludes disabled principles."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=full_constitution_yaml,
        )
        filtered = service.filter_principles()
        disabled_ids = [p.id for p in filtered if not p.enabled]
        assert len(disabled_ids) == 0


# =============================================================================
# Batching Tests
# =============================================================================


class TestPrincipleBatching:
    """Tests for principle batching logic."""

    def test_create_batches_default_size(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test creating batches with default size."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        batches = service._create_principle_batches(sample_principles, batch_size=5)
        assert len(batches) == 1
        assert len(batches[0]) == 4

    def test_create_batches_multiple(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test creating multiple batches."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        batches = service._create_principle_batches(sample_principles, batch_size=2)
        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2

    def test_create_batches_empty_list(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test creating batches from empty list."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        batches = service._create_principle_batches([])
        assert batches == []


# =============================================================================
# Mock Mode Tests
# =============================================================================


class TestMockMode:
    """Tests for mock mode functionality."""

    @pytest.mark.asyncio
    async def test_critique_in_mock_mode(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test critique evaluation in mock mode."""
        # Use context with matching domain tags for minimal_constitution_yaml
        context = ConstitutionalContext(
            agent_name="TestAgent",
            operation_type="test",
            domain_tags=["test"],
        )
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        summary = await service.critique_output(
            "test output",
            context=context,
        )
        assert isinstance(summary, ConstitutionalEvaluationSummary)
        assert summary.total_principles_evaluated == 2
        assert all(c.metadata.get("mock") for c in summary.critiques)

    @pytest.mark.asyncio
    async def test_mock_mode_no_llm_calls(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test that mock mode doesn't make LLM calls."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        await service.critique_output("test output")
        mock_llm_service.invoke_model_async.assert_not_called()

    def test_generate_mock_critiques(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test mock critique generation."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        mocks = service._generate_mock_critiques(sample_principles)
        assert len(mocks) == len(sample_principles)
        assert all(m.requires_revision is False for m in mocks)
        assert all(m.confidence == 1.0 for m in mocks)


# =============================================================================
# Critique Output Tests
# =============================================================================


class TestCritiqueOutput:
    """Tests for critique_output method."""

    @pytest.mark.asyncio
    async def test_critique_with_no_applicable_principles(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test critique when no principles are applicable."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        summary = await service.critique_output(
            "test output",
            applicable_principles=["nonexistent_principle"],
        )
        assert summary.total_principles_evaluated == 0

    @pytest.mark.asyncio
    async def test_critique_creates_default_context(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test that critique creates default context when none provided."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        summary = await service.critique_output("test output")
        assert summary.total_principles_evaluated > 0

    @pytest.mark.asyncio
    async def test_critique_with_specific_principles(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test critique with specific principle IDs."""
        # Use context with matching domain tags
        context = ConstitutionalContext(
            agent_name="TestAgent",
            operation_type="test",
            domain_tags=["test"],
        )
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        summary = await service.critique_output(
            "test output",
            context=context,
            applicable_principles=["test_principle_1"],
        )
        assert summary.total_principles_evaluated == 1
        assert summary.critiques[0].principle_id == "test_principle_1"

    @pytest.mark.asyncio
    async def test_critique_returns_evaluation_summary(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test that critique returns ConstitutionalEvaluationSummary."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        summary = await service.critique_output("test output")
        assert isinstance(summary, ConstitutionalEvaluationSummary)
        assert hasattr(summary, "critical_issues")
        assert hasattr(summary, "requires_revision")
        assert summary.evaluation_time_ms > 0


# =============================================================================
# LLM Integration Tests
# =============================================================================


class TestLLMIntegration:
    """Tests for LLM service integration."""

    @pytest.mark.asyncio
    async def test_critique_calls_llm(
        self,
        mock_llm_service,
        minimal_constitution_yaml,
        mock_llm_response_factory,
        critique_response_factory,
    ):
        """Test that critique calls LLM service."""
        response = critique_response_factory("test_principle_1")
        mock_llm_service.invoke_model_async.return_value = mock_llm_response_factory(
            response
        )

        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        await service.critique_output(
            "test output",
            applicable_principles=["test_principle_1"],
        )
        mock_llm_service.invoke_model_async.assert_called()

    @pytest.mark.asyncio
    async def test_critique_uses_temperature_zero(
        self,
        mock_llm_service,
        minimal_constitution_yaml,
        mock_llm_response_factory,
        critique_response_factory,
    ):
        """Test that critique uses temperature 0 for determinism."""
        response = critique_response_factory("test_principle_1")
        mock_llm_service.invoke_model_async.return_value = mock_llm_response_factory(
            response
        )

        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        await service.critique_output(
            "test output",
            applicable_principles=["test_principle_1"],
        )

        call_kwargs = mock_llm_service.invoke_model_async.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.0

    @pytest.mark.asyncio
    async def test_critique_without_llm_service_raises(self, minimal_constitution_yaml):
        """Test that critique without LLM service raises error."""
        # Use context that matches the principle domain tags
        context = ConstitutionalContext(
            agent_name="TestAgent",
            operation_type="test",
            domain_tags=["test"],  # Match minimal_constitution_yaml domain_tags
        )
        # Use BLOCK policy to ensure errors are raised instead of caught
        config = ConstitutionalFailureConfig(
            critique_failure_policy=CritiqueFailurePolicy.BLOCK
        )
        service = ConstitutionalCritiqueService(
            llm_service=None,
            constitution_path=minimal_constitution_yaml,
            failure_config=config,
        )
        with pytest.raises(LLMServiceError) as exc_info:
            await service.critique_output(
                "test output",
                context=context,
            )
        assert "not configured" in str(exc_info.value).lower()


# =============================================================================
# Response Parsing Tests
# =============================================================================


class TestResponseParsing:
    """Tests for LLM response parsing."""

    def test_parse_batch_response_valid_json(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test parsing valid JSON response."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        response = json.dumps(
            [
                {
                    "principle_id": "principle_security",
                    "issues_found": ["Issue 1"],
                    "reasoning": "Test reasoning",
                    "requires_revision": True,
                    "confidence": 0.9,
                }
            ]
        )
        results = service._parse_batch_response(response, sample_principles)
        assert len(results) == 1
        assert results[0].principle_id == "principle_security"
        assert results[0].requires_revision is True

    def test_parse_batch_response_with_code_block(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test parsing response with markdown code block."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        response = """```json
[{"principle_id": "principle_security", "issues_found": [], "reasoning": "ok", "requires_revision": false, "confidence": 0.8}]
```"""
        results = service._parse_batch_response(response, sample_principles)
        assert len(results) == 1
        assert results[0].requires_revision is False

    def test_parse_batch_response_unknown_principle_skipped(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test that unknown principle IDs are skipped."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        response = json.dumps(
            [
                {
                    "principle_id": "unknown_principle",
                    "issues_found": [],
                    "reasoning": "",
                    "requires_revision": False,
                    "confidence": 0.5,
                }
            ]
        )
        results = service._parse_batch_response(response, sample_principles)
        assert len(results) == 0

    def test_parse_batch_response_invalid_json_raises(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test that invalid JSON raises CritiqueParseError."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        with pytest.raises(CritiqueParseError):
            service._parse_batch_response("not valid json", sample_principles)

    def test_parse_batch_response_not_array_raises(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test that non-array JSON raises CritiqueParseError."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        with pytest.raises(CritiqueParseError):
            service._parse_batch_response('{"not": "array"}', sample_principles)


# =============================================================================
# Conflict Resolution Tests
# =============================================================================


class TestConflictResolution:
    """Tests for principle conflict resolution."""

    def test_resolve_conflicts_sorts_by_severity(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test that conflict resolution sorts by severity."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        critiques = [
            CritiqueResult(
                principle_id="low",
                principle_name="Low",
                severity=PrincipleSeverity.LOW,
                issues_found=[],
                reasoning="",
                requires_revision=False,
            ),
            CritiqueResult(
                principle_id="critical",
                principle_name="Critical",
                severity=PrincipleSeverity.CRITICAL,
                issues_found=["issue"],
                reasoning="",
                requires_revision=True,
            ),
        ]
        resolved = service._resolve_conflicts(critiques)
        assert resolved[0].severity == PrincipleSeverity.CRITICAL

    def test_resolve_conflicts_critical_always_requires_revision(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test that critical issues with problems always require revision."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        critiques = [
            CritiqueResult(
                principle_id="critical",
                principle_name="Critical",
                severity=PrincipleSeverity.CRITICAL,
                issues_found=["serious issue"],
                reasoning="",
                requires_revision=False,  # Set to False
            ),
        ]
        resolved = service._resolve_conflicts(critiques)
        # Should be forced to True because critical with issues
        assert resolved[0].requires_revision is True

    def test_resolve_conflicts_empty_list(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test conflict resolution with empty list."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        resolved = service._resolve_conflicts([])
        assert resolved == []


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in critique service."""

    @pytest.mark.asyncio
    async def test_handle_batch_error_block_policy(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test batch error handling with BLOCK policy."""
        config = ConstitutionalFailureConfig(
            critique_failure_policy=CritiqueFailurePolicy.BLOCK
        )
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            failure_config=config,
        )
        with pytest.raises(Exception):
            await service._handle_batch_error(
                ValueError("test error"),
                sample_principles,
                [],
            )

    @pytest.mark.asyncio
    async def test_handle_batch_error_proceed_flagged(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test batch error handling with PROCEED_FLAGGED policy."""
        config = ConstitutionalFailureConfig(
            critique_failure_policy=CritiqueFailurePolicy.PROCEED_FLAGGED
        )
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            failure_config=config,
        )
        all_critiques = []
        await service._handle_batch_error(
            ValueError("test error"),
            sample_principles,
            all_critiques,
        )
        assert len(all_critiques) == len(sample_principles)
        assert all(c.requires_revision for c in all_critiques)
        assert all("evaluation_error" in c.metadata for c in all_critiques)

    @pytest.mark.asyncio
    async def test_handle_batch_error_proceed_logged(
        self, mock_llm_service, minimal_constitution_yaml, sample_principles
    ):
        """Test batch error handling with PROCEED_LOGGED policy."""
        config = ConstitutionalFailureConfig(
            critique_failure_policy=CritiqueFailurePolicy.PROCEED_LOGGED
        )
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            failure_config=config,
        )
        all_critiques = []
        await service._handle_batch_error(
            ValueError("test error"),
            sample_principles,
            all_critiques,
        )
        assert len(all_critiques) == len(sample_principles)
        # PROCEED_LOGGED doesn't flag for revision
        assert all(c.requires_revision is False for c in all_critiques)


# =============================================================================
# Timeout Tests
# =============================================================================


class TestTimeoutHandling:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_critique_timeout_raises_error(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test that LLM timeout raises CritiqueTimeoutError."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(10)
            return {"response": "[]"}

        mock_llm_service.invoke_model_async.side_effect = slow_response

        # Use context with matching domain tags
        context = ConstitutionalContext(
            agent_name="TestAgent",
            operation_type="test",
            domain_tags=["test"],
        )

        # Use BLOCK policy to ensure timeout errors are raised
        config = ConstitutionalFailureConfig(
            critique_timeout_seconds=0.1,
            critique_failure_policy=CritiqueFailurePolicy.BLOCK,
        )
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            failure_config=config,
        )
        with pytest.raises(CritiqueTimeoutError) as exc_info:
            await service.critique_output(
                "test output",
                context=context,
                applicable_principles=["test_principle_1"],
            )
        assert "timed out" in str(exc_info.value).lower()


# =============================================================================
# Single Principle Critique Tests
# =============================================================================


class TestSinglePrincipleCritique:
    """Tests for critiquing against a single principle."""

    @pytest.mark.asyncio
    async def test_critique_single_principle(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test critiquing against a single principle."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        result = await service.critique_single_principle(
            "test output",
            "test_principle_1",
        )
        assert result is not None
        assert result.principle_id == "test_principle_1"

    @pytest.mark.asyncio
    async def test_critique_single_principle_not_found(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test critiquing against non-existent principle."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        result = await service.critique_single_principle(
            "test output",
            "nonexistent_principle",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_critique_single_principle_with_context(
        self, mock_llm_service, minimal_constitution_yaml
    ):
        """Test single principle critique with context."""
        # Use context with matching domain tags
        context = ConstitutionalContext(
            agent_name="TestAgent",
            operation_type="test",
            domain_tags=["test"],
        )
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
            mock_mode=True,
        )
        result = await service.critique_single_principle(
            "test output",
            "test_principle_1",
            context=context,
        )
        assert result is not None


# =============================================================================
# Prompt Building Tests
# =============================================================================


class TestPromptBuilding:
    """Tests for prompt building functionality."""

    def test_build_batch_critique_prompt(
        self,
        mock_llm_service,
        minimal_constitution_yaml,
        sample_context,
        sample_principles,
    ):
        """Test batch critique prompt building."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        prompt = service._build_batch_critique_prompt(
            "test output",
            sample_context,
            sample_principles[:2],
        )
        assert "test output" in prompt
        assert "TestAgent" in prompt
        assert "Security Check" in prompt
        assert "Compliance Check" in prompt

    def test_prompt_includes_severity(
        self,
        mock_llm_service,
        minimal_constitution_yaml,
        sample_context,
        sample_principles,
    ):
        """Test that prompt includes severity information."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        prompt = service._build_batch_critique_prompt(
            "test output",
            sample_context,
            sample_principles[:1],
        )
        assert "CRITICAL" in prompt

    def test_prompt_includes_json_format(
        self,
        mock_llm_service,
        minimal_constitution_yaml,
        sample_context,
        sample_principles,
    ):
        """Test that prompt specifies JSON output format."""
        service = ConstitutionalCritiqueService(
            llm_service=mock_llm_service,
            constitution_path=minimal_constitution_yaml,
        )
        prompt = service._build_batch_critique_prompt(
            "test output",
            sample_context,
            sample_principles[:1],
        )
        assert "JSON" in prompt or "json" in prompt
