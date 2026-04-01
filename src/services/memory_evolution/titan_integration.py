"""
Project Aura - Titan Memory Integration for REINFORCE Operation (ADR-080)

Integrates the REINFORCE refine operation with Titan's test-time training
to strengthen successful reasoning patterns.

Maps REINFORCE to Titan TTT:
- Positive outcome: Lower memorization_threshold (more likely to retrieve)
- High reuse: Increase TTT learning rate for related memories
- Negative outcome: Raise threshold (less reinforcement)

Reference: ADR-024 Titan Neural Memory Architecture
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from .config import MemoryEvolutionConfig, get_memory_evolution_config
from .contracts import RefineAction, RefineOperation, RefineResult
from .exceptions import FeatureDisabledError, ReinforceError, ValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLS
# =============================================================================


class TitanMemoryServiceProtocol(Protocol):
    """Protocol for Titan Memory Service interface."""

    @property
    def config(self) -> Any:
        """Get service configuration."""
        ...

    def compute_surprise(
        self,
        input_tensor: Any,
        target_tensor: Optional[Any] = None,
    ) -> float:
        """Compute surprise score for an input."""
        ...


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class TaskOutcome:
    """Outcome of a task execution for reinforcement."""

    success: bool
    task_id: str
    agent_id: str
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    quality_score: float = 0.0  # 0.0 to 1.0
    reuse_count: int = 0  # How many times this pattern was reused
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "quality_score": self.quality_score,
            "reuse_count": self.reuse_count,
            "metadata": self.metadata,
        }


@dataclass
class ReinforceMetrics:
    """Metrics from a REINFORCE operation."""

    threshold_adjustment: float  # Delta applied to memorization threshold
    learning_rate_multiplier: float  # Multiplier applied to TTT learning rate
    surprise_delta: float  # Change in surprise score
    affected_memories: int
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "threshold_adjustment": self.threshold_adjustment,
            "learning_rate_multiplier": self.learning_rate_multiplier,
            "surprise_delta": self.surprise_delta,
            "affected_memories": self.affected_memories,
            "latency_ms": self.latency_ms,
        }


# =============================================================================
# SURPRISE CALCULATOR
# =============================================================================


class SurpriseCalculator:
    """
    Calculates surprise deltas for reinforcement learning.

    Surprise delta = expected_outcome - actual_outcome
    - Positive delta: Outcome exceeded expectations (reinforce more)
    - Negative delta: Outcome below expectations (reinforce less)
    - Zero delta: Outcome matched expectations (neutral)
    """

    def __init__(self, momentum: float = 0.9):
        """
        Initialize calculator.

        Args:
            momentum: Smoothing momentum for running average
        """
        self.momentum = momentum
        self._running_avg: dict[str, float] = {}

    def compute_delta(
        self,
        expected_outcome: Optional[dict[str, Any]],
        actual_outcome: TaskOutcome,
    ) -> float:
        """
        Compute surprise delta between expected and actual outcomes.

        Args:
            expected_outcome: Expected outcome dict with 'success' and 'quality_score'
            actual_outcome: Actual task outcome

        Returns:
            Surprise delta between -1.0 and 1.0
        """
        if expected_outcome is None:
            # No expectation, use binary success as baseline
            return 1.0 if actual_outcome.success else -0.5

        expected_success = expected_outcome.get("success", True)
        expected_quality = expected_outcome.get("quality_score", 0.5)

        # Compute success component
        success_delta = 0.0
        if actual_outcome.success and not expected_success:
            success_delta = 0.5  # Exceeded expectations
        elif not actual_outcome.success and expected_success:
            success_delta = -0.5  # Failed expectations
        elif actual_outcome.success and expected_success:
            success_delta = 0.2  # Met expectations

        # Compute quality component
        quality_delta = actual_outcome.quality_score - expected_quality

        # Combine with weighting
        total_delta = (success_delta * 0.6) + (quality_delta * 0.4)

        # Apply momentum smoothing
        agent_key = actual_outcome.agent_id
        if agent_key in self._running_avg:
            smoothed = (
                self.momentum * total_delta
                + (1 - self.momentum) * self._running_avg[agent_key]
            )
            self._running_avg[agent_key] = smoothed
            return smoothed
        else:
            self._running_avg[agent_key] = total_delta
            return total_delta

    def reset_agent(self, agent_id: str) -> None:
        """Reset running average for an agent."""
        if agent_id in self._running_avg:
            del self._running_avg[agent_id]


# =============================================================================
# TITAN REFINE INTEGRATION
# =============================================================================


class TitanRefineIntegration:
    """
    Integrates Refine REINFORCE operation with Titan neural memory.

    Maps REINFORCE to Titan's test-time training:
    - Positive outcome: Lower memorization_threshold for pattern
    - High reuse: Increase TTT learning rate for related memories
    - Negative outcome: Raise threshold (less reinforcement)

    Thread Safety:
    - Threshold adjustments are applied per-memory-ID
    - Learning rate changes affect the shared optimizer
    """

    def __init__(
        self,
        titan_service: TitanMemoryServiceProtocol,
        surprise_calculator: Optional[SurpriseCalculator] = None,
        config: Optional[MemoryEvolutionConfig] = None,
    ):
        """
        Initialize Titan integration.

        Args:
            titan_service: Titan memory service instance
            surprise_calculator: Optional calculator (creates default if None)
            config: Memory evolution config
        """
        self.titan = titan_service
        self.surprise = surprise_calculator or SurpriseCalculator()
        self.config = config or get_memory_evolution_config()

        # Per-memory threshold adjustments (additive)
        self._threshold_adjustments: dict[str, float] = {}

        # Per-memory learning rate multipliers
        self._learning_rate_multipliers: dict[str, float] = {}

    async def reinforce_pattern(
        self,
        action: RefineAction,
        outcome: TaskOutcome,
    ) -> RefineResult:
        """
        Strengthen successful patterns via Titan TTT.

        Maps to:
        - Positive outcome: Lower memorization_threshold for pattern
        - High reuse: Increase TTT learning rate for related memories

        Args:
            action: REINFORCE action with target memory IDs
            outcome: Task execution outcome

        Returns:
            RefineResult with metrics

        Raises:
            FeatureDisabledError: If REINFORCE is disabled
            ReinforceError: If reinforcement fails
        """
        start_time = time.time()

        # Validate feature is enabled
        if not self.config.features.reinforce_enabled:
            raise FeatureDisabledError("reinforce", "1b")

        # Validate action
        if action.operation != RefineOperation.REINFORCE:
            raise ValidationError(
                f"Expected REINFORCE operation, got {action.operation.value}",
                field="operation",
                value=action.operation.value,
            )

        try:
            # Calculate surprise delta based on outcome
            surprise_delta = self.surprise.compute_delta(
                expected_outcome=action.metadata.get("expected_outcome"),
                actual_outcome=outcome,
            )

            # Determine adjustments based on outcome
            threshold_adjustment = 0.0
            learning_rate_multiplier = 1.0

            if outcome.success:
                # Lower threshold = more likely to be retrieved
                # Scale by confidence and surprise delta
                threshold_adjustment = (
                    -self.config.reinforce.threshold_adjustment
                    * action.confidence
                    * max(0.5, surprise_delta + 0.5)
                )

                # Increase learning rate for successful patterns
                # More reuse = higher boost
                reuse_factor = min(1.0, outcome.reuse_count / 10.0)
                learning_rate_multiplier = min(
                    self.config.reinforce.max_reinforcement_factor,
                    self.config.reinforce.learning_rate_factor
                    * (1 + reuse_factor * action.confidence),
                )
            else:
                # Raise threshold slightly for failed patterns
                threshold_adjustment = (
                    self.config.reinforce.threshold_adjustment * 0.5 * action.confidence
                )
                # Reduce learning rate slightly
                learning_rate_multiplier = 0.9

            # Apply adjustments to all target memories
            for memory_id in action.target_memory_ids:
                self._apply_threshold_adjustment(memory_id, threshold_adjustment)
                self._apply_learning_rate_multiplier(
                    memory_id, learning_rate_multiplier
                )

            latency_ms = (time.time() - start_time) * 1000

            metrics = ReinforceMetrics(
                threshold_adjustment=threshold_adjustment,
                learning_rate_multiplier=learning_rate_multiplier,
                surprise_delta=surprise_delta,
                affected_memories=len(action.target_memory_ids),
                latency_ms=latency_ms,
            )

            logger.info(
                f"REINFORCE applied: threshold_adj={threshold_adjustment:.4f}, "
                f"lr_mult={learning_rate_multiplier:.2f}, "
                f"memories={len(action.target_memory_ids)}"
            )

            return RefineResult(
                success=True,
                operation=RefineOperation.REINFORCE,
                affected_memory_ids=action.target_memory_ids,
                rollback_token=None,  # TTT changes are continuous
                latency_ms=latency_ms,
                metrics=metrics.to_dict(),
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"REINFORCE failed: {e}")
            raise ReinforceError(
                f"Failed to reinforce pattern: {e}",
                memory_ids=action.target_memory_ids,
                details={"outcome": outcome.to_dict()},
            ) from e

    def _apply_threshold_adjustment(
        self,
        memory_id: str,
        adjustment: float,
    ) -> None:
        """
        Apply threshold adjustment for a memory.

        Adjustments are additive and bounded.
        """
        current = self._threshold_adjustments.get(memory_id, 0.0)
        new_adjustment = current + adjustment

        # Bound adjustments to reasonable range
        # Max -0.3 (30% lower threshold) to +0.2 (20% higher)
        new_adjustment = max(-0.3, min(0.2, new_adjustment))
        self._threshold_adjustments[memory_id] = new_adjustment

    def _apply_learning_rate_multiplier(
        self,
        memory_id: str,
        multiplier: float,
    ) -> None:
        """
        Apply learning rate multiplier for a memory.

        Multipliers are multiplicative with bounds.
        """
        current = self._learning_rate_multipliers.get(memory_id, 1.0)
        new_multiplier = current * multiplier

        # Bound multiplier to reasonable range
        # 0.5 (half learning) to max_reinforcement_factor
        new_multiplier = max(
            0.5,
            min(self.config.reinforce.max_reinforcement_factor, new_multiplier),
        )
        self._learning_rate_multipliers[memory_id] = new_multiplier

    def get_effective_threshold(self, memory_id: str) -> float:
        """
        Get effective memorization threshold for a memory.

        Args:
            memory_id: Memory identifier

        Returns:
            Adjusted threshold value
        """
        base_threshold = self.titan.config.memorization_threshold
        adjustment = self._threshold_adjustments.get(memory_id, 0.0)
        return max(0.1, min(0.99, base_threshold + adjustment))

    def get_effective_learning_rate(self, memory_id: str) -> float:
        """
        Get effective TTT learning rate for a memory.

        Args:
            memory_id: Memory identifier

        Returns:
            Adjusted learning rate
        """
        base_lr = self.titan.config.ttt_learning_rate
        multiplier = self._learning_rate_multipliers.get(memory_id, 1.0)
        return base_lr * multiplier

    def get_reinforcement_stats(self) -> dict[str, Any]:
        """Get statistics about reinforcement adjustments."""
        threshold_values = list(self._threshold_adjustments.values())
        lr_values = list(self._learning_rate_multipliers.values())

        return {
            "memories_with_threshold_adjustment": len(threshold_values),
            "memories_with_lr_adjustment": len(lr_values),
            "avg_threshold_adjustment": (
                sum(threshold_values) / len(threshold_values) if threshold_values else 0
            ),
            "avg_lr_multiplier": (
                sum(lr_values) / len(lr_values) if lr_values else 1.0
            ),
            "min_threshold_adjustment": (
                min(threshold_values) if threshold_values else 0
            ),
            "max_threshold_adjustment": (
                max(threshold_values) if threshold_values else 0
            ),
        }

    def reset_memory_adjustments(self, memory_id: str) -> None:
        """Reset all adjustments for a specific memory."""
        if memory_id in self._threshold_adjustments:
            del self._threshold_adjustments[memory_id]
        if memory_id in self._learning_rate_multipliers:
            del self._learning_rate_multipliers[memory_id]

    def reset_all_adjustments(self) -> None:
        """Reset all reinforcement adjustments."""
        self._threshold_adjustments.clear()
        self._learning_rate_multipliers.clear()
        logger.info("All reinforcement adjustments reset")


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_titan_integration_instance: Optional[TitanRefineIntegration] = None


def get_titan_refine_integration(
    titan_service: Optional[TitanMemoryServiceProtocol] = None,
    surprise_calculator: Optional[SurpriseCalculator] = None,
    config: Optional[MemoryEvolutionConfig] = None,
) -> TitanRefineIntegration:
    """Get or create the singleton TitanRefineIntegration instance."""
    global _titan_integration_instance
    if _titan_integration_instance is None:
        if titan_service is None:
            raise ValueError("titan_service is required for initial creation")
        _titan_integration_instance = TitanRefineIntegration(
            titan_service=titan_service,
            surprise_calculator=surprise_calculator,
            config=config,
        )
    return _titan_integration_instance


def reset_titan_refine_integration() -> None:
    """Reset the singleton instance (for testing)."""
    global _titan_integration_instance
    _titan_integration_instance = None
