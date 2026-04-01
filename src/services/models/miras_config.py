"""MIRAS Configuration Module.

Implements the Memory-Integrated Recurrent Architecture with Surprise (MIRAS)
framework from arXiv:2504.13173. This module provides configurable:
1. Attentional Bias (loss functions for memory updates)
2. Retention Gate (regularization for memory consolidation)
3. Memory Algorithm (update strategies)

Key insight: Memory can be viewed as optimization where:
- Loss function determines what information is preserved
- Regularization controls retention vs. forgetting
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

import torch
import torch.nn.functional as F


class AttentionalBias(Enum):
    """Loss functions for memory updates (what to remember).

    From MIRAS paper: Different loss functions create different
    memory behaviors:
    - L2: Strong focus on average case, sensitive to outliers
    - L1: Robust to outliers, creates sparse updates
    - HUBER: Best of both worlds, outlier robust but smooth
    - COSINE: Preserves directional information, ignores magnitude
    """

    L2 = "l2"
    L1 = "l1"
    HUBER = "huber"
    COSINE = "cosine"


class RetentionGate(Enum):
    """Regularization strategies for memory retention.

    Controls how quickly old memories fade:
    - WEIGHT_DECAY: Standard L2 regularization, gradual fade
    - EXPONENTIAL: Time-based exponential decay
    - ADAPTIVE: Adjusts based on memory utilization
    - NONE: No regularization (memories persist indefinitely)
    """

    WEIGHT_DECAY = "weight_decay"
    EXPONENTIAL = "exponential"
    ADAPTIVE = "adaptive"
    NONE = "none"


class MemoryAlgorithm(Enum):
    """Memory update algorithms.

    - SGD: Standard gradient descent
    - MOMENTUM: SGD with momentum for smoother updates
    - ADAM: Adaptive learning rates per parameter
    - ADALR: Adaptive learning rate based on surprise
    """

    SGD = "sgd"
    MOMENTUM = "momentum"
    ADAM = "adam"
    ADALR = "adalr"


@dataclass
class MIRASConfig:
    """Configuration for MIRAS memory system.

    This configuration controls how the neural memory learns and retains
    information. Settings can be tuned per-organization for different
    use cases (security-focused, research, enterprise).

    Attributes:
        attentional_bias: Loss function for memory updates
        retention_gate: Regularization strategy for retention
        memory_algorithm: Optimization algorithm for updates
        huber_delta: Delta parameter for Huber loss (robustness threshold)
        retention_strength: Strength of retention regularization
        momentum: Momentum coefficient (for MOMENTUM algorithm)
        adam_betas: Beta coefficients for ADAM optimizer
        adam_eps: Epsilon for numerical stability in ADAM
        adaptive_threshold: Threshold for adaptive retention
        max_memory_norm: Maximum L2 norm for memory weights
        gradient_clip: Maximum gradient norm (0 = no clipping)
    """

    # Core settings
    attentional_bias: AttentionalBias = AttentionalBias.HUBER
    retention_gate: RetentionGate = RetentionGate.ADAPTIVE
    memory_algorithm: MemoryAlgorithm = MemoryAlgorithm.ADAM

    # Loss function parameters
    huber_delta: float = 1.0

    # Retention parameters
    retention_strength: float = 0.01
    adaptive_threshold: float = 0.5

    # Optimizer parameters
    momentum: float = 0.9
    adam_betas: tuple = (0.9, 0.999)
    adam_eps: float = 1e-8

    # Safety limits
    max_memory_norm: float = 100.0
    gradient_clip: float = 1.0

    # Extra configuration for extensibility
    extra_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "attentional_bias": self.attentional_bias.value,
            "retention_gate": self.retention_gate.value,
            "memory_algorithm": self.memory_algorithm.value,
            "huber_delta": self.huber_delta,
            "retention_strength": self.retention_strength,
            "adaptive_threshold": self.adaptive_threshold,
            "momentum": self.momentum,
            "adam_betas": self.adam_betas,
            "adam_eps": self.adam_eps,
            "max_memory_norm": self.max_memory_norm,
            "gradient_clip": self.gradient_clip,
            "extra_config": self.extra_config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MIRASConfig":
        """Create config from dictionary."""
        if "attentional_bias" in data and isinstance(data["attentional_bias"], str):
            data["attentional_bias"] = AttentionalBias(data["attentional_bias"])
        if "retention_gate" in data and isinstance(data["retention_gate"], str):
            data["retention_gate"] = RetentionGate(data["retention_gate"])
        if "memory_algorithm" in data and isinstance(data["memory_algorithm"], str):
            data["memory_algorithm"] = MemoryAlgorithm(data["memory_algorithm"])
        return cls(**data)


class MIRASLossFunctions:
    """Loss function implementations for MIRAS attentional bias."""

    @staticmethod
    def l2_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """L2 (Mean Squared Error) loss.

        Properties:
        - Penalizes large errors quadratically
        - Sensitive to outliers
        - Smooth gradients everywhere
        """
        return F.mse_loss(prediction, target)

    @staticmethod
    def l1_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """L1 (Mean Absolute Error) loss.

        Properties:
        - Linear penalty for all error magnitudes
        - Robust to outliers
        - Non-smooth at zero (sparse gradients)
        """
        return F.l1_loss(prediction, target)

    @staticmethod
    def huber_loss(
        prediction: torch.Tensor,
        target: torch.Tensor,
        delta: float = 1.0,
    ) -> torch.Tensor:
        """Huber loss (smooth L1).

        Properties:
        - Quadratic for small errors (< delta)
        - Linear for large errors (>= delta)
        - Best of L1 and L2: smooth + outlier robust
        """
        return F.huber_loss(prediction, target, delta=delta)

    @staticmethod
    def cosine_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """Cosine distance loss.

        Properties:
        - Measures angular difference, ignores magnitude
        - Range [0, 2] where 0 = identical direction
        - Useful for embedding spaces
        """
        # Cosine similarity in [-1, 1], convert to loss [0, 2]
        similarity = F.cosine_similarity(prediction, target, dim=-1)
        result: torch.Tensor = (1.0 - similarity).mean()
        return result

    @classmethod
    def get_loss_fn(
        cls,
        bias: AttentionalBias,
        config: Optional[MIRASConfig] = None,
    ) -> Callable[[torch.Tensor, torch.Tensor], torch.Tensor]:
        """Get the loss function for a given attentional bias.

        Args:
            bias: The attentional bias type
            config: Optional MIRAS config for parameters

        Returns:
            Loss function callable
        """
        if bias == AttentionalBias.L2:
            return cls.l2_loss
        elif bias == AttentionalBias.L1:
            return cls.l1_loss
        elif bias == AttentionalBias.HUBER:
            delta = config.huber_delta if config else 1.0
            return lambda p, t: cls.huber_loss(p, t, delta=delta)
        elif bias == AttentionalBias.COSINE:
            return cls.cosine_loss
        else:
            raise ValueError(f"Unknown attentional bias: {bias}")


class MIRASRetention:
    """Retention gate implementations for memory consolidation."""

    @staticmethod
    def weight_decay(
        model: torch.nn.Module,
        strength: float = 0.01,
    ) -> torch.Tensor:
        """Standard L2 weight decay regularization.

        Args:
            model: The memory model
            strength: Decay strength (higher = faster forgetting)

        Returns:
            Regularization loss term
        """
        reg_loss = torch.tensor(0.0)
        for param in model.parameters():
            if param.requires_grad:
                reg_loss = reg_loss + torch.sum(param**2)
        return strength * reg_loss

    @staticmethod
    def exponential_decay(
        model: torch.nn.Module,
        age: float,
        base_strength: float = 0.01,
        half_life: float = 100.0,
    ) -> torch.Tensor:
        """Time-based exponential decay.

        Memory fades exponentially based on time since creation.

        Args:
            model: The memory model
            age: Age of memory in arbitrary units (e.g., steps)
            base_strength: Base decay strength
            half_life: Steps until memory decays to half strength

        Returns:
            Regularization loss term
        """
        import math

        decay_factor = math.exp(-0.693 * age / half_life)  # 0.693 = ln(2)
        adjusted_strength = base_strength * (1.0 - decay_factor)

        reg_loss = torch.tensor(0.0)
        for param in model.parameters():
            if param.requires_grad:
                reg_loss = reg_loss + torch.sum(param**2)
        return adjusted_strength * reg_loss

    @staticmethod
    def adaptive_decay(
        model: torch.nn.Module,
        utilization: float,
        base_strength: float = 0.01,
        threshold: float = 0.5,
    ) -> torch.Tensor:
        """Adaptive decay based on memory utilization.

        High utilization = slow decay (important memories)
        Low utilization = fast decay (unused memories)

        Args:
            model: The memory model
            utilization: Memory utilization score [0, 1]
            base_strength: Base decay strength
            threshold: Threshold below which decay accelerates

        Returns:
            Regularization loss term
        """
        # Decay faster for underutilized memories
        if utilization < threshold:
            # Increase decay for unused memories
            multiplier = 2.0 * (threshold - utilization) / threshold
        else:
            # Reduce decay for frequently used memories
            multiplier = 0.5 * (1.0 - (utilization - threshold) / (1.0 - threshold))

        adjusted_strength = base_strength * (1.0 + multiplier)

        reg_loss = torch.tensor(0.0)
        for param in model.parameters():
            if param.requires_grad:
                reg_loss = reg_loss + torch.sum(param**2)
        return adjusted_strength * reg_loss

    @classmethod
    def apply_retention(
        cls,
        model: torch.nn.Module,
        gate: RetentionGate,
        config: MIRASConfig,
        **kwargs: Any,
    ) -> torch.Tensor:
        """Apply retention regularization.

        Args:
            model: The memory model
            gate: Retention gate type
            config: MIRAS configuration
            **kwargs: Additional arguments (age, utilization, etc.)

        Returns:
            Regularization loss term
        """
        if gate == RetentionGate.NONE:
            return torch.tensor(0.0)
        elif gate == RetentionGate.WEIGHT_DECAY:
            return cls.weight_decay(model, config.retention_strength)
        elif gate == RetentionGate.EXPONENTIAL:
            age = kwargs.get("age", 0.0)
            return cls.exponential_decay(
                model,
                age,
                config.retention_strength,
            )
        elif gate == RetentionGate.ADAPTIVE:
            utilization = kwargs.get("utilization", 0.5)
            return cls.adaptive_decay(
                model,
                utilization,
                config.retention_strength,
                config.adaptive_threshold,
            )
        else:
            raise ValueError(f"Unknown retention gate: {gate}")


class MIRASOptimizer:
    """Optimizer factory for MIRAS memory algorithms."""

    @staticmethod
    def create_optimizer(
        model: torch.nn.Module,
        config: MIRASConfig,
        learning_rate: float = 0.001,
    ) -> torch.optim.Optimizer:
        """Create optimizer based on MIRAS config.

        Args:
            model: The memory model
            config: MIRAS configuration
            learning_rate: Base learning rate

        Returns:
            Configured optimizer
        """
        params = [p for p in model.parameters() if p.requires_grad]

        if config.memory_algorithm == MemoryAlgorithm.SGD:
            return torch.optim.SGD(params, lr=learning_rate)
        elif config.memory_algorithm == MemoryAlgorithm.MOMENTUM:
            return torch.optim.SGD(
                params,
                lr=learning_rate,
                momentum=config.momentum,
            )
        elif config.memory_algorithm == MemoryAlgorithm.ADAM:
            return torch.optim.Adam(
                params,
                lr=learning_rate,
                betas=config.adam_betas,
                eps=config.adam_eps,
            )
        elif config.memory_algorithm == MemoryAlgorithm.ADALR:
            # Adaptive learning rate - use Adam with higher eps for stability
            return torch.optim.Adam(
                params,
                lr=learning_rate,
                betas=(0.9, 0.99),
                eps=1e-4,
            )
        else:
            raise ValueError(f"Unknown memory algorithm: {config.memory_algorithm}")


# Preset configurations for different use cases
MIRAS_PRESETS: Dict[str, MIRASConfig] = {
    # Security-focused: Minimal learning, high retention
    "defense_contractor": MIRASConfig(
        attentional_bias=AttentionalBias.HUBER,
        retention_gate=RetentionGate.NONE,  # Don't forget security patterns
        memory_algorithm=MemoryAlgorithm.SGD,
        retention_strength=0.0,
        gradient_clip=0.5,  # Smaller updates
    ),
    # Standard enterprise: Balanced learning and retention
    "enterprise_standard": MIRASConfig(
        attentional_bias=AttentionalBias.HUBER,
        retention_gate=RetentionGate.ADAPTIVE,
        memory_algorithm=MemoryAlgorithm.ADAM,
        retention_strength=0.01,
        gradient_clip=1.0,
    ),
    # Research lab: Aggressive learning, fast adaptation
    "research_lab": MIRASConfig(
        attentional_bias=AttentionalBias.L2,
        retention_gate=RetentionGate.EXPONENTIAL,
        memory_algorithm=MemoryAlgorithm.ADAM,
        retention_strength=0.05,
        gradient_clip=2.0,  # Allow larger updates
    ),
    # Development/testing: Simple and fast
    "development": MIRASConfig(
        attentional_bias=AttentionalBias.L2,
        retention_gate=RetentionGate.WEIGHT_DECAY,
        memory_algorithm=MemoryAlgorithm.SGD,
        retention_strength=0.01,
        gradient_clip=1.0,
    ),
}


def get_miras_preset(name: str) -> MIRASConfig:
    """Get a predefined MIRAS configuration.

    Args:
        name: Preset name (defense_contractor, enterprise_standard,
              research_lab, development)

    Returns:
        MIRASConfig for the preset

    Raises:
        ValueError: If preset name is not recognized
    """
    if name not in MIRAS_PRESETS:
        available = ", ".join(MIRAS_PRESETS.keys())
        raise ValueError(f"Unknown preset '{name}'. Available: {available}")
    return MIRAS_PRESETS[name]
