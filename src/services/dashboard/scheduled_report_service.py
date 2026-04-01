"""Scheduled Reports Service.

Enables users to schedule automated dashboard report delivery via email.
Implements ADR-064 Phase 3 scheduled reports functionality.

Features:
- Configurable report schedules (daily, weekly, monthly)
- Multiple recipients per schedule
- Dashboard snapshot rendering
- Email delivery via SES
- Schedule management with CRUD operations
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, model_validator

logger = logging.getLogger(__name__)


class ScheduleFrequency(str, Enum):
    """Report delivery frequency options."""

    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class ReportFormat(str, Enum):
    """Report output format options."""

    PDF = "pdf"
    HTML_EMAIL = "html_email"
    CSV = "csv"  # For table-heavy dashboards


class DayOfWeek(str, Enum):
    """Days of the week for weekly schedules."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class ScheduleConfig(BaseModel):
    """Configuration for report delivery schedule."""

    frequency: ScheduleFrequency = Field(..., description="How often to send reports")
    time_utc: str = Field(
        default="09:00",
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Time to send report in UTC (HH:MM format)",
    )
    day_of_week: DayOfWeek | None = Field(
        default=None,
        description="Day of week for weekly/biweekly schedules",
    )
    day_of_month: int | None = Field(
        default=None,
        ge=1,
        le=28,
        description="Day of month for monthly schedules (1-28)",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for schedule (for display purposes)",
    )

    @model_validator(mode="after")
    def validate_schedule_config(self) -> "ScheduleConfig":
        """Validate schedule configuration based on frequency."""
        if self.frequency in [ScheduleFrequency.WEEKLY, ScheduleFrequency.BIWEEKLY]:
            if self.day_of_week is None:
                raise ValueError("day_of_week required for weekly/biweekly schedules")
        if self.frequency == ScheduleFrequency.MONTHLY:
            if self.day_of_month is None:
                raise ValueError("day_of_month required for monthly schedules")
        return self


class ScheduledReportCreate(BaseModel):
    """Request model for creating a scheduled report."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the scheduled report",
    )
    description: str = Field(
        default="",
        max_length=500,
        description="Description of the report",
    )
    recipients: list[EmailStr] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Email addresses to receive the report",
    )
    schedule: ScheduleConfig = Field(..., description="Schedule configuration")
    format: ReportFormat = Field(
        default=ReportFormat.HTML_EMAIL,
        description="Report output format",
    )
    include_widgets: list[str] | None = Field(
        default=None,
        description="Widget IDs to include (None = all widgets)",
    )
    subject_template: str = Field(
        default="{dashboard_name} - {report_name} Report",
        max_length=200,
        description="Email subject template",
    )


class ScheduledReportUpdate(BaseModel):
    """Request model for updating a scheduled report."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    recipients: list[EmailStr] | None = Field(default=None, min_length=1, max_length=20)
    schedule: ScheduleConfig | None = None
    format: ReportFormat | None = None
    include_widgets: list[str] | None = None
    subject_template: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class ScheduledReport(BaseModel):
    """Full scheduled report model."""

    report_id: str = Field(..., description="Unique report schedule identifier")
    dashboard_id: str = Field(..., description="Associated dashboard ID")
    user_id: str = Field(..., description="Owner user ID")
    name: str = Field(..., description="Report name")
    description: str = Field(default="", description="Report description")
    recipients: list[str] = Field(..., description="Recipient email addresses")
    schedule: ScheduleConfig = Field(..., description="Schedule configuration")
    format: ReportFormat = Field(..., description="Report output format")
    include_widgets: list[str] | None = Field(
        default=None,
        description="Widget IDs to include",
    )
    subject_template: str = Field(..., description="Email subject template")
    is_active: bool = Field(default=True, description="Whether schedule is active")
    last_sent_at: datetime | None = Field(
        default=None,
        description="Last successful send timestamp",
    )
    next_run_at: datetime | None = Field(
        default=None,
        description="Next scheduled run timestamp",
    )
    send_count: int = Field(default=0, description="Total reports sent")
    failure_count: int = Field(default=0, description="Total send failures")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class ReportDeliveryResult(BaseModel):
    """Result of a report delivery attempt."""

    success: bool = Field(..., description="Whether delivery succeeded")
    report_id: str = Field(..., description="Report schedule ID")
    recipients_sent: list[str] = Field(
        default_factory=list,
        description="Recipients successfully sent to",
    )
    recipients_failed: list[str] = Field(
        default_factory=list,
        description="Recipients that failed",
    )
    error: str | None = Field(default=None, description="Error message if failed")
    sent_at: datetime = Field(..., description="Delivery attempt timestamp")


class ScheduledReportService:
    """Service for managing scheduled dashboard reports.

    Provides CRUD operations, schedule management, and report delivery
    for automated dashboard report generation and email delivery.
    """

    # Maximum schedules per dashboard
    MAX_SCHEDULES_PER_DASHBOARD = 5
    # Maximum schedules per user across all dashboards
    MAX_SCHEDULES_PER_USER = 20

    def __init__(self) -> None:
        """Initialize the scheduled report service."""
        self._reports: dict[str, ScheduledReport] = {}
        self._dashboard_reports: dict[str, list[str]] = {}
        self._user_reports: dict[str, list[str]] = {}

    def create_schedule(
        self,
        dashboard_id: str,
        user_id: str,
        schedule_data: ScheduledReportCreate,
    ) -> ScheduledReport:
        """Create a new scheduled report.

        Args:
            dashboard_id: Dashboard to generate reports for
            user_id: Owner user ID
            schedule_data: Schedule creation data

        Returns:
            Created ScheduledReport

        Raises:
            ValueError: If limits exceeded or validation fails
        """
        # Check dashboard schedule limit
        dashboard_schedules = self._dashboard_reports.get(dashboard_id, [])
        if len(dashboard_schedules) >= self.MAX_SCHEDULES_PER_DASHBOARD:
            raise ValueError(
                f"Maximum {self.MAX_SCHEDULES_PER_DASHBOARD} schedules per dashboard"
            )

        # Check user schedule limit
        user_schedules = self._user_reports.get(user_id, [])
        if len(user_schedules) >= self.MAX_SCHEDULES_PER_USER:
            raise ValueError(
                f"Maximum {self.MAX_SCHEDULES_PER_USER} schedules per user"
            )

        # Generate report ID
        report_id = f"rpt-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Calculate next run time
        next_run = self._calculate_next_run(schedule_data.schedule)

        report = ScheduledReport(
            report_id=report_id,
            dashboard_id=dashboard_id,
            user_id=user_id,
            name=schedule_data.name,
            description=schedule_data.description,
            recipients=[str(r) for r in schedule_data.recipients],
            schedule=schedule_data.schedule,
            format=schedule_data.format,
            include_widgets=schedule_data.include_widgets,
            subject_template=schedule_data.subject_template,
            is_active=True,
            next_run_at=next_run,
            created_at=now,
            updated_at=now,
        )

        # Store report
        self._reports[report_id] = report
        if dashboard_id not in self._dashboard_reports:
            self._dashboard_reports[dashboard_id] = []
        self._dashboard_reports[dashboard_id].append(report_id)
        if user_id not in self._user_reports:
            self._user_reports[user_id] = []
        self._user_reports[user_id].append(report_id)

        logger.info(
            f"Scheduled report created: {report_id} for dashboard {dashboard_id}"
        )
        return report

    def get_schedule(
        self,
        report_id: str,
        user_id: str,
    ) -> ScheduledReport:
        """Get a scheduled report by ID.

        Args:
            report_id: Report schedule ID
            user_id: Requesting user ID

        Returns:
            ScheduledReport

        Raises:
            KeyError: If report not found
            PermissionError: If user doesn't have access
        """
        report = self._reports.get(report_id)
        if not report:
            raise KeyError(f"Report schedule {report_id} not found")

        if report.user_id != user_id:
            raise PermissionError("Access denied to this report schedule")

        return report

    def update_schedule(
        self,
        report_id: str,
        user_id: str,
        updates: ScheduledReportUpdate,
    ) -> ScheduledReport:
        """Update a scheduled report.

        Args:
            report_id: Report schedule ID
            user_id: Owner user ID
            updates: Update data

        Returns:
            Updated ScheduledReport

        Raises:
            KeyError: If report not found
            PermissionError: If user is not the owner
        """
        report = self._reports.get(report_id)
        if not report:
            raise KeyError(f"Report schedule {report_id} not found")

        if report.user_id != user_id:
            raise PermissionError("Only the owner can update this schedule")

        # Apply updates
        update_data = updates.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                if key == "recipients":
                    setattr(report, key, [str(r) for r in value])
                else:
                    setattr(report, key, value)

        # Recalculate next run if schedule changed
        if updates.schedule:
            report.next_run_at = self._calculate_next_run(report.schedule)

        report.updated_at = datetime.now(timezone.utc)

        logger.info(f"Scheduled report updated: {report_id}")
        return report

    def delete_schedule(
        self,
        report_id: str,
        user_id: str,
    ) -> None:
        """Delete a scheduled report.

        Args:
            report_id: Report schedule ID
            user_id: Owner user ID

        Raises:
            KeyError: If report not found
            PermissionError: If user is not the owner
        """
        report = self._reports.get(report_id)
        if not report:
            raise KeyError(f"Report schedule {report_id} not found")

        if report.user_id != user_id:
            raise PermissionError("Only the owner can delete this schedule")

        # Remove from all indexes
        del self._reports[report_id]
        self._dashboard_reports[report.dashboard_id].remove(report_id)
        self._user_reports[user_id].remove(report_id)

        logger.info(f"Scheduled report deleted: {report_id}")

    def list_schedules(
        self,
        dashboard_id: str,
        user_id: str,
    ) -> list[ScheduledReport]:
        """List scheduled reports for a dashboard.

        Args:
            dashboard_id: Dashboard ID
            user_id: User ID (for permission filtering)

        Returns:
            List of ScheduledReports
        """
        report_ids = self._dashboard_reports.get(dashboard_id, [])
        reports = []

        for report_id in report_ids:
            report = self._reports.get(report_id)
            if report and report.user_id == user_id:
                reports.append(report)

        return reports

    def list_user_schedules(
        self,
        user_id: str,
    ) -> list[ScheduledReport]:
        """List all scheduled reports for a user.

        Args:
            user_id: User ID

        Returns:
            List of ScheduledReports
        """
        report_ids = self._user_reports.get(user_id, [])
        return [self._reports[rid] for rid in report_ids if rid in self._reports]

    def send_report_now(
        self,
        report_id: str,
        user_id: str,
    ) -> ReportDeliveryResult:
        """Manually trigger report delivery.

        Args:
            report_id: Report schedule ID
            user_id: Requesting user ID

        Returns:
            ReportDeliveryResult with delivery status
        """
        report = self.get_schedule(report_id, user_id)

        # Generate and send report (mock implementation)
        result = self._send_report(report)

        # Update report stats
        if result.success:
            report.last_sent_at = result.sent_at
            report.send_count += 1
        else:
            report.failure_count += 1

        return result

    def get_due_reports(self) -> list[ScheduledReport]:
        """Get reports that are due to be sent.

        Returns:
            List of ScheduledReports due for delivery
        """
        now = datetime.now(timezone.utc)
        due_reports = []

        for report in self._reports.values():
            if report.is_active and report.next_run_at and report.next_run_at <= now:
                due_reports.append(report)

        return due_reports

    def _calculate_next_run(self, schedule: ScheduleConfig) -> datetime:
        """Calculate the next scheduled run time.

        Args:
            schedule: Schedule configuration

        Returns:
            Next run datetime in UTC
        """
        import calendar
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        hour, minute = map(int, schedule.time_utc.split(":"))

        # Start with today at the scheduled time
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If already past today's time, move to next occurrence
        if next_run <= now:
            if schedule.frequency == ScheduleFrequency.DAILY:
                next_run += timedelta(days=1)
            elif schedule.frequency == ScheduleFrequency.WEEKLY:
                next_run += timedelta(days=7)
            elif schedule.frequency == ScheduleFrequency.BIWEEKLY:
                next_run += timedelta(days=14)
            elif schedule.frequency == ScheduleFrequency.MONTHLY:
                # Move to next month, handling variable month lengths
                year = next_run.year
                month = next_run.month + 1
                if month > 12:
                    month = 1
                    year += 1
                # Use day 1 temporarily to avoid "day out of range" error
                next_run = next_run.replace(year=year, month=month, day=1)

        # Adjust for day of week (weekly/biweekly)
        if schedule.frequency in [
            ScheduleFrequency.WEEKLY,
            ScheduleFrequency.BIWEEKLY,
        ]:
            if schedule.day_of_week:
                day_map = {
                    DayOfWeek.MONDAY: 0,
                    DayOfWeek.TUESDAY: 1,
                    DayOfWeek.WEDNESDAY: 2,
                    DayOfWeek.THURSDAY: 3,
                    DayOfWeek.FRIDAY: 4,
                    DayOfWeek.SATURDAY: 5,
                    DayOfWeek.SUNDAY: 6,
                }
                target_day = day_map[schedule.day_of_week]
                current_day = next_run.weekday()
                days_ahead = target_day - current_day
                if days_ahead <= 0:
                    days_ahead += 7
                next_run += timedelta(days=days_ahead)

        # Adjust for day of month (monthly)
        if schedule.frequency == ScheduleFrequency.MONTHLY and schedule.day_of_month:
            # Handle months with fewer days than requested
            max_day = calendar.monthrange(next_run.year, next_run.month)[1]
            target_day = min(schedule.day_of_month, max_day)
            next_run = next_run.replace(day=target_day)

        return next_run

    def _send_report(self, report: ScheduledReport) -> ReportDeliveryResult:
        """Send a report to recipients (mock implementation).

        In production, this would:
        1. Render the dashboard to HTML/PDF
        2. Send via SES with proper formatting

        Args:
            report: ScheduledReport to send

        Returns:
            ReportDeliveryResult
        """
        now = datetime.now(timezone.utc)

        # Mock successful delivery
        logger.info(
            f"Sending report {report.report_id} to {len(report.recipients)} recipients"
        )

        return ReportDeliveryResult(
            success=True,
            report_id=report.report_id,
            recipients_sent=report.recipients,
            recipients_failed=[],
            sent_at=now,
        )

    def _advance_schedule(self, report: ScheduledReport) -> None:
        """Advance a report's next_run_at after successful send.

        Args:
            report: ScheduledReport to advance
        """
        report.next_run_at = self._calculate_next_run(report.schedule)


# Singleton instance
_service_instance: ScheduledReportService | None = None


def get_scheduled_report_service() -> ScheduledReportService:
    """Get the scheduled report service singleton.

    Returns:
        ScheduledReportService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = ScheduledReportService()
    return _service_instance
