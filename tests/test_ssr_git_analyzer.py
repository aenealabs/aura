"""
Tests for SSR Git History Analyzer.

Tests the git history analysis for identifying bug-fix commits
that can be used for history-aware bug injection.
"""

import pytest

from src.services.ssr.git_analyzer import (
    AnalysisResult,
    AnalysisStatus,
    CommitCategory,
    CommitInfo,
    GitHistoryAnalyzer,
    RevertCandidate,
    create_git_analyzer,
)

# Run tests in forked processes for isolation
# Note: pytest.mark.forked disabled for accurate coverage measurement
# pytestmark = pytest.mark.forked


class TestCommitCategoryEnum:
    """Tests for CommitCategory enum."""

    def test_all_categories_defined(self):
        """Verify all expected categories exist."""
        expected = {
            "bug_fix",
            "feature",
            "refactor",
            "security",
            "performance",
            "documentation",
            "test",
            "chore",
            "unknown",
        }
        actual = {c.value for c in CommitCategory}
        assert expected == actual

    def test_bug_fix_category(self):
        """Test bug fix category value."""
        assert CommitCategory.BUG_FIX.value == "bug_fix"

    def test_security_category(self):
        """Test security category value."""
        assert CommitCategory.SECURITY.value == "security"


class TestAnalysisStatusEnum:
    """Tests for AnalysisStatus enum."""

    def test_all_statuses_defined(self):
        """Verify all expected statuses exist."""
        expected = {"pending", "in_progress", "completed", "failed"}
        actual = {s.value for s in AnalysisStatus}
        assert expected == actual


class TestCommitInfo:
    """Tests for CommitInfo dataclass."""

    def test_commit_creation(self):
        """Test creating a commit info object."""
        commit = CommitInfo(
            sha="abc123def456",
            short_sha="abc123d",
            author="Test Author",
            author_email="test@example.com",
            date="2026-01-01T00:00:00Z",
            message="Fix bug in parser\n\nDetailed description",
            subject="Fix bug in parser",
            files_changed=["src/parser.py", "tests/test_parser.py"],
            insertions=10,
            deletions=5,
            category=CommitCategory.BUG_FIX,
        )

        assert commit.sha == "abc123def456"
        assert commit.short_sha == "abc123d"
        assert commit.author == "Test Author"
        assert commit.category == CommitCategory.BUG_FIX
        assert len(commit.files_changed) == 2

    def test_commit_serialization(self):
        """Test serialization to dictionary."""
        commit = CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="Author",
            author_email="author@test.com",
            date="2026-01-01T00:00:00Z",
            message="Fix issue",
            subject="Fix issue",
        )

        data = commit.to_dict()
        assert data["sha"] == "abc123"
        assert data["author"] == "Author"
        assert data["category"] == "unknown"

    def test_commit_deserialization(self):
        """Test deserialization from dictionary."""
        data = {
            "sha": "def456",
            "short_sha": "def",
            "author": "Another Author",
            "author_email": "another@test.com",
            "date": "2026-01-01T00:00:00Z",
            "message": "Bug fix",
            "subject": "Bug fix",
            "files_changed": ["file.py"],
            "insertions": 5,
            "deletions": 3,
            "category": "bug_fix",
        }

        commit = CommitInfo.from_dict(data)
        assert commit.sha == "def456"
        assert commit.category == CommitCategory.BUG_FIX
        assert commit.insertions == 5

    def test_commit_default_values(self):
        """Test default values for optional fields."""
        commit = CommitInfo(
            sha="test",
            short_sha="tes",
            author="Author",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Msg",
            subject="Msg",
        )

        assert commit.files_changed == []
        assert commit.insertions == 0
        assert commit.deletions == 0
        assert commit.category == CommitCategory.UNKNOWN


class TestRevertCandidate:
    """Tests for RevertCandidate dataclass."""

    def test_candidate_creation(self):
        """Test creating a revert candidate."""
        commit = CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="Author",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix",
            subject="Fix",
        )

        candidate = RevertCandidate(
            commit=commit,
            diff_content="diff --git a/file.py b/file.py\n",
            affected_functions=["parse", "validate"],
            affected_classes=["Parser"],
            test_files=["tests/test_parser.py"],
            complexity_score=0.7,
            test_coverage_score=0.8,
            reversion_score=0.75,
            is_safe_to_revert=True,
        )

        assert candidate.commit.sha == "abc123"
        assert len(candidate.affected_functions) == 2
        assert candidate.reversion_score == 0.75
        assert candidate.is_safe_to_revert is True

    def test_candidate_serialization(self):
        """Test candidate serialization."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="M",
            subject="M",
        )

        candidate = RevertCandidate(
            commit=commit,
            complexity_score=0.5,
            test_coverage_score=0.6,
        )

        data = candidate.to_dict()
        assert "commit" in data
        assert data["complexity_score"] == 0.5
        assert data["is_safe_to_revert"] is True

    def test_candidate_deserialization(self):
        """Test candidate deserialization."""
        data = {
            "commit": {
                "sha": "xyz",
                "short_sha": "x",
                "author": "B",
                "author_email": "b@c.com",
                "date": "2026-01-01T00:00:00Z",
                "message": "N",
                "subject": "N",
            },
            "diff_content": "diff content",
            "affected_functions": ["func1"],
            "complexity_score": 0.9,
            "test_coverage_score": 0.85,
            "reversion_score": 0.87,
            "is_safe_to_revert": False,
            "exclusion_reason": "Contains secrets",
        }

        candidate = RevertCandidate.from_dict(data)
        assert candidate.commit.sha == "xyz"
        assert candidate.complexity_score == 0.9
        assert candidate.is_safe_to_revert is False
        assert candidate.exclusion_reason == "Contains secrets"

    def test_candidate_default_values(self):
        """Test default values."""
        commit = CommitInfo(
            sha="a",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="M",
            subject="M",
        )
        candidate = RevertCandidate(commit=commit)

        assert candidate.diff_content == ""
        assert candidate.affected_functions == []
        assert candidate.affected_classes == []
        assert candidate.test_files == []
        assert candidate.complexity_score == 0.0
        assert candidate.test_coverage_score == 0.0
        assert candidate.reversion_score == 0.0
        assert candidate.is_safe_to_revert is True
        assert candidate.exclusion_reason is None


class TestAnalysisResult:
    """Tests for AnalysisResult dataclass."""

    def test_result_creation(self):
        """Test creating an analysis result."""
        result = AnalysisResult(
            repository_id="repo-123",
            repository_path="/path/to/repo",
            total_commits_analyzed=100,
            bug_fix_commits_found=25,
            status=AnalysisStatus.COMPLETED,
        )

        assert result.repository_id == "repo-123"
        assert result.total_commits_analyzed == 100
        assert result.bug_fix_commits_found == 25
        assert result.status == AnalysisStatus.COMPLETED

    def test_result_serialization(self):
        """Test result serialization."""
        result = AnalysisResult(
            repository_id="repo-456",
            repository_path="/path",
            status=AnalysisStatus.PENDING,
        )

        data = result.to_dict()
        assert data["repository_id"] == "repo-456"
        assert data["status"] == "pending"
        assert data["revert_candidates"] == []

    def test_result_with_candidates(self):
        """Test result with revert candidates."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="M",
            subject="M",
        )
        candidate = RevertCandidate(commit=commit, reversion_score=0.8)

        result = AnalysisResult(
            repository_id="repo-789",
            repository_path="/path",
            revert_candidates=[candidate],
            status=AnalysisStatus.COMPLETED,
        )

        assert len(result.revert_candidates) == 1
        assert result.revert_candidates[0].reversion_score == 0.8

    def test_result_default_values(self):
        """Test default values."""
        result = AnalysisResult(
            repository_id="repo",
            repository_path="/path",
        )

        assert result.total_commits_analyzed == 0
        assert result.bug_fix_commits_found == 0
        assert result.revert_candidates == []
        assert result.excluded_commits == []
        assert result.analysis_duration_seconds == 0.0
        assert result.status == AnalysisStatus.PENDING
        assert result.completed_at is None
        assert result.error_message is None


class TestGitHistoryAnalyzer:
    """Tests for GitHistoryAnalyzer service."""

    @pytest.fixture
    def analyzer(self):
        """Create a GitHistoryAnalyzer instance."""
        return GitHistoryAnalyzer()

    def test_analyzer_initialization(self, analyzer):
        """Test analyzer initialization."""
        assert analyzer.max_diff_size_bytes == 100_000
        assert analyzer.min_test_coverage_score == 0.3
        assert analyzer.min_complexity_score == 0.2
        assert analyzer.git_timeout_seconds == 30

    def test_custom_initialization(self):
        """Test analyzer with custom parameters."""
        analyzer = GitHistoryAnalyzer(
            max_diff_size_bytes=50_000,
            min_test_coverage_score=0.5,
            min_complexity_score=0.4,
            excluded_authors=["bot@example.com"],
            git_timeout_seconds=60,
        )

        assert analyzer.max_diff_size_bytes == 50_000
        assert analyzer.min_test_coverage_score == 0.5
        assert analyzer.min_complexity_score == 0.4
        assert "bot@example.com" in analyzer.excluded_authors
        assert analyzer.git_timeout_seconds == 60

    def test_default_excluded_authors(self, analyzer):
        """Test default excluded authors list."""
        assert "noreply@github.com" in analyzer.excluded_authors
        assert "dependabot[bot]@users.noreply.github.com" in analyzer.excluded_authors
        assert "renovate[bot]@users.noreply.github.com" in analyzer.excluded_authors

    def test_bug_fix_patterns(self, analyzer):
        """Test bug fix patterns are defined."""
        patterns = analyzer.BUG_FIX_PATTERNS
        assert "fix" in patterns
        assert "bug" in patterns
        assert "issue" in patterns
        assert "crash" in patterns

    def test_security_patterns(self, analyzer):
        """Test security patterns are defined."""
        patterns = analyzer.SECURITY_PATTERNS
        assert "security" in patterns
        assert "cve" in patterns
        assert "vulnerability" in patterns

    def test_excluded_file_patterns(self, analyzer):
        """Test excluded file patterns are defined."""
        patterns = analyzer.EXCLUDED_FILE_PATTERNS
        assert ".env" in patterns
        assert "secret" in patterns
        assert "password" in patterns

    def test_get_metrics(self, analyzer):
        """Test getting analyzer metrics."""
        metrics = analyzer.get_metrics()

        assert "total_commits_analyzed" in metrics
        assert "total_candidates_found" in metrics
        assert "max_diff_size_bytes" in metrics
        assert "min_test_coverage_score" in metrics
        assert "min_complexity_score" in metrics
        assert "excluded_authors_count" in metrics

    def test_categorize_bug_fix_commit(self, analyzer):
        """Test categorizing a bug fix commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix parsing error in handler",
            subject="Fix parsing error in handler",
        )

        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.BUG_FIX

    def test_categorize_feature_commit(self, analyzer):
        """Test categorizing a feature commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Add new API endpoint",
            subject="Add new API endpoint",
        )

        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.FEATURE

    def test_categorize_security_commit(self, analyzer):
        """Test categorizing a security commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix security vulnerability CVE-2025-1234",
            subject="Fix security vulnerability CVE-2025-1234",
        )

        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.SECURITY

    def test_categorize_refactor_commit(self, analyzer):
        """Test categorizing a refactor commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Refactor database layer",
            subject="Refactor database layer",
        )

        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.REFACTOR

    def test_extract_functions_from_python_diff(self, analyzer):
        """Test extracting function names from Python diff."""
        diff = """
+def parse_input(data):
+    return data.strip()
+
+def validate_output(result):
+    return result is not None
"""
        functions = analyzer._extract_functions_from_diff(diff)
        assert "parse_input" in functions
        assert "validate_output" in functions

    def test_extract_classes_from_python_diff(self, analyzer):
        """Test extracting class names from Python diff."""
        diff = """
+class DataParser:
+    def __init__(self):
+        pass
+
+class ResultValidator:
+    pass
"""
        classes = analyzer._extract_classes_from_diff(diff)
        assert "DataParser" in classes
        assert "ResultValidator" in classes

    def test_find_test_files(self, analyzer):
        """Test finding test files from changed files."""
        changed_files = [
            "src/parser.py",
            "src/handler.py",
            "tests/test_parser.py",
        ]

        test_files = analyzer._find_test_files(changed_files)
        assert "tests/test_parser.py" in test_files

    def test_score_candidate(self, analyzer):
        """Test scoring a revert candidate."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix",
            subject="Fix",
            files_changed=["file1.py", "file2.py"],
            insertions=50,
            deletions=20,
        )

        candidate = RevertCandidate(
            commit=commit,
            affected_functions=["func1", "func2"],
            affected_classes=["Class1"],
            test_files=["tests/test.py"],
        )

        scored = analyzer._score_candidate(candidate)

        assert scored.complexity_score > 0
        assert scored.test_coverage_score > 0
        assert scored.reversion_score > 0

    def test_meets_threshold(self, analyzer):
        """Test threshold checking."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix",
            subject="Fix",
        )

        # Candidate that meets thresholds
        good_candidate = RevertCandidate(
            commit=commit,
            complexity_score=0.5,
            test_coverage_score=0.5,
        )
        assert analyzer._meets_threshold(good_candidate) is True

        # Candidate that doesn't meet thresholds
        bad_candidate = RevertCandidate(
            commit=commit,
            complexity_score=0.1,
            test_coverage_score=0.1,
        )
        assert analyzer._meets_threshold(bad_candidate) is False


class TestGitHistoryAnalyzerCommitLog:
    """Tests for commit log parsing."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    def test_parse_empty_log(self, analyzer):
        """Test parsing empty log output."""
        commits = analyzer._parse_commit_log("")
        assert commits == []

    def test_parse_single_commit(self, analyzer):
        """Test parsing a single commit."""
        log_output = "abc123|abc123d|Author|author@test.com|2026-01-01T00:00:00Z|Fix bug|Body text|||\n1\t0\tfile.py"

        commits = analyzer._parse_commit_log(log_output)
        assert len(commits) == 1
        assert commits[0].sha == "abc123"
        assert commits[0].author == "Author"
        assert commits[0].subject == "Fix bug"

    def test_parse_multiple_commits(self, analyzer):
        """Test parsing multiple commits."""
        log_output = """abc123|abc|Auth1|a@b.com|2026-01-01T00:00:00Z|Fix 1|Body 1|||
1\t1\tfile1.py
def456|def|Auth2|c@d.com|2026-01-01T00:00:00Z|Fix 2|Body 2|||
2\t2\tfile2.py"""

        commits = analyzer._parse_commit_log(log_output)
        assert len(commits) == 2
        assert commits[0].sha == "abc123"
        assert commits[1].sha == "def456"


class TestCreateGitAnalyzer:
    """Tests for create_git_analyzer factory function."""

    def test_create_with_defaults(self):
        """Test creating analyzer with defaults."""
        analyzer = create_git_analyzer()

        assert analyzer.max_diff_size_bytes == 100_000
        assert analyzer.min_test_coverage_score == 0.3
        assert analyzer.min_complexity_score == 0.2

    def test_create_with_custom_values(self):
        """Test creating analyzer with custom values."""
        analyzer = create_git_analyzer(
            max_diff_size_bytes=50_000,
            min_test_coverage_score=0.6,
            min_complexity_score=0.5,
        )

        assert analyzer.max_diff_size_bytes == 50_000
        assert analyzer.min_test_coverage_score == 0.6
        assert analyzer.min_complexity_score == 0.5


class TestCategorizeCommitAdditional:
    """Additional tests for _categorize_commit to cover all categories."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    def test_categorize_performance_commit(self, analyzer):
        """Test categorizing a performance commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Optimize database queries for faster response",
            subject="perf: optimize database queries",
        )
        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.PERFORMANCE

    def test_categorize_documentation_commit(self, analyzer):
        """Test categorizing a documentation commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Update API documentation",
            subject="docs: update API readme",
        )
        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.DOCUMENTATION

    def test_categorize_test_commit(self, analyzer):
        """Test categorizing a test commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Improve test coverage for parser",
            subject="test: improve parser coverage",
        )
        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.TEST

    def test_categorize_chore_commit(self, analyzer):
        """Test categorizing a chore commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Update CI configuration",
            subject="chore: update CI config",
        )
        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.CHORE

    def test_categorize_unknown_commit(self, analyzer):
        """Test categorizing an unrecognized commit."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Random update to something",
            subject="random update",
        )
        category = analyzer._categorize_commit(commit)
        assert category == CommitCategory.UNKNOWN


class TestFilterBugFixCommits:
    """Tests for _filter_bug_fix_commits method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    def test_filter_finds_bug_fixes(self, analyzer):
        """Test filtering for bug fix commits."""
        commits = [
            CommitInfo(
                sha="abc1",
                short_sha="a1",
                author="A",
                author_email="a@b.com",
                date="2026-01-01T00:00:00Z",
                message="Fix null pointer exception",
                subject="Fix null pointer exception",
            ),
            CommitInfo(
                sha="abc2",
                short_sha="a2",
                author="A",
                author_email="a@b.com",
                date="2026-01-01T00:00:00Z",
                message="Add new feature",
                subject="feat: add new feature",
            ),
            CommitInfo(
                sha="abc3",
                short_sha="a3",
                author="A",
                author_email="a@b.com",
                date="2026-01-01T00:00:00Z",
                message="Fix typo in variable name",
                subject="fix: typo in variable",
            ),
        ]

        bug_fixes = analyzer._filter_bug_fix_commits(commits)
        assert len(bug_fixes) == 2
        assert all(c.category == CommitCategory.BUG_FIX for c in bug_fixes)

    def test_filter_excludes_bot_authors(self, analyzer):
        """Test that excluded authors are filtered out."""
        commits = [
            CommitInfo(
                sha="abc1",
                short_sha="a1",
                author="Dependabot",
                author_email="dependabot[bot]@users.noreply.github.com",
                date="2026-01-01T00:00:00Z",
                message="Fix dependency issue",
                subject="fix: update dependencies",
            ),
            CommitInfo(
                sha="abc2",
                short_sha="a2",
                author="Human Developer",
                author_email="dev@example.com",
                date="2026-01-01T00:00:00Z",
                message="Fix actual bug",
                subject="fix: resolve actual bug",
            ),
        ]

        bug_fixes = analyzer._filter_bug_fix_commits(commits)
        assert len(bug_fixes) == 1
        assert bug_fixes[0].author_email == "dev@example.com"


class TestProcessCommit:
    """Tests for _process_commit method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    @pytest.mark.asyncio
    async def test_process_commit_with_excluded_files(self, analyzer):
        """Test that commits with excluded files are marked unsafe."""
        commit = CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix config",
            subject="Fix config",
            files_changed=[".env.production", "src/main.py"],
        )

        candidate = await analyzer._process_commit("/fake/path", commit)

        assert candidate.is_safe_to_revert is False
        assert "excluded file" in candidate.exclusion_reason.lower()

    @pytest.mark.asyncio
    async def test_process_commit_security_excluded(self, analyzer):
        """Test that security commits are excluded."""
        commit = CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix security vulnerability",
            subject="Fix security vulnerability",
            files_changed=["src/auth.py"],
            category=CommitCategory.SECURITY,
        )

        candidate = await analyzer._process_commit("/fake/path", commit)

        assert candidate.is_safe_to_revert is False
        assert "security" in candidate.exclusion_reason.lower()

    @pytest.mark.asyncio
    async def test_process_commit_diff_failure(self, analyzer):
        """Test handling when diff retrieval fails."""
        from unittest.mock import AsyncMock, patch

        commit = CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix bug",
            subject="Fix bug",
            files_changed=["src/parser.py"],
            category=CommitCategory.BUG_FIX,
        )

        with patch.object(
            analyzer,
            "_get_commit_diff",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Git command failed"),
        ):
            candidate = await analyzer._process_commit("/fake/path", commit)

        assert candidate.is_safe_to_revert is False
        assert "diff" in candidate.exclusion_reason.lower()

    @pytest.mark.asyncio
    async def test_process_commit_diff_too_large(self, analyzer):
        """Test that large diffs are excluded."""
        from unittest.mock import AsyncMock, patch

        # Create analyzer with small max diff size
        analyzer = GitHistoryAnalyzer(max_diff_size_bytes=100)

        commit = CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix bug",
            subject="Fix bug",
            files_changed=["src/parser.py"],
            category=CommitCategory.BUG_FIX,
        )

        large_diff = "x" * 200  # Exceeds 100 byte limit

        with patch.object(
            analyzer,
            "_get_commit_diff",
            new_callable=AsyncMock,
            return_value=large_diff,
        ):
            candidate = await analyzer._process_commit("/fake/path", commit)

        assert candidate.is_safe_to_revert is False
        assert "too large" in candidate.exclusion_reason.lower()

    @pytest.mark.asyncio
    async def test_process_commit_success(self, analyzer):
        """Test successful commit processing."""
        from unittest.mock import AsyncMock, patch

        commit = CommitInfo(
            sha="abc123",
            short_sha="abc",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix parsing bug",
            subject="Fix parsing bug",
            files_changed=["src/parser.py", "tests/test_parser.py"],
            category=CommitCategory.BUG_FIX,
        )

        diff_content = """+def fixed_function():
+    return "fixed"
"""

        with patch.object(
            analyzer,
            "_get_commit_diff",
            new_callable=AsyncMock,
            return_value=diff_content,
        ):
            candidate = await analyzer._process_commit("/fake/path", commit)

        assert candidate.is_safe_to_revert is True
        assert candidate.diff_content == diff_content
        assert "fixed_function" in candidate.affected_functions


class TestGetCommitDiff:
    """Tests for _get_commit_diff method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    @pytest.mark.asyncio
    async def test_get_commit_diff_success(self, analyzer):
        """Test successful diff retrieval."""
        # asyncio imported at module level
        from unittest.mock import AsyncMock, patch

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"diff --git a/file.py b/file.py\n", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            diff = await analyzer._get_commit_diff("/path/to/repo", "abc123")

        assert "diff --git" in diff

    @pytest.mark.asyncio
    async def test_get_commit_diff_failure(self, analyzer):
        """Test diff retrieval failure."""
        from unittest.mock import AsyncMock, patch

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"fatal: bad object abc123")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Git diff failed"):
                await analyzer._get_commit_diff("/path/to/repo", "abc123")

    @pytest.mark.asyncio
    async def test_get_commit_diff_timeout(self, analyzer):
        """Test diff retrieval timeout."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        # Create analyzer with short timeout
        analyzer = GitHistoryAnalyzer(git_timeout_seconds=1)

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="timed out"):
                await analyzer._get_commit_diff("/path/to/repo", "abc123")


class TestGetCommitLog:
    """Tests for _get_commit_log method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    @pytest.mark.asyncio
    async def test_get_commit_log_success(self, analyzer):
        """Test successful commit log retrieval."""
        from unittest.mock import AsyncMock, patch

        log_output = b"abc123|abc|Author|a@b.com|2026-01-01T00:00:00Z|Fix bug|Body|||\n1\t0\tfile.py"

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(log_output, b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            commits = await analyzer._get_commit_log(
                "/path/to/repo", max_commits=10, since_date=None, branch="main"
            )

        assert len(commits) == 1
        assert commits[0].sha == "abc123"

    @pytest.mark.asyncio
    async def test_get_commit_log_with_since_date(self, analyzer):
        """Test commit log with since_date filter."""
        from unittest.mock import AsyncMock, patch

        log_output = b"abc123|abc|Author|a@b.com|2026-01-01T00:00:00Z|Fix bug|Body|||\n1\t0\tfile.py"

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(log_output, b""))

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_exec:
            await analyzer._get_commit_log(
                "/path/to/repo",
                max_commits=10,
                since_date="2025-01-01",
                branch="main",
            )

        # Verify since_date was passed to git command
        call_args = mock_exec.call_args
        assert any("--since=2025-01-01" in str(arg) for arg in call_args[0])

    @pytest.mark.asyncio
    async def test_get_commit_log_failure(self, analyzer):
        """Test commit log retrieval failure."""
        from unittest.mock import AsyncMock, patch

        mock_proc = AsyncMock()
        mock_proc.returncode = 128
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"fatal: not a git repository")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="Git log failed"):
                await analyzer._get_commit_log(
                    "/not/a/repo", max_commits=10, since_date=None, branch="main"
                )

    @pytest.mark.asyncio
    async def test_get_commit_log_timeout(self, analyzer):
        """Test commit log retrieval timeout."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        analyzer = GitHistoryAnalyzer(git_timeout_seconds=1)

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="timed out"):
                await analyzer._get_commit_log(
                    "/path/to/repo", max_commits=10, since_date=None, branch="main"
                )


class TestAnalyzeRepository:
    """Tests for analyze_repository method."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    @pytest.mark.asyncio
    async def test_analyze_repository_success(self, analyzer):
        """Test successful repository analysis."""
        from unittest.mock import AsyncMock, patch

        commits = [
            CommitInfo(
                sha="abc123",
                short_sha="abc",
                author="A",
                author_email="a@b.com",
                date="2026-01-01T00:00:00Z",
                message="Fix parsing bug",
                subject="Fix parsing bug",
                files_changed=["src/parser.py"],
                insertions=10,
                deletions=5,
            ),
        ]

        candidate = RevertCandidate(
            commit=commits[0],
            diff_content="+def func(): pass",
            affected_functions=[
                "func",
                "func2",
                "func3",
            ],  # More functions for higher complexity
            affected_classes=["MyClass"],
            test_files=[
                "tests/test_parser.py"
            ],  # Need test files for test_coverage_score
            is_safe_to_revert=True,
        )

        with (
            patch.object(
                analyzer,
                "_get_commit_log",
                new_callable=AsyncMock,
                return_value=commits,
            ),
            patch.object(
                analyzer,
                "_process_commit",
                new_callable=AsyncMock,
                return_value=candidate,
            ),
        ):
            result = await analyzer.analyze_repository(
                repository_id="repo-123",
                repository_path="/path/to/repo",
                max_commits=100,
            )

        assert result.status == AnalysisStatus.COMPLETED
        assert result.total_commits_analyzed == 1
        assert result.bug_fix_commits_found == 1
        assert len(result.revert_candidates) == 1

    @pytest.mark.asyncio
    async def test_analyze_repository_excludes_low_score(self, analyzer):
        """Test that low-score candidates are excluded."""
        from unittest.mock import AsyncMock, patch

        commits = [
            CommitInfo(
                sha="abc123",
                short_sha="abc",
                author="A",
                author_email="a@b.com",
                date="2026-01-01T00:00:00Z",
                message="Fix minor bug",
                subject="Fix minor bug",
                files_changed=["src/util.py"],
                insertions=1,
                deletions=1,
            ),
        ]

        # Low scores that won't meet threshold
        candidate = RevertCandidate(
            commit=commits[0],
            diff_content="+x = 1",
            is_safe_to_revert=True,
            complexity_score=0.05,  # Below min_complexity_score
            test_coverage_score=0.1,  # Below min_test_coverage_score
        )

        with (
            patch.object(
                analyzer,
                "_get_commit_log",
                new_callable=AsyncMock,
                return_value=commits,
            ),
            patch.object(
                analyzer,
                "_process_commit",
                new_callable=AsyncMock,
                return_value=candidate,
            ),
        ):
            result = await analyzer.analyze_repository(
                repository_id="repo-123",
                repository_path="/path/to/repo",
            )

        assert result.status == AnalysisStatus.COMPLETED
        assert len(result.revert_candidates) == 0
        assert len(result.excluded_commits) == 1
        assert "threshold" in result.excluded_commits[0]["reason"].lower()

    @pytest.mark.asyncio
    async def test_analyze_repository_excludes_unsafe(self, analyzer):
        """Test that unsafe candidates are excluded."""
        from unittest.mock import AsyncMock, patch

        commits = [
            CommitInfo(
                sha="abc123",
                short_sha="abc",
                author="A",
                author_email="a@b.com",
                date="2026-01-01T00:00:00Z",
                message="Fix configuration loading issue",
                subject="Fix configuration loading issue",
                files_changed=[".env", "src/config.py"],  # .env triggers exclusion
            ),
        ]

        candidate = RevertCandidate(
            commit=commits[0],
            is_safe_to_revert=False,
            exclusion_reason="Contains .env file",
        )

        with (
            patch.object(
                analyzer,
                "_get_commit_log",
                new_callable=AsyncMock,
                return_value=commits,
            ),
            patch.object(
                analyzer,
                "_process_commit",
                new_callable=AsyncMock,
                return_value=candidate,
            ),
        ):
            result = await analyzer.analyze_repository(
                repository_id="repo-123",
                repository_path="/path/to/repo",
            )

        assert result.status == AnalysisStatus.COMPLETED
        assert len(result.revert_candidates) == 0
        assert len(result.excluded_commits) == 1

    @pytest.mark.asyncio
    async def test_analyze_repository_failure(self, analyzer):
        """Test repository analysis failure handling."""
        from unittest.mock import AsyncMock, patch

        with patch.object(
            analyzer,
            "_get_commit_log",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Not a git repository"),
        ):
            result = await analyzer.analyze_repository(
                repository_id="repo-123",
                repository_path="/not/a/repo",
            )

        assert result.status == AnalysisStatus.FAILED
        assert result.error_message is not None
        assert "git repository" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_analyze_repository_updates_metrics(self, analyzer):
        """Test that metrics are updated after analysis."""
        from unittest.mock import AsyncMock, patch

        commits = [
            CommitInfo(
                sha="abc123",
                short_sha="abc",
                author="A",
                author_email="a@b.com",
                date="2026-01-01T00:00:00Z",
                message="Fix bug",
                subject="Fix bug",
                files_changed=["src/main.py"],
                insertions=50,
                deletions=10,
            ),
        ]

        candidate = RevertCandidate(
            commit=commits[0],
            diff_content="+code",
            affected_functions=["func1", "func2"],
            test_files=["tests/test.py"],
            is_safe_to_revert=True,
        )

        initial_metrics = analyzer.get_metrics()

        with (
            patch.object(
                analyzer,
                "_get_commit_log",
                new_callable=AsyncMock,
                return_value=commits,
            ),
            patch.object(
                analyzer,
                "_process_commit",
                new_callable=AsyncMock,
                return_value=candidate,
            ),
        ):
            await analyzer.analyze_repository(
                repository_id="repo-123",
                repository_path="/path/to/repo",
            )

        updated_metrics = analyzer.get_metrics()
        assert (
            updated_metrics["total_commits_analyzed"]
            > initial_metrics["total_commits_analyzed"]
        )


class TestExtractFunctionsJS:
    """Tests for JavaScript function extraction."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    def test_extract_js_named_function(self, analyzer):
        """Test extracting named JavaScript functions."""
        diff = """+function handleClick(event) {
+    console.log(event);
+}
"""
        functions = analyzer._extract_functions_from_diff(diff)
        assert "handleClick" in functions

    def test_extract_js_arrow_function(self, analyzer):
        """Test extracting arrow functions."""
        diff = """+const processData = async (data) => {
+    return data;
+}
"""
        functions = analyzer._extract_functions_from_diff(diff)
        assert "processData" in functions

    def test_extract_js_method(self, analyzer):
        """Test extracting class methods."""
        diff = """+render() {
+    return <div>Hello</div>;
+}
"""
        functions = analyzer._extract_functions_from_diff(diff)
        assert "render" in functions


class TestScoreCandidateNoTestFiles:
    """Tests for _score_candidate with no test files."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    def test_score_candidate_no_test_files(self, analyzer):
        """Test scoring when no test files are present."""
        commit = CommitInfo(
            sha="abc",
            short_sha="a",
            author="A",
            author_email="a@b.com",
            date="2026-01-01T00:00:00Z",
            message="Fix",
            subject="Fix",
            files_changed=["src/util.py"],
            insertions=20,
            deletions=10,
        )

        candidate = RevertCandidate(
            commit=commit,
            affected_functions=["helper"],
            test_files=[],  # No test files
        )

        scored = analyzer._score_candidate(candidate)

        # Should get minimum baseline score
        assert scored.test_coverage_score == 0.2
        assert scored.complexity_score > 0


class TestParseCommitLogEdgeCases:
    """Tests for edge cases in commit log parsing."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return GitHistoryAnalyzer()

    def test_parse_commit_log_with_binary_files(self, analyzer):
        """Test parsing commits with binary file stats."""
        log_output = """abc123|abc|Author|a@b.com|2026-01-01T00:00:00Z|Add image|Body|||
-\t-\timage.png
10\t5\tREADME.md"""

        commits = analyzer._parse_commit_log(log_output)
        assert len(commits) == 1
        # Binary files use "-" which should be converted to 0
        assert commits[0].insertions == 10  # Only from README.md
        assert commits[0].deletions == 5

    def test_parse_commit_log_malformed_numstat(self, analyzer):
        """Test parsing with malformed numstat lines."""
        log_output = """abc123|abc|Author|a@b.com|2026-01-01T00:00:00Z|Fix|Body|||
invalid_line_without_tabs"""

        commits = analyzer._parse_commit_log(log_output)
        assert len(commits) == 1
        # Malformed lines should be skipped
        assert commits[0].insertions == 0

    def test_parse_commit_log_invalid_numbers(self, analyzer):
        """Test parsing with invalid insertion/deletion counts."""
        log_output = """abc123|abc|Author|a@b.com|2026-01-01T00:00:00Z|Fix|Body|||
abc\txyz\tfile.py"""

        commits = analyzer._parse_commit_log(log_output)
        assert len(commits) == 1
        # Invalid numbers should be skipped (ValueError branch)
        assert commits[0].insertions == 0
        assert commits[0].deletions == 0
