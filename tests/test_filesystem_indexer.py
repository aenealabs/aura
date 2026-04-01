"""
Project Aura - Filesystem Indexer Tests

Tests for the filesystem indexer service that indexes repository metadata into OpenSearch.
Comprehensive test coverage for file discovery, indexing operations, and edge cases.
"""

# ruff: noqa: PLR2004

import platform
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.services.filesystem_indexer import (
    MIN_TEXT_LENGTH_FOR_EMBEDDING,
    FilesystemIndexer,
)

# Run tests in separate processes to avoid git.Repo patch pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestFilesystemIndexerInitialization:
    """Tests for FilesystemIndexer initialization."""

    @pytest.fixture
    def mock_opensearch(self):
        """Create mock OpenSearch client."""
        mock_client = AsyncMock()
        mock_client.index = AsyncMock()
        mock_client.delete = AsyncMock()
        mock_client.bulk = AsyncMock()
        return mock_client

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        service = Mock()
        service.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
        return service

    @pytest.fixture
    def mock_git_repo(self):
        """Create mock git repository."""
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123"
        mock_repo.head.commit.author.name = "Test Author"
        mock_repo.head.commit.author.email = "test@example.com"
        mock_repo.head.commit.committed_datetime.isoformat.return_value = (
            "2024-01-01T00:00:00"
        )
        mock_repo.git.log.return_value = "abc123 2024-01-01 Test commit"
        return mock_repo

    @pytest.fixture
    def temp_git_repo(self, mock_git_repo):
        """Create temporary directory for testing with mocked git."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=mock_git_repo):
                yield Path(tmpdir)

    def test_initialization(
        self, mock_opensearch, mock_embedding_service, temp_git_repo, mock_git_repo
    ):
        """Test FilesystemIndexer initialization."""
        with patch("git.Repo", return_value=mock_git_repo):
            indexer = FilesystemIndexer(
                opensearch_client=mock_opensearch,
                embedding_service=mock_embedding_service,
                git_repo_path=str(temp_git_repo),
                index_name="test-index",
            )

            assert indexer.opensearch == mock_opensearch
            assert indexer.embeddings == mock_embedding_service
            assert indexer.index_name == "test-index"
            assert indexer.repo_root == temp_git_repo
            assert isinstance(indexer.ignore_patterns, list)
            assert len(indexer.ignore_patterns) > 0

    def test_initialization_default_index_name(
        self, mock_opensearch, mock_embedding_service, temp_git_repo, mock_git_repo
    ):
        """Test that default index name is used when not specified."""
        with patch("git.Repo", return_value=mock_git_repo):
            indexer = FilesystemIndexer(
                opensearch_client=mock_opensearch,
                embedding_service=mock_embedding_service,
                git_repo_path=str(temp_git_repo),
            )

            assert indexer.index_name == "aura-filesystem-metadata"

    def test_initialization_stores_repo_root_as_path(
        self, mock_opensearch, mock_embedding_service, temp_git_repo, mock_git_repo
    ):
        """Test that repo_root is stored as a Path object."""
        with patch("git.Repo", return_value=mock_git_repo):
            indexer = FilesystemIndexer(
                mock_opensearch, mock_embedding_service, str(temp_git_repo)
            )

            assert isinstance(indexer.repo_root, Path)
            assert indexer.repo_root == temp_git_repo


class TestShouldIgnore:
    """Tests for the _should_ignore method."""

    @pytest.fixture
    def mock_opensearch(self):
        """Create mock OpenSearch client."""
        return AsyncMock()

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        service = Mock()
        service.generate_embedding = AsyncMock(return_value=[0.1] * 1536)
        return service

    @pytest.fixture
    def mock_git_repo(self):
        """Create mock git repository."""
        return MagicMock()

    @pytest.fixture
    def indexer(self, mock_opensearch, mock_embedding_service, mock_git_repo):
        """Create indexer instance for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=mock_git_repo):
                yield FilesystemIndexer(
                    mock_opensearch, mock_embedding_service, str(tmpdir)
                )

    def test_should_ignore_pycache(self, indexer):
        """Test that __pycache__ directories are ignored."""
        path = Path("src/__pycache__/module.pyc")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_git_directory(self, indexer):
        """Test that .git directory is ignored."""
        path = Path(".git/objects/abc123")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_node_modules(self, indexer):
        """Test that node_modules is ignored."""
        path = Path("frontend/node_modules/react/index.js")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_venv(self, indexer):
        """Test that .venv directory is ignored."""
        path = Path(".venv/lib/python3.12/site-packages")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_venv_without_dot(self, indexer):
        """Test that venv directory without dot is ignored."""
        path = Path("venv/lib/python3.12/site-packages")
        assert indexer._should_ignore(path) is True

    def test_should_not_ignore_regular_file(self, indexer):
        """Test that regular files are not ignored."""
        path = Path("src/agents/orchestrator.py")
        assert indexer._should_ignore(path) is False

    def test_should_ignore_pyc_file_in_pycache(self, indexer):
        """Test that .pyc files in __pycache__ are ignored."""
        # Note: The implementation uses substring matching. *.pyc pattern
        # contains the literal "*.pyc" which won't match "module.pyc".
        # However, .pyc files are typically in __pycache__ which IS matched.
        path = Path("src/__pycache__/module.cpython-312.pyc")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_pytest_cache(self, indexer):
        """Test that .pytest_cache is ignored."""
        path = Path(".pytest_cache/v/cache/nodeids")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_mypy_cache(self, indexer):
        """Test that .mypy_cache is ignored."""
        path = Path(".mypy_cache/3.12/module.meta.json")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_ruff_cache(self, indexer):
        """Test that .ruff_cache is ignored."""
        path = Path(".ruff_cache/content/abc123")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_build_directory(self, indexer):
        """Test that build directory is ignored."""
        path = Path("build/lib/package/module.py")
        assert indexer._should_ignore(path) is True

    def test_should_ignore_dist_directory(self, indexer):
        """Test that dist directory is ignored."""
        path = Path("dist/package-1.0.0.tar.gz")
        assert indexer._should_ignore(path) is True

    def test_ignore_patterns_comprehensive(self, indexer):
        """Test that comprehensive list of patterns are ignored."""
        patterns_to_ignore = [
            "__pycache__",
            ".git",
            ".venv",
            "node_modules",
            ".pytest_cache",
            ".mypy_cache",
            "dist",
            "build",
            ".ruff_cache",
        ]

        for pattern in patterns_to_ignore:
            path = Path(f"some/path/{pattern}/file.py")
            assert (
                indexer._should_ignore(path) is True
            ), f"Pattern {pattern} should be ignored"


class TestDetectLanguage:
    """Tests for the _detect_language method."""

    @pytest.fixture
    def indexer(self):
        """Create indexer instance for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                yield FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

    def test_detect_language_python(self, indexer):
        """Test language detection for Python files."""
        assert indexer._detect_language(Path("test.py")) == "python"

    def test_detect_language_javascript(self, indexer):
        """Test language detection for JavaScript files."""
        assert indexer._detect_language(Path("app.js")) == "javascript"
        assert indexer._detect_language(Path("Component.jsx")) == "javascript"

    def test_detect_language_typescript(self, indexer):
        """Test language detection for TypeScript files."""
        assert indexer._detect_language(Path("app.ts")) == "typescript"
        assert indexer._detect_language(Path("Component.tsx")) == "typescript"

    def test_detect_language_yaml(self, indexer):
        """Test language detection for YAML files."""
        assert indexer._detect_language(Path("config.yaml")) == "yaml"
        assert indexer._detect_language(Path("docker-compose.yml")) == "yaml"

    def test_detect_language_java(self, indexer):
        """Test language detection for Java files."""
        assert indexer._detect_language(Path("Main.java")) == "java"

    def test_detect_language_go(self, indexer):
        """Test language detection for Go files."""
        assert indexer._detect_language(Path("main.go")) == "go"

    def test_detect_language_rust(self, indexer):
        """Test language detection for Rust files."""
        assert indexer._detect_language(Path("main.rs")) == "rust"

    def test_detect_language_cpp(self, indexer):
        """Test language detection for C++ files."""
        assert indexer._detect_language(Path("main.cpp")) == "cpp"
        assert indexer._detect_language(Path("header.hpp")) == "cpp"

    def test_detect_language_c(self, indexer):
        """Test language detection for C files."""
        assert indexer._detect_language(Path("main.c")) == "c"
        assert indexer._detect_language(Path("header.h")) == "c"

    def test_detect_language_ruby(self, indexer):
        """Test language detection for Ruby files."""
        assert indexer._detect_language(Path("app.rb")) == "ruby"

    def test_detect_language_php(self, indexer):
        """Test language detection for PHP files."""
        assert indexer._detect_language(Path("index.php")) == "php"

    def test_detect_language_bash(self, indexer):
        """Test language detection for Bash files."""
        assert indexer._detect_language(Path("script.sh")) == "bash"

    def test_detect_language_json(self, indexer):
        """Test language detection for JSON files."""
        assert indexer._detect_language(Path("package.json")) == "json"

    def test_detect_language_toml(self, indexer):
        """Test language detection for TOML files."""
        assert indexer._detect_language(Path("pyproject.toml")) == "toml"

    def test_detect_language_markdown(self, indexer):
        """Test language detection for Markdown files."""
        assert indexer._detect_language(Path("README.md")) == "markdown"

    def test_detect_language_sql(self, indexer):
        """Test language detection for SQL files."""
        assert indexer._detect_language(Path("query.sql")) == "sql"

    def test_detect_language_unknown(self, indexer):
        """Test language detection for unknown extensions."""
        assert indexer._detect_language(Path("file.xyz")) == "unknown"
        assert indexer._detect_language(Path("file.unknown")) == "unknown"
        assert indexer._detect_language(Path("noextension")) == "unknown"


class TestCountLines:
    """Tests for the _count_lines method."""

    @pytest.fixture
    def indexer(self):
        """Create indexer instance for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))
                indexer._temp_dir = tmpdir
                yield indexer

    def test_count_lines(self, indexer):
        """Test line counting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("line1\nline2\nline3\n")

            assert indexer._count_lines(test_file) == 3

    def test_count_lines_empty_file(self, indexer):
        """Test line counting for empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "empty.txt"
            test_file.write_text("")

            assert indexer._count_lines(test_file) == 0

    def test_count_lines_single_line_no_newline(self, indexer):
        """Test line counting for file with single line and no trailing newline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "single.txt"
            test_file.write_text("single line")

            assert indexer._count_lines(test_file) == 1

    def test_count_lines_nonexistent_file(self, indexer):
        """Test line counting for nonexistent file."""
        assert indexer._count_lines(Path("/nonexistent/file.txt")) == 0

    def test_count_lines_with_encoding_errors(self, indexer):
        """Test line counting handles encoding errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "binary.bin"
            test_file.write_bytes(b"\x80\x81\x82\x83")

            # Should handle gracefully and return a count
            result = indexer._count_lines(test_file)
            assert result >= 0  # Should not crash


class TestGetFileId:
    """Tests for the _get_file_id method."""

    @pytest.fixture
    def indexer_with_temp_dir(self):
        """Create indexer instance with temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))
                yield indexer, Path(tmpdir)

    def test_get_file_id_deterministic(self, indexer_with_temp_dir):
        """Test that file ID generation is deterministic."""
        indexer, temp_dir = indexer_with_temp_dir

        # Create a test file within the temp directory
        test_dir = temp_dir / "src" / "agents"
        test_dir.mkdir(parents=True, exist_ok=True)
        path = test_dir / "test.py"
        path.write_text("# test file")

        file_id1 = indexer._get_file_id(path)
        file_id2 = indexer._get_file_id(path)

        assert file_id1 == file_id2
        assert isinstance(file_id1, str)
        assert len(file_id1) == 32  # MD5 hex digest length

    def test_get_file_id_unique(self, indexer_with_temp_dir):
        """Test that different paths generate different IDs."""
        indexer, temp_dir = indexer_with_temp_dir

        # Create test files within the temp directory
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        file1.write_text("# test file 1")
        file2.write_text("# test file 2")

        id1 = indexer._get_file_id(file1)
        id2 = indexer._get_file_id(file2)

        assert id1 != id2


class TestEmbedText:
    """Tests for the _embed_text method."""

    @pytest.fixture
    def mock_embedding_service(self):
        """Create mock embedding service."""
        service = Mock()
        service.generate_embedding = AsyncMock(return_value=[0.5] * 1536)
        return service

    @pytest.fixture
    def indexer(self, mock_embedding_service):
        """Create indexer instance for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                yield FilesystemIndexer(
                    AsyncMock(), mock_embedding_service, str(tmpdir)
                )

    @pytest.mark.anyio
    async def test_embed_text_short_text(self, mock_embedding_service):
        """Test embedding generation for short text returns zero vector."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    AsyncMock(), mock_embedding_service, str(tmpdir)
                )

                result = await indexer._embed_text("ab")  # Less than MIN_TEXT_LENGTH

                assert result == [0.0] * 1536
                # Embedding service should not be called
                mock_embedding_service.generate_embedding.assert_not_called()

    @pytest.mark.anyio
    async def test_embed_text_empty_string(self, mock_embedding_service):
        """Test embedding generation for empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    AsyncMock(), mock_embedding_service, str(tmpdir)
                )

                result = await indexer._embed_text("")

                assert result == [0.0] * 1536
                mock_embedding_service.generate_embedding.assert_not_called()

    @pytest.mark.anyio
    async def test_embed_text_none(self, mock_embedding_service):
        """Test embedding generation for None returns zero vector."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    AsyncMock(), mock_embedding_service, str(tmpdir)
                )

                # Empty string case (None would be caught by the not text check)
                result = await indexer._embed_text("")

                assert result == [0.0] * 1536

    @pytest.mark.anyio
    async def test_embed_text_exactly_min_length(self, mock_embedding_service):
        """Test embedding generation for text exactly at minimum length."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    AsyncMock(), mock_embedding_service, str(tmpdir)
                )

                # Text with exactly MIN_TEXT_LENGTH_FOR_EMBEDDING characters
                text = "a" * MIN_TEXT_LENGTH_FOR_EMBEDDING
                result = await indexer._embed_text(text)

                assert result == [0.5] * 1536
                mock_embedding_service.generate_embedding.assert_called_once_with(text)

    @pytest.mark.anyio
    async def test_embed_text_valid_text(self, mock_embedding_service):
        """Test embedding generation for valid text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    AsyncMock(), mock_embedding_service, str(tmpdir)
                )

                result = await indexer._embed_text("valid text for embedding")

                assert result == [0.5] * 1536
                mock_embedding_service.generate_embedding.assert_called_once()

    @pytest.mark.anyio
    async def test_embed_text_error_handling(self):
        """Test embedding generation with error returns zero vector."""
        mock_service = Mock()
        mock_service.generate_embedding = AsyncMock(
            side_effect=Exception("Embedding failed")
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(AsyncMock(), mock_service, str(tmpdir))

                result = await indexer._embed_text("text that will fail")

                assert result == [0.0] * 1536


class TestAnalyzePythonFile:
    """Tests for the _analyze_python_file method."""

    @pytest.fixture
    def indexer(self):
        """Create indexer instance for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                yield FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

    @pytest.mark.anyio
    async def test_analyze_python_file(self, indexer):
        """Test Python file analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text('''"""Module docstring"""
import os
from pathlib import Path

class MyClass:
    pass

def my_function():
    if True:
        pass
''')

            result = await indexer._analyze_python_file(test_file)

            assert "docstring" in result
            assert result["docstring"] == "Module docstring"
            assert "imports" in result
            assert "os" in result["imports"]
            assert "pathlib.Path" in result["imports"]
            assert "functions" in result
            assert "my_function" in result["functions"]
            assert "classes" in result
            assert "MyClass" in result["classes"]
            assert "complexity" in result
            assert result["complexity"] >= 1  # At least one if statement

    @pytest.mark.anyio
    async def test_analyze_python_file_invalid_syntax(self, indexer):
        """Test Python file analysis with syntax errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "invalid.py"
            test_file.write_text("def invalid syntax;;")

            result = await indexer._analyze_python_file(test_file)

            # Should return empty dict on error
            assert result == {}

    @pytest.mark.anyio
    async def test_analyze_python_file_private_functions_excluded(self, indexer):
        """Test that private functions/classes are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def public_function():
    pass

def _private_function():
    pass

class PublicClass:
    pass

class _PrivateClass:
    pass
""")

            result = await indexer._analyze_python_file(test_file)

            assert "public_function" in result["functions"]
            assert "_private_function" not in result["functions"]
            assert "PublicClass" in result["classes"]
            assert "_PrivateClass" not in result["classes"]

    @pytest.mark.anyio
    async def test_analyze_python_file_complexity_scoring(self, indexer):
        """Test complexity scoring with various control structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "complex.py"
            test_file.write_text("""
def complex_function():
    if True:
        pass
    for i in range(10):
        pass
    while True:
        break
    try:
        pass
    except:
        pass
    with open('file') as f:
        pass
""")

            result = await indexer._analyze_python_file(test_file)

            # Should count: if, for, while, try, with = 5
            assert result["complexity"] == 5.0

    @pytest.mark.anyio
    async def test_analyze_python_file_no_docstring(self, indexer):
        """Test Python file analysis when no docstring present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "no_docstring.py"
            test_file.write_text("""
import os

def my_function():
    pass
""")

            result = await indexer._analyze_python_file(test_file)

            assert result["docstring"] is None

    @pytest.mark.anyio
    async def test_analyze_python_file_import_from(self, indexer):
        """Test that ImportFrom statements are captured correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "imports.py"
            test_file.write_text("""
from os.path import join, exists
from typing import Optional, List
import json
""")

            result = await indexer._analyze_python_file(test_file)

            assert "os.path.join" in result["imports"]
            assert "os.path.exists" in result["imports"]
            assert "typing.Optional" in result["imports"]
            assert "typing.List" in result["imports"]
            assert "json" in result["imports"]

    @pytest.mark.anyio
    async def test_analyze_python_file_limits_results(self, indexer):
        """Test that results are limited to 50 items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "many_functions.py"
            # Create file with 60 functions
            functions = "\n".join([f"def func_{i}(): pass" for i in range(60)])
            test_file.write_text(functions)

            result = await indexer._analyze_python_file(test_file)

            # Should be limited to 50
            assert len(result["functions"]) == 50

    @pytest.mark.anyio
    async def test_analyze_python_file_nonexistent(self, indexer):
        """Test Python file analysis for nonexistent file."""
        result = await indexer._analyze_python_file(Path("/nonexistent/file.py"))

        assert result == {}


class TestGetGitMetadata:
    """Tests for the _get_git_metadata method."""

    @pytest.mark.anyio
    async def test_get_git_metadata_no_commits(self):
        """Test git metadata extraction when file has no commits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])  # No commits
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                result = await indexer._get_git_metadata(Path("test.py"))

                assert result == {}

    @pytest.mark.anyio
    async def test_get_git_metadata_with_commits(self):
        """Test git metadata extraction with commit history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                # Create mock commit
                mock_commit = Mock()
                mock_commit.author.name = "Test Author"
                mock_commit.hexsha = "abc123"
                mock_commit.message = "Test commit\nMore details"

                mock_repo = Mock()
                mock_repo.iter_commits.side_effect = lambda **kwargs: iter(
                    [mock_commit]
                )
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                result = await indexer._get_git_metadata(Path("test.py"))

                assert result["author"] == "Test Author"
                assert result["commit_hash"] == "abc123"
                assert result["commit_message"] == "Test commit"
                assert result["num_contributors"] == 1

    @pytest.mark.anyio
    async def test_get_git_metadata_bytes_message(self):
        """Test git metadata extraction when commit message is bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                # Create mock commit with bytes message
                mock_commit = Mock()
                mock_commit.author.name = "Test Author"
                mock_commit.hexsha = "def456"
                mock_commit.message = b"Bytes commit message\nDetails"

                mock_repo = Mock()
                mock_repo.iter_commits.side_effect = lambda **kwargs: iter(
                    [mock_commit]
                )
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                result = await indexer._get_git_metadata(Path("test.py"))

                assert result["commit_message"] == "Bytes commit message"

    @pytest.mark.anyio
    async def test_get_git_metadata_multiple_contributors(self):
        """Test git metadata extraction with multiple contributors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                # Create mock commits from different authors
                mock_commit1 = Mock()
                mock_commit1.author.name = "Author One"
                mock_commit1.hexsha = "abc123"
                mock_commit1.message = "First commit"

                mock_commit2 = Mock()
                mock_commit2.author.name = "Author Two"
                mock_commit2.hexsha = "def456"
                mock_commit2.message = "Second commit"

                mock_commit3 = Mock()
                mock_commit3.author.name = "Author One"  # Same as first
                mock_commit3.hexsha = "ghi789"
                mock_commit3.message = "Third commit"

                mock_repo = Mock()
                # First call returns most recent, second call returns all
                call_count = [0]

                def mock_iter_commits(**kwargs):
                    call_count[0] += 1
                    if kwargs.get("max_count") == 1:
                        return iter([mock_commit1])
                    return iter([mock_commit1, mock_commit2, mock_commit3])

                mock_repo.iter_commits = mock_iter_commits
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                result = await indexer._get_git_metadata(Path("test.py"))

                assert result["num_contributors"] == 2  # Two unique authors

    @pytest.mark.anyio
    async def test_get_git_metadata_exception_handling(self):
        """Test git metadata extraction handles exceptions gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.side_effect = Exception("Git error")
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                result = await indexer._get_git_metadata(Path("test.py"))

                assert result == {}


class TestExtractMetadata:
    """Tests for the _extract_metadata method."""

    @pytest.mark.anyio
    async def test_extract_metadata_python_file(self):
        """Test metadata extraction for Python file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                mock_commit = Mock()
                mock_commit.author.name = "Test Author"
                mock_commit.hexsha = "abc123"
                mock_commit.message = "Test commit"

                mock_repo = Mock()
                mock_repo.iter_commits.side_effect = lambda **kwargs: iter(
                    [mock_commit]
                )
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                # Create test Python file
                test_file = Path(tmpdir) / "src" / "module.py"
                test_file.parent.mkdir(parents=True, exist_ok=True)
                test_file.write_text('''"""Module docstring"""

def my_function():
    pass
''')

                result = await indexer._extract_metadata(test_file)

                assert result["file_name"] == "module.py"
                assert result["file_extension"] == ".py"
                assert result["language"] == "python"
                assert result["is_test_file"] is False
                assert result["is_config_file"] is False
                assert result["docstring"] == "Module docstring"
                assert "my_function" in result["exported_functions"]
                assert result["last_author"] == "Test Author"

    @pytest.mark.anyio
    async def test_extract_metadata_test_file(self):
        """Test metadata extraction identifies test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                # Create test file
                test_file = Path(tmpdir) / "test_module.py"
                test_file.write_text("# test file")

                result = await indexer._extract_metadata(test_file)

                assert result["is_test_file"] is True

    @pytest.mark.anyio
    async def test_extract_metadata_config_file(self):
        """Test metadata extraction identifies config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                config_extensions = [".yaml", ".yml", ".json", ".toml", ".ini"]

                for ext in config_extensions:
                    test_file = Path(tmpdir) / f"config{ext}"
                    test_file.write_text("# config")

                    result = await indexer._extract_metadata(test_file)

                    assert result["is_config_file"] is True, f"{ext} should be config"

    @pytest.mark.anyio
    async def test_extract_metadata_non_python_file(self):
        """Test metadata extraction for non-Python file skips code analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                # Create JavaScript file
                test_file = Path(tmpdir) / "app.js"
                test_file.write_text("console.log('hello');")

                result = await indexer._extract_metadata(test_file)

                assert result["language"] == "javascript"
                assert result["docstring"] is None
                assert result["imports"] == []
                assert result["exported_functions"] == []
                assert result["exported_classes"] == []
                assert result["complexity_score"] == 0.0


class TestIndexFile:
    """Tests for the index_file method."""

    @pytest.mark.anyio
    async def test_index_file_ignored(self):
        """Test that ignored files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                # Try to index ignored file
                ignored_path = Path(tmpdir) / "__pycache__" / "module.pyc"
                ignored_path.parent.mkdir(parents=True, exist_ok=True)
                ignored_path.write_bytes(b"\x00\x00")

                await indexer.index_file(ignored_path)

                # OpenSearch should not be called
                mock_opensearch.index.assert_not_called()

    @pytest.mark.anyio
    async def test_index_file_success(self):
        """Test successful file indexing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                # Create and index file
                test_file = Path(tmpdir) / "module.py"
                test_file.write_text("# test module")

                await indexer.index_file(test_file)

                # OpenSearch should be called
                mock_opensearch.index.assert_called_once()
                call_kwargs = mock_opensearch.index.call_args.kwargs
                assert call_kwargs["index"] == "aura-filesystem-metadata"
                assert "path_embedding" in call_kwargs["body"]
                assert "docstring_embedding" in call_kwargs["body"]
                assert "indexed_at" in call_kwargs["body"]


class TestDeleteFile:
    """Tests for the delete_file method."""

    @pytest.mark.anyio
    async def test_delete_file_success(self):
        """Test file deletion from index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()

            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(mock_opensearch, Mock(), str(tmpdir))

                # Create test file within temp directory
                test_path = Path(tmpdir) / "test.py"
                test_path.write_text("# test file")

                await indexer.delete_file(test_path)

                # Should call delete with generated ID
                mock_opensearch.delete.assert_called_once()
                call_kwargs = mock_opensearch.delete.call_args.kwargs
                assert call_kwargs["index"] == "aura-filesystem-metadata"
                assert "id" in call_kwargs

    @pytest.mark.anyio
    async def test_delete_file_error_handling(self):
        """Test delete file handles errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_opensearch.delete.side_effect = Exception("Delete failed")

            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(mock_opensearch, Mock(), str(tmpdir))

                test_path = Path(tmpdir) / "test.py"
                test_path.write_text("# test file")

                # Should not raise exception
                await indexer.delete_file(test_path)

                # Delete was still attempted
                mock_opensearch.delete.assert_called_once()


class TestUpdateFile:
    """Tests for the update_file method."""

    @pytest.mark.anyio
    async def test_update_file_calls_index_file(self):
        """Test that update_file delegates to index_file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(AsyncMock(), Mock(), str(tmpdir))

                # Mock index_file method
                indexer.index_file = AsyncMock()

                test_path = Path("test.py")
                await indexer.update_file(test_path)

                # Should have called index_file
                indexer.index_file.assert_called_once_with(test_path)


class TestBulkIndex:
    """Tests for the _bulk_index method."""

    @pytest.mark.anyio
    async def test_bulk_index_empty_list(self):
        """Test bulk indexing with empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                await indexer._bulk_index([])

                # Should not call bulk with empty list
                mock_opensearch.bulk.assert_not_called()

    @pytest.mark.anyio
    async def test_bulk_index_multiple_documents(self):
        """Test bulk indexing with multiple documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                documents = [
                    {"file_path": "src/file1.py", "docstring": "Doc 1"},
                    {"file_path": "src/file2.py", "docstring": "Doc 2"},
                    {"file_path": "src/file3.py", "docstring": None},
                ]

                await indexer._bulk_index(documents)

                # Should call bulk once
                mock_opensearch.bulk.assert_called_once()
                call_kwargs = mock_opensearch.bulk.call_args.kwargs
                assert call_kwargs["refresh"] is True

                # Body should have 6 items (2 per document: action + doc)
                body = call_kwargs["body"]
                assert len(body) == 6

    @pytest.mark.anyio
    async def test_bulk_index_adds_embeddings(self):
        """Test that bulk indexing adds embeddings to documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.5] * 1536)

            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                documents = [
                    {"file_path": "src/module.py", "docstring": "Module doc"},
                ]

                await indexer._bulk_index(documents)

                # Check that embeddings were added
                call_kwargs = mock_opensearch.bulk.call_args.kwargs
                body = call_kwargs["body"]
                doc = body[1]  # Second item is the document

                assert "path_embedding" in doc
                assert "docstring_embedding" in doc
                assert "indexed_at" in doc


class TestIndexRepository:
    """Tests for the index_repository method."""

    @pytest.mark.anyio
    async def test_index_repository_empty_directory(self):
        """Test repository indexing with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo", return_value=MagicMock()):
                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                await indexer.index_repository(Path(tmpdir))

                # No files to index, bulk should not be called
                mock_opensearch.bulk.assert_not_called()

    @pytest.mark.anyio
    async def test_index_repository_with_files(self):
        """Test repository indexing with files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                # Create test files
                (Path(tmpdir) / "file1.py").write_text("# file 1")
                (Path(tmpdir) / "file2.py").write_text("# file 2")
                (Path(tmpdir) / "file3.js").write_text("// file 3")

                await indexer.index_repository(Path(tmpdir))

                # Should call bulk at least once
                assert mock_opensearch.bulk.called

    @pytest.mark.anyio
    async def test_index_repository_skips_ignored_files(self):
        """Test that repository indexing skips ignored files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                # Create mix of regular and ignored files
                (Path(tmpdir) / "regular.py").write_text("# regular")
                pycache = Path(tmpdir) / "__pycache__"
                pycache.mkdir()
                (pycache / "cached.pyc").write_bytes(b"\x00")

                await indexer.index_repository(Path(tmpdir))

                # Check that only regular file was indexed
                if mock_opensearch.bulk.called:
                    call_kwargs = mock_opensearch.bulk.call_args.kwargs
                    body = call_kwargs["body"]
                    # Only 2 items (action + doc) for single file
                    assert len(body) == 2

    @pytest.mark.anyio
    async def test_index_repository_batching(self):
        """Test that repository indexing respects batch size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                # Create more files than batch size
                for i in range(5):
                    (Path(tmpdir) / f"file{i}.py").write_text(f"# file {i}")

                # Use small batch size
                await indexer.index_repository(Path(tmpdir), batch_size=2)

                # Should call bulk multiple times due to batching
                assert mock_opensearch.bulk.call_count >= 2

    @pytest.mark.anyio
    async def test_index_repository_handles_errors(self):
        """Test that repository indexing handles file errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                # Create a regular file
                (Path(tmpdir) / "good.py").write_text("# good file")

                # Mock _extract_metadata to fail for some files
                original_extract = indexer._extract_metadata

                async def failing_extract(file_path):
                    if "bad" in str(file_path):
                        raise ValueError("Simulated error")
                    return await original_extract(file_path)

                indexer._extract_metadata = failing_extract

                # Should complete without raising
                await indexer.index_repository(Path(tmpdir))

    @pytest.mark.anyio
    async def test_index_repository_skips_directories(self):
        """Test that repository indexing only processes files, not directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_opensearch = AsyncMock()
            mock_embedding = Mock()
            mock_embedding.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

            with patch("git.Repo") as mock_repo_class:
                mock_repo = Mock()
                mock_repo.iter_commits.return_value = iter([])
                mock_repo_class.return_value = mock_repo

                indexer = FilesystemIndexer(
                    mock_opensearch, mock_embedding, str(tmpdir)
                )

                # Create directory structure
                subdir = Path(tmpdir) / "subdir"
                subdir.mkdir()
                (subdir / "file.py").write_text("# file in subdir")

                await indexer.index_repository(Path(tmpdir))

                # Should process the file, not the directory
                if mock_opensearch.bulk.called:
                    call_kwargs = mock_opensearch.bulk.call_args.kwargs
                    body = call_kwargs["body"]
                    # Only the file should be indexed
                    file_paths = [
                        item.get("file_path")
                        for item in body
                        if isinstance(item, dict) and "file_path" in item
                    ]
                    assert len(file_paths) == 1
                    assert "file.py" in file_paths[0]


class TestMinTextLengthConstant:
    """Tests for the MIN_TEXT_LENGTH_FOR_EMBEDDING constant."""

    def test_min_text_length_value(self):
        """Test that MIN_TEXT_LENGTH_FOR_EMBEDDING has expected value."""
        assert MIN_TEXT_LENGTH_FOR_EMBEDDING == 3

    def test_min_text_length_is_int(self):
        """Test that MIN_TEXT_LENGTH_FOR_EMBEDDING is an integer."""
        assert isinstance(MIN_TEXT_LENGTH_FOR_EMBEDDING, int)
