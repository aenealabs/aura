"""
Project Aura - File-Based Secrets Adapter

Adapter for file-based secrets management implementing SecretsService interface.
Uses encrypted files on disk for self-hosted deployments without cloud secrets managers.

See ADR-049: Self-Hosted Deployment Strategy

Security:
- Secrets are encrypted at rest using Fernet (AES-128-CBC)
- Master key stored separately from secrets
- File permissions enforced (0600)

Environment Variables:
    SECRETS_PATH: Base path for secrets storage (default: /etc/aura/secrets)
    SECRETS_MASTER_KEY: Base64-encoded master key (or path to key file)
    SECRETS_KEY_FILE: Path to master key file (default: /etc/aura/.secrets_key)
"""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.abstractions.secrets_service import (
    Secret,
    SecretRotationConfig,
    SecretsService,
)

logger = logging.getLogger(__name__)

# Lazy import cryptography
_fernet = None


def _get_fernet():
    """Lazy import Fernet."""
    global _fernet
    if _fernet is None:
        try:
            from cryptography.fernet import Fernet

            _fernet = Fernet
        except ImportError:
            raise ImportError(
                "cryptography package not installed. Install with: pip install cryptography"
            )
    return _fernet


class FileSecretsAdapter(SecretsService):
    """
    File-based secrets adapter implementing SecretsService interface.

    Stores secrets as encrypted JSON files on the local filesystem.
    Suitable for single-node deployments and development environments.

    For production multi-node deployments, consider using:
    - HashiCorp Vault
    - External Secrets Operator with a backend
    - Kubernetes Secrets with encryption at rest
    """

    def __init__(
        self,
        secrets_path: str | None = None,
        master_key: str | None = None,
        key_file: str | None = None,
    ):
        """
        Initialize file secrets adapter.

        Args:
            secrets_path: Base path for secrets storage
            master_key: Base64-encoded master encryption key
            key_file: Path to file containing master key
        """
        self.secrets_path = Path(
            secrets_path or os.environ.get("SECRETS_PATH", "/etc/aura/secrets")
        )
        self._master_key = master_key or os.environ.get("SECRETS_MASTER_KEY")
        self._key_file = Path(
            key_file or os.environ.get("SECRETS_KEY_FILE", "/etc/aura/.secrets_key")
        )

        self._fernet = None
        self._connected = False

    def _get_fernet_instance(self):
        """Get or create Fernet encryption instance."""
        if self._fernet is None:
            Fernet = _get_fernet()
            key = self._load_master_key()
            self._fernet = Fernet(key)
        return self._fernet

    def _load_master_key(self) -> bytes:
        """Load or generate master encryption key."""
        # Try environment variable first
        if self._master_key:
            return base64.urlsafe_b64decode(self._master_key)

        # Try key file
        if self._key_file.exists():
            return self._key_file.read_bytes().strip()

        # Generate new key if none exists
        Fernet = _get_fernet()
        key = Fernet.generate_key()

        # Save to key file
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        self._key_file.write_bytes(key)
        os.chmod(self._key_file, 0o600)
        logger.warning(f"Generated new master key at {self._key_file}")

        return key

    def _secret_file_path(self, name: str) -> Path:
        """Get path for a secret file."""
        # Sanitize name to prevent path traversal
        safe_name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self.secrets_path / f"{safe_name}.secret"

    def _metadata_file_path(self, name: str) -> Path:
        """Get path for secret metadata file."""
        safe_name = name.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self.secrets_path / f"{safe_name}.meta"

    async def connect(self) -> bool:
        """Initialize the secrets service."""
        try:
            # Ensure secrets directory exists with secure permissions
            self.secrets_path.mkdir(parents=True, exist_ok=True)
            os.chmod(self.secrets_path, 0o700)  # nosec - 0o700 is secure (owner-only)

            # Initialize encryption
            self._get_fernet_instance()

            self._connected = True
            logger.info(f"File secrets adapter initialized at {self.secrets_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize file secrets adapter: {e}")
            return False

    async def disconnect(self) -> None:
        """Clean up resources."""
        self._fernet = None
        self._connected = False

    async def create_secret(
        self,
        name: str,
        value: str | dict[str, Any],
        description: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> Secret:
        """Create a new secret."""
        fernet = self._get_fernet_instance()

        # Serialize value
        if isinstance(value, dict):
            value_bytes = json.dumps(value).encode()
        else:
            value_bytes = value.encode()

        # Encrypt
        encrypted = fernet.encrypt(value_bytes)

        # Write encrypted secret
        secret_path = self._secret_file_path(name)
        secret_path.write_bytes(encrypted)
        os.chmod(secret_path, 0o600)

        # Write metadata
        now = datetime.now(timezone.utc)
        metadata = {
            "name": name,
            "description": description,
            "tags": tags or {},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "version": "1",
        }

        meta_path = self._metadata_file_path(name)
        meta_path.write_text(json.dumps(metadata, indent=2))
        os.chmod(meta_path, 0o600)

        logger.info(f"Created secret: {name}")

        return Secret(
            name=name,
            value=value,
            version_id="1",
            created_at=now,
            updated_at=now,
            description=description,
            tags=tags or {},
        )

    async def get_secret(self, name: str, version: str | None = None) -> Secret | None:
        """Get secret metadata (without value)."""
        meta_path = self._metadata_file_path(name)
        if not meta_path.exists():
            return None

        metadata = json.loads(meta_path.read_text())

        return Secret(
            name=name,
            value="***REDACTED***",  # Don't return value in metadata call
            version_id=metadata.get("version", "1"),
            created_at=datetime.fromisoformat(metadata["created_at"]),
            updated_at=datetime.fromisoformat(metadata["updated_at"]),
            description=metadata.get("description"),
            tags=metadata.get("tags", {}),
        )

    async def get_secret_value(
        self, name: str, version: str | None = None
    ) -> str | dict[str, Any] | None:
        """Get the actual secret value."""
        secret_path = self._secret_file_path(name)
        if not secret_path.exists():
            return None

        fernet = self._get_fernet_instance()

        try:
            encrypted = secret_path.read_bytes()
            decrypted = fernet.decrypt(encrypted)
            value_str = decrypted.decode()

            # Try to parse as JSON
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                return value_str
        except Exception as e:
            logger.error(f"Failed to decrypt secret {name}: {e}")
            return None

    async def update_secret(
        self,
        name: str,
        value: str | dict[str, Any],
    ) -> Secret:
        """Update an existing secret."""
        # Get existing metadata
        meta_path = self._metadata_file_path(name)
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
            version = int(metadata.get("version", "1")) + 1
        else:
            version = 1
            metadata = {"name": name, "tags": {}}

        # Encrypt new value
        fernet = self._get_fernet_instance()
        if isinstance(value, dict):
            value_bytes = json.dumps(value).encode()
        else:
            value_bytes = value.encode()

        encrypted = fernet.encrypt(value_bytes)

        # Write new encrypted secret
        secret_path = self._secret_file_path(name)
        secret_path.write_bytes(encrypted)
        os.chmod(secret_path, 0o600)

        # Update metadata
        now = datetime.now(timezone.utc)
        metadata["updated_at"] = now.isoformat()
        metadata["version"] = str(version)

        meta_path.write_text(json.dumps(metadata, indent=2))

        logger.info(f"Updated secret: {name} (version {version})")

        return Secret(
            name=name,
            value=value,
            version_id=str(version),
            created_at=datetime.fromisoformat(
                metadata.get("created_at", now.isoformat())
            ),
            updated_at=now,
            description=metadata.get("description"),
            tags=metadata.get("tags", {}),
        )

    async def delete_secret(
        self, name: str, force: bool = False, recovery_days: int = 30
    ) -> bool:
        """Delete a secret."""
        secret_path = self._secret_file_path(name)
        meta_path = self._metadata_file_path(name)

        deleted = False
        if secret_path.exists():
            secret_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
            deleted = True

        if deleted:
            logger.info(f"Deleted secret: {name}")

        return deleted

    async def restore_secret(self, name: str) -> Secret | None:
        """Restore a deleted secret (not supported for file-based)."""
        logger.warning("Secret restoration not supported for file-based secrets")
        return None

    async def secret_exists(self, name: str) -> bool:
        """Check if a secret exists."""
        return self._secret_file_path(name).exists()

    async def list_secrets(
        self, prefix: str | None = None, max_results: int = 100
    ) -> list[Secret]:
        """List all secrets."""
        secrets = []

        for meta_path in self.secrets_path.glob("*.meta"):
            name = meta_path.stem

            if prefix and not name.startswith(prefix):
                continue

            try:
                metadata = json.loads(meta_path.read_text())
                secrets.append(
                    Secret(
                        name=name,
                        value="***REDACTED***",
                        version_id=metadata.get("version", "1"),
                        created_at=datetime.fromisoformat(metadata["created_at"]),
                        updated_at=datetime.fromisoformat(metadata["updated_at"]),
                        description=metadata.get("description"),
                        tags=metadata.get("tags", {}),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to read metadata for {name}: {e}")

            if len(secrets) >= max_results:
                break

        return secrets

    async def list_secret_versions(self, name: str) -> list[str]:
        """List versions of a secret (only current version for file-based)."""
        meta_path = self._metadata_file_path(name)
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
            return [metadata.get("version", "1")]
        return []

    async def configure_rotation(self, name: str, config: SecretRotationConfig) -> bool:
        """Configure secret rotation (not supported for file-based)."""
        logger.warning("Secret rotation not supported for file-based secrets")
        return False

    async def rotate_secret_immediately(self, name: str) -> Secret | None:
        """Rotate a secret immediately (not supported for file-based)."""
        logger.warning("Secret rotation not supported for file-based secrets")
        return None

    async def get_health(self) -> dict[str, Any]:
        """Get health status."""
        try:
            # Check if secrets directory is accessible
            if self.secrets_path.exists() and os.access(self.secrets_path, os.W_OK):
                secret_count = len(list(self.secrets_path.glob("*.secret")))
                return {
                    "status": "healthy",
                    "connected": self._connected,
                    "secrets_path": str(self.secrets_path),
                    "secret_count": secret_count,
                    "encryption": "fernet",
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": "Secrets directory not accessible",
                    "secrets_path": str(self.secrets_path),
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
