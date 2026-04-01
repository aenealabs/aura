"""
Tests for ABAC contracts dataclasses and enums.

Tests the attribute dataclasses used for authorization decisions.
"""

from datetime import datetime, timezone

from src.services.authorization import (
    AttributeContext,
    AuthorizationDecision,
    ClearanceLevel,
    ContextAttributes,
    ResourceAttributes,
    SensitivityLevel,
    SubjectAttributes,
)
from src.services.authorization.abac_contracts import (
    ACTION_ROLE_MAPPING,
    ABACPolicy,
    AuthMethod,
    DeviceTrust,
)


class TestClearanceLevel:
    """Tests for ClearanceLevel enum."""

    def test_clearance_values(self):
        """Test all clearance level values exist."""
        assert ClearanceLevel.PUBLIC.value == "public"
        assert ClearanceLevel.INTERNAL.value == "internal"
        assert ClearanceLevel.CONFIDENTIAL.value == "confidential"
        assert ClearanceLevel.RESTRICTED.value == "restricted"
        assert ClearanceLevel.TOP_LEVEL.value == "top_level"

    def test_numeric_levels(self):
        """Test numeric level mapping."""
        assert ClearanceLevel.PUBLIC.numeric_level == 0
        assert ClearanceLevel.INTERNAL.numeric_level == 1
        assert ClearanceLevel.CONFIDENTIAL.numeric_level == 2
        assert ClearanceLevel.RESTRICTED.numeric_level == 3
        assert ClearanceLevel.TOP_LEVEL.numeric_level == 4

    def test_clearance_comparison_greater_than(self):
        """Test greater than comparison."""
        assert ClearanceLevel.TOP_LEVEL > ClearanceLevel.RESTRICTED
        assert ClearanceLevel.RESTRICTED > ClearanceLevel.CONFIDENTIAL
        assert ClearanceLevel.CONFIDENTIAL > ClearanceLevel.INTERNAL
        assert ClearanceLevel.INTERNAL > ClearanceLevel.PUBLIC
        assert not ClearanceLevel.PUBLIC > ClearanceLevel.INTERNAL

    def test_clearance_comparison_greater_equal(self):
        """Test greater than or equal comparison."""
        assert ClearanceLevel.TOP_LEVEL >= ClearanceLevel.TOP_LEVEL
        assert ClearanceLevel.TOP_LEVEL >= ClearanceLevel.RESTRICTED
        assert ClearanceLevel.INTERNAL >= ClearanceLevel.PUBLIC
        assert not ClearanceLevel.PUBLIC >= ClearanceLevel.INTERNAL

    def test_clearance_comparison_less_than(self):
        """Test less than comparison."""
        assert ClearanceLevel.PUBLIC < ClearanceLevel.INTERNAL
        assert ClearanceLevel.INTERNAL < ClearanceLevel.CONFIDENTIAL
        assert not ClearanceLevel.TOP_LEVEL < ClearanceLevel.RESTRICTED

    def test_clearance_comparison_less_equal(self):
        """Test less than or equal comparison."""
        assert ClearanceLevel.PUBLIC <= ClearanceLevel.PUBLIC
        assert ClearanceLevel.PUBLIC <= ClearanceLevel.INTERNAL
        assert not ClearanceLevel.TOP_LEVEL <= ClearanceLevel.RESTRICTED


class TestSensitivityLevel:
    """Tests for SensitivityLevel enum."""

    def test_sensitivity_values(self):
        """Test all sensitivity level values exist."""
        assert SensitivityLevel.PUBLIC.value == "public"
        assert SensitivityLevel.INTERNAL.value == "internal"
        assert SensitivityLevel.CONFIDENTIAL.value == "confidential"
        assert SensitivityLevel.RESTRICTED.value == "restricted"
        assert SensitivityLevel.TOP_LEVEL.value == "top_level"

    def test_numeric_levels(self):
        """Test numeric level mapping for sensitivity."""
        assert SensitivityLevel.PUBLIC.numeric_level == 0
        assert SensitivityLevel.TOP_LEVEL.numeric_level == 4


class TestDeviceTrust:
    """Tests for DeviceTrust enum."""

    def test_device_trust_values(self):
        """Test all device trust values."""
        assert DeviceTrust.UNKNOWN.value == "unknown"
        assert DeviceTrust.LOW.value == "low"
        assert DeviceTrust.MEDIUM.value == "medium"
        assert DeviceTrust.HIGH.value == "high"
        assert DeviceTrust.MANAGED.value == "managed"


class TestAuthMethod:
    """Tests for AuthMethod enum."""

    def test_auth_method_values(self):
        """Test all auth method values."""
        assert AuthMethod.BASIC.value == "basic"
        assert AuthMethod.MFA.value == "mfa"
        assert AuthMethod.SSO.value == "sso"
        assert AuthMethod.API_KEY.value == "api_key"
        assert AuthMethod.SERVICE_ACCOUNT.value == "service_account"


class TestSubjectAttributes:
    """Tests for SubjectAttributes dataclass."""

    def test_create_subject(self):
        """Test creating a subject with all attributes."""
        subject = SubjectAttributes(
            user_id="user-123",
            tenant_id="tenant-abc",
            roles=["developer", "viewer"],
            department="engineering",
            clearance_level=ClearanceLevel.CONFIDENTIAL,
            risk_score=0.25,
            organization="Acme Corp",
            email="user@acme.com",
            groups=["dev-team"],
            mfa_enabled=True,
        )
        assert subject.user_id == "user-123"
        assert subject.tenant_id == "tenant-abc"
        assert "developer" in subject.roles
        assert subject.clearance_level == ClearanceLevel.CONFIDENTIAL
        assert subject.mfa_enabled is True

    def test_subject_defaults(self):
        """Test subject default values."""
        subject = SubjectAttributes(
            user_id="user-456",
            tenant_id="tenant-xyz",
        )
        assert subject.roles == []
        assert subject.department is None
        assert subject.clearance_level == ClearanceLevel.INTERNAL
        assert subject.risk_score == 0.0
        assert subject.mfa_enabled is False

    def test_subject_to_dict(self, sample_subject):
        """Test converting subject to dictionary."""
        result = sample_subject.to_dict()
        assert "user_id" in result
        assert "tenant_id" in result
        assert "clearance_level" in result
        assert result["clearance_level"] == sample_subject.clearance_level.value

    def test_subject_from_jwt_claims(self, sample_jwt_claims):
        """Test creating subject from JWT claims."""
        subject = SubjectAttributes.from_jwt_claims(sample_jwt_claims)
        assert subject.user_id == "user-12345"
        assert subject.tenant_id == "tenant-abc"
        assert "security-engineer" in subject.roles

    def test_subject_from_jwt_with_extended(
        self, sample_jwt_claims, extended_attributes
    ):
        """Test creating subject with extended attributes."""
        subject = SubjectAttributes.from_jwt_claims(
            sample_jwt_claims, extended_attributes
        )
        assert subject.department == "engineering"
        assert subject.clearance_level == ClearanceLevel.CONFIDENTIAL
        assert subject.risk_score == 0.15
        assert subject.mfa_enabled is True

    def test_subject_invalid_clearance_fallback(self, sample_jwt_claims):
        """Test fallback for invalid clearance level."""
        extended = {"clearance_level": "invalid_level"}
        subject = SubjectAttributes.from_jwt_claims(sample_jwt_claims, extended)
        assert subject.clearance_level == ClearanceLevel.INTERNAL


class TestResourceAttributes:
    """Tests for ResourceAttributes dataclass."""

    def test_create_resource(self):
        """Test creating a resource with all attributes."""
        resource = ResourceAttributes(
            resource_type="vulnerability",
            resource_id="vuln-123",
            tenant_id="tenant-abc",
            sensitivity=SensitivityLevel.CONFIDENTIAL,
            owner_id="user-456",
            classification="security",
            tags={"env": "prod", "team": "security"},
            environment="production",
        )
        assert resource.resource_type == "vulnerability"
        assert resource.sensitivity == SensitivityLevel.CONFIDENTIAL
        assert resource.tags["env"] == "prod"

    def test_resource_defaults(self):
        """Test resource default values."""
        resource = ResourceAttributes(
            resource_type="document",
            resource_id="doc-123",
            tenant_id="tenant-xyz",
        )
        assert resource.sensitivity == SensitivityLevel.INTERNAL
        assert resource.owner_id == ""
        assert resource.environment == "production"

    def test_resource_to_dict(self, sample_resource):
        """Test converting resource to dictionary."""
        result = sample_resource.to_dict()
        assert "resource_type" in result
        assert "sensitivity" in result
        assert result["sensitivity"] == sample_resource.sensitivity.value

    def test_resource_from_arn(self):
        """Test creating resource from ARN."""
        arn = "arn:aws:aura:us-east-1:123456789:tenant/tenant-abc"
        resource = ResourceAttributes.from_arn(arn)
        assert resource.resource_type == "tenant"
        assert resource.resource_id == "tenant-abc"

    def test_resource_from_arn_with_tags(self):
        """Test creating resource from ARN with tags."""
        arn = "arn:aws:aura:us-east-1:123456789:vulnerability/vuln-001"
        tags = {
            "tenant_id": "tenant-abc",
            "sensitivity": "confidential",
            "owner_id": "user-123",
        }
        resource = ResourceAttributes.from_arn(arn, tags)
        assert resource.tenant_id == "tenant-abc"
        assert resource.sensitivity == SensitivityLevel.CONFIDENTIAL
        assert resource.owner_id == "user-123"

    def test_resource_from_arn_invalid_sensitivity(self):
        """Test fallback for invalid sensitivity in tags."""
        arn = "arn:aws:aura:::resource/test"
        tags = {"sensitivity": "invalid_level"}
        resource = ResourceAttributes.from_arn(arn, tags)
        assert resource.sensitivity == SensitivityLevel.INTERNAL

    def test_resource_from_short_arn(self):
        """Test resource from short/malformed ARN."""
        arn = "short:arn"
        resource = ResourceAttributes.from_arn(arn)
        assert resource.resource_type == "unknown"
        assert resource.resource_id == "short:arn"


class TestContextAttributes:
    """Tests for ContextAttributes dataclass."""

    def test_create_context(self):
        """Test creating a context with all attributes."""
        now = datetime.now(timezone.utc)
        context = ContextAttributes(
            request_time=now,
            source_ip="10.0.1.50",
            device_trust=DeviceTrust.HIGH,
            session_risk=0.1,
            mfa_verified=True,
            auth_method=AuthMethod.MFA,
            user_agent="Mozilla/5.0",
            request_id="req-123",
        )
        assert context.source_ip == "10.0.1.50"
        assert context.mfa_verified is True
        assert context.device_trust == DeviceTrust.HIGH

    def test_context_defaults(self):
        """Test context default values."""
        context = ContextAttributes()
        assert context.source_ip == ""
        assert context.device_trust == DeviceTrust.UNKNOWN
        assert context.mfa_verified is False
        assert context.auth_method == AuthMethod.BASIC

    def test_context_to_dict(self, sample_context):
        """Test converting context to dictionary."""
        result = sample_context.to_dict()
        assert "request_time" in result
        assert "source_ip" in result
        assert "mfa_verified" in result

    def test_context_from_request(self, sample_request_context):
        """Test creating context from request dict."""
        context = ContextAttributes.from_request(sample_request_context)
        assert context.source_ip == "10.0.1.50"
        assert context.mfa_verified is True
        assert context.device_trust == DeviceTrust.HIGH

    def test_context_from_request_invalid_values(self):
        """Test context from request with invalid values."""
        request_ctx = {
            "device_trust": "invalid_trust",
            "auth_method": "invalid_method",
        }
        context = ContextAttributes.from_request(request_ctx)
        assert context.device_trust == DeviceTrust.UNKNOWN
        assert context.auth_method == AuthMethod.BASIC

    def test_context_from_request_with_datetime_string(self):
        """Test context from request with datetime as string."""
        now = datetime.now(timezone.utc)
        request_ctx = {"request_time": now.isoformat()}
        context = ContextAttributes.from_request(request_ctx)
        assert isinstance(context.request_time, datetime)

    def test_context_from_request_invalid_datetime(self):
        """Test context from request with invalid datetime."""
        request_ctx = {"request_time": "invalid-time"}
        context = ContextAttributes.from_request(request_ctx)
        assert isinstance(context.request_time, datetime)

    def test_is_business_hours_during_hours(self):
        """Test business hours check during business hours."""
        # Create time at 10 AM UTC
        business_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        context = ContextAttributes(request_time=business_time)
        assert context.is_business_hours() is True

    def test_is_business_hours_outside_hours(self):
        """Test business hours check outside business hours."""
        # Create time at 3 AM UTC
        late_night = datetime(2026, 1, 15, 3, 0, 0, tzinfo=timezone.utc)
        context = ContextAttributes(request_time=late_night)
        assert context.is_business_hours() is False

    def test_is_business_hours_with_offset(self):
        """Test business hours check with timezone offset."""
        # Create time at 10 PM UTC, but +5 hours would be 3 AM
        late_utc = datetime(2026, 1, 15, 22, 0, 0, tzinfo=timezone.utc)
        context = ContextAttributes(request_time=late_utc)
        # With +5 offset, 22 + 5 = 27 % 24 = 3, which is outside business hours
        assert context.is_business_hours(timezone_offset=5) is False


class TestAttributeContext:
    """Tests for AttributeContext dataclass."""

    def test_create_attribute_context(
        self, sample_subject, sample_resource, sample_context
    ):
        """Test creating a complete attribute context."""
        attr_ctx = AttributeContext(
            subject=sample_subject,
            resource=sample_resource,
            context=sample_context,
            action="view_vulnerabilities",
        )
        assert attr_ctx.action == "view_vulnerabilities"
        assert attr_ctx.subject.user_id == sample_subject.user_id

    def test_attribute_context_to_dict(self, sample_attribute_context):
        """Test converting attribute context to dictionary."""
        result = sample_attribute_context.to_dict()
        assert "action" in result
        assert "subject" in result
        assert "resource" in result
        assert "context" in result
        assert isinstance(result["subject"], dict)


class TestAuthorizationDecision:
    """Tests for AuthorizationDecision dataclass."""

    def test_create_allowed_decision(self):
        """Test creating an allowed decision."""
        decision = AuthorizationDecision(
            allowed=True,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc",
            explanation="Access granted",
            policy_version="1.0",
            matched_policies=["tenant_check"],
        )
        assert decision.allowed is True
        assert decision.action == "view_vulnerabilities"

    def test_create_denied_decision(self):
        """Test creating a denied decision."""
        decision = AuthorizationDecision(
            allowed=False,
            action="deploy_production",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/deploy",
            explanation="Insufficient role",
        )
        assert decision.allowed is False

    def test_decision_defaults(self):
        """Test decision default values."""
        decision = AuthorizationDecision(allowed=True)
        assert decision.action == ""
        assert decision.resource_arn == ""
        assert decision.explanation is None
        assert decision.matched_policies == []
        assert decision.evaluation_time_ms == 0.0

    def test_decision_to_dict(self, allowed_decision):
        """Test converting decision to dictionary."""
        result = allowed_decision.to_dict()
        assert "allowed" in result
        assert "action" in result
        assert "evaluated_at" in result
        assert result["allowed"] is True


class TestABACPolicy:
    """Tests for ABACPolicy dataclass."""

    def test_create_policy(self):
        """Test creating an ABAC policy."""
        policy = ABACPolicy(
            policy_id="pol-001",
            name="TenantIsolation",
            description="Enforces tenant isolation",
            effect="permit",
            actions=["view_vulnerabilities", "create_patch"],
            conditions={"subject.tenant_id": {"equals": "resource.tenant_id"}},
            priority=100,
            enabled=True,
        )
        assert policy.policy_id == "pol-001"
        assert policy.effect == "permit"
        assert "view_vulnerabilities" in policy.actions

    def test_policy_to_dict(self):
        """Test converting policy to dictionary."""
        policy = ABACPolicy(
            policy_id="pol-002",
            name="AdminOnly",
            description="Admin only access",
            effect="permit",
            actions=["manage_users"],
            conditions={"subject.roles": {"contains": "admin"}},
        )
        result = policy.to_dict()
        assert result["policy_id"] == "pol-002"
        assert result["enabled"] is True


class TestActionRoleMapping:
    """Tests for ACTION_ROLE_MAPPING constant."""

    def test_mapping_exists(self):
        """Test that action role mapping exists."""
        assert "view_vulnerabilities" in ACTION_ROLE_MAPPING
        assert "approve_patch" in ACTION_ROLE_MAPPING
        assert "manage_users" in ACTION_ROLE_MAPPING

    def test_view_vulnerabilities_roles(self):
        """Test roles allowed for view_vulnerabilities."""
        roles = ACTION_ROLE_MAPPING["view_vulnerabilities"]
        assert "security-engineer" in roles
        assert "admin" in roles
        assert "viewer" in roles

    def test_approve_patch_roles(self):
        """Test roles allowed for approve_patch."""
        roles = ACTION_ROLE_MAPPING["approve_patch"]
        assert "security-engineer" in roles
        assert "admin" in roles
        assert "viewer" not in roles

    def test_manage_users_roles(self):
        """Test roles allowed for manage_users (admin only)."""
        roles = ACTION_ROLE_MAPPING["manage_users"]
        assert "admin" in roles
        assert len(roles) == 1

    def test_access_all_tenants_roles(self):
        """Test roles for cross-tenant access."""
        roles = ACTION_ROLE_MAPPING["access_all_tenants"]
        assert "platform-admin" in roles
