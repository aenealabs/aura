"""
Tests for ABAC middleware and decorators.

Tests the FastAPI decorators for ABAC-protected endpoints.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.authorization import (
    AuthorizationDecision,
    ClearanceLevel,
)
from src.services.authorization.abac_middleware import (
    ABACAccessDenied,
    ABACMiddleware,
    require_abac,
    require_admin,
    require_clearance,
    require_tenant_access,
)


class TestABACAccessDeniedException:
    """Tests for ABACAccessDenied exception."""

    def test_exception_creation(self):
        """Test creating ABACAccessDenied exception."""
        exc = ABACAccessDenied(
            action="view_vulnerabilities",
            resource_arn="arn:aws:aura:::tenant/tenant-abc",
            reason="Insufficient clearance",
        )
        assert exc.action == "view_vulnerabilities"
        assert exc.resource_arn == "arn:aws:aura:::tenant/tenant-abc"
        assert exc.reason == "Insufficient clearance"
        assert "Insufficient clearance" in str(exc)

    def test_exception_with_decision(self, denied_decision):
        """Test exception with decision object."""
        exc = ABACAccessDenied(
            action="deploy_production",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/deploy",
            reason="Role check failed",
            decision=denied_decision,
        )
        assert exc.decision is not None
        assert exc.decision.allowed is False

    def test_exception_to_dict(self):
        """Test converting exception to dictionary."""
        exc = ABACAccessDenied(
            action="approve_patch",
            resource_arn="arn:aws:aura:::tenant/tenant-abc/patches",
            reason="MFA required",
        )
        result = exc.to_dict()
        assert result["error"] == "Access denied"
        assert result["action"] == "approve_patch"
        assert result["reason"] == "MFA required"


class TestRequireABACDecorator:
    """Tests for require_abac decorator."""

    @pytest.mark.asyncio
    async def test_decorator_allows_authorized_request(self, mock_fastapi_request):
        """Test that decorator allows authorized requests."""

        # Create a mock endpoint function
        @require_abac(
            action="view_vulnerabilities",
            resource_resolver=lambda r, tenant_id: f"arn:aws:aura:::tenant/{tenant_id}",
        )
        async def get_vulnerabilities(request, tenant_id: str):
            return {"vulnerabilities": []}

        # Mock the ABAC service to return allowed
        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(
                    allowed=True,
                    action="view_vulnerabilities",
                    explanation="Access granted",
                )
            )
            mock_get_service.return_value = mock_service

            result = await get_vulnerabilities(
                mock_fastapi_request, tenant_id="tenant-abc"
            )
            assert result == {"vulnerabilities": []}

    @pytest.mark.asyncio
    async def test_decorator_denies_unauthorized_request(self, mock_fastapi_request):
        """Test that decorator denies unauthorized requests."""

        @require_abac(
            action="approve_patch",
            resource_resolver=lambda r, patch_id: f"arn:aws:aura:::patch/{patch_id}",
        )
        async def approve_patch(request, patch_id: str):
            return {"status": "approved"}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(
                    allowed=False,
                    action="approve_patch",
                    explanation="User does not have approver role",
                )
            )
            mock_get_service.return_value = mock_service

            with pytest.raises(ABACAccessDenied) as exc_info:
                await approve_patch(mock_fastapi_request, patch_id="patch-123")

            assert exc_info.value.action == "approve_patch"

    @pytest.mark.asyncio
    async def test_decorator_extracts_request_from_args(self, mock_fastapi_request):
        """Test that decorator can find request in positional args."""

        @require_abac(action="view_data")
        async def endpoint(request, data_id: str):
            return {"data": data_id}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            result = await endpoint(mock_fastapi_request, "data-123")
            assert result["data"] == "data-123"

    @pytest.mark.asyncio
    async def test_decorator_extracts_request_from_kwargs(self, mock_fastapi_request):
        """Test that decorator can find request in keyword args."""

        @require_abac(action="view_data")
        async def endpoint(data_id: str, request=None):
            return {"data": data_id}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            result = await endpoint("data-123", request=mock_fastapi_request)
            assert result["data"] == "data-123"

    @pytest.mark.asyncio
    async def test_decorator_no_request_object(self):
        """Test decorator behavior when no request object found."""

        @require_abac(action="view_data")
        async def endpoint(data_id: str):
            return {"data": data_id}

        with pytest.raises(ABACAccessDenied) as exc_info:
            await endpoint("data-123")

        assert "No request object" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_decorator_skip_if_no_claims(self, mock_request_no_claims):
        """Test decorator with skip_if_no_claims=True."""

        @require_abac(action="public_data", skip_if_no_claims=True)
        async def endpoint(request):
            return {"public": True}

        # Should succeed without claims when skip_if_no_claims is True
        result = await endpoint(mock_request_no_claims)
        assert result["public"] is True

    @pytest.mark.asyncio
    async def test_decorator_no_claims_without_skip(self, mock_request_no_claims):
        """Test decorator fails when no claims and skip_if_no_claims=False."""

        @require_abac(action="protected_data", skip_if_no_claims=False)
        async def endpoint(request):
            return {"protected": True}

        with pytest.raises(ABACAccessDenied) as exc_info:
            await endpoint(mock_request_no_claims)

        assert "No authentication credentials" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_decorator_stores_decision_in_state(self, mock_fastapi_request):
        """Test that decorator stores decision in request state."""

        @require_abac(action="view_data")
        async def endpoint(request):
            return {"data": "test"}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            expected_decision = AuthorizationDecision(allowed=True)
            mock_service.authorize = AsyncMock(return_value=expected_decision)
            mock_get_service.return_value = mock_service

            await endpoint(mock_fastapi_request)

            # Decision should be stored in request state
            assert mock_fastapi_request.state.abac_decision is not None

    @pytest.mark.asyncio
    async def test_decorator_default_resource_arn(self, mock_fastapi_request):
        """Test decorator uses default ARN when no resolver provided."""

        @require_abac(action="custom_action")
        async def my_endpoint(request):
            return {"result": "ok"}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            await my_endpoint(mock_fastapi_request)

            # Check that authorize was called with default ARN pattern
            call_args = mock_service.authorize.call_args
            assert "my_endpoint" in call_args.kwargs["resource_arn"]

    @pytest.mark.asyncio
    async def test_decorator_resource_resolver_error(self, mock_fastapi_request):
        """Test decorator handles resource resolver errors gracefully."""

        def bad_resolver(r, tenant_id):
            raise ValueError("Resolver failed")

        @require_abac(action="view_data", resource_resolver=bad_resolver)
        async def endpoint(request, tenant_id: str):
            return {"data": tenant_id}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            # Should not raise, but use fallback ARN
            result = await endpoint(mock_fastapi_request, tenant_id="tenant-abc")
            assert result["data"] == "tenant-abc"


class TestRequireTenantAccessDecorator:
    """Tests for require_tenant_access decorator."""

    @pytest.mark.asyncio
    async def test_tenant_access_decorator(self, mock_fastapi_request):
        """Test require_tenant_access decorator."""

        @require_tenant_access()
        async def get_tenant_data(request, tenant_id: str):
            return {"tenant": tenant_id}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            result = await get_tenant_data(mock_fastapi_request, tenant_id="tenant-abc")
            assert result["tenant"] == "tenant-abc"

            # Verify the action used
            call_args = mock_service.authorize.call_args
            assert call_args.kwargs["action"] == "access_tenant_resource"

    @pytest.mark.asyncio
    async def test_tenant_access_custom_param(self, mock_fastapi_request):
        """Test require_tenant_access with custom parameter name."""

        @require_tenant_access(tenant_param="org_id")
        async def get_org_data(request, org_id: str):
            return {"org": org_id}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            result = await get_org_data(mock_fastapi_request, org_id="org-xyz")
            assert result["org"] == "org-xyz"


class TestRequireAdminDecorator:
    """Tests for require_admin decorator."""

    @pytest.mark.asyncio
    async def test_admin_decorator_allows_admin(self, mock_fastapi_request):
        """Test require_admin allows admin users."""
        # Update mock to have admin role
        mock_fastapi_request.state.jwt_claims["cognito:groups"] = ["admin"]

        @require_admin()
        async def admin_endpoint(request):
            return {"admin": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            result = await admin_endpoint(mock_fastapi_request)
            assert result["admin"] is True

            # Verify the action used
            call_args = mock_service.authorize.call_args
            assert call_args.kwargs["action"] == "manage_users"

    @pytest.mark.asyncio
    async def test_admin_decorator_denies_non_admin(self, mock_fastapi_request):
        """Test require_admin denies non-admin users."""

        @require_admin()
        async def admin_endpoint(request):
            return {"admin": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(
                    allowed=False, explanation="User is not admin"
                )
            )
            mock_get_service.return_value = mock_service

            with pytest.raises(ABACAccessDenied):
                await admin_endpoint(mock_fastapi_request)


class TestRequireClearanceDecorator:
    """Tests for require_clearance decorator."""

    @pytest.mark.asyncio
    async def test_clearance_decorator_sufficient(self, mock_fastapi_request):
        """Test require_clearance allows sufficient clearance."""

        @require_clearance("confidential")
        async def classified_endpoint(request):
            return {"classified": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            # Mock _resolve_subject to return user with sufficient clearance
            from src.services.authorization.abac_contracts import SubjectAttributes

            mock_subject = SubjectAttributes(
                user_id="user-123",
                tenant_id="tenant-abc",
                clearance_level=ClearanceLevel.CONFIDENTIAL,
            )
            mock_service._resolve_subject = AsyncMock(return_value=mock_subject)
            mock_get_service.return_value = mock_service

            result = await classified_endpoint(mock_fastapi_request)
            assert result["classified"] is True

    @pytest.mark.asyncio
    async def test_clearance_decorator_insufficient(self, mock_fastapi_request):
        """Test require_clearance denies insufficient clearance."""

        @require_clearance("top_level")
        async def top_level_endpoint(request):
            return {"top_level": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            # Mock _resolve_subject to return user with insufficient clearance
            from src.services.authorization.abac_contracts import SubjectAttributes

            mock_subject = SubjectAttributes(
                user_id="user-123",
                tenant_id="tenant-abc",
                clearance_level=ClearanceLevel.INTERNAL,
            )
            mock_service._resolve_subject = AsyncMock(return_value=mock_subject)
            mock_get_service.return_value = mock_service

            with pytest.raises(ABACAccessDenied) as exc_info:
                await top_level_endpoint(mock_fastapi_request)

            assert "clearance level" in exc_info.value.reason.lower()

    @pytest.mark.asyncio
    async def test_clearance_decorator_invalid_level(self, mock_fastapi_request):
        """Test require_clearance handles invalid level gracefully."""

        @require_clearance("invalid_level")
        async def endpoint(request):
            return {"data": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            from src.services.authorization.abac_contracts import SubjectAttributes

            mock_subject = SubjectAttributes(
                user_id="user-123",
                tenant_id="tenant-abc",
                clearance_level=ClearanceLevel.INTERNAL,
            )
            mock_service._resolve_subject = AsyncMock(return_value=mock_subject)
            mock_get_service.return_value = mock_service

            # Invalid level should default to INTERNAL
            result = await endpoint(mock_fastapi_request)
            assert result["data"] is True

    @pytest.mark.asyncio
    async def test_clearance_decorator_no_request(self):
        """Test require_clearance fails without request object."""

        @require_clearance("confidential")
        async def endpoint(data: str):
            return {"data": data}

        with pytest.raises(ABACAccessDenied) as exc_info:
            await endpoint("test")

        assert "No request object" in exc_info.value.reason

    @pytest.mark.asyncio
    async def test_clearance_decorator_no_claims(self, mock_request_no_claims):
        """Test require_clearance fails without JWT claims."""

        @require_clearance("confidential")
        async def endpoint(request):
            return {"data": True}

        with pytest.raises(ABACAccessDenied) as exc_info:
            await endpoint(mock_request_no_claims)

        assert "No authentication credentials" in exc_info.value.reason


class TestABACMiddleware:
    """Tests for ABACMiddleware class."""

    @pytest.mark.asyncio
    async def test_middleware_passes_non_http(self):
        """Test middleware passes through non-HTTP requests."""
        app = AsyncMock()
        middleware = ABACMiddleware(app, protected_paths=["/api/"])

        scope = {"type": "websocket", "path": "/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_middleware_checks_protected_paths(self):
        """Test middleware checks protected paths."""
        app = AsyncMock()
        middleware = ABACMiddleware(
            app, protected_paths=["/api/v1/"], exclude_paths=["/api/v1/health"]
        )

        scope = {"type": "http", "path": "/api/v1/vulnerabilities"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_skips_excluded_paths(self):
        """Test middleware skips excluded paths."""
        app = AsyncMock()
        middleware = ABACMiddleware(
            app, protected_paths=["/api/"], exclude_paths=["/api/health"]
        )

        scope = {"type": "http", "path": "/api/health"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_skips_unprotected_paths(self):
        """Test middleware skips unprotected paths."""
        app = AsyncMock()
        middleware = ABACMiddleware(app, protected_paths=["/api/"])

        scope = {"type": "http", "path": "/static/image.png"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once()

    def test_middleware_initialization(self):
        """Test middleware initialization with options."""
        app = MagicMock()
        middleware = ABACMiddleware(
            app,
            protected_paths=["/api/v1/", "/api/v2/"],
            exclude_paths=["/api/v1/health", "/api/v1/auth"],
            default_action="api_access",
        )

        assert middleware.protected_paths == ["/api/v1/", "/api/v2/"]
        assert "/api/v1/health" in middleware.exclude_paths
        assert middleware.default_action == "api_access"


class TestRequestContextExtraction:
    """Tests for request context extraction in decorators."""

    @pytest.mark.asyncio
    async def test_extracts_source_ip(self, mock_fastapi_request):
        """Test that source IP is extracted from request."""

        @require_abac(action="view_data")
        async def endpoint(request):
            return {"ip": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            await endpoint(mock_fastapi_request)

            call_args = mock_service.authorize.call_args
            assert call_args.kwargs["request_context"]["source_ip"] == "10.0.1.50"

    @pytest.mark.asyncio
    async def test_extracts_user_agent(self, mock_fastapi_request):
        """Test that user agent is extracted from request."""

        @require_abac(action="view_data")
        async def endpoint(request):
            return {"agent": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            await endpoint(mock_fastapi_request)

            call_args = mock_service.authorize.call_args
            assert "Mozilla" in call_args.kwargs["request_context"]["user_agent"]

    @pytest.mark.asyncio
    async def test_extracts_mfa_verified(self, mock_fastapi_request):
        """Test that MFA status is extracted from request headers."""

        @require_abac(action="view_data")
        async def endpoint(request):
            return {"mfa": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            await endpoint(mock_fastapi_request)

            call_args = mock_service.authorize.call_args
            assert call_args.kwargs["request_context"]["mfa_verified"] is True

    @pytest.mark.asyncio
    async def test_extracts_device_trust(self, mock_fastapi_request):
        """Test that device trust is extracted from request headers."""

        @require_abac(action="view_data")
        async def endpoint(request):
            return {"trust": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            await endpoint(mock_fastapi_request)

            call_args = mock_service.authorize.call_args
            assert call_args.kwargs["request_context"]["device_trust"] == "high"


class TestUserObjectConversion:
    """Tests for user object to dict conversion."""

    @pytest.mark.asyncio
    async def test_converts_user_object_to_dict(self):
        """Test that user objects are converted to dicts."""

        # Create a mock user object (not a dict)
        class MockUser:
            def __init__(self):
                self.sub = "user-123"
                self.tenant_id = "tenant-abc"
                self.groups = ["developer"]

        mock_request = MagicMock()
        mock_request.state = MagicMock()
        mock_request.state.jwt_claims = None
        mock_request.state.user = MockUser()
        mock_request.client = MagicMock()
        mock_request.client.host = "10.0.0.1"
        mock_request.headers = {}

        @require_abac(action="view_data")
        async def endpoint(request):
            return {"data": True}

        with patch(
            "src.services.authorization.abac_service.get_abac_service"
        ) as mock_get_service:
            mock_service = AsyncMock()
            mock_service.authorize = AsyncMock(
                return_value=AuthorizationDecision(allowed=True)
            )
            mock_get_service.return_value = mock_service

            await endpoint(mock_request)

            # Verify the claims were converted to dict
            call_args = mock_service.authorize.call_args
            jwt_claims = call_args.kwargs["jwt_claims"]
            assert isinstance(jwt_claims, dict)
