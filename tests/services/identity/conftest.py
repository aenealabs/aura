"""
Project Aura - Identity Services Test Fixtures

Shared fixtures for identity provider tests.
"""

from unittest.mock import MagicMock

import pytest

from src.services.identity.models import (
    AttributeMapping,
    AuthCredentials,
    AuthResult,
    GroupMapping,
    IdentityProviderConfig,
    IdPType,
)


@pytest.fixture
def ldap_config():
    """Create a standard LDAP configuration for testing."""
    return IdentityProviderConfig(
        idp_id="idp-ldap-test",
        organization_id="org-test-123",
        idp_type=IdPType.LDAP,
        name="Test LDAP Server",
        enabled=True,
        priority=10,
        connection_settings={
            "server": "ldap.test.com",
            "port": 636,
            "use_ssl": True,
            "use_tls": False,
            "base_dn": "DC=test,DC=com",
            "user_search_base": "OU=Users,DC=test,DC=com",
            "bind_dn": "CN=Service,OU=Services,DC=test,DC=com",
        },
        credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:ldap-test",
        attribute_mappings=[
            AttributeMapping("mail", "email", required=True),
            AttributeMapping("displayName", "name"),
            AttributeMapping("sAMAccountName", "username", transform="lowercase"),
        ],
        group_mappings=[
            GroupMapping("CN=Admins,DC=test,DC=com", "admin", priority=10),
            GroupMapping("CN=Developers,DC=test,DC=com", "developer", priority=20),
            GroupMapping("CN=Users,DC=test,DC=com", "viewer", priority=100),
        ],
        email_domains=["test.com"],
    )


@pytest.fixture
def saml_config():
    """Create a standard SAML configuration for testing."""
    return IdentityProviderConfig(
        idp_id="idp-saml-test",
        organization_id="org-test-123",
        idp_type=IdPType.SAML,
        name="Test SAML Provider",
        enabled=True,
        priority=20,
        connection_settings={
            "idp_entity_id": "https://idp.test.com/saml",
            "idp_sso_url": "https://idp.test.com/saml/sso",
            "idp_slo_url": "https://idp.test.com/saml/slo",
            "sp_entity_id": "https://aura.test.com/saml/sp",
            "acs_url": "https://aura.test.com/saml/acs",
            "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        },
        certificate_settings={
            "idp_certificate": "-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
        },
        attribute_mappings=[
            AttributeMapping(
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                "email",
                required=True,
            ),
            AttributeMapping(
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
                "name",
            ),
        ],
        group_mappings=[
            GroupMapping("admins", "admin"),
            GroupMapping("developers", "developer"),
        ],
        email_domains=["contractor.com"],
    )


@pytest.fixture
def oidc_config():
    """Create a standard OIDC configuration for testing."""
    return IdentityProviderConfig(
        idp_id="idp-oidc-test",
        organization_id="org-test-123",
        idp_type=IdPType.OIDC,
        name="Test OIDC Provider",
        enabled=True,
        priority=30,
        connection_settings={
            "issuer": "https://oidc.test.com",
            "authorization_endpoint": "https://oidc.test.com/authorize",
            "token_endpoint": "https://oidc.test.com/token",
            "userinfo_endpoint": "https://oidc.test.com/userinfo",
            "jwks_uri": "https://oidc.test.com/.well-known/jwks.json",
            "client_id": "test-client-id",
            "scopes": ["openid", "email", "profile"],
            "response_type": "code",
            "use_pkce": True,
        },
        credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:oidc-test",
        attribute_mappings=[
            AttributeMapping("email", "email", required=True),
            AttributeMapping("name", "name"),
            AttributeMapping("preferred_username", "username"),
        ],
        group_mappings=[
            GroupMapping("admin-group", "admin"),
            GroupMapping("dev-group", "developer"),
        ],
        email_domains=["partner.com"],
    )


@pytest.fixture
def cognito_config():
    """Create a standard Cognito configuration for testing."""
    return IdentityProviderConfig(
        idp_id="idp-cognito-test",
        organization_id="org-test-123",
        idp_type=IdPType.COGNITO,
        name="Test Cognito Pool",
        enabled=True,
        priority=100,  # Fallback
        connection_settings={
            "region": "us-east-1",
            "user_pool_id": "us-east-1_ABC123",
            "client_id": "test-client-id",
        },
        attribute_mappings=[
            AttributeMapping("email", "email", required=True),
            AttributeMapping("name", "name"),
            AttributeMapping("cognito:username", "username"),
        ],
        group_mappings=[
            GroupMapping("Administrators", "admin"),
            GroupMapping("Developers", "developer"),
        ],
    )


@pytest.fixture
def pingid_config():
    """Create a standard PingID configuration for testing."""
    return IdentityProviderConfig(
        idp_id="idp-pingid-test",
        organization_id="org-test-123",
        idp_type=IdPType.PINGID,
        name="Test PingFederate",
        enabled=True,
        priority=15,
        connection_settings={
            "issuer": "https://pingfederate.test.com",
            "authorization_endpoint": "https://pingfederate.test.com/as/authorization.oauth2",
            "token_endpoint": "https://pingfederate.test.com/as/token.oauth2",
            "userinfo_endpoint": "https://pingfederate.test.com/idp/userinfo.openid",
            "jwks_uri": "https://pingfederate.test.com/pf/JWKS",
            "client_id": "ping-client-id",
            "adapter_id": "HTMLFormAdapter",
            "acr_values": "urn:acr:form",
        },
        credentials_secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:ping-test",
        attribute_mappings=[
            AttributeMapping("email", "email", required=True),
            AttributeMapping("name", "name"),
        ],
        email_domains=["enterprise.com"],
    )


@pytest.fixture
def successful_auth_result():
    """Create a successful auth result for testing."""
    return AuthResult(
        success=True,
        user_id="user-123-abc",
        email="test.user@example.com",
        name="Test User",
        groups=["Admins", "Developers"],
        roles=["admin", "developer"],
        attributes={
            "email": "test.user@example.com",
            "name": "Test User",
            "username": "testuser",
        },
        provider_metadata={
            "idp_type": "ldap",
            "idp_id": "idp-test",
        },
    )


@pytest.fixture
def failed_auth_result():
    """Create a failed auth result for testing."""
    return AuthResult(
        success=False,
        error="Invalid credentials",
        error_code="INVALID_CREDENTIALS",
    )


@pytest.fixture
def mock_dynamodb_resource():
    """Create a mock DynamoDB resource."""
    mock_resource = MagicMock()
    mock_table = MagicMock()
    mock_resource.Table.return_value = mock_table
    return mock_resource, mock_table


@pytest.fixture
def mock_secrets_manager():
    """Create a mock Secrets Manager client."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"client_secret": "test-secret", "bind_password": "test-password"}'
    }
    return mock_client


@pytest.fixture
def ldap_credentials():
    """Create LDAP-style credentials."""
    return AuthCredentials(
        username="john.doe",
        password="correctpassword123",
    )


@pytest.fixture
def oidc_credentials():
    """Create OIDC-style credentials (authorization code)."""
    return AuthCredentials(
        code="authorization_code_123",
        code_verifier="code_verifier_abc",
        state="state_xyz",
        nonce="nonce_123",
    )


@pytest.fixture
def saml_credentials():
    """Create SAML-style credentials (assertion response)."""
    return AuthCredentials(
        saml_response="base64encodedsamlresponse==",
        relay_state="https://app.test.com/callback",
    )
