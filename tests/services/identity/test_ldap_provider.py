"""
Project Aura - LDAP Provider Tests

Tests for the LDAP/Active Directory identity provider.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.identity.base_provider import AuthenticationError, ConfigurationError
from src.services.identity.models import (
    AttributeMapping,
    AuthCredentials,
    ConnectionStatus,
    GroupMapping,
    IdentityProviderConfig,
    IdPType,
)
from src.services.identity.providers.ldap_provider import LDAPProvider


class TestLDAPProviderConfiguration:
    """Tests for LDAP provider configuration."""

    @pytest.fixture
    def valid_ldap_config(self):
        """Create valid LDAP configuration."""
        return IdentityProviderConfig(
            idp_id="idp-ldap-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="Corporate LDAP",
            connection_settings={
                "server": "ldap.corp.com",
                "port": 636,
                "use_ssl": True,
                "use_tls": False,
                "base_dn": "DC=corp,DC=com",
                "user_search_base": "OU=Users,DC=corp,DC=com",
                "bind_dn": "CN=ServiceAccount,OU=Services,DC=corp,DC=com",
            },
            credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:ldap-creds",
        )

    def test_valid_configuration(self, valid_ldap_config):
        """Test valid configuration creates provider."""
        provider = LDAPProvider(valid_ldap_config)
        assert provider.server == "ldap.corp.com"
        assert provider.port == 636
        assert provider.use_ssl is True
        assert provider.use_tls is False
        assert provider.base_dn == "DC=corp,DC=com"

    def test_missing_server(self, valid_ldap_config):
        """Test error when server is missing."""
        valid_ldap_config.connection_settings["server"] = None
        with pytest.raises(ConfigurationError) as exc_info:
            LDAPProvider(valid_ldap_config)
        assert "server is required" in str(exc_info.value)

    def test_missing_base_dn(self, valid_ldap_config):
        """Test error when base_dn is missing."""
        valid_ldap_config.connection_settings["base_dn"] = None
        with pytest.raises(ConfigurationError) as exc_info:
            LDAPProvider(valid_ldap_config)
        assert "base_dn is required" in str(exc_info.value)

    def test_missing_bind_dn(self, valid_ldap_config):
        """Test error when bind_dn is missing."""
        valid_ldap_config.connection_settings["bind_dn"] = None
        with pytest.raises(ConfigurationError) as exc_info:
            LDAPProvider(valid_ldap_config)
        assert "bind_dn is required" in str(exc_info.value)

    def test_wrong_idp_type(self, valid_ldap_config):
        """Test error when IdP type is not LDAP."""
        valid_ldap_config.idp_type = IdPType.SAML
        with pytest.raises(ConfigurationError) as exc_info:
            LDAPProvider(valid_ldap_config)
        assert "Invalid IdP type" in str(exc_info.value)

    def test_default_settings(self, valid_ldap_config):
        """Test default values are applied."""
        # Remove optional settings
        valid_ldap_config.connection_settings = {
            "server": "ldap.corp.com",
            "base_dn": "DC=corp,DC=com",
            "bind_dn": "CN=Service,DC=corp,DC=com",
        }
        provider = LDAPProvider(valid_ldap_config)

        assert provider.port == 389  # Default
        assert provider.use_ssl is False  # Default
        assert provider.use_tls is True  # Default
        assert provider.connect_timeout == 10  # Default
        assert provider.receive_timeout == 30  # Default
        assert provider.resolve_nested_groups is True  # Default

    def test_user_search_base_defaults_to_base_dn(self, valid_ldap_config):
        """Test user_search_base defaults to base_dn."""
        del valid_ldap_config.connection_settings["user_search_base"]
        provider = LDAPProvider(valid_ldap_config)
        assert provider.user_search_base == provider.base_dn


class TestLDAPProviderAuthentication:
    """Tests for LDAP authentication."""

    @pytest.fixture
    def ldap_config(self):
        """Create LDAP configuration for tests."""
        return IdentityProviderConfig(
            idp_id="idp-ldap-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="Corporate LDAP",
            connection_settings={
                "server": "ldap.corp.com",
                "port": 636,
                "use_ssl": True,
                "base_dn": "DC=corp,DC=com",
                "bind_dn": "CN=Service,DC=corp,DC=com",
            },
            credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:ldap-creds",
            attribute_mappings=[
                AttributeMapping("mail", "email", required=True),
                AttributeMapping("displayName", "name"),
            ],
            group_mappings=[
                GroupMapping("CN=Admins,DC=corp,DC=com", "admin"),
            ],
        )

    @pytest.fixture
    def provider(self, ldap_config):
        """Create LDAP provider."""
        return LDAPProvider(ldap_config)

    @pytest.mark.asyncio
    async def test_authenticate_missing_username(self, provider):
        """Test authentication fails without username."""
        credentials = AuthCredentials(password="secret")
        result = await provider.authenticate(credentials)

        assert result.success is False
        assert result.error_code == "MISSING_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_authenticate_missing_password(self, provider):
        """Test authentication fails without password."""
        credentials = AuthCredentials(username="john.doe")
        result = await provider.authenticate(credentials)

        assert result.success is False
        assert result.error_code == "MISSING_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_authenticate_ldap_not_available(self, provider):
        """Test authentication when ldap3 is not available."""
        credentials = AuthCredentials(username="john.doe", password="secret")

        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=None,
        ):
            result = await provider.authenticate(credentials)

        assert result.success is False
        assert result.error_code == "LDAP_NOT_AVAILABLE"

    @pytest.mark.asyncio
    async def test_authenticate_success(self, provider):
        """Test successful LDAP authentication."""
        credentials = AuthCredentials(username="john.doe", password="correctpassword")

        # Create mock ldap3 module
        mock_ldap3 = MagicMock()
        mock_ldap3.ALL = "ALL"
        mock_ldap3.ALL_ATTRIBUTES = "ALL_ATTRIBUTES"
        mock_ldap3.SUBTREE = "SUBTREE"
        mock_ldap3.BASE = "BASE"

        # Mock user entry
        mock_entry = MagicMock()
        mock_entry.entry_dn = "CN=John Doe,OU=Users,DC=corp,DC=com"
        mock_entry.entry_attributes_as_dict = {
            "mail": ["john.doe@corp.com"],
            "displayName": ["John Doe"],
            "sAMAccountName": ["john.doe"],
        }

        # Mock service connection
        mock_service_conn = MagicMock()
        mock_service_conn.bind.return_value = True
        mock_service_conn.search.return_value = True
        mock_service_conn.entries = [mock_entry]

        # Mock user connection
        mock_user_conn = MagicMock()
        mock_user_conn.bind.return_value = True

        # Mock ldap3.Connection to return different mocks
        connection_call_count = [0]

        def mock_connection(*args, **kwargs):
            connection_call_count[0] += 1
            if connection_call_count[0] == 1:
                return mock_service_conn
            return mock_user_conn

        mock_ldap3.Connection = mock_connection
        mock_ldap3.Server = MagicMock()

        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=mock_ldap3,
        ):
            with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
                with patch.object(
                    provider, "_resolve_groups", new_callable=AsyncMock
                ) as mock_groups:
                    mock_groups.return_value = ["CN=Admins,DC=corp,DC=com"]

                    # Mock the server and connection creation
                    with patch.object(
                        provider, "_create_server", return_value=MagicMock()
                    ):
                        with patch.object(
                            provider,
                            "_create_service_connection",
                            return_value=mock_service_conn,
                        ):
                            result = await provider.authenticate(credentials)

        assert result.success is True
        assert result.email == "john.doe@corp.com"
        assert result.name == "John Doe"
        assert "admin" in result.roles

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, provider):
        """Test authentication when user is not found."""
        credentials = AuthCredentials(username="unknown.user", password="secret")

        mock_ldap3 = MagicMock()
        mock_ldap3.ALL_ATTRIBUTES = "ALL_ATTRIBUTES"
        mock_ldap3.SUBTREE = "SUBTREE"

        mock_service_conn = MagicMock()
        mock_service_conn.bind.return_value = True
        mock_service_conn.search.return_value = True
        mock_service_conn.entries = []  # No entries found

        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=mock_ldap3,
        ):
            with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
                with patch.object(provider, "_create_server", return_value=MagicMock()):
                    with patch.object(
                        provider,
                        "_create_service_connection",
                        return_value=mock_service_conn,
                    ):
                        result = await provider.authenticate(credentials)

        assert result.success is False
        assert result.error_code == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_credentials(self, provider):
        """Test authentication with wrong password."""
        credentials = AuthCredentials(username="john.doe", password="wrongpassword")

        mock_ldap3 = MagicMock()
        mock_ldap3.ALL_ATTRIBUTES = "ALL_ATTRIBUTES"
        mock_ldap3.SUBTREE = "SUBTREE"

        mock_entry = MagicMock()
        mock_entry.entry_dn = "CN=John Doe,OU=Users,DC=corp,DC=com"
        mock_entry.entry_attributes_as_dict = {"mail": ["john@corp.com"]}

        mock_service_conn = MagicMock()
        mock_service_conn.bind.return_value = True
        mock_service_conn.search.return_value = True
        mock_service_conn.entries = [mock_entry]

        mock_user_conn = MagicMock()
        mock_user_conn.bind.return_value = False  # User bind fails

        mock_ldap3.Connection = MagicMock(return_value=mock_user_conn)

        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=mock_ldap3,
        ):
            with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
                with patch.object(provider, "_create_server", return_value=MagicMock()):
                    with patch.object(
                        provider,
                        "_create_service_connection",
                        return_value=mock_service_conn,
                    ):
                        result = await provider.authenticate(credentials)

        assert result.success is False
        assert result.error_code == "INVALID_CREDENTIALS"


class TestLDAPProviderTokenOperations:
    """Tests for LDAP token operations (mostly unsupported)."""

    @pytest.fixture
    def provider(self):
        """Create LDAP provider."""
        config = IdentityProviderConfig(
            idp_id="idp-ldap-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="LDAP",
            connection_settings={
                "server": "ldap.corp.com",
                "base_dn": "DC=corp,DC=com",
                "bind_dn": "CN=Service,DC=corp,DC=com",
            },
            credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:ldap",
        )
        return LDAPProvider(config)

    @pytest.mark.asyncio
    async def test_validate_token_always_invalid(self, provider):
        """Test LDAP doesn't support token validation."""
        result = await provider.validate_token("some-token")

        assert result.valid is False
        assert "LDAP does not use tokens" in result.error

    @pytest.mark.asyncio
    async def test_refresh_token_not_supported(self, provider):
        """Test LDAP doesn't support token refresh."""
        with pytest.raises(AuthenticationError) as exc_info:
            await provider.refresh_token("refresh-token")
        assert "does not support token refresh" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_logout_always_succeeds(self, provider):
        """Test LDAP logout always succeeds (stateless)."""
        result = await provider.logout("token")
        assert result is True


class TestLDAPProviderHealthCheck:
    """Tests for LDAP health check."""

    @pytest.fixture
    def provider(self):
        """Create LDAP provider."""
        config = IdentityProviderConfig(
            idp_id="idp-ldap-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="LDAP",
            connection_settings={
                "server": "ldap.corp.com",
                "port": 636,
                "use_ssl": True,
                "base_dn": "DC=corp,DC=com",
                "bind_dn": "CN=Service,DC=corp,DC=com",
            },
            credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:ldap",
        )
        return LDAPProvider(config)

    @pytest.mark.asyncio
    async def test_health_check_ldap_not_available(self, provider):
        """Test health check when ldap3 is not available."""
        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=None,
        ):
            result = await provider.health_check()

        assert result.healthy is False
        assert result.status == ConnectionStatus.ERROR
        assert "ldap3 library not available" in result.message

    @pytest.mark.asyncio
    async def test_health_check_success(self, provider):
        """Test successful health check."""
        mock_ldap3 = MagicMock()
        mock_ldap3.BASE = "BASE"

        mock_conn = MagicMock()
        mock_conn.bind.return_value = True
        mock_conn.search.return_value = True

        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=mock_ldap3,
        ):
            with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
                with patch.object(provider, "_create_server", return_value=MagicMock()):
                    with patch.object(
                        provider, "_create_service_connection", return_value=mock_conn
                    ):
                        result = await provider.health_check()

        assert result.healthy is True
        assert result.status == ConnectionStatus.CONNECTED
        assert result.latency_ms > 0
        assert "server" in result.details
        assert result.details["server"] == "ldap.corp.com"

    @pytest.mark.asyncio
    async def test_health_check_connection_failure(self, provider):
        """Test health check on connection failure."""
        mock_ldap3 = MagicMock()

        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=mock_ldap3,
        ):
            with patch.object(provider, "_load_credentials", new_callable=AsyncMock):
                with patch.object(
                    provider,
                    "_create_server",
                    side_effect=Exception("Connection refused"),
                ):
                    result = await provider.health_check()

        assert result.healthy is False
        assert result.status == ConnectionStatus.ERROR
        assert "Connection refused" in result.message


class TestLDAPProviderGroupResolution:
    """Tests for LDAP group resolution."""

    @pytest.fixture
    def provider(self):
        """Create LDAP provider."""
        config = IdentityProviderConfig(
            idp_id="idp-ldap-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="LDAP",
            connection_settings={
                "server": "ldap.corp.com",
                "base_dn": "DC=corp,DC=com",
                "bind_dn": "CN=Service,DC=corp,DC=com",
                "resolve_nested_groups": True,
            },
            credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:ldap",
        )
        return LDAPProvider(config)

    @pytest.mark.asyncio
    async def test_resolve_groups_ad_nested(self, provider):
        """Test AD nested group resolution."""
        mock_ldap3 = MagicMock()
        mock_ldap3.SUBTREE = "SUBTREE"

        mock_entry1 = MagicMock()
        mock_entry1.entry_dn = "CN=Admins,DC=corp,DC=com"
        mock_entry2 = MagicMock()
        mock_entry2.entry_dn = "CN=AllUsers,DC=corp,DC=com"

        mock_conn = MagicMock()
        mock_conn.search.return_value = True
        mock_conn.entries = [mock_entry1, mock_entry2]

        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=mock_ldap3,
        ):
            groups = await provider._resolve_groups(
                mock_conn, "CN=John Doe,OU=Users,DC=corp,DC=com"
            )

        assert len(groups) == 2
        assert "CN=Admins,DC=corp,DC=com" in groups
        assert "CN=AllUsers,DC=corp,DC=com" in groups

    @pytest.mark.asyncio
    async def test_resolve_groups_fallback_direct(self, provider):
        """Test fallback to direct group membership."""
        mock_ldap3 = MagicMock()
        mock_ldap3.SUBTREE = "SUBTREE"

        mock_entry = MagicMock()
        mock_entry.entry_dn = "CN=DirectGroup,DC=corp,DC=com"

        mock_conn = MagicMock()
        # First call (AD nested query) fails, second succeeds
        mock_conn.search.side_effect = [
            Exception("Not supported"),  # AD nested fails
            True,  # Direct query succeeds
        ]
        mock_conn.entries = [mock_entry]

        with patch(
            "src.services.identity.providers.ldap_provider._get_ldap3",
            return_value=mock_ldap3,
        ):
            groups = await provider._resolve_groups(
                mock_conn, "CN=John Doe,OU=Users,DC=corp,DC=com"
            )

        assert len(groups) == 1
        assert "CN=DirectGroup,DC=corp,DC=com" in groups


class TestLDAPProviderCredentialsLoading:
    """Tests for LDAP credentials loading from Secrets Manager."""

    @pytest.fixture
    def provider(self):
        """Create LDAP provider."""
        config = IdentityProviderConfig(
            idp_id="idp-ldap-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="LDAP",
            connection_settings={
                "server": "ldap.corp.com",
                "base_dn": "DC=corp,DC=com",
                "bind_dn": "CN=Service,DC=corp,DC=com",
            },
            credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:ldap",
        )
        return LDAPProvider(config)

    @pytest.mark.asyncio
    async def test_load_credentials_missing_arn(self, provider):
        """Test error when credentials_secret_arn is missing."""
        provider.config.credentials_secret_arn = None

        with pytest.raises(ConfigurationError) as exc_info:
            await provider._load_credentials()
        assert "credentials_secret_arn is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_credentials_success(self, provider):
        """Test successful credentials loading."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": '{"bind_password": "supersecret"}'
        }

        with patch(
            "src.services.identity.providers.ldap_provider._get_secrets_client",
            return_value=mock_client,
        ):
            await provider._load_credentials()

        assert provider._bind_password == "supersecret"
        assert provider._credentials_loaded is True

    @pytest.mark.asyncio
    async def test_load_credentials_missing_password(self, provider):
        """Test error when bind_password is missing in secret."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": '{"other_field": "value"}'
        }

        with patch(
            "src.services.identity.providers.ldap_provider._get_secrets_client",
            return_value=mock_client,
        ):
            with pytest.raises(ConfigurationError) as exc_info:
                await provider._load_credentials()
        assert "bind_password not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_credentials_cached(self, provider):
        """Test credentials are only loaded once."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": '{"bind_password": "secret"}'
        }

        with patch(
            "src.services.identity.providers.ldap_provider._get_secrets_client",
            return_value=mock_client,
        ):
            await provider._load_credentials()
            await provider._load_credentials()  # Second call

        # Should only be called once
        assert mock_client.get_secret_value.call_count == 1
