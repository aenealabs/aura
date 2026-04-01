"""
Tests for SSR History-Aware Bug Injector.

Tests the history-aware bug injection service that uses git history
analysis and GraphRAG integration to create training artifacts.
"""

import platform
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.ssr.bug_artifact import InjectionStrategy
from src.services.ssr.git_analyzer import (
    AnalysisResult,
    AnalysisStatus,
    CommitInfo,
    RevertCandidate,
)
from src.services.ssr.history_injector import (
    CandidateRankingStrategy,
    EnrichedCandidate,
    GraphRAGContext,
    HistoryAwareBugInjector,
    InjectionResult,
    InjectionStatus,
    create_history_injector,
)

# Run tests in forked processes for isolation
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestInjectionStatusEnum:
    """Tests for InjectionStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all expected statuses exist."""
        expected = {
            "pending",
            "analyzing",
            "selecting",
            "injecting",
            "validating",
            "completed",
            "failed",
        }
        actual = {s.value for s in InjectionStatus}
        assert expected == actual


class TestCandidateRankingStrategyEnum:
    """Tests for CandidateRankingStrategy enum."""

    def test_all_strategies_defined(self):
        """Verify all expected strategies exist."""
        expected = {
            "complexity_first",
            "coverage_first",
            "balanced",
            "graphrag_enhanced",
        }
        actual = {s.value for s in CandidateRankingStrategy}
        assert expected == actual


class TestGraphRAGContext:
    """Tests for GraphRAGContext dataclass."""

    def test_context_creation(self):
        """Test creating a GraphRAG context."""
        context = GraphRAGContext(
            file_path="src/parser.py",
            function_name="parse_input",
            class_name="Parser",
            call_graph_depth=2,
            callers=["handler", "main"],
            callees=["validate", "transform"],
            dependencies=["json", "re"],
            dependents=["api_handler"],
            test_coverage=["tests/test_parser.py"],
            complexity_score=15.5,
            centrality_score=0.7,
        )

        assert context.file_path == "src/parser.py"
        assert context.function_name == "parse_input"
        assert context.class_name == "Parser"
        assert len(context.callers) == 2
        assert len(context.callees) == 2
        assert context.complexity_score == 15.5
        assert context.centrality_score == 0.7

    def test_context_serialization(self):
        """Test context serialization."""
        context = GraphRAGContext(
            file_path="file.py",
            callers=["a", "b"],
            complexity_score=10.0,
        )

        data = context.to_dict()
        assert data["file_path"] == "file.py"
        assert data["callers"] == ["a", "b"]
        assert data["complexity_score"] == 10.0

    def test_context_deserialization(self):
        """Test context deserialization."""
        data = {
            "file_path": "module.py",
            "function_name": "process",
            "callers": ["caller1"],
            "callees": ["callee1", "callee2"],
            "complexity_score": 20.0,
            "centrality_score": 0.8,
        }

        context = GraphRAGContext.from_dict(data)
        assert context.file_path == "module.py"
        assert context.function_name == "process"
        assert len(context.callees) == 2
        assert context.centrality_score == 0.8

    def test_context_default_values(self):
        """Test default values."""
        context = GraphRAGContext(file_path="file.py")

        assert context.function_name is None
        assert context.class_name is None
        assert context.call_graph_depth == 0
        assert context.callers == []
        assert context.callees == []
        assert context.dependencies == []
        assert context.dependents == []
        assert context.test_coverage == []
        assert context.complexity_score == 0.0
        assert context.centrality_score == 0.0


class TestEnrichedCandidate:
    """Tests for EnrichedCandidate dataclass."""

    @pytest.fixture
    def sample_commit(self):
        """Create a sample commit."""
        return CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="Author",
            author_email="author@test.com",
            date="2026-01-01T00:00:00Z",
            message="Fix bug",
            subject="Fix bug",
        )

    @pytest.fixture
    def sample_candidate(self, sample_commit):
        """Create a sample revert candidate."""
        return RevertCandidate(
            commit=sample_commit,
            diff_content="diff content",
            complexity_score=0.6,
            test_coverage_score=0.7,
            reversion_score=0.65,
        )

    def test_enriched_creation(self, sample_candidate):
        """Test creating an enriched candidate."""
        context = GraphRAGContext(
            file_path="file.py",
            complexity_score=15.0,
        )

        enriched = EnrichedCandidate(
            candidate=sample_candidate,
            graphrag_context=[context],
            enhanced_score=0.85,
            test_file_paths=["tests/test.py"],
            affected_components=["parser", "handler"],
            injection_difficulty=7,
            is_selected=True,
        )

        assert enriched.candidate == sample_candidate
        assert len(enriched.graphrag_context) == 1
        assert enriched.enhanced_score == 0.85
        assert enriched.injection_difficulty == 7
        assert enriched.is_selected is True

    def test_enriched_serialization(self, sample_candidate):
        """Test enriched candidate serialization."""
        enriched = EnrichedCandidate(
            candidate=sample_candidate,
            enhanced_score=0.9,
            injection_difficulty=8,
        )

        data = enriched.to_dict()
        assert "candidate" in data
        assert data["enhanced_score"] == 0.9
        assert data["injection_difficulty"] == 8

    def test_enriched_default_values(self, sample_candidate):
        """Test default values."""
        enriched = EnrichedCandidate(candidate=sample_candidate)

        assert enriched.graphrag_context == []
        assert enriched.enhanced_score == 0.0
        assert enriched.test_file_paths == []
        assert enriched.affected_components == []
        assert enriched.injection_difficulty == 5
        assert enriched.is_selected is False
        assert enriched.rejection_reason is None


class TestInjectionResult:
    """Tests for InjectionResult dataclass."""

    def test_result_creation(self):
        """Test creating an injection result."""
        result = InjectionResult(
            repository_id="repo-123",
            total_candidates_analyzed=10,
            graphrag_queries_executed=40,
            status=InjectionStatus.COMPLETED,
            duration_seconds=5.5,
        )

        assert result.repository_id == "repo-123"
        assert result.total_candidates_analyzed == 10
        assert result.graphrag_queries_executed == 40
        assert result.status == InjectionStatus.COMPLETED

    def test_result_serialization(self):
        """Test result serialization."""
        result = InjectionResult(
            repository_id="repo-456",
            status=InjectionStatus.FAILED,
            error_message="Test error",
        )

        data = result.to_dict()
        assert data["repository_id"] == "repo-456"
        assert data["status"] == "failed"
        assert data["error_message"] == "Test error"
        assert data["artifact"] is None

    def test_result_default_values(self):
        """Test default values."""
        result = InjectionResult(repository_id="repo")

        assert result.artifact is None
        assert result.candidate_used is None
        assert result.total_candidates_analyzed == 0
        assert result.graphrag_queries_executed == 0
        assert result.status == InjectionStatus.PENDING
        assert result.duration_seconds == 0.0
        assert result.completed_at is None
        assert result.error_message is None


class TestHistoryAwareBugInjector:
    """Tests for HistoryAwareBugInjector service."""

    @pytest.fixture
    def injector(self):
        """Create a HistoryAwareBugInjector instance."""
        return HistoryAwareBugInjector()

    def test_injector_initialization(self, injector):
        """Test injector initialization."""
        assert injector.min_test_coverage == 1
        assert injector.min_enhanced_score == 0.4
        assert injector.ranking_strategy == CandidateRankingStrategy.GRAPHRAG_ENHANCED
        assert injector.graphrag_timeout == 30

    def test_custom_initialization(self):
        """Test injector with custom parameters."""
        injector = HistoryAwareBugInjector(
            min_test_coverage=3,
            min_enhanced_score=0.6,
            max_graphrag_queries_per_candidate=10,
            ranking_strategy=CandidateRankingStrategy.COMPLEXITY_FIRST,
            graphrag_timeout_seconds=60,
        )

        assert injector.min_test_coverage == 3
        assert injector.min_enhanced_score == 0.6
        assert injector.max_graphrag_queries == 10
        assert injector.ranking_strategy == CandidateRankingStrategy.COMPLEXITY_FIRST
        assert injector.graphrag_timeout == 60

    def test_get_metrics(self, injector):
        """Test getting injector metrics."""
        metrics = injector.get_metrics()

        assert "total_injections" in metrics
        assert "successful_injections" in metrics
        assert "success_rate" in metrics
        assert "graphrag_queries_total" in metrics
        assert "min_test_coverage" in metrics
        assert "min_enhanced_score" in metrics
        assert "ranking_strategy" in metrics

    def test_query_templates_defined(self, injector):
        """Test GraphRAG query templates are defined."""
        assert "{repo_id}" in injector.CALL_GRAPH_QUERY
        assert "{file_path}" in injector.CALL_GRAPH_QUERY
        assert "{repo_id}" in injector.CALLERS_QUERY
        assert "{repo_id}" in injector.TEST_COVERAGE_QUERY
        assert "{repo_id}" in injector.COMPLEXITY_QUERY


class TestHistoryAwareBugInjectorMethods:
    """Tests for HistoryAwareBugInjector internal methods."""

    @pytest.fixture
    def injector(self):
        """Create injector instance."""
        return HistoryAwareBugInjector()

    @pytest.fixture
    def sample_commit(self):
        """Create sample commit."""
        return CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="Author",
            author_email="author@test.com",
            date="2026-01-01T00:00:00Z",
            message="Fix bug",
            subject="Fix bug",
            files_changed=["file.py"],
            insertions=20,
            deletions=10,
        )

    @pytest.fixture
    def sample_candidate(self, sample_commit):
        """Create sample candidate."""
        return RevertCandidate(
            commit=sample_commit,
            diff_content="diff content",
            affected_functions=["parse"],
            affected_classes=["Parser"],
            test_files=["tests/test.py"],
            reversion_score=0.7,
        )

    def test_extract_test_files(self, injector):
        """Test extracting test files from contexts."""
        contexts = [
            GraphRAGContext(
                file_path="file1.py",
                test_coverage=["tests/test1.py", "tests/test2.py"],
            ),
            GraphRAGContext(
                file_path="file2.py",
                test_coverage=["tests/test2.py", "tests/test3.py"],
            ),
        ]

        test_files = injector._extract_test_files(contexts)

        # Should have unique test files
        assert len(test_files) == 3
        assert "tests/test1.py" in test_files
        assert "tests/test2.py" in test_files
        assert "tests/test3.py" in test_files

    def test_calculate_enhanced_score_no_contexts(self, injector, sample_candidate):
        """Test enhanced score without contexts."""
        score = injector._calculate_enhanced_score(sample_candidate, [])
        assert score == sample_candidate.reversion_score

    def test_calculate_enhanced_score_with_contexts(self, injector, sample_candidate):
        """Test enhanced score with contexts."""
        contexts = [
            GraphRAGContext(
                file_path="file.py",
                test_coverage=["t1.py", "t2.py", "t3.py"],
                complexity_score=15.0,
                centrality_score=0.6,
            )
        ]

        score = injector._calculate_enhanced_score(sample_candidate, contexts)

        # Score should be enhanced beyond base
        assert score > sample_candidate.reversion_score

    def test_estimate_difficulty(self, injector, sample_candidate):
        """Test difficulty estimation."""
        contexts = [
            GraphRAGContext(
                file_path="file.py",
                complexity_score=20.0,
                callers=["a", "b", "c"],
                callees=["x", "y"],
            )
        ]

        difficulty = injector._estimate_difficulty(sample_candidate, contexts)

        # Difficulty should be between 1 and 10
        assert 1 <= difficulty <= 10

    def test_estimate_difficulty_no_contexts(self, injector, sample_candidate):
        """Test difficulty estimation without contexts."""
        difficulty = injector._estimate_difficulty(sample_candidate, [])
        assert 1 <= difficulty <= 10

    def test_rank_candidates_complexity_first(self, injector, sample_commit):
        """Test ranking by complexity."""
        injector.ranking_strategy = CandidateRankingStrategy.COMPLEXITY_FIRST

        candidates = [
            EnrichedCandidate(
                candidate=RevertCandidate(
                    commit=sample_commit,
                    complexity_score=0.3,
                ),
            ),
            EnrichedCandidate(
                candidate=RevertCandidate(
                    commit=sample_commit,
                    complexity_score=0.8,
                ),
            ),
            EnrichedCandidate(
                candidate=RevertCandidate(
                    commit=sample_commit,
                    complexity_score=0.5,
                ),
            ),
        ]

        ranked = injector._rank_candidates(candidates)

        # Should be sorted by complexity descending
        assert ranked[0].candidate.complexity_score == 0.8
        assert ranked[1].candidate.complexity_score == 0.5
        assert ranked[2].candidate.complexity_score == 0.3

    def test_rank_candidates_coverage_first(self, injector, sample_commit):
        """Test ranking by coverage."""
        injector.ranking_strategy = CandidateRankingStrategy.COVERAGE_FIRST

        candidates = [
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                test_file_paths=["t1.py"],
            ),
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                test_file_paths=["t1.py", "t2.py", "t3.py"],
            ),
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                test_file_paths=["t1.py", "t2.py"],
            ),
        ]

        ranked = injector._rank_candidates(candidates)

        # Should be sorted by test coverage descending
        assert len(ranked[0].test_file_paths) == 3
        assert len(ranked[1].test_file_paths) == 2
        assert len(ranked[2].test_file_paths) == 1

    def test_rank_candidates_graphrag_enhanced(self, injector, sample_commit):
        """Test ranking by enhanced score."""
        injector.ranking_strategy = CandidateRankingStrategy.GRAPHRAG_ENHANCED

        candidates = [
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                enhanced_score=0.4,
            ),
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                enhanced_score=0.9,
            ),
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                enhanced_score=0.6,
            ),
        ]

        ranked = injector._rank_candidates(candidates)

        # Should be sorted by enhanced score descending
        assert ranked[0].enhanced_score == 0.9
        assert ranked[1].enhanced_score == 0.6
        assert ranked[2].enhanced_score == 0.4

    def test_select_best_candidate_success(self, injector, sample_commit):
        """Test selecting best candidate that meets criteria."""
        candidates = [
            EnrichedCandidate(
                candidate=RevertCandidate(
                    commit=sample_commit,
                    is_safe_to_revert=True,
                ),
                test_file_paths=["t1.py", "t2.py"],
                enhanced_score=0.8,
            ),
        ]

        selected = injector._select_best_candidate(candidates)

        assert selected is not None
        assert selected.enhanced_score == 0.8

    def test_select_best_candidate_insufficient_coverage(self, injector, sample_commit):
        """Test rejection due to insufficient test coverage."""
        injector.min_test_coverage = 3

        candidates = [
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                test_file_paths=["t1.py"],  # Only 1 test file
                enhanced_score=0.9,
            ),
        ]

        selected = injector._select_best_candidate(candidates)
        assert selected is None
        assert candidates[0].rejection_reason == "Insufficient test coverage"

    def test_select_best_candidate_low_score(self, injector, sample_commit):
        """Test rejection due to low score."""
        candidates = [
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                test_file_paths=["t1.py"],
                enhanced_score=0.2,  # Below threshold
            ),
        ]

        selected = injector._select_best_candidate(candidates)
        assert selected is None
        assert candidates[0].rejection_reason == "Score below threshold"

    def test_select_best_candidate_not_safe(self, injector, sample_commit):
        """Test rejection due to unsafe candidate."""
        candidates = [
            EnrichedCandidate(
                candidate=RevertCandidate(
                    commit=sample_commit,
                    is_safe_to_revert=False,
                    exclusion_reason="Contains secrets",
                ),
                test_file_paths=["t1.py"],
                enhanced_score=0.9,
            ),
        ]

        selected = injector._select_best_candidate(candidates)
        assert selected is None

    def test_reverse_diff(self, injector):
        """Test reversing a diff."""
        diff = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 line1
-removed_line
+added_line
 line2
"""
        reversed_diff = injector._reverse_diff(diff)

        # + and - should be swapped
        assert "-added_line" in reversed_diff
        assert "+removed_line" in reversed_diff

    def test_generate_test_script_python(self, injector):
        """Test generating test script for Python files."""
        test_files = ["tests/test_parser.py", "tests/test_handler.py"]

        script = injector._generate_test_script(test_files)

        assert "#!/bin/bash" in script
        assert "pytest" in script
        assert "test_parser.py" in script

    def test_generate_test_script_javascript(self, injector):
        """Test generating test script for JavaScript files."""
        test_files = ["__tests__/parser.test.js"]

        script = injector._generate_test_script(test_files)

        assert "npm test" in script

    def test_generate_test_parser(self, injector):
        """Test generating test parser."""
        parser = injector._generate_test_parser()

        assert "#!/usr/bin/env python3" in parser
        assert "json" in parser
        assert "parse_pytest_output" in parser

    def test_count_queries(self, injector, sample_commit):
        """Test counting GraphRAG queries."""
        candidates = [
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                graphrag_context=[
                    GraphRAGContext(file_path="f1.py"),
                    GraphRAGContext(file_path="f2.py"),
                ],
            ),
            EnrichedCandidate(
                candidate=RevertCandidate(commit=sample_commit),
                graphrag_context=[
                    GraphRAGContext(file_path="f3.py"),
                ],
            ),
        ]

        count = injector._count_queries(candidates)
        # 3 contexts * 4 queries per context = 12
        assert count == 12


class TestHistoryAwareBugInjectorAsync:
    """Async tests for HistoryAwareBugInjector."""

    @pytest.fixture
    def mock_git_analyzer(self):
        """Create mock git analyzer."""
        analyzer = MagicMock()
        analyzer.analyze_repository = AsyncMock()
        return analyzer

    @pytest.fixture
    def injector_with_mock(self, mock_git_analyzer):
        """Create injector with mock analyzer."""
        return HistoryAwareBugInjector(
            git_analyzer=mock_git_analyzer,
            graph_service=None,
        )

    @pytest.mark.asyncio
    async def test_inject_no_candidates(self, injector_with_mock, mock_git_analyzer):
        """Test injection when no candidates found."""
        mock_git_analyzer.analyze_repository.return_value = AnalysisResult(
            repository_id="repo-123",
            repository_path="/path",
            revert_candidates=[],
            status=AnalysisStatus.COMPLETED,
        )

        result = await injector_with_mock.inject_from_history(
            repository_id="repo-123",
            repository_path="/path",
        )

        assert result.status == InjectionStatus.FAILED
        assert "No suitable bug-fix commits" in result.error_message

    @pytest.mark.asyncio
    async def test_inject_with_candidates(self, injector_with_mock, mock_git_analyzer):
        """Test successful injection with candidates."""
        commit = CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="Author",
            author_email="author@test.com",
            date="2026-01-01T00:00:00Z",
            message="Fix bug",
            subject="Fix bug",
            files_changed=["file.py"],
        )

        candidate = RevertCandidate(
            commit=commit,
            diff_content="diff content",
            test_files=["tests/test.py"],
            reversion_score=0.8,
            is_safe_to_revert=True,
        )

        mock_git_analyzer.analyze_repository.return_value = AnalysisResult(
            repository_id="repo-123",
            repository_path="/path",
            revert_candidates=[candidate],
            status=AnalysisStatus.COMPLETED,
        )

        result = await injector_with_mock.inject_from_history(
            repository_id="repo-123",
            repository_path="/path",
        )

        assert result.status == InjectionStatus.COMPLETED
        assert result.artifact is not None
        assert result.artifact.injection_strategy == InjectionStrategy.HISTORY_AWARE


class TestCreateHistoryInjector:
    """Tests for create_history_injector factory function."""

    def test_create_with_defaults(self):
        """Test creating injector with defaults."""
        injector = create_history_injector()

        assert injector.min_test_coverage == 1
        assert injector.min_enhanced_score == 0.4
        assert injector.graph_service is None

    def test_create_with_custom_values(self):
        """Test creating injector with custom values."""
        injector = create_history_injector(
            min_test_coverage=3,
            min_enhanced_score=0.7,
        )

        assert injector.min_test_coverage == 3
        assert injector.min_enhanced_score == 0.7

    def test_create_with_graph_service(self):
        """Test creating injector with graph service."""
        mock_graph = MagicMock()

        injector = create_history_injector(graph_service=mock_graph)

        assert injector.graph_service == mock_graph
