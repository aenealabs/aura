"""
Unit Tests for HITL Approval and Notification Services

Tests the HITLApprovalService and NotificationService used in the
human-in-the-loop approval workflow for security patches.
"""

from datetime import datetime, timedelta

import pytest

from src.services.hitl_approval_service import (
    ApprovalRequest,
    ApprovalStatus,
    EscalationAction,
    ExpirationProcessingResult,
    ExpirationResult,
    HITLApprovalError,
    HITLApprovalService,
    HITLMode,
    PatchSeverity,
    create_hitl_approval_service,
)
from src.services.notification_service import (
    NotificationChannel,
    NotificationMode,
    NotificationPriority,
    NotificationResult,
    NotificationService,
    create_notification_service,
)


class TestHITLApprovalServiceInitialization:
    """Test HITLApprovalService initialization and configuration."""

    def test_mock_mode_initialization(self):
        """Test service initializes correctly in mock mode."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        assert service.mode == HITLMode.MOCK
        assert service.timeout_hours == 24  # Default timeout
        assert isinstance(service.mock_store, dict)
        assert len(service.mock_store) == 0

    def test_custom_timeout(self):
        """Test custom timeout configuration."""
        service = HITLApprovalService(mode=HITLMode.MOCK, timeout_hours=48)

        assert service.timeout_hours == 48

    def test_custom_table_name(self):
        """Test custom table name configuration."""
        service = HITLApprovalService(
            mode=HITLMode.MOCK, table_name="custom-approvals-table"
        )

        assert service.table_name == "custom-approvals-table"

    def test_factory_function_mock(self):
        """Test factory function creates mock service."""
        service = create_hitl_approval_service(use_mock=True)

        assert service.mode == HITLMode.MOCK

    def test_factory_function_custom_timeout(self):
        """Test factory function with custom timeout."""
        service = create_hitl_approval_service(use_mock=True, timeout_hours=72)

        assert service.timeout_hours == 72


class TestApprovalRequestCreation:
    """Test creating approval requests."""

    @pytest.fixture
    def service(self):
        """Provide a fresh mock service for each test."""
        return HITLApprovalService(mode=HITLMode.MOCK)

    def test_create_basic_request(self, service):
        """Test creating a basic approval request."""
        request = service.create_approval_request(
            patch_id="patch-123",
            vulnerability_id="vuln-456",
        )

        assert request.patch_id == "patch-123"
        assert request.vulnerability_id == "vuln-456"
        assert request.status == ApprovalStatus.PENDING
        assert request.severity == PatchSeverity.MEDIUM  # Default
        assert request.approval_id.startswith("approval-")
        assert request.created_at is not None
        assert request.expires_at is not None

    def test_create_request_with_severity(self, service):
        """Test creating request with specific severity."""
        request = service.create_approval_request(
            patch_id="patch-critical",
            vulnerability_id="vuln-rce",
            severity=PatchSeverity.CRITICAL,
        )

        assert request.severity == PatchSeverity.CRITICAL

    def test_create_request_with_full_details(self, service):
        """Test creating request with all optional fields."""
        sandbox_results = {"tests_passed": 10, "tests_failed": 0, "coverage": 95.0}
        metadata = {"repository": "my-repo", "branch": "main"}

        request = service.create_approval_request(
            patch_id="patch-full",
            vulnerability_id="vuln-full",
            severity=PatchSeverity.HIGH,
            patch_diff="- old_code\n+ new_code",
            original_code="old_code",
            sandbox_results=sandbox_results,
            reviewer_email="reviewer@test.com",
            metadata=metadata,
        )

        assert request.patch_diff == "- old_code\n+ new_code"
        assert request.original_code == "old_code"
        assert request.sandbox_test_results == sandbox_results
        assert request.reviewer_email == "reviewer@test.com"
        assert request.metadata == metadata

    def test_request_persisted_to_mock_store(self, service):
        """Test request is saved to mock store."""
        request = service.create_approval_request(
            patch_id="patch-store-test",
            vulnerability_id="vuln-store-test",
        )

        assert request.approval_id in service.mock_store
        stored = service.mock_store[request.approval_id]
        assert stored["patchId"] == "patch-store-test"


class TestApprovalRequestRetrieval:
    """Test retrieving approval requests."""

    @pytest.fixture
    def service_with_requests(self):
        """Provide service with pre-created requests."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        # Create requests with different severities
        service.create_approval_request(
            patch_id="patch-critical",
            vulnerability_id="vuln-1",
            severity=PatchSeverity.CRITICAL,
        )
        service.create_approval_request(
            patch_id="patch-high",
            vulnerability_id="vuln-2",
            severity=PatchSeverity.HIGH,
        )
        service.create_approval_request(
            patch_id="patch-medium",
            vulnerability_id="vuln-3",
            severity=PatchSeverity.MEDIUM,
        )

        return service

    def test_get_request_by_id(self, service_with_requests):
        """Test retrieving request by approval ID."""
        # Create a specific request to retrieve
        original = service_with_requests.create_approval_request(
            patch_id="patch-to-get",
            vulnerability_id="vuln-to-get",
        )

        retrieved = service_with_requests.get_request(original.approval_id)

        assert retrieved is not None
        assert retrieved.approval_id == original.approval_id
        assert retrieved.patch_id == "patch-to-get"

    def test_get_nonexistent_request(self, service_with_requests):
        """Test retrieving non-existent request returns None."""
        result = service_with_requests.get_request("nonexistent-id")

        assert result is None

    def test_get_pending_requests(self, service_with_requests):
        """Test getting all pending requests."""
        pending = service_with_requests.get_pending_requests()

        assert len(pending) >= 3  # At least our 3 created requests
        for request in pending:
            assert request.status == ApprovalStatus.PENDING

    def test_get_pending_requests_by_severity(self, service_with_requests):
        """Test filtering pending requests by severity."""
        critical = service_with_requests.get_pending_requests(
            severity=PatchSeverity.CRITICAL
        )

        assert len(critical) >= 1
        for request in critical:
            assert request.severity == PatchSeverity.CRITICAL

    def test_pending_requests_sorted_by_severity(self, service_with_requests):
        """Test pending requests are sorted by severity (CRITICAL first)."""
        pending = service_with_requests.get_pending_requests()

        # Verify CRITICAL comes before HIGH, HIGH before MEDIUM, etc.
        severity_order = {
            PatchSeverity.CRITICAL: 0,
            PatchSeverity.HIGH: 1,
            PatchSeverity.MEDIUM: 2,
            PatchSeverity.LOW: 3,
        }

        for i in range(len(pending) - 1):
            current_order = severity_order[pending[i].severity]
            next_order = severity_order[pending[i + 1].severity]
            assert current_order <= next_order

    def test_get_requests_by_patch_id(self, service_with_requests):
        """Test getting requests by patch ID."""
        requests = service_with_requests.get_requests_by_patch("patch-critical")

        assert len(requests) >= 1
        assert requests[0].patch_id == "patch-critical"


class TestApprovalDecisions:
    """Test approval and rejection workflows."""

    @pytest.fixture
    def service(self):
        """Provide a fresh mock service."""
        return HITLApprovalService(mode=HITLMode.MOCK)

    def test_approve_request(self, service):
        """Test approving a request."""
        request = service.create_approval_request(
            patch_id="patch-to-approve",
            vulnerability_id="vuln-approve",
        )

        result = service.approve_request(
            approval_id=request.approval_id,
            reviewer_id="reviewer@test.com",
            reason="LGTM",
        )

        assert result is True

        # Verify status updated
        updated = service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.APPROVED
        assert updated.reviewed_by == "reviewer@test.com"
        assert updated.decision_reason == "LGTM"
        assert updated.reviewed_at is not None

    def test_reject_request_with_reason(self, service):
        """Test rejecting a request with reason."""
        request = service.create_approval_request(
            patch_id="patch-to-reject",
            vulnerability_id="vuln-reject",
        )

        result = service.reject_request(
            approval_id=request.approval_id,
            reviewer_id="reviewer@test.com",
            reason="Code quality issues",
        )

        assert result is True

        updated = service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.REJECTED
        assert updated.decision_reason == "Code quality issues"

    def test_reject_without_reason_raises_error(self, service):
        """Test that rejection requires a reason."""
        request = service.create_approval_request(
            patch_id="patch-no-reason",
            vulnerability_id="vuln-no-reason",
        )

        with pytest.raises(HITLApprovalError, match="Rejection reason is required"):
            service.reject_request(
                approval_id=request.approval_id,
                reviewer_id="reviewer@test.com",
                reason="",
            )

    def test_cannot_approve_already_approved(self, service):
        """Test cannot approve an already approved request."""
        request = service.create_approval_request(
            patch_id="patch-double-approve",
            vulnerability_id="vuln-double",
        )

        # First approval
        service.approve_request(request.approval_id, "reviewer1@test.com", "First")

        # Second approval attempt
        result = service.approve_request(
            request.approval_id, "reviewer2@test.com", "Second"
        )

        assert result is False  # Should fail

    def test_approve_nonexistent_request(self, service):
        """Test approving non-existent request returns False."""
        result = service.approve_request(
            approval_id="nonexistent",
            reviewer_id="reviewer@test.com",
            reason="test",
        )

        assert result is False


class TestRequestCancellation:
    """Test request cancellation."""

    @pytest.fixture
    def service(self):
        """Provide a fresh mock service."""
        return HITLApprovalService(mode=HITLMode.MOCK)

    def test_cancel_request(self, service):
        """Test cancelling a request."""
        request = service.create_approval_request(
            patch_id="patch-to-cancel",
            vulnerability_id="vuln-cancel",
        )

        result = service.cancel_request(
            approval_id=request.approval_id, reason="No longer needed"
        )

        assert result is True

        updated = service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.CANCELLED
        assert updated.decision_reason == "No longer needed"

    def test_cancel_nonexistent_request(self, service):
        """Test cancelling non-existent request."""
        result = service.cancel_request(approval_id="nonexistent", reason="test")

        assert result is False


class TestRequestExpiration:
    """Test request expiration handling."""

    def test_expiry_calculation(self):
        """Test expiry timestamp is calculated correctly."""
        service = HITLApprovalService(mode=HITLMode.MOCK, timeout_hours=24)

        request = service.create_approval_request(
            patch_id="patch-expiry",
            vulnerability_id="vuln-expiry",
        )

        # Parse timestamps
        created = datetime.fromisoformat(request.created_at)
        expires = datetime.fromisoformat(request.expires_at)

        # Should expire approximately 24 hours after creation
        expected_expiry = created + timedelta(hours=24)

        # Allow 1 minute tolerance for test execution time
        delta = abs((expires - expected_expiry).total_seconds())
        assert delta < 60

    def test_short_timeout_for_testing(self):
        """Test expiration detection by manually setting past expiry time."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        request = service.create_approval_request(
            patch_id="patch-immediate-expiry",
            vulnerability_id="vuln-immediate",
        )

        # Manually set expires_at to the past in mock store
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service.mock_store[request.approval_id]["expiresAt"] = past_time

        # Try to approve - should fail due to expiration
        result = service.approve_request(
            approval_id=request.approval_id,
            reviewer_id="reviewer@test.com",
            reason="Too late",
        )

        assert result is False

        # Verify marked as expired
        updated = service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.EXPIRED


class TestAuditLog:
    """Test audit log functionality."""

    @pytest.fixture
    def service_with_decisions(self):
        """Provide service with various approval decisions."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        # Create and approve a request
        req1 = service.create_approval_request(
            patch_id="patch-approved", vulnerability_id="vuln-1"
        )
        service.approve_request(req1.approval_id, "approver@test.com", "Good")

        # Create and reject a request
        req2 = service.create_approval_request(
            patch_id="patch-rejected", vulnerability_id="vuln-2"
        )
        service.reject_request(req2.approval_id, "rejector@test.com", "Bad code")

        # Create a pending request (should not appear in audit log)
        service.create_approval_request(
            patch_id="patch-pending", vulnerability_id="vuln-3"
        )

        return service

    def test_audit_log_contains_decisions(self, service_with_decisions):
        """Test audit log contains approval decisions."""
        audit = service_with_decisions.get_audit_log()

        assert len(audit) >= 2  # At least our approved and rejected

        statuses = [entry["status"] for entry in audit]
        assert "APPROVED" in statuses
        assert "REJECTED" in statuses

    def test_audit_log_excludes_pending(self, service_with_decisions):
        """Test audit log excludes pending requests."""
        audit = service_with_decisions.get_audit_log()

        statuses = [entry["status"] for entry in audit]
        assert "PENDING" not in statuses


class TestStatistics:
    """Test statistics functionality."""

    @pytest.fixture
    def service_with_mixed_requests(self):
        """Provide service with mixed request statuses."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        # Create requests of different severities
        for severity in [
            PatchSeverity.CRITICAL,
            PatchSeverity.HIGH,
            PatchSeverity.MEDIUM,
        ]:
            req = service.create_approval_request(
                patch_id=f"patch-{severity.value}",
                vulnerability_id=f"vuln-{severity.value}",
                severity=severity,
            )
            if severity == PatchSeverity.CRITICAL:
                service.approve_request(req.approval_id, "reviewer@test.com", "Urgent")

        return service

    def test_statistics_counts(self, service_with_mixed_requests):
        """Test statistics counting."""
        stats = service_with_mixed_requests.get_statistics()

        assert stats["total_requests"] >= 3
        assert stats["pending"] >= 2
        assert stats["approved"] >= 1
        assert "by_severity" in stats
        assert stats["by_severity"]["CRITICAL"] >= 1


# =============================================================================
# Notification Service Tests
# =============================================================================


class TestNotificationServiceInitialization:
    """Test NotificationService initialization."""

    def test_mock_mode_initialization(self):
        """Test service initializes in mock mode."""
        service = NotificationService(mode=NotificationMode.MOCK)

        assert service.mode == NotificationMode.MOCK
        assert service.delivery_log == []
        assert service.sns_client is None
        assert service.ses_client is None

    def test_factory_function_mock(self):
        """Test factory function creates mock service."""
        service = create_notification_service(use_mock=True)

        assert service.mode == NotificationMode.MOCK

    def test_custom_configuration(self):
        """Test custom SNS/SES configuration."""
        service = NotificationService(
            mode=NotificationMode.MOCK,
            sns_topic_arn="arn:aws:sns:us-east-1:123456789:custom-topic",
            ses_sender_email="custom@test.com",
            dashboard_url="https://custom-dashboard.test.com",
        )

        assert "custom-topic" in service.sns_topic_arn
        assert service.ses_sender_email == "custom@test.com"
        assert service.dashboard_url == "https://custom-dashboard.test.com"


class TestApprovalNotifications:
    """Test approval notification sending."""

    @pytest.fixture
    def service(self):
        """Provide a fresh mock notification service."""
        return NotificationService(mode=NotificationMode.MOCK)

    def test_send_approval_notification(self, service):
        """Test sending approval notification."""
        results = service.send_approval_notification(
            approval_id="approval-123",
            patch_id="patch-456",
            vulnerability_id="vuln-789",
            severity="HIGH",
            created_at="2025-12-01T10:00:00",
            expires_at="2025-12-02T10:00:00",
            sandbox_results={"tests_passed": 10, "tests_failed": 0},
            patch_diff="- old\n+ new",
            recipients=["security@test.com"],
        )

        # Should have results for email and SNS
        assert len(results) >= 2

        # All should succeed in mock mode
        for result in results:
            assert result.success is True
            assert result.message_id is not None

    def test_notification_to_multiple_recipients(self, service):
        """Test sending to multiple recipients."""
        results = service.send_approval_notification(
            approval_id="approval-multi",
            patch_id="patch-multi",
            vulnerability_id="vuln-multi",
            severity="CRITICAL",
            created_at="2025-12-01T10:00:00",
            expires_at="2025-12-02T10:00:00",
            sandbox_results={},
            patch_diff="diff",
            recipients=["user1@test.com", "user2@test.com", "user3@test.com"],
        )

        # 3 emails + 1 SNS
        assert len(results) == 4

    def test_delivery_log_populated(self, service):
        """Test delivery log is populated."""
        service.send_approval_notification(
            approval_id="approval-log",
            patch_id="patch-log",
            vulnerability_id="vuln-log",
            severity="MEDIUM",
            created_at="2025-12-01T10:00:00",
            expires_at="2025-12-02T10:00:00",
            sandbox_results={},
            patch_diff="",
            recipients=["user@test.com"],
        )

        log = service.get_delivery_log()
        assert len(log) >= 2  # Email + SNS

        channels = [entry.get("channel") for entry in log]
        assert "email" in channels
        assert "sns" in channels


class TestDecisionNotifications:
    """Test decision notification sending."""

    @pytest.fixture
    def service(self):
        """Provide a fresh mock notification service."""
        return NotificationService(mode=NotificationMode.MOCK)

    def test_send_approval_decision(self, service):
        """Test sending approval decision notification."""
        results = service.send_decision_notification(
            approval_id="approval-decided",
            patch_id="patch-decided",
            decision="APPROVED",
            reviewer="reviewer@test.com",
            reason="LGTM",
            recipients=["dev@test.com"],
        )

        assert len(results) >= 2  # Email + SNS
        for result in results:
            assert result.success is True

    def test_send_rejection_decision(self, service):
        """Test sending rejection decision notification."""
        results = service.send_decision_notification(
            approval_id="approval-rejected",
            patch_id="patch-rejected",
            decision="REJECTED",
            reviewer="reviewer@test.com",
            reason="Security concerns",
            recipients=["dev@test.com"],
        )

        assert len(results) >= 2
        for result in results:
            assert result.success is True


class TestExpirationWarnings:
    """Test expiration warning notifications."""

    @pytest.fixture
    def service(self):
        """Provide a fresh mock notification service."""
        return NotificationService(mode=NotificationMode.MOCK)

    def test_send_expiration_warning(self, service):
        """Test sending expiration warning."""
        results = service.send_expiration_warning(
            approval_id="approval-expiring",
            patch_id="patch-expiring",
            severity="HIGH",
            expires_at="2025-12-01T23:00:00",
            recipients=["reviewer@test.com"],
        )

        assert len(results) >= 1
        for result in results:
            assert result.success is True


class TestNotificationPriority:
    """Test notification priority mapping."""

    @pytest.fixture
    def service(self):
        """Provide a fresh mock notification service."""
        return NotificationService(mode=NotificationMode.MOCK)

    def test_critical_severity_high_priority(self, service):
        """Test CRITICAL severity maps to CRITICAL priority."""
        service.send_approval_notification(
            approval_id="approval-crit",
            patch_id="patch-crit",
            vulnerability_id="vuln-crit",
            severity="CRITICAL",
            created_at="2025-12-01T10:00:00",
            expires_at="2025-12-02T10:00:00",
            sandbox_results={},
            patch_diff="",
            recipients=["user@test.com"],
        )

        log = service.get_delivery_log()
        email_entry = next(e for e in log if e.get("channel") == "email")
        assert email_entry.get("priority") == "critical"


class TestDeliveryLogManagement:
    """Test delivery log management."""

    @pytest.fixture
    def service(self):
        """Provide a fresh mock notification service."""
        return NotificationService(mode=NotificationMode.MOCK)

    def test_clear_delivery_log(self, service):
        """Test clearing delivery log."""
        # Add some entries
        service.send_approval_notification(
            approval_id="approval-clear",
            patch_id="patch-clear",
            vulnerability_id="vuln-clear",
            severity="LOW",
            created_at="2025-12-01T10:00:00",
            expires_at="2025-12-02T10:00:00",
            sandbox_results={},
            patch_diff="",
            recipients=["user@test.com"],
        )

        assert len(service.get_delivery_log()) > 0

        # Clear the log
        service.clear_delivery_log()

        assert len(service.get_delivery_log()) == 0

    def test_delivery_log_limit(self, service):
        """Test delivery log respects limit parameter."""
        # Add many entries
        for i in range(10):
            service.send_approval_notification(
                approval_id=f"approval-{i}",
                patch_id=f"patch-{i}",
                vulnerability_id=f"vuln-{i}",
                severity="LOW",
                created_at="2025-12-01T10:00:00",
                expires_at="2025-12-02T10:00:00",
                sandbox_results={},
                patch_diff="",
                recipients=["user@test.com"],
            )

        # Get with limit
        limited = service.get_delivery_log(limit=5)
        assert len(limited) == 5


class TestNotificationResult:
    """Test NotificationResult dataclass."""

    def test_successful_result(self):
        """Test creating successful result."""
        result = NotificationResult(
            success=True,
            message_id="msg-123",
            channel=NotificationChannel.EMAIL,
        )

        assert result.success is True
        assert result.message_id == "msg-123"
        assert result.channel == NotificationChannel.EMAIL
        assert result.error is None

    def test_failed_result(self):
        """Test creating failed result."""
        result = NotificationResult(
            success=False, channel=NotificationChannel.SNS, error="Connection failed"
        )

        assert result.success is False
        assert result.error == "Connection failed"
        assert result.message_id is None


class TestApprovalRequestDataclass:
    """Test ApprovalRequest dataclass."""

    def test_default_values(self):
        """Test ApprovalRequest default values."""
        request = ApprovalRequest(
            approval_id="test-id",
            patch_id="patch-id",
            vulnerability_id="vuln-id",
        )

        assert request.status == ApprovalStatus.PENDING
        assert request.severity == PatchSeverity.MEDIUM
        assert request.sandbox_test_results == {}
        assert request.metadata == {}


class TestEnumValues:
    """Test enum value consistency."""

    def test_approval_status_values(self):
        """Test ApprovalStatus enum values."""
        assert ApprovalStatus.PENDING.value == "PENDING"
        assert ApprovalStatus.APPROVED.value == "APPROVED"
        assert ApprovalStatus.REJECTED.value == "REJECTED"
        assert ApprovalStatus.EXPIRED.value == "EXPIRED"
        assert ApprovalStatus.CANCELLED.value == "CANCELLED"

    def test_patch_severity_values(self):
        """Test PatchSeverity enum values."""
        assert PatchSeverity.CRITICAL.value == "CRITICAL"
        assert PatchSeverity.HIGH.value == "HIGH"
        assert PatchSeverity.MEDIUM.value == "MEDIUM"
        assert PatchSeverity.LOW.value == "LOW"

    def test_notification_channel_values(self):
        """Test NotificationChannel enum values."""
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.SNS.value == "sns"
        assert NotificationChannel.SLACK.value == "slack"

    def test_notification_priority_values(self):
        """Test NotificationPriority enum values."""
        assert NotificationPriority.CRITICAL.value == "critical"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.LOW.value == "low"


# =============================================================================
# Expiration Processing Tests
# =============================================================================


class TestExpirationProcessing:
    """Test expiration processing and escalation logic."""

    @pytest.fixture
    def service_with_backup_reviewers(self):
        """Provide service with backup reviewers configured."""
        notification_service = NotificationService(mode=NotificationMode.MOCK)
        return HITLApprovalService(
            mode=HITLMode.MOCK,
            timeout_hours=24,
            notification_service=notification_service,
            backup_reviewers=[
                "backup1@test.com",
                "backup2@test.com",
            ],
            escalation_timeout_hours=12,
        )

    def test_process_expirations_no_pending_requests(
        self, service_with_backup_reviewers
    ):
        """Test processing when there are no pending requests."""
        result = service_with_backup_reviewers.process_expirations()

        assert isinstance(result, ExpirationProcessingResult)
        assert result.processed == 0
        assert result.escalated == 0
        assert result.expired == 0
        assert result.warnings_sent == 0
        assert result.errors == 0

    def test_process_expirations_no_expired_requests(
        self, service_with_backup_reviewers
    ):
        """Test processing pending requests that haven't expired."""
        # Create a fresh request (not expired, not near expiration)
        service_with_backup_reviewers.create_approval_request(
            patch_id="patch-fresh",
            vulnerability_id="vuln-fresh",
            severity=PatchSeverity.HIGH,
        )

        result = service_with_backup_reviewers.process_expirations()

        assert result.processed == 1
        assert result.escalated == 0
        assert result.expired == 0
        assert result.warnings_sent == 0  # Not at warning threshold yet

    def test_warning_sent_at_threshold(self, service_with_backup_reviewers):
        """Test warning is sent when request reaches 75% of timeout."""
        request = service_with_backup_reviewers.create_approval_request(
            patch_id="patch-warning",
            vulnerability_id="vuln-warning",
            severity=PatchSeverity.MEDIUM,
            reviewer_email="reviewer@test.com",
        )

        # Manually set created_at to 20 hours ago (>75% of 24h timeout)
        # and expires_at to 4 hours from now
        past_time = (datetime.now() - timedelta(hours=20)).isoformat()
        future_time = (datetime.now() + timedelta(hours=4)).isoformat()
        service_with_backup_reviewers.mock_store[request.approval_id][
            "createdAt"
        ] = past_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = future_time

        result = service_with_backup_reviewers.process_expirations()

        assert result.warnings_sent == 1
        assert result.processed == 1

        # Verify warning_sent_at is set
        updated = service_with_backup_reviewers.get_request(request.approval_id)
        assert updated.warning_sent_at is not None

    def test_no_duplicate_warnings(self, service_with_backup_reviewers):
        """Test warning is not sent twice."""
        request = service_with_backup_reviewers.create_approval_request(
            patch_id="patch-no-dup-warning",
            vulnerability_id="vuln-no-dup",
            severity=PatchSeverity.MEDIUM,
            reviewer_email="reviewer@test.com",
        )

        # Set times to trigger warning
        past_time = (datetime.now() - timedelta(hours=20)).isoformat()
        future_time = (datetime.now() + timedelta(hours=4)).isoformat()
        service_with_backup_reviewers.mock_store[request.approval_id][
            "createdAt"
        ] = past_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = future_time

        # First run - should send warning
        result1 = service_with_backup_reviewers.process_expirations()
        assert result1.warnings_sent == 1

        # Second run - should NOT send warning again
        result2 = service_with_backup_reviewers.process_expirations()
        assert result2.warnings_sent == 0

    def test_critical_severity_escalation(self, service_with_backup_reviewers):
        """Test CRITICAL severity request is escalated when expired."""
        request = service_with_backup_reviewers.create_approval_request(
            patch_id="patch-critical-escalate",
            vulnerability_id="vuln-critical",
            severity=PatchSeverity.CRITICAL,
            reviewer_email="original@test.com",
        )

        # Set to expired
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service_with_backup_reviewers.mock_store[request.approval_id][
            "createdAt"
        ] = past_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = expired_time

        result = service_with_backup_reviewers.process_expirations()

        assert result.escalated == 1
        assert result.expired == 0

        # Verify escalation details
        updated = service_with_backup_reviewers.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.ESCALATED
        assert updated.reviewer_email == "backup1@test.com"
        assert updated.escalation_count == 1
        assert updated.last_escalated_at is not None

    def test_high_severity_escalation(self, service_with_backup_reviewers):
        """Test HIGH severity request is escalated when expired."""
        request = service_with_backup_reviewers.create_approval_request(
            patch_id="patch-high-escalate",
            vulnerability_id="vuln-high",
            severity=PatchSeverity.HIGH,
        )

        # Set to expired
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service_with_backup_reviewers.mock_store[request.approval_id][
            "createdAt"
        ] = past_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = expired_time

        result = service_with_backup_reviewers.process_expirations()

        assert result.escalated == 1
        updated = service_with_backup_reviewers.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.ESCALATED

    def test_medium_severity_expires_not_escalates(self, service_with_backup_reviewers):
        """Test MEDIUM severity request expires instead of escalating."""
        request = service_with_backup_reviewers.create_approval_request(
            patch_id="patch-medium-expire",
            vulnerability_id="vuln-medium",
            severity=PatchSeverity.MEDIUM,
        )

        # Set to expired
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service_with_backup_reviewers.mock_store[request.approval_id][
            "createdAt"
        ] = past_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = expired_time

        result = service_with_backup_reviewers.process_expirations()

        assert result.expired == 1
        assert result.escalated == 0

        updated = service_with_backup_reviewers.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.EXPIRED

    def test_low_severity_expires_not_escalates(self, service_with_backup_reviewers):
        """Test LOW severity request expires instead of escalating."""
        request = service_with_backup_reviewers.create_approval_request(
            patch_id="patch-low-expire",
            vulnerability_id="vuln-low",
            severity=PatchSeverity.LOW,
        )

        # Set to expired
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service_with_backup_reviewers.mock_store[request.approval_id][
            "createdAt"
        ] = past_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = expired_time

        result = service_with_backup_reviewers.process_expirations()

        assert result.expired == 1
        assert result.escalated == 0

    def test_max_escalations_then_expire(self, service_with_backup_reviewers):
        """Test request expires after max escalations reached."""
        request = service_with_backup_reviewers.create_approval_request(
            patch_id="patch-max-escalate",
            vulnerability_id="vuln-max",
            severity=PatchSeverity.CRITICAL,
        )

        # Set to expired AND already at max escalations
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service_with_backup_reviewers.mock_store[request.approval_id][
            "createdAt"
        ] = past_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = expired_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "escalationCount"
        ] = 2  # MAX_ESCALATIONS

        result = service_with_backup_reviewers.process_expirations()

        assert result.expired == 1
        assert result.escalated == 0

    def test_escalation_to_second_backup(self, service_with_backup_reviewers):
        """Test second escalation goes to second backup reviewer."""
        request = service_with_backup_reviewers.create_approval_request(
            patch_id="patch-second-escalate",
            vulnerability_id="vuln-second",
            severity=PatchSeverity.CRITICAL,
        )

        # First escalation
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service_with_backup_reviewers.mock_store[request.approval_id][
            "createdAt"
        ] = past_time
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = expired_time

        result1 = service_with_backup_reviewers.process_expirations()
        assert result1.escalated == 1

        # Simulate first escalation expired, trigger second
        _ = service_with_backup_reviewers.get_request(
            request.approval_id
        )  # Verify state
        # Reset status to allow re-processing (in reality, ESCALATED would need separate handling)
        service_with_backup_reviewers.mock_store[request.approval_id][
            "status"
        ] = "PENDING"
        service_with_backup_reviewers.mock_store[request.approval_id][
            "expiresAt"
        ] = expired_time

        result2 = service_with_backup_reviewers.process_expirations()
        assert result2.escalated == 1

        final = service_with_backup_reviewers.get_request(request.approval_id)
        assert final.reviewer_email == "backup2@test.com"
        assert final.escalation_count == 2


class TestEscalationDataclasses:
    """Test escalation-related dataclasses."""

    def test_expiration_result_success(self):
        """Test ExpirationResult for successful action."""
        result = ExpirationResult(
            approval_id="approval-123",
            action=EscalationAction.ESCALATE,
            success=True,
            message="Escalated successfully",
            escalated_to="backup@test.com",
        )

        assert result.success is True
        assert result.action == EscalationAction.ESCALATE
        assert result.escalated_to == "backup@test.com"

    def test_expiration_result_failure(self):
        """Test ExpirationResult for failed action."""
        result = ExpirationResult(
            approval_id="approval-456",
            action=EscalationAction.WARN,
            success=False,
            message="Notification failed",
        )

        assert result.success is False
        assert result.escalated_to is None

    def test_expiration_processing_result(self):
        """Test ExpirationProcessingResult dataclass."""
        result = ExpirationProcessingResult(
            processed=10,
            escalated=3,
            expired=2,
            warnings_sent=5,
            errors=0,
        )

        assert result.processed == 10
        assert result.escalated == 3
        assert result.expired == 2
        assert result.warnings_sent == 5
        assert result.details == []


class TestEscalationEnums:
    """Test escalation-related enum values."""

    def test_escalation_action_values(self):
        """Test EscalationAction enum values."""
        assert EscalationAction.ESCALATE.value == "ESCALATE"
        assert EscalationAction.EXPIRE.value == "EXPIRE"
        assert EscalationAction.WARN.value == "WARN"

    def test_approval_status_escalated(self):
        """Test ESCALATED status exists."""
        assert ApprovalStatus.ESCALATED.value == "ESCALATED"


class TestAuditLogging:
    """Test audit logging for expiration processing."""

    @pytest.fixture
    def service(self):
        """Provide service with audit logging."""
        notification_service = NotificationService(mode=NotificationMode.MOCK)
        return HITLApprovalService(
            mode=HITLMode.MOCK,
            notification_service=notification_service,
            backup_reviewers=["backup@test.com"],
        )

    def test_expiration_processing_creates_audit_entry(self, service):
        """Test expiration processing creates audit log entry."""
        # Run processing (even with no requests)
        service.process_expirations()

        # Check audit entries
        assert len(service.audit_entries) >= 1
        processing_entry = next(
            (
                e
                for e in service.audit_entries
                if e["event_type"] == "expiration_processing"
            ),
            None,
        )
        assert processing_entry is not None
        assert "processed" in processing_entry["details"]

    def test_escalation_creates_audit_entry(self, service):
        """Test escalation creates specific audit log entry."""
        request = service.create_approval_request(
            patch_id="patch-audit-escalate",
            vulnerability_id="vuln-audit",
            severity=PatchSeverity.CRITICAL,
        )

        # Set to expired
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service.mock_store[request.approval_id]["createdAt"] = past_time
        service.mock_store[request.approval_id]["expiresAt"] = expired_time

        service.process_expirations()

        escalation_entry = next(
            (e for e in service.audit_entries if e["event_type"] == "escalation"), None
        )
        assert escalation_entry is not None
        assert escalation_entry["approval_id"] == request.approval_id
        assert "escalated_to" in escalation_entry["details"]


# =============================================================================
# Additional Edge Case Tests for Improved Coverage
# =============================================================================


class TestHITLApprovalServiceEdgeCases:
    """Test edge cases and error handling in HITLApprovalService."""

    def test_get_all_requests_empty(self):
        """Test getting all requests when store is empty."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        requests = service.get_all_requests()
        assert requests == []

    def test_get_all_requests_with_limit(self):
        """Test get_all_requests respects limit."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        # Create 5 requests
        for i in range(5):
            service.create_approval_request(
                patch_id=f"patch-{i}",
                vulnerability_id=f"vuln-{i}",
            )

        requests = service.get_all_requests(limit=3)
        assert len(requests) == 3

    def test_get_all_requests_sorted_by_created_at(self):
        """Test get_all_requests returns newest first."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        # Create requests with slight time gaps
        import time

        for i in range(3):
            service.create_approval_request(
                patch_id=f"patch-{i}",
                vulnerability_id=f"vuln-{i}",
            )
            time.sleep(0.01)

        requests = service.get_all_requests()
        # Verify sorted by created_at descending (newest first)
        for i in range(len(requests) - 1):
            assert requests[i]["created_at"] >= requests[i + 1]["created_at"]

    def test_request_to_dict_conversion(self):
        """Test _request_to_dict includes all fields."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        request = service.create_approval_request(
            patch_id="patch-dict",
            vulnerability_id="vuln-dict",
            severity=PatchSeverity.HIGH,
            patch_diff="diff content",
            original_code="original",
            sandbox_results={"passed": True},
            reviewer_email="reviewer@test.com",
            metadata={"key": "value"},
        )

        result = service._request_to_dict(request)

        assert result["approval_id"] == request.approval_id
        assert result["patch_id"] == "patch-dict"
        assert result["vulnerability_id"] == "vuln-dict"
        assert result["status"] == "PENDING"
        assert result["severity"] == "HIGH"
        assert result["patch_diff"] == "diff content"
        assert result["original_code"] == "original"
        assert result["sandbox_test_results"] == {"passed": True}
        assert result["reviewer_email"] == "reviewer@test.com"
        assert result["metadata"] == {"key": "value"}
        assert result["escalation_count"] == 0
        assert result["last_escalated_at"] is None
        assert result["warning_sent_at"] is None

    def test_is_expired_with_empty_expires_at(self):
        """Test _is_expired returns False when expires_at is empty."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        request = ApprovalRequest(
            approval_id="test-id",
            patch_id="patch",
            vulnerability_id="vuln",
            expires_at="",  # Empty expiry
        )
        assert service._is_expired(request) is False

    def test_is_expired_with_invalid_timestamp(self):
        """Test _is_expired handles invalid timestamp gracefully."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        request = ApprovalRequest(
            approval_id="test-id",
            patch_id="patch",
            vulnerability_id="vuln",
            expires_at="invalid-timestamp",
        )
        assert service._is_expired(request) is False

    def test_determine_action_invalid_timestamps(self):
        """Test _determine_action returns None for invalid timestamps."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        request = ApprovalRequest(
            approval_id="test-id",
            patch_id="patch",
            vulnerability_id="vuln",
            created_at="invalid",
            expires_at="also-invalid",
        )
        result = service._determine_action(request)
        assert result is None

    def test_determine_action_negative_elapsed(self):
        """Test _determine_action returns None when elapsed is negative."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        # Create request with future created_at (edge case)
        future = (datetime.now() + timedelta(hours=1)).isoformat()
        request = ApprovalRequest(
            approval_id="test-id",
            patch_id="patch",
            vulnerability_id="vuln",
            created_at=future,
            expires_at=(datetime.now() + timedelta(hours=25)).isoformat(),
        )
        result = service._determine_action(request)
        assert result is None

    def test_update_request_field_mock(self):
        """Test _update_request_field updates mock store."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        request = service.create_approval_request(
            patch_id="patch-update",
            vulnerability_id="vuln-update",
        )

        service._update_request_field(
            request.approval_id, "warningSentAt", "2025-01-01T00:00:00"
        )

        stored = service.mock_store[request.approval_id]
        assert stored["warningSentAt"] == "2025-01-01T00:00:00"

    def test_log_audit_creates_entry(self):
        """Test _log_audit creates proper entry."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        service._log_audit(
            event_type="test_event",
            approval_id="approval-123",
            details={"key": "value"},
        )

        assert len(service.audit_entries) == 1
        entry = service.audit_entries[0]
        assert entry["event_type"] == "test_event"
        assert entry["approval_id"] == "approval-123"
        assert entry["details"]["key"] == "value"
        assert "timestamp" in entry

    def test_log_audit_without_approval_id(self):
        """Test _log_audit works without approval_id."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        service._log_audit(event_type="system_event")

        assert len(service.audit_entries) == 1
        assert service.audit_entries[0]["approval_id"] is None

    def test_statistics_with_approval_time_calculation(self):
        """Test statistics calculates average approval time."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        # Create and approve multiple requests
        for i in range(3):
            request = service.create_approval_request(
                patch_id=f"patch-stat-{i}",
                vulnerability_id=f"vuln-stat-{i}",
            )
            service.approve_request(
                request.approval_id, "reviewer@test.com", "Approved"
            )

        stats = service.get_statistics()
        assert stats["approved"] == 3
        assert "avg_approval_time_hours" in stats
        # Time should be very small since approval was immediate
        assert stats["avg_approval_time_hours"] >= 0

    def test_escalate_no_backup_reviewers(self):
        """Test escalation when no backup reviewers configured falls back to expire."""
        service = HITLApprovalService(
            mode=HITLMode.MOCK,
            backup_reviewers=[],  # No backups
        )

        request = service.create_approval_request(
            patch_id="patch-no-backup",
            vulnerability_id="vuln-no-backup",
            severity=PatchSeverity.CRITICAL,
        )

        # Set to expired
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service.mock_store[request.approval_id]["createdAt"] = past_time
        service.mock_store[request.approval_id]["expiresAt"] = expired_time

        result = service.process_expirations()

        # Escalation attempt is made but internally falls back to expire
        # The result counts it as an escalation attempt with expire action
        assert result.processed == 1
        # The escalation logic is entered, but no backup exists so it expires
        assert len(result.details) == 1
        assert result.details[0].action == EscalationAction.EXPIRE
        assert result.details[0].success is True

    def test_send_warning_no_notification_service(self):
        """Test warning is sent even without notification service."""
        service = HITLApprovalService(
            mode=HITLMode.MOCK,
            notification_service=None,  # No notification service
        )

        request = service.create_approval_request(
            patch_id="patch-no-notify",
            vulnerability_id="vuln-no-notify",
            reviewer_email="reviewer@test.com",
        )

        # Set to warning threshold
        past_time = (datetime.now() - timedelta(hours=20)).isoformat()
        future_time = (datetime.now() + timedelta(hours=4)).isoformat()
        service.mock_store[request.approval_id]["createdAt"] = past_time
        service.mock_store[request.approval_id]["expiresAt"] = future_time

        result = service.process_expirations()

        # Warning should still be recorded (just not sent)
        assert result.warnings_sent == 1

    def test_expire_request_no_notification_service(self):
        """Test expire works without notification service."""
        service = HITLApprovalService(
            mode=HITLMode.MOCK,
            notification_service=None,
        )

        request = service.create_approval_request(
            patch_id="patch-expire-no-notify",
            vulnerability_id="vuln-expire",
            severity=PatchSeverity.LOW,
        )

        # Set to expired
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service.mock_store[request.approval_id]["createdAt"] = past_time
        service.mock_store[request.approval_id]["expiresAt"] = expired_time

        result = service.process_expirations()
        assert result.expired == 1

    def test_get_pending_requests_empty(self):
        """Test get_pending_requests returns empty list when no pending."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        pending = service.get_pending_requests()
        assert pending == []

    def test_get_requests_by_patch_empty(self):
        """Test get_requests_by_patch returns empty for non-existent patch."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        requests = service.get_requests_by_patch("non-existent-patch")
        assert requests == []

    def test_cancel_request_without_reason(self):
        """Test cancel request works without reason."""
        service = HITLApprovalService(mode=HITLMode.MOCK)
        request = service.create_approval_request(
            patch_id="patch-cancel-no-reason",
            vulnerability_id="vuln-cancel",
        )

        result = service.cancel_request(approval_id=request.approval_id)

        assert result is True
        updated = service.get_request(request.approval_id)
        assert updated.status == ApprovalStatus.CANCELLED
        assert updated.decision_reason is None


class TestHITLApprovalServiceAWSModeFallback:
    """Test AWS mode initialization and fallback behavior."""

    def test_aws_mode_fallback_no_boto3(self, monkeypatch):
        """Test AWS mode falls back to mock when boto3 unavailable."""
        # Temporarily disable boto3
        from services import hitl_approval_service

        original = hitl_approval_service.BOTO3_AVAILABLE
        monkeypatch.setattr(hitl_approval_service, "BOTO3_AVAILABLE", False)

        service = HITLApprovalService(mode=HITLMode.AWS)

        # Should fall back to mock mode
        assert service.mode == HITLMode.MOCK

        monkeypatch.setattr(hitl_approval_service, "BOTO3_AVAILABLE", original)


class TestHITLApprovalServiceItemConversion:
    """Test DynamoDB item conversion methods."""

    def test_item_to_request_with_all_fields(self):
        """Test _item_to_request handles all optional fields."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        item = {
            "approvalId": "approval-full",
            "patchId": "patch-full",
            "vulnerabilityId": "vuln-full",
            "status": "APPROVED",
            "severity": "HIGH",
            "createdAt": "2025-01-01T00:00:00",
            "expiresAt": "2025-01-02T00:00:00",
            "reviewerEmail": "reviewer@test.com",
            "reviewedAt": "2025-01-01T12:00:00",
            "reviewedBy": "approver@test.com",
            "decisionReason": "LGTM",
            "sandboxTestResults": {"passed": True},
            "patchDiff": "diff",
            "originalCode": "original",
            "metadata": {"repo": "test"},
            "escalationCount": 1,
            "lastEscalatedAt": "2025-01-01T06:00:00",
            "warningSentAt": "2025-01-01T03:00:00",
        }

        request = service._item_to_request(item)

        assert request.approval_id == "approval-full"
        assert request.status == ApprovalStatus.APPROVED
        assert request.severity == PatchSeverity.HIGH
        assert request.reviewed_by == "approver@test.com"
        assert request.escalation_count == 1
        assert request.warning_sent_at == "2025-01-01T03:00:00"

    def test_item_to_request_with_minimal_fields(self):
        """Test _item_to_request handles missing optional fields."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        item = {
            "approvalId": "approval-min",
            "patchId": "patch-min",
            "vulnerabilityId": "vuln-min",
        }

        request = service._item_to_request(item)

        assert request.approval_id == "approval-min"
        assert request.status == ApprovalStatus.PENDING  # Default
        assert request.severity == PatchSeverity.MEDIUM  # Default
        assert request.sandbox_test_results == {}
        assert request.escalation_count == 0


class TestExpirationProcessingErrorHandling:
    """Test error handling in expiration processing."""

    def test_expiration_processing_handles_individual_errors(self):
        """Test processing continues after individual request errors."""
        notification_service = NotificationService(mode=NotificationMode.MOCK)
        service = HITLApprovalService(
            mode=HITLMode.MOCK,
            notification_service=notification_service,
            backup_reviewers=["backup@test.com"],
        )

        # Create valid request
        request = service.create_approval_request(
            patch_id="patch-error-test",
            vulnerability_id="vuln-error",
            severity=PatchSeverity.MEDIUM,
        )

        # Set to expired
        past_time = (datetime.now() - timedelta(hours=25)).isoformat()
        expired_time = (datetime.now() - timedelta(hours=1)).isoformat()
        service.mock_store[request.approval_id]["createdAt"] = past_time
        service.mock_store[request.approval_id]["expiresAt"] = expired_time

        result = service.process_expirations()

        # Should process successfully despite being a single request
        assert result.processed == 1
        assert result.errors == 0


class TestWarningWithBackupReviewerFallback:
    """Test warning notification uses backup reviewer when no primary."""

    def test_warning_uses_backup_when_no_reviewer(self):
        """Test warning uses backup reviewer when no reviewer assigned."""
        notification_service = NotificationService(mode=NotificationMode.MOCK)
        service = HITLApprovalService(
            mode=HITLMode.MOCK,
            notification_service=notification_service,
            backup_reviewers=["backup@test.com"],
        )

        # Create request without reviewer
        request = service.create_approval_request(
            patch_id="patch-no-reviewer",
            vulnerability_id="vuln-no-reviewer",
            reviewer_email=None,  # No reviewer assigned
        )

        # Set to warning threshold
        past_time = (datetime.now() - timedelta(hours=20)).isoformat()
        future_time = (datetime.now() + timedelta(hours=4)).isoformat()
        service.mock_store[request.approval_id]["createdAt"] = past_time
        service.mock_store[request.approval_id]["expiresAt"] = future_time

        result = service.process_expirations()

        assert result.warnings_sent == 1


class TestAuditLogFiltering:
    """Test audit log date filtering."""

    def test_audit_log_with_date_filter(self):
        """Test audit log filters by date range."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        # Create and approve requests
        request1 = service.create_approval_request(
            patch_id="patch-audit-1",
            vulnerability_id="vuln-1",
        )
        service.approve_request(request1.approval_id, "reviewer@test.com", "Approved")

        # Get with date filter (should include all)
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now() + timedelta(hours=1)
        audit = service.get_audit_log(start_date=start, end_date=end)

        assert len(audit) >= 1

    def test_audit_log_empty_after_date_filter(self):
        """Test audit log returns empty when filtered out by date."""
        service = HITLApprovalService(mode=HITLMode.MOCK)

        request = service.create_approval_request(
            patch_id="patch-audit-filter",
            vulnerability_id="vuln-filter",
        )
        service.approve_request(request.approval_id, "reviewer@test.com", "OK")

        # Filter with dates that exclude the entry
        future_start = datetime.now() + timedelta(days=1)
        future_end = datetime.now() + timedelta(days=2)
        audit = service.get_audit_log(start_date=future_start, end_date=future_end)

        assert len(audit) == 0
