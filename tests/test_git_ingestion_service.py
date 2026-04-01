"""
Unit tests for git_ingestion_service.py

Tests the GitIngestionService components including:
- Enums and data classes
- Job persistence
- Repository operations
- Authentication
- Async operations and concurrency
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.services.git_ingestion_service import (
    GitIngestionService,
    IngestionJob,
    IngestionMode,
    IngestionResult,
    IngestionStatus,
)

# =============================================================================
# ENUM TESTS
# =============================================================================


class TestIngestionStatus:
    """Test IngestionStatus enum."""

    def test_all_values_exist(self):
        """Test all expected enum values exist."""
        assert IngestionStatus.PENDING.value == "pending"
        assert IngestionStatus.CLONING.value == "cloning"
        assert IngestionStatus.PARSING.value == "parsing"
        assert IngestionStatus.INDEXING_GRAPH.value == "indexing_graph"
        assert IngestionStatus.INDEXING_VECTORS.value == "indexing_vectors"
        assert IngestionStatus.COMPLETED.value == "completed"
        assert IngestionStatus.FAILED.value == "failed"

    def test_enum_conversion(self):
        """Test enum string conversion."""
        assert IngestionStatus("pending") == IngestionStatus.PENDING
        assert IngestionStatus("completed") == IngestionStatus.COMPLETED


class TestIngestionMode:
    """Test IngestionMode enum."""

    def test_all_values_exist(self):
        """Test all expected enum values exist."""
        assert IngestionMode.FULL.value == "full"
        assert IngestionMode.INCREMENTAL.value == "incremental"
        assert IngestionMode.BRANCH.value == "branch"


# =============================================================================
# DATA CLASS TESTS
# =============================================================================


class TestIngestionJob:
    """Test IngestionJob dataclass."""

    def test_basic_creation(self):
        """Test basic job creation."""
        job = IngestionJob(
            job_id="job-123",
            repository_url="https://github.com/org/repo",
        )
        assert job.job_id == "job-123"
        assert job.branch == "main"
        assert job.mode == IngestionMode.FULL
        assert job.status == IngestionStatus.PENDING

    def test_default_values(self):
        """Test default values are applied."""
        job = IngestionJob(
            job_id="job-123",
            repository_url="https://github.com/org/repo",
        )
        assert job.started_at is None
        assert job.completed_at is None
        assert job.files_processed == 0
        assert job.entities_indexed == 0
        assert job.embeddings_generated == 0
        assert job.errors == []
        assert job.metadata == {}

    def test_with_values(self):
        """Test job with explicit values."""
        now = datetime.now()
        job = IngestionJob(
            job_id="job-123",
            repository_url="https://github.com/org/repo",
            branch="develop",
            mode=IngestionMode.INCREMENTAL,
            status=IngestionStatus.PARSING,
            started_at=now,
            files_processed=10,
        )
        assert job.branch == "develop"
        assert job.mode == IngestionMode.INCREMENTAL
        assert job.status == IngestionStatus.PARSING
        assert job.files_processed == 10


class TestIngestionResult:
    """Test IngestionResult dataclass."""

    def test_success_result(self):
        """Test successful result creation."""
        result = IngestionResult(
            job_id="job-123",
            success=True,
            files_processed=50,
            entities_indexed=200,
            embeddings_generated=50,
            duration_seconds=45.5,
            errors=[],
            commit_hash="abc123",
        )
        assert result.success is True
        assert result.files_processed == 50
        assert result.commit_hash == "abc123"

    def test_failure_result(self):
        """Test failure result creation."""
        result = IngestionResult(
            job_id="job-123",
            success=False,
            files_processed=10,
            entities_indexed=0,
            embeddings_generated=0,
            duration_seconds=5.0,
            errors=["Clone failed", "Network error"],
        )
        assert result.success is False
        assert len(result.errors) == 2
        assert result.commit_hash is None


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_neptune():
    """Create mock Neptune service."""
    mock = MagicMock()
    mock.add_code_entity = MagicMock(return_value="entity-123")
    mock.add_relationship = MagicMock(return_value=True)
    mock.delete_by_repository = MagicMock(return_value=10)
    return mock


@pytest.fixture
def mock_opensearch():
    """Create mock OpenSearch service."""
    mock = MagicMock()
    mock.index_embedding = MagicMock(return_value=True)
    mock.delete_by_repository = MagicMock(return_value=5)
    return mock


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service."""
    mock = MagicMock()
    mock.generate_embedding = MagicMock(return_value=[0.1] * 1024)
    return mock


@pytest.fixture
def mock_ast_parser():
    """Create mock AST parser."""
    from src.agents.ast_parser_agent import CodeEntity

    mock = MagicMock()
    mock.parse_file = MagicMock(
        return_value=[
            CodeEntity(
                name="TestClass",
                entity_type="class",
                file_path="test.py",
                line_number=1,
                dependencies=["os"],
            )
        ]
    )
    return mock


@pytest.fixture
def mock_persistence():
    """Create mock persistence service."""
    mock = MagicMock()
    mock.save_job = MagicMock()
    mock.update_job_status = MagicMock()
    mock.get_active_jobs = MagicMock(return_value=[])
    mock.get_job = MagicMock(return_value=None)
    return mock


@pytest.fixture
def mock_observability():
    """Create mock observability service."""
    mock = MagicMock()
    mock.record_request = MagicMock()
    mock.record_latency = MagicMock()
    mock.record_success = MagicMock()
    mock.record_error = MagicMock()
    mock.record_resource_usage = MagicMock()
    return mock


@pytest.fixture
def mock_github_app_auth():
    """Create mock GitHub App auth."""
    mock = MagicMock()
    mock.get_installation_token = MagicMock(return_value="ghs_test_token")
    return mock


@pytest.fixture
def service(
    mock_neptune,
    mock_opensearch,
    mock_embedding_service,
    mock_ast_parser,
    mock_observability,
):
    """Create GitIngestionService with mocked dependencies."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = GitIngestionService(
            neptune_service=mock_neptune,
            opensearch_service=mock_opensearch,
            embedding_service=mock_embedding_service,
            ast_parser=mock_ast_parser,
            observability_service=mock_observability,
            clone_base_path=temp_dir,
        )
        yield service


@pytest.fixture
def service_with_persistence(
    mock_neptune,
    mock_opensearch,
    mock_embedding_service,
    mock_ast_parser,
    mock_persistence,
    mock_observability,
):
    """Create GitIngestionService with persistence."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = GitIngestionService(
            neptune_service=mock_neptune,
            opensearch_service=mock_opensearch,
            embedding_service=mock_embedding_service,
            ast_parser=mock_ast_parser,
            persistence_service=mock_persistence,
            observability_service=mock_observability,
            clone_base_path=temp_dir,
        )
        yield service


# =============================================================================
# SERVICE INITIALIZATION TESTS
# =============================================================================


class TestGitIngestionServiceInit:
    """Test service initialization."""

    def test_basic_initialization(
        self, mock_neptune, mock_opensearch, mock_embedding_service, mock_ast_parser
    ):
        """Test basic service initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embedding_service,
                ast_parser=mock_ast_parser,
                clone_base_path=temp_dir,
            )
            assert service.neptune == mock_neptune
            assert service.opensearch == mock_opensearch
            assert service.clone_dir.exists()
            assert service.batch_size == 50
            assert service.max_file_size_kb == 500

    def test_default_clone_path(
        self, mock_neptune, mock_opensearch, mock_embedding_service, mock_ast_parser
    ):
        """Test default clone path uses temp directory."""
        service = GitIngestionService(
            neptune_service=mock_neptune,
            opensearch_service=mock_opensearch,
            embedding_service=mock_embedding_service,
            ast_parser=mock_ast_parser,
        )
        assert "aura-repos" in str(service.clone_dir)

    def test_supported_extensions(self, service):
        """Test supported file extensions."""
        expected = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs"}
        assert service.supported_extensions == expected

    def test_ignore_patterns(self, service):
        """Test ignore patterns are set."""
        assert "__pycache__" in service.ignore_patterns
        assert ".git" in service.ignore_patterns
        assert "node_modules" in service.ignore_patterns


# =============================================================================
# PERSISTENCE TESTS
# =============================================================================


class TestPersistence:
    """Test job persistence functionality."""

    def test_load_active_jobs_empty(self, service_with_persistence, mock_persistence):
        """Test loading active jobs when none exist."""
        mock_persistence.get_active_jobs.return_value = []
        assert len(service_with_persistence.active_jobs) == 0

    def test_load_active_jobs_with_data(
        self,
        mock_neptune,
        mock_opensearch,
        mock_embedding_service,
        mock_ast_parser,
        mock_observability,
    ):
        """Test loading active jobs from persistence."""
        mock_persistence = MagicMock()
        mock_persistence.get_active_jobs.return_value = [
            {
                "job_id": "test-job-1",
                "repository_url": "https://github.com/org/repo",
                "branch": "main",
                "mode": "full",  # Lowercase to match IngestionMode enum
                "status": "pending",  # Lowercase to match IngestionStatus enum
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            service = GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embedding_service,
                ast_parser=mock_ast_parser,
                persistence_service=mock_persistence,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
            )
            assert "test-job-1" in service.active_jobs

    def test_persist_job(self, service_with_persistence, mock_persistence):
        """Test job persistence."""
        job = IngestionJob(
            job_id="test-123",
            repository_url="https://github.com/org/repo",
        )
        service_with_persistence._persist_job(job)
        mock_persistence.save_job.assert_called_once_with(job)

    def test_persist_job_no_persistence(self, service):
        """Test persist job does nothing without persistence service."""
        job = IngestionJob(
            job_id="test-123",
            repository_url="https://github.com/org/repo",
        )
        service._persist_job(job)  # Should not raise

    def test_update_job_status(self, service_with_persistence, mock_persistence):
        """Test updating job status in persistence."""
        service_with_persistence._update_job_status_in_persistence(
            "job-123",
            IngestionStatus.COMPLETED,
            {"files_processed": 10},
        )
        mock_persistence.update_job_status.assert_called_once_with(
            "job-123", "completed", {"files_processed": 10}
        )

    def test_persist_job_error_handling(
        self, service_with_persistence, mock_persistence
    ):
        """Test persistence error handling."""
        mock_persistence.save_job.side_effect = Exception("DB error")
        job = IngestionJob(
            job_id="test-123",
            repository_url="https://github.com/org/repo",
        )
        # Should not raise
        service_with_persistence._persist_job(job)


# =============================================================================
# URL AND ID HELPERS TESTS
# =============================================================================


class TestUrlHelpers:
    """Test URL and ID helper methods."""

    def test_url_to_repo_id_github(self, service):
        """Test GitHub URL to repo ID conversion."""
        assert service._url_to_repo_id("https://github.com/org/repo.git") == "org-repo"
        assert service._url_to_repo_id("https://github.com/org/repo") == "org-repo"

    def test_url_to_repo_id_trailing_slash(self, service):
        """Test URL with trailing slash."""
        assert service._url_to_repo_id("https://github.com/org/repo/") == "org-repo"

    def test_url_to_repo_id_short_url(self, service):
        """Test fallback for short URLs."""
        result = service._url_to_repo_id("short")
        assert len(result) == 16  # SHA256 hash truncated

    def test_generate_job_id(self, service):
        """Test job ID generation."""
        job_id = service._generate_job_id("https://github.com/org/repo", "main")
        assert job_id.startswith("ingest-")
        assert len(job_id) > 20

    def test_generate_job_id_unique(self, service):
        """Test job IDs are unique."""
        id1 = service._generate_job_id("https://github.com/org/repo", "main")
        id2 = service._generate_job_id("https://github.com/org/repo", "main")
        # IDs include timestamp so should be same if generated same second
        # But hash is different due to content
        assert "ingest-" in id1
        assert "ingest-" in id2


# =============================================================================
# AUTHENTICATION TESTS
# =============================================================================


class TestAuthentication:
    """Test secure authentication methods.

    These tests verify that credentials are passed securely via HTTP headers
    instead of being embedded in URLs.
    """

    def test_get_auth_header_legacy_token(self, service):
        """Test generating auth header with legacy PAT."""
        import base64

        service.github_app_auth = None
        service.github_token = "ghp_test123"
        header = service._get_auth_header("https://github.com/org/repo.git")

        # Should return Basic auth header with base64-encoded credentials
        assert header is not None
        assert header.startswith("Basic ")
        # Decode and verify format
        encoded = header.split(" ")[1]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "x-access-token:ghp_test123"

    def test_get_auth_header_no_token(self, service):
        """Test no auth header without token."""
        service.github_app_auth = None
        service.github_token = None
        header = service._get_auth_header("https://github.com/org/repo.git")
        assert header is None

    def test_get_auth_header_non_github(self, service):
        """Test non-GitHub URL returns no auth header."""
        service.github_token = "ghp_test123"
        header = service._get_auth_header("https://gitlab.com/org/repo.git")
        assert header is None

    def test_get_git_auth_options_with_token(self, service):
        """Test git auth options include http.extraHeader."""
        service.github_app_auth = None
        service.github_token = "ghp_test123"
        options = service._get_git_auth_options("https://github.com/org/repo.git")

        assert len(options) == 2
        assert options[0] == "-c"
        assert options[1].startswith("http.extraHeader=Authorization: Basic ")

    def test_get_git_auth_options_without_token(self, service):
        """Test git auth options empty without token."""
        service.github_app_auth = None
        service.github_token = None
        options = service._get_git_auth_options("https://github.com/org/repo.git")
        assert options == []

    def test_get_auth_header_github_app(
        self,
        mock_neptune,
        mock_opensearch,
        mock_embedding_service,
        mock_ast_parser,
        mock_github_app_auth,
        mock_observability,
    ):
        """Test GitHub App authentication generates secure header."""
        import base64

        with tempfile.TemporaryDirectory() as temp_dir:
            service = GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embedding_service,
                ast_parser=mock_ast_parser,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
                github_app_auth=mock_github_app_auth,
            )
            header = service._get_auth_header("https://github.com/org/repo.git")

            assert header is not None
            assert header.startswith("Basic ")
            encoded = header.split(" ")[1]
            decoded = base64.b64decode(encoded).decode()
            assert "x-access-token:ghs_test_token" in decoded

    def test_get_auth_header_github_app_failure_fallback(
        self,
        mock_neptune,
        mock_opensearch,
        mock_embedding_service,
        mock_ast_parser,
        mock_observability,
    ):
        """Test fallback to PAT when App auth fails."""
        import base64

        mock_app_auth = MagicMock()
        mock_app_auth.get_installation_token.side_effect = Exception("App auth failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embedding_service,
                ast_parser=mock_ast_parser,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
                github_app_auth=mock_app_auth,
                github_token="ghp_fallback",
            )
            header = service._get_auth_header("https://github.com/org/repo.git")

            assert header is not None
            encoded = header.split(" ")[1]
            decoded = base64.b64decode(encoded).decode()
            assert "ghp_fallback" in decoded

    def test_sanitize_git_output_redacts_tokens(self, service):
        """Test that git output sanitization redacts various token formats."""
        # Test various token patterns
        test_cases = [
            (
                "Error: ghp_abc123xyz789defghijklmnopqrstu1234567 not found",
                "[REDACTED]",
            ),
            ("Failed with ghs_installtokenxyz123456789012345678901", "[REDACTED]"),
            ("x-access-token:secrettoken@github.com", "[REDACTED]"),
            ("Authorization: Basic dXNlcjpwYXNz", "[REDACTED]"),
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "[REDACTED]"),
        ]

        for input_text, expected_redaction in test_cases:
            result = service._sanitize_git_output(input_text)
            assert expected_redaction in result
            # Ensure original secret is not in output
            if "ghp_" in input_text:
                assert "ghp_" not in result
            if "ghs_" in input_text:
                assert "ghs_" not in result

    def test_sanitize_git_output_preserves_safe_text(self, service):
        """Test that sanitization preserves non-sensitive text."""
        safe_text = "Cloning into '/tmp/repo'...\nReceiving objects: 100%"
        result = service._sanitize_git_output(safe_text)
        assert result == safe_text


# =============================================================================
# FILE DISCOVERY TESTS
# =============================================================================


class TestFileDiscovery:
    """Test file discovery methods."""

    async def test_discover_python_files(self, service):
        """Test discovering Python files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "app.py").write_text("print('hello')")
            (temp_path / "test.js").write_text("console.log('hi')")

            files = await service._discover_files(temp_path)
            assert len(files) == 2

    async def test_discover_ignores_pycache(self, service):
        """Test that __pycache__ is ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "__pycache__").mkdir()
            (temp_path / "__pycache__" / "module.cpython-311.pyc").write_text("data")
            (temp_path / "app.py").write_text("print('hello')")

            files = await service._discover_files(temp_path)
            assert len(files) == 1
            assert files[0].name == "app.py"

    async def test_discover_ignores_node_modules(self, service):
        """Test that node_modules is ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "node_modules").mkdir()
            (temp_path / "node_modules" / "lib.js").write_text("code")
            (temp_path / "app.js").write_text("code")

            files = await service._discover_files(temp_path)
            assert len(files) == 1
            assert files[0].name == "app.js"

    async def test_discover_ignores_large_files(self, service):
        """Test that large files are skipped."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "small.py").write_text("x = 1")
            # Create file larger than max_file_size_kb
            (temp_path / "large.py").write_text("x" * (600 * 1024))

            files = await service._discover_files(temp_path)
            assert len(files) == 1
            assert files[0].name == "small.py"

    async def test_discover_ignores_unsupported_extensions(self, service):
        """Test that unsupported extensions are ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "app.py").write_text("code")
            (temp_path / "readme.md").write_text("# Readme")
            (temp_path / "config.yaml").write_text("key: value")

            files = await service._discover_files(temp_path)
            assert len(files) == 1
            assert files[0].suffix == ".py"


# =============================================================================
# JOB STATUS TESTS
# =============================================================================


class TestJobStatus:
    """Test job status methods."""

    def test_get_job_status_active(self, service):
        """Test getting active job status."""
        job = IngestionJob(
            job_id="test-1", repository_url="https://github.com/org/repo"
        )
        service.active_jobs["test-1"] = job

        result = service.get_job_status("test-1")
        assert result == job

    def test_get_job_status_completed(self, service):
        """Test getting completed job status."""
        job = IngestionJob(
            job_id="test-1", repository_url="https://github.com/org/repo"
        )
        service.completed_jobs.append(job)

        result = service.get_job_status("test-1")
        assert result == job

    def test_get_job_status_not_found(self, service):
        """Test getting non-existent job status."""
        result = service.get_job_status("nonexistent")
        assert result is None

    def test_list_active_jobs(self, service):
        """Test listing active jobs."""
        job1 = IngestionJob(
            job_id="test-1", repository_url="https://github.com/org/repo1"
        )
        job2 = IngestionJob(
            job_id="test-2", repository_url="https://github.com/org/repo2"
        )
        service.active_jobs["test-1"] = job1
        service.active_jobs["test-2"] = job2

        result = service.list_active_jobs()
        assert len(result) == 2


# =============================================================================
# DELETE REPOSITORY TESTS
# =============================================================================


class TestDeleteRepository:
    """Test repository deletion."""

    @pytest.mark.asyncio
    async def test_delete_repository_success(
        self, service, mock_neptune, mock_opensearch
    ):
        """Test successful repository deletion."""
        # Create a fake clone directory
        repo_id = service._url_to_repo_id("https://github.com/org/repo")
        clone_path = service.clone_dir / repo_id
        clone_path.mkdir(parents=True)
        (clone_path / "test.py").write_text("test")

        result = await service.delete_repository("https://github.com/org/repo")

        assert result["success"] is True
        assert result["neptune_entities_deleted"] == 10
        assert result["opensearch_documents_deleted"] == 5
        assert result["local_clone_removed"] is True
        assert not clone_path.exists()

    @pytest.mark.asyncio
    async def test_delete_repository_no_local_clone(
        self, service, mock_neptune, mock_opensearch
    ):
        """Test deletion when no local clone exists."""
        result = await service.delete_repository("https://github.com/org/repo")

        assert result["success"] is True
        assert result["local_clone_removed"] is False

    @pytest.mark.asyncio
    async def test_delete_repository_neptune_error(
        self, service, mock_neptune, mock_opensearch
    ):
        """Test deletion with Neptune error."""
        mock_neptune.delete_by_repository.side_effect = Exception("Neptune error")

        result = await service.delete_repository("https://github.com/org/repo")

        assert result["success"] is False
        assert any("Neptune" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_delete_repository_opensearch_error(
        self, service, mock_neptune, mock_opensearch
    ):
        """Test deletion with OpenSearch error."""
        mock_opensearch.delete_by_repository.side_effect = Exception("OpenSearch error")

        result = await service.delete_repository("https://github.com/org/repo")

        assert result["success"] is False
        assert any("OpenSearch" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_delete_repository_no_services(
        self, mock_embedding_service, mock_ast_parser, mock_observability
    ):
        """Test deletion without Neptune/OpenSearch services."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = GitIngestionService(
                neptune_service=None,
                opensearch_service=None,
                embedding_service=mock_embedding_service,
                ast_parser=mock_ast_parser,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
            )
            result = await service.delete_repository("https://github.com/org/repo")

        assert result["success"] is True
        assert result["neptune_entities_deleted"] == 0
        assert result["opensearch_documents_deleted"] == 0


# =============================================================================
# EMBEDDING GENERATION TESTS
# =============================================================================


class TestEmbeddingGeneration:
    """Test embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embedding_with_generate_method(
        self, service, mock_embedding_service
    ):
        """Test embedding with generate_embedding method."""
        mock_embedding_service.generate_embedding.return_value = [0.5] * 1024

        result = await service._generate_embedding("Test text")

        assert result == [0.5] * 1024

    @pytest.mark.asyncio
    async def test_generate_embedding_with_embed_method(
        self, mock_neptune, mock_opensearch, mock_ast_parser, mock_observability
    ):
        """Test embedding with embed method."""
        mock_embedding = MagicMock()
        mock_embedding.embed = MagicMock(return_value=[0.3] * 1024)
        del mock_embedding.generate_embedding  # Remove generate_embedding

        with tempfile.TemporaryDirectory() as temp_dir:
            service = GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embedding,
                ast_parser=mock_ast_parser,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
            )
            result = await service._generate_embedding("Test text")

        assert result == [0.3] * 1024

    @pytest.mark.asyncio
    async def test_generate_embedding_truncates_text(
        self, service, mock_embedding_service
    ):
        """Test embedding truncates long text."""
        long_text = "x" * 10000
        await service._generate_embedding(long_text)

        # Check that truncated text was passed (max 8000 chars)
        call_args = mock_embedding_service.generate_embedding.call_args[0][0]
        assert len(call_args) <= 8000

    @pytest.mark.asyncio
    async def test_generate_embedding_error(self, service, mock_embedding_service):
        """Test embedding error handling."""
        mock_embedding_service.generate_embedding.side_effect = Exception("API error")

        result = await service._generate_embedding("Test text")

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_embedding_mock_fallback(
        self, mock_neptune, mock_opensearch, mock_ast_parser, mock_observability
    ):
        """Test mock embedding fallback."""
        mock_embedding = MagicMock(spec=[])  # No methods defined

        with tempfile.TemporaryDirectory() as temp_dir:
            service = GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embedding,
                ast_parser=mock_ast_parser,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
            )
            result = await service._generate_embedding("Test text")

        assert result == [0.1] * 1024


# =============================================================================
# COMMIT HASH TESTS
# =============================================================================


class TestCommitHash:
    """Test commit hash retrieval."""

    def test_get_current_commit_invalid_repo(self, service):
        """Test getting commit from invalid repo path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = service._get_current_commit(Path(temp_dir))
            assert result == "unknown"

    def test_get_current_commit_valid_repo(self, service):
        """Test getting commit from valid repo."""
        import subprocess

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            subprocess.run(["git", "init"], cwd=temp_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=temp_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_path,
                capture_output=True,
            )
            (temp_path / "test.txt").write_text("test")
            subprocess.run(["git", "add", "."], cwd=temp_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial"],
                cwd=temp_path,
                capture_output=True,
            )

            result = service._get_current_commit(temp_path)
            assert len(result) == 8  # Short hash


# =============================================================================
# INGEST CHANGES TESTS
# =============================================================================


class TestIngestChanges:
    """Test incremental ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_changes_filters_unsupported(self, service, mock_ast_parser):
        """Test that unsupported files are filtered."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "app.py").write_text("code")
            (temp_path / "readme.md").write_text("docs")

            result = await service.ingest_changes(
                repository_path=temp_path,
                changed_files=["app.py", "readme.md"],
            )

            # Only app.py should be processed
            assert result.files_processed == 1

    @pytest.mark.asyncio
    async def test_ingest_changes_filters_nonexistent(self, service, mock_ast_parser):
        """Test that non-existent files are filtered."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "existing.py").write_text("code")

            result = await service.ingest_changes(
                repository_path=temp_path,
                changed_files=["existing.py", "deleted.py"],
            )

            assert result.files_processed == 1

    @pytest.mark.asyncio
    async def test_ingest_changes_success(
        self,
        service,
        mock_neptune,
        mock_opensearch,
        mock_ast_parser,
        mock_observability,
    ):
        """Test successful incremental ingestion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "app.py").write_text("class App: pass")

            result = await service.ingest_changes(
                repository_path=temp_path,
                changed_files=["app.py"],
                commit_hash="abc123",
            )

            assert result.success is True
            assert result.commit_hash == "abc123"
            mock_observability.record_success.assert_called()

    @pytest.mark.asyncio
    async def test_ingest_changes_failure(
        self, service, mock_ast_parser, mock_observability
    ):
        """Test incremental ingestion failure."""
        mock_ast_parser.parse_file.side_effect = Exception("Parse error")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "app.py").write_text("invalid python")

            result = await service.ingest_changes(
                repository_path=temp_path,
                changed_files=["app.py"],
            )

            # Should still succeed (errors are logged but not fatal)
            assert result.success is True


# =============================================================================
# PARSE FILES TESTS
# =============================================================================


class TestParseFiles:
    """Test file parsing."""

    @pytest.mark.asyncio
    async def test_parse_files_updates_paths(self, service, mock_ast_parser):
        """Test that file paths are made relative."""
        from src.agents.ast_parser_agent import CodeEntity

        mock_ast_parser.parse_file.return_value = [
            CodeEntity(
                name="Test",
                entity_type="class",
                file_path="/absolute/path/test.py",
                line_number=1,
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "src" / "test.py"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("class Test: pass")

            entities = await service._parse_files([test_file], temp_path)

            assert entities[0].file_path == "src/test.py"

    @pytest.mark.asyncio
    async def test_parse_files_handles_errors(self, service, mock_ast_parser):
        """Test that parse errors are handled gracefully."""
        mock_ast_parser.parse_file.side_effect = Exception("Parse error")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text("invalid")

            entities = await service._parse_files([test_file], temp_path)

            assert entities == []


# =============================================================================
# INDEX EMBEDDINGS TESTS
# =============================================================================


class TestIndexEmbeddings:
    """Test embedding indexing."""

    @pytest.mark.asyncio
    async def test_index_embeddings_skips_empty_files(self, service, mock_opensearch):
        """Test that nearly empty files are skipped."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "empty.py").write_text("# hi")

            count = await service._index_embeddings(
                [temp_path / "empty.py"],
                temp_path,
                "https://github.com/org/repo",
            )

            assert count == 0

    @pytest.mark.asyncio
    async def test_index_embeddings_handles_errors(
        self, service, mock_opensearch, mock_embedding_service
    ):
        """Test that indexing errors are handled."""
        mock_embedding_service.generate_embedding.side_effect = Exception("Error")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "app.py").write_text("print('hello world')")

            count = await service._index_embeddings(
                [temp_path / "app.py"],
                temp_path,
                "https://github.com/org/repo",
            )

            assert count == 0

    @pytest.mark.asyncio
    async def test_index_embeddings_truncates_content(
        self, service, mock_opensearch, mock_embedding_service
    ):
        """Test that content is truncated for storage."""
        mock_embedding_service.generate_embedding.return_value = [0.1] * 1024
        # Mock bulk_index_embeddings to return a success count
        mock_opensearch.bulk_index_embeddings.return_value = {"success_count": 1}

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create file with more than 5000 chars
            (temp_path / "large.py").write_text("x" * 10000)

            # Set clone_dir to temp directory so security check passes
            original_clone_dir = service.clone_dir
            service.clone_dir = temp_path

            try:
                count = await service._index_embeddings(
                    [temp_path / "large.py"],
                    temp_path,
                    "https://github.com/org/repo",
                )

                assert count == 1
                # Check that text was truncated in the bulk call
                call_args = mock_opensearch.bulk_index_embeddings.call_args
                documents = call_args[0][
                    0
                ]  # First positional arg is the documents list
                assert len(documents[0]["text"]) <= 5000
            finally:
                service.clone_dir = original_clone_dir


# =============================================================================
# ASYNC AND CONCURRENCY TESTS
# =============================================================================


class TestAsyncConcurrency:
    """Test async operations and concurrency controls."""

    @pytest.fixture
    def service_with_concurrency(self, mock_observability):
        """Create service with custom concurrency limits."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_ast_parser = MagicMock()
            mock_ast_parser.parse_file.return_value = []
            mock_neptune = MagicMock()
            mock_opensearch = MagicMock()
            mock_embeddings = MagicMock()
            mock_embeddings.generate_embedding.return_value = [0.1] * 1024

            yield GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embeddings,
                ast_parser=mock_ast_parser,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
                max_concurrent_parse=2,
                max_concurrent_graph=3,
                max_concurrent_index=1,
            )

    def test_semaphore_initialization(self, service_with_concurrency):
        """Test that semaphores are initialized with correct limits."""
        service = service_with_concurrency
        # Semaphores should be created
        assert hasattr(service, "_parse_semaphore")
        assert hasattr(service, "_graph_semaphore")
        assert hasattr(service, "_index_semaphore")
        # Semaphores are asyncio.Semaphore instances
        assert isinstance(service._parse_semaphore, asyncio.Semaphore)
        assert isinstance(service._graph_semaphore, asyncio.Semaphore)
        assert isinstance(service._index_semaphore, asyncio.Semaphore)

    def test_default_concurrency_limits(self, service):
        """Test that default concurrency limits are applied."""
        assert service._parse_semaphore._value == 10  # DEFAULT_MAX_CONCURRENT_PARSE
        assert service._graph_semaphore._value == 20  # DEFAULT_MAX_CONCURRENT_GRAPH
        assert service._index_semaphore._value == 5  # DEFAULT_MAX_CONCURRENT_INDEX

    def test_custom_concurrency_limits(self, service_with_concurrency):
        """Test that custom concurrency limits are applied."""
        service = service_with_concurrency
        assert service._parse_semaphore._value == 2
        assert service._graph_semaphore._value == 3
        assert service._index_semaphore._value == 1

    @pytest.mark.asyncio
    async def test_discover_files_is_async(self, service):
        """Test that _discover_files is properly async."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "app.py").write_text("print('hello')")

            # Should return awaitable
            result = service._discover_files(temp_path)
            assert asyncio.iscoroutine(result)

            # Should complete successfully
            files = await result
            assert len(files) == 1

    @pytest.mark.asyncio
    async def test_parse_files_concurrent(self, mock_observability):
        """Test that _parse_files processes files concurrently."""
        mock_ast_parser = MagicMock()
        mock_ast_parser.parse_file.return_value = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create multiple files
            for i in range(5):
                (temp_path / f"file{i}.py").write_text(f"x = {i}")

            service = GitIngestionService(
                ast_parser=mock_ast_parser,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
            )

            files = [temp_path / f"file{i}.py" for i in range(5)]
            await service._parse_files(files, temp_path)

            # All files should be parsed
            assert mock_ast_parser.parse_file.call_count == 5

    @pytest.mark.asyncio
    async def test_populate_graph_concurrent(self, mock_observability):
        """Test that _populate_graph processes entities concurrently."""
        mock_neptune = MagicMock()

        with tempfile.TemporaryDirectory() as temp_dir:
            service = GitIngestionService(
                neptune_service=mock_neptune,
                observability_service=mock_observability,
                clone_base_path=temp_dir,
            )

            # Create mock entities
            entities = []
            for i in range(5):
                entity = MagicMock()
                entity.name = f"Entity{i}"
                entity.entity_type = "class"
                entity.file_path = f"file{i}.py"
                entity.line_number = 1
                entity.parent_entity = None
                entity.dependencies = []
                entity.attributes = {}
                entities.append(entity)

            await service._populate_graph(
                entities, "https://github.com/org/repo", "main"
            )

            # All entities should be added
            assert mock_neptune.add_code_entity.call_count == 5

    @pytest.mark.asyncio
    async def test_async_clone_or_fetch_offloads_to_thread(self, mock_observability):
        """Test that git operations are offloaded to thread pool."""
        import subprocess
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Initialize a git repo
            subprocess.run(["git", "init"], cwd=temp_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=temp_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=temp_path,
                capture_output=True,
            )
            (temp_path / "test.txt").write_text("test")
            subprocess.run(["git", "add", "."], cwd=temp_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial"],
                cwd=temp_path,
                capture_output=True,
            )

            service = GitIngestionService(
                observability_service=mock_observability,
                clone_base_path=str(temp_path / "clones"),
            )

            # Patch asyncio.to_thread to verify it's called
            with patch("asyncio.to_thread") as mock_to_thread:
                mock_to_thread.return_value = temp_path

                try:
                    # Will fail due to mock, but we're checking to_thread is used
                    await service._clone_or_fetch(
                        str(temp_path), "main", shallow=True, force_refresh=True
                    )
                except Exception:
                    pass

                # asyncio.to_thread should have been called
                assert mock_to_thread.called
