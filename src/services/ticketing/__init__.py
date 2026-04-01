"""
Support Ticketing Connectors Module.

Provides a pluggable architecture for integrating with various ticketing systems:
- GitHub Issues (primary, fully implemented)
- Zendesk (enterprise stub)
- Linear (enterprise stub)
- ServiceNow (enterprise stub)

See ADR-046 for architecture details.
"""

from .base_connector import (
    Ticket,
    TicketComment,
    TicketCreate,
    TicketFilters,
    TicketingConnector,
    TicketPriority,
    TicketResult,
    TicketStatus,
    TicketUpdate,
)
from .connector_factory import TicketingConnectorFactory, get_ticketing_connector
from .github_connector import GitHubIssuesConnector
from .linear_connector import LinearConnector
from .servicenow_connector import ServiceNowTicketConnector
from .zendesk_connector import ZendeskConnector

__all__ = [
    # Base classes
    "TicketingConnector",
    "TicketCreate",
    "TicketUpdate",
    "Ticket",
    "TicketResult",
    "TicketPriority",
    "TicketStatus",
    "TicketComment",
    "TicketFilters",
    # Connectors
    "GitHubIssuesConnector",
    "ZendeskConnector",
    "LinearConnector",
    "ServiceNowTicketConnector",
    # Factory
    "TicketingConnectorFactory",
    "get_ticketing_connector",
]
