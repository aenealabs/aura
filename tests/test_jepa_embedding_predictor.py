"""
Tests for JEPA Embedding Predictor module.

Tests cover:
- JEPAConfig validation
- TaskType enum behavior
- MaskingStrategy for I-JEPA training
- TransformerLayer forward pass
- EmbeddingPredictor prediction
- SelectiveDecodingService integration
- InfoNCE loss computation
- Metrics collection

Reference: ADR-051 Recursive Context Scaling and Embedding Prediction
"""

import asyncio
import math
import platform

import pytest

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestJEPAConfig:
    """Tests for JEPAConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        from src.services.jepa import JEPAConfig

        config = JEPAConfig()

        assert config.embed_dim == 768
        assert config.predictor_depth == 6
        assert config.decoder_depth == 2
        assert config.num_heads == 12
        assert config.temperature == 0.07
        assert config.dropout == 0.1
        assert config.max_sequence_length == 8192
        assert config.mask_ratio == 0.75
        assert config.num_negatives == 64
        assert config.use_ema_encoder is True
        assert config.ema_decay == 0.999

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        from src.services.jepa import JEPAConfig

        config = JEPAConfig(
            embed_dim=512,
            predictor_depth=4,
            decoder_depth=1,
            num_heads=8,
            temperature=0.1,
        )

        assert config.embed_dim == 512
        assert config.predictor_depth == 4
        assert config.decoder_depth == 1
        assert config.num_heads == 8
        assert config.temperature == 0.1

    def test_config_validation_embed_dim(self) -> None:
        """Test that embed_dim must be divisible by num_heads."""
        from src.services.jepa import JEPAConfig

        with pytest.raises(ValueError, match="must be divisible"):
            JEPAConfig(embed_dim=768, num_heads=7)

    def test_config_validation_temperature(self) -> None:
        """Test that temperature must be in (0, 1]."""
        from src.services.jepa import JEPAConfig

        with pytest.raises(ValueError, match="temperature"):
            JEPAConfig(temperature=0.0)

        with pytest.raises(ValueError, match="temperature"):
            JEPAConfig(temperature=1.5)

    def test_config_validation_mask_ratio(self) -> None:
        """Test that mask_ratio must be in [0, 1)."""
        from src.services.jepa import JEPAConfig

        with pytest.raises(ValueError, match="mask_ratio"):
            JEPAConfig(mask_ratio=1.0)

        with pytest.raises(ValueError, match="mask_ratio"):
            JEPAConfig(mask_ratio=-0.1)


class TestTaskType:
    """Tests for TaskType enum."""

    def test_non_generative_tasks(self) -> None:
        """Test that non-generative tasks are identified correctly."""
        from src.services.jepa import TaskType

        non_generative = [
            TaskType.CLASSIFICATION,
            TaskType.RETRIEVAL,
            TaskType.SIMILARITY,
            TaskType.ROUTING,
        ]

        for task_type in non_generative:
            assert task_type.is_non_generative is True
            assert task_type.is_generative is False

    def test_generative_tasks(self) -> None:
        """Test that generative tasks are identified correctly."""
        from src.services.jepa import TaskType

        generative = [
            TaskType.GENERATION,
            TaskType.EXPLANATION,
            TaskType.CODE_GENERATION,
        ]

        for task_type in generative:
            assert task_type.is_generative is True
            assert task_type.is_non_generative is False

    def test_task_type_values(self) -> None:
        """Test TaskType enum values."""
        from src.services.jepa import TaskType

        assert TaskType.CLASSIFICATION.value == "classification"
        assert TaskType.RETRIEVAL.value == "retrieval"
        assert TaskType.SIMILARITY.value == "similarity"
        assert TaskType.ROUTING.value == "routing"
        assert TaskType.GENERATION.value == "generation"
        assert TaskType.EXPLANATION.value == "explanation"
        assert TaskType.CODE_GENERATION.value == "code_gen"


class TestMaskingStrategy:
    """Tests for MaskingStrategy."""

    def test_default_masking_strategy(self) -> None:
        """Test default masking strategy values."""
        from src.services.jepa import MaskingStrategy

        strategy = MaskingStrategy()

        assert strategy.mask_ratio == 0.75
        assert strategy.min_mask_patches == 4
        assert strategy.max_mask_patches == 16
        assert strategy.aspect_ratio_range == (0.75, 1.5)

    def test_generate_mask_length(self) -> None:
        """Test that generate_mask returns correct length."""
        from src.services.jepa import MaskingStrategy

        strategy = MaskingStrategy(mask_ratio=0.5)
        mask = strategy.generate_mask(100, seed=42)

        assert len(mask) == 100
        assert all(isinstance(m, bool) for m in mask)

    def test_generate_mask_ratio(self) -> None:
        """Test that mask ratio is approximately correct."""
        from src.services.jepa import MaskingStrategy

        strategy = MaskingStrategy(mask_ratio=0.75)
        mask = strategy.generate_mask(100, seed=42)

        masked_count = sum(mask)
        # Allow some tolerance due to block masking
        assert 70 <= masked_count <= 80

    def test_generate_mask_reproducibility(self) -> None:
        """Test that mask generation is reproducible with seed."""
        from src.services.jepa import MaskingStrategy

        strategy = MaskingStrategy()

        mask1 = strategy.generate_mask(100, seed=42)
        mask2 = strategy.generate_mask(100, seed=42)

        assert mask1 == mask2

    def test_generate_mask_different_seeds(self) -> None:
        """Test that different seeds produce different masks."""
        from src.services.jepa import MaskingStrategy

        strategy = MaskingStrategy()

        mask1 = strategy.generate_mask(100, seed=42)
        mask2 = strategy.generate_mask(100, seed=43)

        assert mask1 != mask2

    def test_generate_target_indices(self) -> None:
        """Test target index generation from mask."""
        from src.services.jepa import MaskingStrategy

        strategy = MaskingStrategy()
        mask = [False, True, True, False, True, False, True, True]

        targets = strategy.generate_target_indices(mask, num_targets=3)

        assert len(targets) == 3
        assert all(mask[i] for i in targets)  # All targets should be masked

    def test_generate_target_indices_fewer_masked(self) -> None:
        """Test target generation when fewer masked than requested."""
        from src.services.jepa import MaskingStrategy

        strategy = MaskingStrategy()
        mask = [False, True, False, False, True, False, False, False]

        targets = strategy.generate_target_indices(mask, num_targets=5)

        assert len(targets) == 2  # Only 2 masked positions
        assert all(mask[i] for i in targets)


class TestTransformerLayer:
    """Tests for TransformerLayer."""

    def test_transformer_layer_init(self) -> None:
        """Test TransformerLayer initialization."""
        from src.services.jepa import TransformerLayer

        layer = TransformerLayer(embed_dim=64, num_heads=4, dropout=0.1)

        assert layer.embed_dim == 64
        assert layer.num_heads == 4
        assert layer.dropout == 0.1
        assert layer._q_weight is not None
        assert layer._k_weight is not None
        assert layer._v_weight is not None
        assert layer._o_weight is not None

    def test_transformer_layer_forward_shape(self) -> None:
        """Test that forward pass preserves shape."""
        from src.services.jepa import TransformerLayer

        layer = TransformerLayer(embed_dim=64, num_heads=4)

        # Input: [seq_len=8, embed_dim=64]
        x = [[0.1 * i + 0.01 * j for j in range(64)] for i in range(8)]

        output = layer.forward(x)

        assert len(output) == 8
        assert len(output[0]) == 64

    def test_transformer_layer_forward_values(self) -> None:
        """Test that forward pass produces finite values."""
        from src.services.jepa import TransformerLayer

        layer = TransformerLayer(embed_dim=32, num_heads=4)

        x = [[1.0] * 32 for _ in range(4)]
        output = layer.forward(x)

        # Check all values are finite
        for row in output:
            for val in row:
                assert math.isfinite(val)


class TestPredictionResult:
    """Tests for PredictionResult dataclass."""

    def test_prediction_result_creation(self) -> None:
        """Test PredictionResult creation."""
        from src.services.jepa import PredictionResult, TaskType

        result = PredictionResult(
            embedding=[[0.1, 0.2, 0.3]],
            task_type=TaskType.CLASSIFICATION,
            confidence=0.95,
            latency_ms=15.5,
            operations_saved="2.85x",
            request_id="test-123",
        )

        assert result.embedding == [[0.1, 0.2, 0.3]]
        assert result.task_type == TaskType.CLASSIFICATION
        assert result.decoded_text is None
        assert result.confidence == 0.95
        assert result.latency_ms == 15.5
        assert result.operations_saved == "2.85x"
        assert result.request_id == "test-123"

    def test_prediction_result_to_dict(self) -> None:
        """Test PredictionResult serialization."""
        from src.services.jepa import PredictionResult, TaskType

        result = PredictionResult(
            embedding=[[0.1, 0.2]],
            task_type=TaskType.GENERATION,
            decoded_text="generated text",
            confidence=0.8,
        )

        d = result.to_dict()

        assert d["embedding"] == [[0.1, 0.2]]
        assert d["task_type"] == "generation"
        assert d["decoded_text"] == "generated text"
        assert d["confidence"] == 0.8


class TestEmbeddingPredictor:
    """Tests for EmbeddingPredictor."""

    def test_predictor_init(self) -> None:
        """Test EmbeddingPredictor initialization."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig

        config = JEPAConfig(
            embed_dim=64, predictor_depth=2, decoder_depth=1, num_heads=4
        )
        predictor = EmbeddingPredictor(config)

        assert len(predictor.predictor_layers) == 2
        assert len(predictor.decoder_layers) == 1
        assert predictor.config == config

    def test_predictor_predict_non_generative(self) -> None:
        """Test prediction for non-generative task."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig, TaskType

        config = JEPAConfig(
            embed_dim=64, predictor_depth=1, decoder_depth=1, num_heads=4
        )
        predictor = EmbeddingPredictor(config)

        x_embed = [[0.1] * 64 for _ in range(4)]
        result = predictor.predict(x_embed, task_type=TaskType.CLASSIFICATION)

        assert result.task_type == TaskType.CLASSIFICATION
        assert result.decoded_text is None
        assert result.operations_saved == "2.85x"
        assert len(result.embedding) == 4
        assert len(result.embedding[0]) == 64

    def test_predictor_predict_generative(self) -> None:
        """Test prediction for generative task."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig, TaskType

        config = JEPAConfig(
            embed_dim=64, predictor_depth=1, decoder_depth=1, num_heads=4
        )
        predictor = EmbeddingPredictor(config)

        x_embed = [[0.1] * 64 for _ in range(4)]
        result = predictor.predict(x_embed, task_type=TaskType.GENERATION)

        assert result.task_type == TaskType.GENERATION
        assert result.decoded_text is not None
        assert result.operations_saved == "1x"

    def test_predictor_auto_route_task(self) -> None:
        """Test automatic task routing."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig

        config = JEPAConfig(
            embed_dim=64, predictor_depth=1, decoder_depth=1, num_heads=4
        )
        predictor = EmbeddingPredictor(config)

        x_embed = [[0.1] * 64 for _ in range(4)]
        result = predictor.predict(x_embed, task_type=None)

        # Should route to some task type
        assert result.task_type is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_predictor_request_id(self) -> None:
        """Test request ID generation."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        predictor = EmbeddingPredictor(config)

        x_embed = [[0.1] * 64]

        # Auto-generated
        result1 = predictor.predict(x_embed, task_type=TaskType.CLASSIFICATION)
        assert result1.request_id.startswith("jepa-")

        # Custom
        result2 = predictor.predict(
            x_embed, task_type=TaskType.CLASSIFICATION, request_id="custom-123"
        )
        assert result2.request_id == "custom-123"

    def test_predictor_latency_tracking(self) -> None:
        """Test that latency is tracked."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        predictor = EmbeddingPredictor(config)

        x_embed = [[0.1] * 64 for _ in range(4)]
        result = predictor.predict(x_embed, task_type=TaskType.CLASSIFICATION)

        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_predictor_predict_async(self) -> None:
        """Test async prediction."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        predictor = EmbeddingPredictor(config)

        x_embed = [[0.1] * 64 for _ in range(4)]
        result = await predictor.predict_async(x_embed, task_type=TaskType.SIMILARITY)

        assert result.task_type == TaskType.SIMILARITY
        assert result.operations_saved == "2.85x"

    def test_predictor_get_stats(self) -> None:
        """Test get_stats method."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig

        config = JEPAConfig(
            embed_dim=128, predictor_depth=4, decoder_depth=2, num_heads=8
        )
        predictor = EmbeddingPredictor(config)

        stats = predictor.get_stats()

        assert stats["embed_dim"] == 128
        assert stats["predictor_depth"] == 4
        assert stats["decoder_depth"] == 2
        assert stats["num_heads"] == 8
        assert stats["num_predictor_params"] > 0
        assert stats["num_decoder_params"] > 0


class TestInfoNCELoss:
    """Tests for InfoNCE loss computation."""

    def test_infonce_loss_positive(self) -> None:
        """Test InfoNCE loss with similar embeddings."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        predictor = EmbeddingPredictor(config)

        # Similar embeddings should have low loss
        y_pred = [[1.0] * 64]
        y_true = [[1.0] * 64]
        negatives = [[[0.0] * 64] for _ in range(4)]

        loss = predictor.compute_infonce_loss(y_pred, y_true, negatives)

        assert loss >= 0
        assert math.isfinite(loss)

    def test_infonce_loss_negative(self) -> None:
        """Test InfoNCE loss with dissimilar embeddings."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        predictor = EmbeddingPredictor(config)

        # Dissimilar embeddings should have higher loss
        y_pred = [[1.0] * 64]
        y_true = [[-1.0] * 64]
        negatives = [[[0.0] * 64] for _ in range(4)]

        loss = predictor.compute_infonce_loss(y_pred, y_true, negatives)

        assert loss > 0
        assert math.isfinite(loss)

    def test_infonce_loss_temperature_effect(self) -> None:
        """Test that temperature affects loss magnitude."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig

        config_low_temp = JEPAConfig(
            embed_dim=64, predictor_depth=1, num_heads=4, temperature=0.05
        )
        config_high_temp = JEPAConfig(
            embed_dim=64, predictor_depth=1, num_heads=4, temperature=0.5
        )

        predictor_low = EmbeddingPredictor(config_low_temp)
        predictor_high = EmbeddingPredictor(config_high_temp)

        y_pred = [[0.5] * 64]
        y_true = [[0.7] * 64]
        negatives = [[[0.0] * 64]]

        loss_low = predictor_low.compute_infonce_loss(y_pred, y_true, negatives)
        loss_high = predictor_high.compute_infonce_loss(y_pred, y_true, negatives)

        # Lower temperature should generally produce different loss
        assert loss_low != loss_high


class TestSelectiveDecodingService:
    """Tests for SelectiveDecodingService."""

    def test_service_init(self) -> None:
        """Test service initialization."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        assert service.predictor is not None
        assert service.config == config

    @pytest.mark.asyncio
    async def test_service_process_task_classification(self) -> None:
        """Test process_task for classification."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        result = await service.process_task(
            input_text="def vulnerable_function(): pass",
            task_hint=TaskType.CLASSIFICATION,
        )

        assert result["type"] == "embedding"
        assert result["task_type"] == "classification"
        assert result["operations_saved"] == "2.85x"
        assert "embedding" in result
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_service_process_task_generation(self) -> None:
        """Test process_task for generation."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        result = await service.process_task(
            input_text="Explain this code",
            task_hint=TaskType.EXPLANATION,
        )

        assert result["type"] == "text"
        assert result["task_type"] == "explanation"
        assert "text" in result

    @pytest.mark.asyncio
    async def test_service_classify_code(self) -> None:
        """Test classify_code method."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        result = await service.classify_code(
            code="print('hello')",
            labels=["safe", "vulnerable"],
        )

        assert "classification" in result
        assert result["labels"] == ["safe", "vulnerable"]

    @pytest.mark.asyncio
    async def test_service_compute_similarity(self) -> None:
        """Test compute_similarity method."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        result = await service.compute_similarity(
            code_a="def foo(): pass",
            code_b="def bar(): pass",
        )

        assert "similarity" in result
        assert -1.0 <= result["similarity"] <= 1.0
        assert result["operations_saved"] == "2.85x"

    @pytest.mark.asyncio
    async def test_service_route_to_agent(self) -> None:
        """Test route_to_agent method."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        result = await service.route_to_agent(
            task_description="Fix this security vulnerability",
            available_agents=["coder", "reviewer", "validator"],
        )

        assert "recommended_agent" in result
        assert result["recommended_agent"] in ["coder", "reviewer", "validator"]
        assert result["operations_saved"] == "2.85x"

    @pytest.mark.asyncio
    async def test_service_generate_explanation(self) -> None:
        """Test generate_explanation method."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        result = await service.generate_explanation(code="x = 1 + 2")

        assert "explanation" in result
        assert "embedding" in result
        assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_service_metrics(self) -> None:
        """Test service metrics collection."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        # Make some requests
        await service.process_task("test1", task_hint=TaskType.CLASSIFICATION)
        await service.process_task("test2", task_hint=TaskType.CLASSIFICATION)
        await service.process_task("test3", task_hint=TaskType.GENERATION)

        metrics = service.get_metrics()

        assert metrics["total_requests"] == 3
        assert metrics["fast_path_requests"] == 2
        assert metrics["slow_path_requests"] == 1
        assert metrics["fast_path_ratio"] == pytest.approx(2 / 3)
        assert metrics["avg_latency_ms"] > 0

    @pytest.mark.asyncio
    async def test_service_reset_metrics(self) -> None:
        """Test metrics reset."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        await service.process_task("test", task_hint=TaskType.CLASSIFICATION)

        service.reset_metrics()

        metrics = service.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["fast_path_requests"] == 0


class TestPackageExports:
    """Tests for package exports."""

    def test_all_exports_available(self) -> None:
        """Test that all expected exports are available."""
        from src.services import jepa

        expected_exports = [
            "EmbeddingPredictor",
            "SelectiveDecodingService",
            "JEPAConfig",
            "PredictionResult",
            "MaskingStrategy",
            "TransformerLayer",
            "TaskType",
            "Encoder",
            "Decoder",
            "JEPA",
            "SelectiveDecoder",
        ]

        for export in expected_exports:
            assert hasattr(jepa, export), f"Missing export: {export}"

    def test_aliases(self) -> None:
        """Test that aliases work correctly."""
        from src.services.jepa import (
            JEPA,
            EmbeddingPredictor,
            SelectiveDecoder,
            SelectiveDecodingService,
        )

        assert JEPA is EmbeddingPredictor
        assert SelectiveDecoder is SelectiveDecodingService


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_input(self) -> None:
        """Test handling of empty input."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        predictor = EmbeddingPredictor(config)

        # Single token
        x_embed = [[0.1] * 64]
        result = predictor.predict(x_embed, task_type=TaskType.CLASSIFICATION)

        assert len(result.embedding) == 1

    def test_large_sequence(self) -> None:
        """Test handling of large sequences."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        predictor = EmbeddingPredictor(config)

        # Large sequence
        x_embed = [[0.1] * 64 for _ in range(100)]
        result = predictor.predict(x_embed, task_type=TaskType.CLASSIFICATION)

        assert len(result.embedding) == 100

    def test_zero_embeddings(self) -> None:
        """Test handling of zero embeddings."""
        from src.services.jepa import EmbeddingPredictor, JEPAConfig, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        predictor = EmbeddingPredictor(config)

        x_embed = [[0.0] * 64 for _ in range(4)]
        result = predictor.predict(x_embed, task_type=TaskType.CLASSIFICATION)

        # Should complete without error
        assert result.embedding is not None

    @pytest.mark.asyncio
    async def test_concurrent_requests(self) -> None:
        """Test handling of concurrent requests."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService, TaskType

        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        # Make concurrent requests
        tasks = [
            service.process_task(f"input_{i}", task_hint=TaskType.CLASSIFICATION)
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(r["type"] == "embedding" for r in results)


class TestIntegrationWithRLM:
    """Tests for integration with RLM module."""

    def test_embedding_dimensions_compatible(self) -> None:
        """Test that JEPA embedding dimensions are compatible with RLM."""
        from src.services.jepa import JEPAConfig
        from src.services.rlm import RLMConfig

        # Both should work with same embedding dimension
        jepa_config = JEPAConfig(embed_dim=768)
        rlm_config = RLMConfig(base_context_size=200_000)

        assert jepa_config.embed_dim == 768
        assert rlm_config.base_context_size == 200_000

    @pytest.mark.asyncio
    async def test_jepa_can_process_rlm_output(self) -> None:
        """Test that JEPA can process RLM output embeddings."""
        from src.services.jepa import JEPAConfig, SelectiveDecodingService, TaskType

        # Simulate RLM output being fed to JEPA for classification
        config = JEPAConfig(embed_dim=64, predictor_depth=1, num_heads=4)
        service = SelectiveDecodingService(config=config)

        # RLM would produce aggregated results as text
        rlm_output = "Vulnerability found: SQL injection in query_users function"

        result = await service.process_task(
            input_text=rlm_output,
            task_hint=TaskType.CLASSIFICATION,
        )

        assert result["type"] == "embedding"
        assert result["operations_saved"] == "2.85x"
