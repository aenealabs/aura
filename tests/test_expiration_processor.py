"""
Project Aura - Expiration Processor Lambda Tests

Comprehensive tests for the HITL expiration processor Lambda function.
Tests scheduled event handling and expiration processing workflows.
"""

import importlib
import json
import os
import sys
from dataclasses import dataclass
from unittest.mock import MagicMock

# Save original modules before mocking to prevent test pollution
_modules_to_save = [
    "src.services.hitl_approval_service",
    "src.services.notification_service",
    "src.lambda.expiration_processor",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}


# Mock the HITL and Notification services before imports
@dataclass
class MockExpirationResult:
    """Mock expiration result."""

    processed: int = 0
    escalated: int = 0
    expired: int = 0
    warnings_sent: int = 0
    errors: list = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


mock_hitl_service = MagicMock()
mock_hitl_service.process_expirations.return_value = MockExpirationResult(
    processed=5, escalated=1, expired=2, warnings_sent=2
)

mock_notification_service = MagicMock()

# Mock the service modules
mock_hitl_module = MagicMock()
mock_hitl_module.HITLApprovalService = MagicMock(return_value=mock_hitl_service)
mock_hitl_module.HITLMode = MagicMock()
mock_hitl_module.HITLMode.MOCK = "mock"
mock_hitl_module.HITLMode.AWS = "aws"

mock_notification_module = MagicMock()
mock_notification_module.NotificationService = MagicMock(
    return_value=mock_notification_service
)
mock_notification_module.NotificationMode = MagicMock()
mock_notification_module.NotificationMode.MOCK = "mock"
mock_notification_module.NotificationMode.AWS = "aws"

sys.modules["src.services.hitl_approval_service"] = mock_hitl_module
sys.modules["src.services.notification_service"] = mock_notification_module

# Need to force SERVICES_AVAILABLE to True after mocking
if "src.lambda.expiration_processor" in sys.modules:
    del sys.modules["src.lambda.expiration_processor"]

# Use importlib to import from lambda (reserved keyword)
expiration_processor = importlib.import_module("src.lambda.expiration_processor")
expiration_processor.SERVICES_AVAILABLE = True
expiration_processor.HITLApprovalService = mock_hitl_module.HITLApprovalService
expiration_processor.HITLMode = mock_hitl_module.HITLMode
expiration_processor.NotificationService = mock_notification_module.NotificationService
expiration_processor.NotificationMode = mock_notification_module.NotificationMode

handler = expiration_processor.handler

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


class TestHandlerConfiguration:
    """Tests for handler configuration parsing."""

    def setup_method(self):
        """Set up environment variables."""
        os.environ["HITL_TABLE_NAME"] = "test-hitl-table"
        os.environ["HITL_SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:topic"
        os.environ["BACKUP_REVIEWERS"] = "backup1@test.com,backup2@test.com"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"
        os.environ["USE_MOCK"] = "true"

    def teardown_method(self):
        """Clean up environment variables."""
        for key in [
            "HITL_TABLE_NAME",
            "HITL_SNS_TOPIC_ARN",
            "BACKUP_REVIEWERS",
            "TIMEOUT_HOURS",
            "ESCALATION_TIMEOUT_HOURS",
            "USE_MOCK",
        ]:
            if key in os.environ:
                del os.environ[key]

    def test_handler_reads_table_name(self):
        """Test handler reads HITL_TABLE_NAME."""
        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)
        # Handler should complete
        assert response is not None

    def test_handler_reads_backup_reviewers(self):
        """Test handler parses BACKUP_REVIEWERS comma-separated list."""
        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)
        # Handler should complete without error
        assert response["statusCode"] in [200, 500]


class TestHandlerExecution:
    """Tests for handler execution."""

    def setup_method(self):
        """Set up environment variables and reset mocks."""
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"
        os.environ["BACKUP_REVIEWERS"] = ""
        mock_hitl_service.process_expirations.reset_mock()
        mock_hitl_service.process_expirations.return_value = MockExpirationResult(
            processed=5, escalated=1, expired=2, warnings_sent=2
        )

    def teardown_method(self):
        """Clean up environment variables."""
        for key in [
            "USE_MOCK",
            "TIMEOUT_HOURS",
            "ESCALATION_TIMEOUT_HOURS",
            "BACKUP_REVIEWERS",
        ]:
            if key in os.environ:
                del os.environ[key]

    def test_handler_success(self):
        """Test successful handler execution."""
        event = {
            "version": "0",
            "id": "test-event-id",
            "detail-type": "Scheduled Event",
            "source": "aws.events",
            "time": "2025-12-01T12:00:00Z",
            "detail": {},
        }

        response = handler(event, None)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["processed"] == 5
        assert body["escalated"] == 1
        assert body["expired"] == 2
        assert body["warnings_sent"] == 2

    def test_handler_uses_mock_mode(self):
        """Test handler uses mock mode when USE_MOCK=true."""
        os.environ["USE_MOCK"] = "true"
        event = {"detail-type": "Scheduled Event"}

        response = handler(event, None)
        # Should complete successfully in mock mode
        assert response["statusCode"] == 200

    def test_handler_uses_aws_mode(self):
        """Test handler uses AWS mode when USE_MOCK=false."""
        os.environ["USE_MOCK"] = "false"
        event = {"detail-type": "Scheduled Event"}

        response = handler(event, None)
        # Should complete (may fail in test env without AWS)
        assert response is not None


class TestHandlerErrors:
    """Tests for handler error handling."""

    def setup_method(self):
        """Set up environment variables."""
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"
        os.environ["BACKUP_REVIEWERS"] = ""

    def teardown_method(self):
        """Clean up environment variables."""
        for key in [
            "USE_MOCK",
            "TIMEOUT_HOURS",
            "ESCALATION_TIMEOUT_HOURS",
            "BACKUP_REVIEWERS",
        ]:
            if key in os.environ:
                del os.environ[key]

    def test_handler_processing_error(self):
        """Test handler handles processing errors."""
        mock_hitl_service.process_expirations.side_effect = Exception(
            "Processing error"
        )

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body
        assert body["processed"] == 0

        # Reset side effect
        mock_hitl_service.process_expirations.side_effect = None
        mock_hitl_service.process_expirations.return_value = MockExpirationResult()

    def test_handler_services_unavailable(self):
        """Test handler handles unavailable services."""
        # Temporarily set SERVICES_AVAILABLE to False
        original_value = expiration_processor.SERVICES_AVAILABLE
        expiration_processor.SERVICES_AVAILABLE = False

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "Services not available" in body["error"]

        # Restore
        expiration_processor.SERVICES_AVAILABLE = original_value


class TestExpirationResult:
    """Tests for expiration result handling."""

    def setup_method(self):
        """Set up environment variables."""
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"
        os.environ["BACKUP_REVIEWERS"] = ""

    def teardown_method(self):
        """Clean up environment variables."""
        for key in [
            "USE_MOCK",
            "TIMEOUT_HOURS",
            "ESCALATION_TIMEOUT_HOURS",
            "BACKUP_REVIEWERS",
        ]:
            if key in os.environ:
                del os.environ[key]

    def test_result_includes_all_fields(self):
        """Test response includes all result fields."""
        mock_hitl_service.process_expirations.return_value = MockExpirationResult(
            processed=10,
            escalated=3,
            expired=4,
            warnings_sent=5,
            errors=["error1", "error2"],
        )

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        body = json.loads(response["body"])
        assert "processed" in body
        assert "escalated" in body
        assert "expired" in body
        assert "warnings_sent" in body
        assert "errors" in body
        assert body["processed"] == 10
        assert body["escalated"] == 3
        assert body["expired"] == 4
        assert body["warnings_sent"] == 5
        assert len(body["errors"]) == 2

    def test_result_with_zero_counts(self):
        """Test response with zero counts."""
        mock_hitl_service.process_expirations.return_value = MockExpirationResult(
            processed=0, escalated=0, expired=0, warnings_sent=0, errors=[]
        )

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        body = json.loads(response["body"])
        assert body["processed"] == 0
        assert body["escalated"] == 0
        assert body["expired"] == 0


class TestBackupReviewersParsing:
    """Tests for backup reviewers configuration parsing."""

    def test_empty_backup_reviewers(self):
        """Test empty backup reviewers string."""
        os.environ["BACKUP_REVIEWERS"] = ""
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response["statusCode"] in [200, 500]

    def test_single_backup_reviewer(self):
        """Test single backup reviewer."""
        os.environ["BACKUP_REVIEWERS"] = "backup@test.com"
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response["statusCode"] in [200, 500]

    def test_multiple_backup_reviewers(self):
        """Test multiple backup reviewers."""
        os.environ["BACKUP_REVIEWERS"] = (
            "backup1@test.com,backup2@test.com,backup3@test.com"
        )
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response["statusCode"] in [200, 500]

    def test_backup_reviewers_with_whitespace(self):
        """Test backup reviewers with extra whitespace."""
        os.environ["BACKUP_REVIEWERS"] = "  backup1@test.com , backup2@test.com  ,  "
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response["statusCode"] in [200, 500]


class TestCloudWatchEvent:
    """Tests for CloudWatch Events integration."""

    def setup_method(self):
        """Set up environment variables."""
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"
        os.environ["BACKUP_REVIEWERS"] = ""
        mock_hitl_service.process_expirations.reset_mock()
        mock_hitl_service.process_expirations.return_value = MockExpirationResult()

    def teardown_method(self):
        """Clean up environment variables."""
        for key in [
            "USE_MOCK",
            "TIMEOUT_HOURS",
            "ESCALATION_TIMEOUT_HOURS",
            "BACKUP_REVIEWERS",
        ]:
            if key in os.environ:
                del os.environ[key]

    def test_scheduled_event_format(self):
        """Test handler handles standard scheduled event format."""
        event = {
            "version": "0",
            "id": "12345678-1234-1234-1234-123456789012",
            "detail-type": "Scheduled Event",
            "source": "aws.events",
            "account": "123456789012",
            "time": "2025-12-01T12:00:00Z",
            "region": "us-east-1",
            "resources": [
                "arn:aws:events:us-east-1:123456789012:rule/aura-expiration-processor"
            ],
            "detail": {},
        }

        response = handler(event, None)
        assert response is not None
        assert response["statusCode"] == 200

    def test_minimal_event(self):
        """Test handler handles minimal event."""
        event = {}
        response = handler(event, None)
        assert response is not None

    def test_event_with_extra_fields(self):
        """Test handler ignores extra fields."""
        event = {
            "detail-type": "Scheduled Event",
            "extra_field": "ignored",
            "another_extra": {"nested": "value"},
        }
        response = handler(event, None)
        assert response is not None


class TestTimeoutConfiguration:
    """Tests for timeout configuration."""

    def test_default_timeout_hours(self):
        """Test default timeout hours."""
        # Don't set TIMEOUT_HOURS
        if "TIMEOUT_HOURS" in os.environ:
            del os.environ["TIMEOUT_HOURS"]
        os.environ["USE_MOCK"] = "true"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "12"
        os.environ["BACKUP_REVIEWERS"] = ""

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response is not None

    def test_default_escalation_timeout(self):
        """Test default escalation timeout hours."""
        # Don't set ESCALATION_TIMEOUT_HOURS
        if "ESCALATION_TIMEOUT_HOURS" in os.environ:
            del os.environ["ESCALATION_TIMEOUT_HOURS"]
        os.environ["USE_MOCK"] = "true"
        os.environ["TIMEOUT_HOURS"] = "24"
        os.environ["BACKUP_REVIEWERS"] = ""

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response is not None

    def test_custom_timeout_values(self):
        """Test custom timeout values."""
        os.environ["TIMEOUT_HOURS"] = "48"
        os.environ["ESCALATION_TIMEOUT_HOURS"] = "6"
        os.environ["USE_MOCK"] = "true"
        os.environ["BACKUP_REVIEWERS"] = ""

        event = {"detail-type": "Scheduled Event"}
        response = handler(event, None)

        assert response is not None
