"""
Tests for GPU/MPS memory backend.

Test Type: UNIT (with real GPU hardware requirement)
Dependencies: PyTorch with CUDA support
Isolation: pytest.mark.gpu_required (skipped on Apple Silicon/non-CUDA systems)
Run Command: pytest tests/services/test_memory_backends/test_gpu_backend.py -v

These tests validate:
- GPU backend initialization and device detection
- Tensor movement between CPU and GPU
- Forward/backward pass on GPU
- Memory usage tracking and optimization

Hardware Requirements:
- NVIDIA GPU with CUDA support
- Tests are automatically skipped on Apple Silicon (MPS) and CPU-only systems

Related Tests:
- test_cpu_backend.py: CPU backend tests (always run)
- test_mps_backend.py: Apple Silicon MPS tests (run on macOS with MPS)
"""

import platform

import pytest

torch = pytest.importorskip("torch", reason="PyTorch required for neural memory tests")

# Skip all tests in this module if CUDA is not available
# This includes Apple Silicon Macs which use MPS instead of CUDA
_is_cuda_available = torch.cuda.is_available()
_is_apple_silicon = platform.system() == "Darwin" and platform.machine() == "arm64"

pytestmark = [
    pytest.mark.gpu_required,
    pytest.mark.skipif(
        not _is_cuda_available,
        reason=(
            "CUDA not available (Apple Silicon uses MPS, not CUDA)"
            if _is_apple_silicon
            else "CUDA not available (no NVIDIA GPU detected)"
        ),
    ),
]

from src.services.memory_backends import (  # noqa: E402
    BackendType,
    GPUMemoryBackend,
    create_gpu_backend,
)
from src.services.models import DeepMLPMemory, MemoryConfig  # noqa: E402


class TestGPUMemoryBackend:
    """Tests for GPUMemoryBackend."""

    @pytest.fixture
    def backend(self):
        """Create a GPU backend."""
        backend = GPUMemoryBackend()
        backend.initialize()
        yield backend
        backend.cleanup()

    @pytest.fixture
    def model(self):
        """Create a small model for testing."""
        config = MemoryConfig(dim=128, depth=2)
        return DeepMLPMemory(config)

    def test_initialization(self, backend):
        """Test backend initialization."""
        assert backend._is_initialized is True
        # Should have detected MPS or CUDA or fallback to CPU
        assert backend._gpu_type in ("cuda", "mps", None)

    def test_get_device(self):
        """Test device getter."""
        backend = GPUMemoryBackend()
        device = backend.device
        # Should be cuda, mps, or cpu
        assert device.type in ("cuda", "mps", "cpu")

    def test_to_device(self, backend):
        """Test moving tensor to GPU."""
        tensor = torch.randn(4, 128)
        result = backend.to_device(tensor)
        assert result.device.type == backend.device.type

    def test_from_device(self, backend):
        """Test moving tensor from GPU to CPU."""
        tensor = torch.randn(4, 128)
        tensor = backend.to_device(tensor)
        result = backend.from_device(tensor)
        assert result.device.type == "cpu"

    def test_forward(self, backend, model):
        """Test forward pass through backend."""
        model = model.to(backend.device)
        inputs = torch.randn(4, 128)

        output = backend.forward(model, inputs)

        assert output.shape == (4, 128)
        assert output.device.type == backend.device.type

    def test_forward_with_kwargs(self, backend, model):
        """Test forward pass with additional kwargs."""
        model = model.to(backend.device)
        inputs = torch.randn(4, 128)

        output = backend.forward(model, inputs, use_persistent=False)

        assert output.shape == (4, 128)

    def test_backward(self, backend, model):
        """Test backward pass."""
        model = model.to(backend.device)
        model.train()

        inputs = torch.randn(4, 128)
        target = torch.randn(4, 128)

        output = backend.forward(model, inputs, use_persistent=False)
        loss = torch.nn.functional.mse_loss(output, backend.to_device(target))

        grad_stats = backend.backward(loss, model)

        assert "grad_norm" in grad_stats
        assert grad_stats["grad_norm"] > 0

    def test_backward_with_optimizer(self, backend, model):
        """Test backward pass with optimizer step."""
        model = model.to(backend.device)
        model.train()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.1)

        inputs = torch.randn(4, 128)
        target = torch.randn(4, 128) * 10

        # Get initial parameters
        initial_params = [p.detach().clone() for p in model.parameters()]

        output = backend.forward(model, inputs, use_persistent=False)
        loss = torch.nn.functional.mse_loss(output, backend.to_device(target))

        backend.backward(loss, model, optimizer)

        # Verify at least some parameters changed
        changed = 0
        for initial, current in zip(initial_params, model.parameters()):
            if not torch.allclose(initial.cpu(), current.detach().cpu()):
                changed += 1
        assert changed > 0, "No parameters changed after optimizer step"

    def test_compute_surprise(self, backend, model):
        """Test surprise computation."""
        model = model.to(backend.device)
        inputs = torch.randn(4, 128)
        targets = torch.randn(4, 128)

        surprise = backend.compute_surprise(model, inputs, targets)

        assert isinstance(surprise, float)
        assert surprise >= 0

    def test_get_memory_usage(self, backend):
        """Test memory usage reporting."""
        usage = backend.get_memory_usage()

        assert "allocated_mb" in usage
        assert "reserved_mb" in usage
        assert "peak_mb" in usage

    def test_synchronize(self, backend):
        """Test synchronize."""
        # Should not raise
        backend.synchronize()

    def test_get_backend_info(self, backend):
        """Test backend info reporting."""
        info = backend.get_backend_info()

        assert "type" in info
        assert "gpu_type" in info
        assert "device_name" in info
        assert info["is_initialized"] is True

    def test_optimize_for_inference(self, backend, model):
        """Test model optimization for inference."""
        optimized = backend.optimize_for_inference(model)

        assert optimized.training is False
        assert next(optimized.parameters()).device.type == backend.device.type

    def test_context_manager(self):
        """Test backend as context manager."""
        with GPUMemoryBackend() as backend:
            assert backend._is_initialized is True
            device = backend.device
            assert device.type in ("cuda", "mps", "cpu")
        assert backend._is_initialized is False


class TestCreateGPUBackend:
    """Tests for create_gpu_backend factory function."""

    def test_default_creation(self):
        """Test creating backend with defaults."""
        backend = create_gpu_backend()
        assert backend.config.backend_type == BackendType.GPU
        assert backend.config.enable_ttt is True

    def test_custom_creation(self):
        """Test creating backend with custom parameters."""
        backend = create_gpu_backend(
            enable_ttt=False,
            ttt_learning_rate=0.01,
            mixed_precision=True,
            device_id=0,
        )
        assert backend.config.enable_ttt is False
        assert backend.config.ttt_learning_rate == 0.01
        assert backend.config.mixed_precision is True


class TestGPUvsCPUConsistency:
    """Tests to ensure GPU and CPU produce consistent results."""

    @pytest.fixture
    def cpu_backend(self):
        """Create CPU backend."""
        from src.services.memory_backends import CPUMemoryBackend

        backend = CPUMemoryBackend()
        backend.initialize()
        yield backend
        backend.cleanup()

    @pytest.fixture
    def gpu_backend(self):
        """Create GPU backend."""
        backend = GPUMemoryBackend()
        backend.initialize()
        yield backend
        backend.cleanup()

    def test_forward_consistency(self, cpu_backend, gpu_backend):
        """Test that forward pass gives similar results on CPU and GPU."""
        # Create identical models
        torch.manual_seed(42)
        config = MemoryConfig(dim=64, depth=2)
        model_cpu = DeepMLPMemory(config)

        torch.manual_seed(42)
        model_gpu = DeepMLPMemory(config)

        # Same input
        torch.manual_seed(123)
        inputs = torch.randn(4, 64)

        # Forward on both backends
        model_cpu.eval()
        model_gpu.eval()

        with torch.no_grad():
            output_cpu = cpu_backend.forward(
                model_cpu, inputs.clone(), use_persistent=True
            )
            output_gpu = gpu_backend.forward(
                model_gpu, inputs.clone(), use_persistent=True
            )

        # Move GPU output to CPU for comparison
        output_gpu = gpu_backend.from_device(output_gpu)

        # Should be very close (small floating point differences expected)
        torch.testing.assert_close(output_cpu, output_gpu, rtol=1e-4, atol=1e-4)

    def test_surprise_consistency(self, cpu_backend, gpu_backend):
        """Test that surprise computation gives similar results."""
        # Create identical models
        torch.manual_seed(42)
        config = MemoryConfig(dim=64, depth=2)
        model_cpu = DeepMLPMemory(config)

        torch.manual_seed(42)
        model_gpu = DeepMLPMemory(config)

        # Same input
        torch.manual_seed(123)
        inputs = torch.randn(4, 64)
        targets = torch.randn(4, 64)

        # Compute surprise on both
        surprise_cpu = cpu_backend.compute_surprise(
            model_cpu, inputs.clone(), targets.clone()
        )
        surprise_gpu = gpu_backend.compute_surprise(
            model_gpu, inputs.clone(), targets.clone()
        )

        # Should be reasonably close
        assert (
            abs(surprise_cpu - surprise_gpu) < 0.1
        ), f"Surprise values differ: CPU={surprise_cpu:.4f}, GPU={surprise_gpu:.4f}"
