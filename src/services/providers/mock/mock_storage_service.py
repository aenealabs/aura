"""
Project Aura - Mock Storage Service

In-memory mock implementation of StorageService for testing.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, BinaryIO

from src.abstractions.storage_service import (
    PresignedUrl,
    StorageClass,
    StorageObject,
    StorageService,
)

logger = logging.getLogger(__name__)


class MockStorageService(StorageService):
    """Mock storage service for testing."""

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, bytes]] = {}
        self._metadata: dict[str, dict[str, dict[str, Any]]] = {}
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        logger.info("MockStorageService connected")
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def create_bucket(
        self,
        bucket_name: str,
        region: str | None = None,
        encryption: bool = True,
    ) -> bool:
        self._buckets[bucket_name] = {}
        self._metadata[bucket_name] = {}
        return True

    async def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        if bucket_name in self._buckets:
            del self._buckets[bucket_name]
            del self._metadata[bucket_name]
            return True
        return False

    async def bucket_exists(self, bucket_name: str) -> bool:
        return bucket_name in self._buckets

    async def list_buckets(self) -> list[str]:
        return list(self._buckets.keys())

    async def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        storage_class: StorageClass = StorageClass.STANDARD,
    ) -> StorageObject:
        if bucket not in self._buckets:
            self._buckets[bucket] = {}
            self._metadata[bucket] = {}

        obj_data = data if isinstance(data, bytes) else data.read()
        self._buckets[bucket][key] = obj_data
        self._metadata[bucket][key] = {
            "content_type": content_type,
            "metadata": metadata or {},
            "storage_class": storage_class,
            "last_modified": datetime.now(timezone.utc),
        }

        return StorageObject(
            key=key,
            bucket=bucket,
            size_bytes=len(obj_data),
            content_type=content_type,
            etag=f"mock-{hash(obj_data)}",
            last_modified=datetime.now(timezone.utc),
            storage_class=storage_class,
            metadata=metadata or {},
        )

    async def download_object(self, bucket: str, key: str) -> bytes:
        return self._buckets.get(bucket, {}).get(key, b"")

    async def download_object_to_file(
        self, bucket: str, key: str, file_path: str
    ) -> bool:
        try:
            data = await self.download_object(bucket, key)
            with open(file_path, "wb") as f:
                f.write(data)
            return True
        except Exception:
            return False

    async def delete_object(self, bucket: str, key: str) -> bool:
        if bucket in self._buckets and key in self._buckets[bucket]:
            del self._buckets[bucket][key]
            del self._metadata[bucket][key]
            return True
        return False

    async def delete_objects(self, bucket: str, keys: list[str]) -> dict[str, Any]:
        deleted = 0
        for key in keys:
            if await self.delete_object(bucket, key):
                deleted += 1
        return {"deleted": deleted, "errors": len(keys) - deleted}

    async def object_exists(self, bucket: str, key: str) -> bool:
        return bucket in self._buckets and key in self._buckets[bucket]

    async def get_object_info(self, bucket: str, key: str) -> StorageObject | None:
        if bucket in self._buckets and key in self._buckets[bucket]:
            data = self._buckets[bucket][key]
            meta = self._metadata[bucket].get(key, {})
            return StorageObject(
                key=key,
                bucket=bucket,
                size_bytes=len(data),
                content_type=meta.get("content_type", "application/octet-stream"),
                etag=f"mock-{hash(data)}",
                last_modified=meta.get("last_modified"),
                metadata=meta.get("metadata", {}),
            )
        return None

    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> tuple[list[StorageObject], str | None]:
        objects = []
        for key, data in self._buckets.get(bucket, {}).items():
            if key.startswith(prefix):
                meta = self._metadata.get(bucket, {}).get(key, {})
                objects.append(
                    StorageObject(
                        key=key,
                        bucket=bucket,
                        size_bytes=len(data),
                        content_type=meta.get(
                            "content_type", "application/octet-stream"
                        ),
                        last_modified=meta.get("last_modified"),
                    )
                )
        return objects[:max_keys], None

    async def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> StorageObject:
        data = self._buckets.get(source_bucket, {}).get(source_key, b"")
        if dest_bucket not in self._buckets:
            self._buckets[dest_bucket] = {}
            self._metadata[dest_bucket] = {}

        self._buckets[dest_bucket][dest_key] = data
        self._metadata[dest_bucket][dest_key] = {
            "content_type": "application/octet-stream",
            "last_modified": datetime.now(timezone.utc),
        }

        return StorageObject(
            key=dest_key,
            bucket=dest_bucket,
            size_bytes=len(data),
            content_type="application/octet-stream",
        )

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in_seconds: int = 3600,
        method: str = "GET",
    ) -> PresignedUrl:
        return PresignedUrl(
            url=f"https://mock-storage/{bucket}/{key}?signature=mock",
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=expires_in_seconds),
            method=method,
        )

    async def get_health(self) -> dict[str, Any]:
        return {"status": "healthy", "mode": "mock"}

    async def get_bucket_stats(self, bucket: str) -> dict[str, Any]:
        data = self._buckets.get(bucket, {})
        total_size = sum(len(v) for v in data.values())
        return {
            "bucket": bucket,
            "object_count": len(data),
            "total_size_bytes": total_size,
        }
