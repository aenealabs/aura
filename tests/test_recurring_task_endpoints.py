"""
Tests for Recurring Task API Endpoints

ADR-055 Phase 3: Recurring Tasks and Advanced Features
"""

import platform
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Use forked mode on non-Linux to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked


# Clear cached modules to ensure fresh imports
for module_name in list(sys.modules.keys()):
    if module_name.startswith("src.api.recurring_task"):
        del sys.modules[module_name]


from src.api.recurring_task_endpoints import router
from src.services.recurring_task_service import (
    RecurringTask,
    RecurringTaskService,
    set_recurring_task_service,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def app():
    """Create a test FastAPI app."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_service():
    """Create a mock recurring task service."""
    service = MagicMock(spec=RecurringTaskService)
    service.list_tasks = AsyncMock(return_value=[])
    service.get_task = AsyncMock(return_value=None)
    service.create_task = AsyncMock()
    service.update_task = AsyncMock(return_value=None)
    service.delete_task = AsyncMock(return_value=True)
    service.toggle_task = AsyncMock(return_value=None)
    service.get_due_tasks = AsyncMock(return_value=[])
    set_recurring_task_service(service)
    return service


def make_task(**kwargs):
    """Helper to create a RecurringTask with defaults."""
    defaults = {
        "task_id": "task-123",
        "name": "Test Task",
        "job_type": "SECURITY_SCAN",
        "cron_expression": "0 6 * * *",
        "enabled": True,
        "description": "Test description",
        "target_repository": None,
        "parameters": {},
        "organization_id": "default",
        "created_by": "system",
        "next_run": "2026-01-07T06:00:00Z",
        "last_run": None,
        "run_count": 0,
        "failure_count": 0,
        "timeout_seconds": 3600,
        "max_retries": 3,
        "notification_emails": [],
        "tags": [],
        "status": "active",
        "created_at": "2026-01-06T12:00:00Z",
        "updated_at": "2026-01-06T12:00:00Z",
    }
    defaults.update(kwargs)
    return RecurringTask(**defaults)


# =============================================================================
# List Recurring Tasks Tests
# =============================================================================


class TestListRecurringTasks:
    """Tests for GET /api/v1/schedule/recurring."""

    def test_list_tasks_empty(self, client, mock_service):
        """Test listing when no tasks exist."""
        mock_service.list_tasks.return_value = []

        response = client.get("/api/v1/schedule/recurring")

        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    def test_list_tasks_with_results(self, client, mock_service):
        """Test listing with tasks."""
        mock_service.list_tasks.return_value = [
            make_task(task_id="task-1", name="Task 1"),
            make_task(task_id="task-2", name="Task 2"),
        ]

        response = client.get("/api/v1/schedule/recurring")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 2
        assert data["total"] == 2
        assert data["tasks"][0]["name"] == "Task 1"
        assert data["tasks"][1]["name"] == "Task 2"

    def test_list_tasks_with_enabled_filter(self, client, mock_service):
        """Test listing with enabled filter."""
        response = client.get("/api/v1/schedule/recurring?enabled=true")

        assert response.status_code == 200
        mock_service.list_tasks.assert_called_once()
        call_kwargs = mock_service.list_tasks.call_args[1]
        assert call_kwargs["enabled"] is True

    def test_list_tasks_with_job_type_filter(self, client, mock_service):
        """Test listing with job type filter."""
        response = client.get("/api/v1/schedule/recurring?job_type=SECURITY_SCAN")

        assert response.status_code == 200
        call_kwargs = mock_service.list_tasks.call_args[1]
        assert call_kwargs["job_type"] == "SECURITY_SCAN"

    def test_list_tasks_with_limit(self, client, mock_service):
        """Test listing with limit."""
        response = client.get("/api/v1/schedule/recurring?limit=10")

        assert response.status_code == 200
        call_kwargs = mock_service.list_tasks.call_args[1]
        assert call_kwargs["limit"] == 10


# =============================================================================
# Create Recurring Task Tests
# =============================================================================


class TestCreateRecurringTask:
    """Tests for POST /api/v1/schedule/recurring."""

    def test_create_task_success(self, client, mock_service):
        """Test successful task creation."""
        mock_service.create_task.return_value = make_task()

        response = client.post(
            "/api/v1/schedule/recurring",
            json={
                "name": "Test Task",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "task-123"
        assert data["name"] == "Test Task"

    def test_create_task_with_all_fields(self, client, mock_service):
        """Test task creation with all optional fields."""
        mock_service.create_task.return_value = make_task(
            description="Full description",
            target_repository="https://github.com/test/repo",
            notification_emails=["test@example.com"],
            tags=["security", "weekly"],
        )

        response = client.post(
            "/api/v1/schedule/recurring",
            json={
                "name": "Full Task",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * 1",
                "description": "Full description",
                "target_repository": "https://github.com/test/repo",
                "parameters": {"depth": "full"},
                "enabled": True,
                "timeout_seconds": 7200,
                "max_retries": 5,
                "notification_emails": ["test@example.com"],
                "tags": ["security", "weekly"],
            },
        )

        assert response.status_code == 201
        mock_service.create_task.assert_called_once()

    def test_create_task_invalid_cron(self, client, mock_service):
        """Test creation with invalid cron expression."""
        mock_service.create_task.side_effect = ValueError("Invalid cron expression")

        response = client.post(
            "/api/v1/schedule/recurring",
            json={
                "name": "Bad Task",
                "job_type": "SECURITY_SCAN",
                "cron_expression": "invalid",
            },
        )

        assert response.status_code == 400
        assert "Invalid cron expression" in response.json()["detail"]

    def test_create_task_missing_name(self, client, mock_service):
        """Test creation without required name field."""
        response = client.post(
            "/api/v1/schedule/recurring",
            json={
                "job_type": "SECURITY_SCAN",
                "cron_expression": "0 6 * * *",
            },
        )

        assert response.status_code == 422  # Validation error


# =============================================================================
# Get Recurring Task Tests
# =============================================================================


class TestGetRecurringTask:
    """Tests for GET /api/v1/schedule/recurring/{task_id}."""

    def test_get_task_found(self, client, mock_service):
        """Test getting an existing task."""
        mock_service.get_task.return_value = make_task(task_id="task-456")

        response = client.get("/api/v1/schedule/recurring/task-456")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-456"

    def test_get_task_not_found(self, client, mock_service):
        """Test getting a non-existent task."""
        mock_service.get_task.return_value = None

        response = client.get("/api/v1/schedule/recurring/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# =============================================================================
# Update Recurring Task Tests
# =============================================================================


class TestUpdateRecurringTask:
    """Tests for PUT /api/v1/schedule/recurring/{task_id}."""

    def test_update_task_success(self, client, mock_service):
        """Test successful task update."""
        mock_service.update_task.return_value = make_task(name="Updated Name")

        response = client.put(
            "/api/v1/schedule/recurring/task-123",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_task_not_found(self, client, mock_service):
        """Test updating non-existent task."""
        mock_service.update_task.return_value = None

        response = client.put(
            "/api/v1/schedule/recurring/nonexistent",
            json={"name": "New Name"},
        )

        assert response.status_code == 404

    def test_update_task_no_updates(self, client, mock_service):
        """Test update with empty body."""
        response = client.put(
            "/api/v1/schedule/recurring/task-123",
            json={},
        )

        assert response.status_code == 400
        assert "No updates provided" in response.json()["detail"]

    def test_update_task_invalid_cron(self, client, mock_service):
        """Test update with invalid cron expression."""
        mock_service.update_task.side_effect = ValueError("Invalid cron expression")

        response = client.put(
            "/api/v1/schedule/recurring/task-123",
            json={"cron_expression": "invalid"},
        )

        assert response.status_code == 400


# =============================================================================
# Delete Recurring Task Tests
# =============================================================================


class TestDeleteRecurringTask:
    """Tests for DELETE /api/v1/schedule/recurring/{task_id}."""

    def test_delete_task_success(self, client, mock_service):
        """Test successful task deletion."""
        mock_service.delete_task.return_value = True

        response = client.delete("/api/v1/schedule/recurring/task-123")

        assert response.status_code == 204

    def test_delete_task_not_found(self, client, mock_service):
        """Test deleting non-existent task."""
        mock_service.delete_task.return_value = False

        response = client.delete("/api/v1/schedule/recurring/nonexistent")

        assert response.status_code == 404

    def test_delete_task_hard(self, client, mock_service):
        """Test hard deletion."""
        mock_service.delete_task.return_value = True

        response = client.delete("/api/v1/schedule/recurring/task-123?hard=true")

        assert response.status_code == 204
        mock_service.delete_task.assert_called_with("task-123", hard_delete=True)


# =============================================================================
# Toggle Recurring Task Tests
# =============================================================================


class TestToggleRecurringTask:
    """Tests for POST /api/v1/schedule/recurring/{task_id}/toggle."""

    def test_toggle_task_enable(self, client, mock_service):
        """Test enabling a task."""
        mock_service.toggle_task.return_value = make_task(enabled=True)

        response = client.post(
            "/api/v1/schedule/recurring/task-123/toggle",
            json={"enabled": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    def test_toggle_task_disable(self, client, mock_service):
        """Test disabling a task."""
        mock_service.toggle_task.return_value = make_task(enabled=False)

        response = client.post(
            "/api/v1/schedule/recurring/task-123/toggle",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

    def test_toggle_task_not_found(self, client, mock_service):
        """Test toggling non-existent task."""
        mock_service.toggle_task.return_value = None

        response = client.post(
            "/api/v1/schedule/recurring/nonexistent/toggle",
            json={"enabled": True},
        )

        assert response.status_code == 404


# =============================================================================
# Get Due Tasks Tests
# =============================================================================


class TestGetDueTasks:
    """Tests for GET /api/v1/schedule/recurring/due."""

    def test_get_due_tasks_empty(self, client, mock_service):
        """Test when no tasks are due."""
        mock_service.get_due_tasks.return_value = []

        response = client.get("/api/v1/schedule/recurring/due")

        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0

    def test_get_due_tasks_with_results(self, client, mock_service):
        """Test when tasks are due."""
        mock_service.get_due_tasks.return_value = [
            make_task(task_id="due-1"),
            make_task(task_id="due-2"),
        ]

        response = client.get("/api/v1/schedule/recurring/due")

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 2

    def test_get_due_tasks_with_limit(self, client, mock_service):
        """Test with limit parameter."""
        response = client.get("/api/v1/schedule/recurring/due?limit=10")

        assert response.status_code == 200
        mock_service.get_due_tasks.assert_called_with(limit=10)


# =============================================================================
# Cron Validation Tests
# =============================================================================


class TestCronValidation:
    """Tests for POST /api/v1/schedule/cron/validate."""

    def test_validate_valid_cron(self, client, mock_service):
        """Test validation of valid cron expression."""
        response = client.post(
            "/api/v1/schedule/cron/validate",
            json={"cron_expression": "0 6 * * *"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["error"] is None
        assert data["description"] is not None
        assert len(data["next_runs"]) > 0

    def test_validate_invalid_cron(self, client, mock_service):
        """Test validation of invalid cron expression."""
        response = client.post(
            "/api/v1/schedule/cron/validate",
            json={"cron_expression": "invalid"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["error"] is not None


# =============================================================================
# Cron Description Tests
# =============================================================================


class TestCronDescription:
    """Tests for POST /api/v1/schedule/cron/describe."""

    def test_describe_valid_cron(self, client, mock_service):
        """Test description of valid cron expression."""
        response = client.post(
            "/api/v1/schedule/cron/describe",
            json={"cron_expression": "0 6 * * *"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cron_expression"] == "0 6 * * *"
        assert data["description"] is not None

    def test_describe_invalid_cron(self, client, mock_service):
        """Test description of invalid cron expression."""
        response = client.post(
            "/api/v1/schedule/cron/describe",
            json={"cron_expression": "invalid"},
        )

        assert response.status_code == 400
        assert "Invalid cron expression" in response.json()["detail"]


# =============================================================================
# List Job Types Tests
# =============================================================================


class TestListJobTypes:
    """Tests for GET /api/v1/schedule/job-types."""

    def test_list_job_types(self, client, mock_service):
        """Test listing available job types."""
        response = client.get("/api/v1/schedule/job-types")

        assert response.status_code == 200
        data = response.json()
        assert "job_types" in data
        assert len(data["job_types"]) > 0

        # Verify structure
        for job_type in data["job_types"]:
            assert "value" in job_type
            assert "label" in job_type
            assert "description" in job_type

    def test_list_job_types_includes_expected(self, client, mock_service):
        """Test that expected job types are included."""
        response = client.get("/api/v1/schedule/job-types")

        data = response.json()
        values = [jt["value"] for jt in data["job_types"]]

        assert "SECURITY_SCAN" in values
        assert "CODE_REVIEW" in values
        assert "DEPENDENCY_UPDATE" in values
        assert "BACKUP" in values
        assert "COMPLIANCE_CHECK" in values
