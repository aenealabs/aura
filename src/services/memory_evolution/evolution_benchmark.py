"""
Project Aura - Memory Evolution Benchmark Framework (ADR-080 Phase 4)

Evaluation framework for measuring memory evolution effectiveness across
task sequences. Implements sampling for production use and drift detection.

Benchmark Categories:
1. Factual Recall - entity tracking, temporal ordering, relationships
2. Reasoning - multi-step inference, pattern recognition
3. Strategy Transfer - cross-domain application, novel problem solving
4. Evolution Efficiency - consolidation rate, adaptation speed

Key Features:
- Adaptive sampling (1% base, 10% during anomalies)
- Drift detection with Population Stability Index (PSI)
- Off-peak execution scheduling
- Baseline capture and delta tracking

Reference: ADR-080 Evo-Memory Enhancements (Phase 4)
"""

import hashlib
import logging
import math
import random
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol

from .config import MemoryEvolutionConfig, get_memory_evolution_config

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================


class BenchmarkCategory(Enum):
    """Categories for memory evolution benchmarks."""

    FACTUAL_RECALL = "factual_recall"
    REASONING = "reasoning"
    STRATEGY_TRANSFER = "strategy_transfer"
    EVOLUTION_EFFICIENCY = "evolution_efficiency"


class BenchmarkSubcategory(Enum):
    """Subcategories for detailed benchmark analysis."""

    # Factual Recall
    ENTITY_TRACKING = "entity_tracking"
    TEMPORAL_ORDERING = "temporal_ordering"
    RELATIONSHIP_MEMORY = "relationship_memory"
    ATTRIBUTE_RECALL = "attribute_recall"

    # Reasoning
    MULTI_STEP_INFERENCE = "multi_step_inference"
    HYPOTHESIS_TESTING = "hypothesis_testing"
    PATTERN_RECOGNITION = "pattern_recognition"

    # Strategy Transfer
    CROSS_DOMAIN_APPLICATION = "cross_domain_application"
    NOVEL_PROBLEM_SOLVING = "novel_problem_solving"
    STRATEGY_ADAPTATION = "strategy_adaptation"

    # Evolution Efficiency
    CONSOLIDATION_RATE = "consolidation_rate"
    ADAPTATION_SPEED = "adaptation_speed"


class DriftSeverity(Enum):
    """Severity levels for distribution drift."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# PROTOCOLS
# =============================================================================


class AgentProtocol(Protocol):
    """Protocol for agent operations in benchmarks."""

    @property
    def agent_id(self) -> str:
        """Get agent identifier."""
        ...

    async def execute_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute a task and return result."""
        ...


class MemoryServiceProtocol(Protocol):
    """Protocol for memory service operations."""

    async def get_memory_count(self, agent_id: str) -> int:
        """Get total memory count for agent."""
        ...

    async def get_active_memory_count(self, agent_id: str) -> int:
        """Get active (non-pruned) memory count."""
        ...

    async def get_strategy_count(self, agent_id: str) -> int:
        """Get strategy count for agent."""
        ...


class MetricsStoreProtocol(Protocol):
    """Protocol for metrics storage operations."""

    async def store_benchmark_result(self, result: "BenchmarkResult") -> str:
        """Store benchmark result. Returns result ID."""
        ...

    async def get_baseline(
        self, agent_id: str, category: str
    ) -> Optional["BaselineMetrics"]:
        """Get baseline metrics for agent/category."""
        ...

    async def store_baseline(self, baseline: "BaselineMetrics") -> str:
        """Store baseline metrics. Returns baseline ID."""
        ...


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution."""

    # Sampling configuration
    base_sampling_rate: float = 0.01  # 1% of tasks
    anomaly_sampling_rate: float = 0.10  # 10% during anomalies
    max_tasks_per_benchmark: int = 100

    # Environment restrictions
    exclude_production: bool = True  # Default to staging only
    allowed_environments: list[str] = field(
        default_factory=lambda: ["dev", "qa", "staging"]
    )

    # Off-peak scheduling
    off_peak_only: bool = True
    off_peak_start_hour: int = 2  # 2 AM UTC
    off_peak_end_hour: int = 6  # 6 AM UTC

    # Drift detection
    psi_threshold: float = 0.2  # Population Stability Index threshold
    drift_window_size: int = 100  # Tasks to consider for drift

    # Scoring
    min_tasks_for_scoring: int = 5
    baseline_task_count: int = 50

    # Timeouts
    task_timeout_seconds: float = 30.0
    benchmark_timeout_seconds: float = 300.0

    # Feature flag
    enabled: bool = True


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class BenchmarkTask:
    """A single task for benchmark evaluation."""

    task_id: str
    category: BenchmarkCategory
    subcategory: BenchmarkSubcategory
    description: str
    input_data: dict[str, Any]
    expected_output: dict[str, Any]
    difficulty: float = 0.5  # 0.0 to 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "category": self.category.value,
            "subcategory": self.subcategory.value,
            "description": self.description,
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "difficulty": self.difficulty,
            "metadata": self.metadata,
        }


@dataclass
class TaskResult:
    """Result of executing a benchmark task."""

    task_id: str
    success: bool
    actual_output: dict[str, Any]
    score: float  # 0.0 to 1.0
    latency_ms: float
    memory_accesses: int = 0
    strategies_used: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "actual_output": self.actual_output,
            "score": self.score,
            "latency_ms": self.latency_ms,
            "memory_accesses": self.memory_accesses,
            "strategies_used": self.strategies_used,
            "error": self.error,
        }


@dataclass
class BaselineMetrics:
    """Baseline metrics for comparison."""

    baseline_id: str
    agent_id: str
    category: BenchmarkCategory
    mean_score: float
    std_score: float
    task_count: int
    score_distribution: list[float]  # Binned for PSI calculation
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "baseline_id": self.baseline_id,
            "agent_id": self.agent_id,
            "category": self.category.value,
            "mean_score": self.mean_score,
            "std_score": self.std_score,
            "task_count": self.task_count,
            "score_distribution": self.score_distribution,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DriftResult:
    """Result of drift detection analysis."""

    psi_value: float
    severity: DriftSeverity
    is_drifted: bool
    expected_distribution: list[float]
    actual_distribution: list[float]
    contributing_bins: list[int]  # Bins with highest PSI contribution

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "psi_value": self.psi_value,
            "severity": self.severity.value,
            "is_drifted": self.is_drifted,
            "expected_distribution": self.expected_distribution,
            "actual_distribution": self.actual_distribution,
            "contributing_bins": self.contributing_bins,
        }


@dataclass
class BenchmarkResult:
    """Complete result of a benchmark run."""

    result_id: str
    agent_id: str
    category: BenchmarkCategory
    score: float
    baseline_score: float
    evolution_delta: float  # score - baseline_score
    task_count: int
    task_results: list[TaskResult]
    drift_result: Optional[DriftResult] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    latency_ms: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "result_id": self.result_id,
            "agent_id": self.agent_id,
            "category": self.category.value,
            "score": self.score,
            "baseline_score": self.baseline_score,
            "evolution_delta": self.evolution_delta,
            "task_count": self.task_count,
            "task_results": [r.to_dict() for r in self.task_results],
            "drift_result": self.drift_result.to_dict() if self.drift_result else None,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "latency_ms": self.latency_ms,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


@dataclass
class EvolutionMetricsSummary:
    """Summary of evolution metrics across all categories."""

    agent_id: str
    overall_score: float
    overall_evolution_delta: float
    category_scores: dict[str, float]
    category_deltas: dict[str, float]
    drift_detected: bool
    anomaly_rate: float
    benchmark_count: int
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id,
            "overall_score": self.overall_score,
            "overall_evolution_delta": self.overall_evolution_delta,
            "category_scores": self.category_scores,
            "category_deltas": self.category_deltas,
            "drift_detected": self.drift_detected,
            "anomaly_rate": self.anomaly_rate,
            "benchmark_count": self.benchmark_count,
            "computed_at": self.computed_at.isoformat(),
        }


# =============================================================================
# DRIFT DETECTOR
# =============================================================================


class DriftDetector:
    """Detects distribution drift using Population Stability Index (PSI).

    PSI measures how much a distribution has shifted from a baseline:
    - PSI < 0.1: No significant drift
    - 0.1 <= PSI < 0.2: Low drift (monitor)
    - 0.2 <= PSI < 0.25: Medium drift (investigate)
    - PSI >= 0.25: High drift (action required)
    """

    NUM_BINS = 10  # Number of bins for distribution

    def __init__(self, psi_threshold: float = 0.2):
        """Initialize drift detector.

        Args:
            psi_threshold: PSI threshold for drift detection
        """
        self.psi_threshold = psi_threshold

    def compute_psi(
        self,
        expected: list[float],
        actual: list[float],
    ) -> DriftResult:
        """Compute Population Stability Index between distributions.

        Args:
            expected: Expected (baseline) score distribution
            actual: Actual (current) score distribution

        Returns:
            DriftResult with PSI value and severity
        """
        if not expected or not actual:
            return DriftResult(
                psi_value=0.0,
                severity=DriftSeverity.NONE,
                is_drifted=False,
                expected_distribution=[],
                actual_distribution=[],
                contributing_bins=[],
            )

        # Bin the scores
        expected_bins = self._bin_scores(expected)
        actual_bins = self._bin_scores(actual)

        # Compute PSI for each bin
        psi_contributions = []
        contributing_bins = []

        for i in range(self.NUM_BINS):
            e = expected_bins[i]
            a = actual_bins[i]

            # Avoid division by zero
            if e == 0 or a == 0:
                # Use small value to avoid log(0)
                e = max(e, 0.001)
                a = max(a, 0.001)

            psi_bin = (a - e) * math.log(a / e)
            psi_contributions.append(psi_bin)

            # Track high-contribution bins
            if abs(psi_bin) > 0.02:
                contributing_bins.append(i)

        psi_value = sum(psi_contributions)

        # Determine severity
        severity = self._classify_severity(psi_value)

        return DriftResult(
            psi_value=psi_value,
            severity=severity,
            is_drifted=psi_value >= self.psi_threshold,
            expected_distribution=expected_bins,
            actual_distribution=actual_bins,
            contributing_bins=contributing_bins,
        )

    def _bin_scores(self, scores: list[float]) -> list[float]:
        """Bin scores into distribution buckets.

        Args:
            scores: List of scores (0.0 to 1.0)

        Returns:
            List of bin proportions
        """
        bins = [0] * self.NUM_BINS
        total = len(scores)

        if total == 0:
            return [1.0 / self.NUM_BINS] * self.NUM_BINS

        for score in scores:
            # Clamp score to [0, 1]
            score = max(0.0, min(1.0, score))
            # Determine bin (0-9)
            bin_idx = min(int(score * self.NUM_BINS), self.NUM_BINS - 1)
            bins[bin_idx] += 1

        # Convert to proportions
        return [count / total for count in bins]

    def _classify_severity(self, psi: float) -> DriftSeverity:
        """Classify PSI value into severity level."""
        if psi < 0.1:
            return DriftSeverity.NONE
        elif psi < 0.2:
            return DriftSeverity.LOW
        elif psi < 0.25:
            return DriftSeverity.MEDIUM
        elif psi < 0.5:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL


# =============================================================================
# SAMPLING STRATEGY
# =============================================================================


class AdaptiveSampler:
    """Adaptive sampling strategy for benchmarks.

    Uses stratified sampling with anomaly detection to increase
    sampling rate when performance degrades.
    """

    def __init__(self, config: BenchmarkConfig):
        """Initialize adaptive sampler.

        Args:
            config: Benchmark configuration
        """
        self.config = config
        self._recent_scores: deque[float] = deque(maxlen=self.config.drift_window_size)
        self._anomaly_detected = False

    def should_sample(self, agent_id: str) -> bool:
        """Determine if we should run benchmark for this task.

        Args:
            agent_id: Agent identifier

        Returns:
            True if benchmark should run
        """
        # Determine effective sampling rate
        rate = self._get_effective_rate()

        # Use agent_id + timestamp for deterministic but varied sampling
        sample_key = f"{agent_id}:{time.time()}"
        # MD5 used for sampling distribution, not security (B324 safe)
        hash_value = int(
            hashlib.md5(sample_key.encode(), usedforsecurity=False).hexdigest()[:8], 16
        )
        threshold = int(rate * 0xFFFFFFFF)

        return hash_value < threshold

    def record_score(self, score: float) -> None:
        """Record a benchmark score for anomaly detection.

        Args:
            score: Benchmark score (0.0 to 1.0)
        """
        self._recent_scores.append(score)

        # Check for anomalies
        self._anomaly_detected = self._detect_anomaly()

    def _get_effective_rate(self) -> float:
        """Get effective sampling rate based on anomaly state."""
        if self._anomaly_detected:
            return self.config.anomaly_sampling_rate
        return self.config.base_sampling_rate

    def _detect_anomaly(self) -> bool:
        """Detect if recent scores indicate an anomaly."""
        if len(self._recent_scores) < 10:
            return False

        # deque does not support slicing; convert to list for windowed access
        scores_list = list(self._recent_scores)
        recent = scores_list[-10:]
        mean = statistics.mean(recent)
        std = statistics.stdev(recent) if len(recent) > 1 else 0

        # Anomaly if recent scores are significantly lower than historical
        if len(self._recent_scores) >= 20:
            historical = scores_list[:-10]
            hist_mean = statistics.mean(historical)

            # More than 1 std below historical mean
            if mean < hist_mean - std:
                return True

        return False

    def reset(self) -> None:
        """Reset sampler state."""
        self._recent_scores.clear()
        self._anomaly_detected = False


# =============================================================================
# BENCHMARK SUITE
# =============================================================================


class MemoryEvolutionBenchmark:
    """Benchmark suite for memory evolution effectiveness.

    Measures agent memory performance across four categories:
    1. Factual Recall - ability to remember and retrieve facts
    2. Reasoning - ability to use memories for inference
    3. Strategy Transfer - ability to apply strategies to new problems
    4. Evolution Efficiency - rate of memory improvement

    Features:
    - Adaptive sampling for production use
    - Drift detection with PSI
    - Off-peak scheduling support
    - Baseline capture and delta tracking
    """

    CATEGORY_SUBCATEGORIES = {
        BenchmarkCategory.FACTUAL_RECALL: [
            BenchmarkSubcategory.ENTITY_TRACKING,
            BenchmarkSubcategory.TEMPORAL_ORDERING,
            BenchmarkSubcategory.RELATIONSHIP_MEMORY,
            BenchmarkSubcategory.ATTRIBUTE_RECALL,
        ],
        BenchmarkCategory.REASONING: [
            BenchmarkSubcategory.MULTI_STEP_INFERENCE,
            BenchmarkSubcategory.HYPOTHESIS_TESTING,
            BenchmarkSubcategory.PATTERN_RECOGNITION,
        ],
        BenchmarkCategory.STRATEGY_TRANSFER: [
            BenchmarkSubcategory.CROSS_DOMAIN_APPLICATION,
            BenchmarkSubcategory.NOVEL_PROBLEM_SOLVING,
            BenchmarkSubcategory.STRATEGY_ADAPTATION,
        ],
        BenchmarkCategory.EVOLUTION_EFFICIENCY: [
            BenchmarkSubcategory.CONSOLIDATION_RATE,
            BenchmarkSubcategory.ADAPTATION_SPEED,
        ],
    }

    def __init__(
        self,
        config: Optional[BenchmarkConfig] = None,
        evolution_config: Optional[MemoryEvolutionConfig] = None,
        metrics_store: Optional[MetricsStoreProtocol] = None,
        memory_service: Optional[MemoryServiceProtocol] = None,
    ):
        """Initialize benchmark suite.

        Args:
            config: Benchmark configuration
            evolution_config: Memory evolution configuration
            metrics_store: Optional metrics storage
            memory_service: Optional memory service for metrics
        """
        self.config = config or BenchmarkConfig()
        self.evolution_config = evolution_config or get_memory_evolution_config()
        self.metrics_store = metrics_store
        self.memory_service = memory_service

        self.drift_detector = DriftDetector(psi_threshold=self.config.psi_threshold)
        self.sampler = AdaptiveSampler(self.config)

        # Cache for baselines
        self._baseline_cache: dict[str, BaselineMetrics] = {}

    async def capture_baseline(
        self,
        agent: AgentProtocol,
        task_generator: "TaskGenerator",
    ) -> dict[str, BaselineMetrics]:
        """Capture baseline metrics for an agent.

        Args:
            agent: Agent to benchmark
            task_generator: Generator for benchmark tasks

        Returns:
            Dictionary of category -> BaselineMetrics
        """
        baselines: dict[str, BaselineMetrics] = {}

        for category in BenchmarkCategory:
            tasks = task_generator.generate_tasks(
                category=category,
                count=self.config.baseline_task_count,
            )

            scores = []
            for task in tasks:
                result = await self._execute_task(agent, task)
                scores.append(result.score)

            if scores:
                baseline_id = (
                    f"baseline_{agent.agent_id}_{category.value}_{int(time.time())}"
                )
                baseline = BaselineMetrics(
                    baseline_id=baseline_id,
                    agent_id=agent.agent_id,
                    category=category,
                    mean_score=statistics.mean(scores),
                    std_score=statistics.stdev(scores) if len(scores) > 1 else 0.0,
                    task_count=len(scores),
                    score_distribution=scores,
                )

                baselines[category.value] = baseline
                self._baseline_cache[f"{agent.agent_id}:{category.value}"] = baseline

                if self.metrics_store:
                    await self.metrics_store.store_baseline(baseline)

        return baselines

    async def run_benchmark(
        self,
        agent: AgentProtocol,
        category: BenchmarkCategory,
        tasks: list[BenchmarkTask],
    ) -> BenchmarkResult:
        """Run benchmark on agent's memory system.

        Args:
            agent: Agent to benchmark
            category: Benchmark category
            tasks: List of benchmark tasks

        Returns:
            BenchmarkResult with scores and evolution delta
        """
        result_id = f"bench_{agent.agent_id}_{category.value}_{int(time.time())}"
        start_time = time.time()

        # Check if we should run
        skip_reason = self._check_should_skip(agent)
        if skip_reason:
            return BenchmarkResult(
                result_id=result_id,
                agent_id=agent.agent_id,
                category=category,
                score=0.0,
                baseline_score=0.0,
                evolution_delta=0.0,
                task_count=0,
                task_results=[],
                skipped=True,
                skip_reason=skip_reason,
            )

        # Execute benchmark tasks
        task_results: list[TaskResult] = []
        for task in tasks[: self.config.max_tasks_per_benchmark]:
            try:
                result = await self._execute_task(agent, task)
                task_results.append(result)
            except Exception as e:
                logger.error(f"Task {task.task_id} failed: {e}")
                task_results.append(
                    TaskResult(
                        task_id=task.task_id,
                        success=False,
                        actual_output={},
                        score=0.0,
                        latency_ms=0.0,
                        error=str(e),
                    )
                )

        # Compute score
        if len(task_results) < self.config.min_tasks_for_scoring:
            return BenchmarkResult(
                result_id=result_id,
                agent_id=agent.agent_id,
                category=category,
                score=0.0,
                baseline_score=0.0,
                evolution_delta=0.0,
                task_count=len(task_results),
                task_results=task_results,
                skipped=True,
                skip_reason=f"Insufficient tasks ({len(task_results)} < {self.config.min_tasks_for_scoring})",
            )

        current_score = self._compute_category_score(task_results)

        # Get baseline
        baseline = await self._get_baseline(agent.agent_id, category)
        baseline_score = baseline.mean_score if baseline else 0.0

        # Compute evolution delta
        evolution_delta = current_score - baseline_score

        # Check for drift
        drift_result = None
        if baseline and baseline.score_distribution:
            current_scores = [r.score for r in task_results]
            drift_result = self.drift_detector.compute_psi(
                expected=baseline.score_distribution,
                actual=current_scores,
            )

        # Record for adaptive sampling
        self.sampler.record_score(current_score)

        latency_ms = (time.time() - start_time) * 1000

        result = BenchmarkResult(
            result_id=result_id,
            agent_id=agent.agent_id,
            category=category,
            score=current_score,
            baseline_score=baseline_score,
            evolution_delta=evolution_delta,
            task_count=len(task_results),
            task_results=task_results,
            drift_result=drift_result,
            latency_ms=latency_ms,
            completed_at=datetime.now(timezone.utc),
        )

        # Store result
        if self.metrics_store:
            await self.metrics_store.store_benchmark_result(result)

        return result

    async def run_full_benchmark(
        self,
        agent: AgentProtocol,
        task_generator: "TaskGenerator",
    ) -> EvolutionMetricsSummary:
        """Run full benchmark across all categories.

        Args:
            agent: Agent to benchmark
            task_generator: Generator for benchmark tasks

        Returns:
            EvolutionMetricsSummary with overall results
        """
        category_scores: dict[str, float] = {}
        category_deltas: dict[str, float] = {}
        drift_detected = False
        results: list[BenchmarkResult] = []

        for category in BenchmarkCategory:
            tasks = task_generator.generate_tasks(
                category=category,
                count=self.config.max_tasks_per_benchmark,
            )

            result = await self.run_benchmark(agent, category, tasks)
            results.append(result)

            if not result.skipped:
                category_scores[category.value] = result.score
                category_deltas[category.value] = result.evolution_delta

                if result.drift_result and result.drift_result.is_drifted:
                    drift_detected = True

        # Compute overall metrics
        valid_scores = [r.score for r in results if not r.skipped]
        valid_deltas = [r.evolution_delta for r in results if not r.skipped]

        overall_score = statistics.mean(valid_scores) if valid_scores else 0.0
        overall_delta = statistics.mean(valid_deltas) if valid_deltas else 0.0

        # Compute anomaly rate
        anomaly_count = sum(
            1
            for r in results
            if r.drift_result
            and r.drift_result.severity in [DriftSeverity.HIGH, DriftSeverity.CRITICAL]
        )
        anomaly_rate = anomaly_count / len(results) if results else 0.0

        return EvolutionMetricsSummary(
            agent_id=agent.agent_id,
            overall_score=overall_score,
            overall_evolution_delta=overall_delta,
            category_scores=category_scores,
            category_deltas=category_deltas,
            drift_detected=drift_detected,
            anomaly_rate=anomaly_rate,
            benchmark_count=len(results),
        )

    async def _execute_task(
        self,
        agent: AgentProtocol,
        task: BenchmarkTask,
    ) -> TaskResult:
        """Execute a single benchmark task.

        Args:
            agent: Agent to execute task
            task: Benchmark task

        Returns:
            TaskResult with score and metrics
        """
        start_time = time.time()

        try:
            result = await agent.execute_task(task.to_dict())

            # Score the result
            score = self._score_result(task, result)

            latency_ms = (time.time() - start_time) * 1000

            return TaskResult(
                task_id=task.task_id,
                success=True,
                actual_output=result,
                score=score,
                latency_ms=latency_ms,
                memory_accesses=result.get("memory_accesses", 0),
                strategies_used=result.get("strategies_used", 0),
            )

        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                success=False,
                actual_output={},
                score=0.0,
                latency_ms=(time.time() - start_time) * 1000,
                error=str(e),
            )

    def _score_result(
        self,
        task: BenchmarkTask,
        result: dict[str, Any],
    ) -> float:
        """Score a task result against expected output.

        Args:
            task: Benchmark task with expected output
            result: Actual result from agent

        Returns:
            Score from 0.0 to 1.0
        """
        expected = task.expected_output
        actual = result.get("output", result)

        # Simple key-matching score
        if not expected:
            return 1.0 if result.get("success", False) else 0.0

        matches = 0
        total = len(expected)

        for key, expected_value in expected.items():
            actual_value = actual.get(key)

            if actual_value == expected_value:
                matches += 1
            elif isinstance(expected_value, (int, float)) and isinstance(
                actual_value, (int, float)
            ):
                # Fuzzy numeric matching
                if abs(expected_value - actual_value) < 0.1 * abs(expected_value + 1):
                    matches += 0.5

        return matches / total if total > 0 else 0.0

    def _compute_category_score(self, results: list[TaskResult]) -> float:
        """Compute overall score for a category.

        Args:
            results: List of task results

        Returns:
            Weighted average score
        """
        if not results:
            return 0.0

        # Weight by success (failed tasks count less)
        weighted_sum = sum(r.score * (1.0 if r.success else 0.5) for r in results)
        weight_total = sum(1.0 if r.success else 0.5 for r in results)

        return weighted_sum / weight_total if weight_total > 0 else 0.0

    async def _get_baseline(
        self,
        agent_id: str,
        category: BenchmarkCategory,
    ) -> Optional[BaselineMetrics]:
        """Get baseline metrics for agent/category."""
        cache_key = f"{agent_id}:{category.value}"

        if cache_key in self._baseline_cache:
            return self._baseline_cache[cache_key]

        if self.metrics_store:
            baseline = await self.metrics_store.get_baseline(agent_id, category.value)
            if baseline:
                self._baseline_cache[cache_key] = baseline
            return baseline

        return None

    def _check_should_skip(self, agent: AgentProtocol) -> Optional[str]:
        """Check if benchmark should be skipped.

        Returns:
            Skip reason if should skip, None otherwise
        """
        if not self.config.enabled:
            return "Benchmarks disabled"

        # Check environment
        env = self.evolution_config.environment
        if self.config.exclude_production and env == "prod":
            return "Production environment excluded"

        if env not in self.config.allowed_environments:
            return f"Environment {env} not in allowed list"

        # Check off-peak hours
        if self.config.off_peak_only:
            current_hour = datetime.now(timezone.utc).hour
            if not (
                self.config.off_peak_start_hour
                <= current_hour
                < self.config.off_peak_end_hour
            ):
                return f"Not in off-peak hours ({self.config.off_peak_start_hour}-{self.config.off_peak_end_hour} UTC)"

        # Check sampling
        if not self.sampler.should_sample(agent.agent_id):
            return "Not selected by sampling"

        return None


# =============================================================================
# TASK GENERATOR
# =============================================================================


class TaskGenerator:
    """Generates benchmark tasks for each category."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize task generator.

        Args:
            seed: Random seed for reproducibility
        """
        self.rng = random.Random(seed)
        self._task_counter = 0

    def generate_tasks(
        self,
        category: BenchmarkCategory,
        count: int,
    ) -> list[BenchmarkTask]:
        """Generate benchmark tasks for a category.

        Args:
            category: Benchmark category
            count: Number of tasks to generate

        Returns:
            List of benchmark tasks
        """
        tasks = []
        subcategories = MemoryEvolutionBenchmark.CATEGORY_SUBCATEGORIES[category]

        for i in range(count):
            subcategory = subcategories[i % len(subcategories)]
            task = self._generate_task(category, subcategory)
            tasks.append(task)

        return tasks

    def _generate_task(
        self,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate a single benchmark task."""
        self._task_counter += 1
        task_id = f"task_{category.value}_{subcategory.value}_{self._task_counter}"

        # Generate task based on subcategory
        generator_map = {
            BenchmarkSubcategory.ENTITY_TRACKING: self._gen_entity_tracking,
            BenchmarkSubcategory.TEMPORAL_ORDERING: self._gen_temporal_ordering,
            BenchmarkSubcategory.RELATIONSHIP_MEMORY: self._gen_relationship_memory,
            BenchmarkSubcategory.ATTRIBUTE_RECALL: self._gen_attribute_recall,
            BenchmarkSubcategory.MULTI_STEP_INFERENCE: self._gen_multi_step_inference,
            BenchmarkSubcategory.HYPOTHESIS_TESTING: self._gen_hypothesis_testing,
            BenchmarkSubcategory.PATTERN_RECOGNITION: self._gen_pattern_recognition,
            BenchmarkSubcategory.CROSS_DOMAIN_APPLICATION: self._gen_cross_domain,
            BenchmarkSubcategory.NOVEL_PROBLEM_SOLVING: self._gen_novel_problem,
            BenchmarkSubcategory.STRATEGY_ADAPTATION: self._gen_strategy_adaptation,
            BenchmarkSubcategory.CONSOLIDATION_RATE: self._gen_consolidation_rate,
            BenchmarkSubcategory.ADAPTATION_SPEED: self._gen_adaptation_speed,
        }

        generator = generator_map.get(subcategory, self._gen_default)
        return generator(task_id, category, subcategory)

    def _gen_entity_tracking(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate entity tracking task."""
        entities = ["Alice", "Bob", "Charlie", "Diana"]
        entity = self.rng.choice(entities)
        attribute = self.rng.choice(["role", "department", "project"])
        value = f"value_{self.rng.randint(1, 100)}"

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description=f"Track {attribute} for {entity}",
            input_data={
                "action": "track_entity",
                "entity": entity,
                "attribute": attribute,
                "value": value,
            },
            expected_output={
                "entity": entity,
                "attribute": attribute,
                "value": value,
            },
            difficulty=0.3,
        )

    def _gen_temporal_ordering(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate temporal ordering task."""
        events = [f"event_{i}" for i in range(5)]
        self.rng.shuffle(events)
        correct_order = sorted(events)

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description="Order events chronologically",
            input_data={"action": "order_events", "events": events},
            expected_output={"ordered_events": correct_order},
            difficulty=0.5,
        )

    def _gen_relationship_memory(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate relationship memory task."""
        entities = ["A", "B", "C", "D"]
        relationships = ["works_with", "manages", "reports_to"]
        e1, e2 = self.rng.sample(entities, 2)
        rel = self.rng.choice(relationships)

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description=f"Remember relationship between {e1} and {e2}",
            input_data={
                "action": "store_relationship",
                "entity1": e1,
                "entity2": e2,
                "relationship": rel,
            },
            expected_output={"entity1": e1, "entity2": e2, "relationship": rel},
            difficulty=0.4,
        )

    def _gen_attribute_recall(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate attribute recall task."""
        item = f"item_{self.rng.randint(1, 100)}"
        attributes = {"color": "blue", "size": "large", "type": "widget"}

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description=f"Recall attributes of {item}",
            input_data={
                "action": "recall_attributes",
                "item": item,
                "stored_attributes": attributes,
            },
            expected_output={"item": item, "attributes": attributes},
            difficulty=0.3,
        )

    def _gen_multi_step_inference(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate multi-step inference task."""
        a = self.rng.randint(1, 10)
        b = self.rng.randint(1, 10)
        c = self.rng.randint(1, 10)
        result = (a + b) * c

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description="Multi-step calculation",
            input_data={
                "action": "calculate",
                "steps": [f"add {a} + {b}", f"multiply by {c}"],
                "values": {"a": a, "b": b, "c": c},
            },
            expected_output={"result": result},
            difficulty=0.6,
        )

    def _gen_hypothesis_testing(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate hypothesis testing task."""
        hypothesis = self.rng.choice(["true", "false"])
        evidence = ["supports" if hypothesis == "true" else "refutes"]

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description="Test hypothesis against evidence",
            input_data={
                "action": "test_hypothesis",
                "hypothesis": hypothesis,
                "evidence": evidence,
            },
            expected_output={"conclusion": hypothesis, "confidence": 0.8},
            difficulty=0.7,
        )

    def _gen_pattern_recognition(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate pattern recognition task."""
        sequence = [i * 2 for i in range(5)]  # 0, 2, 4, 6, 8
        next_value = 10

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description="Recognize pattern and predict next",
            input_data={"action": "predict_next", "sequence": sequence},
            expected_output={"next_value": next_value, "pattern": "multiply_by_2"},
            difficulty=0.5,
        )

    def _gen_cross_domain(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate cross-domain application task."""
        source_domain = "debugging"
        target_domain = "testing"
        strategy = "isolate_and_verify"

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description=f"Apply {strategy} from {source_domain} to {target_domain}",
            input_data={
                "action": "transfer_strategy",
                "source_domain": source_domain,
                "target_domain": target_domain,
                "strategy": strategy,
            },
            expected_output={"applied": True, "adaptation_needed": True},
            difficulty=0.8,
        )

    def _gen_novel_problem(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate novel problem solving task."""
        problem_type = self.rng.choice(
            ["optimization", "resource_allocation", "scheduling"]
        )

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description=f"Solve novel {problem_type} problem",
            input_data={"action": "solve_novel", "problem_type": problem_type},
            expected_output={"solution_found": True, "approach": "heuristic"},
            difficulty=0.9,
        )

    def _gen_strategy_adaptation(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate strategy adaptation task."""
        original_strategy = "brute_force"
        constraint = "time_limit"
        adapted_strategy = "binary_search"

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description=f"Adapt {original_strategy} with {constraint}",
            input_data={
                "action": "adapt_strategy",
                "original": original_strategy,
                "constraint": constraint,
            },
            expected_output={"adapted_strategy": adapted_strategy, "improvement": True},
            difficulty=0.7,
        )

    def _gen_consolidation_rate(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate consolidation rate task."""
        memories_before = self.rng.randint(50, 100)
        memories_after = int(memories_before * 0.7)

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description="Measure memory consolidation rate",
            input_data={
                "action": "measure_consolidation",
                "memories_before": memories_before,
            },
            expected_output={
                "memories_after": memories_after,
                "consolidation_rate": (memories_before - memories_after)
                / memories_before,
            },
            difficulty=0.4,
        )

    def _gen_adaptation_speed(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate adaptation speed task."""
        initial_performance = 0.5
        target_performance = 0.8
        tasks_to_adapt = self.rng.randint(5, 20)

        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description="Measure adaptation speed",
            input_data={
                "action": "measure_adaptation",
                "initial_performance": initial_performance,
                "target_performance": target_performance,
            },
            expected_output={
                "tasks_to_adapt": tasks_to_adapt,
                "adaptation_rate": (target_performance - initial_performance)
                / tasks_to_adapt,
            },
            difficulty=0.5,
        )

    def _gen_default(
        self,
        task_id: str,
        category: BenchmarkCategory,
        subcategory: BenchmarkSubcategory,
    ) -> BenchmarkTask:
        """Generate default task."""
        return BenchmarkTask(
            task_id=task_id,
            category=category,
            subcategory=subcategory,
            description="Default benchmark task",
            input_data={"action": "default", "value": 1},
            expected_output={"success": True},
            difficulty=0.5,
        )


# =============================================================================
# SINGLETON MANAGEMENT
# =============================================================================

_benchmark_instance: Optional[MemoryEvolutionBenchmark] = None
_task_generator_instance: Optional[TaskGenerator] = None


def get_evolution_benchmark(
    config: Optional[BenchmarkConfig] = None,
    metrics_store: Optional[MetricsStoreProtocol] = None,
    memory_service: Optional[MemoryServiceProtocol] = None,
) -> MemoryEvolutionBenchmark:
    """Get or create the singleton MemoryEvolutionBenchmark instance."""
    global _benchmark_instance
    if _benchmark_instance is None:
        _benchmark_instance = MemoryEvolutionBenchmark(
            config=config,
            metrics_store=metrics_store,
            memory_service=memory_service,
        )
    return _benchmark_instance


def reset_evolution_benchmark() -> None:
    """Reset the singleton instance (for testing)."""
    global _benchmark_instance
    _benchmark_instance = None


def get_task_generator(seed: Optional[int] = None) -> TaskGenerator:
    """Get or create the singleton TaskGenerator instance."""
    global _task_generator_instance
    if _task_generator_instance is None:
        _task_generator_instance = TaskGenerator(seed=seed)
    return _task_generator_instance


def reset_task_generator() -> None:
    """Reset the singleton instance (for testing)."""
    global _task_generator_instance
    _task_generator_instance = None
