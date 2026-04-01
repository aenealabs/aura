"""
Tests for Scheduling Service Models.

Comprehensive tests for dataclasses, enums, and model methods.
ADR-055: Agent Scheduling View and Job Queue Management
"""

import platform
from datetime import datetime, timedelta, timezone

import pytest

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.scheduling.models import (
    JobType,
    Priority,
    QueueStatus,
    RecurringSchedule,
    RecurringTask,
    ScheduledJob,
    ScheduleJobRequest,
    ScheduleStatus,
    TimelineEntry,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestScheduleStatus:
    """Tests for ScheduleStatus enum."""

    def test_pending_value(self):
        """Test PENDING status value."""
        assert ScheduleStatus.PENDING.value == "PENDING"

    def test_dispatched_value(self):
        """Test DISPATCHED status value."""
        assert ScheduleStatus.DISPATCHED.value == "DISPATCHED"

    def test_cancelled_value(self):
        """Test CANCELLED status value."""
        assert ScheduleStatus.CANCELLED.value == "CANCELLED"

    def test_failed_value(self):
        """Test FAILED status value."""
        assert ScheduleStatus.FAILED.value == "FAILED"

    def test_all_statuses_are_strings(self):
        """Test all statuses have string values."""
        for status in ScheduleStatus:
            assert isinstance(status.value, str)


class TestJobType:
    """Tests for JobType enum."""

    def test_security_scan_value(self):
        """Test SECURITY_SCAN job type."""
        assert JobType.SECURITY_SCAN.value == "SECURITY_SCAN"

    def test_code_review_value(self):
        """Test CODE_REVIEW job type."""
        assert JobType.CODE_REVIEW.value == "CODE_REVIEW"

    def test_patch_generation_value(self):
        """Test PATCH_GENERATION job type."""
        assert JobType.PATCH_GENERATION.value == "PATCH_GENERATION"

    def test_vulnerability_assessment_value(self):
        """Test VULNERABILITY_ASSESSMENT job type."""
        assert JobType.VULNERABILITY_ASSESSMENT.value == "VULNERABILITY_ASSESSMENT"

    def test_dependency_update_value(self):
        """Test DEPENDENCY_UPDATE job type."""
        assert JobType.DEPENDENCY_UPDATE.value == "DEPENDENCY_UPDATE"

    def test_repository_indexing_value(self):
        """Test REPOSITORY_INDEXING job type."""
        assert JobType.REPOSITORY_INDEXING.value == "REPOSITORY_INDEXING"

    def test_compliance_check_value(self):
        """Test COMPLIANCE_CHECK job type."""
        assert JobType.COMPLIANCE_CHECK.value == "COMPLIANCE_CHECK"

    def test_threat_analysis_value(self):
        """Test THREAT_ANALYSIS job type."""
        assert JobType.THREAT_ANALYSIS.value == "THREAT_ANALYSIS"

    def test_code_quality_scan_value(self):
        """Test CODE_QUALITY_SCAN job type."""
        assert JobType.CODE_QUALITY_SCAN.value == "CODE_QUALITY_SCAN"

    def test_performance_analysis_value(self):
        """Test PERFORMANCE_ANALYSIS job type."""
        assert JobType.PERFORMANCE_ANALYSIS.value == "PERFORMANCE_ANALYSIS"

    def test_custom_value(self):
        """Test CUSTOM job type."""
        assert JobType.CUSTOM.value == "CUSTOM"

    def test_all_job_types_count(self):
        """Test total count of job types."""
        assert len(list(JobType)) == 11


class TestPriority:
    """Tests for Priority enum."""

    def test_critical_value(self):
        """Test CRITICAL priority."""
        assert Priority.CRITICAL.value == "CRITICAL"

    def test_high_value(self):
        """Test HIGH priority."""
        assert Priority.HIGH.value == "HIGH"

    def test_normal_value(self):
        """Test NORMAL priority."""
        assert Priority.NORMAL.value == "NORMAL"

    def test_low_value(self):
        """Test LOW priority."""
        assert Priority.LOW.value == "LOW"

    def test_all_priorities_count(self):
        """Test total count of priorities."""
        assert len(list(Priority)) == 4


class TestRecurringSchedule:
    """Tests for RecurringSchedule enum."""

    def test_hourly_value(self):
        """Test HOURLY schedule."""
        assert RecurringSchedule.HOURLY.value == "HOURLY"

    def test_daily_value(self):
        """Test DAILY schedule."""
        assert RecurringSchedule.DAILY.value == "DAILY"

    def test_weekly_value(self):
        """Test WEEKLY schedule."""
        assert RecurringSchedule.WEEKLY.value == "WEEKLY"

    def test_monthly_value(self):
        """Test MONTHLY schedule."""
        assert RecurringSchedule.MONTHLY.value == "MONTHLY"

    def test_custom_value(self):
        """Test CUSTOM schedule."""
        assert RecurringSchedule.CUSTOM.value == "CUSTOM"


# =============================================================================
# ScheduleJobRequest Tests
# =============================================================================


class TestScheduleJobRequest:
    """Tests for ScheduleJobRequest dataclass."""

    def test_create_request_basic(self):
        """Test basic request creation."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
        )

        assert request.job_type == JobType.SECURITY_SCAN
        assert request.scheduled_at == scheduled_at
        assert request.priority == Priority.NORMAL
        assert request.notify_on_completion is True

    def test_create_request_with_all_fields(self):
        """Test request creation with all fields."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.CODE_REVIEW,
            scheduled_at=scheduled_at,
            repository_id="repo-123",
            priority=Priority.HIGH,
            parameters={"branch": "main"},
            notify_on_completion=False,
            description="Code review for PR #42",
        )

        assert request.job_type == JobType.CODE_REVIEW
        assert request.repository_id == "repo-123"
        assert request.priority == Priority.HIGH
        assert request.parameters == {"branch": "main"}
        assert request.notify_on_completion is False
        assert request.description == "Code review for PR #42"

    def test_validate_future_time(self):
        """Test validation accepts future scheduled time."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
        )

        errors = request.validate()
        assert not any("future" in e.lower() for e in errors)

    def test_validate_past_time_error(self):
        """Test validation rejects past scheduled time."""
        scheduled_at = datetime.now(timezone.utc) - timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
        )

        errors = request.validate()
        assert any("future" in e.lower() for e in errors)

    def test_validate_too_far_future(self):
        """Test validation rejects time more than 30 days in future."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(days=31)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
        )

        errors = request.validate()
        assert any("30 days" in e for e in errors)

    def test_validate_too_soon(self):
        """Test validation rejects time less than 5 minutes in future."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=2)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
        )

        errors = request.validate()
        assert any("5 minutes" in e for e in errors)

    def test_validate_naive_datetime(self):
        """Test validation handles naive datetime."""
        # Naive datetime (no timezone)
        scheduled_at = datetime.now() + timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
        )

        errors = request.validate()
        # Should add timezone and validate
        assert request.scheduled_at.tzinfo is not None

    def test_validate_exactly_30_days(self):
        """Test validation at exactly 30 days boundary."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(days=30, minutes=-1)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
        )

        errors = request.validate()
        # Should be valid at just under 30 days
        assert not any("30 days" in e for e in errors)

    def test_validate_exactly_5_minutes(self):
        """Test validation at exactly 5 minutes boundary."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=6)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
        )

        errors = request.validate()
        # Should be valid at just over 5 minutes
        assert not any("5 minutes" in e for e in errors)


# =============================================================================
# ScheduledJob Tests
# =============================================================================


class TestScheduledJob:
    """Tests for ScheduledJob dataclass."""

    @pytest.fixture
    def sample_job(self):
        """Create a sample scheduled job."""
        now = datetime.now(timezone.utc)
        return ScheduledJob(
            schedule_id="sched-123",
            organization_id="org-001",
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=now + timedelta(hours=1),
            created_at=now,
            created_by="user-001",
            status=ScheduleStatus.PENDING,
            priority=Priority.HIGH,
            repository_id="repo-123",
            parameters={"branch": "main"},
            notify_on_completion=True,
            description="Security scan",
        )

    def test_create_from_request(self):
        """Test creating ScheduledJob from request."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.CODE_REVIEW,
            scheduled_at=scheduled_at,
            repository_id="repo-456",
            priority=Priority.CRITICAL,
            parameters={"pr_number": 42},
            notify_on_completion=True,
            description="Review PR",
        )

        job = ScheduledJob.create(
            organization_id="org-001",
            request=request,
            created_by="user-001",
        )

        assert job.schedule_id is not None
        assert job.organization_id == "org-001"
        assert job.job_type == JobType.CODE_REVIEW
        assert job.status == ScheduleStatus.PENDING
        assert job.priority == Priority.CRITICAL
        assert job.repository_id == "repo-456"
        assert job.created_by == "user-001"

    def test_to_dynamodb_item_basic(self, sample_job):
        """Test DynamoDB item conversion."""
        item = sample_job.to_dynamodb_item()

        assert item["schedule_id"] == "sched-123"
        assert item["organization_id"] == "org-001"
        assert item["job_type"] == "SECURITY_SCAN"
        assert item["status"] == "PENDING"
        assert item["priority"] == "HIGH"
        assert "scheduled_at" in item
        assert "created_at" in item
        assert "ttl" in item

    def test_to_dynamodb_item_optional_fields(self, sample_job):
        """Test DynamoDB item includes optional fields."""
        item = sample_job.to_dynamodb_item()

        assert item["repository_id"] == "repo-123"
        assert item["parameters"] == {"branch": "main"}
        assert item["description"] == "Security scan"

    def test_to_dynamodb_item_dispatched_fields(self, sample_job):
        """Test DynamoDB item includes dispatched fields."""
        sample_job.dispatched_at = datetime.now(timezone.utc)
        sample_job.dispatched_job_id = "job-456"

        item = sample_job.to_dynamodb_item()

        assert "dispatched_at" in item
        assert item["dispatched_job_id"] == "job-456"

    def test_to_dynamodb_item_cancelled_fields(self, sample_job):
        """Test DynamoDB item includes cancelled fields."""
        sample_job.cancelled_at = datetime.now(timezone.utc)
        sample_job.cancelled_by = "admin-001"

        item = sample_job.to_dynamodb_item()

        assert "cancelled_at" in item
        assert item["cancelled_by"] == "admin-001"

    def test_to_dynamodb_item_error_message(self, sample_job):
        """Test DynamoDB item includes error message."""
        sample_job.error_message = "Failed to dispatch"

        item = sample_job.to_dynamodb_item()

        assert item["error_message"] == "Failed to dispatch"

    def test_to_dynamodb_item_ttl_calculation(self, sample_job):
        """Test TTL is 30 days after scheduled time."""
        item = sample_job.to_dynamodb_item()

        expected_ttl = sample_job.scheduled_at + timedelta(days=30)
        assert item["ttl"] == int(expected_ttl.timestamp())

    def test_from_dynamodb_item(self):
        """Test creating ScheduledJob from DynamoDB item."""
        now = datetime.now(timezone.utc)
        item = {
            "schedule_id": "sched-789",
            "organization_id": "org-002",
            "job_type": "CODE_REVIEW",
            "scheduled_at": (now + timedelta(hours=2)).isoformat(),
            "created_at": now.isoformat(),
            "created_by": "user-002",
            "status": "DISPATCHED",
            "priority": "HIGH",
            "repository_id": "repo-789",
            "parameters": {"pr": 123},
            "notify_on_completion": True,
            "description": "PR review",
            "dispatched_at": now.isoformat(),
            "dispatched_job_id": "job-999",
        }

        job = ScheduledJob.from_dynamodb_item(item)

        assert job.schedule_id == "sched-789"
        assert job.organization_id == "org-002"
        assert job.job_type == JobType.CODE_REVIEW
        assert job.status == ScheduleStatus.DISPATCHED
        assert job.priority == Priority.HIGH
        assert job.dispatched_job_id == "job-999"

    def test_from_dynamodb_item_z_timezone(self):
        """Test parsing datetime with Z timezone suffix."""
        item = {
            "schedule_id": "sched-123",
            "organization_id": "org-001",
            "job_type": "SECURITY_SCAN",
            "scheduled_at": "2025-01-15T10:00:00Z",
            "created_at": "2025-01-15T09:00:00Z",
            "created_by": "user-001",
            "status": "PENDING",
        }

        job = ScheduledJob.from_dynamodb_item(item)

        assert job.scheduled_at.tzinfo is not None

    def test_from_dynamodb_item_defaults(self):
        """Test from_dynamodb_item uses defaults for missing fields."""
        item = {
            "schedule_id": "sched-123",
            "organization_id": "org-001",
            "job_type": "SECURITY_SCAN",
            "scheduled_at": "2025-01-15T10:00:00+00:00",
            "created_at": "2025-01-15T09:00:00+00:00",
            "created_by": "user-001",
            "status": "PENDING",
        }

        job = ScheduledJob.from_dynamodb_item(item)

        assert job.priority == Priority.NORMAL
        assert job.parameters == {}
        assert job.notify_on_completion is True
        assert job.dispatched_at is None

    def test_to_dict(self, sample_job):
        """Test dictionary conversion for API responses."""
        data = sample_job.to_dict()

        assert data["schedule_id"] == "sched-123"
        assert data["organization_id"] == "org-001"
        assert data["job_type"] == "SECURITY_SCAN"
        assert data["status"] == "PENDING"
        assert data["priority"] == "HIGH"
        assert data["repository_id"] == "repo-123"

    def test_to_dict_optional_datetime_fields(self, sample_job):
        """Test to_dict includes optional datetime fields."""
        sample_job.dispatched_at = datetime.now(timezone.utc)
        sample_job.cancelled_at = datetime.now(timezone.utc)

        data = sample_job.to_dict()

        assert "dispatched_at" in data
        assert "cancelled_at" in data

    def test_to_dict_with_string_enums(self):
        """Test to_dict handles string values for enums."""
        now = datetime.now(timezone.utc)
        job = ScheduledJob(
            schedule_id="sched-123",
            organization_id="org-001",
            job_type="SECURITY_SCAN",  # String instead of enum
            scheduled_at=now + timedelta(hours=1),
            created_at=now,
            created_by="user-001",
            status="PENDING",  # String instead of enum
            priority="HIGH",  # String instead of enum
        )

        data = job.to_dict()

        assert data["job_type"] == "SECURITY_SCAN"
        assert data["status"] == "PENDING"
        assert data["priority"] == "HIGH"


# =============================================================================
# QueueStatus Tests
# =============================================================================


class TestQueueStatus:
    """Tests for QueueStatus dataclass."""

    def test_create_queue_status_basic(self):
        """Test basic QueueStatus creation."""
        status = QueueStatus(
            total_queued=10,
            total_scheduled=5,
            active_jobs=3,
            by_priority={"CRITICAL": 2, "HIGH": 3, "NORMAL": 5},
            by_type={"SECURITY_SCAN": 4, "CODE_REVIEW": 6},
            avg_wait_time_seconds=120.5,
            throughput_per_hour=15.0,
        )

        assert status.total_queued == 10
        assert status.total_scheduled == 5
        assert status.active_jobs == 3
        assert status.avg_wait_time_seconds == 120.5
        assert status.throughput_per_hour == 15.0

    def test_create_queue_status_with_optional_fields(self):
        """Test QueueStatus with optional datetime fields."""
        now = datetime.now(timezone.utc)
        status = QueueStatus(
            total_queued=10,
            total_scheduled=5,
            active_jobs=3,
            by_priority={},
            by_type={},
            avg_wait_time_seconds=0,
            throughput_per_hour=0,
            oldest_queued_at=now - timedelta(hours=2),
            next_scheduled_at=now + timedelta(hours=1),
        )

        assert status.oldest_queued_at is not None
        assert status.next_scheduled_at is not None

    def test_to_dict_basic(self):
        """Test QueueStatus to_dict conversion."""
        status = QueueStatus(
            total_queued=10,
            total_scheduled=5,
            active_jobs=3,
            by_priority={"HIGH": 3},
            by_type={"SECURITY_SCAN": 4},
            avg_wait_time_seconds=100.0,
            throughput_per_hour=20.0,
        )

        data = status.to_dict()

        assert data["total_queued"] == 10
        assert data["total_scheduled"] == 5
        assert data["active_jobs"] == 3
        assert data["by_priority"] == {"HIGH": 3}
        assert data["by_type"] == {"SECURITY_SCAN": 4}
        assert data["avg_wait_time_seconds"] == 100.0
        assert data["throughput_per_hour"] == 20.0
        assert data["oldest_queued_at"] is None
        assert data["next_scheduled_at"] is None

    def test_to_dict_with_datetimes(self):
        """Test QueueStatus to_dict with datetime fields."""
        now = datetime.now(timezone.utc)
        oldest = now - timedelta(hours=2)
        next_sched = now + timedelta(hours=1)

        status = QueueStatus(
            total_queued=10,
            total_scheduled=5,
            active_jobs=3,
            by_priority={},
            by_type={},
            avg_wait_time_seconds=0,
            throughput_per_hour=0,
            oldest_queued_at=oldest,
            next_scheduled_at=next_sched,
        )

        data = status.to_dict()

        assert data["oldest_queued_at"] == oldest.isoformat()
        assert data["next_scheduled_at"] == next_sched.isoformat()


# =============================================================================
# TimelineEntry Tests
# =============================================================================


class TestTimelineEntry:
    """Tests for TimelineEntry dataclass."""

    def test_create_timeline_entry_basic(self):
        """Test basic TimelineEntry creation."""
        entry = TimelineEntry(
            job_id="job-123",
            job_type="SECURITY_SCAN",
            status="COMPLETED",
            title="Security Scan",
        )

        assert entry.job_id == "job-123"
        assert entry.job_type == "SECURITY_SCAN"
        assert entry.status == "COMPLETED"
        assert entry.title == "Security Scan"

    def test_create_timeline_entry_with_all_fields(self):
        """Test TimelineEntry with all fields."""
        now = datetime.now(timezone.utc)
        entry = TimelineEntry(
            job_id="job-456",
            job_type="CODE_REVIEW",
            status="RUNNING",
            title="Code Review",
            scheduled_at=now + timedelta(hours=1),
            started_at=now,
            completed_at=None,
            duration_seconds=300,
            repository_name="my-repo",
            created_by="user-001",
        )

        assert entry.job_id == "job-456"
        assert entry.scheduled_at is not None
        assert entry.started_at is not None
        assert entry.completed_at is None
        assert entry.duration_seconds == 300
        assert entry.repository_name == "my-repo"
        assert entry.created_by == "user-001"

    def test_to_dict_basic(self):
        """Test TimelineEntry to_dict conversion."""
        entry = TimelineEntry(
            job_id="job-123",
            job_type="SECURITY_SCAN",
            status="COMPLETED",
            title="Security Scan",
        )

        data = entry.to_dict()

        assert data["job_id"] == "job-123"
        assert data["job_type"] == "SECURITY_SCAN"
        assert data["status"] == "COMPLETED"
        assert data["title"] == "Security Scan"
        assert data["scheduled_at"] is None
        assert data["started_at"] is None
        assert data["completed_at"] is None

    def test_to_dict_with_datetimes(self):
        """Test TimelineEntry to_dict with datetime fields."""
        now = datetime.now(timezone.utc)
        scheduled = now - timedelta(hours=1)
        started = now - timedelta(minutes=30)
        completed = now

        entry = TimelineEntry(
            job_id="job-789",
            job_type="PATCH_GENERATION",
            status="COMPLETED",
            title="Patch Gen",
            scheduled_at=scheduled,
            started_at=started,
            completed_at=completed,
            duration_seconds=1800,
        )

        data = entry.to_dict()

        assert data["scheduled_at"] == scheduled.isoformat()
        assert data["started_at"] == started.isoformat()
        assert data["completed_at"] == completed.isoformat()
        assert data["duration_seconds"] == 1800


# =============================================================================
# RecurringTask Tests
# =============================================================================


class TestRecurringTask:
    """Tests for RecurringTask dataclass."""

    def test_create_recurring_task_basic(self):
        """Test basic RecurringTask creation."""
        task = RecurringTask(
            task_id="task-123",
            organization_id="org-001",
            job_type=JobType.SECURITY_SCAN,
            schedule=RecurringSchedule.DAILY,
        )

        assert task.task_id == "task-123"
        assert task.organization_id == "org-001"
        assert task.job_type == JobType.SECURITY_SCAN
        assert task.schedule == RecurringSchedule.DAILY
        assert task.enabled is True
        assert task.priority == Priority.NORMAL

    def test_create_recurring_task_with_cron(self):
        """Test RecurringTask with custom cron expression."""
        task = RecurringTask(
            task_id="task-456",
            organization_id="org-001",
            job_type=JobType.CODE_REVIEW,
            schedule=RecurringSchedule.CUSTOM,
            cron_expression="0 9 * * 1-5",
        )

        assert task.schedule == RecurringSchedule.CUSTOM
        assert task.cron_expression == "0 9 * * 1-5"

    def test_create_recurring_task_with_all_fields(self):
        """Test RecurringTask with all fields."""
        now = datetime.now(timezone.utc)
        task = RecurringTask(
            task_id="task-789",
            organization_id="org-001",
            job_type=JobType.COMPLIANCE_CHECK,
            schedule=RecurringSchedule.WEEKLY,
            cron_expression=None,
            repository_id="repo-123",
            priority=Priority.HIGH,
            parameters={"check_type": "full"},
            enabled=True,
            created_at=now,
            created_by="admin-001",
            last_run_at=now - timedelta(days=7),
            next_run_at=now + timedelta(days=7),
            description="Weekly compliance check",
        )

        assert task.repository_id == "repo-123"
        assert task.priority == Priority.HIGH
        assert task.parameters == {"check_type": "full"}
        assert task.created_by == "admin-001"
        assert task.description == "Weekly compliance check"

    def test_to_dict_basic(self):
        """Test RecurringTask to_dict conversion."""
        task = RecurringTask(
            task_id="task-123",
            organization_id="org-001",
            job_type=JobType.SECURITY_SCAN,
            schedule=RecurringSchedule.DAILY,
        )

        data = task.to_dict()

        assert data["task_id"] == "task-123"
        assert data["organization_id"] == "org-001"
        assert data["job_type"] == "SECURITY_SCAN"
        assert data["schedule"] == "DAILY"
        assert data["enabled"] is True
        assert data["priority"] == "NORMAL"

    def test_to_dict_with_datetimes(self):
        """Test RecurringTask to_dict with datetime fields."""
        now = datetime.now(timezone.utc)
        task = RecurringTask(
            task_id="task-456",
            organization_id="org-001",
            job_type=JobType.CODE_REVIEW,
            schedule=RecurringSchedule.WEEKLY,
            created_at=now,
            last_run_at=now - timedelta(days=7),
            next_run_at=now + timedelta(days=7),
        )

        data = task.to_dict()

        assert data["created_at"] == now.isoformat()
        assert data["last_run_at"] == (now - timedelta(days=7)).isoformat()
        assert data["next_run_at"] == (now + timedelta(days=7)).isoformat()

    def test_to_dict_with_string_enums(self):
        """Test RecurringTask to_dict handles string values for enums."""
        task = RecurringTask(
            task_id="task-789",
            organization_id="org-001",
            job_type="SECURITY_SCAN",  # String instead of enum
            schedule="DAILY",  # String instead of enum
            priority="HIGH",  # String instead of enum
        )

        data = task.to_dict()

        assert data["job_type"] == "SECURITY_SCAN"
        assert data["schedule"] == "DAILY"
        assert data["priority"] == "HIGH"

    def test_to_dict_none_datetimes(self):
        """Test RecurringTask to_dict with None datetime fields."""
        task = RecurringTask(
            task_id="task-123",
            organization_id="org-001",
            job_type=JobType.SECURITY_SCAN,
            schedule=RecurringSchedule.DAILY,
            created_at=None,
            last_run_at=None,
            next_run_at=None,
        )

        data = task.to_dict()

        assert data["created_at"] is None
        assert data["last_run_at"] is None
        assert data["next_run_at"] is None


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and integration scenarios."""

    def test_scheduled_job_roundtrip(self):
        """Test ScheduledJob can be serialized and deserialized."""
        now = datetime.now(timezone.utc)
        original = ScheduledJob(
            schedule_id="sched-roundtrip",
            organization_id="org-001",
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=now + timedelta(hours=1),
            created_at=now,
            created_by="user-001",
            status=ScheduleStatus.PENDING,
            priority=Priority.HIGH,
            repository_id="repo-123",
            parameters={"key": "value"},
            notify_on_completion=True,
            description="Test job",
        )

        # Convert to DynamoDB item and back
        item = original.to_dynamodb_item()
        restored = ScheduledJob.from_dynamodb_item(item)

        assert restored.schedule_id == original.schedule_id
        assert restored.organization_id == original.organization_id
        assert restored.job_type == original.job_type
        assert restored.status == original.status
        assert restored.priority == original.priority
        assert restored.repository_id == original.repository_id

    def test_schedule_job_request_empty_parameters(self):
        """Test ScheduleJobRequest with empty parameters."""
        scheduled_at = datetime.now(timezone.utc) + timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=scheduled_at,
            parameters={},
        )

        assert request.parameters == {}

    def test_queue_status_zero_values(self):
        """Test QueueStatus with all zero values."""
        status = QueueStatus(
            total_queued=0,
            total_scheduled=0,
            active_jobs=0,
            by_priority={},
            by_type={},
            avg_wait_time_seconds=0.0,
            throughput_per_hour=0.0,
        )

        data = status.to_dict()

        assert data["total_queued"] == 0
        assert data["avg_wait_time_seconds"] == 0.0

    def test_timeline_entry_zero_duration(self):
        """Test TimelineEntry with zero duration."""
        entry = TimelineEntry(
            job_id="job-123",
            job_type="SECURITY_SCAN",
            status="COMPLETED",
            title="Quick scan",
            duration_seconds=0,
        )

        data = entry.to_dict()

        assert data["duration_seconds"] == 0

    def test_recurring_task_disabled(self):
        """Test RecurringTask when disabled."""
        task = RecurringTask(
            task_id="task-disabled",
            organization_id="org-001",
            job_type=JobType.SECURITY_SCAN,
            schedule=RecurringSchedule.DAILY,
            enabled=False,
        )

        assert task.enabled is False

        data = task.to_dict()
        assert data["enabled"] is False
