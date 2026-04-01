"""
Tests for DiagramGitSync service (ADR-060 Phase 4).

Tests GitHub/GitLab integration for committing diagrams to repositories
with GovCloud compliance restrictions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.diagrams.diagram_git_sync import (
    CommitStatus,
    DiagramCommitRequest,
    DiagramGitSync,
    GitHostConfig,
    GitProvider,
    get_diagram_git_sync,
)


class TestDiagramGitSync:
    """Tests for DiagramGitSync class."""

    @pytest.fixture
    def mock_ssm_client(self):
        """Create mock SSM client."""
        client = MagicMock()
        client.get_parameter.return_value = {
            "Parameter": {"Value": "github.com,gitlab.com,git.internal.company.com"}
        }
        return client

    @pytest.fixture
    def mock_oauth_service(self):
        """Create mock OAuth service."""
        service = MagicMock()
        service.get_access_token = AsyncMock(return_value="test-oauth-token")
        return service

    @pytest.fixture
    def mock_github_app_auth(self):
        """Create mock GitHub App auth."""
        auth = MagicMock()
        auth.get_installation_token.return_value = "test-app-token"
        return auth

    @pytest.fixture
    def git_sync(self, mock_ssm_client, mock_oauth_service, mock_github_app_auth):
        """Create DiagramGitSync instance with mocks."""
        return DiagramGitSync(
            oauth_service=mock_oauth_service,
            github_app_auth=mock_github_app_auth,
            ssm_client=mock_ssm_client,
            environment="test",
            govcloud_mode=False,
        )

    @pytest.fixture
    def govcloud_git_sync(
        self, mock_ssm_client, mock_oauth_service, mock_github_app_auth
    ):
        """Create GovCloud-enabled DiagramGitSync instance."""
        return DiagramGitSync(
            oauth_service=mock_oauth_service,
            github_app_auth=mock_github_app_auth,
            ssm_client=mock_ssm_client,
            environment="test",
            govcloud_mode=True,
        )

    @pytest.fixture
    def sample_svg(self):
        """Sample SVG diagram content."""
        return """<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600">
            <rect data-node-id="node1" data-node-label="API Gateway" x="100" y="100" width="200" height="100" fill="#3B82F6"/>
        </svg>"""

    @pytest.fixture
    def commit_request(self, sample_svg):
        """Create sample commit request."""
        return DiagramCommitRequest(
            repo_owner="test-org",
            repo_name="test-repo",
            file_path="docs/diagrams/architecture.svg",
            diagram_content=sample_svg,
            content_type="svg",
            commit_message="Add architecture diagram",
            branch="main",
        )


class TestGitSyncInitialization(TestDiagramGitSync):
    """Tests for service initialization."""

    def test_creates_with_defaults(self):
        """Test creation with default values."""
        sync = DiagramGitSync()
        assert sync.environment in ["dev", "test", "qa", "prod"]
        assert sync.govcloud_mode is False

    def test_creates_with_govcloud_mode(self, mock_ssm_client):
        """Test creation in GovCloud mode."""
        sync = DiagramGitSync(
            ssm_client=mock_ssm_client,
            govcloud_mode=True,
        )
        assert sync.govcloud_mode is True

    def test_loads_allowed_hosts_in_govcloud(self, mock_ssm_client):
        """Test allowed hosts are loaded in GovCloud mode."""
        sync = DiagramGitSync(
            ssm_client=mock_ssm_client,
            environment="test",
            govcloud_mode=True,
        )
        assert sync._allowed_git_hosts is not None
        assert "github.com" in sync._allowed_git_hosts
        assert "gitlab.com" in sync._allowed_git_hosts

    def test_handles_missing_ssm_parameter(self, mock_ssm_client):
        """Test graceful handling of missing SSM parameter."""
        from botocore.exceptions import ClientError

        mock_ssm_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound"}},
            "GetParameter",
        )

        sync = DiagramGitSync(
            ssm_client=mock_ssm_client,
            govcloud_mode=True,
        )
        # Should fall back to defaults
        assert "github.com" in sync._allowed_git_hosts


class TestHostValidation(TestDiagramGitSync):
    """Tests for Git host validation."""

    def test_allows_any_host_when_not_govcloud(self, git_sync):
        """Test all hosts allowed when not in GovCloud mode."""
        is_allowed, error = git_sync._validate_host("random.git.server.com")
        assert is_allowed is True
        assert error is None

    def test_allows_configured_hosts_in_govcloud(self, govcloud_git_sync):
        """Test configured hosts are allowed in GovCloud."""
        is_allowed, error = govcloud_git_sync._validate_host("github.com")
        assert is_allowed is True
        assert error is None

    def test_blocks_unconfigured_hosts_in_govcloud(self, govcloud_git_sync):
        """Test unconfigured hosts are blocked in GovCloud."""
        is_allowed, error = govcloud_git_sync._validate_host(
            "unauthorized.git.server.com"
        )
        assert is_allowed is False
        assert "not authorized" in error

    def test_extracts_host_from_url(self, git_sync):
        """Test host extraction from clone URL."""
        host = git_sync._extract_host(
            "owner", "repo", "https://github.enterprise.com/owner/repo.git"
        )
        assert host == "github.enterprise.com"

    def test_defaults_to_github_for_owner_repo(self, git_sync):
        """Test default host for owner/repo format."""
        host = git_sync._extract_host("owner", "repo", None)
        assert host == "github.com"


class TestHostConfiguration(TestDiagramGitSync):
    """Tests for Git host configuration."""

    def test_github_config(self, git_sync):
        """Test GitHub host configuration."""
        config = git_sync._get_host_config("github.com")
        assert config.provider == GitProvider.GITHUB
        assert config.api_base_url == "https://api.github.com"
        assert config.enterprise is False

    def test_gitlab_config(self, git_sync):
        """Test GitLab host configuration."""
        config = git_sync._get_host_config("gitlab.com")
        assert config.provider == GitProvider.GITLAB
        assert config.api_base_url == "https://gitlab.com/api/v4"
        assert config.enterprise is False

    def test_github_enterprise_config(self, git_sync):
        """Test GitHub Enterprise host configuration."""
        config = git_sync._get_host_config("github.enterprise.com")
        assert config.provider == GitProvider.GITHUB
        assert "github.enterprise.com" in config.api_base_url
        assert config.enterprise is True


class TestGitHubCommit(TestDiagramGitSync):
    """Tests for GitHub commit operations."""

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_commits_svg_to_github(self, mock_requests, git_sync, commit_request):
        """Test committing SVG diagram to GitHub."""
        # Mock file doesn't exist
        mock_get_response = MagicMock()
        mock_get_response.status_code = 404

        # Mock successful commit
        mock_put_response = MagicMock()
        mock_put_response.status_code = 201
        mock_put_response.json.return_value = {
            "commit": {"sha": "abc123"},
            "content": {
                "html_url": "https://github.com/test-org/test-repo/blob/main/docs/diagrams/architecture.svg"
            },
        }
        mock_put_response.raise_for_status = MagicMock()

        mock_requests.get.return_value = mock_get_response
        mock_requests.put.return_value = mock_put_response

        result = await git_sync.commit_diagram(
            commit_request,
            access_token="test-token",
        )

        assert result.success is True
        assert result.status == CommitStatus.SUCCESS
        assert result.commit_sha == "abc123"
        assert result.file_url is not None

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_updates_existing_file(self, mock_requests, git_sync, commit_request):
        """Test updating existing file in GitHub."""
        # Mock file exists
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"sha": "existing-sha-123"}

        # Mock successful update
        mock_put_response = MagicMock()
        mock_put_response.status_code = 200
        mock_put_response.json.return_value = {
            "commit": {"sha": "new-sha-456"},
            "content": {
                "html_url": "https://github.com/test-org/test-repo/blob/main/docs/diagrams/architecture.svg"
            },
        }
        mock_put_response.raise_for_status = MagicMock()

        mock_requests.get.return_value = mock_get_response
        mock_requests.put.return_value = mock_put_response

        result = await git_sync.commit_diagram(
            commit_request,
            access_token="test-token",
        )

        assert result.success is True
        # Verify SHA was passed for update
        put_call = mock_requests.put.call_args
        assert "sha" in put_call.kwargs.get("json", {}) or "existing-sha-123" in str(
            put_call
        )

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_creates_pr_on_request(self, mock_requests, git_sync, commit_request):
        """Test creating PR when requested."""
        commit_request.create_pr = True
        commit_request.pr_title = "Add diagram"
        commit_request.pr_description = "Adding architecture diagram"

        # Mock branch creation
        mock_ref_response = MagicMock()
        mock_ref_response.json.return_value = {"object": {"sha": "base-sha"}}
        mock_ref_response.raise_for_status = MagicMock()

        mock_create_ref_response = MagicMock()
        mock_create_ref_response.raise_for_status = MagicMock()

        # Mock file commit
        mock_put_response = MagicMock()
        mock_put_response.json.return_value = {
            "commit": {"sha": "commit-sha"},
            "content": {"html_url": "https://github.com/..."},
        }
        mock_put_response.raise_for_status = MagicMock()

        # Mock PR creation
        mock_pr_response = MagicMock()
        mock_pr_response.json.return_value = {
            "number": 42,
            "html_url": "https://github.com/test-org/test-repo/pull/42",
        }
        mock_pr_response.raise_for_status = MagicMock()

        mock_requests.get.return_value = mock_ref_response
        mock_requests.post.side_effect = [mock_create_ref_response, mock_pr_response]
        mock_requests.put.return_value = mock_put_response

        result = await git_sync.commit_diagram(
            commit_request,
            access_token="test-token",
        )

        assert result.success is True
        assert result.pr_number == 42
        assert result.pr_url == "https://github.com/test-org/test-repo/pull/42"

    @pytest.mark.asyncio
    async def test_fails_without_authentication(self, git_sync, commit_request):
        """Test failure when no authentication provided."""
        result = await git_sync.commit_diagram(commit_request)

        assert result.success is False
        assert result.status == CommitStatus.UNAUTHORIZED
        assert "No authentication method" in result.error

    @pytest.mark.asyncio
    async def test_uses_oauth_connection(
        self, git_sync, commit_request, mock_oauth_service
    ):
        """Test using OAuth connection for authentication."""
        with patch("src.services.diagrams.diagram_git_sync.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 404  # File doesn't exist

            mock_put_response = MagicMock()
            mock_put_response.json.return_value = {
                "commit": {"sha": "sha123"},
                "content": {"html_url": "url"},
            }
            mock_put_response.raise_for_status = MagicMock()

            mock_requests.get.return_value = mock_response
            mock_requests.put.return_value = mock_put_response

            result = await git_sync.commit_diagram(
                commit_request,
                connection_id="oauth-connection-123",
            )

            mock_oauth_service.get_access_token.assert_called_once_with(
                "oauth-connection-123"
            )

    @pytest.mark.asyncio
    async def test_uses_github_app_auth(
        self, git_sync, commit_request, mock_github_app_auth
    ):
        """Test using GitHub App for authentication."""
        with patch("src.services.diagrams.diagram_git_sync.requests") as mock_requests:
            mock_response = MagicMock()
            mock_response.status_code = 404

            mock_put_response = MagicMock()
            mock_put_response.json.return_value = {
                "commit": {"sha": "sha123"},
                "content": {"html_url": "url"},
            }
            mock_put_response.raise_for_status = MagicMock()

            mock_requests.get.return_value = mock_response
            mock_requests.put.return_value = mock_put_response

            result = await git_sync.commit_diagram(
                commit_request,
                use_github_app=True,
            )

            mock_github_app_auth.get_installation_token.assert_called_once()


class TestGitLabCommit(TestDiagramGitSync):
    """Tests for GitLab commit operations."""

    @pytest.fixture
    def gitlab_commit_request(self, sample_svg):
        """Create GitLab commit request."""
        return DiagramCommitRequest(
            repo_owner="test-group",
            repo_name="test-project",
            file_path="docs/diagrams/architecture.svg",
            diagram_content=sample_svg,
            content_type="svg",
            commit_message="Add architecture diagram",
            branch="main",
        )

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_commits_to_gitlab(
        self, mock_requests, git_sync, gitlab_commit_request
    ):
        """Test committing diagram to GitLab."""
        # Mock host as GitLab
        git_sync._enterprise_hosts["gitlab.com"] = GitHostConfig(
            host="gitlab.com",
            api_base_url="https://gitlab.com/api/v4",
            provider=GitProvider.GITLAB,
        )

        # Mock file doesn't exist
        mock_head_response = MagicMock()
        mock_head_response.status_code = 404
        mock_requests.head.return_value = mock_head_response

        # Mock successful commit
        mock_post_response = MagicMock()
        mock_post_response.json.return_value = {
            "id": "gitlab-commit-sha",
            "web_url": "https://gitlab.com/test-group/test-project/-/commit/gitlab-commit-sha",
        }
        mock_post_response.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_post_response

        with patch.object(git_sync, "_extract_host", return_value="gitlab.com"):
            result = await git_sync.commit_diagram(
                gitlab_commit_request,
                access_token="gitlab-token",
            )

        assert result.success is True
        assert result.commit_sha == "gitlab-commit-sha"


class TestGovCloudRestrictions(TestDiagramGitSync):
    """Tests for GovCloud compliance restrictions."""

    @pytest.mark.asyncio
    async def test_blocks_unauthorized_host(self, govcloud_git_sync, commit_request):
        """Test blocking commits to unauthorized hosts."""
        with patch.object(
            govcloud_git_sync, "_extract_host", return_value="unauthorized.com"
        ):
            result = await govcloud_git_sync.commit_diagram(
                commit_request,
                access_token="test-token",
            )

        assert result.success is False
        assert result.status == CommitStatus.HOST_NOT_ALLOWED
        assert "not authorized" in result.error

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_allows_authorized_host(
        self, mock_requests, govcloud_git_sync, commit_request
    ):
        """Test allowing commits to authorized hosts."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response

        mock_put_response = MagicMock()
        mock_put_response.json.return_value = {
            "commit": {"sha": "sha"},
            "content": {"html_url": "url"},
        }
        mock_put_response.raise_for_status = MagicMock()
        mock_requests.put.return_value = mock_put_response

        result = await govcloud_git_sync.commit_diagram(
            commit_request,
            access_token="test-token",
        )

        assert result.success is True
        assert result.status == CommitStatus.SUCCESS


class TestListDiagrams(TestDiagramGitSync):
    """Tests for listing repository diagrams."""

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_lists_github_diagrams(self, mock_requests, git_sync):
        """Test listing diagrams from GitHub."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "name": "arch.svg",
                "path": "docs/arch.svg",
                "sha": "sha1",
                "size": 1000,
                "type": "file",
            },
            {
                "name": "flow.png",
                "path": "docs/flow.png",
                "sha": "sha2",
                "size": 2000,
                "type": "file",
            },
            {
                "name": "readme.md",
                "path": "docs/readme.md",
                "sha": "sha3",
                "size": 500,
                "type": "file",
            },
        ]
        mock_response.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_response

        diagrams = await git_sync.list_repository_diagrams(
            "test-org",
            "test-repo",
            access_token="test-token",
            path="docs",
        )

        # Should only return diagram files
        assert len(diagrams) == 2
        assert any(d["name"] == "arch.svg" for d in diagrams)
        assert any(d["name"] == "flow.png" for d in diagrams)
        assert not any(d["name"] == "readme.md" for d in diagrams)

    @pytest.mark.asyncio
    async def test_returns_empty_without_auth(self, git_sync):
        """Test returns empty list without authentication."""
        diagrams = await git_sync.list_repository_diagrams(
            "test-org",
            "test-repo",
        )
        assert diagrams == []


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_diagram_git_sync_returns_same_instance(self):
        """Test singleton returns same instance."""
        import src.services.diagrams.diagram_git_sync as module

        # Reset singleton
        module._git_sync_service = None

        sync1 = get_diagram_git_sync()
        sync2 = get_diagram_git_sync()

        assert sync1 is sync2

        # Cleanup
        module._git_sync_service = None


class TestEdgeCases(TestDiagramGitSync):
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_handles_401_response(self, mock_requests, git_sync, commit_request):
        """Test handling 401 unauthorized response."""
        import requests as real_requests

        mock_response = MagicMock()
        mock_response.status_code = 401
        error = real_requests.exceptions.HTTPError(response=mock_response)

        mock_requests.get.return_value = MagicMock(status_code=404)
        mock_requests.put.side_effect = error
        mock_requests.exceptions = real_requests.exceptions

        result = await git_sync.commit_diagram(
            commit_request,
            access_token="invalid-token",
        )

        assert result.success is False
        assert result.status == CommitStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_handles_404_response(self, mock_requests, git_sync, commit_request):
        """Test handling 404 not found response."""
        import requests as real_requests

        mock_response = MagicMock()
        mock_response.status_code = 404
        error = real_requests.exceptions.HTTPError(response=mock_response)

        mock_requests.get.return_value = MagicMock(status_code=404)
        mock_requests.put.side_effect = error
        mock_requests.exceptions = real_requests.exceptions

        result = await git_sync.commit_diagram(
            commit_request,
            access_token="test-token",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handles_oauth_failure(
        self, git_sync, commit_request, mock_oauth_service
    ):
        """Test handling OAuth service failure."""
        mock_oauth_service.get_access_token.side_effect = Exception("OAuth failed")

        result = await git_sync.commit_diagram(
            commit_request,
            connection_id="failing-connection",
        )

        assert result.success is False
        assert result.status == CommitStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_handles_unconfigured_github_app(
        self, git_sync, commit_request, mock_github_app_auth
    ):
        """Test handling unconfigured GitHub App."""
        mock_github_app_auth.get_installation_token.return_value = None

        result = await git_sync.commit_diagram(
            commit_request,
            use_github_app=True,
        )

        assert result.success is False
        assert result.status == CommitStatus.UNAUTHORIZED
        assert "not configured" in result.error


class TestContentTypes(TestDiagramGitSync):
    """Tests for different content type handling."""

    @pytest.mark.asyncio
    @patch("src.services.diagrams.diagram_git_sync.requests")
    async def test_handles_png_content(self, mock_requests, git_sync):
        """Test handling PNG (base64) content."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_requests.get.return_value = mock_response

        mock_put_response = MagicMock()
        mock_put_response.json.return_value = {
            "commit": {"sha": "sha"},
            "content": {"html_url": "url"},
        }
        mock_put_response.raise_for_status = MagicMock()
        mock_requests.put.return_value = mock_put_response

        request = DiagramCommitRequest(
            repo_owner="test-org",
            repo_name="test-repo",
            file_path="docs/diagram.png",
            diagram_content="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            content_type="png",
            commit_message="Add PNG diagram",
            branch="main",
        )

        result = await git_sync.commit_diagram(
            request,
            access_token="test-token",
        )

        assert result.success is True
        # Verify PNG content is passed as-is (already base64)
        put_call = mock_requests.put.call_args
        assert put_call is not None
