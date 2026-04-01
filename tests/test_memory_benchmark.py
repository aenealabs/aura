"""
Project Aura - Memory Benchmark Tests

Comprehensive tests for the neural memory backend benchmarking module.
Tests BenchmarkConfig, BenchmarkResult, BenchmarkSuite, MemoryBenchmark,
and the run_benchmarks function from the actual source module.

Tests use mocking to isolate from hardware dependencies while achieving
high code coverage of the benchmark.py module.

Test Type: UNIT (no GPU hardware required)
Dependencies: PyTorch
Run Command: pytest tests/test_memory_benchmark.py -v
"""

import json
import os
import platform
from dataclasses import asdict
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Ensure torch is available - skip if not installed
torch = pytest.importorskip("torch", reason="PyTorch required for neural memory tests")

# Import the module once - torch is available in the test environment
from src.services.memory_backends.benchmark import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkSuite,
    MemoryBenchmark,
    run_benchmarks,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_backend():
    """Create a mock memory backend."""
    backend = MagicMock()
    backend.config = MagicMock()
    backend.config.backend_type = MagicMock()
    backend.config.backend_type.value = "cpu"
    backend.device = "cpu"
    backend.to_device.side_effect = lambda x: x
    backend.forward.return_value = MagicMock()
    backend.backward.return_value = {}
    backend.compute_surprise.return_value = 0.5
    backend.synchronize.return_value = None
    backend.get_memory_usage.return_value = {"peak_mb": 128.0}
    backend.get_backend_info.return_value = {"device_name": "cpu", "gpu_type": "none"}
    backend.initialize.return_value = None
    backend.cleanup.return_value = None
    return backend


@pytest.fixture
def mock_gpu_backend():
    """Create a mock GPU memory backend."""
    backend = MagicMock()
    backend.config = MagicMock()
    backend.config.backend_type = MagicMock()
    backend.config.backend_type.value = "gpu"
    backend.device = "cuda:0"
    backend.to_device.side_effect = lambda x: x
    backend.forward.return_value = MagicMock()
    backend.backward.return_value = {}
    backend.compute_surprise.return_value = 0.3
    backend.synchronize.return_value = None
    backend.get_memory_usage.return_value = {"peak_mb": 512.0}
    backend.get_backend_info.return_value = {
        "device_name": "NVIDIA A100",
        "gpu_type": "cuda",
    }
    backend.initialize.return_value = None
    backend.cleanup.return_value = None
    return backend


@pytest.fixture
def mock_model():
    """Create a mock DeepMLPMemory model."""
    model = MagicMock()
    model.to.return_value = model
    model.eval.return_value = None
    model.train.return_value = None
    model.parameters.return_value = [MagicMock()]
    return model


# ============================================================================
# BenchmarkConfig Tests
# ============================================================================


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig dataclass."""

    def test_default_values(self):
        """Test that BenchmarkConfig has correct defaults."""
        config = BenchmarkConfig()
        assert config.memory_dim == 512
        assert config.memory_depth == 3
        assert config.batch_sizes == [1, 8, 32, 64, 128]
        assert config.warmup_iterations == 10
        assert config.benchmark_iterations == 100
        assert config.benchmark_forward is True
        assert config.benchmark_backward is True
        assert config.benchmark_surprise is True
        assert config.benchmark_ttt is True

    def test_custom_values(self):
        """Test BenchmarkConfig with custom values."""
        config = BenchmarkConfig(
            memory_dim=256,
            memory_depth=4,
            batch_sizes=[1, 4, 8],
            warmup_iterations=5,
            benchmark_iterations=50,
            benchmark_forward=True,
            benchmark_backward=False,
            benchmark_surprise=False,
            benchmark_ttt=False,
        )
        assert config.memory_dim == 256
        assert config.memory_depth == 4
        assert config.batch_sizes == [1, 4, 8]
        assert config.warmup_iterations == 5
        assert config.benchmark_iterations == 50
        assert config.benchmark_backward is False
        assert config.benchmark_surprise is False
        assert config.benchmark_ttt is False

    def test_batch_sizes_mutable_default_factory(self):
        """Test that batch_sizes uses a default factory for mutability isolation."""
        config1 = BenchmarkConfig()
        config2 = BenchmarkConfig()
        config1.batch_sizes.append(256)
        assert 256 in config1.batch_sizes
        assert 256 not in config2.batch_sizes

    def test_empty_batch_sizes(self):
        """Test config with empty batch_sizes."""
        config = BenchmarkConfig(batch_sizes=[])
        assert config.batch_sizes == []


# ============================================================================
# BenchmarkResult Tests
# ============================================================================


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_creation_with_all_fields(self):
        """Test BenchmarkResult creation with all required fields."""
        result = BenchmarkResult(
            backend_type="cpu",
            device_name="Intel CPU",
            operation="forward",
            batch_size=32,
            memory_dim=512,
            mean_latency_ms=1.5,
            std_latency_ms=0.2,
            min_latency_ms=1.2,
            max_latency_ms=2.0,
            p50_latency_ms=1.4,
            p95_latency_ms=1.8,
            p99_latency_ms=1.9,
            throughput_samples_per_sec=21333.33,
            peak_memory_mb=256.0,
        )
        assert result.backend_type == "cpu"
        assert result.device_name == "Intel CPU"
        assert result.operation == "forward"
        assert result.batch_size == 32
        assert result.memory_dim == 512
        assert result.mean_latency_ms == 1.5
        assert result.std_latency_ms == 0.2
        assert result.min_latency_ms == 1.2
        assert result.max_latency_ms == 2.0
        assert result.p50_latency_ms == 1.4
        assert result.p95_latency_ms == 1.8
        assert result.p99_latency_ms == 1.9
        assert result.throughput_samples_per_sec == 21333.33
        assert result.peak_memory_mb == 256.0

    def test_timestamp_default_factory(self):
        """Test that timestamp is automatically set via default factory."""
        result = BenchmarkResult(
            backend_type="cpu",
            device_name="cpu",
            operation="forward",
            batch_size=32,
            memory_dim=512,
            mean_latency_ms=1.5,
            std_latency_ms=0.2,
            min_latency_ms=1.2,
            max_latency_ms=2.0,
            p50_latency_ms=1.4,
            p95_latency_ms=1.8,
            p99_latency_ms=1.9,
            throughput_samples_per_sec=21333.33,
            peak_memory_mb=256.0,
        )
        assert result.timestamp is not None
        assert len(result.timestamp) > 0
        # Should be a valid ISO format timestamp
        datetime.fromisoformat(result.timestamp)

    def test_pytorch_version_default_factory(self):
        """Test that pytorch_version is set from torch.__version__."""
        import torch

        result = BenchmarkResult(
            backend_type="cpu",
            device_name="cpu",
            operation="forward",
            batch_size=32,
            memory_dim=512,
            mean_latency_ms=1.5,
            std_latency_ms=0.2,
            min_latency_ms=1.2,
            max_latency_ms=2.0,
            p50_latency_ms=1.4,
            p95_latency_ms=1.8,
            p99_latency_ms=1.9,
            throughput_samples_per_sec=21333.33,
            peak_memory_mb=256.0,
        )
        assert result.pytorch_version == torch.__version__

    def test_json_serializable(self):
        """Test that all fields are JSON-serializable."""
        result = BenchmarkResult(
            backend_type="gpu",
            device_name="NVIDIA A100",
            operation="ttt_step",
            batch_size=64,
            memory_dim=1024,
            mean_latency_ms=2.5,
            std_latency_ms=0.3,
            min_latency_ms=2.0,
            max_latency_ms=3.5,
            p50_latency_ms=2.4,
            p95_latency_ms=3.0,
            p99_latency_ms=3.2,
            throughput_samples_per_sec=25600.0,
            peak_memory_mb=1024.0,
        )
        d = asdict(result)
        json_str = json.dumps(d)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["backend_type"] == "gpu"
        assert parsed["operation"] == "ttt_step"


# ============================================================================
# BenchmarkSuite Tests
# ============================================================================


class TestBenchmarkSuite:
    """Tests for BenchmarkSuite dataclass."""

    def test_creation_with_empty_results(self):
        """Test BenchmarkSuite creation with empty results."""
        config = BenchmarkConfig()
        suite = BenchmarkSuite(config=config)
        assert suite.config == config
        assert suite.results == []
        assert suite.summary == {}

    def test_to_dict_serialization(self):
        """Test BenchmarkSuite.to_dict() serialization."""
        config = BenchmarkConfig(memory_dim=256, batch_sizes=[1, 8])
        suite = BenchmarkSuite(config=config)

        result = BenchmarkResult(
            backend_type="cpu",
            device_name="cpu",
            operation="forward",
            batch_size=8,
            memory_dim=256,
            mean_latency_ms=1.0,
            std_latency_ms=0.1,
            min_latency_ms=0.9,
            max_latency_ms=1.2,
            p50_latency_ms=1.0,
            p95_latency_ms=1.1,
            p99_latency_ms=1.15,
            throughput_samples_per_sec=8000.0,
            peak_memory_mb=128.0,
        )
        suite.results.append(result)
        suite.summary = {"test": "summary"}

        d = suite.to_dict()
        assert "config" in d
        assert "results" in d
        assert "summary" in d
        assert d["config"]["memory_dim"] == 256
        assert len(d["results"]) == 1
        assert d["summary"]["test"] == "summary"

    def test_to_dict_json_serializable(self):
        """Test that to_dict() returns JSON-serializable data."""
        config = BenchmarkConfig()
        suite = BenchmarkSuite(config=config)
        suite.summary = {"backends": {"cpu": {"device": "cpu"}}}

        d = suite.to_dict()
        json_str = json.dumps(d)
        assert len(json_str) > 0

    def test_multiple_results(self):
        """Test suite with multiple results."""
        config = BenchmarkConfig()
        suite = BenchmarkSuite(config=config)

        for i in range(5):
            result = BenchmarkResult(
                backend_type="cpu",
                device_name="cpu",
                operation=f"op_{i}",
                batch_size=8,
                memory_dim=512,
                mean_latency_ms=1.0 + i,
                std_latency_ms=0.1,
                min_latency_ms=0.9,
                max_latency_ms=1.2,
                p50_latency_ms=1.0,
                p95_latency_ms=1.1,
                p99_latency_ms=1.15,
                throughput_samples_per_sec=8000.0,
                peak_memory_mb=128.0,
            )
            suite.results.append(result)

        assert len(suite.results) == 5
        d = suite.to_dict()
        assert len(d["results"]) == 5


# ============================================================================
# MemoryBenchmark Tests
# ============================================================================


class TestMemoryBenchmark:
    """Tests for MemoryBenchmark class."""

    def test_init_with_default_config(self):
        """Test MemoryBenchmark initialization with default config."""
        benchmark = MemoryBenchmark()
        assert benchmark.config is not None
        assert benchmark.config.memory_dim == 512
        assert benchmark.results == []

    def test_init_with_custom_config(self):
        """Test MemoryBenchmark initialization with custom config."""
        config = BenchmarkConfig(memory_dim=256, batch_sizes=[1, 4])
        benchmark = MemoryBenchmark(config)
        assert benchmark.config.memory_dim == 256
        assert benchmark.config.batch_sizes == [1, 4]

    def test_compute_stats(self):
        """Test _compute_stats method."""
        benchmark = MemoryBenchmark()
        latencies = [1.0, 1.5, 2.0, 1.2, 1.8, 1.3, 1.6, 1.4, 1.7, 1.9]
        batch_size = 8

        stats = benchmark._compute_stats(latencies, batch_size)

        assert "mean_latency_ms" in stats
        assert "std_latency_ms" in stats
        assert "min_latency_ms" in stats
        assert "max_latency_ms" in stats
        assert "p50_latency_ms" in stats
        assert "p95_latency_ms" in stats
        assert "p99_latency_ms" in stats
        assert "throughput_samples_per_sec" in stats

        assert stats["min_latency_ms"] == 1.0
        assert stats["max_latency_ms"] == 2.0
        assert stats["throughput_samples_per_sec"] > 0

    def test_compute_stats_single_value(self):
        """Test _compute_stats with single value (std should be 0)."""
        benchmark = MemoryBenchmark()
        latencies = [1.5]
        stats = benchmark._compute_stats(latencies, batch_size=1)
        assert stats["std_latency_ms"] == 0.0

    def test_measure_latencies(self):
        """Test _measure_latencies method."""
        benchmark = MemoryBenchmark()
        call_count = 0

        def mock_func():
            nonlocal call_count
            call_count += 1

        latencies = benchmark._measure_latencies(mock_func, warmup=3, iterations=5)

        assert len(latencies) == 5
        assert all(isinstance(lat, float) for lat in latencies)
        assert call_count == 8  # 3 warmup + 5 iterations


class TestMemoryBenchmarkForward:
    """Tests for MemoryBenchmark.benchmark_forward method."""

    def test_benchmark_forward(self, mock_backend, mock_model):
        """Test benchmark_forward method."""
        config = BenchmarkConfig(warmup_iterations=2, benchmark_iterations=5)
        benchmark = MemoryBenchmark(config)

        result = benchmark.benchmark_forward(mock_backend, mock_model, batch_size=8)

        assert result.backend_type == "cpu"
        assert result.operation == "forward"
        assert result.batch_size == 8
        assert result.mean_latency_ms >= 0
        mock_backend.forward.assert_called()
        mock_backend.synchronize.assert_called()


class TestMemoryBenchmarkBackward:
    """Tests for MemoryBenchmark.benchmark_backward method."""

    def test_benchmark_backward(self, mock_backend, mock_model):
        """Test benchmark_backward method."""
        import torch as torch_mod

        # Create mock that returns real tensors for mse_loss compatibility
        def mock_forward(model, inputs, **kwargs):
            batch_size = inputs.shape[0]
            dim = inputs.shape[1]
            return torch_mod.randn(batch_size, dim)

        mock_backend.forward.side_effect = mock_forward

        config = BenchmarkConfig(warmup_iterations=2, benchmark_iterations=5)
        benchmark = MemoryBenchmark(config)

        result = benchmark.benchmark_backward(mock_backend, mock_model, batch_size=8)

        assert result.backend_type == "cpu"
        assert result.operation == "backward"
        assert result.batch_size == 8
        mock_backend.backward.assert_called()
        mock_backend.synchronize.assert_called()


class TestMemoryBenchmarkSurprise:
    """Tests for MemoryBenchmark.benchmark_surprise method."""

    def test_benchmark_surprise(self, mock_backend, mock_model):
        """Test benchmark_surprise method."""
        config = BenchmarkConfig(warmup_iterations=2, benchmark_iterations=5)
        benchmark = MemoryBenchmark(config)

        result = benchmark.benchmark_surprise(mock_backend, mock_model, batch_size=8)

        assert result.backend_type == "cpu"
        assert result.operation == "surprise"
        assert result.batch_size == 8
        mock_backend.compute_surprise.assert_called()
        mock_backend.synchronize.assert_called()


class TestMemoryBenchmarkTTTStep:
    """Tests for MemoryBenchmark.benchmark_ttt_step method."""

    def test_benchmark_ttt_step(self, mock_backend):
        """Test benchmark_ttt_step method."""
        import torch as torch_mod

        from src.services.models import DeepMLPMemory, MemoryConfig

        # Create a real model for this test since Adam optimizer needs real parameters
        mem_config = MemoryConfig(dim=512, depth=2)
        real_model = DeepMLPMemory(mem_config)

        # Create mock that returns real tensors for mse_loss compatibility
        def mock_forward(model, inputs, **kwargs):
            batch_size = inputs.shape[0]
            dim = inputs.shape[1]
            return torch_mod.randn(batch_size, dim, requires_grad=True)

        mock_backend.forward.side_effect = mock_forward

        config = BenchmarkConfig(warmup_iterations=2, benchmark_iterations=5)
        benchmark = MemoryBenchmark(config)

        result = benchmark.benchmark_ttt_step(mock_backend, real_model, batch_size=8)

        assert result.backend_type == "cpu"
        assert result.operation == "ttt_step"
        assert result.batch_size == 8
        mock_backend.forward.assert_called()
        mock_backend.backward.assert_called()
        mock_backend.synchronize.assert_called()


class TestMemoryBenchmarkRunBackend:
    """Tests for MemoryBenchmark.run_backend_benchmarks method."""

    def test_run_backend_benchmarks_all_operations(self, mock_backend):
        """Test run_backend_benchmarks with all operations enabled."""
        import torch as torch_mod

        from src.services.models import DeepMLPMemory, MemoryConfig

        # Create real model for operations that need real tensors
        mem_config = MemoryConfig(dim=512, depth=2)
        real_model = DeepMLPMemory(mem_config)

        # Create mock that returns real tensors for mse_loss compatibility
        def mock_forward(model, inputs, **kwargs):
            batch_size = inputs.shape[0]
            dim = inputs.shape[1]
            return torch_mod.randn(batch_size, dim, requires_grad=True)

        mock_backend.forward.side_effect = mock_forward

        with patch.object(MemoryBenchmark, "_create_model", return_value=real_model):
            config = BenchmarkConfig(
                batch_sizes=[8],
                warmup_iterations=1,
                benchmark_iterations=2,
                benchmark_forward=True,
                benchmark_backward=True,
                benchmark_surprise=True,
                benchmark_ttt=True,
            )
            benchmark = MemoryBenchmark(config)

            results = benchmark.run_backend_benchmarks(mock_backend)

            # Should have 4 results (one per operation)
            assert len(results) == 4
            operations = {r.operation for r in results}
            assert operations == {"forward", "backward", "surprise", "ttt_step"}

    def test_run_backend_benchmarks_selective_operations(
        self, mock_backend, mock_model
    ):
        """Test run_backend_benchmarks with selective operations."""
        with patch.object(MemoryBenchmark, "_create_model", return_value=mock_model):
            config = BenchmarkConfig(
                batch_sizes=[8],
                warmup_iterations=1,
                benchmark_iterations=2,
                benchmark_forward=True,
                benchmark_backward=False,
                benchmark_surprise=False,
                benchmark_ttt=False,
            )
            benchmark = MemoryBenchmark(config)

            results = benchmark.run_backend_benchmarks(mock_backend)

            # Should only have forward results
            assert len(results) == 1
            assert results[0].operation == "forward"

    def test_run_backend_benchmarks_multiple_batch_sizes(
        self, mock_backend, mock_model
    ):
        """Test run_backend_benchmarks with multiple batch sizes."""
        with patch.object(MemoryBenchmark, "_create_model", return_value=mock_model):
            config = BenchmarkConfig(
                batch_sizes=[1, 8, 32],
                warmup_iterations=1,
                benchmark_iterations=2,
                benchmark_forward=True,
                benchmark_backward=False,
                benchmark_surprise=False,
                benchmark_ttt=False,
            )
            benchmark = MemoryBenchmark(config)

            results = benchmark.run_backend_benchmarks(mock_backend)

            # Should have 3 results (one per batch size)
            assert len(results) == 3
            batch_sizes = {r.batch_size for r in results}
            assert batch_sizes == {1, 8, 32}


class TestMemoryBenchmarkRunAll:
    """Tests for MemoryBenchmark.run_all_benchmarks method."""

    def test_run_all_benchmarks(self, mock_backend, mock_gpu_backend, mock_model):
        """Test run_all_benchmarks method."""
        with patch.object(MemoryBenchmark, "_create_model", return_value=mock_model):
            with patch(
                "src.services.memory_backends.benchmark.create_cpu_backend",
                return_value=mock_backend,
            ):
                with patch(
                    "src.services.memory_backends.benchmark.create_gpu_backend",
                    return_value=mock_gpu_backend,
                ):
                    config = BenchmarkConfig(
                        batch_sizes=[8],
                        warmup_iterations=1,
                        benchmark_iterations=2,
                        benchmark_forward=True,
                        benchmark_backward=False,
                        benchmark_surprise=False,
                        benchmark_ttt=False,
                    )
                    benchmark = MemoryBenchmark(config)

                    suite = benchmark.run_all_benchmarks()

                    assert isinstance(suite, BenchmarkSuite)
                    assert suite.config == config
                    # CPU + GPU results
                    assert len(suite.results) == 2
                    mock_backend.initialize.assert_called()
                    mock_backend.cleanup.assert_called()
                    mock_gpu_backend.initialize.assert_called()
                    mock_gpu_backend.cleanup.assert_called()

    def test_run_all_benchmarks_no_gpu(self, mock_backend, mock_model):
        """Test run_all_benchmarks when no GPU is available."""
        # GPU backend that reports no GPU
        mock_gpu_backend = MagicMock()
        mock_gpu_backend.get_backend_info.return_value = {
            "device_name": "cpu",
            "gpu_type": "none",
        }
        mock_gpu_backend.initialize.return_value = None
        mock_gpu_backend.cleanup.return_value = None

        with patch.object(MemoryBenchmark, "_create_model", return_value=mock_model):
            with patch(
                "src.services.memory_backends.benchmark.create_cpu_backend",
                return_value=mock_backend,
            ):
                with patch(
                    "src.services.memory_backends.benchmark.create_gpu_backend",
                    return_value=mock_gpu_backend,
                ):
                    config = BenchmarkConfig(
                        batch_sizes=[8],
                        warmup_iterations=1,
                        benchmark_iterations=2,
                        benchmark_forward=True,
                        benchmark_backward=False,
                        benchmark_surprise=False,
                        benchmark_ttt=False,
                    )
                    benchmark = MemoryBenchmark(config)

                    suite = benchmark.run_all_benchmarks()

                    # Only CPU results (GPU skipped)
                    assert len(suite.results) == 1
                    assert suite.results[0].backend_type == "cpu"


class TestComputeSummary:
    """Tests for MemoryBenchmark._compute_summary method."""

    def test_compute_summary_empty_results(self):
        """Test _compute_summary with empty results."""
        benchmark = MemoryBenchmark()
        summary = benchmark._compute_summary([])

        assert "timestamp" in summary
        assert "pytorch_version" in summary
        assert "backends" in summary
        assert summary["backends"] == {}

    def test_compute_summary_single_backend(self):
        """Test _compute_summary with single backend."""
        results = [
            BenchmarkResult(
                backend_type="cpu",
                device_name="Intel CPU",
                operation="forward",
                batch_size=8,
                memory_dim=512,
                mean_latency_ms=1.0,
                std_latency_ms=0.1,
                min_latency_ms=0.9,
                max_latency_ms=1.2,
                p50_latency_ms=1.0,
                p95_latency_ms=1.1,
                p99_latency_ms=1.15,
                throughput_samples_per_sec=8000.0,
                peak_memory_mb=128.0,
            )
        ]

        benchmark = MemoryBenchmark()
        summary = benchmark._compute_summary(results)

        assert "cpu" in summary["backends"]
        assert summary["backends"]["cpu"]["device_name"] == "Intel CPU"
        assert "forward_batch8" in summary["backends"]["cpu"]["operations"]

    def test_compute_summary_gpu_speedup(self):
        """Test _compute_summary with GPU speedup calculation."""
        results = [
            BenchmarkResult(
                backend_type="cpu",
                device_name="Intel CPU",
                operation="forward",
                batch_size=8,
                memory_dim=512,
                mean_latency_ms=10.0,
                std_latency_ms=0.1,
                min_latency_ms=9.0,
                max_latency_ms=11.0,
                p50_latency_ms=10.0,
                p95_latency_ms=10.5,
                p99_latency_ms=10.8,
                throughput_samples_per_sec=800.0,
                peak_memory_mb=128.0,
            ),
            BenchmarkResult(
                backend_type="gpu",
                device_name="NVIDIA GPU",
                operation="forward",
                batch_size=8,
                memory_dim=512,
                mean_latency_ms=2.0,
                std_latency_ms=0.1,
                min_latency_ms=1.8,
                max_latency_ms=2.2,
                p50_latency_ms=2.0,
                p95_latency_ms=2.1,
                p99_latency_ms=2.15,
                throughput_samples_per_sec=4000.0,
                peak_memory_mb=256.0,
            ),
        ]

        benchmark = MemoryBenchmark()
        summary = benchmark._compute_summary(results)

        assert "gpu_speedup" in summary
        assert "forward_batch8" in summary["gpu_speedup"]
        assert summary["gpu_speedup"]["forward_batch8"] == 5.0  # 10.0 / 2.0


# ============================================================================
# run_benchmarks Function Tests
# ============================================================================


class TestRunBenchmarks:
    """Tests for run_benchmarks function."""

    def test_run_benchmarks_default_config(self, mock_backend, mock_model):
        """Test run_benchmarks with default config."""
        mock_gpu_backend = MagicMock()
        mock_gpu_backend.get_backend_info.return_value = {
            "device_name": "cpu",
            "gpu_type": "none",
        }
        mock_gpu_backend.initialize.return_value = None
        mock_gpu_backend.cleanup.return_value = None

        with patch.object(MemoryBenchmark, "_create_model", return_value=mock_model):
            with patch(
                "src.services.memory_backends.benchmark.create_cpu_backend",
                return_value=mock_backend,
            ):
                with patch(
                    "src.services.memory_backends.benchmark.create_gpu_backend",
                    return_value=mock_gpu_backend,
                ):
                    config = BenchmarkConfig(
                        batch_sizes=[8],
                        warmup_iterations=1,
                        benchmark_iterations=2,
                        benchmark_forward=True,
                        benchmark_backward=False,
                        benchmark_surprise=False,
                        benchmark_ttt=False,
                    )

                    suite = run_benchmarks(config=config)

                    assert isinstance(suite, BenchmarkSuite)

    def test_run_benchmarks_with_output_file(self, mock_backend, mock_model, tmp_path):
        """Test run_benchmarks with output file."""
        mock_gpu_backend = MagicMock()
        mock_gpu_backend.get_backend_info.return_value = {
            "device_name": "cpu",
            "gpu_type": "none",
        }
        mock_gpu_backend.initialize.return_value = None
        mock_gpu_backend.cleanup.return_value = None

        output_file = str(tmp_path / "benchmark_results.json")

        with patch.object(MemoryBenchmark, "_create_model", return_value=mock_model):
            with patch(
                "src.services.memory_backends.benchmark.create_cpu_backend",
                return_value=mock_backend,
            ):
                with patch(
                    "src.services.memory_backends.benchmark.create_gpu_backend",
                    return_value=mock_gpu_backend,
                ):
                    config = BenchmarkConfig(
                        batch_sizes=[8],
                        warmup_iterations=1,
                        benchmark_iterations=2,
                        benchmark_forward=True,
                        benchmark_backward=False,
                        benchmark_surprise=False,
                        benchmark_ttt=False,
                    )

                    suite = run_benchmarks(config=config, output_file=output_file)

                    assert os.path.exists(output_file)
                    with open(output_file, "r") as f:
                        data = json.load(f)
                    assert "config" in data
                    assert "results" in data
                    assert "summary" in data

    def test_run_benchmarks_prints_summary(self, mock_backend, mock_model, capsys):
        """Test that run_benchmarks prints summary output."""
        mock_gpu_backend = MagicMock()
        mock_gpu_backend.get_backend_info.return_value = {
            "device_name": "cpu",
            "gpu_type": "none",
        }
        mock_gpu_backend.initialize.return_value = None
        mock_gpu_backend.cleanup.return_value = None

        with patch.object(MemoryBenchmark, "_create_model", return_value=mock_model):
            with patch(
                "src.services.memory_backends.benchmark.create_cpu_backend",
                return_value=mock_backend,
            ):
                with patch(
                    "src.services.memory_backends.benchmark.create_gpu_backend",
                    return_value=mock_gpu_backend,
                ):
                    config = BenchmarkConfig(
                        batch_sizes=[8],
                        warmup_iterations=1,
                        benchmark_iterations=2,
                        benchmark_forward=True,
                        benchmark_backward=False,
                        benchmark_surprise=False,
                        benchmark_ttt=False,
                    )

                    run_benchmarks(config=config)

                    captured = capsys.readouterr()
                    assert "BENCHMARK SUMMARY" in captured.out
                    assert "PyTorch Version" in captured.out


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases in the benchmark module."""

    def test_zero_iterations(self):
        """Test config with zero iterations."""
        config = BenchmarkConfig(warmup_iterations=0, benchmark_iterations=0)
        assert config.warmup_iterations == 0
        assert config.benchmark_iterations == 0

    def test_large_batch_sizes(self):
        """Test config with large batch sizes."""
        config = BenchmarkConfig(batch_sizes=[1024, 2048, 4096])
        assert 4096 in config.batch_sizes

    def test_high_memory_dim(self):
        """Test config with high memory dimension."""
        config = BenchmarkConfig(memory_dim=2048)
        assert config.memory_dim == 2048

    def test_throughput_calculation(self):
        """Test throughput calculation from latency."""
        benchmark = MemoryBenchmark()
        latencies = [2.0, 2.0, 2.0, 2.0, 2.0]  # 2ms each
        batch_size = 32

        stats = benchmark._compute_stats(latencies, batch_size)

        # throughput = batch_size * 1000 / mean_latency_ms = 32 * 1000 / 2.0 = 16000
        assert stats["throughput_samples_per_sec"] == 16000.0


class TestCreateModel:
    """Tests for MemoryBenchmark._create_model method."""

    def test_create_model_uses_config(self):
        """Test that _create_model uses config values."""
        mock_memory_config = MagicMock()
        mock_deep_mlp = MagicMock()

        with patch(
            "src.services.memory_backends.benchmark.MemoryConfig",
            return_value=mock_memory_config,
        ) as mock_config_class:
            with patch(
                "src.services.memory_backends.benchmark.DeepMLPMemory",
                return_value=mock_deep_mlp,
            ) as mock_model_class:
                config = BenchmarkConfig(memory_dim=256, memory_depth=4)
                benchmark = MemoryBenchmark(config)

                model = benchmark._create_model()

                mock_config_class.assert_called_with(dim=256, depth=4)
                mock_model_class.assert_called_with(mock_memory_config)


class TestPrintOutput:
    """Tests for print output during benchmarking."""

    def test_run_backend_benchmarks_prints_progress(self, mock_backend, capsys):
        """Test that run_backend_benchmarks prints progress."""
        import torch as torch_mod

        from src.services.models import DeepMLPMemory, MemoryConfig

        # Create real model for operations that need real tensors
        mem_config = MemoryConfig(dim=512, depth=2)
        real_model = DeepMLPMemory(mem_config)

        # Create mock that returns real tensors for mse_loss compatibility
        def mock_forward(model, inputs, **kwargs):
            batch_size = inputs.shape[0]
            dim = inputs.shape[1]
            return torch_mod.randn(batch_size, dim, requires_grad=True)

        mock_backend.forward.side_effect = mock_forward

        with patch.object(MemoryBenchmark, "_create_model", return_value=real_model):
            config = BenchmarkConfig(
                batch_sizes=[8],
                warmup_iterations=1,
                benchmark_iterations=2,
                benchmark_forward=True,
                benchmark_backward=True,
                benchmark_surprise=True,
                benchmark_ttt=True,
            )
            benchmark = MemoryBenchmark(config)

            benchmark.run_backend_benchmarks(mock_backend)

            captured = capsys.readouterr()
            assert "Forward" in captured.out
            assert "Backward" in captured.out
            assert "Surprise" in captured.out
            assert "TTT Step" in captured.out


class TestSummaryPrinting:
    """Tests for summary printing with GPU speedup."""

    def test_prints_gpu_speedup_when_available(
        self, mock_backend, mock_gpu_backend, mock_model, capsys
    ):
        """Test that GPU speedup is printed when GPU results are available."""
        with patch.object(MemoryBenchmark, "_create_model", return_value=mock_model):
            with patch(
                "src.services.memory_backends.benchmark.create_cpu_backend",
                return_value=mock_backend,
            ):
                with patch(
                    "src.services.memory_backends.benchmark.create_gpu_backend",
                    return_value=mock_gpu_backend,
                ):
                    config = BenchmarkConfig(
                        batch_sizes=[8],
                        warmup_iterations=1,
                        benchmark_iterations=2,
                        benchmark_forward=True,
                        benchmark_backward=False,
                        benchmark_surprise=False,
                        benchmark_ttt=False,
                    )

                    run_benchmarks(config=config)

                    captured = capsys.readouterr()
                    assert "GPU Speedup vs CPU" in captured.out


# ============================================================================
# Percentile Calculation Tests
# ============================================================================


class TestPercentileCalculation:
    """Tests for percentile calculation accuracy."""

    def test_p50_calculation(self):
        """Test p50 (median) calculation."""
        benchmark = MemoryBenchmark()
        # 100 values from 1 to 100
        latencies = list(range(1, 101))
        stats = benchmark._compute_stats(latencies, batch_size=1)

        # p50 should be around index 50 (value 51)
        assert stats["p50_latency_ms"] == 51

    def test_p95_calculation(self):
        """Test p95 calculation."""
        benchmark = MemoryBenchmark()
        latencies = list(range(1, 101))
        stats = benchmark._compute_stats(latencies, batch_size=1)

        # p95 should be at index 95 (value 96)
        assert stats["p95_latency_ms"] == 96

    def test_p99_calculation(self):
        """Test p99 calculation."""
        benchmark = MemoryBenchmark()
        latencies = list(range(1, 101))
        stats = benchmark._compute_stats(latencies, batch_size=1)

        # p99 should be at index 99 (value 100)
        assert stats["p99_latency_ms"] == 100


# ============================================================================
# Additional Coverage Tests
# ============================================================================


class TestBenchmarkResultOperations:
    """Tests for different operation types in benchmark results."""

    def test_backward_result(self):
        """Test result for backward operation."""
        result = BenchmarkResult(
            backend_type="cpu",
            device_name="cpu",
            operation="backward",
            batch_size=8,
            memory_dim=512,
            mean_latency_ms=2.0,
            std_latency_ms=0.2,
            min_latency_ms=1.8,
            max_latency_ms=2.4,
            p50_latency_ms=2.0,
            p95_latency_ms=2.2,
            p99_latency_ms=2.3,
            throughput_samples_per_sec=4000.0,
            peak_memory_mb=256.0,
        )
        assert result.operation == "backward"
        assert result.peak_memory_mb >= 128.0

    def test_surprise_result(self):
        """Test result for surprise operation."""
        result = BenchmarkResult(
            backend_type="cpu",
            device_name="cpu",
            operation="surprise",
            batch_size=8,
            memory_dim=512,
            mean_latency_ms=1.5,
            std_latency_ms=0.15,
            min_latency_ms=1.3,
            max_latency_ms=1.8,
            p50_latency_ms=1.5,
            p95_latency_ms=1.7,
            p99_latency_ms=1.75,
            throughput_samples_per_sec=5333.33,
            peak_memory_mb=192.0,
        )
        assert result.operation == "surprise"

    def test_ttt_step_result(self):
        """Test result for TTT step operation."""
        result = BenchmarkResult(
            backend_type="gpu",
            device_name="NVIDIA A100",
            operation="ttt_step",
            batch_size=64,
            memory_dim=1024,
            mean_latency_ms=5.0,
            std_latency_ms=0.5,
            min_latency_ms=4.5,
            max_latency_ms=6.0,
            p50_latency_ms=5.0,
            p95_latency_ms=5.5,
            p99_latency_ms=5.8,
            throughput_samples_per_sec=12800.0,
            peak_memory_mb=2048.0,
        )
        assert result.operation == "ttt_step"
        assert result.peak_memory_mb > 256.0


class TestThroughputCalculation:
    """Tests for throughput calculation."""

    def test_throughput_inverse_to_latency(self):
        """Test that throughput is inversely proportional to latency."""
        batch_size = 8

        result_fast = BenchmarkResult(
            backend_type="gpu",
            device_name="gpu",
            operation="forward",
            batch_size=batch_size,
            memory_dim=512,
            mean_latency_ms=1.0,
            std_latency_ms=0.1,
            min_latency_ms=0.9,
            max_latency_ms=1.1,
            p50_latency_ms=1.0,
            p95_latency_ms=1.05,
            p99_latency_ms=1.08,
            throughput_samples_per_sec=8000.0,  # 8 * 1000 / 1.0
            peak_memory_mb=256.0,
        )

        result_slow = BenchmarkResult(
            backend_type="cpu",
            device_name="cpu",
            operation="forward",
            batch_size=batch_size,
            memory_dim=512,
            mean_latency_ms=4.0,
            std_latency_ms=0.4,
            min_latency_ms=3.6,
            max_latency_ms=4.4,
            p50_latency_ms=4.0,
            p95_latency_ms=4.2,
            p99_latency_ms=4.3,
            throughput_samples_per_sec=2000.0,  # 8 * 1000 / 4.0
            peak_memory_mb=128.0,
        )

        # Faster (lower latency) should have higher throughput
        assert (
            result_fast.throughput_samples_per_sec
            > result_slow.throughput_samples_per_sec
        )
        # And specifically, should be 4x higher (1/4 the latency)
        assert (
            result_fast.throughput_samples_per_sec
            == 4 * result_slow.throughput_samples_per_sec
        )


class TestOutputFileSerialization:
    """Tests for output file serialization."""

    def test_save_to_file(self, tmp_path):
        """Test saving benchmark results to a file."""
        config = BenchmarkConfig(memory_dim=256, batch_sizes=[1, 8])
        suite = BenchmarkSuite(config=config)

        result = BenchmarkResult(
            backend_type="cpu",
            device_name="cpu",
            operation="forward",
            batch_size=8,
            memory_dim=256,
            mean_latency_ms=1.0,
            std_latency_ms=0.1,
            min_latency_ms=0.9,
            max_latency_ms=1.2,
            p50_latency_ms=1.0,
            p95_latency_ms=1.1,
            p99_latency_ms=1.15,
            throughput_samples_per_sec=8000.0,
            peak_memory_mb=128.0,
        )
        suite.results.append(result)

        output_file = str(tmp_path / "benchmark_results.json")
        with open(output_file, "w") as f:
            json.dump(suite.to_dict(), f, indent=2)

        assert os.path.exists(output_file)

        with open(output_file, "r") as f:
            data = json.load(f)

        assert "config" in data
        assert "results" in data
        assert data["config"]["memory_dim"] == 256
        assert len(data["results"]) == 1

    def test_load_from_file(self, tmp_path):
        """Test loading benchmark results from a file."""
        output_file = str(tmp_path / "benchmark_results.json")

        data = {
            "config": {"memory_dim": 512, "batch_sizes": [1, 8]},
            "results": [
                {
                    "backend_type": "cpu",
                    "operation": "forward",
                    "mean_latency_ms": 1.5,
                }
            ],
            "summary": {"test": "value"},
        }

        with open(output_file, "w") as f:
            json.dump(data, f)

        with open(output_file, "r") as f:
            loaded = json.load(f)

        assert loaded["config"]["memory_dim"] == 512
        assert len(loaded["results"]) == 1
        assert loaded["summary"]["test"] == "value"
