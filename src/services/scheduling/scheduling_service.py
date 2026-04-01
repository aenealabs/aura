"""
Scheduling Service

Manages job scheduling, queue status, and timeline queries.
ADR-055: Agent Scheduling View and Job Queue Management
"""

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.services.scheduling.models import (
    Priority,
    QueueStatus,
    ScheduledJob,
    ScheduleJobRequest,
    ScheduleStatus,
    TimelineEntry,
)

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

logger = logging.getLogger(__name__)

# Singleton instance
_scheduling_service: Optional["SchedulingService"] = None


class SchedulingServiceError(Exception):
    """Base exception for scheduling service errors."""


class ScheduleNotFoundError(SchedulingServiceError):
    """Raised when a scheduled job is not found."""


class ScheduleValidationError(SchedulingServiceError):
    """Raised when schedule request validation fails."""


class SchedulingService:
    """
    Service for managing scheduled jobs and queue status.

    Provides:
    - CRUD operations for scheduled jobs
    - Queue status and metrics
    - Timeline queries for visualization
    - Dispatcher for due jobs
    """

    def __init__(
        self,
        table_name: Optional[str] = None,
        jobs_table_name: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """
        Initialize the scheduling service.

        Args:
            table_name: DynamoDB table for scheduled jobs
            jobs_table_name: DynamoDB table for orchestrator jobs (for queue status)
            region: AWS region
        """
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        env = os.environ.get("ENVIRONMENT", "dev")

        self.table_name = table_name or f"aura-scheduled-jobs-{env}"
        self.jobs_table_name = jobs_table_name or f"aura-orchestrator-jobs-{env}"

        self._table: Optional["Table"] = None
        self._jobs_table: Optional["Table"] = None
        self._dynamodb = None

    @property
    def table(self) -> "Table":
        """Get DynamoDB table for scheduled jobs."""
        if self._table is None:
            import boto3

            if self._dynamodb is None:
                self._dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._table = self._dynamodb.Table(self.table_name)
        return self._table

    @property
    def jobs_table(self) -> "Table":
        """Get DynamoDB table for orchestrator jobs."""
        if self._jobs_table is None:
            import boto3

            if self._dynamodb is None:
                self._dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._jobs_table = self._dynamodb.Table(self.jobs_table_name)
        return self._jobs_table

    async def schedule_job(
        self,
        organization_id: str,
        request: ScheduleJobRequest,
        user_id: str,
    ) -> ScheduledJob:
        """
        Schedule a new job for future execution.

        Args:
            organization_id: Organization ID
            request: Schedule job request
            user_id: User creating the schedule

        Returns:
            Created scheduled job

        Raises:
            ScheduleValidationError: If request validation fails
        """
        # Validate request
        errors = request.validate()
        if errors:
            raise ScheduleValidationError(", ".join(errors))

        # Create scheduled job
        scheduled_job = ScheduledJob.create(
            organization_id=organization_id,
            request=request,
            created_by=user_id,
        )

        # Store in DynamoDB
        try:
            self.table.put_item(Item=scheduled_job.to_dynamodb_item())
            logger.info(
                "Scheduled job created",
                extra={
                    "schedule_id": scheduled_job.schedule_id,
                    "job_type": scheduled_job.job_type.value,
                    "scheduled_at": scheduled_job.scheduled_at.isoformat(),
                    "created_by": user_id,
                },
            )
        except Exception as e:
            logger.error(f"Failed to create scheduled job: {e}")
            raise SchedulingServiceError(f"Failed to create scheduled job: {e}")

        return scheduled_job

    async def get_scheduled_job(
        self,
        organization_id: str,
        schedule_id: str,
    ) -> ScheduledJob:
        """
        Get a scheduled job by ID.

        Args:
            organization_id: Organization ID
            schedule_id: Schedule ID

        Returns:
            Scheduled job

        Raises:
            ScheduleNotFoundError: If job not found
        """
        try:
            response = self.table.get_item(
                Key={
                    "organization_id": organization_id,
                    "schedule_id": schedule_id,
                }
            )
        except Exception as e:
            logger.error(f"Failed to get scheduled job: {e}")
            raise SchedulingServiceError(f"Failed to get scheduled job: {e}")

        item = response.get("Item")
        if not item:
            raise ScheduleNotFoundError(f"Scheduled job {schedule_id} not found")

        return ScheduledJob.from_dynamodb_item(item)

    async def list_scheduled_jobs(
        self,
        organization_id: str,
        status: Optional[ScheduleStatus] = None,
        limit: int = 50,
        start_key: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[ScheduledJob], Optional[Dict[str, Any]]]:
        """
        List scheduled jobs for an organization.

        Args:
            organization_id: Organization ID
            status: Filter by status
            limit: Maximum number of results
            start_key: Pagination key

        Returns:
            Tuple of (jobs list, next pagination key)
        """
        try:
            from boto3.dynamodb.conditions import Attr, Key

            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": Key("organization_id").eq(organization_id),
                "Limit": limit,
                "ScanIndexForward": True,  # Sort by schedule_id ascending
            }

            if status:
                query_kwargs["FilterExpression"] = Attr("status").eq(status.value)

            if start_key:
                query_kwargs["ExclusiveStartKey"] = start_key

            response = self.table.query(**query_kwargs)

            jobs = [
                ScheduledJob.from_dynamodb_item(item)
                for item in response.get("Items", [])
            ]
            next_key = response.get("LastEvaluatedKey")

            return jobs, next_key

        except Exception as e:
            logger.error(f"Failed to list scheduled jobs: {e}")
            raise SchedulingServiceError(f"Failed to list scheduled jobs: {e}")

    async def list_pending_jobs(
        self,
        organization_id: Optional[str] = None,
        before: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[ScheduledJob]:
        """
        List pending scheduled jobs, optionally filtered by time.

        Args:
            organization_id: Optional organization filter
            before: Only jobs scheduled before this time
            limit: Maximum number of results

        Returns:
            List of pending scheduled jobs
        """
        try:
            from boto3.dynamodb.conditions import Attr, Key

            # Use status-scheduled_at GSI
            query_kwargs: Dict[str, Any] = {
                "IndexName": "status-scheduled_at-index",
                "KeyConditionExpression": Key("status").eq(
                    ScheduleStatus.PENDING.value
                ),
                "Limit": limit,
            }

            if before:
                query_kwargs["KeyConditionExpression"] &= Key("scheduled_at").lte(
                    before.isoformat()
                )

            if organization_id:
                query_kwargs["FilterExpression"] = Attr("organization_id").eq(
                    organization_id
                )

            response = self.table.query(**query_kwargs)

            return [
                ScheduledJob.from_dynamodb_item(item)
                for item in response.get("Items", [])
            ]

        except Exception as e:
            logger.error(f"Failed to list pending jobs: {e}")
            raise SchedulingServiceError(f"Failed to list pending jobs: {e}")

    async def reschedule_job(
        self,
        organization_id: str,
        schedule_id: str,
        new_scheduled_at: datetime,
        user_id: str,
    ) -> ScheduledJob:
        """
        Reschedule a pending job.

        Args:
            organization_id: Organization ID
            schedule_id: Schedule ID
            new_scheduled_at: New scheduled time
            user_id: User making the change

        Returns:
            Updated scheduled job

        Raises:
            ScheduleNotFoundError: If job not found
            ScheduleValidationError: If job cannot be rescheduled
        """
        # Get existing job
        job = await self.get_scheduled_job(organization_id, schedule_id)

        # Validate status
        if job.status != ScheduleStatus.PENDING:
            raise ScheduleValidationError(
                f"Cannot reschedule job with status {job.status.value}"
            )

        # Validate new time
        now = datetime.now(timezone.utc)
        if new_scheduled_at.tzinfo is None:
            new_scheduled_at = new_scheduled_at.replace(tzinfo=timezone.utc)

        if new_scheduled_at <= now:
            raise ScheduleValidationError("New scheduled time must be in the future")

        # Update job
        try:
            self.table.update_item(
                Key={
                    "organization_id": organization_id,
                    "schedule_id": schedule_id,
                },
                UpdateExpression="SET scheduled_at = :scheduled_at",
                ExpressionAttributeValues={
                    ":scheduled_at": new_scheduled_at.isoformat(),
                },
            )

            job.scheduled_at = new_scheduled_at
            logger.info(
                "Scheduled job rescheduled",
                extra={
                    "schedule_id": schedule_id,
                    "new_scheduled_at": new_scheduled_at.isoformat(),
                    "user_id": user_id,
                },
            )
            return job

        except Exception as e:
            logger.error(f"Failed to reschedule job: {e}")
            raise SchedulingServiceError(f"Failed to reschedule job: {e}")

    async def cancel_scheduled_job(
        self,
        organization_id: str,
        schedule_id: str,
        user_id: str,
    ) -> ScheduledJob:
        """
        Cancel a pending scheduled job.

        Args:
            organization_id: Organization ID
            schedule_id: Schedule ID
            user_id: User cancelling the job

        Returns:
            Updated scheduled job

        Raises:
            ScheduleNotFoundError: If job not found
            ScheduleValidationError: If job cannot be cancelled
        """
        # Get existing job
        job = await self.get_scheduled_job(organization_id, schedule_id)

        # Validate status
        if job.status != ScheduleStatus.PENDING:
            raise ScheduleValidationError(
                f"Cannot cancel job with status {job.status.value}"
            )

        # Update job
        now = datetime.now(timezone.utc)
        try:
            self.table.update_item(
                Key={
                    "organization_id": organization_id,
                    "schedule_id": schedule_id,
                },
                UpdateExpression="SET #status = :status, cancelled_at = :cancelled_at, cancelled_by = :cancelled_by",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": ScheduleStatus.CANCELLED.value,
                    ":cancelled_at": now.isoformat(),
                    ":cancelled_by": user_id,
                },
            )

            job.status = ScheduleStatus.CANCELLED
            job.cancelled_at = now
            job.cancelled_by = user_id

            logger.info(
                "Scheduled job cancelled",
                extra={
                    "schedule_id": schedule_id,
                    "cancelled_by": user_id,
                },
            )
            return job

        except Exception as e:
            logger.error(f"Failed to cancel scheduled job: {e}")
            raise SchedulingServiceError(f"Failed to cancel scheduled job: {e}")

    async def dispatch_due_jobs(self) -> List[str]:
        """
        Dispatch all jobs that are due for execution.

        This method is called by the scheduler Lambda.

        Returns:
            List of dispatched schedule IDs
        """
        now = datetime.now(timezone.utc)
        dispatched_ids = []

        try:
            # Get all pending jobs due now
            due_jobs = await self.list_pending_jobs(before=now, limit=100)

            for job in due_jobs:
                try:
                    # Mark as dispatched
                    job_id = await self._dispatch_job(job)
                    dispatched_ids.append(job.schedule_id)

                    # Update status
                    self.table.update_item(
                        Key={
                            "organization_id": job.organization_id,
                            "schedule_id": job.schedule_id,
                        },
                        UpdateExpression="SET #status = :status, dispatched_at = :dispatched_at, dispatched_job_id = :job_id",
                        ExpressionAttributeNames={"#status": "status"},
                        ExpressionAttributeValues={
                            ":status": ScheduleStatus.DISPATCHED.value,
                            ":dispatched_at": now.isoformat(),
                            ":job_id": job_id,
                        },
                    )

                    logger.info(
                        "Dispatched scheduled job",
                        extra={
                            "schedule_id": job.schedule_id,
                            "job_id": job_id,
                        },
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to dispatch job {job.schedule_id}: {e}",
                        extra={"schedule_id": job.schedule_id},
                    )
                    # Mark as failed
                    self.table.update_item(
                        Key={
                            "organization_id": job.organization_id,
                            "schedule_id": job.schedule_id,
                        },
                        UpdateExpression="SET #status = :status, error_message = :error",
                        ExpressionAttributeNames={"#status": "status"},
                        ExpressionAttributeValues={
                            ":status": ScheduleStatus.FAILED.value,
                            ":error": str(e),
                        },
                    )

        except Exception as e:
            logger.error(f"Failed to dispatch due jobs: {e}")

        return dispatched_ids

    async def _dispatch_job(self, job: ScheduledJob) -> str:
        """
        Dispatch a single job to the orchestration service.

        Args:
            job: Scheduled job to dispatch

        Returns:
            Created job ID
        """
        # Import here to avoid circular imports
        from src.services.orchestration_service import get_orchestration_service

        orchestration = get_orchestration_service()

        # Submit job
        result = await orchestration.submit_job(
            job_type=job.job_type.value,
            priority=job.priority.value,
            parameters=job.parameters,
            user_id=job.created_by,
            repository_id=job.repository_id,
        )

        return result.get("job_id", "unknown")

    async def get_queue_status(
        self,
        organization_id: Optional[str] = None,
    ) -> QueueStatus:
        """
        Get current queue status and metrics.

        Args:
            organization_id: Optional organization filter

        Returns:
            Queue status metrics
        """
        try:
            from boto3.dynamodb.conditions import Attr

            # Count scheduled jobs
            scheduled_count = 0
            pending_jobs = await self.list_pending_jobs(
                organization_id=organization_id, limit=1000
            )
            scheduled_count = len(pending_jobs)

            # Get next scheduled time
            next_scheduled = None
            if pending_jobs:
                sorted_jobs = sorted(pending_jobs, key=lambda j: j.scheduled_at)
                next_scheduled = sorted_jobs[0].scheduled_at

            # Query orchestrator jobs table for queue metrics
            queued_count = 0
            active_count = 0
            by_priority: Dict[str, int] = {p.value: 0 for p in Priority}
            by_type: Dict[str, int] = {}
            oldest_queued: Optional[datetime] = None

            try:
                # Scan for QUEUED jobs
                scan_kwargs: Dict[str, Any] = {
                    "FilterExpression": Attr("status").is_in(
                        ["QUEUED", "DISPATCHED", "RUNNING"]
                    ),
                }
                if organization_id:
                    scan_kwargs["FilterExpression"] &= Attr("organization_id").eq(
                        organization_id
                    )

                response = self.jobs_table.scan(**scan_kwargs)

                for item in response.get("Items", []):
                    status = item.get("status")
                    if status in ["QUEUED", "DISPATCHED"]:
                        queued_count += 1
                        priority = item.get("priority", "NORMAL")
                        if priority in by_priority:
                            by_priority[priority] += 1

                        job_type = item.get("job_type", "UNKNOWN")
                        by_type[job_type] = by_type.get(job_type, 0) + 1

                        created_at = item.get("created_at")
                        if created_at:
                            dt = datetime.fromisoformat(
                                created_at.replace("Z", "+00:00")
                            )
                            if oldest_queued is None or dt < oldest_queued:
                                oldest_queued = dt

                    elif status == "RUNNING":
                        active_count += 1

            except Exception as e:
                logger.warning(f"Failed to query jobs table for queue status: {e}")

            # Calculate average wait time (simplified)
            avg_wait = 0.0
            if oldest_queued:
                now = datetime.now(timezone.utc)
                avg_wait = (now - oldest_queued).total_seconds() / max(queued_count, 1)

            return QueueStatus(
                total_queued=queued_count,
                total_scheduled=scheduled_count,
                active_jobs=active_count,
                by_priority=by_priority,
                by_type=by_type,
                avg_wait_time_seconds=avg_wait,
                throughput_per_hour=0.0,  # Would need historical data
                oldest_queued_at=oldest_queued,
                next_scheduled_at=next_scheduled,
            )

        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            raise SchedulingServiceError(f"Failed to get queue status: {e}")

    async def get_timeline(
        self,
        organization_id: str,
        start_date: datetime,
        end_date: datetime,
        include_scheduled: bool = True,
        include_completed: bool = True,
        limit: int = 200,
    ) -> List[TimelineEntry]:
        """
        Get timeline entries for visualization.

        Args:
            organization_id: Organization ID
            start_date: Start of time range
            end_date: End of time range
            include_scheduled: Include scheduled (future) jobs
            include_completed: Include completed jobs
            limit: Maximum entries

        Returns:
            List of timeline entries
        """
        entries: List[TimelineEntry] = []

        try:
            # Get scheduled jobs in range
            if include_scheduled:
                scheduled_jobs, _ = await self.list_scheduled_jobs(
                    organization_id=organization_id,
                    limit=limit,
                )
                for job in scheduled_jobs:
                    if start_date <= job.scheduled_at <= end_date:
                        entries.append(
                            TimelineEntry(
                                job_id=job.schedule_id,
                                job_type=job.job_type.value,
                                status=job.status.value,
                                title=job.description or f"{job.job_type.value} Job",
                                scheduled_at=job.scheduled_at,
                                repository_name=job.repository_id,
                                created_by=job.created_by,
                            )
                        )

            # Get completed jobs from orchestrator table
            if include_completed:
                try:
                    from boto3.dynamodb.conditions import Attr

                    scan_kwargs: Dict[str, Any] = {
                        "FilterExpression": (
                            Attr("organization_id").eq(organization_id)
                            & Attr("status").is_in(["SUCCEEDED", "FAILED", "RUNNING"])
                        ),
                        "Limit": limit,
                    }

                    response = self.jobs_table.scan(**scan_kwargs)

                    for item in response.get("Items", []):
                        started_at = None
                        completed_at = None
                        duration = None

                        if item.get("started_at"):
                            started_at = datetime.fromisoformat(
                                item["started_at"].replace("Z", "+00:00")
                            )
                        if item.get("completed_at"):
                            completed_at = datetime.fromisoformat(
                                item["completed_at"].replace("Z", "+00:00")
                            )

                        if started_at and completed_at:
                            duration = int((completed_at - started_at).total_seconds())

                        # Check if in date range
                        job_time = completed_at or started_at
                        if job_time and start_date <= job_time <= end_date:
                            entries.append(
                                TimelineEntry(
                                    job_id=item.get("job_id", ""),
                                    job_type=item.get("job_type", "UNKNOWN"),
                                    status=item.get("status", "UNKNOWN"),
                                    title=item.get(
                                        "description",
                                        f"{item.get('job_type', 'Unknown')} Job",
                                    ),
                                    started_at=started_at,
                                    completed_at=completed_at,
                                    duration_seconds=duration,
                                    repository_name=item.get("repository_id"),
                                    created_by=item.get("user_id"),
                                )
                            )

                except Exception as e:
                    logger.warning(f"Failed to query completed jobs for timeline: {e}")

            # Sort by time
            entries.sort(
                key=lambda e: e.scheduled_at
                or e.started_at
                or datetime.min.replace(tzinfo=timezone.utc)
            )

            return entries[:limit]

        except Exception as e:
            logger.error(f"Failed to get timeline: {e}")
            raise SchedulingServiceError(f"Failed to get timeline: {e}")


def get_scheduling_service() -> SchedulingService:
    """Get singleton instance of SchedulingService."""
    global _scheduling_service
    if _scheduling_service is None:
        _scheduling_service = SchedulingService()
    return _scheduling_service


def set_scheduling_service(service: Optional[SchedulingService]) -> None:
    """Set singleton instance of SchedulingService (for testing)."""
    global _scheduling_service
    _scheduling_service = service


def clear_scheduling_service() -> None:
    """Clear singleton instance (for testing)."""
    global _scheduling_service
    _scheduling_service = None
