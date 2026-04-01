"""
Project Aura - Repository Onboarding Service

Orchestrates repository onboarding workflow including:
- Repository configuration management
- Integration with GitIngestionService
- Ingestion job tracking

Author: Project Aura Team
Created: 2025-12-17
Version: 1.0.0
"""

import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, cast

import boto3
from botocore.exceptions import ClientError

from src.services.oauth_provider_service import (
    OAuthProviderService,
    ProviderRepository,
    get_oauth_service,
)

logger = logging.getLogger(__name__)


class RepositoryStatus(Enum):
    """Repository status values."""

    PENDING = "pending"
    ACTIVE = "active"
    SYNCING = "syncing"
    ERROR = "error"
    ARCHIVED = "archived"


class IngestionJobStatus(Enum):
    """Ingestion job status values."""

    PENDING = "pending"
    CLONING = "cloning"
    PARSING = "parsing"
    INDEXING_GRAPH = "indexing_graph"
    INDEXING_VECTORS = "indexing_vectors"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanFrequency(Enum):
    """Repository scan frequency options."""

    ON_PUSH = "on_push"
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"


@dataclass
class RepositoryConfig:
    """Repository configuration."""

    repository_id: str | None = None
    connection_id: str | None = None
    provider_repo_id: str | None = None
    clone_url: str | None = None
    token: str | None = None  # For manual URL+token
    name: str = ""
    branch: str = "main"
    languages: list[str] = field(
        default_factory=lambda: ["python", "javascript", "typescript"]
    )
    scan_frequency: str = "on_push"
    exclude_patterns: list[str] = field(default_factory=list)
    enable_webhook: bool = True


@dataclass
class Repository:
    """Repository entity."""

    repository_id: str
    user_id: str
    name: str
    provider: str
    clone_url: str
    branch: str
    languages: list[str]
    scan_frequency: str
    status: str
    exclude_patterns: list[str]
    webhook_id: str | None = None
    last_ingestion_at: str | None = None
    last_ingestion_job_id: str | None = None
    file_count: int = 0
    entity_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "Repository":
        """Create Repository from DynamoDB item with proper type casting."""
        return cls(
            repository_id=str(item["repository_id"]),
            user_id=str(item["user_id"]),
            name=str(item["name"]),
            provider=str(item["provider"]),
            clone_url=str(item["clone_url"]),
            branch=str(item.get("branch", "main")),
            languages=cast(list[str], item.get("languages", [])),
            scan_frequency=str(item.get("scan_frequency", "on_push")),
            status=str(item.get("status", RepositoryStatus.PENDING.value)),
            exclude_patterns=cast(list[str], item.get("exclude_patterns", [])),
            webhook_id=str(item["webhook_id"]) if item.get("webhook_id") else None,
            last_ingestion_at=(
                str(item["last_ingestion_at"])
                if item.get("last_ingestion_at")
                else None
            ),
            last_ingestion_job_id=(
                str(item["last_ingestion_job_id"])
                if item.get("last_ingestion_job_id")
                else None
            ),
            file_count=int(item.get("file_count", 0)),
            entity_count=int(item.get("entity_count", 0)),
            created_at=str(item.get("created_at", "")),
            updated_at=str(item.get("updated_at", "")),
        )


@dataclass
class IngestionJob:
    """Ingestion job entity."""

    job_id: str
    repository_id: str
    user_id: str
    status: str
    progress: int = 0
    files_processed: int = 0
    entities_indexed: int = 0
    embeddings_generated: int = 0
    current_stage: str = "pending"
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str = ""

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "IngestionJob":
        """Create IngestionJob from DynamoDB item with proper type casting."""
        return cls(
            job_id=str(item["job_id"]),
            repository_id=str(item["repository_id"]),
            user_id=str(item["user_id"]),
            status=str(item.get("status", IngestionJobStatus.PENDING.value)),
            progress=int(item.get("progress", 0)),
            files_processed=int(item.get("files_processed", 0)),
            entities_indexed=int(item.get("entities_indexed", 0)),
            embeddings_generated=int(item.get("embeddings_generated", 0)),
            current_stage=str(item.get("current_stage", "pending")),
            error_message=(
                str(item["error_message"]) if item.get("error_message") else None
            ),
            started_at=str(item["started_at"]) if item.get("started_at") else None,
            completed_at=(
                str(item["completed_at"]) if item.get("completed_at") else None
            ),
            created_at=str(item.get("created_at", "")),
        )


class RepositoryOnboardService:
    """
    Repository Onboarding Service.

    Orchestrates the repository onboarding workflow:
    1. Add repositories from OAuth connections or manual URL
    2. Configure analysis settings
    3. Trigger ingestion via GitIngestionService
    4. Track ingestion job status
    5. Manage webhooks for incremental updates
    """

    def __init__(
        self,
        dynamodb_client: Any | None = None,
        secrets_client: Any | None = None,
        oauth_service: OAuthProviderService | None = None,
        environment: str | None = None,
        project_name: str = "aura",
    ):
        """Initialize repository onboard service."""
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self.project_name = project_name

        self.dynamodb = dynamodb_client or boto3.resource("dynamodb")
        self.secrets_client = secrets_client or boto3.client("secretsmanager")
        self.oauth_service = oauth_service or get_oauth_service()

        self.repositories_table = self.dynamodb.Table(
            f"{project_name}-repositories-{self.environment}"
        )
        self.jobs_table = self.dynamodb.Table(
            f"{project_name}-ingestion-jobs-{self.environment}"
        )

    async def list_repositories(self, user_id: str) -> list[Repository]:
        """List user's connected repositories."""
        try:
            response = self.repositories_table.query(
                IndexName="user-index",
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
                ScanIndexForward=False,  # Most recent first
            )

            repositories = []
            for item in response.get("Items", []):
                repositories.append(Repository.from_dynamodb_item(item))
            return repositories
        except ClientError as e:
            logger.error(f"Error listing repositories: {e}")
            return []

    async def list_available_repositories(
        self, user_id: str, connection_id: str
    ) -> list[ProviderRepository]:
        """List available repositories from OAuth provider."""
        # Verify connection ownership
        connections = await self.oauth_service.list_connections(user_id)
        if not any(c.connection_id == connection_id for c in connections):
            raise ValueError("Connection not found or not authorized")

        return await self.oauth_service.list_repositories(connection_id)

    async def add_repository(
        self, user_id: str, config: RepositoryConfig
    ) -> Repository:
        """
        Add a repository (manual URL+token).

        For OAuth-connected repos, use add_repositories_from_connection instead.
        """
        if not config.clone_url:
            raise ValueError("clone_url is required for manual repository")

        repository_id = secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc).isoformat()
        clone_url: str = config.clone_url

        # Store token in Secrets Manager if provided
        if config.token:
            secret_name = (
                f"/{self.project_name}/{self.environment}/repos/{repository_id}/token"
            )
            try:
                self.secrets_client.create_secret(
                    Name=secret_name,
                    SecretString=json.dumps({"token": config.token}),
                    Tags=[
                        {"Key": "Project", "Value": self.project_name},
                        {"Key": "Environment", "Value": self.environment},
                        {"Key": "Component", "Value": "repository"},
                    ],
                )
            except ClientError as e:
                logger.error(f"Failed to store repository token: {e}")
                raise

        repo_name = config.name or clone_url.split("/")[-1].replace(".git", "")

        repository = Repository(
            repository_id=repository_id,
            user_id=user_id,
            name=repo_name,
            provider="manual",
            clone_url=clone_url,
            branch=config.branch,
            languages=config.languages,
            scan_frequency=config.scan_frequency,
            status=RepositoryStatus.PENDING.value,
            exclude_patterns=config.exclude_patterns,
            created_at=now,
            updated_at=now,
        )

        self.repositories_table.put_item(
            Item={
                "repository_id": repository_id,
                "user_id": user_id,
                "name": repo_name,
                "provider": "manual",
                "clone_url": clone_url,
                "branch": config.branch,
                "languages": config.languages,
                "scan_frequency": config.scan_frequency,
                "status": RepositoryStatus.PENDING.value,
                "exclude_patterns": config.exclude_patterns,
                "secrets_arn": (
                    f"/{self.project_name}/{self.environment}/repos/{repository_id}/token"
                    if config.token
                    else None
                ),
                "created_at": now,
                "updated_at": now,
            }
        )

        logger.info(f"Added repository: {repository_id} for user={user_id}")
        return repository

    async def add_repositories_from_connection(
        self, user_id: str, connection_id: str, configs: list[RepositoryConfig]
    ) -> list[Repository]:
        """Add multiple repositories from an OAuth connection."""
        # Verify connection
        connections = await self.oauth_service.list_connections(user_id)
        connection = next(
            (c for c in connections if c.connection_id == connection_id), None
        )
        if not connection:
            raise ValueError("Connection not found or not authorized")

        repositories: list[Repository] = []
        now = datetime.now(timezone.utc).isoformat()

        for config in configs:
            if not config.clone_url:
                logger.warning(
                    f"Skipping repository config without clone_url: {config.name}"
                )
                continue

            repository_id = secrets.token_urlsafe(16)
            clone_url: str = config.clone_url

            repository = Repository(
                repository_id=repository_id,
                user_id=user_id,
                name=config.name,
                provider=connection.provider,
                clone_url=clone_url,
                branch=config.branch,
                languages=config.languages,
                scan_frequency=config.scan_frequency,
                status=RepositoryStatus.PENDING.value,
                exclude_patterns=config.exclude_patterns,
                created_at=now,
                updated_at=now,
            )

            self.repositories_table.put_item(
                Item={
                    "repository_id": repository_id,
                    "user_id": user_id,
                    "name": config.name,
                    "provider": connection.provider,
                    "provider_repo_id": config.provider_repo_id,
                    "connection_id": connection_id,
                    "clone_url": clone_url,
                    "branch": config.branch,
                    "languages": config.languages,
                    "scan_frequency": config.scan_frequency,
                    "status": RepositoryStatus.PENDING.value,
                    "exclude_patterns": config.exclude_patterns,
                    "enable_webhook": config.enable_webhook,
                    "created_at": now,
                    "updated_at": now,
                }
            )

            repositories.append(repository)
            logger.info(
                f"Added repository: {repository_id} from connection={connection_id}"
            )

        return repositories

    async def get_repository(
        self, user_id: str, repository_id: str
    ) -> Repository | None:
        """Get repository details."""
        try:
            response = self.repositories_table.get_item(
                Key={"repository_id": repository_id}
            )
            item = response.get("Item")
            if not item or item.get("user_id") != user_id:
                return None

            return Repository.from_dynamodb_item(item)
        except ClientError as e:
            logger.error(f"Error getting repository: {e}")
            return None

    async def update_repository(
        self, user_id: str, repository_id: str, config: RepositoryConfig
    ) -> Repository:
        """Update repository settings."""
        # Verify ownership
        existing = await self.get_repository(user_id, repository_id)
        if not existing:
            raise ValueError("Repository not found or not authorized")

        now = datetime.now(timezone.utc).isoformat()

        self.repositories_table.update_item(
            Key={"repository_id": repository_id},
            UpdateExpression="""
                SET branch = :branch,
                    languages = :languages,
                    scan_frequency = :scan_frequency,
                    exclude_patterns = :exclude_patterns,
                    updated_at = :updated_at
            """,
            ExpressionAttributeValues={
                ":branch": config.branch,
                ":languages": config.languages,
                ":scan_frequency": config.scan_frequency,
                ":exclude_patterns": config.exclude_patterns,
                ":updated_at": now,
            },
        )

        existing.branch = config.branch
        existing.languages = config.languages
        existing.scan_frequency = config.scan_frequency
        existing.exclude_patterns = config.exclude_patterns
        existing.updated_at = now

        logger.info(f"Updated repository: {repository_id}")
        return existing

    async def delete_repository(self, user_id: str, repository_id: str) -> None:
        """Remove a repository."""
        # Verify ownership
        existing = await self.get_repository(user_id, repository_id)
        if not existing:
            raise ValueError("Repository not found or not authorized")

        # Get item to find secrets ARN
        response = self.repositories_table.get_item(
            Key={"repository_id": repository_id}
        )
        item = response.get("Item", {})
        secrets_arn = item.get("secrets_arn")

        # Delete secret if exists
        if secrets_arn:
            try:
                self.secrets_client.delete_secret(
                    SecretId=secrets_arn,
                    ForceDeleteWithoutRecovery=True,
                )
            except ClientError as e:
                logger.warning(f"Failed to delete repository secret: {e}")

        # Delete repository
        self.repositories_table.delete_item(Key={"repository_id": repository_id})
        logger.info(f"Deleted repository: {repository_id}")

    async def start_ingestion(
        self, user_id: str, repository_configs: list[RepositoryConfig]
    ) -> list[IngestionJob]:
        """
        Start ingestion for multiple repositories.

        This creates ingestion jobs and triggers the GitIngestionService.
        """
        jobs = []
        now = datetime.now(timezone.utc).isoformat()
        ttl = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())

        for config in repository_configs:
            if not config.repository_id:
                logger.warning("Skipping config without repository_id")
                continue

            job_id = secrets.token_urlsafe(16)
            repository_id: str = config.repository_id

            # Get repository to get clone URL and token
            repo = await self.get_repository(user_id, repository_id)
            if not repo:
                logger.warning(f"Repository not found: {repository_id}")
                continue

            job = IngestionJob(
                job_id=job_id,
                repository_id=repository_id,
                user_id=user_id,
                status=IngestionJobStatus.PENDING.value,
                current_stage="pending",
                created_at=now,
            )

            # Store job in DynamoDB
            self.jobs_table.put_item(
                Item={
                    "job_id": job_id,
                    "repository_id": repository_id,
                    "user_id": user_id,
                    "status": IngestionJobStatus.PENDING.value,
                    "progress": 0,
                    "files_processed": 0,
                    "entities_indexed": 0,
                    "embeddings_generated": 0,
                    "current_stage": "pending",
                    "created_at": now,
                    "ttl": ttl,
                }
            )

            # Update repository status
            self.repositories_table.update_item(
                Key={"repository_id": repository_id},
                UpdateExpression="SET #s = :status, last_ingestion_job_id = :job_id, updated_at = :now",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":status": RepositoryStatus.SYNCING.value,
                    ":job_id": job_id,
                    ":now": now,
                },
            )

            jobs.append(job)
            logger.info(
                f"Created ingestion job: {job_id} for repository={repository_id}"
            )

            # TODO: Trigger actual GitIngestionService
            # This would call:
            # await self.git_ingestion_service.ingest_repository(
            #     repository_url=repo.clone_url,
            #     branch=repo.branch,
            #     github_token=token,
            #     job_id=job_id
            # )

        return jobs

    async def get_ingestion_status(
        self, user_id: str, job_ids: list[str]
    ) -> list[IngestionJob]:
        """Get status of ingestion jobs.

        Uses batch_get_item for efficient retrieval of multiple jobs
        instead of sequential get_item calls (N+1 pattern).
        """
        if not job_ids:
            return []

        jobs: list[IngestionJob] = []
        table_name = self.jobs_table.table_name

        # DynamoDB batch_get_item supports up to 100 items per call
        batch_size = 100
        for i in range(0, len(job_ids), batch_size):
            batch_ids = job_ids[i : i + batch_size]

            try:
                response = self.dynamodb.batch_get_item(
                    RequestItems={
                        table_name: {
                            "Keys": [{"job_id": job_id} for job_id in batch_ids],
                            "ConsistentRead": False,
                        }
                    }
                )

                # Process returned items
                items = response.get("Responses", {}).get(table_name, [])
                for item in items:
                    if item.get("user_id") == user_id:
                        jobs.append(IngestionJob.from_dynamodb_item(item))

                # Handle unprocessed keys (retry logic for throttling)
                unprocessed = response.get("UnprocessedKeys", {})
                retry_count = 0
                while unprocessed.get(table_name) and retry_count < 3:
                    retry_count += 1
                    logger.warning(
                        f"Retrying {len(unprocessed[table_name]['Keys'])} "
                        f"unprocessed keys (attempt {retry_count})"
                    )
                    response = self.dynamodb.batch_get_item(RequestItems=unprocessed)
                    items = response.get("Responses", {}).get(table_name, [])
                    for item in items:
                        if item.get("user_id") == user_id:
                            jobs.append(IngestionJob.from_dynamodb_item(item))
                    unprocessed = response.get("UnprocessedKeys", {})

            except ClientError as e:
                logger.error(f"Error in batch_get_item: {e}")

        return jobs

    async def cancel_ingestion(self, user_id: str, job_id: str) -> None:
        """Cancel an in-progress ingestion job."""
        # Verify ownership
        response = self.jobs_table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        if not item or item.get("user_id") != user_id:
            raise ValueError("Job not found or not authorized")

        # Only cancel if not already completed
        if item.get("status") in [
            IngestionJobStatus.COMPLETED.value,
            IngestionJobStatus.FAILED.value,
            IngestionJobStatus.CANCELLED.value,
        ]:
            raise ValueError("Job already completed or cancelled")

        now = datetime.now(timezone.utc).isoformat()

        # Update job status
        self.jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #s = :status, completed_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": IngestionJobStatus.CANCELLED.value,
                ":now": now,
            },
        )

        # Update repository status
        repository_id = item.get("repository_id")
        if repository_id:
            self.repositories_table.update_item(
                Key={"repository_id": repository_id},
                UpdateExpression="SET #s = :status, updated_at = :now",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":status": RepositoryStatus.PENDING.value,
                    ":now": now,
                },
            )

        logger.info(f"Cancelled ingestion job: {job_id}")

    async def update_job_progress(
        self,
        job_id: str,
        status: str,
        progress: int = 0,
        files_processed: int = 0,
        entities_indexed: int = 0,
        embeddings_generated: int = 0,
        current_stage: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update ingestion job progress (called by GitIngestionService)."""
        now = datetime.now(timezone.utc).isoformat()

        update_expr = """
            SET #s = :status,
                progress = :progress,
                files_processed = :files_processed,
                entities_indexed = :entities_indexed,
                embeddings_generated = :embeddings_generated
        """
        expr_values: dict[str, str | int] = {
            ":status": status,
            ":progress": progress,
            ":files_processed": files_processed,
            ":entities_indexed": entities_indexed,
            ":embeddings_generated": embeddings_generated,
        }

        if current_stage:
            update_expr += ", current_stage = :stage"
            expr_values[":stage"] = current_stage

        if status == IngestionJobStatus.PENDING.value:
            update_expr += ", started_at = :now"
            expr_values[":now"] = now

        if status in [
            IngestionJobStatus.COMPLETED.value,
            IngestionJobStatus.FAILED.value,
        ]:
            update_expr += ", completed_at = :completed_at"
            expr_values[":completed_at"] = now

        if error_message:
            update_expr += ", error_message = :error"
            expr_values[":error"] = error_message

        self.jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues=expr_values,
        )

        # If completed, update repository stats
        if status == IngestionJobStatus.COMPLETED.value:
            response = self.jobs_table.get_item(Key={"job_id": job_id})
            item = response.get("Item", {})
            repository_id = item.get("repository_id")

            if repository_id:
                self.repositories_table.update_item(
                    Key={"repository_id": repository_id},
                    UpdateExpression="""
                        SET #s = :status,
                            file_count = :files,
                            entity_count = :entities,
                            last_ingestion_at = :now,
                            updated_at = :now
                    """,
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":status": RepositoryStatus.ACTIVE.value,
                        ":files": files_processed,
                        ":entities": entities_indexed,
                        ":now": now,
                    },
                )


# Singleton instance
_repository_service: RepositoryOnboardService | None = None


def get_repository_service() -> RepositoryOnboardService:
    """Get or create repository service singleton."""
    global _repository_service
    if _repository_service is None:
        _repository_service = RepositoryOnboardService()
    return _repository_service
