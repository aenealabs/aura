"""
Project Aura - MinIO Storage Adapter

Adapter for MinIO (S3-compatible) implementing StorageService interface.
Replaces AWS S3 for self-hosted deployments.

See ADR-049: Self-Hosted Deployment Strategy

Environment Variables:
    MINIO_ENDPOINT: MinIO endpoint (default: localhost:9000)
    MINIO_ACCESS_KEY: Access key
    MINIO_SECRET_KEY: Secret key
    MINIO_SECURE: Use HTTPS (default: true)
    MINIO_REGION: Region (default: us-east-1)
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, BinaryIO

from src.abstractions.storage_service import (
    PresignedUrl,
    StorageClass,
    StorageObject,
    StorageService,
)

logger = logging.getLogger(__name__)

# Lazy import minio
_minio = None


def _get_minio():
    """Lazy import minio."""
    global _minio
    if _minio is None:
        try:
            from minio import Minio
            from minio.error import S3Error

            _minio = {"Minio": Minio, "S3Error": S3Error}
        except ImportError:
            raise ImportError(
                "minio package not installed. Install with: pip install minio"
            )
    return _minio


class MinioStorageAdapter(StorageService):
    """
    MinIO adapter implementing StorageService interface.

    Provides S3-compatible object storage for self-hosted deployments.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool | None = None,
        region: str | None = None,
    ):
        """
        Initialize MinIO storage adapter.

        Args:
            endpoint: MinIO endpoint (host:port)
            access_key: Access key
            secret_key: Secret key
            secure: Use HTTPS
            region: Region identifier
        """
        self.endpoint = endpoint or os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.environ.get("MINIO_SECRET_KEY", "minioadmin")

        if secure is None:
            secure_str = os.environ.get("MINIO_SECURE", "true")
            secure = secure_str.lower() in ("true", "1", "yes")
        self.secure = secure

        self.region = region or os.environ.get("MINIO_REGION", "us-east-1")

        self._client = None
        self._connected = False

    def _get_client(self):
        """Get or create MinIO client."""
        if self._client is None:
            minio_mod = _get_minio()
            self._client = minio_mod["Minio"](
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
                region=self.region,
            )
        return self._client

    async def connect(self) -> bool:
        """Initialize storage client."""
        try:
            client = self._get_client()
            # Test connectivity by listing buckets
            list(client.list_buckets())
            self._connected = True
            logger.info(f"MinIO adapter connected to {self.endpoint}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MinIO: {e}")
            return False

    async def disconnect(self) -> None:
        """Clean up resources."""
        self._client = None
        self._connected = False
        logger.info("MinIO adapter disconnected")

    async def create_bucket(
        self,
        bucket_name: str,
        region: str | None = None,
        encryption: bool = True,
    ) -> bool:
        """Create a storage bucket."""
        try:
            client = self._get_client()
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name, location=region or self.region)
                logger.info(f"Created bucket: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            return False

    async def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """Delete a storage bucket."""
        try:
            client = self._get_client()
            if force:
                # Delete all objects first
                objects = client.list_objects(bucket_name, recursive=True)
                for obj in objects:
                    client.remove_object(bucket_name, obj.object_name)
            client.remove_bucket(bucket_name)
            logger.info(f"Deleted bucket: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete bucket {bucket_name}: {e}")
            return False

    async def bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists."""
        try:
            client = self._get_client()
            return client.bucket_exists(bucket_name)
        except Exception:
            return False

    async def list_buckets(self) -> list[str]:
        """List all buckets."""
        client = self._get_client()
        buckets = client.list_buckets()
        return [b.name for b in buckets]

    async def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        storage_class: StorageClass = StorageClass.STANDARD,
    ) -> StorageObject:
        """Upload an object to storage."""
        import io

        client = self._get_client()

        if isinstance(data, bytes):
            data_stream = io.BytesIO(data)
            size = len(data)
        else:
            # Get size from file-like object
            data.seek(0, 2)  # Seek to end
            size = data.tell()
            data.seek(0)  # Seek back to start
            data_stream = data

        client.put_object(
            bucket,
            key,
            data_stream,
            size,
            content_type=content_type,
            metadata=metadata,
        )

        return StorageObject(
            key=key,
            bucket=bucket,
            size_bytes=size,
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
            storage_class=storage_class,
            metadata=metadata or {},
        )

    async def download_object(self, bucket: str, key: str) -> bytes:
        """Download an object from storage."""
        client = self._get_client()
        response = client.get_object(bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def download_object_to_file(
        self, bucket: str, key: str, file_path: str
    ) -> bool:
        """Download an object directly to a file."""
        try:
            client = self._get_client()
            client.fget_object(bucket, key, file_path)
            return True
        except Exception as e:
            logger.error(f"Failed to download {key} to {file_path}: {e}")
            return False

    async def delete_object(self, bucket: str, key: str) -> bool:
        """Delete an object from storage."""
        try:
            client = self._get_client()
            client.remove_object(bucket, key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete object {key}: {e}")
            return False

    async def delete_objects(self, bucket: str, keys: list[str]) -> dict[str, Any]:
        """Bulk delete objects."""
        from minio.deleteobjects import DeleteObject

        client = self._get_client()
        delete_list = [DeleteObject(key) for key in keys]

        errors = list(client.remove_objects(bucket, delete_list))

        return {
            "deleted": len(keys) - len(errors),
            "errors": [str(e) for e in errors],
        }

    async def object_exists(self, bucket: str, key: str) -> bool:
        """Check if an object exists."""
        try:
            client = self._get_client()
            client.stat_object(bucket, key)
            return True
        except Exception:
            return False

    async def get_object_info(self, bucket: str, key: str) -> StorageObject | None:
        """Get object metadata without downloading content."""
        try:
            client = self._get_client()
            stat = client.stat_object(bucket, key)

            return StorageObject(
                key=key,
                bucket=bucket,
                size_bytes=stat.size,
                content_type=stat.content_type or "application/octet-stream",
                etag=stat.etag,
                last_modified=stat.last_modified,
                storage_class=StorageClass.STANDARD,
                metadata=dict(stat.metadata) if stat.metadata else {},
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
        """List objects in a bucket with optional prefix filter."""
        client = self._get_client()

        objects = []
        object_iter = client.list_objects(bucket, prefix=prefix, recursive=True)

        count = 0
        for obj in object_iter:
            if count >= max_keys:
                break
            objects.append(
                StorageObject(
                    key=obj.object_name,
                    bucket=bucket,
                    size_bytes=obj.size or 0,
                    content_type="application/octet-stream",
                    etag=obj.etag,
                    last_modified=obj.last_modified,
                    storage_class=StorageClass.STANDARD,
                    metadata={},
                )
            )
            count += 1

        return objects, None  # MinIO doesn't use continuation tokens the same way

    async def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> StorageObject:
        """Copy an object within or between buckets."""
        from minio.commonconfig import CopySource

        client = self._get_client()
        source = CopySource(source_bucket, source_key)
        result = client.copy_object(dest_bucket, dest_key, source)

        return StorageObject(
            key=dest_key,
            bucket=dest_bucket,
            size_bytes=0,  # Size not returned by copy
            content_type="application/octet-stream",
            etag=result.etag,
            last_modified=datetime.now(timezone.utc),
            storage_class=StorageClass.STANDARD,
            metadata={},
        )

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in_seconds: int = 3600,
        method: str = "GET",
    ) -> PresignedUrl:
        """Generate a presigned URL for temporary access."""
        client = self._get_client()

        if method.upper() == "GET":
            url = client.presigned_get_object(
                bucket, key, expires=timedelta(seconds=expires_in_seconds)
            )
        else:
            url = client.presigned_put_object(
                bucket, key, expires=timedelta(seconds=expires_in_seconds)
            )

        return PresignedUrl(
            url=url,
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=expires_in_seconds),
            method=method,
        )

    async def get_health(self) -> dict[str, Any]:
        """Get storage service health status."""
        try:
            if self._connected:
                client = self._get_client()
                buckets = list(client.list_buckets())
                return {
                    "status": "healthy",
                    "connected": True,
                    "endpoint": self.endpoint,
                    "bucket_count": len(buckets),
                    "secure": self.secure,
                }
            else:
                return {
                    "status": "disconnected",
                    "connected": False,
                    "endpoint": self.endpoint,
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "endpoint": self.endpoint,
            }

    async def get_bucket_stats(self, bucket: str) -> dict[str, Any]:
        """Get statistics for a bucket."""
        try:
            client = self._get_client()
            objects = list(client.list_objects(bucket, recursive=True))

            total_size = sum(obj.size or 0 for obj in objects)

            return {
                "bucket": bucket,
                "object_count": len(objects),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
            }
        except Exception as e:
            return {
                "bucket": bucket,
                "error": str(e),
            }
