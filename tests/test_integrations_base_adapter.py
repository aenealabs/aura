"""
Tests for the Integration Base Adapter module.

Tests the abstract base class for all integrations, including
error handling, retry logic, and configuration validation.
"""

from datetime import datetime, timezone

import pytest

from src.services.integrations.base_adapter import (
    AuthenticationError,
    BaseIntegrationAdapter,
    ConnectionError,
    IntegrationConfig,
    IntegrationError,
    IntegrationResult,
    IntegrationStatus,
    IntegrationType,
    RateLimitError,
    RetryConfig,
    ValidationError,
)


# Concrete implementation for testing
class MockIntegrationAdapter(BaseIntegrationAdapter):
    """Mock adapter for testing base class functionality."""

    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.health_check_calls = 0
        self.execute_calls = []
        self.should_fail = False
        self.failure_count = 0
        self.max_failures = 0

    async def connect(self) -> IntegrationResult:
        self.connect_calls += 1
        if self.should_fail:
            self._status = IntegrationStatus.ERROR
            return IntegrationResult(
                success=False,
                error_message="Connection failed",
                error_code="CONNECTION_ERROR",
            )
        self._status = IntegrationStatus.CONNECTED
        return IntegrationResult(success=True, data={"connected": True})

    async def disconnect(self) -> IntegrationResult:
        self.disconnect_calls += 1
        self._status = IntegrationStatus.DISCONNECTED
        return IntegrationResult(success=True)

    async def health_check(self) -> IntegrationResult:
        self.health_check_calls += 1
        return IntegrationResult(success=True, data={"healthy": True}, latency_ms=50.0)

    async def execute(self, operation: str, payload: dict) -> IntegrationResult:
        self.execute_calls.append((operation, payload))

        if self.max_failures > 0 and self.failure_count < self.max_failures:
            self.failure_count += 1
            raise ConnectionError("Temporary failure")

        if self.should_fail:
            return IntegrationResult(
                success=False,
                error_message="Operation failed",
                error_code="OPERATION_ERROR",
            )
        return IntegrationResult(success=True, data={"result": operation})


@pytest.fixture
def mock_config():
    """Create a mock integration config."""
    return IntegrationConfig(
        integration_id="test-123",
        integration_type=IntegrationType.IDE,
        provider="vscode",
        organization_id="org-456",
        user_id="user-789",
        credentials={"token": "test-token"},
        settings={"auto_scan": True},
    )


@pytest.fixture
def mock_adapter(mock_config):
    """Create a mock adapter instance."""
    return MockIntegrationAdapter(mock_config)


class TestIntegrationConfig:
    """Tests for IntegrationConfig dataclass."""

    def test_config_creation(self, mock_config):
        """Test creating a config with all fields."""
        assert mock_config.integration_id == "test-123"
        assert mock_config.integration_type == IntegrationType.IDE
        assert mock_config.provider == "vscode"
        assert mock_config.organization_id == "org-456"
        assert mock_config.user_id == "user-789"
        assert mock_config.enabled is True

    def test_config_to_dict(self, mock_config):
        """Test config serialization."""
        result = mock_config.to_dict()

        assert result["integration_id"] == "test-123"
        assert result["integration_type"] == "ide"
        assert result["provider"] == "vscode"
        assert "credentials" not in result  # Should not expose credentials

    def test_config_default_timestamps(self, mock_config):
        """Test that timestamps are set by default."""
        assert mock_config.created_at is not None
        assert mock_config.updated_at is not None
        assert mock_config.created_at <= datetime.now(timezone.utc)


class TestIntegrationResult:
    """Tests for IntegrationResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = IntegrationResult(
            success=True, data={"findings": []}, latency_ms=100.0
        )

        assert result.success is True
        assert result.data == {"findings": []}
        assert result.latency_ms == 100.0
        assert result.error_message is None

    def test_error_result(self):
        """Test creating an error result."""
        result = IntegrationResult(
            success=False,
            error_message="Authentication failed",
            error_code="AUTH_ERROR",
        )

        assert result.success is False
        assert result.error_message == "Authentication failed"
        assert result.error_code == "AUTH_ERROR"

    def test_result_to_dict_success(self):
        """Test serializing success result."""
        result = IntegrationResult(success=True, data={"status": "ok"})
        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["data"] == {"status": "ok"}
        assert "error" not in result_dict

    def test_result_to_dict_error(self):
        """Test serializing error result."""
        result = IntegrationResult(
            success=False, error_message="Failed", error_code="ERROR"
        )
        result_dict = result.to_dict()

        assert result_dict["success"] is False
        assert result_dict["error"]["message"] == "Failed"
        assert result_dict["error"]["code"] == "ERROR"


class TestIntegrationErrors:
    """Tests for integration error classes."""

    def test_integration_error(self):
        """Test base IntegrationError."""
        error = IntegrationError("Something went wrong", code="TEST_ERROR")

        assert str(error) == "Something went wrong"
        assert error.code == "TEST_ERROR"
        assert error.retryable is False
        assert error.details == {}

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("Invalid token")

        assert error.code == "AUTH_ERROR"
        assert error.retryable is False

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError("Too many requests", retry_after_seconds=120)

        assert error.code == "RATE_LIMIT"
        assert error.retryable is True
        assert error.retry_after_seconds == 120

    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Could not connect")

        assert error.code == "CONNECTION_ERROR"
        assert error.retryable is True

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Invalid field", field="api_key")

        assert error.code == "VALIDATION_ERROR"
        assert error.retryable is False
        assert error.field == "api_key"


class TestBaseIntegrationAdapter:
    """Tests for BaseIntegrationAdapter abstract class."""

    @pytest.mark.asyncio
    async def test_connect(self, mock_adapter):
        """Test successful connection."""
        result = await mock_adapter.connect()

        assert result.success is True
        assert mock_adapter.status == IntegrationStatus.CONNECTED
        assert mock_adapter.connect_calls == 1

    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_adapter):
        """Test connection failure."""
        mock_adapter.should_fail = True
        result = await mock_adapter.connect()

        assert result.success is False
        assert mock_adapter.status == IntegrationStatus.ERROR

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_adapter):
        """Test disconnection."""
        await mock_adapter.connect()
        result = await mock_adapter.disconnect()

        assert result.success is True
        assert mock_adapter.status == IntegrationStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_health_check(self, mock_adapter):
        """Test health check."""
        result = await mock_adapter.health_check()

        assert result.success is True
        assert result.data["healthy"] is True
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_execute(self, mock_adapter):
        """Test executing an operation."""
        result = await mock_adapter.execute("scan", {"file_path": "/test.py"})

        assert result.success is True
        assert result.data["result"] == "scan"
        assert len(mock_adapter.execute_calls) == 1

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, mock_adapter):
        """Test retry logic with eventual success."""
        mock_adapter.max_failures = 2  # Fail twice, then succeed

        result = await mock_adapter.execute_with_retry("scan", {"file": "test.py"})

        assert result.success is True
        assert len(mock_adapter.execute_calls) == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_execute_with_retry_max_retries(self, mock_adapter):
        """Test retry logic exhausting retries."""
        mock_adapter.max_failures = 10  # More than max retries

        retry_config = RetryConfig(
            max_retries=2, base_delay_seconds=0.01, max_delay_seconds=0.1
        )

        result = await mock_adapter.execute_with_retry(
            "scan", {"file": "test.py"}, retry_config
        )

        assert result.success is False
        assert result.error_code == "MAX_RETRIES_EXCEEDED"

    @pytest.mark.asyncio
    async def test_execute_with_retry_non_retryable(self, mock_adapter):
        """Test that non-retryable errors don't retry."""
        mock_adapter.should_fail = True

        result = await mock_adapter.execute_with_retry("scan", {})

        # Should not retry on non-retryable error
        assert result.success is False
        assert len(mock_adapter.execute_calls) == 1

    def test_validate_config_valid(self, mock_adapter):
        """Test config validation with valid config."""
        errors = mock_adapter.validate_config()
        assert errors == []

    def test_validate_config_missing_fields(self):
        """Test config validation with missing fields."""
        config = IntegrationConfig(
            integration_id="",
            integration_type=IntegrationType.IDE,
            provider="",
            organization_id="",
        )
        adapter = MockIntegrationAdapter(config)

        errors = adapter.validate_config()

        assert "integration_id is required" in errors
        assert "organization_id is required" in errors
        assert "provider is required" in errors

    def test_provider_property(self, mock_adapter):
        """Test provider property."""
        assert mock_adapter.provider == "vscode"

    def test_integration_type_property(self, mock_adapter):
        """Test integration_type property."""
        assert mock_adapter.integration_type == IntegrationType.IDE


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self):
        """Test default retry configuration."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay_seconds == 1.0
        assert config.max_delay_seconds == 60.0
        assert config.backoff_multiplier == 2.0
        assert "CONNECTION_ERROR" in config.retryable_codes

    def test_custom_values(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_retries=5,
            base_delay_seconds=0.5,
            retryable_codes=frozenset({"CUSTOM_ERROR"}),
        )

        assert config.max_retries == 5
        assert config.base_delay_seconds == 0.5
        assert "CUSTOM_ERROR" in config.retryable_codes


class TestIntegrationType:
    """Tests for IntegrationType enum."""

    def test_enum_values(self):
        """Test that all integration types are defined."""
        assert IntegrationType.IDE.value == "ide"
        assert IntegrationType.DATA_PLATFORM.value == "data_platform"
        assert IntegrationType.EXPORT.value == "export"
        assert IntegrationType.MONITORING.value == "monitoring"
        assert IntegrationType.SECURITY.value == "security"
        assert IntegrationType.TICKETING.value == "ticketing"


class TestIntegrationStatus:
    """Tests for IntegrationStatus enum."""

    def test_status_values(self):
        """Test that all statuses are defined."""
        assert IntegrationStatus.CONNECTED.value == "connected"
        assert IntegrationStatus.DISCONNECTED.value == "disconnected"
        assert IntegrationStatus.ERROR.value == "error"
        assert IntegrationStatus.CONFIGURING.value == "configuring"
        assert IntegrationStatus.RATE_LIMITED.value == "rate_limited"
