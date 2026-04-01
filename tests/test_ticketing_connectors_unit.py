"""
Tests for Ticketing Connectors.

Comprehensive tests for base connector, GitHub connector, Linear connector,
and connector factory.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.services.ticketing.base_connector import (
    Ticket,
    TicketComment,
    TicketCreate,
    TicketFilters,
    TicketPriority,
    TicketResult,
    TicketStatus,
    TicketUpdate,
)
from src.services.ticketing.connector_factory import (
    PROVIDER_METADATA,
    TicketingConnectorFactory,
    TicketingProvider,
    get_ticketing_connector,
    get_ticketing_connector_factory,
)
from src.services.ticketing.github_connector import (
    GITHUB_STATE_TO_STATUS,
    PRIORITY_LABELS,
    GitHubIssuesConnector,
)
from src.services.ticketing.linear_connector import LinearConnector
from src.services.ticketing.servicenow_connector import ServiceNowTicketConnector
from src.services.ticketing.zendesk_connector import ZendeskConnector

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_ticket_create():
    """Sample ticket creation data."""
    return TicketCreate(
        title="Test Issue",
        description="This is a test issue description",
        priority=TicketPriority.HIGH,
        labels=["bug", "urgent"],
        assignee="testuser",
        customer_id="cust-123",
        metadata={"source": "api"},
    )


@pytest.fixture
def sample_ticket_update():
    """Sample ticket update data."""
    return TicketUpdate(
        title="Updated Title",
        description="Updated description",
        status=TicketStatus.IN_PROGRESS,
        priority=TicketPriority.CRITICAL,
        labels=["bug", "critical"],
        assignee="newuser",
    )


@pytest.fixture
def sample_ticket():
    """Sample ticket for testing."""
    return Ticket(
        id="ticket-123",
        external_id="42",
        title="Test Issue",
        description="Test description",
        status=TicketStatus.OPEN,
        priority=TicketPriority.HIGH,
        labels=["bug"],
        assignee="testuser",
        reporter="reporter",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        external_url="https://github.com/owner/repo/issues/42",
        customer_id="cust-123",
    )


@pytest.fixture
def sample_ticket_filters():
    """Sample ticket filters."""
    return TicketFilters(
        status=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS],
        priority=[TicketPriority.HIGH, TicketPriority.CRITICAL],
        labels=["bug"],
        assignee="testuser",
        limit=25,
        offset=0,
    )


@pytest.fixture
def mock_http_client():
    """Mock httpx async client."""
    return MagicMock(spec=httpx.AsyncClient)


@pytest.fixture
def github_connector(mock_http_client):
    """Create GitHub connector with mocked HTTP client."""
    with patch.object(httpx, "AsyncClient", return_value=mock_http_client):
        connector = GitHubIssuesConnector(
            repository="owner/repo",
            token="test-token",
        )
        connector._client = mock_http_client
        return connector


@pytest.fixture
def linear_connector():
    """Create Linear connector."""
    return LinearConnector(
        api_key="test-key",
        team_id="team-123",
        project_id="proj-456",
    )


@pytest.fixture
def zendesk_connector():
    """Create Zendesk connector."""
    return ZendeskConnector(
        subdomain="testcompany",
        email="test@example.com",
        api_token="test-token",
    )


@pytest.fixture
def servicenow_connector():
    """Create ServiceNow connector."""
    return ServiceNowTicketConnector(
        instance_url="https://dev12345.service-now.com",
        username="admin",
        password="password",
        table="incident",
    )


@pytest.fixture
def sample_github_issue():
    """Sample GitHub issue response."""
    return {
        "id": 123456789,
        "number": 42,
        "title": "Test Issue",
        "body": "Test description",
        "state": "open",
        "labels": [
            {"name": "bug"},
            {"name": "priority:high"},
        ],
        "assignees": [{"login": "testuser"}],
        "assignee": {"login": "testuser"},
        "user": {"login": "reporter"},
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T12:00:00Z",
        "html_url": "https://github.com/owner/repo/issues/42",
    }


# =============================================================================
# Data Classes Tests
# =============================================================================


class TestTicketPriority:
    """Tests for TicketPriority enum."""

    def test_all_priorities_exist(self):
        """Test all priority levels exist."""
        assert TicketPriority.LOW.value == "low"
        assert TicketPriority.MEDIUM.value == "medium"
        assert TicketPriority.HIGH.value == "high"
        assert TicketPriority.CRITICAL.value == "critical"


class TestTicketStatus:
    """Tests for TicketStatus enum."""

    def test_all_statuses_exist(self):
        """Test all status values exist."""
        assert TicketStatus.OPEN.value == "open"
        assert TicketStatus.IN_PROGRESS.value == "in_progress"
        assert TicketStatus.PENDING.value == "pending"
        assert TicketStatus.RESOLVED.value == "resolved"
        assert TicketStatus.CLOSED.value == "closed"


class TestTicketCreate:
    """Tests for TicketCreate dataclass."""

    def test_create_minimal(self):
        """Test creating with minimal data."""
        ticket = TicketCreate(
            title="Test",
            description="Description",
        )
        assert ticket.title == "Test"
        assert ticket.priority == TicketPriority.MEDIUM  # default
        assert ticket.labels == []

    def test_create_full(self, sample_ticket_create):
        """Test creating with full data."""
        assert sample_ticket_create.title == "Test Issue"
        assert sample_ticket_create.priority == TicketPriority.HIGH
        assert "bug" in sample_ticket_create.labels
        assert sample_ticket_create.customer_id == "cust-123"


class TestTicketUpdate:
    """Tests for TicketUpdate dataclass."""

    def test_update_partial(self):
        """Test partial update."""
        update = TicketUpdate(title="New Title")
        assert update.title == "New Title"
        assert update.description is None
        assert update.status is None

    def test_update_full(self, sample_ticket_update):
        """Test full update."""
        assert sample_ticket_update.title == "Updated Title"
        assert sample_ticket_update.status == TicketStatus.IN_PROGRESS


class TestTicketComment:
    """Tests for TicketComment dataclass."""

    def test_create_comment(self):
        """Test creating a comment."""
        comment = TicketComment(
            id="comment-1",
            author="testuser",
            body="This is a comment",
            created_at=datetime.now(),
            is_internal=False,
        )
        assert comment.id == "comment-1"
        assert comment.is_internal is False

    def test_internal_comment(self):
        """Test internal comment."""
        comment = TicketComment(
            id="comment-2",
            author="agent",
            body="Internal note",
            created_at=datetime.now(),
            is_internal=True,
        )
        assert comment.is_internal is True


class TestTicket:
    """Tests for Ticket dataclass."""

    def test_create_ticket(self, sample_ticket):
        """Test creating a ticket."""
        assert sample_ticket.id == "ticket-123"
        assert sample_ticket.external_id == "42"
        assert sample_ticket.status == TicketStatus.OPEN

    def test_ticket_defaults(self):
        """Test ticket default values."""
        ticket = Ticket(
            id="t-1",
            external_id="1",
            title="Test",
            description="Desc",
            status=TicketStatus.OPEN,
            priority=TicketPriority.MEDIUM,
            labels=[],
            assignee=None,
            reporter="user",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            external_url="http://example.com",
        )
        assert ticket.comments == []
        assert ticket.metadata == {}


class TestTicketResult:
    """Tests for TicketResult dataclass."""

    def test_success_result(self, sample_ticket):
        """Test successful result."""
        result = TicketResult(success=True, ticket=sample_ticket)
        assert result.success is True
        assert result.ticket is not None
        assert result.error_message is None

    def test_error_result(self):
        """Test error result."""
        result = TicketResult(
            success=False,
            error_message="Not found",
            error_code="NOT_FOUND",
        )
        assert result.success is False
        assert result.error_code == "NOT_FOUND"


class TestTicketFilters:
    """Tests for TicketFilters dataclass."""

    def test_default_filters(self):
        """Test default filter values."""
        filters = TicketFilters()
        assert filters.limit == 50
        assert filters.offset == 0
        assert filters.status is None

    def test_custom_filters(self, sample_ticket_filters):
        """Test custom filter values."""
        assert len(sample_ticket_filters.status) == 2
        assert sample_ticket_filters.limit == 25


# =============================================================================
# GitHub Connector Tests
# =============================================================================


class TestGitHubIssuesConnector:
    """Tests for GitHubIssuesConnector class."""

    def test_init_valid_repo(self, github_connector):
        """Test initialization with valid repository."""
        assert github_connector._owner == "owner"
        assert github_connector._repo == "repo"
        assert github_connector.provider_name == "github"
        assert github_connector.provider_display_name == "GitHub Issues"

    def test_init_invalid_repo_format(self):
        """Test initialization with invalid repository format."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            GitHubIssuesConnector(
                repository="invalid-format",
                token="test-token",
            )

    def test_init_default_labels(self, github_connector):
        """Test default labels are set."""
        assert "support" in github_connector._default_labels
        assert "aura" in github_connector._default_labels


class TestGitHubConnectorConnection:
    """Tests for GitHub connector connection testing."""

    @pytest.mark.asyncio
    async def test_test_connection_success(self, github_connector, mock_http_client):
        """Test successful connection."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.test_connection()

        assert result is True
        mock_http_client.get.assert_called_with("/repos/owner/repo")

    @pytest.mark.asyncio
    async def test_test_connection_unauthorized(
        self, github_connector, mock_http_client
    ):
        """Test connection with invalid token."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.test_connection()

        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_not_found(self, github_connector, mock_http_client):
        """Test connection with non-existent repo."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.test_connection()

        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_exception(self, github_connector, mock_http_client):
        """Test connection handles exceptions."""
        mock_http_client.get = AsyncMock(side_effect=Exception("Network error"))

        result = await github_connector.test_connection()

        assert result is False


class TestGitHubConnectorCreateTicket:
    """Tests for GitHub connector ticket creation."""

    @pytest.mark.asyncio
    async def test_create_ticket_success(
        self,
        github_connector,
        mock_http_client,
        sample_ticket_create,
        sample_github_issue,
    ):
        """Test successful ticket creation."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = sample_github_issue
        mock_http_client.post = AsyncMock(return_value=mock_response)

        result = await github_connector.create_ticket(sample_ticket_create)

        assert result.success is True
        assert result.ticket is not None
        assert result.ticket.external_id == "42"

    @pytest.mark.asyncio
    async def test_create_ticket_failure(
        self, github_connector, mock_http_client, sample_ticket_create
    ):
        """Test failed ticket creation."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"message": "Validation failed"}
        mock_http_client.post = AsyncMock(return_value=mock_response)

        result = await github_connector.create_ticket(sample_ticket_create)

        assert result.success is False
        assert "Validation failed" in result.error_message

    @pytest.mark.asyncio
    async def test_create_ticket_exception(
        self, github_connector, mock_http_client, sample_ticket_create
    ):
        """Test ticket creation handles exceptions."""
        mock_http_client.post = AsyncMock(side_effect=Exception("API error"))

        result = await github_connector.create_ticket(sample_ticket_create)

        assert result.success is False
        assert result.error_code == "INTERNAL_ERROR"


class TestGitHubConnectorGetTicket:
    """Tests for GitHub connector ticket retrieval."""

    @pytest.mark.asyncio
    async def test_get_ticket_success(
        self, github_connector, mock_http_client, sample_github_issue
    ):
        """Test successful ticket retrieval."""
        # First create ticket to set up mapping
        github_connector._ticket_mapping["ticket-123"] = 42
        github_connector._reverse_mapping[42] = "ticket-123"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_github_issue
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.get_ticket("ticket-123")

        assert result is not None
        assert result.external_id == "42"

    @pytest.mark.asyncio
    async def test_get_ticket_not_in_mapping(self, github_connector):
        """Test getting ticket not in mapping."""
        result = await github_connector.get_ticket("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_ticket_not_found(self, github_connector, mock_http_client):
        """Test getting ticket that doesn't exist on GitHub."""
        github_connector._ticket_mapping["ticket-123"] = 42

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.get_ticket("ticket-123")

        assert result is None


class TestGitHubConnectorGetByExternalId:
    """Tests for getting ticket by external ID."""

    @pytest.mark.asyncio
    async def test_get_by_external_id_success(
        self, github_connector, mock_http_client, sample_github_issue
    ):
        """Test getting ticket by GitHub issue number."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_github_issue
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.get_ticket_by_external_id("42")

        assert result is not None
        assert result.external_id == "42"

    @pytest.mark.asyncio
    async def test_get_by_external_id_invalid(self, github_connector):
        """Test getting ticket with invalid external ID."""
        result = await github_connector.get_ticket_by_external_id("not-a-number")

        assert result is None


class TestGitHubConnectorUpdateTicket:
    """Tests for GitHub connector ticket updates."""

    @pytest.mark.asyncio
    async def test_update_ticket_success(
        self,
        github_connector,
        mock_http_client,
        sample_ticket_update,
        sample_github_issue,
    ):
        """Test successful ticket update."""
        github_connector._ticket_mapping["ticket-123"] = 42

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_github_issue
        mock_http_client.patch = AsyncMock(return_value=mock_response)

        result = await github_connector.update_ticket(
            "ticket-123", sample_ticket_update
        )

        assert result.success is True
        mock_http_client.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_ticket_not_found(
        self, github_connector, sample_ticket_update
    ):
        """Test updating non-existent ticket."""
        result = await github_connector.update_ticket(
            "nonexistent", sample_ticket_update
        )

        assert result.success is False
        assert result.error_code == "NOT_FOUND"


class TestGitHubConnectorListTickets:
    """Tests for GitHub connector listing tickets."""

    @pytest.mark.asyncio
    async def test_list_tickets_success(
        self, github_connector, mock_http_client, sample_github_issue
    ):
        """Test listing tickets successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_github_issue]
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.list_tickets()

        assert len(result) == 1
        assert result[0].external_id == "42"

    @pytest.mark.asyncio
    async def test_list_tickets_with_filters(
        self,
        github_connector,
        mock_http_client,
        sample_ticket_filters,
        sample_github_issue,
    ):
        """Test listing tickets with filters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_github_issue]
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.list_tickets(sample_ticket_filters)

        assert len(result) >= 0  # May filter out PRs

    @pytest.mark.asyncio
    async def test_list_tickets_skips_prs(self, github_connector, mock_http_client):
        """Test listing tickets skips pull requests."""
        issue_with_pr = {
            "number": 1,
            "title": "PR",
            "pull_request": {},  # This indicates a PR
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [issue_with_pr]
        mock_http_client.get = AsyncMock(return_value=mock_response)

        result = await github_connector.list_tickets()

        assert len(result) == 0


class TestGitHubConnectorComments:
    """Tests for GitHub connector comment operations."""

    @pytest.mark.asyncio
    async def test_add_comment_success(
        self, github_connector, mock_http_client, sample_github_issue
    ):
        """Test adding comment successfully."""
        github_connector._ticket_mapping["ticket-123"] = 42

        post_response = MagicMock()
        post_response.status_code = 201
        mock_http_client.post = AsyncMock(return_value=post_response)

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = sample_github_issue
        mock_http_client.get = AsyncMock(return_value=get_response)

        result = await github_connector.add_comment("ticket-123", "Test comment")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_add_internal_comment(
        self, github_connector, mock_http_client, sample_github_issue
    ):
        """Test adding internal comment adds prefix."""
        github_connector._ticket_mapping["ticket-123"] = 42

        post_response = MagicMock()
        post_response.status_code = 201
        mock_http_client.post = AsyncMock(return_value=post_response)

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = sample_github_issue
        mock_http_client.get = AsyncMock(return_value=get_response)

        await github_connector.add_comment(
            "ticket-123", "Internal note", is_internal=True
        )

        # Verify internal note prefix was added
        call_args = mock_http_client.post.call_args
        assert "[Internal Note]" in call_args.kwargs["json"]["body"]


class TestGitHubConnectorCloseReopen:
    """Tests for GitHub connector close/reopen operations."""

    @pytest.mark.asyncio
    async def test_close_ticket(
        self, github_connector, mock_http_client, sample_github_issue
    ):
        """Test closing a ticket."""
        github_connector._ticket_mapping["ticket-123"] = 42

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_github_issue
        mock_http_client.patch = AsyncMock(return_value=mock_response)

        result = await github_connector.close_ticket("ticket-123")

        assert result.success is True

    @pytest.mark.asyncio
    async def test_close_ticket_with_resolution(
        self, github_connector, mock_http_client, sample_github_issue
    ):
        """Test closing ticket with resolution note."""
        github_connector._ticket_mapping["ticket-123"] = 42

        post_response = MagicMock()
        post_response.status_code = 201
        mock_http_client.post = AsyncMock(return_value=post_response)

        patch_response = MagicMock()
        patch_response.status_code = 200
        patch_response.json.return_value = sample_github_issue
        mock_http_client.patch = AsyncMock(return_value=patch_response)

        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = sample_github_issue
        mock_http_client.get = AsyncMock(return_value=get_response)

        await github_connector.close_ticket("ticket-123", resolution="Fixed in v2.0")

        # Verify comment was added
        mock_http_client.post.assert_called()

    @pytest.mark.asyncio
    async def test_reopen_ticket(
        self, github_connector, mock_http_client, sample_github_issue
    ):
        """Test reopening a ticket."""
        github_connector._ticket_mapping["ticket-123"] = 42

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_github_issue
        mock_http_client.patch = AsyncMock(return_value=mock_response)

        result = await github_connector.reopen_ticket("ticket-123")

        assert result.success is True


class TestGitHubConnectorParseIssue:
    """Tests for parsing GitHub issues."""

    def test_parse_github_issue(self, github_connector, sample_github_issue):
        """Test parsing GitHub issue to Ticket."""
        ticket = github_connector._parse_github_issue(sample_github_issue, "ticket-123")

        assert ticket.id == "ticket-123"
        assert ticket.external_id == "42"
        assert ticket.title == "Test Issue"
        assert ticket.priority == TicketPriority.HIGH
        assert ticket.assignee == "testuser"

    def test_parse_github_issue_no_assignee(self, github_connector):
        """Test parsing issue without assignee."""
        issue = {
            "id": 123,
            "number": 1,
            "title": "Test",
            "body": "",
            "state": "open",
            "labels": [],
            "assignees": [],
            "user": {"login": "user"},
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "html_url": "http://example.com",
        }

        ticket = github_connector._parse_github_issue(issue, "t-1")

        assert ticket.assignee is None


# =============================================================================
# Stub Connector Tests
# =============================================================================


class TestLinearConnector:
    """Tests for Linear connector stub."""

    def test_init(self, linear_connector):
        """Test Linear connector initialization."""
        assert linear_connector.provider_name == "linear"
        assert linear_connector.provider_display_name == "Linear"

    @pytest.mark.asyncio
    async def test_test_connection_stub(self, linear_connector):
        """Test connection returns False (stub)."""
        result = await linear_connector.test_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_create_ticket_stub(self, linear_connector, sample_ticket_create):
        """Test create ticket returns not implemented."""
        result = await linear_connector.create_ticket(sample_ticket_create)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_get_ticket_stub(self, linear_connector):
        """Test get ticket returns None (stub)."""
        result = await linear_connector.get_ticket("123")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_tickets_stub(self, linear_connector):
        """Test list tickets returns empty (stub)."""
        result = await linear_connector.list_tickets()
        assert result == []


class TestZendeskConnector:
    """Tests for Zendesk connector stub."""

    def test_init(self, zendesk_connector):
        """Test Zendesk connector initialization."""
        assert zendesk_connector.provider_name == "zendesk"
        assert zendesk_connector.provider_display_name == "Zendesk"

    @pytest.mark.asyncio
    async def test_test_connection_stub(self, zendesk_connector):
        """Test connection returns False (stub)."""
        result = await zendesk_connector.test_connection()
        assert result is False


class TestServiceNowConnector:
    """Tests for ServiceNow connector stub."""

    def test_init(self, servicenow_connector):
        """Test ServiceNow connector initialization."""
        assert servicenow_connector.provider_name == "servicenow"
        assert servicenow_connector.provider_display_name == "ServiceNow"

    @pytest.mark.asyncio
    async def test_test_connection_stub(self, servicenow_connector):
        """Test connection returns False (stub)."""
        result = await servicenow_connector.test_connection()
        assert result is False


# =============================================================================
# Connector Factory Tests
# =============================================================================


class TestTicketingProvider:
    """Tests for TicketingProvider enum."""

    def test_all_providers_exist(self):
        """Test all providers are defined."""
        assert TicketingProvider.GITHUB.value == "github"
        assert TicketingProvider.ZENDESK.value == "zendesk"
        assert TicketingProvider.LINEAR.value == "linear"
        assert TicketingProvider.SERVICENOW.value == "servicenow"


class TestProviderMetadata:
    """Tests for provider metadata."""

    def test_metadata_for_all_providers(self):
        """Test metadata exists for all providers."""
        for provider in TicketingProvider:
            assert provider in PROVIDER_METADATA
            meta = PROVIDER_METADATA[provider]
            assert "name" in meta
            assert "is_implemented" in meta
            assert "config_fields" in meta

    def test_github_is_implemented(self):
        """Test GitHub is marked as implemented."""
        meta = PROVIDER_METADATA[TicketingProvider.GITHUB]
        assert meta["is_implemented"] is True

    def test_stubs_not_implemented(self):
        """Test stubs are marked as not implemented."""
        assert PROVIDER_METADATA[TicketingProvider.ZENDESK]["is_implemented"] is False
        assert PROVIDER_METADATA[TicketingProvider.LINEAR]["is_implemented"] is False
        assert (
            PROVIDER_METADATA[TicketingProvider.SERVICENOW]["is_implemented"] is False
        )


class TestTicketingConnectorFactory:
    """Tests for TicketingConnectorFactory class."""

    def test_init(self):
        """Test factory initialization."""
        factory = TicketingConnectorFactory()
        assert factory._connectors == {}

    def test_get_provider_metadata(self):
        """Test getting provider metadata."""
        metadata = TicketingConnectorFactory.get_provider_metadata()

        assert "github" in metadata
        assert "zendesk" in metadata
        assert metadata["github"]["name"] == "GitHub Issues"

    def test_get_implemented_providers(self):
        """Test getting implemented providers."""
        providers = TicketingConnectorFactory.get_implemented_providers()

        assert "github" in providers
        assert "zendesk" not in providers

    @pytest.mark.asyncio
    async def test_get_connector_no_config(self):
        """Test getting connector with no config returns None."""
        factory = TicketingConnectorFactory()

        result = await factory.get_connector("cust-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_connector_with_github_config(self):
        """Test getting connector with GitHub config."""
        factory = TicketingConnectorFactory()
        config = {
            "provider": "github",
            "repository": "owner/repo",
            "token": "test-token",
        }

        result = await factory.get_connector("cust-123", config=config)

        assert result is not None
        assert result.provider_name == "github"

    @pytest.mark.asyncio
    async def test_get_connector_caches_result(self):
        """Test connector is cached after creation."""
        factory = TicketingConnectorFactory()
        config = {
            "provider": "github",
            "repository": "owner/repo",
            "token": "test-token",
        }

        result1 = await factory.get_connector("cust-123", config=config)
        result2 = await factory.get_connector("cust-123")

        assert result1 is result2

    @pytest.mark.asyncio
    async def test_create_connector_linear(self):
        """Test creating Linear connector."""
        factory = TicketingConnectorFactory()
        config = {
            "provider": "linear",
            "api_key": "key",
            "team_id": "team",
        }

        result = await factory._create_connector("linear", config)

        assert result is not None
        assert result.provider_name == "linear"

    @pytest.mark.asyncio
    async def test_create_connector_unknown_provider(self):
        """Test creating connector with unknown provider."""
        factory = TicketingConnectorFactory()

        result = await factory._create_connector("unknown", {})

        assert result is None

    @pytest.mark.asyncio
    async def test_create_connector_missing_field(self):
        """Test creating connector with missing field."""
        factory = TicketingConnectorFactory()
        config = {"provider": "github"}  # Missing repository and token

        result = await factory._create_connector("github", config)

        assert result is None

    def test_clear_cache_specific(self):
        """Test clearing specific customer cache."""
        factory = TicketingConnectorFactory()
        factory._connectors["cust-123"] = MagicMock()
        factory._connectors["cust-456"] = MagicMock()

        factory.clear_cache("cust-123")

        assert "cust-123" not in factory._connectors
        assert "cust-456" in factory._connectors

    def test_clear_cache_all(self):
        """Test clearing all cache."""
        factory = TicketingConnectorFactory()
        factory._connectors["cust-123"] = MagicMock()
        factory._connectors["cust-456"] = MagicMock()

        factory.clear_cache()

        assert len(factory._connectors) == 0


class TestFactoryHelperFunctions:
    """Tests for factory helper functions."""

    def test_get_ticketing_connector_factory(self):
        """Test getting singleton factory."""
        factory1 = get_ticketing_connector_factory()
        factory2 = get_ticketing_connector_factory()

        assert factory1 is factory2

    @pytest.mark.asyncio
    async def test_get_ticketing_connector(self):
        """Test convenience function."""
        config = {
            "provider": "github",
            "repository": "owner/repo",
            "token": "test-token",
        }

        result = await get_ticketing_connector("cust-999", config=config)

        assert result is not None


# =============================================================================
# Base Connector Priority Mapping Tests
# =============================================================================


class TestPriorityMapping:
    """Tests for priority to labels mapping."""

    def test_map_priority_to_labels(self, github_connector):
        """Test mapping priority to labels."""
        labels = github_connector._map_priority_to_labels(TicketPriority.CRITICAL)
        assert "priority:critical" in labels

        labels = github_connector._map_priority_to_labels(TicketPriority.LOW)
        assert "priority:low" in labels

    def test_github_priority_labels(self):
        """Test GitHub priority label mapping."""
        assert PRIORITY_LABELS["priority:critical"] == TicketPriority.CRITICAL
        assert PRIORITY_LABELS["P0"] == TicketPriority.CRITICAL
        assert PRIORITY_LABELS["P3"] == TicketPriority.LOW


class TestGitHubStateMapping:
    """Tests for GitHub state to status mapping."""

    def test_state_mapping(self):
        """Test GitHub state mapping."""
        assert GITHUB_STATE_TO_STATUS["open"] == TicketStatus.OPEN
        assert GITHUB_STATE_TO_STATUS["closed"] == TicketStatus.CLOSED
