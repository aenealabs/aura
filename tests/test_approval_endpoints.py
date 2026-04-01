"""
Tests for HITL Approval API Endpoints.

Tests the REST API endpoints for the Human-in-the-Loop approval workflow.

IMPORTANT: Uses lazy imports inside fixtures to ensure fresh module state
in forked test processes. Module-level imports of src.* modules would
create stale references after process fork.
"""

import platform
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# These tests require pytest-forked for proper isolation due to complex FastAPI
# router state. On Linux, neither forked mode nor module clearing works correctly:
# - Forked mode: Routes not registered properly in forked subprocess (404 errors)
# - Module clearing: Causes FastAPIError due to starlette.Request class identity issues
#
# On macOS/Windows, forked mode works correctly and provides test isolation.
# On Linux (CI), skip these tests - they are validated locally before merge.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_hitl_service():
    """Create a mock HITL service for testing."""
    from src.services.hitl_approval_service import HITLApprovalService

    service = MagicMock(spec=HITLApprovalService)

    # Setup default return values (sync methods - no AsyncMock)
    service.get_all_requests = MagicMock(return_value=[])
    service.get_pending_requests = MagicMock(return_value=[])
    service.get_request = MagicMock(return_value=None)
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
def sample_approval():
    """Sample approval request data as ApprovalRequest object."""
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
        expires_at="",
        patch_diff="--- a/src/auth/login.py\n+++ b/src/auth/login.py\n@@ -10,7 +10,7 @@\n",
        metadata={
            "title": "Fix SQL injection in user login",
            "description": "Patches SQL injection vulnerability in authentication module",
            "affected_file": "src/auth/login.py",
            "lines_changed": 15,
            "generated_by": "coder-agent",
            "sandbox_status": "passed",
            "requested_by": "security-agent",
            "vulnerability_description": "SQL injection in user login",
            "affected_component": "auth",
        },
        sandbox_test_results={"passed": True, "tests_run": 5, "tests_passed": 5},
    )


@pytest.fixture
def sample_approval_dict():
    """Sample approval as dict (for get_all_requests mock)."""
    return {
        "approval_id": "apr-123",
        "patch_id": "patch-456",
        "vulnerability_id": "CVE-2024-1234",
        "status": "PENDING",
        "severity": "HIGH",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": "",
        "patch_diff": "--- a/src/auth/login.py\n+++ b/src/auth/login.py\n",
        "metadata": {
            "title": "Fix SQL injection in user login",
            "description": "SQL injection fix",
            "affected_file": "src/auth/login.py",
            "lines_changed": 15,
            "generated_by": "coder-agent",
            "sandbox_status": "passed",
            "requested_by": "security-agent",
        },
    }


@pytest.fixture
def sample_approvals_list(sample_approval_dict):
    """List of sample approval requests as dicts (for get_all_requests mock)."""
    now = datetime.now(timezone.utc).isoformat()
    base = sample_approval_dict.copy()
    return [
        base,
        {
            **base,
            "approval_id": "apr-456",
            "vulnerability_id": "CVE-2024-5678",
            "status": "APPROVED",
            "severity": "CRITICAL",
            "reviewed_by": "reviewer@example.com",
            "reviewed_at": now,
            "metadata": {
                "title": "Fix XSS in comment field",
                "description": "XSS fix",
                "affected_file": "src/comments.py",
            },
        },
        {
            **base,
            "approval_id": "apr-789",
            "vulnerability_id": "CVE-2024-9012",
            "status": "REJECTED",
            "severity": "MEDIUM",
            "reviewed_by": "reviewer@example.com",
            "reviewed_at": now,
            "decision_reason": "Incomplete fix",
            "metadata": {
                "title": "Fix path traversal",
                "description": "Path traversal fix",
                "affected_file": "src/files.py",
            },
        },
    ]


@pytest.fixture
def test_client(mock_hitl_service):
    """Create a test client with mocked service.

    Uses lazy imports to ensure fresh module state in forked processes.
    Uses app.dependency_overrides for clean dependency injection.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.approval_endpoints import router
    from src.api.dependencies import get_hitl_service
    from src.services.api_rate_limiter import reset_rate_limiter

    # Reset rate limiter to ensure clean state for each test
    reset_rate_limiter()

    app = FastAPI()
    app.include_router(router)

    # Use FastAPI dependency injection override pattern
    app.dependency_overrides[get_hitl_service] = lambda: mock_hitl_service

    client = TestClient(app)
    yield client

    # Cleanup: clear overrides after test
    app.dependency_overrides.clear()


# ============================================================================
# List Approvals Tests
# ============================================================================


class TestListApprovals:
    """Tests for GET /api/v1/approvals endpoint."""

    def test_list_approvals_empty(self, test_client, mock_hitl_service):
        """Test listing approvals when none exist."""
        mock_hitl_service.get_all_requests.return_value = []

        response = test_client.get("/api/v1/approvals")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["approvals"] == []

    def test_list_approvals_with_data(
        self, test_client, mock_hitl_service, sample_approvals_list
    ):
        """Test listing approvals with existing data."""
        mock_hitl_service.get_all_requests.return_value = sample_approvals_list

        response = test_client.get("/api/v1/approvals")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["approvals"]) == 3

    def test_list_approvals_filter_pending(
        self, test_client, mock_hitl_service, sample_approvals_list
    ):
        """Test filtering by pending status."""
        pending = [a for a in sample_approvals_list if a["status"] == "PENDING"]
        mock_hitl_service.get_pending_requests.return_value = pending
        mock_hitl_service.get_all_requests.return_value = sample_approvals_list

        response = test_client.get("/api/v1/approvals?status=pending")

        assert response.status_code == 200
        data = response.json()
        # Should only have pending approvals
        for approval in data["approvals"]:
            assert approval["status"] == "pending"

    def test_list_approvals_filter_severity(
        self, test_client, mock_hitl_service, sample_approvals_list
    ):
        """Test filtering by severity."""
        mock_hitl_service.get_all_requests.return_value = sample_approvals_list

        response = test_client.get("/api/v1/approvals?severity=critical")

        assert response.status_code == 200
        data = response.json()
        for approval in data["approvals"]:
            assert approval["severity"] == "critical"

    def test_list_approvals_with_limit(
        self, test_client, mock_hitl_service, sample_approvals_list
    ):
        """Test pagination limit."""
        mock_hitl_service.get_all_requests.return_value = sample_approvals_list

        response = test_client.get("/api/v1/approvals?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["approvals"]) <= 2


# ============================================================================
# Get Approval Details Tests
# ============================================================================


class TestGetApprovalDetails:
    """Tests for GET /api/v1/approvals/{approval_id} endpoint."""

    def test_get_approval_success(
        self, test_client, mock_hitl_service, sample_approval
    ):
        """Test getting approval details successfully."""
        mock_hitl_service.get_request.return_value = sample_approval

        response = test_client.get("/api/v1/approvals/apr-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "apr-123"
        assert data["title"] == "Fix SQL injection in user login"

    def test_get_approval_not_found(self, test_client, mock_hitl_service):
        """Test getting non-existent approval."""
        mock_hitl_service.get_request.return_value = None

        response = test_client.get("/api/v1/approvals/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


# ============================================================================
# Approve Request Tests
# ============================================================================


class TestApproveRequest:
    """Tests for POST /api/v1/approvals/{approval_id}/approve endpoint."""

    def test_approve_success(self, test_client, mock_hitl_service, sample_approval):
        """Test approving a request successfully."""
        mock_hitl_service.approve_request.return_value = {"success": True}

        response = test_client.post(
            "/api/v1/approvals/apr-123/approve",
            json={
                "reviewer_email": "reviewer@example.com",
                "comment": "Looks good!",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_status"] == "approved"
        assert data["approval_id"] == "apr-123"

    def test_approve_missing_reviewer(self, test_client):
        """Test approving without reviewer email."""
        response = test_client.post(
            "/api/v1/approvals/apr-123/approve",
            json={},
        )

        assert response.status_code == 422  # Validation error

    def test_approve_invalid_request(self, test_client, mock_hitl_service):
        """Test approving an already-processed request."""
        from src.services.hitl_approval_service import HITLApprovalError

        mock_hitl_service.approve_request.side_effect = HITLApprovalError(
            "Request already approved"
        )

        response = test_client.post(
            "/api/v1/approvals/apr-123/approve",
            json={"reviewer_email": "reviewer@example.com"},
        )

        assert response.status_code == 400
        # Generic error message for security (doesn't expose internal exception)
        assert "cannot be processed" in response.json()["detail"]


# ============================================================================
# Reject Request Tests
# ============================================================================


class TestRejectRequest:
    """Tests for POST /api/v1/approvals/{approval_id}/reject endpoint."""

    def test_reject_success(self, test_client, mock_hitl_service):
        """Test rejecting a request successfully."""
        mock_hitl_service.reject_request.return_value = {"success": True}

        response = test_client.post(
            "/api/v1/approvals/apr-123/reject",
            json={
                "reviewer_email": "reviewer@example.com",
                "reason": "Incomplete fix - missing edge case handling",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_status"] == "rejected"

    def test_reject_missing_reason(self, test_client):
        """Test rejecting without providing a reason."""
        response = test_client.post(
            "/api/v1/approvals/apr-123/reject",
            json={"reviewer_email": "reviewer@example.com"},
        )

        assert response.status_code == 422  # Validation error

    def test_reject_invalid_request(self, test_client, mock_hitl_service):
        """Test rejecting an already-processed request."""
        from src.services.hitl_approval_service import HITLApprovalError

        mock_hitl_service.reject_request.side_effect = HITLApprovalError(
            "Request already rejected"
        )

        response = test_client.post(
            "/api/v1/approvals/apr-123/reject",
            json={
                "reviewer_email": "reviewer@example.com",
                "reason": "Not needed",
            },
        )

        assert response.status_code == 400


# ============================================================================
# Cancel Request Tests
# ============================================================================


class TestCancelRequest:
    """Tests for POST /api/v1/approvals/{approval_id}/cancel endpoint."""

    def test_cancel_success(self, test_client, mock_hitl_service):
        """Test cancelling a request successfully."""
        mock_hitl_service.cancel_request.return_value = {"success": True}

        response = test_client.post("/api/v1/approvals/apr-123/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_status"] == "cancelled"


# ============================================================================
# Statistics Tests
# ============================================================================


class TestApprovalStats:
    """Tests for GET /api/v1/approvals/stats endpoint."""

    def test_get_stats_success(self, test_client, mock_hitl_service):
        """Test getting approval statistics."""
        mock_hitl_service.get_statistics.return_value = {
            "total": 100,
            "pending": 25,
            "approved": 60,
            "rejected": 15,
            "expired": 0,
            "avg_approval_time_hours": 4.5,
            "by_severity": {
                "critical": 10,
                "high": 30,
                "medium": 40,
                "low": 20,
            },
        }

        response = test_client.get("/api/v1/approvals/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 100
        assert data["pending"] == 25
        assert data["approved"] == 60
        assert data["by_severity"]["critical"] == 10


# ============================================================================
# Integration Tests
# ============================================================================


class TestApprovalWorkflow:
    """Integration tests for the full approval workflow."""

    @pytest.fixture(autouse=True)
    def mock_rate_limiter(self):
        """Disable rate limiting for workflow tests that make multiple requests."""
        from src.services.api_rate_limiter import (
            disable_rate_limiting,
            enable_rate_limiting,
        )

        disable_rate_limiting()
        yield
        enable_rate_limiting()

    def test_full_approval_workflow(
        self, test_client, mock_hitl_service, sample_approval, sample_approval_dict
    ):
        """Test complete approval workflow: list -> view -> approve."""
        # Step 1: List shows pending approval (get_all_requests returns dicts)
        mock_hitl_service.get_all_requests.return_value = [sample_approval_dict]

        list_response = test_client.get("/api/v1/approvals")
        assert list_response.status_code == 200
        assert len(list_response.json()["approvals"]) == 1

        # Step 2: View details (get_request returns ApprovalRequest object)
        mock_hitl_service.get_request.return_value = sample_approval

        detail_response = test_client.get("/api/v1/approvals/apr-123")
        assert detail_response.status_code == 200
        assert detail_response.json()["status"] == "pending"

        # Step 3: Approve the request
        mock_hitl_service.approve_request.return_value = {"success": True}

        approve_response = test_client.post(
            "/api/v1/approvals/apr-123/approve",
            json={"reviewer_email": "reviewer@example.com"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["new_status"] == "approved"

    def test_full_rejection_workflow(
        self, test_client, mock_hitl_service, sample_approval, sample_approval_dict
    ):
        """Test complete rejection workflow: list -> view -> reject."""
        # Step 1: List shows pending approval (get_all_requests returns dicts)
        mock_hitl_service.get_all_requests.return_value = [sample_approval_dict]

        list_response = test_client.get("/api/v1/approvals")
        assert list_response.status_code == 200

        # Step 2: View details (get_request returns ApprovalRequest object)
        mock_hitl_service.get_request.return_value = sample_approval

        detail_response = test_client.get("/api/v1/approvals/apr-123")
        assert detail_response.status_code == 200

        # Step 3: Reject the request with reason
        mock_hitl_service.reject_request.return_value = {"success": True}

        reject_response = test_client.post(
            "/api/v1/approvals/apr-123/reject",
            json={
                "reviewer_email": "reviewer@example.com",
                "reason": "Fix introduces new security issue",
            },
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["new_status"] == "rejected"
