"""
Circuit Breaker Pattern for Cloud Discovery
============================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Implements the circuit breaker pattern to prevent cascading failures
when cloud provider APIs are unavailable or experiencing issues.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit is open, requests fail fast without calling provider
- HALF_OPEN: Testing if provider has recovered

Configuration:
- failure_threshold: Number of failures before opening circuit
- recovery_timeout: Seconds before attempting recovery
- success_threshold: Successes needed to close circuit from half-open
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

from src.services.cloud_discovery.exceptions import CircuitOpenError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.

    Attributes:
        failure_threshold: Consecutive failures to open circuit
        recovery_timeout_seconds: Seconds before attempting recovery
        success_threshold: Successes to close from half-open
        half_open_max_calls: Max concurrent calls in half-open
    """

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 300.0  # 5 minutes
    success_threshold: int = 3
    half_open_max_calls: int = 1


@dataclass
class CircuitBreakerState:
    """State tracking for a circuit breaker.

    Attributes:
        state: Current circuit state
        failure_count: Consecutive failure count
        success_count: Consecutive success count (in half-open)
        last_failure_time: Time of last failure
        last_state_change: Time of last state transition
        total_failures: Total failures since creation
        total_successes: Total successes since creation
    """

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: datetime | None = None
    last_state_change: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    total_failures: int = 0
    total_successes: int = 0

    # For half-open concurrent call limiting
    half_open_calls: int = 0


class CircuitBreaker:
    """
    Circuit breaker for cloud provider API calls.

    Usage:
        breaker = CircuitBreaker(provider='aws', service='ec2')

        # As context manager
        async with breaker:
            await make_api_call()

        # As decorator
        @breaker.protect
        async def my_api_call():
            ...

        # Manual check
        if breaker.is_call_permitted():
            try:
                result = await make_api_call()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure(e)
    """

    def __init__(
        self,
        provider: str,
        service: str | None = None,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            provider: Cloud provider name
            service: Specific service (e.g., 'ec2', 'rds')
            config: Circuit breaker configuration
        """
        self.provider = provider
        self.service = service
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Get circuit breaker name."""
        if self.service:
            return f"{self.provider}:{self.service}"
        return self.provider

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state.state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing fast)."""
        return self._state.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state.state == CircuitState.HALF_OPEN

    def is_call_permitted(self) -> bool:
        """Check if a call is permitted through the circuit.

        Returns:
            True if call is permitted
        """
        if self._state.state == CircuitState.CLOSED:
            return True

        if self._state.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self._should_attempt_recovery():
                self._transition_to_half_open()
                return True
            return False

        if self._state.state == CircuitState.HALF_OPEN:
            # Limit concurrent calls in half-open
            return self._state.half_open_calls < self.config.half_open_max_calls

        return False

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._state.last_failure_time is None:
            return True

        elapsed = datetime.now(timezone.utc) - self._state.last_failure_time
        return elapsed.total_seconds() >= self.config.recovery_timeout_seconds

    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN."""
        self._state.state = CircuitState.HALF_OPEN
        self._state.success_count = 0
        self._state.half_open_calls = 0
        self._state.last_state_change = datetime.now(timezone.utc)
        logger.info(f"Circuit {self.name} transitioned to HALF_OPEN")

    def record_success(self) -> None:
        """Record a successful call."""
        self._state.total_successes += 1

        if self._state.state == CircuitState.HALF_OPEN:
            self._state.success_count += 1
            self._state.half_open_calls = max(0, self._state.half_open_calls - 1)

            if self._state.success_count >= self.config.success_threshold:
                self._close_circuit()
        elif self._state.state == CircuitState.CLOSED:
            # Reset failure count on success
            self._state.failure_count = 0

    def _close_circuit(self) -> None:
        """Close the circuit (return to normal operation)."""
        self._state.state = CircuitState.CLOSED
        self._state.failure_count = 0
        self._state.success_count = 0
        self._state.last_state_change = datetime.now(timezone.utc)
        logger.info(f"Circuit {self.name} CLOSED - recovered")

    def record_failure(self, error: Exception | None = None) -> None:
        """Record a failed call.

        Args:
            error: The exception that caused the failure
        """
        self._state.total_failures += 1
        self._state.failure_count += 1
        self._state.last_failure_time = datetime.now(timezone.utc)

        if self._state.state == CircuitState.HALF_OPEN:
            self._state.half_open_calls = max(0, self._state.half_open_calls - 1)
            self._open_circuit()
        elif self._state.state == CircuitState.CLOSED:
            if self._state.failure_count >= self.config.failure_threshold:
                self._open_circuit()

        if error:
            logger.warning(
                f"Circuit {self.name} recorded failure: {type(error).__name__}"
            )

    def _open_circuit(self) -> None:
        """Open the circuit (start failing fast)."""
        self._state.state = CircuitState.OPEN
        self._state.last_state_change = datetime.now(timezone.utc)
        logger.warning(
            f"Circuit {self.name} OPENED after {self._state.failure_count} failures"
        )

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitBreakerState()
        logger.info(f"Circuit {self.name} reset")

    def get_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics.

        Returns:
            Dict with circuit breaker stats
        """
        return {
            "name": self.name,
            "provider": self.provider,
            "service": self.service,
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "total_failures": self._state.total_failures,
            "total_successes": self._state.total_successes,
            "last_failure": (
                self._state.last_failure_time.isoformat()
                if self._state.last_failure_time
                else None
            ),
            "last_state_change": self._state.last_state_change.isoformat(),
            "recovery_timeout_seconds": self.config.recovery_timeout_seconds,
        }

    async def __aenter__(self) -> "CircuitBreaker":
        """Async context manager entry."""
        async with self._lock:
            if not self.is_call_permitted():
                raise CircuitOpenError(
                    f"Circuit {self.name} is open",
                    provider=self.provider,
                    service=self.service,
                    failures_count=self._state.failure_count,
                    recovery_time_seconds=self._time_until_recovery(),
                )
            if self.is_half_open:
                self._state.half_open_calls += 1
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Async context manager exit."""
        if exc_val is None:
            self.record_success()
        else:
            self.record_failure(exc_val)
        return False  # Don't suppress exceptions

    def _time_until_recovery(self) -> float:
        """Calculate seconds until recovery attempt."""
        if self._state.last_failure_time is None:
            return 0.0

        elapsed = datetime.now(timezone.utc) - self._state.last_failure_time
        remaining = self.config.recovery_timeout_seconds - elapsed.total_seconds()
        return max(0.0, remaining)

    def protect(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to protect a function with circuit breaker.

        Usage:
            @breaker.protect
            async def my_api_call():
                ...

        Args:
            func: Async function to protect

        Returns:
            Wrapped function with circuit breaker protection
        """

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async with self:
                return await func(*args, **kwargs)

        return wrapper


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Provides centralized management of circuit breakers for
    different providers and services.

    Usage:
        registry = CircuitBreakerRegistry()

        # Get or create circuit breaker
        breaker = registry.get_breaker('aws', 'ec2')

        # Check all breaker states
        states = registry.get_all_states()
    """

    def __init__(self, default_config: CircuitBreakerConfig | None = None) -> None:
        """Initialize registry.

        Args:
            default_config: Default config for new breakers
        """
        self.default_config = default_config or CircuitBreakerConfig()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    def get_breaker(
        self,
        provider: str,
        service: str | None = None,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker.

        Args:
            provider: Cloud provider name
            service: Optional service name
            config: Optional custom config

        Returns:
            Circuit breaker instance
        """
        key = f"{provider}:{service}" if service else provider

        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker(
                provider=provider,
                service=service,
                config=config or self.default_config,
            )

        return self._breakers[key]

    def is_provider_available(self, provider: str) -> bool:
        """Check if any circuit for a provider is open.

        Args:
            provider: Provider name

        Returns:
            True if at least one service is available
        """
        found_any = False
        for key, breaker in self._breakers.items():
            if key.startswith(f"{provider}:") or key == provider:
                found_any = True
                if breaker.is_call_permitted():
                    return True

        # No breakers registered means provider hasn't been tried
        # If breakers exist but none permit calls, provider is unavailable
        return not found_any

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """Get states of all circuit breakers.

        Returns:
            Dict mapping breaker names to their metrics
        """
        return {key: breaker.get_metrics() for key, breaker in self._breakers.items()}

    def get_open_circuits(self) -> list[str]:
        """Get list of open circuit names.

        Returns:
            List of breaker names that are currently open
        """
        return [key for key, breaker in self._breakers.items() if breaker.is_open]

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()
        logger.info(f"Reset {len(self._breakers)} circuit breakers")

    def reset_provider(self, provider: str) -> int:
        """Reset all circuit breakers for a provider.

        Args:
            provider: Provider name

        Returns:
            Number of breakers reset
        """
        count = 0
        for key, breaker in self._breakers.items():
            if key.startswith(f"{provider}:") or key == provider:
                breaker.reset()
                count += 1
        logger.info(f"Reset {count} circuit breakers for {provider}")
        return count


# Module-level registry instance
_default_registry: CircuitBreakerRegistry | None = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the default circuit breaker registry.

    Returns:
        Default CircuitBreakerRegistry instance
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = CircuitBreakerRegistry()
    return _default_registry


def get_circuit_breaker(
    provider: str,
    service: str | None = None,
) -> CircuitBreaker:
    """Convenience function to get a circuit breaker.

    Args:
        provider: Cloud provider name
        service: Optional service name

    Returns:
        Circuit breaker instance
    """
    return get_circuit_breaker_registry().get_breaker(provider, service)
