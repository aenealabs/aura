"""
Project Aura - Secrets Service Abstraction

Abstract interface for secrets management.
Implementations: AWS Secrets Manager, Azure Key Vault

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Secret:
    """Represents a secret in the secrets manager."""

    name: str
    value: str | dict[str, Any]  # String or JSON object
    version_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    description: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def is_json(self) -> bool:
        """Check if the secret value is a JSON object."""
        return isinstance(self.value, dict)

    def get_value(self, key: str | None = None) -> Any:
        """
        Get secret value or specific key from JSON secret.

        Args:
            key: Optional key for JSON secrets

        Returns:
            Secret value or specific key value
        """
        if key and isinstance(self.value, dict):
            return self.value.get(key)
        return self.value


@dataclass
class SecretRotationConfig:
    """Configuration for automatic secret rotation."""

    rotation_enabled: bool = False
    rotation_lambda_arn: str | None = None  # AWS-specific
    rotation_days: int = 30
    next_rotation_date: datetime | None = None


class SecretsService(ABC):
    """
    Abstract interface for secrets management.

    Implementations:
    - AWS: SecretsManagerService
    - Azure: KeyVaultSecretsService
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Initialize secrets client."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up resources."""

    # Secret Operations
    @abstractmethod
    async def create_secret(
        self,
        name: str,
        value: str | dict[str, Any],
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Secret:
        """
        Create a new secret.

        Args:
            name: Secret name/identifier
            value: Secret value (string or JSON)
            description: Optional description
            tags: Optional tags for organization

        Returns:
            The created secret
        """

    @abstractmethod
    async def get_secret(
        self,
        name: str,
        version_id: str | None = None,
    ) -> Secret | None:
        """
        Get a secret by name.

        Args:
            name: Secret name
            version_id: Optional specific version

        Returns:
            The secret if found
        """

    @abstractmethod
    async def get_secret_value(
        self,
        name: str,
        key: str | None = None,
    ) -> str | Any | None:
        """
        Get secret value directly.

        Args:
            name: Secret name
            key: Optional key for JSON secrets

        Returns:
            The secret value
        """

    @abstractmethod
    async def update_secret(
        self,
        name: str,
        value: str | dict[str, Any],
    ) -> Secret:
        """
        Update an existing secret.

        Args:
            name: Secret name
            value: New secret value

        Returns:
            The updated secret with new version
        """

    @abstractmethod
    async def delete_secret(
        self,
        name: str,
        force: bool = False,
        recovery_window_days: int = 30,
    ) -> bool:
        """
        Delete a secret.

        Args:
            name: Secret name
            force: Immediately delete without recovery window
            recovery_window_days: Days before permanent deletion

        Returns:
            True if deleted successfully
        """

    @abstractmethod
    async def restore_secret(self, name: str) -> bool:
        """
        Restore a deleted secret within recovery window.

        Args:
            name: Secret name

        Returns:
            True if restored successfully
        """

    @abstractmethod
    async def secret_exists(self, name: str) -> bool:
        """Check if a secret exists."""

    @abstractmethod
    async def list_secrets(
        self,
        prefix: str | None = None,
        max_results: int = 100,
    ) -> list[str]:
        """
        List secret names.

        Args:
            prefix: Optional name prefix filter
            max_results: Maximum results to return

        Returns:
            List of secret names
        """

    # Version Management
    @abstractmethod
    async def list_secret_versions(
        self,
        name: str,
        max_versions: int = 10,
    ) -> list[dict[str, Any]]:
        """
        List versions of a secret.

        Args:
            name: Secret name
            max_versions: Maximum versions to return

        Returns:
            List of version info dicts
        """

    # Rotation
    @abstractmethod
    async def configure_rotation(
        self,
        name: str,
        config: SecretRotationConfig,
    ) -> bool:
        """
        Configure automatic rotation for a secret.

        Args:
            name: Secret name
            config: Rotation configuration

        Returns:
            True if configured successfully
        """

    @abstractmethod
    async def rotate_secret_immediately(self, name: str) -> Secret:
        """
        Trigger immediate rotation of a secret.

        Args:
            name: Secret name

        Returns:
            The rotated secret with new version
        """

    # Health
    @abstractmethod
    async def get_health(self) -> dict[str, Any]:
        """Get secrets service health status."""
