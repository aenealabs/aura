"""
Project Aura - Log Retention Sync Lambda Tests

Tests for the Lambda handler that syncs CloudWatch log group retention
policies based on UI settings changes.

Target: 85% coverage of src/lambda/log_retention_sync.py
"""

import importlib
import json
import os
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

# Set environment and AWS region before importing Lambda
os.environ["ENVIRONMENT"] = "dev"
os.environ["PROJECT_NAME"] = "aura"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

# Import the lambda module
log_retention_sync = importlib.import_module("src.lambda.log_retention_sync")


class TestValidateRetentionDays:
    """Tests for validate_retention_days function."""

    def test_valid_retention_value_passes_through(self):
        """Test that valid CloudWatch retention values pass through unchanged."""
        assert log_retention_sync.validate_retention_days(30) == 30
        assert log_retention_sync.validate_retention_days(90) == 90
        assert log_retention_sync.validate_retention_days(365) == 365

    def test_invalid_value_normalized_up(self):
        """Test that invalid values are normalized to next valid value."""
        # 45 is not valid, should return 60 (next valid)
        assert log_retention_sync.validate_retention_days(45) == 60
        # 100 should return 120
        assert log_retention_sync.validate_retention_days(100) == 120
        # 200 should return 365
        assert log_retention_sync.validate_retention_days(200) == 365

    def test_large_value_returns_max(self):
        """Test that very large values return the maximum valid value."""
        result = log_retention_sync.validate_retention_days(10000)
        assert result == log_retention_sync.VALID_RETENTION_DAYS[-1]


class TestGetEnv:
    """Tests for get_env helper function."""

    def test_get_env_returns_value(self):
        """Test get_env returns environment variable value."""
        os.environ["TEST_LOG_VAR"] = "test_value"
        assert log_retention_sync.get_env("TEST_LOG_VAR") == "test_value"
        del os.environ["TEST_LOG_VAR"]

    def test_get_env_returns_default(self):
        """Test get_env returns default when var not set."""
        assert log_retention_sync.get_env("NONEXISTENT_LOG_VAR", "default") == "default"

    def test_get_env_returns_empty_string_by_default(self):
        """Test get_env returns empty string when no default."""
        assert log_retention_sync.get_env("NONEXISTENT_LOG_VAR_2") == ""


class TestGetLogGroupsByPrefix:
    """Tests for get_log_groups_by_prefix function."""

    def test_get_log_groups_success(self):
        """Test successful retrieval of log groups."""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {"logGroupName": "/aws/lambda/aura-test-1"},
                    {"logGroupName": "/aws/lambda/aura-test-2"},
                ]
            }
        ]

        mock_logs = MagicMock()
        mock_logs.get_paginator.return_value = mock_paginator

        with patch.object(
            log_retention_sync, "get_logs_client", return_value=mock_logs
        ):
            result = log_retention_sync.get_log_groups_by_prefix("/aws/lambda/aura")

            assert len(result) == 2
            assert result[0]["logGroupName"] == "/aws/lambda/aura-test-1"

    def test_get_log_groups_empty(self):
        """Test retrieval when no log groups match."""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"logGroups": []}]

        mock_logs = MagicMock()
        mock_logs.get_paginator.return_value = mock_paginator

        with patch.object(
            log_retention_sync, "get_logs_client", return_value=mock_logs
        ):
            result = log_retention_sync.get_log_groups_by_prefix("/nonexistent/prefix")

            assert len(result) == 0

    def test_get_log_groups_error(self):
        """Test error handling in log group retrieval."""
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "DescribeLogGroups",
        )

        mock_logs = MagicMock()
        mock_logs.get_paginator.return_value = mock_paginator

        with patch.object(
            log_retention_sync, "get_logs_client", return_value=mock_logs
        ):
            result = log_retention_sync.get_log_groups_by_prefix("/aws/lambda/aura")

            assert len(result) == 0


class TestUpdateLogGroupRetention:
    """Tests for update_log_group_retention function."""

    def test_update_success(self):
        """Test successful retention update."""
        mock_logs = MagicMock()
        mock_logs.describe_log_groups.return_value = {
            "logGroups": [
                {"logGroupName": "/aws/lambda/aura-test", "retentionInDays": 30}
            ]
        }
        mock_logs.put_retention_policy.return_value = {}

        with patch.object(
            log_retention_sync, "get_logs_client", return_value=mock_logs
        ):
            result = log_retention_sync.update_log_group_retention(
                "/aws/lambda/aura-test", 90, dry_run=False
            )

            assert result["success"] is True
            assert result["previousRetention"] == 30
            assert result["newRetention"] == 90
            mock_logs.put_retention_policy.assert_called_once()

    def test_update_already_at_target(self):
        """Test that update is skipped when already at target retention."""
        mock_logs = MagicMock()
        mock_logs.describe_log_groups.return_value = {
            "logGroups": [
                {"logGroupName": "/aws/lambda/aura-test", "retentionInDays": 90}
            ]
        }

        with patch.object(
            log_retention_sync, "get_logs_client", return_value=mock_logs
        ):
            result = log_retention_sync.update_log_group_retention(
                "/aws/lambda/aura-test", 90, dry_run=False
            )

            assert result["success"] is True
            assert result["skipped"] is True
            mock_logs.put_retention_policy.assert_not_called()

    def test_update_dry_run(self):
        """Test dry run mode doesn't apply changes."""
        mock_logs = MagicMock()
        mock_logs.describe_log_groups.return_value = {
            "logGroups": [
                {"logGroupName": "/aws/lambda/aura-test", "retentionInDays": 30}
            ]
        }

        with patch.object(
            log_retention_sync, "get_logs_client", return_value=mock_logs
        ):
            result = log_retention_sync.update_log_group_retention(
                "/aws/lambda/aura-test", 90, dry_run=True
            )

            assert result["success"] is True
            assert result["dryRun"] is True
            mock_logs.put_retention_policy.assert_not_called()

    def test_update_log_group_not_found(self):
        """Test handling when log group doesn't exist."""
        mock_logs = MagicMock()
        mock_logs.describe_log_groups.return_value = {"logGroups": []}

        with patch.object(
            log_retention_sync, "get_logs_client", return_value=mock_logs
        ):
            result = log_retention_sync.update_log_group_retention(
                "/aws/lambda/nonexistent", 90, dry_run=False
            )

            assert result["success"] is False
            assert "not found" in result["message"]

    def test_update_error(self):
        """Test error handling during update."""
        mock_logs = MagicMock()
        mock_logs.describe_log_groups.return_value = {
            "logGroups": [
                {"logGroupName": "/aws/lambda/aura-test", "retentionInDays": 30}
            ]
        }
        mock_logs.put_retention_policy.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterException", "Message": "Invalid"}},
            "PutRetentionPolicy",
        )

        with patch.object(
            log_retention_sync, "get_logs_client", return_value=mock_logs
        ):
            result = log_retention_sync.update_log_group_retention(
                "/aws/lambda/aura-test", 90, dry_run=False
            )

            assert result["success"] is False
            assert "Failed" in result["message"]


class TestLambdaHandler:
    """Tests for the main lambda_handler function."""

    def test_handler_missing_retention_days(self):
        """Test handler returns 400 when retention_days is missing."""
        event = {}
        context = MagicMock()

        response = log_retention_sync.lambda_handler(event, context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["status"] == "error"
        assert "retention_days is required" in body["error"]

    def test_handler_basic_invocation(self):
        """Test basic Lambda invocation with mocked log groups."""
        event = {"retention_days": 90, "dry_run": True}
        context = MagicMock()

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            mock_get_groups.return_value = [
                {"logGroupName": "/aws/lambda/aura-test-1"},
                {"logGroupName": "/aws/lambda/aura-test-2"},
            ]

            with patch.object(
                log_retention_sync, "update_log_group_retention"
            ) as mock_update:
                mock_update.return_value = {
                    "success": True,
                    "dryRun": True,
                    "message": "DRY RUN",
                }

                response = log_retention_sync.lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"
        assert body["dry_run"] is True
        assert body["retention_days"] == 90

    def test_handler_with_custom_prefixes(self):
        """Test handler with custom log group prefixes."""
        event = {
            "retention_days": 90,
            "dry_run": True,
            "prefixes": ["/custom/prefix"],
        }
        context = MagicMock()

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            mock_get_groups.return_value = []

            response = log_retention_sync.lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "/custom/prefix" in body["prefixes_searched"]

    def test_handler_deduplicates_log_groups(self):
        """Test that handler deduplicates overlapping log groups."""
        event = {"retention_days": 90, "dry_run": True}
        context = MagicMock()

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            # Return same log group from multiple prefixes
            mock_get_groups.side_effect = [
                [{"logGroupName": "/aws/lambda/aura-test"}],
                [{"logGroupName": "/aws/lambda/aura-test"}],  # duplicate
                [],
                [],
                [],
            ]

            with patch.object(
                log_retention_sync, "update_log_group_retention"
            ) as mock_update:
                mock_update.return_value = {"success": True, "dryRun": True}

                response = log_retention_sync.lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        # Should only process 1 unique log group
        assert body["statistics"]["total_log_groups"] == 1
        mock_update.assert_called_once()

    def test_handler_error_returns_500(self):
        """Test that errors return 500 status code."""
        event = {"retention_days": 90}
        context = MagicMock()

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            mock_get_groups.side_effect = Exception("Unexpected error")

            response = log_retention_sync.lambda_handler(event, context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["status"] == "error"

    def test_handler_sends_sns_notification(self):
        """Test that SNS notification is sent on successful update."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789:test-topic"

        event = {"retention_days": 90, "dry_run": False}
        context = MagicMock()

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            mock_get_groups.return_value = [{"logGroupName": "/aws/lambda/aura-test"}]

            with patch.object(
                log_retention_sync, "update_log_group_retention"
            ) as mock_update:
                mock_update.return_value = {"success": True, "newRetention": 90}

                with patch.object(
                    log_retention_sync, "send_notification"
                ) as mock_notify:
                    response = log_retention_sync.lambda_handler(event, context)
                    mock_notify.assert_called_once()

        del os.environ["SNS_TOPIC_ARN"]
        assert response["statusCode"] == 200


class TestSendNotification:
    """Tests for SNS notification functions."""

    def test_send_notification_success(self):
        """Test successful SNS notification."""
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "123"}

        with patch.object(log_retention_sync, "get_sns_client", return_value=mock_sns):
            result_data = {
                "status": "success",
                "environment": "dev",
                "retention_days": 90,
                "statistics": {
                    "total_log_groups": 10,
                    "updated": 8,
                    "skipped": 2,
                    "failed": 0,
                },
                "prefixes_searched": ["/aws/lambda/aura"],
            }

            log_retention_sync.send_notification(
                "arn:aws:sns:us-east-1:123456789:test", result_data
            )
            mock_sns.publish.assert_called_once()

    def test_send_notification_error_handled(self):
        """Test that notification errors are handled gracefully."""
        mock_sns = MagicMock()
        mock_sns.publish.side_effect = ClientError(
            {"Error": {"Code": "TopicNotFound", "Message": "Topic not found"}},
            "Publish",
        )

        with patch.object(log_retention_sync, "get_sns_client", return_value=mock_sns):
            result_data = {"status": "success", "statistics": {}}

            # Should not raise exception
            log_retention_sync.send_notification(
                "arn:aws:sns:us-east-1:123456789:nonexistent", result_data
            )

    def test_send_error_notification(self):
        """Test error notification is sent correctly."""
        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "456"}

        with patch.object(log_retention_sync, "get_sns_client", return_value=mock_sns):
            error_data = {
                "status": "error",
                "error": "Test failure",
            }

            log_retention_sync.send_error_notification(
                "arn:aws:sns:us-east-1:123456789:test", error_data
            )
            mock_sns.publish.assert_called_once()


class TestStatisticsAccuracy:
    """Tests for statistics counting accuracy."""

    def test_statistics_counts_correctly(self):
        """Test that statistics accurately reflect update results."""
        event = {"retention_days": 90, "dry_run": False}
        context = MagicMock()

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            mock_get_groups.return_value = [
                {"logGroupName": "/aws/lambda/aura-test-1"},
                {"logGroupName": "/aws/lambda/aura-test-2"},
                {"logGroupName": "/aws/lambda/aura-test-3"},
            ]

            update_results = [
                {"success": True, "newRetention": 90},  # updated
                {"success": True, "skipped": True},  # skipped
                {"success": False, "message": "Error"},  # failed
            ]

            with patch.object(
                log_retention_sync, "update_log_group_retention"
            ) as mock_update:
                mock_update.side_effect = update_results

                response = log_retention_sync.lambda_handler(event, context)

        body = json.loads(response["body"])
        stats = body["statistics"]
        assert stats["total_log_groups"] == 3
        assert stats["updated"] == 1
        assert stats["skipped"] == 1
        assert stats["failed"] == 1
        assert body["status"] == "partial_success"


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_retention_normalized_in_response(self):
        """Test that normalized retention value is returned."""
        event = {"retention_days": 45, "dry_run": True}  # 45 is not valid
        context = MagicMock()

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            mock_get_groups.return_value = []

            response = log_retention_sync.lambda_handler(event, context)

        body = json.loads(response["body"])
        assert body["retention_days"] == 60  # Normalized to 60

    def test_env_prefixes_parsing(self):
        """Test that LOG_GROUP_PREFIXES env var is parsed correctly."""
        os.environ["LOG_GROUP_PREFIXES"] = "/prefix1,/prefix2,/prefix3"

        event = {"retention_days": 90, "dry_run": True}
        context = MagicMock()

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            mock_get_groups.return_value = []

            response = log_retention_sync.lambda_handler(event, context)

        body = json.loads(response["body"])
        assert "/prefix1" in body["prefixes_searched"]
        assert "/prefix2" in body["prefixes_searched"]
        assert "/prefix3" in body["prefixes_searched"]

        del os.environ["LOG_GROUP_PREFIXES"]

    def test_large_result_set_truncated(self):
        """Test that large result sets only include non-skipped items in details."""
        event = {"retention_days": 90, "dry_run": False}
        context = MagicMock()

        # Generate 60 log groups
        log_groups = [{"logGroupName": f"/aws/lambda/aura-test-{i}"} for i in range(60)]

        with patch.object(
            log_retention_sync, "get_log_groups_by_prefix"
        ) as mock_get_groups:
            mock_get_groups.return_value = log_groups

            # Most are skipped, one fails
            def update_side_effect(name, days, dry_run):
                if "test-0" in name:
                    return {"success": False, "message": "Error"}
                return {"success": True, "skipped": True}

            with patch.object(
                log_retention_sync, "update_log_group_retention"
            ) as mock_update:
                mock_update.side_effect = update_side_effect

                response = log_retention_sync.lambda_handler(event, context)

        body = json.loads(response["body"])
        # Details should only include the failed one (not all 60)
        assert len(body["details"]) < 60
