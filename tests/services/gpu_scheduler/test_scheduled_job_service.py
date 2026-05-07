"""Tests for GPU Scheduled Job Service (Phase 5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from src.services.gpu_scheduler.exceptions import ScheduleNotFoundError
from src.services.gpu_scheduler.models import (
    EmbeddingJobConfig,
    GPUJobType,
    GPUScheduledJob,
    ScheduleCreateRequest,
    ScheduledJobStatus,
    ScheduleFrequency,
)
from src.services.gpu_scheduler.scheduled_job_service import GPUScheduledJobService


def _make_schedule_request(
    name: str,
    frequency: ScheduleFrequency,
    timezone: str = "UTC",
    cron_expression: str | None = None,
    start_date: datetime | None = None,
) -> ScheduleCreateRequest:
    """Helper to create schedule request with inline config."""
    return ScheduleCreateRequest(
        name=name,
        job_type=GPUJobType.EMBEDDING_GENERATION,
        config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
        frequency=frequency,
        timezone=timezone,
        cron_expression=cron_expression,
        start_date=start_date,
    )


class TestGPUScheduledJobService:
    """Tests for scheduled job CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
        sample_schedule_request: ScheduleCreateRequest,
    ):
        """Test creating a new scheduled job."""
        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_schedule_request,
        )

        assert schedule is not None
        assert schedule.schedule_id.startswith("sch-")
        assert schedule.organization_id == "org-test-123"
        assert schedule.user_id == "user-test-456"
        assert schedule.name == sample_schedule_request.name
        assert schedule.frequency == sample_schedule_request.frequency
        assert schedule.status == ScheduledJobStatus.ACTIVE
        assert schedule.next_run_at is not None

    @pytest.mark.asyncio
    async def test_get_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
        sample_schedule_request: ScheduleCreateRequest,
    ):
        """Test retrieving a schedule by ID."""
        # Create schedule first
        created = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_schedule_request,
        )

        # Retrieve it
        retrieved = await scheduled_job_service.get_schedule(
            organization_id="org-test-123",
            schedule_id=created.schedule_id,
        )

        assert retrieved is not None
        assert retrieved.schedule_id == created.schedule_id
        assert retrieved.name == created.name

    @pytest.mark.asyncio
    async def test_get_schedule_not_found(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test error when schedule not found."""
        with pytest.raises(ScheduleNotFoundError):
            await scheduled_job_service.get_schedule(
                organization_id="org-test-123",
                schedule_id="nonexistent-id",
            )

    @pytest.mark.asyncio
    async def test_pause_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
        sample_schedule_request: ScheduleCreateRequest,
    ):
        """Test pausing an active schedule."""
        # Create schedule
        created = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_schedule_request,
        )

        # Pause it
        paused = await scheduled_job_service.pause_schedule(
            organization_id="org-test-123",
            schedule_id=created.schedule_id,
        )

        assert paused.status == ScheduledJobStatus.PAUSED

    @pytest.mark.asyncio
    async def test_resume_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
        sample_schedule_request: ScheduleCreateRequest,
    ):
        """Test resuming a paused schedule."""
        # Create and pause schedule
        created = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_schedule_request,
        )
        await scheduled_job_service.pause_schedule(
            organization_id="org-test-123",
            schedule_id=created.schedule_id,
        )

        # Resume it
        resumed = await scheduled_job_service.resume_schedule(
            organization_id="org-test-123",
            schedule_id=created.schedule_id,
        )

        assert resumed.status == ScheduledJobStatus.ACTIVE
        assert resumed.next_run_at is not None

    @pytest.mark.asyncio
    async def test_disable_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
        sample_schedule_request: ScheduleCreateRequest,
    ):
        """Test disabling a schedule."""
        # Create schedule
        created = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_schedule_request,
        )

        # Disable it
        disabled = await scheduled_job_service.disable_schedule(
            organization_id="org-test-123",
            schedule_id=created.schedule_id,
        )

        assert disabled.status == ScheduledJobStatus.DISABLED

    @pytest.mark.asyncio
    async def test_delete_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
        sample_schedule_request: ScheduleCreateRequest,
    ):
        """Test deleting a schedule."""
        # Create schedule
        created = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=sample_schedule_request,
        )

        # Delete it
        result = await scheduled_job_service.delete_schedule(
            organization_id="org-test-123",
            schedule_id=created.schedule_id,
        )

        assert result is True

        # Verify it's gone
        with pytest.raises(ScheduleNotFoundError):
            await scheduled_job_service.get_schedule(
                organization_id="org-test-123",
                schedule_id=created.schedule_id,
            )

    @pytest.mark.asyncio
    async def test_list_schedules(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test listing schedules."""
        # Create multiple schedules
        for i in range(3):
            request = _make_schedule_request(f"Schedule {i}", ScheduleFrequency.DAILY)
            await scheduled_job_service.create_schedule(
                organization_id="org-test-123",
                user_id="user-test-456",
                request=request,
            )

        # List all
        schedules = await scheduled_job_service.list_schedules(
            organization_id="org-test-123",
        )

        assert len(schedules) == 3

    @pytest.mark.asyncio
    async def test_list_schedules_by_status(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test listing schedules filtered by status."""
        # Create and pause a schedule
        request = _make_schedule_request("Schedule 1", ScheduleFrequency.DAILY)
        created = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )
        await scheduled_job_service.pause_schedule(
            organization_id="org-test-123",
            schedule_id=created.schedule_id,
        )

        # Create an active schedule
        request2 = _make_schedule_request("Schedule 2", ScheduleFrequency.DAILY)
        await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request2,
        )

        # List only active
        active_schedules = await scheduled_job_service.list_schedules(
            organization_id="org-test-123",
            status=ScheduledJobStatus.ACTIVE,
        )

        assert len(active_schedules) == 1


class TestScheduleFrequencies:
    """Tests for different schedule frequencies."""

    @pytest.mark.asyncio
    async def test_hourly_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test hourly schedule calculates next run correctly."""
        request = _make_schedule_request("Hourly Job", ScheduleFrequency.HOURLY)

        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        # Next run should be within the next hour
        now = datetime.now(timezone.utc)
        assert schedule.next_run_at is not None
        assert schedule.next_run_at <= now + timedelta(hours=1)

    @pytest.mark.asyncio
    async def test_daily_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test daily schedule calculates next run correctly."""
        request = _make_schedule_request("Daily Job", ScheduleFrequency.DAILY)

        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        # Next run should be within the next 24 hours
        now = datetime.now(timezone.utc)
        assert schedule.next_run_at is not None
        assert schedule.next_run_at <= now + timedelta(days=1)

    @pytest.mark.asyncio
    async def test_weekly_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test weekly schedule calculates next run correctly."""
        request = _make_schedule_request("Weekly Job", ScheduleFrequency.WEEKLY)

        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        # Next run should be within the next week
        now = datetime.now(timezone.utc)
        assert schedule.next_run_at is not None
        assert schedule.next_run_at <= now + timedelta(weeks=1)

    @pytest.mark.asyncio
    async def test_custom_cron_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test custom cron expression schedule."""
        request = _make_schedule_request(
            "Custom Cron Job",
            ScheduleFrequency.CUSTOM,
            cron_expression="0 2 * * *",  # Every day at 2 AM
        )

        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        assert schedule.cron_expression == "0 2 * * *"
        assert schedule.next_run_at is not None

    @pytest.mark.asyncio
    async def test_once_schedule(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test one-time schedule."""
        future_time = datetime.now(timezone.utc) + timedelta(hours=2)
        request = _make_schedule_request(
            "One-Time Job",
            ScheduleFrequency.ONCE,
            start_date=future_time,
        )

        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        assert schedule.frequency == ScheduleFrequency.ONCE
        assert schedule.next_run_at is not None


class TestScheduleDispatch:
    """Tests for schedule dispatch functionality."""

    @pytest.mark.asyncio
    async def test_get_due_schedules(
        self,
        scheduled_job_service: GPUScheduledJobService,
        mock_dynamodb: dict[str, Any],
    ):
        """Test finding schedules that are due for execution."""
        # Create a schedule with next_run in the past by directly inserting
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        schedule = GPUScheduledJob(
            schedule_id="sch-due-test-123",
            organization_id="org-test-123",
            user_id="user-test-456",
            name="Due Job",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            frequency=ScheduleFrequency.DAILY,
            status=ScheduledJobStatus.ACTIVE,
            next_run_at=past_time,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )

        # Insert directly into DynamoDB
        mock_dynamodb["schedules_table"].put_item(Item=schedule.to_dynamodb_item())

        # Get due schedules
        due_schedules = await scheduled_job_service.get_due_schedules()

        assert len(due_schedules) >= 1
        assert any(s.schedule_id == "sch-due-test-123" for s in due_schedules)

    @pytest.mark.asyncio
    async def test_record_execution(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test recording successful execution updates schedule."""
        request = _make_schedule_request("Test Job", ScheduleFrequency.DAILY)
        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        # Record execution
        updated = await scheduled_job_service.record_execution(
            organization_id="org-test-123",
            schedule_id=schedule.schedule_id,
            job_id="job-123",
            success=True,
        )

        assert updated.run_count == 1
        assert updated.last_job_id == "job-123"
        assert updated.last_run_at is not None
        assert updated.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_record_failure_increments_count(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test recording failure increments failure count."""
        request = _make_schedule_request("Test Job", ScheduleFrequency.DAILY)
        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        # Record failure
        updated = await scheduled_job_service.record_execution(
            organization_id="org-test-123",
            schedule_id=schedule.schedule_id,
            job_id="job-123",
            success=False,
        )

        assert updated.run_count == 1
        assert updated.failure_count == 1
        assert updated.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_auto_pause_after_consecutive_failures(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test schedule auto-pauses after 3 consecutive failures."""
        request = _make_schedule_request("Failing Job", ScheduleFrequency.DAILY)
        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        # Record 3 consecutive failures
        for i in range(3):
            updated = await scheduled_job_service.record_execution(
                organization_id="org-test-123",
                schedule_id=schedule.schedule_id,
                job_id=f"job-{i}",
                success=False,
            )

        # Should be auto-paused
        assert updated.status == ScheduledJobStatus.PAUSED
        assert updated.consecutive_failures == 3


class TestTimezoneSupport:
    """Tests for timezone handling."""

    @pytest.mark.asyncio
    async def test_schedule_with_timezone(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test schedule respects timezone."""
        request = _make_schedule_request(
            "Timezone Job",
            ScheduleFrequency.DAILY,
            timezone="America/New_York",
        )

        schedule = await scheduled_job_service.create_schedule(
            organization_id="org-test-123",
            user_id="user-test-456",
            request=request,
        )

        assert schedule.timezone == "America/New_York"
        assert schedule.next_run_at is not None

    @pytest.mark.asyncio
    async def test_invalid_timezone_rejected(
        self,
        scheduled_job_service: GPUScheduledJobService,
    ):
        """Test invalid timezone is rejected."""
        with pytest.raises(ValueError):
            _make_schedule_request(
                "Invalid TZ Job",
                ScheduleFrequency.DAILY,
                timezone="Invalid/Timezone",
            )


class TestScheduleValidation:
    """Tests for schedule request validation."""

    def test_cron_required_for_custom_frequency(self):
        """Test cron expression required for custom frequency."""
        request = ScheduleCreateRequest(
            name="Custom Job",
            job_type=GPUJobType.EMBEDDING_GENERATION,
            config=EmbeddingJobConfig(repository_id="test-repo", branch="main"),
            frequency=ScheduleFrequency.CUSTOM,
            timezone="UTC",
            # Missing cron_expression for CUSTOM frequency
        )
        errors = request.validate_config()
        assert "cron_expression required for custom frequency" in errors

    def test_either_template_or_inline_config_required(self):
        """Test either template_id or inline config must be provided."""
        request = ScheduleCreateRequest(
            name="No Config Job",
            frequency=ScheduleFrequency.DAILY,
            timezone="UTC",
            # Missing both template_id and inline config
        )
        errors = request.validate_config()
        assert len(errors) > 0
