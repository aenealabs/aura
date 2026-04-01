"""
Tests for Environment Provisioner Lambda Handler.
"""

from __future__ import annotations

import importlib
import platform
from unittest.mock import MagicMock, patch

import pytest

# These tests require pytest-forked for isolation due to AWS mock state.
# On Linux (CI), mock patches don't apply correctly without forked mode.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Mock environment variables before import
# Note: 'lambda' is a reserved keyword, so we use importlib
with patch.dict(
    "os.environ",
    {
        "STATE_TABLE": "test-state-table",
        "PROJECT_NAME": "aura",
        "ENVIRONMENT": "dev",
        "NOTIFICATIONS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "SERVICE_CATALOG_PORTFOLIO_ID": "port-abc123",
    },
):
    # Import module using importlib to handle 'lambda' reserved keyword
    environment_provisioner = importlib.import_module(
        "src.lambda.environment_provisioner"
    )

    ProvisioningError = environment_provisioner.ProvisioningError
    build_provisioning_parameters = (
        environment_provisioner.build_provisioning_parameters
    )
    check_provisioning_status = environment_provisioner.check_provisioning_status
    get_product_id_for_template = environment_provisioner.get_product_id_for_template
    get_provisioning_artifact_id = environment_provisioner.get_provisioning_artifact_id
    handler = environment_provisioner.handler
    provision_environment = environment_provisioner.provision_environment
    send_notification = environment_provisioner.send_notification
    status_handler = environment_provisioner.status_handler
    update_environment_state = environment_provisioner.update_environment_state


class TestBuildProvisioningParameters:
    """Tests for build_provisioning_parameters function."""

    def test_basic_parameters(self):
        """Test building basic provisioning parameters."""
        params = build_provisioning_parameters(
            environment_id="env-123",
            user_id="user-456",
            display_name="Test Environment",
            ttl_hours=24,
        )

        assert len(params) == 4
        assert {"Key": "EnvironmentId", "Value": "env-123"} in params
        assert {"Key": "UserId", "Value": "user-456"} in params
        assert {"Key": "DisplayName", "Value": "Test Environment"} in params
        assert {"Key": "TTLHours", "Value": "24"} in params

    def test_with_custom_parameters(self):
        """Test building parameters with custom values."""
        params = build_provisioning_parameters(
            environment_id="env-123",
            user_id="user-456",
            display_name="Test Env",
            ttl_hours=48,
            custom_params={"ApiPort": "8080", "Memory": "2048"},
        )

        assert len(params) == 6
        assert {"Key": "ApiPort", "Value": "8080"} in params
        assert {"Key": "Memory", "Value": "2048"} in params


class TestGetProductIdForTemplate:
    """Tests for get_product_id_for_template function."""

    @patch.dict("os.environ", {"SERVICE_CATALOG_PORTFOLIO_ID": "port-test123"})
    @patch("src.lambda.environment_provisioner.get_sc_client")
    def test_finds_matching_product(self, mock_get_sc):
        """Test finding a matching product in the portfolio."""
        mock_sc = MagicMock()
        mock_get_sc.return_value = mock_sc
        mock_paginator = MagicMock()
        mock_sc.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "ProductViewDetails": [
                    {
                        "ProductViewSummary": {
                            "ProductId": "prod-abc123",
                            "Name": "Quick Test",
                        }
                    },
                    {
                        "ProductViewSummary": {
                            "ProductId": "prod-def456",
                            "Name": "Python FastAPI",
                        }
                    },
                ]
            }
        ]

        # Clear the cache
        environment_provisioner.TEMPLATE_PRODUCT_MAP.clear()

        result = get_product_id_for_template("quick-test")
        assert result == "prod-abc123"

    @patch("src.lambda.environment_provisioner.get_sc_client")
    def test_returns_none_when_no_match(self, mock_get_sc):
        """Test returning None when no product matches."""
        mock_sc = MagicMock()
        mock_get_sc.return_value = mock_sc
        mock_paginator = MagicMock()
        mock_sc.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "ProductViewDetails": [
                    {
                        "ProductViewSummary": {
                            "ProductId": "prod-abc123",
                            "Name": "Other Product",
                        }
                    }
                ]
            }
        ]

        environment_provisioner.TEMPLATE_PRODUCT_MAP.clear()

        result = get_product_id_for_template("nonexistent-template")
        assert result is None


class TestGetProvisioningArtifactId:
    """Tests for get_provisioning_artifact_id function."""

    @patch("src.lambda.environment_provisioner.get_sc_client")
    def test_returns_default_artifact(self, mock_get_sc):
        """Test returning the DEFAULT guidance artifact."""
        mock_sc = MagicMock()
        mock_get_sc.return_value = mock_sc
        mock_sc.describe_product_as_admin.return_value = {
            "ProvisioningArtifactSummaries": [
                {"Id": "pa-old", "Guidance": "DEPRECATED"},
                {"Id": "pa-new", "Guidance": "DEFAULT"},
            ]
        }

        result = get_provisioning_artifact_id("prod-123")
        assert result == "pa-new"

    @patch("src.lambda.environment_provisioner.get_sc_client")
    def test_returns_first_artifact_when_no_default(self, mock_get_sc):
        """Test returning first artifact when no DEFAULT guidance."""
        mock_sc = MagicMock()
        mock_get_sc.return_value = mock_sc
        mock_sc.describe_product_as_admin.return_value = {
            "ProvisioningArtifactSummaries": [
                {"Id": "pa-first", "Guidance": "DEPRECATED"},
                {"Id": "pa-second", "Guidance": "DEPRECATED"},
            ]
        }

        result = get_provisioning_artifact_id("prod-123")
        assert result == "pa-first"


class TestUpdateEnvironmentState:
    """Tests for update_environment_state function."""

    @patch("src.lambda.environment_provisioner.get_dynamodb")
    def test_updates_basic_state(self, mock_get_dynamodb):
        """Test updating basic environment state."""
        mock_dynamodb = MagicMock()
        mock_get_dynamodb.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        update_environment_state("env-123", "active")

        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        assert call_args[1]["Key"] == {"environment_id": "env-123"}
        assert ":status" in call_args[1]["ExpressionAttributeValues"]
        assert call_args[1]["ExpressionAttributeValues"][":status"] == "active"

    @patch("src.lambda.environment_provisioner.get_dynamodb")
    def test_updates_with_all_fields(self, mock_get_dynamodb):
        """Test updating state with all optional fields."""
        mock_dynamodb = MagicMock()
        mock_get_dynamodb.return_value = mock_dynamodb
        mock_table = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        update_environment_state(
            environment_id="env-123",
            status="failed",
            provisioned_product_id="pp-456",
            stack_id="stack-789",
            resources={"bucket": "my-bucket"},
            error_message="Something went wrong",
        )

        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        expr_values = call_args[1]["ExpressionAttributeValues"]
        assert expr_values[":status"] == "failed"
        assert expr_values[":ppid"] == "pp-456"
        assert expr_values[":sid"] == "stack-789"
        assert expr_values[":err"] == "Something went wrong"


class TestSendNotification:
    """Tests for send_notification function."""

    @patch("src.lambda.environment_provisioner.get_sns_client")
    def test_sends_notification(self, mock_get_sns):
        """Test sending SNS notification."""
        mock_sns = MagicMock()
        mock_get_sns.return_value = mock_sns
        send_notification("Test Subject", "Test message body")

        mock_sns.publish.assert_called_once()
        call_args = mock_sns.publish.call_args
        assert call_args[1]["Subject"] == "Test Subject"
        assert call_args[1]["Message"] == "Test message body"

    @patch("src.lambda.environment_provisioner.get_sns_client")
    def test_truncates_long_subject(self, mock_get_sns):
        """Test that long subjects are truncated."""
        mock_sns = MagicMock()
        mock_get_sns.return_value = mock_sns
        long_subject = "A" * 150
        send_notification(long_subject, "Body")

        call_args = mock_sns.publish.call_args
        assert len(call_args[1]["Subject"]) == 100


class TestProvisionEnvironment:
    """Tests for provision_environment function."""

    @patch("src.lambda.environment_provisioner.send_notification")
    @patch("src.lambda.environment_provisioner.update_environment_state")
    @patch("src.lambda.environment_provisioner.get_provisioning_artifact_id")
    @patch("src.lambda.environment_provisioner.get_product_id_for_template")
    @patch("src.lambda.environment_provisioner.get_sc_client")
    def test_successful_provisioning(
        self, mock_get_sc, mock_get_product, mock_get_artifact, mock_update, mock_notify
    ):
        """Test successful environment provisioning."""
        mock_sc = MagicMock()
        mock_get_sc.return_value = mock_sc
        mock_get_product.return_value = "prod-123"
        mock_get_artifact.return_value = "pa-456"
        mock_sc.provision_product.return_value = {
            "RecordDetail": {
                "ProvisionedProductId": "pp-789",
                "RecordId": "rec-abc",
            }
        }

        result = provision_environment(
            environment_id="env-123",
            template_id="python-fastapi",
            user_id="user-456",
            display_name="My Test Env",
            ttl_hours=24,
        )

        assert result["environment_id"] == "env-123"
        assert result["provisioned_product_id"] == "pp-789"
        assert result["status"] == "provisioning"
        mock_sc.provision_product.assert_called_once()

    @patch("src.lambda.environment_provisioner.send_notification")
    @patch("src.lambda.environment_provisioner.update_environment_state")
    @patch("src.lambda.environment_provisioner.get_product_id_for_template")
    def test_raises_error_when_no_product(
        self, mock_get_product, mock_update, mock_notify
    ):
        """Test that error is raised when product not found."""
        mock_get_product.return_value = None

        with pytest.raises(ProvisioningError, match="No Service Catalog product found"):
            provision_environment(
                environment_id="env-123",
                template_id="unknown-template",
                user_id="user-456",
                display_name="Test",
            )


class TestHandler:
    """Tests for the main Lambda handler."""

    @patch("src.lambda.environment_provisioner.provision_environment")
    def test_successful_handler_invocation(self, mock_provision):
        """Test successful handler invocation."""
        mock_provision.return_value = {
            "environment_id": "env-123",
            "provisioned_product_id": "pp-456",
            "status": "provisioning",
        }

        event = {
            "environment_id": "env-123",
            "template_id": "python-fastapi",
            "user_id": "user-456",
            "display_name": "Test Env",
        }

        result = handler(event, None)

        assert result["statusCode"] == 200
        assert result["body"]["environment_id"] == "env-123"

    def test_handler_requires_template_id(self):
        """Test that handler requires template_id."""
        event = {"user_id": "user-123"}

        result = handler(event, None)

        assert result["statusCode"] == 400
        assert "template_id is required" in result["body"]["error"]

    @patch("src.lambda.environment_provisioner.provision_environment")
    def test_handler_generates_environment_id(self, mock_provision):
        """Test that handler generates environment_id if not provided."""
        mock_provision.return_value = {"status": "provisioning"}

        event = {"template_id": "quick-test"}

        handler(event, None)

        # Check that provision_environment was called with a generated ID
        call_args = mock_provision.call_args
        env_id = call_args[1]["environment_id"]
        assert env_id.startswith("env-")
        assert len(env_id) == 16  # "env-" + 12 hex chars


class TestCheckProvisioningStatus:
    """Tests for check_provisioning_status function."""

    @patch("src.lambda.environment_provisioner.get_sc_client")
    def test_returns_available_status(self, mock_get_sc):
        """Test returning AVAILABLE status."""
        mock_sc = MagicMock()
        mock_get_sc.return_value = mock_sc
        mock_sc.describe_provisioned_product.return_value = {
            "ProvisionedProductDetail": {
                "Status": "AVAILABLE",
                "StatusMessage": "",
                "PhysicalId": "stack-123",
            }
        }

        result = check_provisioning_status("pp-123")

        assert result["status"] == "AVAILABLE"
        assert result["stack_id"] == "stack-123"

    @patch("src.lambda.environment_provisioner.get_sc_client")
    def test_handles_error_status(self, mock_get_sc):
        """Test handling ERROR status."""
        mock_sc = MagicMock()
        mock_get_sc.return_value = mock_sc
        mock_sc.describe_provisioned_product.return_value = {
            "ProvisionedProductDetail": {
                "Status": "ERROR",
                "StatusMessage": "Stack creation failed",
                "PhysicalId": None,
            }
        }

        result = check_provisioning_status("pp-123")

        assert result["status"] == "ERROR"
        assert result["status_message"] == "Stack creation failed"


class TestStatusHandler:
    """Tests for status_handler function."""

    @patch("src.lambda.environment_provisioner.update_environment_state")
    @patch("src.lambda.environment_provisioner.check_provisioning_status")
    def test_updates_state_when_available(self, mock_check, mock_update):
        """Test that state is updated when product is available."""
        mock_check.return_value = {
            "provisioned_product_id": "pp-123",
            "status": "AVAILABLE",
            "stack_id": "stack-456",
        }

        event = {
            "provisioned_product_id": "pp-123",
            "environment_id": "env-789",
        }

        result = status_handler(event, None)

        assert result["statusCode"] == 200
        assert result["body"]["environment_status"] == "active"
        mock_update.assert_called_once()

    @patch("src.lambda.environment_provisioner.update_environment_state")
    @patch("src.lambda.environment_provisioner.check_provisioning_status")
    def test_updates_state_when_failed(self, mock_check, mock_update):
        """Test that state is updated when provisioning failed."""
        mock_check.return_value = {
            "provisioned_product_id": "pp-123",
            "status": "ERROR",
            "status_message": "Failed to create resources",
            "stack_id": None,
        }

        event = {
            "provisioned_product_id": "pp-123",
            "environment_id": "env-789",
        }

        result = status_handler(event, None)

        assert result["statusCode"] == 200
        assert result["body"]["environment_status"] == "failed"
        mock_update.assert_called_once()

    def test_requires_provisioned_product_id(self):
        """Test that provisioned_product_id is required."""
        event = {"environment_id": "env-123"}

        result = status_handler(event, None)

        assert result["statusCode"] == 400
        assert "provisioned_product_id required" in result["body"]["error"]
