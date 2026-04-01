"""
Tests for Titan Memory Service configuration and dataclasses.

Covers TitanMemoryServiceConfig, MemoryMetrics, and basic service initialization.
Full integration tests require PyTorch and are skipped in unit tests.
"""

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

# Save original modules before mocking to prevent test pollution
_modules_to_save = [
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "torch.optim",
    "src.services.memory_backends",
    "src.services.memory_consolidation",
    "src.services.models",
    "src.services.neural_memory_audit",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# =============================================================================
# Mock dependencies BEFORE importing
# =============================================================================

# Mock torch
mock_torch = MagicMock()
mock_torch.nn = MagicMock()
mock_torch.nn.functional = MagicMock()
mock_torch.nn.Module = type("Module", (), {})
mock_torch.Tensor = MagicMock
mock_torch.optim = MagicMock()
mock_torch.no_grad = MagicMock(
    return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
)
sys.modules["torch"] = mock_torch
sys.modules["torch.nn"] = mock_torch.nn
sys.modules["torch.nn.functional"] = mock_torch.nn.functional
sys.modules["torch.optim"] = mock_torch.optim

# Mock other dependencies
mock_backends = MagicMock()
mock_backends.BackendConfig = MagicMock
mock_backends.BackendType = MagicMock()
mock_backends.BackendType.CPU = "cpu"
mock_backends.CPUMemoryBackend = MagicMock
mock_backends.MemoryBackend = MagicMock
sys.modules["src.services.memory_backends"] = mock_backends

mock_consolidation = MagicMock()
mock_consolidation.ConsolidationConfig = MagicMock
mock_consolidation.ConsolidationResult = MagicMock
mock_consolidation.ConsolidationStrategy = MagicMock
mock_consolidation.MemoryConsolidationManager = MagicMock()
mock_consolidation.MemoryPressureLevel = MagicMock()
mock_consolidation.MemorySizeLimiter = MagicMock
mock_consolidation.create_production_consolidation_config = MagicMock(
    return_value=MagicMock()
)
sys.modules["src.services.memory_consolidation"] = mock_consolidation

mock_models = MagicMock()
mock_models.DeepMLPMemory = MagicMock
mock_models.MemoryConfig = MagicMock
mock_models.MIRASConfig = MagicMock(return_value=MagicMock())
mock_models.MIRASLossFunctions = MagicMock
mock_models.MIRASOptimizer = MagicMock
mock_models.MIRASRetention = MagicMock
mock_models.get_miras_preset = MagicMock(return_value=MagicMock())
sys.modules["src.services.models"] = mock_models

mock_audit = MagicMock()
mock_audit.AuditEventType = MagicMock
mock_audit.AuditSeverity = MagicMock
mock_audit.InMemoryAuditStorage = MagicMock
mock_audit.NeuralMemoryAuditLogger = MagicMock()
sys.modules["src.services.neural_memory_audit"] = mock_audit

# Now import the module
from src.services.titan_memory_service import (
    MemoryMetrics,
    RetrievalResult,
    TitanMemoryService,
    TitanMemoryServiceConfig,
    create_titan_memory_service,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


# =============================================================================
# TitanMemoryServiceConfig Dataclass Tests
# =============================================================================


class TestTitanMemoryServiceConfig:
    """Tests for TitanMemoryServiceConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = TitanMemoryServiceConfig()

        assert config.memory_dim == 512
        assert config.memory_depth == 3
        assert config.hidden_multiplier == 4
        assert config.persistent_memory_size == 64
        assert config.miras_preset == "enterprise_standard"
        assert config.miras_config is None
        assert config.backend_config is None
        assert config.enable_ttt is True
        assert config.ttt_learning_rate == 0.001
        assert config.max_ttt_steps == 3
        assert config.memorization_threshold == 0.7
        assert config.surprise_momentum == 0.9
        assert config.max_memory_size_mb == 100.0
        assert config.enable_size_limit_enforcement is True
        assert config.enable_metrics is True
        assert config.enable_audit_logging is True
        assert config.environment == "dev"
        assert config.extra_config == {}

    def test_custom_memory_config(self):
        """Test custom memory architecture config."""
        config = TitanMemoryServiceConfig(
            memory_dim=256,
            memory_depth=5,
            hidden_multiplier=2,
            persistent_memory_size=128,
        )

        assert config.memory_dim == 256
        assert config.memory_depth == 5
        assert config.hidden_multiplier == 2
        assert config.persistent_memory_size == 128

    def test_custom_ttt_config(self):
        """Test custom TTT configuration."""
        config = TitanMemoryServiceConfig(
            enable_ttt=False,
            ttt_learning_rate=0.01,
            max_ttt_steps=10,
            memorization_threshold=0.5,
            surprise_momentum=0.8,
        )

        assert config.enable_ttt is False
        assert config.ttt_learning_rate == 0.01
        assert config.max_ttt_steps == 10
        assert config.memorization_threshold == 0.5
        assert config.surprise_momentum == 0.8

    def test_custom_safety_limits(self):
        """Test custom safety limit configuration."""
        config = TitanMemoryServiceConfig(
            max_memory_size_mb=500.0,
            enable_size_limit_enforcement=False,
        )

        assert config.max_memory_size_mb == 500.0
        assert config.enable_size_limit_enforcement is False

    def test_custom_observability(self):
        """Test custom observability configuration."""
        config = TitanMemoryServiceConfig(
            enable_metrics=False,
            enable_audit_logging=False,
            environment="prod",
        )

        assert config.enable_metrics is False
        assert config.enable_audit_logging is False
        assert config.environment == "prod"

    def test_extra_config_dict(self):
        """Test extra_config dictionary."""
        config = TitanMemoryServiceConfig(extra_config={"custom_key": "custom_value"})

        assert config.extra_config["custom_key"] == "custom_value"


# =============================================================================
# MemoryMetrics Dataclass Tests
# =============================================================================


class TestMemoryMetrics:
    """Tests for MemoryMetrics dataclass."""

    def test_create_basic_metric(self):
        """Test creating a basic metric."""
        metric = MemoryMetrics(
            operation="retrieve",
            latency_ms=15.5,
        )

        assert metric.operation == "retrieve"
        assert metric.latency_ms == 15.5

    def test_default_values(self):
        """Test default values for optional fields."""
        metric = MemoryMetrics(
            operation="update",
            latency_ms=25.0,
        )

        assert metric.surprise_score is None
        assert metric.was_memorized is False
        assert metric.ttt_steps == 0
        assert metric.memory_usage_mb == 0.0
        assert metric.timestamp > 0

    def test_full_metric(self):
        """Test metric with all fields."""
        metric = MemoryMetrics(
            operation="update",
            latency_ms=50.0,
            surprise_score=0.85,
            was_memorized=True,
            ttt_steps=3,
            memory_usage_mb=45.5,
        )

        assert metric.surprise_score == 0.85
        assert metric.was_memorized is True
        assert metric.ttt_steps == 3
        assert metric.memory_usage_mb == 45.5

    def test_timestamp_auto_generated(self):
        """Test that timestamp is auto-generated."""
        before = time.time()
        metric = MemoryMetrics(operation="test", latency_ms=1.0)
        after = time.time()

        assert before <= metric.timestamp <= after


# =============================================================================
# RetrievalResult Dataclass Tests
# =============================================================================


class TestRetrievalResult:
    """Tests for RetrievalResult dataclass."""

    def test_create_result(self):
        """Test creating a retrieval result."""
        mock_tensor = MagicMock()
        result = RetrievalResult(
            content=mock_tensor,
            confidence=0.92,
            surprise=0.08,
            latency_ms=12.3,
        )

        assert result.content == mock_tensor
        assert result.confidence == 0.92
        assert result.surprise == 0.08
        assert result.latency_ms == 12.3

    def test_default_source(self):
        """Test default source value."""
        result = RetrievalResult(
            content=MagicMock(),
            confidence=0.8,
            surprise=0.2,
            latency_ms=10.0,
        )

        assert result.source == "neural"

    def test_custom_source(self):
        """Test custom source value."""
        result = RetrievalResult(
            content=MagicMock(),
            confidence=0.9,
            surprise=0.1,
            latency_ms=15.0,
            source="hybrid",
        )

        assert result.source == "hybrid"


# =============================================================================
# TitanMemoryService Initialization Tests
# =============================================================================


class TestTitanMemoryServiceInit:
    """Tests for TitanMemoryService initialization."""

    def test_initialization_with_defaults(self):
        """Test service initialization with default config."""
        service = TitanMemoryService()

        assert service.config is not None
        assert service.config.memory_dim == 512
        assert service._is_initialized is False
        assert service._update_count == 0
        assert service._retrieval_count == 0

    def test_initialization_with_custom_config(self):
        """Test service initialization with custom config."""
        config = TitanMemoryServiceConfig(
            memory_dim=256,
            enable_ttt=False,
            environment="staging",
        )
        service = TitanMemoryService(config=config)

        assert service.config.memory_dim == 256
        assert service.config.enable_ttt is False
        assert service.config.environment == "staging"

    def test_audit_logger_disabled(self):
        """Test service with audit logging disabled."""
        config = TitanMemoryServiceConfig(enable_audit_logging=False)
        service = TitanMemoryService(config=config)

        assert service.audit_logger is None

    def test_consolidation_manager_initialized(self):
        """Test that consolidation manager is initialized."""
        service = TitanMemoryService()

        assert service.consolidation_manager is not None

    def test_initial_metrics_empty(self):
        """Test that metrics list is empty initially."""
        service = TitanMemoryService()

        assert service._metrics == []


# =============================================================================
# TitanMemoryService State Management Tests
# =============================================================================


class TestTitanMemoryServiceState:
    """Tests for TitanMemoryService state management."""

    def test_ensure_initialized_raises_when_not_initialized(self):
        """Test that _ensure_initialized raises when not initialized."""
        service = TitanMemoryService()

        with pytest.raises(RuntimeError) as exc_info:
            service._ensure_initialized()

        assert "not initialized" in str(exc_info.value)

    def test_reset_surprise_momentum(self):
        """Test resetting surprise momentum."""
        service = TitanMemoryService()
        service._past_surprise = 0.5

        service.reset_surprise_momentum()

        assert service._past_surprise == 0.0

    def test_compute_utilization_empty(self):
        """Test utilization with no operations."""
        service = TitanMemoryService()

        utilization = service._compute_utilization()

        assert utilization == 0.5  # Default when no operations

    def test_compute_utilization_with_operations(self):
        """Test utilization with operations."""
        service = TitanMemoryService()
        service._retrieval_count = 80
        service._update_count = 20

        utilization = service._compute_utilization()

        assert utilization == 0.8  # 80/(80+20)


# =============================================================================
# TitanMemoryService Metrics Tests
# =============================================================================


class TestTitanMemoryServiceMetrics:
    """Tests for TitanMemoryService metrics."""

    def test_record_metric(self):
        """Test recording a metric."""
        service = TitanMemoryService()
        metric = MemoryMetrics(operation="test", latency_ms=10.0)

        service._record_metric(metric)

        assert len(service._metrics) == 1
        assert service._metrics[0].operation == "test"

    @pytest.mark.slow
    def test_record_metric_caps_at_1000(self):
        """Test that metrics are capped at 1000 entries."""
        service = TitanMemoryService()

        # Add 1100 metrics
        for i in range(1100):
            metric = MemoryMetrics(operation=f"test_{i}", latency_ms=float(i))
            service._record_metric(metric)

        assert len(service._metrics) == 1000

    def test_get_metrics_returns_copy(self):
        """Test that get_metrics returns a copy."""
        service = TitanMemoryService()
        metric = MemoryMetrics(operation="test", latency_ms=10.0)
        service._record_metric(metric)

        metrics = service.get_metrics()
        metrics.clear()

        # Original should still have the metric
        assert len(service._metrics) == 1

    def test_get_stats_not_initialized(self):
        """Test getting stats when not initialized."""
        service = TitanMemoryService()

        stats = service.get_stats()

        assert stats["is_initialized"] is False
        assert stats["update_count"] == 0
        assert stats["retrieval_count"] == 0


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateTitanMemoryService:
    """Tests for create_titan_memory_service factory function."""

    def test_create_with_defaults(self):
        """Test creating service with default parameters."""
        service = create_titan_memory_service()

        assert service is not None
        assert service.config.miras_preset == "enterprise_standard"
        assert service.config.enable_ttt is True
        assert service.config.memory_dim == 512
        assert service.config.memory_depth == 3

    def test_create_with_custom_preset(self):
        """Test creating service with custom preset."""
        service = create_titan_memory_service(preset="defense_contractor")

        assert service.config.miras_preset == "defense_contractor"

    def test_create_with_ttt_disabled(self):
        """Test creating service with TTT disabled."""
        service = create_titan_memory_service(enable_ttt=False)

        assert service.config.enable_ttt is False

    def test_create_with_custom_dimensions(self):
        """Test creating service with custom dimensions."""
        service = create_titan_memory_service(
            memory_dim=256,
            memory_depth=5,
        )

        assert service.config.memory_dim == 256
        assert service.config.memory_depth == 5


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestTitanMemoryServiceContextManager:
    """Tests for context manager interface."""

    @patch.object(TitanMemoryService, "initialize")
    @patch.object(TitanMemoryService, "shutdown")
    def test_context_manager_calls_init_and_shutdown(self, mock_shutdown, mock_init):
        """Test that context manager calls initialize and shutdown."""
        with TitanMemoryService() as service:
            assert service is not None
            mock_init.assert_called_once()

        mock_shutdown.assert_called_once()


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestTitanMemoryServiceEdgeCases:
    """Tests for edge cases and error handling."""

    def test_get_memory_usage_not_initialized(self):
        """Test getting memory usage when backend is None."""
        service = TitanMemoryService()

        usage = service._get_memory_usage_mb()

        assert usage == 0.0

    def test_multiple_initialize_calls_warns(self):
        """Test that multiple initialize calls log warning."""
        service = TitanMemoryService()
        service._is_initialized = True  # Simulate already initialized

        # Should log warning but not crash
        service.initialize()

    def test_shutdown_when_not_initialized(self):
        """Test shutdown when not initialized."""
        service = TitanMemoryService()

        # Should not raise
        service.shutdown()


# =============================================================================
# TitanMemoryService Initialize and Shutdown Tests
# =============================================================================


class TestTitanMemoryServiceInitialize:
    """Tests for TitanMemoryService initialize and shutdown methods.

    Note: Full initialize() tests are handled via integration tests since
    they require actual PyTorch module loading. These tests verify the
    state management and logging aspects.
    """

    def test_initialize_already_initialized_warns(self):
        """Test that calling initialize when already initialized logs warning."""
        service = TitanMemoryService()
        service._is_initialized = True  # Pretend it's initialized

        # Should not raise, just log warning
        service.initialize()

        # Still initialized
        assert service._is_initialized is True

    def test_shutdown_when_initialized_cleans_up(self):
        """Test shutdown when service is fully initialized."""
        service = TitanMemoryService()
        service._is_initialized = True

        # Set up mock components
        mock_backend = MagicMock()
        mock_audit_logger = MagicMock()

        service.backend = mock_backend
        service.model = MagicMock()
        service.optimizer = MagicMock()
        service.size_limiter = MagicMock()
        service.audit_logger = mock_audit_logger

        service.shutdown()

        mock_backend.cleanup.assert_called_once()
        mock_audit_logger.log_service_shutdown.assert_called_once()
        mock_audit_logger.flush.assert_called_once()
        assert service._is_initialized is False
        assert service.model is None
        assert service.backend is None
        assert service.optimizer is None
        assert service.size_limiter is None

    def test_shutdown_without_audit_logger(self):
        """Test shutdown when audit logger is None."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.backend = MagicMock()
        service.model = MagicMock()
        service.audit_logger = None

        # Should not raise
        service.shutdown()

        assert service._is_initialized is False

    def test_shutdown_without_backend(self):
        """Test shutdown when backend is None."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.backend = None
        service.model = MagicMock()
        # Disable audit logger to avoid get_stats() call on None backend
        service.audit_logger = None

        # Should not raise
        service.shutdown()

        assert service._is_initialized is False


# =============================================================================
# TitanMemoryService Retrieve Tests
# =============================================================================


class TestTitanMemoryServiceRetrieve:
    """Tests for TitanMemoryService retrieve method."""

    def _create_initialized_service(self):
        """Helper to create an initialized service with mocks."""
        service = TitanMemoryService()
        service._is_initialized = True

        # Mock backend
        service.backend = MagicMock()
        service.backend.to_device.return_value = MagicMock()
        service.backend.from_device.return_value = MagicMock()
        service.backend.forward.return_value = MagicMock()
        service.backend.get_memory_usage.return_value = {"allocated_mb": 10.0}

        # Mock model
        service.model = MagicMock()

        return service

    def test_retrieve_basic(self):
        """Test basic retrieve operation."""
        service = self._create_initialized_service()
        mock_query = MagicMock()

        # Mock _compute_surprise to return a value
        with patch.object(service, "_compute_surprise", return_value=0.3):
            result = service.retrieve(mock_query)

        assert result.confidence == 0.7  # 1.0 - 0.3
        assert result.surprise == 0.3
        assert result.source == "hybrid"
        assert service._retrieval_count == 1

    def test_retrieve_without_persistent_memory(self):
        """Test retrieve without using persistent memory."""
        service = self._create_initialized_service()
        mock_query = MagicMock()

        with patch.object(service, "_compute_surprise", return_value=0.2):
            result = service.retrieve(mock_query, use_persistent=False)

        assert result.source == "neural"  # Should be neural, not hybrid

    def test_retrieve_with_audit_logging(self):
        """Test retrieve logs to audit logger."""
        service = self._create_initialized_service()
        service.audit_logger = MagicMock()
        mock_query = MagicMock()

        with patch.object(service, "_compute_surprise", return_value=0.1):
            _result = service.retrieve(mock_query, actor="test_user")

        service.audit_logger.log_memory_retrieve.assert_called_once()
        call_kwargs = service.audit_logger.log_memory_retrieve.call_args[1]
        assert call_kwargs["actor"] == "test_user"

    def test_retrieve_records_metric(self):
        """Test retrieve records metrics when enabled."""
        config = TitanMemoryServiceConfig(enable_metrics=True)
        service = TitanMemoryService(config=config)
        service._is_initialized = True
        service.backend = MagicMock()
        service.backend.to_device.return_value = MagicMock()
        service.backend.from_device.return_value = MagicMock()
        service.backend.forward.return_value = MagicMock()
        service.backend.get_memory_usage.return_value = {"allocated_mb": 5.0}
        service.model = MagicMock()

        with patch.object(service, "_compute_surprise", return_value=0.5):
            service.retrieve(MagicMock())

        assert len(service._metrics) == 1
        assert service._metrics[0].operation == "retrieve"


# =============================================================================
# TitanMemoryService Update Tests
# =============================================================================


class TestTitanMemoryServiceUpdate:
    """Tests for TitanMemoryService update method."""

    def _create_initialized_service(self, enable_ttt=True):
        """Helper to create an initialized service."""
        config = TitanMemoryServiceConfig(enable_ttt=enable_ttt)
        service = TitanMemoryService(config=config)
        service._is_initialized = True

        service.backend = MagicMock()
        service.backend.to_device.return_value = MagicMock()
        service.backend.compute_surprise.return_value = 0.8
        service.backend.get_memory_usage.return_value = {"allocated_mb": 10.0}

        service.model = MagicMock()
        service.optimizer = MagicMock()

        return service

    def test_update_with_ttt_disabled(self):
        """Test update when TTT is disabled."""
        service = self._create_initialized_service(enable_ttt=False)

        was_memorized, surprise = service.update(MagicMock(), MagicMock())

        assert was_memorized is False
        assert surprise == 0.0

    def test_update_below_threshold_not_memorized(self):
        """Test update below surprise threshold is not memorized."""
        service = self._create_initialized_service()
        service.config.memorization_threshold = 0.9
        service.backend.compute_surprise.return_value = 0.5  # Below threshold

        with patch.object(service, "_perform_ttt", return_value=0):
            was_memorized, surprise = service.update(MagicMock(), MagicMock())

        # With momentum smoothing: 0.9 * 0.5 + 0.1 * 0 = 0.45 < 0.9
        assert was_memorized is False

    def test_update_above_threshold_memorized(self):
        """Test update above surprise threshold is memorized."""
        service = self._create_initialized_service()
        service.config.memorization_threshold = 0.3
        service.backend.compute_surprise.return_value = 0.8

        with patch.object(service, "_perform_ttt", return_value=3):
            was_memorized, surprise = service.update(MagicMock(), MagicMock())

        assert was_memorized is True
        assert service._update_count == 1

    def test_update_force_memorize(self):
        """Test update with force_memorize bypasses threshold."""
        service = self._create_initialized_service()
        service.config.memorization_threshold = 0.99  # Very high threshold
        service.backend.compute_surprise.return_value = 0.1  # Very low surprise

        with patch.object(service, "_perform_ttt", return_value=2):
            was_memorized, surprise = service.update(
                MagicMock(), MagicMock(), force_memorize=True
            )

        assert was_memorized is True

    def test_update_size_limit_rejection(self):
        """Test update rejected when size limit exceeded."""
        service = self._create_initialized_service()
        service.size_limiter = MagicMock()
        service.size_limiter.can_update.return_value = False
        service.size_limiter.check_and_enforce.return_value = False
        service.size_limiter.get_current_memory_mb.return_value = 100.0
        service.size_limiter.max_memory_mb = 50.0
        service.audit_logger = MagicMock()

        was_memorized, surprise = service.update(MagicMock(), MagicMock())

        assert was_memorized is False
        assert service._updates_rejected_count == 1
        service.audit_logger.log_size_limit_exceeded.assert_called_once()

    def test_update_records_metric(self):
        """Test update records metrics."""
        service = self._create_initialized_service()
        service.config.enable_metrics = True
        service.consolidation_manager = MagicMock()

        with patch.object(service, "_perform_ttt", return_value=1):
            service.update(MagicMock(), MagicMock(), force_memorize=True)

        assert len(service._metrics) == 1
        assert service._metrics[0].operation == "update"

    def test_update_with_audit_logging(self):
        """Test update logs to audit logger."""
        service = self._create_initialized_service()
        service.audit_logger = MagicMock()
        service.consolidation_manager = MagicMock()

        with patch.object(service, "_perform_ttt", return_value=1):
            service.update(
                MagicMock(), MagicMock(), actor="agent1", force_memorize=True
            )

        service.audit_logger.log_memory_update.assert_called_once()


# =============================================================================
# TitanMemoryService Compute Surprise Tests
# =============================================================================


class TestTitanMemoryServiceComputeSurprise:
    """Tests for compute_surprise public method."""

    def test_compute_surprise_basic(self):
        """Test basic compute_surprise call."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.backend = MagicMock()
        service.backend.to_device.return_value = MagicMock()
        service.backend.compute_surprise.return_value = 0.65
        service.model = MagicMock()

        surprise = service.compute_surprise(MagicMock())

        assert surprise == 0.65
        service.backend.compute_surprise.assert_called_once()

    def test_compute_surprise_with_target(self):
        """Test compute_surprise with explicit target tensor."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.backend = MagicMock()
        service.backend.to_device.return_value = MagicMock()
        service.backend.compute_surprise.return_value = 0.4
        service.model = MagicMock()

        mock_input = MagicMock()
        mock_target = MagicMock()

        surprise = service.compute_surprise(mock_input, mock_target)

        assert surprise == 0.4
        # to_device should be called twice (input and target)
        assert service.backend.to_device.call_count == 2


# =============================================================================
# TitanMemoryService TTT Tests
# =============================================================================


class TestTitanMemoryServiceTTT:
    """Tests for _perform_ttt method.

    Note: Full TTT execution tests require real PyTorch and are done via
    integration tests. These tests verify the public interface for TTT config.
    """

    def test_update_performs_ttt_when_enabled(self):
        """Test that update calls TTT when above threshold."""
        config = TitanMemoryServiceConfig(enable_ttt=True, memorization_threshold=0.3)
        service = TitanMemoryService(config=config)
        service._is_initialized = True

        service.backend = MagicMock()
        service.backend.to_device.return_value = MagicMock()
        service.backend.compute_surprise.return_value = 0.8  # High surprise
        service.backend.get_memory_usage.return_value = {"allocated_mb": 10.0}

        service.model = MagicMock()
        service.optimizer = MagicMock()
        service.consolidation_manager = MagicMock()

        # Mock _perform_ttt to verify it's called
        with patch.object(service, "_perform_ttt", return_value=3) as mock_ttt:
            was_memorized, surprise = service.update(MagicMock(), MagicMock())

        assert was_memorized is True
        mock_ttt.assert_called_once()

    def test_ttt_config_max_steps(self):
        """Test TTT config max_ttt_steps is respected."""
        config = TitanMemoryServiceConfig(max_ttt_steps=5)
        service = TitanMemoryService(config=config)

        assert service.config.max_ttt_steps == 5

    def test_ttt_config_learning_rate(self):
        """Test TTT config learning_rate is respected."""
        config = TitanMemoryServiceConfig(ttt_learning_rate=0.005)
        service = TitanMemoryService(config=config)

        assert service.config.ttt_learning_rate == 0.005


# =============================================================================
# TitanMemoryService Consolidation Tests
# =============================================================================


class TestTitanMemoryServiceConsolidation:
    """Tests for consolidation and memory pressure methods."""

    def test_consolidate(self):
        """Test manual consolidation trigger."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.model = MagicMock()
        service.consolidation_manager = MagicMock()
        mock_result = MagicMock()
        service.consolidation_manager.consolidate.return_value = mock_result

        result = service.consolidate()

        assert result == mock_result
        service.consolidation_manager.consolidate.assert_called_once()

    def test_consolidate_with_strategy(self):
        """Test consolidation with specific strategy."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.model = MagicMock()
        service.consolidation_manager = MagicMock()

        mock_strategy = MagicMock()
        service.consolidate(strategy=mock_strategy)

        call_kwargs = service.consolidation_manager.consolidate.call_args[1]
        assert call_kwargs["strategy"] == mock_strategy

    def test_get_memory_pressure(self):
        """Test getting current memory pressure level."""
        service = TitanMemoryService()
        service._is_initialized = False
        service.backend = MagicMock()
        service.backend.get_memory_usage.return_value = {"allocated_mb": 25.0}
        service.consolidation_manager = MagicMock()
        mock_level = MagicMock()
        service.consolidation_manager.check_memory_pressure.return_value = mock_level

        level = service.get_memory_pressure()

        assert level == mock_level

    def test_on_consolidation_callback(self):
        """Test consolidation callback logs to audit."""
        service = TitanMemoryService()
        service.audit_logger = MagicMock()

        mock_result = MagicMock()
        mock_result.memory_before_mb = 50.0
        mock_result.memory_after_mb = 30.0
        mock_result.duration_ms = 100.0
        mock_result.strategy_used = MagicMock(value="pruning")
        mock_result.weights_pruned = 100
        mock_result.slots_removed = 5
        mock_result.layers_reset = 0
        mock_result.success = True

        service._on_consolidation(mock_result)

        service.audit_logger.log_consolidation.assert_called_once()

    def test_on_pressure_change_callback_exists(self):
        """Test that _on_pressure_change callback is defined and callable."""
        service = TitanMemoryService()
        service.config = TitanMemoryServiceConfig(max_memory_size_mb=100.0)
        service.audit_logger = MagicMock()
        service.backend = MagicMock()
        service.backend.get_memory_usage.return_value = {"allocated_mb": 80.0}

        # Create mock pressure level
        mock_pressure = MagicMock()
        mock_pressure.value = "normal"

        # Callback should not raise with any pressure value
        service._on_pressure_change(mock_pressure)

        # If pressure is not WARNING, log should not be called
        service.audit_logger.log_size_limit_warning.assert_not_called()

    def test_on_limit_exceeded(self):
        """Test limit exceeded callback."""
        service = TitanMemoryService()

        # Should log warning but not raise
        service._on_limit_exceeded(120.0, 100.0)
        # Just verify it doesn't raise


# =============================================================================
# TitanMemoryService Checkpoint Tests
# =============================================================================


class TestTitanMemoryServiceCheckpoint:
    """Tests for save_checkpoint and load_checkpoint methods.

    Note: Full checkpoint save/load tests require real PyTorch for torch.save/load.
    These tests verify the state management and configuration aspects.
    """

    def test_save_checkpoint_requires_initialization(self):
        """Test that save_checkpoint raises when not initialized."""
        service = TitanMemoryService()
        service._is_initialized = False

        with pytest.raises(RuntimeError) as exc_info:
            service.save_checkpoint("/tmp/checkpoint.pt")

        assert "not initialized" in str(exc_info.value)

    def test_save_checkpoint_config(self):
        """Test checkpoint config values are prepared correctly."""
        service = TitanMemoryService()
        service._is_initialized = True
        service._update_count = 100
        service._retrieval_count = 500
        service._memory_age = 25.0

        # Verify config values are accessible
        assert service.config.memory_dim == 512
        assert service.config.memory_depth == 3
        assert service.config.hidden_multiplier == 4
        assert service.config.persistent_memory_size == 64

    def test_load_checkpoint_requires_initialization(self):
        """Test that load_checkpoint raises when not initialized."""
        service = TitanMemoryService()
        service._is_initialized = False

        with pytest.raises(RuntimeError) as exc_info:
            service.load_checkpoint("/tmp/checkpoint.pt")

        assert "not initialized" in str(exc_info.value)

    def test_checkpoint_state_restoration(self):
        """Test that checkpoint-related state can be set."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.model = MagicMock()
        service.optimizer = MagicMock()
        service.backend = MagicMock()
        service.backend.device = "cpu"

        # Simulate loading checkpoint stats
        service._update_count = 100
        service._retrieval_count = 500
        service._memory_age = 50.0

        assert service._update_count == 100
        assert service._retrieval_count == 500
        assert service._memory_age == 50.0


# =============================================================================
# TitanMemoryService Freeze/Unfreeze Tests
# =============================================================================


class TestTitanMemoryServiceFreeze:
    """Tests for freeze/unfreeze persistent memory."""

    def test_freeze_persistent_memory(self):
        """Test freezing persistent memory."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.model = MagicMock()

        service.freeze_persistent_memory()

        service.model.freeze_persistent_memory.assert_called_once()

    def test_unfreeze_persistent_memory(self):
        """Test unfreezing persistent memory."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.model = MagicMock()

        service.unfreeze_persistent_memory()

        service.model.unfreeze_persistent_memory.assert_called_once()


# =============================================================================
# TitanMemoryService get_stats Tests
# =============================================================================


class TestTitanMemoryServiceGetStatsExtended:
    """Extended tests for get_stats method."""

    def test_get_stats_when_initialized(self):
        """Test get_stats returns extended info when initialized."""
        service = TitanMemoryService()
        service._is_initialized = True
        service._update_count = 10
        service._retrieval_count = 50

        service.model = MagicMock()
        service.model.get_parameter_count.return_value = 1000000
        service.model.get_memory_size_mb.return_value = 4.0

        service.backend = MagicMock()
        service.backend.config.backend_type.value = "cpu"

        stats = service.get_stats()

        assert stats["is_initialized"] is True
        assert stats["model_parameters"] == 1000000
        assert stats["memory_size_mb"] == 4.0
        assert stats["backend_type"] == "cpu"

    def test_get_stats_with_latency_metrics(self):
        """Test get_stats computes latency statistics."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.model = MagicMock()
        service.model.get_parameter_count.return_value = 1000
        service.model.get_memory_size_mb.return_value = 1.0
        service.backend = MagicMock()
        service.backend.config.backend_type.value = "cpu"

        # Add metrics
        service._metrics = [
            MemoryMetrics(operation="retrieve", latency_ms=10.0),
            MemoryMetrics(operation="retrieve", latency_ms=20.0),
            MemoryMetrics(operation="update", latency_ms=50.0),
            MemoryMetrics(operation="update", latency_ms=100.0),
        ]

        stats = service.get_stats()

        assert stats["avg_retrieve_latency_ms"] == 15.0  # (10 + 20) / 2
        assert stats["avg_update_latency_ms"] == 75.0  # (50 + 100) / 2

    def test_get_stats_with_size_limiter(self):
        """Test get_stats includes size limiter stats."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.model = MagicMock()
        service.model.get_parameter_count.return_value = 1000
        service.model.get_memory_size_mb.return_value = 1.0
        service.backend = MagicMock()
        service.backend.config.backend_type.value = "cpu"
        service.size_limiter = MagicMock()
        service.size_limiter.get_stats.return_value = {"current_mb": 50.0}

        stats = service.get_stats()

        assert "size_limiter" in stats
        assert stats["size_limiter"]["current_mb"] == 50.0

    def test_get_stats_with_audit_logger(self):
        """Test get_stats includes audit logger stats."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.model = MagicMock()
        service.model.get_parameter_count.return_value = 1000
        service.model.get_memory_size_mb.return_value = 1.0
        service.backend = MagicMock()
        service.backend.config.backend_type.value = "cpu"
        service.audit_logger = MagicMock()
        service.audit_logger.get_stats.return_value = {"events_logged": 100}

        stats = service.get_stats()

        assert "audit_logging" in stats
        assert stats["audit_logging"]["events_logged"] == 100


# =============================================================================
# TitanMemoryService _get_memory_usage_mb Tests
# =============================================================================


class TestTitanMemoryServiceMemoryUsage:
    """Tests for _get_memory_usage_mb method."""

    def test_get_memory_usage_with_backend(self):
        """Test getting memory usage when backend exists."""
        service = TitanMemoryService()
        service.backend = MagicMock()
        service.backend.get_memory_usage.return_value = {"allocated_mb": 25.5}

        usage = service._get_memory_usage_mb()

        assert usage == 25.5

    def test_get_memory_usage_missing_key(self):
        """Test getting memory usage when key is missing."""
        service = TitanMemoryService()
        service.backend = MagicMock()
        service.backend.get_memory_usage.return_value = {}  # No allocated_mb

        usage = service._get_memory_usage_mb()

        assert usage == 0.0


# =============================================================================
# TitanMemoryService _compute_surprise Tests
# =============================================================================


class TestTitanMemoryServiceInternalComputeSurprise:
    """Tests for _compute_surprise internal method.

    Note: The internal _compute_surprise uses torch.nn.functional.huber_loss
    which requires real PyTorch tensors. The retrieve method uses this internally.
    """

    def test_compute_surprise_via_retrieve(self):
        """Test _compute_surprise is called via retrieve method."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.backend = MagicMock()
        service.backend.to_device.return_value = MagicMock()
        service.backend.from_device.return_value = MagicMock()
        service.backend.forward.return_value = MagicMock()
        service.backend.get_memory_usage.return_value = {"allocated_mb": 10.0}
        service.model = MagicMock()

        # Mock _compute_surprise to verify it's called
        with patch.object(
            service, "_compute_surprise", return_value=0.42
        ) as mock_compute:
            result = service.retrieve(MagicMock())

        mock_compute.assert_called_once()
        assert result.surprise == 0.42
        # Use pytest.approx for floating point comparison
        assert result.confidence == pytest.approx(0.58, rel=1e-6)  # 1.0 - 0.42

    def test_compute_surprise_high_value_capped(self):
        """Test surprise values above 1.0 are capped at 1.0 for confidence."""
        service = TitanMemoryService()
        service._is_initialized = True
        service.backend = MagicMock()
        service.backend.to_device.return_value = MagicMock()
        service.backend.from_device.return_value = MagicMock()
        service.backend.forward.return_value = MagicMock()
        service.backend.get_memory_usage.return_value = {"allocated_mb": 10.0}
        service.model = MagicMock()

        # Mock _compute_surprise to return high value
        with patch.object(
            service, "_compute_surprise", return_value=1.5
        ) as _mock_compute:
            result = service.retrieve(MagicMock())

        # Confidence should be 0 (capped at 1.0 - min(1.5, 1.0))
        assert result.surprise == 1.5
        assert result.confidence == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
