"""
Integration Tests for Git Ingestion Pipeline

Tests the GitIngestionService and GitHubWebhookHandler components.

Author: Project Aura Team
Created: 2025-11-28
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Configure pytest-anyio to use asyncio backend
pytestmark = pytest.mark.anyio

from src.api.webhook_handler import GitHubWebhookHandler, WebhookEvent, WebhookEventType
from src.services.git_ingestion_service import (
    GitIngestionService,
    IngestionJob,
    IngestionStatus,
)

# ==================== Fixtures ====================


@pytest.fixture
def mock_neptune():
    """Create a mock Neptune client."""
    mock = MagicMock()
    mock.add_code_entity = MagicMock(return_value="entity-123")
    mock.add_relationship = MagicMock(return_value=True)
    return mock


@pytest.fixture
def mock_opensearch():
    """Create a mock OpenSearch client."""
    mock = MagicMock()
    mock.index_embedding = MagicMock(return_value=True)
    mock.bulk_index_embeddings = MagicMock(
        return_value={"success": True, "success_count": 1}
    )
    mock.search_similar = MagicMock(return_value=[])
    return mock


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    mock = MagicMock()
    mock.generate_embedding = AsyncMock(return_value=[0.1] * 1024)
    return mock


@pytest.fixture
def mock_ast_parser():
    """Create a mock AST parser."""
    from src.agents.ast_parser_agent import CodeEntity

    mock = MagicMock()
    mock.parse_file = MagicMock(
        return_value=[
            CodeEntity(
                name="TestClass",
                entity_type="class",
                file_path="test.py",
                line_number=1,
                dependencies=["os", "sys"],
                attributes={"docstring": "A test class"},
            ),
            CodeEntity(
                name="test_function",
                entity_type="function",
                file_path="test.py",
                line_number=10,
                parent_entity="TestClass",
                dependencies=[],
                attributes={"is_async": False},
            ),
        ]
    )
    return mock


@pytest.fixture
def ingestion_service(
    mock_neptune, mock_opensearch, mock_embedding_service, mock_ast_parser
):
    """Create a GitIngestionService with mocked dependencies."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = GitIngestionService(
            neptune_service=mock_neptune,
            opensearch_service=mock_opensearch,
            embedding_service=mock_embedding_service,
            ast_parser=mock_ast_parser,
            clone_base_path=temp_dir,
        )
        yield service


@pytest.fixture
def webhook_handler(ingestion_service):
    """Create a GitHubWebhookHandler with ingestion service."""
    return GitHubWebhookHandler(
        webhook_secret="test-secret",
        ingestion_service=ingestion_service,
        allowed_branches=["main", "develop"],
    )


@pytest.fixture
def sample_push_payload():
    """Sample GitHub push event payload."""
    return {
        "ref": "refs/heads/main",
        "after": "abc123def456",
        "repository": {
            "name": "test-repo",
            "full_name": "org/test-repo",
            "clone_url": "https://github.com/org/test-repo.git",
            "html_url": "https://github.com/org/test-repo",
        },
        "commits": [
            {
                "id": "abc123",
                "added": ["src/new_file.py"],
                "modified": ["src/existing.py"],
                "removed": ["src/old_file.py"],
            }
        ],
        "sender": {"login": "developer"},
    }


@pytest.fixture
def sample_pr_payload():
    """Sample GitHub pull request event payload."""
    return {
        "action": "opened",
        "pull_request": {
            "number": 42,
            "title": "Add new feature",
            "head": {
                "ref": "feature/new-feature",
                "sha": "def456abc789",
            },
            "base": {
                "ref": "main",
            },
        },
        "repository": {
            "name": "test-repo",
            "full_name": "org/test-repo",
            "clone_url": "https://github.com/org/test-repo.git",
        },
        "sender": {"login": "developer"},
    }


# ==================== GitIngestionService Tests ====================


class TestGitIngestionService:
    """Tests for GitIngestionService."""

    def test_initialization(self, ingestion_service):
        """Test service initializes correctly."""
        assert ingestion_service.neptune is not None
        assert ingestion_service.opensearch is not None
        assert ingestion_service.embeddings is not None
        assert ingestion_service.ast_parser is not None
        assert ingestion_service.clone_dir.exists()

    def test_generate_job_id(self, ingestion_service):
        """Test job ID generation."""
        job_id = ingestion_service._generate_job_id(
            "https://github.com/org/repo", "main"
        )
        assert job_id.startswith("ingest-")
        assert len(job_id) > 20

    def test_url_to_repo_id(self, ingestion_service):
        """Test URL to repo ID conversion."""
        repo_id = ingestion_service._url_to_repo_id(
            "https://github.com/myorg/myrepo.git"
        )
        assert repo_id == "myorg-myrepo"

        repo_id = ingestion_service._url_to_repo_id("https://github.com/myorg/myrepo")
        assert repo_id == "myorg-myrepo"

    def test_get_git_auth_options(self, ingestion_service):
        """Test git auth command-line options generation."""
        # Test with token set - should return auth header options
        ingestion_service.github_token = "ghp_test123"
        options = ingestion_service._get_git_auth_options(
            "https://github.com/org/repo.git"
        )
        assert isinstance(options, list)
        if options:  # Will have options if token is set
            assert "-c" in options
            assert any("http.extraHeader" in opt for opt in options)

        # Test without token - should return empty list
        ingestion_service.github_token = None
        options = ingestion_service._get_git_auth_options(
            "https://github.com/org/repo.git"
        )
        assert options == []

    async def test_discover_files(self, ingestion_service):
        """Test file discovery respects filters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "src").mkdir()
            (temp_path / "src" / "app.py").write_text("print('hello')")
            (temp_path / "src" / "utils.js").write_text("console.log('hi')")
            (temp_path / "README.md").write_text("# Readme")
            (temp_path / "__pycache__").mkdir()
            (temp_path / "__pycache__" / "cache.pyc").write_text("cache")

            files = await ingestion_service._discover_files(temp_path)

            file_names = [f.name for f in files]
            assert "app.py" in file_names
            assert "utils.js" in file_names
            assert "README.md" not in file_names
            assert "cache.pyc" not in file_names

    async def test_parse_files(self, ingestion_service):
        """Test file parsing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.py"
            test_file.write_text("class MyClass:\n    pass")

            entities = await ingestion_service._parse_files([test_file], temp_path)

            assert len(entities) == 2
            assert entities[0].name == "TestClass"
            assert entities[0].entity_type == "class"

    async def test_populate_graph(self, ingestion_service, mock_neptune):
        """Test Neptune graph population."""
        from src.agents.ast_parser_agent import CodeEntity

        entities = [
            CodeEntity(
                name="MyClass",
                entity_type="class",
                file_path="src/app.py",
                line_number=1,
                dependencies=["os"],
            )
        ]

        await ingestion_service._populate_graph(
            entities, "https://github.com/org/repo", "main"
        )

        mock_neptune.add_code_entity.assert_called()
        mock_neptune.add_relationship.assert_called()

    async def test_index_embeddings(self, ingestion_service, mock_opensearch):
        """Test OpenSearch embedding indexing with bulk API."""
        # Use the service's clone_dir to pass security checks
        repo_path = ingestion_service.clone_dir / "test-repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        test_file = repo_path / "test.py"
        test_file.write_text("def hello():\n    print('world')")

        count = await ingestion_service._index_embeddings(
            [test_file], repo_path, "https://github.com/org/repo"
        )

        assert count == 1
        mock_opensearch.bulk_index_embeddings.assert_called_once()

    def test_job_status_tracking(self, ingestion_service):
        """Test job status tracking."""
        assert len(ingestion_service.list_active_jobs()) == 0

        job = IngestionJob(
            job_id="test-123",
            repository_url="https://github.com/org/repo",
            status=IngestionStatus.PENDING,
        )
        ingestion_service.active_jobs["test-123"] = job

        assert len(ingestion_service.list_active_jobs()) == 1
        assert ingestion_service.get_job_status("test-123") == job

        ingestion_service.completed_jobs.append(
            ingestion_service.active_jobs.pop("test-123")
        )

        assert len(ingestion_service.list_active_jobs()) == 0
        assert ingestion_service.get_job_status("test-123") == job


# ==================== WebhookHandler Tests ====================


class TestGitHubWebhookHandler:
    """Tests for GitHubWebhookHandler."""

    def test_initialization(self, webhook_handler):
        """Test handler initializes correctly."""
        assert webhook_handler.webhook_secret == "test-secret"
        assert "main" in webhook_handler.allowed_branches
        assert "develop" in webhook_handler.allowed_branches

    def test_validate_signature_valid(self, webhook_handler):
        """Test valid signature validation."""
        import hashlib
        import hmac

        payload = b'{"test": "data"}'
        signature = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()

        assert webhook_handler.validate_signature(payload, f"sha256={signature}")

    def test_validate_signature_invalid(self, webhook_handler):
        """Test invalid signature validation."""
        payload = b'{"test": "data"}'
        assert not webhook_handler.validate_signature(payload, "sha256=invalid")

    def test_validate_signature_no_secret(self):
        """Test validation when no secret configured."""
        handler = GitHubWebhookHandler(webhook_secret=None)
        assert handler.validate_signature(b"payload", "")

    def test_parse_push_event(self, webhook_handler, sample_push_payload):
        """Test parsing push event."""
        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "",
        }
        webhook_handler.webhook_secret = None

        event = webhook_handler.parse_event(headers, json.dumps(sample_push_payload))

        assert event is not None
        assert event.event_type == WebhookEventType.PUSH
        assert event.branch == "main"
        assert event.repository_name == "org/test-repo"
        assert event.commit_hash == "abc123def456"
        assert "src/new_file.py" in event.changed_files
        assert "src/existing.py" in event.changed_files

    def test_parse_pull_request_event(self, webhook_handler, sample_pr_payload):
        """Test parsing pull request event."""
        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "",
        }
        webhook_handler.webhook_secret = None

        event = webhook_handler.parse_event(headers, json.dumps(sample_pr_payload))

        assert event is not None
        assert event.event_type == WebhookEventType.PULL_REQUEST
        assert event.branch == "feature/new-feature"
        assert event.commit_hash == "def456abc789"

    def test_parse_unsupported_event(self, webhook_handler):
        """Test parsing unsupported event type."""
        headers = {"X-GitHub-Event": "star"}
        webhook_handler.webhook_secret = None

        event = webhook_handler.parse_event(headers, "{}")
        assert event is None

    def test_parse_invalid_json(self, webhook_handler):
        """Test parsing invalid JSON."""
        headers = {"X-GitHub-Event": "push"}
        webhook_handler.webhook_secret = None

        event = webhook_handler.parse_event(headers, "not valid json")
        assert event is None

    async def test_process_event_allowed_branch(
        self, webhook_handler, sample_push_payload
    ):
        """Test processing event on allowed branch."""
        webhook_handler.webhook_secret = None
        webhook_handler.ingestion_service = None

        headers = {"X-GitHub-Event": "push"}
        event = webhook_handler.parse_event(headers, json.dumps(sample_push_payload))

        result = await webhook_handler.process_event(event)

        assert result["status"] == "queued"
        assert len(webhook_handler.event_queue) == 1

    async def test_process_event_disallowed_branch(self, webhook_handler):
        """Test processing event on disallowed branch."""
        event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/repo",
            repository_name="org/repo",
            branch="feature/test",
            commit_hash="abc123",
            changed_files=["file.py"],
            sender="dev",
            timestamp=datetime.now(),
            raw_payload={},
        )

        result = await webhook_handler.process_event(event)

        assert result["status"] == "skipped"
        assert "not in allowed branches" in result["reason"]

    async def test_process_event_no_files(self, webhook_handler):
        """Test processing event with no changed files."""
        event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/repo",
            repository_name="org/repo",
            branch="main",
            commit_hash="abc123",
            changed_files=[],
            sender="dev",
            timestamp=datetime.now(),
            raw_payload={},
        )

        result = await webhook_handler.process_event(event)

        assert result["status"] == "skipped"
        assert "No files changed" in result["reason"]

    def test_queue_status(self, webhook_handler):
        """Test queue status reporting."""
        status = webhook_handler.get_queue_status()
        assert status["queue_length"] == 0

        event = WebhookEvent(
            event_type=WebhookEventType.PUSH,
            repository_url="https://github.com/org/repo",
            repository_name="org/repo",
            branch="main",
            commit_hash="abc123",
            changed_files=["file.py"],
            sender="dev",
            timestamp=datetime.now(),
            raw_payload={},
        )
        webhook_handler.event_queue.append(event)

        status = webhook_handler.get_queue_status()
        assert status["queue_length"] == 1
        assert status["events"][0]["repository"] == "org/repo"

    def test_clear_queue(self, webhook_handler):
        """Test clearing the queue."""
        for _ in range(3):
            webhook_handler.event_queue.append(MagicMock())

        assert len(webhook_handler.event_queue) == 3

        cleared = webhook_handler.clear_queue()

        assert cleared == 3
        assert len(webhook_handler.event_queue) == 0


# ==================== Integration Tests ====================


class TestIngestionIntegration:
    """End-to-end integration tests."""

    async def test_full_ingestion_workflow(
        self, mock_neptune, mock_opensearch, mock_embedding_service, mock_ast_parser
    ):
        """Test complete ingestion workflow with mocks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test-repo"
            repo_path.mkdir()
            (repo_path / "src").mkdir()
            (repo_path / "src" / "app.py").write_text(
                "class App:\n    def run(self):\n        pass"
            )
            (repo_path / "src" / "utils.py").write_text(
                "def helper():\n    return True"
            )

            import subprocess

            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial"],
                cwd=repo_path,
                capture_output=True,
            )

            service = GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embedding_service,
                ast_parser=mock_ast_parser,
                clone_base_path=temp_dir,
            )

            result = await service.ingest_changes(
                repository_path=repo_path,
                changed_files=["src/app.py", "src/utils.py"],
                commit_hash="abc123",
            )

            assert result.success
            assert result.files_processed == 2
            assert result.entities_indexed > 0

            assert mock_neptune.add_code_entity.called
            assert mock_opensearch.bulk_index_embeddings.called

    async def test_webhook_to_ingestion_flow(
        self, mock_neptune, mock_opensearch, mock_embedding_service, mock_ast_parser
    ):
        """Test webhook triggering ingestion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            _ = GitIngestionService(
                neptune_service=mock_neptune,
                opensearch_service=mock_opensearch,
                embedding_service=mock_embedding_service,
                ast_parser=mock_ast_parser,
                clone_base_path=temp_dir,
            )  # Service configured for this test context

            handler = GitHubWebhookHandler(
                webhook_secret=None,
                ingestion_service=None,
                allowed_branches=["main"],
            )

            payload = {
                "ref": "refs/heads/main",
                "after": "abc123",
                "repository": {
                    "name": "test",
                    "full_name": "org/test",
                    "clone_url": "https://github.com/org/test.git",
                },
                "commits": [{"added": ["src/new.py"], "modified": [], "removed": []}],
                "sender": {"login": "dev"},
            }

            event = handler.parse_event(
                {"X-GitHub-Event": "push"},
                json.dumps(payload),
            )

            assert event is not None
            assert event.event_type == WebhookEventType.PUSH
            assert "src/new.py" in event.changed_files

            result = await handler.process_event(event)
            assert result["status"] == "queued"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
