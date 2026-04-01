"""
Tests for ADR-080 Phase 4: Evolution Benchmark Framework

Tests the memory evolution benchmark suite, including drift detection,
adaptive sampling, and task generation.
"""

import statistics
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.memory_evolution.evolution_benchmark import (
    AdaptiveSampler,
    BaselineMetrics,
    BenchmarkCategory,
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkSubcategory,
    BenchmarkTask,
    DriftDetector,
    DriftResult,
    DriftSeverity,
    EvolutionMetricsSummary,
    MemoryEvolutionBenchmark,
    TaskGenerator,
    TaskResult,
    get_evolution_benchmark,
    get_task_generator,
    reset_evolution_benchmark,
    reset_task_generator,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    reset_evolution_benchmark()
    reset_task_generator()
    yield
    reset_evolution_benchmark()
    reset_task_generator()


@pytest.fixture
def benchmark_config():
    """Create test benchmark config."""
    return BenchmarkConfig(
        base_sampling_rate=1.0,  # Always sample for testing
        anomaly_sampling_rate=1.0,
        max_tasks_per_benchmark=10,
        exclude_production=False,
        allowed_environments=["dev", "qa", "staging", "prod", "test"],
        off_peak_only=False,
        min_tasks_for_scoring=2,
        baseline_task_count=5,
        enabled=True,
    )


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = MagicMock()
    agent.agent_id = "test-agent-1"
    agent.execute_task = AsyncMock(
        return_value={
            "success": True,
            "output": {"result": 10},
            "memory_accesses": 5,
            "strategies_used": 2,
        }
    )
    return agent


@pytest.fixture
def mock_metrics_store():
    """Create a mock metrics store."""
    store = AsyncMock()
    store.store_benchmark_result = AsyncMock(return_value="result-123")
    store.get_baseline = AsyncMock(return_value=None)
    store.store_baseline = AsyncMock(return_value="baseline-123")
    return store


@pytest.fixture
def task_generator():
    """Create a task generator with fixed seed."""
    return TaskGenerator(seed=42)


# =============================================================================
# BENCHMARK TASK TESTS
# =============================================================================


class TestBenchmarkTask:
    """Tests for BenchmarkTask dataclass."""

    def test_create_task(self):
        """Test creating a benchmark task."""
        task = BenchmarkTask(
            task_id="task-1",
            category=BenchmarkCategory.FACTUAL_RECALL,
            subcategory=BenchmarkSubcategory.ENTITY_TRACKING,
            description="Track entity",
            input_data={"entity": "Alice"},
            expected_output={"entity": "Alice"},
            difficulty=0.5,
        )

        assert task.task_id == "task-1"
        assert task.category == BenchmarkCategory.FACTUAL_RECALL
        assert task.difficulty == 0.5

    def test_to_dict(self):
        """Test serialization."""
        task = BenchmarkTask(
            task_id="task-1",
            category=BenchmarkCategory.REASONING,
            subcategory=BenchmarkSubcategory.MULTI_STEP_INFERENCE,
            description="Test",
            input_data={"a": 1},
            expected_output={"b": 2},
        )

        data = task.to_dict()

        assert data["task_id"] == "task-1"
        assert data["category"] == "reasoning"
        assert data["subcategory"] == "multi_step_inference"


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_create_successful_result(self):
        """Test creating a successful result."""
        result = TaskResult(
            task_id="task-1",
            success=True,
            actual_output={"result": 42},
            score=0.9,
            latency_ms=100.0,
            memory_accesses=5,
        )

        assert result.success
        assert result.score == 0.9

    def test_create_failed_result(self):
        """Test creating a failed result."""
        result = TaskResult(
            task_id="task-1",
            success=False,
            actual_output={},
            score=0.0,
            latency_ms=50.0,
            error="Task failed",
        )

        assert not result.success
        assert result.error == "Task failed"


class TestBaselineMetrics:
    """Tests for BaselineMetrics dataclass."""

    def test_create_baseline(self):
        """Test creating baseline metrics."""
        scores = [0.7, 0.8, 0.75, 0.85, 0.9]
        baseline = BaselineMetrics(
            baseline_id="baseline-1",
            agent_id="agent-1",
            category=BenchmarkCategory.FACTUAL_RECALL,
            mean_score=statistics.mean(scores),
            std_score=statistics.stdev(scores),
            task_count=len(scores),
            score_distribution=scores,
        )

        assert baseline.mean_score == pytest.approx(0.8, rel=0.01)
        assert baseline.task_count == 5

    def test_to_dict(self):
        """Test serialization."""
        baseline = BaselineMetrics(
            baseline_id="baseline-1",
            agent_id="agent-1",
            category=BenchmarkCategory.REASONING,
            mean_score=0.75,
            std_score=0.1,
            task_count=10,
            score_distribution=[0.7, 0.8],
        )

        data = baseline.to_dict()

        assert data["baseline_id"] == "baseline-1"
        assert data["category"] == "reasoning"
        assert "created_at" in data


# =============================================================================
# DRIFT DETECTOR TESTS
# =============================================================================


class TestDriftDetector:
    """Tests for DriftDetector."""

    def test_no_drift_identical_distributions(self):
        """Test PSI with identical distributions."""
        detector = DriftDetector(psi_threshold=0.2)

        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        result = detector.compute_psi(scores, scores)

        assert result.psi_value < 0.01
        assert result.severity == DriftSeverity.NONE
        assert not result.is_drifted

    def test_significant_drift(self):
        """Test PSI with significantly different distributions."""
        detector = DriftDetector(psi_threshold=0.2)

        expected = [0.1, 0.2, 0.3, 0.4, 0.5] * 20  # Low scores
        actual = [0.6, 0.7, 0.8, 0.9, 1.0] * 20  # High scores

        result = detector.compute_psi(expected, actual)

        assert result.psi_value > 0.2
        assert result.is_drifted
        assert result.severity in [
            DriftSeverity.MEDIUM,
            DriftSeverity.HIGH,
            DriftSeverity.CRITICAL,
        ]

    def test_low_drift(self):
        """Test PSI with slightly different distributions."""
        detector = DriftDetector(psi_threshold=0.2)

        # Create distributions that stay within the same bins but with slight variance
        # Scores 0.50-0.59 fall in bin 5, so small changes within same bin = low drift
        expected = [0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57, 0.58, 0.59] * 10
        actual = [0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.50] * 10

        result = detector.compute_psi(expected, actual)

        # Should be very low PSI since all scores fall in the same bin
        assert result.psi_value < 0.1
        assert result.severity == DriftSeverity.NONE

    def test_empty_distributions(self):
        """Test handling of empty distributions."""
        detector = DriftDetector()

        result = detector.compute_psi([], [])

        assert result.psi_value == 0.0
        assert result.severity == DriftSeverity.NONE

    def test_drift_severity_classification(self):
        """Test severity classification."""
        detector = DriftDetector()

        assert detector._classify_severity(0.05) == DriftSeverity.NONE
        assert detector._classify_severity(0.15) == DriftSeverity.LOW
        assert detector._classify_severity(0.22) == DriftSeverity.MEDIUM
        assert detector._classify_severity(0.35) == DriftSeverity.HIGH
        assert detector._classify_severity(0.6) == DriftSeverity.CRITICAL

    def test_bin_scores(self):
        """Test score binning."""
        detector = DriftDetector()

        scores = [0.0, 0.1, 0.5, 0.9, 1.0]
        bins = detector._bin_scores(scores)

        assert len(bins) == 10
        assert sum(bins) == pytest.approx(1.0)


# =============================================================================
# ADAPTIVE SAMPLER TESTS
# =============================================================================


class TestAdaptiveSampler:
    """Tests for AdaptiveSampler."""

    def test_base_sampling_rate(self, benchmark_config):
        """Test that sampling works with base rate."""
        sampler = AdaptiveSampler(benchmark_config)

        # With 100% sampling rate, should always sample
        assert sampler.should_sample("agent-1")

    def test_anomaly_detection_increases_sampling(self, benchmark_config):
        """Test that anomalies increase sampling rate."""
        config = BenchmarkConfig(
            base_sampling_rate=0.01,
            anomaly_sampling_rate=0.5,
            drift_window_size=20,
        )
        sampler = AdaptiveSampler(config)

        # Record some good scores followed by bad scores
        for _ in range(15):
            sampler.record_score(0.8)

        # Record anomalously low scores
        for _ in range(10):
            sampler.record_score(0.3)

        assert sampler._anomaly_detected

    def test_record_score_maintains_window(self, benchmark_config):
        """Test that score window is maintained."""
        config = BenchmarkConfig(drift_window_size=10)
        sampler = AdaptiveSampler(config)

        for i in range(20):
            sampler.record_score(float(i) / 20)

        assert len(sampler._recent_scores) == 10

    def test_reset(self, benchmark_config):
        """Test sampler reset."""
        sampler = AdaptiveSampler(benchmark_config)

        sampler.record_score(0.5)
        sampler._anomaly_detected = True

        sampler.reset()

        assert len(sampler._recent_scores) == 0
        assert not sampler._anomaly_detected


# =============================================================================
# TASK GENERATOR TESTS
# =============================================================================


class TestTaskGenerator:
    """Tests for TaskGenerator."""

    def test_generate_tasks_all_categories(self, task_generator):
        """Test generating tasks for all categories."""
        for category in BenchmarkCategory:
            tasks = task_generator.generate_tasks(category, count=5)

            assert len(tasks) == 5
            for task in tasks:
                assert task.category == category

    def test_generate_tasks_covers_subcategories(self, task_generator):
        """Test that tasks cover all subcategories."""
        category = BenchmarkCategory.FACTUAL_RECALL
        subcategories = MemoryEvolutionBenchmark.CATEGORY_SUBCATEGORIES[category]

        tasks = task_generator.generate_tasks(category, count=len(subcategories))

        generated_subcategories = {task.subcategory for task in tasks}
        assert generated_subcategories == set(subcategories)

    def test_reproducibility_with_seed(self):
        """Test that tasks are reproducible with same seed."""
        gen1 = TaskGenerator(seed=123)
        gen2 = TaskGenerator(seed=123)

        tasks1 = gen1.generate_tasks(BenchmarkCategory.REASONING, count=5)
        tasks2 = gen2.generate_tasks(BenchmarkCategory.REASONING, count=5)

        for t1, t2 in zip(tasks1, tasks2):
            assert t1.subcategory == t2.subcategory
            assert t1.difficulty == t2.difficulty

    def test_entity_tracking_task(self, task_generator):
        """Test entity tracking task generation."""
        task = task_generator._gen_entity_tracking(
            "task-1",
            BenchmarkCategory.FACTUAL_RECALL,
            BenchmarkSubcategory.ENTITY_TRACKING,
        )

        assert task.subcategory == BenchmarkSubcategory.ENTITY_TRACKING
        assert "entity" in task.input_data
        assert "entity" in task.expected_output

    def test_multi_step_inference_task(self, task_generator):
        """Test multi-step inference task generation."""
        task = task_generator._gen_multi_step_inference(
            "task-1",
            BenchmarkCategory.REASONING,
            BenchmarkSubcategory.MULTI_STEP_INFERENCE,
        )

        assert task.subcategory == BenchmarkSubcategory.MULTI_STEP_INFERENCE
        assert "steps" in task.input_data
        assert "result" in task.expected_output

    def test_singleton_management(self):
        """Test singleton getter and reset."""
        gen1 = get_task_generator(seed=42)
        gen2 = get_task_generator()

        assert gen1 is gen2

        reset_task_generator()
        gen3 = get_task_generator(seed=42)

        assert gen1 is not gen3


# =============================================================================
# BENCHMARK SUITE TESTS
# =============================================================================


class TestMemoryEvolutionBenchmark:
    """Tests for MemoryEvolutionBenchmark."""

    def test_init(self, benchmark_config):
        """Test benchmark initialization."""
        benchmark = MemoryEvolutionBenchmark(config=benchmark_config)

        assert benchmark.config == benchmark_config
        assert benchmark.drift_detector is not None
        assert benchmark.sampler is not None

    @pytest.mark.asyncio
    async def test_run_benchmark(self, benchmark_config, mock_agent, task_generator):
        """Test running a benchmark."""
        benchmark = MemoryEvolutionBenchmark(config=benchmark_config)

        tasks = task_generator.generate_tasks(BenchmarkCategory.FACTUAL_RECALL, count=5)

        result = await benchmark.run_benchmark(
            mock_agent, BenchmarkCategory.FACTUAL_RECALL, tasks
        )

        assert not result.skipped
        assert result.agent_id == "test-agent-1"
        assert result.category == BenchmarkCategory.FACTUAL_RECALL
        assert len(result.task_results) == 5

    @pytest.mark.asyncio
    async def test_run_benchmark_disabled(self, mock_agent, task_generator):
        """Test benchmark when disabled."""
        config = BenchmarkConfig(enabled=False)
        benchmark = MemoryEvolutionBenchmark(config=config)

        tasks = task_generator.generate_tasks(BenchmarkCategory.REASONING, count=5)

        result = await benchmark.run_benchmark(
            mock_agent, BenchmarkCategory.REASONING, tasks
        )

        assert result.skipped
        assert "disabled" in result.skip_reason.lower()

    @pytest.mark.asyncio
    async def test_run_benchmark_production_excluded(self, mock_agent, task_generator):
        """Test benchmark excluded in production."""
        config = BenchmarkConfig(
            exclude_production=True,
            allowed_environments=["dev", "qa"],
        )
        benchmark = MemoryEvolutionBenchmark(config=config)

        # Mock production environment
        with patch.object(benchmark.evolution_config, "environment", "prod"):
            tasks = task_generator.generate_tasks(BenchmarkCategory.REASONING, count=5)

            result = await benchmark.run_benchmark(
                mock_agent, BenchmarkCategory.REASONING, tasks
            )

            assert result.skipped
            assert "production" in result.skip_reason.lower()

    @pytest.mark.asyncio
    async def test_run_benchmark_insufficient_tasks(self, mock_agent):
        """Test benchmark with too few tasks."""
        config = BenchmarkConfig(
            min_tasks_for_scoring=10,
            allowed_environments=["dev", "qa", "staging", "prod", "test"],
            off_peak_only=False,
            base_sampling_rate=1.0,
            enabled=True,
        )
        benchmark = MemoryEvolutionBenchmark(config=config)

        tasks = [
            BenchmarkTask(
                task_id="task-1",
                category=BenchmarkCategory.REASONING,
                subcategory=BenchmarkSubcategory.PATTERN_RECOGNITION,
                description="Test",
                input_data={},
                expected_output={},
            )
        ]

        result = await benchmark.run_benchmark(
            mock_agent, BenchmarkCategory.REASONING, tasks
        )

        assert result.skipped
        assert "insufficient" in result.skip_reason.lower()

    @pytest.mark.asyncio
    async def test_capture_baseline(self, benchmark_config, mock_agent, task_generator):
        """Test baseline capture."""
        benchmark = MemoryEvolutionBenchmark(config=benchmark_config)

        baselines = await benchmark.capture_baseline(mock_agent, task_generator)

        assert len(baselines) == len(BenchmarkCategory)
        for category in BenchmarkCategory:
            assert category.value in baselines
            assert baselines[category.value].agent_id == "test-agent-1"

    @pytest.mark.asyncio
    async def test_run_full_benchmark(
        self, benchmark_config, mock_agent, task_generator
    ):
        """Test running full benchmark across all categories."""
        benchmark = MemoryEvolutionBenchmark(config=benchmark_config)

        summary = await benchmark.run_full_benchmark(mock_agent, task_generator)

        assert summary.agent_id == "test-agent-1"
        assert summary.benchmark_count == len(BenchmarkCategory)
        assert len(summary.category_scores) == len(BenchmarkCategory)

    @pytest.mark.asyncio
    async def test_score_result_exact_match(self, benchmark_config):
        """Test scoring with exact match."""
        benchmark = MemoryEvolutionBenchmark(config=benchmark_config)

        task = BenchmarkTask(
            task_id="task-1",
            category=BenchmarkCategory.FACTUAL_RECALL,
            subcategory=BenchmarkSubcategory.ENTITY_TRACKING,
            description="Test",
            input_data={},
            expected_output={"entity": "Alice", "role": "admin"},
        )

        # Exact match
        result = {"entity": "Alice", "role": "admin"}
        score = benchmark._score_result(task, result)

        assert score == 1.0

    @pytest.mark.asyncio
    async def test_score_result_partial_match(self, benchmark_config):
        """Test scoring with partial match."""
        benchmark = MemoryEvolutionBenchmark(config=benchmark_config)

        task = BenchmarkTask(
            task_id="task-1",
            category=BenchmarkCategory.FACTUAL_RECALL,
            subcategory=BenchmarkSubcategory.ENTITY_TRACKING,
            description="Test",
            input_data={},
            expected_output={"entity": "Alice", "role": "admin"},
        )

        # Partial match
        result = {"entity": "Alice", "role": "user"}
        score = benchmark._score_result(task, result)

        assert score == 0.5

    @pytest.mark.asyncio
    async def test_score_result_no_match(self, benchmark_config):
        """Test scoring with no match."""
        benchmark = MemoryEvolutionBenchmark(config=benchmark_config)

        task = BenchmarkTask(
            task_id="task-1",
            category=BenchmarkCategory.FACTUAL_RECALL,
            subcategory=BenchmarkSubcategory.ENTITY_TRACKING,
            description="Test",
            input_data={},
            expected_output={"entity": "Alice", "role": "admin"},
        )

        # No match
        result = {"entity": "Bob", "role": "user"}
        score = benchmark._score_result(task, result)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_compute_category_score(self, benchmark_config):
        """Test category score computation."""
        benchmark = MemoryEvolutionBenchmark(config=benchmark_config)

        results = [
            TaskResult("t1", True, {}, 0.8, 100),
            TaskResult("t2", True, {}, 0.6, 100),
            TaskResult("t3", False, {}, 0.0, 100),
        ]

        score = benchmark._compute_category_score(results)

        # Weighted by success: (0.8*1 + 0.6*1 + 0.0*0.5) / (1+1+0.5)
        expected = (0.8 + 0.6 + 0.0) / 2.5
        assert score == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_stores_result(
        self, benchmark_config, mock_agent, mock_metrics_store, task_generator
    ):
        """Test that results are stored."""
        benchmark = MemoryEvolutionBenchmark(
            config=benchmark_config,
            metrics_store=mock_metrics_store,
        )

        tasks = task_generator.generate_tasks(BenchmarkCategory.REASONING, count=5)

        await benchmark.run_benchmark(mock_agent, BenchmarkCategory.REASONING, tasks)

        mock_metrics_store.store_benchmark_result.assert_called_once()

    def test_singleton_management(self, benchmark_config):
        """Test singleton getter and reset."""
        benchmark1 = get_evolution_benchmark(config=benchmark_config)
        benchmark2 = get_evolution_benchmark()

        assert benchmark1 is benchmark2

        reset_evolution_benchmark()
        benchmark3 = get_evolution_benchmark(config=benchmark_config)

        assert benchmark1 is not benchmark3


# =============================================================================
# DRIFT RESULT TESTS
# =============================================================================


class TestDriftResult:
    """Tests for DriftResult dataclass."""

    def test_create_drift_result(self):
        """Test creating drift result."""
        result = DriftResult(
            psi_value=0.25,
            severity=DriftSeverity.MEDIUM,
            is_drifted=True,
            expected_distribution=[0.1] * 10,
            actual_distribution=[0.1] * 10,
            contributing_bins=[3, 7],
        )

        assert result.psi_value == 0.25
        assert result.is_drifted

    def test_to_dict(self):
        """Test serialization."""
        result = DriftResult(
            psi_value=0.15,
            severity=DriftSeverity.LOW,
            is_drifted=False,
            expected_distribution=[0.1] * 10,
            actual_distribution=[0.1] * 10,
            contributing_bins=[],
        )

        data = result.to_dict()

        assert data["psi_value"] == 0.15
        assert data["severity"] == "low"


# =============================================================================
# EVOLUTION METRICS SUMMARY TESTS
# =============================================================================


class TestEvolutionMetricsSummary:
    """Tests for EvolutionMetricsSummary dataclass."""

    def test_create_summary(self):
        """Test creating metrics summary."""
        summary = EvolutionMetricsSummary(
            agent_id="agent-1",
            overall_score=0.75,
            overall_evolution_delta=0.15,
            category_scores={
                "factual_recall": 0.8,
                "reasoning": 0.7,
            },
            category_deltas={
                "factual_recall": 0.1,
                "reasoning": 0.2,
            },
            drift_detected=False,
            anomaly_rate=0.0,
            benchmark_count=4,
        )

        assert summary.overall_score == 0.75
        assert summary.benchmark_count == 4

    def test_to_dict(self):
        """Test serialization."""
        summary = EvolutionMetricsSummary(
            agent_id="agent-1",
            overall_score=0.8,
            overall_evolution_delta=0.1,
            category_scores={},
            category_deltas={},
            drift_detected=True,
            anomaly_rate=0.25,
            benchmark_count=4,
        )

        data = summary.to_dict()

        assert data["agent_id"] == "agent-1"
        assert data["drift_detected"]
        assert "computed_at" in data


# =============================================================================
# BENCHMARK RESULT TESTS
# =============================================================================


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_create_successful_result(self):
        """Test creating successful benchmark result."""
        result = BenchmarkResult(
            result_id="result-1",
            agent_id="agent-1",
            category=BenchmarkCategory.FACTUAL_RECALL,
            score=0.85,
            baseline_score=0.70,
            evolution_delta=0.15,
            task_count=10,
            task_results=[],
        )

        assert result.score == 0.85
        assert result.evolution_delta == 0.15
        assert not result.skipped

    def test_create_skipped_result(self):
        """Test creating skipped benchmark result."""
        result = BenchmarkResult(
            result_id="result-1",
            agent_id="agent-1",
            category=BenchmarkCategory.REASONING,
            score=0.0,
            baseline_score=0.0,
            evolution_delta=0.0,
            task_count=0,
            task_results=[],
            skipped=True,
            skip_reason="Not sampled",
        )

        assert result.skipped
        assert result.skip_reason == "Not sampled"

    def test_to_dict(self):
        """Test serialization."""
        result = BenchmarkResult(
            result_id="result-1",
            agent_id="agent-1",
            category=BenchmarkCategory.STRATEGY_TRANSFER,
            score=0.9,
            baseline_score=0.75,
            evolution_delta=0.15,
            task_count=5,
            task_results=[],
            drift_result=DriftResult(
                psi_value=0.1,
                severity=DriftSeverity.NONE,
                is_drifted=False,
                expected_distribution=[],
                actual_distribution=[],
                contributing_bins=[],
            ),
        )

        data = result.to_dict()

        assert data["result_id"] == "result-1"
        assert data["category"] == "strategy_transfer"
        assert data["drift_result"]["psi_value"] == 0.1
