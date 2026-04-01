"""Tests for GPU Scheduler service."""

from __future__ import annotations

import pytest

from src.services.gpu_scheduler.exceptions import (
    GPUJobNotFoundError,
    InvalidJobConfigError,
    JobCancellationError,
    QuotaExceededError,
)
from src.services.gpu_scheduler.gpu_scheduler_service import (
    GPUSchedulerService,
    get_gpu_scheduler_service,
    init_gpu_scheduler_service,
)
from src.services.gpu_scheduler.models import (
    GPUJobCreateRequest,
    GPUJobStatus,
    GPUQuota,
)


class TestGPUSchedulerServiceInit:
    """Tests for service initialization."""

    def test_service_init_defaults(self, mock_env_vars):
        """Test service initializes with default values."""
        service = GPUSchedulerService()
        assert service.region == "us-east-1"
        assert "aura-gpu-jobs" in service.jobs_table_name
        assert "aura-gpu-quotas" in service.quotas_table_name

    def test_service_init_custom(self):
        """Test service initializes with custom values."""
        service = GPUSchedulerService(
            jobs_table_name="custom-jobs",
            quotas_table_name="custom-quotas",
            queue_url="https://sqs.us-west-2.amazonaws.com/123/queue.fifo",
            checkpoints_bucket="custom-bucket",
            region="us-west-2",
        )
        assert service.jobs_table_name == "custom-jobs"
        assert service.quotas_table_name == "custom-quotas"
        assert service.region == "us-west-2"

    def test_singleton_pattern(self, mock_env_vars):
        """Test singleton pattern works."""
        service1 = init_gpu_scheduler_service(
            jobs_table_name="test-jobs-1",
        )
        service2 = get_gpu_scheduler_service()
        assert service1 is service2


class TestGPUSchedulerServiceSubmitJob:
    """Tests for job submission."""

    @pytest.mark.asyncio
    async def test_submit_job_success(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test successful job submission."""
        job = await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )

        assert job.job_id is not None
        assert job.organization_id == "org-123"
        assert job.user_id == "user-456"
        assert job.status == GPUJobStatus.QUEUED
        assert job.job_type == sample_job_request.job_type
        assert job.priority == sample_job_request.priority
        assert job.checkpoint_s3_path is not None

    @pytest.mark.asyncio
    async def test_submit_job_quota_exceeded_concurrent(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test job submission fails when concurrent quota exceeded."""
        # Set up quota at limit
        quota = GPUQuota(
            organization_id="org-123",
            max_concurrent_jobs=2,
            current_concurrent_jobs=2,
        )
        gpu_scheduler_service.quotas_table.put_item(Item=quota.to_dynamodb_item())

        with pytest.raises(QuotaExceededError) as exc_info:
            await gpu_scheduler_service.submit_job(
                organization_id="org-123",
                user_id="user-456",
                request=sample_job_request,
            )

        assert "concurrent_jobs" in exc_info.value.quota_type

    @pytest.mark.asyncio
    async def test_submit_job_runtime_exceeds_quota(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test job submission fails when runtime exceeds quota."""
        # Set up quota with short max runtime
        quota = GPUQuota(
            organization_id="org-123",
            max_job_runtime_hours=1,
        )
        gpu_scheduler_service.quotas_table.put_item(Item=quota.to_dynamodb_item())

        # Request has max_runtime_hours=2, which exceeds quota
        with pytest.raises(InvalidJobConfigError) as exc_info:
            await gpu_scheduler_service.submit_job(
                organization_id="org-123",
                user_id="user-456",
                request=sample_job_request,
            )

        assert "exceeds quota limit" in str(exc_info.value)


class TestGPUSchedulerServiceGetJob:
    """Tests for getting jobs."""

    @pytest.mark.asyncio
    async def test_get_job_success(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test getting an existing job."""
        # Submit a job first
        submitted = await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )

        # Get the job
        retrieved = await gpu_scheduler_service.get_job(
            organization_id="org-123",
            job_id=submitted.job_id,
        )

        assert retrieved.job_id == submitted.job_id
        assert retrieved.organization_id == submitted.organization_id

    @pytest.mark.asyncio
    async def test_get_job_not_found(
        self,
        gpu_scheduler_service: GPUSchedulerService,
    ):
        """Test getting a non-existent job."""
        with pytest.raises(GPUJobNotFoundError):
            await gpu_scheduler_service.get_job(
                organization_id="org-123",
                job_id="non-existent-job",
            )


class TestGPUSchedulerServiceListJobs:
    """Tests for listing jobs."""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(
        self,
        gpu_scheduler_service: GPUSchedulerService,
    ):
        """Test listing jobs when none exist."""
        jobs = await gpu_scheduler_service.list_jobs(
            organization_id="org-123",
        )
        assert jobs == []

    @pytest.mark.asyncio
    async def test_list_jobs_with_jobs(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test listing jobs when jobs exist."""
        # Submit multiple jobs
        await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )
        await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )

        jobs = await gpu_scheduler_service.list_jobs(
            organization_id="org-123",
        )

        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test listing jobs filtered by status."""
        # Submit a job (will be QUEUED)
        await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )

        # Filter by QUEUED status
        queued_jobs = await gpu_scheduler_service.list_jobs(
            organization_id="org-123",
            status=GPUJobStatus.QUEUED,
        )
        assert len(queued_jobs) == 1

        # Filter by RUNNING status (should be empty)
        running_jobs = await gpu_scheduler_service.list_jobs(
            organization_id="org-123",
            status=GPUJobStatus.RUNNING,
        )
        assert len(running_jobs) == 0


class TestGPUSchedulerServiceCancelJob:
    """Tests for cancelling jobs."""

    @pytest.mark.asyncio
    async def test_cancel_job_success(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test successful job cancellation."""
        # Submit a job
        submitted = await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )

        # Cancel the job
        cancelled = await gpu_scheduler_service.cancel_job(
            organization_id="org-123",
            job_id=submitted.job_id,
            user_id="user-456",
        )

        assert cancelled.status == GPUJobStatus.CANCELLED
        assert cancelled.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_job_already_completed(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test cancelling an already completed job fails."""
        # Submit and complete a job
        submitted = await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )
        await gpu_scheduler_service.update_job_status(
            organization_id="org-123",
            job_id=submitted.job_id,
            status=GPUJobStatus.COMPLETED,
        )

        # Try to cancel
        with pytest.raises(JobCancellationError):
            await gpu_scheduler_service.cancel_job(
                organization_id="org-123",
                job_id=submitted.job_id,
                user_id="user-456",
            )

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(
        self,
        gpu_scheduler_service: GPUSchedulerService,
    ):
        """Test cancelling a non-existent job."""
        with pytest.raises(GPUJobNotFoundError):
            await gpu_scheduler_service.cancel_job(
                organization_id="org-123",
                job_id="non-existent",
                user_id="user-456",
            )


class TestGPUSchedulerServiceQuota:
    """Tests for quota management."""

    @pytest.mark.asyncio
    async def test_get_quota_creates_default(
        self,
        gpu_scheduler_service: GPUSchedulerService,
    ):
        """Test getting quota creates default if not exists."""
        quota = await gpu_scheduler_service.get_quota(
            organization_id="new-org",
        )

        assert quota.organization_id == "new-org"
        assert quota.max_concurrent_jobs == 4  # default
        assert quota.max_gpu_hours_monthly == 100  # default

    @pytest.mark.asyncio
    async def test_get_quota_existing(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_quota: GPUQuota,
    ):
        """Test getting an existing quota."""
        # Store quota
        gpu_scheduler_service.quotas_table.put_item(
            Item=sample_quota.to_dynamodb_item()
        )

        # Get quota
        quota = await gpu_scheduler_service.get_quota(
            organization_id=sample_quota.organization_id,
        )

        assert quota.organization_id == sample_quota.organization_id
        assert quota.max_concurrent_jobs == sample_quota.max_concurrent_jobs

    @pytest.mark.asyncio
    async def test_update_quota(
        self,
        gpu_scheduler_service: GPUSchedulerService,
    ):
        """Test updating quota."""
        # Create initial quota
        await gpu_scheduler_service.get_quota(organization_id="org-123")

        # Update quota
        updated = await gpu_scheduler_service.update_quota(
            organization_id="org-123",
            max_concurrent_jobs=10,
            max_gpu_hours_monthly=500,
        )

        assert updated.max_concurrent_jobs == 10
        assert updated.max_gpu_hours_monthly == 500


class TestGPUSchedulerServiceHealth:
    """Tests for health check."""

    @pytest.mark.asyncio
    async def test_health_check(
        self,
        gpu_scheduler_service: GPUSchedulerService,
    ):
        """Test health check returns status."""
        health = await gpu_scheduler_service.health_check()

        assert health["service"] == "gpu_scheduler"
        assert "region" in health
        assert "jobs_table" in health
        assert "healthy" in health


class TestGPUSchedulerServiceUpdateStatus:
    """Tests for updating job status."""

    @pytest.mark.asyncio
    async def test_update_to_running(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test updating job status to running."""
        # Submit a job
        submitted = await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )

        # Update to running
        updated = await gpu_scheduler_service.update_job_status(
            organization_id="org-123",
            job_id=submitted.job_id,
            status=GPUJobStatus.RUNNING,
            kubernetes_job_name="gpu-job-12345",
        )

        assert updated.status == GPUJobStatus.RUNNING
        assert updated.started_at is not None
        assert updated.kubernetes_job_name == "gpu-job-12345"

    @pytest.mark.asyncio
    async def test_update_to_failed_with_error(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test updating job status to failed with error details."""
        # Submit a job
        submitted = await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )

        # Update to failed
        updated = await gpu_scheduler_service.update_job_status(
            organization_id="org-123",
            job_id=submitted.job_id,
            status=GPUJobStatus.FAILED,
            error_message="Out of GPU memory",
            error_type="oom",
        )

        assert updated.status == GPUJobStatus.FAILED
        assert updated.completed_at is not None
        assert updated.error_message == "Out of GPU memory"

    @pytest.mark.asyncio
    async def test_update_progress(
        self,
        gpu_scheduler_service: GPUSchedulerService,
        sample_job_request: GPUJobCreateRequest,
    ):
        """Test updating job progress."""
        # Submit a job
        submitted = await gpu_scheduler_service.submit_job(
            organization_id="org-123",
            user_id="user-456",
            request=sample_job_request,
        )

        # Update progress
        updated = await gpu_scheduler_service.update_job_status(
            organization_id="org-123",
            job_id=submitted.job_id,
            status=GPUJobStatus.RUNNING,
            progress_percent=50,
        )

        assert updated.progress_percent == 50
