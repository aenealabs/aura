"""
Project Aura - SSR Artifact Storage Service

Provides S3 + DynamoDB storage for bug artifacts in the
Self-Play SWE-RL training pipeline per ADR-050.

Storage Strategy:
- S3: Stores artifact content as tar.gz (test_script, diffs, etc.)
- DynamoDB: Stores metadata, status, validation results (for queries)

This separation handles DynamoDB's 400KB item limit while enabling
efficient queries on artifact metadata.

Author: Project Aura Team
Created: 2026-01-01
Version: 1.0.0
ADR: ADR-050
"""

from __future__ import annotations

import io
import json
import logging
import os
import tarfile
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from src.services.ssr.bug_artifact import (
    ArtifactStatus,
    BugArtifact,
    ValidationPipelineResult,
)

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
    from mypy_boto3_s3.client import S3Client

logger = logging.getLogger(__name__)

# AWS SDK imports with fallback
try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("Boto3 not available - using mock mode")


def _convert_floats_to_decimal(obj: Any) -> Any:
    """
    Recursively convert float values to Decimal for DynamoDB compatibility.

    DynamoDB does not support Python float types directly. This function
    converts floats to Decimal, which is the required numeric type.

    Args:
        obj: Any Python object (dict, list, float, etc.)

    Returns:
        The object with all floats converted to Decimal
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats_to_decimal(item) for item in obj]
    return obj


class ArtifactStorageService:
    """
    S3 + DynamoDB storage service for SSR bug artifacts.

    Usage:
        service = ArtifactStorageService(environment="dev")

        # Store artifact
        await service.store_artifact(artifact)

        # Get artifact with full content
        artifact = await service.get_artifact(artifact_id)

        # List by repository
        artifacts = await service.list_by_repository(repository_id)

        # Update validation results
        await service.update_validation_result(artifact_id, result)
    """

    def __init__(
        self,
        project_name: str = "aura",
        environment: str | None = None,
        region: str | None = None,
        bucket_name: str | None = None,
        table_name: str | None = None,
        kms_key_id: str | None = None,
    ):
        """
        Initialize the artifact storage service.

        Args:
            project_name: Project name for resource naming
            environment: Environment (dev, qa, prod)
            region: AWS region
            bucket_name: Override S3 bucket name
            table_name: Override DynamoDB table name
            kms_key_id: KMS key ID or alias for S3 encryption
        """
        self.project_name = project_name
        self.environment = environment or os.environ.get("ENVIRONMENT", "dev")
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        # Resource names (can be overridden via parameters or env vars)
        self.bucket_name = bucket_name or os.environ.get(
            "SSR_TRAINING_BUCKET",
            f"{project_name}-ssr-training-{self.environment}",
        )
        self.table_name = table_name or os.environ.get(
            "SSR_TRAINING_TABLE",
            f"{project_name}-ssr-training-state-{self.environment}",
        )
        # KMS key for S3 encryption (required by bucket policy)
        self.kms_key_id = kms_key_id or os.environ.get(
            "SSR_KMS_KEY_ID",
            f"alias/{project_name}-ssr-training-{self.environment}",
        )

        # Lazy AWS client initialization
        self._s3: S3Client | None = None
        self._dynamodb: DynamoDBServiceResource | None = None
        self._table: Table | None = None

        # Mock mode for testing
        self._use_mock = not BOTO3_AVAILABLE or self.environment == "test"
        self._mock_artifacts: dict[str, BugArtifact] = {}
        self._mock_s3: dict[str, bytes] = {}

        # Cache for reducing S3 reads
        self._cache: dict[str, tuple[float, BugArtifact]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes

        logger.info(
            f"ArtifactStorageService initialized: bucket={self.bucket_name}, "
            f"table={self.table_name}, mock_mode={self._use_mock}"
        )

    # =========================================================================
    # AWS Client Properties (Lazy Initialization)
    # =========================================================================

    @property
    def s3(self) -> S3Client | None:
        """Get or create S3 client."""
        if self._s3 is None and BOTO3_AVAILABLE and not self._use_mock:
            try:
                self._s3 = boto3.client("s3", region_name=self.region)
            except Exception as e:
                logger.warning(f"Failed to create S3 client: {e}")
                self._use_mock = True
        return self._s3

    @property
    def dynamodb(self) -> DynamoDBServiceResource | None:
        """Get or create DynamoDB resource."""
        if self._dynamodb is None and BOTO3_AVAILABLE and not self._use_mock:
            try:
                self._dynamodb = boto3.resource("dynamodb", region_name=self.region)
            except Exception as e:
                logger.warning(f"Failed to create DynamoDB resource: {e}")
                self._use_mock = True
        return self._dynamodb

    @property
    def table(self) -> Table | None:
        """Get DynamoDB table."""
        if self._table is None and self.dynamodb is not None:
            self._table = self.dynamodb.Table(self.table_name)
        return self._table

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def store_artifact(self, artifact: BugArtifact) -> str:
        """
        Store a new bug artifact.

        Uploads content to S3 and metadata to DynamoDB.

        Args:
            artifact: The bug artifact to store

        Returns:
            The artifact_id of the stored artifact

        Raises:
            Exception: If storage fails
        """
        artifact.update_timestamp()

        if self._use_mock:
            self._mock_artifacts[artifact.artifact_id] = artifact
            logger.debug(f"Stored artifact in mock: {artifact.artifact_id}")
            return artifact.artifact_id

        # Upload content to S3
        s3_uri = await self._upload_to_s3(artifact)
        artifact.s3_uri = s3_uri

        # Store metadata in DynamoDB
        if self.table:
            try:
                self.table.put_item(Item=artifact.to_dict())
                logger.info(f"Stored artifact: {artifact.artifact_id}")
            except ClientError as e:
                logger.error(f"Failed to store artifact metadata: {e}")
                raise

        return artifact.artifact_id

    async def get_artifact(
        self,
        artifact_id: str,
        include_content: bool = True,
    ) -> BugArtifact | None:
        """
        Retrieve a bug artifact by ID.

        Args:
            artifact_id: The artifact ID to retrieve
            include_content: Whether to fetch content from S3

        Returns:
            The artifact or None if not found
        """
        # Check cache first
        if artifact_id in self._cache:
            timestamp, cached = self._cache[artifact_id]
            if time.time() - timestamp < self._cache_ttl_seconds:
                logger.debug(f"Cache hit for artifact: {artifact_id}")
                return cached

        if self._use_mock:
            artifact = self._mock_artifacts.get(artifact_id)
            if artifact:
                # Cache the result (consistent with real mode)
                self._cache[artifact_id] = (time.time(), artifact)
            return artifact

        if not self.table:
            return None

        try:
            response = self.table.get_item(Key={"artifact_id": artifact_id})
            item = response.get("Item")
            if not item:
                return None

            # Fetch content from S3 if requested
            content = None
            if include_content and item.get("s3_uri"):
                content = await self._download_from_s3(item["s3_uri"])

            artifact = BugArtifact.from_dynamodb_item(item, content)

            # Cache the result
            self._cache[artifact_id] = (time.time(), artifact)

            return artifact

        except ClientError as e:
            logger.error(f"Failed to get artifact {artifact_id}: {e}")
            return None

    async def update_artifact(self, artifact: BugArtifact) -> bool:
        """
        Update an existing artifact.

        Args:
            artifact: The artifact with updated fields

        Returns:
            True if update succeeded
        """
        artifact.update_timestamp()

        if self._use_mock:
            if artifact.artifact_id in self._mock_artifacts:
                self._mock_artifacts[artifact.artifact_id] = artifact
                return True
            return False

        if not self.table:
            return False

        try:
            # Update S3 content if needed
            if artifact.s3_uri:
                await self._upload_to_s3(artifact)

            # Update DynamoDB metadata
            self.table.put_item(Item=artifact.to_dict())

            # Invalidate cache
            if artifact.artifact_id in self._cache:
                del self._cache[artifact.artifact_id]

            logger.info(f"Updated artifact: {artifact.artifact_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to update artifact: {e}")
            return False

    async def update_status(
        self,
        artifact_id: str,
        status: ArtifactStatus,
    ) -> bool:
        """
        Update artifact status only.

        More efficient than full update for status transitions.

        Args:
            artifact_id: The artifact ID
            status: New status

        Returns:
            True if update succeeded
        """
        if self._use_mock:
            if artifact_id in self._mock_artifacts:
                self._mock_artifacts[artifact_id].status = status
                self._mock_artifacts[artifact_id].update_timestamp()
                # Invalidate cache (consistent with real mode)
                if artifact_id in self._cache:
                    del self._cache[artifact_id]
                return True
            return False

        if not self.table:
            return False

        try:
            self.table.update_item(
                Key={"artifact_id": artifact_id},
                UpdateExpression="SET #s = :status, updated_at = :updated",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":status": status.value,
                    ":updated": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Invalidate cache
            if artifact_id in self._cache:
                del self._cache[artifact_id]

            return True

        except ClientError as e:
            logger.error(f"Failed to update status: {e}")
            return False

    async def update_validation_result(
        self,
        artifact_id: str,
        result: ValidationPipelineResult,
    ) -> bool:
        """
        Update artifact with validation pipeline result.

        Args:
            artifact_id: The artifact ID
            result: Validation pipeline result

        Returns:
            True if update succeeded
        """
        new_status = (
            ArtifactStatus.VALID if result.is_valid() else ArtifactStatus.INVALID
        )

        if self._use_mock:
            if artifact_id in self._mock_artifacts:
                artifact = self._mock_artifacts[artifact_id]
                artifact.status = new_status
                artifact.validation_results = result.to_dict()
                artifact.update_timestamp()
                return True
            return False

        if not self.table:
            return False

        try:
            self.table.update_item(
                Key={"artifact_id": artifact_id},
                UpdateExpression=(
                    "SET #s = :status, validation_results = :results, "
                    "updated_at = :updated"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":status": new_status.value,
                    ":results": _convert_floats_to_decimal(result.to_dict()),
                    ":updated": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Invalidate cache
            if artifact_id in self._cache:
                del self._cache[artifact_id]

            logger.info(
                f"Updated validation result for {artifact_id}: {new_status.value}"
            )
            return True

        except ClientError as e:
            logger.error(f"Failed to update validation result: {e}")
            return False

    async def delete_artifact(self, artifact_id: str) -> bool:
        """
        Delete an artifact.

        Removes from both S3 and DynamoDB.

        Args:
            artifact_id: The artifact ID to delete

        Returns:
            True if deletion succeeded
        """
        if self._use_mock:
            if artifact_id in self._mock_artifacts:
                del self._mock_artifacts[artifact_id]
                # Invalidate cache (consistent with real mode)
                if artifact_id in self._cache:
                    del self._cache[artifact_id]
                return True
            return False

        # Get artifact to find S3 URI
        artifact = await self.get_artifact(artifact_id, include_content=False)
        if not artifact:
            return False

        try:
            # Delete from S3
            if artifact.s3_uri and self.s3:
                s3_key = artifact.s3_uri.replace(f"s3://{self.bucket_name}/", "")
                self.s3.delete_object(Bucket=self.bucket_name, Key=s3_key)

            # Delete from DynamoDB
            if self.table:
                self.table.delete_item(Key={"artifact_id": artifact_id})

            # Invalidate cache
            if artifact_id in self._cache:
                del self._cache[artifact_id]

            logger.info(f"Deleted artifact: {artifact_id}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete artifact: {e}")
            return False

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def list_by_repository(
        self,
        repository_id: str,
        status: ArtifactStatus | None = None,
        limit: int = 100,
    ) -> list[BugArtifact]:
        """
        List artifacts for a repository.

        Args:
            repository_id: Repository ID to filter by
            status: Optional status filter
            limit: Maximum number of results

        Returns:
            List of artifacts (metadata only, no S3 content)
        """
        if self._use_mock:
            results = [
                a
                for a in self._mock_artifacts.values()
                if a.repository_id == repository_id
                and (status is None or a.status == status)
            ]
            return results[:limit]

        if not self.table:
            return []

        try:
            # Query using GSI
            key_condition = "repository_id = :repo_id"
            expr_values: dict[str, Any] = {":repo_id": repository_id}

            if status:
                # Use the status-created GSI for status filtering
                response = self.table.query(
                    IndexName="status-created-index",
                    KeyConditionExpression="#s = :status",
                    FilterExpression="repository_id = :repo_id",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":status": status.value,
                        ":repo_id": repository_id,
                    },
                    Limit=limit,
                    ScanIndexForward=False,  # Most recent first
                )
            else:
                response = self.table.query(
                    IndexName="repository-created-index",
                    KeyConditionExpression=key_condition,
                    ExpressionAttributeValues=expr_values,
                    Limit=limit,
                    ScanIndexForward=False,
                )

            return [
                BugArtifact.from_dynamodb_item(item)
                for item in response.get("Items", [])
            ]

        except ClientError as e:
            logger.error(f"Failed to list artifacts: {e}")
            return []

    async def list_pending_validation(self, limit: int = 100) -> list[BugArtifact]:
        """
        List artifacts pending validation.

        Args:
            limit: Maximum number of results

        Returns:
            List of pending artifacts
        """
        if self._use_mock:
            return [
                a
                for a in self._mock_artifacts.values()
                if a.status == ArtifactStatus.PENDING
            ][:limit]

        if not self.table:
            return []

        try:
            response = self.table.query(
                IndexName="status-created-index",
                KeyConditionExpression="#s = :status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":status": ArtifactStatus.PENDING.value},
                Limit=limit,
                ScanIndexForward=True,  # Oldest first (FIFO)
            )

            return [
                BugArtifact.from_dynamodb_item(item)
                for item in response.get("Items", [])
            ]

        except ClientError as e:
            logger.error(f"Failed to list pending artifacts: {e}")
            return []

    async def count_by_status(
        self,
        repository_id: str | None = None,
    ) -> dict[str, int]:
        """
        Count artifacts by status.

        Args:
            repository_id: Optional repository filter

        Returns:
            Dictionary of status -> count
        """
        if self._use_mock:
            counts: dict[str, int] = {}
            for artifact in self._mock_artifacts.values():
                if repository_id and artifact.repository_id != repository_id:
                    continue
                status = artifact.status.value
                counts[status] = counts.get(status, 0) + 1
            return counts

        # For real DynamoDB, we'd need to scan or maintain counters
        # This is a simplified implementation
        counts = {}
        for status in ArtifactStatus:
            artifacts = await self.list_by_repository(
                repository_id or "", status=status, limit=1000
            )
            if artifacts:
                counts[status.value] = len(artifacts)

        return counts

    # =========================================================================
    # S3 Operations
    # =========================================================================

    async def _upload_to_s3(self, artifact: BugArtifact) -> str:
        """
        Upload artifact content to S3 as tar.gz.

        Args:
            artifact: The artifact to upload

        Returns:
            S3 URI of the uploaded content
        """
        if self._use_mock:
            s3_uri = f"s3://{self.bucket_name}/artifacts/{artifact.artifact_id}.tar.gz"
            # Store compressed content in mock
            content = self._create_tar_gz(artifact)
            self._mock_s3[s3_uri] = content
            return s3_uri

        if not self.s3:
            raise RuntimeError("S3 client not available")

        s3_key = f"artifacts/{artifact.artifact_id}.tar.gz"
        content = self._create_tar_gz(artifact)

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content,
                ContentType="application/gzip",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=self.kms_key_id,
                Metadata={
                    "artifact_id": artifact.artifact_id,
                    "repository_id": artifact.repository_id,
                    "status": artifact.status.value,
                },
            )

            return f"s3://{self.bucket_name}/{s3_key}"

        except ClientError as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise

    async def _download_from_s3(self, s3_uri: str) -> dict[str, Any]:
        """
        Download artifact content from S3.

        Args:
            s3_uri: S3 URI to download

        Returns:
            Dictionary with artifact content fields
        """
        if self._use_mock:
            content = self._mock_s3.get(s3_uri)
            if content:
                return self._extract_tar_gz(content)
            return {}

        if not self.s3:
            return {}

        s3_key = s3_uri.replace(f"s3://{self.bucket_name}/", "")

        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response["Body"].read()
            return self._extract_tar_gz(content)

        except ClientError as e:
            logger.error(f"Failed to download from S3: {e}")
            return {}

    def _create_tar_gz(self, artifact: BugArtifact) -> bytes:
        """Create tar.gz archive from artifact content."""
        buffer = io.BytesIO()

        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            # Add test_script.sh
            self._add_string_to_tar(tar, "test_script.sh", artifact.test_script)

            # Add test_files.json
            self._add_string_to_tar(
                tar, "test_files.json", json.dumps(artifact.test_files)
            )

            # Add test_parser.py
            self._add_string_to_tar(tar, "test_parser.py", artifact.test_parser)

            # Add bug_inject.diff
            self._add_string_to_tar(tar, "bug_inject.diff", artifact.bug_inject_diff)

            # Add test_weaken.diff
            self._add_string_to_tar(tar, "test_weaken.diff", artifact.test_weaken_diff)

            # Add failed_patch.diff if present (higher-order bugs)
            if artifact.failed_patch_diff:
                self._add_string_to_tar(
                    tar, "failed_patch.diff", artifact.failed_patch_diff
                )

            # Add metadata.json
            metadata = {
                "artifact_id": artifact.artifact_id,
                "repository_id": artifact.repository_id,
                "commit_sha": artifact.commit_sha,
                "order": artifact.order,
                "parent_artifact_id": artifact.parent_artifact_id,
                "injection_strategy": artifact.injection_strategy.value,
                "created_at": artifact.created_at,
            }
            self._add_string_to_tar(tar, "metadata.json", json.dumps(metadata))

        return buffer.getvalue()

    def _add_string_to_tar(self, tar: tarfile.TarFile, name: str, content: str) -> None:
        """Add a string as a file to tar archive."""
        data = content.encode("utf-8")
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    def _extract_tar_gz(self, data: bytes) -> dict[str, Any]:
        """Extract content from tar.gz archive."""
        result: dict[str, Any] = {}

        buffer = io.BytesIO(data)
        with tarfile.open(fileobj=buffer, mode="r:gz") as tar:
            for member in tar.getmembers():
                f = tar.extractfile(member)
                if f:
                    content = f.read().decode("utf-8")
                    if member.name == "test_files.json":
                        result["test_files"] = json.loads(content)
                    elif member.name == "metadata.json":
                        # Metadata is stored separately, skip
                        pass
                    else:
                        # Map filename to field name
                        field_name = (
                            member.name.replace(".sh", "")
                            .replace(".py", "")
                            .replace(".diff", "_diff")
                        )
                        result[field_name] = content

        return result

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """
        Check service health.

        Returns:
            Health status dictionary
        """
        status: dict[str, Any] = {
            "service": "artifact_storage",
            "status": "healthy",
            "mock_mode": self._use_mock,
            "bucket": self.bucket_name,
            "table": self.table_name,
            "cache_entries": len(self._cache),
        }

        if self._use_mock:
            status["mock_artifacts"] = len(self._mock_artifacts)
            return status

        # Check S3
        try:
            if self.s3:
                self.s3.head_bucket(Bucket=self.bucket_name)
                status["s3_status"] = "connected"
        except Exception as e:
            status["s3_status"] = f"error: {e}"
            status["status"] = "degraded"

        # Check DynamoDB
        try:
            if self.table:
                self.table.table_status
                status["dynamodb_status"] = "connected"
        except Exception as e:
            status["dynamodb_status"] = f"error: {e}"
            status["status"] = "degraded"

        return status


# =============================================================================
# Factory Function
# =============================================================================


def create_artifact_storage_service(
    project_name: str = "aura",
    environment: str | None = None,
    region: str | None = None,
) -> ArtifactStorageService:
    """
    Factory function to create an ArtifactStorageService.

    Args:
        project_name: Project name for resource naming
        environment: Environment (dev, qa, prod)
        region: AWS region

    Returns:
        Configured ArtifactStorageService instance
    """
    return ArtifactStorageService(
        project_name=project_name,
        environment=environment,
        region=region,
    )
