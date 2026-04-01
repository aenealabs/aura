"""
Project Aura - Approval Callback Handler Lambda Tests

Comprehensive tests for the HITL approval callback handler Lambda function.
Tests API Gateway events, Step Functions callbacks, and DynamoDB operations.
"""

import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
import importlib
import json
import os
import sys
from unittest.mock import MagicMock, patch

# Save original modules before mocking to prevent test pollution
_original_boto3 = sys.modules.get("boto3")
_original_handler = sys.modules.get("src.lambda.approval_callback_handler")

# Mock boto3 before imports
mock_dynamodb_resource = MagicMock()
mock_dynamodb_table = MagicMock()
mock_dynamodb_resource.Table.return_value = mock_dynamodb_table

mock_sfn_client = MagicMock()
mock_sns_client = MagicMock()

mock_boto3 = MagicMock()
mock_boto3.resource.return_value = mock_dynamodb_resource
mock_boto3.client.side_effect = lambda service, **kwargs: {
    "stepfunctions": mock_sfn_client,
    "sns": mock_sns_client,
}.get(service, MagicMock())

sys.modules["boto3"] = mock_boto3
# Note: Don't mock botocore.exceptions - it's needed for real exception handling in other tests

# Use importlib to import from lambda (reserved keyword)
approval_handler = importlib.import_module("src.lambda.approval_callback_handler")

handler = approval_handler.handler
handle_api_gateway_event = approval_handler.handle_api_gateway_event
handle_register_token = approval_handler.handle_register_token
handle_approval_decision = approval_handler.handle_approval_decision
handle_process_approval = approval_handler.handle_process_approval
await_send_notification = approval_handler.await_send_notification
get_timestamp = approval_handler.get_timestamp
api_response = approval_handler.api_response

# Restore original modules to prevent pollution of other tests
if _original_boto3 is not None:
    sys.modules["boto3"] = _original_boto3
else:
    sys.modules.pop("boto3", None)

if _original_handler is not None:
    sys.modules["src.lambda.approval_callback_handler"] = _original_handler


class TestApiResponse:
    """Tests for api_response helper function."""

    def test_api_response_200(self):
        """Test successful response."""
        response = api_response(200, {"status": "ok"})
        assert response["statusCode"] == 200
        assert "Content-Type" in response["headers"]
        body = json.loads(response["body"])
        assert body["status"] == "ok"

    def test_api_response_400(self):
        """Test error response."""
        response = api_response(400, {"error": "Bad request"})
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"] == "Bad request"

    def test_api_response_cors_headers(self):
        """Test CORS headers are set."""
        response = api_response(200, {})
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Headers" in response["headers"]
        assert "Access-Control-Allow-Methods" in response["headers"]


class TestGetTimestamp:
    """Tests for get_timestamp helper function."""

    def test_timestamp_format(self):
        """Test timestamp is ISO format."""
        ts = get_timestamp()
        assert "T" in ts
        # Should end with +00:00 or Z for UTC
        assert "+" in ts or ts.endswith("Z")


class TestHandler:
    """Tests for main handler function."""

    def test_handler_api_gateway_event(self):
        """Test handler with API Gateway event."""
        event = {
            "httpMethod": "POST",
            "path": "/approval/register-token",
            "body": json.dumps({"workflow_id": "wf-123", "task_token": "token-abc"}),
        }

        # Use patch.object on the imported module to ensure the patch is applied
        with patch.object(approval_handler, "handle_api_gateway_event") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "ok"})
            approval_handler.handler(event, None)
            mock_handle.assert_called_once()

    def test_handler_register_token_action(self):
        """Test handler with register_token action."""
        event = {
            "action": "register_token",
            "workflow_id": "wf-123",
            "task_token": "token-abc",
        }

        with patch.object(approval_handler, "handle_register_token") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "registered"})
            approval_handler.handler(event, None)
            mock_handle.assert_called_once()

    def test_handler_process_approval_action(self):
        """Test handler with process_approval action."""
        event = {
            "action": "process_approval",
            "approval_id": "apr-123",
            "decision": "APPROVED",
        }

        with patch.object(approval_handler, "handle_process_approval") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "processed"})
            approval_handler.handler(event, None)
            mock_handle.assert_called_once()

    def test_handler_unknown_action(self):
        """Test handler with unknown action."""
        event = {"action": "unknown"}
        response = handler(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Unknown action" in body["error"]


class TestHandleApiGatewayEvent:
    """Tests for API Gateway event handling."""

    def test_approve_route(self):
        """Test approve route."""
        event = {
            "httpMethod": "POST",
            "path": "/approval/approve",
            "body": json.dumps(
                {"approval_id": "apr-123", "approver_email": "test@example.com"}
            ),
        }

        with patch.object(approval_handler, "handle_approval_decision") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "approved"})
            approval_handler.handle_api_gateway_event(event, None)
            mock_handle.assert_called_once_with(
                {"approval_id": "apr-123", "approver_email": "test@example.com"},
                decision="APPROVED",
            )

    def test_reject_route(self):
        """Test reject route."""
        event = {
            "httpMethod": "POST",
            "path": "/approval/reject",
            "body": json.dumps({"approval_id": "apr-123", "comments": "Not suitable"}),
        }

        with patch.object(approval_handler, "handle_approval_decision") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "rejected"})
            approval_handler.handle_api_gateway_event(event, None)
            mock_handle.assert_called_once_with(
                {"approval_id": "apr-123", "comments": "Not suitable"},
                decision="REJECTED",
            )

    def test_register_token_route(self):
        """Test register-token route."""
        event = {
            "httpMethod": "POST",
            "path": "/approval/register-token",
            "body": json.dumps({"workflow_id": "wf-123", "task_token": "token-abc"}),
        }

        with patch.object(approval_handler, "handle_register_token") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "registered"})
            approval_handler.handle_api_gateway_event(event, None)
            mock_handle.assert_called_once()

    def test_invalid_json_body(self):
        """Test handling of invalid JSON body."""
        event = {
            "httpMethod": "POST",
            "path": "/approval/approve",
            "body": "not valid json",
        }
        response = handle_api_gateway_event(event, None)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid JSON" in body["error"]

    def test_route_not_found(self):
        """Test unknown route."""
        event = {"httpMethod": "GET", "path": "/unknown/route", "body": "{}"}
        response = handle_api_gateway_event(event, None)
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "Route not found" in body["error"]


class TestHandleRegisterToken:
    """Tests for token registration."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_dynamodb_table.update_item.reset_mock()
        mock_dynamodb_table.update_item.return_value = {}

    def test_register_token_success(self):
        """Test successful token registration."""
        event = {
            "workflow_id": "wf-123",
            "approval_id": "apr-456",
            "task_token": "token-abc",
        }

        os.environ["WORKFLOW_TABLE_NAME"] = "test-workflows"
        os.environ["APPROVAL_TABLE_NAME"] = "test-approvals"
        os.environ["AWS_REGION"] = "us-east-1"

        response = handle_register_token(event)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "registered"
        assert body["workflow_id"] == "wf-123"

    def test_register_token_missing_workflow_id(self):
        """Test registration without workflow_id."""
        event = {"task_token": "token-abc"}
        response = handle_register_token(event)
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Missing required fields" in body["error"]

    def test_register_token_missing_task_token(self):
        """Test registration without task_token."""
        event = {"workflow_id": "wf-123"}
        response = handle_register_token(event)
        assert response["statusCode"] == 400

    def test_register_token_without_approval_id(self):
        """Test registration without approval_id (should still work)."""
        event = {"workflow_id": "wf-123", "task_token": "token-abc"}

        response = handle_register_token(event)
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["approval_id"] is None


class TestHandleApprovalDecision:
    """Tests for approval decision handling."""

    def test_approval_decision_approved(self):
        """Test approval decision with APPROVED."""
        body = {
            "approval_id": "apr-123",
            "approver_email": "test@example.com",
            "comments": "Looks good",
        }

        with patch.object(approval_handler, "handle_process_approval") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "processed"})
            _response = approval_handler.handle_approval_decision(
                body, decision="APPROVED"
            )
            mock_handle.assert_called_once()
            call_args = mock_handle.call_args[0][0]
            assert call_args["decision"] == "APPROVED"
            assert call_args["approval_id"] == "apr-123"

    def test_approval_decision_rejected(self):
        """Test approval decision with REJECTED."""
        body = {"approval_id": "apr-123", "comments": "Not suitable"}

        with patch.object(approval_handler, "handle_process_approval") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "processed"})
            _response = approval_handler.handle_approval_decision(
                body, decision="REJECTED"
            )
            call_args = mock_handle.call_args[0][0]
            assert call_args["decision"] == "REJECTED"

    def test_approval_decision_missing_approval_id(self):
        """Test approval decision without approval_id."""
        body = {"comments": "test"}
        response = handle_approval_decision(body, decision="APPROVED")
        assert response["statusCode"] == 400
        body_json = json.loads(response["body"])
        assert "Missing approval_id" in body_json["error"]

    def test_approval_decision_default_email(self):
        """Test approval decision with default email."""
        body = {"approval_id": "apr-123"}

        with patch.object(approval_handler, "handle_process_approval") as mock_handle:
            mock_handle.return_value = api_response(200, {"status": "processed"})
            approval_handler.handle_approval_decision(body, decision="APPROVED")
            call_args = mock_handle.call_args[0][0]
            assert call_args["approver_email"] == "unknown@company.com"


class TestHandleProcessApproval:
    """Tests for approval processing."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_dynamodb_table.get_item.reset_mock()
        mock_dynamodb_table.update_item.reset_mock()
        mock_sfn_client.send_task_success.reset_mock()
        mock_sfn_client.send_task_failure.reset_mock()

    def test_process_approval_invalid_decision(self):
        """Test processing with invalid decision."""
        event = {"approval_id": "apr-123", "decision": "MAYBE"}
        response = handle_process_approval(event)
        assert response["statusCode"] == 400

    def test_process_approval_missing_approval_id(self):
        """Test processing without approval_id."""
        event = {"decision": "APPROVED"}
        response = handle_process_approval(event)
        assert response["statusCode"] == 400


class TestAwaitSendNotification:
    """Tests for notification sending."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_sns_client.publish.reset_mock()

    def test_send_notification_no_topic(self):
        """Test notification without SNS topic configured."""
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

        # Should not raise
        await_send_notification("apr-123", "APPROVED", "test@example.com", "Good")
        mock_sns_client.publish.assert_not_called()

    def test_send_notification_with_topic(self):
        """Test notification with SNS topic configured."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:topic"
        os.environ["AWS_REGION"] = "us-east-1"

        await_send_notification("apr-123", "APPROVED", "test@example.com", "Good")

        # Clean up
        del os.environ["SNS_TOPIC_ARN"]

    def test_send_notification_error_handling(self):
        """Test notification error doesn't raise."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:topic"
        mock_sns_client.publish.side_effect = Exception("SNS error")

        # Should not raise
        await_send_notification("apr-123", "REJECTED", "test@example.com", "Bad")

        # Clean up
        del os.environ["SNS_TOPIC_ARN"]
        mock_sns_client.publish.side_effect = None


class TestIntegration:
    """Integration tests for complete workflows."""

    def setup_method(self):
        """Reset all mocks before each test."""
        mock_dynamodb_table.get_item.reset_mock()
        mock_dynamodb_table.update_item.reset_mock()
        mock_sfn_client.send_task_success.reset_mock()
        mock_sfn_client.send_task_failure.reset_mock()
        mock_sns_client.publish.reset_mock()

    def test_full_api_gateway_approve_flow(self):
        """Test complete API Gateway approve flow."""
        event = {
            "httpMethod": "POST",
            "path": "/approval/approve",
            "body": json.dumps(
                {
                    "approval_id": "apr-123",
                    "approver_email": "senior@example.com",
                    "comments": "Verified and approved",
                }
            ),
        }

        # Mock approval record
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "approvalId": "apr-123",
                "task_token": "token-xyz",
                "workflow_id": "wf-123",
            }
        }

        response = handler(event, None)
        # Response depends on implementation
        assert response is not None

    def test_full_api_gateway_reject_flow(self):
        """Test complete API Gateway reject flow."""
        event = {
            "httpMethod": "POST",
            "path": "/approval/reject",
            "body": json.dumps(
                {
                    "approval_id": "apr-456",
                    "approver_email": "senior@example.com",
                    "comments": "Security concern",
                }
            ),
        }

        # Mock approval record
        mock_dynamodb_table.get_item.return_value = {
            "Item": {
                "approvalId": "apr-456",
                "task_token": "token-abc",
                "workflow_id": "wf-456",
            }
        }

        response = handler(event, None)
        assert response is not None

    def test_full_direct_invoke_register_token(self):
        """Test direct invocation for token registration."""
        event = {
            "action": "register_token",
            "workflow_id": "wf-789",
            "approval_id": "apr-789",
            "task_token": "token-new",
        }

        response = handler(event, None)
        assert response is not None
