"""
Project Aura - PingID/PingFederate Identity Provider

Implements PingIdentity authentication for enterprise customers using PingFederate.
Built on top of OIDC with PingIdentity-specific extensions.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import logging

from src.services.identity.base_provider import (
    ConfigurationError,
    IdentityProviderFactory,
)
from src.services.identity.models import IdentityProviderConfig, IdPType
from src.services.identity.providers.oidc_provider import OIDCProvider

logger = logging.getLogger(__name__)


class PingIDProvider(OIDCProvider):
    """
    PingID/PingFederate identity provider.

    Extends OIDCProvider with PingIdentity-specific configurations
    and endpoints.

    Connection Settings (config.connection_settings):
        pingfederate_url: str - PingFederate base URL
        client_id: str - OAuth client ID
        connection_id: str - PingFederate connection ID
        acr_values: str - Authentication Context Class Reference
        scopes: list[str] - OAuth scopes (default includes PingID-specific)

    Credentials (from Secrets Manager):
        client_secret: str - OAuth client secret
    """

    def __init__(self, config: IdentityProviderConfig):
        """Initialize PingID provider."""
        # Override IdP type check since we accept PINGID
        if config.idp_type != IdPType.PINGID:
            raise ConfigurationError(
                f"Invalid IdP type for PingIDProvider: {config.idp_type}"
            )

        conn = config.connection_settings

        # Derive OIDC settings from PingFederate configuration
        pingfederate_url = conn.get("pingfederate_url")
        if not pingfederate_url:
            raise ConfigurationError("PingFederate URL is required")

        # Build issuer from PingFederate URL
        issuer = pingfederate_url.rstrip("/")

        # Update connection settings for OIDC base class
        oidc_conn = {
            "issuer": issuer,
            "client_id": conn.get("client_id"),
            "redirect_uri": conn.get(
                "redirect_uri", "https://api.aenealabs.com/auth/pingid/callback"
            ),
            "scopes": conn.get("scopes", ["openid", "profile", "email"]),
            "use_pkce": conn.get("use_pkce", True),
            "additional_params": {},
        }

        # Add PingFederate-specific parameters
        if conn.get("connection_id"):
            oidc_conn["additional_params"]["pfidpadapterid"] = conn["connection_id"]

        if conn.get("acr_values"):
            oidc_conn["additional_params"]["acr_values"] = conn["acr_values"]

        # Create modified config for parent class
        modified_config = IdentityProviderConfig(
            idp_id=config.idp_id,
            organization_id=config.organization_id,
            idp_type=IdPType.OIDC,  # Use OIDC for parent class
            name=config.name,
            enabled=config.enabled,
            priority=config.priority,
            connection_settings=oidc_conn,
            credentials_secret_arn=config.credentials_secret_arn,
            certificate_settings=config.certificate_settings,
            attribute_mappings=config.attribute_mappings,
            group_mappings=config.group_mappings,
            email_domains=config.email_domains,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
        )

        # Initialize OIDC parent
        super().__init__(modified_config)

        # Store original config for reference
        self._original_config = config
        self.idp_type = IdPType.PINGID
        self.pingfederate_url = pingfederate_url
        self.connection_id = conn.get("connection_id")

        logger.info(f"Initialized PingID provider for {pingfederate_url}")


# Register provider with factory
IdentityProviderFactory.register("pingid", PingIDProvider)
