"""
Tests for AnomalyTriggers - API event integration with anomaly detection.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.anomaly_triggers import AnomalyTriggers, get_triggers, set_triggers


class TestAnomalyTriggersInit:
    """Test AnomalyTriggers initialization."""

    def test_init_with_detector(self):
        """Test initialization with a detector."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(anomaly_detector=mock_detector)

        assert triggers.enabled is True
        assert triggers.anomaly_detector is mock_detector

    def test_init_without_detector(self):
        """Test initialization without a detector (passive mode)."""
        triggers = AnomalyTriggers()

        assert triggers.enabled is False
        assert triggers.anomaly_detector is None

    def test_set_detector(self):
        """Test setting detector after initialization."""
        triggers = AnomalyTriggers()
        assert triggers.enabled is False

        mock_detector = MagicMock()
        triggers.set_detector(mock_detector)

        assert triggers.enabled is True
        assert triggers.anomaly_detector is mock_detector


class TestGlobalTriggers:
    """Test global triggers management."""

    def test_get_set_triggers(self):
        """Test global get/set functions."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        set_triggers(triggers)
        retrieved = get_triggers()

        assert retrieved is triggers


class TestHITLApprovalMetrics:
    """Test HITL approval decision tracking."""

    def test_record_approval_decision_approved(self):
        """Test recording an approval."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        triggers.record_approval_decision(
            decision="approved",
            severity="critical",
            approval_time_hours=2.5,
            reviewer="test@example.com",
        )

        # Verify metrics were recorded
        assert mock_detector.record_metric.call_count >= 2

        # Check approval rate metric (value should be 1.0 for approved)
        calls = mock_detector.record_metric.call_args_list
        approval_rate_call = next(
            c for c in calls if c.kwargs.get("metric_name") == "hitl.approval_rate"
        )
        assert approval_rate_call.kwargs["value"] == 1.0

    def test_record_approval_decision_rejected(self):
        """Test recording a rejection."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        triggers.record_approval_decision(
            decision="rejected",
            severity="high",
            reviewer="test@example.com",
        )

        # Check approval rate metric (value should be 0.0 for rejected)
        calls = mock_detector.record_metric.call_args_list
        approval_rate_call = next(
            c for c in calls if c.kwargs.get("metric_name") == "hitl.approval_rate"
        )
        assert approval_rate_call.kwargs["value"] == 0.0

    def test_critical_rejection_triggers_security_event(self):
        """Test that critical patch rejection triggers security event."""
        mock_detector = MagicMock()
        mock_detector.process_security_event = AsyncMock()
        triggers = AnomalyTriggers(mock_detector)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete = MagicMock()

            triggers.record_approval_decision(
                decision="rejected",
                severity="critical",
                reviewer="test@example.com",
            )

            # Verify security event was processed
            mock_loop.return_value.run_until_complete.assert_called()

    def test_approval_time_tracked_for_approved_only(self):
        """Test that time-to-approve is only tracked for approved requests."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        # Record an approval with time
        triggers.record_approval_decision(
            decision="approved",
            severity="high",
            approval_time_hours=1.5,
        )

        # Check time_to_approve metric was recorded
        calls = mock_detector.record_metric.call_args_list
        time_calls = [
            c for c in calls if "time_to_approve" in c.kwargs.get("metric_name", "")
        ]
        assert len(time_calls) == 1
        assert time_calls[0].kwargs["value"] == 1.5

        # Reset mock
        mock_detector.reset_mock()

        # Record a rejection with time (should not track time)
        triggers.record_approval_decision(
            decision="rejected",
            severity="high",
            approval_time_hours=1.5,  # Should be ignored
        )

        calls = mock_detector.record_metric.call_args_list
        time_calls = [
            c for c in calls if "time_to_approve" in c.kwargs.get("metric_name", "")
        ]
        assert len(time_calls) == 0

    def test_disabled_triggers_no_op(self):
        """Test that disabled triggers don't record anything."""
        triggers = AnomalyTriggers()  # No detector
        assert triggers.enabled is False

        # Should not raise
        triggers.record_approval_decision(
            decision="approved",
            severity="critical",
            approval_time_hours=1.0,
        )


class TestHITLTimeoutMetrics:
    """Test HITL timeout tracking."""

    def test_record_timeout(self):
        """Test recording a timeout."""
        mock_detector = MagicMock()
        mock_detector.process_security_event = AsyncMock()
        triggers = AnomalyTriggers(mock_detector)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete = MagicMock()

            triggers.record_approval_timeout(
                approval_id="test-123",
                severity="critical",
                pending_hours=48.0,
            )

            # Verify timeout count metric
            calls = mock_detector.record_metric.call_args_list
            timeout_call = next(
                c for c in calls if c.kwargs.get("metric_name") == "hitl.timeout_count"
            )
            assert timeout_call.kwargs["value"] == 1.0


class TestWebhookMetrics:
    """Test webhook event tracking."""

    def test_record_webhook_success(self):
        """Test recording a successful webhook."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        triggers.record_webhook_event(
            success=True,
            event_type="push",
            processing_time_ms=150.0,
        )

        # Verify metrics
        calls = mock_detector.record_metric.call_args_list

        # Success rate
        success_call = next(
            c for c in calls if c.kwargs.get("metric_name") == "webhook.success_rate"
        )
        assert success_call.kwargs["value"] == 1.0

        # Event count
        count_call = next(
            c for c in calls if c.kwargs.get("metric_name") == "webhook.event_count"
        )
        assert count_call.kwargs["value"] == 1.0

        # Processing time
        time_call = next(
            c
            for c in calls
            if c.kwargs.get("metric_name") == "webhook.processing_time_ms"
        )
        assert time_call.kwargs["value"] == 150.0

    def test_record_webhook_failure(self):
        """Test recording a failed webhook."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        triggers.record_webhook_event(
            success=False,
            event_type="push",
            error="timeout",
        )

        calls = mock_detector.record_metric.call_args_list
        success_call = next(
            c for c in calls if c.kwargs.get("metric_name") == "webhook.success_rate"
        )
        assert success_call.kwargs["value"] == 0.0

    def test_signature_failure_triggers_security_event(self):
        """Test that signature validation failure triggers security event."""
        mock_detector = MagicMock()
        mock_detector.process_security_event = AsyncMock()
        triggers = AnomalyTriggers(mock_detector)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete = MagicMock()

            triggers.record_webhook_event(
                success=False,
                event_type="push",
                error="signature_invalid",
            )

            # Verify security event was processed
            mock_loop.return_value.run_until_complete.assert_called()


class TestAPIRequestMetrics:
    """Test API request tracking."""

    @pytest.mark.asyncio
    async def test_record_api_request(self):
        """Test recording an API request."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        await triggers.record_api_request(
            endpoint="/api/v1/approvals",
            latency_ms=50.0,
            status_code=200,
            method="GET",
        )

        # Verify latency metric
        calls = mock_detector.record_metric.call_args_list
        latency_call = next(
            c for c in calls if c.kwargs.get("metric_name") == "api.latency_ms"
        )
        assert latency_call.kwargs["value"] == 50.0

        # Verify error rate (should be 0 for 200)
        error_call = next(
            c for c in calls if c.kwargs.get("metric_name") == "api.error_rate"
        )
        assert error_call.kwargs["value"] == 0.0

    @pytest.mark.asyncio
    async def test_record_api_error(self):
        """Test recording an API error (5xx)."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        await triggers.record_api_request(
            endpoint="/api/v1/approvals",
            latency_ms=500.0,
            status_code=500,
        )

        # Error rate should be 1.0 for 5xx
        calls = mock_detector.record_metric.call_args_list
        error_call = next(
            c for c in calls if c.kwargs.get("metric_name") == "api.error_rate"
        )
        assert error_call.kwargs["value"] == 1.0


class TestSecurityEvents:
    """Test security event recording."""

    def test_record_security_event(self):
        """Test direct security event recording."""
        mock_detector = MagicMock()
        mock_detector.process_security_event = AsyncMock()
        triggers = AnomalyTriggers(mock_detector)

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            mock_loop.return_value.run_until_complete = MagicMock()

            triggers.record_security_event(
                event_type="suspicious_activity",
                severity="HIGH",
                description="Unusual login pattern detected",
                affected_components=["auth-service"],
            )

            mock_loop.return_value.run_until_complete.assert_called()


class TestEndpointNormalization:
    """Test endpoint path normalization for metrics."""

    def test_normalize_simple_endpoint(self):
        """Test normalizing a simple endpoint."""
        triggers = AnomalyTriggers()

        result = triggers._normalize_endpoint("/api/v1/approvals")
        assert result == "approvals"

    def test_normalize_endpoint_with_id(self):
        """Test normalizing endpoint with UUID."""
        triggers = AnomalyTriggers()

        # UUID-like path parts (>20 chars) are stripped
        result = triggers._normalize_endpoint(
            "/api/v1/approvals/abc123def456ghi789xyz012"
        )
        assert result == "approvals"

    def test_normalize_nested_endpoint(self):
        """Test normalizing nested endpoint."""
        triggers = AnomalyTriggers()

        result = triggers._normalize_endpoint("/api/v1/settings/mode")
        assert result == "settings_mode"

    def test_normalize_root(self):
        """Test normalizing root endpoint."""
        triggers = AnomalyTriggers()

        result = triggers._normalize_endpoint("/")
        assert result == "root"


class TestIntegrationWithApprovals:
    """Test integration with approval workflow."""

    def test_approval_workflow_integration(self):
        """Test that triggers work in approval workflow context."""
        mock_detector = MagicMock()
        triggers = AnomalyTriggers(mock_detector)

        # Simulate approval workflow
        approval = {
            "approval_id": "test-123",
            "severity": "HIGH",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Record the decision
        triggers.record_approval_decision(
            decision="approved",
            severity=approval["severity"].lower(),
            approval_time_hours=2.0,
            reviewer="reviewer@example.com",
        )

        # Verify metrics were recorded
        assert mock_detector.record_metric.called

        # Check that severity-specific metric was recorded
        calls = mock_detector.record_metric.call_args_list
        severity_call = next(
            c for c in calls if "high" in c.kwargs.get("metric_name", "")
        )
        assert severity_call is not None
