"""TitanMemoryService: Neural memory orchestrator for Project Aura.

This service provides the main interface for Titan-inspired neural memory,
coordinating:
1. DeepMLPMemory model for storage and retrieval
2. MIRAS configuration for loss functions and retention
3. Hardware backends for CPU/GPU/Inferentia2 execution
4. Surprise-based selective memorization
5. Memory size limits and consolidation (Phase 5)
6. Comprehensive audit logging (Phase 5)

Reference: Titans - Learning to Memorize at Test Time (arXiv:2501.00663)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F

from .memory_backends import BackendConfig, BackendType, CPUMemoryBackend, MemoryBackend
from .memory_consolidation import (
    ConsolidationConfig,
    ConsolidationResult,
    ConsolidationStrategy,
    MemoryConsolidationManager,
    MemoryPressureLevel,
    MemorySizeLimiter,
    create_production_consolidation_config,
)
from .models import (
    DeepMLPMemory,
    MemoryConfig,
    MIRASConfig,
    MIRASLossFunctions,
    MIRASOptimizer,
    MIRASRetention,
    get_miras_preset,
)
from .neural_memory_audit import InMemoryAuditStorage, NeuralMemoryAuditLogger

logger = logging.getLogger(__name__)


@dataclass
class TitanMemoryServiceConfig:
    """Configuration for TitanMemoryService.

    Attributes:
        memory_dim: Dimension of memory vectors
        memory_depth: Number of MLP layers in memory
        hidden_multiplier: Hidden layer size multiplier
        persistent_memory_size: Number of persistent memory slots
        miras_preset: Name of MIRAS preset or None for custom
        miras_config: Custom MIRAS configuration (overrides preset)
        backend_config: Hardware backend configuration
        enable_ttt: Enable test-time training
        ttt_learning_rate: Learning rate for TTT
        max_ttt_steps: Maximum TTT steps per update
        memorization_threshold: Surprise threshold for memorization
        surprise_momentum: Momentum for surprise smoothing
        max_memory_size_mb: Maximum memory size in MB
        enable_metrics: Enable performance metrics collection
        enable_audit_logging: Enable audit logging for all updates
        consolidation_config: Memory consolidation configuration
        enable_size_limit_enforcement: Enforce memory size limits
        environment: Environment name (dev, staging, prod)
    """

    # Memory architecture
    memory_dim: int = 512
    memory_depth: int = 3
    hidden_multiplier: int = 4
    persistent_memory_size: int = 64

    # MIRAS settings
    miras_preset: Optional[str] = "enterprise_standard"
    miras_config: Optional[MIRASConfig] = None

    # Backend settings
    backend_config: Optional[BackendConfig] = None

    # Test-time training
    enable_ttt: bool = True
    ttt_learning_rate: float = 0.001
    max_ttt_steps: int = 3

    # Surprise thresholds
    memorization_threshold: float = 0.7
    surprise_momentum: float = 0.9

    # Safety limits
    max_memory_size_mb: float = 100.0
    enable_size_limit_enforcement: bool = True

    # Consolidation (Phase 5)
    consolidation_config: Optional[ConsolidationConfig] = None

    # Observability
    enable_metrics: bool = True
    enable_audit_logging: bool = True
    environment: str = "dev"

    # Extra configuration
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryMetrics:
    """Metrics from memory operations."""

    operation: str
    latency_ms: float
    surprise_score: Optional[float] = None
    was_memorized: bool = False
    ttt_steps: int = 0
    memory_usage_mb: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class RetrievalResult:
    """Result from memory retrieval."""

    content: torch.Tensor
    confidence: float
    surprise: float
    latency_ms: float
    source: str = "neural"  # neural, persistent, hybrid


class TitanMemoryService:
    """Neural memory service with test-time training.

    This service provides a high-level interface for neural memory operations,
    abstracting away hardware details and providing enterprise-grade features:

    1. **Retrieval**: Query memory and get relevant context
    2. **Update**: Store new experiences with selective memorization
    3. **TTT**: Test-time training for inference-time learning
    4. **Metrics**: Performance and usage tracking

    Example:
        ```python
        # Create service with defaults (CPU backend, enterprise preset)
        service = TitanMemoryService()
        service.initialize()

        # Retrieve from memory
        query = torch.randn(1, 512)
        result = service.retrieve(query)

        # Store new experience (if surprising enough)
        key = torch.randn(1, 512)
        value = torch.randn(1, 512)
        was_stored = service.update(key, value)

        # Cleanup
        service.shutdown()
        ```
    """

    def __init__(self, config: Optional[TitanMemoryServiceConfig] = None) -> None:
        """Initialize TitanMemoryService.

        Args:
            config: Service configuration. Uses defaults if None.
        """
        self.config = config or TitanMemoryServiceConfig()

        # Initialize MIRAS config
        if self.config.miras_config is not None:
            self.miras_config = self.config.miras_config
        elif self.config.miras_preset is not None:
            self.miras_config = get_miras_preset(self.config.miras_preset)
        else:
            self.miras_config = MIRASConfig()

        # Components (initialized in initialize())
        self.model: Optional[DeepMLPMemory] = None
        self.backend: Optional[MemoryBackend] = None
        self.optimizer: Optional[torch.optim.Optimizer] = None

        # Phase 5: Consolidation manager
        consolidation_config = self.config.consolidation_config
        if consolidation_config is None:
            consolidation_config = create_production_consolidation_config(
                max_memory_mb=self.config.max_memory_size_mb,
            )
        self.consolidation_manager = MemoryConsolidationManager(
            config=consolidation_config,
            on_consolidation=self._on_consolidation,
            on_pressure_change=self._on_pressure_change,
        )
        self.size_limiter: Optional[MemorySizeLimiter] = None

        # Phase 5: Audit logger
        self.audit_logger: Optional[NeuralMemoryAuditLogger] = None
        if self.config.enable_audit_logging:
            self.audit_logger = NeuralMemoryAuditLogger(
                storage=InMemoryAuditStorage(max_records=10000),
                environment=self.config.environment,
                batch_size=100,
                auto_flush=True,
            )

        # State
        self._is_initialized = False
        self._past_surprise = 0.0
        self._update_count = 0
        self._retrieval_count = 0
        self._memory_age = 0.0
        self._updates_rejected_count = 0

        # Metrics storage
        self._metrics: List[MemoryMetrics] = []

    def initialize(self) -> None:
        """Initialize service components.

        Creates the memory model, sets up the backend, and prepares
        the optimizer for TTT updates.
        """
        if self._is_initialized:
            logger.warning("TitanMemoryService already initialized")
            return

        logger.info("Initializing TitanMemoryService...")

        # Create memory model
        memory_config = MemoryConfig(
            dim=self.config.memory_dim,
            depth=self.config.memory_depth,
            hidden_multiplier=self.config.hidden_multiplier,
            persistent_memory_size=self.config.persistent_memory_size,
        )
        self.model = DeepMLPMemory(memory_config)

        # Create backend
        if self.config.backend_config is not None:
            backend_config = self.config.backend_config
        else:
            # Default to CPU backend
            backend_config = BackendConfig(
                backend_type=BackendType.CPU,
                enable_ttt=self.config.enable_ttt,
                ttt_learning_rate=self.config.ttt_learning_rate,
            )

        # Currently only CPU backend is implemented
        if backend_config.backend_type == BackendType.CPU:
            self.backend = CPUMemoryBackend(backend_config)
        else:
            logger.warning(
                f"Backend {backend_config.backend_type} not implemented, "
                "falling back to CPU"
            )
            backend_config.backend_type = BackendType.CPU
            self.backend = CPUMemoryBackend(backend_config)

        self.backend.initialize()

        # Move model to backend device
        self.model = self.model.to(self.backend.device)

        # Create optimizer for TTT
        if self.config.enable_ttt:
            self.optimizer = MIRASOptimizer.create_optimizer(
                self.model,
                self.miras_config,
                self.config.ttt_learning_rate,
            )

        # Phase 5: Initialize size limiter
        if self.config.enable_size_limit_enforcement:
            self.size_limiter = MemorySizeLimiter(
                max_memory_mb=self.config.max_memory_size_mb,
                model=self.model,
                consolidation_manager=self.consolidation_manager,
                on_limit_exceeded=self._on_limit_exceeded,
            )

        self._is_initialized = True

        # Log initialization info
        param_count = self.model.get_parameter_count()
        memory_mb = self.model.get_memory_size_mb()
        logger.info(
            f"TitanMemoryService initialized: "
            f"{param_count:,} parameters, {memory_mb:.2f} MB"
        )

        # Phase 5: Audit log initialization
        if self.audit_logger:
            self.audit_logger.log_service_init(
                config={
                    "memory_dim": self.config.memory_dim,
                    "memory_depth": self.config.memory_depth,
                    "miras_preset": self.config.miras_preset,
                    "enable_ttt": self.config.enable_ttt,
                    "max_memory_size_mb": self.config.max_memory_size_mb,
                    "enable_size_limit_enforcement": self.config.enable_size_limit_enforcement,
                },
                memory_size_mb=memory_mb,
            )

    def shutdown(self) -> None:
        """Shutdown service and release resources."""
        if not self._is_initialized:
            return

        logger.info("Shutting down TitanMemoryService...")

        # Phase 5: Audit log shutdown
        if self.audit_logger:
            self.audit_logger.log_service_shutdown(
                stats=self.get_stats(),
            )
            self.audit_logger.flush()

        if self.backend is not None:
            self.backend.cleanup()

        self.model = None
        self.backend = None
        self.optimizer = None
        self.size_limiter = None
        self._is_initialized = False

        logger.info("TitanMemoryService shutdown complete")

    def retrieve(
        self,
        query: torch.Tensor,
        use_persistent: bool = True,
        actor: str = "system",
    ) -> RetrievalResult:
        """Retrieve from memory given a query.

        Args:
            query: Query tensor [batch_size, dim]
            use_persistent: Whether to include persistent memory
            actor: Actor identifier for audit logging

        Returns:
            RetrievalResult with content, confidence, and metrics
        """
        self._ensure_initialized()
        backend = self._backend
        model = self._model

        start_time = time.perf_counter()

        # Move query to backend device
        query = backend.to_device(query)

        # Forward pass through model
        with torch.no_grad():
            output = backend.forward(
                model,
                query,
                use_persistent=use_persistent,
            )

        # Compute surprise as confidence inverse
        surprise = self._compute_surprise(query, output)
        confidence = 1.0 - min(surprise, 1.0)

        # Move output to CPU for return
        output = backend.from_device(output)

        latency_ms = (time.perf_counter() - start_time) * 1000
        memory_mb = self._get_memory_usage_mb()

        # Record metrics
        self._retrieval_count += 1
        if self.config.enable_metrics:
            self._record_metric(
                MemoryMetrics(
                    operation="retrieve",
                    latency_ms=latency_ms,
                    surprise_score=surprise,
                    memory_usage_mb=memory_mb,
                )
            )

        # Phase 5: Audit logging
        if self.audit_logger:
            self.audit_logger.log_memory_retrieve(
                actor=actor,
                surprise_score=surprise,
                latency_ms=latency_ms,
                memory_size_mb=memory_mb,
                details={"use_persistent": use_persistent},
            )

        source = "hybrid" if use_persistent else "neural"
        return RetrievalResult(
            content=output,
            confidence=confidence,
            surprise=surprise,
            latency_ms=latency_ms,
            source=source,
        )

    def update(
        self,
        key: torch.Tensor,
        value: torch.Tensor,
        force_memorize: bool = False,
        actor: str = "system",
    ) -> Tuple[bool, float]:
        """Store experience in memory with selective memorization.

        Uses surprise-based gating: only store if the experience is
        surprising (high gradient magnitude).

        Args:
            key: Key tensor for storage [batch_size, dim]
            value: Value tensor to store [batch_size, dim]
            force_memorize: Force storage regardless of surprise
            actor: Actor identifier for audit logging

        Returns:
            Tuple of (was_memorized, surprise_score)
        """
        self._ensure_initialized()
        backend = self._backend
        model = self._model

        if not self.config.enable_ttt:
            logger.debug("TTT disabled, skipping update")
            return False, 0.0

        start_time = time.perf_counter()

        # Phase 5: Check size limits before update
        if self.size_limiter and not self.size_limiter.can_update():
            if not self.size_limiter.check_and_enforce():
                self._updates_rejected_count += 1
                logger.warning("Update rejected: memory size limit exceeded")
                if self.audit_logger:
                    self.audit_logger.log_size_limit_exceeded(
                        current_size_mb=self.size_limiter.get_current_memory_mb(),
                        max_size_mb=self.size_limiter.max_memory_mb,
                        action_taken="update_rejected",
                    )
                return False, 0.0

        # Move tensors to backend device
        key = backend.to_device(key)
        value = backend.to_device(value)

        # Compute surprise score
        surprise = backend.compute_surprise(model, key, value)

        # Apply momentum smoothing
        effective_surprise = (
            self.config.surprise_momentum * surprise
            + (1 - self.config.surprise_momentum) * self._past_surprise
        )
        self._past_surprise = effective_surprise

        # Decide whether to memorize
        should_memorize = force_memorize or (
            effective_surprise > self.config.memorization_threshold
        )

        ttt_steps = 0
        if should_memorize:
            # Perform TTT updates
            ttt_steps = self._perform_ttt(key, value)
            self._update_count += 1
            self._memory_age += 1

            logger.debug(
                f"Memory update: surprise={effective_surprise:.4f}, "
                f"ttt_steps={ttt_steps}"
            )

        latency_ms = (time.perf_counter() - start_time) * 1000
        memory_mb = self._get_memory_usage_mb()

        # Record metrics
        if self.config.enable_metrics:
            self._record_metric(
                MemoryMetrics(
                    operation="update",
                    latency_ms=latency_ms,
                    surprise_score=effective_surprise,
                    was_memorized=should_memorize,
                    ttt_steps=ttt_steps,
                    memory_usage_mb=memory_mb,
                )
            )

        # Phase 5: Audit logging
        if self.audit_logger:
            self.audit_logger.log_memory_update(
                actor=actor,
                surprise_score=effective_surprise,
                was_memorized=should_memorize,
                ttt_steps=ttt_steps,
                latency_ms=latency_ms,
                memory_size_mb=memory_mb,
                details={
                    "force_memorize": force_memorize,
                    "threshold": self.config.memorization_threshold,
                },
            )

        # Phase 5: Check memory pressure after update
        if self.consolidation_manager:
            self.consolidation_manager.record_update(memory_mb)

        return should_memorize, effective_surprise

    def compute_surprise(
        self,
        input_tensor: torch.Tensor,
        target_tensor: Optional[torch.Tensor] = None,
    ) -> float:
        """Compute surprise score for an input.

        Args:
            input_tensor: Input to evaluate
            target_tensor: Optional target; uses input as target if None

        Returns:
            Surprise score (higher = more surprising)
        """
        self._ensure_initialized()
        assert (
            self.backend is not None
        )  # Guaranteed by _ensure_initialized  # nosec B101
        assert self.model is not None  # nosec B101

        input_tensor = self.backend.to_device(input_tensor)
        if target_tensor is None:
            target_tensor = input_tensor
        else:
            target_tensor = self.backend.to_device(target_tensor)

        return self.backend.compute_surprise(self.model, input_tensor, target_tensor)

    def _perform_ttt(self, key: torch.Tensor, value: torch.Tensor) -> int:
        """Perform test-time training updates.

        Args:
            key: Key tensor
            value: Target value tensor

        Returns:
            Number of TTT steps performed

        Error Handling:
        - NaN/Inf detection in loss and gradients
        - Model state preserved on failure via state_dict backup
        - Graceful degradation returns 0 steps on critical failure
        """
        # Type narrowing - these are guaranteed by caller (update method)
        assert self.model is not None  # nosec B101
        assert self.optimizer is not None  # nosec B101

        # Backup model state for recovery on failure
        model_state_backup = {k: v.clone() for k, v in self.model.state_dict().items()}

        self.model.train()
        steps_completed = 0

        try:
            for step in range(self.config.max_ttt_steps):
                # Zero gradients
                self.optimizer.zero_grad()

                # Forward pass
                try:
                    prediction = self.model(key, use_persistent=False)
                except RuntimeError as e:
                    logger.error(f"Forward pass failed at step {step}: {e}")
                    break

                # Compute loss using MIRAS attentional bias
                try:
                    loss_fn = MIRASLossFunctions.get_loss_fn(
                        self.miras_config.attentional_bias,
                        self.miras_config,
                    )
                    loss = loss_fn(prediction, value)

                    # Add retention regularization
                    retention_loss = MIRASRetention.apply_retention(
                        self.model,
                        self.miras_config.retention_gate,
                        self.miras_config,
                        age=self._memory_age,
                        utilization=self._compute_utilization(),
                    )
                    total_loss = loss + retention_loss
                except Exception as e:
                    logger.error(f"Loss computation failed at step {step}: {e}")
                    break

                # Check for NaN/Inf in loss
                if torch.isnan(total_loss) or torch.isinf(total_loss):
                    logger.warning(
                        f"NaN/Inf detected in loss at step {step}, stopping TTT"
                    )
                    break

                # Backward pass with gradient safety
                try:
                    total_loss.backward()
                except RuntimeError as e:
                    logger.error(f"Backward pass failed at step {step}: {e}")
                    break

                # Check for NaN/Inf in gradients
                has_nan_grad = False
                for param in self.model.parameters():
                    if param.grad is not None:
                        if (
                            torch.isnan(param.grad).any()
                            or torch.isinf(param.grad).any()
                        ):
                            has_nan_grad = True
                            break

                if has_nan_grad:
                    logger.warning(
                        f"NaN/Inf detected in gradients at step {step}, stopping TTT"
                    )
                    # Restore model state
                    self.model.load_state_dict(model_state_backup)
                    break

                # Gradient clipping
                if self.miras_config.gradient_clip > 0:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(),
                        self.miras_config.gradient_clip,
                    )

                # Optimizer step
                try:
                    self.optimizer.step()
                    steps_completed = step + 1
                except RuntimeError as e:
                    logger.error(f"Optimizer step failed at step {step}: {e}")
                    self.model.load_state_dict(model_state_backup)
                    break

                # Check for convergence
                if loss.item() < 0.01:
                    break

        except Exception as e:
            logger.error(f"TTT failed with unexpected error: {e}")
            # Restore model state on any unexpected failure
            self.model.load_state_dict(model_state_backup)
            steps_completed = 0

        self.model.eval()
        return steps_completed

    def _compute_surprise(
        self,
        query: torch.Tensor,
        output: torch.Tensor,
    ) -> float:
        """Compute surprise from query-output pair.

        Uses reconstruction loss as a proxy for surprise.
        """
        with torch.no_grad():
            loss = F.huber_loss(output, query, delta=1.0)
            return loss.item()

    def _compute_utilization(self) -> float:
        """Compute memory utilization score.

        Based on ratio of retrievals to updates.
        """
        total = self._retrieval_count + self._update_count
        if total == 0:
            return 0.5
        return self._retrieval_count / total

    def _ensure_initialized(self) -> None:
        """Ensure service is initialized."""
        if not self._is_initialized:
            raise RuntimeError(
                "TitanMemoryService not initialized. Call initialize() first."
            )

    @property
    def _model(self) -> DeepMLPMemory:
        """Get initialized model with type narrowing."""
        if self.model is None:
            raise RuntimeError("Model not initialized")
        return self.model

    @property
    def _backend(self) -> MemoryBackend:
        """Get initialized backend with type narrowing."""
        if self.backend is None:
            raise RuntimeError("Backend not initialized")
        return self.backend

    @property
    def _optim(self) -> torch.optim.Optimizer:
        """Get initialized optimizer with type narrowing."""
        if self.optimizer is None:
            raise RuntimeError("Optimizer not initialized")
        return self.optimizer

    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        if self.backend is None:
            return 0.0
        usage = self.backend.get_memory_usage()
        return usage.get("allocated_mb", 0.0)

    def _record_metric(self, metric: MemoryMetrics) -> None:
        """Record a metric, keeping only recent entries."""
        self._metrics.append(metric)
        # Keep last 1000 metrics
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-1000:]

    # Phase 5: Callback methods for consolidation and size limits

    def _on_consolidation(self, result: ConsolidationResult) -> None:
        """Callback when consolidation occurs."""
        if self.audit_logger:
            self.audit_logger.log_consolidation(
                records_consolidated=0,  # Not tracking individual records
                memory_before_mb=result.memory_before_mb,
                memory_after_mb=result.memory_after_mb,
                latency_ms=result.duration_ms,
                details={
                    "strategy": result.strategy_used.value,
                    "weights_pruned": result.weights_pruned,
                    "slots_removed": result.slots_removed,
                    "layers_reset": result.layers_reset,
                    "success": result.success,
                },
            )

    def _on_pressure_change(self, pressure: MemoryPressureLevel) -> None:
        """Callback when memory pressure level changes."""
        # Compare by value to handle enum class instance differences
        # (can happen in test environments with module reloading)
        if pressure.value == MemoryPressureLevel.WARNING.value:
            if self.audit_logger:
                current_mb = self._get_memory_usage_mb()
                self.audit_logger.log_size_limit_warning(
                    current_size_mb=current_mb,
                    max_size_mb=self.config.max_memory_size_mb,
                    utilization_percent=(current_mb / self.config.max_memory_size_mb)
                    * 100,
                )

    def _on_limit_exceeded(self, current_mb: float, max_mb: float) -> None:
        """Callback when memory limit is exceeded."""
        logger.warning(f"Memory limit exceeded: {current_mb:.2f} / {max_mb:.2f} MB")

    def consolidate(
        self,
        strategy: Optional[ConsolidationStrategy] = None,
    ) -> Optional[ConsolidationResult]:
        """Manually trigger memory consolidation.

        Args:
            strategy: Optional consolidation strategy override

        Returns:
            ConsolidationResult if consolidation was performed
        """
        self._ensure_initialized()
        assert self.model is not None  # Guaranteed by _ensure_initialized  # nosec B101

        result = self.consolidation_manager.consolidate(
            model=self.model,
            strategy=strategy,
        )

        return result

    def get_memory_pressure(self) -> MemoryPressureLevel:
        """Get current memory pressure level."""
        current_mb = self._get_memory_usage_mb()
        return self.consolidation_manager.check_memory_pressure(current_mb)

    def get_metrics(self) -> List[MemoryMetrics]:
        """Get collected metrics."""
        return list(self._metrics)

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service stats
        """
        stats: Dict[str, Any] = {
            "is_initialized": self._is_initialized,
            "update_count": self._update_count,
            "retrieval_count": self._retrieval_count,
            "memory_age": self._memory_age,
            "past_surprise": self._past_surprise,
            "updates_rejected_count": self._updates_rejected_count,
        }

        if self._is_initialized and self.model is not None and self.backend is not None:
            stats.update(
                {
                    "model_parameters": self.model.get_parameter_count(),
                    "memory_size_mb": self.model.get_memory_size_mb(),
                    "backend_type": self.backend.config.backend_type.value,
                    "ttt_enabled": self.config.enable_ttt,
                    "miras_preset": self.config.miras_preset,
                }
            )

        if self._metrics:
            # Compute latency stats
            retrieve_latencies = [
                m.latency_ms for m in self._metrics if m.operation == "retrieve"
            ]
            update_latencies = [
                m.latency_ms for m in self._metrics if m.operation == "update"
            ]

            if retrieve_latencies:
                stats["avg_retrieve_latency_ms"] = sum(retrieve_latencies) / len(
                    retrieve_latencies
                )
            if update_latencies:
                stats["avg_update_latency_ms"] = sum(update_latencies) / len(
                    update_latencies
                )

        # Phase 5: Add consolidation and audit stats
        if self.consolidation_manager:
            stats["consolidation"] = self.consolidation_manager.get_stats()

        if self.size_limiter:
            stats["size_limiter"] = self.size_limiter.get_stats()

        if self.audit_logger:
            stats["audit_logging"] = self.audit_logger.get_stats()

        return stats

    def freeze_persistent_memory(self) -> None:
        """Freeze persistent memory for inference-only mode."""
        self._ensure_initialized()
        assert self.model is not None  # Guaranteed by _ensure_initialized  # nosec B101
        self.model.freeze_persistent_memory()
        logger.info("Persistent memory frozen")

    def unfreeze_persistent_memory(self) -> None:
        """Unfreeze persistent memory for training."""
        self._ensure_initialized()
        assert self.model is not None  # Guaranteed by _ensure_initialized  # nosec B101
        self.model.unfreeze_persistent_memory()
        logger.info("Persistent memory unfrozen")

    def reset_surprise_momentum(self) -> None:
        """Reset surprise momentum accumulator."""
        self._past_surprise = 0.0

    def save_checkpoint(self, path: str) -> None:
        """Save model checkpoint.

        Args:
            path: Path to save checkpoint
        """
        self._ensure_initialized()
        assert self.model is not None  # Guaranteed by _ensure_initialized  # nosec B101

        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": (
                self.optimizer.state_dict() if self.optimizer else None
            ),
            "config": {
                "memory_dim": self.config.memory_dim,
                "memory_depth": self.config.memory_depth,
                "hidden_multiplier": self.config.hidden_multiplier,
                "persistent_memory_size": self.config.persistent_memory_size,
            },
            "miras_config": self.miras_config.to_dict(),
            "stats": {
                "update_count": self._update_count,
                "retrieval_count": self._retrieval_count,
                "memory_age": self._memory_age,
            },
        }

        torch.save(checkpoint, path)
        logger.info(f"Checkpoint saved to {path}")

        # Phase 5: Audit log checkpoint save
        if self.audit_logger:
            self.audit_logger.log_checkpoint_save(
                path=path,
                memory_size_mb=self.model.get_memory_size_mb(),
                details={
                    "update_count": self._update_count,
                    "retrieval_count": self._retrieval_count,
                },
            )

    def load_checkpoint(self, path: str) -> None:
        """Load model checkpoint.

        Args:
            path: Path to load checkpoint from
        """
        self._ensure_initialized()
        assert (
            self.backend is not None
        )  # Guaranteed by _ensure_initialized  # nosec B101
        assert self.model is not None  # nosec B101

        checkpoint = torch.load(
            path, map_location=self.backend.device
        )  # nosec B614 - internal model checkpoint

        self.model.load_state_dict(checkpoint["model_state_dict"])

        if self.optimizer and checkpoint.get("optimizer_state_dict"):
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

        if "stats" in checkpoint:
            self._update_count = checkpoint["stats"].get("update_count", 0)
            self._retrieval_count = checkpoint["stats"].get("retrieval_count", 0)
            self._memory_age = checkpoint["stats"].get("memory_age", 0.0)

        logger.info(f"Checkpoint loaded from {path}")

        # Phase 5: Audit log checkpoint load
        if self.audit_logger:
            self.audit_logger.log_checkpoint_load(
                path=path,
                memory_size_mb=self.model.get_memory_size_mb(),
                details={
                    "update_count": self._update_count,
                    "retrieval_count": self._retrieval_count,
                },
            )

    def __enter__(self) -> "TitanMemoryService":
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.shutdown()


def create_titan_memory_service(
    preset: str = "enterprise_standard",
    enable_ttt: bool = True,
    memory_dim: int = 512,
    memory_depth: int = 3,
) -> TitanMemoryService:
    """Factory function to create a TitanMemoryService.

    Args:
        preset: MIRAS preset name
        enable_ttt: Enable test-time training
        memory_dim: Memory dimension
        memory_depth: Number of MLP layers

    Returns:
        Configured TitanMemoryService (call initialize() to start)
    """
    config = TitanMemoryServiceConfig(
        memory_dim=memory_dim,
        memory_depth=memory_depth,
        miras_preset=preset,
        enable_ttt=enable_ttt,
    )
    return TitanMemoryService(config)
