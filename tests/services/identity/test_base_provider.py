"""
Project Aura - Base Provider Tests

Tests for the abstract base identity provider class and factory.
"""

import pytest

from src.services.identity.base_provider import (
    AttributeMappingError,
    AuthenticationError,
    ConfigurationError,
    ConnectionError,
    IdentityProvider,
    IdentityProviderError,
    IdentityProviderFactory,
)
from src.services.identity.models import (
    AttributeMapping,
    AuthCredentials,
    AuthResult,
    ConnectionStatus,
    GroupMapping,
    HealthCheckResult,
    IdentityProviderConfig,
    IdPType,
    TokenResult,
    TokenValidationResult,
    UserInfo,
)


class MockIdentityProvider(IdentityProvider):
    """Mock provider for testing base class functionality."""

    async def authenticate(self, credentials: AuthCredentials) -> AuthResult:
        return AuthResult(
            success=True,
            user_id="mock-user-123",
            email="user@example.com",
        )

    async def validate_token(self, token: str) -> TokenValidationResult:
        return TokenValidationResult(valid=True, claims={"sub": "mock-user"})

    async def get_user_info(self, token: str) -> UserInfo:
        return UserInfo(user_id="mock-user-123", email="user@example.com")

    async def refresh_token(self, refresh_token: str) -> TokenResult:
        return TokenResult(access_token="new_access_token")

    async def logout(self, token: str) -> bool:
        return True

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(healthy=True, status=ConnectionStatus.CONNECTED)


class TestIdentityProviderExceptions:
    """Tests for identity provider exceptions."""

    def test_base_exception(self):
        """Test base IdentityProviderError."""
        error = IdentityProviderError("Test error", error_code="TEST_001")
        assert str(error) == "Test error"
        assert error.error_code == "TEST_001"

    def test_attribute_mapping_error(self):
        """Test AttributeMappingError."""
        error = AttributeMappingError(
            "Missing required attribute",
            error_code="MISSING_ATTR",
        )
        assert "Missing required attribute" in str(error)
        assert error.error_code == "MISSING_ATTR"

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("Invalid credentials")
        assert "Invalid credentials" in str(error)

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Invalid configuration")
        assert "Invalid configuration" in str(error)

    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Cannot connect to LDAP server")
        assert "Cannot connect" in str(error)


class TestIdentityProviderBase:
    """Tests for IdentityProvider base class."""

    @pytest.fixture
    def ldap_config(self):
        """Create a test LDAP configuration."""
        return IdentityProviderConfig(
            idp_id="idp-ldap-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="Corporate LDAP",
            attribute_mappings=[
                AttributeMapping("mail", "email", required=True),
                AttributeMapping("displayName", "name"),
                AttributeMapping("sAMAccountName", "username", transform="lowercase"),
            ],
            group_mappings=[
                GroupMapping("CN=Admins,DC=corp,DC=com", "admin", priority=10),
                GroupMapping("CN=Developers,DC=corp,DC=com", "developer", priority=20),
                GroupMapping("CN=Users,DC=corp,DC=com", "viewer", priority=100),
            ],
        )

    @pytest.fixture
    def mock_provider(self, ldap_config):
        """Create a mock provider instance."""
        return MockIdentityProvider(ldap_config)

    def test_provider_initialization(self, mock_provider, ldap_config):
        """Test provider initialization."""
        assert mock_provider.idp_id == "idp-ldap-123"
        assert mock_provider.name == "Corporate LDAP"
        assert mock_provider.idp_type == IdPType.LDAP
        assert mock_provider.organization_id == "org-456"

    def test_initial_status(self, mock_provider):
        """Test initial connection status."""
        assert mock_provider.status == ConnectionStatus.DISCONNECTED
        assert mock_provider._last_error is None

    def test_metrics_initial(self, mock_provider):
        """Test initial metrics."""
        metrics = mock_provider.metrics
        assert metrics["idp_id"] == "idp-ldap-123"
        assert metrics["request_count"] == 0
        assert metrics["error_count"] == 0
        assert metrics["avg_latency_ms"] == 0

    def test_map_attributes_basic(self, mock_provider):
        """Test basic attribute mapping."""
        claims = {
            "mail": "user@corp.com",
            "displayName": "John Doe",
            "sAMAccountName": "JDoe",
        }
        result = mock_provider.map_attributes(claims)
        assert result["email"] == "user@corp.com"
        assert result["name"] == "John Doe"
        assert result["username"] == "jdoe"  # lowercase transformed

    def test_map_attributes_missing_required(self, mock_provider):
        """Test error when required attribute is missing."""
        claims = {
            "displayName": "John Doe",
            # mail is missing
        }
        with pytest.raises(AttributeMappingError) as exc_info:
            mock_provider.map_attributes(claims)
        assert "mail" in str(exc_info.value)
        assert "MISSING_REQUIRED_ATTRIBUTE" in exc_info.value.error_code

    def test_map_attributes_default_value(self, ldap_config):
        """Test attribute mapping with default value."""
        ldap_config.attribute_mappings.append(
            AttributeMapping(
                "department",
                "department",
                required=False,
                default_value="Unassigned",
            )
        )
        provider = MockIdentityProvider(ldap_config)
        claims = {"mail": "user@corp.com"}
        result = provider.map_attributes(claims)
        assert result["department"] == "Unassigned"

    def test_map_attributes_nested_value(self, ldap_config):
        """Test mapping nested attribute values."""
        ldap_config.attribute_mappings = [
            AttributeMapping("user.profile.email", "email", required=True),
        ]
        provider = MockIdentityProvider(ldap_config)
        claims = {
            "user": {
                "profile": {
                    "email": "nested@example.com",
                }
            }
        }
        result = provider.map_attributes(claims)
        assert result["email"] == "nested@example.com"

    def test_map_groups_to_roles_basic(self, mock_provider):
        """Test basic group to role mapping."""
        groups = ["CN=Admins,DC=corp,DC=com", "CN=Users,DC=corp,DC=com"]
        roles = mock_provider.map_groups_to_roles(groups)
        assert "admin" in roles
        assert "viewer" in roles

    def test_map_groups_to_roles_empty(self, mock_provider):
        """Test empty groups default to viewer."""
        roles = mock_provider.map_groups_to_roles([])
        assert roles == ["viewer"]

    def test_map_groups_to_roles_no_match(self, mock_provider):
        """Test unmatched groups default to viewer."""
        groups = ["CN=Unknown,DC=corp,DC=com"]
        roles = mock_provider.map_groups_to_roles(groups)
        assert roles == ["viewer"]

    def test_map_groups_priority(self, mock_provider):
        """Test group mapping respects priority."""
        # Both groups match but admin has lower priority (higher importance)
        groups = ["CN=Admins,DC=corp,DC=com", "CN=Developers,DC=corp,DC=com"]
        roles = mock_provider.map_groups_to_roles(groups)
        # Both roles should be present
        assert "admin" in roles
        assert "developer" in roles

    def test_apply_transform_lowercase(self, mock_provider):
        """Test lowercase transform."""
        result = mock_provider._apply_transform("UPPERCASE", "lowercase")
        assert result == "uppercase"

    def test_apply_transform_uppercase(self, mock_provider):
        """Test uppercase transform."""
        result = mock_provider._apply_transform("lowercase", "uppercase")
        assert result == "LOWERCASE"

    def test_apply_transform_split(self, mock_provider):
        """Test split transform."""
        result = mock_provider._apply_transform("a,b,c", "split")
        assert result == ["a", "b", "c"]

    def test_apply_transform_join(self, mock_provider):
        """Test join transform."""
        result = mock_provider._apply_transform(["a", "b", "c"], "join")
        assert result == "a,b,c"

    def test_apply_transform_first(self, mock_provider):
        """Test first transform."""
        result = mock_provider._apply_transform(["first", "second"], "first")
        assert result == "first"

    def test_apply_transform_trim(self, mock_provider):
        """Test trim transform."""
        result = mock_provider._apply_transform("  spaced  ", "trim")
        assert result == "spaced"

    def test_apply_transform_strip_domain(self, mock_provider):
        """Test strip_domain transform."""
        result = mock_provider._apply_transform("user@example.com", "strip_domain")
        assert result == "user"

    def test_apply_transform_unknown(self, mock_provider):
        """Test unknown transform returns value as-is."""
        result = mock_provider._apply_transform("value", "unknown_transform")
        assert result == "value"

    def test_apply_transform_none_value(self, mock_provider):
        """Test transform with None value."""
        result = mock_provider._apply_transform(None, "lowercase")
        assert result is None

    def test_flatten_ldap_attrs_single(self, mock_provider):
        """Test flattening single-element lists."""
        attrs = {
            "mail": ["user@example.com"],
            "displayName": ["John Doe"],
        }
        result = mock_provider._flatten_ldap_attrs(attrs)
        assert result["mail"] == "user@example.com"
        assert result["displayName"] == "John Doe"

    def test_flatten_ldap_attrs_multiple(self, mock_provider):
        """Test multi-element lists stay as lists."""
        attrs = {
            "memberOf": ["Group1", "Group2", "Group3"],
        }
        result = mock_provider._flatten_ldap_attrs(attrs)
        assert result["memberOf"] == ["Group1", "Group2", "Group3"]

    def test_record_request(self, mock_provider):
        """Test request recording."""
        mock_provider._record_request(100.0, True)
        mock_provider._record_request(50.0, False)

        assert mock_provider._request_count == 2
        assert mock_provider._error_count == 1
        assert mock_provider._total_latency_ms == 150.0

        metrics = mock_provider.metrics
        assert metrics["avg_latency_ms"] == 75.0

    def test_set_status(self, mock_provider):
        """Test status updates."""
        mock_provider._set_status(ConnectionStatus.CONNECTED)
        assert mock_provider.status == ConnectionStatus.CONNECTED

        mock_provider._set_status(ConnectionStatus.ERROR, "Connection failed")
        assert mock_provider.status == ConnectionStatus.ERROR
        assert mock_provider._last_error == "Connection failed"


class TestIdentityProviderFactory:
    """Tests for IdentityProviderFactory."""

    def test_register_provider(self):
        """Test provider registration."""
        IdentityProviderFactory.register("test", MockIdentityProvider)
        assert "test" in IdentityProviderFactory.available_providers()

    def test_create_provider(self):
        """Test creating a registered provider."""
        # Register the mock provider
        IdentityProviderFactory.register("mock", MockIdentityProvider)

        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.SSO,  # Will use the registered "mock" type
            name="Mock Provider",
        )
        # Manually set the value to match our registered type
        config.idp_type = IdPType.SSO

        # Re-register with correct type
        IdentityProviderFactory.register("sso", MockIdentityProvider)

        provider = IdentityProviderFactory.create(config)
        assert isinstance(provider, MockIdentityProvider)

    def test_create_unknown_provider(self):
        """Test creating unregistered provider raises error."""
        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="Unknown Provider",
        )
        # Clear registrations to ensure LDAP isn't registered
        original_providers = IdentityProviderFactory._providers.copy()
        IdentityProviderFactory._providers = {}

        try:
            with pytest.raises(ValueError) as exc_info:
                IdentityProviderFactory.create(config)
            assert "Unknown IdP type" in str(exc_info.value)
        finally:
            # Restore original providers
            IdentityProviderFactory._providers = original_providers

    def test_available_providers(self):
        """Test listing available providers."""
        IdentityProviderFactory.register("test1", MockIdentityProvider)
        IdentityProviderFactory.register("test2", MockIdentityProvider)
        providers = IdentityProviderFactory.available_providers()
        assert "test1" in providers
        assert "test2" in providers


class TestDefaultAttributeMappings:
    """Tests for default attribute mappings in configs."""

    def test_uses_defaults_when_no_mappings(self):
        """Test that default mappings are used when none configured."""
        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.OIDC,
            name="OIDC Provider",
            attribute_mappings=[],  # No mappings
        )
        provider = MockIdentityProvider(config)

        claims = {
            "email": "user@example.com",
            "name": "Test User",
        }
        result = provider.map_attributes(claims)
        assert result["email"] == "user@example.com"
        assert result["name"] == "Test User"


class TestRegexGroupMapping:
    """Tests for regex-based group matching."""

    @pytest.fixture
    def regex_config(self):
        """Create config with regex group mappings."""
        return IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="LDAP",
            group_mappings=[
                GroupMapping(
                    source_group=r"CN=.*-Admins,.*",
                    target_role="admin",
                    is_regex=True,
                    priority=10,
                ),
                GroupMapping(
                    source_group=r"CN=.*-Dev(eloper)?s?,.*",
                    target_role="developer",
                    is_regex=True,
                    priority=20,
                ),
            ],
        )

    def test_regex_admin_match(self, regex_config):
        """Test regex matches admin groups."""
        provider = MockIdentityProvider(regex_config)
        groups = ["CN=Security-Admins,OU=Groups,DC=corp,DC=com"]
        roles = provider.map_groups_to_roles(groups)
        assert "admin" in roles

    def test_regex_developer_match(self, regex_config):
        """Test regex matches developer groups."""
        provider = MockIdentityProvider(regex_config)
        groups = ["CN=App-Developers,OU=Groups,DC=corp,DC=com"]
        roles = provider.map_groups_to_roles(groups)
        assert "developer" in roles

    def test_regex_no_match(self, regex_config):
        """Test regex non-match defaults to viewer."""
        provider = MockIdentityProvider(regex_config)
        groups = ["CN=Sales-Team,OU=Groups,DC=corp,DC=com"]
        roles = provider.map_groups_to_roles(groups)
        assert roles == ["viewer"]
