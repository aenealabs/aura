"""
Unit tests for scheduled_provisioner.py Lambda handler.

Tests cover:
- Pending job queries
- Status updates
- Provisioner invocation
- Error handling
- CloudWatch metrics publishing

Part of ADR-039 Phase 4: Advanced Features
"""

import importlib
import json
import os
from unittest.mock import MagicMock, patch

# Set environment variables before importing Lambda
os.environ.setdefault("SCHEDULE_TABLE", "test-schedule-table")
os.environ.setdefault("PROVISIONER_FUNCTION", "test-provisioner")
os.environ.setdefault("SNS_TOPIC", "arn:aws:sns:us-east-1:123456789012:test-topic")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PROJECT_NAME", "aura")
os.environ.setdefault("METRICS_NAMESPACE", "aura/TestEnvironments")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# Import using importlib (lambda is a reserved keyword)
scheduled_provisioner = importlib.import_module("src.lambda.scheduled_provisioner")


class TestGetPendingJobs:
    """Tests for get_pending_jobs function."""

    def test_returns_pending_jobs(self):
        """Test that pending jobs are returned correctly."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "schedule_id": "sched-123",
                    "user_id": "user-456",
                    "scheduled_at": "2025-01-01T10:00:00Z",
                    "status": "pending",
                }
            ]
        }

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.object(
            scheduled_provisioner, "get_dynamodb_resource", return_value=mock_dynamodb
        ):
            jobs = scheduled_provisioner.get_pending_jobs()

            assert len(jobs) == 1
            assert jobs[0]["schedule_id"] == "sched-123"

    def test_returns_empty_when_no_jobs(self):
        """Test that empty list is returned when no pending jobs."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.object(
            scheduled_provisioner, "get_dynamodb_resource", return_value=mock_dynamodb
        ):
            jobs = scheduled_provisioner.get_pending_jobs()

            assert len(jobs) == 0

    def test_returns_empty_on_error(self):
        """Test that empty list is returned on DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_table = MagicMock()
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test"}}, "Query"
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.object(
            scheduled_provisioner, "get_dynamodb_resource", return_value=mock_dynamodb
        ):
            jobs = scheduled_provisioner.get_pending_jobs()

            assert len(jobs) == 0


class TestUpdateJobStatus:
    """Tests for update_job_status function."""

    def test_updates_status_successfully(self):
        """Test successful status update."""
        mock_table = MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.object(
            scheduled_provisioner, "get_dynamodb_resource", return_value=mock_dynamodb
        ):
            result = scheduled_provisioner.update_job_status("sched-123", "triggered")

            assert result is True
            mock_table.update_item.assert_called_once()

    def test_updates_with_error_message(self):
        """Test status update with error message."""
        mock_table = MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.object(
            scheduled_provisioner, "get_dynamodb_resource", return_value=mock_dynamodb
        ):
            result = scheduled_provisioner.update_job_status(
                "sched-123", "failed", error_message="Test error"
            )

            assert result is True
            call_args = mock_table.update_item.call_args
            assert ":error" in call_args.kwargs["ExpressionAttributeValues"]

    def test_returns_false_on_error(self):
        """Test that False is returned on update error."""
        from botocore.exceptions import ClientError

        mock_table = MagicMock()
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test"}}, "UpdateItem"
        )

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch.object(
            scheduled_provisioner, "get_dynamodb_resource", return_value=mock_dynamodb
        ):
            result = scheduled_provisioner.update_job_status("sched-123", "triggered")

            assert result is False


class TestInvokeProvisioner:
    """Tests for invoke_provisioner function."""

    def test_invokes_provisioner_successfully(self):
        """Test successful provisioner invocation."""
        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = {
            "StatusCode": 202,
            "ResponseMetadata": {"RequestId": "req-123"},
        }

        job = {
            "schedule_id": "sched-123",
            "user_id": "user-456",
            "environment_type": "standard",
        }

        with patch.object(
            scheduled_provisioner, "get_lambda_client", return_value=mock_lambda
        ):
            success, exec_id, error = scheduled_provisioner.invoke_provisioner(job)

            assert success is True
            assert exec_id == "req-123"
            assert error is None

    def test_returns_error_on_failed_invocation(self):
        """Test error handling on failed invocation."""
        from botocore.exceptions import ClientError

        mock_lambda = MagicMock()
        mock_lambda.invoke.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test error"}}, "Invoke"
        )

        job = {"schedule_id": "sched-123", "user_id": "user-456"}

        with patch.object(
            scheduled_provisioner, "get_lambda_client", return_value=mock_lambda
        ):
            success, exec_id, error = scheduled_provisioner.invoke_provisioner(job)

            assert success is False
            assert exec_id is None
            assert error is not None


class TestHandler:
    """Tests for the Lambda handler function."""

    def test_handler_processes_jobs(self):
        """Test handler processes pending jobs."""
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "schedule_id": "sched-123",
                    "user_id": "user-456",
                    "scheduled_at": "2025-01-01T10:00:00Z",
                }
            ]
        }

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = {
            "StatusCode": 202,
            "ResponseMetadata": {"RequestId": "req-123"},
        }

        event = {"source": "aws.events"}
        context = MagicMock()

        with (
            patch.object(
                scheduled_provisioner,
                "get_dynamodb_resource",
                return_value=mock_dynamodb,
            ),
            patch.object(
                scheduled_provisioner, "get_lambda_client", return_value=mock_lambda
            ),
            patch.object(scheduled_provisioner, "publish_metric"),
        ):
            response = scheduled_provisioner.handler(event, context)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["jobs_processed"] == 1
            assert body["triggered"] == 1

    def test_handler_returns_early_when_no_jobs(self):
        """Test handler returns early when no pending jobs."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        event = {"source": "aws.events"}
        context = MagicMock()

        with (
            patch.object(
                scheduled_provisioner,
                "get_dynamodb_resource",
                return_value=mock_dynamodb,
            ),
            patch.object(scheduled_provisioner, "publish_metric"),
        ):
            response = scheduled_provisioner.handler(event, context)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["jobs_processed"] == 0

    def test_handler_tracks_failures(self):
        """Test handler tracks failed invocations."""
        from botocore.exceptions import ClientError

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [{"schedule_id": "sched-123", "user_id": "user-456"}]
        }

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        mock_lambda = MagicMock()
        mock_lambda.invoke.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test"}}, "Invoke"
        )

        mock_sns = MagicMock()

        event = {"source": "aws.events"}
        context = MagicMock()

        with (
            patch.object(
                scheduled_provisioner,
                "get_dynamodb_resource",
                return_value=mock_dynamodb,
            ),
            patch.object(
                scheduled_provisioner, "get_lambda_client", return_value=mock_lambda
            ),
            patch.object(
                scheduled_provisioner, "get_sns_client", return_value=mock_sns
            ),
            patch.object(scheduled_provisioner, "publish_metric"),
        ):
            response = scheduled_provisioner.handler(event, context)

            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["failed"] == 1
