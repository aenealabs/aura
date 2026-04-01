"""
Tests for Scheduling Service.

Tests DynamoDB-backed scheduling operations including:
- Job scheduling CRUD
- Queue status queries
- Timeline queries
- Job dispatching

ADR-055: Agent Scheduling View and Job Queue Management
"""

import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.scheduling.models import (
    JobType,
    Priority,
    QueueStatus,
    ScheduledJob,
    ScheduleJobRequest,
    ScheduleStatus,
    TimelineEntry,
)
from src.services.scheduling.scheduling_service import (
    ScheduleNotFoundError,
    ScheduleValidationError,
    SchedulingService,
    SchedulingServiceError,
    get_scheduling_service,
    set_scheduling_service,
)

# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service():
    """Create a scheduling service for testing."""
    return SchedulingService(
        table_name="test-scheduled-jobs",
        jobs_table_name="test-orchestrator-jobs",
    )


@pytest.fixture
def mock_dynamodb_table():
    """Create a mock DynamoDB table."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}
    mock_table.put_item.return_value = {}
    mock_table.query.return_value = {"Items": []}
    mock_table.update_item.return_value = {}
    return mock_table


@pytest.fixture
def mock_jobs_table():
    """Create a mock DynamoDB jobs table."""
    mock_table = MagicMock()
    mock_table.query.return_value = {"Items": [], "Count": 0}
    mock_table.scan.return_value = {"Items": []}
    mock_table.put_item.return_value = {}
    return mock_table


@pytest.fixture
def organization_id():
    """Test organization ID."""
    return "test-org-001"


@pytest.fixture
def user_id():
    """Test user ID."""
    return "test-user-001"


@pytest.fixture
def schedule_request():
    """Create a valid schedule request."""
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)
    return ScheduleJobRequest(
        job_type=JobType.SECURITY_SCAN,
        scheduled_at=future_time,
        priority=Priority.NORMAL,
        repository_id="repo-main",
        description="Test security scan",
    )


@pytest.fixture
def sample_scheduled_job(organization_id, user_id):
    """Create a sample scheduled job."""
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)
    return ScheduledJob(
        schedule_id="sched-test-001",
        organization_id=organization_id,
        job_type=JobType.SECURITY_SCAN,
        scheduled_at=future_time,
        created_at=datetime.now(timezone.utc),
        created_by=user_id,
        status=ScheduleStatus.PENDING,
        priority=Priority.NORMAL,
        repository_id="repo-main",
        description="Test security scan",
    )


# =============================================================================
# Service Initialization Tests
# =============================================================================


class TestServiceInitialization:
    """Test service initialization."""

    def test_default_initialization(self):
        """Test default initialization values."""
        service = SchedulingService()
        assert "aura-scheduled-jobs" in service.table_name
        assert "aura-orchestrator-jobs" in service.jobs_table_name
        assert service._table is None
        assert service._jobs_table is None
        assert service._dynamodb is None

    def test_custom_initialization(self, service):
        """Test custom initialization."""
        assert service.table_name == "test-scheduled-jobs"
        assert service.jobs_table_name == "test-orchestrator-jobs"

    def test_singleton_pattern(self):
        """Test get/set singleton functions."""
        original = get_scheduling_service()

        custom_service = SchedulingService(table_name="custom-table")
        set_scheduling_service(custom_service)

        assert get_scheduling_service() is custom_service

        # Reset to original
        set_scheduling_service(original)


# =============================================================================
# Schedule Job Tests
# =============================================================================


class TestScheduleJob:
    """Test job scheduling."""

    @pytest.mark.asyncio
    async def test_schedule_job_success(
        self, service, mock_dynamodb_table, organization_id, user_id, schedule_request
    ):
        """Test successful job scheduling."""
        service._table = mock_dynamodb_table

        result = await service.schedule_job(organization_id, schedule_request, user_id)

        assert result.organization_id == organization_id
        assert result.job_type == schedule_request.job_type
        assert result.status == ScheduleStatus.PENDING
        assert result.created_by == user_id
        assert result.repository_id == schedule_request.repository_id
        mock_dynamodb_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_job_validation_error(
        self, service, mock_dynamodb_table, organization_id, user_id
    ):
        """Test job scheduling with invalid request."""
        service._table = mock_dynamodb_table

        # Create invalid request with past time
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        invalid_request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=past_time,
        )

        with pytest.raises(ScheduleValidationError):
            await service.schedule_job(organization_id, invalid_request, user_id)

    @pytest.mark.asyncio
    async def test_schedule_job_dynamodb_error(
        self, service, mock_dynamodb_table, organization_id, user_id, schedule_request
    ):
        """Test job scheduling with DynamoDB error."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.put_item.side_effect = Exception("DynamoDB error")

        with pytest.raises(SchedulingServiceError):
            await service.schedule_job(organization_id, schedule_request, user_id)


# =============================================================================
# Get Scheduled Job Tests
# =============================================================================


class TestGetScheduledJob:
    """Test getting scheduled jobs."""

    @pytest.mark.asyncio
    async def test_get_scheduled_job_success(
        self, service, mock_dynamodb_table, organization_id, sample_scheduled_job
    ):
        """Test successful job retrieval."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }

        result = await service.get_scheduled_job(
            organization_id, sample_scheduled_job.schedule_id
        )

        assert result.schedule_id == sample_scheduled_job.schedule_id
        assert result.organization_id == organization_id
        assert result.job_type == sample_scheduled_job.job_type

    @pytest.mark.asyncio
    async def test_get_scheduled_job_not_found(
        self, service, mock_dynamodb_table, organization_id
    ):
        """Test job retrieval when not found."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {}

        with pytest.raises(ScheduleNotFoundError):
            await service.get_scheduled_job(organization_id, "nonexistent-id")

    @pytest.mark.asyncio
    async def test_get_scheduled_job_dynamodb_error(
        self, service, mock_dynamodb_table, organization_id
    ):
        """Test job retrieval with DynamoDB error."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.side_effect = Exception("DynamoDB error")

        with pytest.raises(SchedulingServiceError):
            await service.get_scheduled_job(organization_id, "test-id")


# =============================================================================
# List Scheduled Jobs Tests
# =============================================================================


class TestListScheduledJobs:
    """Test listing scheduled jobs."""

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_empty(
        self, service, mock_dynamodb_table, organization_id
    ):
        """Test listing when no jobs exist."""
        service._table = mock_dynamodb_table

        jobs, next_key = await service.list_scheduled_jobs(organization_id)

        assert jobs == []
        assert next_key is None

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_with_results(
        self, service, mock_dynamodb_table, organization_id, sample_scheduled_job
    ):
        """Test listing with results."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_scheduled_job.to_dynamodb_item()],
            "LastEvaluatedKey": None,
        }

        jobs, next_key = await service.list_scheduled_jobs(organization_id)

        assert len(jobs) == 1
        assert jobs[0].schedule_id == sample_scheduled_job.schedule_id

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_with_status_filter(
        self, service, mock_dynamodb_table, organization_id
    ):
        """Test listing with status filter."""
        service._table = mock_dynamodb_table

        jobs, next_key = await service.list_scheduled_jobs(
            organization_id, status=ScheduleStatus.PENDING
        )

        # Verify FilterExpression was used
        call_args = mock_dynamodb_table.query.call_args
        assert "FilterExpression" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_pagination(
        self, service, mock_dynamodb_table, organization_id, sample_scheduled_job
    ):
        """Test listing with pagination."""
        service._table = mock_dynamodb_table
        pagination_key = {
            "organization_id": organization_id,
            "schedule_id": "sched-001",
        }
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_scheduled_job.to_dynamodb_item()],
            "LastEvaluatedKey": pagination_key,
        }

        jobs, next_key = await service.list_scheduled_jobs(organization_id, limit=10)

        assert next_key == pagination_key


# =============================================================================
# Reschedule Job Tests
# =============================================================================


class TestRescheduleJob:
    """Test job rescheduling."""

    @pytest.mark.asyncio
    async def test_reschedule_job_success(
        self,
        service,
        mock_dynamodb_table,
        organization_id,
        user_id,
        sample_scheduled_job,
    ):
        """Test successful job rescheduling."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }

        new_time = datetime.now(timezone.utc) + timedelta(hours=5)
        result = await service.reschedule_job(
            organization_id, sample_scheduled_job.schedule_id, new_time, user_id
        )

        assert result.scheduled_at == new_time
        mock_dynamodb_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_reschedule_job_not_found(
        self, service, mock_dynamodb_table, organization_id, user_id
    ):
        """Test rescheduling non-existent job."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {}

        new_time = datetime.now(timezone.utc) + timedelta(hours=5)
        with pytest.raises(ScheduleNotFoundError):
            await service.reschedule_job(
                organization_id, "nonexistent-id", new_time, user_id
            )

    @pytest.mark.asyncio
    async def test_reschedule_job_past_time(
        self,
        service,
        mock_dynamodb_table,
        organization_id,
        user_id,
        sample_scheduled_job,
    ):
        """Test rescheduling to past time."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }

        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        with pytest.raises(ScheduleValidationError):
            await service.reschedule_job(
                organization_id, sample_scheduled_job.schedule_id, past_time, user_id
            )

    @pytest.mark.asyncio
    async def test_reschedule_job_non_pending_status(
        self,
        service,
        mock_dynamodb_table,
        organization_id,
        user_id,
        sample_scheduled_job,
    ):
        """Test rescheduling job that is not pending."""
        service._table = mock_dynamodb_table
        sample_scheduled_job.status = ScheduleStatus.DISPATCHED
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }

        new_time = datetime.now(timezone.utc) + timedelta(hours=5)
        with pytest.raises(ScheduleValidationError):
            await service.reschedule_job(
                organization_id, sample_scheduled_job.schedule_id, new_time, user_id
            )


# =============================================================================
# Cancel Job Tests
# =============================================================================


class TestCancelJob:
    """Test job cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_job_success(
        self,
        service,
        mock_dynamodb_table,
        organization_id,
        user_id,
        sample_scheduled_job,
    ):
        """Test successful job cancellation."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }

        result = await service.cancel_scheduled_job(
            organization_id, sample_scheduled_job.schedule_id, user_id
        )

        assert result.status == ScheduleStatus.CANCELLED
        assert result.cancelled_by == user_id
        assert result.cancelled_at is not None
        mock_dynamodb_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(
        self, service, mock_dynamodb_table, organization_id, user_id
    ):
        """Test cancelling non-existent job."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {}

        with pytest.raises(ScheduleNotFoundError):
            await service.cancel_scheduled_job(
                organization_id, "nonexistent-id", user_id
            )

    @pytest.mark.asyncio
    async def test_cancel_job_non_pending_status(
        self,
        service,
        mock_dynamodb_table,
        organization_id,
        user_id,
        sample_scheduled_job,
    ):
        """Test cancelling job that is not pending."""
        service._table = mock_dynamodb_table
        sample_scheduled_job.status = ScheduleStatus.DISPATCHED
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }

        with pytest.raises(ScheduleValidationError):
            await service.cancel_scheduled_job(
                organization_id, sample_scheduled_job.schedule_id, user_id
            )


# =============================================================================
# Queue Status Tests
# =============================================================================


class TestQueueStatus:
    """Test queue status queries."""

    @pytest.mark.asyncio
    async def test_get_queue_status_empty(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test queue status when empty."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Mock all the queries that get_queue_status makes
        mock_jobs_table.query.side_effect = [
            {"Items": [], "Count": 0},  # Queued jobs
            {"Items": [], "Count": 0},  # Active jobs
        ]
        mock_dynamodb_table.query.return_value = {"Items": [], "Count": 0}

        status = await service.get_queue_status(organization_id)

        assert isinstance(status, QueueStatus)
        assert status.total_queued == 0
        assert status.active_jobs == 0

    @pytest.mark.asyncio
    async def test_get_queue_status_with_jobs(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test queue status with active jobs."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Mock queued and running jobs (scan is used, not query)
        all_jobs = [
            {
                "job_id": f"job-{i}",
                "status": "QUEUED",
                "priority": "NORMAL",
                "job_type": "SECURITY_SCAN",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(5)
        ] + [
            {
                "job_id": f"active-{i}",
                "status": "RUNNING",
                "priority": "HIGH",
                "job_type": "CODE_REVIEW",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(2)
        ]

        # Mock scan for jobs table
        mock_jobs_table.scan.return_value = {"Items": all_jobs}

        # Mock query for scheduled jobs (list_pending_jobs uses query)
        mock_dynamodb_table.query.return_value = {"Items": []}

        status = await service.get_queue_status(organization_id)

        assert status.total_queued == 5
        assert status.active_jobs == 2


# =============================================================================
# Timeline Tests
# =============================================================================


class TestTimeline:
    """Test timeline queries."""

    @pytest.mark.asyncio
    async def test_get_timeline_empty(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test timeline when empty."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table
        mock_dynamodb_table.query.return_value = {"Items": []}
        mock_jobs_table.query.return_value = {"Items": []}

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc) + timedelta(days=7)

        entries = await service.get_timeline(
            organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(entries, list)
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_get_timeline_with_entries(
        self,
        service,
        mock_dynamodb_table,
        mock_jobs_table,
        organization_id,
        sample_scheduled_job,
    ):
        """Test timeline with scheduled and completed jobs."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Mock scheduled jobs
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_scheduled_job.to_dynamodb_item()]
        }

        # Mock completed jobs
        completed_job = {
            "job_id": "completed-001",
            "job_type": "SECURITY_SCAN",
            "status": "SUCCEEDED",
            "started_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "repository_id": "repo-main",
        }
        mock_jobs_table.query.return_value = {"Items": [completed_job]}

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc) + timedelta(days=7)

        entries = await service.get_timeline(
            organization_id,
            start_date=start_date,
            end_date=end_date,
            include_scheduled=True,
            include_completed=True,
        )

        assert len(entries) >= 1


# =============================================================================
# List Pending Jobs Tests
# =============================================================================


class TestListPendingJobs:
    """Test listing pending jobs."""

    @pytest.mark.asyncio
    async def test_list_pending_jobs_empty(self, service, mock_dynamodb_table):
        """Test listing pending jobs when none exist."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {"Items": []}

        jobs = await service.list_pending_jobs()

        assert jobs == []

    @pytest.mark.asyncio
    async def test_list_pending_jobs_with_before_filter(
        self, service, mock_dynamodb_table, sample_scheduled_job
    ):
        """Test listing pending jobs with time filter."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_scheduled_job.to_dynamodb_item()]
        }

        before_time = datetime.now(timezone.utc) + timedelta(hours=3)
        jobs = await service.list_pending_jobs(before=before_time)

        assert len(jobs) == 1


# =============================================================================
# Dispatch Due Jobs Tests
# =============================================================================


class TestDispatchDueJobs:
    """Test job dispatching."""

    @pytest.mark.asyncio
    async def test_dispatch_due_jobs_empty(
        self, service, mock_dynamodb_table, mock_jobs_table
    ):
        """Test dispatching when no jobs are due."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table
        mock_dynamodb_table.query.return_value = {"Items": []}

        dispatched_ids = await service.dispatch_due_jobs()

        assert isinstance(dispatched_ids, list)
        assert len(dispatched_ids) == 0

    @pytest.mark.asyncio
    async def test_dispatch_due_jobs_success(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test successful job dispatching."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Create a due job (scheduled in the past)
        past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        due_job = ScheduledJob(
            schedule_id="sched-due-001",
            organization_id=organization_id,
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=past_time,
            created_at=past_time - timedelta(hours=1),
            created_by="test-user",
            status=ScheduleStatus.PENDING,
            priority=Priority.NORMAL,
        )

        mock_dynamodb_table.query.return_value = {"Items": [due_job.to_dynamodb_item()]}

        # Mock the _dispatch_job method to avoid importing orchestration_service
        async def mock_dispatch_job(job):
            return f"dispatched-{job.schedule_id}"

        with patch.object(service, "_dispatch_job", side_effect=mock_dispatch_job):
            dispatched_ids = await service.dispatch_due_jobs()

        assert len(dispatched_ids) == 1
        assert "sched-due-001" in dispatched_ids
        mock_dynamodb_table.update_item.assert_called_once()


# =============================================================================
# Model Tests
# =============================================================================


class TestScheduleJobRequest:
    """Test ScheduleJobRequest model."""

    def test_valid_request(self):
        """Test valid schedule request."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=future_time,
            priority=Priority.HIGH,
        )

        errors = request.validate()
        assert len(errors) == 0

    def test_invalid_past_time(self):
        """Test request with past scheduled time."""
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        request = ScheduleJobRequest(
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=past_time,
        )

        errors = request.validate()
        assert len(errors) > 0
        assert any("past" in e.lower() or "future" in e.lower() for e in errors)


class TestScheduledJob:
    """Test ScheduledJob model."""

    def test_to_dynamodb_item(self, sample_scheduled_job):
        """Test DynamoDB serialization."""
        item = sample_scheduled_job.to_dynamodb_item()

        assert item["schedule_id"] == sample_scheduled_job.schedule_id
        assert item["organization_id"] == sample_scheduled_job.organization_id
        assert item["job_type"] == sample_scheduled_job.job_type.value
        assert item["status"] == sample_scheduled_job.status.value

    def test_from_dynamodb_item(self, sample_scheduled_job):
        """Test DynamoDB deserialization."""
        item = sample_scheduled_job.to_dynamodb_item()
        restored = ScheduledJob.from_dynamodb_item(item)

        assert restored.schedule_id == sample_scheduled_job.schedule_id
        assert restored.organization_id == sample_scheduled_job.organization_id
        assert restored.job_type == sample_scheduled_job.job_type
        assert restored.status == sample_scheduled_job.status

    def test_create_from_request(self, organization_id, user_id, schedule_request):
        """Test creating ScheduledJob from request."""
        job = ScheduledJob.create(
            organization_id=organization_id,
            request=schedule_request,
            created_by=user_id,
        )

        assert job.organization_id == organization_id
        assert job.job_type == schedule_request.job_type
        assert job.priority == schedule_request.priority
        assert job.created_by == user_id
        assert job.status == ScheduleStatus.PENDING
        assert job.schedule_id is not None


class TestQueueStatusModel:
    """Test QueueStatus model."""

    def test_empty_queue_status(self):
        """Test empty queue status."""
        status = QueueStatus(
            total_queued=0,
            total_scheduled=0,
            active_jobs=0,
            by_priority={},
            by_type={},
            avg_wait_time_seconds=0.0,
            throughput_per_hour=0.0,
        )

        assert status.total_queued == 0
        assert status.avg_wait_time_seconds == 0.0

    def test_queue_status_with_data(self):
        """Test queue status with data."""
        status = QueueStatus(
            total_queued=10,
            total_scheduled=5,
            active_jobs=3,
            by_priority={"CRITICAL": 2, "HIGH": 4, "NORMAL": 4},
            by_type={"SECURITY_SCAN": 6, "CODE_REVIEW": 4},
            avg_wait_time_seconds=45.5,
            throughput_per_hour=24.0,
            oldest_queued_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            next_scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert status.total_queued == 10
        assert status.avg_wait_time_seconds == 45.5
        assert status.by_priority["CRITICAL"] == 2


class TestTimelineEntry:
    """Test TimelineEntry model."""

    def test_timeline_entry_scheduled(self):
        """Test timeline entry for scheduled job."""
        entry = TimelineEntry(
            job_id="sched-001",
            job_type=JobType.SECURITY_SCAN,
            status=ScheduleStatus.PENDING,
            title="Scheduled security scan",
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert entry.status == ScheduleStatus.PENDING
        assert entry.scheduled_at is not None
        assert entry.completed_at is None

    def test_timeline_entry_completed(self):
        """Test timeline entry for completed job."""
        started = datetime.now(timezone.utc) - timedelta(minutes=10)
        completed = datetime.now(timezone.utc)

        entry = TimelineEntry(
            job_id="job-001",
            job_type=JobType.CODE_REVIEW,
            status=ScheduleStatus.DISPATCHED,
            title="Completed code review",
            started_at=started,
            completed_at=completed,
            duration_seconds=600,
        )

        assert entry.completed_at is not None
        assert entry.duration_seconds == 600


# =============================================================================
# Enum Tests
# =============================================================================


class TestEnums:
    """Test enum values."""

    def test_job_type_values(self):
        """Test JobType enum values."""
        assert JobType.SECURITY_SCAN.value == "SECURITY_SCAN"
        assert JobType.CODE_REVIEW.value == "CODE_REVIEW"
        assert JobType.PATCH_GENERATION.value == "PATCH_GENERATION"

    def test_priority_values(self):
        """Test Priority enum values."""
        assert Priority.CRITICAL.value == "CRITICAL"
        assert Priority.HIGH.value == "HIGH"
        assert Priority.NORMAL.value == "NORMAL"
        assert Priority.LOW.value == "LOW"

    def test_schedule_status_values(self):
        """Test ScheduleStatus enum values."""
        assert ScheduleStatus.PENDING.value == "PENDING"
        assert ScheduleStatus.DISPATCHED.value == "DISPATCHED"
        assert ScheduleStatus.CANCELLED.value == "CANCELLED"
        assert ScheduleStatus.FAILED.value == "FAILED"


# =============================================================================
# Extended Coverage Tests - dispatch_due_jobs Error Paths
# =============================================================================


class TestDispatchDueJobsExtended:
    """Extended tests for dispatch_due_jobs error handling."""

    @pytest.mark.asyncio
    async def test_dispatch_due_jobs_individual_job_failure(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test that individual job failures are handled gracefully."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Create two due jobs
        past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        due_jobs = [
            ScheduledJob(
                schedule_id=f"sched-due-{i}",
                organization_id=organization_id,
                job_type=JobType.SECURITY_SCAN,
                scheduled_at=past_time,
                created_at=past_time - timedelta(hours=1),
                created_by="test-user",
                status=ScheduleStatus.PENDING,
                priority=Priority.NORMAL,
            )
            for i in range(2)
        ]

        mock_dynamodb_table.query.return_value = {
            "Items": [job.to_dynamodb_item() for job in due_jobs]
        }

        # Mock _dispatch_job to fail on first job, succeed on second
        call_count = 0

        async def mock_dispatch_job(job):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Dispatch failed")
            return f"dispatched-{job.schedule_id}"

        with patch.object(service, "_dispatch_job", side_effect=mock_dispatch_job):
            dispatched_ids = await service.dispatch_due_jobs()

        # Only second job should be dispatched
        assert len(dispatched_ids) == 1
        assert "sched-due-1" in dispatched_ids
        # Should have called update_item twice (once for fail, once for success)
        assert mock_dynamodb_table.update_item.call_count == 2

    @pytest.mark.asyncio
    async def test_dispatch_due_jobs_list_pending_failure(
        self, service, mock_dynamodb_table, mock_jobs_table
    ):
        """Test dispatch_due_jobs when list_pending_jobs fails."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        mock_dynamodb_table.query.side_effect = Exception("DynamoDB error")

        # Should not raise, just return empty list
        dispatched_ids = await service.dispatch_due_jobs()
        assert dispatched_ids == []


# =============================================================================
# Extended Coverage Tests - get_queue_status
# =============================================================================


class TestGetQueueStatusExtended:
    """Extended tests for get_queue_status."""

    @pytest.mark.asyncio
    async def test_get_queue_status_with_dispatched_jobs(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test queue status counting DISPATCHED as queued."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Jobs with DISPATCHED status should be counted as queued
        jobs_data = [
            {
                "job_id": "job-1",
                "status": "DISPATCHED",
                "priority": "HIGH",
                "job_type": "SECURITY_SCAN",
                "created_at": (
                    datetime.now(timezone.utc) - timedelta(minutes=10)
                ).isoformat(),
            },
            {
                "job_id": "job-2",
                "status": "QUEUED",
                "priority": "NORMAL",
                "job_type": "CODE_REVIEW",
                "created_at": (
                    datetime.now(timezone.utc) - timedelta(minutes=5)
                ).isoformat(),
            },
        ]

        mock_jobs_table.scan.return_value = {"Items": jobs_data}
        mock_dynamodb_table.query.return_value = {"Items": []}

        status = await service.get_queue_status(organization_id)

        assert status.total_queued == 2
        assert status.by_priority["HIGH"] == 1
        assert status.by_priority["NORMAL"] == 1
        assert status.by_type["SECURITY_SCAN"] == 1
        assert status.by_type["CODE_REVIEW"] == 1

    @pytest.mark.asyncio
    async def test_get_queue_status_oldest_queued_calculation(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test oldest_queued_at calculation."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        oldest_time = datetime.now(timezone.utc) - timedelta(hours=2)
        newer_time = datetime.now(timezone.utc) - timedelta(minutes=30)

        jobs_data = [
            {
                "job_id": "job-1",
                "status": "QUEUED",
                "priority": "NORMAL",
                "job_type": "SECURITY_SCAN",
                "created_at": oldest_time.isoformat(),
            },
            {
                "job_id": "job-2",
                "status": "QUEUED",
                "priority": "NORMAL",
                "job_type": "CODE_REVIEW",
                "created_at": newer_time.isoformat(),
            },
        ]

        mock_jobs_table.scan.return_value = {"Items": jobs_data}
        mock_dynamodb_table.query.return_value = {"Items": []}

        status = await service.get_queue_status(organization_id)

        assert status.oldest_queued_at is not None
        # The oldest should be approximately 2 hours ago
        time_diff = (
            datetime.now(timezone.utc) - status.oldest_queued_at
        ).total_seconds()
        assert 7100 < time_diff < 7300  # ~2 hours in seconds

    @pytest.mark.asyncio
    async def test_get_queue_status_avg_wait_time(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test average wait time calculation."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        oldest_time = datetime.now(timezone.utc) - timedelta(minutes=60)

        jobs_data = [
            {
                "job_id": "job-1",
                "status": "QUEUED",
                "priority": "NORMAL",
                "job_type": "SECURITY_SCAN",
                "created_at": oldest_time.isoformat(),
            },
        ]

        mock_jobs_table.scan.return_value = {"Items": jobs_data}
        mock_dynamodb_table.query.return_value = {"Items": []}

        status = await service.get_queue_status(organization_id)

        # avg_wait should be roughly 60 minutes in seconds
        assert status.avg_wait_time_seconds > 3500  # > 58 mins
        assert status.avg_wait_time_seconds < 3700  # < 62 mins

    @pytest.mark.asyncio
    async def test_get_queue_status_jobs_table_error(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test queue status when jobs table query fails."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Make jobs table scan fail
        mock_jobs_table.scan.side_effect = Exception("Jobs table error")
        mock_dynamodb_table.query.return_value = {"Items": []}

        # Should still return status (with zeros for jobs table data)
        status = await service.get_queue_status(organization_id)

        assert status.total_queued == 0
        assert status.active_jobs == 0

    @pytest.mark.asyncio
    async def test_get_queue_status_general_error(
        self, service, mock_dynamodb_table, mock_jobs_table
    ):
        """Test queue status with general error."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Make list_pending_jobs fail
        mock_dynamodb_table.query.side_effect = Exception("General error")

        with pytest.raises(SchedulingServiceError):
            await service.get_queue_status()

    @pytest.mark.asyncio
    async def test_get_queue_status_without_organization_filter(
        self, service, mock_dynamodb_table, mock_jobs_table
    ):
        """Test queue status without organization filter."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        mock_jobs_table.scan.return_value = {"Items": []}
        mock_dynamodb_table.query.return_value = {"Items": []}

        # Call without organization_id
        status = await service.get_queue_status()

        assert isinstance(status, QueueStatus)

    @pytest.mark.asyncio
    async def test_get_queue_status_next_scheduled(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test next_scheduled_at is set from pending jobs."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        pending_job = ScheduledJob(
            schedule_id="sched-001",
            organization_id=organization_id,
            job_type=JobType.SECURITY_SCAN,
            scheduled_at=future_time,
            created_at=datetime.now(timezone.utc),
            created_by="test-user",
            status=ScheduleStatus.PENDING,
            priority=Priority.NORMAL,
        )

        mock_dynamodb_table.query.return_value = {
            "Items": [pending_job.to_dynamodb_item()]
        }
        mock_jobs_table.scan.return_value = {"Items": []}

        status = await service.get_queue_status(organization_id)

        assert status.next_scheduled_at is not None
        assert status.total_scheduled == 1


# =============================================================================
# Extended Coverage Tests - get_timeline
# =============================================================================


class TestGetTimelineExtended:
    """Extended tests for get_timeline."""

    @pytest.mark.asyncio
    async def test_get_timeline_scheduled_only(
        self,
        service,
        mock_dynamodb_table,
        mock_jobs_table,
        organization_id,
        sample_scheduled_job,
    ):
        """Test timeline with only scheduled jobs (no completed)."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        mock_dynamodb_table.query.return_value = {
            "Items": [sample_scheduled_job.to_dynamodb_item()]
        }

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc) + timedelta(days=7)

        entries = await service.get_timeline(
            organization_id,
            start_date=start_date,
            end_date=end_date,
            include_scheduled=True,
            include_completed=False,  # Don't include completed
        )

        # Should have scheduled entry
        assert len(entries) >= 1
        # jobs_table.scan should not be called
        mock_jobs_table.scan.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_timeline_completed_only(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test timeline with only completed jobs (no scheduled)."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        completed_job = {
            "job_id": "completed-001",
            "job_type": "SECURITY_SCAN",
            "status": "SUCCEEDED",
            "organization_id": organization_id,
            "started_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_jobs_table.scan.return_value = {"Items": [completed_job]}

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc) + timedelta(days=7)

        entries = await service.get_timeline(
            organization_id,
            start_date=start_date,
            end_date=end_date,
            include_scheduled=False,  # Don't include scheduled
            include_completed=True,
        )

        # Should have completed entry
        assert len(entries) == 1
        # scheduled jobs query should still be called (for list_scheduled_jobs)
        # but entries from it should be excluded

    @pytest.mark.asyncio
    async def test_get_timeline_job_outside_date_range(
        self,
        service,
        mock_dynamodb_table,
        mock_jobs_table,
        organization_id,
        sample_scheduled_job,
    ):
        """Test timeline excludes jobs outside date range."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Job scheduled far in the future
        sample_scheduled_job.scheduled_at = datetime.now(timezone.utc) + timedelta(
            days=30
        )
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_scheduled_job.to_dynamodb_item()]
        }
        mock_jobs_table.scan.return_value = {"Items": []}

        # Query for only next 7 days
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc) + timedelta(days=7)

        entries = await service.get_timeline(
            organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Job should be excluded (outside range)
        assert len(entries) == 0

    @pytest.mark.asyncio
    async def test_get_timeline_completed_jobs_scan_error(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test timeline when completed jobs scan fails."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        mock_dynamodb_table.query.return_value = {"Items": []}
        mock_jobs_table.scan.side_effect = Exception("Scan error")

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc) + timedelta(days=7)

        # Should not raise, just return empty or partial results
        entries = await service.get_timeline(
            organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert isinstance(entries, list)

    @pytest.mark.asyncio
    async def test_get_timeline_sorting(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test timeline entries are sorted by time."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Create jobs with different times
        job1_time = datetime.now(timezone.utc) + timedelta(hours=3)
        job2_time = datetime.now(timezone.utc) + timedelta(hours=1)
        job3_time = datetime.now(timezone.utc) + timedelta(hours=2)

        scheduled_jobs = [
            ScheduledJob(
                schedule_id=f"sched-{i}",
                organization_id=organization_id,
                job_type=JobType.SECURITY_SCAN,
                scheduled_at=t,
                created_at=datetime.now(timezone.utc),
                created_by="test-user",
                status=ScheduleStatus.PENDING,
                priority=Priority.NORMAL,
            )
            for i, t in enumerate([job1_time, job2_time, job3_time])
        ]

        mock_dynamodb_table.query.return_value = {
            "Items": [job.to_dynamodb_item() for job in scheduled_jobs]
        }
        mock_jobs_table.scan.return_value = {"Items": []}

        start_date = datetime.now(timezone.utc)
        end_date = datetime.now(timezone.utc) + timedelta(days=7)

        entries = await service.get_timeline(
            organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Should be sorted: job2 (1h), job3 (2h), job1 (3h)
        assert len(entries) == 3
        assert entries[0].job_id == "sched-1"  # 1 hour
        assert entries[1].job_id == "sched-2"  # 2 hours
        assert entries[2].job_id == "sched-0"  # 3 hours

    @pytest.mark.asyncio
    async def test_get_timeline_general_error(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test timeline with general error."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        # Make list_scheduled_jobs fail
        mock_dynamodb_table.query.side_effect = Exception("General error")

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc) + timedelta(days=7)

        with pytest.raises(SchedulingServiceError):
            await service.get_timeline(
                organization_id,
                start_date=start_date,
                end_date=end_date,
            )

    @pytest.mark.asyncio
    async def test_get_timeline_running_job(
        self, service, mock_dynamodb_table, mock_jobs_table, organization_id
    ):
        """Test timeline includes RUNNING jobs."""
        service._table = mock_dynamodb_table
        service._jobs_table = mock_jobs_table

        mock_dynamodb_table.query.return_value = {"Items": []}

        running_job = {
            "job_id": "running-001",
            "job_type": "CODE_REVIEW",
            "status": "RUNNING",
            "organization_id": organization_id,
            "started_at": (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            ).isoformat(),
            "description": "Running job",
            "repository_id": "repo-main",
            "user_id": "test-user",
        }
        mock_jobs_table.scan.return_value = {"Items": [running_job]}

        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc) + timedelta(days=1)

        entries = await service.get_timeline(
            organization_id,
            start_date=start_date,
            end_date=end_date,
        )

        assert len(entries) == 1
        assert entries[0].status == "RUNNING"


# =============================================================================
# Extended Coverage Tests - list_pending_jobs
# =============================================================================


class TestListPendingJobsExtended:
    """Extended tests for list_pending_jobs."""

    @pytest.mark.asyncio
    async def test_list_pending_jobs_with_organization_filter(
        self, service, mock_dynamodb_table, sample_scheduled_job
    ):
        """Test listing pending jobs with organization filter."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_scheduled_job.to_dynamodb_item()]
        }

        jobs = await service.list_pending_jobs(organization_id="test-org")

        # Verify FilterExpression was used
        call_args = mock_dynamodb_table.query.call_args
        assert "FilterExpression" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_list_pending_jobs_dynamodb_error(self, service, mock_dynamodb_table):
        """Test listing pending jobs with DynamoDB error."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.side_effect = Exception("DynamoDB error")

        with pytest.raises(SchedulingServiceError):
            await service.list_pending_jobs()


# =============================================================================
# Extended Coverage Tests - reschedule_job
# =============================================================================


class TestRescheduleJobExtended:
    """Extended tests for reschedule_job."""

    @pytest.mark.asyncio
    async def test_reschedule_job_naive_datetime(
        self,
        service,
        mock_dynamodb_table,
        organization_id,
        user_id,
        sample_scheduled_job,
    ):
        """Test rescheduling with naive datetime (no tzinfo)."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }

        # Naive datetime (no tzinfo) - use 48 hours to account for any timezone offset
        new_time = datetime.now() + timedelta(hours=48)
        assert new_time.tzinfo is None

        result = await service.reschedule_job(
            organization_id, sample_scheduled_job.schedule_id, new_time, user_id
        )

        # Should succeed and convert to UTC
        assert result.scheduled_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_reschedule_job_dynamodb_error(
        self,
        service,
        mock_dynamodb_table,
        organization_id,
        user_id,
        sample_scheduled_job,
    ):
        """Test rescheduling with DynamoDB update error."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }
        mock_dynamodb_table.update_item.side_effect = Exception("DynamoDB error")

        new_time = datetime.now(timezone.utc) + timedelta(hours=5)

        with pytest.raises(SchedulingServiceError):
            await service.reschedule_job(
                organization_id, sample_scheduled_job.schedule_id, new_time, user_id
            )


# =============================================================================
# Extended Coverage Tests - cancel_scheduled_job
# =============================================================================


class TestCancelJobExtended:
    """Extended tests for cancel_scheduled_job."""

    @pytest.mark.asyncio
    async def test_cancel_job_dynamodb_error(
        self,
        service,
        mock_dynamodb_table,
        organization_id,
        user_id,
        sample_scheduled_job,
    ):
        """Test cancelling with DynamoDB update error."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.get_item.return_value = {
            "Item": sample_scheduled_job.to_dynamodb_item()
        }
        mock_dynamodb_table.update_item.side_effect = Exception("DynamoDB error")

        with pytest.raises(SchedulingServiceError):
            await service.cancel_scheduled_job(
                organization_id, sample_scheduled_job.schedule_id, user_id
            )


# =============================================================================
# Extended Coverage Tests - lazy loading and singleton
# =============================================================================


class TestLazyLoadingAndSingleton:
    """Tests for lazy loading and singleton management."""

    def test_table_property_lazy_loading(self):
        """Test that table property lazily loads DynamoDB resource."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_boto3.return_value = mock_dynamodb
            mock_dynamodb.Table.return_value = mock_table

            service = SchedulingService()
            assert service._table is None
            assert service._dynamodb is None

            # Access table property
            table = service.table

            # Should have created DynamoDB resource
            mock_boto3.assert_called_once_with("dynamodb", region_name=service.region)
            assert service._dynamodb is mock_dynamodb
            assert table is mock_table

    def test_jobs_table_property_lazy_loading(self):
        """Test that jobs_table property lazily loads DynamoDB resource."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_boto3.return_value = mock_dynamodb
            mock_dynamodb.Table.return_value = mock_table

            service = SchedulingService()

            # Access jobs_table property
            jobs_table = service.jobs_table

            mock_boto3.assert_called_once()
            assert jobs_table is mock_table

    def test_jobs_table_reuses_dynamodb_resource(self):
        """Test that jobs_table reuses existing DynamoDB resource."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_boto3.return_value = mock_dynamodb
            mock_dynamodb.Table.return_value = mock_table

            service = SchedulingService()

            # Access table first
            _ = service.table
            # Then jobs_table
            _ = service.jobs_table

            # Should only create DynamoDB resource once
            assert mock_boto3.call_count == 1

    def test_clear_scheduling_service(self):
        """Test clear_scheduling_service function."""
        from src.services.scheduling.scheduling_service import (
            clear_scheduling_service,
            get_scheduling_service,
            set_scheduling_service,
        )

        # Set a service
        custom_service = SchedulingService(table_name="custom")
        set_scheduling_service(custom_service)

        # Clear it
        clear_scheduling_service()

        # Getting service should create a new one
        new_service = get_scheduling_service()
        assert new_service is not custom_service


# =============================================================================
# Extended Coverage Tests - list_scheduled_jobs
# =============================================================================


class TestListScheduledJobsExtended:
    """Extended tests for list_scheduled_jobs."""

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_with_start_key(
        self, service, mock_dynamodb_table, organization_id, sample_scheduled_job
    ):
        """Test listing with explicit start key for pagination."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.return_value = {
            "Items": [sample_scheduled_job.to_dynamodb_item()],
        }

        start_key = {"organization_id": organization_id, "schedule_id": "prev-001"}
        jobs, next_key = await service.list_scheduled_jobs(
            organization_id, start_key=start_key
        )

        # Verify ExclusiveStartKey was passed
        call_args = mock_dynamodb_table.query.call_args
        assert call_args.kwargs["ExclusiveStartKey"] == start_key

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_dynamodb_error(
        self, service, mock_dynamodb_table, organization_id
    ):
        """Test listing with DynamoDB error."""
        service._table = mock_dynamodb_table
        mock_dynamodb_table.query.side_effect = Exception("DynamoDB error")

        with pytest.raises(SchedulingServiceError):
            await service.list_scheduled_jobs(organization_id)
