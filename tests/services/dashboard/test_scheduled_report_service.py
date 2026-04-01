"""Tests for Scheduled Report Service (ADR-064 Phase 3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.services.dashboard import (
    DayOfWeek,
    ReportFormat,
    ScheduleConfig,
    ScheduledReportCreate,
    ScheduledReportService,
    ScheduledReportUpdate,
    ScheduleFrequency,
    get_scheduled_report_service,
)


@pytest.fixture
def scheduled_report_service():
    """Create a fresh ScheduledReportService instance."""
    return ScheduledReportService()


@pytest.fixture
def sample_schedule_config():
    """Create a sample schedule configuration."""
    return ScheduleConfig(
        frequency=ScheduleFrequency.WEEKLY,
        time_utc="09:00",
        day_of_week=DayOfWeek.MONDAY,
        timezone="UTC",
    )


@pytest.fixture
def sample_schedule_create(sample_schedule_config):
    """Create a sample ScheduledReportCreate request."""
    return ScheduledReportCreate(
        name="Weekly Security Report",
        description="Summary of weekly security metrics",
        recipients=["security@example.com", "manager@example.com"],
        schedule=sample_schedule_config,
        format=ReportFormat.HTML_EMAIL,
        subject_template="{dashboard_name} - {report_name} Report",
    )


class TestScheduleConfigValidation:
    """Tests for ScheduleConfig validation."""

    def test_valid_daily_schedule(self):
        """Test valid daily schedule creates successfully."""
        config = ScheduleConfig(
            frequency=ScheduleFrequency.DAILY,
            time_utc="14:30",
            timezone="America/New_York",
        )
        assert config.frequency == ScheduleFrequency.DAILY
        assert config.time_utc == "14:30"

    def test_valid_weekly_schedule(self):
        """Test valid weekly schedule requires day_of_week."""
        config = ScheduleConfig(
            frequency=ScheduleFrequency.WEEKLY,
            time_utc="09:00",
            day_of_week=DayOfWeek.FRIDAY,
        )
        assert config.day_of_week == DayOfWeek.FRIDAY

    def test_weekly_schedule_missing_day_of_week(self):
        """Test weekly schedule without day_of_week fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduleConfig(
                frequency=ScheduleFrequency.WEEKLY,
                time_utc="09:00",
                # Missing day_of_week
            )
        assert "day_of_week required" in str(exc_info.value)

    def test_valid_monthly_schedule(self):
        """Test valid monthly schedule requires day_of_month."""
        config = ScheduleConfig(
            frequency=ScheduleFrequency.MONTHLY,
            time_utc="08:00",
            day_of_month=15,
        )
        assert config.day_of_month == 15

    def test_monthly_schedule_missing_day_of_month(self):
        """Test monthly schedule without day_of_month fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduleConfig(
                frequency=ScheduleFrequency.MONTHLY,
                time_utc="09:00",
                # Missing day_of_month
            )
        assert "day_of_month required" in str(exc_info.value)

    def test_invalid_time_format(self):
        """Test invalid time format fails validation."""
        with pytest.raises(ValidationError):
            ScheduleConfig(
                frequency=ScheduleFrequency.DAILY,
                time_utc="25:00",  # Invalid hour
            )

    def test_day_of_month_bounds(self):
        """Test day_of_month validation enforces bounds."""
        # Below minimum
        with pytest.raises(ValidationError):
            ScheduleConfig(
                frequency=ScheduleFrequency.MONTHLY,
                time_utc="09:00",
                day_of_month=0,
            )

        # Above maximum (limited to 28 for all months)
        with pytest.raises(ValidationError):
            ScheduleConfig(
                frequency=ScheduleFrequency.MONTHLY,
                time_utc="09:00",
                day_of_month=31,
            )


class TestScheduledReportCreate:
    """Tests for ScheduledReportCreate validation."""

    def test_valid_create_request(self, sample_schedule_create):
        """Test valid create request validates successfully."""
        assert sample_schedule_create.name == "Weekly Security Report"
        assert len(sample_schedule_create.recipients) == 2
        assert sample_schedule_create.format == ReportFormat.HTML_EMAIL

    def test_name_length_validation(self, sample_schedule_config):
        """Test name length validation."""
        # Too short
        with pytest.raises(ValidationError):
            ScheduledReportCreate(
                name="",  # Empty name
                recipients=["test@example.com"],
                schedule=sample_schedule_config,
            )

        # Too long
        with pytest.raises(ValidationError):
            ScheduledReportCreate(
                name="x" * 101,  # Over 100 chars
                recipients=["test@example.com"],
                schedule=sample_schedule_config,
            )

    def test_recipients_required(self, sample_schedule_config):
        """Test at least one recipient is required."""
        with pytest.raises(ValidationError):
            ScheduledReportCreate(
                name="Test Report",
                recipients=[],  # Empty recipients
                schedule=sample_schedule_config,
            )

    def test_recipients_max_limit(self, sample_schedule_config):
        """Test maximum recipients limit."""
        with pytest.raises(ValidationError):
            ScheduledReportCreate(
                name="Test Report",
                recipients=[f"user{i}@example.com" for i in range(25)],  # Over 20
                schedule=sample_schedule_config,
            )


class TestCreateSchedule:
    """Tests for schedule creation."""

    def test_create_schedule_success(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test successful schedule creation."""
        report = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        assert report.report_id.startswith("rpt-")
        assert report.dashboard_id == "dash-001"
        assert report.user_id == "user-123"
        assert report.name == "Weekly Security Report"
        assert report.is_active is True
        assert report.send_count == 0
        assert report.next_run_at is not None
        assert isinstance(report.created_at, datetime)

    def test_create_schedule_dashboard_limit(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test schedule creation fails when dashboard limit exceeded."""
        # Create max schedules for one dashboard
        for i in range(ScheduledReportService.MAX_SCHEDULES_PER_DASHBOARD):
            schedule_data = sample_schedule_create.model_copy()
            schedule_data.name = f"Report {i}"
            scheduled_report_service.create_schedule(
                dashboard_id="dash-001",
                user_id="user-123",
                schedule_data=schedule_data,
            )

        # Attempt to create one more
        with pytest.raises(ValueError) as exc_info:
            scheduled_report_service.create_schedule(
                dashboard_id="dash-001",
                user_id="user-123",
                schedule_data=sample_schedule_create,
            )

        assert "Maximum 5 schedules per dashboard" in str(exc_info.value)

    def test_create_schedule_user_limit(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test schedule creation fails when user limit exceeded."""
        # Create max schedules for user across dashboards
        for i in range(ScheduledReportService.MAX_SCHEDULES_PER_USER):
            schedule_data = sample_schedule_create.model_copy()
            schedule_data.name = f"Report {i}"
            scheduled_report_service.create_schedule(
                dashboard_id=f"dash-{i:03d}",
                user_id="user-123",
                schedule_data=schedule_data,
            )

        # Attempt to create one more
        with pytest.raises(ValueError) as exc_info:
            scheduled_report_service.create_schedule(
                dashboard_id="dash-999",
                user_id="user-123",
                schedule_data=sample_schedule_create,
            )

        assert "Maximum 20 schedules per user" in str(exc_info.value)


class TestGetSchedule:
    """Tests for schedule retrieval."""

    def test_get_schedule_success(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test successful schedule retrieval by owner."""
        created = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        report = scheduled_report_service.get_schedule(
            report_id=created.report_id,
            user_id="user-123",
        )

        assert report.report_id == created.report_id
        assert report.name == "Weekly Security Report"

    def test_get_schedule_not_found(
        self,
        scheduled_report_service: ScheduledReportService,
    ):
        """Test schedule retrieval when not found."""
        with pytest.raises(KeyError) as exc_info:
            scheduled_report_service.get_schedule(
                report_id="rpt-nonexistent",
                user_id="user-123",
            )

        assert "not found" in str(exc_info.value)

    def test_get_schedule_access_denied(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test schedule retrieval access denied for non-owner."""
        created = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        with pytest.raises(PermissionError) as exc_info:
            scheduled_report_service.get_schedule(
                report_id=created.report_id,
                user_id="user-456",  # Different user
            )

        assert "Access denied" in str(exc_info.value)


class TestUpdateSchedule:
    """Tests for schedule updates."""

    def test_update_schedule_success(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test successful schedule update."""
        created = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        updates = ScheduledReportUpdate(
            name="Updated Report Name",
            is_active=False,
        )

        updated = scheduled_report_service.update_schedule(
            report_id=created.report_id,
            user_id="user-123",
            updates=updates,
        )

        assert updated.name == "Updated Report Name"
        assert updated.is_active is False

    def test_update_schedule_not_found(
        self,
        scheduled_report_service: ScheduledReportService,
    ):
        """Test schedule update when not found."""
        with pytest.raises(KeyError):
            scheduled_report_service.update_schedule(
                report_id="rpt-nonexistent",
                user_id="user-123",
                updates=ScheduledReportUpdate(name="New Name"),
            )

    def test_update_schedule_not_owner(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test schedule update by non-owner fails."""
        created = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        with pytest.raises(PermissionError) as exc_info:
            scheduled_report_service.update_schedule(
                report_id=created.report_id,
                user_id="user-456",  # Different user
                updates=ScheduledReportUpdate(name="New Name"),
            )

        assert "Only the owner" in str(exc_info.value)


class TestDeleteSchedule:
    """Tests for schedule deletion."""

    def test_delete_schedule_success(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test successful schedule deletion."""
        created = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        scheduled_report_service.delete_schedule(
            report_id=created.report_id,
            user_id="user-123",
        )

        # Verify deletion
        with pytest.raises(KeyError):
            scheduled_report_service.get_schedule(
                report_id=created.report_id,
                user_id="user-123",
            )

    def test_delete_schedule_not_found(
        self,
        scheduled_report_service: ScheduledReportService,
    ):
        """Test schedule deletion when not found."""
        with pytest.raises(KeyError):
            scheduled_report_service.delete_schedule(
                report_id="rpt-nonexistent",
                user_id="user-123",
            )

    def test_delete_schedule_not_owner(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test schedule deletion by non-owner fails."""
        created = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        with pytest.raises(PermissionError) as exc_info:
            scheduled_report_service.delete_schedule(
                report_id=created.report_id,
                user_id="user-456",  # Different user
            )

        assert "Only the owner" in str(exc_info.value)


class TestListSchedules:
    """Tests for listing schedules."""

    def test_list_schedules_empty(
        self,
        scheduled_report_service: ScheduledReportService,
    ):
        """Test listing schedules when none exist."""
        schedules = scheduled_report_service.list_schedules(
            dashboard_id="dash-001",
            user_id="user-123",
        )
        assert schedules == []

    def test_list_schedules_for_dashboard(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test listing schedules for a dashboard."""
        # Create schedules for dashboard
        for i in range(3):
            schedule_data = sample_schedule_create.model_copy()
            schedule_data.name = f"Report {i}"
            scheduled_report_service.create_schedule(
                dashboard_id="dash-001",
                user_id="user-123",
                schedule_data=schedule_data,
            )

        schedules = scheduled_report_service.list_schedules(
            dashboard_id="dash-001",
            user_id="user-123",
        )

        assert len(schedules) == 3

    def test_list_schedules_filters_by_user(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test listing schedules only returns user's schedules."""
        # Create schedule for user-123
        scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        # User-456 sees no schedules
        schedules = scheduled_report_service.list_schedules(
            dashboard_id="dash-001",
            user_id="user-456",
        )

        assert len(schedules) == 0

    def test_list_user_schedules(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test listing all schedules for a user across dashboards."""
        # Create schedules across dashboards
        for i in range(3):
            schedule_data = sample_schedule_create.model_copy()
            schedule_data.name = f"Report {i}"
            scheduled_report_service.create_schedule(
                dashboard_id=f"dash-{i:03d}",
                user_id="user-123",
                schedule_data=schedule_data,
            )

        schedules = scheduled_report_service.list_user_schedules(user_id="user-123")

        assert len(schedules) == 3


class TestSendReport:
    """Tests for manual report delivery."""

    def test_send_report_now_success(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test manual report delivery."""
        created = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        result = scheduled_report_service.send_report_now(
            report_id=created.report_id,
            user_id="user-123",
        )

        assert result.success is True
        assert result.report_id == created.report_id
        assert len(result.recipients_sent) == 2
        assert result.sent_at is not None

        # Check stats updated
        report = scheduled_report_service.get_schedule(
            report_id=created.report_id,
            user_id="user-123",
        )
        assert report.send_count == 1
        assert report.last_sent_at is not None


class TestGetDueReports:
    """Tests for getting due reports."""

    def test_get_due_reports(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_create: ScheduledReportCreate,
    ):
        """Test getting reports due for delivery."""
        created = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=sample_schedule_create,
        )

        # Manually set next_run_at to past
        created.next_run_at = datetime(2020, 1, 1, tzinfo=timezone.utc)

        due_reports = scheduled_report_service.get_due_reports()

        assert len(due_reports) == 1
        assert due_reports[0].report_id == created.report_id


class TestNextRunCalculation:
    """Tests for next run time calculation."""

    def test_daily_next_run(
        self,
        scheduled_report_service: ScheduledReportService,
    ):
        """Test daily schedule next run calculation."""
        config = ScheduleConfig(
            frequency=ScheduleFrequency.DAILY,
            time_utc="09:00",
        )

        next_run = scheduled_report_service._calculate_next_run(config)

        assert next_run is not None
        assert next_run.hour == 9
        assert next_run.minute == 0

    def test_weekly_next_run(
        self,
        scheduled_report_service: ScheduledReportService,
    ):
        """Test weekly schedule next run calculation."""
        config = ScheduleConfig(
            frequency=ScheduleFrequency.WEEKLY,
            time_utc="14:30",
            day_of_week=DayOfWeek.WEDNESDAY,
        )

        next_run = scheduled_report_service._calculate_next_run(config)

        assert next_run is not None
        assert next_run.weekday() == 2  # Wednesday

    def test_monthly_next_run(
        self,
        scheduled_report_service: ScheduledReportService,
    ):
        """Test monthly schedule next run calculation."""
        config = ScheduleConfig(
            frequency=ScheduleFrequency.MONTHLY,
            time_utc="08:00",
            day_of_month=15,
        )

        next_run = scheduled_report_service._calculate_next_run(config)

        assert next_run is not None
        assert next_run.day == 15


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_scheduled_report_service_singleton(self):
        """Test get_scheduled_report_service returns same instance."""
        # Reset singleton for test
        import src.services.dashboard.scheduled_report_service as module

        module._service_instance = None

        service1 = get_scheduled_report_service()
        service2 = get_scheduled_report_service()

        assert service1 is service2


class TestAllFrequencies:
    """Tests for all schedule frequency types."""

    @pytest.mark.parametrize(
        "frequency,extra_config",
        [
            (ScheduleFrequency.DAILY, {}),
            (ScheduleFrequency.WEEKLY, {"day_of_week": DayOfWeek.MONDAY}),
            (ScheduleFrequency.BIWEEKLY, {"day_of_week": DayOfWeek.FRIDAY}),
            (ScheduleFrequency.MONTHLY, {"day_of_month": 1}),
        ],
    )
    def test_all_frequencies_work(
        self,
        scheduled_report_service: ScheduledReportService,
        frequency: ScheduleFrequency,
        extra_config: dict,
    ):
        """Test all frequency types can create schedules."""
        config = ScheduleConfig(
            frequency=frequency,
            time_utc="09:00",
            **extra_config,
        )

        schedule_data = ScheduledReportCreate(
            name=f"Test {frequency.value}",
            recipients=["test@example.com"],
            schedule=config,
        )

        report = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=schedule_data,
        )

        assert report.report_id.startswith("rpt-")
        assert report.schedule.frequency == frequency


class TestAllFormats:
    """Tests for all report format types."""

    @pytest.mark.parametrize(
        "format_type",
        [ReportFormat.PDF, ReportFormat.HTML_EMAIL, ReportFormat.CSV],
    )
    def test_all_formats_work(
        self,
        scheduled_report_service: ScheduledReportService,
        sample_schedule_config: ScheduleConfig,
        format_type: ReportFormat,
    ):
        """Test all report formats can be used."""
        schedule_data = ScheduledReportCreate(
            name=f"Test {format_type.value}",
            recipients=["test@example.com"],
            schedule=sample_schedule_config,
            format=format_type,
        )

        report = scheduled_report_service.create_schedule(
            dashboard_id="dash-001",
            user_id="user-123",
            schedule_data=schedule_data,
        )

        assert report.format == format_type
