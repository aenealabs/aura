"""Unit tests for Constitutional AI LLM-as-Judge service.

Tests the ConstitutionalJudgeService evaluation pipeline.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.constitutional_ai.evaluation_models import (
    JudgePreference,
    JudgeResult,
    ResponsePair,
)
from src.services.constitutional_ai.llm_judge_service import (
    BatchEvaluationResult,
    ConstitutionalJudgeService,
    JudgeMode,
    JudgeServiceConfig,
)
from src.services.constitutional_ai.models import ConstitutionalContext

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_bedrock_service():
    """Create a mock BedrockLLMService."""
    service = MagicMock()
    service.generate_async = AsyncMock()
    return service


@pytest.fixture
def sample_context() -> ConstitutionalContext:
    """Create a sample ConstitutionalContext."""
    return ConstitutionalContext(
        agent_name="TestAgent",
        operation_type="code_generation",
        user_request="Generate a function",
        domain_tags=["security", "testing"],
    )


@pytest.fixture
def sample_response_pair(sample_context) -> ResponsePair:
    """Create a sample ResponsePair."""
    return ResponsePair(
        pair_id="test_pair_001",
        prompt="Write a function to validate user input",
        response_a="def validate(x): return True",
        response_b="def validate(x):\n    if not x:\n        raise ValueError('Empty input')\n    return True",
        context=sample_context,
        applicable_principles=["principle_1_security_first"],
        human_preference="b",
        human_reasoning="Response B has proper input validation",
    )


@pytest.fixture
def sample_response_pairs(sample_context) -> list[ResponsePair]:
    """Create multiple sample ResponsePairs."""
    return [
        ResponsePair(
            pair_id="pair_001",
            prompt="Prompt 1",
            response_a="A1",
            response_b="B1",
            context=sample_context,
            human_preference="b",
        ),
        ResponsePair(
            pair_id="pair_002",
            prompt="Prompt 2",
            response_a="A2",
            response_b="B2",
            context=sample_context,
            human_preference="a",
        ),
        ResponsePair(
            pair_id="pair_003",
            prompt="Prompt 3",
            response_a="A3",
            response_b="B3",
            context=sample_context,
            human_preference="tie",
        ),
    ]


@pytest.fixture
def mock_judge_config() -> JudgeServiceConfig:
    """Create mock judge service config."""
    return JudgeServiceConfig(
        mode=JudgeMode.MOCK,
        batch_size=5,
        timeout_seconds=30,
    )


@pytest.fixture
def mock_judge_service(mock_judge_config) -> ConstitutionalJudgeService:
    """Create a mock ConstitutionalJudgeService."""
    return ConstitutionalJudgeService(config=mock_judge_config)


# =============================================================================
# Test JudgeServiceConfig
# =============================================================================


class TestJudgeServiceConfig:
    """Tests for JudgeServiceConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = JudgeServiceConfig()
        assert config.mode == JudgeMode.MOCK
        assert config.batch_size == 10
        assert config.timeout_seconds == 60.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = JudgeServiceConfig(
            mode=JudgeMode.AWS,
            batch_size=5,
            timeout_seconds=120,
            default_model_tier="fast",
        )
        assert config.mode == JudgeMode.AWS
        assert config.batch_size == 5
        assert config.timeout_seconds == 120
        assert config.default_model_tier == "fast"


# =============================================================================
# Test ConstitutionalJudgeService Initialization
# =============================================================================


class TestConstitutionalJudgeServiceInit:
    """Tests for ConstitutionalJudgeService initialization."""

    def test_init_mock_mode(self):
        """Test initializing in mock mode."""
        config = JudgeServiceConfig(mode=JudgeMode.MOCK)
        service = ConstitutionalJudgeService(config=config)
        assert service.config.mode == JudgeMode.MOCK

    def test_init_default_config(self):
        """Test initializing with default config."""
        service = ConstitutionalJudgeService()
        assert service.config is not None

    def test_init_with_bedrock_service(self, mock_bedrock_service):
        """Test initializing with Bedrock service."""
        config = JudgeServiceConfig(mode=JudgeMode.AWS)
        service = ConstitutionalJudgeService(
            config=config,
            bedrock_service=mock_bedrock_service,
        )
        assert service._bedrock_service is mock_bedrock_service


# =============================================================================
# Test evaluate_pair
# =============================================================================


class TestEvaluatePair:
    """Tests for evaluate_pair method."""

    @pytest.mark.asyncio
    async def test_evaluate_pair_mock_mode(
        self, mock_judge_service, sample_response_pair
    ):
        """Test evaluating a single pair in mock mode."""
        result = await mock_judge_service.evaluate_pair(sample_response_pair)
        assert isinstance(result, JudgeResult)
        assert result.pair_id == sample_response_pair.pair_id
        assert result.judge_preference in list(JudgePreference)
        assert 0.0 <= result.confidence <= 1.0
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_evaluate_pair_with_principles(
        self, mock_judge_service, sample_response_pair
    ):
        """Test evaluating with specific principles."""
        principles = ["principle_1_security_first", "principle_2_data_protection"]
        result = await mock_judge_service.evaluate_pair(
            sample_response_pair,
            principles=principles,
        )
        assert isinstance(result, JudgeResult)

    @pytest.mark.asyncio
    async def test_evaluate_pair_computes_agreement(
        self, mock_judge_service, sample_response_pair
    ):
        """Test that human agreement is computed when label available."""
        result = await mock_judge_service.evaluate_pair(sample_response_pair)
        # agrees_with_human should be set since sample_response_pair has human_preference
        assert result.agrees_with_human is not None


# =============================================================================
# Test batch_evaluate
# =============================================================================


class TestBatchEvaluate:
    """Tests for batch_evaluate method."""

    @pytest.mark.asyncio
    async def test_batch_evaluate_mock_mode(
        self, mock_judge_service, sample_response_pairs
    ):
        """Test batch evaluation in mock mode."""
        result = await mock_judge_service.batch_evaluate(sample_response_pairs)
        assert isinstance(result, BatchEvaluationResult)
        assert len(result.results) == len(sample_response_pairs)
        assert result.total_pairs == len(sample_response_pairs)

    @pytest.mark.asyncio
    async def test_batch_evaluate_calculates_accuracy(
        self, mock_judge_service, sample_response_pairs
    ):
        """Test that batch evaluation calculates accuracy vs human."""
        result = await mock_judge_service.batch_evaluate(sample_response_pairs)
        # Accuracy should be between 0 and 1 or None
        assert (
            result.accuracy_vs_human is None or 0.0 <= result.accuracy_vs_human <= 1.0
        )

    @pytest.mark.asyncio
    async def test_batch_evaluate_with_batch_size(self, sample_response_pairs):
        """Test batch evaluation with custom batch size."""
        config = JudgeServiceConfig(mode=JudgeMode.MOCK, batch_size=2)
        service = ConstitutionalJudgeService(config=config)
        result = await service.batch_evaluate(sample_response_pairs)
        assert len(result.results) == len(sample_response_pairs)

    @pytest.mark.asyncio
    async def test_batch_evaluate_empty_list(self, mock_judge_service):
        """Test batch evaluation with empty list."""
        result = await mock_judge_service.batch_evaluate([])
        assert len(result.results) == 0
        assert result.total_pairs == 0


# =============================================================================
# Test compute_accuracy
# =============================================================================


class TestComputeAccuracy:
    """Tests for compute_accuracy method."""

    def test_compute_accuracy_all_agree(self, mock_judge_service):
        """Test accuracy when all judgments agree with human."""
        results = [
            JudgeResult(
                pair_id="pair_1",
                judge_preference=JudgePreference.RESPONSE_A,
                judge_reasoning="Test reasoning",
                confidence=0.9,
                agrees_with_human=True,
            ),
            JudgeResult(
                pair_id="pair_2",
                judge_preference=JudgePreference.RESPONSE_B,
                judge_reasoning="Test reasoning",
                confidence=0.85,
                agrees_with_human=True,
            ),
        ]
        accuracy = mock_judge_service.compute_accuracy(results)
        assert accuracy == 1.0

    def test_compute_accuracy_none_agree(self, mock_judge_service):
        """Test accuracy when no judgments agree with human."""
        results = [
            JudgeResult(
                pair_id="pair_1",
                judge_preference=JudgePreference.RESPONSE_A,
                judge_reasoning="Test reasoning",
                confidence=0.9,
                agrees_with_human=False,
            ),
            JudgeResult(
                pair_id="pair_2",
                judge_preference=JudgePreference.RESPONSE_B,
                judge_reasoning="Test reasoning",
                confidence=0.85,
                agrees_with_human=False,
            ),
        ]
        accuracy = mock_judge_service.compute_accuracy(results)
        assert accuracy == 0.0

    def test_compute_accuracy_partial_agree(self, mock_judge_service):
        """Test accuracy with partial agreement."""
        results = [
            JudgeResult(
                pair_id="pair_1",
                judge_preference=JudgePreference.RESPONSE_A,
                judge_reasoning="Test reasoning",
                confidence=0.9,
                agrees_with_human=True,
            ),
            JudgeResult(
                pair_id="pair_2",
                judge_preference=JudgePreference.RESPONSE_A,
                judge_reasoning="Test reasoning",
                confidence=0.85,
                agrees_with_human=False,
            ),
        ]
        accuracy = mock_judge_service.compute_accuracy(results)
        assert accuracy == 0.5

    def test_compute_accuracy_empty_results(self, mock_judge_service):
        """Test accuracy with empty results."""
        accuracy = mock_judge_service.compute_accuracy([])
        assert accuracy == 0.0

    def test_compute_accuracy_no_human_labels(self, mock_judge_service):
        """Test accuracy when no human labels provided."""
        results = [
            JudgeResult(
                pair_id="pair_1",
                judge_preference=JudgePreference.RESPONSE_A,
                judge_reasoning="Test reasoning",
                confidence=0.9,
                agrees_with_human=None,
            ),
        ]
        accuracy = mock_judge_service.compute_accuracy(results)
        # Should handle missing human labels gracefully
        assert accuracy == 0.0


# =============================================================================
# Test evaluate_non_evasiveness
# =============================================================================


class TestEvaluateNonEvasiveness:
    """Tests for evaluate_non_evasiveness method."""

    @pytest.mark.asyncio
    async def test_evaluate_non_evasiveness_mock_mode(self, mock_judge_service):
        """Test non-evasiveness evaluation in mock mode."""
        result = await mock_judge_service.evaluate_non_evasiveness(
            response="Here's how to implement that feature: ...",
            user_request="How do I implement feature X?",
            agent_name="TestAgent",
        )
        assert "non_evasive_score" in result
        assert 0.0 <= result["non_evasive_score"] <= 1.0
        assert "is_evasive" in result

    @pytest.mark.asyncio
    async def test_evaluate_non_evasiveness_evasive_response(self, mock_judge_service):
        """Test non-evasiveness with evasive response."""
        result = await mock_judge_service.evaluate_non_evasiveness(
            response="I cannot help with that.",
            user_request="How do I implement feature X?",
            agent_name="TestAgent",
        )
        assert "non_evasive_score" in result


# =============================================================================
# Test BatchEvaluationResult
# =============================================================================


class TestBatchEvaluationResult:
    """Tests for BatchEvaluationResult model."""

    def test_to_dict(self):
        """Test BatchEvaluationResult.to_dict() serialization."""
        results = [
            JudgeResult(
                pair_id="pair_1",
                judge_preference=JudgePreference.RESPONSE_A,
                judge_reasoning="Test reasoning",
                confidence=0.9,
                agrees_with_human=True,
            ),
        ]
        batch_result = BatchEvaluationResult(
            batch_id="batch_001",
            results=results,
            total_pairs=1,
            successful_evaluations=1,
            failed_evaluations=0,
            accuracy_vs_human=1.0,
            avg_latency_ms=100.0,
            total_duration_ms=500.0,
        )
        data = batch_result.to_dict()
        assert data["total_pairs"] == 1
        assert data["accuracy_vs_human"] == 1.0
        assert len(data["results"]) == 1
        assert data["batch_id"] == "batch_001"


# =============================================================================
# Test get_stats
# =============================================================================


class TestGetStats:
    """Tests for get_stats method."""

    def test_get_stats_initial(self, mock_judge_service):
        """Test getting stats before any evaluations."""
        stats = mock_judge_service.get_stats()
        assert stats["evaluation_count"] == 0
        assert stats["mode"] == "mock"

    @pytest.mark.asyncio
    async def test_get_stats_after_evaluations(
        self, mock_judge_service, sample_response_pair
    ):
        """Test getting stats after evaluations."""
        await mock_judge_service.evaluate_pair(sample_response_pair)
        await mock_judge_service.evaluate_pair(sample_response_pair)
        stats = mock_judge_service.get_stats()
        assert stats["evaluation_count"] == 2
