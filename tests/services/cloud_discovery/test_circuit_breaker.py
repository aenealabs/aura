"""
Tests for Circuit Breaker Pattern
=================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Tests for circuit breaker state management and fault tolerance.
"""

import platform

import pytest

# pytest-forked on macOS to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.cloud_discovery.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitBreakerState,
    CircuitState,
    get_circuit_breaker,
    get_circuit_breaker_registry,
)
from src.services.cloud_discovery.exceptions import CircuitOpenError


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_state_values(self) -> None:
        """Test circuit state values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout_seconds == 300.0
        assert config.success_threshold == 3
        assert config.half_open_max_calls == 1

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout_seconds=60.0,
            success_threshold=5,
            half_open_max_calls=3,
        )
        assert config.failure_threshold == 10
        assert config.recovery_timeout_seconds == 60.0
        assert config.success_threshold == 5
        assert config.half_open_max_calls == 3


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState."""

    def test_default_state(self) -> None:
        """Test default state values."""
        state = CircuitBreakerState()
        assert state.state == CircuitState.CLOSED
        assert state.failure_count == 0
        assert state.success_count == 0
        assert state.last_failure_time is None
        assert state.total_failures == 0
        assert state.total_successes == 0
        assert state.half_open_calls == 0


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_create_breaker(self) -> None:
        """Test creating circuit breaker."""
        breaker = CircuitBreaker(provider="aws", service="ec2")
        assert breaker.provider == "aws"
        assert breaker.service == "ec2"
        assert breaker.name == "aws:ec2"
        assert breaker.state == CircuitState.CLOSED

    def test_breaker_without_service(self) -> None:
        """Test breaker name without service."""
        breaker = CircuitBreaker(provider="aws")
        assert breaker.name == "aws"

    def test_is_closed_property(self) -> None:
        """Test is_closed property."""
        breaker = CircuitBreaker(provider="aws")
        assert breaker.is_closed is True
        assert breaker.is_open is False
        assert breaker.is_half_open is False

    def test_is_call_permitted_when_closed(self) -> None:
        """Test calls are permitted when closed."""
        breaker = CircuitBreaker(provider="aws")
        assert breaker.is_call_permitted() is True

    def test_record_success_resets_failure_count(self) -> None:
        """Test success resets failure count in closed state."""
        breaker = CircuitBreaker(provider="aws")
        breaker._state.failure_count = 3
        breaker.record_success()
        assert breaker._state.failure_count == 0
        assert breaker._state.total_successes == 1

    def test_record_failure_increments_count(self) -> None:
        """Test failure increments failure count."""
        breaker = CircuitBreaker(provider="aws")
        breaker.record_failure()
        assert breaker._state.failure_count == 1
        assert breaker._state.total_failures == 1
        assert breaker._state.last_failure_time is not None

    def test_circuit_opens_after_threshold(self) -> None:
        """Test circuit opens after failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(provider="aws", config=config)

        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open is True
        assert breaker.state == CircuitState.OPEN

    def test_is_call_permitted_when_open(self) -> None:
        """Test calls not permitted when open."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=300.0,
        )
        breaker = CircuitBreaker(provider="aws", config=config)

        breaker.record_failure()  # Opens circuit
        assert breaker.is_open is True
        assert breaker.is_call_permitted() is False

    def test_circuit_transitions_to_half_open(self) -> None:
        """Test circuit transitions to half-open after recovery timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,  # Immediate recovery for test
        )
        breaker = CircuitBreaker(provider="aws", config=config)

        breaker.record_failure()  # Opens circuit
        assert breaker.is_open is True

        # With 0 recovery timeout, should immediately transition
        assert breaker.is_call_permitted() is True
        assert breaker.is_half_open is True

    def test_half_open_limits_concurrent_calls(self) -> None:
        """Test half-open state limits concurrent calls."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,
            half_open_max_calls=1,
        )
        breaker = CircuitBreaker(provider="aws", config=config)

        breaker.record_failure()
        assert breaker.is_call_permitted() is True  # Transitions to half-open

        # Simulate a call in progress
        breaker._state.half_open_calls = 1

        # Second call should not be permitted
        assert breaker.is_call_permitted() is False

    def test_half_open_closes_on_success_threshold(self) -> None:
        """Test half-open closes after success threshold."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,
            success_threshold=2,
        )
        breaker = CircuitBreaker(provider="aws", config=config)

        breaker.record_failure()  # Opens circuit
        breaker.is_call_permitted()  # Transitions to half-open

        assert breaker.is_half_open is True

        breaker.record_success()
        assert breaker.is_half_open is True  # Not yet

        breaker.record_success()
        assert breaker.is_closed is True  # Now closed

    def test_half_open_reopens_on_failure(self) -> None:
        """Test half-open reopens on failure."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,
        )
        breaker = CircuitBreaker(provider="aws", config=config)

        breaker.record_failure()  # Opens circuit
        breaker.is_call_permitted()  # Transitions to half-open

        assert breaker.is_half_open is True

        breaker.record_failure()
        assert breaker.is_open is True

    def test_reset_clears_state(self) -> None:
        """Test reset clears all state."""
        breaker = CircuitBreaker(provider="aws")

        breaker.record_failure()
        breaker.record_failure()
        assert breaker._state.failure_count == 2

        breaker.reset()
        assert breaker._state.failure_count == 0
        assert breaker._state.state == CircuitState.CLOSED

    def test_get_metrics(self) -> None:
        """Test metrics retrieval."""
        breaker = CircuitBreaker(provider="aws", service="ec2")

        breaker.record_success()
        breaker.record_failure()

        metrics = breaker.get_metrics()
        assert metrics["name"] == "aws:ec2"
        assert metrics["provider"] == "aws"
        assert metrics["service"] == "ec2"
        assert metrics["state"] == "closed"
        assert metrics["total_failures"] == 1
        assert metrics["total_successes"] == 1

    def test_time_until_recovery(self) -> None:
        """Test time until recovery calculation."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=300.0,
        )
        breaker = CircuitBreaker(provider="aws", config=config)

        # No failure yet
        assert breaker._time_until_recovery() == 0.0

        # After failure
        breaker.record_failure()
        recovery_time = breaker._time_until_recovery()
        assert 299.0 <= recovery_time <= 300.0


class TestCircuitBreakerAsync:
    """Tests for async circuit breaker operations."""

    @pytest.mark.asyncio
    async def test_context_manager_success(self) -> None:
        """Test context manager with successful call."""
        breaker = CircuitBreaker(provider="aws")

        async with breaker:
            pass  # Successful call

        assert breaker._state.total_successes == 1
        assert breaker._state.failure_count == 0

    @pytest.mark.asyncio
    async def test_context_manager_failure(self) -> None:
        """Test context manager with failed call."""
        breaker = CircuitBreaker(provider="aws")

        with pytest.raises(ValueError):
            async with breaker:
                raise ValueError("test error")

        assert breaker._state.total_failures == 1
        assert breaker._state.failure_count == 1

    @pytest.mark.asyncio
    async def test_context_manager_raises_when_open(self) -> None:
        """Test context manager raises when circuit is open."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=300.0,
        )
        breaker = CircuitBreaker(provider="aws", service="ec2", config=config)

        breaker.record_failure()  # Opens circuit

        with pytest.raises(CircuitOpenError) as exc_info:
            async with breaker:
                pass

        assert exc_info.value.provider == "aws"
        assert exc_info.value.service == "ec2"

    @pytest.mark.asyncio
    async def test_protect_decorator_success(self) -> None:
        """Test protect decorator with successful call."""
        breaker = CircuitBreaker(provider="aws")

        @breaker.protect
        async def my_func() -> str:
            return "success"

        result = await my_func()
        assert result == "success"
        assert breaker._state.total_successes == 1

    @pytest.mark.asyncio
    async def test_protect_decorator_failure(self) -> None:
        """Test protect decorator with failed call."""
        breaker = CircuitBreaker(provider="aws")

        @breaker.protect
        async def failing_func() -> str:
            raise RuntimeError("error")

        with pytest.raises(RuntimeError):
            await failing_func()

        assert breaker._state.total_failures == 1

    @pytest.mark.asyncio
    async def test_half_open_increments_calls_on_entry(self) -> None:
        """Test half-open state increments call count on entry."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.0,
        )
        breaker = CircuitBreaker(provider="aws", config=config)

        breaker.record_failure()  # Opens circuit

        async with breaker:
            # Should be in half-open with call in progress
            pass

        # Call completed, should decrement
        assert breaker._state.half_open_calls == 0


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""

    def test_create_registry(self) -> None:
        """Test creating registry."""
        registry = CircuitBreakerRegistry()
        assert registry.default_config is not None

    def test_get_breaker_creates_new(self) -> None:
        """Test get_breaker creates new breaker."""
        registry = CircuitBreakerRegistry()
        breaker = registry.get_breaker("aws", "ec2")

        assert breaker.provider == "aws"
        assert breaker.service == "ec2"

    def test_get_breaker_returns_existing(self) -> None:
        """Test get_breaker returns existing breaker."""
        registry = CircuitBreakerRegistry()
        breaker1 = registry.get_breaker("aws", "ec2")
        breaker2 = registry.get_breaker("aws", "ec2")

        assert breaker1 is breaker2

    def test_get_breaker_with_custom_config(self) -> None:
        """Test get_breaker with custom config."""
        registry = CircuitBreakerRegistry()
        custom_config = CircuitBreakerConfig(failure_threshold=10)
        breaker = registry.get_breaker("aws", "lambda", config=custom_config)

        assert breaker.config.failure_threshold == 10

    def test_is_provider_available(self) -> None:
        """Test provider availability check."""
        registry = CircuitBreakerRegistry()

        # No breakers registered - available by default
        assert registry.is_provider_available("aws") is True

        # Register a closed breaker
        breaker = registry.get_breaker("aws", "ec2")
        assert registry.is_provider_available("aws") is True

        # Open the circuit
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=300)
        breaker = CircuitBreaker(provider="aws", service="ec2", config=config)
        breaker.record_failure()
        registry._breakers["aws:ec2"] = breaker

        assert registry.is_provider_available("aws") is False

    def test_get_all_states(self) -> None:
        """Test getting all states."""
        registry = CircuitBreakerRegistry()
        registry.get_breaker("aws", "ec2")
        registry.get_breaker("aws", "lambda")

        states = registry.get_all_states()
        assert "aws:ec2" in states
        assert "aws:lambda" in states
        assert states["aws:ec2"]["state"] == "closed"

    def test_get_open_circuits(self) -> None:
        """Test getting open circuits."""
        registry = CircuitBreakerRegistry()

        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = registry.get_breaker("aws", "ec2", config=config)
        breaker.record_failure()  # Opens circuit

        registry.get_breaker("aws", "lambda")  # Closed

        open_circuits = registry.get_open_circuits()
        assert "aws:ec2" in open_circuits
        assert "aws:lambda" not in open_circuits

    def test_reset_all(self) -> None:
        """Test resetting all breakers."""
        registry = CircuitBreakerRegistry()

        config = CircuitBreakerConfig(failure_threshold=1)
        breaker1 = registry.get_breaker("aws", "ec2", config=config)
        breaker2 = registry.get_breaker("aws", "lambda", config=config)

        breaker1.record_failure()
        breaker2.record_failure()

        assert breaker1.is_open
        assert breaker2.is_open

        registry.reset_all()

        assert breaker1.is_closed
        assert breaker2.is_closed

    def test_reset_provider(self) -> None:
        """Test resetting specific provider."""
        registry = CircuitBreakerRegistry()

        config = CircuitBreakerConfig(failure_threshold=1)
        aws_breaker = registry.get_breaker("aws", "ec2", config=config)
        azure_breaker = registry.get_breaker("azure", "vm", config=config)

        aws_breaker.record_failure()
        azure_breaker.record_failure()

        count = registry.reset_provider("aws")
        assert count == 1
        assert aws_breaker.is_closed
        assert azure_breaker.is_open


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_circuit_breaker_registry(self) -> None:
        """Test getting default registry."""
        # Clear module-level registry for test isolation
        import src.services.cloud_discovery.circuit_breaker as cb_module

        cb_module._default_registry = None

        registry1 = get_circuit_breaker_registry()
        registry2 = get_circuit_breaker_registry()

        assert registry1 is registry2

    def test_get_circuit_breaker(self) -> None:
        """Test convenience function for getting breaker."""
        import src.services.cloud_discovery.circuit_breaker as cb_module

        cb_module._default_registry = None

        breaker = get_circuit_breaker("aws", "s3")
        assert breaker.provider == "aws"
        assert breaker.service == "s3"
