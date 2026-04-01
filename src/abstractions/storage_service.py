"""
Project Aura - Storage Service Abstraction

Abstract interface for object storage operations.
Implementations: AWS S3, Azure Blob Storage

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, BinaryIO


class StorageClass(Enum):
    """Storage tiers for cost optimization."""

    STANDARD = "standard"
    INFREQUENT_ACCESS = "infrequent_access"
    ARCHIVE = "archive"
    COLD = "cold"


@dataclass
class StorageObject:
    """Represents an object in cloud storage."""

    key: str  # Object key/path
    bucket: str  # Bucket/container name
    size_bytes: int
    content_type: str
    etag: str | None = None
    last_modified: datetime | None = None
    storage_class: StorageClass = StorageClass.STANDARD
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert object to dictionary."""
        return {
            "key": self.key,
            "bucket": self.bucket,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "etag": self.etag,
            "last_modified": (
                self.last_modified.isoformat() if self.last_modified else None
            ),
            "storage_class": self.storage_class.value,
            "metadata": self.metadata,
        }


@dataclass
class PresignedUrl:
    """Presigned URL for temporary access."""

    url: str
    expires_at: datetime
    method: str  # GET, PUT


class StorageService(ABC):
    """
    Abstract interface for object storage operations.

    Implementations:
    - AWS: S3StorageService
    - Azure: AzureBlobService
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Initialize storage client."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up resources."""

    # Bucket/Container Operations
    @abstractmethod
    async def create_bucket(
        self,
        bucket_name: str,
        region: str | None = None,
        encryption: bool = True,
    ) -> bool:
        """
        Create a storage bucket/container.

        Args:
            bucket_name: Name of the bucket
            region: Region for the bucket
            encryption: Enable server-side encryption

        Returns:
            True if created successfully
        """

    @abstractmethod
    async def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """
        Delete a storage bucket/container.

        Args:
            bucket_name: Name of the bucket
            force: Delete even if not empty

        Returns:
            True if deleted successfully
        """

    @abstractmethod
    async def bucket_exists(self, bucket_name: str) -> bool:
        """Check if a bucket exists."""

    @abstractmethod
    async def list_buckets(self) -> list[str]:
        """List all buckets."""

    # Object Operations
    @abstractmethod
    async def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        storage_class: StorageClass = StorageClass.STANDARD,
    ) -> StorageObject:
        """
        Upload an object to storage.

        Args:
            bucket: Bucket name
            key: Object key
            data: Object data (bytes or file-like object)
            content_type: MIME type
            metadata: Optional object metadata
            storage_class: Storage tier

        Returns:
            The created storage object
        """

    @abstractmethod
    async def download_object(self, bucket: str, key: str) -> bytes:
        """
        Download an object from storage.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            Object data as bytes
        """

    @abstractmethod
    async def download_object_to_file(
        self, bucket: str, key: str, file_path: str
    ) -> bool:
        """
        Download an object directly to a file.

        Args:
            bucket: Bucket name
            key: Object key
            file_path: Local file path

        Returns:
            True if downloaded successfully
        """

    @abstractmethod
    async def delete_object(self, bucket: str, key: str) -> bool:
        """
        Delete an object from storage.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            True if deleted successfully
        """

    @abstractmethod
    async def delete_objects(self, bucket: str, keys: list[str]) -> dict[str, Any]:
        """
        Bulk delete objects.

        Args:
            bucket: Bucket name
            keys: List of object keys

        Returns:
            Result with success/failure counts
        """

    @abstractmethod
    async def object_exists(self, bucket: str, key: str) -> bool:
        """Check if an object exists."""

    @abstractmethod
    async def get_object_info(self, bucket: str, key: str) -> StorageObject | None:
        """
        Get object metadata without downloading content.

        Args:
            bucket: Bucket name
            key: Object key

        Returns:
            Object metadata if exists
        """

    @abstractmethod
    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> tuple[list[StorageObject], str | None]:
        """
        List objects in a bucket with optional prefix filter.

        Args:
            bucket: Bucket name
            prefix: Key prefix filter
            max_keys: Maximum objects to return
            continuation_token: Token for pagination

        Returns:
            Tuple of (objects list, next continuation token)
        """

    @abstractmethod
    async def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> StorageObject:
        """
        Copy an object within or between buckets.

        Args:
            source_bucket: Source bucket name
            source_key: Source object key
            dest_bucket: Destination bucket name
            dest_key: Destination object key

        Returns:
            The copied object
        """

    # Presigned URLs
    @abstractmethod
    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in_seconds: int = 3600,
        method: str = "GET",
    ) -> PresignedUrl:
        """
        Generate a presigned URL for temporary access.

        Args:
            bucket: Bucket name
            key: Object key
            expires_in_seconds: URL expiration time
            method: HTTP method (GET for download, PUT for upload)

        Returns:
            Presigned URL with expiration
        """

    # Health and Metrics
    @abstractmethod
    async def get_health(self) -> dict[str, Any]:
        """Get storage service health status."""

    @abstractmethod
    async def get_bucket_stats(self, bucket: str) -> dict[str, Any]:
        """Get statistics for a bucket (size, object count)."""
