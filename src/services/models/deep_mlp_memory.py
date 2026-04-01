"""
DeepMLPMemory: Neural memory module inspired by Google's Titans architecture.

This module implements a deep MLP-based memory that can:
1. Store and retrieve information via learned representations
2. Support test-time training (TTT) for adaptive learning
3. Use surprise-driven consolidation for selective memorization

Reference: Titans - Learning to Memorize at Test Time (arXiv:2501.00663)
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class MemoryConfig:
    """Configuration for DeepMLPMemory module."""

    dim: int = 512
    depth: int = 3
    hidden_multiplier: int = 4
    dropout: float = 0.1
    use_layer_norm: bool = True
    use_residual: bool = True
    persistent_memory_size: int = 64  # Number of persistent memory slots


class PersistentMemory(nn.Module):
    """
    Persistent Memory: Fixed learnable weights that store task-specific knowledge.

    Unlike contextual memory which updates during inference, persistent memory
    is learned during training and remains fixed at inference time.

    Analogy: Long-term procedural knowledge (how to ride a bike)
    """

    def __init__(self, num_slots: int, dim: int) -> None:
        super().__init__()
        self.num_slots = num_slots
        self.dim = dim

        # Learnable memory slots
        self.memory = nn.Parameter(torch.randn(num_slots, dim) * 0.02)

        # Attention projection for querying persistent memory
        self.query_proj = nn.Linear(dim, dim)
        self.key_proj = nn.Linear(dim, dim)
        self.value_proj = nn.Linear(dim, dim)

    def forward(self, query: torch.Tensor) -> torch.Tensor:
        """
        Retrieve from persistent memory using attention.

        Args:
            query: Input query tensor [batch_size, dim]

        Returns:
            Retrieved memory content [batch_size, dim]
        """
        _batch_size = query.shape[0]  # noqa: F841

        # Project query
        q = self.query_proj(query)  # [batch_size, dim]

        # Keys and values from persistent memory
        k = self.key_proj(self.memory)  # [num_slots, dim]
        v = self.value_proj(self.memory)  # [num_slots, dim]

        # Compute attention scores
        # q: [batch_size, dim], k: [num_slots, dim]
        attn_scores = torch.matmul(q, k.t()) / math.sqrt(
            self.dim
        )  # [batch_size, num_slots]
        attn_weights = F.softmax(attn_scores, dim=-1)

        # Retrieve weighted combination
        output = torch.matmul(attn_weights, v)  # [batch_size, dim]

        return output


class MLPBlock(nn.Module):
    """Single MLP block with optional residual connection and layer norm."""

    def __init__(
        self,
        dim: int,
        hidden_dim: int,
        dropout: float = 0.1,
        use_layer_norm: bool = True,
        use_residual: bool = True,
    ):
        super().__init__()
        self.use_residual = use_residual

        self.fc1 = nn.Linear(dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, dim)
        self.dropout = nn.Dropout(dropout)

        self.layer_norm = nn.LayerNorm(dim) if use_layer_norm else nn.Identity()
        self.activation = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass through MLP block."""
        residual = x

        x = self.layer_norm(x)
        x = self.fc1(x)
        x = self.activation(x)
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.dropout(x)

        if self.use_residual:
            x = x + residual

        return x


class DeepMLPMemory(nn.Module):
    """
    Deep MLP Memory Module inspired by Titans architecture.

    This module uses a stack of MLP blocks as the memory representation,
    providing significantly higher expressiveness than vector or matrix-based
    memory used in traditional linear RNNs.

    Key features:
    1. Deep MLP storage (3+ layers) for rich representations
    2. Persistent memory for fixed task knowledge
    3. Support for test-time training via gradient-based updates
    4. Configurable depth and width for capacity tuning

    Architecture:
        Input → [MLP Block 1] → [MLP Block 2] → ... → [MLP Block N] → Output
                     ↓               ↓                    ↓
                  Residual       Residual              Residual
    """

    def __init__(self, config: Optional[MemoryConfig] = None, **kwargs) -> None:
        """
        Initialize DeepMLPMemory.

        Args:
            config: MemoryConfig object with all settings
            **kwargs: Alternative way to pass config parameters
        """
        super().__init__()

        # Handle config
        if config is None:
            config = MemoryConfig(**kwargs)
        self.config = config

        # Build MLP layers
        hidden_dim = config.dim * config.hidden_multiplier
        self.layers = nn.ModuleList(
            [
                MLPBlock(
                    dim=config.dim,
                    hidden_dim=hidden_dim,
                    dropout=config.dropout,
                    use_layer_norm=config.use_layer_norm,
                    use_residual=config.use_residual,
                )
                for _ in range(config.depth)
            ]
        )

        # Input/output projections
        self.input_proj = nn.Linear(config.dim, config.dim)
        self.output_proj = nn.Linear(config.dim, config.dim)

        # Persistent memory (fixed learned weights)
        self.persistent_memory = PersistentMemory(
            num_slots=config.persistent_memory_size,
            dim=config.dim,
        )

        # Layer norm for combining persistent and contextual memory
        self.output_norm = nn.LayerNorm(config.dim)

        # Initialize weights
        self._init_weights()

    def _init_weights(self) -> None:
        """Initialize weights using Xavier/Glorot initialization."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(
        self,
        x: torch.Tensor,
        use_persistent: bool = True,
    ) -> torch.Tensor:
        """
        Forward pass: retrieve from memory.

        Args:
            x: Input query tensor [batch_size, dim]
            use_persistent: Whether to combine with persistent memory

        Returns:
            Memory output [batch_size, dim]
        """
        # Project input
        h = self.input_proj(x)

        # Pass through MLP layers (contextual memory)
        for layer in self.layers:
            h = layer(h)

        # Combine with persistent memory
        if use_persistent:
            persistent_output = self.persistent_memory(x)
            h = h + persistent_output

        # Final projection and normalization
        output = self.output_proj(h)
        output = self.output_norm(output)

        result: torch.Tensor = output
        return result

    def retrieve(self, query: torch.Tensor) -> torch.Tensor:
        """
        Retrieve from memory given a query.

        Alias for forward() with more semantic naming.

        Args:
            query: Query tensor [batch_size, dim]

        Returns:
            Retrieved memory content [batch_size, dim]
        """
        return self.forward(query, use_persistent=True)

    def compute_reconstruction_loss(
        self,
        key: torch.Tensor,
        value: torch.Tensor,
        loss_type: str = "huber",
    ) -> torch.Tensor:
        """
        Compute reconstruction loss for TTT updates.

        Args:
            key: Input key tensor [batch_size, dim]
            value: Target value tensor [batch_size, dim]
            loss_type: Loss function type ('l2', 'l1', 'huber', 'cosine')

        Returns:
            Scalar loss tensor
        """
        prediction = self.forward(key, use_persistent=False)

        if loss_type == "l2":
            loss = F.mse_loss(prediction, value)
        elif loss_type == "l1":
            loss = F.l1_loss(prediction, value)
        elif loss_type == "huber":
            loss = F.huber_loss(prediction, value, delta=1.0)
        elif loss_type == "cosine":
            # Cosine distance: 1 - cosine_similarity
            loss = 1.0 - F.cosine_similarity(prediction, value, dim=-1).mean()
        else:
            raise ValueError(f"Unknown loss type: {loss_type}")

        return loss

    def get_parameter_count(self) -> int:
        """Return total number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def get_memory_size_mb(self) -> float:
        """Return approximate memory size in MB."""
        param_count = self.get_parameter_count()
        # FP32: 4 bytes per parameter
        return (param_count * 4) / (1024 * 1024)

    def freeze_persistent_memory(self) -> None:
        """Freeze persistent memory for inference (no TTT on persistent)."""
        for param in self.persistent_memory.parameters():
            param.requires_grad = False

    def unfreeze_persistent_memory(self) -> None:
        """Unfreeze persistent memory for training."""
        for param in self.persistent_memory.parameters():
            param.requires_grad = True


class SurpriseCalculator:
    """
    Calculates surprise score based on gradient magnitude.

    Surprise metric from Titans: High gradients indicate unexpected,
    memorable data that should trigger memory consolidation.

    surprise(x) = ||∇_θ L(f_θ(x), x)||

    Low surprise: Input aligns with model expectations → skip storage
    High surprise: Input breaks patterns → consolidate to memory
    """

    def __init__(
        self,
        model: DeepMLPMemory,
        momentum: float = 0.9,
        threshold: float = 0.7,
    ):
        """
        Initialize SurpriseCalculator.

        Args:
            model: DeepMLPMemory model to compute gradients on
            momentum: Momentum for temporal smoothing of surprise
            threshold: Threshold for memorization decision
        """
        self.model = model
        self.momentum = momentum
        self.threshold = threshold
        self.past_surprise = 0.0

    def compute_surprise(
        self,
        input_tensor: torch.Tensor,
        target_tensor: Optional[torch.Tensor] = None,
    ) -> float:
        """
        Compute gradient-based surprise score.

        Args:
            input_tensor: Input to evaluate surprise on
            target_tensor: Optional target; if None, uses input as target

        Returns:
            Surprise score (higher = more surprising)
        """
        if target_tensor is None:
            target_tensor = input_tensor

        # Ensure gradients are enabled
        was_training = self.model.training
        self.model.train()

        # Zero existing gradients
        self.model.zero_grad()

        # Forward pass
        input_tensor = input_tensor.detach().requires_grad_(True)
        output = self.model(input_tensor, use_persistent=False)

        # Compute loss (reconstruction)
        loss = F.huber_loss(output, target_tensor.detach())

        # Backward pass to get gradients
        loss.backward()

        # Compute gradient magnitude
        grad_norm = 0.0
        for param in self.model.parameters():
            if param.grad is not None:
                grad_norm += param.grad.norm().item() ** 2
        grad_norm = math.sqrt(grad_norm)

        # Normalize by parameter count for comparability
        param_count = self.model.get_parameter_count()
        normalized_surprise = grad_norm / math.sqrt(param_count)

        # Apply momentum for temporal smoothing
        effective_surprise = (
            self.momentum * normalized_surprise
            + (1 - self.momentum) * self.past_surprise
        )
        self.past_surprise = effective_surprise

        # Restore training mode
        if not was_training:
            self.model.eval()

        # Clear gradients
        self.model.zero_grad()

        return effective_surprise

    def should_memorize(
        self,
        input_tensor: torch.Tensor,
        target_tensor: Optional[torch.Tensor] = None,
    ) -> Tuple[bool, float]:
        """
        Determine if input should be memorized based on surprise.

        Args:
            input_tensor: Input to evaluate
            target_tensor: Optional target

        Returns:
            Tuple of (should_memorize, surprise_score)
        """
        surprise = self.compute_surprise(input_tensor, target_tensor)
        return surprise > self.threshold, surprise

    def reset_momentum(self) -> None:
        """Reset momentum accumulator."""
        self.past_surprise = 0.0


def create_memory_model(
    dim: int = 512,
    depth: int = 3,
    hidden_multiplier: int = 4,
    persistent_slots: int = 64,
) -> DeepMLPMemory:
    """
    Factory function to create a DeepMLPMemory model.

    Args:
        dim: Model dimension
        depth: Number of MLP layers
        hidden_multiplier: Hidden layer size multiplier
        persistent_slots: Number of persistent memory slots

    Returns:
        Configured DeepMLPMemory instance
    """
    config = MemoryConfig(
        dim=dim,
        depth=depth,
        hidden_multiplier=hidden_multiplier,
        persistent_memory_size=persistent_slots,
    )
    return DeepMLPMemory(config)
