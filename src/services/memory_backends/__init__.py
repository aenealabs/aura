"""Memory backend implementations for hardware abstraction.

This module provides a hardware abstraction layer that allows the same
DeepMLPMemory model to run on different compute backends:
- CPU: Development and testing
- GPU: Production with TTT capabilities (CUDA or MPS)
- Inferentia2: Production inference optimization (future)
"""

from .base import BackendConfig, BackendType, MemoryBackend
from .cpu_backend import CPUMemoryBackend, create_cpu_backend
from .gpu_backend import GPUMemoryBackend, create_gpu_backend

__all__ = [
    "MemoryBackend",
    "BackendConfig",
    "BackendType",
    "CPUMemoryBackend",
    "create_cpu_backend",
    "GPUMemoryBackend",
    "create_gpu_backend",
]
