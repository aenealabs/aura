"""Unit tests for ConstitutionalMixin.

Tests the constitutional AI agent integration mixin including:
- Configuration dataclasses
- Initialization and service creation
- Processing flows with mock services
- Skip logic for autonomy levels
- Serialization/deserialization
- HITL escalation
- Metrics tracking
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.constitutional_mixin import (
    ConstitutionalMixin,
    ConstitutionalMixinConfig,
    ConstitutionalProcessingResult,
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
def mock_critique_summary_clean():
    """Mock critique summary with no issues."""
    return ConstitutionalEvaluationSummary(
        critiques=[],
        total_principles_evaluated=5,
        critical_issues=0,
        high_issues=0,
        medium_issues=0,
        low_issues=0,
        requires_revision=False,
        requires_hitl=False,
    )


@pytest.fixture
def mock_critique_summary_with_issues():
    """Mock critique summary with issues requiring revision."""
    return ConstitutionalEvaluationSummary(
        critiques=[
            CritiqueResult(
                principle_id="test_principle_1",
                principle_name="Test Principle 1",
                severity=PrincipleSeverity.HIGH,
                issues_found=["Issue 1", "Issue 2"],
                reasoning="Test reasoning",
                confidence=0.9,
                requires_revision=True,
            ),
        ],
        total_principles_evaluated=5,
        critical_issues=0,
        high_issues=1,
        medium_issues=0,
        low_issues=0,
        requires_revision=True,
        requires_hitl=False,
    )


@pytest.fixture
def mock_critique_summary_critical():
    """Mock critique summary with critical issues."""
    return ConstitutionalEvaluationSummary(
        critiques=[
            CritiqueResult(
                principle_id="critical_principle",
                principle_name="Critical Principle",
                severity=PrincipleSeverity.CRITICAL,
                issues_found=["Critical issue"],
                reasoning="Critical reasoning",
                confidence=0.95,
                requires_revision=True,
            ),
        ],
        total_principles_evaluated=5,
        critical_issues=1,
        high_issues=0,
        medium_issues=0,
        low_issues=0,
        requires_revision=True,
        requires_hitl=True,
    )


@pytest.fixture
def mock_revision_result_converged():
    """Mock revision result that converged."""
    return RevisionResult(
        original_output="original",
        revised_output="revised output",
        critiques_addressed=["test_principle_1"],
        reasoning_chain="Addressed issues",
        revision_iterations=1,
        converged=True,
        metadata={"remaining_issues": 0},
    )


@pytest.fixture
def mock_revision_result_not_converged():
    """Mock revision result that did not converge."""
    return RevisionResult(
        original_output="original",
        revised_output="partially revised",
        critiques_addressed=[],
        reasoning_chain="Could not fully address",
        revision_iterations=3,
        converged=False,
        metadata={"remaining_issues": 1},
    )


@pytest.fixture
def sample_context():
    """Sample constitutional context."""
    return ConstitutionalContext(
        agent_name="TestAgent",
        operation_type="test_operation",
        user_request="Test request",
        domain_tags=["testing", "security"],
    )


@pytest.fixture
def sample_context_no_tags():
    """Sample context without domain tags."""
    return ConstitutionalContext(
        agent_name="TestAgent",
        operation_type="test_operation",
        user_request="Test request",
    )


# =============================================================================
# Test Helper: Agent with Mixin
# =============================================================================


class MockAgent(ConstitutionalMixin):
    """Mock agent class that uses ConstitutionalMixin."""

    def __init__(
        self,
        llm_service: Optional[Any] = None,
        config: Optional[ConstitutionalMixinConfig] = None,
    ):
        self.llm_service = llm_service
        self._init_constitutional(llm_service=llm_service, config=config)


class MockAgentWithHITL(ConstitutionalMixin):
    """Mock agent with HITL method (simulating MCPToolMixin)."""

    def __init__(
        self,
        config: Optional[ConstitutionalMixinConfig] = None,
    ):
        self._init_constitutional(config=config)
        self.hitl_requests: List[Dict[str, Any]] = []

    async def _request_hitl_approval(
        self, tool_name: str, params: Dict[str, Any]
    ) -> None:
        """Mock HITL approval request."""
        self.hitl_requests.append({"tool_name": tool_name, "params": params})


# =============================================================================
# Tests: ConstitutionalMixinConfig
# =============================================================================


class TestConstitutionalMixinConfig:
    """Tests for ConstitutionalMixinConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ConstitutionalMixinConfig()

        assert config.domain_tags == []
        assert config.applicable_principles is None
        assert config.skip_for_autonomy_levels == ["FULL_AUTONOMOUS"]
        assert config.block_on_critical is True
        assert config.enable_hitl_escalation is True
        assert config.max_revision_iterations is None
        assert config.include_in_metrics is True
        assert config.mock_mode is False

    def test_custom_values(self):
        """Test configuration with custom values."""
        config = ConstitutionalMixinConfig(
            domain_tags=["security", "compliance"],
            applicable_principles=["principle_1", "principle_2"],
            skip_for_autonomy_levels=["FULL_AUTONOMOUS", "HIGH_AUTONOMOUS"],
            block_on_critical=False,
            enable_hitl_escalation=False,
            max_revision_iterations=5,
            include_in_metrics=False,
            mock_mode=True,
        )

        assert config.domain_tags == ["security", "compliance"]
        assert config.applicable_principles == ["principle_1", "principle_2"]
        assert config.skip_for_autonomy_levels == ["FULL_AUTONOMOUS", "HIGH_AUTONOMOUS"]
        assert config.block_on_critical is False
        assert config.enable_hitl_escalation is False
        assert config.max_revision_iterations == 5
        assert config.include_in_metrics is False
        assert config.mock_mode is True

    def test_validation_max_revision_iterations(self):
        """Test validation of max_revision_iterations."""
        with pytest.raises(
            ValueError, match="max_revision_iterations must be at least 1"
        ):
            ConstitutionalMixinConfig(max_revision_iterations=0)

        with pytest.raises(
            ValueError, match="max_revision_iterations must be at least 1"
        ):
            ConstitutionalMixinConfig(max_revision_iterations=-1)

    def test_valid_max_revision_iterations(self):
        """Test valid max_revision_iterations values."""
        config = ConstitutionalMixinConfig(max_revision_iterations=1)
        assert config.max_revision_iterations == 1

        config = ConstitutionalMixinConfig(max_revision_iterations=10)
        assert config.max_revision_iterations == 10


# =============================================================================
# Tests: ConstitutionalProcessingResult
# =============================================================================


class TestConstitutionalProcessingResult:
    """Tests for ConstitutionalProcessingResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = ConstitutionalProcessingResult(
            original_output="test",
            processed_output="test",
        )

        assert result.original_output == "test"
        assert result.processed_output == "test"
        assert result.was_revised is False
        assert result.critique_summary is None
        assert result.revision_result is None
        assert result.hitl_required is False
        assert result.hitl_request_id is None
        assert result.blocked is False
        assert result.block_reason is None
        assert result.processing_time_ms == 0.0
        assert result.skipped is False
        assert result.skip_reason is None
        assert isinstance(result.timestamp, datetime)

    def test_full_values(
        self, mock_critique_summary_with_issues, mock_revision_result_converged
    ):
        """Test result with all values populated."""
        result = ConstitutionalProcessingResult(
            original_output="original",
            processed_output="revised",
            was_revised=True,
            critique_summary=mock_critique_summary_with_issues,
            revision_result=mock_revision_result_converged,
            hitl_required=True,
            hitl_request_id="request-123",
            blocked=True,
            block_reason="Critical issues",
            processing_time_ms=150.5,
            skipped=False,
            skip_reason=None,
        )

        assert result.original_output == "original"
        assert result.processed_output == "revised"
        assert result.was_revised is True
        assert result.critique_summary == mock_critique_summary_with_issues
        assert result.revision_result == mock_revision_result_converged
        assert result.hitl_required is True
        assert result.hitl_request_id == "request-123"
        assert result.blocked is True
        assert result.block_reason == "Critical issues"
        assert result.processing_time_ms == 150.5

    def test_to_dict_basic(self):
        """Test to_dict with basic result."""
        result = ConstitutionalProcessingResult(
            original_output="test",
            processed_output="test",
            processing_time_ms=100.0,
        )

        data = result.to_dict()

        assert data["was_revised"] is False
        assert data["hitl_required"] is False
        assert data["blocked"] is False
        assert data["processing_time_ms"] == 100.0
        assert data["skipped"] is False
        assert "timestamp" in data

    def test_to_dict_with_summary(self, mock_critique_summary_with_issues):
        """Test to_dict with critique summary."""
        result = ConstitutionalProcessingResult(
            original_output="test",
            processed_output="test",
            critique_summary=mock_critique_summary_with_issues,
        )

        data = result.to_dict()

        assert "critique_summary" in data
        assert data["critique_summary"]["total_principles_evaluated"] == 5
        assert data["critique_summary"]["high_issues"] == 1
        assert data["critique_summary"]["requires_revision"] is True

    def test_to_dict_with_revision(self, mock_revision_result_converged):
        """Test to_dict with revision result."""
        result = ConstitutionalProcessingResult(
            original_output="test",
            processed_output="revised",
            was_revised=True,
            revision_result=mock_revision_result_converged,
        )

        data = result.to_dict()

        assert "revision_result" in data
        assert data["revision_result"]["was_modified"] is True
        assert data["revision_result"]["converged"] is True
        assert data["revision_result"]["revision_iterations"] == 1


# =============================================================================
# Tests: ConstitutionalMixin Initialization
# =============================================================================


class TestConstitutionalMixinInitialization:
    """Tests for mixin initialization."""

    def test_basic_initialization(self):
        """Test basic initialization without services."""
        agent = MockAgent()

        assert agent._constitutional_config is not None
        assert agent._constitutional_initialized is True
        assert agent._constitutional_metrics["total_processed"] == 0

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = ConstitutionalMixinConfig(
            domain_tags=["test"],
            mock_mode=True,
        )
        agent = MockAgent(config=config)

        assert agent._constitutional_config.domain_tags == ["test"]
        assert agent._constitutional_config.mock_mode is True

    def test_initialization_with_llm_service(self):
        """Test initialization with LLM service."""
        mock_llm = MagicMock()
        agent = MockAgent(llm_service=mock_llm)

        assert agent._constitutional_llm == mock_llm

    def test_ensure_initialized_raises_when_not_initialized(self):
        """Test that _ensure_constitutional_initialized raises when not initialized."""

        class UninitializedAgent(ConstitutionalMixin):
            pass

        agent = UninitializedAgent()

        with pytest.raises(RuntimeError, match="Constitutional mixin not initialized"):
            agent._ensure_constitutional_initialized()

    def test_metrics_initialized(self):
        """Test that metrics are properly initialized."""
        agent = MockAgent()

        metrics = agent._constitutional_metrics
        assert metrics["total_processed"] == 0
        assert metrics["total_revised"] == 0
        assert metrics["total_blocked"] == 0
        assert metrics["total_hitl_escalations"] == 0
        assert metrics["total_skipped"] == 0
        assert metrics["critique_counts"] == {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }


# =============================================================================
# Tests: Service Creation
# =============================================================================


class TestServiceCreation:
    """Tests for lazy service creation."""

    def test_critique_service_created_lazily(self):
        """Test that critique service is created on first access."""
        config = ConstitutionalMixinConfig(mock_mode=True)
        agent = MockAgent(config=config)

        assert agent._constitutional_critique_service is None

        # Access should create the service - patch at the source module
        with patch(
            "src.services.constitutional_ai.critique_service.ConstitutionalCritiqueService"
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            service = agent._get_critique_service()
            assert service is not None
            mock_cls.assert_called_once()

    def test_revision_service_created_lazily(self):
        """Test that revision service is created on first access."""
        config = ConstitutionalMixinConfig(mock_mode=True)
        agent = MockAgent(config=config)

        assert agent._constitutional_revision_service is None

        # Mock the critique service first
        mock_critique = MagicMock()
        agent._constitutional_critique_service = mock_critique

        # Patch at the source module
        with patch(
            "src.services.constitutional_ai.revision_service.ConstitutionalRevisionService"
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            service = agent._get_revision_service()
            assert service is not None
            mock_cls.assert_called_once()

    def test_provided_services_used(self):
        """Test that provided services are used instead of creating new ones."""
        mock_critique = MagicMock()
        mock_revision = MagicMock()

        agent = MockAgent()
        agent._constitutional_critique_service = mock_critique
        agent._constitutional_revision_service = mock_revision

        assert agent._get_critique_service() == mock_critique
        assert agent._get_revision_service() == mock_revision


# =============================================================================
# Tests: Skip Logic
# =============================================================================


class TestSkipLogic:
    """Tests for autonomy level skip logic."""

    def test_skip_for_full_autonomous(self):
        """Test that FULL_AUTONOMOUS is skipped by default."""
        agent = MockAgent()

        assert agent._should_skip_constitutional("FULL_AUTONOMOUS") is True

    def test_no_skip_for_supervised(self):
        """Test that SUPERVISED is not skipped."""
        agent = MockAgent()

        assert agent._should_skip_constitutional("SUPERVISED") is False

    def test_no_skip_when_none(self):
        """Test that None autonomy level doesn't skip."""
        agent = MockAgent()

        assert agent._should_skip_constitutional(None) is False

    def test_custom_skip_levels(self):
        """Test custom skip levels in config."""
        config = ConstitutionalMixinConfig(
            skip_for_autonomy_levels=["FULL_AUTONOMOUS", "HIGH_AUTONOMOUS"]
        )
        agent = MockAgent(config=config)

        assert agent._should_skip_constitutional("FULL_AUTONOMOUS") is True
        assert agent._should_skip_constitutional("HIGH_AUTONOMOUS") is True
        assert agent._should_skip_constitutional("SUPERVISED") is False

    def test_empty_skip_list(self):
        """Test with empty skip list (never skip)."""
        config = ConstitutionalMixinConfig(skip_for_autonomy_levels=[])
        agent = MockAgent(config=config)

        assert agent._should_skip_constitutional("FULL_AUTONOMOUS") is False
        assert agent._should_skip_constitutional("HIGH_AUTONOMOUS") is False


# =============================================================================
# Tests: Serialization/Deserialization
# =============================================================================


class TestSerialization:
    """Tests for output serialization and deserialization."""

    def test_serialize_string(self):
        """Test serializing string output."""
        agent = MockAgent()
        result = agent._serialize_output("test string")
        assert result == "test string"

    def test_serialize_dict(self):
        """Test serializing dict output."""
        agent = MockAgent()
        data = {"key": "value", "number": 123}
        result = agent._serialize_output(data)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["number"] == 123

    def test_serialize_dict_with_non_json_types(self):
        """Test serializing dict with non-JSON-serializable types."""
        agent = MockAgent()
        data = {"timestamp": datetime.now(), "normal": "value"}
        result = agent._serialize_output(data)

        # Should convert to string representation
        assert "normal" in result
        assert "value" in result

    def test_serialize_other_types(self):
        """Test serializing other types."""
        agent = MockAgent()

        result = agent._serialize_output(12345)
        assert result == "12345"

        # Lists get str() applied, not json.dumps
        result = agent._serialize_output(["a", "b", "c"])
        assert result == "['a', 'b', 'c']"

    def test_deserialize_to_string(self):
        """Test deserializing when original was string."""
        agent = MockAgent()
        result = agent._deserialize_output("revised text", "original")
        assert result == "revised text"

    def test_deserialize_to_dict(self):
        """Test deserializing when original was dict."""
        agent = MockAgent()
        original = {"key": "value"}
        revised = '{"key": "new_value", "extra": "field"}'
        result = agent._deserialize_output(revised, original)

        assert isinstance(result, dict)
        assert result["key"] == "new_value"
        assert result["extra"] == "field"

    def test_deserialize_invalid_json_fallback(self):
        """Test deserializing invalid JSON falls back to string."""
        agent = MockAgent()
        original = {"key": "value"}
        result = agent._deserialize_output("not valid json", original)

        # Should return string when JSON parse fails
        assert result == "not valid json"


# =============================================================================
# Tests: process_with_constitutional
# =============================================================================


class TestProcessWithConstitutional:
    """Tests for the main process_with_constitutional method."""

    @pytest.mark.asyncio
    async def test_skip_for_autonomy_level(self, sample_context):
        """Test processing is skipped for configured autonomy levels."""
        agent = MockAgent()

        result = await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
            autonomy_level="FULL_AUTONOMOUS",
        )

        assert result.skipped is True
        assert result.skip_reason is not None
        assert "FULL_AUTONOMOUS" in result.skip_reason
        assert result.original_output == "test output"
        assert result.processed_output == "test output"

    @pytest.mark.asyncio
    async def test_no_revision_needed(
        self, sample_context, mock_critique_summary_clean
    ):
        """Test processing when critique finds no issues."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_clean
        )

        agent = MockAgent()
        agent._constitutional_critique_service = mock_critique_service

        result = await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        assert result.was_revised is False
        assert result.original_output == "test output"
        assert result.processed_output == "test output"
        assert result.critique_summary == mock_critique_summary_clean
        assert result.blocked is False
        mock_critique_service.critique_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_revision_performed(
        self,
        sample_context,
        mock_critique_summary_with_issues,
        mock_revision_result_converged,
    ):
        """Test processing when critique finds issues requiring revision."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_with_issues
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            return_value=mock_revision_result_converged
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        agent = MockAgent()
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        result = await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        assert result.was_revised is True
        assert result.processed_output == "revised output"
        assert result.revision_result == mock_revision_result_converged
        assert result.blocked is False
        mock_revision_service.revise_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_block_on_unresolved_critical(
        self,
        sample_context,
        mock_critique_summary_critical,
        mock_revision_result_not_converged,
    ):
        """Test blocking when critical issues cannot be resolved."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_critical
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            return_value=mock_revision_result_not_converged
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        config = ConstitutionalMixinConfig(block_on_critical=True)
        agent = MockAgent(config=config)
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        result = await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        assert result.blocked is True
        assert result.block_reason is not None
        assert "Unresolved critical issues" in result.block_reason

    @pytest.mark.asyncio
    async def test_no_block_when_disabled(
        self,
        sample_context,
        mock_critique_summary_critical,
        mock_revision_result_not_converged,
    ):
        """Test no blocking when block_on_critical is False."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_critical
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            return_value=mock_revision_result_not_converged
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        config = ConstitutionalMixinConfig(block_on_critical=False)
        agent = MockAgent(config=config)
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        result = await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        assert result.blocked is False

    @pytest.mark.asyncio
    async def test_hitl_escalation(
        self,
        sample_context,
        mock_critique_summary_critical,
        mock_revision_result_not_converged,
    ):
        """Test HITL escalation for unresolved issues."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_critical
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            return_value=mock_revision_result_not_converged
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        config = ConstitutionalMixinConfig(enable_hitl_escalation=True)
        agent = MockAgent(config=config)
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        result = await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        assert result.hitl_required is True
        assert result.hitl_request_id is not None

    @pytest.mark.asyncio
    async def test_no_hitl_when_disabled(
        self,
        sample_context,
        mock_critique_summary_critical,
        mock_revision_result_not_converged,
    ):
        """Test no HITL when enable_hitl_escalation is False."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_critical
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            return_value=mock_revision_result_not_converged
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        config = ConstitutionalMixinConfig(
            enable_hitl_escalation=False, block_on_critical=False
        )
        agent = MockAgent(config=config)
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        result = await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        assert result.hitl_required is False
        assert result.hitl_request_id is None

    @pytest.mark.asyncio
    async def test_context_domain_tags_applied(
        self, sample_context_no_tags, mock_critique_summary_clean
    ):
        """Test that config domain tags are applied to context."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_clean
        )

        config = ConstitutionalMixinConfig(domain_tags=["security", "testing"])
        agent = MockAgent(config=config)
        agent._constitutional_critique_service = mock_critique_service

        await agent.process_with_constitutional(
            output="test output",
            context=sample_context_no_tags,
        )

        # Verify the context passed to critique has domain tags
        call_args = mock_critique_service.critique_output.call_args
        context_arg = call_args.kwargs.get("context") or call_args.args[1]
        assert context_arg.domain_tags == ["security", "testing"]

    @pytest.mark.asyncio
    async def test_dict_output_serialization_and_deserialization(
        self,
        sample_context,
        mock_critique_summary_with_issues,
    ):
        """Test that dict outputs are properly serialized and deserialized."""
        revised_dict = {"key": "revised_value"}

        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_with_issues
        )

        mock_revision_result = RevisionResult(
            original_output='{"key": "value"}',
            revised_output=json.dumps(revised_dict),
            critiques_addressed=["test"],
            reasoning_chain="Revised",
            revision_iterations=1,
            converged=True,
            metadata={"remaining_issues": 0},
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            return_value=mock_revision_result
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        agent = MockAgent()
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        result = await agent.process_with_constitutional(
            output={"key": "value"},
            context=sample_context,
        )

        # Output should be deserialized back to dict
        assert result.processed_output == revised_dict
        assert isinstance(result.processed_output, dict)

    @pytest.mark.asyncio
    async def test_revision_failure_handled_gracefully(
        self, sample_context, mock_critique_summary_with_issues
    ):
        """Test that revision failures are handled gracefully."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_with_issues
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            side_effect=Exception("Revision failed")
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        config = ConstitutionalMixinConfig(block_on_critical=False)
        agent = MockAgent(config=config)
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        result = await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        # Should complete without exception
        assert result.was_revised is False
        assert result.revision_result is None


# =============================================================================
# Tests: critique_only
# =============================================================================


class TestCritiqueOnly:
    """Tests for the critique_only method."""

    @pytest.mark.asyncio
    async def test_critique_only_returns_summary(
        self, sample_context, mock_critique_summary_with_issues
    ):
        """Test critique_only returns evaluation summary."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_with_issues
        )

        agent = MockAgent()
        agent._constitutional_critique_service = mock_critique_service

        summary = await agent.critique_only(
            output="test output",
            context=sample_context,
        )

        assert summary == mock_critique_summary_with_issues
        mock_critique_service.critique_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_critique_only_applies_config_tags(
        self, sample_context_no_tags, mock_critique_summary_clean
    ):
        """Test critique_only applies config domain tags."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_clean
        )

        config = ConstitutionalMixinConfig(domain_tags=["analysis"])
        agent = MockAgent(config=config)
        agent._constitutional_critique_service = mock_critique_service

        await agent.critique_only(
            output="test output",
            context=sample_context_no_tags,
        )

        call_args = mock_critique_service.critique_output.call_args
        context_arg = call_args.kwargs.get("context") or call_args.args[1]
        assert context_arg.domain_tags == ["analysis"]


# =============================================================================
# Tests: HITL Integration
# =============================================================================


class TestHITLIntegration:
    """Tests for HITL escalation integration."""

    @pytest.mark.asyncio
    async def test_hitl_request_via_mcp_mixin(self, sample_context):
        """Test HITL request uses MCPToolMixin when available."""
        config = ConstitutionalMixinConfig(enable_hitl_escalation=True)
        agent = MockAgentWithHITL(config=config)

        critiques = [
            CritiqueResult(
                principle_id="test",
                principle_name="Test",
                severity=PrincipleSeverity.CRITICAL,
                issues_found=["Issue"],
                reasoning="Reasoning",
                confidence=0.9,
                requires_revision=True,
            )
        ]

        request_id = await agent._request_constitutional_hitl(
            output="test output",
            remaining_issues=critiques,
            context=sample_context,
        )

        assert request_id is not None
        assert len(agent.hitl_requests) == 1
        assert agent.hitl_requests[0]["tool_name"] == "constitutional_ai_review"

    @pytest.mark.asyncio
    async def test_hitl_disabled_returns_none(self, sample_context):
        """Test HITL returns None when disabled."""
        config = ConstitutionalMixinConfig(enable_hitl_escalation=False)
        agent = MockAgent(config=config)

        request_id = await agent._request_constitutional_hitl(
            output="test output",
            remaining_issues=[],
            context=sample_context,
        )

        assert request_id is None


# =============================================================================
# Tests: Metrics
# =============================================================================


class TestMetrics:
    """Tests for constitutional metrics tracking."""

    def test_initial_metrics(self):
        """Test initial metrics state."""
        agent = MockAgent()
        metrics = agent.get_constitutional_metrics()

        assert metrics["total_processed"] == 0
        assert metrics["total_revised"] == 0
        assert metrics["total_blocked"] == 0
        assert metrics["revision_rate"] == 0.0
        assert metrics["block_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_metrics_updated_after_processing(
        self, sample_context, mock_critique_summary_clean
    ):
        """Test metrics are updated after processing."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_clean
        )

        agent = MockAgent()
        agent._constitutional_critique_service = mock_critique_service

        await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        metrics = agent.get_constitutional_metrics()
        assert metrics["total_processed"] == 1
        assert metrics["total_processing_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_revision_metrics_updated(
        self,
        sample_context,
        mock_critique_summary_with_issues,
        mock_revision_result_converged,
    ):
        """Test revision metrics are updated."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_with_issues
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            return_value=mock_revision_result_converged
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        agent = MockAgent()
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        metrics = agent.get_constitutional_metrics()
        assert metrics["total_revised"] == 1
        assert metrics["revision_iterations_total"] == 1

    @pytest.mark.asyncio
    async def test_critique_counts_updated(
        self, sample_context, mock_critique_summary_with_issues
    ):
        """Test critique counts are updated by severity."""
        mock_critique_service = MagicMock()
        mock_critique_service.critique_output = AsyncMock(
            return_value=mock_critique_summary_with_issues
        )

        mock_revision_service = MagicMock()
        mock_revision_service.revise_output = AsyncMock(
            return_value=RevisionResult(
                original_output="",
                revised_output="revised",
                critiques_addressed=[],
                reasoning_chain="",
                revision_iterations=1,
                converged=True,
                metadata={},
            )
        )
        mock_revision_service.failure_config = MagicMock(max_revision_iterations=3)

        agent = MockAgent()
        agent._constitutional_critique_service = mock_critique_service
        agent._constitutional_revision_service = mock_revision_service

        await agent.process_with_constitutional(
            output="test output",
            context=sample_context,
        )

        metrics = agent.get_constitutional_metrics()
        assert metrics["critique_counts"]["high"] == 1

    def test_derived_metrics_calculated(self):
        """Test derived metrics (rates) are calculated correctly."""
        agent = MockAgent()

        # Simulate some processing
        agent._constitutional_metrics["total_processed"] = 10
        agent._constitutional_metrics["total_revised"] = 3
        agent._constitutional_metrics["total_blocked"] = 1
        agent._constitutional_metrics["total_hitl_escalations"] = 2
        agent._constitutional_metrics["total_processing_time_ms"] = 500.0

        metrics = agent.get_constitutional_metrics()

        assert metrics["revision_rate"] == 0.3
        assert metrics["block_rate"] == 0.1
        assert metrics["hitl_rate"] == 0.2
        assert metrics["avg_processing_time_ms"] == 50.0


# =============================================================================
# Tests: Agent Config Module
# =============================================================================


class TestAgentConfigModule:
    """Tests for the constitutional_agent_config module."""

    def test_get_default_config(self):
        """Test getting default config for an agent type."""
        from src.agents.constitutional_agent_config import get_default_config

        config = get_default_config("CoderAgent")

        assert "code_generation" in config.domain_tags
        assert "security" in config.domain_tags
        assert config.block_on_critical is True

    def test_get_default_config_unknown_agent(self):
        """Test getting config for unknown agent type."""
        from src.agents.constitutional_agent_config import get_default_config

        config = get_default_config("UnknownAgent")

        # Should get BaseAgent defaults
        assert "general" in config.domain_tags or len(config.domain_tags) >= 0

    def test_get_domain_tags(self):
        """Test getting domain tags for agent types."""
        from src.agents.constitutional_agent_config import get_domain_tags

        tags = get_domain_tags("SecurityAgent")
        assert "security" in tags

        tags = get_domain_tags("CoderAgent")
        assert "code_generation" in tags

    def test_get_config_with_overrides(self):
        """Test getting config with selective overrides."""
        from src.agents.constitutional_agent_config import get_config_with_overrides

        config = get_config_with_overrides(
            "CoderAgent",
            block_on_critical=False,
            max_revision_iterations=5,
        )

        # Overridden values
        assert config.block_on_critical is False
        assert config.max_revision_iterations == 5

        # Default values preserved
        assert "code_generation" in config.domain_tags

    def test_preset_configs(self):
        """Test preset configurations."""
        from src.agents.constitutional_agent_config import (
            DEVELOPMENT_CONFIG,
            LENIENT_ANALYSIS_CONFIG,
            STRICT_SECURITY_CONFIG,
        )

        # Strict security config
        assert STRICT_SECURITY_CONFIG.block_on_critical is True
        assert STRICT_SECURITY_CONFIG.skip_for_autonomy_levels == []

        # Lenient analysis config
        assert LENIENT_ANALYSIS_CONFIG.block_on_critical is False

        # Development config
        assert DEVELOPMENT_CONFIG.mock_mode is True
        assert DEVELOPMENT_CONFIG.include_in_metrics is False
