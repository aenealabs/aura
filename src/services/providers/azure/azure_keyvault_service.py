"""
Project Aura - Azure Key Vault Service

Azure Key Vault implementation of SecretsService.
Provides secrets management for Azure Government deployments.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from src.abstractions.secrets_service import (
    Secret,
    SecretRotationConfig,
    SecretsService,
)

logger = logging.getLogger(__name__)

# Optional Azure dependencies
try:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    AZURE_KEYVAULT_AVAILABLE = True
except ImportError:
    AZURE_KEYVAULT_AVAILABLE = False
    logger.warning("Azure Key Vault SDK not available - using mock mode")


class AzureKeyVaultService(SecretsService):
    """
    Azure Key Vault implementation for secrets management.

    Compatible with Azure Government regions.
    """

    def __init__(
        self,
        vault_url: str | None = None,
    ):
        self.vault_url = vault_url or os.environ.get("AZURE_KEYVAULT_URL")
        self._client: "SecretClient | None" = None
        self._connected = False

        # Mock storage
        self._mock_secrets: dict[str, dict[str, Any]] = {}

    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return not AZURE_KEYVAULT_AVAILABLE or not self.vault_url

    async def connect(self) -> bool:
        """Connect to Key Vault."""
        if self.is_mock_mode:
            logger.info("Azure Key Vault running in mock mode")
            self._connected = True
            return True

        try:
            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self.vault_url, credential=credential)
            self._connected = True
            logger.info(f"Connected to Azure Key Vault: {self.vault_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Key Vault: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect."""
        self._connected = False
        self._client = None

    async def create_secret(
        self,
        name: str,
        value: str | dict[str, Any],
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Secret:
        """Create a secret."""
        secret_value = json.dumps(value) if isinstance(value, dict) else value

        if self.is_mock_mode:
            self._mock_secrets[name] = {
                "value": value,
                "description": description,
                "tags": tags or {},
                "created_at": datetime.now(timezone.utc),
                "version": "1",
            }
            return Secret(
                name=name,
                value=value,
                version_id="1",
                created_at=datetime.now(timezone.utc),
                description=description,
                tags=tags or {},
            )

        if self._client is None:
            raise RuntimeError("Azure Key Vault client not initialized")

        secret = self._client.set_secret(
            name,
            secret_value,
            content_type=(
                "application/json" if isinstance(value, dict) else "text/plain"
            ),
            tags=tags,
        )

        return Secret(
            name=name,
            value=value,
            version_id=secret.properties.version,
            created_at=secret.properties.created_on,
            description=description,
            tags=tags or {},
        )

    async def get_secret(
        self,
        name: str,
        version_id: str | None = None,
    ) -> Secret | None:
        """Get a secret."""
        if self.is_mock_mode:
            data = self._mock_secrets.get(name)
            if data:
                return Secret(
                    name=name,
                    value=data["value"],
                    version_id=data.get("version", "1"),
                    created_at=data.get("created_at"),
                    updated_at=data.get("updated_at"),
                    description=data.get("description"),
                    tags=data.get("tags", {}),
                )
            return None

        if self._client is None:
            raise RuntimeError("Azure Key Vault client not initialized")

        try:
            secret = self._client.get_secret(name, version_id)

            secret_value = secret.value
            if secret.properties.content_type == "application/json":
                try:
                    secret_value = json.loads(secret_value)
                except json.JSONDecodeError:
                    pass

            return Secret(
                name=name,
                value=secret_value,
                version_id=secret.properties.version,
                created_at=secret.properties.created_on,
                updated_at=secret.properties.updated_on,
                tags=secret.properties.tags or {},
            )
        except Exception as e:
            if "SecretNotFound" in str(e):
                return None
            raise

    async def get_secret_value(
        self,
        name: str,
        key: str | None = None,
    ) -> str | Any | None:
        """Get secret value."""
        secret = await self.get_secret(name)
        if secret is None:
            return None

        if key and isinstance(secret.value, dict):
            return secret.value.get(key)
        return secret.value

    async def update_secret(
        self,
        name: str,
        value: str | dict[str, Any],
    ) -> Secret:
        """Update a secret."""
        secret_value = json.dumps(value) if isinstance(value, dict) else value

        if self.is_mock_mode:
            if name in self._mock_secrets:
                self._mock_secrets[name]["value"] = value
                self._mock_secrets[name]["updated_at"] = datetime.now(timezone.utc)
                version = str(int(self._mock_secrets[name].get("version", "1")) + 1)
                self._mock_secrets[name]["version"] = version
            return Secret(
                name=name,
                value=value,
                version_id=self._mock_secrets.get(name, {}).get("version", "1"),
                updated_at=datetime.now(timezone.utc),
            )

        if self._client is None:
            raise RuntimeError("Azure Key Vault client not initialized")

        secret = self._client.set_secret(
            name,
            secret_value,
            content_type=(
                "application/json" if isinstance(value, dict) else "text/plain"
            ),
        )

        return Secret(
            name=name,
            value=value,
            version_id=secret.properties.version,
            updated_at=secret.properties.updated_on,
        )

    async def delete_secret(
        self,
        name: str,
        force: bool = False,
        recovery_window_days: int = 30,
    ) -> bool:
        """Delete a secret."""
        if self.is_mock_mode:
            if name in self._mock_secrets:
                del self._mock_secrets[name]
                return True
            return False

        if self._client is None:
            raise RuntimeError("Azure Key Vault client not initialized")

        try:
            poller = self._client.begin_delete_secret(name)
            poller.wait()

            if force:
                self._client.purge_deleted_secret(name)

            return True
        except Exception as e:
            logger.error(f"Failed to delete secret: {e}")
            return False

    async def restore_secret(self, name: str) -> bool:
        """Restore a deleted secret."""
        if self.is_mock_mode:
            return False

        if self._client is None:
            raise RuntimeError("Azure Key Vault client not initialized")

        try:
            self._client.begin_recover_deleted_secret(name).wait()
            return True
        except Exception as e:
            logger.error(f"Failed to restore secret: {e}")
            return False

    async def secret_exists(self, name: str) -> bool:
        """Check if secret exists."""
        return await self.get_secret(name) is not None

    async def list_secrets(
        self,
        prefix: str | None = None,
        max_results: int = 100,
    ) -> list[str]:
        """List secret names."""
        if self.is_mock_mode:
            secrets = list(self._mock_secrets.keys())
            if prefix:
                secrets = [s for s in secrets if s.startswith(prefix)]
            return secrets[:max_results]

        if self._client is None:
            raise RuntimeError("Azure Key Vault client not initialized")

        secrets = []
        for secret_properties in self._client.list_properties_of_secrets():
            if prefix and not secret_properties.name.startswith(prefix):
                continue
            secrets.append(secret_properties.name)
            if len(secrets) >= max_results:
                break

        return secrets

    async def list_secret_versions(
        self,
        name: str,
        max_versions: int = 10,
    ) -> list[dict[str, Any]]:
        """List secret versions."""
        if self.is_mock_mode:
            data = self._mock_secrets.get(name, {})
            return [
                {
                    "version_id": data.get("version", "1"),
                    "created_date": data.get("created_at"),
                }
            ]

        if self._client is None:
            raise RuntimeError("Azure Key Vault client not initialized")

        versions = []
        for version in self._client.list_properties_of_secret_versions(name):
            versions.append(
                {
                    "version_id": version.version,
                    "created_date": version.created_on,
                    "enabled": version.enabled,
                }
            )
            if len(versions) >= max_versions:
                break

        return versions

    async def configure_rotation(
        self,
        name: str,
        config: SecretRotationConfig,
    ) -> bool:
        """Configure rotation (not natively supported in Key Vault)."""
        logger.warning(
            "Azure Key Vault does not natively support automatic rotation configuration"
        )
        return False

    async def rotate_secret_immediately(self, name: str) -> Secret:
        """Rotate secret (manual rotation)."""
        secret = await self.get_secret(name)
        if secret:
            # For manual rotation, just update with same value (version increment)
            return await self.update_secret(name, secret.value)
        raise ValueError(f"Secret {name} not found")

    async def get_health(self) -> dict[str, Any]:
        """Get health status."""
        return {
            "status": "healthy" if self._connected else "disconnected",
            "mode": "mock" if self.is_mock_mode else "azure",
            "vault_url": self.vault_url,
        }
