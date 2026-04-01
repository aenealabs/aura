"""
Project Aura - Mock Secrets Service

In-memory mock implementation of SecretsService for testing.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.abstractions.secrets_service import (
    Secret,
    SecretRotationConfig,
    SecretsService,
)

logger = logging.getLogger(__name__)


class MockSecretsService(SecretsService):
    """Mock secrets service for testing."""

    def __init__(self) -> None:
        self._secrets: dict[str, dict[str, Any]] = {}
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        logger.info("MockSecretsService connected")
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def create_secret(
        self,
        name: str,
        value: str | dict[str, Any],
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Secret:
        self._secrets[name] = {
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

    async def get_secret(
        self,
        name: str,
        version_id: str | None = None,
    ) -> Secret | None:
        data = self._secrets.get(name)
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

    async def get_secret_value(
        self,
        name: str,
        key: str | None = None,
    ) -> str | Any | None:
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
        if name in self._secrets:
            self._secrets[name]["value"] = value
            self._secrets[name]["updated_at"] = datetime.now(timezone.utc)
            version = str(int(self._secrets[name].get("version", "1")) + 1)
            self._secrets[name]["version"] = version
        else:
            return await self.create_secret(name, value)

        return Secret(
            name=name,
            value=value,
            version_id=self._secrets[name]["version"],
            updated_at=datetime.now(timezone.utc),
        )

    async def delete_secret(
        self,
        name: str,
        force: bool = False,
        recovery_window_days: int = 30,
    ) -> bool:
        if name in self._secrets:
            del self._secrets[name]
            return True
        return False

    async def restore_secret(self, name: str) -> bool:
        return False  # Can't restore in mock

    async def secret_exists(self, name: str) -> bool:
        return name in self._secrets

    async def list_secrets(
        self,
        prefix: str | None = None,
        max_results: int = 100,
    ) -> list[str]:
        secrets = list(self._secrets.keys())
        if prefix:
            secrets = [s for s in secrets if s.startswith(prefix)]
        return secrets[:max_results]

    async def list_secret_versions(
        self,
        name: str,
        max_versions: int = 10,
    ) -> list[dict[str, Any]]:
        data = self._secrets.get(name)
        if data:
            return [
                {
                    "version_id": data.get("version", "1"),
                    "created_date": data.get("created_at"),
                }
            ]
        return []

    async def configure_rotation(
        self,
        name: str,
        config: SecretRotationConfig,
    ) -> bool:
        return True  # No-op in mock

    async def rotate_secret_immediately(self, name: str) -> Secret:
        secret = await self.get_secret(name)
        if secret:
            return await self.update_secret(name, secret.value)
        raise ValueError(f"Secret {name} not found")

    async def get_health(self) -> dict[str, Any]:
        return {"status": "healthy", "mode": "mock"}
