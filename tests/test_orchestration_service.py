"""
Tests for Orchestration Service.

Tests the agent orchestration job management system:
- Job submission and tracking
- Status updates and transitions
- Queue management
- Health checks
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.services.orchestration_service import (
    JobPriority,
    JobStatus,
    JobSubmission,
    OrchestrationJob,
    OrchestrationService,
    PersistenceMode,
    create_orchestration_service,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_service():
    """Create orchestration service in mock mode."""
    return OrchestrationService(mode=PersistenceMode.MOCK)


@pytest.fixture
def job_submission():
    """Create a sample job submission."""
    return JobSubmission(
        prompt="Analyze the codebase for security vulnerabilities",
        user_id="user-123",
        priority=JobPriority.NORMAL,
        metadata={"project": "test-project"},
        callback_url="https://webhook.example.com/callback",
    )


# ============================================================================
# Enum Tests
# ============================================================================


class TestEnums:
    """Test enum definitions."""

    def test_job_status_values(self):
        """Test JobStatus enum values."""
        assert JobStatus.QUEUED.value == "QUEUED"
        assert JobStatus.DISPATCHED.value == "DISPATCHED"
        assert JobStatus.RUNNING.value == "RUNNING"
        assert JobStatus.SUCCEEDED.value == "SUCCEEDED"
        assert JobStatus.FAILED.value == "FAILED"
        assert JobStatus.CANCELLED.value == "CANCELLED"
        assert JobStatus.TIMED_OUT.value == "TIMED_OUT"

    def test_job_priority_values(self):
        """Test JobPriority enum values."""
        assert JobPriority.LOW.value == "LOW"
        assert JobPriority.NORMAL.value == "NORMAL"
        assert JobPriority.HIGH.value == "HIGH"
        assert JobPriority.CRITICAL.value == "CRITICAL"

    def test_persistence_mode_values(self):
        """Test PersistenceMode enum values."""
        assert PersistenceMode.MOCK.value == "mock"
        assert PersistenceMode.AWS.value == "aws"


# ============================================================================
# OrchestrationJob Tests
# ============================================================================


class TestOrchestrationJob:
    """Test OrchestrationJob dataclass."""

    def test_create_job(self):
        """Test creating an orchestration job."""
        now = datetime.now(timezone.utc).isoformat()
        job = OrchestrationJob(
            job_id="job-123",
            task_id="task-456",
            user_id="user-789",
            prompt="Test prompt",
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            created_at=now,
            updated_at=now,
        )
        assert job.job_id == "job-123"
        assert job.task_id == "task-456"
        assert job.status == JobStatus.QUEUED
        assert job.priority == JobPriority.NORMAL
        assert job.started_at is None
        assert job.completed_at is None
        assert job.result is None
        assert job.error_message is None

    def test_job_with_all_fields(self):
        """Test job with all optional fields."""
        now = datetime.now(timezone.utc).isoformat()
        job = OrchestrationJob(
            job_id="job-123",
            task_id="task-456",
            user_id="user-789",
            prompt="Test prompt",
            status=JobStatus.SUCCEEDED,
            priority=JobPriority.HIGH,
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now,
            result={"output": "Success"},
            error_message=None,
            metadata={"key": "value"},
            ttl=1234567890,
        )
        assert job.started_at == now
        assert job.completed_at == now
        assert job.result == {"output": "Success"}
        assert job.metadata == {"key": "value"}
        assert job.ttl == 1234567890

    def test_job_to_dict(self):
        """Test converting job to dictionary."""
        now = datetime.now(timezone.utc).isoformat()
        job = OrchestrationJob(
            job_id="job-123",
            task_id="task-456",
            user_id="user-789",
            prompt="Test",
            status=JobStatus.QUEUED,
            priority=JobPriority.NORMAL,
            created_at=now,
            updated_at=now,
        )
        data = job.to_dict()
        assert data["job_id"] == "job-123"
        assert data["status"] == "QUEUED"
        assert data["priority"] == "NORMAL"

    def test_job_to_dict_with_optional_fields(self):
        """Test to_dict includes optional fields when set."""
        now = datetime.now(timezone.utc).isoformat()
        job = OrchestrationJob(
            job_id="job-123",
            task_id="task-456",
            user_id="user-789",
            prompt="Test",
            status=JobStatus.FAILED,
            priority=JobPriority.HIGH,
            created_at=now,
            updated_at=now,
            started_at=now,
            completed_at=now,
            result={"data": "result"},
            error_message="Something went wrong",
            ttl=999999,
        )
        data = job.to_dict()
        assert data["started_at"] == now
        assert data["completed_at"] == now
        assert data["result"] == {"data": "result"}
        assert data["error_message"] == "Something went wrong"
        assert data["ttl"] == 999999

    def test_job_from_dict(self):
        """Test creating job from dictionary."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "job_id": "job-abc",
            "task_id": "task-def",
            "user_id": "user-ghi",
            "prompt": "Test prompt",
            "status": "RUNNING",
            "priority": "HIGH",
            "created_at": now,
            "updated_at": now,
            "metadata": {"custom": "data"},
        }
        job = OrchestrationJob.from_dict(data)
        assert job.job_id == "job-abc"
        assert job.status == JobStatus.RUNNING
        assert job.priority == JobPriority.HIGH
        assert job.metadata == {"custom": "data"}

    def test_job_from_dict_with_defaults(self):
        """Test from_dict uses defaults for missing optional fields."""
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "job_id": "job-abc",
            "task_id": "task-def",
            "user_id": "user-ghi",
            "prompt": "Test",
            "status": "QUEUED",
            "created_at": now,
            "updated_at": now,
        }
        job = OrchestrationJob.from_dict(data)
        assert job.priority == JobPriority.NORMAL
        assert job.started_at is None
        assert job.metadata == {}


# ============================================================================
# JobSubmission Tests
# ============================================================================


class TestJobSubmission:
    """Test JobSubmission dataclass."""

    def test_create_submission(self):
        """Test creating a job submission."""
        submission = JobSubmission(
            prompt="Analyze code",
            user_id="user-123",
        )
        assert submission.prompt == "Analyze code"
        assert submission.user_id == "user-123"
        assert submission.priority == JobPriority.NORMAL
        assert submission.metadata == {}
        assert submission.callback_url is None

    def test_submission_with_all_fields(self, job_submission):
        """Test submission with all fields."""
        assert job_submission.priority == JobPriority.NORMAL
        assert job_submission.metadata == {"project": "test-project"}
        assert job_submission.callback_url == "https://webhook.example.com/callback"


# ============================================================================
# OrchestrationService Initialization Tests
# ============================================================================


class TestServiceInitialization:
    """Test OrchestrationService initialization."""

    def test_mock_mode_initialization(self, mock_service):
        """Test initialization in mock mode."""
        assert mock_service.mode == PersistenceMode.MOCK
        assert mock_service._mock_jobs == {}
        assert mock_service._mock_queue == []
        assert mock_service._dynamodb is None
        assert mock_service._sqs is None

    def test_custom_configuration(self):
        """Test initialization with custom configuration."""
        service = OrchestrationService(
            mode=PersistenceMode.MOCK,
            table_name="custom-table",
            queue_url="https://sqs.example.com/queue",
            project_name="my-project",
            environment="staging",
        )
        assert service.table_name == "custom-table"
        assert service._queue_url == "https://sqs.example.com/queue"
        assert service.project_name == "my-project"
        assert service.environment == "staging"

    def test_default_table_name_derivation(self, mock_service):
        """Test default table name is derived correctly."""
        assert mock_service.table_name == "aura-orchestrator-jobs-dev"

    def test_aws_mode_requires_region(self):
        """Test AWS mode requires region parameter."""
        with pytest.raises(ValueError, match="AWS_REGION is required"):
            OrchestrationService(mode=PersistenceMode.AWS)

    def test_aws_mode_with_region(self):
        """Test AWS mode with region provided."""
        service = OrchestrationService(
            mode=PersistenceMode.AWS,
            region="us-east-1",
        )
        assert service.mode == PersistenceMode.AWS
        assert service.region == "us-east-1"


# ============================================================================
# Job Submission Tests
# ============================================================================


class TestJobSubmissionFlow:
    """Test job submission flow."""

    @pytest.mark.asyncio
    async def test_submit_job_mock(self, mock_service, job_submission):
        """Test submitting a job in mock mode."""
        job = await mock_service.submit_job(job_submission)

        assert job.job_id.startswith("job-")
        assert job.task_id.startswith("task-")
        assert job.user_id == "user-123"
        assert job.prompt == job_submission.prompt
        assert job.status == JobStatus.QUEUED
        assert job.priority == JobPriority.NORMAL
        assert job.job_id in mock_service._mock_jobs
        assert len(mock_service._mock_queue) == 1

    @pytest.mark.asyncio
    async def test_submit_high_priority_job(self, mock_service):
        """Test submitting a high priority job."""
        submission = JobSubmission(
            prompt="Critical analysis",
            user_id="user-123",
            priority=JobPriority.CRITICAL,
        )
        job = await mock_service.submit_job(submission)

        assert job.priority == JobPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_submit_job_with_metadata(self, mock_service, job_submission):
        """Test job metadata is preserved."""
        job = await mock_service.submit_job(job_submission)

        assert "project" in job.metadata
        assert job.metadata["callback_url"] == job_submission.callback_url

    @pytest.mark.asyncio
    async def test_submit_job_creates_ttl(self, mock_service, job_submission):
        """Test TTL is set on job submission."""
        job = await mock_service.submit_job(job_submission)

        assert job.ttl is not None
        # TTL should be approximately 7 days from now
        expected_ttl = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        assert abs(job.ttl - expected_ttl) < 60  # Within 1 minute tolerance


# ============================================================================
# Job Retrieval Tests
# ============================================================================


class TestJobRetrieval:
    """Test job retrieval operations."""

    @pytest.mark.asyncio
    async def test_get_job(self, mock_service, job_submission):
        """Test getting a job by ID."""
        submitted = await mock_service.submit_job(job_submission)
        retrieved = await mock_service.get_job(submitted.job_id)

        assert retrieved is not None
        assert retrieved.job_id == submitted.job_id
        assert retrieved.prompt == submitted.prompt

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, mock_service):
        """Test getting a non-existent job returns None."""
        result = await mock_service.get_job("nonexistent-job-id")
        assert result is None


# ============================================================================
# Job Listing Tests
# ============================================================================


class TestJobListing:
    """Test job listing operations."""

    @pytest.mark.asyncio
    async def test_list_jobs(self, mock_service):
        """Test listing all jobs."""
        # Submit multiple jobs
        for i in range(5):
            await mock_service.submit_job(
                JobSubmission(
                    prompt=f"Task {i}",
                    user_id="user-123",
                )
            )

        jobs = await mock_service.list_jobs()
        assert len(jobs) == 5

    @pytest.mark.asyncio
    async def test_list_jobs_by_user(self, mock_service):
        """Test listing jobs filtered by user."""
        await mock_service.submit_job(JobSubmission(prompt="Task 1", user_id="user-a"))
        await mock_service.submit_job(JobSubmission(prompt="Task 2", user_id="user-b"))
        await mock_service.submit_job(JobSubmission(prompt="Task 3", user_id="user-a"))

        jobs = await mock_service.list_jobs(user_id="user-a")
        assert len(jobs) == 2
        assert all(j.user_id == "user-a" for j in jobs)

    @pytest.mark.asyncio
    async def test_list_jobs_by_status(self, mock_service):
        """Test listing jobs filtered by status."""
        job1 = await mock_service.submit_job(
            JobSubmission(prompt="Task 1", user_id="u")
        )
        await mock_service.submit_job(JobSubmission(prompt="Task 2", user_id="u"))
        await mock_service.update_job_status(job1.job_id, JobStatus.RUNNING)

        jobs = await mock_service.list_jobs(status=JobStatus.RUNNING)
        assert len(jobs) == 1
        assert jobs[0].status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_list_jobs_sorted_by_created_at(self, mock_service):
        """Test jobs are sorted by created_at descending."""
        for i in range(3):
            await mock_service.submit_job(
                JobSubmission(prompt=f"Task {i}", user_id="u")
            )

        jobs = await mock_service.list_jobs()
        # Most recent first
        assert jobs[0].created_at >= jobs[-1].created_at

    @pytest.mark.asyncio
    async def test_list_jobs_with_limit(self, mock_service):
        """Test listing jobs with limit."""
        for i in range(10):
            await mock_service.submit_job(
                JobSubmission(prompt=f"Task {i}", user_id="u")
            )

        jobs = await mock_service.list_jobs(limit=5)
        assert len(jobs) == 5


# ============================================================================
# Job Status Update Tests
# ============================================================================


class TestJobStatusUpdate:
    """Test job status update operations."""

    @pytest.mark.asyncio
    async def test_update_status_to_running(self, mock_service, job_submission):
        """Test updating status to RUNNING."""
        job = await mock_service.submit_job(job_submission)
        updated = await mock_service.update_job_status(job.job_id, JobStatus.RUNNING)

        assert updated.status == JobStatus.RUNNING
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_update_status_to_succeeded(self, mock_service, job_submission):
        """Test updating status to SUCCEEDED."""
        job = await mock_service.submit_job(job_submission)
        await mock_service.update_job_status(job.job_id, JobStatus.RUNNING)

        result_data = {"findings": ["Issue 1", "Issue 2"]}
        updated = await mock_service.update_job_status(
            job.job_id,
            JobStatus.SUCCEEDED,
            result=result_data,
        )

        assert updated.status == JobStatus.SUCCEEDED
        assert updated.completed_at is not None
        assert updated.result == result_data

    @pytest.mark.asyncio
    async def test_update_status_to_failed(self, mock_service, job_submission):
        """Test updating status to FAILED."""
        job = await mock_service.submit_job(job_submission)
        updated = await mock_service.update_job_status(
            job.job_id,
            JobStatus.FAILED,
            error_message="Task execution failed",
        )

        assert updated.status == JobStatus.FAILED
        assert updated.error_message == "Task execution failed"
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent_job(self, mock_service):
        """Test updating a non-existent job returns None."""
        result = await mock_service.update_job_status("nonexistent", JobStatus.RUNNING)
        assert result is None


# ============================================================================
# Job Cancellation Tests
# ============================================================================


class TestJobCancellation:
    """Test job cancellation operations."""

    @pytest.mark.asyncio
    async def test_cancel_job(self, mock_service, job_submission):
        """Test canceling a job."""
        job = await mock_service.submit_job(job_submission)
        cancelled = await mock_service.cancel_job(job.job_id, "user-123")

        assert cancelled.status == JobStatus.CANCELLED
        assert cancelled.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, mock_service):
        """Test canceling a non-existent job returns None."""
        result = await mock_service.cancel_job("nonexistent", "user-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_job_wrong_user(self, mock_service, job_submission):
        """Test canceling job by wrong user raises error."""
        job = await mock_service.submit_job(job_submission)

        with pytest.raises(PermissionError, match="cannot cancel"):
            await mock_service.cancel_job(job.job_id, "different-user")

    @pytest.mark.asyncio
    async def test_cancel_already_completed_job(self, mock_service, job_submission):
        """Test canceling an already completed job returns it unchanged."""
        job = await mock_service.submit_job(job_submission)
        await mock_service.update_job_status(job.job_id, JobStatus.SUCCEEDED)

        result = await mock_service.cancel_job(job.job_id, "user-123")
        assert result.status == JobStatus.SUCCEEDED


# ============================================================================
# Queue Depth Tests
# ============================================================================


class TestQueueDepth:
    """Test queue depth operations."""

    @pytest.mark.asyncio
    async def test_get_queue_depth_mock(self, mock_service):
        """Test getting queue depth in mock mode."""
        depth = await mock_service.get_queue_depth()
        assert depth == 0

    @pytest.mark.asyncio
    async def test_get_queue_depth_after_submissions(self, mock_service):
        """Test queue depth increases with submissions."""
        for i in range(3):
            await mock_service.submit_job(
                JobSubmission(prompt=f"Task {i}", user_id="u")
            )

        depth = await mock_service.get_queue_depth()
        assert depth == 3


# ============================================================================
# Health Check Tests
# ============================================================================


class TestHealthCheck:
    """Test health check operations."""

    @pytest.mark.asyncio
    async def test_health_check_mock(self, mock_service):
        """Test health check in mock mode."""
        health = await mock_service.health_check()

        assert health["status"] == "healthy"
        assert health["mode"] == "mock"
        assert "jobs_count" in health
        assert "queue_depth" in health

    @pytest.mark.asyncio
    async def test_health_check_reflects_job_count(self, mock_service, job_submission):
        """Test health check reflects correct job count."""
        await mock_service.submit_job(job_submission)
        await mock_service.submit_job(job_submission)

        health = await mock_service.health_check()
        assert health["jobs_count"] == 2
        assert health["queue_depth"] == 2


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestFactoryFunction:
    """Test create_orchestration_service factory function."""

    @patch.dict("os.environ", {"USE_MOCK_ORCHESTRATION": "true"})
    def test_create_mock_service_via_env(self):
        """Test factory creates mock service via environment variable."""
        service = create_orchestration_service()
        assert service.mode == PersistenceMode.MOCK

    def test_create_mock_service_via_param(self):
        """Test factory creates mock service via parameter."""
        service = create_orchestration_service(use_mock=True)
        assert service.mode == PersistenceMode.MOCK

    @patch.dict("os.environ", {}, clear=True)
    def test_create_aws_service_requires_region(self):
        """Test factory requires AWS_REGION for AWS mode."""
        with pytest.raises(ValueError, match="AWS_REGION"):
            create_orchestration_service(use_mock=False)

    @patch.dict("os.environ", {"AWS_REGION": "us-west-2"})
    def test_create_aws_service_with_region(self):
        """Test factory creates AWS service with region."""
        service = create_orchestration_service(use_mock=False)
        assert service.mode == PersistenceMode.AWS
        assert service.region == "us-west-2"
