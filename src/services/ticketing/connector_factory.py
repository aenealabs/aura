"""
Ticketing Connector Factory.

Factory pattern for creating ticketing connector instances based on
provider configuration stored in DynamoDB and Secrets Manager.
See ADR-046 for architecture details.
"""

import logging
from enum import Enum
from typing import Any, Dict, Optional

from .base_connector import TicketingConnector
from .github_connector import GitHubIssuesConnector
from .linear_connector import LinearConnector
from .servicenow_connector import ServiceNowTicketConnector
from .zendesk_connector import ZendeskConnector

logger = logging.getLogger(__name__)


class TicketingProvider(Enum):
    """Supported ticketing providers."""

    GITHUB = "github"
    ZENDESK = "zendesk"
    LINEAR = "linear"
    SERVICENOW = "servicenow"


# Provider metadata for UI display
PROVIDER_METADATA = {
    TicketingProvider.GITHUB: {
        "name": "GitHub Issues",
        "description": "Free, open-source issue tracking built into GitHub",
        "icon": "github",
        "is_implemented": True,
        "config_fields": [
            {
                "name": "repository",
                "label": "Repository",
                "type": "text",
                "placeholder": "owner/repo",
                "required": True,
            },
            {
                "name": "token",
                "label": "Personal Access Token",
                "type": "password",
                "required": True,
            },
            {
                "name": "default_labels",
                "label": "Default Labels",
                "type": "tags",
                "required": False,
            },
        ],
    },
    TicketingProvider.ZENDESK: {
        "name": "Zendesk",
        "description": "Enterprise customer service platform (coming soon)",
        "icon": "zendesk",
        "is_implemented": False,
        "config_fields": [
            {
                "name": "subdomain",
                "label": "Subdomain",
                "type": "text",
                "placeholder": "yourcompany",
                "required": True,
            },
            {
                "name": "email",
                "label": "Agent Email",
                "type": "email",
                "required": True,
            },
            {
                "name": "api_token",
                "label": "API Token",
                "type": "password",
                "required": True,
            },
        ],
    },
    TicketingProvider.LINEAR: {
        "name": "Linear",
        "description": "Modern issue tracking for engineering teams (coming soon)",
        "icon": "linear",
        "is_implemented": False,
        "config_fields": [
            {
                "name": "api_key",
                "label": "API Key",
                "type": "password",
                "required": True,
            },
            {"name": "team_id", "label": "Team ID", "type": "text", "required": True},
            {
                "name": "project_id",
                "label": "Default Project ID",
                "type": "text",
                "required": False,
            },
        ],
    },
    TicketingProvider.SERVICENOW: {
        "name": "ServiceNow",
        "description": "Enterprise IT service management (coming soon)",
        "icon": "servicenow",
        "is_implemented": False,
        "config_fields": [
            {
                "name": "instance_url",
                "label": "Instance URL",
                "type": "url",
                "placeholder": "https://dev12345.service-now.com",
                "required": True,
            },
            {"name": "username", "label": "Username", "type": "text", "required": True},
            {
                "name": "password",
                "label": "Password",
                "type": "password",
                "required": True,
            },
            {
                "name": "table",
                "label": "Table",
                "type": "select",
                "options": ["incident", "sc_request", "problem"],
                "required": True,
            },
        ],
    },
}


class TicketingConnectorFactory:
    """
    Factory for creating ticketing connector instances.

    Manages connector configuration and credential retrieval from
    DynamoDB and Secrets Manager.

    Usage:
        factory = TicketingConnectorFactory()
        connector = await factory.get_connector(customer_id="cust-123")
        result = await connector.create_ticket(...)
    """

    def __init__(self) -> None:
        """Initialize the connector factory."""
        self._connectors: Dict[str, TicketingConnector] = {}
        logger.info("TicketingConnectorFactory initialized")

    @staticmethod
    def get_provider_metadata() -> Dict[str, Any]:
        """
        Get metadata for all providers for UI display.

        Returns:
            Dict with provider information including name, description,
            implementation status, and configuration fields.
        """
        return {
            provider.value: metadata for provider, metadata in PROVIDER_METADATA.items()
        }

    @staticmethod
    def get_implemented_providers() -> list:
        """Get list of fully implemented providers."""
        return [
            provider.value
            for provider, metadata in PROVIDER_METADATA.items()
            if metadata["is_implemented"]
        ]

    async def get_connector(
        self,
        customer_id: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[TicketingConnector]:
        """
        Get or create a ticketing connector for a customer.

        Args:
            customer_id: Customer identifier
            config: Optional explicit configuration (overrides stored config)

        Returns:
            Configured TicketingConnector instance or None if not configured
        """
        # Check cache first
        cache_key = customer_id
        if cache_key in self._connectors:
            return self._connectors[cache_key]

        # Get configuration
        if config is None:
            config = await self._get_customer_config(customer_id)

        if config is None:
            logger.warning(
                f"No ticketing configuration found for customer {customer_id}"
            )
            return None

        # Create connector based on provider
        provider = config.get("provider")
        if not provider or not isinstance(provider, str):
            logger.error(
                f"Invalid or missing provider in config for customer {customer_id}"
            )
            return None

        connector = await self._create_connector(provider, config)

        if connector:
            self._connectors[cache_key] = connector

        return connector

    async def _get_customer_config(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve ticketing configuration for a customer from DynamoDB.

        In production, this would query the aura-ticketing-config table
        and retrieve credentials from Secrets Manager.
        """
        # TODO: Implement DynamoDB lookup
        # For now, return None to indicate no configuration
        logger.debug(f"Looking up ticketing config for customer {customer_id}")
        return None

    async def _create_connector(
        self,
        provider: str,
        config: Dict[str, Any],
    ) -> Optional[TicketingConnector]:
        """Create a connector instance for the given provider."""
        try:
            if provider == TicketingProvider.GITHUB.value:
                return GitHubIssuesConnector(
                    repository=config["repository"],
                    token=config["token"],
                    api_url=config.get("api_url", "https://api.github.com"),
                    default_labels=config.get("default_labels"),
                    default_assignees=config.get("default_assignees"),
                )
            elif provider == TicketingProvider.ZENDESK.value:
                return ZendeskConnector(
                    subdomain=config["subdomain"],
                    email=config["email"],
                    api_token=config["api_token"],
                )
            elif provider == TicketingProvider.LINEAR.value:
                return LinearConnector(
                    api_key=config["api_key"],
                    team_id=config["team_id"],
                    project_id=config.get("project_id"),
                )
            elif provider == TicketingProvider.SERVICENOW.value:
                return ServiceNowTicketConnector(
                    instance_url=config["instance_url"],
                    username=config["username"],
                    password=config["password"],
                    table=config.get("table", "incident"),
                )
            else:
                logger.error(f"Unknown ticketing provider: {provider}")
                return None
        except KeyError as e:
            logger.error(f"Missing required configuration field: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error creating {provider} connector: {e}")
            return None

    def clear_cache(self, customer_id: Optional[str] = None) -> None:
        """
        Clear cached connectors.

        Args:
            customer_id: Optional customer ID to clear specific cache.
                        If None, clears all cached connectors.
        """
        if customer_id:
            self._connectors.pop(customer_id, None)
        else:
            self._connectors.clear()
        logger.info(f"Cleared connector cache for: {customer_id or 'all'}")


# Module-level factory instance
_factory: Optional[TicketingConnectorFactory] = None


def get_ticketing_connector_factory() -> TicketingConnectorFactory:
    """Get the singleton factory instance."""
    global _factory
    if _factory is None:
        _factory = TicketingConnectorFactory()
    return _factory


async def get_ticketing_connector(
    customer_id: str,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[TicketingConnector]:
    """
    Convenience function to get a ticketing connector for a customer.

    Args:
        customer_id: Customer identifier
        config: Optional explicit configuration

    Returns:
        Configured TicketingConnector instance or None
    """
    factory = get_ticketing_connector_factory()
    return await factory.get_connector(customer_id, config)
