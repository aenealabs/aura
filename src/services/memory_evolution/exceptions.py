"""
Project Aura - Memory Evolution Exceptions (ADR-080)

Custom exception classes for memory evolution operations.
"""

from typing import Any, Optional


class MemoryEvolutionError(Exception):
    """Base exception for all memory evolution errors."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "operation": self.operation,
            "details": self.details,
        }


class RefineOperationError(MemoryEvolutionError):
    """Error during a refine operation."""


class ConsolidationError(RefineOperationError):
    """Error during CONSOLIDATE operation."""

    def __init__(
        self,
        message: str,
        memory_ids: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, operation="CONSOLIDATE", details=details)
        self.memory_ids = memory_ids or []


class PruneError(RefineOperationError):
    """Error during PRUNE operation."""

    def __init__(
        self,
        message: str,
        memory_ids: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, operation="PRUNE", details=details)
        self.memory_ids = memory_ids or []


class ReinforceError(RefineOperationError):
    """Error during REINFORCE operation."""

    def __init__(
        self,
        message: str,
        memory_ids: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, operation="REINFORCE", details=details)
        self.memory_ids = memory_ids or []


class AbstractError(RefineOperationError):
    """Error during ABSTRACT operation."""

    def __init__(
        self,
        message: str,
        memory_ids: Optional[list[str]] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, operation="ABSTRACT", details=details)
        self.memory_ids = memory_ids or []


class RollbackError(RefineOperationError):
    """Error during ROLLBACK operation."""

    def __init__(
        self,
        message: str,
        rollback_token: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, operation="ROLLBACK", details=details)
        self.rollback_token = rollback_token


class SecurityBoundaryViolation(MemoryEvolutionError):
    """Attempted operation crosses security domain boundary."""

    def __init__(
        self,
        message: str,
        expected_domain: Optional[str] = None,
        actual_domain: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "expected_domain": expected_domain,
                "actual_domain": actual_domain,
                "tenant_id": tenant_id,
            },
        )
        self.expected_domain = expected_domain
        self.actual_domain = actual_domain
        self.tenant_id = tenant_id


class TenantIsolationViolation(MemoryEvolutionError):
    """Attempted operation crosses tenant boundary."""

    def __init__(
        self,
        message: str,
        expected_tenant: Optional[str] = None,
        actual_tenant: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            details={
                "expected_tenant": expected_tenant,
                "actual_tenant": actual_tenant,
            },
        )
        self.expected_tenant = expected_tenant
        self.actual_tenant = actual_tenant


class FeatureDisabledError(MemoryEvolutionError):
    """Attempted to use a disabled feature."""

    def __init__(self, operation: str, phase: Optional[str] = None) -> None:
        message = f"Operation '{operation}' is disabled"
        if phase:
            message += f" (Phase {phase})"
        super().__init__(message, operation=operation, details={"phase": phase})
        self.phase = phase


class ValidationError(MemoryEvolutionError):
    """Validation error for refine action."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
    ) -> None:
        super().__init__(
            message, details={"field": field, "value": str(value) if value else None}
        )
        self.field = field
        self.value = value


class StorageError(MemoryEvolutionError):
    """Error interacting with storage (DynamoDB)."""

    def __init__(
        self,
        message: str,
        table_name: Optional[str] = None,
        aws_error: Optional[str] = None,
    ) -> None:
        super().__init__(
            message, details={"table_name": table_name, "aws_error": aws_error}
        )
        self.table_name = table_name
        self.aws_error = aws_error


class QueueError(MemoryEvolutionError):
    """Error interacting with SQS queue."""

    def __init__(
        self,
        message: str,
        queue_url: Optional[str] = None,
        aws_error: Optional[str] = None,
    ) -> None:
        super().__init__(
            message, details={"queue_url": queue_url, "aws_error": aws_error}
        )
        self.queue_url = queue_url
        self.aws_error = aws_error


class MetricsError(MemoryEvolutionError):
    """Error publishing metrics to CloudWatch."""

    def __init__(
        self,
        message: str,
        metric_name: Optional[str] = None,
        aws_error: Optional[str] = None,
    ) -> None:
        super().__init__(
            message, details={"metric_name": metric_name, "aws_error": aws_error}
        )
        self.metric_name = metric_name
        self.aws_error = aws_error


class SnapshotError(MemoryEvolutionError):
    """Error creating or restoring memory snapshot."""

    def __init__(
        self,
        message: str,
        snapshot_id: Optional[str] = None,
        memory_ids: Optional[list[str]] = None,
    ) -> None:
        super().__init__(
            message, details={"snapshot_id": snapshot_id, "memory_ids": memory_ids}
        )
        self.snapshot_id = snapshot_id
        self.memory_ids = memory_ids or []


class CircuitBreakerOpen(MemoryEvolutionError):
    """Circuit breaker is open due to repeated failures."""

    def __init__(
        self,
        message: str,
        operation: str,
        failure_count: int,
        cooldown_remaining_seconds: float,
    ) -> None:
        super().__init__(
            message,
            operation=operation,
            details={
                "failure_count": failure_count,
                "cooldown_remaining_seconds": cooldown_remaining_seconds,
            },
        )
        self.failure_count = failure_count
        self.cooldown_remaining_seconds = cooldown_remaining_seconds
