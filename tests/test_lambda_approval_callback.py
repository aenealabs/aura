"""
Project Aura - Approval Callback Handler Lambda Tests

Tests for the Lambda handler that processes Step Functions task token callbacks
for the HITL approval workflow.

Target: 85% coverage of src/lambda/approval_callback_handler.py
"""

# ruff: noqa: PLR2004

import importlib
import json
import os
from unittest.mock import MagicMock, patch

# Set environment before importing Lambda
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

# Import the lambda module using importlib (lambda is a reserved keyword)
approval_callback = importlib.import_module("src.lambda.approval_callback_handler")


class TestApiResponse:
    """Tests for the api_response helper function."""

    def test_api_response_success(self):
        """Test creating a successful API response."""
        response = approval_callback.api_response(200, {"status": "ok"})

        assert response["statusCode"] == 200
        assert "Content-Type" in response["headers"]
        assert response["headers"]["Content-Type"] == "application/json"
        assert "Access-Control-Allow-Origin" in response["headers"]
        body = json.loads(response["body"])
        assert body["status"] == "ok"

    def test_api_response_error(self):
        """Test creating an error API response."""
        response = approval_callback.api_response(500, {"error": "Server error"})

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Server error"

    def test_api_response_cors_headers(self):
        """Test that CORS headers are included."""
        response = approval_callback.api_response(200, {})

        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Content-Type" in response["headers"]["Access-Control-Allow-Headers"]
        assert "POST" in response["headers"]["Access-Control-Allow-Methods"]


class TestGetTimestamp:
    """Tests for the get_timestamp helper function."""

    def test_get_timestamp_format(self):
        """Test timestamp is in ISO format."""
        timestamp = approval_callback.get_timestamp()

        assert isinstance(timestamp, str)
        # Should contain date separator and time indicator
        assert "T" in timestamp
        # Should have timezone info
        assert "+" in timestamp or "Z" in timestamp

    def test_get_timestamp_is_utc(self):
        """Test timestamp is in UTC."""
        timestamp = approval_callback.get_timestamp()

        # UTC timestamps end with +00:00 or Z
        assert "+00:00" in timestamp or timestamp.endswith("Z")


class TestHandler:
    """Tests for the main handler function."""

    def test_handler_unknown_action(self):
        """Test handler returns 400 for unknown action."""
        event = {"action": "unknown_action"}
        response = approval_callback.handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Unknown action" in body["error"]

    def test_handler_empty_action(self):
        """Test handler returns 400 for empty action."""
        event = {}
        response = approval_callback.handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Unknown action" in body["error"]

    def test_handler_routes_to_register_token(self):
        """Test handler routes register_token action correctly."""
        event = {
            "action": "register_token",
            "workflow_id": "test-workflow",
            "task_token": "test-token",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            response = approval_callback.handler(event, None)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["status"] == "registered"

    def test_handler_routes_to_process_approval(self):
        """Test handler routes process_approval action correctly."""
        event = {
            "action": "process_approval",
            "approval_id": "test-approval",
            "decision": "APPROVED",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-approval",
                    "task_token": "test-token",
                    "workflow_id": "test-workflow",
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            mock_sfn = MagicMock()
            mock_boto3.client.return_value = mock_sfn

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handler(event, None)

            assert response["statusCode"] == 200

    def test_handler_routes_api_gateway_event(self):
        """Test handler routes API Gateway events correctly."""
        event = {
            "httpMethod": "POST",
            "path": "/approvals/approve",
            "body": json.dumps({"approval_id": "test-123"}),
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-123",
                    "task_token": "token-abc",
                    "workflow_id": "workflow-xyz",
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            mock_sfn = MagicMock()
            mock_boto3.client.return_value = mock_sfn

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handler(event, None)

            assert response["statusCode"] == 200


class TestHandleApiGatewayEvent:
    """Tests for the handle_api_gateway_event function."""

    def test_invalid_json_body(self):
        """Test handling of invalid JSON body."""
        event = {
            "httpMethod": "POST",
            "path": "/approvals/approve",
            "body": "not valid json",
        }

        response = approval_callback.handle_api_gateway_event(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid JSON" in body["error"]

    def test_route_approve(self):
        """Test routing to approve endpoint."""
        event = {
            "httpMethod": "POST",
            "path": "/approvals/approve",
            "body": json.dumps({"approval_id": "test-123"}),
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {"approvalId": "test-123", "workflow_id": "wf-1"}
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = MagicMock()

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_api_gateway_event(event, None)

            assert response["statusCode"] == 200

    def test_route_reject(self):
        """Test routing to reject endpoint."""
        event = {
            "httpMethod": "POST",
            "path": "/approvals/reject",
            "body": json.dumps({"approval_id": "test-123"}),
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {"approvalId": "test-123", "workflow_id": "wf-1"}
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = MagicMock()

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_api_gateway_event(event, None)

            assert response["statusCode"] == 200

    def test_route_register_token(self):
        """Test routing to register-token endpoint."""
        event = {
            "httpMethod": "POST",
            "path": "/approvals/register-token",
            "body": json.dumps(
                {
                    "workflow_id": "wf-123",
                    "task_token": "token-abc",
                }
            ),
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            response = approval_callback.handle_api_gateway_event(event, None)

            assert response["statusCode"] == 200

    def test_route_not_found(self):
        """Test handling of unknown route."""
        event = {
            "httpMethod": "GET",
            "path": "/unknown/path",
            "body": "{}",
        }

        response = approval_callback.handle_api_gateway_event(event, None)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "Route not found" in body["error"]


class TestHandleRegisterToken:
    """Tests for the handle_register_token function."""

    def test_missing_workflow_id(self):
        """Test handling of missing workflow_id."""
        event = {"task_token": "test-token"}

        response = approval_callback.handle_register_token(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Missing required fields" in body["error"]

    def test_missing_task_token(self):
        """Test handling of missing task_token."""
        event = {"workflow_id": "test-workflow"}

        response = approval_callback.handle_register_token(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Missing required fields" in body["error"]

    def test_successful_registration(self):
        """Test successful token registration."""
        event = {
            "workflow_id": "test-workflow",
            "task_token": "test-token",
            "approval_id": "test-approval",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            response = approval_callback.handle_register_token(event)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["status"] == "registered"
            assert body["workflow_id"] == "test-workflow"
            assert body["approval_id"] == "test-approval"

            # Verify DynamoDB was called
            assert mock_table.update_item.called

    def test_registration_without_approval_id(self):
        """Test registration without approval_id (only workflow table updated)."""
        event = {
            "workflow_id": "test-workflow",
            "task_token": "test-token",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            response = approval_callback.handle_register_token(event)

            assert response["statusCode"] == 200
            # Only workflow table should be updated (1 call, not 2)
            assert mock_table.update_item.call_count == 1

    def test_dynamodb_error(self):
        """Test handling of DynamoDB error."""
        from botocore.exceptions import ClientError

        event = {
            "workflow_id": "test-workflow",
            "task_token": "test-token",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_table.update_item.side_effect = ClientError(
                {"Error": {"Code": "ValidationException", "Message": "Test error"}},
                "UpdateItem",
            )
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            response = approval_callback.handle_register_token(event)

            assert response["statusCode"] == 500
            body = json.loads(response["body"])
            assert "error" in body


class TestHandleApprovalDecision:
    """Tests for the handle_approval_decision function."""

    def test_missing_approval_id(self):
        """Test handling of missing approval_id."""
        body = {"approver_email": "test@example.com"}

        response = approval_callback.handle_approval_decision(body, "APPROVED")

        assert response["statusCode"] == 400
        body_response = json.loads(response["body"])
        assert "Missing approval_id" in body_response["error"]

    def test_approved_decision(self):
        """Test handling of APPROVED decision."""
        body = {
            "approval_id": "test-approval",
            "approver_email": "test@example.com",
            "comments": "Looks good",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {"approvalId": "test-approval", "workflow_id": "wf-1"}
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = MagicMock()

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_approval_decision(body, "APPROVED")

            assert response["statusCode"] == 200
            body_response = json.loads(response["body"])
            assert body_response["decision"] == "APPROVED"

    def test_rejected_decision(self):
        """Test handling of REJECTED decision."""
        body = {
            "approval_id": "test-approval",
            "approver_email": "test@example.com",
            "comments": "Security concern",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {"approvalId": "test-approval", "workflow_id": "wf-1"}
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = MagicMock()

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_approval_decision(body, "REJECTED")

            assert response["statusCode"] == 200
            body_response = json.loads(response["body"])
            assert body_response["decision"] == "REJECTED"


class TestHandleProcessApproval:
    """Tests for the handle_process_approval function."""

    def test_missing_approval_id(self):
        """Test handling of missing approval_id."""
        event = {"decision": "APPROVED"}

        response = approval_callback.handle_process_approval(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid request" in body["error"]

    def test_invalid_decision(self):
        """Test handling of invalid decision."""
        event = {"approval_id": "test-123", "decision": "MAYBE"}

        response = approval_callback.handle_process_approval(event)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "Invalid request" in body["error"]

    def test_approval_not_found(self):
        """Test handling of non-existent approval."""
        event = {"approval_id": "nonexistent", "decision": "APPROVED"}

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {}  # No Item
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = MagicMock()

            response = approval_callback.handle_process_approval(event)

            assert response["statusCode"] == 404
            body = json.loads(response["body"])
            assert "not found" in body["error"]

    def test_successful_approval_with_task_token(self):
        """Test successful approval with Step Functions callback."""
        event = {
            "approval_id": "test-approval",
            "decision": "APPROVED",
            "approver_email": "approver@example.com",
            "comments": "Ship it!",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-approval",
                    "task_token": "sfn-task-token",
                    "workflow_id": "wf-123",
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            mock_sfn = MagicMock()
            mock_boto3.client.return_value = mock_sfn

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_process_approval(event)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["status"] == "processed"
            assert body["callback_result"] == "success_sent"

            # Verify Step Functions was called
            mock_sfn.send_task_success.assert_called_once()

    def test_successful_rejection_with_task_token(self):
        """Test successful rejection with Step Functions callback."""
        event = {
            "approval_id": "test-approval",
            "decision": "REJECTED",
            "approver_email": "reviewer@example.com",
            "comments": "Security vulnerability found",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-approval",
                    "task_token": "sfn-task-token",
                    "workflow_id": "wf-123",
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            mock_sfn = MagicMock()
            mock_boto3.client.return_value = mock_sfn

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_process_approval(event)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["callback_result"] == "failure_sent"

            # Verify Step Functions failure was called
            mock_sfn.send_task_failure.assert_called_once()

    def test_approval_without_task_token(self):
        """Test approval when no task token is present."""
        event = {
            "approval_id": "test-approval",
            "decision": "APPROVED",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-approval",
                    # No task_token
                    "workflow_id": "wf-123",
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = MagicMock()

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_process_approval(event)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["callback_result"] == "no_token"

    def test_task_token_expired(self):
        """Test handling of expired task token."""
        from botocore.exceptions import ClientError

        event = {
            "approval_id": "test-approval",
            "decision": "APPROVED",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-approval",
                    "task_token": "expired-token",
                    "workflow_id": "wf-123",
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            mock_sfn = MagicMock()
            mock_sfn.send_task_success.side_effect = ClientError(
                {"Error": {"Code": "TaskTimedOut", "Message": "Task timed out"}},
                "SendTaskSuccess",
            )
            mock_boto3.client.return_value = mock_sfn

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_process_approval(event)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["callback_result"] == "token_expired"

    def test_task_does_not_exist(self):
        """Test handling when task no longer exists."""
        from botocore.exceptions import ClientError

        event = {
            "approval_id": "test-approval",
            "decision": "APPROVED",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-approval",
                    "task_token": "old-token",
                    "workflow_id": "wf-123",
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            mock_sfn = MagicMock()
            mock_sfn.send_task_success.side_effect = ClientError(
                {"Error": {"Code": "TaskDoesNotExist", "Message": "Task not found"}},
                "SendTaskSuccess",
            )
            mock_boto3.client.return_value = mock_sfn

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_process_approval(event)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["callback_result"] == "task_not_found"

    def test_step_functions_other_error(self):
        """Test handling of other Step Functions errors."""
        from botocore.exceptions import ClientError

        event = {
            "approval_id": "test-approval",
            "decision": "APPROVED",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-approval",
                    "task_token": "token",
                    "workflow_id": "wf-123",
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            mock_sfn = MagicMock()
            mock_sfn.send_task_success.side_effect = ClientError(
                {"Error": {"Code": "InternalError", "Message": "Internal error"}},
                "SendTaskSuccess",
            )
            mock_boto3.client.return_value = mock_sfn

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_process_approval(event)

            # Should return 500 for unknown errors
            assert response["statusCode"] == 500

    def test_dynamodb_error_during_processing(self):
        """Test handling of DynamoDB error during approval processing."""
        from botocore.exceptions import ClientError

        event = {
            "approval_id": "test-approval",
            "decision": "APPROVED",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_table.get_item.side_effect = ClientError(
                {
                    "Error": {
                        "Code": "ResourceNotFoundException",
                        "Message": "Table not found",
                    }
                },
                "GetItem",
            )
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb
            mock_boto3.client.return_value = MagicMock()

            response = approval_callback.handle_process_approval(event)

            assert response["statusCode"] == 500

    def test_approval_without_workflow_id(self):
        """Test approval when workflow_id is not present."""
        event = {
            "approval_id": "test-approval",
            "decision": "APPROVED",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_table = MagicMock()
            mock_table.get_item.return_value = {
                "Item": {
                    "approvalId": "test-approval",
                    "task_token": "token",
                    # No workflow_id
                }
            }
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            mock_sfn = MagicMock()
            mock_boto3.client.return_value = mock_sfn

            with patch.object(approval_callback, "await_send_notification"):
                response = approval_callback.handle_process_approval(event)

            assert response["statusCode"] == 200
            # Workflow table update should not be called
            # Only approval table update should happen


class TestAwaitSendNotification:
    """Tests for the await_send_notification function."""

    def test_no_sns_topic_configured(self):
        """Test that notification is skipped when no SNS topic configured."""
        # Ensure SNS_TOPIC_ARN is not set
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

        # Should not raise any errors
        approval_callback.await_send_notification(
            "approval-123", "APPROVED", "test@example.com", "comments"
        )

    def test_successful_notification(self):
        """Test successful SNS notification."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:test-topic"

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_sns = MagicMock()
            mock_boto3.client.return_value = mock_sns

            approval_callback.await_send_notification(
                "approval-123", "APPROVED", "approver@example.com", "Ship it!"
            )

            mock_sns.publish.assert_called_once()
            call_kwargs = mock_sns.publish.call_args.kwargs
            assert "TopicArn" in call_kwargs
            assert "APPROVED" in call_kwargs["Subject"]

        del os.environ["SNS_TOPIC_ARN"]

    def test_notification_failure_does_not_raise(self):
        """Test that notification failure doesn't raise exception."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:test-topic"

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_sns = MagicMock()
            mock_sns.publish.side_effect = Exception("SNS error")
            mock_boto3.client.return_value = mock_sns

            # Should not raise
            approval_callback.await_send_notification(
                "approval-123", "REJECTED", "test@example.com", ""
            )

        del os.environ["SNS_TOPIC_ARN"]

    def test_notification_subject_truncation(self):
        """Test that long subjects are truncated to 100 chars."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:test-topic"

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_sns = MagicMock()
            mock_boto3.client.return_value = mock_sns

            long_approval_id = "a" * 200
            approval_callback.await_send_notification(
                long_approval_id, "APPROVED", "test@example.com", ""
            )

            call_kwargs = mock_sns.publish.call_args.kwargs
            assert len(call_kwargs["Subject"]) <= 100

        del os.environ["SNS_TOPIC_ARN"]

    def test_notification_with_empty_comments(self):
        """Test notification with no comments shows (none)."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:test-topic"

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_sns = MagicMock()
            mock_boto3.client.return_value = mock_sns

            approval_callback.await_send_notification(
                "approval-123", "APPROVED", "test@example.com", ""
            )

            call_kwargs = mock_sns.publish.call_args.kwargs
            assert "(none)" in call_kwargs["Message"]

        del os.environ["SNS_TOPIC_ARN"]


class TestEnvironmentConfiguration:
    """Tests for environment variable handling."""

    def test_default_table_names(self):
        """Test default table names are used when env vars not set."""
        # Remove env vars if set
        for key in ["WORKFLOW_TABLE_NAME", "APPROVAL_TABLE_NAME"]:
            if key in os.environ:
                del os.environ[key]

        event = {
            "workflow_id": "test-workflow",
            "task_token": "test-token",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            approval_callback.handle_register_token(event)

            # Should use default table name
            mock_dynamodb.Table.assert_called_with("aura-patch-workflows-dev")

    def test_custom_table_names(self):
        """Test custom table names from environment variables."""
        os.environ["WORKFLOW_TABLE_NAME"] = "custom-workflow-table"
        os.environ["APPROVAL_TABLE_NAME"] = "custom-approval-table"

        event = {
            "workflow_id": "test-workflow",
            "task_token": "test-token",
            "approval_id": "test-approval",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            approval_callback.handle_register_token(event)

            # Should use custom table names
            calls = [call[0][0] for call in mock_dynamodb.Table.call_args_list]
            assert "custom-workflow-table" in calls
            assert "custom-approval-table" in calls

        del os.environ["WORKFLOW_TABLE_NAME"]
        del os.environ["APPROVAL_TABLE_NAME"]

    def test_custom_region(self):
        """Test custom AWS region from environment variable."""
        os.environ["AWS_REGION"] = "eu-west-1"

        event = {
            "workflow_id": "test-workflow",
            "task_token": "test-token",
        }

        with patch.object(approval_callback, "boto3") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_table = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_boto3.resource.return_value = mock_dynamodb

            approval_callback.handle_register_token(event)

            # Should use custom region
            mock_boto3.resource.assert_called_with("dynamodb", region_name="eu-west-1")

        del os.environ["AWS_REGION"]
