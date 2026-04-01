"""
Scheduling Service Models

Data models for job scheduling and queue management.
ADR-055: Agent Scheduling View and Job Queue Management
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ScheduleStatus(str, Enum):
    """Status of a scheduled job."""

    PENDING = "PENDING"  # Awaiting scheduled time
    DISPATCHED = "DISPATCHED"  # Sent to job queue
    CANCELLED = "CANCELLED"  # Cancelled by user
    FAILED = "FAILED"  # Failed to dispatch


class JobType(str, Enum):
    """Types of jobs that can be scheduled."""

    SECURITY_SCAN = "SECURITY_SCAN"
    CODE_REVIEW = "CODE_REVIEW"
    PATCH_GENERATION = "PATCH_GENERATION"
    VULNERABILITY_ASSESSMENT = "VULNERABILITY_ASSESSMENT"
    DEPENDENCY_UPDATE = "DEPENDENCY_UPDATE"
    REPOSITORY_INDEXING = "REPOSITORY_INDEXING"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    THREAT_ANALYSIS = "THREAT_ANALYSIS"
    CODE_QUALITY_SCAN = "CODE_QUALITY_SCAN"
    PERFORMANCE_ANALYSIS = "PERFORMANCE_ANALYSIS"
    CUSTOM = "CUSTOM"


class Priority(str, Enum):
    """Job priority levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class RecurringSchedule(str, Enum):
    """Predefined recurring schedule options."""

    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"  # Uses cron_expression


@dataclass
class ScheduleJobRequest:
    """Request to schedule a new job."""

    job_type: JobType
    scheduled_at: datetime
    repository_id: Optional[str] = None
    priority: Priority = Priority.NORMAL
    parameters: Dict[str, Any] = field(default_factory=dict)
    notify_on_completion: bool = True
    description: Optional[str] = None

    def validate(self) -> List[str]:
        """Validate the schedule request."""
        errors = []

        # Scheduled time must be in the future
        now = datetime.now(timezone.utc)
        if self.scheduled_at.tzinfo is None:
            self.scheduled_at = self.scheduled_at.replace(tzinfo=timezone.utc)

        if self.scheduled_at <= now:
            errors.append("scheduled_at must be in the future")

        # Max 30 days in the future
        max_future = now.replace(day=now.day + 30) if now.day <= 1 else now
        try:
            from datetime import timedelta

            max_future = now + timedelta(days=30)
            if self.scheduled_at > max_future:
                errors.append("scheduled_at cannot be more than 30 days in the future")
        except Exception:
            pass

        # Min 5 minutes in the future
        try:
            from datetime import timedelta

            min_future = now + timedelta(minutes=5)
            if self.scheduled_at < min_future:
                errors.append("scheduled_at must be at least 5 minutes in the future")
        except Exception:
            pass

        return errors


@dataclass
class ScheduledJob:
    """A scheduled job awaiting execution."""

    schedule_id: str
    organization_id: str
    job_type: JobType
    scheduled_at: datetime
    created_at: datetime
    created_by: str
    status: ScheduleStatus
    priority: Priority = Priority.NORMAL
    repository_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    notify_on_completion: bool = True
    description: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    dispatched_job_id: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def create(
        cls,
        organization_id: str,
        request: ScheduleJobRequest,
        created_by: str,
    ) -> "ScheduledJob":
        """Create a new scheduled job from a request."""
        now = datetime.now(timezone.utc)
        return cls(
            schedule_id=str(uuid.uuid4()),
            organization_id=organization_id,
            job_type=request.job_type,
            scheduled_at=request.scheduled_at,
            created_at=now,
            created_by=created_by,
            status=ScheduleStatus.PENDING,
            priority=request.priority,
            repository_id=request.repository_id,
            parameters=request.parameters,
            notify_on_completion=request.notify_on_completion,
            description=request.description,
        )

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            "schedule_id": self.schedule_id,
            "organization_id": self.organization_id,
            "job_type": (
                self.job_type.value
                if isinstance(self.job_type, Enum)
                else self.job_type
            ),
            "scheduled_at": self.scheduled_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "status": (
                self.status.value if isinstance(self.status, Enum) else self.status
            ),
            "priority": (
                self.priority.value
                if isinstance(self.priority, Enum)
                else self.priority
            ),
            "notify_on_completion": self.notify_on_completion,
        }

        if self.repository_id:
            item["repository_id"] = self.repository_id
        if self.parameters:
            item["parameters"] = self.parameters
        if self.description:
            item["description"] = self.description
        if self.dispatched_at:
            item["dispatched_at"] = self.dispatched_at.isoformat()
        if self.dispatched_job_id:
            item["dispatched_job_id"] = self.dispatched_job_id
        if self.cancelled_at:
            item["cancelled_at"] = self.cancelled_at.isoformat()
        if self.cancelled_by:
            item["cancelled_by"] = self.cancelled_by
        if self.error_message:
            item["error_message"] = self.error_message

        # TTL: 30 days after scheduled time
        from datetime import timedelta

        ttl_time = self.scheduled_at + timedelta(days=30)
        item["ttl"] = int(ttl_time.timestamp())

        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "ScheduledJob":
        """Create from DynamoDB item."""

        def parse_datetime(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        return cls(
            schedule_id=item["schedule_id"],
            organization_id=item["organization_id"],
            job_type=JobType(item["job_type"]),
            scheduled_at=parse_datetime(item["scheduled_at"]),
            created_at=parse_datetime(item["created_at"]),
            created_by=item["created_by"],
            status=ScheduleStatus(item["status"]),
            priority=Priority(item.get("priority", "NORMAL")),
            repository_id=item.get("repository_id"),
            parameters=item.get("parameters", {}),
            notify_on_completion=item.get("notify_on_completion", True),
            description=item.get("description"),
            dispatched_at=parse_datetime(item.get("dispatched_at")),
            dispatched_job_id=item.get("dispatched_job_id"),
            cancelled_at=parse_datetime(item.get("cancelled_at")),
            cancelled_by=item.get("cancelled_by"),
            error_message=item.get("error_message"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "schedule_id": self.schedule_id,
            "organization_id": self.organization_id,
            "job_type": (
                self.job_type.value
                if isinstance(self.job_type, Enum)
                else self.job_type
            ),
            "scheduled_at": self.scheduled_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "status": (
                self.status.value if isinstance(self.status, Enum) else self.status
            ),
            "priority": (
                self.priority.value
                if isinstance(self.priority, Enum)
                else self.priority
            ),
            "repository_id": self.repository_id,
            "parameters": self.parameters,
            "notify_on_completion": self.notify_on_completion,
            "description": self.description,
        }

        if self.dispatched_at:
            result["dispatched_at"] = self.dispatched_at.isoformat()
        if self.dispatched_job_id:
            result["dispatched_job_id"] = self.dispatched_job_id
        if self.cancelled_at:
            result["cancelled_at"] = self.cancelled_at.isoformat()
        if self.cancelled_by:
            result["cancelled_by"] = self.cancelled_by
        if self.error_message:
            result["error_message"] = self.error_message

        return result


@dataclass
class QueueStatus:
    """Current status of the job queue."""

    total_queued: int
    total_scheduled: int
    active_jobs: int
    by_priority: Dict[str, int]
    by_type: Dict[str, int]
    avg_wait_time_seconds: float
    throughput_per_hour: float
    oldest_queued_at: Optional[datetime] = None
    next_scheduled_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "total_queued": self.total_queued,
            "total_scheduled": self.total_scheduled,
            "active_jobs": self.active_jobs,
            "by_priority": self.by_priority,
            "by_type": self.by_type,
            "avg_wait_time_seconds": self.avg_wait_time_seconds,
            "throughput_per_hour": self.throughput_per_hour,
            "oldest_queued_at": (
                self.oldest_queued_at.isoformat() if self.oldest_queued_at else None
            ),
            "next_scheduled_at": (
                self.next_scheduled_at.isoformat() if self.next_scheduled_at else None
            ),
        }


@dataclass
class TimelineEntry:
    """Entry for timeline visualization."""

    job_id: str
    job_type: str
    status: str
    title: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    repository_name: Optional[str] = None
    created_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "title": self.title,
            "scheduled_at": (
                self.scheduled_at.isoformat() if self.scheduled_at else None
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "duration_seconds": self.duration_seconds,
            "repository_name": self.repository_name,
            "created_by": self.created_by,
        }


@dataclass
class RecurringTask:
    """A recurring scheduled task (Phase 2)."""

    task_id: str
    organization_id: str
    job_type: JobType
    schedule: RecurringSchedule
    cron_expression: Optional[str] = None  # For CUSTOM schedule
    repository_id: Optional[str] = None
    priority: Priority = Priority.NORMAL
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "task_id": self.task_id,
            "organization_id": self.organization_id,
            "job_type": (
                self.job_type.value
                if isinstance(self.job_type, Enum)
                else self.job_type
            ),
            "schedule": (
                self.schedule.value
                if isinstance(self.schedule, Enum)
                else self.schedule
            ),
            "cron_expression": self.cron_expression,
            "repository_id": self.repository_id,
            "priority": (
                self.priority.value
                if isinstance(self.priority, Enum)
                else self.priority
            ),
            "parameters": self.parameters,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "description": self.description,
        }
