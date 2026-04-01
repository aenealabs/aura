"""
Project Aura - GPU Scheduled Job Service

Manages recurring GPU job schedules with cron expressions for:
- Daily/weekly/monthly recurring embedding updates
- Scheduled model training runs
- Automatic job submission based on schedule

ADR-061: GPU Workload Scheduler - Phase 5 Advanced Features
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import boto3

from .exceptions import GPUSchedulerError, InvalidScheduleError, ScheduleNotFoundError
from .job_template_service import GPUJobTemplateService
from .models import (
    GPUJobCreateRequest,
    GPUScheduledJob,
    ScheduleCreateRequest,
    ScheduledJobStatus,
    ScheduleFrequency,
)

logger = logging.getLogger(__name__)


class ScheduleValidationError(InvalidScheduleError):
    """Raised when schedule configuration is invalid."""


class ScheduleLimitExceededError(GPUSchedulerError):
    """Raised when schedule limits are exceeded."""

    def __init__(self, message: str):
        super().__init__(message)


# Configuration
MAX_SCHEDULES_PER_ORG = 50
MAX_CONSECUTIVE_FAILURES = 3


class GPUScheduledJobService:
    """
    Manages scheduled recurring GPU jobs.

    Features:
    - Cron-based scheduling (hourly, daily, weekly, monthly, custom)
    - Timezone-aware execution
    - Integration with job templates
    - Auto-pause on consecutive failures
    - Next run calculation

    Usage:
        service = GPUScheduledJobService(
            schedules_table_name="aura-gpu-schedules-dev",
            templates_table_name="aura-gpu-templates-dev",
        )

        # Create a daily schedule
        schedule = await service.create_schedule(
            organization_id="org-123",
            user_id="user-456",
            request=ScheduleCreateRequest(
                name="Nightly Embeddings",
                template_id="template-789",
                frequency=ScheduleFrequency.DAILY,
                timezone="UTC",
            ),
        )

        # Process due schedules (called by dispatcher)
        dispatched = await service.dispatch_due_schedules()
    """

    def __init__(
        self,
        schedules_table_name: str | None = None,
        templates_table_name: str | None = None,
        region: str | None = None,
    ):
        """
        Initialize the scheduled job service.

        Args:
            schedules_table_name: DynamoDB table for schedules
            templates_table_name: DynamoDB table for templates
            region: AWS region
        """
        self.schedules_table_name = schedules_table_name or "aura-gpu-schedules"
        self.templates_table_name = templates_table_name or "aura-gpu-templates"
        self.region = region or "us-east-1"

        # Lazy-loaded resources
        self._schedules_table = None
        self._template_service = None

        logger.info(
            f"GPUScheduledJobService initialized "
            f"(schedules={self.schedules_table_name})"
        )

    @property
    def schedules_table(self):
        """Lazy-load schedules DynamoDB table."""
        if self._schedules_table is None:
            dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self._schedules_table = dynamodb.Table(self.schedules_table_name)
        return self._schedules_table

    @property
    def template_service(self) -> GPUJobTemplateService:
        """Lazy-load template service."""
        if self._template_service is None:
            self._template_service = GPUJobTemplateService(
                table_name=self.templates_table_name,
                region=self.region,
            )
        return self._template_service

    # =========================================================================
    # Schedule CRUD Operations
    # =========================================================================

    async def create_schedule(
        self,
        organization_id: str,
        user_id: str,
        request: ScheduleCreateRequest,
    ) -> GPUScheduledJob:
        """
        Create a new scheduled job.

        Args:
            organization_id: Organization ID
            user_id: User creating the schedule
            request: Schedule creation request

        Returns:
            Created schedule

        Raises:
            ScheduleValidationError: If request is invalid
            ScheduleLimitExceededError: If limits exceeded
            TemplateNotFoundError: If template_id is invalid
        """
        # Validate request
        errors = request.validate_config()
        if errors:
            raise ScheduleValidationError(", ".join(errors))

        # Check limits
        await self._check_schedule_limits(organization_id)

        # Validate template if specified
        if request.template_id:
            await self.template_service.get_template(
                organization_id=organization_id,
                template_id=request.template_id,
                user_id=user_id,
            )

        schedule_id = f"sch-{uuid.uuid4()}"
        now = datetime.now(timezone.utc)

        # Calculate first run time
        start_time = request.start_date or now
        next_run = self._calculate_next_run(
            frequency=request.frequency,
            cron_expression=request.cron_expression,
            tz=request.timezone,
            after=start_time,
        )

        schedule = GPUScheduledJob(
            schedule_id=schedule_id,
            organization_id=organization_id,
            user_id=user_id,
            name=request.name,
            description=request.description,
            template_id=request.template_id,
            job_type=request.job_type,
            config=request.config,
            priority=request.priority,
            gpu_memory_gb=request.gpu_memory_gb,
            gpu_count=request.gpu_count,
            max_runtime_hours=request.max_runtime_hours,
            checkpoint_enabled=request.checkpoint_enabled,
            frequency=request.frequency,
            cron_expression=request.cron_expression,
            timezone=request.timezone,
            start_date=request.start_date,
            end_date=request.end_date,
            status=ScheduledJobStatus.ACTIVE,
            next_run_at=next_run,
            created_at=now,
        )

        self.schedules_table.put_item(Item=schedule.to_dynamodb_item())

        logger.info(
            f"Created schedule '{schedule.name}' ({schedule_id}) "
            f"for org {organization_id}, next run: {next_run}"
        )

        return schedule

    async def get_schedule(
        self,
        organization_id: str,
        schedule_id: str,
    ) -> GPUScheduledJob:
        """
        Get a schedule by ID.

        Args:
            organization_id: Organization ID
            schedule_id: Schedule ID

        Returns:
            Schedule object

        Raises:
            ScheduleNotFoundError: If schedule not found
        """
        response = self.schedules_table.get_item(
            Key={
                "organization_id": organization_id,
                "schedule_id": schedule_id,
            }
        )

        item = response.get("Item")
        if not item:
            raise ScheduleNotFoundError(schedule_id, organization_id)

        return GPUScheduledJob.from_dynamodb_item(item)

    async def update_schedule(
        self,
        organization_id: str,
        schedule_id: str,
        user_id: str,
        updates: dict[str, Any],
    ) -> GPUScheduledJob:
        """
        Update an existing schedule.

        Args:
            organization_id: Organization ID
            schedule_id: Schedule ID
            user_id: User making the update
            updates: Fields to update

        Returns:
            Updated schedule
        """
        schedule = await self.get_schedule(organization_id, schedule_id)

        # Build update expression
        update_parts = ["updated_at = :updated_at"]
        expr_values: dict[str, Any] = {
            ":updated_at": datetime.now(timezone.utc).isoformat()
        }
        expr_names: dict[str, str] = {}

        allowed_fields = {
            "name",
            "description",
            "priority",
            "gpu_memory_gb",
            "gpu_count",
            "max_runtime_hours",
            "checkpoint_enabled",
            "frequency",
            "cron_expression",
            "timezone",
            "start_date",
            "end_date",
        }

        # Reserved words in DynamoDB that need expression attribute names
        reserved_words = {"name", "status", "type", "config"}

        for field, value in updates.items():
            if field in allowed_fields:
                if hasattr(value, "value"):
                    value = value.value
                elif hasattr(value, "isoformat"):
                    value = value.isoformat()

                # Handle reserved words
                if field in reserved_words:
                    expr_names[f"#{field}"] = field
                    update_parts.append(f"#{field} = :{field}")
                else:
                    update_parts.append(f"{field} = :{field}")
                expr_values[f":{field}"] = value

        # Recalculate next run if schedule params changed
        recalc_fields = {"frequency", "cron_expression", "timezone", "start_date"}
        if any(f in updates for f in recalc_fields):
            freq = updates.get("frequency", schedule.frequency)
            cron = updates.get("cron_expression", schedule.cron_expression)
            tz = updates.get("timezone", schedule.timezone)

            next_run = self._calculate_next_run(
                frequency=freq,
                cron_expression=cron,
                tz=tz,
            )
            update_parts.append("next_run_at = :next_run_at")
            expr_values[":next_run_at"] = next_run.isoformat()

            # Update composite key for GSI
            status = schedule.status.value
            update_parts.append("status_next_run = :status_next_run")
            expr_values[":status_next_run"] = f"{status}#{next_run.isoformat()}"

        update_kwargs = {
            "Key": {
                "organization_id": organization_id,
                "schedule_id": schedule_id,
            },
            "UpdateExpression": "SET " + ", ".join(update_parts),
            "ExpressionAttributeValues": expr_values,
        }
        if expr_names:
            update_kwargs["ExpressionAttributeNames"] = expr_names

        self.schedules_table.update_item(**update_kwargs)

        logger.info(f"Updated schedule {schedule_id}")

        return await self.get_schedule(organization_id, schedule_id)

    async def delete_schedule(
        self,
        organization_id: str,
        schedule_id: str,
    ) -> bool:
        """
        Delete a schedule.

        Args:
            organization_id: Organization ID
            schedule_id: Schedule ID

        Returns:
            True if deleted successfully

        Raises:
            ScheduleNotFoundError: If schedule not found
        """
        # Verify exists
        await self.get_schedule(organization_id, schedule_id)

        self.schedules_table.delete_item(
            Key={
                "organization_id": organization_id,
                "schedule_id": schedule_id,
            }
        )
        logger.info(f"Deleted schedule {schedule_id}")
        return True

    # =========================================================================
    # Schedule Status Management
    # =========================================================================

    async def pause_schedule(
        self,
        organization_id: str,
        schedule_id: str,
    ) -> GPUScheduledJob:
        """Pause a schedule."""
        return await self._update_status(
            organization_id, schedule_id, ScheduledJobStatus.PAUSED
        )

    async def resume_schedule(
        self,
        organization_id: str,
        schedule_id: str,
    ) -> GPUScheduledJob:
        """Resume a paused schedule."""
        # Verify schedule exists (raises ScheduleNotFoundError if not)
        await self.get_schedule(organization_id, schedule_id)

        # Reset consecutive failures on manual resume
        await self._update_status(
            organization_id, schedule_id, ScheduledJobStatus.ACTIVE
        )

        # Update with reset failures
        self.schedules_table.update_item(
            Key={
                "organization_id": organization_id,
                "schedule_id": schedule_id,
            },
            UpdateExpression="SET consecutive_failures = :zero",
            ExpressionAttributeValues={":zero": 0},
        )

        return await self.get_schedule(organization_id, schedule_id)

    async def disable_schedule(
        self,
        organization_id: str,
        schedule_id: str,
    ) -> GPUScheduledJob:
        """Disable a schedule permanently."""
        return await self._update_status(
            organization_id, schedule_id, ScheduledJobStatus.DISABLED
        )

    async def _update_status(
        self,
        organization_id: str,
        schedule_id: str,
        status: ScheduledJobStatus,
    ) -> GPUScheduledJob:
        """Update schedule status."""
        schedule = await self.get_schedule(organization_id, schedule_id)

        next_run_str = (
            schedule.next_run_at.isoformat()
            if schedule.next_run_at
            else "9999-12-31T23:59:59"
        )

        self.schedules_table.update_item(
            Key={
                "organization_id": organization_id,
                "schedule_id": schedule_id,
            },
            UpdateExpression="SET #status = :status, status_next_run = :status_next_run, updated_at = :updated_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status.value,
                ":status_next_run": f"{status.value}#{next_run_str}",
                ":updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(f"Updated schedule {schedule_id} status to {status.value}")

        return await self.get_schedule(organization_id, schedule_id)

    # =========================================================================
    # Schedule Listing
    # =========================================================================

    async def list_schedules(
        self,
        organization_id: str,
        status: ScheduledJobStatus | None = None,
        limit: int = 50,
    ) -> list[GPUScheduledJob]:
        """
        List schedules for an organization.

        Args:
            organization_id: Organization ID
            status: Optional status filter
            limit: Maximum results

        Returns:
            List of schedules
        """
        if status:
            # Use status-next-run GSI (org_id as hash, status_next_run as range)
            response = self.schedules_table.query(
                IndexName="status-next-run-index",
                KeyConditionExpression="organization_id = :org_id AND begins_with(status_next_run, :prefix)",
                ExpressionAttributeValues={
                    ":org_id": organization_id,
                    ":prefix": f"{status.value}#",
                },
                Limit=limit,
            )
        else:
            response = self.schedules_table.query(
                KeyConditionExpression="organization_id = :org_id",
                ExpressionAttributeValues={":org_id": organization_id},
                Limit=limit,
            )

        return [
            GPUScheduledJob.from_dynamodb_item(item)
            for item in response.get("Items", [])
        ]

    async def list_due_schedules(
        self,
        before: datetime | None = None,
        limit: int = 100,
    ) -> list[GPUScheduledJob]:
        """
        List schedules that are due for execution across all organizations.

        This uses a table scan with filters since we need to find due schedules
        across all organizations. Suitable for background scheduler operations.

        Args:
            before: Time threshold (default: now)
            limit: Maximum results

        Returns:
            Schedules ready to run
        """
        before = before or datetime.now(timezone.utc)
        cutoff = before.isoformat()

        # Scan for active schedules with next_run_at <= before
        # Using scan because we need to find schedules across all organizations
        response = self.schedules_table.scan(
            FilterExpression="#status = :active_status AND next_run_at <= :cutoff",
            ExpressionAttributeNames={
                "#status": "status",  # 'status' is a DynamoDB reserved word
            },
            ExpressionAttributeValues={
                ":active_status": ScheduledJobStatus.ACTIVE.value,
                ":cutoff": cutoff,
            },
            Limit=limit,
        )

        return [
            GPUScheduledJob.from_dynamodb_item(item)
            for item in response.get("Items", [])
        ]

    async def get_due_schedules(
        self,
        before: datetime | None = None,
        limit: int = 100,
    ) -> list[GPUScheduledJob]:
        """Alias for list_due_schedules."""
        return await self.list_due_schedules(before=before, limit=limit)

    async def record_execution(
        self,
        organization_id: str,
        schedule_id: str,
        job_id: str,
        success: bool,
    ) -> GPUScheduledJob:
        """
        Record the result of a schedule execution.

        Args:
            organization_id: Organization ID
            schedule_id: Schedule ID
            job_id: ID of the job that was created
            success: Whether the execution was successful

        Returns:
            Updated schedule
        """
        schedule = await self.get_schedule(organization_id, schedule_id)
        now = datetime.now(timezone.utc)

        # Calculate next run
        next_run = self._calculate_next_run(
            frequency=schedule.frequency,
            cron_expression=schedule.cron_expression,
            tz=schedule.timezone,
            after=now,
        )

        if success:
            # Success - reset consecutive failures
            self.schedules_table.update_item(
                Key={
                    "organization_id": organization_id,
                    "schedule_id": schedule_id,
                },
                UpdateExpression=(
                    "SET run_count = run_count + :inc, "
                    "consecutive_failures = :zero, "
                    "last_run_at = :last_run, "
                    "last_job_id = :job_id, "
                    "next_run_at = :next_run, "
                    "status_next_run = :status_next_run, "
                    "updated_at = :updated_at"
                ),
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":zero": 0,
                    ":last_run": now.isoformat(),
                    ":job_id": job_id,
                    ":next_run": next_run.isoformat(),
                    ":status_next_run": f"{schedule.status.value}#{next_run.isoformat()}",
                    ":updated_at": now.isoformat(),
                },
            )
        else:
            # Failure - increment consecutive failures
            new_failures = schedule.consecutive_failures + 1
            new_status = schedule.status

            # Auto-pause after max consecutive failures
            if new_failures >= MAX_CONSECUTIVE_FAILURES:
                new_status = ScheduledJobStatus.PAUSED
                logger.warning(
                    f"Auto-paused schedule {schedule_id} after "
                    f"{new_failures} consecutive failures"
                )

            self.schedules_table.update_item(
                Key={
                    "organization_id": organization_id,
                    "schedule_id": schedule_id,
                },
                UpdateExpression=(
                    "SET run_count = run_count + :inc, "
                    "failure_count = failure_count + :inc, "
                    "consecutive_failures = :failures, "
                    "last_run_at = :last_run, "
                    "last_job_id = :job_id, "
                    "next_run_at = :next_run, "
                    "#status = :new_status, "
                    "status_next_run = :status_next_run, "
                    "updated_at = :updated_at"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":failures": new_failures,
                    ":last_run": now.isoformat(),
                    ":job_id": job_id,
                    ":next_run": next_run.isoformat(),
                    ":new_status": new_status.value,
                    ":status_next_run": f"{new_status.value}#{next_run.isoformat()}",
                    ":updated_at": now.isoformat(),
                },
            )

        return await self.get_schedule(organization_id, schedule_id)

    # =========================================================================
    # Schedule Dispatch
    # =========================================================================

    async def dispatch_due_schedules(
        self,
        gpu_scheduler_service: Any = None,
    ) -> list[str]:
        """
        Dispatch all schedules that are due for execution.

        Args:
            gpu_scheduler_service: GPU scheduler service for job submission

        Returns:
            List of submitted job IDs
        """
        due_schedules = await self.list_due_schedules()
        dispatched_job_ids: list[str] = []

        for schedule in due_schedules:
            try:
                job_id = await self._dispatch_schedule(schedule, gpu_scheduler_service)
                dispatched_job_ids.append(job_id)
            except Exception as e:
                logger.error(f"Failed to dispatch schedule {schedule.schedule_id}: {e}")
                await self._handle_dispatch_failure(schedule)

        return dispatched_job_ids

    async def _dispatch_schedule(
        self,
        schedule: GPUScheduledJob,
        gpu_scheduler_service: Any = None,
    ) -> str:
        """
        Dispatch a single schedule.

        Args:
            schedule: Schedule to dispatch
            gpu_scheduler_service: GPU scheduler service

        Returns:
            Created job ID
        """
        now = datetime.now(timezone.utc)

        # Check end date
        if schedule.end_date and now > schedule.end_date:
            await self.disable_schedule(schedule.organization_id, schedule.schedule_id)
            raise ValueError(f"Schedule {schedule.schedule_id} has ended")

        # Build job request
        if schedule.template_id:
            # Get config from template
            job_request = await self.template_service.create_job_request_from_template(
                organization_id=schedule.organization_id,
                template_id=schedule.template_id,
                user_id=schedule.user_id,
                overrides={
                    "priority": schedule.priority.value,
                    "gpu_memory_gb": schedule.gpu_memory_gb,
                    "max_runtime_hours": schedule.max_runtime_hours,
                    "checkpoint_enabled": schedule.checkpoint_enabled,
                },
            )
        else:
            # Use inline config
            job_request = {
                "job_type": schedule.job_type.value,
                "config": schedule.config.model_dump(),
                "priority": schedule.priority.value,
                "gpu_memory_gb": schedule.gpu_memory_gb,
                "max_runtime_hours": schedule.max_runtime_hours,
                "checkpoint_enabled": schedule.checkpoint_enabled,
            }

        # Submit job
        job_id = str(uuid.uuid4())  # Would come from gpu_scheduler_service

        if gpu_scheduler_service:
            request = GPUJobCreateRequest(**job_request)
            job = await gpu_scheduler_service.submit_job(
                organization_id=schedule.organization_id,
                user_id=schedule.user_id,
                request=request,
            )
            job_id = job.job_id

        # Update schedule with next run
        next_run = self._calculate_next_run(
            frequency=schedule.frequency,
            cron_expression=schedule.cron_expression,
            tz=schedule.timezone,
            after=now,
        )

        self.schedules_table.update_item(
            Key={
                "organization_id": schedule.organization_id,
                "schedule_id": schedule.schedule_id,
            },
            UpdateExpression=(
                "SET last_run_at = :last_run, "
                "last_job_id = :job_id, "
                "next_run_at = :next_run, "
                "run_count = run_count + :inc, "
                "consecutive_failures = :zero, "
                "status_next_run = :status_next_run"
            ),
            ExpressionAttributeValues={
                ":last_run": now.isoformat(),
                ":job_id": job_id,
                ":next_run": next_run.isoformat(),
                ":inc": 1,
                ":zero": 0,
                ":status_next_run": f"{ScheduledJobStatus.ACTIVE.value}#{next_run.isoformat()}",
            },
        )

        logger.info(
            f"Dispatched schedule {schedule.schedule_id} -> job {job_id}, "
            f"next run: {next_run}"
        )

        return job_id

    async def _handle_dispatch_failure(
        self,
        schedule: GPUScheduledJob,
    ) -> None:
        """Handle a schedule dispatch failure."""
        now = datetime.now(timezone.utc)
        new_failures = schedule.consecutive_failures + 1

        # Auto-pause after max consecutive failures
        if new_failures >= MAX_CONSECUTIVE_FAILURES:
            await self.pause_schedule(schedule.organization_id, schedule.schedule_id)
            logger.warning(
                f"Auto-paused schedule {schedule.schedule_id} after "
                f"{new_failures} consecutive failures"
            )
            return

        # Calculate next run with backoff
        backoff_minutes = min(5 * (2**new_failures), 60)  # Max 60 min backoff
        next_run = now + timedelta(minutes=backoff_minutes)

        self.schedules_table.update_item(
            Key={
                "organization_id": schedule.organization_id,
                "schedule_id": schedule.schedule_id,
            },
            UpdateExpression=(
                "SET failure_count = failure_count + :inc, "
                "consecutive_failures = :failures, "
                "next_run_at = :next_run, "
                "status_next_run = :status_next_run"
            ),
            ExpressionAttributeValues={
                ":inc": 1,
                ":failures": new_failures,
                ":next_run": next_run.isoformat(),
                ":status_next_run": f"{schedule.status.value}#{next_run.isoformat()}",
            },
        )

    # =========================================================================
    # Cron Calculation
    # =========================================================================

    def _calculate_next_run(
        self,
        frequency: ScheduleFrequency,
        cron_expression: str | None = None,
        tz: str = "UTC",
        after: datetime | None = None,
    ) -> datetime:
        """
        Calculate the next run time based on frequency.

        Args:
            frequency: Schedule frequency
            cron_expression: Custom cron expression
            tz: Timezone name
            after: Calculate next run after this time

        Returns:
            Next run datetime in UTC
        """
        after = after or datetime.now(timezone.utc)

        # Convert to local timezone
        local_tz = ZoneInfo(tz)
        local_time = after.astimezone(local_tz)

        if frequency == ScheduleFrequency.ONCE:
            # One-time schedule - next run is the start time
            return after

        elif frequency == ScheduleFrequency.HOURLY:
            # Next hour, at :00
            next_run = local_time.replace(minute=0, second=0, microsecond=0)
            next_run += timedelta(hours=1)

        elif frequency == ScheduleFrequency.DAILY:
            # Next day at midnight
            next_run = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
            next_run += timedelta(days=1)

        elif frequency == ScheduleFrequency.WEEKLY:
            # Next Monday at midnight
            days_until_monday = (7 - local_time.weekday()) % 7 or 7
            next_run = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
            next_run += timedelta(days=days_until_monday)

        elif frequency == ScheduleFrequency.MONTHLY:
            # First day of next month at midnight
            if local_time.month == 12:
                next_run = local_time.replace(
                    year=local_time.year + 1,
                    month=1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                next_run = local_time.replace(
                    month=local_time.month + 1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )

        elif frequency == ScheduleFrequency.CUSTOM and cron_expression:
            # Parse cron expression
            next_run = self._parse_cron_next_run(cron_expression, local_time)

        else:
            # Default to daily
            next_run = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
            next_run += timedelta(days=1)

        # Convert back to UTC
        return next_run.astimezone(timezone.utc)

    def _parse_cron_next_run(
        self,
        cron_expression: str,
        after: datetime,
    ) -> datetime:
        """
        Parse cron expression and find next run time.

        Supports standard 5-field cron format:
        minute hour day_of_month month day_of_week

        Args:
            cron_expression: Cron expression string
            after: Calculate next run after this time

        Returns:
            Next run datetime
        """
        parts = cron_expression.split()
        if len(parts) < 5:
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        minute, hour, day, month, day_of_week = parts[:5]

        # Simple implementation: support specific values and wildcards
        # For production, use a library like croniter

        def parse_field(field: str, min_val: int, max_val: int) -> list[int]:
            """Parse a single cron field."""
            if field == "*":
                return list(range(min_val, max_val + 1))
            if "/" in field:
                base, step = field.split("/")
                if base == "*":
                    return list(range(min_val, max_val + 1, int(step)))
            if "," in field:
                return [int(v) for v in field.split(",")]
            if "-" in field:
                start, end = field.split("-")
                return list(range(int(start), int(end) + 1))
            return [int(field)]

        valid_minutes = parse_field(minute, 0, 59)
        valid_hours = parse_field(hour, 0, 23)
        valid_days = parse_field(day, 1, 31)
        valid_months = parse_field(month, 1, 12)
        valid_days_of_week = parse_field(day_of_week, 0, 6)

        # Find next matching time
        candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

        for _ in range(366 * 24 * 60):  # Max 1 year search
            if (
                candidate.month in valid_months
                and candidate.day in valid_days
                and candidate.weekday() in valid_days_of_week
                and candidate.hour in valid_hours
                and candidate.minute in valid_minutes
            ):
                return candidate
            candidate += timedelta(minutes=1)

        # Fallback: next day
        return after + timedelta(days=1)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _check_schedule_limits(
        self,
        organization_id: str,
    ) -> None:
        """Check if schedule limits are exceeded."""
        schedules = await self.list_schedules(
            organization_id=organization_id,
            limit=MAX_SCHEDULES_PER_ORG + 1,
        )
        if len(schedules) >= MAX_SCHEDULES_PER_ORG:
            raise ScheduleLimitExceededError(
                f"Organization limit of {MAX_SCHEDULES_PER_ORG} schedules exceeded"
            )
