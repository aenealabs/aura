"""
Authentication and authorization tests for the HITL approval API.

Covers:
- Regression guard: every state-changing route on the approvals router must
  depend on authentication and the approver role check.
- Unauthenticated requests are rejected with 401.
- Users without an approver role are rejected with 403.
- Reviewer identity is taken from the token, and a body ``reviewer_email``
  that disagrees with the token is rejected.
- Requesters cannot approve their own requests.
- Explainability evidence is returned by the detail endpoint.
- Tenant isolation: approvals are scoped to the caller's organization;
  another tenant's approval is indistinguishable from a missing one (404).

Uses lazy imports inside fixtures to keep module state fresh in forked
test processes (same pattern as tests/test_approval_endpoints.py).
"""

import platform
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


# ============================================================================
# Helpers / Fixtures
# ============================================================================


def _dependency_calls(dependant) -> set:
    """Collect every dependency callable reachable from a route dependant."""
    calls = set()
    stack = list(dependant.dependencies)
    while stack:
        dep = stack.pop()
        if dep.call is not None:
            calls.add(dep.call)
        stack.extend(dep.dependencies)
    return calls


_UNSET = object()


def _make_user(
    email="reviewer@example.com",
    sub="user-reviewer-001",
    groups=None,
    organization_id=_UNSET,
):
    from src.api.auth import User

    return User(
        sub=sub,
        email=email,
        name="Test User",
        groups=["security-engineer"] if groups is None else groups,
        organization_id="org-123" if organization_id is _UNSET else organization_id,
    )


@pytest.fixture(autouse=True)
def _no_auth_bypass(monkeypatch):
    """Ensure the dev auth bypass can never mask a missing-auth failure."""
    monkeypatch.delenv("AURA_AUTH_BYPASS", raising=False)


@pytest.fixture(autouse=True)
def _no_rate_limit():
    """Disable rate limiting; these tests issue several critical requests."""
    from src.services.api_rate_limiter import (
        disable_rate_limiting,
        enable_rate_limiting,
        reset_rate_limiter,
    )

    reset_rate_limiter()
    disable_rate_limiting()
    yield
    enable_rate_limiting()


@pytest.fixture
def sample_approval():
    """Pending approval request raised by an agent."""
    from src.services.hitl_approval_service import (
        ApprovalRequest,
        ApprovalStatus,
        PatchSeverity,
    )

    return ApprovalRequest(
        approval_id="apr-123",
        patch_id="patch-456",
        vulnerability_id="CVE-2024-1234",
        status=ApprovalStatus.PENDING,
        severity=PatchSeverity.HIGH,
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata={
            "title": "Fix SQLi",
            "requested_by": "security-agent",
            "organization_id": "org-123",
        },
    )


@pytest.fixture
def mock_service(sample_approval):
    from src.services.hitl_approval_service import HITLApprovalService

    service = MagicMock(spec=HITLApprovalService)
    service.get_all_requests = MagicMock(return_value=[])
    service.get_request = MagicMock(return_value=sample_approval)
    service.approve_request = MagicMock(return_value=True)
    service.reject_request = MagicMock(return_value=True)
    service.cancel_request = MagicMock(return_value=True)
    service.get_statistics = MagicMock(
        return_value={
            "total": 0,
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "expired": 0,
            "by_severity": {},
        }
    )
    return service


@pytest.fixture
def make_client(mock_service):
    """Build a TestClient; pass a User to authenticate, or None for anonymous."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.approval_endpoints import router
    from src.api.auth import get_current_user
    from src.api.dependencies import get_hitl_service

    apps = []

    def _factory(user=None, service=None):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_hitl_service] = lambda: (
            service if service is not None else mock_service
        )
        if user is not None:
            app.dependency_overrides[get_current_user] = lambda: user
        apps.append(app)
        return TestClient(app)

    yield _factory
    for app in apps:
        app.dependency_overrides.clear()


# ============================================================================
# Route Enumeration Regression Guard
# ============================================================================


class TestRouteAuthCoverage:
    """Fail if any approvals route is reachable without authentication."""

    def test_router_has_state_changing_routes(self):
        """Sanity check so the guard below cannot pass vacuously."""
        from fastapi.routing import APIRoute

        from src.api.approval_endpoints import router

        mutating = [
            r
            for r in router.routes
            if isinstance(r, APIRoute) and r.methods & STATE_CHANGING_METHODS
        ]
        assert len(mutating) >= 3

    def test_every_state_changing_route_requires_approver_role(self):
        from fastapi.routing import APIRoute

        from src.api.approval_endpoints import require_approver, router
        from src.api.auth import get_current_user

        missing = []
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            if not route.methods & STATE_CHANGING_METHODS:
                continue
            calls = _dependency_calls(route.dependant)
            if get_current_user not in calls or require_approver not in calls:
                missing.append(f"{sorted(route.methods)} {route.path}")

        assert not missing, f"State-changing routes without auth/role: {missing}"

    def test_every_route_requires_authentication(self):
        from fastapi.routing import APIRoute

        from src.api.approval_endpoints import router
        from src.api.auth import get_current_user

        missing = [
            f"{sorted(r.methods)} {r.path}"
            for r in router.routes
            if isinstance(r, APIRoute)
            and get_current_user not in _dependency_calls(r.dependant)
        ]
        assert not missing, f"Routes without authentication: {missing}"


# ============================================================================
# Unauthenticated / Wrong Role
# ============================================================================


class TestUnauthenticated:
    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("get", "/api/v1/approvals", None),
            ("get", "/api/v1/approvals/stats", None),
            ("get", "/api/v1/approvals/apr-123", None),
            ("post", "/api/v1/approvals/apr-123/approve", {}),
            ("post", "/api/v1/approvals/apr-123/reject", {"reason": "no"}),
            ("post", "/api/v1/approvals/apr-123/cancel", None),
        ],
    )
    def test_requires_token(self, make_client, mock_service, method, path, body):
        client = make_client(user=None)
        kwargs = {"json": body} if body is not None else {}

        response = getattr(client, method)(path, **kwargs)

        assert response.status_code == 401
        mock_service.approve_request.assert_not_called()
        mock_service.reject_request.assert_not_called()
        mock_service.cancel_request.assert_not_called()


class TestWrongRole:
    @pytest.mark.parametrize("groups", [[], ["viewer"], ["developer", "devops"]])
    @pytest.mark.parametrize(
        "path,body",
        [
            ("/api/v1/approvals/apr-123/approve", {}),
            ("/api/v1/approvals/apr-123/reject", {"reason": "no"}),
            ("/api/v1/approvals/apr-123/cancel", None),
        ],
    )
    def test_non_approver_forbidden(
        self, make_client, mock_service, groups, path, body
    ):
        client = make_client(user=_make_user(groups=groups))
        kwargs = {"json": body} if body is not None else {}

        response = client.post(path, **kwargs)

        assert response.status_code == 403
        mock_service.approve_request.assert_not_called()
        mock_service.reject_request.assert_not_called()
        mock_service.cancel_request.assert_not_called()

    def test_viewer_can_read(self, make_client):
        client = make_client(user=_make_user(groups=["viewer"]))

        assert client.get("/api/v1/approvals").status_code == 200
        assert client.get("/api/v1/approvals/apr-123").status_code == 200

    @pytest.mark.parametrize("groups", [["security-engineer"], ["admin"]])
    def test_approver_roles_allowed(self, make_client, groups):
        client = make_client(user=_make_user(groups=groups))

        response = client.post("/api/v1/approvals/apr-123/approve", json={})

        assert response.status_code == 200


# ============================================================================
# Reviewer Identity
# ============================================================================


class TestReviewerIdentity:
    def test_identity_recorded_from_token(self, make_client, mock_service):
        client = make_client(user=_make_user(email="alice@example.com"))

        response = client.post(
            "/api/v1/approvals/apr-123/approve", json={"comment": "LGTM"}
        )

        assert response.status_code == 200
        assert response.json()["reviewed_by"] == "alice@example.com"
        kwargs = mock_service.approve_request.call_args.kwargs
        assert kwargs["reviewer_id"] == "alice@example.com"

    def test_spoofed_reviewer_email_rejected_on_approve(
        self, make_client, mock_service
    ):
        client = make_client(user=_make_user(email="alice@example.com"))

        response = client.post(
            "/api/v1/approvals/apr-123/approve",
            json={"reviewer_email": "ciso@example.com"},
        )

        assert response.status_code == 403
        mock_service.approve_request.assert_not_called()

    def test_spoofed_reviewer_email_rejected_on_reject(self, make_client, mock_service):
        client = make_client(user=_make_user(email="alice@example.com"))

        response = client.post(
            "/api/v1/approvals/apr-123/reject",
            json={"reviewer_email": "ciso@example.com", "reason": "bad"},
        )

        assert response.status_code == 403
        mock_service.reject_request.assert_not_called()

    def test_matching_reviewer_email_accepted_case_insensitive(
        self, make_client, mock_service
    ):
        client = make_client(user=_make_user(email="alice@example.com"))

        response = client.post(
            "/api/v1/approvals/apr-123/reject",
            json={"reviewer_email": "Alice@Example.com", "reason": "bad"},
        )

        assert response.status_code == 200
        kwargs = mock_service.reject_request.call_args.kwargs
        assert kwargs["reviewer_id"] == "alice@example.com"

    def test_falls_back_to_sub_when_token_has_no_email(self, make_client, mock_service):
        client = make_client(user=_make_user(email=None, sub="cognito-sub-42"))

        response = client.post("/api/v1/approvals/apr-123/approve", json={})

        assert response.status_code == 200
        kwargs = mock_service.approve_request.call_args.kwargs
        assert kwargs["reviewer_id"] == "cognito-sub-42"

    def test_notification_and_triggers_use_token_identity(
        self, make_client, mock_service, monkeypatch
    ):
        from src.api import approval_endpoints

        notifier = MagicMock()
        triggers = MagicMock()
        monkeypatch.setattr(
            approval_endpoints, "get_notification_service", lambda: notifier
        )
        monkeypatch.setattr(approval_endpoints, "get_triggers", lambda: triggers)
        client = make_client(user=_make_user(email="alice@example.com"))

        response = client.post("/api/v1/approvals/apr-123/approve", json={})

        assert response.status_code == 200
        assert notifier.send_decision_notification.call_args.kwargs["reviewer"] == (
            "alice@example.com"
        )
        assert triggers.record_approval_decision.call_args.kwargs["reviewer"] == (
            "alice@example.com"
        )


# ============================================================================
# Separation of Duties
# ============================================================================


class TestSelfApproval:
    @pytest.mark.parametrize(
        "path,body",
        [
            ("/api/v1/approvals/apr-123/approve", {}),
            ("/api/v1/approvals/apr-123/reject", {"reason": "no"}),
        ],
    )
    def test_requester_cannot_decide_own_request(
        self, make_client, mock_service, sample_approval, path, body
    ):
        sample_approval.metadata["requested_by"] = "Alice@Example.com"
        client = make_client(user=_make_user(email="alice@example.com"))

        response = client.post(path, json=body)

        assert response.status_code == 403
        mock_service.approve_request.assert_not_called()
        mock_service.reject_request.assert_not_called()

    def test_agent_requested_approval_allowed(self, make_client, mock_service):
        client = make_client(user=_make_user(email="alice@example.com"))

        response = client.post("/api/v1/approvals/apr-123/approve", json={})

        assert response.status_code == 200
        mock_service.approve_request.assert_called_once()


# ============================================================================
# Explainability Evidence (real service in MOCK mode)
# ============================================================================


class TestExplainabilityInDetail:
    def test_detail_returns_explainability(self, make_client):
        from src.services.hitl_approval_service import (
            HITLApprovalService,
            HITLMode,
            PatchSeverity,
        )

        service = HITLApprovalService(mode=HITLMode.MOCK)
        created = service.create_approval_request(
            patch_id="patch-1",
            vulnerability_id="CVE-2026-0001",
            severity=PatchSeverity.HIGH,
            metadata={"organization_id": "org-123"},
            explainability={
                "record_id": "exp-001",
                "summary": "Parameterized the query to remove SQL injection",
                "confidence": 0.87,
                "reasoning_chain": [
                    {"step_number": 1, "description": "Found taint", "confidence": 0.9}
                ],
            },
        )
        client = make_client(user=_make_user(groups=["viewer"]), service=service)

        response = client.get(f"/api/v1/approvals/{created.approval_id}")

        assert response.status_code == 200
        explain = response.json()["explainability"]
        assert explain["record_id"] == "exp-001"
        assert explain["confidence"] == pytest.approx(0.87)
        assert explain["summary"].startswith("Parameterized")
        assert explain["reasoning_chain"][0]["description"] == "Found taint"

    def test_detail_without_explainability_is_null(self, make_client):
        client = make_client(user=_make_user(groups=["viewer"]))

        response = client.get("/api/v1/approvals/apr-123")

        assert response.status_code == 200
        assert response.json()["explainability"] is None


# ============================================================================
# Tenant Isolation
# ============================================================================


def _approval_dict(approval_id, status="PENDING", organization_id=None):
    """Approval in the dict shape returned by get_all_requests."""
    metadata = {"title": approval_id}
    if organization_id is not None:
        metadata["organization_id"] = organization_id
    return {
        "approval_id": approval_id,
        "patch_id": f"patch-{approval_id}",
        "vulnerability_id": "CVE-2024-0001",
        "status": status,
        "severity": "HIGH",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
    }


TENANT_ROUTES = [
    ("get", "/api/v1/approvals/apr-123", None),
    ("post", "/api/v1/approvals/apr-123/approve", {}),
    ("post", "/api/v1/approvals/apr-123/reject", {"reason": "no"}),
    ("post", "/api/v1/approvals/apr-123/cancel", None),
]


def _call(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    return getattr(client, method)(path, **kwargs)


def _assert_no_decision(service):
    service.approve_request.assert_not_called()
    service.reject_request.assert_not_called()
    service.cancel_request.assert_not_called()


@pytest.fixture
def isolated_service(monkeypatch):
    """Real HITL service in MOCK mode with no seeded demo data."""
    from src.services.hitl_approval_service import HITLApprovalService, HITLMode

    monkeypatch.setenv("AURA_SEED_MOCK_APPROVALS", "false")
    return HITLApprovalService(mode=HITLMode.MOCK)


class TestTenantIsolationSingleApproval:
    @pytest.mark.parametrize("method,path,body", TENANT_ROUTES)
    @pytest.mark.parametrize(
        "groups,organization_id",
        [
            (["security-engineer"], "org-999"),
            (["admin"], "org-999"),
            # Platform admins are not granted cross-tenant approval access.
            (["platform_admin", "admin"], "org-999"),
            (["security-engineer"], None),
            (["platform_admin", "admin"], None),
        ],
        ids=["engineer", "org-admin", "platform-admin", "no-org", "no-org-platform"],
    )
    def test_other_tenant_approval_is_not_found(
        self, make_client, mock_service, method, path, body, groups, organization_id
    ):
        client = make_client(
            user=_make_user(groups=groups, organization_id=organization_id)
        )

        response = _call(client, method, path, body)

        assert response.status_code == 404
        assert response.json()["detail"] == "Approval apr-123 not found"
        _assert_no_decision(mock_service)

    @pytest.mark.parametrize("method,path,body", TENANT_ROUTES)
    def test_cross_tenant_response_matches_missing_approval(
        self, make_client, mock_service, method, path, body
    ):
        client = make_client(user=_make_user(organization_id="org-999"))
        cross_tenant = _call(client, method, path, body)

        mock_service.get_request.return_value = None
        missing = _call(client, method, path, body)

        assert cross_tenant.status_code == missing.status_code == 404
        assert cross_tenant.json() == missing.json()

    @pytest.mark.parametrize("method,path,body", TENANT_ROUTES)
    def test_same_tenant_allowed(self, make_client, mock_service, method, path, body):
        client = make_client(user=_make_user(organization_id="org-123"))

        response = _call(client, method, path, body)

        assert response.status_code == 200


class TestTenantIsolationLegacyApprovals:
    """Approvals without an organization are visible only to platform admins."""

    @pytest.fixture
    def legacy_service(self, mock_service, sample_approval):
        sample_approval.metadata.pop("organization_id")
        return mock_service

    @pytest.mark.parametrize("method,path,body", TENANT_ROUTES)
    def test_platform_admin_can_access(
        self, make_client, legacy_service, method, path, body
    ):
        client = make_client(
            user=_make_user(groups=["platform_admin", "admin"], organization_id=None)
        )

        response = _call(client, method, path, body)

        assert response.status_code == 200

    @pytest.mark.parametrize("method,path,body", TENANT_ROUTES)
    @pytest.mark.parametrize(
        "groups,organization_id",
        [
            (["admin"], "org-123"),
            (["security-engineer"], "org-123"),
            (["admin"], None),
        ],
        ids=["org-admin", "engineer", "no-org-admin"],
    )
    def test_non_platform_admin_gets_not_found(
        self,
        make_client,
        legacy_service,
        method,
        path,
        body,
        groups,
        organization_id,
    ):
        client = make_client(
            user=_make_user(groups=groups, organization_id=organization_id)
        )

        response = _call(client, method, path, body)

        assert response.status_code == 404
        _assert_no_decision(legacy_service)


class TestTenantIsolationListAndStats:
    @pytest.fixture
    def mixed_approvals(self):
        return [
            _approval_dict("own-pending", "PENDING", "org-123"),
            _approval_dict("own-approved", "APPROVED", "org-123"),
            _approval_dict("other-pending", "PENDING", "org-999"),
            _approval_dict("other-rejected", "REJECTED", "org-999"),
            _approval_dict("legacy-pending", "PENDING", None),
        ]

    def test_list_shows_only_own_org(self, make_client, mock_service, mixed_approvals):
        mock_service.get_all_requests.return_value = mixed_approvals
        client = make_client(user=_make_user(groups=["viewer"]))

        data = client.get("/api/v1/approvals").json()

        assert {a["id"] for a in data["approvals"]} == {"own-pending", "own-approved"}
        assert data["total"] == 2
        assert data["pending"] == 1
        assert data["approved"] == 1
        assert data["rejected"] == 0

    def test_list_org_admin_does_not_see_legacy(
        self, make_client, mock_service, mixed_approvals
    ):
        mock_service.get_all_requests.return_value = mixed_approvals
        client = make_client(user=_make_user(groups=["admin"]))

        data = client.get("/api/v1/approvals").json()

        assert "legacy-pending" not in {a["id"] for a in data["approvals"]}

    def test_list_platform_admin_without_org_sees_only_legacy(
        self, make_client, mock_service, mixed_approvals
    ):
        mock_service.get_all_requests.return_value = mixed_approvals
        client = make_client(
            user=_make_user(groups=["platform_admin"], organization_id=None)
        )

        data = client.get("/api/v1/approvals").json()

        assert [a["id"] for a in data["approvals"]] == ["legacy-pending"]
        assert data["total"] == 1

    def test_list_user_without_org_sees_nothing(
        self, make_client, mock_service, mixed_approvals
    ):
        mock_service.get_all_requests.return_value = mixed_approvals
        client = make_client(user=_make_user(groups=["admin"], organization_id=None))

        data = client.get("/api/v1/approvals").json()

        assert data["approvals"] == []
        assert data["total"] == 0

    def test_stats_scoped_to_own_org(self, make_client, isolated_service):
        from src.services.hitl_approval_service import PatchSeverity

        for org in ("org-123", "org-123", "org-999", None):
            metadata = {"organization_id": org} if org else {}
            isolated_service.create_approval_request(
                patch_id="p",
                vulnerability_id="v",
                severity=PatchSeverity.CRITICAL,
                metadata=metadata,
            )
        client = make_client(
            user=_make_user(groups=["viewer"]), service=isolated_service
        )

        data = client.get("/api/v1/approvals/stats").json()

        assert data["total"] == 2
        assert data["pending"] == 2
        assert data["by_severity"]["CRITICAL"] == 2

    def test_stats_user_without_org_sees_zero(self, make_client, isolated_service):
        isolated_service.create_approval_request(
            patch_id="p", vulnerability_id="v", metadata={"organization_id": "org-1"}
        )
        client = make_client(
            user=_make_user(groups=["admin"], organization_id=None),
            service=isolated_service,
        )

        data = client.get("/api/v1/approvals/stats").json()

        assert data["total"] == 0
        assert data["pending"] == 0


class TestDevBypassSeededData:
    """Local dev (auth bypass + seeded MOCK data) keeps working under scoping."""

    def test_dev_user_sees_and_can_open_seeded_approvals(
        self, make_client, monkeypatch
    ):
        from src.services.hitl_approval_service import (
            DEMO_ORGANIZATION_ID,
            HITLApprovalService,
            HITLMode,
        )

        monkeypatch.setenv("AURA_SEED_MOCK_APPROVALS", "true")
        monkeypatch.setenv("AURA_AUTH_BYPASS", "true")
        monkeypatch.setenv("AURA_ENVIRONMENT", "test")
        service = HITLApprovalService(mode=HITLMode.MOCK)
        seeded = len(service.mock_store)
        assert seeded > 0
        # No user override: get_current_user resolves the dev bypass user.
        client = make_client(user=None, service=service)

        listing = client.get("/api/v1/approvals").json()
        stats = client.get("/api/v1/approvals/stats").json()
        first_id = listing["approvals"][0]["id"]
        detail = client.get(f"/api/v1/approvals/{first_id}")

        assert listing["total"] == seeded
        assert stats["total"] == seeded
        assert detail.status_code == 200
        assert detail.json()["metadata"]["organization_id"] == DEMO_ORGANIZATION_ID
