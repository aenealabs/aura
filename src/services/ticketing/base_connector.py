"""
Base Ticketing Connector Interface.

Defines the abstract interface that all ticketing connectors must implement.
See ADR-046 for architecture details.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TicketPriority(Enum):
    """Ticket priority levels, mapped to provider-specific values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketStatus(Enum):
    """Unified ticket status across all providers."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class TicketCreate:
    """Data for creating a new ticket."""

    title: str
    description: str
    priority: TicketPriority = TicketPriority.MEDIUM
    labels: List[str] = field(default_factory=list)
    assignee: Optional[str] = None
    customer_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketUpdate:
    """Data for updating an existing ticket."""

    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    labels: Optional[List[str]] = None
    assignee: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TicketComment:
    """A comment on a ticket."""

    id: str
    author: str
    body: str
    created_at: datetime
    is_internal: bool = False  # Internal notes not visible to customer


@dataclass
class Ticket:
    """Unified ticket representation across all providers."""

    id: str  # Internal Aura ticket ID
    external_id: str  # ID in external system (GitHub issue number, etc.)
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    labels: List[str]
    assignee: Optional[str]
    reporter: str
    created_at: datetime
    updated_at: datetime
    external_url: str  # Link to ticket in external system
    comments: List[TicketComment] = field(default_factory=list)
    customer_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketResult:
    """Result of a ticketing operation."""

    success: bool
    ticket: Optional[Ticket] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class TicketFilters:
    """Filters for listing tickets."""

    status: Optional[List[TicketStatus]] = None
    priority: Optional[List[TicketPriority]] = None
    labels: Optional[List[str]] = None
    assignee: Optional[str] = None
    customer_id: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class TicketingConnector(ABC):
    """
    Abstract base class for ticketing system connectors.

    All ticketing connectors must implement this interface to provide
    a consistent API for ticket operations regardless of the backend
    ticketing system.

    Implementations:
    - GitHubIssuesConnector: GitHub Issues integration
    - ZendeskConnector: Zendesk integration (stub)
    - LinearConnector: Linear integration (stub)
    - ServiceNowTicketConnector: ServiceNow integration (stub)
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Return the provider name.

        Returns:
            Provider identifier: 'github', 'zendesk', 'linear', 'servicenow'
        """

    @property
    @abstractmethod
    def provider_display_name(self) -> str:
        """
        Return human-readable provider name for UI display.

        Returns:
            Display name: 'GitHub Issues', 'Zendesk', 'Linear', 'ServiceNow'
        """

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the connector can reach the external system.

        Used by the UI 'Test Connection' button to validate credentials.

        Returns:
            True if connection successful, False otherwise
        """

    @abstractmethod
    async def create_ticket(self, ticket: TicketCreate) -> TicketResult:
        """
        Create a new ticket in the external system.

        Args:
            ticket: Ticket creation data

        Returns:
            TicketResult with created ticket or error details
        """

    @abstractmethod
    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """
        Retrieve a ticket by its internal ID.

        Args:
            ticket_id: Internal Aura ticket ID

        Returns:
            Ticket if found, None otherwise
        """

    @abstractmethod
    async def get_ticket_by_external_id(self, external_id: str) -> Optional[Ticket]:
        """
        Retrieve a ticket by its external system ID.

        Args:
            external_id: External system ID (e.g., GitHub issue number)

        Returns:
            Ticket if found, None otherwise
        """

    @abstractmethod
    async def update_ticket(
        self, ticket_id: str, updates: TicketUpdate
    ) -> TicketResult:
        """
        Update an existing ticket.

        Args:
            ticket_id: Internal Aura ticket ID
            updates: Fields to update (None fields are ignored)

        Returns:
            TicketResult with updated ticket or error details
        """

    @abstractmethod
    async def list_tickets(
        self, filters: Optional[TicketFilters] = None
    ) -> List[Ticket]:
        """
        List tickets with optional filters.

        Args:
            filters: Optional filter criteria

        Returns:
            List of matching tickets
        """

    @abstractmethod
    async def add_comment(
        self, ticket_id: str, comment: str, is_internal: bool = False
    ) -> TicketResult:
        """
        Add a comment to an existing ticket.

        Args:
            ticket_id: Internal Aura ticket ID
            comment: Comment text (markdown supported)
            is_internal: If True, comment is internal note (not visible to customer)

        Returns:
            TicketResult with updated ticket or error details
        """

    @abstractmethod
    async def close_ticket(
        self, ticket_id: str, resolution: Optional[str] = None
    ) -> TicketResult:
        """
        Close a ticket with optional resolution note.

        Args:
            ticket_id: Internal Aura ticket ID
            resolution: Optional resolution summary

        Returns:
            TicketResult with closed ticket or error details
        """

    @abstractmethod
    async def reopen_ticket(
        self, ticket_id: str, reason: Optional[str] = None
    ) -> TicketResult:
        """
        Reopen a previously closed ticket.

        Args:
            ticket_id: Internal Aura ticket ID
            reason: Optional reason for reopening

        Returns:
            TicketResult with reopened ticket or error details
        """

    def _map_priority_to_labels(self, priority: TicketPriority) -> List[str]:
        """
        Map priority to provider-agnostic labels.

        Override in subclasses for provider-specific mappings.
        """
        priority_labels = {
            TicketPriority.LOW: ["priority:low"],
            TicketPriority.MEDIUM: ["priority:medium"],
            TicketPriority.HIGH: ["priority:high"],
            TicketPriority.CRITICAL: ["priority:critical"],
        }
        return priority_labels.get(priority, [])
