"""
Linear Ticketing Connector (Stub).

Enterprise connector for Linear issue tracking integration.
Currently a stub implementation for future development.
See ADR-046 for architecture details.
"""

import logging
from typing import List, Optional

from .base_connector import (
    Ticket,
    TicketCreate,
    TicketFilters,
    TicketingConnector,
    TicketResult,
    TicketUpdate,
)

logger = logging.getLogger(__name__)


class LinearConnector(TicketingConnector):
    """
    Linear issue tracking connector for enterprise ticketing.

    This is a stub implementation. Full implementation will use:
    - Linear GraphQL API
    - OAuth 2.0 authentication
    - Issue states, labels, and projects
    - Webhooks for real-time sync

    Configuration:
        - api_key: Linear API key
        - team_id: Linear team ID for issue creation
        - project_id: Optional default project

    Reference:
        https://developers.linear.app/docs/graphql
    """

    def __init__(
        self,
        api_key: str,
        team_id: str,
        project_id: Optional[str] = None,
    ):
        """
        Initialize Linear connector.

        Args:
            api_key: Linear API key
            team_id: Linear team ID
            project_id: Optional default project ID
        """
        self._api_key = api_key
        self._team_id = team_id
        self._project_id = project_id
        self._graphql_url = "https://api.linear.app/graphql"
        logger.info(f"Linear connector initialized for team {team_id} (stub)")

    @property
    def provider_name(self) -> str:
        return "linear"

    @property
    def provider_display_name(self) -> str:
        return "Linear"

    async def test_connection(self) -> bool:
        """Test Linear API connectivity."""
        logger.warning("Linear connector is a stub - test_connection not implemented")
        # Stub: Would verify API key by querying viewer { id }
        return False

    async def create_ticket(self, ticket: TicketCreate) -> TicketResult:
        """Create a new Linear issue."""
        logger.warning("Linear connector is a stub - create_ticket not implemented")
        return TicketResult(
            success=False,
            error_message="Linear connector not yet implemented",
            error_code="NOT_IMPLEMENTED",
        )

    async def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get issue by internal ID."""
        logger.warning("Linear connector is a stub - get_ticket not implemented")
        return None

    async def get_ticket_by_external_id(self, external_id: str) -> Optional[Ticket]:
        """Get issue by Linear issue ID."""
        logger.warning(
            "Linear connector is a stub - get_ticket_by_external_id not implemented"
        )
        return None

    async def update_ticket(
        self, ticket_id: str, updates: TicketUpdate
    ) -> TicketResult:
        """Update an existing Linear issue."""
        logger.warning("Linear connector is a stub - update_ticket not implemented")
        return TicketResult(
            success=False,
            error_message="Linear connector not yet implemented",
            error_code="NOT_IMPLEMENTED",
        )

    async def list_tickets(
        self, filters: Optional[TicketFilters] = None
    ) -> List[Ticket]:
        """List Linear issues with optional filters."""
        logger.warning("Linear connector is a stub - list_tickets not implemented")
        return []

    async def add_comment(
        self, ticket_id: str, comment: str, is_internal: bool = False
    ) -> TicketResult:
        """Add a comment to a Linear issue."""
        logger.warning("Linear connector is a stub - add_comment not implemented")
        return TicketResult(
            success=False,
            error_message="Linear connector not yet implemented",
            error_code="NOT_IMPLEMENTED",
        )

    async def close_ticket(
        self, ticket_id: str, resolution: Optional[str] = None
    ) -> TicketResult:
        """Close a Linear issue by moving to 'Done' state."""
        logger.warning("Linear connector is a stub - close_ticket not implemented")
        return TicketResult(
            success=False,
            error_message="Linear connector not yet implemented",
            error_code="NOT_IMPLEMENTED",
        )

    async def reopen_ticket(
        self, ticket_id: str, reason: Optional[str] = None
    ) -> TicketResult:
        """Reopen a closed Linear issue."""
        logger.warning("Linear connector is a stub - reopen_ticket not implemented")
        return TicketResult(
            success=False,
            error_message="Linear connector not yet implemented",
            error_code="NOT_IMPLEMENTED",
        )
