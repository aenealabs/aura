"""
Tests for Ticketing API Endpoints.

Comprehensive test suite covering:
- Configuration management
- Provider connection testing
- Ticket CRUD operations
- Comments and status changes
- Provider listing
"""

import platform

import pytest

# Run tests in separate processes to avoid mock pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from src.api.ticketing_endpoints import (
    TestConnectionModel,
    TicketCloseModel,
    TicketCommentModel,
    TicketCreateModel,
    TicketingConfigModel,
    TicketReopenModel,
    TicketUpdateModel,
    _ticket_to_response,
    get_config,
    save_config,
)
from src.services.ticketing import TicketPriority, TicketStatus

# =============================================================================
# Mock Classes
# =============================================================================


@dataclass
class MockTicket:
    """Mock ticket for testing."""

    id: str = "ticket-123"
    external_id: str = "GH-123"
    title: str = "Test Ticket"
    description: str = "Test description"
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.MEDIUM
    labels: List[str] = field(default_factory=lambda: ["bug", "support"])
    assignee: str = "dev@example.com"
    reporter: str = "user@example.com"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    external_url: str = "https://github.com/org/repo/issues/123"
    customer_id: str = "cust-456"


@dataclass
class MockTicketResult:
    """Mock ticket operation result."""

    success: bool = True
    ticket: MockTicket = None
    error_message: str = None

    def __post_init__(self):
        if self.ticket is None:
            self.ticket = MockTicket()


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_rate_limit():
    """Create a mock rate limit result."""
    return MagicMock()


@pytest.fixture
def sample_config():
    """Create sample ticketing configuration."""
    return TicketingConfigModel(
        provider="github",
        enabled=True,
        config={
            "owner": "test-org",
            "repo": "test-repo",
            "token": "ghp_secrettoken123",
        },
        default_labels=["support", "aura"],
        auto_assign=True,
    )


@pytest.fixture
def sample_ticket():
    """Create a sample mock ticket."""
    return MockTicket()


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Test helper functions."""

    def test_ticket_to_response(self, sample_ticket):
        """Test converting ticket to response."""
        response = _ticket_to_response(sample_ticket)

        assert response["id"] == "ticket-123"
        assert response["external_id"] == "GH-123"
        assert response["title"] == "Test Ticket"
        assert response["status"] == "open"
        assert response["priority"] == "medium"
        assert "bug" in response["labels"]
        assert response["assignee"] == "dev@example.com"
        assert response["reporter"] == "user@example.com"
        assert response["customer_id"] == "cust-456"

    def test_get_config_default(self):
        """Test getting config with no saved config."""
        # Clear any existing config
        from src.api.ticketing_endpoints import _ticketing_config

        _ticketing_config.clear()

        config = get_config("new-customer")
        assert isinstance(config, TicketingConfigModel)
        assert config.provider is None
        assert config.enabled is False

    def test_save_and_get_config(self, sample_config):
        """Test saving and retrieving config."""
        save_config(sample_config, "test-customer")
        retrieved = get_config("test-customer")

        assert retrieved.provider == "github"
        assert retrieved.enabled is True
        assert retrieved.config["owner"] == "test-org"


# =============================================================================
# Configuration Endpoint Tests
# =============================================================================


class TestConfigurationEndpoints:
    """Test configuration endpoints."""

    @pytest.mark.asyncio
    async def test_get_ticketing_config(self, mock_rate_limit, sample_config):
        """Test getting ticketing configuration."""
        from src.api.ticketing_endpoints import get_ticketing_config

        save_config(sample_config, "config-test")

        result = await get_ticketing_config(
            customer_id="config-test",
            rate_limit=mock_rate_limit,
        )

        assert result.provider == "github"
        assert result.enabled is True
        # Token should be masked
        assert result.config["token"] == "***"

    @pytest.mark.asyncio
    async def test_get_ticketing_config_masks_sensitive(self, mock_rate_limit):
        """Test that sensitive fields are masked."""
        from src.api.ticketing_endpoints import get_ticketing_config

        config = TicketingConfigModel(
            provider="zendesk",
            enabled=True,
            config={
                "subdomain": "company",
                "email": "support@company.com",
                "api_token": "secret123",
                "password": "secret456",
                "api_key": "secret789",
            },
        )
        save_config(config, "mask-test")

        result = await get_ticketing_config(
            customer_id="mask-test",
            rate_limit=mock_rate_limit,
        )

        assert result.config["subdomain"] == "company"
        assert result.config["api_token"] == "***"
        assert result.config["password"] == "***"
        assert result.config["api_key"] == "***"

    @pytest.mark.asyncio
    async def test_save_ticketing_config(self, mock_rate_limit, sample_config):
        """Test saving ticketing configuration."""
        from src.api.ticketing_endpoints import save_ticketing_config

        result = await save_ticketing_config(
            config=sample_config,
            customer_id="save-test",
            rate_limit=mock_rate_limit,
        )

        assert result.provider == "github"
        assert result.enabled is True

    @pytest.mark.asyncio
    async def test_update_ticketing_config(self, mock_rate_limit, sample_config):
        """Test partial update of configuration."""
        from src.api.ticketing_endpoints import update_ticketing_config

        save_config(sample_config, "update-test")

        updates = {"auto_assign": False, "default_labels": ["updated"]}

        result = await update_ticketing_config(
            updates=updates,
            customer_id="update-test",
            rate_limit=mock_rate_limit,
        )

        assert result.auto_assign is False
        assert "updated" in result.default_labels
        assert result.provider == "github"  # Unchanged


# =============================================================================
# Connection Test Endpoint Tests
# =============================================================================


class TestConnectionEndpoints:
    """Test connection testing endpoints."""

    @pytest.mark.asyncio
    async def test_test_connection_success(self, mock_rate_limit):
        """Test successful connection test."""
        from src.api.ticketing_endpoints import test_ticketing_connection

        mock_connector = MagicMock()
        mock_connector.test_connection = AsyncMock(return_value=True)

        mock_factory = MagicMock()
        mock_factory._create_connector = AsyncMock(return_value=mock_connector)

        request = TestConnectionModel(
            provider="github",
            config={"owner": "test", "repo": "test", "token": "test"},
        )

        with patch(
            "src.api.ticketing_endpoints.TicketingConnectorFactory",
            return_value=mock_factory,
        ):
            result = await test_ticketing_connection(
                request=request,
                rate_limit=mock_rate_limit,
            )

        assert result["success"] is True
        assert "tested_at" in result

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, mock_rate_limit):
        """Test failed connection test."""
        from src.api.ticketing_endpoints import test_ticketing_connection

        mock_connector = MagicMock()
        mock_connector.test_connection = AsyncMock(return_value=False)

        mock_factory = MagicMock()
        mock_factory._create_connector = AsyncMock(return_value=mock_connector)

        request = TestConnectionModel(
            provider="github",
            config={"owner": "test", "repo": "test", "token": "bad-token"},
        )

        with patch(
            "src.api.ticketing_endpoints.TicketingConnectorFactory",
            return_value=mock_factory,
        ):
            result = await test_ticketing_connection(
                request=request,
                rate_limit=mock_rate_limit,
            )

        assert result["success"] is False
        assert "error_message" in result

    @pytest.mark.asyncio
    async def test_test_connection_unknown_provider(self, mock_rate_limit):
        """Test connection with unknown provider."""
        from src.api.ticketing_endpoints import test_ticketing_connection

        mock_factory = MagicMock()
        mock_factory._create_connector = AsyncMock(return_value=None)

        request = TestConnectionModel(
            provider="unknown",
            config={},
        )

        with patch(
            "src.api.ticketing_endpoints.TicketingConnectorFactory",
            return_value=mock_factory,
        ):
            result = await test_ticketing_connection(
                request=request,
                rate_limit=mock_rate_limit,
            )

        assert result["success"] is False
        assert "Unknown provider" in result["error_message"]


# =============================================================================
# Provider Endpoint Tests
# =============================================================================


class TestProviderEndpoints:
    """Test provider listing endpoints."""

    @pytest.mark.asyncio
    async def test_get_providers(self, mock_rate_limit):
        """Test getting available providers."""
        from src.api.ticketing_endpoints import get_ticketing_providers

        mock_metadata = {
            "github": {
                "id": "github",
                "name": "GitHub Issues",
                "description": "GitHub Issues integration",
                "icon": "github",
                "is_implemented": True,
                "config_fields": [],
            }
        }

        with patch(
            "src.api.ticketing_endpoints.TicketingConnectorFactory.get_provider_metadata",
            return_value=mock_metadata,
        ):
            result = await get_ticketing_providers(rate_limit=mock_rate_limit)

        assert "github" in result
        assert result["github"]["name"] == "GitHub Issues"


# =============================================================================
# Ticket CRUD Tests
# =============================================================================


class TestTicketCRUD:
    """Test ticket CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_ticket_success(self, mock_rate_limit, sample_ticket):
        """Test successful ticket creation."""
        from src.api.ticketing_endpoints import create_ticket

        mock_connector = MagicMock()
        mock_connector.create_ticket = AsyncMock(
            return_value=MockTicketResult(success=True, ticket=sample_ticket)
        )

        ticket_request = TicketCreateModel(
            title="New Bug",
            description="Something is broken",
            priority="high",
            labels=["bug"],
        )

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            result = await create_ticket(
                ticket=ticket_request,
                customer_id="test",
                rate_limit=mock_rate_limit,
            )

        assert result["id"] == "ticket-123"
        mock_connector.create_ticket.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_ticket_no_connector(self, mock_rate_limit):
        """Test ticket creation when ticketing not configured."""
        from src.api.ticketing_endpoints import create_ticket

        ticket_request = TicketCreateModel(
            title="New Bug",
            description="Something is broken",
        )

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector", return_value=None
        ):
            with pytest.raises(HTTPException) as exc_info:
                await create_ticket(
                    ticket=ticket_request,
                    customer_id="test",
                    rate_limit=mock_rate_limit,
                )

        assert exc_info.value.status_code == 400
        assert "not configured" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_ticket_failure(self, mock_rate_limit):
        """Test ticket creation failure."""
        from src.api.ticketing_endpoints import create_ticket

        mock_connector = MagicMock()
        mock_connector.create_ticket = AsyncMock(
            return_value=MockTicketResult(success=False, error_message="API error")
        )

        ticket_request = TicketCreateModel(
            title="New Bug",
            description="Something is broken",
        )

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await create_ticket(
                    ticket=ticket_request,
                    customer_id="test",
                    rate_limit=mock_rate_limit,
                )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_list_tickets(self, mock_rate_limit, sample_ticket):
        """Test listing tickets."""
        from src.api.ticketing_endpoints import list_tickets

        mock_connector = MagicMock()
        mock_connector.list_tickets = AsyncMock(return_value=[sample_ticket])

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            result = await list_tickets(
                customer_id="test",
                status=None,
                priority=None,
                assignee=None,
                limit=50,
                offset=0,
                rate_limit=mock_rate_limit,
            )

        assert len(result) == 1
        assert result[0]["id"] == "ticket-123"

    @pytest.mark.asyncio
    async def test_list_tickets_with_filters(self, mock_rate_limit, sample_ticket):
        """Test listing tickets with filters."""
        from src.api.ticketing_endpoints import list_tickets

        mock_connector = MagicMock()
        mock_connector.list_tickets = AsyncMock(return_value=[sample_ticket])

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            _result = await list_tickets(
                customer_id="test",
                status="open",
                priority="high",
                assignee="dev@example.com",
                limit=10,
                offset=0,
                rate_limit=mock_rate_limit,
            )

        mock_connector.list_tickets.assert_called_once()
        call_args = mock_connector.list_tickets.call_args[0][0]
        assert call_args.limit == 10
        assert call_args.assignee == "dev@example.com"

    @pytest.mark.asyncio
    async def test_get_ticket_success(self, mock_rate_limit, sample_ticket):
        """Test getting a specific ticket."""
        from src.api.ticketing_endpoints import get_ticket

        mock_connector = MagicMock()
        mock_connector.get_ticket = AsyncMock(return_value=sample_ticket)

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            result = await get_ticket(
                ticket_id="ticket-123",
                customer_id="test",
                rate_limit=mock_rate_limit,
            )

        assert result["id"] == "ticket-123"
        assert result["title"] == "Test Ticket"

    @pytest.mark.asyncio
    async def test_get_ticket_not_found(self, mock_rate_limit):
        """Test getting a non-existent ticket."""
        from src.api.ticketing_endpoints import get_ticket

        mock_connector = MagicMock()
        mock_connector.get_ticket = AsyncMock(return_value=None)

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_ticket(
                    ticket_id="nonexistent",
                    customer_id="test",
                    rate_limit=mock_rate_limit,
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_ticket(self, mock_rate_limit, sample_ticket):
        """Test updating a ticket."""
        from src.api.ticketing_endpoints import update_ticket

        updated_ticket = MockTicket(title="Updated Title")

        mock_connector = MagicMock()
        mock_connector.update_ticket = AsyncMock(
            return_value=MockTicketResult(success=True, ticket=updated_ticket)
        )

        updates = TicketUpdateModel(title="Updated Title")

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            result = await update_ticket(
                ticket_id="ticket-123",
                updates=updates,
                customer_id="test",
                rate_limit=mock_rate_limit,
            )

        assert result["title"] == "Updated Title"


# =============================================================================
# Comment and Status Tests
# =============================================================================


class TestTicketActions:
    """Test ticket action endpoints."""

    @pytest.mark.asyncio
    async def test_add_comment(self, mock_rate_limit, sample_ticket):
        """Test adding a comment to a ticket."""
        from src.api.ticketing_endpoints import add_ticket_comment

        mock_connector = MagicMock()
        mock_connector.add_comment = AsyncMock(
            return_value=MockTicketResult(success=True, ticket=sample_ticket)
        )

        comment = TicketCommentModel(
            comment="This is a test comment",
            is_internal=False,
        )

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            _result = await add_ticket_comment(
                ticket_id="ticket-123",
                comment=comment,
                customer_id="test",
                rate_limit=mock_rate_limit,
            )

        mock_connector.add_comment.assert_called_once_with(
            "ticket-123", "This is a test comment", False
        )

    @pytest.mark.asyncio
    async def test_add_internal_comment(self, mock_rate_limit, sample_ticket):
        """Test adding an internal comment."""
        from src.api.ticketing_endpoints import add_ticket_comment

        mock_connector = MagicMock()
        mock_connector.add_comment = AsyncMock(
            return_value=MockTicketResult(success=True, ticket=sample_ticket)
        )

        comment = TicketCommentModel(
            comment="Internal note",
            is_internal=True,
        )

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            await add_ticket_comment(
                ticket_id="ticket-123",
                comment=comment,
                customer_id="test",
                rate_limit=mock_rate_limit,
            )

        mock_connector.add_comment.assert_called_once_with(
            "ticket-123", "Internal note", True
        )

    @pytest.mark.asyncio
    async def test_close_ticket(self, mock_rate_limit):
        """Test closing a ticket."""
        from src.api.ticketing_endpoints import close_ticket

        closed_ticket = MockTicket(status=TicketStatus.CLOSED)

        mock_connector = MagicMock()
        mock_connector.close_ticket = AsyncMock(
            return_value=MockTicketResult(success=True, ticket=closed_ticket)
        )

        close_request = TicketCloseModel(resolution="Fixed in v2.0")

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            result = await close_ticket(
                ticket_id="ticket-123",
                request=close_request,
                customer_id="test",
                rate_limit=mock_rate_limit,
            )

        assert result["status"] == "closed"
        mock_connector.close_ticket.assert_called_once_with(
            "ticket-123", "Fixed in v2.0"
        )

    @pytest.mark.asyncio
    async def test_reopen_ticket(self, mock_rate_limit):
        """Test reopening a ticket."""
        from src.api.ticketing_endpoints import reopen_ticket

        reopened_ticket = MockTicket(status=TicketStatus.OPEN)

        mock_connector = MagicMock()
        mock_connector.reopen_ticket = AsyncMock(
            return_value=MockTicketResult(success=True, ticket=reopened_ticket)
        )

        reopen_request = TicketReopenModel(reason="Issue reoccurred")

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            result = await reopen_ticket(
                ticket_id="ticket-123",
                request=reopen_request,
                customer_id="test",
                rate_limit=mock_rate_limit,
            )

        assert result["status"] == "open"
        mock_connector.reopen_ticket.assert_called_once_with(
            "ticket-123", "Issue reoccurred"
        )


# =============================================================================
# Model Tests
# =============================================================================


class TestModels:
    """Test Pydantic models."""

    def test_ticketing_config_defaults(self):
        """Test TicketingConfigModel defaults."""
        config = TicketingConfigModel()
        assert config.provider is None
        assert config.enabled is False
        assert config.auto_assign is False
        assert "support" in config.default_labels
        assert "aura" in config.default_labels

    def test_ticket_create_validation(self):
        """Test TicketCreateModel validation."""
        # Valid request
        ticket = TicketCreateModel(
            title="Valid Title",
            description="Valid description",
            priority="high",
        )
        assert ticket.priority == "high"

        # Empty title should fail
        with pytest.raises(ValueError):
            TicketCreateModel(title="", description="Description")

    def test_ticket_update_optional_fields(self):
        """Test TicketUpdateModel optional fields."""
        update = TicketUpdateModel()
        assert update.title is None
        assert update.status is None
        assert update.priority is None

        update = TicketUpdateModel(title="New Title")
        assert update.title == "New Title"

    def test_ticket_comment_validation(self):
        """Test TicketCommentModel validation."""
        # Valid comment
        comment = TicketCommentModel(comment="Test comment")
        assert comment.is_internal is False

        # Empty comment should fail
        with pytest.raises(ValueError):
            TicketCommentModel(comment="")

    def test_test_connection_model(self):
        """Test TestConnectionModel."""
        test = TestConnectionModel(
            provider="github",
            config={"token": "test"},
        )
        assert test.provider == "github"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_connector_exception(self, mock_rate_limit):
        """Test handling of connector exceptions."""
        from src.api.ticketing_endpoints import test_ticketing_connection

        mock_factory = MagicMock()
        mock_factory._create_connector = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        request = TestConnectionModel(
            provider="github",
            config={},
        )

        with patch(
            "src.api.ticketing_endpoints.TicketingConnectorFactory",
            return_value=mock_factory,
        ):
            result = await test_ticketing_connection(
                request=request,
                rate_limit=mock_rate_limit,
            )

        assert result["success"] is False
        assert "Connection failed" in result["error_message"]

    @pytest.mark.asyncio
    async def test_invalid_priority_fallback(self, mock_rate_limit, sample_ticket):
        """Test invalid priority defaults to MEDIUM."""
        from src.api.ticketing_endpoints import create_ticket

        mock_connector = MagicMock()
        mock_connector.create_ticket = AsyncMock(
            return_value=MockTicketResult(success=True, ticket=sample_ticket)
        )

        ticket_request = TicketCreateModel(
            title="Bug",
            description="Description",
            priority="invalid_priority",
        )

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            await create_ticket(
                ticket=ticket_request,
                customer_id="test",
                rate_limit=mock_rate_limit,
            )

        # Should use MEDIUM as fallback
        call_args = mock_connector.create_ticket.call_args[0][0]
        assert call_args.priority == TicketPriority.MEDIUM

    @pytest.mark.asyncio
    async def test_operation_failure(self, mock_rate_limit):
        """Test handling operation failures."""
        from src.api.ticketing_endpoints import close_ticket

        mock_connector = MagicMock()
        mock_connector.close_ticket = AsyncMock(
            return_value=MockTicketResult(
                success=False,
                error_message="Permission denied",
            )
        )

        close_request = TicketCloseModel()

        with patch(
            "src.api.ticketing_endpoints.get_ticketing_connector",
            return_value=mock_connector,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await close_ticket(
                    ticket_id="ticket-123",
                    request=close_request,
                    customer_id="test",
                    rate_limit=mock_rate_limit,
                )

        assert exc_info.value.status_code == 500
        assert "Permission denied" in str(exc_info.value.detail)
