"""
Tests for Compliance Audit Trail Service.

Tests audit event logging, persistence, and reporting.
"""

import platform

import pytest

# These tests require pytest-forked for isolation due to global service state.
# On Linux (CI), mock patches don't apply correctly without forked mode.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services.compliance_audit_service import (
    AuditEvent,
    AuditEventType,
    ComplianceAuditService,
    get_audit_service,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def audit_service():
    """Create audit service instance."""
    return ComplianceAuditService(
        profile_name="CMMC_LEVEL_3",
        profile_version="1.0.0",
        enable_cloudwatch=False,
        enable_dynamodb=False,
    )


@pytest.fixture
def audit_service_with_logging():
    """Create audit service with logging enabled."""
    return ComplianceAuditService(
        profile_name="CMMC_LEVEL_3",
        profile_version="1.0.0",
        enable_cloudwatch=True,
        enable_dynamodb=True,
    )


@pytest.fixture
def reset_global_service():
    """Reset global audit service after test."""
    import src.services.compliance_audit_service as audit_module

    original = audit_module._global_audit_service
    yield
    audit_module._global_audit_service = original


# ============================================================================
# AuditEventType Tests
# ============================================================================


class TestAuditEventType:
    """Test AuditEventType enum."""

    def test_scan_initiated(self):
        """Test SCAN_INITIATED value."""
        assert AuditEventType.SCAN_INITIATED.value == "SCAN_INITIATED"

    def test_scan_completed(self):
        """Test SCAN_COMPLETED value."""
        assert AuditEventType.SCAN_COMPLETED.value == "SCAN_COMPLETED"

    def test_file_scanned(self):
        """Test FILE_SCANNED value."""
        assert AuditEventType.FILE_SCANNED.value == "FILE_SCANNED"

    def test_file_skipped(self):
        """Test FILE_SKIPPED value."""
        assert AuditEventType.FILE_SKIPPED.value == "FILE_SKIPPED"

    def test_finding_detected(self):
        """Test FINDING_DETECTED value."""
        assert AuditEventType.FINDING_DETECTED.value == "FINDING_DETECTED"

    def test_deployment_blocked(self):
        """Test DEPLOYMENT_BLOCKED value."""
        assert AuditEventType.DEPLOYMENT_BLOCKED.value == "DEPLOYMENT_BLOCKED"

    def test_deployment_approved(self):
        """Test DEPLOYMENT_APPROVED value."""
        assert AuditEventType.DEPLOYMENT_APPROVED.value == "DEPLOYMENT_APPROVED"

    def test_manual_review_required(self):
        """Test MANUAL_REVIEW_REQUIRED value."""
        assert AuditEventType.MANUAL_REVIEW_REQUIRED.value == "MANUAL_REVIEW_REQUIRED"

    def test_manual_review_approved(self):
        """Test MANUAL_REVIEW_APPROVED value."""
        assert AuditEventType.MANUAL_REVIEW_APPROVED.value == "MANUAL_REVIEW_APPROVED"

    def test_manual_review_rejected(self):
        """Test MANUAL_REVIEW_REJECTED value."""
        assert AuditEventType.MANUAL_REVIEW_REJECTED.value == "MANUAL_REVIEW_REJECTED"

    def test_profile_loaded(self):
        """Test PROFILE_LOADED value."""
        assert AuditEventType.PROFILE_LOADED.value == "PROFILE_LOADED"

    def test_profile_override_applied(self):
        """Test PROFILE_OVERRIDE_APPLIED value."""
        assert (
            AuditEventType.PROFILE_OVERRIDE_APPLIED.value == "PROFILE_OVERRIDE_APPLIED"
        )

    def test_compliance_violation(self):
        """Test COMPLIANCE_VIOLATION value."""
        assert AuditEventType.COMPLIANCE_VIOLATION.value == "COMPLIANCE_VIOLATION"


# ============================================================================
# AuditEvent Tests
# ============================================================================


class TestAuditEvent:
    """Test AuditEvent dataclass."""

    def test_create_event(self):
        """Test creating an audit event."""
        now = datetime.now(timezone.utc)
        event = AuditEvent(
            event_id="audit-12345678",
            event_type=AuditEventType.SCAN_INITIATED,
            timestamp=now,
            profile_name="CMMC_LEVEL_3",
            profile_version="1.0.0",
            actor="test-agent",
            action="Started security scan",
        )
        assert event.event_id == "audit-12345678"
        assert event.event_type == AuditEventType.SCAN_INITIATED
        assert event.actor == "test-agent"

    def test_event_with_optional_fields(self):
        """Test event with optional fields."""
        event = AuditEvent(
            event_id="audit-12345678",
            event_type=AuditEventType.FINDING_DETECTED,
            timestamp=datetime.now(timezone.utc),
            profile_name="CMMC_LEVEL_3",
            profile_version="1.0.0",
            actor="scanner",
            action="Detected SQL injection",
            resource="src/api.py",
            metadata={"line": 42},
            compliance_controls=["SI-3.14.4"],
            result="CRITICAL",
        )
        assert event.resource == "src/api.py"
        assert event.metadata == {"line": 42}
        assert "SI-3.14.4" in event.compliance_controls

    def test_to_dict(self):
        """Test converting event to dictionary."""
        now = datetime.now(timezone.utc)
        event = AuditEvent(
            event_id="audit-12345678",
            event_type=AuditEventType.SCAN_COMPLETED,
            timestamp=now,
            profile_name="CMMC_LEVEL_3",
            profile_version="1.0.0",
            actor="scanner",
            action="Scan completed",
            result="SUCCESS",
        )
        event_dict = event.to_dict()

        assert event_dict["event_id"] == "audit-12345678"
        assert event_dict["event_type"] == "SCAN_COMPLETED"
        assert event_dict["timestamp"] == now.isoformat()
        assert event_dict["result"] == "SUCCESS"

    def test_to_cloudwatch_log(self):
        """Test formatting event for CloudWatch."""
        event = AuditEvent(
            event_id="audit-12345678",
            event_type=AuditEventType.PROFILE_LOADED,
            timestamp=datetime.now(timezone.utc),
            profile_name="CMMC_LEVEL_3",
            profile_version="1.0.0",
            actor="system",
            action="Loaded profile",
        )
        log = event.to_cloudwatch_log()

        # Should be valid JSON
        parsed = json.loads(log)
        assert parsed["event_id"] == "audit-12345678"
        assert parsed["event_type"] == "PROFILE_LOADED"


# ============================================================================
# ComplianceAuditService Initialization Tests
# ============================================================================


class TestComplianceAuditServiceInit:
    """Test ComplianceAuditService initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        service = ComplianceAuditService(
            profile_name="CMMC_LEVEL_3",
            profile_version="1.0.0",
        )
        assert service.profile_name == "CMMC_LEVEL_3"
        assert service.profile_version == "1.0.0"
        assert service.enable_cloudwatch is True
        assert service.enable_dynamodb is True

    def test_init_with_options(self):
        """Test initialization with custom options."""
        service = ComplianceAuditService(
            profile_name="SOX",
            profile_version="2.0.0",
            enable_cloudwatch=False,
            enable_dynamodb=False,
        )
        assert service.profile_name == "SOX"
        assert service.enable_cloudwatch is False
        assert service.enable_dynamodb is False


# ============================================================================
# Event Logging Tests
# ============================================================================


class TestEventLogging:
    """Test event logging methods."""

    def test_log_event_basic(self, audit_service):
        """Test basic event logging."""
        event = audit_service.log_event(
            event_type=AuditEventType.SCAN_INITIATED,
            actor="test-agent",
            action="Started scan",
        )
        assert event.event_id.startswith("audit-")
        assert event.event_type == AuditEventType.SCAN_INITIATED
        assert event.actor == "test-agent"
        assert event.profile_name == "CMMC_LEVEL_3"

    def test_log_event_with_metadata(self, audit_service):
        """Test event logging with metadata."""
        event = audit_service.log_event(
            event_type=AuditEventType.FINDING_DETECTED,
            actor="scanner",
            action="Found vulnerability",
            resource="src/main.py",
            metadata={"severity": "HIGH", "cwe": "CWE-89"},
            compliance_controls=["SI-3.14.4"],
            result="DETECTED",
        )
        assert event.resource == "src/main.py"
        assert event.metadata["severity"] == "HIGH"
        assert "SI-3.14.4" in event.compliance_controls

    def test_log_scan_initiated(self, audit_service):
        """Test logging scan initiation."""
        event = audit_service.log_scan_initiated(
            actor="ci-pipeline",
            files_to_scan=["src/a.py", "src/b.py", "src/c.py"],
            metadata={"branch": "main"},
        )
        assert event.event_type == AuditEventType.SCAN_INITIATED
        assert event.metadata["file_count"] == 3
        assert "CA-3.12.4" in event.compliance_controls
        assert event.result == "INITIATED"

    def test_log_scan_completed(self, audit_service):
        """Test logging scan completion."""
        event = audit_service.log_scan_completed(
            actor="ci-pipeline",
            files_scanned=100,
            findings_count=5,
            critical_count=1,
            high_count=2,
        )
        assert event.event_type == AuditEventType.SCAN_COMPLETED
        assert event.metadata["files_scanned"] == 100
        assert event.metadata["findings_count"] == 5
        assert event.metadata["critical_count"] == 1

    def test_log_file_skipped(self, audit_service):
        """Test logging file skip."""
        event = audit_service.log_file_skipped(
            actor="scanner",
            file_path="archive/old.py",
            reason="Excluded by pattern",
        )
        assert event.event_type == AuditEventType.FILE_SKIPPED
        assert event.resource == "archive/old.py"
        assert event.metadata["skip_reason"] == "Excluded by pattern"

    def test_log_deployment_blocked(self, audit_service):
        """Test logging deployment block."""
        event = audit_service.log_deployment_decision(
            actor="ci-pipeline",
            should_block=True,
            reason="Critical vulnerability found",
        )
        assert event.event_type == AuditEventType.DEPLOYMENT_BLOCKED
        assert event.result == "BLOCKED"
        assert "CM-3.4.7" in event.compliance_controls

    def test_log_deployment_approved(self, audit_service):
        """Test logging deployment approval."""
        event = audit_service.log_deployment_decision(
            actor="ci-pipeline",
            should_block=False,
            reason="No blocking issues",
        )
        assert event.event_type == AuditEventType.DEPLOYMENT_APPROVED
        assert event.result == "APPROVED"

    def test_log_manual_review_required(self, audit_service):
        """Test logging manual review requirement."""
        event = audit_service.log_manual_review_required(
            actor="security-scanner",
            reasons=["IAM policy change", "Network config change"],
            affected_files=["iam.yaml", "vpc.yaml"],
        )
        assert event.event_type == AuditEventType.MANUAL_REVIEW_REQUIRED
        assert event.metadata["review_reasons"] == [
            "IAM policy change",
            "Network config change",
        ]
        assert event.result == "PENDING_REVIEW"

    def test_log_manual_review_approved(self, audit_service):
        """Test logging manual review approval."""
        event = audit_service.log_manual_review_decision(
            actor="developer",
            approved=True,
            reviewer="security-lead",
            comments="Looks good",
        )
        assert event.event_type == AuditEventType.MANUAL_REVIEW_APPROVED
        assert event.metadata["reviewer"] == "security-lead"
        assert event.result == "APPROVED"

    def test_log_manual_review_rejected(self, audit_service):
        """Test logging manual review rejection."""
        event = audit_service.log_manual_review_decision(
            actor="developer",
            approved=False,
            reviewer="security-lead",
            comments="Needs more work",
        )
        assert event.event_type == AuditEventType.MANUAL_REVIEW_REJECTED
        assert event.result == "REJECTED"

    def test_log_profile_loaded(self, audit_service):
        """Test logging profile load."""
        event = audit_service.log_profile_loaded(
            actor="system",
            profile_display_name="CMMC Level 3 (Advanced)",
        )
        assert event.event_type == AuditEventType.PROFILE_LOADED
        assert event.result == "SUCCESS"

    def test_log_profile_override(self, audit_service):
        """Test logging profile override."""
        event = audit_service.log_profile_override(
            actor="admin",
            overrides={"scanning.scan_docs": False},
        )
        assert event.event_type == AuditEventType.PROFILE_OVERRIDE_APPLIED
        assert event.metadata["overrides"] == {"scanning.scan_docs": False}

    def test_log_compliance_violation(self, audit_service):
        """Test logging compliance violation."""
        event = audit_service.log_compliance_violation(
            actor="scanner",
            violation_type="Missing encryption",
            details="S3 bucket without encryption",
            affected_controls=["SC-3.13.8"],
        )
        assert event.event_type == AuditEventType.COMPLIANCE_VIOLATION
        assert event.metadata["violation_type"] == "Missing encryption"
        assert event.result == "VIOLATION"


# ============================================================================
# Buffer Management Tests
# ============================================================================


class TestBufferManagement:
    """Test event buffer management."""

    def test_buffer_accumulates_events(self, audit_service):
        """Test that events accumulate in buffer."""
        for i in range(5):
            audit_service.log_event(
                event_type=AuditEventType.FILE_SCANNED,
                actor="scanner",
                action=f"Scanned file {i}",
            )
        assert len(audit_service._event_buffer) == 5

    def test_buffer_auto_flushes(self, audit_service):
        """Test that buffer auto-flushes when full."""
        audit_service._buffer_size = 5  # Set smaller buffer for test

        for i in range(6):
            audit_service.log_event(
                event_type=AuditEventType.FILE_SCANNED,
                actor="scanner",
                action=f"Scanned file {i}",
            )

        # Buffer should have been flushed and contain only the 6th event
        assert len(audit_service._event_buffer) == 1

    def test_manual_flush(self, audit_service):
        """Test manual buffer flush."""
        audit_service.log_event(
            event_type=AuditEventType.SCAN_INITIATED,
            actor="scanner",
            action="Starting",
        )
        assert len(audit_service._event_buffer) == 1

        audit_service.flush()
        assert len(audit_service._event_buffer) == 0

    def test_flush_empty_buffer(self, audit_service):
        """Test flushing empty buffer."""
        # Should not raise
        audit_service.flush()
        assert len(audit_service._event_buffer) == 0


# ============================================================================
# Persistence Tests
# ============================================================================


class TestPersistence:
    """Test event persistence methods."""

    def test_write_to_cloudwatch(self, audit_service_with_logging):
        """Test writing to CloudWatch (logs to standard logger)."""
        event = AuditEvent(
            event_id="audit-test",
            event_type=AuditEventType.SCAN_COMPLETED,
            timestamp=datetime.now(timezone.utc),
            profile_name="CMMC_LEVEL_3",
            profile_version="1.0.0",
            actor="test",
            action="Test action",
        )
        # Should not raise
        audit_service_with_logging._write_to_cloudwatch([event])

    def test_write_to_dynamodb(self, audit_service_with_logging):
        """Test writing to DynamoDB (logs to standard logger)."""
        event = AuditEvent(
            event_id="audit-test",
            event_type=AuditEventType.SCAN_COMPLETED,
            timestamp=datetime.now(timezone.utc),
            profile_name="CMMC_LEVEL_3",
            profile_version="1.0.0",
            actor="test",
            action="Test action",
        )
        # Should not raise
        audit_service_with_logging._write_to_dynamodb([event])


# ============================================================================
# Query and Reporting Tests
# ============================================================================


class TestQueryAndReporting:
    """Test query and reporting methods."""

    def test_query_events(self, audit_service):
        """Test querying events."""
        events = audit_service.query_events(
            event_type=AuditEventType.SCAN_COMPLETED,
            actor="scanner",
            start_time=datetime.now(timezone.utc) - timedelta(days=7),
            end_time=datetime.now(timezone.utc),
            limit=100,
        )
        # Returns empty list in current implementation
        assert events == []

    def test_generate_compliance_report(self, audit_service):
        """Test generating compliance report."""
        start_time = datetime.now(timezone.utc) - timedelta(days=7)
        end_time = datetime.now(timezone.utc)

        report = audit_service.generate_compliance_report(
            start_time=start_time,
            end_time=end_time,
        )

        assert "report_period" in report
        assert report["profile"]["name"] == "CMMC_LEVEL_3"
        assert "event_summary" in report
        assert "total_events" in report
        assert "generated_at" in report


# ============================================================================
# Global Service Tests
# ============================================================================


class TestGlobalService:
    """Test global audit service functions."""

    @patch("src.services.compliance_audit_service._global_audit_service", None)
    def test_get_audit_service(self, reset_global_service):
        """Test getting global audit service."""
        service = get_audit_service()
        assert service is not None
        assert service.profile_name == "CMMC_LEVEL_3"

    @patch("src.services.compliance_audit_service._global_audit_service", None)
    def test_get_audit_service_custom_profile(self, reset_global_service):
        """Test getting global audit service with custom profile."""
        service = get_audit_service(profile_name="SOX", profile_version="2.0.0")
        assert service.profile_name == "SOX"
        assert service.profile_version == "2.0.0"


# ============================================================================
# Event ID Generation Tests
# ============================================================================


class TestEventIdGeneration:
    """Test event ID generation."""

    def test_unique_event_ids(self, audit_service):
        """Test that event IDs are unique."""
        event1 = audit_service.log_event(
            event_type=AuditEventType.SCAN_INITIATED,
            actor="test",
            action="First",
        )
        event2 = audit_service.log_event(
            event_type=AuditEventType.SCAN_INITIATED,
            actor="test",
            action="Second",
        )
        assert event1.event_id != event2.event_id

    def test_event_id_format(self, audit_service):
        """Test event ID format."""
        event = audit_service.log_event(
            event_type=AuditEventType.SCAN_INITIATED,
            actor="test",
            action="Test",
        )
        assert event.event_id.startswith("audit-")
        assert len(event.event_id) == 22  # "audit-" + 16 hex chars
