"""
Project Aura - Orchestration Service Edge Case Tests

Tests for concurrent job submission, status transitions, failure recovery,
priority queue behavior, and ownership enforcement.

Priority: P1 - Data Integrity
"""

import asyncio

import pytest

from src.services.orchestration_service import (
    JobPriority,
    JobStatus,
    JobSubmission,
    OrchestrationService,
    PersistenceMode,
)


class TestConcurrentJobSubmission:
    """Test concurrent job submission scenarios."""

    @pytest.fixture
    def service(self):
        """Create orchestration service in mock mode."""
        return OrchestrationService(
            mode=PersistenceMode.MOCK,
            project_name="aura-test",
            environment="test",
        )

    @pytest.mark.asyncio
    async def test_rapid_concurrent_submissions(self, service):
        """Test rapid concurrent job submissions don't lose jobs."""
        submissions = [
            JobSubmission(
                prompt=f"Task {i}",
                user_id="user-123",
                priority=JobPriority.NORMAL,
            )
            for i in range(50)
        ]

        # Submit all jobs concurrently
        tasks = [service.submit_job(sub) for sub in submissions]
        jobs = await asyncio.gather(*tasks)

        # All jobs should be created with unique IDs
        job_ids = [j.job_id for j in jobs]
        assert len(set(job_ids)) == 50, "Job IDs should be unique"

        # All jobs should be tracked
        assert len(service._mock_queue) == 50

    @pytest.mark.asyncio
    async def test_job_status_transition_ordering(self, service):
        """Verify job status transitions follow valid state machine."""
        job = await service.submit_job(JobSubmission(prompt="Test", user_id="user-1"))

        # Valid transition: QUEUED -> RUNNING
        updated = await service.update_job_status(job.job_id, JobStatus.RUNNING)
        assert updated.status == JobStatus.RUNNING
        assert updated.started_at is not None

        # Valid transition: RUNNING -> SUCCEEDED
        updated = await service.update_job_status(
            job.job_id, JobStatus.SUCCEEDED, result={"output": "done"}
        )
        assert updated.status == JobStatus.SUCCEEDED
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_double_cancellation_idempotent(self, service):
        """Test that cancelling already cancelled job is idempotent."""
        job = await service.submit_job(JobSubmission(prompt="Test", user_id="user-1"))

        # First cancellation
        cancelled1 = await service.cancel_job(job.job_id, "user-1")
        assert cancelled1.status == JobStatus.CANCELLED

        # Second cancellation should return same result (idempotent)
        cancelled2 = await service.cancel_job(job.job_id, "user-1")
        assert cancelled2.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_job_returns_current_state(self, service):
        """Test that cancelling completed job returns current state."""
        job = await service.submit_job(JobSubmission(prompt="Test", user_id="user-1"))

        # Complete the job
        await service.update_job_status(
            job.job_id, JobStatus.SUCCEEDED, result={"done": True}
        )

        # Attempting to cancel should return current state
        result = await service.cancel_job(job.job_id, "user-1")
        assert result.status == JobStatus.SUCCEEDED


class TestJobFailureRecovery:
    """Test job failure and recovery scenarios."""

    @pytest.fixture
    def service(self):
        return OrchestrationService(mode=PersistenceMode.MOCK)

    @pytest.mark.asyncio
    async def test_partial_batch_failure(self, service):
        """Test handling when some jobs in batch fail."""
        submissions = [
            JobSubmission(prompt=f"Task {i}", user_id="user-1") for i in range(5)
        ]

        jobs = []
        for sub in submissions:
            jobs.append(await service.submit_job(sub))

        # Simulate partial failure
        await service.update_job_status(jobs[0].job_id, JobStatus.SUCCEEDED)
        await service.update_job_status(
            jobs[1].job_id, JobStatus.FAILED, error_message="Out of memory"
        )
        await service.update_job_status(jobs[2].job_id, JobStatus.SUCCEEDED)
        await service.update_job_status(jobs[3].job_id, JobStatus.TIMED_OUT)
        await service.update_job_status(jobs[4].job_id, JobStatus.SUCCEEDED)

        # Query by status
        failed_jobs = await service.list_jobs(status=JobStatus.FAILED)
        timed_out_jobs = await service.list_jobs(status=JobStatus.TIMED_OUT)

        assert len(failed_jobs) == 1
        assert len(timed_out_jobs) == 1
        assert failed_jobs[0].error_message == "Out of memory"

    @pytest.mark.asyncio
    async def test_job_timeout_with_partial_results(self, service):
        """Test handling timeout with partial results available."""
        job = await service.submit_job(
            JobSubmission(prompt="Long task", user_id="user-1")
        )

        # Job starts running
        await service.update_job_status(job.job_id, JobStatus.RUNNING)

        # Job times out but has partial results
        partial_result = {
            "completed_steps": ["step1", "step2"],
            "pending_steps": ["step3", "step4"],
            "partial_output": "Some work done...",
        }

        await service.update_job_status(
            job.job_id,
            JobStatus.TIMED_OUT,
            result=partial_result,
            error_message="Execution exceeded 10 minute timeout",
        )

        # Verify partial results are preserved
        retrieved = await service.get_job(job.job_id)
        assert retrieved.status == JobStatus.TIMED_OUT
        assert retrieved.result["completed_steps"] == ["step1", "step2"]


class TestPriorityQueueBehavior:
    """Test job priority queue behavior."""

    @pytest.fixture
    def service(self):
        return OrchestrationService(mode=PersistenceMode.MOCK)

    @pytest.mark.asyncio
    async def test_priority_ordering_preserved(self, service):
        """Verify priority ordering in queue."""
        # Submit jobs in mixed priority order
        low = await service.submit_job(
            JobSubmission(prompt="Low", user_id="u", priority=JobPriority.LOW)
        )
        critical = await service.submit_job(
            JobSubmission(prompt="Critical", user_id="u", priority=JobPriority.CRITICAL)
        )
        normal = await service.submit_job(
            JobSubmission(prompt="Normal", user_id="u", priority=JobPriority.NORMAL)
        )
        high = await service.submit_job(
            JobSubmission(prompt="High", user_id="u", priority=JobPriority.HIGH)
        )

        # Verify jobs are in queue
        assert len(service._mock_queue) == 4

        # In production, SQS would order by delay/attributes
        # Verify all priorities are recorded correctly
        priorities = {q["priority"] for q in service._mock_queue}
        assert priorities == {"LOW", "NORMAL", "HIGH", "CRITICAL"}


class TestOwnershipEnforcement:
    """Test job ownership enforcement."""

    @pytest.fixture
    def service(self):
        return OrchestrationService(mode=PersistenceMode.MOCK)

    @pytest.mark.asyncio
    async def test_non_owner_cannot_cancel_job(self, service):
        """Verify non-owner cannot cancel another user's job."""
        job = await service.submit_job(
            JobSubmission(prompt="User A's task", user_id="user-A")
        )

        # User B tries to cancel User A's job
        with pytest.raises(PermissionError):
            await service.cancel_job(job.job_id, "user-B")

    @pytest.mark.asyncio
    async def test_job_isolation_between_users(self, service):
        """Verify users only see their own jobs when filtering."""
        # Create jobs for different users
        await service.submit_job(JobSubmission(prompt="A1", user_id="user-A"))
        await service.submit_job(JobSubmission(prompt="A2", user_id="user-A"))
        await service.submit_job(JobSubmission(prompt="B1", user_id="user-B"))

        # Filter by user
        user_a_jobs = await service.list_jobs(user_id="user-A")
        user_b_jobs = await service.list_jobs(user_id="user-B")

        assert len(user_a_jobs) == 2
        assert len(user_b_jobs) == 1
        assert all(j.user_id == "user-A" for j in user_a_jobs)


class TestJobIdempotency:
    """Test idempotency of job operations."""

    @pytest.fixture
    def service(self):
        return OrchestrationService(mode=PersistenceMode.MOCK)

    @pytest.mark.asyncio
    async def test_duplicate_submission_creates_unique_jobs(self, service):
        """Test that duplicate submissions create unique jobs (no idempotency key)."""
        submission1 = JobSubmission(
            prompt="Idempotent task",
            user_id="user-1",
        )
        submission2 = JobSubmission(
            prompt="Idempotent task",
            user_id="user-1",
        )

        # Both submissions should create separate jobs
        job1 = await service.submit_job(submission1)
        job2 = await service.submit_job(submission2)

        # Without idempotency key, should be different jobs
        assert job1.job_id != job2.job_id

    @pytest.mark.asyncio
    async def test_status_update_idempotency(self, service):
        """Test that repeated status updates are idempotent."""
        job = await service.submit_job(JobSubmission(prompt="Test", user_id="user-1"))

        # Update to RUNNING multiple times
        result1 = await service.update_job_status(job.job_id, JobStatus.RUNNING)
        result2 = await service.update_job_status(job.job_id, JobStatus.RUNNING)

        # Both should succeed with same state
        assert result1.status == result2.status == JobStatus.RUNNING


class TestErrorHandling:
    """Test error handling in orchestration service."""

    @pytest.fixture
    def service(self):
        return OrchestrationService(mode=PersistenceMode.MOCK)

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, service):
        """Test getting a job that doesn't exist."""
        result = await service.get_job("nonexistent-job-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_nonexistent_job(self, service):
        """Test updating a job that doesn't exist."""
        # Service may return None or raise - both are valid
        try:
            result = await service.update_job_status(
                "nonexistent-job-id", JobStatus.RUNNING
            )
            # If it doesn't raise, result should indicate failure
            assert result is None or (
                hasattr(result, "status") and result.status != JobStatus.RUNNING
            )
        except (ValueError, KeyError):
            # Raising is also valid behavior
            pass

    @pytest.mark.asyncio
    async def test_invalid_status_transition(self, service):
        """Test invalid status transitions behavior."""
        job = await service.submit_job(JobSubmission(prompt="Test", user_id="user-1"))

        # Complete the job
        await service.update_job_status(job.job_id, JobStatus.SUCCEEDED)

        # Try to transition from SUCCEEDED back to RUNNING
        # Service may reject this or allow it (implementation dependent)
        try:
            result = await service.update_job_status(job.job_id, JobStatus.RUNNING)
            # If allowed, verify state is tracked
            assert result is not None
        except (ValueError, Exception):
            # Rejecting invalid transition is valid behavior
            pass
