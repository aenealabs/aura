"""
Pytest fixtures for authorization tests.

Provides common fixtures for testing the ABAC authorization framework.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.services.authorization import (
    ABACAuthorizationService,
    AttributeContext,
    AuthorizationDecision,
    ContextAttributes,
    ResourceAttributes,
    SensitivityLevel,
    SubjectAttributes,
    reset_abac_service,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singleton instances before each test."""
    reset_abac_service()
    yield
    reset_abac_service()


@pytest.fixture
def sample_jwt_claims() -> dict[str, Any]:
    """Create sample JWT claims from Cognito."""
    return {
        "sub": "user-12345",
        "custom:tenant_id": "tenant-abc",
        "cognito:groups": ["security-engineer", "developer"],
        "email": "user@example.com",
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_xxxxx",
        "aud": "client-id-xxxxx",
    }


@pytest.fixture
def admin_jwt_claims() -> dict[str, Any]:
    """Create JWT claims for an admin user."""
    return {
        "sub": "admin-99999",
        "custom:tenant_id": "tenant-abc",
        "cognito:groups": ["admin", "platform-admin"],
        "email": "admin@example.com",
    }


@pytest.fixture
def platform_admin_jwt_claims() -> dict[str, Any]:
    """Create JWT claims for a platform admin (cross-tenant access)."""
    return {
        "sub": "platform-admin-001",
        "custom:tenant_id": "aura-platform",
        "cognito:groups": ["platform-admin"],
        "email": "platform-admin@aura.com",
    }


@pytest.fixture
def viewer_jwt_claims() -> dict[str, Any]:
    """Create JWT claims for a viewer user."""
    return {
        "sub": "viewer-55555",
        "custom:tenant_id": "tenant-abc",
        "cognito:groups": ["viewer"],
        "email": "viewer@example.com",
    }


@pytest.fixture
def extended_attributes() -> dict[str, Any]:
    """Create extended user attributes from DynamoDB."""
    return {
        "tenant_id": "tenant-abc",
        "department": "engineering",
        "clearance_level": "confidential",
        "risk_score": 0.15,
        "organization": "Acme Corp",
        "mfa_enabled": True,
    }


@pytest.fixture
def high_risk_attributes() -> dict[str, Any]:
    """Create extended attributes for a high-risk user."""
    return {
        "tenant_id": "tenant-abc",
        "department": "external",
        "clearance_level": "internal",
        "risk_score": 0.75,
        "organization": "Contractor Inc",
        "mfa_enabled": False,
    }


@pytest.fixture
def top_secret_attributes() -> dict[str, Any]:
    """Create extended attributes for a top secret clearance user."""
    return {
        "tenant_id": "tenant-gov",
        "department": "classified",
        "clearance_level": "top_secret",
        "risk_score": 0.05,
        "organization": "Government Agency",
        "mfa_enabled": True,
    }


@pytest.fixture
def sample_subject(sample_jwt_claims, extended_attributes) -> SubjectAttributes:
    """Create a sample subject from JWT claims."""
    return SubjectAttributes.from_jwt_claims(sample_jwt_claims, extended_attributes)


@pytest.fixture
def admin_subject(admin_jwt_claims, extended_attributes) -> SubjectAttributes:
    """Create an admin subject."""
    return SubjectAttributes.from_jwt_claims(admin_jwt_claims, extended_attributes)


@pytest.fixture
def sample_resource() -> ResourceAttributes:
    """Create a sample resource."""
    return ResourceAttributes(
        resource_type="vulnerability",
        resource_id="vuln-12345",
        tenant_id="tenant-abc",
        sensitivity=SensitivityLevel.CONFIDENTIAL,
        owner_id="user-12345",
        classification="security",
        environment="production",
    )


@pytest.fixture
def internal_resource() -> ResourceAttributes:
    """Create an internal sensitivity resource."""
    return ResourceAttributes(
        resource_type="document",
        resource_id="doc-67890",
        tenant_id="tenant-abc",
        sensitivity=SensitivityLevel.INTERNAL,
        classification="general",
        environment="development",
    )


@pytest.fixture
def top_secret_resource() -> ResourceAttributes:
    """Create a top secret resource."""
    return ResourceAttributes(
        resource_type="classified_document",
        resource_id="classified-001",
        tenant_id="tenant-gov",
        sensitivity=SensitivityLevel.TOP_LEVEL,
        classification="sap",
        environment="production",
    )


@pytest.fixture
def cross_tenant_resource() -> ResourceAttributes:
    """Create a resource from a different tenant."""
    return ResourceAttributes(
        resource_type="vulnerability",
        resource_id="vuln-other-001",
        tenant_id="tenant-xyz",
        sensitivity=SensitivityLevel.INTERNAL,
        environment="production",
    )


@pytest.fixture
def sample_context() -> ContextAttributes:
    """Create a sample context."""
    return ContextAttributes(
        request_time=datetime.now(timezone.utc),
        source_ip="10.0.1.50",
        mfa_verified=True,
        user_agent="Mozilla/5.0",
        request_id="req-abc-123",
    )


@pytest.fixture
def no_mfa_context() -> ContextAttributes:
    """Create a context without MFA verification."""
    return ContextAttributes(
        request_time=datetime.now(timezone.utc),
        source_ip="192.168.1.100",
        mfa_verified=False,
        user_agent="curl/7.68.0",
        request_id="req-xyz-789",
    )


@pytest.fixture
def sample_request_context() -> dict[str, Any]:
    """Create sample request context dict (as passed from middleware)."""
    return {
        "source_ip": "10.0.1.50",
        "request_time": datetime.now(timezone.utc).isoformat(),
        "user_agent": "Mozilla/5.0",
        "device_trust": "high",
        "mfa_verified": True,
        "request_id": "req-test-001",
    }


@pytest.fixture
def sample_attribute_context(
    sample_subject, sample_resource, sample_context
) -> AttributeContext:
    """Create a complete attribute context."""
    return AttributeContext(
        subject=sample_subject,
        resource=sample_resource,
        context=sample_context,
        action="view_vulnerabilities",
    )


@pytest.fixture
def mock_dynamodb_client() -> MagicMock:
    """Create a mock DynamoDB client."""
    client = MagicMock()
    client.get_item = MagicMock(return_value={"Item": {}})
    client.put_item = MagicMock(return_value={})
    client.query = MagicMock(return_value={"Items": []})
    return client


@pytest.fixture
def mock_bedrock_client() -> MagicMock:
    """Create a mock Bedrock client for OPA/VP calls."""
    client = MagicMock()
    client.invoke_model = MagicMock()
    return client


@pytest.fixture
def abac_service() -> ABACAuthorizationService:
    """Create an ABAC authorization service."""
    return ABACAuthorizationService()


@pytest.fixture
def abac_service_with_mocks(mock_dynamodb_client) -> ABACAuthorizationService:
    """Create an ABAC service with mocked DynamoDB."""
    return ABACAuthorizationService(
        dynamodb_client=mock_dynamodb_client,
    )


@pytest.fixture
def mock_fastapi_request() -> MagicMock:
    """Create a mock FastAPI request object."""
    request = MagicMock()
    request.state = MagicMock()
    request.state.jwt_claims = {
        "sub": "user-12345",
        "custom:tenant_id": "tenant-abc",
        "cognito:groups": ["security-engineer"],
        "email": "user@example.com",
    }
    request.client = MagicMock()
    request.client.host = "10.0.1.50"
    request.headers = {
        "user-agent": "Mozilla/5.0",
        "x-device-trust": "high",
        "x-mfa-verified": "true",
        "x-request-id": "req-test-001",
    }
    return request


@pytest.fixture
def mock_request_no_claims() -> MagicMock:
    """Create a mock request without JWT claims."""
    request = MagicMock()
    request.state = MagicMock()
    request.state.jwt_claims = None
    request.state.user = None
    request.client = MagicMock()
    request.client.host = "10.0.1.50"
    request.headers = {}
    return request


@pytest.fixture
def allowed_decision() -> AuthorizationDecision:
    """Create an allowed authorization decision."""
    return AuthorizationDecision(
        allowed=True,
        action="view_vulnerabilities",
        resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
        explanation="Access granted by ABAC policy",
        policy_version="1.0.0",
        matched_policies=["tenant_isolation", "role_check"],
    )


@pytest.fixture
def denied_decision() -> AuthorizationDecision:
    """Create a denied authorization decision."""
    return AuthorizationDecision(
        allowed=False,
        action="deploy_production",
        resource_arn="arn:aws:aura:::tenant/tenant-abc/deployments",
        explanation="User does not have required role for this action",
        policy_version="1.0.0",
        matched_policies=["role_check"],
    )
