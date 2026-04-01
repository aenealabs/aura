"""Tests for TitanMemoryService."""

import os
import tempfile

import pytest

torch = pytest.importorskip("torch", reason="PyTorch required for neural memory tests")

from src.services import (
    MemoryMetrics,
    RetrievalResult,
    TitanMemoryService,
    TitanMemoryServiceConfig,
    create_titan_memory_service,
)
from src.services.models import AttentionalBias, MIRASConfig, RetentionGate


class TestTitanMemoryServiceConfig:
    """Tests for TitanMemoryServiceConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TitanMemoryServiceConfig()
        assert config.memory_dim == 512
        assert config.memory_depth == 3
        assert config.hidden_multiplier == 4
        assert config.persistent_memory_size == 64
        assert config.miras_preset == "enterprise_standard"
        assert config.enable_ttt is True
        assert config.memorization_threshold == 0.7

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TitanMemoryServiceConfig(
            memory_dim=256,
            memory_depth=2,
            miras_preset="development",
            enable_ttt=False,
            memorization_threshold=0.5,
        )
        assert config.memory_dim == 256
        assert config.memory_depth == 2
        assert config.miras_preset == "development"
        assert config.enable_ttt is False
        assert config.memorization_threshold == 0.5


class TestTitanMemoryService:
    """Tests for TitanMemoryService."""

    @pytest.fixture
    def service(self):
        """Create a TitanMemoryService for testing."""
        config = TitanMemoryServiceConfig(
            memory_dim=128,
            memory_depth=2,
            persistent_memory_size=16,
            enable_metrics=True,
        )
        service = TitanMemoryService(config)
        service.initialize()
        yield service
        service.shutdown()

    @pytest.fixture
    def service_no_ttt(self):
        """Create a TitanMemoryService without TTT."""
        config = TitanMemoryServiceConfig(
            memory_dim=128,
            memory_depth=2,
            enable_ttt=False,
        )
        service = TitanMemoryService(config)
        service.initialize()
        yield service
        service.shutdown()

    def test_initialization(self, service):
        """Test service initialization."""
        assert service._is_initialized is True
        assert service.model is not None
        assert service.backend is not None
        assert service.optimizer is not None

    def test_initialization_no_ttt(self, service_no_ttt):
        """Test service initialization without TTT."""
        assert service_no_ttt._is_initialized is True
        assert service_no_ttt.optimizer is None

    def test_double_initialization_warns(self, service, caplog):
        """Test that double initialization logs warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            service.initialize()
        assert "already initialized" in caplog.text.lower()

    def test_shutdown(self):
        """Test service shutdown."""
        config = TitanMemoryServiceConfig(memory_dim=128, memory_depth=2)
        service = TitanMemoryService(config)
        service.initialize()
        service.shutdown()

        assert service._is_initialized is False
        assert service.model is None
        assert service.backend is None

    def test_retrieve_basic(self, service):
        """Test basic retrieval."""
        query = torch.randn(1, 128)
        result = service.retrieve(query)

        assert isinstance(result, RetrievalResult)
        assert result.content.shape == (1, 128)
        assert 0 <= result.confidence <= 1
        assert result.surprise >= 0
        assert result.latency_ms > 0

    def test_retrieve_batch(self, service):
        """Test batch retrieval."""
        query = torch.randn(4, 128)
        result = service.retrieve(query)

        assert result.content.shape == (4, 128)

    def test_retrieve_without_persistent(self, service):
        """Test retrieval without persistent memory."""
        query = torch.randn(1, 128)
        result = service.retrieve(query, use_persistent=False)

        assert result.source == "neural"

    def test_retrieve_with_persistent(self, service):
        """Test retrieval with persistent memory."""
        query = torch.randn(1, 128)
        result = service.retrieve(query, use_persistent=True)

        assert result.source == "hybrid"

    def test_update_basic(self, service):
        """Test basic update."""
        key = torch.randn(1, 128)
        value = torch.randn(1, 128)

        was_memorized, surprise = service.update(key, value)

        assert isinstance(was_memorized, bool)
        assert isinstance(surprise, float)
        assert surprise >= 0

    def test_update_force_memorize(self, service):
        """Test forced memorization."""
        key = torch.randn(1, 128)
        value = torch.randn(1, 128)

        was_memorized, surprise = service.update(key, value, force_memorize=True)

        assert was_memorized is True

    def test_update_no_ttt(self, service_no_ttt):
        """Test update with TTT disabled."""
        key = torch.randn(1, 128)
        value = torch.randn(1, 128)

        was_memorized, surprise = service_no_ttt.update(key, value)

        assert was_memorized is False
        assert surprise == 0.0

    def test_compute_surprise(self, service):
        """Test explicit surprise computation."""
        input_tensor = torch.randn(1, 128)
        target_tensor = torch.randn(1, 128)

        surprise = service.compute_surprise(input_tensor, target_tensor)

        assert isinstance(surprise, float)
        assert surprise >= 0

    def test_compute_surprise_self(self, service):
        """Test surprise computation with self as target."""
        input_tensor = torch.randn(1, 128)

        surprise = service.compute_surprise(input_tensor)

        assert isinstance(surprise, float)

    def test_get_stats(self, service):
        """Test getting service statistics."""
        # Perform some operations
        query = torch.randn(1, 128)
        service.retrieve(query)

        key = torch.randn(1, 128)
        value = torch.randn(1, 128)
        service.update(key, value, force_memorize=True)

        stats = service.get_stats()

        assert stats["is_initialized"] is True
        assert stats["retrieval_count"] == 1
        assert stats["update_count"] == 1
        assert "model_parameters" in stats
        assert "memory_size_mb" in stats

    def test_get_metrics(self, service):
        """Test getting collected metrics."""
        # Perform some operations
        query = torch.randn(1, 128)
        service.retrieve(query)

        metrics = service.get_metrics()

        assert len(metrics) > 0
        assert isinstance(metrics[0], MemoryMetrics)
        assert metrics[0].operation == "retrieve"

    def test_freeze_persistent_memory(self, service):
        """Test freezing persistent memory."""
        service.freeze_persistent_memory()

        for param in service.model.persistent_memory.parameters():
            assert param.requires_grad is False

    def test_unfreeze_persistent_memory(self, service):
        """Test unfreezing persistent memory."""
        service.freeze_persistent_memory()
        service.unfreeze_persistent_memory()

        for param in service.model.persistent_memory.parameters():
            assert param.requires_grad is True

    def test_reset_surprise_momentum(self, service):
        """Test resetting surprise momentum."""
        # Perform updates to build momentum
        key = torch.randn(1, 128)
        value = torch.randn(1, 128) * 10  # Large difference
        service.update(key, value, force_memorize=True)

        assert service._past_surprise != 0.0

        service.reset_surprise_momentum()

        assert service._past_surprise == 0.0

    def test_save_load_checkpoint(self, service):
        """Test saving and loading checkpoints."""
        # Perform some operations to change state
        key = torch.randn(1, 128)
        value = torch.randn(1, 128)
        service.update(key, value, force_memorize=True)

        original_stats = service.get_stats()

        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            checkpoint_path = f.name

        try:
            # Save checkpoint
            service.save_checkpoint(checkpoint_path)

            # Create new service and load
            config = TitanMemoryServiceConfig(
                memory_dim=128,
                memory_depth=2,
                persistent_memory_size=16,
            )
            new_service = TitanMemoryService(config)
            new_service.initialize()

            new_service.load_checkpoint(checkpoint_path)

            loaded_stats = new_service.get_stats()

            assert loaded_stats["update_count"] == original_stats["update_count"]

            new_service.shutdown()
        finally:
            os.unlink(checkpoint_path)

    def test_context_manager(self):
        """Test service as context manager."""
        config = TitanMemoryServiceConfig(memory_dim=128, memory_depth=2)

        with TitanMemoryService(config) as service:
            assert service._is_initialized is True
            query = torch.randn(1, 128)
            result = service.retrieve(query)
            assert result.content.shape == (1, 128)

        assert service._is_initialized is False

    def test_uninitialized_raises_error(self):
        """Test that operations on uninitialized service raise error."""
        config = TitanMemoryServiceConfig(memory_dim=128, memory_depth=2)
        service = TitanMemoryService(config)

        with pytest.raises(RuntimeError, match="not initialized"):
            service.retrieve(torch.randn(1, 128))

    def test_custom_miras_config(self):
        """Test service with custom MIRAS config."""
        miras_config = MIRASConfig(
            attentional_bias=AttentionalBias.L2,
            retention_gate=RetentionGate.WEIGHT_DECAY,
        )
        config = TitanMemoryServiceConfig(
            memory_dim=128,
            memory_depth=2,
            miras_preset=None,
            miras_config=miras_config,
        )

        with TitanMemoryService(config) as service:
            assert service.miras_config.attentional_bias == AttentionalBias.L2
            assert service.miras_config.retention_gate == RetentionGate.WEIGHT_DECAY

    @pytest.mark.slow
    def test_metrics_limit(self, service):
        """Test that metrics collection is limited."""
        # Generate many operations
        for _ in range(1100):
            query = torch.randn(1, 128)
            service.retrieve(query)

        metrics = service.get_metrics()
        assert len(metrics) <= 1000  # Should be capped


class TestCreateTitanMemoryService:
    """Tests for create_titan_memory_service factory function."""

    def test_default_creation(self):
        """Test creating service with defaults."""
        service = create_titan_memory_service()

        assert service.config.memory_dim == 512
        assert service.config.memory_depth == 3
        assert service.config.miras_preset == "enterprise_standard"
        assert service.config.enable_ttt is True

    def test_custom_creation(self):
        """Test creating service with custom parameters."""
        service = create_titan_memory_service(
            preset="development",
            enable_ttt=False,
            memory_dim=256,
            memory_depth=2,
        )

        assert service.config.memory_dim == 256
        assert service.config.memory_depth == 2
        assert service.config.miras_preset == "development"
        assert service.config.enable_ttt is False


class TestMemoryMetrics:
    """Tests for MemoryMetrics dataclass."""

    def test_creation(self):
        """Test creating metrics."""
        metrics = MemoryMetrics(
            operation="retrieve",
            latency_ms=5.0,
            surprise_score=0.5,
        )

        assert metrics.operation == "retrieve"
        assert metrics.latency_ms == 5.0
        assert metrics.surprise_score == 0.5
        assert metrics.was_memorized is False
        assert metrics.timestamp > 0


class TestRetrievalResult:
    """Tests for RetrievalResult dataclass."""

    def test_creation(self):
        """Test creating retrieval result."""
        content = torch.randn(1, 128)
        result = RetrievalResult(
            content=content,
            confidence=0.85,
            surprise=0.15,
            latency_ms=3.0,
            source="hybrid",
        )

        assert result.content.shape == (1, 128)
        assert result.confidence == 0.85
        assert result.surprise == 0.15
        assert result.latency_ms == 3.0
        assert result.source == "hybrid"
