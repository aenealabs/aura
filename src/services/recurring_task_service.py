"""
Project Aura - Recurring Task Service

Service for managing recurring scheduled tasks with cron-based scheduling.
Handles CRUD operations, cron expression validation, and next run calculation.

ADR-055 Phase 3: Recurring Tasks and Advanced Features

Table Schema:
- PK: task_id (UUID)
- GSI: organization_id-index for per-org queries
- GSI: enabled-next_run-index for scheduler queries
"""

import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================


class JobType(Enum):
    """Types of jobs that can be scheduled."""

    SECURITY_SCAN = "SECURITY_SCAN"
    CODE_REVIEW = "CODE_REVIEW"
    DEPENDENCY_UPDATE = "DEPENDENCY_UPDATE"
    BACKUP = "BACKUP"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    PATCH_GENERATION = "PATCH_GENERATION"
    CUSTOM = "CUSTOM"


class TaskStatus(Enum):
    """Status of a recurring task."""

    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class RecurringTask:
    """Represents a recurring scheduled task."""

    task_id: str
    name: str
    job_type: str
    cron_expression: str
    enabled: bool = True
    description: str = ""
    target_repository: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    organization_id: str = "default"
    created_by: str = "system"
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    run_count: int = 0
    failure_count: int = 0
    timeout_seconds: int = 3600
    max_retries: int = 3
    notification_emails: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.next_run:
            self.next_run = self._calculate_next_run()

    def _calculate_next_run(self) -> str:
        """Calculate the next run time based on cron expression."""
        try:
            next_time = calculate_next_run(self.cron_expression)
            return next_time.isoformat() if next_time else ""
        except Exception:
            return ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return asdict(self)


@dataclass
class TaskExecution:
    """Record of a task execution."""

    execution_id: str
    task_id: str
    started_at: str
    completed_at: Optional[str] = None
    status: str = "running"  # running, succeeded, failed, timeout
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


# =============================================================================
# Cron Expression Utilities
# =============================================================================


def validate_cron_expression(cron: str) -> tuple[bool, str]:
    """
    Validate a cron expression.

    Args:
        cron: Cron expression (5 parts: minute hour day-of-month month day-of-week)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not cron or not isinstance(cron, str):
        return False, "Cron expression is required"

    parts = cron.strip().split()
    if len(parts) != 5:
        return False, f"Expected 5 parts, got {len(parts)}"

    part_names = ["minute", "hour", "day-of-month", "month", "day-of-week"]
    part_ranges = [
        (0, 59),  # minute
        (0, 23),  # hour
        (1, 31),  # day-of-month
        (1, 12),  # month
        (0, 6),  # day-of-week (0=Sunday)
    ]

    for part, name, (min_val, max_val) in zip(parts, part_names, part_ranges):
        try:
            if not _validate_cron_part(part, min_val, max_val):
                return False, f"Invalid {name} value: {part}"
        except ValueError as e:
            return False, f"Invalid {name}: {str(e)}"

    return True, ""


def _validate_cron_part(part: str, min_val: int, max_val: int) -> bool:
    """Validate a single part of a cron expression."""
    # Handle wildcard
    if part == "*":
        return True

    # Handle step values (*/5, 1-10/2)
    if "/" in part:
        base, step = part.split("/", 1)
        if not step.isdigit() or int(step) < 1:
            return False
        if base == "*":
            return True
        # Continue to validate the base part
        part = base

    # Handle ranges (1-5)
    if "-" in part:
        try:
            start, end = part.split("-", 1)
            start_int = int(start)
            end_int = int(end)
            return min_val <= start_int <= max_val and min_val <= end_int <= max_val
        except ValueError:
            return False

    # Handle lists (1,3,5)
    if "," in part:
        values = part.split(",")
        return all(
            v.isdigit() and min_val <= int(v) <= max_val for v in values if v.strip()
        )

    # Handle single values
    if part.isdigit():
        val = int(part)
        return min_val <= val <= max_val

    return False


def calculate_next_run(cron: str, from_time: Optional[datetime] = None) -> datetime:
    """
    Calculate the next run time for a cron expression.

    This is a simplified implementation. For production, use croniter library.

    Args:
        cron: Cron expression
        from_time: Start time (defaults to now)

    Returns:
        Next scheduled run time
    """
    if from_time is None:
        from_time = datetime.now(timezone.utc)

    # Simple implementation: try to use croniter if available
    try:
        from croniter import croniter

        cron_iter = croniter(cron, from_time)
        return cron_iter.get_next(datetime)
    except ImportError:
        # Fallback: simple next-hour calculation
        # This is just for dev/testing - production should have croniter
        logger.warning("croniter not installed, using simplified scheduling")
        next_run = from_time.replace(minute=0, second=0, microsecond=0) + __import__(
            "datetime"
        ).timedelta(hours=1)
        return next_run


def describe_cron(cron: str) -> str:
    """
    Generate a human-readable description of a cron expression.

    Args:
        cron: Cron expression

    Returns:
        Human-readable description
    """
    parts = cron.strip().split()
    if len(parts) != 5:
        return "Invalid cron expression"

    minute, hour, dom, month, dow = parts

    # Common patterns
    if cron == "0 * * * *":
        return "Every hour at minute 0"
    if cron == "*/15 * * * *":
        return "Every 15 minutes"
    if cron == "*/30 * * * *":
        return "Every 30 minutes"
    if cron == "0 0 * * *":
        return "Daily at midnight"
    if cron == "0 6 * * *":
        return "Daily at 6:00 AM"
    if cron == "0 9 * * 1-5":
        return "Weekdays at 9:00 AM"
    if cron == "0 0 * * 0":
        return "Weekly on Sunday at midnight"
    if cron == "0 6 * * 1":
        return "Weekly on Monday at 6:00 AM"
    if cron == "0 0 1 * *":
        return "Monthly on the 1st at midnight"

    # Build description for other patterns
    desc_parts = []

    # Minute
    if minute == "*":
        desc_parts.append("every minute")
    elif minute.startswith("*/"):
        desc_parts.append(f"every {minute[2:]} minutes")
    elif minute == "0":
        pass  # Will be described with hour
    else:
        desc_parts.append(f"at minute {minute}")

    # Hour
    if hour == "*":
        if minute != "*" and not minute.startswith("*/"):
            desc_parts.append("every hour")
    elif hour.startswith("*/"):
        desc_parts.append(f"every {hour[2:]} hours")
    else:
        try:
            hour_int = int(hour)
            period = "AM" if hour_int < 12 else "PM"
            display_hour = hour_int if hour_int <= 12 else hour_int - 12
            if display_hour == 0:
                display_hour = 12
            min_str = minute if minute != "0" else "00"
            desc_parts.insert(0, f"at {display_hour}:{min_str.zfill(2)} {period}")
        except ValueError:
            desc_parts.append(f"at hour {hour}")

    # Day of week
    if dow != "*":
        days = {
            "0": "Sunday",
            "1": "Monday",
            "2": "Tuesday",
            "3": "Wednesday",
            "4": "Thursday",
            "5": "Friday",
            "6": "Saturday",
        }
        if dow == "1-5":
            desc_parts.append("on weekdays")
        elif dow == "0,6":
            desc_parts.append("on weekends")
        elif dow in days:
            desc_parts.append(f"on {days[dow]}")
        else:
            desc_parts.append(f"on day-of-week {dow}")

    # Day of month
    if dom != "*":
        if dom == "1":
            desc_parts.append("on the 1st")
        elif dom == "15":
            desc_parts.append("on the 15th")
        else:
            desc_parts.append(f"on day {dom}")

    # Month
    if month != "*":
        months = {
            "1": "January",
            "2": "February",
            "3": "March",
            "4": "April",
            "5": "May",
            "6": "June",
            "7": "July",
            "8": "August",
            "9": "September",
            "10": "October",
            "11": "November",
            "12": "December",
        }
        desc_parts.append(f"in {months.get(month, f'month {month}')}")

    return " ".join(desc_parts) if desc_parts else "Custom schedule"


# =============================================================================
# Service Class
# =============================================================================


class RecurringTaskService:
    """Service for managing recurring scheduled tasks."""

    def __init__(self, table_name: Optional[str] = None):
        """Initialize the recurring task service.

        Args:
            table_name: DynamoDB table name for recurring tasks.
        """
        self.table_name = table_name or os.environ.get(
            "RECURRING_TASKS_TABLE_NAME", "aura-recurring-tasks-dev"
        )
        self._table = None
        self._dynamodb = None

    @property
    def table(self) -> Any:
        """Lazy-load DynamoDB table resource."""
        if self._table is None:
            try:
                import boto3

                self._dynamodb = boto3.resource("dynamodb")
                self._table = self._dynamodb.Table(self.table_name)
            except Exception as e:
                logger.warning(f"Failed to connect to DynamoDB: {e}")
                self._table = None
        return self._table

    async def create_task(
        self,
        name: str,
        job_type: str,
        cron_expression: str,
        organization_id: str = "default",
        created_by: str = "system",
        **kwargs: Any,
    ) -> RecurringTask:
        """Create a new recurring task.

        Args:
            name: Task display name
            job_type: Type of job (SECURITY_SCAN, CODE_REVIEW, etc.)
            cron_expression: Cron schedule expression
            organization_id: Organization ID
            created_by: User who created the task
            **kwargs: Additional task parameters

        Returns:
            Created RecurringTask

        Raises:
            ValueError: If cron expression is invalid
        """
        # Validate cron expression
        is_valid, error = validate_cron_expression(cron_expression)
        if not is_valid:
            raise ValueError(f"Invalid cron expression: {error}")

        # Validate job type
        try:
            JobType(job_type)
        except ValueError:
            valid_types = [t.value for t in JobType]
            raise ValueError(f"Invalid job type. Must be one of: {valid_types}")

        # Create task
        task = RecurringTask(
            task_id=str(uuid.uuid4()),
            name=name,
            job_type=job_type,
            cron_expression=cron_expression,
            organization_id=organization_id,
            created_by=created_by,
            **kwargs,
        )

        # Persist to DynamoDB
        if self.table:
            try:
                self.table.put_item(Item=task.to_dict())
                logger.info(f"Created recurring task: {task.task_id}")
            except Exception as e:
                logger.error(f"Failed to persist task: {e}")
                raise
        else:
            logger.warning("DynamoDB not available, task created in-memory only")

        return task

    async def get_task(self, task_id: str) -> Optional[RecurringTask]:
        """Get a recurring task by ID.

        Args:
            task_id: Task identifier

        Returns:
            RecurringTask or None if not found
        """
        if not self.table:
            logger.warning("DynamoDB not available")
            return None

        try:
            response = self.table.get_item(Key={"task_id": task_id})
            item = response.get("Item")
            if item:
                return RecurringTask(**item)
            return None
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            return None

    async def list_tasks(
        self,
        organization_id: Optional[str] = None,
        enabled: Optional[bool] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[RecurringTask]:
        """List recurring tasks with optional filters.

        Args:
            organization_id: Filter by organization
            enabled: Filter by enabled status
            job_type: Filter by job type
            limit: Maximum number of tasks to return

        Returns:
            List of RecurringTask objects
        """
        if not self.table:
            logger.warning("DynamoDB not available")
            return []

        try:
            # Build filter expression
            filter_parts = []
            expression_values = {}
            expression_names = {}

            if organization_id:
                filter_parts.append("#org = :org")
                expression_values[":org"] = organization_id
                expression_names["#org"] = "organization_id"

            if enabled is not None:
                filter_parts.append("#enabled = :enabled")
                expression_values[":enabled"] = enabled
                expression_names["#enabled"] = "enabled"

            if job_type:
                filter_parts.append("#jtype = :jtype")
                expression_values[":jtype"] = job_type
                expression_names["#jtype"] = "job_type"

            # Exclude deleted tasks
            filter_parts.append("#status <> :deleted")
            expression_values[":deleted"] = "deleted"
            expression_names["#status"] = "status"

            scan_kwargs: dict[str, Any] = {"Limit": limit}

            if filter_parts:
                scan_kwargs["FilterExpression"] = " AND ".join(filter_parts)
                scan_kwargs["ExpressionAttributeValues"] = expression_values
                scan_kwargs["ExpressionAttributeNames"] = expression_names

            response = self.table.scan(**scan_kwargs)
            items = response.get("Items", [])

            return [RecurringTask(**item) for item in items]
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []

    async def update_task(
        self, task_id: str, updates: dict[str, Any]
    ) -> Optional[RecurringTask]:
        """Update a recurring task.

        Args:
            task_id: Task identifier
            updates: Dictionary of fields to update

        Returns:
            Updated RecurringTask or None if not found
        """
        # Get existing task
        task = await self.get_task(task_id)
        if not task:
            return None

        # Apply updates
        allowed_fields = {
            "name",
            "description",
            "cron_expression",
            "enabled",
            "target_repository",
            "parameters",
            "timeout_seconds",
            "max_retries",
            "notification_emails",
            "tags",
        }

        for key, value in updates.items():
            if key in allowed_fields:
                setattr(task, key, value)

        # Validate if cron changed
        if "cron_expression" in updates:
            is_valid, error = validate_cron_expression(task.cron_expression)
            if not is_valid:
                raise ValueError(f"Invalid cron expression: {error}")
            # Recalculate next run
            task.next_run = task._calculate_next_run()

        # Update timestamp
        task.updated_at = datetime.now(timezone.utc).isoformat()

        # Persist
        if self.table:
            try:
                self.table.put_item(Item=task.to_dict())
                logger.info(f"Updated recurring task: {task_id}")
            except Exception as e:
                logger.error(f"Failed to update task: {e}")
                raise

        return task

    async def delete_task(self, task_id: str, hard_delete: bool = False) -> bool:
        """Delete a recurring task.

        Args:
            task_id: Task identifier
            hard_delete: If True, permanently delete. Otherwise soft-delete.

        Returns:
            True if deleted, False if not found
        """
        if hard_delete:
            if not self.table:
                return False
            try:
                self.table.delete_item(Key={"task_id": task_id})
                logger.info(f"Hard deleted recurring task: {task_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete task: {e}")
                return False
        else:
            # Soft delete
            task = await self.get_task(task_id)
            if not task:
                return False
            task.status = "deleted"
            task.enabled = False
            task.updated_at = datetime.now(timezone.utc).isoformat()
            if self.table:
                self.table.put_item(Item=task.to_dict())
            logger.info(f"Soft deleted recurring task: {task_id}")
            return True

    async def toggle_task(self, task_id: str, enabled: bool) -> Optional[RecurringTask]:
        """Enable or disable a recurring task.

        Args:
            task_id: Task identifier
            enabled: Whether to enable or disable

        Returns:
            Updated RecurringTask or None if not found
        """
        return await self.update_task(task_id, {"enabled": enabled})

    async def record_execution(
        self,
        task_id: str,
        status: str = "succeeded",
        error: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> Optional[RecurringTask]:
        """Record a task execution and update next run time.

        Args:
            task_id: Task identifier
            status: Execution status (succeeded, failed)
            error: Error message if failed
            duration_seconds: Execution duration

        Returns:
            Updated RecurringTask
        """
        task = await self.get_task(task_id)
        if not task:
            return None

        now = datetime.now(timezone.utc)

        # Update run stats
        task.last_run = now.isoformat()
        task.run_count += 1
        if status == "failed":
            task.failure_count += 1

        # Calculate next run
        task.next_run = calculate_next_run(task.cron_expression, now).isoformat()
        task.updated_at = now.isoformat()

        # Persist
        if self.table:
            self.table.put_item(Item=task.to_dict())

        return task

    async def get_due_tasks(self, limit: int = 50) -> list[RecurringTask]:
        """Get tasks that are due for execution.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of tasks due for execution
        """
        now = datetime.now(timezone.utc).isoformat()

        if not self.table:
            return []

        try:
            response = self.table.scan(
                FilterExpression="#enabled = :enabled AND #status = :status AND #next_run <= :now",
                ExpressionAttributeNames={
                    "#enabled": "enabled",
                    "#status": "status",
                    "#next_run": "next_run",
                },
                ExpressionAttributeValues={
                    ":enabled": True,
                    ":status": "active",
                    ":now": now,
                },
                Limit=limit,
            )

            items = response.get("Items", [])
            return [RecurringTask(**item) for item in items]
        except Exception as e:
            logger.error(f"Failed to get due tasks: {e}")
            return []


# =============================================================================
# Module-level Instance
# =============================================================================


_service_instance: Optional[RecurringTaskService] = None


def get_recurring_task_service() -> RecurringTaskService:
    """Get or create the singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RecurringTaskService()
    return _service_instance


def set_recurring_task_service(service: Optional[RecurringTaskService]) -> None:
    """Set the service instance (for testing)."""
    global _service_instance
    _service_instance = service
