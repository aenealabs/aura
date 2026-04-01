"""Custom exceptions for Dashboard service.

Implements domain-specific exceptions per ADR-064 for clear error handling
in dashboard CRUD operations, sharing, and authorization.
"""

from __future__ import annotations


class DashboardException(Exception):
    """Base exception for all dashboard-related errors."""

    def __init__(self, message: str, code: str | None = None) -> None:
        """Initialize with message and optional error code.

        Args:
            message: Human-readable error description
            code: Machine-readable error code for API responses
        """
        super().__init__(message)
        self.message = message
        self.code = code or "DASHBOARD_ERROR"


class DashboardNotFoundError(DashboardException):
    """Raised when a requested dashboard does not exist."""

    def __init__(self, dashboard_id: str) -> None:
        """Initialize with dashboard ID that was not found.

        Args:
            dashboard_id: The dashboard ID that could not be found
        """
        super().__init__(
            message=f"Dashboard not found: {dashboard_id}",
            code="DASHBOARD_NOT_FOUND",
        )
        self.dashboard_id = dashboard_id


class DashboardAccessDeniedError(DashboardException):
    """Raised when user lacks permission to access a dashboard."""

    def __init__(self, dashboard_id: str, user_id: str, action: str = "access") -> None:
        """Initialize with access denial details.

        Args:
            dashboard_id: The dashboard the user tried to access
            user_id: The user who was denied access
            action: The action that was denied (view, edit, delete, share)
        """
        super().__init__(
            message=f"User {user_id} does not have permission to {action} dashboard {dashboard_id}",
            code="DASHBOARD_ACCESS_DENIED",
        )
        self.dashboard_id = dashboard_id
        self.user_id = user_id
        self.action = action


class DashboardConflictError(DashboardException):
    """Raised when there's a version conflict during update (optimistic locking)."""

    def __init__(
        self, dashboard_id: str, expected_version: int, actual_version: int
    ) -> None:
        """Initialize with version conflict details.

        Args:
            dashboard_id: The dashboard with the conflict
            expected_version: The version the client expected
            actual_version: The current version in the database
        """
        super().__init__(
            message=f"Version conflict for dashboard {dashboard_id}: expected {expected_version}, found {actual_version}",
            code="DASHBOARD_VERSION_CONFLICT",
        )
        self.dashboard_id = dashboard_id
        self.expected_version = expected_version
        self.actual_version = actual_version


class DashboardLimitExceededError(DashboardException):
    """Raised when user exceeds maximum dashboard limit."""

    def __init__(self, user_id: str, limit: int) -> None:
        """Initialize with limit details.

        Args:
            user_id: The user who exceeded the limit
            limit: The maximum allowed dashboards
        """
        super().__init__(
            message=f"User {user_id} has reached the maximum dashboard limit of {limit}",
            code="DASHBOARD_LIMIT_EXCEEDED",
        )
        self.user_id = user_id
        self.limit = limit


class DashboardValidationError(DashboardException):
    """Raised when dashboard data fails validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        """Initialize with validation error details.

        Args:
            message: Description of the validation error
            field: The field that failed validation (optional)
        """
        super().__init__(
            message=message,
            code="DASHBOARD_VALIDATION_ERROR",
        )
        self.field = field


class ShareNotFoundError(DashboardException):
    """Raised when a share record does not exist."""

    def __init__(self, dashboard_id: str, target_id: str) -> None:
        """Initialize with share details.

        Args:
            dashboard_id: The dashboard ID
            target_id: The user or org ID that was not found in shares
        """
        super().__init__(
            message=f"Share not found for dashboard {dashboard_id} with target {target_id}",
            code="SHARE_NOT_FOUND",
        )
        self.dashboard_id = dashboard_id
        self.target_id = target_id


class ShareAlreadyExistsError(DashboardException):
    """Raised when trying to create a duplicate share."""

    def __init__(self, dashboard_id: str, target_id: str) -> None:
        """Initialize with share details.

        Args:
            dashboard_id: The dashboard ID
            target_id: The user or org ID that already has a share
        """
        super().__init__(
            message=f"Share already exists for dashboard {dashboard_id} with target {target_id}",
            code="SHARE_ALREADY_EXISTS",
        )
        self.dashboard_id = dashboard_id
        self.target_id = target_id


class RoleDefaultNotFoundError(DashboardException):
    """Raised when no default dashboard exists for a role."""

    def __init__(self, role: str) -> None:
        """Initialize with role.

        Args:
            role: The role that has no default dashboard
        """
        super().__init__(
            message=f"No default dashboard found for role: {role}",
            code="ROLE_DEFAULT_NOT_FOUND",
        )
        self.role = role


class WidgetNotFoundError(DashboardException):
    """Raised when a widget is not found in the catalog."""

    def __init__(self, widget_type: str) -> None:
        """Initialize with widget type.

        Args:
            widget_type: The widget type that was not found
        """
        super().__init__(
            message=f"Widget type not found in catalog: {widget_type}",
            code="WIDGET_NOT_FOUND",
        )
        self.widget_type = widget_type


class DynamoDBError(DashboardException):
    """Raised when a DynamoDB operation fails."""

    def __init__(self, operation: str, original_error: Exception) -> None:
        """Initialize with operation details.

        Args:
            operation: The DynamoDB operation that failed
            original_error: The underlying exception from boto3
        """
        super().__init__(
            message=f"DynamoDB {operation} failed: {str(original_error)}",
            code="DYNAMODB_ERROR",
        )
        self.operation = operation
        self.original_error = original_error
