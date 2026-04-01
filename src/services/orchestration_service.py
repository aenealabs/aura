"""
Orchestration Service for Agent Orchestrator Job Management.

This service manages the submission, tracking, and retrieval of agent orchestrator
jobs using DynamoDB for state storage and SQS for job dispatch.

Architecture:
    API Request -> OrchestrationService -> SQS Queue -> Dispatcher Lambda -> EKS Job
                                        -> DynamoDB (job state tracking)

Follows the dual-mode persistence pattern from job_persistence_service.py.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource
    from mypy_boto3_sqs.client import SQSClient

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Status of an orchestration job."""

    QUEUED = "QUEUED"  # Job submitted to SQS
    DISPATCHED = "DISPATCHED"  # Dispatcher picked up job
    RUNNING = "RUNNING"  # EKS Job is executing
    SUCCEEDED = "SUCCEEDED"  # Job completed successfully
    FAILED = "FAILED"  # Job failed
    CANCELLED = "CANCELLED"  # Job was cancelled
    TIMED_OUT = "TIMED_OUT"  # Job exceeded deadline


class JobPriority(Enum):
    """Priority level for job scheduling."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PersistenceMode(Enum):
    """Persistence mode for the service."""

    MOCK = "mock"
    AWS = "aws"


@dataclass
class OrchestrationJob:
    """Represents an orchestration job."""

    job_id: str
    task_id: str
    user_id: str
    prompt: str
    status: JobStatus
    priority: JobPriority
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl: int | None = None  # Unix timestamp for DynamoDB TTL

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for DynamoDB storage."""
        data: dict[str, Any] = {
            "job_id": self.job_id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "prompt": self.prompt,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
        if self.started_at:
            data["started_at"] = self.started_at
        if self.completed_at:
            data["completed_at"] = self.completed_at
        if self.result:
            data["result"] = self.result
        if self.error_message:
            data["error_message"] = self.error_message
        if self.ttl:
            data["ttl"] = self.ttl
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrchestrationJob":
        """Create from dictionary."""
        return cls(
            job_id=data["job_id"],
            task_id=data["task_id"],
            user_id=data["user_id"],
            prompt=data["prompt"],
            status=JobStatus(data["status"]),
            priority=JobPriority(data.get("priority", "NORMAL")),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            result=data.get("result"),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
            ttl=data.get("ttl"),
        )


@dataclass
class JobSubmission:
    """Request to submit a new orchestration job."""

    prompt: str
    user_id: str
    priority: JobPriority = JobPriority.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)
    callback_url: str | None = None  # Webhook URL for completion notification


class OrchestrationService:
    """
    Service for managing agent orchestration jobs.

    Supports MOCK mode for testing and AWS mode for production.
    """

    DEFAULT_TTL_DAYS = 7  # Jobs expire after 7 days
    TABLE_NAME_TEMPLATE = "{project}-orchestrator-jobs-{env}"
    QUEUE_NAME_TEMPLATE = "{project}-orchestrator-tasks-{env}"

    def __init__(
        self,
        mode: PersistenceMode = PersistenceMode.MOCK,
        table_name: str | None = None,
        queue_url: str | None = None,
        project_name: str = "aura",
        environment: str = "dev",
        region: str | None = None,
    ):
        """
        Initialize the orchestration service.

        Args:
            mode: MOCK for testing, AWS for production
            table_name: Override DynamoDB table name
            queue_url: Override SQS queue URL
            project_name: Project name for resource naming
            environment: Environment (dev/qa/prod)
            region: AWS region (required for AWS mode)
        """
        self.mode = mode
        self.project_name = project_name
        self.environment = environment

        # Validate region for AWS mode
        if mode == PersistenceMode.AWS and not region:
            raise ValueError(
                "AWS_REGION is required for AWS mode. "
                "Set AWS_REGION environment variable or pass region parameter."
            )
        self.region = region

        # Derive resource names
        self.table_name = table_name or self.TABLE_NAME_TEMPLATE.format(
            project=project_name, env=environment
        )
        self._queue_url = queue_url

        # Mock storage
        self._mock_jobs: dict[str, OrchestrationJob] = {}
        self._mock_queue: list[dict[str, Any]] = []

        # AWS clients (lazy initialization)
        self._dynamodb: "DynamoDBServiceResource | None" = None
        self._sqs: "SQSClient | None" = None

        logger.info(
            f"OrchestrationService initialized in {mode.value} mode, "
            f"table={self.table_name}"
        )

    @property
    def dynamodb(self):
        """Lazy initialization of DynamoDB client."""
        if self._dynamodb is None and self.mode == PersistenceMode.AWS:
            self._dynamodb = boto3.resource("dynamodb", region_name=self.region)
        return self._dynamodb

    @property
    def sqs(self):
        """Lazy initialization of SQS client."""
        if self._sqs is None and self.mode == PersistenceMode.AWS:
            self._sqs = boto3.client("sqs", region_name=self.region)
        return self._sqs

    @property
    def queue_url(self) -> str:
        """Get or discover SQS queue URL."""
        if self._queue_url:
            return self._queue_url

        if self.mode == PersistenceMode.AWS:
            queue_name = self.QUEUE_NAME_TEMPLATE.format(
                project=self.project_name, env=self.environment
            )
            try:
                response = self.sqs.get_queue_url(QueueName=queue_name)
                self._queue_url = response["QueueUrl"]
            except ClientError as e:
                logger.error(f"Failed to get queue URL: {e}")
                raise

        return self._queue_url or ""

    async def submit_job(self, submission: JobSubmission) -> OrchestrationJob:
        """
        Submit a new orchestration job.

        Args:
            submission: Job submission details

        Returns:
            Created OrchestrationJob with job_id
        """
        now = datetime.now(timezone.utc).isoformat()
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        task_id = f"task-{uuid.uuid4().hex[:8]}"

        # Calculate TTL (7 days from now)
        ttl = int(
            (
                datetime.now(timezone.utc) + timedelta(days=self.DEFAULT_TTL_DAYS)
            ).timestamp()
        )

        job = OrchestrationJob(
            job_id=job_id,
            task_id=task_id,
            user_id=submission.user_id,
            prompt=submission.prompt,
            status=JobStatus.QUEUED,
            priority=submission.priority,
            created_at=now,
            updated_at=now,
            metadata={
                **submission.metadata,
                "callback_url": submission.callback_url,
            },
            ttl=ttl,
        )

        if self.mode == PersistenceMode.MOCK:
            self._mock_jobs[job_id] = job
            self._mock_queue.append(
                {
                    "job_id": job_id,
                    "task_id": task_id,
                    "prompt": submission.prompt,
                    "priority": submission.priority.value,
                }
            )
            logger.info(f"[MOCK] Job {job_id} submitted to queue")
        else:
            # Store in DynamoDB
            await self._put_job(job)

            # Send to SQS
            await self._send_to_queue(job, submission)

            logger.info(f"Job {job_id} submitted to DynamoDB and SQS")

        return job

    async def get_job(self, job_id: str) -> OrchestrationJob | None:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            OrchestrationJob or None if not found
        """
        if self.mode == PersistenceMode.MOCK:
            return self._mock_jobs.get(job_id)

        try:
            table = self.dynamodb.Table(self.table_name)
            response = table.get_item(Key={"job_id": job_id})
            if "Item" in response:
                return OrchestrationJob.from_dict(response["Item"])
            return None
        except ClientError as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise

    async def list_jobs(
        self,
        user_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[OrchestrationJob]:
        """
        List jobs with optional filters.

        Args:
            user_id: Filter by user
            status: Filter by status
            limit: Maximum number of jobs to return

        Returns:
            List of OrchestrationJob
        """
        if self.mode == PersistenceMode.MOCK:
            jobs = list(self._mock_jobs.values())
            if user_id:
                jobs = [j for j in jobs if j.user_id == user_id]
            if status:
                jobs = [j for j in jobs if j.status == status]
            return sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

        try:
            table = self.dynamodb.Table(self.table_name)

            if status:
                # Use GSI for status-based queries
                response = table.query(
                    IndexName="by-status",
                    KeyConditionExpression="status = :status",
                    ExpressionAttributeValues={":status": status.value},
                    Limit=limit,
                    ScanIndexForward=False,  # Newest first
                )
            else:
                # Scan (less efficient, but flexible)
                scan_kwargs: dict[str, Any] = {"Limit": limit}
                if user_id:
                    scan_kwargs["FilterExpression"] = "user_id = :uid"
                    scan_kwargs["ExpressionAttributeValues"] = {":uid": user_id}
                response = table.scan(**scan_kwargs)

            jobs = [
                OrchestrationJob.from_dict(item) for item in response.get("Items", [])
            ]

            # Filter by user_id if using status GSI
            if user_id and status:
                jobs = [j for j in jobs if j.user_id == user_id]

            return jobs
        except ClientError as e:
            logger.error(f"Failed to list jobs: {e}")
            raise

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> OrchestrationJob | None:
        """
        Update job status.

        Args:
            job_id: Job identifier
            status: New status
            result: Optional result data
            error_message: Optional error message

        Returns:
            Updated OrchestrationJob or None
        """
        now = datetime.now(timezone.utc).isoformat()

        if self.mode == PersistenceMode.MOCK:
            job = self._mock_jobs.get(job_id)
            if job:
                job.status = status
                job.updated_at = now
                if result:
                    job.result = result
                if error_message:
                    job.error_message = error_message
                if status == JobStatus.RUNNING and not job.started_at:
                    job.started_at = now
                if status in (
                    JobStatus.SUCCEEDED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ):
                    job.completed_at = now
            return job

        try:
            table = self.dynamodb.Table(self.table_name)

            update_expr = "SET #status = :status, updated_at = :updated"
            expr_names: dict[str, str] = {"#status": "status"}
            expr_values: dict[str, Any] = {":status": status.value, ":updated": now}

            if result:
                update_expr += ", #result = :result"
                expr_names["#result"] = "result"
                expr_values[":result"] = result

            if error_message:
                update_expr += ", error_message = :error"
                expr_values[":error"] = error_message

            if status == JobStatus.RUNNING:
                update_expr += ", started_at = if_not_exists(started_at, :started)"
                expr_values[":started"] = now

            if status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
                update_expr += ", completed_at = :completed"
                expr_values[":completed"] = now

            response = table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ReturnValues="ALL_NEW",
            )

            return OrchestrationJob.from_dict(response["Attributes"])
        except ClientError as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            raise

    async def cancel_job(self, job_id: str, user_id: str) -> OrchestrationJob | None:
        """
        Cancel a job.

        Args:
            job_id: Job identifier
            user_id: User requesting cancellation (must own job)

        Returns:
            Updated OrchestrationJob or None
        """
        job = await self.get_job(job_id)
        if not job:
            return None

        if job.user_id != user_id:
            raise PermissionError(f"User {user_id} cannot cancel job {job_id}")

        if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
            return job  # Already terminal state

        return await self.update_job_status(job_id, JobStatus.CANCELLED)

    async def _put_job(self, job: OrchestrationJob) -> None:
        """Store job in DynamoDB."""
        table = self.dynamodb.Table(self.table_name)
        table.put_item(Item=job.to_dict())

    async def _send_to_queue(
        self, job: OrchestrationJob, submission: JobSubmission
    ) -> None:
        """Send job to SQS queue for dispatcher."""
        message = {
            "job_id": job.job_id,
            "task_id": job.task_id,
            "user_id": job.user_id,
            "prompt": submission.prompt,
            "priority": submission.priority.value,
            "metadata": submission.metadata,
            "callback_url": submission.callback_url,
            "submitted_at": job.created_at,
        }

        # Map priority to SQS message attributes
        priority_delay = {
            JobPriority.CRITICAL: 0,
            JobPriority.HIGH: 0,
            JobPriority.NORMAL: 0,
            JobPriority.LOW: 5,  # 5 second delay for low priority
        }

        self.sqs.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(message),
            DelaySeconds=priority_delay.get(submission.priority, 0),
            MessageAttributes={
                "Priority": {
                    "DataType": "String",
                    "StringValue": submission.priority.value,
                },
                "JobId": {
                    "DataType": "String",
                    "StringValue": job.job_id,
                },
            },
        )

    async def get_queue_depth(self) -> int:
        """Get approximate number of messages in queue."""
        if self.mode == PersistenceMode.MOCK:
            return len(self._mock_queue)

        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            return int(response["Attributes"].get("ApproximateNumberOfMessages", 0))
        except ClientError as e:
            logger.error(f"Failed to get queue depth: {e}")
            return -1

    async def health_check(self) -> dict[str, Any]:
        """Health check for the orchestration service."""
        if self.mode == PersistenceMode.MOCK:
            return {
                "status": "healthy",
                "mode": "mock",
                "jobs_count": len(self._mock_jobs),
                "queue_depth": len(self._mock_queue),
            }

        try:
            # Check DynamoDB
            table = self.dynamodb.Table(self.table_name)
            table.table_status  # Will raise if table doesn't exist

            # Check SQS
            queue_depth = await self.get_queue_depth()

            return {
                "status": "healthy",
                "mode": "aws",
                "table_name": self.table_name,
                "queue_url": self.queue_url,
                "queue_depth": queue_depth,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "mode": "aws",
                "error": str(e),
            }


def create_orchestration_service(
    environment: str = "dev",
    use_mock: bool = False,
) -> OrchestrationService:
    """
    Factory function to create OrchestrationService.

    Args:
        environment: Environment name
        use_mock: Force mock mode for testing

    Returns:
        Configured OrchestrationService

    Raises:
        ValueError: If AWS_REGION is not set when using AWS mode
    """
    import os

    if use_mock or os.getenv("USE_MOCK_ORCHESTRATION", "false").lower() == "true":
        mode = PersistenceMode.MOCK
    else:
        mode = PersistenceMode.AWS

    region = os.getenv("AWS_REGION")
    if mode == PersistenceMode.AWS and not region:
        raise ValueError(
            "AWS_REGION environment variable is required for AWS mode. "
            "Set AWS_REGION or use USE_MOCK_ORCHESTRATION=true for testing."
        )

    return OrchestrationService(
        mode=mode,
        project_name=os.getenv("PROJECT_NAME", "aura"),
        environment=os.getenv("ENVIRONMENT", environment),
        region=region,
    )
