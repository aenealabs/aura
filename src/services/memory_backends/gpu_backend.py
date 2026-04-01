"""GPU/MPS backend implementation for production workloads.

This backend supports:
- CUDA: NVIDIA GPUs (Linux/Windows)
- MPS: Apple Silicon GPUs (macOS)

Both provide significant performance improvements over CPU for neural memory
operations, especially for larger batch sizes.
"""

import math
from typing import Any, Dict, Optional

import torch
import torch.nn.functional as F

from .base import BackendConfig, BackendType, MemoryBackend


class GPUMemoryBackend(MemoryBackend):
    """GPU-based memory backend for production workloads.

    This backend automatically selects the best available GPU:
    - CUDA for NVIDIA GPUs
    - MPS for Apple Silicon

    Performance characteristics (typical, varies by hardware):
    - Latency: ~1-5ms per forward pass (batch_size=32, dim=512)
    - Throughput: ~10,000-50,000 requests/second
    - Memory: Efficient batching, automatic memory management

    Note: Falls back to CPU if no GPU is available.
    """

    def __init__(self, config: Optional[BackendConfig] = None) -> None:
        """Initialize GPU backend.

        Args:
            config: Backend configuration. Defaults to GPU settings.
        """
        if config is None:
            config = BackendConfig(backend_type=BackendType.GPU)
        elif config.backend_type not in (BackendType.GPU, BackendType.CPU):
            raise ValueError(
                f"GPUMemoryBackend requires GPU or CPU backend type, got {config.backend_type}"
            )

        super().__init__(config)
        self._gpu_type: Optional[str] = None  # "cuda", "mps", or None
        self._peak_memory = 0.0

    def _get_device(self) -> torch.device:
        """Get the best available GPU device.

        Returns:
            torch.device for the best available accelerator
        """
        if torch.cuda.is_available():
            self._gpu_type = "cuda"
            return torch.device(f"cuda:{self.config.device_id}")
        elif torch.backends.mps.is_available():
            self._gpu_type = "mps"
            return torch.device("mps")
        else:
            self._gpu_type = None
            return torch.device("cpu")

    def initialize(self) -> None:
        """Initialize GPU backend.

        Sets up the device and optionally warms up the GPU.
        """
        self._device = self._get_device()
        self._is_initialized = True
        self._peak_memory = 0.0

        # Warm up GPU
        if self._gpu_type == "cuda":
            # Run a small operation to initialize CUDA context
            dummy = torch.zeros(1, device=self._device)  # noqa: F841
            del dummy
            torch.cuda.synchronize()
        elif self._gpu_type == "mps":
            # MPS warmup
            _dummy = torch.zeros(1, device=self._device)  # noqa: F841
            del _dummy

    def cleanup(self) -> None:
        """Clean up GPU backend resources."""
        if self._gpu_type == "cuda":
            torch.cuda.empty_cache()
        elif self._gpu_type == "mps":
            # MPS doesn't have explicit cache clearing
            pass

        import gc

        gc.collect()

        self._is_initialized = False
        self._peak_memory = 0.0

    def to_device(self, tensor: torch.Tensor) -> torch.Tensor:
        """Move tensor to GPU device.

        Args:
            tensor: Input tensor

        Returns:
            Tensor on GPU
        """
        if tensor.device == self._device:
            return tensor
        return tensor.to(self._device)

    def from_device(self, tensor: torch.Tensor) -> torch.Tensor:
        """Move tensor from GPU to CPU.

        Args:
            tensor: Tensor on GPU

        Returns:
            Tensor on CPU
        """
        return tensor.cpu()

    def forward(
        self,
        model: torch.nn.Module,
        inputs: torch.Tensor,
        **kwargs: Any,
    ) -> torch.Tensor:
        """Execute forward pass on GPU.

        Args:
            model: The neural network module
            inputs: Input tensor
            **kwargs: Additional arguments for the model

        Returns:
            Model output tensor
        """
        # Ensure model is on GPU
        model = model.to(self._device)

        # Ensure inputs are on GPU
        inputs = self.to_device(inputs)

        # Forward pass with optional mixed precision
        if self.config.mixed_precision and self._gpu_type == "cuda":
            with torch.cuda.amp.autocast():
                with torch.set_grad_enabled(self.config.enable_ttt):
                    output = model(inputs, **kwargs)
        else:
            with torch.set_grad_enabled(self.config.enable_ttt):
                output = model(inputs, **kwargs)

        # Track memory usage
        self._update_memory_stats()

        # Cast to Tensor to satisfy mypy
        result: torch.Tensor = output
        return result

    def backward(
        self,
        loss: torch.Tensor,
        model: torch.nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None,
    ) -> Dict[str, float]:
        """Execute backward pass for TTT on GPU.

        Args:
            loss: Scalar loss tensor
            model: The neural network module
            optimizer: Optional optimizer for parameter updates

        Returns:
            Dictionary with gradient statistics
        """
        if not self.config.enable_ttt:
            return {"error": 0.0}  # Type-safe error indicator

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
        """Compute surprise score on GPU.

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
        model = model.to(self._device)

        # Zero existing gradients
        model.zero_grad()

        # Move tensors to GPU
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
        """Get current GPU memory usage statistics.

        Returns:
            Dictionary with memory stats in MB
        """
        if self._gpu_type == "cuda":
            allocated = torch.cuda.memory_allocated(self._device) / (1024 * 1024)
            reserved = torch.cuda.memory_reserved(self._device) / (1024 * 1024)
            peak = torch.cuda.max_memory_allocated(self._device) / (1024 * 1024)
            return {
                "allocated_mb": allocated,
                "reserved_mb": reserved,
                "peak_mb": peak,
            }
        elif self._gpu_type == "mps":
            # MPS doesn't provide detailed memory stats
            # Use driver memory as approximation
            try:
                allocated = torch.mps.current_allocated_memory() / (1024 * 1024)
                return {
                    "allocated_mb": allocated,
                    "reserved_mb": allocated,
                    "peak_mb": max(self._peak_memory, allocated),
                }
            except AttributeError:
                return {
                    "allocated_mb": 0.0,
                    "reserved_mb": 0.0,
                    "peak_mb": 0.0,
                }
        else:
            # Fallback for CPU
            return {
                "allocated_mb": 0.0,
                "reserved_mb": 0.0,
                "peak_mb": 0.0,
            }

    def synchronize(self) -> None:
        """Synchronize GPU operations."""
        if self._gpu_type == "cuda":
            torch.cuda.synchronize()
        elif self._gpu_type == "mps":
            torch.mps.synchronize()
        # CPU is synchronous

    def _compute_gradient_stats(self, model: torch.nn.Module) -> Dict[str, float]:
        """Compute statistics about gradients."""
        grad_norms = []

        for param in model.parameters():
            if param.grad is not None:
                grad_norms.append(param.grad.norm().item())

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
        """Get GPU backend information."""
        info = super().get_backend_info()
        info.update(
            {
                "gpu_type": self._gpu_type or "none",
                "device_name": self._get_device_name(),
            }
        )
        return info

    def _get_device_name(self) -> str:
        """Get the name of the GPU device."""
        if self._gpu_type == "cuda":
            return torch.cuda.get_device_name(self.config.device_id)
        elif self._gpu_type == "mps":
            return "Apple Silicon (MPS)"
        else:
            return "CPU (fallback)"

    def optimize_for_inference(self, model: torch.nn.Module) -> torch.nn.Module:
        """Optimize model for inference on GPU.

        Args:
            model: Model to optimize

        Returns:
            Optimized model
        """
        model = model.to(self._device)
        model.eval()

        # Freeze batch norm for inference
        for module in model.modules():
            if isinstance(module, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d)):
                module.eval()

        # Apply torch.compile if enabled (PyTorch 2.0+)
        if self.config.compile_model and self._gpu_type == "cuda":
            try:
                compiled_model = torch.compile(model, mode="reduce-overhead")
                # torch.compile returns a callable wrapper, treat as optimized model
                return compiled_model  # type: ignore[return-value]
            except Exception:
                pass  # torch.compile not available or failed

        return model


def create_gpu_backend(
    enable_ttt: bool = True,
    ttt_learning_rate: float = 0.001,
    mixed_precision: bool = False,
    device_id: int = 0,
) -> GPUMemoryBackend:
    """Factory function to create a GPU backend.

    Args:
        enable_ttt: Whether to enable test-time training
        ttt_learning_rate: Learning rate for TTT updates
        mixed_precision: Enable mixed precision (FP16)
        device_id: GPU device ID for multi-GPU systems

    Returns:
        Configured GPUMemoryBackend instance
    """
    config = BackendConfig(
        backend_type=BackendType.GPU,
        device_id=device_id,
        enable_ttt=enable_ttt,
        ttt_learning_rate=ttt_learning_rate,
        mixed_precision=mixed_precision,
    )
    return GPUMemoryBackend(config)
