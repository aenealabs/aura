"""
Project Aura - Expiration Processor Lambda Tests

Tests for the Lambda handler that processes expired HITL approval requests.
Uses moto fixtures from conftest.py for AWS service mocking.

Target: 85% coverage of src/lambda/expiration_processor.py
"""

import importlib
import json
import os
from unittest.mock import MagicMock, patch

# Set environment before importing Lambda
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

# Import the lambda module using importlib (lambda is a reserved keyword)
expiration_processor = importlib.import_module("src.lambda.expiration_processor")


class TestExpirationHandler:
    """Tests for the main handler function."""

    def test_handler_services_not_available(self):
        """Test handler returns 500 when services unavailable."""
        # Temporarily set SERVICES_AVAILABLE to False
        original = expiration_processor.SERVICES_AVAILABLE
        expiration_processor.SERVICES_AVAILABLE = False

        try:
            event = {"detail-type": "Scheduled Event"}
            response = expiration_processor.handler(event, None)

            assert response["statusCode"] == 500
            body = json.loads(response["body"])
            assert "error" in body
            assert body["processed"] == 0
        finally:
            expiration_processor.SERVICES_AVAILABLE = original

    def test_handler_success_mock_mode(self):
        """Test handler succeeds in mock mode."""
        os.environ["USE_MOCK"] = "true"
        os.environ["BACKUP_REVIEWERS"] = "backup@example.com"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"

        # Mock the services
        mock_result = MagicMock()
        mock_result.processed = 5
        mock_result.escalated = 1
        mock_result.expired = 2
        mock_result.warnings_sent = 2
        mock_result.errors = []

        with patch.object(
            expiration_processor, "HITLApprovalService"
        ) as mock_hitl_class:
            with patch.object(
                expiration_processor, "NotificationService"
            ) as _mock_notif_class:
                mock_hitl = MagicMock()
                mock_hitl.process_expirations.return_value = mock_result
                mock_hitl_class.return_value = mock_hitl

                # Ensure services are available
                original = expiration_processor.SERVICES_AVAILABLE
                expiration_processor.SERVICES_AVAILABLE = True

                try:
                    event = {"detail-type": "Scheduled Event"}
                    response = expiration_processor.handler(event, None)

                    assert response["statusCode"] == 200
                    body = json.loads(response["body"])
                    assert body["processed"] == 5
                    assert body["escalated"] == 1
                    assert body["expired"] == 2
                    assert body["warnings_sent"] == 2
                finally:
                    expiration_processor.SERVICES_AVAILABLE = original

        # Cleanup
        for key in [
            "USE_MOCK",
            "BACKUP_REVIEWERS",
            "TIMEOUT_HOURS",
            "ESCALATION_TIMEOUT_HOURS",
        ]:
            if key in os.environ:
                del os.environ[key]

    def test_handler_exception_handling(self):
        """Test handler returns 500 on exception."""
        os.environ["USE_MOCK"] = "true"

        with patch.object(
            expiration_processor, "HITLApprovalService"
        ) as mock_hitl_class:
            with patch.object(expiration_processor, "NotificationService"):
                mock_hitl_class.side_effect = Exception("Test error")

                original = expiration_processor.SERVICES_AVAILABLE
                expiration_processor.SERVICES_AVAILABLE = True

                try:
                    event = {}
                    response = expiration_processor.handler(event, None)

                    assert response["statusCode"] == 500
                    body = json.loads(response["body"])
                    assert "Test error" in body["error"]
                    assert body["processed"] == 0
                finally:
                    expiration_processor.SERVICES_AVAILABLE = original

        if "USE_MOCK" in os.environ:
            del os.environ["USE_MOCK"]

    def test_handler_parses_backup_reviewers(self):
        """Test that backup reviewers are parsed correctly."""
        os.environ["USE_MOCK"] = "true"
        os.environ["BACKUP_REVIEWERS"] = (
            "user1@test.com, user2@test.com, user3@test.com"
        )

        mock_result = MagicMock()
        mock_result.processed = 0
        mock_result.escalated = 0
        mock_result.expired = 0
        mock_result.warnings_sent = 0
        mock_result.errors = []

        with patch.object(
            expiration_processor, "HITLApprovalService"
        ) as mock_hitl_class:
            with patch.object(expiration_processor, "NotificationService"):
                mock_hitl = MagicMock()
                mock_hitl.process_expirations.return_value = mock_result
                mock_hitl_class.return_value = mock_hitl

                original = expiration_processor.SERVICES_AVAILABLE
                expiration_processor.SERVICES_AVAILABLE = True

                try:
                    expiration_processor.handler({}, None)

                    # Check that HITLApprovalService was called with parsed reviewers
                    call_kwargs = mock_hitl_class.call_args.kwargs
                    assert "backup_reviewers" in call_kwargs
                    assert len(call_kwargs["backup_reviewers"]) == 3
                    assert "user1@test.com" in call_kwargs["backup_reviewers"]
                finally:
                    expiration_processor.SERVICES_AVAILABLE = original

        for key in ["USE_MOCK", "BACKUP_REVIEWERS"]:
            if key in os.environ:
                del os.environ[key]

    def test_handler_uses_default_timeout(self):
        """Test handler uses default timeout when not specified."""
        os.environ["USE_MOCK"] = "true"
        # Don't set TIMEOUT_HOURS - should default to 24

        mock_result = MagicMock()
        mock_result.processed = 0
        mock_result.escalated = 0
        mock_result.expired = 0
        mock_result.warnings_sent = 0
        mock_result.errors = []

        with patch.object(
            expiration_processor, "HITLApprovalService"
        ) as mock_hitl_class:
            with patch.object(expiration_processor, "NotificationService"):
                mock_hitl = MagicMock()
                mock_hitl.process_expirations.return_value = mock_result
                mock_hitl_class.return_value = mock_hitl

                original = expiration_processor.SERVICES_AVAILABLE
                expiration_processor.SERVICES_AVAILABLE = True

                try:
                    expiration_processor.handler({}, None)

                    call_kwargs = mock_hitl_class.call_args.kwargs
                    assert call_kwargs["timeout_hours"] == 24
                    assert call_kwargs["escalation_timeout_hours"] == 12
                finally:
                    expiration_processor.SERVICES_AVAILABLE = original

        if "USE_MOCK" in os.environ:
            del os.environ["USE_MOCK"]


class TestEnvironmentConfiguration:
    """Tests for environment variable handling."""

    def test_empty_backup_reviewers(self):
        """Test handling of empty backup reviewers string."""
        os.environ["USE_MOCK"] = "true"
        os.environ["BACKUP_REVIEWERS"] = ""

        mock_result = MagicMock()
        mock_result.processed = 0
        mock_result.escalated = 0
        mock_result.expired = 0
        mock_result.warnings_sent = 0
        mock_result.errors = []

        with patch.object(
            expiration_processor, "HITLApprovalService"
        ) as mock_hitl_class:
            with patch.object(expiration_processor, "NotificationService"):
                mock_hitl = MagicMock()
                mock_hitl.process_expirations.return_value = mock_result
                mock_hitl_class.return_value = mock_hitl

                original = expiration_processor.SERVICES_AVAILABLE
                expiration_processor.SERVICES_AVAILABLE = True

                try:
                    expiration_processor.handler({}, None)

                    call_kwargs = mock_hitl_class.call_args.kwargs
                    assert call_kwargs["backup_reviewers"] == []
                finally:
                    expiration_processor.SERVICES_AVAILABLE = original

        for key in ["USE_MOCK", "BACKUP_REVIEWERS"]:
            if key in os.environ:
                del os.environ[key]

    def test_aws_mode_when_use_mock_false(self):
        """Test that AWS mode is used when USE_MOCK is false."""
        os.environ["USE_MOCK"] = "false"

        mock_result = MagicMock()
        mock_result.processed = 0
        mock_result.escalated = 0
        mock_result.expired = 0
        mock_result.warnings_sent = 0
        mock_result.errors = []

        with patch.object(
            expiration_processor, "HITLApprovalService"
        ) as mock_hitl_class:
            with patch.object(
                expiration_processor, "NotificationService"
            ) as mock_notif_class:
                mock_hitl = MagicMock()
                mock_hitl.process_expirations.return_value = mock_result
                mock_hitl_class.return_value = mock_hitl

                original = expiration_processor.SERVICES_AVAILABLE
                expiration_processor.SERVICES_AVAILABLE = True

                try:
                    expiration_processor.handler({}, None)

                    # Check NotificationService was called with AWS mode
                    notif_call_kwargs = mock_notif_class.call_args.kwargs
                    assert (
                        notif_call_kwargs["mode"]
                        == expiration_processor.NotificationMode.AWS
                    )

                    # Check HITLApprovalService was called with AWS mode
                    hitl_call_kwargs = mock_hitl_class.call_args.kwargs
                    assert hitl_call_kwargs["mode"] == expiration_processor.HITLMode.AWS
                finally:
                    expiration_processor.SERVICES_AVAILABLE = original

        if "USE_MOCK" in os.environ:
            del os.environ["USE_MOCK"]


class TestCloudWatchEvent:
    """Tests for CloudWatch Events integration."""

    def test_handler_logs_event(self):
        """Test that handler logs the incoming event."""
        os.environ["USE_MOCK"] = "true"

        mock_result = MagicMock()
        mock_result.processed = 0
        mock_result.escalated = 0
        mock_result.expired = 0
        mock_result.warnings_sent = 0
        mock_result.errors = []

        test_event = {
            "version": "0",
            "id": "test-id",
            "detail-type": "Scheduled Event",
            "source": "aws.events",
        }

        with patch.object(
            expiration_processor, "HITLApprovalService"
        ) as mock_hitl_class:
            with patch.object(expiration_processor, "NotificationService"):
                with patch.object(expiration_processor, "logger") as mock_logger:
                    mock_hitl = MagicMock()
                    mock_hitl.process_expirations.return_value = mock_result
                    mock_hitl_class.return_value = mock_hitl

                    original = expiration_processor.SERVICES_AVAILABLE
                    expiration_processor.SERVICES_AVAILABLE = True

                    try:
                        expiration_processor.handler(test_event, None)

                        # Verify logging was called
                        assert mock_logger.info.called
                    finally:
                        expiration_processor.SERVICES_AVAILABLE = original

        if "USE_MOCK" in os.environ:
            del os.environ["USE_MOCK"]
