"""GPU Scheduler Service.

Manages GPU workload scheduling, queue management, and job lifecycle.
Implements ADR-061: GPU Workload Scheduler.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.services.gpu_scheduler.exceptions import (
    GPUJobNotFoundError,
    GPUSchedulerError,
    InvalidJobConfigError,
    JobCancellationError,
    QuotaExceededError,
)
from src.services.gpu_scheduler.models import (
    GPUJob,
    GPUJobCreateRequest,
    GPUJobPriority,
    GPUJobStatus,
    GPUJobType,
    GPUQuota,
    GPUResourceStatus,
    PositionEstimate,
    QueueMetrics,
)

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table
    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_sqs.client import SQSClient

logger = logging.getLogger(__name__)

# Singleton instance
_gpu_scheduler_service: GPUSchedulerService | None = None

# Default TTL: 90 days in seconds
DEFAULT_TTL_SECONDS = 90 * 24 * 60 * 60

# GPU hourly rate for cost estimation (g4dn.xlarge Spot)
GPU_HOURLY_RATE_USD = 0.16


class GPUSchedulerService:
    """Service for managing GPU workload scheduling.

    Provides:
    - Job submission and lifecycle management
    - Queue management with priority scheduling
    - Quota enforcement per organization
    - Checkpoint management for job recovery
    - Integration with Kubernetes for job execution
    """

    def __init__(
        self,
        jobs_table_name: str | None = None,
        quotas_table_name: str | None = None,
        queue_url: str | None = None,
        checkpoints_bucket: str | None = None,
        region: str | None = None,
    ):
        """Initialize the GPU scheduler service.

        Args:
            jobs_table_name: DynamoDB table for GPU jobs.
            quotas_table_name: DynamoDB table for organization quotas.
            queue_url: SQS FIFO queue URL for job queue.
            checkpoints_bucket: S3 bucket for job checkpoints.
            region: AWS region.
        """
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        env = os.environ.get("ENVIRONMENT", "dev")
        account_id = os.environ.get("AWS_ACCOUNT_ID", "")

        self.jobs_table_name = jobs_table_name or f"aura-gpu-jobs-{env}"
        self.quotas_table_name = quotas_table_name or f"aura-gpu-quotas-{env}"
        self.queue_url = queue_url or os.environ.get(
            "GPU_JOBS_QUEUE_URL",
            f"https://sqs.{self.region}.amazonaws.com/{account_id}/aura-gpu-jobs-queue-{env}.fifo",
        )
        self.checkpoints_bucket = checkpoints_bucket or os.environ.get(
            "GPU_CHECKPOINTS_BUCKET",
            f"aura-gpu-checkpoints-{account_id}-{env}",
        )

        # Lazy-loaded AWS resources
        self._jobs_table: Table | None = None
        self._quotas_table: Table | None = None
        self._dynamodb = None
        self._sqs_client: SQSClient | None = None
        self._s3_client: S3Client | None = None

    @property
    def jobs_table(self) -> Table:
        """Get DynamoDB table for GPU jobs (lazy-loaded)."""
        if self._jobs_table is None:
            import boto3

            if self._dynamodb is None:
                self._dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._jobs_table = self._dynamodb.Table(self.jobs_table_name)
        return self._jobs_table

    @property
    def quotas_table(self) -> Table:
        """Get DynamoDB table for GPU quotas (lazy-loaded)."""
        if self._quotas_table is None:
            import boto3

            if self._dynamodb is None:
                self._dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._quotas_table = self._dynamodb.Table(self.quotas_table_name)
        return self._quotas_table

    @property
    def sqs_client(self) -> SQSClient:
        """Get SQS client (lazy-loaded)."""
        if self._sqs_client is None:
            import boto3

            self._sqs_client = boto3.client("sqs", region_name=self.region)
        return self._sqs_client

    @property
    def s3_client(self) -> S3Client:
        """Get S3 client (lazy-loaded)."""
        if self._s3_client is None:
            import boto3

            self._s3_client = boto3.client("s3", region_name=self.region)
        return self._s3_client

    # =========================================================================
    # Job Submission and Lifecycle
    # =========================================================================

    async def submit_job(
        self,
        organization_id: str,
        user_id: str,
        request: GPUJobCreateRequest,
    ) -> GPUJob:
        """Submit a new GPU job for execution.

        Args:
            organization_id: Organization submitting the job.
            user_id: User submitting the job.
            request: Job creation request with configuration.

        Returns:
            Created GPU job.

        Raises:
            QuotaExceededError: If organization quota is exceeded.
            InvalidJobConfigError: If job configuration is invalid.
            GPUSchedulerError: If job submission fails.
        """
        # Check quota
        quota = await self.get_quota(organization_id)
        await self._validate_quota(quota, request)

        # Generate job ID and checkpoint path
        job_id = str(uuid.uuid4())
        checkpoint_s3_path = None
        if request.checkpoint_enabled:
            checkpoint_s3_path = (
                f"s3://{self.checkpoints_bucket}/{organization_id}/{job_id}/"
            )

        # Calculate TTL (90 days from now)
        ttl = int(time.time()) + DEFAULT_TTL_SECONDS

        # Create job object
        job = GPUJob(
            job_id=job_id,
            organization_id=organization_id,
            user_id=user_id,
            job_type=request.job_type,
            status=GPUJobStatus.QUEUED,
            priority=request.priority,
            config=request.config,
            gpu_memory_gb=request.gpu_memory_gb,
            max_runtime_hours=request.max_runtime_hours,
            checkpoint_enabled=request.checkpoint_enabled,
            checkpoint_s3_path=checkpoint_s3_path,
            created_at=datetime.now(timezone.utc),
            ttl=ttl,
        )

        try:
            # Save to DynamoDB
            self.jobs_table.put_item(Item=job.to_dynamodb_item())

            # Enqueue to SQS FIFO
            await self._enqueue_job(job)

            # Increment concurrent job count in quota
            await self._increment_concurrent_jobs(organization_id)

            logger.info(
                "GPU job submitted",
                extra={
                    "job_id": job_id,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "job_type": request.job_type.value,
                    "priority": request.priority.value,
                },
            )

            return job

        except Exception as e:
            logger.error(f"Failed to submit GPU job: {e}")
            raise GPUSchedulerError(f"Failed to submit GPU job: {e}")

    async def get_job(self, organization_id: str, job_id: str) -> GPUJob:
        """Get a GPU job by ID.

        Args:
            organization_id: Organization that owns the job.
            job_id: Job ID to retrieve.

        Returns:
            GPU job.

        Raises:
            GPUJobNotFoundError: If job is not found.
        """
        try:
            response = self.jobs_table.get_item(
                Key={
                    "organization_id": organization_id,
                    "job_id": job_id,
                }
            )
        except Exception as e:
            logger.error(f"Failed to get GPU job: {e}")
            raise GPUSchedulerError(f"Failed to get GPU job: {e}")

        item = response.get("Item")
        if not item:
            raise GPUJobNotFoundError(job_id, organization_id)

        return GPUJob.from_dynamodb_item(item)

    async def list_jobs(
        self,
        organization_id: str,
        status: GPUJobStatus | None = None,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[GPUJob]:
        """List GPU jobs for an organization.

        Args:
            organization_id: Organization to list jobs for.
            status: Optional status filter.
            user_id: Optional user filter.
            limit: Maximum number of jobs to return.

        Returns:
            List of GPU jobs.
        """
        try:
            if status:
                # Use GSI for status queries
                org_status = f"{organization_id}#{status.value}"
                response = self.jobs_table.query(
                    IndexName="org-status-index",
                    KeyConditionExpression="org_status = :org_status",
                    ExpressionAttributeValues={":org_status": org_status},
                    ScanIndexForward=False,  # Newest first
                    Limit=limit,
                )
            elif user_id:
                # Use user GSI
                response = self.jobs_table.query(
                    IndexName="user-created-index",
                    KeyConditionExpression="user_id = :user_id",
                    ExpressionAttributeValues={":user_id": user_id},
                    ScanIndexForward=False,
                    Limit=limit,
                )
            else:
                # Query by partition key
                response = self.jobs_table.query(
                    KeyConditionExpression="organization_id = :org_id",
                    ExpressionAttributeValues={":org_id": organization_id},
                    ScanIndexForward=False,
                    Limit=limit,
                )

            items = response.get("Items", [])
            return [GPUJob.from_dynamodb_item(item) for item in items]

        except Exception as e:
            logger.error(f"Failed to list GPU jobs: {e}")
            raise GPUSchedulerError(f"Failed to list GPU jobs: {e}")

    async def cancel_job(
        self,
        organization_id: str,
        job_id: str,
        user_id: str,
    ) -> GPUJob:
        """Cancel a GPU job.

        Args:
            organization_id: Organization that owns the job.
            job_id: Job ID to cancel.
            user_id: User requesting cancellation.

        Returns:
            Cancelled job.

        Raises:
            GPUJobNotFoundError: If job is not found.
            JobCancellationError: If job cannot be cancelled.
        """
        job = await self.get_job(organization_id, job_id)

        # Check if job can be cancelled
        if job.status in (
            GPUJobStatus.COMPLETED,
            GPUJobStatus.FAILED,
            GPUJobStatus.CANCELLED,
        ):
            raise JobCancellationError(
                job_id, f"Job is already in terminal state: {job.status.value}"
            )

        # Update job status
        try:
            self.jobs_table.update_item(
                Key={
                    "organization_id": organization_id,
                    "job_id": job_id,
                },
                UpdateExpression=(
                    "SET #status = :status, "
                    "org_status = :org_status, "
                    "completed_at = :completed_at"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": GPUJobStatus.CANCELLED.value,
                    ":org_status": f"{organization_id}#{GPUJobStatus.CANCELLED.value}",
                    ":completed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Decrement concurrent job count
            await self._decrement_concurrent_jobs(organization_id)

            logger.info(
                "GPU job cancelled",
                extra={
                    "job_id": job_id,
                    "organization_id": organization_id,
                    "cancelled_by": user_id,
                },
            )

            # Return updated job
            return await self.get_job(organization_id, job_id)

        except Exception as e:
            logger.error(f"Failed to cancel GPU job: {e}")
            raise GPUSchedulerError(f"Failed to cancel GPU job: {e}")

    async def update_job_status(
        self,
        organization_id: str,
        job_id: str,
        status: GPUJobStatus,
        progress_percent: int | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
        kubernetes_job_name: str | None = None,
    ) -> GPUJob:
        """Update GPU job status.

        Args:
            organization_id: Organization that owns the job.
            job_id: Job ID to update.
            status: New status.
            progress_percent: Optional progress percentage.
            error_message: Optional error message (for failed jobs).
            error_type: Optional error type (for failed jobs).
            kubernetes_job_name: Optional Kubernetes job name.

        Returns:
            Updated job.
        """
        update_expr_parts = [
            "#status = :status",
            "org_status = :org_status",
        ]
        expr_attr_values: dict[str, Any] = {
            ":status": status.value,
            ":org_status": f"{organization_id}#{status.value}",
        }

        if status == GPUJobStatus.RUNNING:
            update_expr_parts.append("started_at = :started_at")
            expr_attr_values[":started_at"] = datetime.now(timezone.utc).isoformat()

        if status in (
            GPUJobStatus.COMPLETED,
            GPUJobStatus.FAILED,
            GPUJobStatus.CANCELLED,
        ):
            update_expr_parts.append("completed_at = :completed_at")
            expr_attr_values[":completed_at"] = datetime.now(timezone.utc).isoformat()

        if progress_percent is not None:
            update_expr_parts.append("progress_percent = :progress")
            expr_attr_values[":progress"] = progress_percent

        if error_message:
            update_expr_parts.append("error_message = :error_message")
            expr_attr_values[":error_message"] = error_message

        if error_type:
            update_expr_parts.append("error_type = :error_type")
            expr_attr_values[":error_type"] = error_type

        if kubernetes_job_name:
            update_expr_parts.append("kubernetes_job_name = :k8s_job")
            expr_attr_values[":k8s_job"] = kubernetes_job_name

        try:
            self.jobs_table.update_item(
                Key={
                    "organization_id": organization_id,
                    "job_id": job_id,
                },
                UpdateExpression="SET " + ", ".join(update_expr_parts),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=expr_attr_values,
            )

            # Decrement concurrent jobs if entering terminal state
            if status in (
                GPUJobStatus.COMPLETED,
                GPUJobStatus.FAILED,
                GPUJobStatus.CANCELLED,
            ):
                await self._decrement_concurrent_jobs(organization_id)

            return await self.get_job(organization_id, job_id)

        except Exception as e:
            logger.error(f"Failed to update GPU job status: {e}")
            raise GPUSchedulerError(f"Failed to update GPU job status: {e}")

    # =========================================================================
    # Quota Management
    # =========================================================================

    async def get_quota(self, organization_id: str) -> GPUQuota:
        """Get GPU quota for an organization.

        Args:
            organization_id: Organization to get quota for.

        Returns:
            GPU quota (creates default if not exists).
        """
        try:
            response = self.quotas_table.get_item(
                Key={
                    "organization_id": organization_id,
                    "quota_type": "QUOTA",
                }
            )

            item = response.get("Item")
            if item:
                return GPUQuota.from_dynamodb_item(item)

            # Create default quota
            default_quota = GPUQuota(organization_id=organization_id)
            self.quotas_table.put_item(Item=default_quota.to_dynamodb_item())
            return default_quota

        except Exception as e:
            logger.error(f"Failed to get GPU quota: {e}")
            raise GPUSchedulerError(f"Failed to get GPU quota: {e}")

    async def update_quota(
        self,
        organization_id: str,
        max_concurrent_jobs: int | None = None,
        max_gpu_hours_monthly: int | None = None,
        max_job_runtime_hours: int | None = None,
    ) -> GPUQuota:
        """Update GPU quota for an organization.

        Args:
            organization_id: Organization to update quota for.
            max_concurrent_jobs: New max concurrent jobs limit.
            max_gpu_hours_monthly: New max monthly GPU hours limit.
            max_job_runtime_hours: New max job runtime hours limit.

        Returns:
            Updated quota.
        """
        update_parts = []
        expr_values: dict[str, Any] = {}

        if max_concurrent_jobs is not None:
            update_parts.append("max_concurrent_jobs = :mcj")
            expr_values[":mcj"] = max_concurrent_jobs

        if max_gpu_hours_monthly is not None:
            update_parts.append("max_gpu_hours_monthly = :mghm")
            expr_values[":mghm"] = max_gpu_hours_monthly

        if max_job_runtime_hours is not None:
            update_parts.append("max_job_runtime_hours = :mjrh")
            expr_values[":mjrh"] = max_job_runtime_hours

        if not update_parts:
            return await self.get_quota(organization_id)

        try:
            self.quotas_table.update_item(
                Key={
                    "organization_id": organization_id,
                    "quota_type": "QUOTA",
                },
                UpdateExpression="SET " + ", ".join(update_parts),
                ExpressionAttributeValues=expr_values,
            )
            return await self.get_quota(organization_id)

        except Exception as e:
            logger.error(f"Failed to update GPU quota: {e}")
            raise GPUSchedulerError(f"Failed to update GPU quota: {e}")

    async def _validate_quota(
        self,
        quota: GPUQuota,
        request: GPUJobCreateRequest,
    ) -> None:
        """Validate that a job request doesn't exceed quota.

        Raises:
            QuotaExceededError: If quota would be exceeded.
            InvalidJobConfigError: If job config violates quota limits.
        """
        # Check concurrent jobs
        if quota.current_concurrent_jobs >= quota.max_concurrent_jobs:
            raise QuotaExceededError(
                organization_id=quota.organization_id,
                quota_type="concurrent_jobs",
                current_value=quota.current_concurrent_jobs,
                max_value=quota.max_concurrent_jobs,
            )

        # Check job runtime against quota limit
        if request.max_runtime_hours > quota.max_job_runtime_hours:
            raise InvalidJobConfigError(
                f"Job runtime {request.max_runtime_hours}h exceeds quota limit "
                f"of {quota.max_job_runtime_hours}h",
                field="max_runtime_hours",
            )

        # Check monthly GPU hours
        estimated_hours = request.max_runtime_hours
        if (
            quota.current_month_gpu_hours + estimated_hours
            > quota.max_gpu_hours_monthly
        ):
            raise QuotaExceededError(
                organization_id=quota.organization_id,
                quota_type="gpu_hours_monthly",
                current_value=quota.current_month_gpu_hours,
                max_value=quota.max_gpu_hours_monthly,
            )

    async def _increment_concurrent_jobs(self, organization_id: str) -> None:
        """Increment concurrent job count for an organization."""
        try:
            self.quotas_table.update_item(
                Key={
                    "organization_id": organization_id,
                    "quota_type": "QUOTA",
                },
                UpdateExpression="SET current_concurrent_jobs = current_concurrent_jobs + :inc",
                ExpressionAttributeValues={":inc": 1},
            )
        except Exception as e:
            logger.warning(f"Failed to increment concurrent jobs: {e}")

    async def _decrement_concurrent_jobs(self, organization_id: str) -> None:
        """Decrement concurrent job count for an organization."""
        try:
            self.quotas_table.update_item(
                Key={
                    "organization_id": organization_id,
                    "quota_type": "QUOTA",
                },
                UpdateExpression="SET current_concurrent_jobs = current_concurrent_jobs - :dec",
                ConditionExpression="current_concurrent_jobs > :zero",
                ExpressionAttributeValues={":dec": 1, ":zero": 0},
            )
        except Exception as e:
            logger.warning(f"Failed to decrement concurrent jobs: {e}")

    # =========================================================================
    # Queue Management
    # =========================================================================

    async def _enqueue_job(self, job: GPUJob) -> None:
        """Enqueue a job to the SQS FIFO queue."""
        message_body = {
            "job_id": job.job_id,
            "organization_id": job.organization_id,
            "job_type": job.job_type.value,
            "priority": job.priority.value,
            "config": job.config.model_dump(),
            "gpu_memory_gb": job.gpu_memory_gb,
            "checkpoint_s3_path": job.checkpoint_s3_path,
        }

        try:
            self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=job.organization_id,  # Per-org ordering
                MessageDeduplicationId=job.job_id,  # Prevent duplicate submissions
            )
        except Exception as e:
            logger.error(f"Failed to enqueue GPU job: {e}")
            raise GPUSchedulerError(f"Failed to enqueue GPU job: {e}")

    async def get_queue_depth(self) -> int:
        """Get the current queue depth."""
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            return int(
                response.get("Attributes", {}).get("ApproximateNumberOfMessages", 0)
            )
        except Exception as e:
            logger.warning(f"Failed to get queue depth: {e}")
            return 0

    # =========================================================================
    # Resource Status
    # =========================================================================

    async def get_resource_status(self) -> GPUResourceStatus:
        """Get current GPU resource availability.

        Returns:
            GPU resource status (placeholder - requires K8s integration).
        """
        queue_depth = await self.get_queue_depth()

        # Placeholder values - actual implementation requires K8s API
        return GPUResourceStatus(
            gpus_available=4,
            gpus_total=4,
            gpus_in_use=0,
            queue_depth=queue_depth,
            estimated_wait_minutes=queue_depth * 15 if queue_depth > 0 else None,
            node_count=1,
            scaling_status="stable",
        )

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> dict[str, Any]:
        """Check service health.

        Returns:
            Health status dictionary.
        """
        status: dict[str, Any] = {
            "service": "gpu_scheduler",
            "region": self.region,
            "jobs_table": self.jobs_table_name,
            "quotas_table": self.quotas_table_name,
            "queue_url": self.queue_url,
            "healthy": True,
        }

        # Check DynamoDB connectivity
        try:
            self.jobs_table.table_status
            status["dynamodb_status"] = "connected"
        except Exception as e:
            status["dynamodb_status"] = f"error: {str(e)}"
            status["healthy"] = False

        # Check SQS connectivity
        try:
            await self.get_queue_depth()
            status["sqs_status"] = "connected"
        except Exception as e:
            status["sqs_status"] = f"error: {str(e)}"
            status["healthy"] = False

        return status

    # =========================================================================
    # Phase 2: Queue Position and Metrics (ADR-061)
    # =========================================================================

    async def get_queue_position(
        self,
        organization_id: str,
        job_id: str,
    ) -> PositionEstimate:
        """Get queue position estimate for a job.

        Args:
            organization_id: Organization that owns the job.
            job_id: Job ID to get position for.

        Returns:
            Position estimate with wait time.
        """
        from src.services.gpu_scheduler.position_estimator import get_position_estimator
        from src.services.gpu_scheduler.queue_engine import get_queue_engine

        # Verify job exists (raises GPUJobNotFoundError if not found)
        await self.get_job(organization_id, job_id)

        # Get resource status for GPU count
        resource_status = await self.get_resource_status()

        # Get position estimate
        estimator = get_position_estimator()
        if estimator.queue_engine is None:
            estimator.queue_engine = get_queue_engine()

        return estimator.estimate_position(
            job_id=job_id,
            current_gpu_count=resource_status.gpus_available,
            scaling_in_progress=resource_status.scaling_status == "scaling_up",
        )

    async def get_queue_metrics(self) -> QueueMetrics:
        """Get current queue metrics.

        Returns:
            Queue metrics with statistics.
        """
        from src.services.gpu_scheduler.queue_engine import get_queue_engine

        queue_engine = get_queue_engine()
        return queue_engine.get_metrics()

    async def estimate_position_for_new_job(
        self,
        organization_id: str,
        priority: GPUJobPriority,
        job_type: GPUJobType,
    ) -> PositionEstimate:
        """Estimate queue position for a job before submission.

        Used by the UI to show expected wait time before user submits.

        Args:
            organization_id: Organization that would submit the job.
            priority: Priority of the potential job.
            job_type: Type of the potential job.

        Returns:
            Position estimate for the potential job.
        """
        from src.services.gpu_scheduler.position_estimator import get_position_estimator
        from src.services.gpu_scheduler.queue_engine import get_queue_engine

        # Get resource status for GPU count
        resource_status = await self.get_resource_status()

        # Get position estimate
        estimator = get_position_estimator()
        if estimator.queue_engine is None:
            estimator.queue_engine = get_queue_engine()

        return estimator.estimate_for_new_job(
            priority=priority,
            job_type=job_type,
            organization_id=organization_id,
            current_gpu_count=resource_status.gpus_available,
        )


def get_gpu_scheduler_service() -> GPUSchedulerService:
    """Get or create the GPU scheduler service singleton."""
    global _gpu_scheduler_service
    if _gpu_scheduler_service is None:
        _gpu_scheduler_service = GPUSchedulerService()
    return _gpu_scheduler_service


def init_gpu_scheduler_service(
    jobs_table_name: str | None = None,
    quotas_table_name: str | None = None,
    queue_url: str | None = None,
    checkpoints_bucket: str | None = None,
    region: str | None = None,
) -> GPUSchedulerService:
    """Initialize the GPU scheduler service singleton with custom configuration."""
    global _gpu_scheduler_service
    _gpu_scheduler_service = GPUSchedulerService(
        jobs_table_name=jobs_table_name,
        quotas_table_name=quotas_table_name,
        queue_url=queue_url,
        checkpoints_bucket=checkpoints_bucket,
        region=region,
    )
    return _gpu_scheduler_service
