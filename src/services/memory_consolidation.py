"""Memory Consolidation for Neural Memory Production Hardening.

This module provides memory size management and consolidation features
for the Titan neural memory system, ensuring stable production operation.

Key features:
1. Memory size limit enforcement
2. Automatic consolidation when limits approached
3. Priority-based memory retention
4. Graceful degradation under memory pressure

Reference: ADR-024 - Titan Neural Memory Architecture Integration (Phase 5)
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

import torch

logger = logging.getLogger(__name__)


class ConsolidationStrategy(Enum):
    """Strategies for memory consolidation."""

    # Reset to initial state (lose all learned knowledge)
    FULL_RESET = "full_reset"

    # Scale down weights to reduce memory footprint
    WEIGHT_PRUNING = "weight_pruning"

    # Reduce persistent memory slots
    SLOT_REDUCTION = "slot_reduction"

    # Reinitialize least important layers
    LAYER_RESET = "layer_reset"

    # Warn only, don't take action
    WARN_ONLY = "warn_only"


class MemoryPressureLevel(Enum):
    """Memory pressure levels.

    Values are ordered so they can be compared with >= and <=.
    """

    NORMAL = 0  # < 70% utilization
    WARNING = 1  # 70-85% utilization
    HIGH = 2  # 85-95% utilization
    CRITICAL = 3  # > 95% utilization

    def __ge__(self, other: object) -> bool:
        if self.__class__ is other.__class__:
            return bool(self.value >= other.value)  # type: ignore[attr-defined]
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if self.__class__ is other.__class__:
            return bool(self.value > other.value)  # type: ignore[attr-defined]
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if self.__class__ is other.__class__:
            return bool(self.value <= other.value)  # type: ignore[attr-defined]
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        if self.__class__ is other.__class__:
            return bool(self.value < other.value)  # type: ignore[attr-defined]
        return NotImplemented


@dataclass
class ConsolidationConfig:
    """Configuration for memory consolidation.

    Attributes:
        max_memory_mb: Maximum memory size in MB
        warning_threshold: Utilization threshold for warnings (0-1)
        high_threshold: Utilization threshold for high pressure (0-1)
        critical_threshold: Utilization threshold for critical (0-1)
        consolidation_strategy: Strategy for handling memory pressure
        prune_ratio: Ratio of weights to prune (for WEIGHT_PRUNING)
        slot_reduction_ratio: Ratio of slots to remove (for SLOT_REDUCTION)
        layers_to_reset: Number of layers to reset (for LAYER_RESET)
        enable_auto_consolidation: Automatically consolidate when needed
        check_interval_updates: Check memory every N updates
    """

    max_memory_mb: float = 100.0
    warning_threshold: float = 0.70
    high_threshold: float = 0.85
    critical_threshold: float = 0.95
    consolidation_strategy: ConsolidationStrategy = ConsolidationStrategy.WEIGHT_PRUNING
    prune_ratio: float = 0.1  # Prune 10% of smallest weights
    slot_reduction_ratio: float = 0.25  # Remove 25% of slots
    layers_to_reset: int = 1  # Reset last layer
    enable_auto_consolidation: bool = True
    check_interval_updates: int = 100


@dataclass
class ConsolidationResult:
    """Result of a consolidation operation."""

    strategy_used: ConsolidationStrategy
    memory_before_mb: float
    memory_after_mb: float
    reduction_mb: float
    reduction_percent: float
    weights_pruned: int = 0
    slots_removed: int = 0
    layers_reset: int = 0
    duration_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None


class MemoryConsolidationManager:
    """Manages memory consolidation for neural memory systems.

    This manager monitors memory usage and performs consolidation
    when configured thresholds are exceeded.

    Usage:
        ```python
        # Create manager
        manager = MemoryConsolidationManager(
            config=ConsolidationConfig(max_memory_mb=100.0),
        )

        # Check memory status
        pressure = manager.check_memory_pressure(current_mb=85.0)

        # Consolidate if needed
        if pressure >= MemoryPressureLevel.HIGH:
            result = manager.consolidate(model)
        ```
    """

    def __init__(
        self,
        config: Optional[ConsolidationConfig] = None,
        on_consolidation: Optional[Callable[[ConsolidationResult], None]] = None,
        on_pressure_change: Optional[Callable[[MemoryPressureLevel], None]] = None,
    ):
        """Initialize consolidation manager.

        Args:
            config: Consolidation configuration
            on_consolidation: Callback when consolidation occurs
            on_pressure_change: Callback when pressure level changes
        """
        self.config = config or ConsolidationConfig()
        self.on_consolidation = on_consolidation
        self.on_pressure_change = on_pressure_change

        self._current_pressure = MemoryPressureLevel.NORMAL
        self._consolidation_count = 0
        self._updates_since_check = 0
        self._total_reduction_mb = 0.0

    def check_memory_pressure(self, current_mb: float) -> MemoryPressureLevel:
        """Check current memory pressure level.

        Args:
            current_mb: Current memory usage in MB

        Returns:
            Current pressure level
        """
        utilization = current_mb / self.config.max_memory_mb

        if utilization >= self.config.critical_threshold:
            new_pressure = MemoryPressureLevel.CRITICAL
        elif utilization >= self.config.high_threshold:
            new_pressure = MemoryPressureLevel.HIGH
        elif utilization >= self.config.warning_threshold:
            new_pressure = MemoryPressureLevel.WARNING
        else:
            new_pressure = MemoryPressureLevel.NORMAL

        # Notify on pressure change
        if new_pressure != self._current_pressure:
            logger.info(
                f"Memory pressure changed: {self._current_pressure.value} -> {new_pressure.value} "
                f"({current_mb:.2f} / {self.config.max_memory_mb:.2f} MB, "
                f"{utilization:.1%} utilization)"
            )
            if self.on_pressure_change:
                self.on_pressure_change(new_pressure)
            self._current_pressure = new_pressure

        return new_pressure

    def should_consolidate(
        self,
        current_mb: float,
        force: bool = False,
    ) -> bool:
        """Determine if consolidation should occur.

        Args:
            current_mb: Current memory usage in MB
            force: Force consolidation regardless of thresholds

        Returns:
            True if consolidation should be performed
        """
        if force:
            return True

        if not self.config.enable_auto_consolidation:
            return False

        pressure = self.check_memory_pressure(current_mb)
        return pressure >= MemoryPressureLevel.HIGH

    def record_update(self, current_mb: float) -> Optional[ConsolidationResult]:
        """Record an update and check if consolidation needed.

        Args:
            current_mb: Current memory usage in MB

        Returns:
            ConsolidationResult if consolidation was performed, None otherwise
        """
        self._updates_since_check += 1

        if self._updates_since_check >= self.config.check_interval_updates:
            self._updates_since_check = 0
            pressure = self.check_memory_pressure(current_mb)

            if pressure >= MemoryPressureLevel.CRITICAL:
                logger.warning(
                    f"Critical memory pressure! {current_mb:.2f} / {self.config.max_memory_mb:.2f} MB"
                )
                return None  # Return None, let caller decide to consolidate

        return None

    def consolidate(
        self,
        model: torch.nn.Module,
        strategy: Optional[ConsolidationStrategy] = None,
    ) -> ConsolidationResult:
        """Perform memory consolidation.

        Args:
            model: Neural memory model to consolidate
            strategy: Strategy to use (defaults to config strategy)

        Returns:
            ConsolidationResult with details of the operation
        """
        start_time = time.perf_counter()
        strategy = strategy or self.config.consolidation_strategy

        # Get current memory usage
        memory_before = self._get_model_memory_mb(model)

        logger.info(f"Starting memory consolidation with strategy: {strategy.value}")

        try:
            # Compare by value to handle cases where enum class instances differ
            # (can happen in test environments with module reloading)
            strategy_value = strategy.value if hasattr(strategy, "value") else strategy
            if strategy_value == ConsolidationStrategy.FULL_RESET.value:
                result = self._full_reset(model, memory_before)
            elif strategy_value == ConsolidationStrategy.WEIGHT_PRUNING.value:
                result = self._weight_pruning(model, memory_before)
            elif strategy_value == ConsolidationStrategy.SLOT_REDUCTION.value:
                result = self._slot_reduction(model, memory_before)
            elif strategy_value == ConsolidationStrategy.LAYER_RESET.value:
                result = self._layer_reset(model, memory_before)
            elif strategy_value == ConsolidationStrategy.WARN_ONLY.value:
                result = ConsolidationResult(
                    strategy_used=strategy,
                    memory_before_mb=memory_before,
                    memory_after_mb=memory_before,
                    reduction_mb=0.0,
                    reduction_percent=0.0,
                )
            else:
                raise ValueError(f"Unknown consolidation strategy: {strategy}")

            result.duration_ms = (time.perf_counter() - start_time) * 1000
            result.success = True

            logger.info(
                f"Consolidation complete: {result.memory_before_mb:.2f} -> "
                f"{result.memory_after_mb:.2f} MB ({result.reduction_percent:.1f}% reduction)"
            )

        except Exception as e:
            logger.error(f"Consolidation failed: {e}")
            return ConsolidationResult(
                strategy_used=strategy,
                memory_before_mb=memory_before,
                memory_after_mb=memory_before,
                reduction_mb=0.0,
                reduction_percent=0.0,
                duration_ms=(time.perf_counter() - start_time) * 1000,
                success=False,
                error_message=str(e),
            )

        # Update stats AFTER try block succeeds (before callback)
        self._consolidation_count += 1
        self._total_reduction_mb += result.reduction_mb

        # Notify callback with separate error handling
        # Callback failure should not affect consolidation success or stats
        if self.on_consolidation:
            try:
                self.on_consolidation(result)
            except Exception as callback_error:
                logger.warning(
                    f"Consolidation callback failed (consolidation itself succeeded): "
                    f"{callback_error}"
                )
                # Note: We don't modify result.success here because
                # the consolidation itself was successful

        return result

    def _full_reset(
        self,
        model: torch.nn.Module,
        memory_before: float,
    ) -> ConsolidationResult:
        """Full reset: reinitialize all weights."""
        # Reinitialize all parameters
        for module in model.modules():
            if hasattr(module, "reset_parameters"):
                module.reset_parameters()
            elif isinstance(module, torch.nn.Linear):
                torch.nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    torch.nn.init.zeros_(module.bias)

        memory_after = self._get_model_memory_mb(model)

        return ConsolidationResult(
            strategy_used=ConsolidationStrategy.FULL_RESET,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            reduction_mb=memory_before - memory_after,
            reduction_percent=(
                (memory_before - memory_after) / memory_before * 100
                if memory_before > 0
                else 0.0
            ),
        )

    def _weight_pruning(
        self,
        model: torch.nn.Module,
        memory_before: float,
    ) -> ConsolidationResult:
        """Weight pruning: zero out smallest magnitude weights."""
        weights_pruned = 0

        with torch.no_grad():
            for name, param in model.named_parameters():
                if "weight" in name and param.dim() >= 2:
                    # Compute threshold for pruning
                    flat = param.abs().flatten()
                    k = int(len(flat) * self.config.prune_ratio)

                    if k > 0:
                        threshold = torch.kthvalue(flat, k).values

                        # Create mask
                        mask = param.abs() >= threshold
                        param.mul_(mask.float())

                        weights_pruned += int((~mask).sum().item())

        memory_after = self._get_model_memory_mb(model)

        return ConsolidationResult(
            strategy_used=ConsolidationStrategy.WEIGHT_PRUNING,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            reduction_mb=memory_before - memory_after,
            reduction_percent=(
                (memory_before - memory_after) / memory_before * 100
                if memory_before > 0
                else 0.0
            ),
            weights_pruned=int(weights_pruned),
        )

    def _slot_reduction(
        self,
        model: torch.nn.Module,
        memory_before: float,
    ) -> ConsolidationResult:
        """Slot reduction: reduce persistent memory slots."""
        slots_removed = 0

        # Look for persistent memory module
        if hasattr(model, "persistent_memory"):
            pm = model.persistent_memory
            if hasattr(pm, "memory") and isinstance(pm.memory, torch.nn.Parameter):
                current_slots = pm.memory.shape[0]
                slots_to_keep = int(
                    current_slots * (1 - self.config.slot_reduction_ratio)
                )
                slots_to_keep = max(slots_to_keep, 8)  # Keep at least 8 slots

                if slots_to_keep < current_slots:
                    # Find most important slots (highest L2 norm)
                    with torch.no_grad():
                        norms = pm.memory.norm(dim=1)
                        _, indices = torch.topk(norms, slots_to_keep)
                        indices = indices.sort().values

                        # Create new smaller memory
                        new_memory = pm.memory[indices].clone()
                        pm.memory = torch.nn.Parameter(new_memory)
                        pm.num_slots = slots_to_keep

                        slots_removed = current_slots - slots_to_keep

        memory_after = self._get_model_memory_mb(model)

        return ConsolidationResult(
            strategy_used=ConsolidationStrategy.SLOT_REDUCTION,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            reduction_mb=memory_before - memory_after,
            reduction_percent=(
                (memory_before - memory_after) / memory_before * 100
                if memory_before > 0
                else 0.0
            ),
            slots_removed=slots_removed,
        )

    def _layer_reset(
        self,
        model: torch.nn.Module,
        memory_before: float,
    ) -> ConsolidationResult:
        """Layer reset: reinitialize least important layers."""
        layers_reset = 0

        # Look for MLP layers
        if hasattr(model, "layers"):
            layers = list(model.layers)
            layers_to_reset = min(self.config.layers_to_reset, len(layers))

            # Reset the last N layers (typically least specialized)
            for layer in layers[-layers_to_reset:]:
                for module in layer.modules():
                    if isinstance(module, torch.nn.Linear):
                        torch.nn.init.xavier_uniform_(module.weight)
                        if module.bias is not None:
                            torch.nn.init.zeros_(module.bias)
                    elif isinstance(module, torch.nn.LayerNorm):
                        if hasattr(module, "weight") and module.weight is not None:
                            torch.nn.init.ones_(module.weight)
                        if hasattr(module, "bias") and module.bias is not None:
                            torch.nn.init.zeros_(module.bias)
                layers_reset += 1

        memory_after = self._get_model_memory_mb(model)

        return ConsolidationResult(
            strategy_used=ConsolidationStrategy.LAYER_RESET,
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            reduction_mb=memory_before - memory_after,
            reduction_percent=(
                (memory_before - memory_after) / memory_before * 100
                if memory_before > 0
                else 0.0
            ),
            layers_reset=layers_reset,
        )

    def _get_model_memory_mb(self, model: torch.nn.Module) -> float:
        """Get model memory usage in MB."""
        param_count = sum(p.numel() for p in model.parameters())
        # FP32: 4 bytes per parameter
        return (param_count * 4) / (1024 * 1024)

    def get_stats(self) -> Dict[str, Any]:
        """Get consolidation manager statistics."""
        return {
            "current_pressure": self._current_pressure.value,
            "consolidation_count": self._consolidation_count,
            "total_reduction_mb": self._total_reduction_mb,
            "updates_since_check": self._updates_since_check,
            "config": {
                "max_memory_mb": self.config.max_memory_mb,
                "warning_threshold": self.config.warning_threshold,
                "high_threshold": self.config.high_threshold,
                "critical_threshold": self.config.critical_threshold,
                "strategy": self.config.consolidation_strategy.value,
                "auto_consolidation": self.config.enable_auto_consolidation,
            },
        }


class MemorySizeLimiter:
    """Enforces memory size limits on neural memory operations.

    This class wraps memory update operations to prevent exceeding
    configured memory limits.

    Usage:
        ```python
        limiter = MemorySizeLimiter(
            max_memory_mb=100.0,
            model=titan_memory_model,
        )

        # Check before update
        if limiter.can_update():
            # Perform update
            ...

        # Or use context manager
        with limiter.update_context():
            # Perform update
            ...
        ```
    """

    def __init__(
        self,
        max_memory_mb: float,
        model: torch.nn.Module,
        consolidation_manager: Optional[MemoryConsolidationManager] = None,
        on_limit_exceeded: Optional[Callable[[float, float], None]] = None,
    ):
        """Initialize size limiter.

        Args:
            max_memory_mb: Maximum memory size in MB
            model: Neural memory model
            consolidation_manager: Optional consolidation manager
            on_limit_exceeded: Callback when limit exceeded (current_mb, max_mb)
        """
        self.max_memory_mb = max_memory_mb
        self.model = model
        self.consolidation_manager = consolidation_manager
        self.on_limit_exceeded = on_limit_exceeded

        self._update_rejected_count = 0
        self._consolidation_triggered_count = 0

    def get_current_memory_mb(self) -> float:
        """Get current memory usage in MB."""
        param_count = sum(p.numel() for p in self.model.parameters())
        return (param_count * 4) / (1024 * 1024)

    def get_utilization(self) -> float:
        """Get current memory utilization (0-1)."""
        return self.get_current_memory_mb() / self.max_memory_mb

    def can_update(self) -> bool:
        """Check if an update can be performed within limits."""
        current = self.get_current_memory_mb()
        return current < self.max_memory_mb

    def check_and_enforce(self) -> bool:
        """Check limits and enforce if necessary.

        Returns:
            True if within limits, False if limit exceeded
        """
        current = self.get_current_memory_mb()

        if current >= self.max_memory_mb:
            logger.warning(
                f"Memory limit exceeded: {current:.2f} / {self.max_memory_mb:.2f} MB"
            )

            if self.on_limit_exceeded:
                self.on_limit_exceeded(current, self.max_memory_mb)

            # Try consolidation if available
            if self.consolidation_manager:
                self._consolidation_triggered_count += 1
                result = self.consolidation_manager.consolidate(self.model)

                if result.success and result.memory_after_mb < self.max_memory_mb:
                    logger.info("Consolidation brought memory within limits")
                    return True

            self._update_rejected_count += 1
            return False

        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get limiter statistics."""
        return {
            "max_memory_mb": self.max_memory_mb,
            "current_memory_mb": self.get_current_memory_mb(),
            "utilization": self.get_utilization(),
            "update_rejected_count": self._update_rejected_count,
            "consolidation_triggered_count": self._consolidation_triggered_count,
        }


def create_production_consolidation_config(
    max_memory_mb: float = 100.0,
    strategy: ConsolidationStrategy = ConsolidationStrategy.WEIGHT_PRUNING,
) -> ConsolidationConfig:
    """Factory function for production consolidation config.

    Args:
        max_memory_mb: Maximum memory size
        strategy: Consolidation strategy

    Returns:
        Production-hardened ConsolidationConfig
    """
    return ConsolidationConfig(
        max_memory_mb=max_memory_mb,
        warning_threshold=0.70,
        high_threshold=0.85,
        critical_threshold=0.95,
        consolidation_strategy=strategy,
        prune_ratio=0.10,
        slot_reduction_ratio=0.25,
        layers_to_reset=1,
        enable_auto_consolidation=True,
        check_interval_updates=100,
    )
