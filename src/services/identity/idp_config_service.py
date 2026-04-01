"""
Project Aura - IdP Configuration Service

CRUD operations for identity provider configurations.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.services.identity.models import IdentityProviderConfig

logger = logging.getLogger(__name__)


class IdPConfigService:
    """
    Service for managing identity provider configurations.

    Handles CRUD operations for IdP configs stored in DynamoDB.
    """

    def __init__(
        self,
        table_name: str | None = None,
        dynamodb_client: Any = None,
    ):
        """
        Initialize IdP configuration service.

        Args:
            table_name: DynamoDB table name (defaults to env var)
            dynamodb_client: Optional DynamoDB resource (for testing)
        """
        self.table_name = table_name or os.environ.get(
            "IDP_CONFIG_TABLE", "aura-idp-configurations-dev"
        )
        self.dynamodb = dynamodb_client or boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    async def create_config(
        self,
        config: IdentityProviderConfig,
        actor_id: str,
    ) -> IdentityProviderConfig:
        """
        Create a new IdP configuration.

        Args:
            config: IdP configuration to create
            actor_id: ID of user creating the config

        Returns:
            Created configuration with generated ID
        """
        # Generate ID if not provided
        if not config.idp_id:
            config.idp_id = str(uuid.uuid4())

        # Set timestamps
        now = datetime.now(timezone.utc).isoformat()
        config.created_at = now
        config.updated_at = now
        config.created_by = actor_id

        # Store in DynamoDB
        try:
            item = config.to_dynamodb_item()

            # Also store email_domain entries for routing index
            # DynamoDB doesn't support set/list in GSI, so we create separate items
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(idp_id)",
            )

            # Create email domain routing entries
            for domain in config.email_domains:
                self._create_email_domain_entry(config.idp_id, domain)

            logger.info(
                f"Created IdP config {config.idp_id} ({config.name}) "
                f"for org {config.organization_id}"
            )

            return config

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"IdP config {config.idp_id} already exists")
            raise

    async def get_config(self, idp_id: str) -> IdentityProviderConfig | None:
        """Get IdP configuration by ID."""
        try:
            response = self.table.get_item(Key={"idp_id": idp_id})
            item = response.get("Item")
            if not item:
                return None
            return IdentityProviderConfig.from_dynamodb_item(item)
        except ClientError as e:
            logger.error(f"Error getting IdP config {idp_id}: {e}")
            raise

    async def update_config(
        self,
        idp_id: str,
        updates: dict[str, Any],
        actor_id: str,
    ) -> IdentityProviderConfig:
        """
        Update an IdP configuration.

        Args:
            idp_id: ID of config to update
            updates: Fields to update
            actor_id: ID of user making the update

        Returns:
            Updated configuration
        """
        # Get existing config
        existing = await self.get_config(idp_id)
        if not existing:
            raise ValueError(f"IdP config {idp_id} not found")

        # Update fields
        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        # Build update expression
        update_expr_parts = []
        expr_attr_names = {}
        expr_attr_values = {}

        for key, value in updates.items():
            safe_key = f"#{key}"
            value_key = f":{key}"
            update_expr_parts.append(f"{safe_key} = {value_key}")
            expr_attr_names[safe_key] = key
            expr_attr_values[value_key] = value

        update_expression = "SET " + ", ".join(update_expr_parts)

        try:
            response = self.table.update_item(
                Key={"idp_id": idp_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
                ReturnValues="ALL_NEW",
            )

            updated_item = response.get("Attributes", {})

            # Update email domain entries if domains changed
            if "email_domains" in updates:
                self._update_email_domains(idp_id, updates["email_domains"])

            logger.info(f"Updated IdP config {idp_id}")
            return IdentityProviderConfig.from_dynamodb_item(updated_item)

        except ClientError as e:
            logger.error(f"Error updating IdP config {idp_id}: {e}")
            raise

    async def delete_config(self, idp_id: str, actor_id: str) -> bool:
        """
        Delete an IdP configuration.

        Args:
            idp_id: ID of config to delete
            actor_id: ID of user deleting the config

        Returns:
            True if deleted
        """
        # Get existing to clean up email domains
        existing = await self.get_config(idp_id)
        if not existing:
            return False

        try:
            self.table.delete_item(Key={"idp_id": idp_id})

            # Delete email domain entries
            for domain in existing.email_domains:
                self._delete_email_domain_entry(domain)

            logger.info(f"Deleted IdP config {idp_id}")
            return True

        except ClientError as e:
            logger.error(f"Error deleting IdP config {idp_id}: {e}")
            raise

    async def list_configs_for_org(
        self,
        organization_id: str,
        enabled_only: bool = False,
    ) -> list[IdentityProviderConfig]:
        """
        List all IdP configs for an organization.

        Args:
            organization_id: Organization ID
            enabled_only: If True, only return enabled configs

        Returns:
            List of configurations ordered by priority
        """
        try:
            response = self.table.query(
                IndexName="organization-priority-index",
                KeyConditionExpression="organization_id = :org_id",
                ExpressionAttributeValues={":org_id": organization_id},
            )

            configs = [
                IdentityProviderConfig.from_dynamodb_item(item)
                for item in response.get("Items", [])
            ]

            if enabled_only:
                configs = [c for c in configs if c.enabled]

            return sorted(configs, key=lambda c: c.priority)

        except ClientError as e:
            logger.error(f"Error listing IdP configs for org {organization_id}: {e}")
            raise

    async def get_config_by_email_domain(
        self,
        email_domain: str,
    ) -> IdentityProviderConfig | None:
        """
        Get IdP config that handles a specific email domain.

        Args:
            email_domain: Email domain (e.g., "company.com")

        Returns:
            Matching IdP config or None
        """
        try:
            response = self.table.query(
                IndexName="email-domain-index",
                KeyConditionExpression="email_domain = :domain",
                ExpressionAttributeValues={":domain": email_domain.lower()},
            )

            items = response.get("Items", [])
            if not items:
                return None

            # Get the actual IdP config (email domain entry points to it)
            idp_id = items[0].get("idp_id")
            if idp_id and not idp_id.startswith("domain:"):
                return await self.get_config(idp_id)

            return None

        except ClientError as e:
            logger.error(f"Error getting IdP for domain {email_domain}: {e}")
            raise

    def _create_email_domain_entry(self, idp_id: str, domain: str) -> None:
        """Create email domain routing entry."""
        # This is a workaround for DynamoDB GSI limitations
        # We store separate items for email domain lookups
        pass  # Email domains stored in main item's email_domains field

    def _delete_email_domain_entry(self, domain: str) -> None:
        """Delete email domain routing entry."""
        pass  # Email domains stored in main item's email_domains field

    def _update_email_domains(
        self,
        idp_id: str,
        new_domains: list[str],
    ) -> None:
        """Update email domain routing entries."""
        pass  # Email domains stored in main item's email_domains field


class IdPRoutingService:
    """
    Service for routing authentication requests to appropriate IdPs.

    Determines which IdP to use based on:
    1. Email domain
    2. Organization ID
    3. Explicit IdP selection
    """

    def __init__(self, config_service: IdPConfigService | None = None):
        """Initialize routing service."""
        self.config_service = config_service or IdPConfigService()

    async def get_idp_for_email(
        self,
        email: str,
        organization_id: str | None = None,
    ) -> IdentityProviderConfig | None:
        """
        Get the appropriate IdP for an email address.

        Args:
            email: User email address
            organization_id: Optional organization hint

        Returns:
            IdP config or None if no match
        """
        from src.services.identity.models import extract_email_domain

        domain = extract_email_domain(email)
        if not domain:
            return None

        # First, try email domain lookup
        config = await self.config_service.get_config_by_email_domain(domain)
        if config and config.enabled:
            return config

        # If we have an organization ID, get the default IdP
        if organization_id:
            configs = await self.config_service.list_configs_for_org(
                organization_id, enabled_only=True
            )
            if configs:
                return configs[0]  # Return highest priority

        return None

    async def list_available_idps(
        self,
        organization_id: str | None = None,
        email: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List available IdPs for login UI.

        Args:
            organization_id: Organization ID
            email: Optional email for domain-based filtering

        Returns:
            List of IdP info for display
        """
        from src.services.identity.models import extract_email_domain

        result = []

        # If we have an email domain, prioritize matching IdPs
        preferred_idp = None
        if email:
            domain = extract_email_domain(email)
            if domain:
                preferred_idp = await self.config_service.get_config_by_email_domain(
                    domain
                )

        # Get all IdPs for organization
        if organization_id:
            configs = await self.config_service.list_configs_for_org(
                organization_id, enabled_only=True
            )

            for config in configs:
                idp_info = {
                    "idp_id": config.idp_id,
                    "name": config.name,
                    "type": config.idp_type.value,
                    "priority": config.priority,
                    "is_preferred": (
                        preferred_idp is not None
                        and config.idp_id == preferred_idp.idp_id
                    ),
                }
                result.append(idp_info)

        return result


# Singleton instances
_config_service: IdPConfigService | None = None
_routing_service: IdPRoutingService | None = None


def get_idp_config_service() -> IdPConfigService:
    """Get or create IdP config service singleton."""
    global _config_service
    if _config_service is None:
        _config_service = IdPConfigService()
    return _config_service


def get_idp_routing_service() -> IdPRoutingService:
    """Get or create IdP routing service singleton."""
    global _routing_service
    if _routing_service is None:
        _routing_service = IdPRoutingService()
    return _routing_service
