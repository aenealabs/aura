"""
Project Aura - AWS Secrets Manager Adapter

Adapter for AWS Secrets Manager that implements SecretsService interface.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.abstractions.secrets_service import (
    Secret,
    SecretRotationConfig,
    SecretsService,
)

logger = logging.getLogger(__name__)


class SecretsManagerAdapter(SecretsService):
    """
    AWS Secrets Manager implementation of SecretsService.
    """

    def __init__(self, region: str = "us-east-1") -> None:
        self.region = region
        self._client = None
        self._connected = False

    @property
    def client(self):
        """Lazy-initialize Secrets Manager client."""
        if self._client is None:
            self._client = boto3.client("secretsmanager", region_name=self.region)
        return self._client

    async def connect(self) -> bool:
        """Initialize Secrets Manager client."""
        try:
            # Test connection
            self.client.list_secrets(MaxResults=1)
            self._connected = True
            logger.info(f"Secrets Manager adapter connected in {self.region}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Secrets Manager: {e}")
            return False

    async def disconnect(self) -> None:
        """Clean up."""
        self._connected = False
        self._client = None

    async def create_secret(
        self,
        name: str,
        value: str | dict[str, Any],
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Secret:
        """Create a new secret."""
        secret_value = json.dumps(value) if isinstance(value, dict) else value

        params: dict[str, Any] = {
            "Name": name,
            "SecretString": secret_value,
        }

        if description:
            params["Description"] = description

        if tags:
            params["Tags"] = [{"Key": k, "Value": v} for k, v in tags.items()]

        response = self.client.create_secret(**params)

        return Secret(
            name=name,
            value=value,
            version_id=response.get("VersionId"),
            created_at=datetime.now(timezone.utc),
            description=description,
            tags=tags or {},
        )

    async def get_secret(
        self,
        name: str,
        version_id: str | None = None,
    ) -> Secret | None:
        """Get a secret by name."""
        try:
            params = {"SecretId": name}
            if version_id:
                params["VersionId"] = version_id

            response = self.client.get_secret_value(**params)

            secret_value = response.get("SecretString", "")
            try:
                secret_value = json.loads(secret_value)
            except json.JSONDecodeError:
                pass  # Keep as string

            # Get metadata
            metadata = self.client.describe_secret(SecretId=name)

            return Secret(
                name=name,
                value=secret_value,
                version_id=response.get("VersionId"),
                created_at=metadata.get("CreatedDate"),
                updated_at=metadata.get("LastChangedDate"),
                description=metadata.get("Description"),
                tags={t["Key"]: t["Value"] for t in metadata.get("Tags", [])},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return None
            raise

    async def get_secret_value(
        self,
        name: str,
        key: str | None = None,
    ) -> str | Any | None:
        """Get secret value directly."""
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
        """Update an existing secret."""
        secret_value = json.dumps(value) if isinstance(value, dict) else value

        response = self.client.update_secret(
            SecretId=name,
            SecretString=secret_value,
        )

        return Secret(
            name=name,
            value=value,
            version_id=response.get("VersionId"),
            updated_at=datetime.now(timezone.utc),
        )

    async def delete_secret(
        self,
        name: str,
        force: bool = False,
        recovery_window_days: int = 30,
    ) -> bool:
        """Delete a secret."""
        try:
            params: dict[str, Any] = {"SecretId": name}

            if force:
                params["ForceDeleteWithoutRecovery"] = True
            else:
                params["RecoveryWindowInDays"] = recovery_window_days

            self.client.delete_secret(**params)
            logger.info(f"Deleted secret: {name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete secret {name}: {e}")
            return False

    async def restore_secret(self, name: str) -> bool:
        """Restore a deleted secret."""
        try:
            self.client.restore_secret(SecretId=name)
            logger.info(f"Restored secret: {name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to restore secret {name}: {e}")
            return False

    async def secret_exists(self, name: str) -> bool:
        """Check if secret exists."""
        try:
            self.client.describe_secret(SecretId=name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return False
            raise

    async def list_secrets(
        self,
        prefix: str | None = None,
        max_results: int = 100,
    ) -> list[str]:
        """List secret names."""
        secrets: list[str] = []
        paginator = self.client.get_paginator("list_secrets")

        params: dict[str, Any] = {"MaxResults": min(max_results, 100)}
        if prefix:
            params["Filters"] = [{"Key": "name", "Values": [prefix]}]

        for page in paginator.paginate(**params):
            for secret in page.get("SecretList", []):
                secrets.append(secret["Name"])
                if len(secrets) >= max_results:
                    return secrets

        return secrets

    async def list_secret_versions(
        self,
        name: str,
        max_versions: int = 10,
    ) -> list[dict[str, Any]]:
        """List secret versions."""
        response = self.client.list_secret_version_ids(
            SecretId=name,
            MaxResults=max_versions,
        )

        versions = []
        for version in response.get("Versions", []):
            versions.append(
                {
                    "version_id": version.get("VersionId"),
                    "created_date": version.get("CreatedDate"),
                    "stages": version.get("VersionStages", []),
                }
            )
        return versions

    async def configure_rotation(
        self,
        name: str,
        config: SecretRotationConfig,
    ) -> bool:
        """Configure secret rotation."""
        try:
            if config.rotation_enabled:
                params = {
                    "SecretId": name,
                    "RotationRules": {
                        "AutomaticallyAfterDays": config.rotation_days,
                    },
                }

                if config.rotation_lambda_arn:
                    params["RotationLambdaARN"] = config.rotation_lambda_arn

                self.client.rotate_secret(**params)
            else:
                self.client.cancel_rotate_secret(SecretId=name)

            return True
        except ClientError as e:
            logger.error(f"Failed to configure rotation for {name}: {e}")
            return False

    async def rotate_secret_immediately(self, name: str) -> Secret:
        """Trigger immediate rotation."""
        self.client.rotate_secret(SecretId=name)
        secret = await self.get_secret(name)
        if secret is None:
            raise ValueError(f"Secret {name} not found after rotation")
        return secret

    async def get_health(self) -> dict[str, Any]:
        """Get health status."""
        return {
            "status": "healthy" if self._connected else "disconnected",
            "region": self.region,
        }
