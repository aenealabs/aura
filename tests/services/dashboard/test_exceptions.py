"""Tests for Dashboard service exceptions."""

from __future__ import annotations

from src.services.dashboard import (
    DashboardAccessDeniedError,
    DashboardConflictError,
    DashboardException,
    DashboardLimitExceededError,
    DashboardNotFoundError,
    DashboardValidationError,
    DynamoDBError,
    RoleDefaultNotFoundError,
    ShareAlreadyExistsError,
    ShareNotFoundError,
    WidgetNotFoundError,
)


class TestDashboardException:
    """Tests for base DashboardException."""

    def test_basic_exception(self):
        """Test basic exception creation."""
        exc = DashboardException("Test error")
        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.code == "DASHBOARD_ERROR"

    def test_exception_with_code(self):
        """Test exception with custom code."""
        exc = DashboardException("Test error", code="CUSTOM_CODE")
        assert exc.code == "CUSTOM_CODE"


class TestDashboardNotFoundError:
    """Tests for DashboardNotFoundError."""

    def test_not_found_error(self):
        """Test not found error creation."""
        exc = DashboardNotFoundError("dash-123")
        assert "dash-123" in str(exc)
        assert exc.dashboard_id == "dash-123"
        assert exc.code == "DASHBOARD_NOT_FOUND"


class TestDashboardAccessDeniedError:
    """Tests for DashboardAccessDeniedError."""

    def test_access_denied_default_action(self):
        """Test access denied with default action."""
        exc = DashboardAccessDeniedError("dash-123", "user-456")
        assert "dash-123" in str(exc)
        assert "user-456" in str(exc)
        assert "access" in str(exc)
        assert exc.dashboard_id == "dash-123"
        assert exc.user_id == "user-456"
        assert exc.action == "access"
        assert exc.code == "DASHBOARD_ACCESS_DENIED"

    def test_access_denied_custom_action(self):
        """Test access denied with custom action."""
        exc = DashboardAccessDeniedError("dash-123", "user-456", "edit")
        assert "edit" in str(exc)
        assert exc.action == "edit"


class TestDashboardConflictError:
    """Tests for DashboardConflictError."""

    def test_conflict_error(self):
        """Test version conflict error creation."""
        exc = DashboardConflictError("dash-123", expected_version=1, actual_version=2)
        assert "dash-123" in str(exc)
        assert "expected 1" in str(exc)
        assert "found 2" in str(exc)
        assert exc.dashboard_id == "dash-123"
        assert exc.expected_version == 1
        assert exc.actual_version == 2
        assert exc.code == "DASHBOARD_VERSION_CONFLICT"


class TestDashboardLimitExceededError:
    """Tests for DashboardLimitExceededError."""

    def test_limit_exceeded_error(self):
        """Test limit exceeded error creation."""
        exc = DashboardLimitExceededError("user-123", 10)
        assert "user-123" in str(exc)
        assert "10" in str(exc)
        assert exc.user_id == "user-123"
        assert exc.limit == 10
        assert exc.code == "DASHBOARD_LIMIT_EXCEEDED"


class TestDashboardValidationError:
    """Tests for DashboardValidationError."""

    def test_validation_error_without_field(self):
        """Test validation error without field."""
        exc = DashboardValidationError("Invalid data")
        assert str(exc) == "Invalid data"
        assert exc.field is None
        assert exc.code == "DASHBOARD_VALIDATION_ERROR"

    def test_validation_error_with_field(self):
        """Test validation error with field."""
        exc = DashboardValidationError("Invalid value", field="name")
        assert exc.field == "name"


class TestShareNotFoundError:
    """Tests for ShareNotFoundError."""

    def test_share_not_found_error(self):
        """Test share not found error creation."""
        exc = ShareNotFoundError("dash-123", "user-456")
        assert "dash-123" in str(exc)
        assert "user-456" in str(exc)
        assert exc.dashboard_id == "dash-123"
        assert exc.target_id == "user-456"
        assert exc.code == "SHARE_NOT_FOUND"


class TestShareAlreadyExistsError:
    """Tests for ShareAlreadyExistsError."""

    def test_share_exists_error(self):
        """Test share already exists error creation."""
        exc = ShareAlreadyExistsError("dash-123", "user-456")
        assert "dash-123" in str(exc)
        assert "user-456" in str(exc)
        assert exc.dashboard_id == "dash-123"
        assert exc.target_id == "user-456"
        assert exc.code == "SHARE_ALREADY_EXISTS"


class TestRoleDefaultNotFoundError:
    """Tests for RoleDefaultNotFoundError."""

    def test_role_default_not_found_error(self):
        """Test role default not found error creation."""
        exc = RoleDefaultNotFoundError("security-engineer")
        assert "security-engineer" in str(exc)
        assert exc.role == "security-engineer"
        assert exc.code == "ROLE_DEFAULT_NOT_FOUND"


class TestWidgetNotFoundError:
    """Tests for WidgetNotFoundError."""

    def test_widget_not_found_error(self):
        """Test widget not found error creation."""
        exc = WidgetNotFoundError("custom_widget")
        assert "custom_widget" in str(exc)
        assert exc.widget_type == "custom_widget"
        assert exc.code == "WIDGET_NOT_FOUND"


class TestDynamoDBError:
    """Tests for DynamoDBError."""

    def test_dynamodb_error(self):
        """Test DynamoDB error creation."""
        original = Exception("Connection refused")
        exc = DynamoDBError("put_item", original)
        assert "put_item" in str(exc)
        assert "Connection refused" in str(exc)
        assert exc.operation == "put_item"
        assert exc.original_error is original
        assert exc.code == "DYNAMODB_ERROR"
