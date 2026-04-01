"""Abstract base class for memory backends.

This module defines the interface that all memory backends must implement,
enabling hardware abstraction across CPU, GPU, and Inferentia2.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

import torch


class BackendType(Enum):
    """Supported backend types for memory operations."""

    CPU = "cpu"
    GPU = "gpu"
    INFERENTIA2 = "inferentia2"


@dataclass
class BackendConfig:
    """Configuration for memory backend.

    Attributes:
        backend_type: Type of compute backend to use
        device_id: Device ID for multi-device setups (e.g., GPU index)
        enable_ttt: Whether test-time training is enabled
        ttt_learning_rate: Learning rate for TTT updates
        max_ttt_steps: Maximum TTT steps per inference
        mixed_precision: Enable mixed precision (FP16/BF16)
        compile_model: Use torch.compile for optimization
        memory_efficient: Enable memory-efficient attention
        batch_size: Default batch size for operations
        extra_config: Additional backend-specific configuration
    """

    backend_type: BackendType = BackendType.CPU
    device_id: int = 0
    enable_ttt: bool = True
    ttt_learning_rate: float = 0.001
    max_ttt_steps: int = 3
    mixed_precision: bool = False
    compile_model: bool = False
    memory_efficient: bool = True
    batch_size: int = 32
    extra_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "backend_type": self.backend_type.value,
            "device_id": self.device_id,
            "enable_ttt": self.enable_ttt,
            "ttt_learning_rate": self.ttt_learning_rate,
            "max_ttt_steps": self.max_ttt_steps,
            "mixed_precision": self.mixed_precision,
            "compile_model": self.compile_model,
            "memory_efficient": self.memory_efficient,
            "batch_size": self.batch_size,
            "extra_config": self.extra_config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackendConfig":
        """Create config from dictionary."""
        if "backend_type" in data and isinstance(data["backend_type"], str):
            data["backend_type"] = BackendType(data["backend_type"])
        return cls(**data)


class MemoryBackend(ABC):
    """Abstract base class for memory backends.

    This interface enables hardware abstraction, allowing DeepMLPMemory
    to run on CPU (development), GPU (production), or Inferentia2
    (optimized inference) with the same code.

    Implementation Strategy:
    - CPU: Pure PyTorch, no optimization
    - GPU: CUDA tensors, optional mixed precision
    - Inferentia2: Neuron SDK compilation (future)
    """

    def __init__(self, config: Optional[BackendConfig] = None) -> None:
        """Initialize backend with configuration.

        Args:
            config: Backend configuration. Uses defaults if None.
        """
        self.config = config or BackendConfig()
        self._device: Optional[torch.device] = None
        self._is_initialized = False

    @property
    def device(self) -> torch.device:
        """Get the torch device for this backend."""
        if self._device is None:
            self._device = self._get_device()
        return self._device

    @abstractmethod
    def _get_device(self) -> torch.device:
        """Get the appropriate torch device for this backend.

        Returns:
            torch.device for tensor operations
        """

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the backend.

        This method should:
        1. Validate hardware availability
        2. Set up any required contexts or sessions
        3. Warm up the device if needed
        """

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up backend resources.

        This method should:
        1. Release device memory
        2. Close any sessions or contexts
        3. Reset state for potential reinitialization
        """

    @abstractmethod
    def to_device(self, tensor: torch.Tensor) -> torch.Tensor:
        """Move tensor to backend device.

        Args:
            tensor: Input tensor on any device

        Returns:
            Tensor on this backend's device
        """

    @abstractmethod
    def from_device(self, tensor: torch.Tensor) -> torch.Tensor:
        """Move tensor from backend device to CPU.

        Args:
            tensor: Tensor on this backend's device

        Returns:
            Tensor on CPU
        """

    @abstractmethod
    def forward(
        self,
        model: torch.nn.Module,
        inputs: torch.Tensor,
        **kwargs: Any,
    ) -> torch.Tensor:
        """Execute forward pass on this backend.

        Args:
            model: The neural network module
            inputs: Input tensor
            **kwargs: Additional arguments for the model

        Returns:
            Model output tensor
        """

    @abstractmethod
    def backward(
        self,
        loss: torch.Tensor,
        model: torch.nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None,
    ) -> Dict[str, float]:
        """Execute backward pass for TTT.

        Args:
            loss: Scalar loss tensor
            model: The neural network module
            optimizer: Optional optimizer for parameter updates

        Returns:
            Dictionary with gradient statistics
        """

    @abstractmethod
    def compute_surprise(
        self,
        model: torch.nn.Module,
        inputs: torch.Tensor,
        targets: torch.Tensor,
    ) -> float:
        """Compute surprise score for selective memorization.

        Args:
            model: The neural network module
            inputs: Input tensor
            targets: Target tensor for reconstruction

        Returns:
            Surprise score (gradient magnitude normalized)
        """

    @abstractmethod
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics.

        Returns:
            Dictionary with memory stats in MB:
            - allocated: Currently allocated memory
            - reserved: Reserved memory (may include cache)
            - peak: Peak memory usage
        """

    @abstractmethod
    def synchronize(self) -> None:
        """Synchronize device operations.

        For GPU: cuda.synchronize()
        For Inferentia2: Wait for all operations to complete
        For CPU: No-op
        """

    def is_available(self) -> bool:
        """Check if this backend is available on the current system.

        Returns:
            True if the backend can be used
        """
        try:
            self.initialize()
            self.cleanup()
            return True
        except Exception:
            return False

    def supports_ttt(self) -> bool:
        """Check if this backend supports test-time training.

        Returns:
            True if TTT is supported
        """
        return self.config.enable_ttt

    def get_backend_info(self) -> Dict[str, Any]:
        """Get information about this backend.

        Returns:
            Dictionary with backend information
        """
        return {
            "type": self.config.backend_type.value,
            "device": str(self.device),
            "ttt_enabled": self.supports_ttt(),
            "mixed_precision": self.config.mixed_precision,
            "is_initialized": self._is_initialized,
        }

    def __enter__(self) -> "MemoryBackend":
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.cleanup()

    def benchmark(
        self,
        model: torch.nn.Module,
        input_shape: Tuple[int, ...],
        num_iterations: int = 100,
        warmup_iterations: int = 10,
    ) -> Dict[str, float]:
        """Benchmark forward pass performance.

        Args:
            model: The neural network module
            input_shape: Shape of input tensor (batch_size, dim)
            num_iterations: Number of benchmark iterations
            warmup_iterations: Number of warmup iterations

        Returns:
            Dictionary with timing statistics in milliseconds
        """
        import time

        # Create random input
        dummy_input = torch.randn(*input_shape)
        dummy_input = self.to_device(dummy_input)

        # Move model to device
        model = model.to(self.device)
        model.eval()

        # Warmup
        with torch.no_grad():
            for _ in range(warmup_iterations):
                _ = self.forward(model, dummy_input)
                self.synchronize()

        # Benchmark
        latencies = []
        with torch.no_grad():
            for _ in range(num_iterations):
                start = time.perf_counter()
                _ = self.forward(model, dummy_input)
                self.synchronize()
                end = time.perf_counter()
                latencies.append((end - start) * 1000)  # Convert to ms

        return {
            "mean_ms": sum(latencies) / len(latencies),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "p50_ms": sorted(latencies)[len(latencies) // 2],
            "p99_ms": sorted(latencies)[int(len(latencies) * 0.99)],
        }
