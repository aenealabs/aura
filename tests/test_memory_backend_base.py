"""
Project Aura - Memory Backend Base Tests

Tests for the abstract memory backend base class and
related configuration dataclasses.
"""

import sys
from unittest.mock import MagicMock

# Save original modules before mocking to prevent test pollution
_modules_to_save = [
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "src.services.memory_backends.base",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock torch to avoid GPU dependency issues
# Must mock submodules too since memory_backends/__init__.py imports cpu/gpu backends
mock_torch = MagicMock()
mock_torch.device = MagicMock
mock_torch.Tensor = MagicMock
mock_torch.float32 = "float32"
mock_torch.float16 = "float16"
mock_torch.bfloat16 = "bfloat16"
mock_torch.nn = MagicMock()
mock_torch.nn.functional = MagicMock()
mock_torch.nn.functional.normalize = MagicMock(return_value=MagicMock())
mock_torch.nn.functional.softmax = MagicMock(return_value=MagicMock())
sys.modules["torch"] = mock_torch
sys.modules["torch.nn"] = mock_torch.nn
sys.modules["torch.nn.functional"] = mock_torch.nn.functional

from src.services.memory_backends.base import BackendConfig, BackendType, MemoryBackend

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


class TestBackendType:
    """Tests for BackendType enum."""

    def test_backend_type_cpu(self):
        """Test CPU backend type."""
        assert BackendType.CPU.value == "cpu"

    def test_backend_type_gpu(self):
        """Test GPU backend type."""
        assert BackendType.GPU.value == "gpu"

    def test_backend_type_inferentia(self):
        """Test Inferentia2 backend type."""
        assert BackendType.INFERENTIA2.value == "inferentia2"

    def test_all_backend_types(self):
        """Test that all expected backend types exist."""
        types = list(BackendType)
        assert len(types) == 3


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
        assert config.mixed_precision is False
        assert config.compile_model is False
        assert config.memory_efficient is True
        assert config.batch_size == 32
        assert config.extra_config == {}

    def test_custom_config(self):
        """Test custom configuration values."""
        config = BackendConfig(
            backend_type=BackendType.GPU,
            device_id=2,
            enable_ttt=False,
            ttt_learning_rate=0.01,
            max_ttt_steps=5,
            mixed_precision=True,
            compile_model=True,
            batch_size=64,
        )
        assert config.backend_type == BackendType.GPU
        assert config.device_id == 2
        assert config.enable_ttt is False
        assert config.ttt_learning_rate == 0.01
        assert config.max_ttt_steps == 5
        assert config.mixed_precision is True
        assert config.compile_model is True
        assert config.batch_size == 64

    def test_extra_config(self):
        """Test extra configuration dictionary."""
        extra = {"custom_param": 42, "flag": True}
        config = BackendConfig(extra_config=extra)
        assert config.extra_config == extra
        assert config.extra_config["custom_param"] == 42

    def test_to_dict(self):
        """Test configuration serialization to dict."""
        config = BackendConfig(
            backend_type=BackendType.GPU,
            device_id=1,
            enable_ttt=True,
            batch_size=16,
        )
        data = config.to_dict()

        assert data["backend_type"] == "gpu"
        assert data["device_id"] == 1
        assert data["enable_ttt"] is True
        assert data["batch_size"] == 16
        assert "ttt_learning_rate" in data
        assert "extra_config" in data

    def test_to_dict_all_fields(self):
        """Test that to_dict includes all fields."""
        config = BackendConfig()
        data = config.to_dict()

        expected_fields = [
            "backend_type",
            "device_id",
            "enable_ttt",
            "ttt_learning_rate",
            "max_ttt_steps",
            "mixed_precision",
            "compile_model",
            "memory_efficient",
            "batch_size",
            "extra_config",
        ]
        for field_name in expected_fields:
            assert field_name in data

    def test_from_dict_basic(self):
        """Test configuration deserialization from dict."""
        data = {
            "backend_type": "cpu",
            "device_id": 0,
            "enable_ttt": True,
            "ttt_learning_rate": 0.001,
            "max_ttt_steps": 3,
            "mixed_precision": False,
            "compile_model": False,
            "memory_efficient": True,
            "batch_size": 32,
            "extra_config": {},
        }
        config = BackendConfig.from_dict(data)

        assert config.backend_type == BackendType.CPU
        assert config.device_id == 0
        assert config.batch_size == 32

    def test_from_dict_gpu(self):
        """Test deserialization with GPU backend."""
        data = {
            "backend_type": "gpu",
            "device_id": 1,
            "enable_ttt": False,
            "ttt_learning_rate": 0.005,
            "max_ttt_steps": 10,
            "mixed_precision": True,
            "compile_model": True,
            "memory_efficient": True,
            "batch_size": 128,
            "extra_config": {"cuda_graphs": True},
        }
        config = BackendConfig.from_dict(data)

        assert config.backend_type == BackendType.GPU
        assert config.device_id == 1
        assert config.mixed_precision is True
        assert config.extra_config["cuda_graphs"] is True

    def test_from_dict_with_enum(self):
        """Test that from_dict handles BackendType enum correctly."""
        # Test with string value
        data1 = {
            "backend_type": "gpu",
            "device_id": 0,
            "enable_ttt": True,
            "ttt_learning_rate": 0.001,
            "max_ttt_steps": 3,
            "mixed_precision": False,
            "compile_model": False,
            "memory_efficient": True,
            "batch_size": 32,
            "extra_config": {},
        }
        config1 = BackendConfig.from_dict(data1)
        assert config1.backend_type == BackendType.GPU

    def test_roundtrip(self):
        """Test serialization and deserialization roundtrip."""
        original = BackendConfig(
            backend_type=BackendType.GPU,
            device_id=3,
            enable_ttt=False,
            ttt_learning_rate=0.0001,
            max_ttt_steps=7,
            mixed_precision=True,
            compile_model=True,
            memory_efficient=False,
            batch_size=256,
            extra_config={"test": 123},
        )

        data = original.to_dict()
        restored = BackendConfig.from_dict(data)

        assert restored.backend_type == original.backend_type
        assert restored.device_id == original.device_id
        assert restored.enable_ttt == original.enable_ttt
        assert restored.ttt_learning_rate == original.ttt_learning_rate
        assert restored.max_ttt_steps == original.max_ttt_steps
        assert restored.mixed_precision == original.mixed_precision
        assert restored.batch_size == original.batch_size
        assert restored.extra_config == original.extra_config


class ConcreteMemoryBackend(MemoryBackend):
    """Concrete implementation for testing abstract base class."""

    def _get_device(self):
        return mock_torch.device("cpu")

    def initialize(self):
        self._is_initialized = True

    def cleanup(self):
        self._is_initialized = False

    def to_device(self, tensor):
        return tensor

    def from_device(self, tensor):
        return tensor

    def allocate_memory(self, size):
        return MagicMock()

    def free_memory(self, tensor):
        pass

    def memory_stats(self):
        return {"allocated": 0, "reserved": 0}

    def forward_pass(self, model, input_tensor):
        return input_tensor

    def backward_pass(self, model, loss):
        pass

    def optimize_step(self, optimizer):
        pass

    # Additional abstract methods required by the interface
    def forward(self, model, input_tensor, labels=None):
        return input_tensor, None

    def backward(self, model, loss):
        pass

    def compute_surprise(self, model, input_tensor):
        return mock_torch.Tensor()

    def get_memory_usage(self):
        return {"allocated_mb": 0, "reserved_mb": 0}

    def synchronize(self):
        pass


class TestMemoryBackend:
    """Tests for MemoryBackend abstract base class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        backend = ConcreteMemoryBackend()
        assert backend.config is not None
        assert backend.config.backend_type == BackendType.CPU
        assert backend._is_initialized is False

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = BackendConfig(
            backend_type=BackendType.GPU,
            device_id=1,
            batch_size=64,
        )
        backend = ConcreteMemoryBackend(config)
        assert backend.config == config
        assert backend.config.device_id == 1

    def test_device_property(self):
        """Test device property."""
        backend = ConcreteMemoryBackend()
        device = backend.device
        assert device is not None

    def test_device_caching(self):
        """Test that device is cached."""
        backend = ConcreteMemoryBackend()
        device1 = backend.device
        device2 = backend.device
        # Should be the same cached device
        assert device1 is device2

    def test_initialize(self):
        """Test backend initialization."""
        backend = ConcreteMemoryBackend()
        assert backend._is_initialized is False
        backend.initialize()
        assert backend._is_initialized is True

    def test_cleanup(self):
        """Test backend cleanup."""
        backend = ConcreteMemoryBackend()
        backend.initialize()
        assert backend._is_initialized is True
        backend.cleanup()
        assert backend._is_initialized is False

    def test_to_device(self):
        """Test moving tensor to device."""
        backend = ConcreteMemoryBackend()
        tensor = MagicMock()
        result = backend.to_device(tensor)
        assert result is not None

    def test_from_device(self):
        """Test moving tensor from device to CPU."""
        backend = ConcreteMemoryBackend()
        tensor = MagicMock()
        result = backend.from_device(tensor)
        assert result is not None

    def test_allocate_memory(self):
        """Test memory allocation."""
        backend = ConcreteMemoryBackend()
        tensor = backend.allocate_memory(1000)
        assert tensor is not None

    def test_memory_stats(self):
        """Test memory statistics."""
        backend = ConcreteMemoryBackend()
        stats = backend.memory_stats()
        assert "allocated" in stats
        assert "reserved" in stats


class TestBackendConfigEdgeCases:
    """Tests for edge cases in BackendConfig."""

    def test_negative_device_id(self):
        """Test that negative device ID is allowed (for validation elsewhere)."""
        config = BackendConfig(device_id=-1)
        assert config.device_id == -1

    def test_zero_batch_size(self):
        """Test zero batch size."""
        config = BackendConfig(batch_size=0)
        assert config.batch_size == 0

    def test_very_large_batch_size(self):
        """Test very large batch size."""
        config = BackendConfig(batch_size=10000)
        assert config.batch_size == 10000

    def test_zero_learning_rate(self):
        """Test zero learning rate."""
        config = BackendConfig(ttt_learning_rate=0.0)
        assert config.ttt_learning_rate == 0.0

    def test_nested_extra_config(self):
        """Test nested extra config dictionary."""
        nested = {"level1": {"level2": {"value": 42}}}
        config = BackendConfig(extra_config=nested)
        assert config.extra_config["level1"]["level2"]["value"] == 42
