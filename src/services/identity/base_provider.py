"""
Project Aura - Base Identity Provider

Abstract base class defining the interface for all identity providers.
Each IdP type (LDAP, SAML, OIDC, etc.) implements this interface.

Author: Project Aura Team
Created: 2026-01-06
Version: 1.0.0
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.services.identity.models import (
    VALID_AURA_ROLES,
    AuthCredentials,
    AuthResult,
    ConnectionStatus,
    HealthCheckResult,
    IdentityProviderConfig,
    TokenResult,
    TokenValidationResult,
    UserInfo,
)

logger = logging.getLogger(__name__)


class IdentityProviderError(Exception):
    """Base exception for identity provider errors."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class AttributeMappingError(IdentityProviderError):
    """Error mapping IdP attributes to Aura attributes."""


class AuthenticationError(IdentityProviderError):
    """Authentication failed."""


class ConfigurationError(IdentityProviderError):
    """IdP configuration error."""


class ConnectionError(IdentityProviderError):
    """Cannot connect to IdP."""


class IdentityProvider(ABC):
    """
    Abstract base class for identity providers.

    All IdP implementations must inherit from this class and implement
    the abstract methods for their specific protocol (LDAP, SAML, OIDC, etc.).

    The base class provides common functionality:
    - Attribute mapping (IdP claims -> Aura user fields)
    - Group to role mapping (IdP groups -> Aura roles)
    - Health check result standardization
    - Metrics and logging
    """

    def __init__(self, config: IdentityProviderConfig):
        """
        Initialize identity provider.

        Args:
            config: Provider configuration from database
        """
        self.config = config
        self.idp_id = config.idp_id
        self.name = config.name
        self.idp_type = config.idp_type
        self.organization_id = config.organization_id

        # Connection state
        self._status = ConnectionStatus.DISCONNECTED
        self._last_error: str | None = None

        # Metrics
        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

    @property
    def status(self) -> ConnectionStatus:
        """Get current connection status."""
        return self._status

    @property
    def metrics(self) -> dict[str, Any]:
        """Get provider metrics."""
        return {
            "idp_id": self.idp_id,
            "name": self.name,
            "type": self.idp_type.value,
            "status": self._status.value,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count
                if self._request_count > 0
                else 0
            ),
            "last_error": self._last_error,
        }

    # =========================================================================
    # Abstract Methods - Must be implemented by each provider
    # =========================================================================

    @abstractmethod
    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        """
        Authenticate user with provider-specific credentials.

        Args:
            credentials: Authentication credentials (type depends on provider)

        Returns:
            AuthResult with success status, user info, and mapped roles
        """

    @abstractmethod
    async def validate_token(self, token: str) -> TokenValidationResult:
        """
        Validate an existing token from this provider.

        Args:
            token: Token to validate (JWT, SAML assertion, etc.)

        Returns:
            TokenValidationResult with validity status and claims
        """

    @abstractmethod
    async def get_user_info(self, token: str) -> UserInfo:
        """
        Get user information from the provider.

        Args:
            token: Valid access token

        Returns:
            UserInfo with user details
        """

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> TokenResult:
        """
        Refresh an expired access token.

        Args:
            refresh_token: Refresh token

        Returns:
            TokenResult with new tokens

        Raises:
            AuthenticationError: If refresh is not supported or fails
        """

    @abstractmethod
    async def logout(self, token: str) -> bool:
        """
        Logout user and revoke token if supported.

        Args:
            token: Token to revoke

        Returns:
            True if logout succeeded
        """

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """
        Check provider connectivity and health.

        Returns:
            HealthCheckResult with status and details
        """

    # =========================================================================
    # Common Methods - Shared across all providers
    # =========================================================================

    def map_attributes(self, provider_claims: dict[str, Any]) -> dict[str, Any]:
        """
        Map provider claims/attributes to Aura user attributes.

        Uses the attribute_mappings from configuration to transform
        IdP-specific claims to Aura's standard user model.

        Args:
            provider_claims: Raw claims from the identity provider

        Returns:
            Dictionary of mapped Aura user attributes

        Raises:
            AttributeMappingError: If a required attribute is missing
        """
        result: dict[str, Any] = {}
        mappings = self.config.attribute_mappings

        # Use defaults if no mappings configured
        if not mappings:
            mappings = self.config.get_default_attribute_mappings()

        for mapping in mappings:
            value = self._get_nested_value(provider_claims, mapping.source_attribute)

            if value is not None:
                # Apply transform if specified
                if mapping.transform:
                    value = self._apply_transform(value, mapping.transform)
                result[mapping.target_attribute] = value

            elif mapping.required:
                raise AttributeMappingError(
                    f"Required attribute '{mapping.source_attribute}' not found in IdP response",
                    error_code="MISSING_REQUIRED_ATTRIBUTE",
                )

            elif mapping.default_value is not None:
                result[mapping.target_attribute] = mapping.default_value

        logger.debug(
            f"Mapped {len(result)} attributes for IdP {self.idp_id}: "
            f"{list(result.keys())}"
        )
        return result

    def map_groups_to_roles(self, provider_groups: list[str]) -> list[str]:
        """
        Map provider groups to Aura roles.

        Uses group_mappings from configuration to convert IdP group
        memberships to Aura's role-based access control.

        Args:
            provider_groups: List of group names/DNs from IdP

        Returns:
            List of Aura roles (admin, security-engineer, developer, viewer)
        """
        if not provider_groups:
            return ["viewer"]  # Default role

        roles: set[str] = set()
        matched_mappings: list[tuple[int, str]] = []

        # Sort mappings by priority (lower = higher priority)
        sorted_mappings = sorted(self.config.group_mappings, key=lambda m: m.priority)

        for group in provider_groups:
            for mapping in sorted_mappings:
                if mapping.matches(group):
                    matched_mappings.append((mapping.priority, mapping.target_role))

        # Add roles from highest priority first (priority used for sorting only)
        for _priority, role in sorted(matched_mappings, key=lambda x: x[0]):
            if role in VALID_AURA_ROLES:
                roles.add(role)

        if not roles:
            roles.add("viewer")  # Default role if no mappings match

        logger.debug(
            f"Mapped {len(provider_groups)} groups to roles {list(roles)} "
            f"for IdP {self.idp_id}"
        )
        return list(roles)

    def _get_nested_value(self, data: dict[str, Any], key: str) -> Any:
        """
        Get value from nested dictionary using dot notation.

        Example: "user.profile.email" -> data["user"]["profile"]["email"]
        """
        keys = key.split(".")
        value = data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None

            if value is None:
                return None

        return value

    def _apply_transform(self, value: Any, transform: str) -> Any:
        """
        Apply transformation to attribute value.

        Supported transforms:
        - lowercase: Convert to lowercase
        - uppercase: Convert to uppercase
        - split: Split comma-separated string to list
        - join: Join list to comma-separated string
        - first: Get first element of list
        - trim: Remove whitespace
        - strip_domain: Remove @domain from email
        """
        if value is None:
            return None

        transform = transform.lower()

        if transform == "lowercase":
            return str(value).lower() if value else value

        elif transform == "uppercase":
            return str(value).upper() if value else value

        elif transform == "split":
            if isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            return value

        elif transform == "join":
            if isinstance(value, list):
                return ",".join(str(v) for v in value)
            return value

        elif transform == "first":
            if isinstance(value, (list, tuple)) and value:
                return value[0]
            return value

        elif transform == "trim":
            return str(value).strip() if value else value

        elif transform == "strip_domain":
            if isinstance(value, str) and "@" in value:
                return value.split("@")[0]
            return value

        else:
            logger.warning(f"Unknown transform '{transform}', returning value as-is")
            return value

    def _flatten_ldap_attrs(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Flatten LDAP attributes that come as lists.

        LDAP attributes are often returned as lists even for single values.
        This flattens single-element lists to their value.
        """
        result = {}
        for key, value in attrs.items():
            if isinstance(value, (list, set)):
                if len(value) == 1:
                    result[key] = list(value)[0]
                else:
                    result[key] = list(value)
            else:
                result[key] = value
        return result

    def _record_request(self, latency_ms: float, success: bool) -> None:
        """Record request metrics."""
        self._request_count += 1
        self._total_latency_ms += latency_ms
        if not success:
            self._error_count += 1

    def _set_status(self, status: ConnectionStatus, error: str | None = None) -> None:
        """Update connection status."""
        self._status = status
        if error:
            self._last_error = error


class IdentityProviderFactory:
    """Factory for creating identity provider instances."""

    _providers: dict[str, type] = {}

    @classmethod
    def register(cls, idp_type: str, provider_class: type) -> None:
        """Register a provider class for an IdP type."""
        cls._providers[idp_type.lower()] = provider_class

    @classmethod
    def create(cls, config: IdentityProviderConfig) -> IdentityProvider:
        """
        Create an identity provider from configuration.

        Args:
            config: Provider configuration

        Returns:
            Configured IdentityProvider instance

        Raises:
            ValueError: If IdP type is not registered
        """
        idp_type = config.idp_type.value

        if idp_type not in cls._providers:
            raise ValueError(
                f"Unknown IdP type: {idp_type}. "
                f"Registered types: {list(cls._providers.keys())}"
            )

        provider_class = cls._providers[idp_type]
        return provider_class(config)

    @classmethod
    def available_providers(cls) -> list[str]:
        """Get list of registered provider types."""
        return list(cls._providers.keys())
