"""
Project Aura - DNS Blocklist Updater Lambda Tests

Tests for the Lambda handler that updates DNS blocklists from threat intelligence.
Uses moto fixtures from conftest.py for AWS service mocking.

Target: 85% coverage of src/lambda/dns_blocklist_updater.py
"""

import importlib
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set environment and AWS region before importing Lambda
# (Lambda creates boto3 clients at module load time)
os.environ["ENVIRONMENT"] = "dev"
os.environ["PROJECT_NAME"] = "aura"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

# Clear module from cache to ensure fresh import with correct environment
_module_name = "src.lambda.dns_blocklist_updater"
if _module_name in sys.modules:
    del sys.modules[_module_name]

# Import the lambda module using importlib (lambda is a reserved keyword)
dns_blocklist = importlib.import_module(_module_name)


class TestLambdaHandler:
    """Tests for the main lambda_handler function."""

    def test_handler_basic_invocation(self, mock_aws_services):
        """Test basic Lambda invocation returns expected structure."""
        event = {"dry_run": True}
        context = MagicMock()

        # Patch the async function directly to avoid unawaited coroutine warning
        with patch.object(
            dns_blocklist,
            "generate_and_deploy_blocklist",
            new_callable=AsyncMock,
            return_value={
                "status": "success",
                "dry_run": True,
                "statistics": {"total_entries": 10},
            },
        ):
            response = dns_blocklist.lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"

    def test_handler_with_force_refresh(self, mock_aws_services):
        """Test Lambda with force_refresh flag."""
        event = {"force_refresh": True, "dry_run": True}
        context = MagicMock()

        # Patch the async function directly to avoid unawaited coroutine warning
        with patch.object(
            dns_blocklist,
            "generate_and_deploy_blocklist",
            new_callable=AsyncMock,
            return_value={
                "status": "success",
                "dry_run": True,
                "force_refresh": True,
                "statistics": {"total_entries": 5},
            },
        ):
            response = dns_blocklist.lambda_handler(event, context)

        assert response["statusCode"] == 200

    def test_handler_error_returns_500(self, mock_aws_services):
        """Test that errors return 500 status code."""
        event = {}
        context = MagicMock()

        # Patch the async function directly to avoid unawaited coroutine warning
        with patch.object(
            dns_blocklist,
            "generate_and_deploy_blocklist",
            new_callable=AsyncMock,
            side_effect=Exception("Test error"),
        ):
            response = dns_blocklist.lambda_handler(event, context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["status"] == "error"
        assert "Test error" in body["error"]

    def test_handler_sends_sns_notification(self, mock_notification_topics):
        """Test that SNS notification is sent on success."""
        topic_arn = mock_notification_topics["topics"]["aura-critical-anomalies-dev"]
        os.environ["SNS_TOPIC_ARN"] = topic_arn

        event = {"dry_run": False}
        context = MagicMock()

        # Patch the async function directly to avoid unawaited coroutine warning
        with patch.object(
            dns_blocklist,
            "generate_and_deploy_blocklist",
            new_callable=AsyncMock,
            return_value={
                "status": "success",
                "statistics": {"total_entries": 10},
            },
        ):
            with patch.object(dns_blocklist, "send_notification") as mock_notify:
                dns_blocklist.lambda_handler(event, context)
                mock_notify.assert_called_once()

        del os.environ["SNS_TOPIC_ARN"]


class TestGetEnv:
    """Tests for get_env helper function."""

    def test_get_env_returns_value(self):
        """Test get_env returns environment variable value."""
        os.environ["TEST_VAR"] = "test_value"
        assert dns_blocklist.get_env("TEST_VAR") == "test_value"
        del os.environ["TEST_VAR"]

    def test_get_env_returns_default(self):
        """Test get_env returns default when var not set."""
        assert dns_blocklist.get_env("NONEXISTENT_VAR", "default") == "default"

    def test_get_env_returns_empty_string_by_default(self):
        """Test get_env returns empty string when no default."""
        assert dns_blocklist.get_env("NONEXISTENT_VAR") == ""


class TestGenerateMockBlocklist:
    """Tests for generate_mock_blocklist function."""

    @pytest.mark.asyncio
    async def test_mock_blocklist_dry_run(self):
        """Test mock blocklist generation in dry run mode."""
        result = await dns_blocklist.generate_mock_blocklist(dry_run=True)

        assert result["status"] == "success"
        assert result["dry_run"] is True
        assert result["mock_mode"] is True
        assert "statistics" in result
        assert result["statistics"]["total_entries"] == 4

    @pytest.mark.asyncio
    async def test_mock_blocklist_has_categories(self):
        """Test mock blocklist includes all threat categories."""
        result = await dns_blocklist.generate_mock_blocklist(dry_run=False)

        categories = result["statistics"]["entries_by_category"]
        assert "malware" in categories
        assert "c2" in categories
        assert "phishing" in categories


class TestUploadToS3:
    """Tests for S3 upload functionality."""

    def test_upload_to_s3_success(self, mock_blocklist_bucket):
        """Test successful S3 upload."""
        mock_s3 = MagicMock()
        mock_s3.put_object.return_value = {"ETag": '"abc123"'}

        with patch.object(dns_blocklist, "get_s3_client", return_value=mock_s3):
            result = dns_blocklist.upload_to_s3(
                bucket="aura-dns-blocklist-dev",
                key="dnsmasq/blocklist.conf",
                content="# test config",
            )

            assert result["success"] is True
            assert result["bucket"] == "aura-dns-blocklist-dev"
            assert result["key"] == "dnsmasq/blocklist.conf"
            mock_s3.put_object.assert_called_once()

    def test_upload_to_s3_error(self):
        """Test S3 upload error handling."""
        from botocore.exceptions import ClientError

        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            "PutObject",
        )

        with patch.object(dns_blocklist, "get_s3_client", return_value=mock_s3):
            result = dns_blocklist.upload_to_s3(
                bucket="nonexistent-bucket",
                key="test.conf",
                content="# test",
            )

            assert result["success"] is False
            assert "error" in result


class TestSendNotification:
    """Tests for SNS notification functions."""

    def test_send_notification_success(self, mock_notification_topics):
        """Test successful SNS notification."""
        topic_arn = mock_notification_topics["topics"]["aura-critical-anomalies-dev"]

        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "123"}

        with patch.object(dns_blocklist, "get_sns_client", return_value=mock_sns):
            result_data = {
                "status": "success",
                "statistics": {"total_entries": 100},
            }

            dns_blocklist.send_notification(topic_arn, result_data)
            mock_sns.publish.assert_called_once()

    def test_send_error_notification(self, mock_notification_topics):
        """Test error notification is sent correctly."""
        topic_arn = mock_notification_topics["topics"]["aura-security-alerts-dev"]

        mock_sns = MagicMock()
        mock_sns.publish.return_value = {"MessageId": "456"}

        with patch.object(dns_blocklist, "get_sns_client", return_value=mock_sns):
            error_data = {
                "status": "error",
                "error": "Test failure",
            }

            dns_blocklist.send_error_notification(topic_arn, error_data)
            mock_sns.publish.assert_called_once()


class TestGenerateAndDeployBlocklist:
    """Tests for the main blocklist generation and deployment function."""

    @pytest.mark.asyncio
    async def test_generate_blocklist_dry_run_mock_mode(self):
        """Test blocklist generation falls back to mock when service unavailable."""
        # Simulate ImportError by patching the import mechanism
        with patch.object(
            dns_blocklist, "generate_mock_blocklist", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = {
                "status": "success",
                "mock_mode": True,
                "dry_run": True,
                "statistics": {"total_entries": 4},
            }

            # Force the ImportError path
            with patch.dict(
                "sys.modules", {"src.services.dns_blocklist_service": None}
            ):
                result = await dns_blocklist.generate_and_deploy_blocklist(
                    environment="dev",
                    project_name="aura",
                    s3_bucket="test-bucket",
                    enable_k8s=False,
                    force_refresh=False,
                    dry_run=True,
                )

            # Should have called mock blocklist
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_generate_blocklist_with_service(self):
        """Test blocklist generation with real service (mocked)."""
        mock_service = MagicMock()
        mock_service.generate_blocklist = AsyncMock(return_value=[])
        mock_service.get_stats.return_value = {"total_entries": 50}
        mock_service.render_dnsmasq_config.return_value = "# blocklist config"
        mock_service.threat_client = MagicMock()
        mock_service.threat_client.close = AsyncMock()

        # Patch the service creation at the point of import
        with patch(
            "src.services.dns_blocklist_service.create_blocklist_service",
            return_value=mock_service,
        ):
            with patch("src.services.dns_blocklist_service.BlocklistConfig"):
                result = await dns_blocklist.generate_and_deploy_blocklist(
                    environment="dev",
                    project_name="aura",
                    s3_bucket="test-bucket",
                    enable_k8s=False,
                    force_refresh=False,
                    dry_run=True,
                )

        assert result["status"] == "success"
        assert result["dry_run"] is True
        assert "preview" in result


class TestIntegrationWithMoto:
    """Integration tests using full moto mocking."""

    def test_full_lambda_flow_with_mocked_aws(self, mock_aws_services):
        """Test complete Lambda flow with mocked AWS services."""
        mock_aws_services["s3"].create_bucket(Bucket="aura-config-dev")
        topic_response = mock_aws_services["sns"].create_topic(Name="aura-alerts-dev")
        topic_arn = topic_response["TopicArn"]

        os.environ["S3_BUCKET"] = "aura-config-dev"
        os.environ["SNS_TOPIC_ARN"] = topic_arn
        os.environ["ENABLE_K8S_UPDATE"] = "false"

        event = {"dry_run": True}
        context = MagicMock()

        # Patch the async function directly to avoid unawaited coroutine warning
        with patch.object(
            dns_blocklist,
            "generate_and_deploy_blocklist",
            new_callable=AsyncMock,
            return_value={
                "status": "success",
                "dry_run": True,
                "statistics": {"total_entries": 50},
                "message": "Blocklist updated",
            },
        ):
            response = dns_blocklist.lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "success"

        del os.environ["S3_BUCKET"]
        del os.environ["SNS_TOPIC_ARN"]
        del os.environ["ENABLE_K8S_UPDATE"]


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_event(self, mock_aws_services):
        """Test handler with empty event."""
        # Patch the async function directly to avoid unawaited coroutine warning
        with patch.object(
            dns_blocklist,
            "generate_and_deploy_blocklist",
            new_callable=AsyncMock,
            return_value={
                "status": "success",
                "statistics": {"total_entries": 0},
            },
        ):
            response = dns_blocklist.lambda_handler({}, MagicMock())

        assert response["statusCode"] == 200

    def test_malformed_event(self, mock_aws_services):
        """Test handler with unexpected event structure."""
        # Patch the async function directly to avoid unawaited coroutine warning
        with patch.object(
            dns_blocklist,
            "generate_and_deploy_blocklist",
            new_callable=AsyncMock,
            return_value={
                "status": "success",
                "statistics": {"total_entries": 0},
            },
        ):
            response = dns_blocklist.lambda_handler(
                {"unexpected_key": "unexpected_value"}, MagicMock()
            )

        assert response["statusCode"] == 200

    def test_environment_variable_defaults(self):
        """Test that default environment variables are used correctly."""
        result = dns_blocklist.get_env("NONEXISTENT_TOTALLY_RANDOM_VAR", "my_default")
        assert result == "my_default"
