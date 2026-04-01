"""
Project Aura - S3 Storage Adapter

Adapter for AWS S3 that implements StorageService interface.

See ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, BinaryIO

import boto3
from botocore.exceptions import ClientError

from src.abstractions.storage_service import (
    PresignedUrl,
    StorageClass,
    StorageObject,
    StorageService,
)

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    S3Client = object

logger = logging.getLogger(__name__)


class S3StorageAdapter(StorageService):
    """
    AWS S3 implementation of StorageService.
    """

    def __init__(self, region: str = "us-east-1") -> None:
        self.region = region
        self._client: S3Client | None = None
        self._connected = False

    @property
    def client(self) -> S3Client:
        """Lazy-initialize S3 client."""
        if self._client is None:
            self._client = boto3.client("s3", region_name=self.region)  # type: ignore[assignment]
        return self._client

    async def connect(self) -> bool:
        """Initialize S3 client."""
        try:
            # Test connection by listing buckets
            self.client.list_buckets()
            self._connected = True
            logger.info(f"S3 adapter connected in {self.region}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to S3: {e}")
            return False

    async def disconnect(self) -> None:
        """Clean up."""
        self._connected = False
        self._client = None

    async def create_bucket(
        self,
        bucket_name: str,
        region: str | None = None,
        encryption: bool = True,
    ) -> bool:
        """Create an S3 bucket."""
        try:
            create_params: dict[str, Any] = {"Bucket": bucket_name}
            target_region = region or self.region

            # LocationConstraint required for non-us-east-1
            if target_region != "us-east-1":
                create_params["CreateBucketConfiguration"] = {
                    "LocationConstraint": target_region
                }

            self.client.create_bucket(**create_params)

            # Enable encryption
            if encryption:
                self.client.put_bucket_encryption(
                    Bucket=bucket_name,
                    ServerSideEncryptionConfiguration={
                        "Rules": [
                            {
                                "ApplyServerSideEncryptionByDefault": {
                                    "SSEAlgorithm": "AES256"
                                }
                            }
                        ]
                    },
                )

            logger.info(f"Created S3 bucket: {bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            return False

    async def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """Delete an S3 bucket."""
        try:
            if force:
                # Delete all objects first
                paginator = self.client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket_name):
                    objects = page.get("Contents", [])
                    if objects:
                        delete_keys = [{"Key": obj["Key"]} for obj in objects]
                        self.client.delete_objects(
                            Bucket=bucket_name, Delete={"Objects": delete_keys}  # type: ignore[typeddict-item]
                        )

            self.client.delete_bucket(Bucket=bucket_name)
            logger.info(f"Deleted S3 bucket: {bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete bucket {bucket_name}: {e}")
            return False

    async def bucket_exists(self, bucket_name: str) -> bool:
        """Check if bucket exists."""
        try:
            self.client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError:
            return False

    async def list_buckets(self) -> list[str]:
        """List all buckets."""
        response = self.client.list_buckets()
        return [b["Name"] for b in response.get("Buckets", [])]

    async def upload_object(
        self,
        bucket: str,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        storage_class: StorageClass = StorageClass.STANDARD,
    ) -> StorageObject:
        """Upload an object to S3."""
        storage_class_map = {
            StorageClass.STANDARD: "STANDARD",
            StorageClass.INFREQUENT_ACCESS: "STANDARD_IA",
            StorageClass.ARCHIVE: "GLACIER",
            StorageClass.COLD: "DEEP_ARCHIVE",
        }

        put_params: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
            "StorageClass": storage_class_map.get(storage_class, "STANDARD"),
        }

        if metadata:
            put_params["Metadata"] = metadata

        self.client.put_object(**put_params)

        # Get object info
        head = self.client.head_object(Bucket=bucket, Key=key)

        return StorageObject(
            key=key,
            bucket=bucket,
            size_bytes=head.get("ContentLength", 0),
            content_type=content_type,
            etag=head.get("ETag", "").strip('"'),
            last_modified=head.get("LastModified"),
            storage_class=storage_class,
            metadata=metadata or {},
        )

    async def download_object(self, bucket: str, key: str) -> bytes:
        """Download an object from S3."""
        response = self.client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        if isinstance(body, bytes):
            return body
        raise TypeError(f"Expected bytes from S3 body, got {type(body)}")

    async def download_object_to_file(
        self, bucket: str, key: str, file_path: str
    ) -> bool:
        """Download object to a file."""
        try:
            self.client.download_file(bucket, key, file_path)
            return True
        except ClientError as e:
            logger.error(f"Failed to download {key}: {e}")
            return False

    async def delete_object(self, bucket: str, key: str) -> bool:
        """Delete an object."""
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {key}: {e}")
            return False

    async def delete_objects(self, bucket: str, keys: list[str]) -> dict[str, Any]:
        """Bulk delete objects."""
        delete_keys = [{"Key": k} for k in keys]
        response = self.client.delete_objects(
            Bucket=bucket, Delete={"Objects": delete_keys}  # type: ignore[typeddict-item]
        )
        return {
            "deleted": len(response.get("Deleted", [])),
            "errors": len(response.get("Errors", [])),
        }

    async def object_exists(self, bucket: str, key: str) -> bool:
        """Check if object exists."""
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    async def get_object_info(self, bucket: str, key: str) -> StorageObject | None:
        """Get object metadata."""
        try:
            head = self.client.head_object(Bucket=bucket, Key=key)
            return StorageObject(
                key=key,
                bucket=bucket,
                size_bytes=head.get("ContentLength", 0),
                content_type=head.get("ContentType", "application/octet-stream"),
                etag=head.get("ETag", "").strip('"'),
                last_modified=head.get("LastModified"),
                metadata=head.get("Metadata", {}),
            )
        except ClientError:
            return None

    async def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> tuple[list[StorageObject], str | None]:
        """List objects with pagination."""
        params: dict[str, Any] = {
            "Bucket": bucket,
            "Prefix": prefix,
            "MaxKeys": max_keys,
        }
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        response = self.client.list_objects_v2(**params)

        objects = []
        for obj in response.get("Contents", []):
            objects.append(
                StorageObject(
                    key=obj["Key"],
                    bucket=bucket,
                    size_bytes=obj["Size"],
                    content_type="application/octet-stream",
                    etag=obj.get("ETag", "").strip('"'),
                    last_modified=obj.get("LastModified"),
                )
            )

        next_token = response.get("NextContinuationToken")
        return objects, next_token

    async def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        dest_bucket: str,
        dest_key: str,
    ) -> StorageObject:
        """Copy an object."""
        self.client.copy_object(
            CopySource={"Bucket": source_bucket, "Key": source_key},
            Bucket=dest_bucket,
            Key=dest_key,
        )
        result = await self.get_object_info(dest_bucket, dest_key)
        if result is None:
            raise RuntimeError(f"Failed to get info for copied object: {dest_key}")
        return result

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expires_in_seconds: int = 3600,
        method: str = "GET",
    ) -> PresignedUrl:
        """Generate a presigned URL."""
        client_method = "get_object" if method == "GET" else "put_object"

        url = self.client.generate_presigned_url(
            client_method,
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )

        return PresignedUrl(
            url=url,
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=expires_in_seconds),
            method=method,
        )

    async def get_health(self) -> dict[str, Any]:
        """Get S3 health status."""
        return {
            "status": "healthy" if self._connected else "disconnected",
            "region": self.region,
        }

    async def get_bucket_stats(self, bucket: str) -> dict[str, Any]:
        """Get bucket statistics."""
        total_size = 0
        object_count = 0

        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                total_size += obj["Size"]
                object_count += 1

        return {
            "bucket": bucket,
            "object_count": object_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
