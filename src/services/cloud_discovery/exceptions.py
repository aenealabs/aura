"""
Cloud Discovery Exception Definitions
=======================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Custom exceptions for cloud resource discovery and credential management.
"""

from typing import Any


class CloudDiscoveryError(Exception):
    """Base exception for cloud discovery operations.

    All cloud discovery exceptions inherit from this base class,
    enabling broad exception handling when needed.

    Attributes:
        message: Error message
        details: Additional error details
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize CloudDiscoveryError.

        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CredentialError(CloudDiscoveryError):
    """Exception raised for credential access or validation failures.

    Raised when:
    - Credentials are not found in Secrets Manager
    - Credentials have expired
    - Credential validation fails
    - Permission denied accessing credentials

    Attributes:
        provider: Cloud provider for which credentials failed
        account_id: Account ID if known
        reason: Specific reason for credential failure
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        account_id: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CredentialError.

        Args:
            message: Error message
            provider: Cloud provider
            account_id: Account ID
            reason: Specific reason for failure
            details: Additional details
        """
        super().__init__(message, details)
        self.provider = provider
        self.account_id = account_id
        self.reason = reason


class ProviderError(CloudDiscoveryError):
    """Exception raised when cloud provider API calls fail.

    Raised when:
    - API call returns error status
    - Provider returns unexpected response
    - Service-specific errors occur

    Attributes:
        provider: Cloud provider that failed
        service: Specific service that failed (e.g., 'ec2', 'rds')
        operation: API operation that failed
        error_code: Provider-specific error code
        is_retryable: Whether the operation can be retried
    """

    def __init__(
        self,
        message: str,
        provider: str,
        service: str | None = None,
        operation: str | None = None,
        error_code: str | None = None,
        is_retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ProviderError.

        Args:
            message: Error message
            provider: Cloud provider
            service: AWS/Azure service name
            operation: API operation
            error_code: Provider error code
            is_retryable: Whether operation can be retried
            details: Additional details
        """
        super().__init__(message, details)
        self.provider = provider
        self.service = service
        self.operation = operation
        self.error_code = error_code
        self.is_retryable = is_retryable


class RateLimitError(CloudDiscoveryError):
    """Exception raised when API rate limits are exceeded.

    Raised when:
    - Provider returns throttling response
    - Too many requests in time window

    Attributes:
        provider: Cloud provider that rate limited
        service: Specific service that was rate limited
        retry_after_seconds: Suggested retry delay in seconds
    """

    def __init__(
        self,
        message: str,
        provider: str,
        service: str | None = None,
        retry_after_seconds: float = 60.0,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize RateLimitError.

        Args:
            message: Error message
            provider: Cloud provider
            service: AWS/Azure service name
            retry_after_seconds: Suggested retry delay
            details: Additional details
        """
        super().__init__(message, details)
        self.provider = provider
        self.service = service
        self.retry_after_seconds = retry_after_seconds


class CircuitOpenError(CloudDiscoveryError):
    """Exception raised when circuit breaker is open.

    The circuit breaker pattern prevents cascading failures by
    stopping requests to a failing service temporarily.

    Raised when:
    - Too many consecutive failures to a provider/service
    - Circuit breaker has not yet recovered

    Attributes:
        provider: Cloud provider with open circuit
        service: Specific service with open circuit
        failures_count: Number of consecutive failures
        recovery_time_seconds: Seconds until circuit may close
    """

    def __init__(
        self,
        message: str,
        provider: str,
        service: str | None = None,
        failures_count: int = 0,
        recovery_time_seconds: float = 300.0,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CircuitOpenError.

        Args:
            message: Error message
            provider: Cloud provider
            service: AWS/Azure service name
            failures_count: Number of consecutive failures
            recovery_time_seconds: Seconds until recovery
            details: Additional details
        """
        super().__init__(message, details)
        self.provider = provider
        self.service = service
        self.failures_count = failures_count
        self.recovery_time_seconds = recovery_time_seconds


class DiscoveryTimeoutError(CloudDiscoveryError):
    """Exception raised when discovery operation times out.

    Raised when:
    - Discovery takes longer than configured timeout
    - Provider API is unresponsive

    Attributes:
        provider: Cloud provider that timed out
        operation: Operation that timed out
        timeout_seconds: Configured timeout that was exceeded
        partial_results: Any results obtained before timeout
    """

    def __init__(
        self,
        message: str,
        provider: str,
        operation: str | None = None,
        timeout_seconds: float = 300.0,
        partial_results: list[Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize DiscoveryTimeoutError.

        Args:
            message: Error message
            provider: Cloud provider
            operation: Operation that timed out
            timeout_seconds: Configured timeout
            partial_results: Results before timeout
            details: Additional details
        """
        super().__init__(message, details)
        self.provider = provider
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        self.partial_results = partial_results or []


class GovCloudUnavailableError(CloudDiscoveryError):
    """Exception raised when a service is unavailable in GovCloud.

    Some AWS services are not available in GovCloud regions:
    - AWS Application Discovery Service
    - AWS Resource Explorer
    - AWS Service Catalog AppRegistry

    This exception indicates that an alternative approach is needed.

    Attributes:
        service: Service that is unavailable
        region: GovCloud region
        alternative: Suggested alternative service/approach
    """

    def __init__(
        self,
        message: str,
        service: str,
        region: str,
        alternative: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize GovCloudUnavailableError.

        Args:
            message: Error message
            service: Unavailable service
            region: GovCloud region
            alternative: Alternative approach
            details: Additional details
        """
        super().__init__(message, details)
        self.service = service
        self.region = region
        self.alternative = alternative


class CrossAccountError(CloudDiscoveryError):
    """Exception raised for cross-account access failures.

    Raised when:
    - Role assumption fails
    - External ID mismatch
    - Cross-account permissions denied

    Attributes:
        source_account: Account initiating the access
        target_account: Account being accessed
        role_arn: Role ARN that failed to assume
        reason: Specific reason for failure
    """

    def __init__(
        self,
        message: str,
        source_account: str | None = None,
        target_account: str | None = None,
        role_arn: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CrossAccountError.

        Args:
            message: Error message
            source_account: Source AWS account
            target_account: Target AWS account
            role_arn: Role that failed to assume
            reason: Specific failure reason
            details: Additional details
        """
        super().__init__(message, details)
        self.source_account = source_account
        self.target_account = target_account
        self.role_arn = role_arn
        self.reason = reason


class IaCParseError(CloudDiscoveryError):
    """Exception raised when IaC template parsing fails.

    Raised when:
    - CloudFormation/Terraform syntax errors
    - Unsupported template features
    - Missing required properties

    Attributes:
        file_path: Path to the IaC file
        line_number: Line where error occurred
        template_type: Type of IaC template (cloudformation, terraform)
    """

    def __init__(
        self,
        message: str,
        file_path: str,
        line_number: int | None = None,
        template_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize IaCParseError.

        Args:
            message: Error message
            file_path: Path to IaC file
            line_number: Line number if known
            template_type: Type of template
            details: Additional details
        """
        super().__init__(message, details)
        self.file_path = file_path
        self.line_number = line_number
        self.template_type = template_type


class CorrelationError(CloudDiscoveryError):
    """Exception raised when IaC-to-resource correlation fails.

    Raised when:
    - Unable to match IaC to deployed resources
    - Ambiguous resource matching
    - Stack lookup fails

    Attributes:
        repository_id: Repository being correlated
        logical_id: IaC logical ID that failed to correlate
        reason: Specific reason for failure
    """

    def __init__(
        self,
        message: str,
        repository_id: str | None = None,
        logical_id: str | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CorrelationError.

        Args:
            message: Error message
            repository_id: Repository ID
            logical_id: IaC logical ID
            reason: Failure reason
            details: Additional details
        """
        super().__init__(message, details)
        self.repository_id = repository_id
        self.logical_id = logical_id
        self.reason = reason
