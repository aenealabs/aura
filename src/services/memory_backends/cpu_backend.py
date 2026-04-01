"""CPU backend implementation for development and testing.

This backend runs on CPU without any special hardware requirements,
making it ideal for local development and CI/CD testing.
"""

import math
from typing import Any, Dict, Optional

import torch
import torch.nn.functional as F

from .base import BackendConfig, BackendType, MemoryBackend


class CPUMemoryBackend(MemoryBackend):
    """CPU-based memory backend for development.

    This backend provides a baseline implementation that works on any
    system without special hardware. It's optimized for correctness
    over performance, making it ideal for:
    - Local development on laptops
    - CI/CD pipeline testing
    - Debugging and profiling
    - Small-scale deployments

    Performance characteristics:
    - Latency: ~10-50ms per forward pass (batch_size=32, dim=512)
    - Throughput: ~1000-5000 requests/second
    - Memory: Efficient, no GPU memory management overhead
    """

    def __init__(self, config: Optional[BackendConfig] = None) -> None:
        """Initialize CPU backend.

        Args:
            config: Backend configuration. Defaults to CPU settings.
        """
        if config is None:
            config = BackendConfig(backend_type=BackendType.CPU)
        elif config.backend_type != BackendType.CPU:
            raise ValueError(
                f"CPUMemoryBackend requires CPU backend type, got {config.backend_type}"
            )

        super().__init__(config)
        self._peak_memory = 0.0

    def _get_device(self) -> torch.device:
        """Get CPU device.

        Returns:
            torch.device("cpu")
        """
        return torch.device("cpu")

    def initialize(self) -> None:
        """Initialize CPU backend.

        CPU backend requires no special initialization.
        """
        self._device = self._get_device()
        self._is_initialized = True
        self._peak_memory = 0.0

    def cleanup(self) -> None:
        """Clean up CPU backend resources.

        Triggers garbage collection to free memory.
        """
        import gc

        gc.collect()
        self._is_initialized = False
        self._peak_memory = 0.0

    def to_device(self, tensor: torch.Tensor) -> torch.Tensor:
        """Move tensor to CPU (no-op if already on CPU).

        Args:
            tensor: Input tensor

        Returns:
            Tensor on CPU
        """
        if tensor.device.type == "cpu":
            return tensor
        return tensor.cpu()

    def from_device(self, tensor: torch.Tensor) -> torch.Tensor:
        """Move tensor from CPU (no-op).

        Args:
            tensor: Input tensor on CPU

        Returns:
            Same tensor (already on CPU)
        """
        return tensor

    def forward(
        self,
        model: torch.nn.Module,
        inputs: torch.Tensor,
        **kwargs: Any,
    ) -> torch.Tensor:
        """Execute forward pass on CPU.

        Args:
            model: The neural network module
            inputs: Input tensor
            **kwargs: Additional arguments for the model

        Returns:
            Model output tensor
        """
        # Ensure model is on CPU
        if next(model.parameters()).device.type != "cpu":
            model = model.cpu()

        # Ensure inputs are on CPU
        inputs = self.to_device(inputs)

        # Forward pass
        with torch.set_grad_enabled(self.config.enable_ttt):
            output = model(inputs, **kwargs)

        # Track memory usage
        self._update_memory_stats()

        # Cast to Tensor to satisfy mypy
        return torch.as_tensor(output)

    def backward(
        self,
        loss: torch.Tensor,
        model: torch.nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None,
    ) -> Dict[str, float]:
        """Execute backward pass for TTT on CPU.

        Args:
            loss: Scalar loss tensor
            model: The neural network module
            optimizer: Optional optimizer for parameter updates

        Returns:
            Dictionary with gradient statistics
        """
        if not self.config.enable_ttt:
            return {"error": "TTT is disabled."}

        # Zero gradients
        model.zero_grad()

        # Backward pass
        loss.backward()

        # Compute gradient statistics
        grad_stats = self._compute_gradient_stats(model)

        # Apply optimizer step if provided
        if optimizer is not None:
            optimizer.step()

        return grad_stats

    def compute_surprise(
        self,
        model: torch.nn.Module,
        inputs: torch.Tensor,
        targets: torch.Tensor,
    ) -> float:
        """Compute surprise score based on gradient magnitude.

        Surprise is measured as the L2 norm of gradients, normalized
        by the number of parameters. High surprise indicates the input
        is unexpected and should be memorized.

        Args:
            model: The neural network module
            inputs: Input tensor
            targets: Target tensor for reconstruction

        Returns:
            Surprise score (gradient magnitude normalized)
        """
        # Ensure model is in training mode for gradient computation
        was_training = model.training
        model.train()

        # Zero existing gradients
        model.zero_grad()

        # Forward pass
        inputs = self.to_device(inputs)
        targets = self.to_device(targets)

        # Detach inputs and enable gradients
        inputs = inputs.detach().requires_grad_(True)

        # Compute output
        output = model(inputs, use_persistent=False)

        # Compute reconstruction loss (Huber for robustness)
        loss = F.huber_loss(output, targets.detach(), delta=1.0)

        # Backward pass
        loss.backward()

        # Compute gradient L2 norm
        grad_norm_sq = 0.0
        param_count = 0
        for param in model.parameters():
            if param.grad is not None:
                grad_norm_sq += param.grad.norm().item() ** 2
                param_count += param.numel()

        grad_norm = math.sqrt(grad_norm_sq)

        # Normalize by parameter count for comparability
        if param_count > 0:
            normalized_surprise = grad_norm / math.sqrt(param_count)
        else:
            normalized_surprise = 0.0

        # Restore training mode
        if not was_training:
            model.eval()

        # Clear gradients
        model.zero_grad()

        return normalized_surprise

    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics.

        For CPU, this uses process memory information.

        Returns:
            Dictionary with memory stats in MB
        """
        import os

        try:
            import psutil

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            allocated = memory_info.rss / (1024 * 1024)  # Convert to MB
            return {
                "allocated_mb": allocated,
                "reserved_mb": allocated,  # CPU doesn't have reserved concept
                "peak_mb": max(self._peak_memory, allocated),
            }
        except ImportError:
            # Fallback if psutil not available
            return {
                "allocated_mb": 0.0,
                "reserved_mb": 0.0,
                "peak_mb": 0.0,
            }

    def synchronize(self) -> None:
        """Synchronize CPU operations (no-op for CPU)."""
        pass  # CPU operations are synchronous

    def _compute_gradient_stats(self, model: torch.nn.Module) -> Dict[str, float]:
        """Compute statistics about gradients.

        Args:
            model: Model with computed gradients

        Returns:
            Dictionary with gradient statistics
        """
        grad_norms = []
        param_counts = []

        for _name, param in model.named_parameters():
            if param.grad is not None:
                grad_norms.append(param.grad.norm().item())
                param_counts.append(param.numel())

        if not grad_norms:
            return {"grad_norm": 0.0, "grad_mean": 0.0, "grad_max": 0.0}

        total_norm = math.sqrt(sum(g**2 for g in grad_norms))
        mean_norm = sum(grad_norms) / len(grad_norms)
        max_norm = max(grad_norms)

        return {
            "grad_norm": total_norm,
            "grad_mean": mean_norm,
            "grad_max": max_norm,
            "num_params_with_grad": len(grad_norms),
        }

    def _update_memory_stats(self) -> None:
        """Update peak memory tracking."""
        current = self.get_memory_usage()
        if current["allocated_mb"] > self._peak_memory:
            self._peak_memory = current["allocated_mb"]

    def get_backend_info(self) -> Dict[str, Any]:
        """Get CPU backend information.

        Returns:
            Dictionary with backend information
        """
        info = super().get_backend_info()
        info.update(
            {
                "num_threads": torch.get_num_threads(),
                "num_interop_threads": torch.get_num_interop_threads(),
            }
        )
        return info

    def set_num_threads(self, num_threads: int) -> None:
        """Set number of CPU threads for parallel operations.

        Args:
            num_threads: Number of threads to use
        """
        torch.set_num_threads(num_threads)

    def optimize_for_inference(self, model: torch.nn.Module) -> torch.nn.Module:
        """Optimize model for inference on CPU.

        Applies optimizations like:
        - Model evaluation mode
        - torch.compile (if enabled and available)
        - Freezing batch norm layers

        Args:
            model: Model to optimize

        Returns:
            Optimized model
        """
        model = model.cpu()
        model.eval()

        # Freeze batch norm for inference
        for module in model.modules():
            if isinstance(module, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d)):
                module.eval()

        # Apply torch.compile if enabled and available (PyTorch 2.0+)
        if self.config.compile_model:
            try:
                compiled_model = torch.compile(model, mode="reduce-overhead")
                return compiled_model  # type: ignore[return-value]
            except Exception:
                pass  # torch.compile not available or failed

        return model


def create_cpu_backend(
    enable_ttt: bool = True,
    ttt_learning_rate: float = 0.001,
    num_threads: Optional[int] = None,
) -> CPUMemoryBackend:
    """Factory function to create a CPU backend.

    Args:
        enable_ttt: Whether to enable test-time training
        ttt_learning_rate: Learning rate for TTT updates
        num_threads: Number of CPU threads (None = use default)

    Returns:
        Configured CPUMemoryBackend instance
    """
    config = BackendConfig(
        backend_type=BackendType.CPU,
        enable_ttt=enable_ttt,
        ttt_learning_rate=ttt_learning_rate,
    )

    backend = CPUMemoryBackend(config)

    if num_threads is not None:
        backend.set_num_threads(num_threads)

    return backend
