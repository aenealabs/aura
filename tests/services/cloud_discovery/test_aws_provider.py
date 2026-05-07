"""
Tests for AWS Discovery Provider
================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Tests for AWS resource discovery using boto3.
"""

import platform
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# pytest-forked on macOS to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.cloud_discovery.aws_provider import AWSDiscoveryProvider
from src.services.cloud_discovery.circuit_breaker import CircuitBreakerConfig
from src.services.cloud_discovery.credential_proxy import (
    AuthenticatedSession,
    CredentialProxyService,
)
from src.services.cloud_discovery.exceptions import GovCloudUnavailableError
from src.services.cloud_discovery.types import CloudProvider, CloudResourceType


class TestAWSDiscoveryProvider:
    """Tests for AWSDiscoveryProvider."""

    def test_create_provider(self) -> None:
        """Test creating provider."""
        provider = AWSDiscoveryProvider()
        assert provider.credential_proxy is None
        assert provider.use_mock is False

    def test_create_provider_mock_mode(self) -> None:
        """Test creating provider in mock mode."""
        provider = AWSDiscoveryProvider(use_mock=True)
        assert provider.use_mock is True

    def test_create_provider_with_circuit_breaker_config(self) -> None:
        """Test creating provider with custom circuit breaker config."""
        config = CircuitBreakerConfig(failure_threshold=10)
        provider = AWSDiscoveryProvider(circuit_breaker_config=config)
        assert provider.circuit_breaker_config.failure_threshold == 10

    def test_get_partition_commercial(self) -> None:
        """Test partition detection for commercial regions."""
        provider = AWSDiscoveryProvider()
        assert provider._get_partition("us-east-1") == "aws"
        assert provider._get_partition("eu-west-1") == "aws"
        assert provider._get_partition("ap-southeast-1") == "aws"

    def test_get_partition_govcloud(self) -> None:
        """Test partition detection for GovCloud regions."""
        provider = AWSDiscoveryProvider()
        assert provider._get_partition("us-gov-west-1") == "aws-us-gov"
        assert provider._get_partition("us-gov-east-1") == "aws-us-gov"

    def test_is_govcloud(self) -> None:
        """Test GovCloud region detection."""
        provider = AWSDiscoveryProvider()
        assert provider._is_govcloud("us-gov-west-1") is True
        assert provider._is_govcloud("us-gov-east-1") is True
        assert provider._is_govcloud("us-east-1") is False

    def test_check_govcloud_availability_available(self) -> None:
        """Test GovCloud availability check for available services."""
        provider = AWSDiscoveryProvider()
        # Should not raise for ec2
        provider._check_govcloud_availability("ec2", "us-gov-west-1")

    def test_check_govcloud_availability_unavailable(self) -> None:
        """Test GovCloud availability check for unavailable services."""
        provider = AWSDiscoveryProvider()
        with pytest.raises(GovCloudUnavailableError) as exc_info:
            provider._check_govcloud_availability("discovery", "us-gov-west-1")

        assert exc_info.value.service == "discovery"
        assert exc_info.value.region == "us-gov-west-1"

    def test_check_govcloud_availability_commercial(self) -> None:
        """Test GovCloud check passes for commercial regions."""
        provider = AWSDiscoveryProvider()
        # Should not raise for unavailable service in commercial region
        provider._check_govcloud_availability("discovery", "us-east-1")


class TestAWSDiscoveryProviderMockMode:
    """Tests for AWS discovery in mock mode."""

    @pytest.mark.asyncio
    async def test_get_session_mock_mode(self) -> None:
        """Test getting session in mock mode."""
        provider = AWSDiscoveryProvider(use_mock=True)
        session = await provider._get_session("123456789012", "us-east-1")

        assert session.provider == CloudProvider.AWS
        assert session.account_id == "123456789012"
        assert session.region == "us-east-1"
        assert session.session_type == "boto3_mock"

    @pytest.mark.asyncio
    async def test_discover_mock_mode(self) -> None:
        """Test discovery in mock mode."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["ec2", "rds", "lambda"],
        )

        assert result.provider == CloudProvider.AWS
        assert result.account_id == "123456789012"
        assert "us-east-1" in result.regions
        assert len(result.resources) > 0

    @pytest.mark.asyncio
    async def test_discover_ec2_mock(self) -> None:
        """Test EC2 discovery in mock mode."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["ec2"],
        )

        ec2_resources = [
            r
            for r in result.resources
            if r.resource_type == CloudResourceType.EC2_INSTANCE
        ]
        assert len(ec2_resources) == 1
        assert "mock-instance" in ec2_resources[0].name

    @pytest.mark.asyncio
    async def test_discover_rds_mock(self) -> None:
        """Test RDS discovery in mock mode."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["rds"],
        )

        rds_resources = [
            r
            for r in result.resources
            if r.resource_type == CloudResourceType.RDS_INSTANCE
        ]
        assert len(rds_resources) == 1
        assert rds_resources[0].properties.get("engine") == "postgres"

    @pytest.mark.asyncio
    async def test_discover_lambda_mock(self) -> None:
        """Test Lambda discovery in mock mode."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["lambda"],
        )

        lambda_resources = [
            r
            for r in result.resources
            if r.resource_type == CloudResourceType.LAMBDA_FUNCTION
        ]
        assert len(lambda_resources) == 1
        assert lambda_resources[0].properties.get("runtime") == "python3.11"

    @pytest.mark.asyncio
    async def test_discover_multiple_regions_mock(self) -> None:
        """Test discovery across multiple regions."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1", "us-west-2"],
            services=["ec2"],
        )

        # Should have resources from both regions
        regions_found = set(r.region for r in result.resources)
        assert "us-east-1" in regions_found
        assert "us-west-2" in regions_found

    @pytest.mark.asyncio
    async def test_discover_default_services(self) -> None:
        """Test discovery with default services."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1"],
        )

        # Should use default services list
        assert result.discovery_time_ms > 0

    @pytest.mark.asyncio
    async def test_discover_govcloud_warning(self) -> None:
        """Test discovery adds warning for GovCloud unavailable services."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-gov-west-1"],
            services=["discovery"],  # Not available in GovCloud
        )

        assert len(result.warnings) > 0
        assert "discovery" in result.warnings[0]


class TestAWSDiscoveryProviderWithCredentialProxy:
    """Tests for AWS discovery with credential proxy."""

    @pytest.fixture
    def mock_credential_proxy(self) -> MagicMock:
        """Create mock credential proxy."""
        proxy = MagicMock(spec=CredentialProxyService)
        mock_session = MagicMock()
        mock_session.region_name = "us-east-1"

        proxy.get_discovery_session = AsyncMock(
            return_value=AuthenticatedSession(
                provider=CloudProvider.AWS,
                account_id="123456789012",
                region="us-east-1",
                session_type="boto3",
                session_object=mock_session,
            )
        )
        return proxy

    @pytest.mark.asyncio
    async def test_get_session_with_proxy(
        self, mock_credential_proxy: MagicMock
    ) -> None:
        """Test getting session via credential proxy."""
        provider = AWSDiscoveryProvider(
            credential_proxy=mock_credential_proxy,
            use_mock=False,
        )

        session = await provider._get_session("123456789012", "us-east-1")

        mock_credential_proxy.get_discovery_session.assert_called_once_with(
            CloudProvider.AWS, "123456789012", "us-east-1"
        )
        assert session.account_id == "123456789012"


class TestAWSDiscoveryProviderDefaultCredentials:
    """Tests for AWS discovery with default credentials."""

    @pytest.mark.asyncio
    async def test_get_session_default_credentials(self) -> None:
        """Test getting session with default boto3 credentials."""
        provider = AWSDiscoveryProvider(use_mock=False)

        with patch("boto3.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session

            session = await provider._get_session("123456789012", "us-east-1")

            mock_session_class.assert_called_once_with(region_name="us-east-1")
            assert session.session_type == "boto3"


class TestAWSDiscoveryMockResources:
    """Tests for mock resource generation."""

    def test_get_mock_resources_ec2(self) -> None:
        """Test mock EC2 resource generation."""
        provider = AWSDiscoveryProvider(use_mock=True)
        resources, relationships = provider._get_mock_resources(
            "ec2", "123456789012", "us-east-1"
        )

        assert len(resources) == 1
        assert resources[0].resource_type == CloudResourceType.EC2_INSTANCE
        assert "aws:ec2:us-east-1" in resources[0].resource_id

    def test_get_mock_resources_rds(self) -> None:
        """Test mock RDS resource generation."""
        provider = AWSDiscoveryProvider(use_mock=True)
        resources, relationships = provider._get_mock_resources(
            "rds", "123456789012", "us-west-2"
        )

        assert len(resources) == 1
        assert resources[0].resource_type == CloudResourceType.RDS_INSTANCE
        assert resources[0].region == "us-west-2"

    def test_get_mock_resources_lambda(self) -> None:
        """Test mock Lambda resource generation."""
        provider = AWSDiscoveryProvider(use_mock=True)
        resources, relationships = provider._get_mock_resources(
            "lambda", "123456789012", "us-east-1"
        )

        assert len(resources) == 1
        assert resources[0].resource_type == CloudResourceType.LAMBDA_FUNCTION
        assert resources[0].properties["runtime"] == "python3.11"

    def test_get_mock_resources_unknown_service(self) -> None:
        """Test mock resource for unknown service returns empty."""
        provider = AWSDiscoveryProvider(use_mock=True)
        resources, relationships = provider._get_mock_resources(
            "unknown-service", "123456789012", "us-east-1"
        )

        assert len(resources) == 0
        assert len(relationships) == 0

    def test_get_mock_resources_govcloud_partition(self) -> None:
        """Test mock resources use correct GovCloud partition."""
        provider = AWSDiscoveryProvider(use_mock=True)
        resources, _ = provider._get_mock_resources(
            "ec2", "123456789012", "us-gov-west-1"
        )

        assert "aws-us-gov" in resources[0].resource_id


class TestAWSDiscoveryServiceMethods:
    """Tests for individual service discovery methods."""

    @pytest.fixture
    def mock_session(self) -> AuthenticatedSession:
        """Create mock session with boto3 clients."""
        mock_boto_session = MagicMock()
        return AuthenticatedSession(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            region="us-east-1",
            session_type="boto3",
            session_object=mock_boto_session,
        )

    @pytest.mark.asyncio
    async def test_discover_service_unknown(
        self, mock_session: AuthenticatedSession
    ) -> None:
        """Test discovering unknown service returns empty."""
        provider = AWSDiscoveryProvider(use_mock=False)

        # Temporarily disable mock to test the dispatch logic
        resources, relationships = await provider._discover_service(
            mock_session, "unknown-service", "us-east-1", None
        )

        assert len(resources) == 0
        assert len(relationships) == 0


class TestAWSDiscoveryCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_get_circuit_breaker(self) -> None:
        """Test getting circuit breaker for service."""
        provider = AWSDiscoveryProvider()
        breaker = provider._get_circuit_breaker("ec2")

        assert breaker.provider == "aws"
        assert breaker.service == "ec2"


class TestAWSDiscoveryResultMetadata:
    """Tests for discovery result metadata."""

    @pytest.mark.asyncio
    async def test_discovery_time_recorded(self) -> None:
        """Test discovery time is recorded."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["ec2"],
        )

        assert result.discovery_time_ms > 0

    @pytest.mark.asyncio
    async def test_regions_recorded(self) -> None:
        """Test regions are recorded in result."""
        provider = AWSDiscoveryProvider(use_mock=True)
        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1", "eu-west-1"],
            services=["ec2"],
        )

        assert "us-east-1" in result.regions
        assert "eu-west-1" in result.regions

    @pytest.mark.asyncio
    async def test_discovered_at_recorded(self) -> None:
        """Test discovered_at timestamp is set."""
        provider = AWSDiscoveryProvider(use_mock=True)
        before = datetime.now(timezone.utc)

        result = await provider.discover(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["ec2"],
        )

        after = datetime.now(timezone.utc)
        assert before <= result.discovered_at <= after
