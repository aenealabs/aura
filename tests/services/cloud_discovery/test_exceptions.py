"""
Tests for Cloud Discovery Exception Classes
===========================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Tests for exception hierarchy and attributes.
"""

import platform

import pytest

# pytest-forked on macOS to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.cloud_discovery.exceptions import (
    CircuitOpenError,
    CloudDiscoveryError,
    CorrelationError,
    CredentialError,
    CrossAccountError,
    DiscoveryTimeoutError,
    GovCloudUnavailableError,
    IaCParseError,
    ProviderError,
    RateLimitError,
)


class TestCloudDiscoveryError:
    """Tests for base CloudDiscoveryError."""

    def test_create_with_message(self) -> None:
        """Test creating error with message."""
        error = CloudDiscoveryError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details == {}

    def test_create_with_details(self) -> None:
        """Test creating error with details."""
        error = CloudDiscoveryError(
            "Failed to connect",
            details={"region": "us-east-1", "attempt": 3},
        )
        assert error.message == "Failed to connect"
        assert error.details["region"] == "us-east-1"
        assert error.details["attempt"] == 3

    def test_inheritance(self) -> None:
        """Test that CloudDiscoveryError inherits from Exception."""
        error = CloudDiscoveryError("test")
        assert isinstance(error, Exception)


class TestCredentialError:
    """Tests for CredentialError."""

    def test_create_minimal(self) -> None:
        """Test creating credential error with minimal fields."""
        error = CredentialError("Credentials not found")
        assert error.message == "Credentials not found"
        assert error.provider is None
        assert error.account_id is None
        assert error.reason is None

    def test_create_full(self) -> None:
        """Test creating credential error with all fields."""
        error = CredentialError(
            "Failed to assume role",
            provider="aws",
            account_id="123456789012",
            reason="AccessDenied",
            details={"role_arn": "arn:aws:iam::123456789012:role/DiscoveryRole"},
        )
        assert error.provider == "aws"
        assert error.account_id == "123456789012"
        assert error.reason == "AccessDenied"
        assert (
            error.details["role_arn"] == "arn:aws:iam::123456789012:role/DiscoveryRole"
        )

    def test_inheritance(self) -> None:
        """Test that CredentialError inherits from CloudDiscoveryError."""
        error = CredentialError("test")
        assert isinstance(error, CloudDiscoveryError)


class TestProviderError:
    """Tests for ProviderError."""

    def test_create_minimal(self) -> None:
        """Test creating provider error with minimal fields."""
        error = ProviderError("API call failed", provider="aws")
        assert error.provider == "aws"
        assert error.service is None
        assert error.operation is None
        assert error.error_code is None
        assert error.is_retryable is False

    def test_create_full(self) -> None:
        """Test creating provider error with all fields."""
        error = ProviderError(
            "Describe instances failed",
            provider="aws",
            service="ec2",
            operation="DescribeInstances",
            error_code="RequestLimitExceeded",
            is_retryable=True,
            details={"request_id": "abc-123"},
        )
        assert error.provider == "aws"
        assert error.service == "ec2"
        assert error.operation == "DescribeInstances"
        assert error.error_code == "RequestLimitExceeded"
        assert error.is_retryable is True

    def test_inheritance(self) -> None:
        """Test that ProviderError inherits from CloudDiscoveryError."""
        error = ProviderError("test", provider="aws")
        assert isinstance(error, CloudDiscoveryError)


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_create_minimal(self) -> None:
        """Test creating rate limit error with defaults."""
        error = RateLimitError("Rate limit exceeded", provider="aws")
        assert error.provider == "aws"
        assert error.service is None
        assert error.retry_after_seconds == 60.0

    def test_create_with_retry(self) -> None:
        """Test creating rate limit error with retry info."""
        error = RateLimitError(
            "Throttled",
            provider="aws",
            service="lambda",
            retry_after_seconds=120.0,
        )
        assert error.service == "lambda"
        assert error.retry_after_seconds == 120.0

    def test_inheritance(self) -> None:
        """Test that RateLimitError inherits from CloudDiscoveryError."""
        error = RateLimitError("test", provider="aws")
        assert isinstance(error, CloudDiscoveryError)


class TestCircuitOpenError:
    """Tests for CircuitOpenError."""

    def test_create_minimal(self) -> None:
        """Test creating circuit open error with minimal fields."""
        error = CircuitOpenError("Circuit is open", provider="aws")
        assert error.provider == "aws"
        assert error.service is None
        assert error.failures_count == 0
        assert error.recovery_time_seconds == 300.0

    def test_create_full(self) -> None:
        """Test creating circuit open error with all fields."""
        error = CircuitOpenError(
            "Circuit aws:ec2 is open",
            provider="aws",
            service="ec2",
            failures_count=5,
            recovery_time_seconds=180.0,
            details={"last_failure": "2024-01-01T00:00:00Z"},
        )
        assert error.provider == "aws"
        assert error.service == "ec2"
        assert error.failures_count == 5
        assert error.recovery_time_seconds == 180.0

    def test_inheritance(self) -> None:
        """Test that CircuitOpenError inherits from CloudDiscoveryError."""
        error = CircuitOpenError("test", provider="aws")
        assert isinstance(error, CloudDiscoveryError)


class TestDiscoveryTimeoutError:
    """Tests for DiscoveryTimeoutError."""

    def test_create_minimal(self) -> None:
        """Test creating timeout error with minimal fields."""
        error = DiscoveryTimeoutError("Discovery timed out", provider="aws")
        assert error.provider == "aws"
        assert error.operation is None
        assert error.timeout_seconds == 300.0
        assert error.partial_results == []

    def test_create_with_partial_results(self) -> None:
        """Test creating timeout error with partial results."""
        partial = [{"resource_id": "i-123"}, {"resource_id": "i-456"}]
        error = DiscoveryTimeoutError(
            "Timed out during EC2 discovery",
            provider="aws",
            operation="discover_ec2",
            timeout_seconds=120.0,
            partial_results=partial,
        )
        assert error.operation == "discover_ec2"
        assert error.timeout_seconds == 120.0
        assert len(error.partial_results) == 2

    def test_inheritance(self) -> None:
        """Test that DiscoveryTimeoutError inherits from CloudDiscoveryError."""
        error = DiscoveryTimeoutError("test", provider="aws")
        assert isinstance(error, CloudDiscoveryError)


class TestGovCloudUnavailableError:
    """Tests for GovCloudUnavailableError."""

    def test_create_minimal(self) -> None:
        """Test creating GovCloud error with minimal fields."""
        error = GovCloudUnavailableError(
            "Service not available in GovCloud",
            service="discovery",
            region="us-gov-west-1",
        )
        assert error.service == "discovery"
        assert error.region == "us-gov-west-1"
        assert error.alternative is None

    def test_create_with_alternative(self) -> None:
        """Test creating GovCloud error with alternative."""
        error = GovCloudUnavailableError(
            "AWS Resource Explorer not available in GovCloud",
            service="resource-explorer-2",
            region="us-gov-east-1",
            alternative="Use direct service-specific API calls",
        )
        assert error.service == "resource-explorer-2"
        assert error.region == "us-gov-east-1"
        assert error.alternative == "Use direct service-specific API calls"

    def test_inheritance(self) -> None:
        """Test that GovCloudUnavailableError inherits from CloudDiscoveryError."""
        error = GovCloudUnavailableError(
            "test",
            service="discovery",
            region="us-gov-west-1",
        )
        assert isinstance(error, CloudDiscoveryError)


class TestCrossAccountError:
    """Tests for CrossAccountError."""

    def test_create_minimal(self) -> None:
        """Test creating cross-account error with minimal fields."""
        error = CrossAccountError("Cross-account access denied")
        assert error.source_account is None
        assert error.target_account is None
        assert error.role_arn is None
        assert error.reason is None

    def test_create_full(self) -> None:
        """Test creating cross-account error with all fields."""
        error = CrossAccountError(
            "Failed to assume role in target account",
            source_account="111111111111",
            target_account="222222222222",
            role_arn="arn:aws:iam::222222222222:role/DiscoveryRole",
            reason="ExternalId mismatch",
            details={"sts_error_code": "AccessDenied"},
        )
        assert error.source_account == "111111111111"
        assert error.target_account == "222222222222"
        assert error.role_arn == "arn:aws:iam::222222222222:role/DiscoveryRole"
        assert error.reason == "ExternalId mismatch"

    def test_inheritance(self) -> None:
        """Test that CrossAccountError inherits from CloudDiscoveryError."""
        error = CrossAccountError("test")
        assert isinstance(error, CloudDiscoveryError)


class TestIaCParseError:
    """Tests for IaCParseError."""

    def test_create_minimal(self) -> None:
        """Test creating parse error with minimal fields."""
        error = IaCParseError(
            "Failed to parse template",
            file_path="deploy/cloudformation/template.yaml",
        )
        assert error.file_path == "deploy/cloudformation/template.yaml"
        assert error.line_number is None
        assert error.template_type is None

    def test_create_full(self) -> None:
        """Test creating parse error with all fields."""
        error = IaCParseError(
            "Invalid YAML syntax",
            file_path="deploy/cloudformation/broken.yaml",
            line_number=42,
            template_type="cloudformation",
            details={"yaml_error": "unexpected indent"},
        )
        assert error.file_path == "deploy/cloudformation/broken.yaml"
        assert error.line_number == 42
        assert error.template_type == "cloudformation"

    def test_inheritance(self) -> None:
        """Test that IaCParseError inherits from CloudDiscoveryError."""
        error = IaCParseError("test", file_path="test.yaml")
        assert isinstance(error, CloudDiscoveryError)


class TestCorrelationError:
    """Tests for CorrelationError."""

    def test_create_minimal(self) -> None:
        """Test creating correlation error with minimal fields."""
        error = CorrelationError("Correlation failed")
        assert error.repository_id is None
        assert error.logical_id is None
        assert error.reason is None

    def test_create_full(self) -> None:
        """Test creating correlation error with all fields."""
        error = CorrelationError(
            "Failed to correlate resource",
            repository_id="my-repo",
            logical_id="MyBucket",
            reason="Multiple matching resources found",
            details={"candidates": ["bucket-1", "bucket-2"]},
        )
        assert error.repository_id == "my-repo"
        assert error.logical_id == "MyBucket"
        assert error.reason == "Multiple matching resources found"

    def test_inheritance(self) -> None:
        """Test that CorrelationError inherits from CloudDiscoveryError."""
        error = CorrelationError("test")
        assert isinstance(error, CloudDiscoveryError)


class TestExceptionHierarchy:
    """Tests for exception hierarchy and catching."""

    def test_catch_all_cloud_errors(self) -> None:
        """Test catching all cloud discovery errors with base class."""
        exceptions = [
            CloudDiscoveryError("base"),
            CredentialError("credential"),
            ProviderError("provider", provider="aws"),
            RateLimitError("rate", provider="aws"),
            CircuitOpenError("circuit", provider="aws"),
            DiscoveryTimeoutError("timeout", provider="aws"),
            GovCloudUnavailableError(
                "govcloud", service="discovery", region="us-gov-west-1"
            ),
            CrossAccountError("cross"),
            IaCParseError("iac", file_path="test.yaml"),
            CorrelationError("correlation"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except CloudDiscoveryError as e:
                assert isinstance(e, CloudDiscoveryError)
            else:
                pytest.fail(
                    f"{type(exc).__name__} was not caught as CloudDiscoveryError"
                )

    def test_catch_specific_exception(self) -> None:
        """Test catching specific exception types."""
        with pytest.raises(CredentialError):
            raise CredentialError("test")

        with pytest.raises(ProviderError):
            raise ProviderError("test", provider="aws")

        with pytest.raises(RateLimitError):
            raise RateLimitError("test", provider="aws")

    def test_exception_str_representation(self) -> None:
        """Test string representation of exceptions."""
        error = ProviderError(
            "EC2 API error",
            provider="aws",
            service="ec2",
            error_code="InvalidInstanceID",
        )
        assert "EC2 API error" in str(error)
