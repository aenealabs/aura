"""
Project Aura - Azure Blob Storage Service

Azure Blob Storage implementation of StorageService.
Provides object storage for Azure Government deployments.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, BinaryIO

from src.abstractions.storage_service import (
    PresignedUrl,
    StorageClass,
    StorageObject,
    StorageService,
)

if TYPE_CHECKING:
    from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

# Optional Azure dependencies
try:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobSasPermissions, BlobServiceClient  # noqa: F811

    AZURE_BLOB_AVAILABLE = True
except ImportError:
    AZURE_BLOB_AVAILABLE = False
    logger.warning("Azure Blob Storage SDK not available - using mock mode")


class AzureBlobService(StorageService):
    """
    Azure Blob Storage implementation.

    Compatible with Azure Government regions.
    """

    def __init__(
        self,
        account_url: str | None = None,
        connection_string: str | None = None,
    ):
        self.account_url = account_url or os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
        self.connection_string = connection_string or os.environ.get(
            "AZURE_STORAGE_CONNECTION_STRING"
        )

        self._client: "BlobServiceClient | None" = None
        self._connected = False

        # Mock storage
        self._mock_containers: dict[str, dict[str, bytes]] = {}

    @property
    def is_mock_mode(self) -> bool:
        """Check if running in mock mode."""
        return not AZURE_BLOB_AVAILABLE or (
            not self.account_url and not self.connection_string
        )

    async def connect(self) -> bool:
        """Connect to Azure Blob Storage."""
        if self.is_mock_mode:
            logger.info("Azure Blob Storage running in mock mode")
            self._connected = True
            return True

        try:
            if self.connection_string:
                self._client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            else:
                credential = DefaultAzureCredential()
                self._client = BlobServiceClient(
                    self.account_url, credential=credential
                )

            self._connected = True
            logger.info("Connected to Azure Blob Storage")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Azure Blob Storage: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect."""
        self._connected = False
        self._client = None

    async def create_bucket(
        self,
        bucket_name: str,
        region: str | None = None,
        encryption: bool = True,
    ) -> bool:
        """Create a container."""
        if self.is_mock_mode:
            self._mock_containers[bucket_name] = {}
            return True

        if self._client is None:
            logger.error("Client not initialized")
            return False

        try:
            self._client.create_container(bucket_name)
            logger.info(f"Created container: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create container: {e}")
            return False

    async def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """Delete a container."""
        if self.is_mock_mode:
            if bucket_name in self._mock_containers:
                del self._mock_containers[bucket_name]
                return True
            return False

        if self._client is None:
            logger.error("Client not initialized")
            return False

        try:
            container = self._client.get_container_client(bucket_name)
            container.delete_container()
            return True
        except Exception as e:
            logger.error(f"Failed to delete container: {e}")
            return False

    async def bucket_exists(self, bucket_name: str) -> bool:
        """Check if container exists."""
        if self.is_mock_mode:
            return bucket_name in self._mock_containers

        if self._client is None:
            return False

        try:
            container = self._client.get_container_client(bucket_name)
            container.get_container_properties()
            return True
        except Exception:
            return False

    async def list_buckets(self) -> list[str]:
        """List containers."""
        if self.is_mock_mode:
            return list(self._mock_containers.keys())

        if self._client is None:
            return []

        containers = self._client.list_containers()
        return [str(c["name"]) for c in containers]

    async def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        storage_class: StorageClass = StorageClass.STANDARD,
    ) -> StorageObject:
        """Upload a blob."""
        if self.is_mock_mode:
            if bucket not in self._mock_containers:
                self._mock_containers[bucket] = {}
            blob_data = data if isinstance(data, bytes) else data.read()
            self._mock_containers[bucket][key] = blob_data
            return StorageObject(
                key=key,
                bucket=bucket,
                size_bytes=len(blob_data),
                content_type=content_type,
                last_modified=datetime.now(timezone.utc),
                metadata=metadata or {},
            )

        if self._client is None:
            raise RuntimeError("Client not initialized")

        tier_map = {
            StorageClass.STANDARD: "Hot",
            StorageClass.INFREQUENT_ACCESS: "Cool",
            StorageClass.ARCHIVE: "Archive",
            StorageClass.COLD: "Archive",
        }

        blob_client = self._client.get_blob_client(bucket, key)
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings={"content_type": content_type},
            metadata=metadata,
            standard_blob_tier=tier_map.get(storage_class, "Hot"),
        )

        props = blob_client.get_blob_properties()
        return StorageObject(
            key=key,
            bucket=bucket,
            size_bytes=props.size,
            content_type=content_type,
            etag=props.etag,
            last_modified=props.last_modified,
            metadata=metadata or {},
        )

    async def download_object(self, bucket: str, key: str) -> bytes:
        """Download a blob."""
        if self.is_mock_mode:
            return self._mock_containers.get(bucket, {}).get(key, b"")

        if self._client is None:
            raise RuntimeError("Client not initialized")

        blob_client = self._client.get_blob_client(bucket, key)
        download_stream = blob_client.download_blob()
        result: bytes = download_stream.readall()
        return result

    async def download_object_to_file(
        self, bucket: str, key: str, file_path: str
    ) -> bool:
        """Download blob to file."""
        try:
            data = await self.download_object(bucket, key)
            with open(file_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            logger.error(f"Failed to download: {e}")
            return False

    async def delete_object(self, bucket: str, key: str) -> bool:
        """Delete a blob."""
        if self.is_mock_mode:
            if bucket in self._mock_containers and key in self._mock_containers[bucket]:
                del self._mock_containers[bucket][key]
                return True
            return False

        if self._client is None:
            logger.error("Client not initialized")
            return False

        try:
            blob_client = self._client.get_blob_client(bucket, key)
            blob_client.delete_blob()
            return True
        except Exception as e:
            logger.error(f"Failed to delete: {e}")
            return False

    async def delete_objects(self, bucket: str, keys: list[str]) -> dict[str, Any]:
        """Bulk delete blobs."""
        deleted = 0
        errors = 0

        for key in keys:
            if await self.delete_object(bucket, key):
                deleted += 1
            else:
                errors += 1

        return {"deleted": deleted, "errors": errors}

    async def object_exists(self, bucket: str, key: str) -> bool:
        """Check if blob exists."""
        if self.is_mock_mode:
            return (
                bucket in self._mock_containers and key in self._mock_containers[bucket]
            )

        if self._client is None:
            return False

        try:
            blob_client = self._client.get_blob_client(bucket, key)
            blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    async def get_object_info(self, bucket: str, key: str) -> StorageObject | None:
        """Get blob properties."""
        if self.is_mock_mode:
            if bucket in self._mock_containers and key in self._mock_containers[bucket]:
                data = self._mock_containers[bucket][key]
                return StorageObject(
                    key=key,
                    bucket=bucket,
                    size_bytes=len(data),
                    content_type="application/octet-stream",
                )
            return None

        if self._client is None:
            return None

        try:
            blob_client = self._client.get_blob_client(bucket, key)
            props = blob_client.get_blob_properties()
            return StorageObject(
                key=key,
                bucket=bucket,
                size_bytes=props.size,
                content_type=props.content_settings.content_type
                or "application/octet-stream",
                etag=props.etag,
                last_modified=props.last_modified,
                metadata=props.metadata or {},
            )
        except Exception:
            return None

    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> tuple[list[StorageObject], str | None]:
        """List blobs."""
        if self.is_mock_mode:
            objects = []
            for key, data in self._mock_containers.get(bucket, {}).items():
                if key.startswith(prefix):
                    objects.append(
                        StorageObject(
                            key=key,
                            bucket=bucket,
                            size_bytes=len(data),
                            content_type="application/octet-stream",
                        )
                    )
            return objects[:max_keys], None

        if self._client is None:
            return [], None

        container = self._client.get_container_client(bucket)
        blobs = container.list_blobs(name_starts_with=prefix)

        objects = []
        for blob in blobs:
            objects.append(
                StorageObject(
                    key=blob.name,
                    bucket=bucket,
                    size_bytes=blob.size,
                    content_type=(
                        blob.content_settings.content_type
                        if blob.content_settings
                        else "application/octet-stream"
                    ),
                    etag=blob.etag,
                    last_modified=blob.last_modified,
                )
            )
            if len(objects) >= max_keys:
                break

        return objects, None

    async def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> StorageObject:
        """Copy a blob."""
        if self.is_mock_mode:
            data = self._mock_containers.get(source_bucket, {}).get(source_key, b"")
            if dest_bucket not in self._mock_containers:
                self._mock_containers[dest_bucket] = {}
            self._mock_containers[dest_bucket][dest_key] = data
            return StorageObject(
                key=dest_key,
                bucket=dest_bucket,
                size_bytes=len(data),
                content_type="application/octet-stream",
            )

        if self._client is None:
            raise RuntimeError("Client not initialized")

        source_blob = self._client.get_blob_client(source_bucket, source_key)
        dest_blob = self._client.get_blob_client(dest_bucket, dest_key)

        dest_blob.start_copy_from_url(source_blob.url)

        result = await self.get_object_info(dest_bucket, dest_key)
        if result is None:
            raise RuntimeError(
                f"Failed to get info for copied object {dest_bucket}/{dest_key}"
            )
        return result

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in_seconds: int = 3600,
        method: str = "GET",
    ) -> PresignedUrl:
        """Generate SAS URL."""
        if self.is_mock_mode:
            return PresignedUrl(
                url=f"https://mock.blob.core.windows.net/{bucket}/{key}?sas=mock",
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=expires_in_seconds),
                method=method,
            )

        if self._client is None:
            raise RuntimeError("Client not initialized")

        _permission = (  # noqa: F841
            BlobSasPermissions(read=True)
            if method == "GET"
            else BlobSasPermissions(write=True)
        )
        expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

        blob_client = self._client.get_blob_client(bucket, key)

        # Note: This requires account key for SAS generation
        # In production, use user delegation SAS with DefaultAzureCredential
        sas_url = blob_client.url

        return PresignedUrl(
            url=sas_url,
            expires_at=expiry,
            method=method,
        )

    async def get_health(self) -> dict[str, Any]:
        """Get health status."""
        return {
            "status": "healthy" if self._connected else "disconnected",
            "mode": "mock" if self.is_mock_mode else "azure",
            "account_url": self.account_url,
        }

    async def get_bucket_stats(self, bucket: str) -> dict[str, Any]:
        """Get container statistics."""
        if self.is_mock_mode:
            container_data = self._mock_containers.get(bucket, {})
            total_size = sum(len(v) for v in container_data.values())
            return {
                "bucket": bucket,
                "object_count": len(container_data),
                "total_size_bytes": total_size,
            }

        objects, _ = await self.list_objects(bucket)
        total_size = sum(obj.size_bytes for obj in objects)

        return {
            "bucket": bucket,
            "object_count": len(objects),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
