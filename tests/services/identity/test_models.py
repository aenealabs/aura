"""
Project Aura - Identity Models Tests

Tests for the identity data models, enums, and validators.
"""

import pytest

from src.services.identity.models import (
    VALID_AURA_ROLES,
    AttributeMapping,
    AuditLogEntry,
    AuraTokens,
    AuthAction,
    AuthCredentials,
    AuthResult,
    AuthSession,
    ConnectionStatus,
    GroupMapping,
    HealthCheckResult,
    IdentityProviderConfig,
    IdPType,
    TokenResult,
    TokenValidationResult,
    UserInfo,
    extract_email_domain,
    validate_email_domain,
    validate_role,
)


class TestIdPType:
    """Tests for IdPType enum."""

    def test_all_types_defined(self):
        """Test all expected IdP types are defined."""
        expected_types = ["cognito", "ldap", "saml", "oidc", "pingid", "sso"]
        actual_types = [t.value for t in IdPType]
        assert set(expected_types) == set(actual_types)

    def test_from_string_valid(self):
        """Test from_string with valid values."""
        assert IdPType.from_string("ldap") == IdPType.LDAP
        assert IdPType.from_string("LDAP") == IdPType.LDAP
        assert IdPType.from_string("Ldap") == IdPType.LDAP
        assert IdPType.from_string("saml") == IdPType.SAML
        assert IdPType.from_string("oidc") == IdPType.OIDC
        assert IdPType.from_string("cognito") == IdPType.COGNITO

    def test_from_string_invalid(self):
        """Test from_string raises error for invalid values."""
        with pytest.raises(ValueError) as exc_info:
            IdPType.from_string("invalid")
        assert "Invalid IdP type" in str(exc_info.value)

    def test_enum_values(self):
        """Test enum values are correct strings."""
        assert IdPType.COGNITO.value == "cognito"
        assert IdPType.LDAP.value == "ldap"
        assert IdPType.SAML.value == "saml"
        assert IdPType.OIDC.value == "oidc"
        assert IdPType.PINGID.value == "pingid"
        assert IdPType.SSO.value == "sso"


class TestAuthAction:
    """Tests for AuthAction enum."""

    def test_all_actions_defined(self):
        """Test all expected auth actions are defined."""
        expected = [
            "config_create",
            "config_update",
            "config_delete",
            "auth_success",
            "auth_failure",
            "token_refresh",
            "token_revoke",
            "session_logout",
            "health_check",
        ]
        actual = [a.value for a in AuthAction]
        assert set(expected) == set(actual)


class TestConnectionStatus:
    """Tests for ConnectionStatus enum."""

    def test_all_statuses_defined(self):
        """Test all expected connection statuses are defined."""
        expected = ["connected", "disconnected", "error", "degraded", "auth_failed"]
        actual = [s.value for s in ConnectionStatus]
        assert set(expected) == set(actual)


class TestAttributeMapping:
    """Tests for AttributeMapping dataclass."""

    def test_basic_creation(self):
        """Test basic attribute mapping creation."""
        mapping = AttributeMapping(
            source_attribute="mail",
            target_attribute="email",
        )
        assert mapping.source_attribute == "mail"
        assert mapping.target_attribute == "email"
        assert mapping.transform is None
        assert mapping.required is False
        assert mapping.default_value is None

    def test_full_creation(self):
        """Test attribute mapping with all fields."""
        mapping = AttributeMapping(
            source_attribute="displayName",
            target_attribute="name",
            transform="lowercase",
            required=True,
            default_value="Unknown",
        )
        assert mapping.source_attribute == "displayName"
        assert mapping.target_attribute == "name"
        assert mapping.transform == "lowercase"
        assert mapping.required is True
        assert mapping.default_value == "Unknown"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        mapping = AttributeMapping(
            source_attribute="mail",
            target_attribute="email",
            required=True,
        )
        d = mapping.to_dict()
        assert d["source_attribute"] == "mail"
        assert d["target_attribute"] == "email"
        assert d["required"] is True

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "source_attribute": "mail",
            "target_attribute": "email",
            "transform": "lowercase",
            "required": True,
            "default_value": "default@example.com",
        }
        mapping = AttributeMapping.from_dict(data)
        assert mapping.source_attribute == "mail"
        assert mapping.target_attribute == "email"
        assert mapping.transform == "lowercase"
        assert mapping.required is True

    def test_from_dict_minimal(self):
        """Test creation from minimal dictionary."""
        data = {
            "source_attribute": "mail",
            "target_attribute": "email",
        }
        mapping = AttributeMapping.from_dict(data)
        assert mapping.source_attribute == "mail"
        assert mapping.required is False


class TestGroupMapping:
    """Tests for GroupMapping dataclass."""

    def test_basic_creation(self):
        """Test basic group mapping creation."""
        mapping = GroupMapping(
            source_group="CN=Admins,OU=Groups,DC=corp,DC=com",
            target_role="admin",
        )
        assert mapping.source_group == "CN=Admins,OU=Groups,DC=corp,DC=com"
        assert mapping.target_role == "admin"
        assert mapping.is_regex is False
        assert mapping.priority == 100

    def test_matches_exact(self):
        """Test exact group matching (case-insensitive)."""
        mapping = GroupMapping(source_group="Admins", target_role="admin")
        assert mapping.matches("Admins")
        assert mapping.matches("admins")
        assert mapping.matches("ADMINS")
        assert not mapping.matches("Admin")
        assert not mapping.matches("SuperAdmins")

    def test_matches_regex(self):
        """Test regex group matching."""
        mapping = GroupMapping(
            source_group=r"CN=.*-Admins,.*",
            target_role="admin",
            is_regex=True,
        )
        assert mapping.matches("CN=Security-Admins,OU=Groups,DC=corp,DC=com")
        assert mapping.matches("CN=App-Admins,OU=Groups,DC=corp,DC=com")
        assert not mapping.matches("CN=Users,OU=Groups,DC=corp,DC=com")

    def test_to_dict(self):
        """Test conversion to dictionary."""
        mapping = GroupMapping(
            source_group="Admins",
            target_role="admin",
            is_regex=True,
            priority=10,
        )
        d = mapping.to_dict()
        assert d["source_group"] == "Admins"
        assert d["target_role"] == "admin"
        assert d["is_regex"] is True
        assert d["priority"] == 10

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "source_group": "Developers",
            "target_role": "developer",
            "is_regex": False,
            "priority": 50,
        }
        mapping = GroupMapping.from_dict(data)
        assert mapping.source_group == "Developers"
        assert mapping.target_role == "developer"
        assert mapping.priority == 50


class TestIdentityProviderConfig:
    """Tests for IdentityProviderConfig dataclass."""

    def test_basic_creation(self):
        """Test basic IdP config creation."""
        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="Corporate LDAP",
        )
        assert config.idp_id == "idp-123"
        assert config.organization_id == "org-456"
        assert config.idp_type == IdPType.LDAP
        assert config.name == "Corporate LDAP"
        assert config.enabled is True
        assert config.priority == 100

    def test_creation_with_string_idp_type(self):
        """Test creation with string IdP type (auto-converted)."""
        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type="saml",  # type: ignore  # Testing string input
            name="SAML Provider",
        )
        assert config.idp_type == IdPType.SAML

    def test_creation_with_dict_mappings(self):
        """Test that dict mappings are converted to objects."""
        attr_mapping_dict = {
            "source_attribute": "mail",
            "target_attribute": "email",
            "required": True,
        }
        group_mapping_dict = {
            "source_group": "Admins",
            "target_role": "admin",
        }
        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="LDAP",
            attribute_mappings=[attr_mapping_dict],  # type: ignore
            group_mappings=[group_mapping_dict],  # type: ignore
        )
        assert isinstance(config.attribute_mappings[0], AttributeMapping)
        assert isinstance(config.group_mappings[0], GroupMapping)

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB item."""
        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.OIDC,
            name="OIDC Provider",
            enabled=True,
            email_domains=["company.com"],
            connection_settings={"client_id": "test"},
        )
        item = config.to_dynamodb_item()
        assert item["idp_id"] == "idp-123"
        assert item["idp_type"] == "oidc"
        assert item["email_domains"] == ["company.com"]

    def test_from_dynamodb_item(self):
        """Test creation from DynamoDB item."""
        item = {
            "idp_id": "idp-123",
            "organization_id": "org-456",
            "idp_type": "ldap",
            "name": "LDAP Server",
            "enabled": True,
            "priority": 10,
            "connection_settings": {"server": "ldap.corp.com"},
            "email_domains": ["corp.com"],
            "attribute_mappings": [
                {"source_attribute": "mail", "target_attribute": "email"}
            ],
            "group_mappings": [{"source_group": "Admins", "target_role": "admin"}],
        }
        config = IdentityProviderConfig.from_dynamodb_item(item)
        assert config.idp_id == "idp-123"
        assert config.idp_type == IdPType.LDAP
        assert config.priority == 10
        assert len(config.attribute_mappings) == 1
        assert len(config.group_mappings) == 1

    def test_get_default_attribute_mappings_ldap(self):
        """Test default attribute mappings for LDAP."""
        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.LDAP,
            name="LDAP",
        )
        defaults = config.get_default_attribute_mappings()
        assert len(defaults) > 0
        # Check for expected LDAP mappings
        source_attrs = [m.source_attribute for m in defaults]
        assert "mail" in source_attrs
        assert "displayName" in source_attrs

    def test_get_default_attribute_mappings_oidc(self):
        """Test default attribute mappings for OIDC."""
        config = IdentityProviderConfig(
            idp_id="idp-123",
            organization_id="org-456",
            idp_type=IdPType.OIDC,
            name="OIDC",
        )
        defaults = config.get_default_attribute_mappings()
        source_attrs = [m.source_attribute for m in defaults]
        assert "email" in source_attrs
        assert "name" in source_attrs


class TestAuthCredentials:
    """Tests for AuthCredentials dataclass."""

    def test_ldap_credentials(self):
        """Test LDAP-style credentials."""
        creds = AuthCredentials(username="john", password="secret")
        assert creds.username == "john"
        assert creds.password == "secret"
        assert creds.saml_response is None

    def test_saml_credentials(self):
        """Test SAML-style credentials."""
        creds = AuthCredentials(
            saml_response="base64encoded==",
            relay_state="https://app.example.com/callback",
        )
        assert creds.saml_response == "base64encoded=="
        assert creds.relay_state is not None

    def test_oidc_credentials(self):
        """Test OIDC-style credentials."""
        creds = AuthCredentials(
            code="auth_code_123",
            code_verifier="verifier_456",
            state="state_789",
            nonce="nonce_abc",
        )
        assert creds.code == "auth_code_123"
        assert creds.code_verifier == "verifier_456"


class TestAuthResult:
    """Tests for AuthResult dataclass."""

    def test_success_result(self):
        """Test successful auth result."""
        result = AuthResult(
            success=True,
            user_id="user-123",
            email="user@example.com",
            name="Test User",
            groups=["Admins", "Developers"],
            roles=["admin", "developer"],
        )
        assert result.success is True
        assert result.user_id == "user-123"
        assert result.error is None

    def test_failure_result(self):
        """Test failed auth result."""
        result = AuthResult(
            success=False,
            error="Invalid credentials",
            error_code="INVALID_CREDENTIALS",
        )
        assert result.success is False
        assert result.error == "Invalid credentials"
        assert result.user_id is None


class TestTokenResult:
    """Tests for TokenResult dataclass."""

    def test_full_token_result(self):
        """Test token result with all fields."""
        result = TokenResult(
            access_token="access.token.here",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh.token.here",
            id_token="id.token.here",
        )
        assert result.access_token == "access.token.here"
        assert result.token_type == "Bearer"
        assert result.expires_in == 3600


class TestAuraTokens:
    """Tests for AuraTokens dataclass."""

    def test_tokens_creation(self):
        """Test Aura tokens creation."""
        tokens = AuraTokens(
            access_token="access_token",
            refresh_token="refresh_token",
            token_type="Bearer",
            expires_in=3600,
        )
        assert tokens.access_token == "access_token"
        assert tokens.refresh_token == "refresh_token"
        assert tokens.token_type == "Bearer"


class TestAuthSession:
    """Tests for AuthSession dataclass."""

    def test_session_creation(self):
        """Test session creation."""
        session = AuthSession(
            session_id="sess-123",
            user_sub="user_sub_hash",
            idp_id="idp-456",
            organization_id="org-789",
            email="user@example.com",
            roles=["admin"],
        )
        assert session.session_id == "sess-123"
        assert session.user_sub == "user_sub_hash"

    def test_to_dynamodb_item(self):
        """Test session to DynamoDB item."""
        session = AuthSession(
            session_id="sess-123",
            user_sub="user_sub_hash",
            idp_id="idp-456",
            organization_id="org-789",
            email="user@example.com",
            roles=["admin", "developer"],
            ip_address="192.168.1.1",
        )
        item = session.to_dynamodb_item()
        assert item["session_id"] == "sess-123"
        assert item["roles"] == ["admin", "developer"]
        assert item["ip_address"] == "192.168.1.1"

    def test_from_dynamodb_item(self):
        """Test session from DynamoDB item."""
        item = {
            "session_id": "sess-123",
            "user_sub": "user_sub_hash",
            "idp_id": "idp-456",
            "organization_id": "org-789",
            "email": "user@example.com",
            "roles": ["viewer"],
        }
        session = AuthSession.from_dynamodb_item(item)
        assert session.session_id == "sess-123"
        assert session.roles == ["viewer"]


class TestAuditLogEntry:
    """Tests for AuditLogEntry dataclass."""

    def test_audit_entry_creation(self):
        """Test audit log entry creation."""
        entry = AuditLogEntry(
            audit_id="audit-123",
            idp_id="idp-456",
            organization_id="org-789",
            action_type=AuthAction.AUTH_SUCCESS.value,
            target_user_id="user-abc",
            success=True,
            ip_address="10.0.0.1",
        )
        assert entry.audit_id == "audit-123"
        assert entry.action_type == "auth_success"
        assert entry.success is True

    def test_to_dynamodb_item(self):
        """Test audit entry to DynamoDB item."""
        entry = AuditLogEntry(
            audit_id="audit-123",
            idp_id="idp-456",
            organization_id="org-789",
            action_type="auth_failure",
            error_message="Invalid password",
            ttl=1234567890,
        )
        item = entry.to_dynamodb_item()
        assert item["audit_id"] == "audit-123"
        assert item["error_message"] == "Invalid password"
        assert item["ttl"] == 1234567890

    def test_to_dynamodb_item_no_ttl(self):
        """Test audit entry without TTL."""
        entry = AuditLogEntry(
            audit_id="audit-123",
            idp_id="idp-456",
            organization_id="org-789",
            action_type="config_update",
        )
        item = entry.to_dynamodb_item()
        assert "ttl" not in item


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_healthy_result(self):
        """Test healthy status result."""
        result = HealthCheckResult(
            healthy=True,
            status=ConnectionStatus.CONNECTED,
            latency_ms=15.5,
            message="Connection successful",
        )
        assert result.healthy is True
        assert result.status == ConnectionStatus.CONNECTED
        assert result.latency_ms == 15.5

    def test_unhealthy_result(self):
        """Test unhealthy status result."""
        result = HealthCheckResult(
            healthy=False,
            status=ConnectionStatus.ERROR,
            message="Connection refused",
            details={"error": "ECONNREFUSED"},
        )
        assert result.healthy is False
        assert result.status == ConnectionStatus.ERROR


class TestValidationHelpers:
    """Tests for validation helper functions."""

    def test_validate_role_valid(self):
        """Test valid role validation."""
        for role in VALID_AURA_ROLES:
            assert validate_role(role) is True

    def test_validate_role_invalid(self):
        """Test invalid role validation."""
        assert validate_role("superadmin") is False
        assert validate_role("root") is False
        assert validate_role("") is False

    def test_validate_email_domain_valid(self):
        """Test valid email domain validation."""
        assert validate_email_domain("example.com") is True
        assert validate_email_domain("sub.example.com") is True
        assert validate_email_domain("company.co.uk") is True
        assert validate_email_domain("aenealabs.com") is True

    def test_validate_email_domain_invalid(self):
        """Test invalid email domain validation."""
        assert validate_email_domain("invalid") is False
        assert validate_email_domain(".com") is False
        assert validate_email_domain("example..com") is False
        assert validate_email_domain("-invalid.com") is False

    def test_extract_email_domain(self):
        """Test email domain extraction."""
        assert extract_email_domain("user@example.com") == "example.com"
        assert extract_email_domain("test@SUB.EXAMPLE.COM") == "sub.example.com"
        assert extract_email_domain("invalid") is None
        assert extract_email_domain("") is None


class TestUserInfo:
    """Tests for UserInfo dataclass."""

    def test_user_info_creation(self):
        """Test user info creation."""
        user = UserInfo(
            user_id="user-123",
            email="user@example.com",
            name="Test User",
            username="testuser",
            groups=["Admins"],
            attributes={"department": "Engineering"},
        )
        assert user.user_id == "user-123"
        assert user.email == "user@example.com"
        assert user.attributes["department"] == "Engineering"

    def test_user_info_minimal(self):
        """Test minimal user info."""
        user = UserInfo(user_id="user-123")
        assert user.user_id == "user-123"
        assert user.email is None
        assert user.groups == []


class TestTokenValidationResult:
    """Tests for TokenValidationResult dataclass."""

    def test_valid_token_result(self):
        """Test valid token result."""
        from datetime import datetime, timezone

        result = TokenValidationResult(
            valid=True,
            claims={"sub": "user-123", "email": "user@example.com"},
            expires_at=datetime.now(timezone.utc),
        )
        assert result.valid is True
        assert result.claims["sub"] == "user-123"
        assert result.error is None

    def test_invalid_token_result(self):
        """Test invalid token result."""
        result = TokenValidationResult(
            valid=False,
            error="Token has expired",
        )
        assert result.valid is False
        assert result.error == "Token has expired"
        assert result.claims == {}
