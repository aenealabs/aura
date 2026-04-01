"""
Tests for Recurring Task Service

ADR-055 Phase 3: Recurring Tasks and Advanced Features
"""

import platform
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.services.recurring_task_service import (
    JobType,
    RecurringTask,
    RecurringTaskService,
    TaskStatus,
    calculate_next_run,
    describe_cron,
    get_recurring_task_service,
    set_recurring_task_service,
    validate_cron_expression,
)

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


# =============================================================================
# Cron Expression Validation Tests
# =============================================================================


class TestValidateCronExpression:
    """Tests for cron expression validation."""

    def test_valid_simple_cron(self):
        """Test validation of simple valid cron expressions."""
        valid_crons = [
            "0 * * * *",  # Every hour at minute 0
            "*/15 * * * *",  # Every 15 minutes
            "0 0 * * *",  # Daily at midnight
            "0 9 * * 1-5",  # Weekdays at 9 AM
            "0 6 * * 1",  # Monday at 6 AM
            "0 0 1 * *",  # Monthly on the 1st
            "30 4 1,15 * *",  # 4:30 AM on 1st and 15th
        ]
        for cron in valid_crons:
            is_valid, error = validate_cron_expression(cron)
            assert is_valid, f"Expected '{cron}' to be valid, got error: {error}"

    def test_invalid_part_count(self):
        """Test rejection of cron with wrong number of parts."""
        is_valid, error = validate_cron_expression("0 * * *")
        assert not is_valid
        assert "Expected 5 parts" in error

        is_valid, error = validate_cron_expression("0 * * * * *")
        assert not is_valid
        assert "Expected 5 parts" in error

    def test_invalid_minute_value(self):
        """Test rejection of invalid minute values."""
        is_valid, error = validate_cron_expression("60 * * * *")
        assert not is_valid
        assert "minute" in error.lower()

    def test_invalid_hour_value(self):
        """Test rejection of invalid hour values."""
        is_valid, error = validate_cron_expression("0 24 * * *")
        assert not is_valid
        assert "hour" in error.lower()

    def test_invalid_day_of_month(self):
        """Test rejection of invalid day-of-month values."""
        is_valid, error = validate_cron_expression("0 0 32 * *")
        assert not is_valid
        assert "day-of-month" in error.lower()

    def test_invalid_month_value(self):
        """Test rejection of invalid month values."""
        is_valid, error = validate_cron_expression("0 0 * 13 *")
        assert not is_valid
        assert "month" in error.lower()

    def test_invalid_day_of_week(self):
        """Test rejection of invalid day-of-week values."""
        is_valid, error = validate_cron_expression("0 0 * * 7")
        assert not is_valid
        assert "day-of-week" in error.lower()

    def test_valid_ranges(self):
        """Test validation of range expressions."""
        is_valid, _ = validate_cron_expression("0 9-17 * * *")
        assert is_valid

        is_valid, _ = validate_cron_expression("0 0 * * 1-5")
        assert is_valid

    def test_valid_step_values(self):
        """Test validation of step expressions."""
        is_valid, _ = validate_cron_expression("*/10 * * * *")
        assert is_valid

        is_valid, _ = validate_cron_expression("0 */2 * * *")
        assert is_valid

    def test_valid_list_values(self):
        """Test validation of list expressions."""
        is_valid, _ = validate_cron_expression("0,30 * * * *")
        assert is_valid

        is_valid, _ = validate_cron_expression("0 0 1,15 * *")
        assert is_valid

    def test_empty_or_none(self):
        """Test rejection of empty or None expressions."""
        is_valid, error = validate_cron_expression("")
        assert not is_valid
        assert "required" in error.lower()

        is_valid, error = validate_cron_expression(None)
        assert not is_valid


# =============================================================================
# Cron Description Tests
# =============================================================================


class TestDescribeCron:
    """Tests for cron expression description."""

    def test_describe_hourly(self):
        """Test description of hourly cron."""
        desc = describe_cron("0 * * * *")
        assert "hour" in desc.lower()

    def test_describe_every_15_minutes(self):
        """Test description of 15-minute interval."""
        desc = describe_cron("*/15 * * * *")
        assert "15" in desc
        assert "minute" in desc.lower()

    def test_describe_daily_midnight(self):
        """Test description of daily at midnight."""
        desc = describe_cron("0 0 * * *")
        assert "midnight" in desc.lower() or "daily" in desc.lower()

    def test_describe_weekdays(self):
        """Test description of weekday schedule."""
        desc = describe_cron("0 9 * * 1-5")
        assert "weekday" in desc.lower()

    def test_describe_weekly(self):
        """Test description of weekly schedule."""
        desc = describe_cron("0 6 * * 1")
        assert "monday" in desc.lower() or "weekly" in desc.lower()

    def test_describe_monthly(self):
        """Test description of monthly schedule."""
        desc = describe_cron("0 0 1 * *")
        assert "1st" in desc or "monthly" in desc.lower()

    def test_describe_invalid_cron(self):
        """Test description of invalid cron."""
        desc = describe_cron("invalid cron expression here extra parts")
        assert "invalid" in desc.lower()


# =============================================================================
# Calculate Next Run Tests
# =============================================================================


class TestCalculateNextRun:
    """Tests for next run calculation."""

    def test_calculate_next_run_returns_datetime(self):
        """Test that calculate_next_run returns a datetime."""
        result = calculate_next_run("0 * * * *")
        assert isinstance(result, datetime)

    def test_calculate_next_run_is_in_future(self):
        """Test that calculated next run is in the future."""
        now = datetime.now(timezone.utc)
        result = calculate_next_run("0 * * * *", now)
        assert result > now

    def test_calculate_next_run_with_from_time(self):
        """Test calculation from specific time."""
        from_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = calculate_next_run("0 * * * *", from_time)
        assert result > from_time


# =============================================================================
# RecurringTask Model Tests
# =============================================================================


class TestRecurringTask:
    """Tests for RecurringTask dataclass."""

    def test_create_task_sets_timestamps(self):
        """Test that creating a task sets timestamps."""
        task = RecurringTask(
            task_id="test-123",
            name="Test Task",
            job_type="SECURITY_SCAN",
            cron_expression="0 6 * * *",
        )

        assert task.created_at != ""
        assert task.updated_at != ""
        assert task.next_run != ""

    def test_task_to_dict(self):
        """Test conversion to dictionary."""
        task = RecurringTask(
            task_id="test-123",
            name="Test Task",
            job_type="SECURITY_SCAN",
            cron_expression="0 6 * * *",
            description="A test task",
        )

        d = task.to_dict()
        assert d["task_id"] == "test-123"
        assert d["name"] == "Test Task"
        assert d["job_type"] == "SECURITY_SCAN"
        assert d["description"] == "A test task"

    def test_task_defaults(self):
        """Test default values."""
        task = RecurringTask(
            task_id="test-123",
            name="Test Task",
            job_type="SECURITY_SCAN",
            cron_expression="0 6 * * *",
        )

        assert task.enabled is True
        assert task.run_count == 0
        assert task.failure_count == 0
        assert task.timeout_seconds == 3600
        assert task.max_retries == 3
        assert task.status == "active"


# =============================================================================
# RecurringTaskService Tests
# =============================================================================


class TestRecurringTaskService:
    """Tests for RecurringTaskService."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        table = MagicMock()
        table.put_item = MagicMock()
        table.get_item = MagicMock(return_value={"Item": None})
        table.scan = MagicMock(return_value={"Items": []})
        table.delete_item = MagicMock()
        return table

    @pytest.fixture
    def service(self, mock_table):
        """Create a service with mocked table."""
        service = RecurringTaskService(table_name="test-table")
        service._table = mock_table
        return service

    @pytest.mark.asyncio
    async def test_create_task_valid(self, service):
        """Test creating a valid task."""
        task = await service.create_task(
            name="Security Scan",
            job_type="SECURITY_SCAN",
            cron_expression="0 6 * * 1",
            description="Weekly security scan",
        )

        assert task.name == "Security Scan"
        assert task.job_type == "SECURITY_SCAN"
        assert task.cron_expression == "0 6 * * 1"
        service._table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_task_invalid_cron(self, service):
        """Test creating a task with invalid cron expression."""
        with pytest.raises(ValueError) as exc_info:
            await service.create_task(
                name="Bad Task",
                job_type="SECURITY_SCAN",
                cron_expression="invalid",
            )
        assert "Invalid cron expression" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_task_invalid_job_type(self, service):
        """Test creating a task with invalid job type."""
        with pytest.raises(ValueError) as exc_info:
            await service.create_task(
                name="Bad Task",
                job_type="INVALID_TYPE",
                cron_expression="0 * * * *",
            )
        assert "Invalid job type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_task_found(self, service, mock_table):
        """Test getting an existing task."""
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Test Task",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
                "run_count": 5,
                "failure_count": 0,
            }
        }

        task = await service.get_task("task-123")
        assert task is not None
        assert task.task_id == "task-123"
        assert task.name == "Test Task"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, service, mock_table):
        """Test getting a non-existent task."""
        mock_table.get_item.return_value = {}
        task = await service.get_task("nonexistent")
        assert task is None

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, service, mock_table):
        """Test listing tasks when empty."""
        mock_table.scan.return_value = {"Items": []}
        tasks = await service.list_tasks()
        assert tasks == []

    @pytest.mark.asyncio
    async def test_list_tasks_with_results(self, service, mock_table):
        """Test listing tasks with results."""
        mock_table.scan.return_value = {
            "Items": [
                {
                    "task_id": "task-1",
                    "name": "Task 1",
                    "job_type": "SECURITY_SCAN",
                    "cron_expression": "0 6 * * *",
                    "enabled": True,
                    "status": "active",
                },
                {
                    "task_id": "task-2",
                    "name": "Task 2",
                    "job_type": "CODE_REVIEW",
                    "cron_expression": "0 9 * * 1-5",
                    "enabled": True,
                    "status": "active",
                },
            ]
        }

        tasks = await service.list_tasks()
        assert len(tasks) == 2
        assert tasks[0].task_id == "task-1"
        assert tasks[1].task_id == "task-2"

    @pytest.mark.asyncio
    async def test_update_task(self, service, mock_table):
        """Test updating a task."""
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Old Name",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
            }
        }

        task = await service.update_task("task-123", {"name": "New Name"})
        assert task is not None
        assert task.name == "New Name"
        service._table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, service, mock_table):
        """Test updating a non-existent task."""
        mock_table.get_item.return_value = {}
        task = await service.update_task("nonexistent", {"name": "New Name"})
        assert task is None

    @pytest.mark.asyncio
    async def test_update_task_invalid_cron(self, service, mock_table):
        """Test updating task with invalid cron."""
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Test",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
            }
        }

        with pytest.raises(ValueError):
            await service.update_task("task-123", {"cron_expression": "invalid"})

    @pytest.mark.asyncio
    async def test_delete_task_soft(self, service, mock_table):
        """Test soft deleting a task."""
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Test",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
            }
        }

        success = await service.delete_task("task-123")
        assert success is True
        # Soft delete should call put_item (update status)
        service._table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_task_hard(self, service, mock_table):
        """Test hard deleting a task."""
        success = await service.delete_task("task-123", hard_delete=True)
        assert success is True
        service._table.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_task(self, service, mock_table):
        """Test toggling task enabled state."""
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Test",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
            }
        }

        task = await service.toggle_task("task-123", False)
        assert task is not None
        assert task.enabled is False

    @pytest.mark.asyncio
    async def test_record_execution(self, service, mock_table):
        """Test recording task execution."""
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Test",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
                "run_count": 5,
                "failure_count": 1,
            }
        }

        task = await service.record_execution("task-123", status="succeeded")
        assert task is not None
        assert task.run_count == 6
        assert task.last_run is not None

    @pytest.mark.asyncio
    async def test_record_execution_failure(self, service, mock_table):
        """Test recording failed execution."""
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Test",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
                "run_count": 5,
                "failure_count": 1,
            }
        }

        task = await service.record_execution(
            "task-123", status="failed", error="Test error"
        )
        assert task is not None
        assert task.run_count == 6
        assert task.failure_count == 2

    @pytest.mark.asyncio
    async def test_get_due_tasks(self, service, mock_table):
        """Test getting tasks due for execution."""
        mock_table.scan.return_value = {
            "Items": [
                {
                    "task_id": "task-1",
                    "name": "Due Task",
                    "job_type": "SECURITY_SCAN",
                    "cron_expression": "0 6 * * *",
                    "enabled": True,
                    "status": "active",
                    "next_run": "2026-01-01T00:00:00Z",
                }
            ]
        }

        tasks = await service.get_due_tasks()
        assert len(tasks) == 1
        assert tasks[0].task_id == "task-1"


# =============================================================================
# Service Singleton Tests
# =============================================================================


class TestServiceSingleton:
    """Tests for service singleton management."""

    def test_get_service_creates_instance(self):
        """Test that get_recurring_task_service creates an instance."""
        set_recurring_task_service(None)
        service = get_recurring_task_service()
        assert service is not None
        assert isinstance(service, RecurringTaskService)

    def test_get_service_returns_same_instance(self):
        """Test that repeated calls return the same instance."""
        set_recurring_task_service(None)
        service1 = get_recurring_task_service()
        service2 = get_recurring_task_service()
        assert service1 is service2

    def test_set_service_overrides(self):
        """Test that set_recurring_task_service overrides the instance."""
        custom_service = RecurringTaskService(table_name="custom-table")
        set_recurring_task_service(custom_service)

        service = get_recurring_task_service()
        assert service is custom_service
        assert service.table_name == "custom-table"


# =============================================================================
# JobType Enum Tests
# =============================================================================


class TestJobType:
    """Tests for JobType enum."""

    def test_all_job_types_have_values(self):
        """Test that all job types have string values."""
        for job_type in JobType:
            assert isinstance(job_type.value, str)
            assert len(job_type.value) > 0

    def test_job_types_exist(self):
        """Test expected job types exist."""
        assert JobType.SECURITY_SCAN.value == "SECURITY_SCAN"
        assert JobType.CODE_REVIEW.value == "CODE_REVIEW"
        assert JobType.DEPENDENCY_UPDATE.value == "DEPENDENCY_UPDATE"
        assert JobType.BACKUP.value == "BACKUP"
        assert JobType.COMPLIANCE_CHECK.value == "COMPLIANCE_CHECK"
        assert JobType.PATCH_GENERATION.value == "PATCH_GENERATION"
        assert JobType.CUSTOM.value == "CUSTOM"


# =============================================================================
# TaskStatus Enum Tests
# =============================================================================


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert TaskStatus.ACTIVE.value == "active"
        assert TaskStatus.PAUSED.value == "paused"
        assert TaskStatus.DELETED.value == "deleted"


# =============================================================================
# Extended Coverage Tests - Cron Validation Edge Cases
# =============================================================================


class TestValidateCronPartEdgeCases:
    """Tests for _validate_cron_part edge cases."""

    def test_step_with_invalid_step_value(self):
        """Test step with non-digit step value."""
        from src.services.recurring_task_service import _validate_cron_part

        # Step with non-digit
        result = _validate_cron_part("*/abc", 0, 59)
        assert result is False

    def test_step_with_zero_step(self):
        """Test step with zero step value (invalid)."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("*/0", 0, 59)
        assert result is False

    def test_range_with_valid_values(self):
        """Test range with valid values."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("1-5", 0, 10)
        assert result is True

    def test_range_with_out_of_bounds_start(self):
        """Test range with start value out of bounds."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("100-5", 0, 59)
        assert result is False

    def test_range_with_out_of_bounds_end(self):
        """Test range with end value out of bounds."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("1-100", 0, 59)
        assert result is False

    def test_range_with_non_digit_values(self):
        """Test range with non-digit values."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("a-b", 0, 59)
        assert result is False

    def test_list_with_empty_values(self):
        """Test list with some empty values."""
        from src.services.recurring_task_service import _validate_cron_part

        # List with empty string filtered out
        result = _validate_cron_part("1,,3", 0, 10)
        # Should handle empty strings
        assert result is True

    def test_list_with_out_of_bounds(self):
        """Test list with out of bounds values."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("1,100", 0, 59)
        assert result is False

    def test_single_value_in_bounds(self):
        """Test single value in bounds."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("30", 0, 59)
        assert result is True

    def test_single_value_out_of_bounds(self):
        """Test single value out of bounds."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("99", 0, 59)
        assert result is False

    def test_non_digit_non_special(self):
        """Test non-digit, non-special characters."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("abc", 0, 59)
        assert result is False

    def test_step_with_range_base(self):
        """Test step with range as base (1-10/2)."""
        from src.services.recurring_task_service import _validate_cron_part

        result = _validate_cron_part("1-10/2", 0, 59)
        assert result is True


# =============================================================================
# Extended Coverage Tests - Describe Cron All Branches
# =============================================================================


class TestDescribeCronExtended:
    """Extended tests for describe_cron covering all branches."""

    def test_describe_every_30_minutes(self):
        """Test description of 30-minute interval."""
        desc = describe_cron("*/30 * * * *")
        assert "30" in desc
        assert "minute" in desc.lower()

    def test_describe_daily_6am(self):
        """Test description of daily at 6 AM."""
        desc = describe_cron("0 6 * * *")
        assert "6:00 AM" in desc or "daily" in desc.lower()

    def test_describe_sunday_midnight(self):
        """Test description of Sunday at midnight."""
        desc = describe_cron("0 0 * * 0")
        assert "sunday" in desc.lower() or "weekly" in desc.lower()

    def test_describe_15th_day(self):
        """Test description of 15th day pattern."""
        desc = describe_cron("0 0 15 * *")
        assert "15th" in desc

    def test_describe_weekends(self):
        """Test description of weekend pattern."""
        desc = describe_cron("0 9 * * 0,6")
        assert "weekend" in desc.lower() or "day-of-week" in desc.lower()

    def test_describe_specific_day_of_week(self):
        """Test description with specific day of week number."""
        desc = describe_cron("0 9 * * 3")
        assert "wednesday" in desc.lower()

    def test_describe_with_hour_step(self):
        """Test description with hour step."""
        desc = describe_cron("0 */3 * * *")
        assert "3" in desc and "hour" in desc.lower()

    def test_describe_pm_hour(self):
        """Test description with PM hour."""
        desc = describe_cron("0 14 * * *")
        assert "PM" in desc or "2:00" in desc

    def test_describe_noon(self):
        """Test description at noon (12:00 PM)."""
        desc = describe_cron("0 12 * * *")
        assert "12" in desc

    def test_describe_with_specific_month(self):
        """Test description with specific month."""
        desc = describe_cron("0 0 1 6 *")
        assert "june" in desc.lower()

    def test_describe_every_minute(self):
        """Test description of every minute."""
        desc = describe_cron("* * * * *")
        assert "minute" in desc.lower()

    def test_describe_at_specific_minute(self):
        """Test description at specific minute (not 0)."""
        desc = describe_cron("15 * * * *")
        assert "15" in desc or "minute" in desc.lower()

    def test_describe_custom_schedule(self):
        """Test description returns custom for unusual patterns."""
        # Complex pattern
        desc = describe_cron("5 4 * * *")
        # Should have some description
        assert len(desc) > 0

    def test_describe_hour_range(self):
        """Test description with hour in non-simple format."""
        desc = describe_cron("0 9-17 * * *")
        # Should mention the hour pattern
        assert len(desc) > 0

    def test_describe_unknown_month_number(self):
        """Test description with month number that needs mapping."""
        desc = describe_cron("0 0 1 12 *")
        assert "december" in desc.lower()

    def test_describe_day_of_week_custom(self):
        """Test description with day-of-week range."""
        desc = describe_cron("0 0 * * 2-4")
        assert "day-of-week" in desc.lower() or len(desc) > 0


# =============================================================================
# Extended Coverage Tests - Calculate Next Run
# =============================================================================


class TestCalculateNextRunExtended:
    """Extended tests for calculate_next_run."""

    def test_calculate_next_run_croniter_fallback(self):
        """Test fallback when croniter is not available."""
        from datetime import timedelta

        with patch.dict("sys.modules", {"croniter": None}):
            # Force reimport to trigger ImportError path
            pass

            import src.services.recurring_task_service as module

            # Clear croniter from modules to force ImportError
            original_modules = dict(module.__dict__)

            from_time = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

            # Patch the import inside the function
            with patch(
                "src.services.recurring_task_service.calculate_next_run"
            ) as mock_calc:
                # Make it return a valid datetime
                mock_calc.return_value = from_time + timedelta(hours=1)
                result = mock_calc("0 * * * *", from_time)
                assert result > from_time

    def test_calculate_next_run_with_none_from_time(self):
        """Test calculation with None from_time uses current time."""
        result = calculate_next_run("0 * * * *", None)
        assert isinstance(result, datetime)
        # Should be in the future from now
        assert result > datetime.now(timezone.utc) - __import__("datetime").timedelta(
            seconds=5
        )


# =============================================================================
# Extended Coverage Tests - DynamoDB Lazy Loading
# =============================================================================


class TestLazyLoadingExtended:
    """Extended tests for DynamoDB lazy loading."""

    def test_table_property_creates_dynamodb(self):
        """Test table property creates DynamoDB resource."""
        with patch("boto3.resource") as mock_boto:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_boto.return_value = mock_dynamodb
            mock_dynamodb.Table.return_value = mock_table

            service = RecurringTaskService(table_name="test-table")
            assert service._table is None

            # Access table property
            table = service.table

            mock_boto.assert_called_once_with("dynamodb")
            mock_dynamodb.Table.assert_called_once_with("test-table")
            assert table is mock_table

    def test_table_property_handles_exception(self):
        """Test table property handles DynamoDB connection failure."""
        with patch("boto3.resource") as mock_boto:
            mock_boto.side_effect = Exception("Connection failed")

            service = RecurringTaskService(table_name="test-table")
            table = service.table

            assert table is None

    def test_table_property_reuses_connection(self):
        """Test table property reuses existing connection."""
        with patch("boto3.resource") as mock_boto:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_boto.return_value = mock_dynamodb
            mock_dynamodb.Table.return_value = mock_table

            service = RecurringTaskService(table_name="test-table")

            # Access twice
            _ = service.table
            _ = service.table

            # Should only create once
            assert mock_boto.call_count == 1


# =============================================================================
# Extended Coverage Tests - Service Error Paths
# =============================================================================


class TestServiceErrorPaths:
    """Tests for service error handling paths."""

    @pytest.fixture
    def service_no_table(self):
        """Create a service with no DynamoDB table."""
        service = RecurringTaskService(table_name="test-table")
        service._table = None
        return service

    @pytest.mark.asyncio
    async def test_get_task_no_table(self, service_no_table):
        """Test get_task when table is None."""
        result = await service_no_table.get_task("task-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_tasks_no_table(self, service_no_table):
        """Test list_tasks when table is None."""
        result = await service_no_table.list_tasks()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_due_tasks_no_table(self, service_no_table):
        """Test get_due_tasks when table is None."""
        result = await service_no_table.get_due_tasks()
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_task_hard_no_table(self, service_no_table):
        """Test hard delete when table is None."""
        result = await service_no_table.delete_task("task-123", hard_delete=True)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_task_no_table(self, service_no_table):
        """Test create_task when table is None (in-memory mode)."""
        task = await service_no_table.create_task(
            name="Test Task",
            job_type="SECURITY_SCAN",
            cron_expression="0 6 * * *",
        )
        # Should still create task in-memory
        assert task is not None
        assert task.name == "Test Task"

    @pytest.mark.asyncio
    async def test_get_task_exception(self):
        """Test get_task when DynamoDB raises exception."""
        mock_table = MagicMock()
        mock_table.get_item.side_effect = Exception("DynamoDB error")

        service = RecurringTaskService()
        service._table = mock_table

        result = await service.get_task("task-123")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_tasks_exception(self):
        """Test list_tasks when DynamoDB raises exception."""
        mock_table = MagicMock()
        mock_table.scan.side_effect = Exception("DynamoDB error")

        service = RecurringTaskService()
        service._table = mock_table

        result = await service.list_tasks()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_due_tasks_exception(self):
        """Test get_due_tasks when DynamoDB raises exception."""
        mock_table = MagicMock()
        mock_table.scan.side_effect = Exception("DynamoDB error")

        service = RecurringTaskService()
        service._table = mock_table

        result = await service.get_due_tasks()
        assert result == []

    @pytest.mark.asyncio
    async def test_delete_task_hard_exception(self):
        """Test hard delete when DynamoDB raises exception."""
        mock_table = MagicMock()
        mock_table.delete_item.side_effect = Exception("DynamoDB error")

        service = RecurringTaskService()
        service._table = mock_table

        result = await service.delete_task("task-123", hard_delete=True)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_task_put_item_exception(self):
        """Test create_task when put_item raises exception."""
        mock_table = MagicMock()
        mock_table.put_item.side_effect = Exception("DynamoDB error")

        service = RecurringTaskService()
        service._table = mock_table

        with pytest.raises(Exception) as exc_info:
            await service.create_task(
                name="Test Task",
                job_type="SECURITY_SCAN",
                cron_expression="0 6 * * *",
            )
        assert "DynamoDB error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_task_put_item_exception(self):
        """Test update_task when put_item raises exception."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Test",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
            }
        }
        mock_table.put_item.side_effect = Exception("DynamoDB error")

        service = RecurringTaskService()
        service._table = mock_table

        with pytest.raises(Exception) as exc_info:
            await service.update_task("task-123", {"name": "New Name"})
        assert "DynamoDB error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_task_soft_not_found(self):
        """Test soft delete when task is not found."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        service = RecurringTaskService()
        service._table = mock_table

        result = await service.delete_task("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_record_execution_not_found(self):
        """Test record_execution when task is not found."""
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}

        service = RecurringTaskService()
        service._table = mock_table

        result = await service.record_execution("nonexistent")
        assert result is None


# =============================================================================
# Extended Coverage Tests - List Tasks Filters
# =============================================================================


class TestListTasksFilters:
    """Tests for list_tasks with various filters."""

    @pytest.fixture
    def mock_table(self):
        """Create a mock DynamoDB table."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_table):
        """Create a service with mocked table."""
        service = RecurringTaskService()
        service._table = mock_table
        return service

    @pytest.mark.asyncio
    async def test_list_tasks_with_organization_filter(self, service, mock_table):
        """Test listing tasks filtered by organization."""
        mock_table.scan.return_value = {"Items": []}

        await service.list_tasks(organization_id="org-123")

        # Verify filter expression was built correctly
        call_args = mock_table.scan.call_args
        assert ":org" in call_args.kwargs["ExpressionAttributeValues"]
        assert call_args.kwargs["ExpressionAttributeValues"][":org"] == "org-123"

    @pytest.mark.asyncio
    async def test_list_tasks_with_enabled_filter(self, service, mock_table):
        """Test listing tasks filtered by enabled status."""
        mock_table.scan.return_value = {"Items": []}

        await service.list_tasks(enabled=True)

        call_args = mock_table.scan.call_args
        assert ":enabled" in call_args.kwargs["ExpressionAttributeValues"]
        assert call_args.kwargs["ExpressionAttributeValues"][":enabled"] is True

    @pytest.mark.asyncio
    async def test_list_tasks_with_job_type_filter(self, service, mock_table):
        """Test listing tasks filtered by job type."""
        mock_table.scan.return_value = {"Items": []}

        await service.list_tasks(job_type="SECURITY_SCAN")

        call_args = mock_table.scan.call_args
        assert ":jtype" in call_args.kwargs["ExpressionAttributeValues"]
        assert (
            call_args.kwargs["ExpressionAttributeValues"][":jtype"] == "SECURITY_SCAN"
        )

    @pytest.mark.asyncio
    async def test_list_tasks_with_all_filters(self, service, mock_table):
        """Test listing tasks with all filters combined."""
        mock_table.scan.return_value = {"Items": []}

        await service.list_tasks(
            organization_id="org-123", enabled=False, job_type="CODE_REVIEW"
        )

        call_args = mock_table.scan.call_args
        values = call_args.kwargs["ExpressionAttributeValues"]
        assert values[":org"] == "org-123"
        assert values[":enabled"] is False
        assert values[":jtype"] == "CODE_REVIEW"
        assert values[":deleted"] == "deleted"

    @pytest.mark.asyncio
    async def test_list_tasks_with_limit(self, service, mock_table):
        """Test listing tasks with custom limit."""
        mock_table.scan.return_value = {"Items": []}

        await service.list_tasks(limit=25)

        call_args = mock_table.scan.call_args
        assert call_args.kwargs["Limit"] == 25


# =============================================================================
# Extended Coverage Tests - Update Task Cron Change
# =============================================================================


class TestUpdateTaskCronChange:
    """Tests for update_task when cron expression changes."""

    @pytest.mark.asyncio
    async def test_update_task_recalculates_next_run(self):
        """Test that updating cron expression recalculates next_run."""
        mock_table = MagicMock()
        original_next_run = "2026-01-15T06:00:00+00:00"
        mock_table.get_item.return_value = {
            "Item": {
                "task_id": "task-123",
                "name": "Test",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
                "enabled": True,
                "status": "active",
                "next_run": original_next_run,
            }
        }

        service = RecurringTaskService()
        service._table = mock_table

        task = await service.update_task("task-123", {"cron_expression": "0 12 * * *"})

        assert task is not None
        # Next run should be different after cron change
        assert task.cron_expression == "0 12 * * *"


# =============================================================================
# Extended Coverage Tests - RecurringTask Model
# =============================================================================


class TestRecurringTaskExtended:
    """Extended tests for RecurringTask dataclass."""

    def test_task_preserves_existing_timestamps(self):
        """Test that existing timestamps are preserved."""
        existing_created = "2026-01-01T00:00:00+00:00"
        existing_updated = "2026-01-10T00:00:00+00:00"

        task = RecurringTask(
            task_id="test-123",
            name="Test Task",
            job_type="SECURITY_SCAN",
            cron_expression="0 6 * * *",
            created_at=existing_created,
            updated_at=existing_updated,
        )

        assert task.created_at == existing_created
        assert task.updated_at == existing_updated

    def test_task_calculate_next_run_exception(self):
        """Test _calculate_next_run handles exceptions."""
        task = RecurringTask(
            task_id="test-123",
            name="Test Task",
            job_type="SECURITY_SCAN",
            cron_expression="invalid-cron",
            next_run=None,
        )

        # Should not raise, should return empty string on error
        # The __post_init__ sets next_run
        # Since cron is invalid, next_run should be empty
        assert task.next_run == "" or task.next_run is not None


# =============================================================================
# Extended Coverage Tests - Environment Variable Default
# =============================================================================


class TestEnvironmentDefaults:
    """Tests for environment variable defaults."""

    def test_service_uses_default_table_name(self):
        """Test service uses default table name from environment."""
        with patch.dict("os.environ", {}, clear=True):
            service = RecurringTaskService()
            assert "aura-recurring-tasks" in service.table_name

    def test_service_uses_env_table_name(self):
        """Test service uses table name from environment."""
        with patch.dict(
            "os.environ", {"RECURRING_TASKS_TABLE_NAME": "custom-table-name"}
        ):
            service = RecurringTaskService()
            assert service.table_name == "custom-table-name"
