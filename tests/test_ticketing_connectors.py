"""
Tests for Support Ticketing Connectors.

Tests the GitHub Issues, Zendesk, Linear, and ServiceNow connectors for ADR-046.
Uses mocked HTTP responses to avoid real API calls during testing.
"""

import json
import platform
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.ticketing.base_connector import (
    Ticket,
    TicketCreate,
    TicketFilters,
    TicketingConnector,
    TicketPriority,
    TicketResult,
    TicketStatus,
    TicketUpdate,
)
from src.services.ticketing.connector_factory import (
    TicketingConnectorFactory,
    get_ticketing_connector_factory,
)
from src.services.ticketing.github_connector import GitHubIssuesConnector
from src.services.ticketing.linear_connector import LinearConnector
from src.services.ticketing.servicenow_connector import ServiceNowTicketConnector
from src.services.ticketing.zendesk_connector import ZendeskConnector

# =============================================================================
# Helper for mocking httpx
# =============================================================================


def create_mock_httpx_response(status_code: int, json_data: dict):
    """Create a mocked httpx Response object."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    mock_response.text = json.dumps(json_data)
    mock_response.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock_response


def create_mock_httpx_client(responses: dict):
    """Create a mocked httpx AsyncClient.

    Args:
        responses: Dict mapping (method, url_pattern) to (status_code, json_data)
    """
    mock_client = MagicMock()

    def mock_request(method, url, **kwargs):
        """Synchronous mock request that returns a mock response."""
        for (m, pattern), (status, data) in responses.items():
            if m.upper() == method.upper() and pattern in url:
                return create_mock_httpx_response(status, data)
        return create_mock_httpx_response(404, {"error": "Not found"})

    # Use return_value wrapper for async methods
    async def mock_get(url, **kw):
        return mock_request("GET", url, **kw)

    async def mock_post(url, **kw):
        return mock_request("POST", url, **kw)

    async def mock_patch(url, **kw):
        return mock_request("PATCH", url, **kw)

    async def mock_put(url, **kw):
        return mock_request("PUT", url, **kw)

    mock_client.request = AsyncMock(
        side_effect=lambda m, url, **kw: mock_request(m, url, **kw)
    )
    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.post = AsyncMock(side_effect=mock_post)
    mock_client.patch = AsyncMock(side_effect=mock_patch)
    mock_client.put = AsyncMock(side_effect=mock_put)

    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def github_connector():
    """Create a GitHub Issues connector with test credentials."""
    # Create connector - note: tests must patch connector._client to mock HTTP calls
    connector = GitHubIssuesConnector(
        repository="test-org/test-repo",
        token="ghp_test_token_12345",
    )
    return connector


@pytest.fixture
def mock_github_connector(sample_github_issue):
    """Create a GitHub connector with mocked HTTP client for testing."""
    connector = GitHubIssuesConnector(
        repository="test-org/test-repo",
        token="ghp_test_token_12345",
    )
    # Replace the real client with a mock
    mock_client = MagicMock()
    mock_client.post = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.patch = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    connector._client = mock_client
    return connector, mock_client


@pytest.fixture
def zendesk_connector():
    """Create a Zendesk connector with test credentials."""
    return ZendeskConnector(
        subdomain="testcompany",
        email="admin@testcompany.com",
        api_token="zendesk_test_token",
    )


@pytest.fixture
def linear_connector():
    """Create a Linear connector with test credentials."""
    return LinearConnector(
        api_key="lin_api_test_key",
        team_id="TEAM123",
    )


@pytest.fixture
def servicenow_connector():
    """Create a ServiceNow connector with test credentials."""
    return ServiceNowTicketConnector(
        instance_url="https://testcompany.service-now.com",
        username="admin",
        password="testpassword123",
    )


@pytest.fixture
def sample_ticket_create():
    """Sample ticket creation request."""
    return TicketCreate(
        title="Critical vulnerability in auth module",
        description="SQL injection found in login endpoint",
        priority=TicketPriority.HIGH,
        labels=["security", "critical"],
        metadata={"finding_id": "VULN-001", "severity": "high"},
    )


@pytest.fixture
def sample_github_issue():
    """Sample GitHub issue response."""
    return {
        "number": 42,
        "id": 12345678,
        "title": "Critical vulnerability in auth module",
        "body": "SQL injection found in login endpoint",
        "state": "open",
        "html_url": "https://github.com/test-org/test-repo/issues/42",
        "created_at": "2025-01-15T10:30:00Z",
        "updated_at": "2025-01-15T10:30:00Z",
        "labels": [{"name": "security"}, {"name": "critical"}],
        "user": {"login": "aura-bot"},
        "comments": 0,
    }


# =============================================================================
# Base Connector Abstract Class Tests
# =============================================================================


class TestTicketingConnectorInterface:
    """Tests for the abstract TicketingConnector interface."""

    def test_cannot_instantiate_abstract_class(self):
        """Verify abstract class cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TicketingConnector()

    def test_required_abstract_methods(self):
        """Verify all required abstract methods are defined."""
        abstract_methods = [
            "create_ticket",
            "get_ticket",
            "update_ticket",
            "list_tickets",
            "add_comment",
        ]
        for method in abstract_methods:
            assert hasattr(TicketingConnector, method)


# =============================================================================
# Data Model Tests
# =============================================================================


class TestTicketDataModels:
    """Tests for ticket data models."""

    def test_ticket_create_defaults(self):
        """Test TicketCreate with minimal fields."""
        ticket = TicketCreate(
            title="Test ticket",
            description="Test description",
        )
        assert ticket.priority == TicketPriority.MEDIUM
        assert ticket.labels == []
        assert ticket.metadata == {}
        assert ticket.assignee is None

    def test_ticket_create_full(self):
        """Test TicketCreate with all fields."""
        ticket = TicketCreate(
            title="Security Issue",
            description="CVE-2025-0001",
            priority=TicketPriority.CRITICAL,
            labels=["security", "p0"],
            assignee="security-team",
            metadata={"cve": "CVE-2025-0001"},
        )
        assert ticket.priority == TicketPriority.CRITICAL
        assert "security" in ticket.labels
        assert ticket.metadata["cve"] == "CVE-2025-0001"

    def test_ticket_priority_ordering(self):
        """Test priority enum ordering."""
        priorities = [
            TicketPriority.LOW,
            TicketPriority.MEDIUM,
            TicketPriority.HIGH,
            TicketPriority.CRITICAL,
        ]
        # Verify enum values exist
        for p in priorities:
            assert p.value in ["low", "medium", "high", "critical"]

    def test_ticket_status_values(self):
        """Test status enum values."""
        statuses = [
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
        ]
        for s in statuses:
            assert s.value in ["open", "in_progress", "resolved", "closed"]

    def test_ticket_result_success(self):
        """Test successful TicketResult."""
        now = datetime.now()
        result = TicketResult(
            success=True,
            ticket=Ticket(
                id="42",
                external_id="42",
                title="Test",
                description="Test",
                status=TicketStatus.OPEN,
                priority=TicketPriority.MEDIUM,
                labels=["security"],
                assignee=None,
                reporter="aura-bot",
                created_at=now,
                updated_at=now,
                external_url="https://github.com/org/repo/issues/42",
            ),
        )
        assert result.success
        assert result.ticket.id == "42"
        assert result.error_message is None

    def test_ticket_result_failure(self):
        """Test failed TicketResult."""
        result = TicketResult(
            success=False,
            error_message="API rate limit exceeded",
        )
        assert not result.success
        assert result.ticket is None
        assert "rate limit" in result.error_message.lower()


# =============================================================================
# GitHub Issues Connector Tests
# =============================================================================


class TestGitHubIssuesConnector:
    """Tests for GitHubIssuesConnector."""

    def test_initialization(self, github_connector):
        """Test connector initializes correctly."""
        assert github_connector.provider_name == "github"

    @pytest.mark.asyncio
    async def test_create_ticket_success(
        self, github_connector, sample_ticket_create, sample_github_issue
    ):
        """Test successful ticket creation."""
        mock_client = create_mock_httpx_client(
            {
                ("POST", "/repos/test-org/test-repo/issues"): (
                    201,
                    sample_github_issue,
                ),
            }
        )

        # Patch the connector's client directly
        github_connector._client = mock_client
        result = await github_connector.create_ticket(sample_ticket_create)

        assert result.success
        assert result.ticket is not None
        # Connector generates internal UUID for ticket IDs, not GitHub issue numbers
        assert result.ticket.id is not None
        assert len(result.ticket.id) > 0
        assert "github.com" in result.ticket.external_url

    @pytest.mark.asyncio
    async def test_create_ticket_api_error(
        self, github_connector, sample_ticket_create
    ):
        """Test ticket creation with API error."""
        mock_client = create_mock_httpx_client(
            {
                ("POST", "/repos/test-org/test-repo/issues"): (
                    401,
                    {"message": "Bad credentials"},
                ),
            }
        )

        # Patch the connector's client directly
        github_connector._client = mock_client
        result = await github_connector.create_ticket(sample_ticket_create)

        assert not result.success
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_get_ticket_success(self, github_connector, sample_github_issue):
        """Test fetching a ticket."""
        mock_client = create_mock_httpx_client(
            {
                ("GET", "/repos/test-org/test-repo/issues/42"): (
                    200,
                    sample_github_issue,
                ),
            }
        )

        # Pre-populate the ticket mapping (connector uses internal ID -> issue number)
        internal_id = "test-ticket-id-123"
        github_connector._ticket_mapping[internal_id] = 42

        # Patch the connector's client directly
        github_connector._client = mock_client
        ticket = await github_connector.get_ticket(internal_id)

        assert ticket is not None
        assert ticket.id == internal_id
        assert ticket.title == "Critical vulnerability in auth module"
        assert ticket.status == TicketStatus.OPEN

    @pytest.mark.asyncio
    async def test_get_ticket_not_found(self, github_connector):
        """Test fetching non-existent ticket."""
        mock_client = create_mock_httpx_client(
            {
                ("GET", "/repos/test-org/test-repo/issues/999"): (
                    404,
                    {"message": "Not Found"},
                ),
            }
        )

        github_connector._client = mock_client
        ticket = await github_connector.get_ticket("999")

        assert ticket is None

    @pytest.mark.asyncio
    async def test_update_ticket_success(self, github_connector):
        """Test updating a ticket."""
        updated_issue = {
            "number": 42,
            "id": 12345678,
            "title": "Updated title",
            "body": "Updated description",
            "state": "open",
            "html_url": "https://github.com/test-org/test-repo/issues/42",
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-15T11:00:00Z",
            "labels": [],
            "user": {"login": "aura-bot"},
            "comments": 0,
        }
        mock_client = create_mock_httpx_client(
            {
                ("PATCH", "/repos/test-org/test-repo/issues/42"): (
                    200,
                    updated_issue,
                ),
            }
        )

        # Pre-populate the ticket mapping
        internal_id = "test-ticket-id-456"
        github_connector._ticket_mapping[internal_id] = 42

        github_connector._client = mock_client
        update = TicketUpdate(title="Updated title")
        result = await github_connector.update_ticket(internal_id, update)

        assert result.success

    @pytest.mark.asyncio
    async def test_list_tickets(self, github_connector, sample_github_issue):
        """Test listing tickets."""
        mock_client = create_mock_httpx_client(
            {
                ("GET", "/repos/test-org/test-repo/issues"): (
                    200,
                    [sample_github_issue],
                ),
            }
        )

        github_connector._client = mock_client
        tickets = await github_connector.list_tickets()

        assert len(tickets) == 1
        # list_tickets generates internal UUIDs, not GitHub issue numbers
        assert tickets[0].id is not None
        assert len(tickets[0].id) > 0
        assert tickets[0].title == "Critical vulnerability in auth module"

    @pytest.mark.asyncio
    async def test_add_comment_success(self, github_connector, sample_github_issue):
        """Test adding a comment."""
        comment_response = {
            "id": 987654,
            "body": "This is a test comment",
            "created_at": "2025-01-15T12:00:00Z",
            "user": {"login": "aura-bot"},
        }
        mock_client = create_mock_httpx_client(
            {
                ("POST", "/repos/test-org/test-repo/issues/42/comments"): (
                    201,
                    comment_response,
                ),
                ("GET", "/repos/test-org/test-repo/issues/42"): (
                    200,
                    sample_github_issue,
                ),
            }
        )

        # Pre-populate the ticket mapping
        internal_id = "test-ticket-id-789"
        github_connector._ticket_mapping[internal_id] = 42

        github_connector._client = mock_client
        result = await github_connector.add_comment(
            internal_id, "This is a test comment"
        )

        assert result.success

    @pytest.mark.asyncio
    async def test_close_ticket(self, github_connector):
        """Test closing a ticket."""
        closed_issue = {
            "number": 42,
            "id": 12345678,
            "title": "Test issue",
            "body": "Test",
            "state": "closed",
            "html_url": "https://github.com/test-org/test-repo/issues/42",
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-15T12:00:00Z",
            "labels": [],
            "user": {"login": "aura-bot"},
            "comments": 0,
        }
        mock_client = create_mock_httpx_client(
            {
                ("PATCH", "/repos/test-org/test-repo/issues/42"): (
                    200,
                    closed_issue,
                ),
            }
        )

        # Pre-populate the ticket mapping
        internal_id = "test-ticket-id-close"
        github_connector._ticket_mapping[internal_id] = 42

        github_connector._client = mock_client
        result = await github_connector.close_ticket(internal_id)

        assert result.success

    @pytest.mark.asyncio
    async def test_reopen_ticket(self, github_connector):
        """Test reopening a ticket."""
        reopened_issue = {
            "number": 42,
            "id": 12345678,
            "title": "Test issue",
            "body": "Test",
            "state": "open",
            "html_url": "https://github.com/test-org/test-repo/issues/42",
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-15T13:00:00Z",
            "labels": [],
            "user": {"login": "aura-bot"},
            "comments": 0,
        }
        mock_client = create_mock_httpx_client(
            {
                ("PATCH", "/repos/test-org/test-repo/issues/42"): (
                    200,
                    reopened_issue,
                ),
            }
        )

        # Pre-populate the ticket mapping
        internal_id = "test-ticket-id-reopen"
        github_connector._ticket_mapping[internal_id] = 42

        github_connector._client = mock_client
        result = await github_connector.reopen_ticket(internal_id)

        assert result.success


# =============================================================================
# Zendesk Connector Tests
# =============================================================================


class TestZendeskConnector:
    """Tests for ZendeskConnector."""

    def test_initialization(self, zendesk_connector):
        """Test connector initializes correctly."""
        assert zendesk_connector.provider_name == "zendesk"


# =============================================================================
# Linear Connector Tests
# =============================================================================


class TestLinearConnector:
    """Tests for LinearConnector."""

    def test_initialization(self, linear_connector):
        """Test connector initializes correctly."""
        assert linear_connector.provider_name == "linear"


# =============================================================================
# ServiceNow Connector Tests
# =============================================================================


class TestServiceNowConnector:
    """Tests for ServiceNowTicketConnector."""

    def test_initialization(self, servicenow_connector):
        """Test connector initializes correctly."""
        assert servicenow_connector.provider_name == "servicenow"


# =============================================================================
# Connector Factory Tests
# =============================================================================


class TestConnectorFactory:
    """Tests for the connector factory."""

    def test_factory_initialization(self):
        """Test factory initializes correctly."""
        factory = TicketingConnectorFactory()
        assert factory is not None

    def test_get_provider_metadata(self):
        """Test getting provider metadata."""
        factory = TicketingConnectorFactory()
        metadata = factory.get_provider_metadata()
        assert "github" in metadata
        assert "zendesk" in metadata
        assert "linear" in metadata
        assert "servicenow" in metadata

    def test_get_implemented_providers(self):
        """Test getting list of implemented providers."""
        factory = TicketingConnectorFactory()
        implemented = factory.get_implemented_providers()
        assert "github" in implemented

    @pytest.mark.asyncio
    async def test_create_github_connector(self):
        """Test creating GitHub Issues connector via factory."""
        factory = TicketingConnectorFactory()
        config = {
            "provider": "github",
            "repository": "test-org/test-repo",
            "token": "test-token",
        }
        connector = await factory._create_connector("github", config)
        assert connector is not None
        assert connector.provider_name == "github"
        assert isinstance(connector, GitHubIssuesConnector)

    @pytest.mark.asyncio
    async def test_create_zendesk_connector(self):
        """Test creating Zendesk connector via factory."""
        factory = TicketingConnectorFactory()
        config = {
            "subdomain": "test",
            "email": "test@example.com",
            "api_token": "token123",
        }
        connector = await factory._create_connector("zendesk", config)
        assert connector is not None
        assert connector.provider_name == "zendesk"
        assert isinstance(connector, ZendeskConnector)

    @pytest.mark.asyncio
    async def test_create_linear_connector(self):
        """Test creating Linear connector via factory."""
        factory = TicketingConnectorFactory()
        config = {
            "api_key": "lin_key",
            "team_id": "TEAM",
        }
        connector = await factory._create_connector("linear", config)
        assert connector is not None
        assert connector.provider_name == "linear"
        assert isinstance(connector, LinearConnector)

    @pytest.mark.asyncio
    async def test_create_servicenow_connector(self):
        """Test creating ServiceNow connector via factory."""
        factory = TicketingConnectorFactory()
        config = {
            "instance_url": "https://company.service-now.com",
            "username": "admin",
            "password": "pass",
        }
        connector = await factory._create_connector("servicenow", config)
        assert connector is not None
        assert connector.provider_name == "servicenow"
        assert isinstance(connector, ServiceNowTicketConnector)

    @pytest.mark.asyncio
    async def test_create_unknown_provider(self):
        """Test creating connector with unknown provider."""
        factory = TicketingConnectorFactory()
        connector = await factory._create_connector(
            "unknown_provider",
            {},
        )
        assert connector is None

    def test_provider_metadata_structure(self):
        """Test provider metadata has required fields."""
        required_providers = [
            "github",
            "zendesk",
            "linear",
            "servicenow",
        ]
        factory = TicketingConnectorFactory()
        metadata = factory.get_provider_metadata()
        for provider in required_providers:
            assert provider in metadata
            provider_data = metadata[provider]
            assert "name" in provider_data
            assert "description" in provider_data
            assert "config_fields" in provider_data
            assert len(provider_data["config_fields"]) > 0

    def test_factory_cache_operations(self):
        """Test factory cache clear operations."""
        factory = TicketingConnectorFactory()
        # Clear specific customer
        factory.clear_cache("customer-123")
        # Clear all
        factory.clear_cache()
        # Should not raise any errors

    def test_get_factory_singleton(self):
        """Test singleton factory access."""
        factory1 = get_ticketing_connector_factory()
        factory2 = get_ticketing_connector_factory()
        assert factory1 is factory2


# =============================================================================
# Integration Pattern Tests
# =============================================================================


class TestTicketingIntegration:
    """Tests for ticketing integration patterns."""

    @pytest.mark.asyncio
    async def test_full_ticket_lifecycle(self, github_connector, sample_ticket_create):
        """Test complete ticket lifecycle: create, update, comment, close."""
        issue = {
            "number": 42,
            "id": 12345678,
            "title": sample_ticket_create.title,
            "body": sample_ticket_create.description,
            "state": "open",
            "html_url": "https://github.com/test-org/test-repo/issues/42",
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-15T10:30:00Z",
            "labels": [],
            "user": {"login": "aura-bot"},
            "comments": 0,
        }
        closed_issue = {**issue, "state": "closed"}
        comment = {
            "id": 987654,
            "body": "Patch applied",
            "created_at": "2025-01-15T11:00:00Z",
            "user": {"login": "aura-bot"},
        }

        mock_client = create_mock_httpx_client(
            {
                ("POST", "/repos/test-org/test-repo/issues"): (201, issue),
                ("PATCH", "/repos/test-org/test-repo/issues/42"): (
                    200,
                    closed_issue,
                ),
                ("POST", "/repos/test-org/test-repo/issues/42/comments"): (
                    201,
                    comment,
                ),
            }
        )

        github_connector._client = mock_client

        # Create ticket
        result = await github_connector.create_ticket(sample_ticket_create)
        assert result.success
        assert result.ticket is not None
        ticket_id = result.ticket.id

        # Add comment
        comment_result = await github_connector.add_comment(ticket_id, "Patch applied")
        assert comment_result.success

        # Close ticket
        close_result = await github_connector.close_ticket(ticket_id)
        assert close_result.success

    def test_priority_to_label_mapping(self):
        """Test priority values can be used as labels."""
        priorities = [
            TicketPriority.LOW,
            TicketPriority.MEDIUM,
            TicketPriority.HIGH,
            TicketPriority.CRITICAL,
        ]
        labels = [f"priority:{p.value}" for p in priorities]
        assert "priority:critical" in labels
        assert "priority:high" in labels


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in connectors."""

    @pytest.mark.asyncio
    async def test_network_error_handling(self, github_connector, sample_ticket_create):
        """Test handling of network errors."""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        github_connector._client = mock_client
        result = await github_connector.create_ticket(sample_ticket_create)

        assert not result.success
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, github_connector, sample_ticket_create):
        """Test handling of rate limit errors."""
        mock_client = create_mock_httpx_client(
            {
                ("POST", "/repos/test-org/test-repo/issues"): (
                    429,
                    {"message": "API rate limit exceeded"},
                ),
            }
        )

        github_connector._client = mock_client
        result = await github_connector.create_ticket(sample_ticket_create)

        assert not result.success
        assert result.error_message is not None
        assert (
            "rate limit" in result.error_message.lower()
            or "429" in result.error_message
        )

    @pytest.mark.asyncio
    async def test_invalid_credentials_handling(
        self, github_connector, sample_ticket_create
    ):
        """Test handling of invalid credentials."""
        mock_client = create_mock_httpx_client(
            {
                ("POST", "/repos/test-org/test-repo/issues"): (
                    401,
                    {"message": "Bad credentials"},
                ),
            }
        )

        github_connector._client = mock_client
        result = await github_connector.create_ticket(sample_ticket_create)

        assert not result.success


# =============================================================================
# Ticket Filters Tests
# =============================================================================


class TestTicketFilters:
    """Tests for ticket filtering functionality."""

    def test_filter_defaults(self):
        """Test TicketFilters with defaults."""
        filters = TicketFilters()
        assert filters.status is None
        assert filters.priority is None
        assert filters.labels is None
        assert filters.assignee is None
        assert filters.customer_id is None

    def test_filter_with_all_fields(self):
        """Test TicketFilters with all fields set."""
        filters = TicketFilters(
            status=[TicketStatus.OPEN],
            priority=[TicketPriority.HIGH],
            labels=["security", "urgent"],
            assignee="security-team",
            customer_id="cust-123",
        )
        assert TicketStatus.OPEN in filters.status
        assert TicketPriority.HIGH in filters.priority
        assert "security" in filters.labels
        assert filters.assignee == "security-team"


# =============================================================================
# ServiceNow Connector Extended Tests (Coverage Improvement)
# =============================================================================

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


class TestServiceNowConnectorExtended:
    """Extended tests for ServiceNowTicketConnector coverage."""

    def test_servicenow_properties(self, servicenow_connector):
        """Test ServiceNow connector properties."""
        assert servicenow_connector.provider_name == "servicenow"
        assert servicenow_connector.provider_display_name == "ServiceNow"

    @pytest.mark.asyncio
    async def test_servicenow_test_connection(self, servicenow_connector):
        """Test ServiceNow test_connection stub."""
        result = await servicenow_connector.test_connection()
        assert result is False  # Stub returns False

    @pytest.mark.asyncio
    async def test_servicenow_create_ticket(
        self, servicenow_connector, sample_ticket_create
    ):
        """Test ServiceNow create_ticket stub."""
        result = await servicenow_connector.create_ticket(sample_ticket_create)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "not yet implemented" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_servicenow_get_ticket(self, servicenow_connector):
        """Test ServiceNow get_ticket stub."""
        result = await servicenow_connector.get_ticket("INC0001234")
        assert result is None

    @pytest.mark.asyncio
    async def test_servicenow_get_ticket_by_external_id(self, servicenow_connector):
        """Test ServiceNow get_ticket_by_external_id stub."""
        result = await servicenow_connector.get_ticket_by_external_id("sys_id_12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_servicenow_update_ticket(self, servicenow_connector):
        """Test ServiceNow update_ticket stub."""
        update = TicketUpdate(title="Updated Title")
        result = await servicenow_connector.update_ticket("INC0001234", update)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_list_tickets(self, servicenow_connector):
        """Test ServiceNow list_tickets stub."""
        result = await servicenow_connector.list_tickets()
        assert result == []

    @pytest.mark.asyncio
    async def test_servicenow_list_tickets_with_filters(self, servicenow_connector):
        """Test ServiceNow list_tickets with filters stub."""
        filters = TicketFilters(status=[TicketStatus.OPEN])
        result = await servicenow_connector.list_tickets(filters)
        assert result == []

    @pytest.mark.asyncio
    async def test_servicenow_add_comment(self, servicenow_connector):
        """Test ServiceNow add_comment stub."""
        result = await servicenow_connector.add_comment("INC0001234", "Test comment")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_add_internal_comment(self, servicenow_connector):
        """Test ServiceNow add_comment with internal flag stub."""
        result = await servicenow_connector.add_comment(
            "INC0001234", "Internal work note", is_internal=True
        )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_close_ticket(self, servicenow_connector):
        """Test ServiceNow close_ticket stub."""
        result = await servicenow_connector.close_ticket("INC0001234")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_close_ticket_with_resolution(self, servicenow_connector):
        """Test ServiceNow close_ticket with resolution stub."""
        result = await servicenow_connector.close_ticket(
            "INC0001234", resolution="Issue resolved by applying patch"
        )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_reopen_ticket(self, servicenow_connector):
        """Test ServiceNow reopen_ticket stub."""
        result = await servicenow_connector.reopen_ticket("INC0001234")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_servicenow_reopen_ticket_with_reason(self, servicenow_connector):
        """Test ServiceNow reopen_ticket with reason stub."""
        result = await servicenow_connector.reopen_ticket(
            "INC0001234", reason="Issue reoccurred after fix"
        )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    def test_servicenow_api_url_construction(self, servicenow_connector):
        """Test ServiceNow API URL is correctly constructed."""
        # Access internal attributes to verify URL construction
        assert (
            servicenow_connector._instance_url == "https://testcompany.service-now.com"
        )
        assert servicenow_connector._table == "incident"
        assert "api/now/table/incident" in servicenow_connector._api_url

    def test_servicenow_custom_table(self):
        """Test ServiceNow connector with custom table."""
        connector = ServiceNowTicketConnector(
            instance_url="https://test.service-now.com",
            username="admin",
            password="password",
            table="sc_request",
        )
        assert connector._table == "sc_request"
        assert "api/now/table/sc_request" in connector._api_url


# =============================================================================
# Zendesk Connector Extended Tests (Coverage Improvement)
# =============================================================================


class TestZendeskConnectorExtended:
    """Extended tests for ZendeskConnector coverage."""

    def test_zendesk_properties(self, zendesk_connector):
        """Test Zendesk connector properties."""
        assert zendesk_connector.provider_name == "zendesk"
        assert zendesk_connector.provider_display_name == "Zendesk"

    @pytest.mark.asyncio
    async def test_zendesk_test_connection(self, zendesk_connector):
        """Test Zendesk test_connection stub."""
        result = await zendesk_connector.test_connection()
        assert result is False  # Stub returns False

    @pytest.mark.asyncio
    async def test_zendesk_create_ticket(self, zendesk_connector, sample_ticket_create):
        """Test Zendesk create_ticket stub."""
        result = await zendesk_connector.create_ticket(sample_ticket_create)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"
        assert "not yet implemented" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_zendesk_get_ticket(self, zendesk_connector):
        """Test Zendesk get_ticket stub."""
        result = await zendesk_connector.get_ticket("12345")
        assert result is None

    @pytest.mark.asyncio
    async def test_zendesk_get_ticket_by_external_id(self, zendesk_connector):
        """Test Zendesk get_ticket_by_external_id stub."""
        result = await zendesk_connector.get_ticket_by_external_id("98765")
        assert result is None

    @pytest.mark.asyncio
    async def test_zendesk_update_ticket(self, zendesk_connector):
        """Test Zendesk update_ticket stub."""
        update = TicketUpdate(title="Updated Title")
        result = await zendesk_connector.update_ticket("12345", update)
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_list_tickets(self, zendesk_connector):
        """Test Zendesk list_tickets stub."""
        result = await zendesk_connector.list_tickets()
        assert result == []

    @pytest.mark.asyncio
    async def test_zendesk_list_tickets_with_filters(self, zendesk_connector):
        """Test Zendesk list_tickets with filters stub."""
        filters = TicketFilters(priority=[TicketPriority.HIGH])
        result = await zendesk_connector.list_tickets(filters)
        assert result == []

    @pytest.mark.asyncio
    async def test_zendesk_add_comment(self, zendesk_connector):
        """Test Zendesk add_comment stub."""
        result = await zendesk_connector.add_comment("12345", "Test comment")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_add_internal_comment(self, zendesk_connector):
        """Test Zendesk add_comment with internal flag stub."""
        result = await zendesk_connector.add_comment(
            "12345", "Internal note", is_internal=True
        )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_close_ticket(self, zendesk_connector):
        """Test Zendesk close_ticket stub."""
        result = await zendesk_connector.close_ticket("12345")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_close_ticket_with_resolution(self, zendesk_connector):
        """Test Zendesk close_ticket with resolution stub."""
        result = await zendesk_connector.close_ticket(
            "12345", resolution="Fixed by upgrading to latest version"
        )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_reopen_ticket(self, zendesk_connector):
        """Test Zendesk reopen_ticket stub."""
        result = await zendesk_connector.reopen_ticket("12345")
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    @pytest.mark.asyncio
    async def test_zendesk_reopen_ticket_with_reason(self, zendesk_connector):
        """Test Zendesk reopen_ticket with reason stub."""
        result = await zendesk_connector.reopen_ticket(
            "12345", reason="Customer reported issue persists"
        )
        assert result.success is False
        assert result.error_code == "NOT_IMPLEMENTED"

    def test_zendesk_base_url_construction(self, zendesk_connector):
        """Test Zendesk base URL is correctly constructed."""
        assert zendesk_connector._subdomain == "testcompany"
        assert zendesk_connector._base_url == "https://testcompany.zendesk.com/api/v2"


# =============================================================================
# Linear Connector Extended Tests (Coverage Improvement)
# =============================================================================


class TestLinearConnectorExtended:
    """Extended tests for LinearConnector coverage."""

    def test_linear_properties(self, linear_connector):
        """Test Linear connector properties."""
        assert linear_connector.provider_name == "linear"
        # Linear may have different display name
        assert linear_connector.provider_display_name in ["Linear", "linear"]


# =============================================================================
# TicketUpdate Data Model Tests
# =============================================================================


class TestTicketUpdateModel:
    """Tests for TicketUpdate model."""

    def test_ticket_update_minimal(self):
        """Test TicketUpdate with minimal fields."""
        update = TicketUpdate()
        assert update.title is None
        assert update.description is None
        assert update.status is None
        assert update.priority is None

    def test_ticket_update_with_title(self):
        """Test TicketUpdate with title only."""
        update = TicketUpdate(title="New Title")
        assert update.title == "New Title"
        assert update.description is None

    def test_ticket_update_with_status(self):
        """Test TicketUpdate with status change."""
        update = TicketUpdate(status=TicketStatus.IN_PROGRESS)
        assert update.status == TicketStatus.IN_PROGRESS

    def test_ticket_update_with_priority(self):
        """Test TicketUpdate with priority change."""
        update = TicketUpdate(priority=TicketPriority.CRITICAL)
        assert update.priority == TicketPriority.CRITICAL

    def test_ticket_update_full(self):
        """Test TicketUpdate with all fields."""
        update = TicketUpdate(
            title="Updated Title",
            description="Updated Description",
            status=TicketStatus.RESOLVED,
            priority=TicketPriority.LOW,
            assignee="new-assignee",
            labels=["resolved", "verified"],
            metadata={"resolution_time": "2h"},
        )
        assert update.title == "Updated Title"
        assert update.status == TicketStatus.RESOLVED
        assert update.priority == TicketPriority.LOW
        assert "resolved" in update.labels
