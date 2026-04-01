"""Benchmarking module for neural memory backends.

This module provides comprehensive benchmarking capabilities to compare
performance across different hardware backends (CPU, GPU/MPS, Inferentia2).

Usage:
    python -m src.services.memory_backends.benchmark

Or programmatically:
    from src.services.memory_backends.benchmark import run_benchmarks
    results = run_benchmarks()
"""

import gc
import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import torch

from ..models import DeepMLPMemory, MemoryConfig
from .base import MemoryBackend
from .cpu_backend import create_cpu_backend
from .gpu_backend import create_gpu_backend


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    # Model configuration
    memory_dim: int = 512
    memory_depth: int = 3

    # Batch sizes to test
    batch_sizes: List[int] = field(default_factory=lambda: [1, 8, 32, 64, 128])

    # Benchmark parameters
    warmup_iterations: int = 10
    benchmark_iterations: int = 100

    # Operations to benchmark
    benchmark_forward: bool = True
    benchmark_backward: bool = True
    benchmark_surprise: bool = True
    benchmark_ttt: bool = True


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    backend_type: str
    device_name: str
    operation: str
    batch_size: int
    memory_dim: int

    # Latency statistics (milliseconds)
    mean_latency_ms: float
    std_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    # Throughput
    throughput_samples_per_sec: float

    # Memory usage (MB)
    peak_memory_mb: float

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    pytorch_version: str = field(default_factory=lambda: torch.__version__)


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""

    config: BenchmarkConfig
    results: List[BenchmarkResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "config": asdict(self.config),
            "results": [asdict(r) for r in self.results],
            "summary": self.summary,
        }


class MemoryBenchmark:
    """Benchmark runner for neural memory backends."""

    def __init__(self, config: Optional[BenchmarkConfig] = None) -> None:
        """Initialize benchmark runner.

        Args:
            config: Benchmark configuration
        """
        self.config = config or BenchmarkConfig()
        self.results: List[BenchmarkResult] = []

    def _create_model(self) -> DeepMLPMemory:
        """Create a fresh model for benchmarking."""
        mem_config = MemoryConfig(
            dim=self.config.memory_dim,
            depth=self.config.memory_depth,
        )
        return DeepMLPMemory(mem_config)

    def _measure_latencies(
        self,
        func,
        warmup: int,
        iterations: int,
    ) -> List[float]:
        """Measure latencies for a function.

        Args:
            func: Function to benchmark (should accept no arguments)
            warmup: Number of warmup iterations
            iterations: Number of measurement iterations

        Returns:
            List of latencies in milliseconds
        """
        # Warmup
        for _ in range(warmup):
            func()

        # Force garbage collection before measurement
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Measure
        latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            func()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms

        return latencies

    def _compute_stats(
        self,
        latencies: List[float],
        batch_size: int,
    ) -> Dict[str, float]:
        """Compute statistics from latency measurements.

        Args:
            latencies: List of latency measurements in ms
            batch_size: Batch size used

        Returns:
            Dictionary with statistics
        """
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        return {
            "mean_latency_ms": statistics.mean(latencies),
            "std_latency_ms": statistics.stdev(latencies) if n > 1 else 0.0,
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "p50_latency_ms": sorted_latencies[n // 2],
            "p95_latency_ms": sorted_latencies[int(n * 0.95)],
            "p99_latency_ms": sorted_latencies[int(n * 0.99)],
            "throughput_samples_per_sec": (
                batch_size * 1000 / statistics.mean(latencies)
            ),
        }

    def benchmark_forward(
        self,
        backend: MemoryBackend,
        model: DeepMLPMemory,
        batch_size: int,
    ) -> BenchmarkResult:
        """Benchmark forward pass.

        Args:
            backend: Memory backend to use
            model: Model to benchmark
            batch_size: Batch size for input

        Returns:
            Benchmark result
        """
        # Create input tensor on device
        inputs = torch.randn(batch_size, self.config.memory_dim)
        inputs = backend.to_device(inputs)
        model = model.to(backend.device)
        model.eval()

        def forward_fn() -> None:
            with torch.no_grad():
                _ = backend.forward(model, inputs, use_persistent=True)
            backend.synchronize()

        latencies = self._measure_latencies(
            forward_fn,
            self.config.warmup_iterations,
            self.config.benchmark_iterations,
        )

        stats = self._compute_stats(latencies, batch_size)
        memory = backend.get_memory_usage()

        return BenchmarkResult(
            backend_type=backend.config.backend_type.value,
            device_name=backend.get_backend_info().get(
                "device_name", str(backend.device)
            ),
            operation="forward",
            batch_size=batch_size,
            memory_dim=self.config.memory_dim,
            peak_memory_mb=memory.get("peak_mb", 0.0),
            mean_latency_ms=stats["mean_latency_ms"],
            std_latency_ms=stats["std_latency_ms"],
            min_latency_ms=stats["min_latency_ms"],
            max_latency_ms=stats["max_latency_ms"],
            p50_latency_ms=stats["p50_latency_ms"],
            p95_latency_ms=stats["p95_latency_ms"],
            p99_latency_ms=stats["p99_latency_ms"],
            throughput_samples_per_sec=stats["throughput_samples_per_sec"],
        )

    def benchmark_backward(
        self,
        backend: MemoryBackend,
        model: DeepMLPMemory,
        batch_size: int,
    ) -> BenchmarkResult:
        """Benchmark backward pass (gradient computation).

        Args:
            backend: Memory backend to use
            model: Model to benchmark
            batch_size: Batch size for input

        Returns:
            Benchmark result
        """
        model = model.to(backend.device)
        model.train()

        def backward_fn() -> None:
            inputs = torch.randn(batch_size, self.config.memory_dim)
            targets = torch.randn(batch_size, self.config.memory_dim)
            inputs = backend.to_device(inputs)
            targets = backend.to_device(targets)

            output = backend.forward(model, inputs, use_persistent=False)
            loss = torch.nn.functional.mse_loss(output, targets)
            backend.backward(loss, model)
            backend.synchronize()

        latencies = self._measure_latencies(
            backward_fn,
            self.config.warmup_iterations,
            self.config.benchmark_iterations,
        )

        stats = self._compute_stats(latencies, batch_size)
        memory = backend.get_memory_usage()

        return BenchmarkResult(
            backend_type=backend.config.backend_type.value,
            device_name=backend.get_backend_info().get(
                "device_name", str(backend.device)
            ),
            operation="backward",
            batch_size=batch_size,
            memory_dim=self.config.memory_dim,
            peak_memory_mb=memory.get("peak_mb", 0.0),
            mean_latency_ms=stats["mean_latency_ms"],
            std_latency_ms=stats["std_latency_ms"],
            min_latency_ms=stats["min_latency_ms"],
            max_latency_ms=stats["max_latency_ms"],
            p50_latency_ms=stats["p50_latency_ms"],
            p95_latency_ms=stats["p95_latency_ms"],
            p99_latency_ms=stats["p99_latency_ms"],
            throughput_samples_per_sec=stats["throughput_samples_per_sec"],
        )

    def benchmark_surprise(
        self,
        backend: MemoryBackend,
        model: DeepMLPMemory,
        batch_size: int,
    ) -> BenchmarkResult:
        """Benchmark surprise computation.

        Args:
            backend: Memory backend to use
            model: Model to benchmark
            batch_size: Batch size for input

        Returns:
            Benchmark result
        """
        model = model.to(backend.device)

        def surprise_fn() -> None:
            inputs = torch.randn(batch_size, self.config.memory_dim)
            targets = torch.randn(batch_size, self.config.memory_dim)
            inputs = backend.to_device(inputs)
            targets = backend.to_device(targets)

            _ = backend.compute_surprise(model, inputs, targets)
            backend.synchronize()

        latencies = self._measure_latencies(
            surprise_fn,
            self.config.warmup_iterations,
            self.config.benchmark_iterations,
        )

        stats = self._compute_stats(latencies, batch_size)
        memory = backend.get_memory_usage()

        return BenchmarkResult(
            backend_type=backend.config.backend_type.value,
            device_name=backend.get_backend_info().get(
                "device_name", str(backend.device)
            ),
            operation="surprise",
            batch_size=batch_size,
            memory_dim=self.config.memory_dim,
            peak_memory_mb=memory.get("peak_mb", 0.0),
            mean_latency_ms=stats["mean_latency_ms"],
            std_latency_ms=stats["std_latency_ms"],
            min_latency_ms=stats["min_latency_ms"],
            max_latency_ms=stats["max_latency_ms"],
            p50_latency_ms=stats["p50_latency_ms"],
            p95_latency_ms=stats["p95_latency_ms"],
            p99_latency_ms=stats["p99_latency_ms"],
            throughput_samples_per_sec=stats["throughput_samples_per_sec"],
        )

    def benchmark_ttt_step(
        self,
        backend: MemoryBackend,
        model: DeepMLPMemory,
        batch_size: int,
    ) -> BenchmarkResult:
        """Benchmark full TTT step (forward + backward + optimizer).

        Args:
            backend: Memory backend to use
            model: Model to benchmark
            batch_size: Batch size for input

        Returns:
            Benchmark result
        """
        model = model.to(backend.device)
        model.train()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

        def ttt_fn() -> None:
            inputs = torch.randn(batch_size, self.config.memory_dim)
            targets = torch.randn(batch_size, self.config.memory_dim)
            inputs = backend.to_device(inputs)
            targets = backend.to_device(targets)

            output = backend.forward(model, inputs, use_persistent=False)
            loss = torch.nn.functional.mse_loss(output, targets)
            backend.backward(loss, model, optimizer)
            backend.synchronize()

        latencies = self._measure_latencies(
            ttt_fn,
            self.config.warmup_iterations,
            self.config.benchmark_iterations,
        )

        stats = self._compute_stats(latencies, batch_size)
        memory = backend.get_memory_usage()

        return BenchmarkResult(
            backend_type=backend.config.backend_type.value,
            device_name=backend.get_backend_info().get(
                "device_name", str(backend.device)
            ),
            operation="ttt_step",
            batch_size=batch_size,
            memory_dim=self.config.memory_dim,
            peak_memory_mb=memory.get("peak_mb", 0.0),
            mean_latency_ms=stats["mean_latency_ms"],
            std_latency_ms=stats["std_latency_ms"],
            min_latency_ms=stats["min_latency_ms"],
            max_latency_ms=stats["max_latency_ms"],
            p50_latency_ms=stats["p50_latency_ms"],
            p95_latency_ms=stats["p95_latency_ms"],
            p99_latency_ms=stats["p99_latency_ms"],
            throughput_samples_per_sec=stats["throughput_samples_per_sec"],
        )

    def run_backend_benchmarks(
        self,
        backend: MemoryBackend,
    ) -> List[BenchmarkResult]:
        """Run all benchmarks for a single backend.

        Args:
            backend: Memory backend to benchmark

        Returns:
            List of benchmark results
        """
        results = []

        for batch_size in self.config.batch_sizes:
            # Create fresh model for each batch size
            model = self._create_model()

            if self.config.benchmark_forward:
                result = self.benchmark_forward(backend, model, batch_size)
                results.append(result)
                print(f"  Forward (batch={batch_size}): {result.mean_latency_ms:.3f}ms")

            if self.config.benchmark_backward:
                model = self._create_model()  # Fresh model
                result = self.benchmark_backward(backend, model, batch_size)
                results.append(result)
                print(
                    f"  Backward (batch={batch_size}): {result.mean_latency_ms:.3f}ms"
                )

            if self.config.benchmark_surprise:
                model = self._create_model()  # Fresh model
                result = self.benchmark_surprise(backend, model, batch_size)
                results.append(result)
                print(
                    f"  Surprise (batch={batch_size}): {result.mean_latency_ms:.3f}ms"
                )

            if self.config.benchmark_ttt:
                model = self._create_model()  # Fresh model
                result = self.benchmark_ttt_step(backend, model, batch_size)
                results.append(result)
                print(
                    f"  TTT Step (batch={batch_size}): {result.mean_latency_ms:.3f}ms"
                )

            # Clean up
            del model
            gc.collect()

        return results

    def run_all_benchmarks(self) -> BenchmarkSuite:
        """Run benchmarks on all available backends.

        Returns:
            BenchmarkSuite with all results
        """
        suite = BenchmarkSuite(config=self.config)

        # CPU benchmark
        print("\n" + "=" * 60)
        print("CPU Backend Benchmark")
        print("=" * 60)
        cpu_backend = create_cpu_backend()
        cpu_backend.initialize()
        cpu_results = self.run_backend_benchmarks(cpu_backend)
        suite.results.extend(cpu_results)
        cpu_backend.cleanup()

        # GPU/MPS benchmark
        print("\n" + "=" * 60)
        print("GPU/MPS Backend Benchmark")
        print("=" * 60)
        gpu_backend = create_gpu_backend()
        gpu_backend.initialize()
        info = gpu_backend.get_backend_info()
        print(f"Device: {info.get('device_name', 'Unknown')}")
        print(f"GPU Type: {info.get('gpu_type', 'none')}")

        if info.get("gpu_type") != "none":
            gpu_results = self.run_backend_benchmarks(gpu_backend)
            suite.results.extend(gpu_results)
        else:
            print("No GPU available, skipping GPU benchmarks")

        gpu_backend.cleanup()

        # Compute summary
        suite.summary = self._compute_summary(suite.results)

        return suite

    def _compute_summary(self, results: List[BenchmarkResult]) -> Dict[str, Any]:
        """Compute summary statistics from benchmark results.

        Args:
            results: List of benchmark results

        Returns:
            Summary dictionary
        """
        summary: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "pytorch_version": torch.__version__,
            "backends": {},
        }

        # Group by backend
        backends: Dict[str, Dict[str, Any]] = {}
        for r in results:
            if r.backend_type not in backends:
                backends[r.backend_type] = {
                    "device_name": r.device_name,
                    "operations": {},
                }

            op_key = f"{r.operation}_batch{r.batch_size}"
            backends[r.backend_type]["operations"][op_key] = {
                "mean_latency_ms": r.mean_latency_ms,
                "p99_latency_ms": r.p99_latency_ms,
                "throughput": r.throughput_samples_per_sec,
            }

        summary["backends"] = backends

        # Compute speedups (GPU vs CPU)
        if "cpu" in backends and "gpu" in backends:
            speedups: Dict[str, float] = {}
            for op_key in backends["cpu"]["operations"]:
                if op_key in backends["gpu"]["operations"]:
                    cpu_latency = float(
                        backends["cpu"]["operations"][op_key]["mean_latency_ms"]
                    )
                    gpu_latency = float(
                        backends["gpu"]["operations"][op_key]["mean_latency_ms"]
                    )
                    if gpu_latency > 0:
                        speedups[op_key] = cpu_latency / gpu_latency
            summary["gpu_speedup"] = speedups

        return summary


def run_benchmarks(
    config: Optional[BenchmarkConfig] = None,
    output_file: Optional[str] = None,
) -> BenchmarkSuite:
    """Run benchmarks and optionally save results.

    Args:
        config: Benchmark configuration
        output_file: Optional file path to save JSON results

    Returns:
        BenchmarkSuite with results
    """
    benchmark = MemoryBenchmark(config)
    suite = benchmark.run_all_benchmarks()

    # Print summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"PyTorch Version: {torch.__version__}")

    for backend_type, data in suite.summary.get("backends", {}).items():
        print(f"\n{backend_type.upper()} ({data['device_name']}):")
        for op, stats in data["operations"].items():
            print(
                f"  {op}: {stats['mean_latency_ms']:.3f}ms (p99: {stats['p99_latency_ms']:.3f}ms)"
            )

    if "gpu_speedup" in suite.summary:
        print("\nGPU Speedup vs CPU:")
        for op, speedup in suite.summary["gpu_speedup"].items():
            print(f"  {op}: {speedup:.2f}x")

    # Save to file if requested
    if output_file:
        with open(output_file, "w") as f:
            json.dump(suite.to_dict(), f, indent=2)
        print(f"\nResults saved to: {output_file}")

    return suite


if __name__ == "__main__":
    # Run with default configuration
    config = BenchmarkConfig(
        memory_dim=512,
        memory_depth=3,
        batch_sizes=[1, 8, 32, 64],
        warmup_iterations=10,
        benchmark_iterations=50,
    )
    run_benchmarks(config, output_file="benchmark_results.json")
