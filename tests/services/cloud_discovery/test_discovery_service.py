"""
Tests for Cloud Discovery Service
=================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Tests for main orchestration service.
"""

import platform
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# pytest-forked on macOS to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.cloud_discovery.discovery_service import (
    CloudDiscoveryService,
    DiscoveryRequest,
    FullDiscoveryResult,
    create_cloud_discovery_service,
)
from src.services.cloud_discovery.types import (
    CloudProvider,
    CloudResource,
    CloudResourceType,
    CorrelationResult,
    DiscoveryResult,
    IaCMapping,
)


class TestDiscoveryRequest:
    """Tests for DiscoveryRequest dataclass."""

    def test_create_minimal_request(self) -> None:
        """Test creating request with minimal fields."""
        request = DiscoveryRequest(account_id="123456789012")
        assert request.account_id == "123456789012"
        assert request.provider == CloudProvider.AWS
        assert request.regions == []
        assert request.services == []
        assert request.include_iac_correlation is True
        assert request.timeout_seconds == 300.0

    def test_create_full_request(self) -> None:
        """Test creating request with all fields."""
        request = DiscoveryRequest(
            account_id="123456789012",
            provider=CloudProvider.AWS,
            regions=["us-east-1", "us-west-2"],
            services=["ec2", "rds"],
            tags_filter={"Environment": "dev"},
            include_iac_correlation=True,
            repository_path="/path/to/repo",
            stack_name="my-stack",
            timeout_seconds=600.0,
        )
        assert request.regions == ["us-east-1", "us-west-2"]
        assert request.services == ["ec2", "rds"]
        assert request.tags_filter["Environment"] == "dev"
        assert request.repository_path == "/path/to/repo"
        assert request.stack_name == "my-stack"


class TestFullDiscoveryResult:
    """Tests for FullDiscoveryResult dataclass."""

    def test_create_result(self) -> None:
        """Test creating full discovery result."""
        discovery = DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            resources=[
                CloudResource(
                    resource_id="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
                    resource_type=CloudResourceType.EC2_INSTANCE,
                    provider=CloudProvider.AWS,
                    name="my-instance",
                )
            ],
        )

        result = FullDiscoveryResult(
            discovery=discovery,
            providers_used=[CloudProvider.AWS],
        )

        assert result.total_resources == 1
        assert result.cache_hit is False
        assert CloudProvider.AWS in result.providers_used

    def test_total_resources_property(self) -> None:
        """Test total_resources property."""
        discovery = DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            resources=[
                CloudResource(
                    resource_id=f"resource-{i}",
                    resource_type=CloudResourceType.EC2_INSTANCE,
                    provider=CloudProvider.AWS,
                    name=f"instance-{i}",
                )
                for i in range(5)
            ],
        )

        result = FullDiscoveryResult(discovery=discovery)
        assert result.total_resources == 5

    def test_correlation_rate_property(self) -> None:
        """Test correlation_rate property."""
        discovery = DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id="123456789012",
        )

        # Without correlation
        result = FullDiscoveryResult(discovery=discovery, correlation=None)
        assert result.correlation_rate is None

        # With correlation
        correlation = CorrelationResult(
            repository_id="my-repo",
            iac_mappings=[
                IaCMapping(
                    logical_id="MyBucket",
                    resource_type="AWS::S3::Bucket",
                    source_file="template.yaml",
                    physical_resource_id="arn:aws:s3:::my-bucket",
                )
            ],
        )
        result_with_correlation = FullDiscoveryResult(
            discovery=discovery, correlation=correlation
        )
        assert result_with_correlation.correlation_rate == 1.0


class TestCloudDiscoveryService:
    """Tests for CloudDiscoveryService."""

    @pytest.fixture
    def mock_secrets_service(self) -> MagicMock:
        """Create mock secrets service."""
        service = MagicMock()
        service.connect = AsyncMock(return_value=True)
        service.disconnect = AsyncMock()
        return service

    def test_create_service(self) -> None:
        """Test creating service."""
        service = CloudDiscoveryService(
            organization_id="my-org",
            region="us-east-1",
        )
        assert service.organization_id == "my-org"
        assert service.region == "us-east-1"
        assert service.use_mock is False

    def test_create_service_mock_mode(self) -> None:
        """Test creating service in mock mode."""
        service = CloudDiscoveryService(use_mock=True)
        assert service.use_mock is True

    def test_create_service_with_secrets(self, mock_secrets_service: MagicMock) -> None:
        """Test creating service with secrets service."""
        service = CloudDiscoveryService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
        )
        assert service.credential_proxy is not None

    @pytest.mark.asyncio
    async def test_initialize(self) -> None:
        """Test service initialization."""
        service = CloudDiscoveryService(use_mock=True)
        result = await service.initialize()

        assert result is True
        assert service._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self) -> None:
        """Test initialization is idempotent."""
        service = CloudDiscoveryService(use_mock=True)

        await service.initialize()
        await service.initialize()

        assert service._initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self, mock_secrets_service: MagicMock) -> None:
        """Test service shutdown."""
        service = CloudDiscoveryService(
            secrets_service=mock_secrets_service,
            use_mock=True,
        )
        await service.initialize()

        # Add something to cache
        service._cache["test"] = (MagicMock(), datetime.now(timezone.utc))

        await service.shutdown()

        assert service._initialized is False
        assert len(service._cache) == 0


class TestCloudDiscoveryServiceDiscovery:
    """Tests for discovery operations."""

    @pytest.mark.asyncio
    async def test_discover_basic(self) -> None:
        """Test basic discovery."""
        service = CloudDiscoveryService(use_mock=True)

        request = DiscoveryRequest(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["ec2"],
            include_iac_correlation=False,
        )

        result = await service.discover(request)

        assert result.total_resources > 0
        assert result.cache_hit is False
        assert CloudProvider.AWS in result.providers_used

    @pytest.mark.asyncio
    async def test_discover_uses_cache(self) -> None:
        """Test discovery uses cache."""
        service = CloudDiscoveryService(use_mock=True)

        request = DiscoveryRequest(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["ec2"],
            include_iac_correlation=False,
        )

        # First call
        result1 = await service.discover(request)
        assert result1.cache_hit is False

        # Second call should use cache
        result2 = await service.discover(request)
        assert result2.cache_hit is True

    @pytest.mark.asyncio
    async def test_discover_bypass_cache(self) -> None:
        """Test discovery can bypass cache."""
        service = CloudDiscoveryService(use_mock=True)

        request = DiscoveryRequest(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["ec2"],
            include_iac_correlation=False,
        )

        # First call
        await service.discover(request)

        # Second call without cache
        result = await service.discover(request, use_cache=False)
        assert result.cache_hit is False

    @pytest.mark.asyncio
    async def test_discover_auto_initializes(self) -> None:
        """Test discovery auto-initializes service."""
        service = CloudDiscoveryService(use_mock=True)
        assert service._initialized is False

        request = DiscoveryRequest(
            account_id="123456789012",
            include_iac_correlation=False,
        )

        await service.discover(request)
        assert service._initialized is True


class TestCloudDiscoveryServiceIaCCorrelation:
    """Tests for IaC correlation."""

    @pytest.fixture
    def temp_repo(self) -> Path:
        """Create temp repository with IaC files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            yaml_content = """
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
"""
            (path / "template.yaml").write_text(yaml_content)
            yield path

    @pytest.mark.asyncio
    async def test_discover_with_iac_correlation(self, temp_repo: Path) -> None:
        """Test discovery with IaC correlation."""
        service = CloudDiscoveryService(use_mock=True)

        request = DiscoveryRequest(
            account_id="123456789012",
            regions=["us-east-1"],
            services=["ec2"],
            include_iac_correlation=True,
            repository_path=str(temp_repo),
        )

        result = await service.discover(request)

        # Should have correlation result
        assert result.correlation is not None

    @pytest.mark.asyncio
    async def test_discover_correlation_failure_continues(self) -> None:
        """Test discovery continues on correlation failure."""
        service = CloudDiscoveryService(use_mock=True)

        request = DiscoveryRequest(
            account_id="123456789012",
            regions=["us-east-1"],
            include_iac_correlation=True,
            repository_path="/nonexistent/path",
        )

        # Should not raise, just skip correlation
        result = await service.discover(request)
        assert result.total_resources >= 0


class TestCloudDiscoveryServiceCaching:
    """Tests for caching behavior."""

    def test_get_cache_key(self) -> None:
        """Test cache key generation."""
        service = CloudDiscoveryService(use_mock=True)

        request = DiscoveryRequest(
            account_id="123456789012",
            regions=["us-east-1", "us-west-2"],
            services=["ec2", "rds"],
        )

        key = service._get_cache_key(request)
        assert "123456789012" in key
        assert "aws" in key
        # Regions and services should be sorted
        assert "us-east-1,us-west-2" in key
        assert "ec2,rds" in key

    def test_get_cache_key_default_values(self) -> None:
        """Test cache key with default values."""
        service = CloudDiscoveryService(use_mock=True)

        request = DiscoveryRequest(account_id="123456789012")

        key = service._get_cache_key(request)
        assert "default" in key
        assert "all" in key

    def test_get_cached_result_miss(self) -> None:
        """Test cache miss."""
        service = CloudDiscoveryService(use_mock=True)
        result = service._get_cached_result("nonexistent-key")
        assert result is None

    def test_get_cached_result_hit(self) -> None:
        """Test cache hit."""
        service = CloudDiscoveryService(use_mock=True)

        # Add to cache
        mock_result = MagicMock(spec=FullDiscoveryResult)
        service._cache["test-key"] = (mock_result, datetime.now(timezone.utc))

        result = service._get_cached_result("test-key")
        assert result is mock_result

    def test_get_cached_result_expired(self) -> None:
        """Test expired cache entry."""
        service = CloudDiscoveryService(
            use_mock=True,
            cache_ttl=timedelta(hours=1),
        )

        # Add expired entry
        mock_result = MagicMock(spec=FullDiscoveryResult)
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        service._cache["test-key"] = (mock_result, old_time)

        result = service._get_cached_result("test-key")
        assert result is None
        # Entry should be removed
        assert "test-key" not in service._cache

    def test_cache_result(self) -> None:
        """Test caching a result."""
        service = CloudDiscoveryService(use_mock=True)

        mock_result = MagicMock(spec=FullDiscoveryResult)
        service._cache_result("test-key", mock_result)

        assert "test-key" in service._cache
        cached_result, cached_at = service._cache["test-key"]
        assert cached_result is mock_result

    def test_clear_cache(self) -> None:
        """Test clearing cache."""
        service = CloudDiscoveryService(use_mock=True)

        # Add entries
        service._cache["key1"] = (MagicMock(), datetime.now(timezone.utc))
        service._cache["key2"] = (MagicMock(), datetime.now(timezone.utc))

        count = service.clear_cache()

        assert count == 2
        assert len(service._cache) == 0


class TestCloudDiscoveryServiceCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_get_circuit_breaker_status(self) -> None:
        """Test getting circuit breaker status."""
        service = CloudDiscoveryService(use_mock=True)
        status = service.get_circuit_breaker_status()

        assert "breakers" in status
        assert "open_circuits" in status


class TestCloudDiscoveryServiceCredentials:
    """Tests for credential management."""

    @pytest.fixture
    def mock_credential_proxy(self) -> MagicMock:
        """Create mock credential proxy."""
        from src.services.cloud_discovery.credential_proxy import CredentialProxyService

        proxy = MagicMock(spec=CredentialProxyService)
        proxy.validate_credentials = AsyncMock(return_value=True)
        proxy.list_configured_accounts = AsyncMock(return_value=[])
        return proxy

    @pytest.mark.asyncio
    async def test_validate_credentials_no_proxy(self) -> None:
        """Test credential validation without proxy."""
        service = CloudDiscoveryService(use_mock=True)
        result = await service.validate_credentials(CloudProvider.AWS, "123456789012")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_credentials_with_proxy(
        self, mock_credential_proxy: MagicMock
    ) -> None:
        """Test credential validation with proxy."""
        service = CloudDiscoveryService(use_mock=True)
        service.credential_proxy = mock_credential_proxy

        result = await service.validate_credentials(CloudProvider.AWS, "123456789012")

        assert result is True
        mock_credential_proxy.validate_credentials.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_configured_accounts_no_proxy(self) -> None:
        """Test listing accounts without proxy."""
        service = CloudDiscoveryService(use_mock=True)
        accounts = await service.list_configured_accounts()
        assert accounts == []

    @pytest.mark.asyncio
    async def test_list_configured_accounts_with_proxy(
        self, mock_credential_proxy: MagicMock
    ) -> None:
        """Test listing accounts with proxy."""
        from src.services.cloud_discovery.credential_proxy import (
            CloudCredentialConfig,
            CredentialType,
        )

        mock_config = CloudCredentialConfig(
            credential_id="cred-123",
            provider=CloudProvider.AWS,
            credential_type=CredentialType.AWS_ROLE,
            account_id="123456789012",
            description="Test account",
        )
        mock_credential_proxy.list_configured_accounts = AsyncMock(
            return_value=[mock_config]
        )

        service = CloudDiscoveryService(use_mock=True)
        service.credential_proxy = mock_credential_proxy

        accounts = await service.list_configured_accounts(CloudProvider.AWS)

        assert len(accounts) == 1
        assert accounts[0]["account_id"] == "123456789012"
        assert accounts[0]["provider"] == "aws"


class TestCloudDiscoveryServiceProviderErrors:
    """Tests for provider error handling."""

    @pytest.mark.asyncio
    async def test_discover_azure_not_implemented(self) -> None:
        """Test Azure discovery raises not implemented."""
        service = CloudDiscoveryService(use_mock=True)

        request = DiscoveryRequest(
            account_id="subscription-123",
            provider=CloudProvider.AZURE,
            include_iac_correlation=False,
        )

        with pytest.raises(Exception) as exc_info:
            await service.discover(request)

        assert "Azure" in str(exc_info.value) or "not yet implemented" in str(
            exc_info.value
        )


class TestCreateCloudDiscoveryService:
    """Tests for factory function."""

    def test_create_service_default(self) -> None:
        """Test factory function with defaults."""
        service = create_cloud_discovery_service()
        assert service.use_mock is False
        assert service.credential_proxy is None

    def test_create_service_mock_mode(self) -> None:
        """Test factory function in mock mode."""
        service = create_cloud_discovery_service(use_mock=True)
        assert service.use_mock is True

    def test_create_service_with_secrets(self) -> None:
        """Test factory function with secrets service."""
        mock_secrets = MagicMock()
        service = create_cloud_discovery_service(
            secrets_service=mock_secrets, use_mock=False
        )
        assert service.credential_proxy is not None

    def test_create_service_uses_environment(self) -> None:
        """Test factory function uses environment variables."""
        with patch.dict(
            "os.environ",
            {"ORGANIZATION_ID": "env-org", "AWS_REGION": "eu-west-1"},
        ):
            service = create_cloud_discovery_service()
            assert service.organization_id == "env-org"
            assert service.region == "eu-west-1"
