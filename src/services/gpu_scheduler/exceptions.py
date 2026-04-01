"""Custom exceptions for GPU Scheduler service.

These exceptions provide semantic error handling for GPU job operations,
enabling proper HTTP status code mapping in the API layer.
"""


class GPUSchedulerError(Exception):
    """Base exception for GPU scheduler errors."""

    def __init__(self, message: str, details: dict | None = None):
        """Initialize the exception.

        Args:
            message: Human-readable error message.
            details: Optional dictionary with additional error context.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class GPUJobNotFoundError(GPUSchedulerError):
    """Raised when a GPU job is not found.

    Maps to HTTP 404 Not Found.
    """

    def __init__(self, job_id: str, organization_id: str | None = None):
        """Initialize the exception.

        Args:
            job_id: The ID of the job that was not found.
            organization_id: Optional organization ID for context.
        """
        details = {"job_id": job_id}
        if organization_id:
            details["organization_id"] = organization_id
        super().__init__(f"GPU job not found: {job_id}", details)
        self.job_id = job_id
        self.organization_id = organization_id


class QuotaExceededError(GPUSchedulerError):
    """Raised when organization GPU quota is exceeded.

    Maps to HTTP 429 Too Many Requests.
    """

    def __init__(
        self,
        organization_id: str,
        quota_type: str,
        current_value: int | float,
        max_value: int | float,
    ):
        """Initialize the exception.

        Args:
            organization_id: The organization that exceeded quota.
            quota_type: Type of quota exceeded (e.g., 'concurrent_jobs', 'gpu_hours').
            current_value: Current usage value.
            max_value: Maximum allowed value.
        """
        message = (
            f"GPU quota exceeded for organization {organization_id}: "
            f"{quota_type} is {current_value}/{max_value}"
        )
        details = {
            "organization_id": organization_id,
            "quota_type": quota_type,
            "current_value": current_value,
            "max_value": max_value,
        }
        super().__init__(message, details)
        self.organization_id = organization_id
        self.quota_type = quota_type
        self.current_value = current_value
        self.max_value = max_value


class JobCancellationError(GPUSchedulerError):
    """Raised when a job cannot be cancelled.

    Maps to HTTP 409 Conflict.
    """

    def __init__(self, job_id: str, reason: str):
        """Initialize the exception.

        Args:
            job_id: The ID of the job that cannot be cancelled.
            reason: Reason why the job cannot be cancelled.
        """
        message = f"Cannot cancel job {job_id}: {reason}"
        details = {"job_id": job_id, "reason": reason}
        super().__init__(message, details)
        self.job_id = job_id
        self.reason = reason


class InvalidJobConfigError(GPUSchedulerError):
    """Raised when job configuration is invalid.

    Maps to HTTP 400 Bad Request.
    """

    def __init__(self, message: str, field: str | None = None):
        """Initialize the exception.

        Args:
            message: Description of the validation error.
            field: Optional field name that caused the error.
        """
        details = {}
        if field:
            details["field"] = field
        super().__init__(message, details)
        self.field = field


class K8sJobCreationError(GPUSchedulerError):
    """Raised when Kubernetes job creation fails.

    Maps to HTTP 503 Service Unavailable.
    """

    def __init__(self, job_id: str, reason: str):
        """Initialize the exception.

        Args:
            job_id: The ID of the GPU job.
            reason: Reason for the K8s job creation failure.
        """
        message = f"Failed to create Kubernetes job for {job_id}: {reason}"
        details = {"job_id": job_id, "reason": reason}
        super().__init__(message, details)
        self.job_id = job_id
        self.reason = reason


class CheckpointError(GPUSchedulerError):
    """Raised when checkpoint operations fail.

    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(self, job_id: str, operation: str, reason: str):
        """Initialize the exception.

        Args:
            job_id: The ID of the GPU job.
            operation: The checkpoint operation that failed (save/restore).
            reason: Reason for the failure.
        """
        message = f"Checkpoint {operation} failed for job {job_id}: {reason}"
        details = {"job_id": job_id, "operation": operation, "reason": reason}
        super().__init__(message, details)
        self.job_id = job_id
        self.operation = operation
        self.reason = reason


# =============================================================================
# Phase 2: Queue Management Exceptions (ADR-061)
# =============================================================================


class PreemptionError(GPUSchedulerError):
    """Raised when job preemption fails.

    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(
        self,
        preempted_job_id: str,
        preempting_job_id: str,
        reason: str,
    ):
        """Initialize the exception.

        Args:
            preempted_job_id: The ID of the job being preempted.
            preempting_job_id: The ID of the job triggering preemption.
            reason: Reason for the preemption failure.
        """
        message = (
            f"Failed to preempt job {preempted_job_id} "
            f"for {preempting_job_id}: {reason}"
        )
        details = {
            "preempted_job_id": preempted_job_id,
            "preempting_job_id": preempting_job_id,
            "reason": reason,
        }
        super().__init__(message, details)
        self.preempted_job_id = preempted_job_id
        self.preempting_job_id = preempting_job_id
        self.reason = reason


class QueueFullError(GPUSchedulerError):
    """Raised when the queue is at capacity for a priority level.

    Maps to HTTP 503 Service Unavailable.
    """

    def __init__(self, priority: str, current: int, max_allowed: int):
        """Initialize the exception.

        Args:
            priority: The priority level that is at capacity.
            current: Current number of jobs at this priority.
            max_allowed: Maximum allowed jobs at this priority.
        """
        message = f"Queue at capacity for {priority} priority: {current}/{max_allowed}"
        details = {
            "priority": priority,
            "current": current,
            "max_allowed": max_allowed,
        }
        super().__init__(message, details)
        self.priority = priority
        self.current = current
        self.max_allowed = max_allowed


class StarvationPromotionError(GPUSchedulerError):
    """Raised when starvation promotion fails.

    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(self, job_id: str, reason: str):
        """Initialize the exception.

        Args:
            job_id: The ID of the job that could not be promoted.
            reason: Reason for the promotion failure.
        """
        message = f"Failed to promote starved job {job_id}: {reason}"
        details = {"job_id": job_id, "reason": reason}
        super().__init__(message, details)
        self.job_id = job_id
        self.reason = reason


class QueueDispatchError(GPUSchedulerError):
    """Raised when job dispatch from queue fails.

    Maps to HTTP 500 Internal Server Error.
    """

    def __init__(self, job_id: str, reason: str):
        """Initialize the exception.

        Args:
            job_id: The ID of the job that could not be dispatched.
            reason: Reason for the dispatch failure.
        """
        message = f"Failed to dispatch job {job_id}: {reason}"
        details = {"job_id": job_id, "reason": reason}
        super().__init__(message, details)
        self.job_id = job_id
        self.reason = reason


# =============================================================================
# Phase 5: Advanced Features Exceptions (ADR-061)
# =============================================================================


class TemplateNotFoundError(GPUSchedulerError):
    """Raised when a GPU job template is not found.

    Maps to HTTP 404 Not Found.
    """

    def __init__(self, template_id: str, organization_id: str | None = None):
        """Initialize the exception.

        Args:
            template_id: The ID of the template that was not found.
            organization_id: Optional organization ID for context.
        """
        details = {"template_id": template_id}
        if organization_id:
            details["organization_id"] = organization_id
        super().__init__(f"GPU job template not found: {template_id}", details)
        self.template_id = template_id
        self.organization_id = organization_id


class ScheduleNotFoundError(GPUSchedulerError):
    """Raised when a GPU scheduled job is not found.

    Maps to HTTP 404 Not Found.
    """

    def __init__(self, schedule_id: str, organization_id: str | None = None):
        """Initialize the exception.

        Args:
            schedule_id: The ID of the schedule that was not found.
            organization_id: Optional organization ID for context.
        """
        details = {"schedule_id": schedule_id}
        if organization_id:
            details["organization_id"] = organization_id
        super().__init__(f"GPU scheduled job not found: {schedule_id}", details)
        self.schedule_id = schedule_id
        self.organization_id = organization_id


class TemplateAccessDeniedError(GPUSchedulerError):
    """Raised when user doesn't have access to a template.

    Maps to HTTP 403 Forbidden.
    """

    def __init__(self, template_id: str, user_id: str):
        """Initialize the exception.

        Args:
            template_id: The ID of the template.
            user_id: The user who tried to access it.
        """
        message = f"Access denied to template {template_id} for user {user_id}"
        details = {"template_id": template_id, "user_id": user_id}
        super().__init__(message, details)
        self.template_id = template_id
        self.user_id = user_id


class InvalidScheduleError(GPUSchedulerError):
    """Raised when schedule configuration is invalid.

    Maps to HTTP 400 Bad Request.
    """

    def __init__(self, message: str, schedule_id: str | None = None):
        """Initialize the exception.

        Args:
            message: Description of the validation error.
            schedule_id: Optional schedule ID for context.
        """
        details = {}
        if schedule_id:
            details["schedule_id"] = schedule_id
        super().__init__(message, details)
        self.schedule_id = schedule_id
