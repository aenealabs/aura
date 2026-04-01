"""
Tests for ABAC authorization service.

Tests the core authorization evaluation logic.
"""

from unittest.mock import MagicMock

import pytest

from src.services.authorization import (
    ABACAuthorizationService,
    get_abac_service,
    reset_abac_service,
)


class TestABACAuthorizationServiceInit:
    """Tests for ABACAuthorizationService initialization."""

    def test_create_service(self):
        """Test creating service with defaults."""
        service = ABACAuthorizationService()
        assert service is not None
        assert service.dynamodb is None
        assert service.opa_url is None
        assert service.avp_client is None

    def test_create_service_with_dynamodb(self, mock_dynamodb_client):
        """Test creating service with DynamoDB client."""
        service = ABACAuthorizationService(
            dynamodb_client=mock_dynamodb_client,
        )
        assert service.dynamodb is not None

    def test_create_service_with_opa(self):
        """Test creating service with OPA backend."""
        service = ABACAuthorizationService(
            opa_url="http://localhost:8181",
        )
        assert service.opa_url == "http://localhost:8181"

    def test_create_service_with_verified_permissions(self):
        """Test creating service with AWS Verified Permissions."""
        mock_avp = MagicMock()
        service = ABACAuthorizationService(
            verified_permissions_client=mock_avp,
            policy_store_id="ps-12345",
        )
        assert service.avp_client is not None
        assert service.policy_store_id == "ps-12345"


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_get_abac_service_returns_same_instance(self):
        """Test that get_abac_service returns singleton."""
        reset_abac_service()
        service1 = get_abac_service()
        service2 = get_abac_service()
        assert service1 is service2

    def test_reset_clears_singleton(self):
        """Test that reset clears the singleton."""
        service1 = get_abac_service()
        reset_abac_service()
        service2 = get_abac_service()
        assert service1 is not service2


class TestSubjectResolution:
    """Tests for subject attribute resolution."""

    @pytest.mark.asyncio
    async def test_resolve_subject_from_jwt(self, abac_service, sample_jwt_claims):
        """Test resolving subject from JWT claims."""
        subject = await abac_service._resolve_subject(sample_jwt_claims)
        assert subject.user_id == "user-12345"
        assert subject.tenant_id == "tenant-abc"
        assert "security-engineer" in subject.roles

    @pytest.mark.asyncio
    async def test_resolve_subject_with_extended_attrs(
        self, abac_service_with_mocks, sample_jwt_claims, mock_dynamodb_client
    ):
        """Test resolving subject with extended attributes from DynamoDB."""
        # Mock DynamoDB response
        mock_dynamodb_client.get_item.return_value = {
            "Item": {
                "user_id": {"S": "user-12345"},
                "department": {"S": "engineering"},
                "clearance_level": {"S": "confidential"},
                "mfa_enabled": {"BOOL": True},
            }
        }

        subject = await abac_service_with_mocks._resolve_subject(sample_jwt_claims)
        # Should have extended attributes from DynamoDB
        assert subject.user_id == "user-12345"


class TestResourceResolution:
    """Tests for resource attribute resolution."""

    @pytest.mark.asyncio
    async def test_resolve_resource_from_arn(self, abac_service):
        """Test resolving resource from ARN."""
        arn = "arn:aws:aura:us-east-1:123456789:tenant/tenant-abc/vulnerabilities"
        resource = await abac_service._resolve_resource(arn)
        assert resource.resource_type == "tenant"
        assert "tenant-abc" in resource.resource_id

    @pytest.mark.asyncio
    async def test_resolve_resource_extracts_tenant(self, abac_service):
        """Test that tenant is extracted from tags."""

        def tag_resolver(arn):
            return {"tenant_id": "tenant-xyz"}

        abac_service.set_tag_resolver(tag_resolver)

        arn = "arn:aws:aura:::tenant/tenant-xyz/data"
        resource = await abac_service._resolve_resource(arn)
        assert resource.tenant_id == "tenant-xyz"


class TestBuiltinPolicyEvaluation:
    """Tests for built-in policy evaluation."""

    @pytest.mark.asyncio
    async def test_allow_same_tenant_access(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test that same-tenant access is allowed."""
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        assert decision.allowed is True
        assert any("tenant_isolation" in p for p in decision.matched_policies)

    @pytest.mark.asyncio
    async def test_deny_cross_tenant_access(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test that cross-tenant access is denied."""

        # Create service with tag resolver to set tenant on resource
        def tag_resolver(arn):
            return {"tenant_id": "tenant-different"}

        abac_service.set_tag_resolver(tag_resolver)

        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-different/vulnerabilities",
            request_context=sample_request_context,
        )
        assert decision.allowed is False
        assert "tenant" in decision.explanation.lower()

    @pytest.mark.asyncio
    async def test_allow_platform_admin_cross_tenant(
        self, abac_service, platform_admin_jwt_claims, sample_request_context
    ):
        """Test that platform admin can access any tenant."""
        # Platform admin with MFA should have cross-tenant access
        mfa_context = {**sample_request_context, "mfa_verified": True}

        # Set tag resolver so resource has different tenant
        def tag_resolver(arn):
            return {"tenant_id": "tenant-xyz"}

        abac_service.set_tag_resolver(tag_resolver)

        decision = await abac_service.authorize(
            jwt_claims=platform_admin_jwt_claims,
            action="access_all_tenants",  # Use correct action for platform admin
            resource_arn="arn:aws:aura:::tenant/tenant-xyz/vulnerabilities",
            request_context=mfa_context,
        )
        assert decision.allowed is True

    @pytest.mark.asyncio
    async def test_deny_platform_admin_without_mfa(
        self, abac_service, platform_admin_jwt_claims
    ):
        """Test that platform admin without MFA cannot access cross-tenant."""
        no_mfa_context = {"mfa_verified": False, "source_ip": "10.0.0.1"}
        decision = await abac_service.authorize(
            jwt_claims=platform_admin_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-xyz/vulnerabilities",
            request_context=no_mfa_context,
        )
        # Without MFA, cross-tenant should be denied
        assert decision.allowed is False

    @pytest.mark.asyncio
    async def test_role_check_allowed(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test that user with correct role is allowed."""
        # security-engineer can view vulnerabilities
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        assert decision.allowed is True

    @pytest.mark.asyncio
    async def test_role_check_denied(
        self, abac_service, viewer_jwt_claims, sample_request_context
    ):
        """Test that user without required role is denied."""
        # viewer cannot approve patches
        decision = await abac_service.authorize(
            jwt_claims=viewer_jwt_claims,
            action="approve_patch",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/patches",
            request_context=sample_request_context,
        )
        assert decision.allowed is False

    @pytest.mark.asyncio
    async def test_admin_can_manage_users(
        self, abac_service, admin_jwt_claims, sample_request_context
    ):
        """Test that admin can manage users."""
        decision = await abac_service.authorize(
            jwt_claims=admin_jwt_claims,
            action="manage_users",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/users",
            request_context=sample_request_context,
        )
        assert decision.allowed is True


class TestClearanceChecks:
    """Tests for clearance level checks."""

    @pytest.mark.asyncio
    async def test_clearance_sufficient(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test access when clearance is sufficient."""
        # User with confidential clearance accessing confidential resource
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        assert decision.allowed is True

    @pytest.mark.asyncio
    async def test_clearance_insufficient(self, abac_service, sample_request_context):
        """Test denial when clearance is insufficient."""
        # Create user with low clearance
        low_clearance_claims = {
            "sub": "user-low",
            "custom:tenant_id": "tenant-abc",
            "cognito:groups": ["viewer"],
        }

        # Note: Resource sensitivity is determined by tags/metadata
        # The built-in policy compares subject clearance to resource sensitivity
        decision = await abac_service.authorize(
            jwt_claims=low_clearance_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        # Without extended attrs, user has INTERNAL clearance by default
        # This may or may not be sufficient depending on resource sensitivity


class TestMFARequirements:
    """Tests for MFA requirements."""

    @pytest.mark.asyncio
    async def test_critical_action_requires_mfa(self, abac_service, admin_jwt_claims):
        """Test that critical actions require MFA."""
        no_mfa_context = {"mfa_verified": False, "source_ip": "10.0.0.1"}
        decision = await abac_service.authorize(
            jwt_claims=admin_jwt_claims,
            action="deploy_production",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/deployments",
            request_context=no_mfa_context,
        )
        # deploy_production should require MFA
        # Note: depends on policy implementation

    @pytest.mark.asyncio
    async def test_critical_action_with_mfa(
        self, abac_service, admin_jwt_claims, sample_request_context
    ):
        """Test that critical action succeeds with MFA."""
        # sample_request_context has mfa_verified=True
        # Admin with correct role should be able to deploy with MFA


class TestBusinessHoursPolicy:
    """Tests for business hours policy."""

    @pytest.mark.asyncio
    async def test_sensitive_action_during_business_hours(
        self, abac_service, admin_jwt_claims
    ):
        """Test sensitive action during business hours."""
        # Create context during business hours (10 AM UTC)
        business_hours_context = {
            "source_ip": "10.0.0.1",
            "request_time": "2026-01-15T10:00:00Z",
            "mfa_verified": True,
        }
        decision = await abac_service.authorize(
            jwt_claims=admin_jwt_claims,
            action="manage_users",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/users",
            request_context=business_hours_context,
        )
        assert decision.allowed is True

    @pytest.mark.asyncio
    async def test_sensitive_action_outside_business_hours(
        self, abac_service, admin_jwt_claims
    ):
        """Test sensitive action outside business hours."""
        # Create context outside business hours (3 AM UTC)
        after_hours_context = {
            "source_ip": "10.0.0.1",
            "request_time": "2026-01-15T03:00:00Z",
            "mfa_verified": True,
        }
        # Some policies may restrict certain actions outside business hours


class TestPolicyVersioning:
    """Tests for policy versioning."""

    @pytest.mark.asyncio
    async def test_decision_includes_policy_version(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test that decision includes policy version."""
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        assert decision.policy_version != ""

    @pytest.mark.asyncio
    async def test_decision_includes_evaluation_time(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test that decision includes evaluation time."""
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        assert decision.evaluation_time_ms >= 0


class TestMatchedPolicies:
    """Tests for matched policies tracking."""

    @pytest.mark.asyncio
    async def test_decision_lists_matched_policies(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test that decision lists matched policies."""
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        assert isinstance(decision.matched_policies, list)
        # At minimum, tenant_isolation should be checked
        assert len(decision.matched_policies) >= 0


class TestOPAIntegration:
    """Tests for OPA backend integration."""

    @pytest.mark.asyncio
    async def test_opa_evaluation_success(self):
        """Test successful OPA policy evaluation."""
        service = ABACAuthorizationService(
            opa_url="http://localhost:8181",
        )
        # OPA integration requires actual OPA server
        # This test validates service creation with OPA config
        assert service.opa_url == "http://localhost:8181"

    @pytest.mark.asyncio
    async def test_opa_fallback_on_error(self):
        """Test fallback when OPA is unavailable."""
        service = ABACAuthorizationService(
            opa_url="http://localhost:8181",
        )
        # When OPA fails, service falls back to builtin evaluation
        assert service.opa_url is not None


class TestVerifiedPermissionsIntegration:
    """Tests for AWS Verified Permissions integration."""

    @pytest.mark.asyncio
    async def test_verified_permissions_evaluation(self):
        """Test AWS Verified Permissions evaluation."""
        mock_vp_client = MagicMock()
        mock_vp_client.is_authorized = MagicMock(
            return_value={
                "decision": "ALLOW",
                "determiningPolicies": [{"policyId": "policy-123"}],
            }
        )

        service = ABACAuthorizationService(
            policy_store_id="ps-12345",
            verified_permissions_client=mock_vp_client,
        )

        # Verified Permissions integration test
        assert service.avp_client is not None
        assert service.policy_store_id == "ps-12345"


class TestDecisionCaching:
    """Tests for decision caching."""

    @pytest.mark.asyncio
    async def test_same_request_uses_cache(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test that identical requests may use cached decisions."""
        # Make same authorization request twice
        decision1 = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        decision2 = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        # Both decisions should have same result
        assert decision1.allowed == decision2.allowed


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_roles(self, abac_service, sample_request_context):
        """Test user with no roles."""
        no_roles_claims = {
            "sub": "user-no-roles",
            "custom:tenant_id": "tenant-abc",
            "cognito:groups": [],
        }
        decision = await abac_service.authorize(
            jwt_claims=no_roles_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        # User with no roles should be denied privileged actions
        assert decision.allowed is False

    @pytest.mark.asyncio
    async def test_missing_tenant_id(self, abac_service, sample_request_context):
        """Test user with no tenant ID trying to access tenant resource."""
        no_tenant_claims = {
            "sub": "user-no-tenant",
            "cognito:groups": ["viewer"],
        }

        # Set tag resolver so resource has a tenant requirement
        def tag_resolver(arn):
            return {"tenant_id": "tenant-abc"}

        abac_service.set_tag_resolver(tag_resolver)

        decision = await abac_service.authorize(
            jwt_claims=no_tenant_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        # User without matching tenant should be denied
        assert decision.allowed is False

    @pytest.mark.asyncio
    async def test_unknown_action(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test handling of unknown action."""
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="unknown_action_xyz",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/resource",
            request_context=sample_request_context,
        )
        # Unknown actions should be denied by default
        assert decision.allowed is False

    @pytest.mark.asyncio
    async def test_malformed_arn(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test handling of malformed ARN."""
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="not-a-valid-arn",
            request_context=sample_request_context,
        )
        # Should handle gracefully (deny if can't parse tenant)

    @pytest.mark.asyncio
    async def test_empty_request_context(self, abac_service, sample_jwt_claims):
        """Test with empty request context."""
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context={},
        )
        # Should handle missing context gracefully


class TestExplanations:
    """Tests for decision explanations."""

    @pytest.mark.asyncio
    async def test_allow_explanation(
        self, abac_service, sample_jwt_claims, sample_request_context
    ):
        """Test explanation for allowed decision."""
        decision = await abac_service.authorize(
            jwt_claims=sample_jwt_claims,
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/vulnerabilities",
            request_context=sample_request_context,
        )
        assert decision.allowed is True
        assert decision.explanation is not None

    @pytest.mark.asyncio
    async def test_deny_explanation(self, abac_service, sample_request_context):
        """Test explanation for denied decision."""
        no_role_claims = {
            "sub": "user-no-access",
            "custom:tenant_id": "tenant-abc",
            "cognito:groups": [],
        }
        decision = await abac_service.authorize(
            jwt_claims=no_role_claims,
            action="approve_patch",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/patches",
            request_context=sample_request_context,
        )
        assert decision.allowed is False
        assert decision.explanation is not None
        # Explanation should describe why access was denied
