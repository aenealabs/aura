"""Tests for CPU memory backend."""

import pytest

torch = pytest.importorskip("torch", reason="PyTorch required for neural memory tests")

from src.services.memory_backends import BackendConfig, BackendType, CPUMemoryBackend
from src.services.memory_backends.cpu_backend import create_cpu_backend
from src.services.models import DeepMLPMemory, MemoryConfig


class TestBackendConfig:
    """Tests for BackendConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BackendConfig()
        assert config.backend_type == BackendType.CPU
        assert config.device_id == 0
        assert config.enable_ttt is True
        assert config.ttt_learning_rate == 0.001
        assert config.max_ttt_steps == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        config = BackendConfig(
            backend_type=BackendType.GPU,
            device_id=1,
            enable_ttt=False,
            ttt_learning_rate=0.01,
            mixed_precision=True,
        )
        assert config.backend_type == BackendType.GPU
        assert config.device_id == 1
        assert config.enable_ttt is False
        assert config.ttt_learning_rate == 0.01
        assert config.mixed_precision is True

    def test_to_dict(self):
        """Test config serialization to dict."""
        config = BackendConfig(backend_type=BackendType.CPU)
        data = config.to_dict()

        assert data["backend_type"] == "cpu"
        assert "enable_ttt" in data
        assert "ttt_learning_rate" in data

    def test_from_dict(self):
        """Test config deserialization from dict."""
        data = {
            "backend_type": "cpu",
            "enable_ttt": False,
            "ttt_learning_rate": 0.005,
        }
        config = BackendConfig.from_dict(data)

        assert config.backend_type == BackendType.CPU
        assert config.enable_ttt is False
        assert config.ttt_learning_rate == 0.005


class TestCPUMemoryBackend:
    """Tests for CPUMemoryBackend."""

    @pytest.fixture
    def backend(self):
        """Create a CPU backend."""
        backend = CPUMemoryBackend()
        backend.initialize()
        try:
            yield backend
        finally:
            # Ensure cleanup runs even if test raises exception
            backend.cleanup()

    @pytest.fixture
    def model(self):
        """Create a small model for testing."""
        config = MemoryConfig(dim=128, depth=2)
        return DeepMLPMemory(config)

    def test_initialization(self, backend):
        """Test backend initialization."""
        assert backend._is_initialized is True
        assert backend.device.type == "cpu"

    def test_get_device(self):
        """Test device getter."""
        backend = CPUMemoryBackend()
        device = backend.device
        assert device.type == "cpu"

    def test_wrong_backend_type_raises_error(self):
        """Test that non-CPU backend type raises error."""
        config = BackendConfig(backend_type=BackendType.GPU)
        with pytest.raises(ValueError, match="requires CPU backend type"):
            CPUMemoryBackend(config)

    def test_to_device_cpu_tensor(self, backend):
        """Test moving CPU tensor (no-op)."""
        tensor = torch.randn(4, 128)
        result = backend.to_device(tensor)
        assert result.device.type == "cpu"
        assert result is tensor  # Should be same object

    def test_from_device(self, backend):
        """Test moving tensor from device (no-op for CPU)."""
        tensor = torch.randn(4, 128)
        result = backend.from_device(tensor)
        assert result is tensor  # Should be same object

    def test_forward(self, backend, model):
        """Test forward pass through backend."""
        model = model.to(backend.device)
        inputs = torch.randn(4, 128)

        output = backend.forward(model, inputs)

        assert output.shape == (4, 128)
        assert output.device.type == "cpu"

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
        loss = torch.nn.functional.mse_loss(output, target)

        grad_stats = backend.backward(loss, model)

        assert "grad_norm" in grad_stats
        assert grad_stats["grad_norm"] > 0

    def test_backward_with_optimizer(self, backend, model):
        """Test backward pass with optimizer step."""
        model = model.to(backend.device)
        model.train()
        # Use higher learning rate to ensure visible parameter changes
        optimizer = torch.optim.Adam(model.parameters(), lr=0.1)

        inputs = torch.randn(4, 128)
        # Make target very different to get larger loss/gradients
        target = torch.randn(4, 128) * 10

        # Get initial parameters (detach to avoid grad_fn issues)
        initial_params = [p.detach().clone() for p in model.parameters()]

        output = backend.forward(model, inputs, use_persistent=False)
        loss = torch.nn.functional.mse_loss(output, target)

        backend.backward(loss, model, optimizer)

        # Verify at least some parameters changed
        changed = 0
        for initial, current in zip(initial_params, model.parameters()):
            if not torch.allclose(initial, current.detach()):
                changed += 1
        assert changed > 0, "No parameters changed after optimizer step"

    def test_backward_disabled_ttt(self):
        """Test backward pass with TTT disabled returns error."""
        config = BackendConfig(backend_type=BackendType.CPU, enable_ttt=False)
        backend = CPUMemoryBackend(config)
        backend.initialize()

        try:
            mem_config = MemoryConfig(dim=128, depth=2)
            model = DeepMLPMemory(mem_config)

            loss = torch.tensor(1.0, requires_grad=True)
            result = backend.backward(loss, model)

            assert "error" in result
        finally:
            backend.cleanup()

    def test_compute_surprise(self, backend, model):
        """Test surprise computation."""
        model = model.to(backend.device)
        inputs = torch.randn(4, 128)
        targets = torch.randn(4, 128)

        surprise = backend.compute_surprise(model, inputs, targets)

        assert isinstance(surprise, float)
        assert surprise >= 0

    def test_compute_surprise_similar_inputs(self, backend, model):
        """Test that similar inputs have lower surprise than different ones."""
        model = model.to(backend.device)
        model.eval()

        inputs = torch.randn(1, 128)

        # Get model prediction
        with torch.no_grad():
            prediction = model(inputs, use_persistent=False)

        # Similar target (the prediction itself)
        surprise_similar = backend.compute_surprise(model, inputs, prediction)

        # Very different target
        different_target = torch.randn(1, 128) * 10
        surprise_different = backend.compute_surprise(model, inputs, different_target)

        # Different targets should have higher surprise
        assert surprise_different >= surprise_similar

    def test_get_memory_usage(self, backend):
        """Test memory usage reporting."""
        usage = backend.get_memory_usage()

        assert "allocated_mb" in usage
        assert "reserved_mb" in usage
        assert "peak_mb" in usage

    def test_synchronize(self, backend):
        """Test synchronize (no-op for CPU)."""
        # Should not raise
        backend.synchronize()

    def test_get_backend_info(self, backend):
        """Test backend info reporting."""
        info = backend.get_backend_info()

        assert info["type"] == "cpu"
        assert info["is_initialized"] is True
        assert "num_threads" in info

    def test_set_num_threads(self, backend):
        """Test setting number of threads."""
        original = torch.get_num_threads()
        backend.set_num_threads(2)
        assert torch.get_num_threads() == 2
        # Reset
        backend.set_num_threads(original)

    def test_optimize_for_inference(self, backend, model):
        """Test model optimization for inference."""
        optimized = backend.optimize_for_inference(model)

        assert optimized.training is False
        assert next(optimized.parameters()).device.type == "cpu"

    def test_benchmark(self, backend, model):
        """Test benchmark function."""
        model = model.to(backend.device)

        results = backend.benchmark(
            model,
            input_shape=(4, 128),
            num_iterations=10,
            warmup_iterations=2,
        )

        assert "mean_ms" in results
        assert "min_ms" in results
        assert "max_ms" in results
        assert "p50_ms" in results
        assert "p99_ms" in results
        assert results["mean_ms"] > 0

    def test_context_manager(self):
        """Test backend as context manager."""
        with CPUMemoryBackend() as backend:
            assert backend._is_initialized is True
            device = backend.device
            assert device.type == "cpu"
        # After context, should be cleaned up
        assert backend._is_initialized is False

    def test_is_available(self):
        """Test availability check."""
        backend = CPUMemoryBackend()
        assert backend.is_available() is True

    def test_supports_ttt(self):
        """Test TTT support check."""
        config_ttt = BackendConfig(backend_type=BackendType.CPU, enable_ttt=True)
        backend_ttt = CPUMemoryBackend(config_ttt)
        assert backend_ttt.supports_ttt() is True

        config_no_ttt = BackendConfig(backend_type=BackendType.CPU, enable_ttt=False)
        backend_no_ttt = CPUMemoryBackend(config_no_ttt)
        assert backend_no_ttt.supports_ttt() is False


class TestCreateCPUBackend:
    """Tests for create_cpu_backend factory function."""

    def test_default_creation(self):
        """Test creating backend with defaults."""
        backend = create_cpu_backend()
        assert backend.config.backend_type == BackendType.CPU
        assert backend.config.enable_ttt is True

    def test_custom_creation(self):
        """Test creating backend with custom parameters."""
        backend = create_cpu_backend(
            enable_ttt=False,
            ttt_learning_rate=0.01,
            num_threads=4,
        )
        assert backend.config.enable_ttt is False
        assert backend.config.ttt_learning_rate == 0.01
