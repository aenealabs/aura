"""
Project Aura - HITL Approval Service Tests

Tests for the Human-in-the-Loop approval service that manages
security patch approval workflows.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.services.hitl_approval_service import (
    ApprovalRequest,
    ApprovalStatus,
    EscalationAction,
    ExpirationProcessingResult,
    ExpirationResult,
    HITLApprovalError,
    HITLApprovalService,
    HITLDecision,
    HITLMode,
    PatchSeverity,
    create_hitl_approval_service,
)


class TestApprovalStatus:
    """Tests for ApprovalStatus enum."""

    def test_pending_status(self):
        """Test PENDING status value."""
        assert ApprovalStatus.PENDING.value == "PENDING"

    def test_approved_status(self):
        """Test APPROVED status value."""
        assert ApprovalStatus.APPROVED.value == "APPROVED"

    def test_rejected_status(self):
        """Test REJECTED status value."""
        assert ApprovalStatus.REJECTED.value == "REJECTED"

    def test_expired_status(self):
        """Test EXPIRED status value."""
        assert ApprovalStatus.EXPIRED.value == "EXPIRED"

    def test_cancelled_status(self):
        """Test CANCELLED status value."""
        assert ApprovalStatus.CANCELLED.value == "CANCELLED"

    def test_escalated_status(self):
        """Test ESCALATED status value."""
        assert ApprovalStatus.ESCALATED.value == "ESCALATED"

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        statuses = list(ApprovalStatus)
        assert len(statuses) == 6


class TestEscalationAction:
    """Tests for EscalationAction enum."""

    def test_escalate_action(self):
        """Test ESCALATE action."""
        assert EscalationAction.ESCALATE.value == "ESCALATE"

    def test_expire_action(self):
        """Test EXPIRE action."""
        assert EscalationAction.EXPIRE.value == "EXPIRE"

    def test_warn_action(self):
        """Test WARN action."""
        assert EscalationAction.WARN.value == "WARN"


class TestPatchSeverity:
    """Tests for PatchSeverity enum."""

    def test_critical_severity(self):
        """Test CRITICAL severity."""
        assert PatchSeverity.CRITICAL.value == "CRITICAL"

    def test_high_severity(self):
        """Test HIGH severity."""
        assert PatchSeverity.HIGH.value == "HIGH"

    def test_medium_severity(self):
        """Test MEDIUM severity."""
        assert PatchSeverity.MEDIUM.value == "MEDIUM"

    def test_low_severity(self):
        """Test LOW severity."""
        assert PatchSeverity.LOW.value == "LOW"

    def test_all_severities_exist(self):
        """Test all expected severities exist."""
        severities = list(PatchSeverity)
        assert len(severities) == 4


class TestHITLMode:
    """Tests for HITLMode enum."""

    def test_mock_mode(self):
        """Test MOCK mode."""
        assert HITLMode.MOCK.value == "mock"

    def test_aws_mode(self):
        """Test AWS mode."""
        assert HITLMode.AWS.value == "aws"


class TestExpirationResult:
    """Tests for ExpirationResult dataclass."""

    def test_expiration_result_creation(self):
        """Test creating expiration result."""
        result = ExpirationResult(
            approval_id="approval-123",
            action=EscalationAction.ESCALATE,
            success=True,
            message="Escalated to backup reviewer",
        )
        assert result.approval_id == "approval-123"
        assert result.action == EscalationAction.ESCALATE
        assert result.success is True
        assert result.message == "Escalated to backup reviewer"
        assert result.escalated_to is None

    def test_expiration_result_with_escalated_to(self):
        """Test expiration result with escalated_to."""
        result = ExpirationResult(
            approval_id="approval-456",
            action=EscalationAction.ESCALATE,
            success=True,
            message="Escalated",
            escalated_to="backup@example.com",
        )
        assert result.escalated_to == "backup@example.com"


class TestExpirationProcessingResult:
    """Tests for ExpirationProcessingResult dataclass."""

    def test_processing_result_creation(self):
        """Test creating processing result."""
        result = ExpirationProcessingResult(
            processed=10,
            escalated=2,
            expired=3,
            warnings_sent=4,
            errors=1,
        )
        assert result.processed == 10
        assert result.escalated == 2
        assert result.expired == 3
        assert result.warnings_sent == 4
        assert result.errors == 1
        assert result.details == []

    def test_processing_result_with_details(self):
        """Test processing result with details."""
        detail = ExpirationResult(
            approval_id="test",
            action=EscalationAction.WARN,
            success=True,
            message="Warning sent",
        )
        result = ExpirationProcessingResult(
            processed=1,
            escalated=0,
            expired=0,
            warnings_sent=1,
            errors=0,
            details=[detail],
        )
        assert len(result.details) == 1


class TestHITLDecision:
    """Tests for HITLDecision dataclass."""

    def test_hitl_decision_requires_hitl(self):
        """Test decision that requires HITL."""
        decision = HITLDecision(
            requires_hitl=True,
            approval_request=None,
            autonomy_level="critical_hitl",
            reason="High severity requires approval",
        )
        assert decision.requires_hitl is True
        assert decision.auto_approved is False
        assert decision.guardrail_triggered is False

    def test_hitl_decision_auto_approved(self):
        """Test auto-approved decision."""
        decision = HITLDecision(
            requires_hitl=False,
            approval_request=None,
            autonomy_level="full_autonomy",
            reason="Low severity auto-approved",
            auto_approved=True,
        )
        assert decision.requires_hitl is False
        assert decision.auto_approved is True

    def test_hitl_decision_with_guardrail(self):
        """Test decision with guardrail triggered."""
        decision = HITLDecision(
            requires_hitl=True,
            approval_request=None,
            autonomy_level="critical_hitl",
            reason="Guardrail triggered",
            guardrail_triggered=True,
        )
        assert decision.guardrail_triggered is True


class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass."""

    def test_approval_request_minimal(self):
        """Test minimal approval request."""
        request = ApprovalRequest(
            approval_id="approval-123",
            patch_id="patch-456",
            vulnerability_id="vuln-789",
        )
        assert request.approval_id == "approval-123"
        assert request.patch_id == "patch-456"
        assert request.vulnerability_id == "vuln-789"
        assert request.status == ApprovalStatus.PENDING
        assert request.severity == PatchSeverity.MEDIUM

    def test_approval_request_full(self):
        """Test full approval request."""
        request = ApprovalRequest(
            approval_id="approval-full",
            patch_id="patch-full",
            vulnerability_id="vuln-full",
            status=ApprovalStatus.APPROVED,
            severity=PatchSeverity.CRITICAL,
            reviewer_email="reviewer@example.com",
            reviewed_at="2025-12-21T10:00:00Z",
            reviewed_by="admin",
            decision_reason="LGTM",
            sandbox_test_results={"tests_passed": 10},
            patch_diff="- old\n+ new",
            original_code="old code",
            metadata={"key": "value"},
            escalation_count=1,
        )
        assert request.status == ApprovalStatus.APPROVED
        assert request.severity == PatchSeverity.CRITICAL
        assert request.reviewer_email == "reviewer@example.com"
        assert request.escalation_count == 1


class TestHITLApprovalService:
    """Tests for HITLApprovalService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = HITLApprovalService(mode=HITLMode.MOCK)

    def test_init_mock_mode(self):
        """Test initialization in mock mode."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        assert service.mode == HITLMode.MOCK
        assert service.mock_store == {}

    def test_init_default_timeout(self):
        """Test default timeout value."""
        assert self.service.timeout_hours == 24

    def test_init_custom_timeout(self):
        """Test custom timeout value."""
        service = HITLApprovalService(mode=HITLMode.MOCK, timeout_hours=48)
        assert service.timeout_hours == 48

    def test_init_backup_reviewers(self):
        """Test initialization with backup reviewers."""
        reviewers = ["backup1@example.com", "backup2@example.com"]
        service = HITLApprovalService(
            mode=HITLMode.MOCK,
            backup_reviewers=reviewers,
        )
        assert service.backup_reviewers == reviewers

    def test_generate_approval_id(self):
        """Test approval ID generation."""
        id1 = self.service._generate_approval_id()
        id2 = self.service._generate_approval_id()
        assert id1.startswith("approval-")
        assert id2.startswith("approval-")
        assert id1 != id2

    def test_calculate_expiry(self):
        """Test expiry calculation."""
        expiry = self.service._calculate_expiry()
        # Should be a valid ISO format string
        datetime.fromisoformat(expiry)

    def test_create_approval_request(self):
        """Test creating approval request."""
        request = self.service.create_approval_request(
            patch_id="patch-123",
            vulnerability_id="vuln-456",
            severity=PatchSeverity.HIGH,
            patch_diff="+ new code",
            sandbox_results={"tests_passed": 5},
        )
        assert request.patch_id == "patch-123"
        assert request.vulnerability_id == "vuln-456"
        assert request.severity == PatchSeverity.HIGH
        assert request.status == ApprovalStatus.PENDING

    def test_create_approval_request_stored(self):
        """Test that created request is stored."""
        request = self.service.create_approval_request(
            patch_id="patch-stored",
            vulnerability_id="vuln-stored",
        )
        # Should be in mock store
        assert request.approval_id in self.service.mock_store

    def test_get_request(self):
        """Test getting request by ID."""
        created = self.service.create_approval_request(
            patch_id="patch-get",
            vulnerability_id="vuln-get",
        )
        retrieved = self.service.get_request(created.approval_id)
        assert retrieved is not None
        assert retrieved.approval_id == created.approval_id

    def test_get_request_not_found(self):
        """Test getting non-existent request."""
        result = self.service.get_request("non-existent-id")
        assert result is None

    def test_get_pending_requests(self):
        """Test getting pending requests."""
        # Create some requests
        self.service.create_approval_request(
            patch_id="patch-1",
            vulnerability_id="vuln-1",
            severity=PatchSeverity.HIGH,
        )
        self.service.create_approval_request(
            patch_id="patch-2",
            vulnerability_id="vuln-2",
            severity=PatchSeverity.MEDIUM,
        )

        pending = self.service.get_pending_requests()
        assert len(pending) == 2

    def test_get_pending_requests_by_severity(self):
        """Test filtering pending requests by severity."""
        self.service.create_approval_request(
            patch_id="patch-high",
            vulnerability_id="vuln-high",
            severity=PatchSeverity.HIGH,
        )
        self.service.create_approval_request(
            patch_id="patch-low",
            vulnerability_id="vuln-low",
            severity=PatchSeverity.LOW,
        )

        high_requests = self.service.get_pending_requests(severity=PatchSeverity.HIGH)
        assert len(high_requests) == 1
        assert high_requests[0].severity == PatchSeverity.HIGH

    def test_get_requests_by_patch(self):
        """Test getting requests by patch ID."""
        self.service.create_approval_request(
            patch_id="patch-target",
            vulnerability_id="vuln-1",
        )
        self.service.create_approval_request(
            patch_id="patch-other",
            vulnerability_id="vuln-2",
        )

        results = self.service.get_requests_by_patch("patch-target")
        assert len(results) == 1
        assert results[0].patch_id == "patch-target"

    def test_approve_request(self):
        """Test approving a request."""
        request = self.service.create_approval_request(
            patch_id="patch-approve",
            vulnerability_id="vuln-approve",
        )
        result = self.service.approve_request(
            approval_id=request.approval_id,
            reviewer_id="admin@example.com",
            reason="LGTM",
        )
        assert result is True

        # Verify status changed
        updated = self.service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.APPROVED

    def test_reject_request(self):
        """Test rejecting a request."""
        request = self.service.create_approval_request(
            patch_id="patch-reject",
            vulnerability_id="vuln-reject",
        )
        result = self.service.reject_request(
            approval_id=request.approval_id,
            reviewer_id="admin@example.com",
            reason="Insufficient testing",
        )
        assert result is True

        updated = self.service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.REJECTED

    def test_reject_request_requires_reason(self):
        """Test that rejection requires reason."""
        request = self.service.create_approval_request(
            patch_id="patch-no-reason",
            vulnerability_id="vuln-no-reason",
        )
        with pytest.raises(HITLApprovalError):
            self.service.reject_request(
                approval_id=request.approval_id,
                reviewer_id="admin@example.com",
                reason="",
            )

    def test_cancel_request(self):
        """Test cancelling a request."""
        request = self.service.create_approval_request(
            patch_id="patch-cancel",
            vulnerability_id="vuln-cancel",
        )
        result = self.service.cancel_request(
            approval_id=request.approval_id,
            reason="No longer needed",
        )
        assert result is True

        updated = self.service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.CANCELLED

    def test_cancel_request_not_found(self):
        """Test cancelling non-existent request."""
        result = self.service.cancel_request("non-existent")
        assert result is False

    def test_get_all_requests(self):
        """Test getting all requests."""
        self.service.create_approval_request(
            patch_id="patch-all-1",
            vulnerability_id="vuln-all-1",
        )
        self.service.create_approval_request(
            patch_id="patch-all-2",
            vulnerability_id="vuln-all-2",
        )

        all_requests = self.service.get_all_requests()
        assert len(all_requests) == 2

    def test_get_statistics(self):
        """Test getting statistics."""
        self.service.create_approval_request(
            patch_id="patch-stats",
            vulnerability_id="vuln-stats",
            severity=PatchSeverity.CRITICAL,
        )

        stats = self.service.get_statistics()
        assert "total_requests" in stats
        assert "pending" in stats
        assert "by_severity" in stats
        assert stats["pending"] >= 1
        assert stats["by_severity"]["CRITICAL"] >= 1

    def test_get_audit_log(self):
        """Test getting audit log."""
        # Create and approve a request
        request = self.service.create_approval_request(
            patch_id="patch-audit",
            vulnerability_id="vuln-audit",
        )
        self.service.approve_request(
            approval_id=request.approval_id,
            reviewer_id="admin@example.com",
            reason="Approved",
        )

        audit = self.service.get_audit_log()
        assert len(audit) >= 1
        assert audit[0]["status"] == ApprovalStatus.APPROVED.value


class TestHITLApprovalServiceExpiration:
    """Tests for expiration handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = HITLApprovalService(
            mode=HITLMode.MOCK,
            timeout_hours=1,  # Short timeout for testing
            backup_reviewers=["backup1@test.com", "backup2@test.com"],
        )

    def test_is_expired_false(self):
        """Test non-expired request."""
        request = self.service.create_approval_request(
            patch_id="patch-not-expired",
            vulnerability_id="vuln-not-expired",
        )
        assert not self.service._is_expired(request)

    def test_determine_action_none(self):
        """Test no action needed for fresh request."""
        request = self.service.create_approval_request(
            patch_id="patch-fresh",
            vulnerability_id="vuln-fresh",
        )
        action = self.service._determine_action(request)
        assert action is None

    def test_process_expirations(self):
        """Test processing expirations."""
        result = self.service.process_expirations()
        assert isinstance(result, ExpirationProcessingResult)
        assert result.errors == 0

    def test_log_audit(self):
        """Test audit logging."""
        self.service._log_audit(
            event_type="test_event",
            approval_id="test-123",
            details={"key": "value"},
        )
        assert len(self.service.audit_entries) == 1
        assert self.service.audit_entries[0]["event_type"] == "test_event"


class TestHITLApprovalServiceConversion:
    """Tests for data conversion methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = HITLApprovalService(mode=HITLMode.MOCK)

    def test_item_to_request(self):
        """Test converting DynamoDB item to request."""
        item = {
            "approvalId": "approval-conv",
            "patchId": "patch-conv",
            "vulnerabilityId": "vuln-conv",
            "status": "PENDING",
            "severity": "HIGH",
            "createdAt": "2025-12-21T10:00:00",
            "expiresAt": "2025-12-22T10:00:00",
            "sandboxTestResults": {},
            "patchDiff": "",
            "originalCode": "",
            "metadata": {},
        }
        request = self.service._item_to_request(item)
        assert request.approval_id == "approval-conv"
        assert request.status == ApprovalStatus.PENDING
        assert request.severity == PatchSeverity.HIGH

    def test_request_to_dict(self):
        """Test converting request to dict."""
        request = ApprovalRequest(
            approval_id="approval-dict",
            patch_id="patch-dict",
            vulnerability_id="vuln-dict",
        )
        data = self.service._request_to_dict(request)
        assert data["approval_id"] == "approval-dict"
        assert data["status"] == "PENDING"


class TestCreateHITLApprovalService:
    """Tests for factory function."""

    def test_create_mock_service(self):
        """Test creating mock service."""
        service = create_hitl_approval_service(use_mock=True)
        assert service.mode == HITLMode.MOCK

    def test_create_with_timeout(self):
        """Test creating service with custom timeout."""
        service = create_hitl_approval_service(
            use_mock=True,
            timeout_hours=72,
        )
        assert service.timeout_hours == 72

    @patch.dict("os.environ", {"AWS_REGION": ""})
    def test_create_defaults_to_mock(self):
        """Test that service defaults to mock without AWS."""
        service = create_hitl_approval_service(use_mock=False)
        assert service.mode == HITLMode.MOCK


class TestHITLApprovalError:
    """Tests for HITLApprovalError exception."""

    def test_error_creation(self):
        """Test creating error."""
        error = HITLApprovalError("Test error message")
        assert str(error) == "Test error message"

    def test_error_is_exception(self):
        """Test error is an Exception."""
        error = HITLApprovalError("Test")
        assert isinstance(error, Exception)

    def test_error_can_be_raised(self):
        """Test error can be raised and caught."""
        with pytest.raises(HITLApprovalError):
            raise HITLApprovalError("Raised error")
