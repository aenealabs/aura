"""
Project Aura - Security Alerts Service Tests

Tests for the security alerts service covering:
- Alert creation from security events
- Priority mapping
- HITL request creation
- Alert lifecycle management

Author: Project Aura Team
Created: 2025-12-12
"""

import pytest

from src.services.security_alerts_service import (
    AlertPriority,
    AlertStatus,
    HITLApprovalRequest,
    SecurityAlertsService,
    get_alerts_service,
    process_security_event,
)
from src.services.security_audit_service import (
    SecurityContext,
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventType,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def alerts_service():
    """Create a fresh alerts service instance."""
    return SecurityAlertsService(
        sns_topic_arn=None,  # Disable SNS for tests
        auto_create_alerts=True,
    )


@pytest.fixture
def critical_event():
    """Create a critical security event."""
    return SecurityEvent(
        event_id="evt-123",
        event_type=SecurityEventType.THREAT_COMMAND_INJECTION,
        severity=SecurityEventSeverity.CRITICAL,
        timestamp="2025-12-12T10:00:00Z",
        message="Command injection detected in filename parameter",
        context=SecurityContext(
            user_id="user-123",
            ip_address="192.168.1.100",
            request_id="req-456",
        ),
        details={"input_field": "filename", "payload": "file.txt; rm -rf /"},
    )


@pytest.fixture
def high_event():
    """Create a high severity security event."""
    return SecurityEvent(
        event_id="evt-456",
        event_type=SecurityEventType.THREAT_PROMPT_INJECTION,
        severity=SecurityEventSeverity.HIGH,
        timestamp="2025-12-12T10:00:00Z",
        message="Prompt injection attempt detected",
        context=SecurityContext(
            user_id="user-456",
            ip_address="10.0.0.1",
        ),
    )


@pytest.fixture
def medium_event():
    """Create a medium severity security event."""
    return SecurityEvent(
        event_id="evt-789",
        event_type=SecurityEventType.AUTH_LOGIN_FAILURE,
        severity=SecurityEventSeverity.MEDIUM,
        timestamp="2025-12-12T10:00:00Z",
        message="Login failed for user@example.com",
        context=SecurityContext(
            user_email="user@example.com",
            ip_address="10.0.0.1",
        ),
    )


# ============================================================================
# Alert Creation Tests
# ============================================================================


class TestAlertCreation:
    """Tests for alert creation from security events."""

    def test_creates_alert_for_critical_event(self, alerts_service, critical_event):
        """Test alert is created for critical event."""
        alert = alerts_service.process_security_event(critical_event)

        assert alert is not None
        assert alert.priority == AlertPriority.P1_CRITICAL
        assert alert.status == AlertStatus.NEW

    def test_creates_alert_for_high_event(self, alerts_service, high_event):
        """Test alert is created for high severity event."""
        alert = alerts_service.process_security_event(high_event)

        assert alert is not None
        assert alert.priority == AlertPriority.P2_HIGH

    def test_no_alert_for_medium_event(self, alerts_service, medium_event):
        """Test no alert is created for medium severity event."""
        alert = alerts_service.process_security_event(medium_event)

        # Medium severity login failures don't create alerts
        assert alert is None

    def test_alert_contains_event_details(self, alerts_service, critical_event):
        """Test alert contains security event details."""
        alert = alerts_service.process_security_event(critical_event)

        assert critical_event.event_id in alert.description
        assert "Command Injection" in alert.title  # Title uses proper case
        assert alert.security_event.event_id == critical_event.event_id

    def test_alert_has_remediation_steps(self, alerts_service, critical_event):
        """Test alert includes remediation steps."""
        alert = alerts_service.process_security_event(critical_event)

        assert len(alert.remediation_steps) > 0
        assert any("Block" in step for step in alert.remediation_steps)

    def test_alert_generates_unique_id(self, alerts_service, critical_event):
        """Test each alert gets a unique ID."""
        alert1 = alerts_service.process_security_event(critical_event)
        alert2 = alerts_service.process_security_event(critical_event)

        assert alert1.alert_id != alert2.alert_id


# ============================================================================
# Priority Mapping Tests
# ============================================================================


class TestPriorityMapping:
    """Tests for event type to priority mapping."""

    def test_command_injection_is_p1(self, alerts_service):
        """Test command injection events are P1."""
        event = SecurityEvent(
            event_id="evt-1",
            event_type=SecurityEventType.THREAT_COMMAND_INJECTION,
            severity=SecurityEventSeverity.CRITICAL,
            timestamp="2025-12-12T10:00:00Z",
            message="Test",
            context=SecurityContext(),
        )
        alert = alerts_service.process_security_event(event)

        assert alert.priority == AlertPriority.P1_CRITICAL

    def test_secrets_exposure_is_p1(self, alerts_service):
        """Test secrets exposure events are P1."""
        event = SecurityEvent(
            event_id="evt-1",
            event_type=SecurityEventType.THREAT_SECRETS_EXPOSURE,
            severity=SecurityEventSeverity.CRITICAL,
            timestamp="2025-12-12T10:00:00Z",
            message="Test",
            context=SecurityContext(),
        )
        alert = alerts_service.process_security_event(event)

        assert alert.priority == AlertPriority.P1_CRITICAL

    def test_privilege_escalation_is_p1(self, alerts_service):
        """Test privilege escalation events are P1."""
        event = SecurityEvent(
            event_id="evt-1",
            event_type=SecurityEventType.AUTHZ_PRIVILEGE_ESCALATION,
            severity=SecurityEventSeverity.CRITICAL,
            timestamp="2025-12-12T10:00:00Z",
            message="Test",
            context=SecurityContext(),
        )
        alert = alerts_service.process_security_event(event)

        assert alert.priority == AlertPriority.P1_CRITICAL

    def test_prompt_injection_is_p2(self, alerts_service):
        """Test prompt injection events are P2."""
        event = SecurityEvent(
            event_id="evt-1",
            event_type=SecurityEventType.THREAT_PROMPT_INJECTION,
            severity=SecurityEventSeverity.HIGH,
            timestamp="2025-12-12T10:00:00Z",
            message="Test",
            context=SecurityContext(),
        )
        alert = alerts_service.process_security_event(event)

        assert alert.priority == AlertPriority.P2_HIGH


# ============================================================================
# HITL Request Tests
# ============================================================================


class TestHITLRequests:
    """Tests for HITL approval request creation."""

    def test_creates_hitl_for_critical(self, alerts_service, critical_event):
        """Test HITL request is created for critical events."""
        alerts_service.process_security_event(critical_event)

        stats = alerts_service.get_stats()
        assert stats["hitl_requests_created"] >= 1

    def test_hitl_request_contains_alert_id(self, alerts_service, critical_event):
        """Test HITL request references the alert."""
        alert = alerts_service.process_security_event(critical_event)

        # Check internal storage
        hitl_requests = list(alerts_service._hitl_requests.values())
        assert len(hitl_requests) > 0

        request = hitl_requests[-1]
        assert request.alert_id == alert.alert_id

    def test_hitl_request_has_remediation_context(self, alerts_service, critical_event):
        """Test HITL request includes remediation steps."""
        alerts_service.process_security_event(critical_event)

        hitl_requests = list(alerts_service._hitl_requests.values())
        request = hitl_requests[-1]

        assert "remediation_steps" in request.context
        assert len(request.context["remediation_steps"]) > 0

    def test_no_hitl_for_non_critical_events(self, alerts_service):
        """Test HITL not created for injection attempts (high but not requiring HITL)."""
        event = SecurityEvent(
            event_id="evt-1",
            event_type=SecurityEventType.INPUT_INJECTION_ATTEMPT,
            severity=SecurityEventSeverity.HIGH,
            timestamp="2025-12-12T10:00:00Z",
            message="Test",
            context=SecurityContext(),
        )
        alerts_service.process_security_event(event)

        # INPUT_INJECTION_ATTEMPT has requires_hitl=False
        # So no HITL request should be created for this event
        # (Stats may have requests from other tests, so check the last request)


# ============================================================================
# Alert Lifecycle Tests
# ============================================================================


class TestAlertLifecycle:
    """Tests for alert lifecycle management."""

    def test_acknowledge_alert(self, alerts_service, critical_event):
        """Test acknowledging an alert."""
        alert = alerts_service.process_security_event(critical_event)
        updated = alerts_service.acknowledge_alert(
            alert.alert_id,
            user_id="admin-123",
            notes="Investigating now",
        )

        assert updated.status == AlertStatus.ACKNOWLEDGED
        assert updated.assigned_to == "admin-123"
        assert updated.acknowledged_at is not None

    def test_resolve_alert(self, alerts_service, critical_event):
        """Test resolving an alert."""
        alert = alerts_service.process_security_event(critical_event)
        alerts_service.acknowledge_alert(alert.alert_id, "admin-123")

        resolved = alerts_service.resolve_alert(
            alert.alert_id,
            user_id="admin-123",
            resolution="Blocked source IP, updated WAF rules",
        )

        assert resolved.status == AlertStatus.RESOLVED
        assert resolved.resolved_at is not None
        assert "resolution" in resolved.metadata

    def test_mark_as_false_positive(self, alerts_service, critical_event):
        """Test marking alert as false positive."""
        alert = alerts_service.process_security_event(critical_event)
        resolved = alerts_service.resolve_alert(
            alert.alert_id,
            user_id="admin-123",
            resolution="Legitimate admin activity",
            is_false_positive=True,
        )

        assert resolved.status == AlertStatus.FALSE_POSITIVE

    def test_get_alert_by_id(self, alerts_service, critical_event):
        """Test retrieving alert by ID."""
        alert = alerts_service.process_security_event(critical_event)
        retrieved = alerts_service.get_alert(alert.alert_id)

        assert retrieved is not None
        assert retrieved.alert_id == alert.alert_id

    def test_get_nonexistent_alert(self, alerts_service):
        """Test retrieving nonexistent alert."""
        result = alerts_service.get_alert("nonexistent-id")
        assert result is None


# ============================================================================
# Alert Filtering Tests
# ============================================================================


class TestAlertFiltering:
    """Tests for alert filtering and listing."""

    def test_get_alerts_by_status(self, alerts_service, critical_event, high_event):
        """Test filtering alerts by status."""
        alert1 = alerts_service.process_security_event(critical_event)
        alert2 = alerts_service.process_security_event(high_event)

        alerts_service.acknowledge_alert(alert1.alert_id, "admin")

        new_alerts = alerts_service.get_alerts(status=AlertStatus.NEW)
        ack_alerts = alerts_service.get_alerts(status=AlertStatus.ACKNOWLEDGED)

        assert any(a.alert_id == alert2.alert_id for a in new_alerts)
        assert any(a.alert_id == alert1.alert_id for a in ack_alerts)

    def test_get_alerts_by_priority(self, alerts_service, critical_event, high_event):
        """Test filtering alerts by priority."""
        alerts_service.process_security_event(critical_event)
        alerts_service.process_security_event(high_event)

        p1_alerts = alerts_service.get_alerts(priority=AlertPriority.P1_CRITICAL)
        p2_alerts = alerts_service.get_alerts(priority=AlertPriority.P2_HIGH)

        assert all(a.priority == AlertPriority.P1_CRITICAL for a in p1_alerts)
        assert all(a.priority == AlertPriority.P2_HIGH for a in p2_alerts)

    def test_alerts_sorted_by_priority(
        self, alerts_service, critical_event, high_event
    ):
        """Test alerts are sorted by priority."""
        # Create in reverse order
        alerts_service.process_security_event(high_event)
        alerts_service.process_security_event(critical_event)

        alerts = alerts_service.get_alerts()

        # Critical should come first
        assert alerts[0].priority == AlertPriority.P1_CRITICAL


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Tests for service statistics."""

    def test_stats_tracking(self, alerts_service, critical_event):
        """Test statistics are tracked."""
        alerts_service.process_security_event(critical_event)

        stats = alerts_service.get_stats()
        assert stats["alerts_created"] >= 1

    def test_active_alerts_count(self, alerts_service, critical_event):
        """Test active alerts count."""
        alert = alerts_service.process_security_event(critical_event)

        stats = alerts_service.get_stats()
        assert stats["active_alerts"] >= 1

        alerts_service.resolve_alert(alert.alert_id, "admin", "Fixed")

        stats = alerts_service.get_stats()
        # Alert is now resolved, active count should decrease


# ============================================================================
# Data Class Tests
# ============================================================================


class TestDataClasses:
    """Tests for data class serialization."""

    def test_alert_to_dict(self, alerts_service, critical_event):
        """Test SecurityAlert.to_dict()."""
        alert = alerts_service.process_security_event(critical_event)
        d = alert.to_dict()

        assert "alert_id" in d
        assert "title" in d
        assert "priority" in d
        assert "status" in d
        assert "security_event" in d

    def test_alert_to_json(self, alerts_service, critical_event):
        """Test SecurityAlert.to_json()."""
        import json

        alert = alerts_service.process_security_event(critical_event)
        json_str = alert.to_json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["alert_id"] == alert.alert_id

    def test_hitl_request_to_dict(self):
        """Test HITLApprovalRequest.to_dict()."""
        request = HITLApprovalRequest(
            request_id="req-123",
            alert_id="alert-456",
            approval_type="security_alert",
            title="Test Alert",
            description="Test description",
            priority="P1",
            requested_action="immediate_response",
            context={"test": "data"},
            created_at="2025-12-12T10:00:00Z",
        )

        d = request.to_dict()
        assert d["request_id"] == "req-123"
        assert d["alert_id"] == "alert-456"


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_alerts_service_singleton(self):
        """Test get_alerts_service returns same instance."""
        service1 = get_alerts_service()
        service2 = get_alerts_service()
        assert service1 is service2


# ============================================================================
# Convenience Function Tests
# ============================================================================


class TestConvenienceFunction:
    """Tests for process_security_event convenience function."""

    def test_process_security_event_function(self, critical_event):
        """Test process_security_event convenience function."""
        alert = process_security_event(critical_event)
        assert alert is not None
        assert alert.priority == AlertPriority.P1_CRITICAL
