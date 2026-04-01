"""
Credential Proxy Service
========================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Secure credential management for cloud discovery. This service acts as
a proxy between the Discovery Agent and cloud credentials, ensuring
that agent code never sees raw credentials.

Security features:
- Credentials stored in Secrets Manager (never in Aura database)
- Pre-authenticated sessions returned to agents
- 90-day automatic rotation support
- Audit logging for credential access
- Credential validation before use
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from src.services.cloud_discovery.exceptions import CredentialError
from src.services.cloud_discovery.types import CloudProvider

if TYPE_CHECKING:
    from mypy_boto3_sts.client import STSClient

logger = logging.getLogger(__name__)


class CredentialType(Enum):
    """Types of cloud credentials."""

    AWS_ACCESS_KEY = "aws_access_key"  # Static access key
    AWS_ROLE = "aws_role"  # IAM role for assumption
    AZURE_SERVICE_PRINCIPAL = "azure_service_principal"  # Service principal
    AZURE_MANAGED_IDENTITY = "azure_managed_identity"  # Managed identity
    GCP_SERVICE_ACCOUNT = "gcp_service_account"  # Service account key


@dataclass
class CloudCredentialConfig:
    """Configuration for a cloud credential.

    Attributes:
        credential_id: Unique identifier
        provider: Cloud provider (aws, azure, gcp)
        credential_type: Type of credential
        account_id: Cloud account/subscription ID
        description: Human-readable description
        enabled: Whether credential is enabled
        rotation_days: Days between automatic rotation
        last_rotated: When credential was last rotated
        external_id: External ID for AWS role assumption
        tags: Optional tags for organization
    """

    credential_id: str
    provider: CloudProvider
    credential_type: CredentialType
    account_id: str
    description: str = ""
    enabled: bool = True
    rotation_days: int = 90
    last_rotated: datetime | None = None
    external_id: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def needs_rotation(self) -> bool:
        """Check if credential needs rotation."""
        if self.last_rotated is None:
            return False
        age = datetime.now(timezone.utc) - self.last_rotated
        return age.days >= self.rotation_days

    @property
    def secret_name(self) -> str:
        """Get the Secrets Manager secret name for this credential."""
        return f"aura/cloud-discovery/{self.provider.value}/{self.account_id}"


@dataclass
class AuthenticatedSession:
    """Pre-authenticated cloud session.

    This is returned to agents instead of raw credentials.
    Agents use this session to make API calls without
    ever seeing the underlying credentials.

    Attributes:
        provider: Cloud provider
        account_id: Account this session is for
        region: Region (if applicable)
        session_type: Type of session (e.g., 'boto3', 'azure_credential')
        expires_at: When the session expires
        session_object: The actual session object (type depends on provider)
    """

    provider: CloudProvider
    account_id: str
    region: str = ""
    session_type: str = "boto3"
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1)
    )
    session_object: Any = None

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) >= self.expires_at


class CredentialProxyService:
    """
    Secure credential proxy for cloud discovery.

    This service:
    1. Stores credentials in Secrets Manager
    2. Returns pre-authenticated sessions to agents
    3. Supports automatic credential rotation
    4. Never exposes raw credentials to agent code

    Usage:
        proxy = CredentialProxyService(secrets_service, organization_id)
        await proxy.connect()

        # Get session for AWS account
        session = await proxy.get_discovery_session('aws', '123456789012')

        # Use session.session_object for boto3 calls
        client = session.session_object.client('ec2')
    """

    # GovCloud regions for partition detection
    GOVCLOUD_REGIONS = {"us-gov-west-1", "us-gov-east-1"}

    # Default session duration (1 hour)
    DEFAULT_SESSION_DURATION = timedelta(hours=1)

    def __init__(
        self,
        secrets_service: Any,  # SecretsService from abstractions
        organization_id: str,
        region: str | None = None,
        use_mock: bool = False,
    ) -> None:
        """Initialize credential proxy.

        Args:
            secrets_service: SecretsService instance for credential storage
            organization_id: Organization ID for namespacing credentials
            region: AWS region for STS calls
            use_mock: Use mock mode for testing
        """
        self.secrets_service = secrets_service
        self.organization_id = organization_id
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.use_mock = use_mock

        # Session cache: key -> (session, expires_at)
        self._session_cache: dict[str, tuple[AuthenticatedSession, datetime]] = {}

        # Credential configs cache
        self._credential_configs: dict[str, CloudCredentialConfig] = {}

        # STS client for role assumption (lazy initialized)
        self._sts_client: "STSClient | None" = None

    def _get_partition(self) -> str:
        """Get AWS partition based on region.

        Returns:
            'aws' for commercial, 'aws-us-gov' for GovCloud
        """
        if self.region in self.GOVCLOUD_REGIONS:
            return "aws-us-gov"
        return "aws"

    def _get_sts_client(self) -> "STSClient":
        """Get or create STS client."""
        if self._sts_client is None:
            import boto3

            self._sts_client = boto3.client("sts", region_name=self.region)
        return self._sts_client

    async def connect(self) -> bool:
        """Connect to secrets service.

        Returns:
            True if connection successful
        """
        if self.use_mock:
            logger.info("Credential proxy connected in mock mode")
            return True

        connected = await self.secrets_service.connect()
        if connected:
            logger.info(f"Credential proxy connected for org {self.organization_id}")
        return connected

    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        self._session_cache.clear()
        self._credential_configs.clear()
        await self.secrets_service.disconnect()

    async def get_discovery_session(
        self,
        provider: str | CloudProvider,
        account_id: str,
        region: str | None = None,
    ) -> AuthenticatedSession:
        """Get pre-authenticated discovery session.

        This is the main method agents use to get cloud access.
        The returned session is pre-authenticated; agents never
        see raw credentials.

        Args:
            provider: Cloud provider ('aws', 'azure', or CloudProvider enum)
            account_id: Cloud account/subscription ID
            region: Optional region override

        Returns:
            AuthenticatedSession for making API calls

        Raises:
            CredentialError: If credentials not found or invalid
        """
        if isinstance(provider, str):
            provider = CloudProvider(provider)

        # Check cache first
        cache_key = f"{provider.value}:{account_id}:{region or self.region}"
        cached = self._session_cache.get(cache_key)
        if cached:
            session, expires_at = cached
            if datetime.now(timezone.utc) < expires_at:
                logger.debug(f"Using cached session for {cache_key}")
                return session

        # Get credential config
        config = await self._get_credential_config(provider, account_id)

        # Create session based on provider
        if provider == CloudProvider.AWS:
            session = await self._create_aws_session(config, region)
        elif provider == CloudProvider.AZURE:
            session = await self._create_azure_session(config)
        else:
            raise CredentialError(
                f"Unsupported provider: {provider.value}",
                provider=provider.value,
                account_id=account_id,
            )

        # Cache the session
        self._session_cache[cache_key] = (session, session.expires_at)

        logger.info(f"Created discovery session for {provider.value}:{account_id}")
        return session

    async def _get_credential_config(
        self, provider: CloudProvider, account_id: str
    ) -> CloudCredentialConfig:
        """Get credential configuration.

        Args:
            provider: Cloud provider
            account_id: Account ID

        Returns:
            Credential configuration

        Raises:
            CredentialError: If credential not found
        """
        config_key = f"{provider.value}:{account_id}"

        # Check cache
        if config_key in self._credential_configs:
            return self._credential_configs[config_key]

        if self.use_mock:
            # Return mock config for testing
            config = CloudCredentialConfig(
                credential_id=f"mock-{config_key}",
                provider=provider,
                credential_type=(
                    CredentialType.AWS_ROLE
                    if provider == CloudProvider.AWS
                    else CredentialType.AZURE_SERVICE_PRINCIPAL
                ),
                account_id=account_id,
                description="Mock credential for testing",
            )
            self._credential_configs[config_key] = config
            return config

        # Fetch from Secrets Manager
        secret_name = f"aura/{self.organization_id}/cloud-discovery/{provider.value}/{account_id}/config"

        try:
            secret = await self.secrets_service.get_secret(secret_name)
            if secret is None:
                raise CredentialError(
                    f"Credential not found for {provider.value}:{account_id}",
                    provider=provider.value,
                    account_id=account_id,
                    reason="not_found",
                )

            # Parse config from secret
            config_data = secret.value if isinstance(secret.value, dict) else {}

            config = CloudCredentialConfig(
                credential_id=config_data.get("credential_id", config_key),
                provider=provider,
                credential_type=CredentialType(
                    config_data.get("credential_type", "aws_role")
                ),
                account_id=account_id,
                description=config_data.get("description", ""),
                enabled=config_data.get("enabled", True),
                rotation_days=config_data.get("rotation_days", 90),
                external_id=config_data.get("external_id"),
            )

            if not config.enabled:
                raise CredentialError(
                    f"Credential for {provider.value}:{account_id} is disabled",
                    provider=provider.value,
                    account_id=account_id,
                    reason="disabled",
                )

            self._credential_configs[config_key] = config
            return config

        except CredentialError:
            raise
        except Exception as e:
            raise CredentialError(
                f"Failed to fetch credential config: {e}",
                provider=provider.value,
                account_id=account_id,
                reason="fetch_failed",
            ) from e

    async def _create_aws_session(
        self,
        config: CloudCredentialConfig,
        region: str | None = None,
    ) -> AuthenticatedSession:
        """Create AWS session from credential config.

        Supports:
        - IAM role assumption (preferred)
        - Static access keys (legacy)

        Args:
            config: Credential configuration
            region: Optional region override

        Returns:
            Authenticated boto3 session
        """
        if self.use_mock:
            return self._create_mock_aws_session(config, region)

        import boto3

        target_region = region or self.region

        if config.credential_type == CredentialType.AWS_ROLE:
            # Role assumption
            session = await self._assume_role(config, target_region)
        else:
            # Static credentials (legacy, not recommended)
            credentials = await self._get_aws_credentials(config)
            session = boto3.Session(
                aws_access_key_id=credentials["access_key_id"],
                aws_secret_access_key=credentials["secret_access_key"],
                region_name=target_region,
            )

        return AuthenticatedSession(
            provider=CloudProvider.AWS,
            account_id=config.account_id,
            region=target_region,
            session_type="boto3",
            expires_at=datetime.now(timezone.utc) + self.DEFAULT_SESSION_DURATION,
            session_object=session,
        )

    async def _assume_role(
        self,
        config: CloudCredentialConfig,
        region: str,
    ) -> Any:
        """Assume IAM role in target account.

        Args:
            config: Credential configuration with role info
            region: Target region

        Returns:
            boto3 Session with assumed role credentials
        """
        import boto3

        partition = self._get_partition()
        role_arn = f"arn:{partition}:iam::{config.account_id}:role/AuraDiscoveryRole"

        assume_params: dict[str, Any] = {
            "RoleArn": role_arn,
            "RoleSessionName": f"AuraDocAgent-{self.organization_id[:8]}",
            "DurationSeconds": 3600,  # 1 hour
        }

        if config.external_id:
            assume_params["ExternalId"] = config.external_id

        sts = self._get_sts_client()
        response = sts.assume_role(**assume_params)

        credentials = response["Credentials"]

        return boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=region,
        )

    async def _get_aws_credentials(
        self, config: CloudCredentialConfig
    ) -> dict[str, str]:
        """Get static AWS credentials from Secrets Manager.

        Args:
            config: Credential configuration

        Returns:
            Dict with access_key_id and secret_access_key
        """
        secret_name = (
            f"aura/{self.organization_id}/cloud-discovery/aws/"
            f"{config.account_id}/credentials"
        )

        secret = await self.secrets_service.get_secret(secret_name)
        if secret is None:
            raise CredentialError(
                f"AWS credentials not found for account {config.account_id}",
                provider="aws",
                account_id=config.account_id,
                reason="not_found",
            )

        if not isinstance(secret.value, dict):
            raise CredentialError(
                "Invalid credential format",
                provider="aws",
                account_id=config.account_id,
                reason="invalid_format",
            )

        return {
            "access_key_id": secret.value.get("access_key_id", ""),
            "secret_access_key": secret.value.get("secret_access_key", ""),
        }

    async def _create_azure_session(
        self, config: CloudCredentialConfig
    ) -> AuthenticatedSession:
        """Create Azure session from credential config.

        Args:
            config: Credential configuration

        Returns:
            Authenticated Azure credential
        """
        if self.use_mock:
            return self._create_mock_azure_session(config)

        from azure.identity import ClientSecretCredential

        # Get Azure credentials from Secrets Manager
        secret_name = (
            f"aura/{self.organization_id}/cloud-discovery/azure/"
            f"{config.account_id}/credentials"
        )

        secret = await self.secrets_service.get_secret(secret_name)
        if secret is None:
            raise CredentialError(
                f"Azure credentials not found for subscription {config.account_id}",
                provider="azure",
                account_id=config.account_id,
                reason="not_found",
            )

        creds = secret.value if isinstance(secret.value, dict) else {}

        credential = ClientSecretCredential(
            tenant_id=creds.get("tenant_id", ""),
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
        )

        return AuthenticatedSession(
            provider=CloudProvider.AZURE,
            account_id=config.account_id,
            session_type="azure_credential",
            expires_at=datetime.now(timezone.utc) + self.DEFAULT_SESSION_DURATION,
            session_object=credential,
        )

    def _create_mock_aws_session(
        self,
        config: CloudCredentialConfig,
        region: str | None = None,
    ) -> AuthenticatedSession:
        """Create mock AWS session for testing."""
        from unittest.mock import MagicMock

        mock_session = MagicMock()
        mock_session.region_name = region or self.region

        return AuthenticatedSession(
            provider=CloudProvider.AWS,
            account_id=config.account_id,
            region=region or self.region,
            session_type="boto3_mock",
            expires_at=datetime.now(timezone.utc) + self.DEFAULT_SESSION_DURATION,
            session_object=mock_session,
        )

    def _create_mock_azure_session(
        self, config: CloudCredentialConfig
    ) -> AuthenticatedSession:
        """Create mock Azure session for testing."""
        from unittest.mock import MagicMock

        mock_credential = MagicMock()

        return AuthenticatedSession(
            provider=CloudProvider.AZURE,
            account_id=config.account_id,
            session_type="azure_credential_mock",
            expires_at=datetime.now(timezone.utc) + self.DEFAULT_SESSION_DURATION,
            session_object=mock_credential,
        )

    async def validate_credentials(
        self, provider: str | CloudProvider, account_id: str
    ) -> bool:
        """Validate that credentials work.

        Args:
            provider: Cloud provider
            account_id: Account ID

        Returns:
            True if credentials are valid
        """
        if isinstance(provider, str):
            provider = CloudProvider(provider)

        try:
            session = await self.get_discovery_session(provider, account_id)

            if provider == CloudProvider.AWS:
                # Test with STS GetCallerIdentity
                sts = session.session_object.client("sts")
                sts.get_caller_identity()
            elif provider == CloudProvider.AZURE:
                # Test by getting a token
                session.session_object.get_token(
                    "https://management.azure.com/.default"
                )

            return True
        except Exception as e:
            logger.warning(f"Credential validation failed: {e}")
            return False

    async def rotate_credentials(
        self, provider: str | CloudProvider, account_id: str
    ) -> bool:
        """Trigger credential rotation.

        Args:
            provider: Cloud provider
            account_id: Account ID

        Returns:
            True if rotation initiated successfully
        """
        if isinstance(provider, str):
            provider = CloudProvider(provider)

        secret_name = (
            f"aura/{self.organization_id}/cloud-discovery/{provider.value}/"
            f"{account_id}/credentials"
        )

        try:
            await self.secrets_service.rotate_secret_immediately(secret_name)

            # Clear cached session
            cache_key = f"{provider.value}:{account_id}:{self.region}"
            self._session_cache.pop(cache_key, None)

            logger.info(f"Initiated rotation for {provider.value}:{account_id}")
            return True
        except Exception as e:
            logger.error(f"Credential rotation failed: {e}")
            return False

    async def list_configured_accounts(
        self, provider: CloudProvider | None = None
    ) -> list[CloudCredentialConfig]:
        """List configured cloud accounts.

        Args:
            provider: Optional filter by provider

        Returns:
            List of credential configurations
        """
        prefix = f"aura/{self.organization_id}/cloud-discovery/"
        if provider:
            prefix += f"{provider.value}/"

        secret_names = await self.secrets_service.list_secrets(prefix=prefix)

        configs: list[CloudCredentialConfig] = []
        for name in secret_names:
            if name.endswith("/config"):
                parts = name.split("/")
                if len(parts) >= 5:
                    prov = CloudProvider(parts[3])
                    acc_id = parts[4]
                    try:
                        config = await self._get_credential_config(prov, acc_id)
                        configs.append(config)
                    except CredentialError:
                        pass  # Skip invalid configs

        return configs

    def clear_session_cache(self) -> None:
        """Clear all cached sessions."""
        self._session_cache.clear()
        logger.info("Session cache cleared")
