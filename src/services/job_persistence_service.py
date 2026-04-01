"""
Project Aura - Job Persistence Service

Provides DynamoDB-backed persistence for ingestion jobs,
enabling job recovery after service restarts and job history queries.

Author: Project Aura Team
Created: 2025-11-28
Version: 1.0.0
"""

import logging
import os
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Boto3 imports (available in AWS environment)
try:
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("Boto3 not available - using mock mode")


class PersistenceMode(Enum):
    """Operating modes for persistence service."""

    MOCK = "mock"  # In-memory storage for testing
    AWS = "aws"  # Real DynamoDB


class JobPersistenceError(Exception):
    """General persistence operation error."""


class JobPersistenceService:
    """
    DynamoDB-backed persistence for ingestion jobs.

    Features:
    - Save and retrieve job state
    - Query jobs by repository, status, or time range
    - Automatic TTL for job cleanup (30 days default)
    - Support for both mock (testing) and AWS modes

    Usage:
        >>> service = JobPersistenceService(mode=PersistenceMode.AWS)
        >>> service.save_job(job)
        >>> job = service.get_job("job-123")
        >>> active_jobs = service.get_jobs_by_status("IN_PROGRESS")
    """

    # Default TTL: 30 days
    DEFAULT_TTL_DAYS = 30

    def __init__(
        self,
        mode: PersistenceMode = PersistenceMode.MOCK,
        table_name: str | None = None,
        region: str | None = None,
    ):
        """
        Initialize Job Persistence Service.

        Args:
            mode: Operating mode (MOCK or AWS)
            table_name: DynamoDB table name (default: aura-ingestion-jobs-{env})
            region: AWS region (default: us-east-1)
        """
        self.mode = mode
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        # Determine table name
        env = os.environ.get("ENVIRONMENT", "dev")
        project = os.environ.get("PROJECT_NAME", "aura")
        self.table_name = table_name or f"{project}-ingestion-jobs-{env}"

        # In-memory store for mock mode
        self.mock_store: dict[str, dict[str, Any]] = {}

        # Initialize DynamoDB client
        if self.mode == PersistenceMode.AWS and BOTO3_AVAILABLE:
            self._init_dynamodb_client()
        else:
            if self.mode == PersistenceMode.AWS:
                logger.warning(
                    "AWS mode requested but boto3 not available. Using MOCK mode."
                )
                self.mode = PersistenceMode.MOCK
            self._init_mock_mode()

        logger.info(
            f"JobPersistenceService initialized in {self.mode.value} mode "
            f"(table: {self.table_name})"
        )

    def _init_dynamodb_client(self) -> None:
        """Initialize DynamoDB client."""
        try:
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.table = self.dynamodb.Table(self.table_name)

            # Verify table exists
            self.table.load()
            logger.info(f"Connected to DynamoDB table: {self.table_name}")

        except Exception as e:
            logger.error(f"Failed to connect to DynamoDB: {e}")
            logger.warning("Falling back to MOCK mode")
            self.mode = PersistenceMode.MOCK
            self._init_mock_mode()

    def _init_mock_mode(self) -> None:
        """Initialize mock mode."""
        logger.info("Mock mode initialized (in-memory storage)")

    def save_job(self, job: Any) -> bool:
        """
        Save or update a job in the database.

        Args:
            job: IngestionJob dataclass instance

        Returns:
            True if successful
        """
        try:
            # Convert job to dictionary
            if hasattr(job, "__dataclass_fields__"):
                job_dict = asdict(job)
            else:
                job_dict = dict(job) if hasattr(job, "keys") else vars(job)

            # Convert enums to strings
            for key, value in job_dict.items():
                if isinstance(value, Enum):
                    job_dict[key] = value.value
                elif isinstance(value, datetime):
                    job_dict[key] = value.isoformat()

            # Add metadata for DynamoDB
            job_dict["repositoryId"] = self._extract_repo_id(
                job_dict.get("repository_url", "")
            )

            # Parse created_at timestamp
            created_at_str = job_dict.get("created_at", datetime.now().isoformat())
            if isinstance(created_at_str, str):
                created_at_dt = datetime.fromisoformat(created_at_str)
                job_dict["createdAt"] = int(created_at_dt.timestamp())
            else:
                created_at_dt = datetime.now()
                job_dict["createdAt"] = int(time.time())

            # Add date partition for efficient time-range queries (DatePartitionIndex GSI)
            job_dict["datePartition"] = created_at_dt.strftime("%Y-%m-%d")
            job_dict["updatedAt"] = int(time.time())

            # Calculate TTL (30 days from now)
            job_dict["ttl"] = int(time.time()) + (self.DEFAULT_TTL_DAYS * 24 * 60 * 60)

            if self.mode == PersistenceMode.MOCK:
                self.mock_store[job_dict["job_id"]] = job_dict
                logger.info(f"[MOCK] Saved job: {job_dict['job_id']}")
                return True

            # Real DynamoDB operation
            # DynamoDB table uses camelCase key "jobId", transform from snake_case
            dynamo_item = job_dict.copy()
            dynamo_item["jobId"] = dynamo_item.pop("job_id")
            self.table.put_item(Item=dynamo_item)
            logger.info(f"Saved job to DynamoDB: {job_dict['job_id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to save job: {e}")
            raise JobPersistenceError(f"Failed to save job: {e}") from e

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """
        Retrieve a job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job dictionary or None if not found
        """
        try:
            if self.mode == PersistenceMode.MOCK:
                return self.mock_store.get(job_id)

            # Real DynamoDB operation
            response = self.table.get_item(Key={"jobId": job_id})
            item = response.get("Item")
            if item and "jobId" in item:
                # Transform camelCase back to snake_case for consistency
                item["job_id"] = item.pop("jobId")
            return item

        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None

    def get_jobs_by_status(
        self,
        status: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query jobs by status.

        Args:
            status: Job status (e.g., "IN_PROGRESS", "COMPLETED", "FAILED")
            limit: Maximum number of results

        Returns:
            List of job dictionaries
        """
        try:
            if self.mode == PersistenceMode.MOCK:
                jobs = [
                    job
                    for job in self.mock_store.values()
                    if job.get("status") == status
                ]
                # Sort by createdAt descending
                jobs.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
                return jobs[:limit]

            # Real DynamoDB query using StatusIndex GSI
            # Note: 'status' is a DynamoDB reserved keyword, use ExpressionAttributeNames
            response = self.table.query(
                IndexName="StatusIndex",
                KeyConditionExpression="#job_status = :status",
                ExpressionAttributeNames={"#job_status": "status"},
                ExpressionAttributeValues={":status": status},
                ScanIndexForward=False,  # Descending order
                Limit=limit,
            )

            return response.get("Items", [])

        except Exception as e:
            logger.error(f"Failed to query jobs by status: {e}")
            return []

    def get_jobs_by_repository(
        self,
        repository_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query jobs for a specific repository.

        Args:
            repository_id: Repository identifier (e.g., "owner/repo")
            limit: Maximum number of results

        Returns:
            List of job dictionaries
        """
        try:
            if self.mode == PersistenceMode.MOCK:
                jobs = [
                    job
                    for job in self.mock_store.values()
                    if job.get("repositoryId") == repository_id
                ]
                jobs.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
                return jobs[:limit]

            # Real DynamoDB query using RepositoryIndex GSI
            response = self.table.query(
                IndexName="RepositoryIndex",
                KeyConditionExpression="repositoryId = :repoId",
                ExpressionAttributeValues={":repoId": repository_id},
                ScanIndexForward=False,
                Limit=limit,
            )

            return response.get("Items", [])

        except Exception as e:
            logger.error(f"Failed to query jobs by repository: {e}")
            return []

    def get_active_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get all active (in-progress) jobs.

        Optimized to use a single DynamoDB scan with IN filter instead of
        5 separate queries (one per status). This reduces API calls from 5 to 1.

        Returns:
            List of active job dictionaries
        """
        active_statuses = [
            "PENDING",
            "CLONING",
            "PARSING",
            "INDEXING_GRAPH",
            "INDEXING_VECTORS",
        ]

        if self.mode == PersistenceMode.MOCK:
            jobs = [
                job
                for job in self.mock_store.values()
                if job.get("status") in active_statuses
            ]
            jobs.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
            return jobs[:limit]

        try:
            # Single scan with IN filter - reduces 5 API calls to 1
            # Over-fetch to ensure we have enough items after sorting
            response = self.table.scan(
                FilterExpression="#job_status IN (:s1, :s2, :s3, :s4, :s5)",
                ExpressionAttributeNames={"#job_status": "status"},
                ExpressionAttributeValues={
                    ":s1": active_statuses[0],
                    ":s2": active_statuses[1],
                    ":s3": active_statuses[2],
                    ":s4": active_statuses[3],
                    ":s5": active_statuses[4],
                },
                Limit=limit * 3,  # Over-fetch since scan applies filter post-read
            )

            all_jobs = response.get("Items", [])

            # Sort by createdAt descending and limit
            def get_created_at(job: dict[str, Any]) -> int:
                created = job.get("createdAt", 0)
                return int(created) if created else 0

            all_jobs.sort(key=get_created_at, reverse=True)
            return all_jobs[:limit]

        except Exception as e:
            logger.error(f"Failed to get active jobs: {e}")
            return []

    def get_recent_jobs(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get jobs created within the last N hours.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of results

        Returns:
            List of job dictionaries
        """
        cutoff_time = int(time.time()) - (hours * 60 * 60)
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(hours=hours)

        try:
            if self.mode == PersistenceMode.MOCK:
                jobs = [
                    job
                    for job in self.mock_store.values()
                    if job.get("createdAt", 0) >= cutoff_time
                ]
                jobs.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
                return jobs[:limit]

            # Use DatePartitionIndex GSI for efficient time-range queries
            # Query each date partition in the range and collect results
            all_jobs: list[dict[str, Any]] = []
            current_date = start_dt.date()
            end_date = end_dt.date()

            while current_date <= end_date:
                date_partition = current_date.strftime("%Y-%m-%d")
                response = self.table.query(
                    IndexName="DatePartitionIndex",
                    KeyConditionExpression=(
                        "datePartition = :dp AND createdAt >= :cutoff"
                    ),
                    ExpressionAttributeValues={
                        ":dp": date_partition,
                        ":cutoff": cutoff_time,
                    },
                    ScanIndexForward=False,  # Descending order
                )
                all_jobs.extend(response.get("Items", []))

                if len(all_jobs) >= limit:
                    break

                current_date += timedelta(days=1)

            # Sort by createdAt descending
            def get_created_at(job: dict[str, Any]) -> int:
                created = job.get("createdAt", 0)
                return int(created) if created else 0

            all_jobs.sort(key=get_created_at, reverse=True)
            return all_jobs[:limit]

        except Exception as e:
            logger.error(f"Failed to get recent jobs: {e}")
            return []

    def update_job_status(
        self,
        job_id: str,
        status: str,
        additional_updates: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update a job's status and optionally other fields.

        Args:
            job_id: Job identifier
            status: New status value
            additional_updates: Additional fields to update

        Returns:
            True if successful
        """
        try:
            updates = {"status": status, "updatedAt": int(time.time())}
            if additional_updates:
                updates.update(additional_updates)

            if self.mode == PersistenceMode.MOCK:
                if job_id in self.mock_store:
                    self.mock_store[job_id].update(updates)
                    logger.info(f"[MOCK] Updated job {job_id} status to {status}")
                    return True
                return False

            # Real DynamoDB update
            update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates.keys())
            expr_attr_names = {f"#{k}": k for k in updates.keys()}
            expr_attr_values: dict[str, Any] = {f":{k}": v for k, v in updates.items()}

            self.table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
            )

            logger.info(f"Updated job {job_id} status to {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            return False

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from the database.

        Args:
            job_id: Job identifier

        Returns:
            True if successful
        """
        try:
            if self.mode == PersistenceMode.MOCK:
                if job_id in self.mock_store:
                    del self.mock_store[job_id]
                    logger.info(f"[MOCK] Deleted job: {job_id}")
                    return True
                return False

            # Real DynamoDB delete
            self.table.delete_item(Key={"jobId": job_id})
            logger.info(f"Deleted job from DynamoDB: {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete job: {e}")
            return False

    def _extract_repo_id(self, repository_url: str) -> str:
        """Extract repository ID from URL."""
        # Handle GitHub URLs
        url = repository_url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]

        # Extract owner/repo from URL
        parts = url.split("/")
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"

        return url


# Convenience function
def create_persistence_service(
    environment: str | None = None,
) -> JobPersistenceService:
    """
    Create and return a JobPersistenceService instance.

    Args:
        environment: Environment name (dev, qa, prod)

    Returns:
        Configured JobPersistenceService instance
    """
    # Auto-detect mode
    mode = (
        PersistenceMode.AWS
        if BOTO3_AVAILABLE and os.environ.get("AWS_REGION")
        else PersistenceMode.MOCK
    )

    return JobPersistenceService(mode=mode)


if __name__ == "__main__":
    # Demo/test usage
    logging.basicConfig(level=logging.INFO)

    print("Project Aura - Job Persistence Service Demo")
    print("=" * 60)

    service = create_persistence_service()
    print(f"\nMode: {service.mode.value}")
    print(f"Table: {service.table_name}")

    # Test save
    test_job = {
        "job_id": "test-123",
        "repository_url": "https://github.com/test/repo",
        "branch": "main",
        "status": "COMPLETED",
        "files_processed": 10,
        "entities_indexed": 50,
        "embeddings_generated": 10,
        "errors": [],
        "created_at": datetime.now().isoformat(),
    }

    print("\nSaving test job...")
    service.save_job(test_job)

    print("Retrieving job...")
    retrieved = service.get_job("test-123")
    print(f"Retrieved: {retrieved}")

    print("\n" + "=" * 60)
    print("Demo complete!")
