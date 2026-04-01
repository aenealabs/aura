"""
Tests for Orchestrator Dispatcher Lambda

Covers:
- lambda_handler for SQS message processing
- Autonomy configuration (_should_auto_remediate, _should_require_hitl)
- Deployment mode routing (on-demand, warm pool, hybrid)
- Job spec building
- Error handling

Reference: Lambda acts as bridge between SQS and EKS MetaOrchestrator Jobs
"""

import base64
import importlib
import json
import os
import platform

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked
from unittest.mock import MagicMock, patch

# Set environment variables before importing module
os.environ["ENVIRONMENT"] = "dev"
os.environ["PROJECT_NAME"] = "aura"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

MODULE_PATH = "src.lambda.orchestrator_dispatcher"

# Create mock boto3 before importing the module
mock_dynamodb = MagicMock()
mock_dynamodb_client = MagicMock()
mock_eks_client = MagicMock()
mock_sqs_client = MagicMock()

# Patch boto3 at the module level before import
with (
    patch("boto3.resource", return_value=mock_dynamodb),
    patch(
        "boto3.client",
        side_effect=lambda svc, **kwargs: {
            "dynamodb": mock_dynamodb_client,
            "eks": mock_eks_client,
            "sqs": mock_sqs_client,
        }.get(svc, MagicMock()),
    ),
):
    # Import the module using importlib since "lambda" is a Python keyword
    dispatcher = importlib.import_module("src.lambda.orchestrator_dispatcher")


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_aws_clients():
    """Mock all AWS clients."""
    with (
        patch(f"{MODULE_PATH}.dynamodb") as mock_dynamodb,
        patch(f"{MODULE_PATH}.dynamodb_client") as mock_dynamodb_client,
        patch(f"{MODULE_PATH}.eks_client") as mock_eks_client,
        patch(f"{MODULE_PATH}.sqs_client") as mock_sqs_client,
    ):

        # Setup mock table
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        yield {
            "dynamodb": mock_dynamodb,
            "dynamodb_client": mock_dynamodb_client,
            "eks_client": mock_eks_client,
            "sqs_client": mock_sqs_client,
            "table": mock_table,
        }


@pytest.fixture
def sqs_event():
    """Create a sample SQS event."""
    message_body = {
        "task_id": "task-12345",
        "payload": {
            "event_type": "vulnerability_detected",
            "cve_id": "CVE-2024-1234",
            "severity": "medium",
            "title": "Test vulnerability",
        },
        "autonomy_config": {},
    }

    return {
        "Records": [
            {
                "messageId": "msg-001",
                "body": json.dumps(message_body),
            }
        ]
    }


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 256
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
    context.get_remaining_time_in_millis.return_value = 30000
    return context


# =============================================================================
# Autonomy Configuration Tests
# =============================================================================


class TestAutonomyConfiguration:
    """Tests for autonomy decision logic."""

    def test_should_auto_remediate_low_severity_dev(self, mock_aws_clients):
        """Test auto-remediate is enabled for low severity in dev."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "dev"):
            assert dispatcher._should_auto_remediate("low", {}) is True
            assert dispatcher._should_auto_remediate("medium", {}) is True
            assert dispatcher._should_auto_remediate("info", {}) is True

    def test_should_not_auto_remediate_high_severity_dev(self, mock_aws_clients):
        """Test auto-remediate is disabled for high severity in dev."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "dev"):
            assert dispatcher._should_auto_remediate("high", {}) is False
            assert dispatcher._should_auto_remediate("critical", {}) is False

    def test_should_not_auto_remediate_in_prod(self, mock_aws_clients):
        """Test auto-remediate is always disabled in prod."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "prod"):
            assert dispatcher._should_auto_remediate("low", {}) is False
            assert dispatcher._should_auto_remediate("medium", {}) is False
            assert dispatcher._should_auto_remediate("high", {}) is False

    def test_should_auto_remediate_respects_config_override(self, mock_aws_clients):
        """Test auto-remediate respects explicit config."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "dev"):
            # Explicit override to disable
            assert (
                dispatcher._should_auto_remediate("low", {"auto_remediate": False})
                is False
            )
            # Explicit override to enable
            assert (
                dispatcher._should_auto_remediate("high", {"auto_remediate": True})
                is True
            )

    def test_should_require_hitl_in_prod(self, mock_aws_clients):
        """Test HITL is always required in prod."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "prod"):
            assert dispatcher._should_require_hitl("low", {}) is True
            assert dispatcher._should_require_hitl("medium", {}) is True
            assert dispatcher._should_require_hitl("high", {}) is True
            assert dispatcher._should_require_hitl("critical", {}) is True

    def test_should_require_hitl_high_severity_dev(self, mock_aws_clients):
        """Test HITL is required for high/critical in dev."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "dev"):
            assert dispatcher._should_require_hitl("high", {}) is True
            assert dispatcher._should_require_hitl("critical", {}) is True

    def test_should_not_require_hitl_low_severity_dev(self, mock_aws_clients):
        """Test HITL is not required for low/medium in dev."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "dev"):
            assert dispatcher._should_require_hitl("low", {}) is False
            assert dispatcher._should_require_hitl("medium", {}) is False

    def test_should_require_hitl_respects_config_override(self, mock_aws_clients):
        """Test HITL respects explicit config."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "dev"):
            # Explicit override to require
            assert (
                dispatcher._should_require_hitl(
                    "low", {"require_hitl_for_deploy": True}
                )
                is True
            )
            # Explicit override to not require
            assert (
                dispatcher._should_require_hitl(
                    "high", {"require_hitl_for_deploy": False}
                )
                is False
            )


# =============================================================================
# Job Spec Building Tests
# =============================================================================


class TestJobSpecBuilding:
    """Tests for Kubernetes Job spec building."""

    def test_build_job_spec_basic(self, mock_aws_clients):
        """Test building a basic job spec."""
        job_spec = dispatcher._build_job_spec(
            job_id="test-job-001",
            task_id="task-001",
            payload={"severity": "medium", "cve_id": "CVE-2024-1234"},
            autonomy_config={"auto_remediate": True},
        )

        assert job_spec["apiVersion"] == "batch/v1"
        assert job_spec["kind"] == "Job"
        assert job_spec["metadata"]["name"] == "test-job-001"
        assert job_spec["metadata"]["labels"]["job-id"] == "test-job-001"
        assert job_spec["metadata"]["labels"]["task-id"] == "task-001"

    def test_build_job_spec_has_correct_container_resources(self, mock_aws_clients):
        """Test job spec has correct container resources."""
        job_spec = dispatcher._build_job_spec(
            job_id="test-job-002",
            task_id="task-002",
            payload={},
            autonomy_config={},
        )

        container = job_spec["spec"]["template"]["spec"]["containers"][0]
        assert container["resources"]["requests"]["memory"] == "2Gi"
        assert container["resources"]["requests"]["cpu"] == "1"
        assert container["resources"]["limits"]["memory"] == "4Gi"
        assert container["resources"]["limits"]["cpu"] == "2"

    def test_build_job_spec_encodes_payload_as_base64(self, mock_aws_clients):
        """Test that payload is base64 encoded."""
        payload = {"test": "data", "nested": {"value": 123}}
        job_spec = dispatcher._build_job_spec(
            job_id="test-job-003",
            task_id="task-003",
            payload=payload,
            autonomy_config={"auto_remediate": False},
        )

        container = job_spec["spec"]["template"]["spec"]["containers"][0]
        payload_b64_env = next(
            e for e in container["env"] if e["name"] == "TASK_PAYLOAD_B64"
        )

        # Decode and verify
        decoded = json.loads(base64.b64decode(payload_b64_env["value"]))
        assert decoded["payload"] == payload
        assert decoded["task_id"] == "task-003"

    def test_build_job_spec_has_ttl_and_deadline(self, mock_aws_clients):
        """Test job spec has TTL and deadline settings."""
        job_spec = dispatcher._build_job_spec(
            job_id="test-job-004",
            task_id="task-004",
            payload={},
            autonomy_config={},
        )

        assert job_spec["spec"]["ttlSecondsAfterFinished"] == 3600
        assert job_spec["spec"]["backoffLimit"] == 2
        assert job_spec["spec"]["activeDeadlineSeconds"] == 1800

    def test_build_job_spec_has_service_account(self, mock_aws_clients):
        """Test job spec uses correct service account."""
        job_spec = dispatcher._build_job_spec(
            job_id="test-job-005",
            task_id="task-005",
            payload={},
            autonomy_config={},
        )

        assert (
            job_spec["spec"]["template"]["spec"]["serviceAccountName"]
            == "meta-orchestrator"
        )


# =============================================================================
# Deployment Mode Tests
# =============================================================================


class TestDeploymentMode:
    """Tests for deployment mode routing."""

    def test_get_deployment_mode_on_demand(self, mock_aws_clients):
        """Test on-demand mode detection."""
        # Clear cache
        dispatcher._cached_settings = None

        mock_aws_clients["dynamodb_client"].get_item.return_value = {
            "Item": {
                "settings_value": {
                    "S": json.dumps(
                        {
                            "on_demand_jobs_enabled": True,
                            "warm_pool_enabled": False,
                            "hybrid_mode_enabled": False,
                        }
                    )
                }
            }
        }

        mode = dispatcher._get_current_deployment_mode()
        assert mode == dispatcher.DeploymentMode.ON_DEMAND

    def test_get_deployment_mode_warm_pool(self, mock_aws_clients):
        """Test warm pool mode detection."""
        # Clear cache
        dispatcher._cached_settings = None

        mock_aws_clients["dynamodb_client"].get_item.return_value = {
            "Item": {
                "settings_value": {
                    "S": json.dumps(
                        {
                            "warm_pool_enabled": True,
                            "hybrid_mode_enabled": False,
                        }
                    )
                }
            }
        }

        mode = dispatcher._get_current_deployment_mode()
        assert mode == dispatcher.DeploymentMode.WARM_POOL

    def test_get_deployment_mode_hybrid(self, mock_aws_clients):
        """Test hybrid mode detection."""
        # Clear cache
        dispatcher._cached_settings = None

        mock_aws_clients["dynamodb_client"].get_item.return_value = {
            "Item": {
                "settings_value": {
                    "S": json.dumps(
                        {
                            "warm_pool_enabled": True,
                            "hybrid_mode_enabled": True,
                        }
                    )
                }
            }
        }

        mode = dispatcher._get_current_deployment_mode()
        assert mode == dispatcher.DeploymentMode.HYBRID

    def test_get_orchestrator_settings_caching(self, mock_aws_clients):
        """Test that settings are cached."""
        # Clear cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        mock_aws_clients["dynamodb_client"].get_item.return_value = {
            "Item": {"settings_value": {"S": json.dumps({"warm_pool_enabled": True})}}
        }

        # First call - should hit DynamoDB
        settings1 = dispatcher._get_orchestrator_settings()

        # Second call - should use cache
        settings2 = dispatcher._get_orchestrator_settings()

        # DynamoDB should only be called once
        assert mock_aws_clients["dynamodb_client"].get_item.call_count == 1
        assert settings1 == settings2

    def test_get_orchestrator_settings_defaults_on_error(self, mock_aws_clients):
        """Test that defaults are used on error."""
        from botocore.exceptions import ClientError

        # Clear cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        mock_aws_clients["dynamodb_client"].get_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetItem",
        )

        settings = dispatcher._get_orchestrator_settings()

        assert settings["on_demand_jobs_enabled"] is True
        assert settings["warm_pool_enabled"] is False

    def test_route_to_warm_pool(self, mock_aws_clients):
        """Test routing to warm pool queue."""
        mock_aws_clients["sqs_client"].send_message.return_value = {
            "MessageId": "sqs-msg-001"
        }

        with patch(f"{MODULE_PATH}.WARM_POOL_QUEUE_URL", "https://sqs.queue.url"):
            result = dispatcher._route_to_warm_pool(
                job_id="job-001",
                task_id="task-001",
                payload={"severity": "medium"},
                autonomy_config={},
            )

        assert result["success"] is True
        assert result["info"]["routing_mode"] == "warm_pool"
        assert result["info"]["message_id"] == "sqs-msg-001"

    def test_route_to_warm_pool_no_queue_url(self, mock_aws_clients):
        """Test routing fails when no queue URL configured."""
        with patch(f"{MODULE_PATH}.WARM_POOL_QUEUE_URL", ""):
            result = dispatcher._route_to_warm_pool(
                job_id="job-001",
                task_id="task-001",
                payload={},
                autonomy_config={},
            )

        assert result["success"] is False
        assert "not configured" in result["error"]

    def test_get_warm_pool_queue_depth(self, mock_aws_clients):
        """Test getting queue depth."""
        mock_aws_clients["sqs_client"].get_queue_attributes.return_value = {
            "Attributes": {"ApproximateNumberOfMessages": "10"}
        }

        with patch(f"{MODULE_PATH}.WARM_POOL_QUEUE_URL", "https://sqs.queue.url"):
            depth = dispatcher._get_warm_pool_queue_depth()

        assert depth == 10


# =============================================================================
# Lambda Handler Tests
# =============================================================================


class TestLambdaHandler:
    """Tests for the main lambda handler."""

    def test_lambda_handler_success(self, mock_aws_clients, sqs_event, lambda_context):
        """Test successful message processing."""
        # Clear settings cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        mock_aws_clients["dynamodb_client"].get_item.return_value = {}

        # Mock STS client for _get_eks_token
        mock_sts = MagicMock()
        mock_sts.generate_presigned_url.return_value = "https://sts.amazonaws.com/test"

        # Patch both eks_client and boto3.client for STS
        with (
            patch.object(dispatcher, "eks_client") as patched_eks,
            patch(f"{MODULE_PATH}.boto3.client", return_value=mock_sts),
        ):
            patched_eks.describe_cluster.return_value = {
                "cluster": {
                    "endpoint": "https://eks.endpoint",
                    "certificateAuthority": {"data": "base64ca"},
                }
            }

            result = dispatcher.lambda_handler(sqs_event, lambda_context)

            assert result["batchItemFailures"] == []
            mock_aws_clients["table"].put_item.assert_called_once()

    def test_lambda_handler_empty_event(self, mock_aws_clients, lambda_context):
        """Test handling empty event."""
        result = dispatcher.lambda_handler({"Records": []}, lambda_context)

        assert result["batchItemFailures"] == []

    def test_lambda_handler_invalid_json(self, mock_aws_clients, lambda_context):
        """Test handling invalid JSON in message."""
        event = {
            "Records": [
                {
                    "messageId": "msg-invalid",
                    "body": "not valid json",
                }
            ]
        }

        result = dispatcher.lambda_handler(event, lambda_context)

        # Should report failure for this message
        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-invalid"

    def test_lambda_handler_dynamodb_error(
        self, mock_aws_clients, sqs_event, lambda_context
    ):
        """Test handling DynamoDB error."""
        from botocore.exceptions import ClientError

        mock_aws_clients["table"].put_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Rate exceeded",
                }
            },
            "PutItem",
        )

        result = dispatcher.lambda_handler(sqs_event, lambda_context)

        # Should report failure
        assert len(result["batchItemFailures"]) == 1

    def test_lambda_handler_updates_job_status_on_success(
        self, mock_aws_clients, sqs_event, lambda_context
    ):
        """Test that job status is updated to DISPATCHED on success."""
        # Clear settings cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        mock_aws_clients["dynamodb_client"].get_item.return_value = {}
        mock_aws_clients["eks_client"].describe_cluster.return_value = {
            "cluster": {
                "endpoint": "https://eks.endpoint",
                "certificateAuthority": {"data": "base64ca"},
            }
        }

        dispatcher.lambda_handler(sqs_event, lambda_context)

        # Check that update_item was called with DISPATCHED status
        update_call = mock_aws_clients["table"].update_item.call_args
        assert ":status" in str(update_call)

    def test_lambda_handler_batch_processing(self, mock_aws_clients, lambda_context):
        """Test processing multiple messages in a batch."""
        # Clear settings cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        mock_aws_clients["dynamodb_client"].get_item.return_value = {}

        # Mock STS client for _get_eks_token
        mock_sts = MagicMock()
        mock_sts.generate_presigned_url.return_value = "https://sts.amazonaws.com/test"

        # Patch both eks_client and boto3.client for STS
        with (
            patch.object(dispatcher, "eks_client") as patched_eks,
            patch(f"{MODULE_PATH}.boto3.client", return_value=mock_sts),
        ):
            patched_eks.describe_cluster.return_value = {
                "cluster": {
                    "endpoint": "https://eks.endpoint",
                    "certificateAuthority": {"data": "base64ca"},
                }
            }

            event = {
                "Records": [
                    {
                        "messageId": f"msg-{i}",
                        "body": json.dumps(
                            {
                                "task_id": f"task-{i}",
                                "payload": {"severity": "low"},
                            }
                        ),
                    }
                    for i in range(3)
                ]
            }

            result = dispatcher.lambda_handler(event, lambda_context)

            assert result["batchItemFailures"] == []
            assert mock_aws_clients["table"].put_item.call_count == 3

    def test_lambda_handler_warm_pool_routing(
        self, mock_aws_clients, sqs_event, lambda_context
    ):
        """Test routing to warm pool mode."""
        # Clear settings cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        # Configure warm pool mode
        mock_aws_clients["dynamodb_client"].get_item.return_value = {
            "Item": {
                "settings_value": {
                    "S": json.dumps(
                        {
                            "warm_pool_enabled": True,
                            "hybrid_mode_enabled": False,
                        }
                    )
                }
            }
        }
        mock_aws_clients["sqs_client"].send_message.return_value = {
            "MessageId": "warm-msg"
        }

        with patch(f"{MODULE_PATH}.WARM_POOL_QUEUE_URL", "https://warm.queue.url"):
            result = dispatcher.lambda_handler(sqs_event, lambda_context)

        assert result["batchItemFailures"] == []
        mock_aws_clients["sqs_client"].send_message.assert_called_once()

    def test_lambda_handler_hybrid_mode_warm_pool_path(
        self, mock_aws_clients, sqs_event, lambda_context
    ):
        """Test hybrid mode routes to warm pool when queue depth is low."""
        # Clear settings cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        # Configure hybrid mode
        mock_aws_clients["dynamodb_client"].get_item.return_value = {
            "Item": {
                "settings_value": {
                    "S": json.dumps(
                        {
                            "warm_pool_enabled": True,
                            "hybrid_mode_enabled": True,
                            "hybrid_threshold_queue_depth": 5,
                        }
                    )
                }
            }
        }
        # Queue depth below threshold
        mock_aws_clients["sqs_client"].get_queue_attributes.return_value = {
            "Attributes": {"ApproximateNumberOfMessages": "2"}
        }
        mock_aws_clients["sqs_client"].send_message.return_value = {
            "MessageId": "hybrid-msg"
        }

        with patch(f"{MODULE_PATH}.WARM_POOL_QUEUE_URL", "https://warm.queue.url"):
            result = dispatcher.lambda_handler(sqs_event, lambda_context)

        assert result["batchItemFailures"] == []
        mock_aws_clients["sqs_client"].send_message.assert_called_once()

    def test_lambda_handler_hybrid_mode_burst_path(
        self, mock_aws_clients, sqs_event, lambda_context
    ):
        """Test hybrid mode creates burst job when queue depth is high."""
        # Clear settings cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        # Configure hybrid mode
        mock_aws_clients["dynamodb_client"].get_item.return_value = {
            "Item": {
                "settings_value": {
                    "S": json.dumps(
                        {
                            "warm_pool_enabled": True,
                            "hybrid_mode_enabled": True,
                            "hybrid_threshold_queue_depth": 5,
                        }
                    )
                }
            }
        }
        # Queue depth above threshold
        mock_aws_clients["sqs_client"].get_queue_attributes.return_value = {
            "Attributes": {"ApproximateNumberOfMessages": "10"}
        }

        # Mock STS client for _get_eks_token
        mock_sts = MagicMock()
        mock_sts.generate_presigned_url.return_value = "https://sts.amazonaws.com/test"

        with (
            patch.object(dispatcher, "eks_client") as patched_eks,
            patch(f"{MODULE_PATH}.boto3.client", return_value=mock_sts),
        ):
            patched_eks.describe_cluster.return_value = {
                "cluster": {
                    "endpoint": "https://eks.endpoint",
                    "certificateAuthority": {"data": "base64ca"},
                }
            }

            with patch(f"{MODULE_PATH}.WARM_POOL_QUEUE_URL", "https://warm.queue.url"):
                result = dispatcher.lambda_handler(sqs_event, lambda_context)

            assert result["batchItemFailures"] == []
            # EKS should be called for burst job
            patched_eks.describe_cluster.assert_called_once()


# =============================================================================
# EKS Dispatch Tests
# =============================================================================


class TestEKSDispatch:
    """Tests for EKS dispatch functionality."""

    def test_dispatch_to_eks_success(self, mock_aws_clients):
        """Test successful dispatch to EKS."""
        # Mock STS client for _get_eks_token
        mock_sts = MagicMock()
        mock_sts.generate_presigned_url.return_value = "https://sts.amazonaws.com/test"

        with (
            patch.object(dispatcher, "eks_client") as patched_eks,
            patch(f"{MODULE_PATH}.boto3.client", return_value=mock_sts),
        ):
            patched_eks.describe_cluster.return_value = {
                "cluster": {
                    "endpoint": "https://eks.endpoint",
                    "certificateAuthority": {"data": "base64ca"},
                }
            }

            job_spec = {"metadata": {"name": "test-job"}}
            result = dispatcher._dispatch_to_eks("test-job", job_spec)

            assert result["success"] is True
            assert result["info"]["method"] == "dynamodb_pickup"

    def test_dispatch_to_eks_missing_endpoint(self, mock_aws_clients):
        """Test dispatch fails when cluster endpoint is missing."""
        with patch.object(dispatcher, "eks_client") as patched_eks:
            patched_eks.describe_cluster.return_value = {"cluster": {}}

            result = dispatcher._dispatch_to_eks("test-job", {})

            assert result["success"] is False
            assert "endpoint" in result["error"].lower()

    def test_dispatch_to_eks_client_error(self, mock_aws_clients):
        """Test dispatch handles EKS client error."""
        from botocore.exceptions import ClientError

        with patch.object(dispatcher, "eks_client") as patched_eks:
            patched_eks.describe_cluster.side_effect = ClientError(
                {
                    "Error": {
                        "Code": "ResourceNotFoundException",
                        "Message": "Cluster not found",
                    }
                },
                "DescribeCluster",
            )

            result = dispatcher._dispatch_to_eks("test-job", {})

            assert result["success"] is False
            assert "error" in result


# =============================================================================
# EKS Token Tests
# =============================================================================


class TestEKSToken:
    """Tests for EKS authentication token generation."""

    def test_get_eks_token_format(self, mock_aws_clients):
        """Test EKS token has correct format."""
        with patch(f"{MODULE_PATH}.boto3.client") as mock_boto:
            mock_sts = MagicMock()
            mock_sts.generate_presigned_url.return_value = (
                "https://sts.amazonaws.com/..."
            )
            mock_boto.return_value = mock_sts

            token = dispatcher._get_eks_token("test-cluster")

            assert token.startswith("k8s-aws-v1.")
            # Token should be base64url encoded
            encoded_part = token.split(".")[1]
            # Should be valid base64url (no padding issues)
            assert len(encoded_part) > 0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_task_id_generates_uuid(self, mock_aws_clients, lambda_context):
        """Test that missing task_id generates a UUID."""
        # Clear settings cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        mock_aws_clients["dynamodb_client"].get_item.return_value = {}

        # Mock STS client for _get_eks_token
        mock_sts = MagicMock()
        mock_sts.generate_presigned_url.return_value = "https://sts.amazonaws.com/test"

        with (
            patch.object(dispatcher, "eks_client") as patched_eks,
            patch(f"{MODULE_PATH}.boto3.client", return_value=mock_sts),
        ):
            patched_eks.describe_cluster.return_value = {
                "cluster": {
                    "endpoint": "https://eks.endpoint",
                    "certificateAuthority": {"data": "base64ca"},
                }
            }

            event = {
                "Records": [
                    {
                        "messageId": "msg-no-task-id",
                        "body": json.dumps({"payload": {"severity": "low"}}),
                    }
                ]
            }

            result = dispatcher.lambda_handler(event, lambda_context)

            assert result["batchItemFailures"] == []
            # Check that put_item was called with a generated task_id
            call_args = mock_aws_clients["table"].put_item.call_args
            item = call_args[1]["Item"]
            assert item["task_id"].startswith("task-")

    def test_empty_payload(self, mock_aws_clients, lambda_context):
        """Test handling empty payload."""
        # Clear settings cache
        dispatcher._cached_settings = None
        dispatcher._settings_cache_time = 0

        mock_aws_clients["dynamodb_client"].get_item.return_value = {}

        # Mock STS client for _get_eks_token
        mock_sts = MagicMock()
        mock_sts.generate_presigned_url.return_value = "https://sts.amazonaws.com/test"

        with (
            patch.object(dispatcher, "eks_client") as patched_eks,
            patch(f"{MODULE_PATH}.boto3.client", return_value=mock_sts),
        ):
            patched_eks.describe_cluster.return_value = {
                "cluster": {
                    "endpoint": "https://eks.endpoint",
                    "certificateAuthority": {"data": "base64ca"},
                }
            }

            event = {
                "Records": [
                    {
                        "messageId": "msg-empty",
                        "body": json.dumps({}),
                    }
                ]
            }

            result = dispatcher.lambda_handler(event, lambda_context)

            # Should succeed with defaults
            assert result["batchItemFailures"] == []

    def test_severity_case_insensitive(self, mock_aws_clients):
        """Test that severity comparison is case insensitive."""
        with patch(f"{MODULE_PATH}.ENVIRONMENT", "dev"):
            assert dispatcher._should_auto_remediate("LOW", {}) is True
            assert dispatcher._should_auto_remediate("Low", {}) is True
            assert dispatcher._should_auto_remediate("MEDIUM", {}) is True
            assert dispatcher._should_auto_remediate("HIGH", {}) is False
            assert dispatcher._should_auto_remediate("CRITICAL", {}) is False
