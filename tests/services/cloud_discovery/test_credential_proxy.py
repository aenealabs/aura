"""
Tests for Credential Proxy Service
==================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Tests for secure credential management and session creation.
"""

import platform
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# pytest-forked on macOS to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.cloud_discovery.credential_proxy import (
    AuthenticatedSession,
    CloudCredentialConfig,
    CredentialProxyService,
    CredentialType,
)
from src.services.cloud_discovery.exceptions import CredentialError
from src.services.cloud_discovery.types import CloudProvider


class TestCredentialType:
    """Tests for CredentialType enum."""

    def test_aws_types(self) -> None:
        """Test AWS credential types."""
        assert CredentialType.AWS_ACCESS_KEY.value == "aws_access_key"
        assert CredentialType.AWS_ROLE.value == "aws_role"

    def test_azure_types(self) -> None:
        """Test Azure credential types."""
        assert CredentialType.AZURE_SERVICE_PRINCIPAL.value == "azure_service_principal"
        assert CredentialType.AZURE_MANAGED_IDENTITY.value == "azure_managed_identity"

    def test_gcp_type(self) -> None:
        """Test GCP credential type."""
        assert CredentialType.GCP_SERVICE_ACCOUNT.value == "gcp_service_account"


class TestCloudCredentialConfig:
    """Tests for CloudCredentialConfig dataclass."""

    def test_create_config(self) -> None:
        """Test creating credential config."""
        config = CloudCredentialConfig(
            credential_id="cred-123",
            provider=CloudProvider.AWS,
            credential_type=CredentialType.AWS_ROLE,
            account_id="123456789012",
        )
        assert config.credential_id == "cred-123"
        assert config.provider == CloudProvider.AWS
        assert config.credential_type == CredentialType.AWS_ROLE
        assert config.account_id == "123456789012"
        assert config.enabled is True
        assert config.rotation_days == 90

    def test_needs_rotation_no_rotation(self) -> None:
        """Test needs_rotation when never rotated."""
        config = CloudCredentialConfig(
            credential_id="cred-123",
            provider=CloudProvider.AWS,
            credential_type=CredentialType.AWS_ROLE,
            account_id="123456789012",
        )
        assert config.needs_rotation is False

    def test_needs_rotation_recent(self) -> None:
        """Test needs_rotation with recent rotation."""
        config = CloudCredentialConfig(
            credential_id="cred-123",
            provider=CloudProvider.AWS,
            credential_type=CredentialType.AWS_ROLE,
            account_id="123456789012",
            last_rotated=datetime.now(timezone.utc) - timedelta(days=30),
        )
        assert config.needs_rotation is False

    def test_needs_rotation_old(self) -> None:
        """Test needs_rotation with old rotation."""
        config = CloudCredentialConfig(
            credential_id="cred-123",
            provider=CloudProvider.AWS,
            credential_type=CredentialType.AWS_ROLE,
            account_id="123456789012",
            rotation_days=90,
            last_rotated=datetime.now(timezone.utc) - timedelta(days=100),
        )
        assert config.needs_rotation is True

    def test_secret_name(self) -> None:
        """Test secret name generation."""
        config = CloudCredentialConfig(
            credential_id="cred-123",
            provider=CloudProvider.AWS,
            credential_type=CredentialType.AWS_ROLE,
            account_id="123456789012",
        )
        assert config.secret_name == "aura/cloud-discovery/aws/123456789012"


class TestAuthenticatedSession:
    """Tests for AuthenticatedSession dataclass."""

    def test_create_session(self) -> None:
        """Test creating authenticated session."""
        session = AuthenticatedSession(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            region="us-east-1",
        )
        assert session.provider == CloudProvider.AWS
        assert session.account_id == "123456789012"
        assert session.region == "us-east-1"
        assert session.session_type == "boto3"
        assert session.session_object is None

    def test_is_expired_not_expired(self) -> None:
        """Test is_expired when session is valid."""
        session = AuthenticatedSession(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert session.is_expired is False

    def test_is_expired_expired(self) -> None:
        """Test is_expired when session has expired."""
        session = AuthenticatedSession(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert session.is_expired is True


class TestCredentialProxyService:
    """Tests for CredentialProxyService."""

    @pytest.fixture
    def mock_secrets_service(self) -> MagicMock:
        """Create mock secrets service."""
        service = MagicMock()
        service.connect = AsyncMock(return_value=True)
        service.disconnect = AsyncMock()
        service.get_secret = AsyncMock(return_value=None)
        service.list_secrets = AsyncMock(return_value=[])
        service.rotate_secret_immediately = AsyncMock()
        return service

    def test_create_proxy(self, mock_secrets_service: MagicMock) -> None:
        """Test creating credential proxy."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            region="us-east-1",
        )
        assert proxy.organization_id == "my-org"
        assert proxy.region == "us-east-1"
        assert proxy.use_mock is False

    def test_create_proxy_mock_mode(self, mock_secrets_service: MagicMock) -> None:
        """Test creating proxy in mock mode."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )
        assert proxy.use_mock is True

    def test_get_partition_commercial(self, mock_secrets_service: MagicMock) -> None:
        """Test partition detection for commercial regions."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            region="us-east-1",
        )
        assert proxy._get_partition() == "aws"

    def test_get_partition_govcloud(self, mock_secrets_service: MagicMock) -> None:
        """Test partition detection for GovCloud regions."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            region="us-gov-west-1",
        )
        assert proxy._get_partition() == "aws-us-gov"

    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, mock_secrets_service: MagicMock) -> None:
        """Test connect in mock mode."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )
        result = await proxy.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_real_mode(self, mock_secrets_service: MagicMock) -> None:
        """Test connect in real mode."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=False,
        )
        result = await proxy.connect()
        assert result is True
        mock_secrets_service.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_secrets_service: MagicMock) -> None:
        """Test disconnect clears caches."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )
        await proxy.connect()

        # Add something to caches
        proxy._session_cache["test"] = (MagicMock(), datetime.now(timezone.utc))
        proxy._credential_configs["test"] = MagicMock()

        await proxy.disconnect()

        assert len(proxy._session_cache) == 0
        assert len(proxy._credential_configs) == 0

    @pytest.mark.asyncio
    async def test_get_discovery_session_mock_mode(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test getting discovery session in mock mode."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )

        session = await proxy.get_discovery_session("aws", "123456789012")

        assert session.provider == CloudProvider.AWS
        assert session.account_id == "123456789012"
        assert session.session_type == "boto3_mock"
        assert session.session_object is not None

    @pytest.mark.asyncio
    async def test_get_discovery_session_azure_mock(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test getting Azure session in mock mode."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )

        session = await proxy.get_discovery_session(
            CloudProvider.AZURE, "subscription-123"
        )

        assert session.provider == CloudProvider.AZURE
        assert session.account_id == "subscription-123"
        assert session.session_type == "azure_credential_mock"

    @pytest.mark.asyncio
    async def test_get_discovery_session_uses_cache(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test session caching."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )

        session1 = await proxy.get_discovery_session("aws", "123456789012")
        session2 = await proxy.get_discovery_session("aws", "123456789012")

        # Should be same session (from cache)
        assert session1 is session2

    @pytest.mark.asyncio
    async def test_get_discovery_session_unsupported_provider(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test error for unsupported provider."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )

        with pytest.raises(CredentialError) as exc_info:
            await proxy.get_discovery_session(CloudProvider.GCP, "project-123")

        assert "Unsupported provider" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_credential_config_mock_mode(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test getting credential config in mock mode."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )

        config = await proxy._get_credential_config(CloudProvider.AWS, "123456789012")

        assert config.provider == CloudProvider.AWS
        assert config.account_id == "123456789012"
        assert config.credential_type == CredentialType.AWS_ROLE

    @pytest.mark.asyncio
    async def test_get_credential_config_not_found(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test error when credential not found."""
        mock_secrets_service.get_secret = AsyncMock(return_value=None)

        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=False,
        )

        with pytest.raises(CredentialError) as exc_info:
            await proxy._get_credential_config(CloudProvider.AWS, "123456789012")

        assert exc_info.value.reason == "not_found"

    @pytest.mark.asyncio
    async def test_get_credential_config_disabled(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test error when credential is disabled."""
        mock_secret = MagicMock()
        mock_secret.value = {"enabled": False, "credential_type": "aws_role"}
        mock_secrets_service.get_secret = AsyncMock(return_value=mock_secret)

        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=False,
        )

        with pytest.raises(CredentialError) as exc_info:
            await proxy._get_credential_config(CloudProvider.AWS, "123456789012")

        assert "disabled" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_validate_credentials_mock_mode(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test credential validation in mock mode."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )

        # Mock mode returns mock session object
        result = await proxy.validate_credentials("aws", "123456789012")
        # In mock mode, the session object is a MagicMock which will return
        # MagicMock for client().get_caller_identity(), so validation succeeds
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_credentials_failure(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test credential validation failure."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,
        )

        # Make the mock raise an exception
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_client.get_caller_identity.side_effect = Exception("Invalid credentials")
        mock_session.client.return_value = mock_client

        # Patch the session creation
        proxy._session_cache["aws:123456789012:us-east-1"] = (
            AuthenticatedSession(
                provider=CloudProvider.AWS,
                account_id="123456789012",
                session_object=mock_session,
            ),
            datetime.now(timezone.utc) + timedelta(hours=1),
        )

        result = await proxy.validate_credentials("aws", "123456789012")
        assert result is False

    @pytest.mark.asyncio
    async def test_rotate_credentials(self, mock_secrets_service: MagicMock) -> None:
        """Test credential rotation."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=False,
        )

        # Add a cached session
        proxy._session_cache["aws:123456789012:us-east-1"] = (
            MagicMock(),
            datetime.now(timezone.utc),
        )

        result = await proxy.rotate_credentials("aws", "123456789012")

        assert result is True
        mock_secrets_service.rotate_secret_immediately.assert_called_once()
        assert "aws:123456789012:us-east-1" not in proxy._session_cache

    @pytest.mark.asyncio
    async def test_rotate_credentials_failure(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test credential rotation failure."""
        mock_secrets_service.rotate_secret_immediately = AsyncMock(
            side_effect=Exception("Rotation failed")
        )

        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=False,
        )

        result = await proxy.rotate_credentials("aws", "123456789012")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_configured_accounts(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test listing configured accounts."""
        mock_secrets_service.list_secrets = AsyncMock(
            return_value=[
                "aura/my-org/cloud-discovery/aws/111111111111/config",
                "aura/my-org/cloud-discovery/aws/222222222222/config",
            ]
        )

        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            use_mock=True,  # So _get_credential_config returns mock config
        )

        configs = await proxy.list_configured_accounts(CloudProvider.AWS)

        assert len(configs) == 2
        assert configs[0].account_id == "111111111111"
        assert configs[1].account_id == "222222222222"

    def test_clear_session_cache(self, mock_secrets_service: MagicMock) -> None:
        """Test clearing session cache."""
        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
        )

        proxy._session_cache["test"] = (MagicMock(), datetime.now(timezone.utc))
        proxy._session_cache["test2"] = (MagicMock(), datetime.now(timezone.utc))

        proxy.clear_session_cache()

        assert len(proxy._session_cache) == 0


class TestCredentialProxyServiceRealAWS:
    """Tests for real AWS session creation (mocked boto3)."""

    @pytest.fixture
    def mock_secrets_service(self) -> MagicMock:
        """Create mock secrets service."""
        service = MagicMock()
        service.connect = AsyncMock(return_value=True)
        service.disconnect = AsyncMock()
        service.get_secret = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_create_aws_session_with_role(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test AWS session creation with role assumption."""
        # Mock the config secret
        mock_secret = MagicMock()
        mock_secret.value = {
            "credential_id": "cred-123",
            "credential_type": "aws_role",
            "enabled": True,
            "external_id": "ext-123",
        }
        mock_secrets_service.get_secret = AsyncMock(return_value=mock_secret)

        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            region="us-east-1",
            use_mock=False,
        )

        # Mock boto3 and STS
        with (
            patch("boto3.client") as mock_boto_client,
            patch("boto3.Session") as mock_boto_session,
        ):
            mock_sts = MagicMock()
            mock_sts.assume_role.return_value = {
                "Credentials": {
                    "AccessKeyId": "AKIATEST",
                    "SecretAccessKey": "secret",
                    "SessionToken": "token",
                }
            }
            mock_boto_client.return_value = mock_sts

            session = await proxy.get_discovery_session("aws", "123456789012")

            mock_sts.assume_role.assert_called_once()
            call_kwargs = mock_sts.assume_role.call_args[1]
            assert "ExternalId" in call_kwargs
            assert call_kwargs["ExternalId"] == "ext-123"

    @pytest.mark.asyncio
    async def test_create_aws_session_with_static_credentials(
        self, mock_secrets_service: MagicMock
    ) -> None:
        """Test AWS session creation with static credentials."""
        # Mock the config secret
        mock_config = MagicMock()
        mock_config.value = {
            "credential_id": "cred-123",
            "credential_type": "aws_access_key",
            "enabled": True,
        }

        # Mock the credentials secret
        mock_creds = MagicMock()
        mock_creds.value = {
            "access_key_id": "AKIATEST",
            "secret_access_key": "secret",
        }

        mock_secrets_service.get_secret = AsyncMock(
            side_effect=[mock_config, mock_creds]
        )

        proxy = CredentialProxyService(
            secrets_service=mock_secrets_service,
            organization_id="my-org",
            region="us-east-1",
            use_mock=False,
        )

        with patch("boto3.Session") as mock_boto_session:
            session = await proxy.get_discovery_session("aws", "123456789012")

            mock_boto_session.assert_called_once_with(
                aws_access_key_id="AKIATEST",
                aws_secret_access_key="secret",
                region_name="us-east-1",
            )
