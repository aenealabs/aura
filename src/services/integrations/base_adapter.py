"""
Base Integration Adapter - Abstract interface for all external integrations.

This module defines the base adapter pattern that all integrations (IDE extensions,
data platforms, etc.) must implement. Provides standardized error handling, retry
logic, and lifecycle management.

ADR Reference: ADR-048 Phase 0 - Integration Abstraction Layer
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)


class IntegrationType(Enum):
    """Categories of integrations supported by Aura."""

    IDE = "ide"  # VSCode, PyCharm, Jupyter
    DATA_PLATFORM = "data_platform"  # Dataiku, Fivetran
    EXPORT = "export"  # Generic export API for BI tools
    MONITORING = "monitoring"  # Splunk, Datadog
    SECURITY = "security"  # Qualys, Snyk
    TICKETING = "ticketing"  # Zendesk, ServiceNow, Linear


class IntegrationStatus(Enum):
    """Connection status for an integration."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CONFIGURING = "configuring"
    RATE_LIMITED = "rate_limited"


@dataclass
class IntegrationConfig:
    """Configuration for an integration instance."""

    integration_id: str
    integration_type: IntegrationType
    provider: str  # e.g., "vscode", "jupyter", "dataiku"
    organization_id: str
    user_id: str | None = None
    credentials: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "integration_id": self.integration_id,
            "integration_type": self.integration_type.value,
            "provider": self.provider,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "settings": self.settings,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class IntegrationResult:
    """Result of an integration operation."""

    success: bool
    data: Any = None
    error_message: str | None = None
    error_code: str | None = None
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "success": self.success,
            "latency_ms": self.latency_ms,
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error_message:
            result["error"] = {
                "message": self.error_message,
                "code": self.error_code,
            }
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class IntegrationError(Exception):
    """Base exception for integration errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTEGRATION_ERROR",
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable
        self.details = details or {}


class AuthenticationError(IntegrationError):
    """Authentication failed for integration."""

    def __init__(
        self, message: str = "Authentication failed", details: dict | None = None
    ):
        super().__init__(message, code="AUTH_ERROR", retryable=False, details=details)


class RateLimitError(IntegrationError):
    """Rate limit exceeded for integration."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after_seconds: int = 60,
        details: dict | None = None,
    ):
        super().__init__(message, code="RATE_LIMIT", retryable=True, details=details)
        self.retry_after_seconds = retry_after_seconds


class ConnectionError(IntegrationError):
    """Connection failed for integration."""

    def __init__(self, message: str = "Connection failed", details: dict | None = None):
        super().__init__(
            message, code="CONNECTION_ERROR", retryable=True, details=details
        )


class ValidationError(IntegrationError):
    """Validation failed for integration request."""

    def __init__(
        self, message: str, field: str | None = None, details: dict | None = None
    ):
        super().__init__(
            message, code="VALIDATION_ERROR", retryable=False, details=details
        )
        self.field = field


T = TypeVar("T")


class BaseIntegrationAdapter(ABC, Generic[T]):
    """
    Abstract base class for all integration adapters.

    All integrations must implement this interface to ensure consistent
    behavior, error handling, and lifecycle management.
    """

    def __init__(self, config: IntegrationConfig):
        self.config = config
        self._status = IntegrationStatus.DISCONNECTED
        self._last_error: IntegrationError | None = None
        self._retry_config = RetryConfig()

    @property
    def provider(self) -> str:
        """Return the provider name for this adapter."""
        return self.config.provider

    @property
    def integration_type(self) -> IntegrationType:
        """Return the integration type."""
        return self.config.integration_type

    @property
    def status(self) -> IntegrationStatus:
        """Return current connection status."""
        return self._status

    @abstractmethod
    async def connect(self) -> IntegrationResult:
        """
        Establish connection to the external service.

        Returns:
            IntegrationResult with connection status
        """

    @abstractmethod
    async def disconnect(self) -> IntegrationResult:
        """
        Gracefully disconnect from the external service.

        Returns:
            IntegrationResult with disconnection status
        """

    @abstractmethod
    async def health_check(self) -> IntegrationResult:
        """
        Perform health check on the integration.

        Returns:
            IntegrationResult with health status and latency
        """

    @abstractmethod
    async def execute(
        self, operation: str, payload: dict[str, Any]
    ) -> IntegrationResult:
        """
        Execute an operation on the integration.

        Args:
            operation: Name of the operation to execute
            payload: Operation-specific payload

        Returns:
            IntegrationResult with operation outcome
        """

    async def execute_with_retry(
        self,
        operation: str,
        payload: dict[str, Any],
        retry_config: "RetryConfig | None" = None,
    ) -> IntegrationResult:
        """
        Execute an operation with automatic retry logic.

        Args:
            operation: Name of the operation to execute
            payload: Operation-specific payload
            retry_config: Optional override for retry configuration

        Returns:
            IntegrationResult with operation outcome
        """
        config = retry_config or self._retry_config
        last_error: Exception | None = None

        for attempt in range(config.max_retries + 1):
            try:
                result = await self.execute(operation, payload)
                if result.success:
                    return result

                # Check if error is retryable
                if result.error_code in config.retryable_codes:
                    last_error = IntegrationError(
                        result.error_message or "Unknown error",
                        code=result.error_code or "UNKNOWN",
                        retryable=True,
                    )
                else:
                    return result

            except RateLimitError as e:
                last_error = e
                wait_time = e.retry_after_seconds
                logger.warning(
                    f"Rate limited on {operation}, waiting {wait_time}s (attempt {attempt + 1})"
                )
                await asyncio.sleep(wait_time)
                continue

            except IntegrationError as e:
                if not e.retryable:
                    return IntegrationResult(
                        success=False,
                        error_message=e.message,
                        error_code=e.code,
                    )
                last_error = e

            except Exception as e:
                last_error = e
                logger.exception(f"Unexpected error in {operation}")

            # Exponential backoff
            if attempt < config.max_retries:
                wait_time = config.base_delay_seconds * (
                    config.backoff_multiplier**attempt
                )
                wait_time = min(wait_time, config.max_delay_seconds)
                logger.info(
                    f"Retrying {operation} in {wait_time:.1f}s (attempt {attempt + 2})"
                )
                await asyncio.sleep(wait_time)

        # All retries exhausted
        error_msg = str(last_error) if last_error else "Max retries exceeded"
        return IntegrationResult(
            success=False,
            error_message=error_msg,
            error_code="MAX_RETRIES_EXCEEDED",
        )

    def validate_config(self) -> list[str]:
        """
        Validate the integration configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.config.integration_id:
            errors.append("integration_id is required")

        if not self.config.organization_id:
            errors.append("organization_id is required")

        if not self.config.provider:
            errors.append("provider is required")

        # Subclasses should override to add provider-specific validation
        return errors


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    retryable_codes: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "CONNECTION_ERROR",
                "RATE_LIMIT",
                "TIMEOUT",
                "SERVICE_UNAVAILABLE",
            }
        )
    )
