"""
Tests for Memory Consolidation Service.

Covers the MemoryConsolidationManager and MemorySizeLimiter classes
for neural memory production hardening.
"""

import sys
from unittest.mock import MagicMock

import pytest

# Save original modules before mocking to prevent test pollution
_modules_to_save = ["torch", "src.services.memory_consolidation"]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock torch before importing
mock_torch = MagicMock()
mock_torch.nn = MagicMock()
mock_torch.nn.Module = type("Module", (), {})
mock_torch.nn.Linear = type("Linear", (), {})
mock_torch.nn.LayerNorm = type("LayerNorm", (), {})
mock_torch.nn.Parameter = MagicMock()
mock_torch.no_grad = MagicMock(
    return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
)
sys.modules["torch"] = mock_torch

from src.services.memory_consolidation import (
    ConsolidationConfig,
    ConsolidationResult,
    ConsolidationStrategy,
    MemoryConsolidationManager,
    MemoryPressureLevel,
    MemorySizeLimiter,
    create_production_consolidation_config,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


# =============================================================================
# ConsolidationStrategy Enum Tests
# =============================================================================


class TestConsolidationStrategy:
    """Tests for ConsolidationStrategy enum."""

    def test_full_reset(self):
        """Test full reset strategy."""
        assert ConsolidationStrategy.FULL_RESET.value == "full_reset"

    def test_weight_pruning(self):
        """Test weight pruning strategy."""
        assert ConsolidationStrategy.WEIGHT_PRUNING.value == "weight_pruning"

    def test_slot_reduction(self):
        """Test slot reduction strategy."""
        assert ConsolidationStrategy.SLOT_REDUCTION.value == "slot_reduction"

    def test_layer_reset(self):
        """Test layer reset strategy."""
        assert ConsolidationStrategy.LAYER_RESET.value == "layer_reset"

    def test_warn_only(self):
        """Test warn only strategy."""
        assert ConsolidationStrategy.WARN_ONLY.value == "warn_only"

    def test_strategy_count(self):
        """Test that all 5 strategies exist."""
        assert len(ConsolidationStrategy) == 5


# =============================================================================
# MemoryPressureLevel Enum Tests
# =============================================================================


class TestMemoryPressureLevel:
    """Tests for MemoryPressureLevel enum."""

    def test_normal(self):
        """Test normal pressure level."""
        assert MemoryPressureLevel.NORMAL.value == 0

    def test_warning(self):
        """Test warning pressure level."""
        assert MemoryPressureLevel.WARNING.value == 1

    def test_high(self):
        """Test high pressure level."""
        assert MemoryPressureLevel.HIGH.value == 2

    def test_critical(self):
        """Test critical pressure level."""
        assert MemoryPressureLevel.CRITICAL.value == 3

    def test_pressure_count(self):
        """Test that all 4 pressure levels exist."""
        assert len(MemoryPressureLevel) == 4

    def test_comparison_ge(self):
        """Test greater than or equal comparison."""
        assert MemoryPressureLevel.HIGH >= MemoryPressureLevel.WARNING
        assert MemoryPressureLevel.HIGH >= MemoryPressureLevel.HIGH
        assert not (MemoryPressureLevel.WARNING >= MemoryPressureLevel.HIGH)

    def test_comparison_gt(self):
        """Test greater than comparison."""
        assert MemoryPressureLevel.CRITICAL > MemoryPressureLevel.HIGH
        assert not (MemoryPressureLevel.HIGH > MemoryPressureLevel.HIGH)

    def test_comparison_le(self):
        """Test less than or equal comparison."""
        assert MemoryPressureLevel.WARNING <= MemoryPressureLevel.HIGH
        assert MemoryPressureLevel.HIGH <= MemoryPressureLevel.HIGH

    def test_comparison_lt(self):
        """Test less than comparison."""
        assert MemoryPressureLevel.NORMAL < MemoryPressureLevel.WARNING
        assert not (MemoryPressureLevel.WARNING < MemoryPressureLevel.NORMAL)


# =============================================================================
# ConsolidationConfig Dataclass Tests
# =============================================================================


class TestConsolidationConfig:
    """Tests for ConsolidationConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ConsolidationConfig()
        assert config.max_memory_mb == 100.0
        assert config.warning_threshold == 0.70
        assert config.high_threshold == 0.85
        assert config.critical_threshold == 0.95
        assert config.consolidation_strategy == ConsolidationStrategy.WEIGHT_PRUNING
        assert config.prune_ratio == 0.1
        assert config.slot_reduction_ratio == 0.25
        assert config.layers_to_reset == 1
        assert config.enable_auto_consolidation is True
        assert config.check_interval_updates == 100

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ConsolidationConfig(
            max_memory_mb=200.0,
            warning_threshold=0.60,
            high_threshold=0.80,
            critical_threshold=0.90,
            consolidation_strategy=ConsolidationStrategy.SLOT_REDUCTION,
            prune_ratio=0.2,
            slot_reduction_ratio=0.5,
            layers_to_reset=2,
            enable_auto_consolidation=False,
            check_interval_updates=50,
        )
        assert config.max_memory_mb == 200.0
        assert config.warning_threshold == 0.60
        assert config.consolidation_strategy == ConsolidationStrategy.SLOT_REDUCTION
        assert config.enable_auto_consolidation is False


# =============================================================================
# ConsolidationResult Dataclass Tests
# =============================================================================


class TestConsolidationResult:
    """Tests for ConsolidationResult dataclass."""

    def test_create_basic_result(self):
        """Test creating a basic result."""
        result = ConsolidationResult(
            strategy_used=ConsolidationStrategy.WEIGHT_PRUNING,
            memory_before_mb=90.0,
            memory_after_mb=80.0,
            reduction_mb=10.0,
            reduction_percent=11.1,
        )
        assert result.strategy_used == ConsolidationStrategy.WEIGHT_PRUNING
        assert result.memory_before_mb == 90.0
        assert result.memory_after_mb == 80.0
        assert result.reduction_mb == 10.0

    def test_default_values(self):
        """Test default optional values."""
        result = ConsolidationResult(
            strategy_used=ConsolidationStrategy.FULL_RESET,
            memory_before_mb=100.0,
            memory_after_mb=50.0,
            reduction_mb=50.0,
            reduction_percent=50.0,
        )
        assert result.weights_pruned == 0
        assert result.slots_removed == 0
        assert result.layers_reset == 0
        assert result.duration_ms == 0.0
        assert result.success is True
        assert result.error_message is None

    def test_full_result(self):
        """Test result with all fields."""
        result = ConsolidationResult(
            strategy_used=ConsolidationStrategy.WEIGHT_PRUNING,
            memory_before_mb=100.0,
            memory_after_mb=85.0,
            reduction_mb=15.0,
            reduction_percent=15.0,
            weights_pruned=1000,
            slots_removed=0,
            layers_reset=0,
            duration_ms=50.5,
            success=True,
            error_message=None,
        )
        assert result.weights_pruned == 1000
        assert result.duration_ms == 50.5

    def test_failed_result(self):
        """Test failed result."""
        result = ConsolidationResult(
            strategy_used=ConsolidationStrategy.LAYER_RESET,
            memory_before_mb=100.0,
            memory_after_mb=100.0,
            reduction_mb=0.0,
            reduction_percent=0.0,
            success=False,
            error_message="Consolidation failed: out of memory",
        )
        assert result.success is False
        assert "Consolidation failed" in result.error_message


# =============================================================================
# MemoryConsolidationManager Tests
# =============================================================================


class TestMemoryConsolidationManager:
    """Tests for MemoryConsolidationManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ConsolidationConfig(max_memory_mb=100.0)
        self.manager = MemoryConsolidationManager(config=self.config)

    def test_initialization_default(self):
        """Test initialization with defaults."""
        manager = MemoryConsolidationManager()
        assert manager.config is not None
        assert manager.config.max_memory_mb == 100.0
        assert manager._current_pressure == MemoryPressureLevel.NORMAL
        assert manager._consolidation_count == 0

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = ConsolidationConfig(max_memory_mb=200.0)
        manager = MemoryConsolidationManager(config=config)
        assert manager.config.max_memory_mb == 200.0

    def test_initialization_with_callbacks(self):
        """Test initialization with callbacks."""
        on_consolidation = MagicMock()
        on_pressure_change = MagicMock()
        manager = MemoryConsolidationManager(
            on_consolidation=on_consolidation,
            on_pressure_change=on_pressure_change,
        )
        assert manager.on_consolidation == on_consolidation
        assert manager.on_pressure_change == on_pressure_change


class TestMemoryPressureCheck:
    """Tests for memory pressure checking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ConsolidationConfig(
            max_memory_mb=100.0,
            warning_threshold=0.70,
            high_threshold=0.85,
            critical_threshold=0.95,
        )
        self.manager = MemoryConsolidationManager(config=self.config)

    def test_pressure_normal(self):
        """Test normal pressure level."""
        pressure = self.manager.check_memory_pressure(50.0)  # 50%
        assert pressure == MemoryPressureLevel.NORMAL

    def test_pressure_warning(self):
        """Test warning pressure level."""
        pressure = self.manager.check_memory_pressure(75.0)  # 75%
        assert pressure == MemoryPressureLevel.WARNING

    def test_pressure_high(self):
        """Test high pressure level."""
        pressure = self.manager.check_memory_pressure(90.0)  # 90%
        assert pressure == MemoryPressureLevel.HIGH

    def test_pressure_critical(self):
        """Test critical pressure level."""
        pressure = self.manager.check_memory_pressure(98.0)  # 98%
        assert pressure == MemoryPressureLevel.CRITICAL

    def test_pressure_change_callback(self):
        """Test pressure change callback is called."""
        callback = MagicMock()
        manager = MemoryConsolidationManager(
            config=self.config,
            on_pressure_change=callback,
        )

        # First call - normal
        manager.check_memory_pressure(50.0)

        # Change to warning
        manager.check_memory_pressure(75.0)
        callback.assert_called_once_with(MemoryPressureLevel.WARNING)


class TestShouldConsolidate:
    """Tests for consolidation decision."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ConsolidationConfig(max_memory_mb=100.0)
        self.manager = MemoryConsolidationManager(config=self.config)

    def test_should_consolidate_high_pressure(self):
        """Test should consolidate at high pressure."""
        result = self.manager.should_consolidate(90.0)
        assert result is True

    def test_should_not_consolidate_low_pressure(self):
        """Test should not consolidate at low pressure."""
        result = self.manager.should_consolidate(50.0)
        assert result is False

    def test_force_consolidation(self):
        """Test force consolidation."""
        result = self.manager.should_consolidate(50.0, force=True)
        assert result is True

    def test_auto_consolidation_disabled(self):
        """Test auto consolidation disabled."""
        config = ConsolidationConfig(enable_auto_consolidation=False)
        manager = MemoryConsolidationManager(config=config)
        result = manager.should_consolidate(95.0)
        assert result is False


class TestRecordUpdate:
    """Tests for update recording."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ConsolidationConfig(
            max_memory_mb=100.0,
            check_interval_updates=10,
        )
        self.manager = MemoryConsolidationManager(config=self.config)

    def test_record_update_increments_counter(self):
        """Test that recording updates increments counter."""
        assert self.manager._updates_since_check == 0
        self.manager.record_update(50.0)
        assert self.manager._updates_since_check == 1

    def test_record_update_resets_at_interval(self):
        """Test counter resets at check interval."""
        for i in range(9):
            self.manager.record_update(50.0)
        assert self.manager._updates_since_check == 9

        # 10th update triggers check
        self.manager.record_update(50.0)
        assert self.manager._updates_since_check == 0


class TestConsolidateMethod:
    """Tests for consolidate method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ConsolidationConfig(max_memory_mb=100.0)
        self.manager = MemoryConsolidationManager(config=self.config)

        # Create mock model
        self.mock_model = MagicMock()
        self.mock_model.parameters.return_value = []
        self.mock_model.modules.return_value = []

    def test_consolidate_warn_only(self):
        """Test consolidate with warn only strategy."""
        result = self.manager.consolidate(
            self.mock_model,
            strategy=ConsolidationStrategy.WARN_ONLY,
        )
        assert result.success is True
        assert result.strategy_used == ConsolidationStrategy.WARN_ONLY
        assert result.reduction_mb == 0.0

    def test_consolidate_increments_count(self):
        """Test consolidation increments counter."""
        assert self.manager._consolidation_count == 0
        self.manager.consolidate(
            self.mock_model,
            strategy=ConsolidationStrategy.WARN_ONLY,
        )
        assert self.manager._consolidation_count == 1

    def test_consolidate_callback(self):
        """Test consolidation callback is called."""
        callback = MagicMock()
        manager = MemoryConsolidationManager(
            config=self.config,
            on_consolidation=callback,
        )

        manager.consolidate(
            self.mock_model,
            strategy=ConsolidationStrategy.WARN_ONLY,
        )
        callback.assert_called_once()


class TestGetStats:
    """Tests for stats retrieval."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ConsolidationConfig(max_memory_mb=100.0)
        self.manager = MemoryConsolidationManager(config=self.config)

    def test_get_stats(self):
        """Test getting stats."""
        stats = self.manager.get_stats()

        assert "current_pressure" in stats
        assert "consolidation_count" in stats
        assert "total_reduction_mb" in stats
        assert "updates_since_check" in stats
        assert "config" in stats

        assert stats["current_pressure"] == 0  # NORMAL
        assert stats["consolidation_count"] == 0
        assert stats["config"]["max_memory_mb"] == 100.0


# =============================================================================
# MemorySizeLimiter Tests
# =============================================================================


class TestMemorySizeLimiter:
    """Tests for MemorySizeLimiter class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock model with known parameter count
        self.mock_model = MagicMock()
        # Simulate 1M parameters (4MB of FP32 memory)
        mock_param = MagicMock()
        mock_param.numel.return_value = 1_000_000
        self.mock_model.parameters.return_value = [mock_param]

        self.limiter = MemorySizeLimiter(
            max_memory_mb=10.0,
            model=self.mock_model,
        )

    def test_initialization(self):
        """Test limiter initialization."""
        assert self.limiter.max_memory_mb == 10.0
        assert self.limiter.model == self.mock_model
        assert self.limiter._update_rejected_count == 0
        assert self.limiter._consolidation_triggered_count == 0

    def test_get_current_memory_mb(self):
        """Test getting current memory usage."""
        memory = self.limiter.get_current_memory_mb()
        # 1M params * 4 bytes / 1MB = ~3.8MB
        assert memory == pytest.approx(3.8, rel=0.1)

    def test_get_utilization(self):
        """Test getting utilization."""
        utilization = self.limiter.get_utilization()
        # ~3.8MB / 10MB = ~0.38
        assert utilization == pytest.approx(0.38, rel=0.1)

    def test_can_update_within_limit(self):
        """Test can update when within limits."""
        result = self.limiter.can_update()
        assert result is True

    def test_can_update_at_limit(self):
        """Test can update when at limit."""
        # Make model exceed limit (10M params = ~38MB)
        mock_param = MagicMock()
        mock_param.numel.return_value = 10_000_000
        self.mock_model.parameters.return_value = [mock_param]

        result = self.limiter.can_update()
        assert result is False

    def test_check_and_enforce_within_limit(self):
        """Test check and enforce when within limits."""
        result = self.limiter.check_and_enforce()
        assert result is True

    def test_check_and_enforce_exceeds_limit(self):
        """Test check and enforce when exceeding limit."""
        # Make model exceed limit
        mock_param = MagicMock()
        mock_param.numel.return_value = 10_000_000
        self.mock_model.parameters.return_value = [mock_param]

        result = self.limiter.check_and_enforce()
        assert result is False
        assert self.limiter._update_rejected_count == 1

    def test_on_limit_exceeded_callback(self):
        """Test limit exceeded callback is called."""
        callback = MagicMock()
        limiter = MemorySizeLimiter(
            max_memory_mb=1.0,  # Very low limit
            model=self.mock_model,
            on_limit_exceeded=callback,
        )

        limiter.check_and_enforce()
        callback.assert_called_once()

    def test_get_stats(self):
        """Test getting limiter stats."""
        stats = self.limiter.get_stats()

        assert "max_memory_mb" in stats
        assert "current_memory_mb" in stats
        assert "utilization" in stats
        assert "update_rejected_count" in stats
        assert "consolidation_triggered_count" in stats

        assert stats["max_memory_mb"] == 10.0


class TestLimiterWithConsolidationManager:
    """Tests for limiter with consolidation manager."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock model with high memory usage
        self.mock_model = MagicMock()
        mock_param = MagicMock()
        mock_param.numel.return_value = 10_000_000  # ~38MB
        self.mock_model.parameters.return_value = [mock_param]
        self.mock_model.modules.return_value = []

        # Create consolidation manager
        self.consolidation_manager = MemoryConsolidationManager(
            config=ConsolidationConfig(max_memory_mb=50.0)
        )

        # Create limiter with consolidation manager
        self.limiter = MemorySizeLimiter(
            max_memory_mb=10.0,  # Low limit to trigger consolidation
            model=self.mock_model,
            consolidation_manager=self.consolidation_manager,
        )

    def test_consolidation_triggered_on_limit_exceeded(self):
        """Test consolidation is triggered when limit exceeded."""
        self.limiter.check_and_enforce()

        # Consolidation was triggered
        assert self.limiter._consolidation_triggered_count == 1


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_production_config_defaults(self):
        """Test creating production config with defaults."""
        config = create_production_consolidation_config()

        assert config.max_memory_mb == 100.0
        assert config.warning_threshold == 0.70
        assert config.high_threshold == 0.85
        assert config.critical_threshold == 0.95
        assert config.consolidation_strategy == ConsolidationStrategy.WEIGHT_PRUNING
        assert config.enable_auto_consolidation is True

    def test_create_production_config_custom_memory(self):
        """Test creating production config with custom memory limit."""
        config = create_production_consolidation_config(max_memory_mb=200.0)
        assert config.max_memory_mb == 200.0

    def test_create_production_config_custom_strategy(self):
        """Test creating production config with custom strategy."""
        config = create_production_consolidation_config(
            strategy=ConsolidationStrategy.SLOT_REDUCTION
        )
        assert config.consolidation_strategy == ConsolidationStrategy.SLOT_REDUCTION


# =============================================================================
# Integration Tests
# =============================================================================


class TestMemoryConsolidationIntegration:
    """Integration tests for memory consolidation workflow."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ConsolidationConfig(
            max_memory_mb=100.0,
            check_interval_updates=5,
        )
        self.manager = MemoryConsolidationManager(config=self.config)

        # Mock model
        self.mock_model = MagicMock()
        self.mock_model.parameters.return_value = []
        self.mock_model.modules.return_value = []

    def test_update_recording_and_pressure_check(self):
        """Test update recording leads to pressure check."""
        # Record updates below threshold
        for i in range(4):
            result = self.manager.record_update(50.0)
            assert result is None

        # 5th update triggers check
        result = self.manager.record_update(50.0)
        assert self.manager._updates_since_check == 0

    def test_pressure_escalation_workflow(self):
        """Test pressure escalation through levels."""
        pressure_changes = []
        self.manager.on_pressure_change = lambda p: pressure_changes.append(p)

        # Start at normal - no callback since initial state is already NORMAL
        self.manager.check_memory_pressure(50.0)

        # Escalate to warning - triggers callback
        self.manager.check_memory_pressure(75.0)

        # Escalate to high - triggers callback
        self.manager.check_memory_pressure(90.0)

        # Escalate to critical - triggers callback
        self.manager.check_memory_pressure(98.0)

        # Only 3 callbacks: NORMAL->WARNING, WARNING->HIGH, HIGH->CRITICAL
        assert len(pressure_changes) == 3
        assert pressure_changes[-1] == MemoryPressureLevel.CRITICAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
