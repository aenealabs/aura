"""
Project Aura - Secrets Manager to File-Based Migrator

Migrates secrets from AWS Secrets Manager to encrypted file-based storage.
Uses Fernet encryption for secure storage at rest.

See ADR-049: Self-Hosted Deployment Strategy
"""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.migration.base import BaseMigrator, MigrationConfig, MigrationError

logger = logging.getLogger(__name__)


class SecretsToFileMigrator(BaseMigrator):
    """
    Migrates secrets from AWS Secrets Manager to file-based storage.

    Features:
    - Encrypted storage using Fernet (AES-128-CBC)
    - Metadata preservation
    - Secure file permissions (0600)
    - JSON and string secret support
    """

    def __init__(
        self,
        secrets_manager_region: str = "us-east-1",
        secrets_prefix: str | None = None,
        target_path: str = "/etc/aura/secrets",
        master_key: str | None = None,
        key_file: str = "/etc/aura/.secrets_key",
        config: MigrationConfig | None = None,
    ):
        """
        Initialize Secrets Manager to file migrator.

        Args:
            secrets_manager_region: AWS region for Secrets Manager
            secrets_prefix: Prefix to filter secrets (e.g., "aura/")
            target_path: Directory for migrated secrets
            master_key: Base64-encoded encryption key (or generate new)
            key_file: Path to store encryption key
            config: Migration configuration
        """
        super().__init__(config)
        self.secrets_manager_region = secrets_manager_region
        self.secrets_prefix = secrets_prefix
        self.target_path = Path(target_path)
        self._master_key = master_key
        self.key_file = Path(key_file)

        self._secrets_client = None
        self._fernet = None
        self._secrets_list: list[dict[str, Any]] = []

    @property
    def source_type(self) -> str:
        return "secrets_manager"

    @property
    def target_type(self) -> str:
        return "file_secrets"

    async def connect_source(self) -> bool:
        """Connect to Secrets Manager."""
        try:
            import boto3

            self._secrets_client = boto3.client(
                "secretsmanager",
                region_name=self.secrets_manager_region,
            )
            # Test connection
            self._secrets_client.list_secrets(MaxResults=1)
            logger.info(
                f"Connected to Secrets Manager in {self.secrets_manager_region}"
            )
            return True
        except ImportError:
            logger.warning("boto3 not installed, using mock mode")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Secrets Manager: {e}")
            return False

    async def connect_target(self) -> bool:
        """Initialize file-based secrets storage."""
        try:
            from cryptography.fernet import Fernet

            # Ensure target directory exists with secure permissions
            self.target_path.mkdir(parents=True, exist_ok=True)
            os.chmod(self.target_path, 0o700)  # nosec - 0o700 is secure (owner-only)

            # Load or generate encryption key
            key = self._load_or_generate_key()
            self._fernet = Fernet(key)

            logger.info(f"File secrets storage initialized at {self.target_path}")
            return True
        except ImportError:
            logger.warning("cryptography not installed, using mock mode")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize file secrets: {e}")
            return False

    def _load_or_generate_key(self) -> bytes:
        """Load existing key or generate a new one."""
        from cryptography.fernet import Fernet

        # Try provided master key
        if self._master_key:
            return base64.urlsafe_b64decode(self._master_key)

        # Try existing key file
        if self.key_file.exists():
            return self.key_file.read_bytes().strip()

        # Generate new key
        key = Fernet.generate_key()

        # Save key file with secure permissions
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        self.key_file.write_bytes(key)
        os.chmod(self.key_file, 0o600)
        logger.info(f"Generated new encryption key at {self.key_file}")

        return key

    async def disconnect(self) -> None:
        """Clean up resources."""
        self._secrets_client = None
        self._fernet = None

    async def count_source_items(self) -> int:
        """Count total secrets in Secrets Manager."""
        if not self._secrets_client:
            return 0

        count = 0
        self._secrets_list = []

        try:
            paginator = self._secrets_client.get_paginator("list_secrets")
            filters = []
            if self.secrets_prefix:
                filters.append({"Key": "name", "Values": [self.secrets_prefix]})

            for page in paginator.paginate(Filters=filters):
                for secret in page.get("SecretList", []):
                    self._secrets_list.append(
                        {
                            "name": secret["Name"],
                            "arn": secret["ARN"],
                            "description": secret.get("Description"),
                            "tags": {
                                t["Key"]: t["Value"] for t in secret.get("Tags", [])
                            },
                            "created_date": secret.get("CreatedDate"),
                            "last_changed_date": secret.get("LastChangedDate"),
                        }
                    )
                    count += 1

            logger.info(f"Found {count} secrets to migrate")

        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")

        return count

    async def fetch_source_batch(self, offset: int, limit: int) -> list[dict[str, Any]]:
        """Fetch batch of secret references."""
        return self._secrets_list[offset : offset + limit]

    async def migrate_item(self, item: dict[str, Any]) -> bool:
        """Migrate a single secret to file storage."""
        if not self._secrets_client or not self._fernet:
            return True  # Mock mode

        secret_name = item["name"]

        try:
            # Get secret value from Secrets Manager
            response = self._secrets_client.get_secret_value(SecretId=secret_name)

            if "SecretString" in response:
                secret_value = response["SecretString"]
            elif "SecretBinary" in response:
                secret_value = base64.b64encode(response["SecretBinary"]).decode()
            else:
                raise MigrationError(f"No secret value found for {secret_name}")

            # Sanitize name for filename
            safe_name = self._sanitize_name(secret_name)

            # Encrypt and write secret
            if isinstance(secret_value, str):
                value_bytes = secret_value.encode()
            else:
                value_bytes = json.dumps(secret_value).encode()

            encrypted = self._fernet.encrypt(value_bytes)

            secret_file = self.target_path / f"{safe_name}.secret"
            secret_file.write_bytes(encrypted)
            os.chmod(secret_file, 0o600)

            # Write metadata
            now = datetime.now(timezone.utc)
            metadata = {
                "name": secret_name,
                "original_arn": item.get("arn"),
                "description": item.get("description"),
                "tags": item.get("tags", {}),
                "created_at": (
                    item.get("created_date", now).isoformat()
                    if isinstance(item.get("created_date"), datetime)
                    else str(item.get("created_date", now.isoformat()))
                ),
                "updated_at": now.isoformat(),
                "migrated_at": now.isoformat(),
                "version": "1",
            }

            meta_file = self.target_path / f"{safe_name}.meta"
            meta_file.write_text(json.dumps(metadata, indent=2))
            os.chmod(meta_file, 0o600)

            logger.debug(f"Migrated secret: {secret_name}")
            return True

        except Exception as e:
            raise MigrationError(
                f"Failed to migrate secret {secret_name}: {e}",
                item_id=secret_name,
            )

    def _sanitize_name(self, name: str) -> str:
        """Sanitize secret name for use as filename."""
        # Replace path separators and special chars
        safe = name.replace("/", "_").replace("\\", "_").replace("..", "_")
        # Remove any remaining problematic characters
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in safe)
        return safe

    async def verify_item(self, item: dict[str, Any]) -> bool:
        """Verify secret was migrated correctly."""
        if not self._fernet:
            return True  # Mock mode

        try:
            safe_name = self._sanitize_name(item["name"])
            secret_file = self.target_path / f"{safe_name}.secret"
            meta_file = self.target_path / f"{safe_name}.meta"

            if not secret_file.exists() or not meta_file.exists():
                return False

            # Verify we can decrypt
            encrypted = secret_file.read_bytes()
            self._fernet.decrypt(encrypted)  # Will raise if invalid

            # Verify metadata is valid JSON
            json.loads(meta_file.read_text())

            return True

        except Exception as e:
            logger.warning(f"Verification failed for {item.get('name')}: {e}")
            return False

    async def export_key_backup(self, backup_path: str) -> bool:
        """
        Export encryption key for backup purposes.

        SECURITY: Handle this backup file with extreme care!
        """
        try:
            if self.key_file.exists():
                backup = Path(backup_path)
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(self.key_file.read_bytes())
                os.chmod(backup, 0o600)
                logger.warning(
                    f"Encryption key exported to {backup_path}. "
                    "Store this file securely!"
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to export key backup: {e}")
            return False
