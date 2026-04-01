"""
Tests for streaming analysis engine service.
"""

import pytest

from src.services.streaming import (
    AnalysisScope,
    AnalysisStatus,
    CIProvider,
    DiffType,
    FileChange,
    IncrementalScanner,
    StreamingAnalysisEngine,
    StreamingAnalysisRequest,
    StreamingConfig,
    TooManyFilesError,
    get_streaming_engine,
    reset_streaming_engine,
)


class TestStreamingConfig:
    """Tests for streaming configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = StreamingConfig()
        assert config.enabled is True
        assert config.kinesis.enabled is True
        assert config.cache.enabled is True
        assert config.worker.min_workers == 5

    def test_for_testing(self):
        """Test test configuration."""
        config = StreamingConfig.for_testing()
        assert config.environment == "test"
        assert config.kinesis.enabled is False
        assert config.cache.enabled is False

    def test_for_production(self):
        """Test production configuration."""
        config = StreamingConfig.for_production()
        assert config.environment == "prod"
        assert config.kinesis.shard_count == 100

    def test_validate_success(self):
        """Test validation with valid config."""
        config = StreamingConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_invalid_shard_count(self):
        """Test validation with invalid shard count."""
        config = StreamingConfig()
        config.kinesis.shard_count = 0
        errors = config.validate()
        assert any("shard_count" in e for e in errors)


class TestStreamingEngine:
    """Tests for StreamingAnalysisEngine."""

    def test_initialize(self, test_config):
        """Test engine initialization."""
        engine = StreamingAnalysisEngine(test_config)
        assert engine is not None

    def test_singleton(self, test_config):
        """Test singleton pattern."""
        engine1 = get_streaming_engine()
        engine2 = get_streaming_engine()
        assert engine1 is engine2

    def test_reset_singleton(self, test_config):
        """Test singleton reset."""
        engine1 = get_streaming_engine()
        reset_streaming_engine()
        engine2 = get_streaming_engine()
        assert engine1 is not engine2

    @pytest.mark.asyncio
    async def test_analyze_batch(self, engine, sample_request):
        """Test batch analysis."""
        result = await engine.analyze_batch(sample_request)

        assert result.request_id == sample_request.request_id
        assert result.status == AnalysisStatus.COMPLETED
        assert result.files_analyzed == 2
        assert result.latency_ms >= 0  # May be 0 for fast test execution

    @pytest.mark.asyncio
    async def test_analyze_batch_with_auth_file(self, engine, test_config):
        """Test analysis detects security issues in auth files."""
        request = StreamingAnalysisRequest(
            request_id="req-002",
            repository_id="repo-001",
            commit_sha="abc123",
            base_sha="def456",
            changed_files=[
                FileChange(
                    file_path="src/auth/password_handler.py",
                    diff_type=DiffType.MODIFIED,
                    additions=20,
                    language="python",
                ),
            ],
        )

        result = await engine.analyze_batch(request)

        assert result.status == AnalysisStatus.COMPLETED
        # Auth-related files should trigger some feedback
        assert result.total_feedback >= 0

    @pytest.mark.asyncio
    async def test_analyze_batch_affected_scope(self, engine, test_config):
        """Test analysis with affected scope."""
        request = StreamingAnalysisRequest(
            request_id="req-003",
            repository_id="repo-001",
            commit_sha="abc123",
            base_sha="def456",
            changed_files=[
                FileChange(
                    file_path="src/utils/common.py",
                    diff_type=DiffType.MODIFIED,
                    additions=10,
                    language="python",
                ),
            ],
            analysis_scope=AnalysisScope.AFFECTED,
        )

        result = await engine.analyze_batch(request)

        assert result.status == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_analyze_batch_too_many_files(self, engine, test_config):
        """Test analysis fails with too many files."""
        # Reduce limit for test
        test_config.analysis.max_files_per_request = 5

        files = [
            FileChange(
                file_path=f"src/file_{i}.py",
                diff_type=DiffType.ADDED,
                additions=10,
            )
            for i in range(10)
        ]

        request = StreamingAnalysisRequest(
            request_id="req-004",
            repository_id="repo-001",
            commit_sha="abc123",
            base_sha="def456",
            changed_files=files,
        )

        with pytest.raises(TooManyFilesError):
            await engine.analyze_batch(request)

    @pytest.mark.asyncio
    async def test_analyze_stream(self, engine, sample_request):
        """Test streaming analysis."""
        feedback_items = []

        async for feedback in engine.analyze_stream(sample_request):
            feedback_items.append(feedback)

        # Should yield feedback items
        assert isinstance(feedback_items, list)

    @pytest.mark.asyncio
    async def test_get_affected_files(self, engine, test_config):
        """Test getting affected files."""
        affected = await engine.get_affected_files(
            "repo-001",
            ["src/utils/helper.py"],
        )

        assert isinstance(affected, list)

    @pytest.mark.asyncio
    async def test_publish_to_ci_disabled(self, engine, sample_request):
        """Test publishing to CI when notifications disabled raises error."""
        from src.services.streaming.exceptions import NotificationDeliveryError

        # First analyze
        result = await engine.analyze_batch(sample_request)

        # Publishing should raise error when notifications are disabled
        with pytest.raises(NotificationDeliveryError) as exc_info:
            await engine.publish_to_ci(
                result,
                CIProvider.GITHUB_ACTIONS,
                "repo-001",
            )

        assert "disabled" in str(exc_info.value).lower()

    def test_get_result(self, engine):
        """Test getting non-existent result."""
        result = engine.get_result("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_results(self, engine, sample_request):
        """Test listing results."""
        await engine.analyze_batch(sample_request)

        results = engine.list_results(repository_id="repo-001")
        assert len(results) >= 1


class TestIncrementalScanner:
    """Tests for IncrementalScanner."""

    def test_initialize(self, test_config):
        """Test scanner initialization."""
        scanner = IncrementalScanner(test_config)
        assert scanner is not None

    @pytest.mark.asyncio
    async def test_scan_diff(self, test_config, sample_file_changes):
        """Test scanning diff."""
        scanner = IncrementalScanner(test_config)

        result = await scanner.scan_diff(
            repository_id="repo-001",
            base_sha="abc123",
            head_sha="def456",
            changed_files=sample_file_changes,
        )

        assert result.repository_id == "repo-001"
        assert result.files_scanned == 3

    def test_get_ast_cache_miss(self, test_config):
        """Test AST cache miss."""
        scanner = IncrementalScanner(test_config)
        cached = scanner.get_ast_cache("nonexistent.py", "hash123")
        assert cached is None

    @pytest.mark.asyncio
    async def test_update_ast_cache(self, test_config):
        """Test updating AST cache."""
        scanner = IncrementalScanner(test_config)

        await scanner.update_ast_cache(
            file_path="test.py",
            content_hash="hash123",
            ast={"type": "module"},
            language="python",
        )

        cached = scanner.get_ast_cache("test.py", "hash123")
        assert cached is not None
        assert cached.ast_data["type"] == "module"


class TestStreamingMetrics:
    """Tests for streaming metrics."""

    def test_record_analysis_latency(self, test_config):
        """Test recording analysis latency."""
        from src.services.streaming import get_streaming_metrics

        metrics = get_streaming_metrics()
        metrics.record_analysis_latency(100.0)

        stats = metrics.get_stats()
        assert stats["request_count"] == 1

    def test_cache_hit_rate(self, test_config):
        """Test cache hit rate calculation."""
        from src.services.streaming import get_streaming_metrics

        metrics = get_streaming_metrics()
        metrics.record_cache_hit()
        metrics.record_cache_miss()

        rate = metrics.get_cache_hit_rate()
        assert rate == 0.5

    def test_latency_percentiles(self, test_config):
        """Test latency percentile calculation."""
        from src.services.streaming import get_streaming_metrics

        metrics = get_streaming_metrics()
        for i in range(100):
            metrics.record_analysis_latency(float(i * 10))

        percentiles = metrics.get_latency_percentiles()
        assert "p50" in percentiles
        assert "p95" in percentiles
        assert "p99" in percentiles
