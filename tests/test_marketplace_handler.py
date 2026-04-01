"""
Unit tests for marketplace_handler.py Lambda handler.

Tests cover:
- Template validation
- S3 upload flow
- DynamoDB record creation
- HITL approval integration
- Service Catalog product creation
- Error handling

Part of ADR-039 Phase 4: Advanced Features
"""

import importlib
import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Set environment variables before importing Lambda
os.environ.setdefault("TEMPLATES_TABLE", "test-templates-table")
os.environ.setdefault("ARTIFACTS_BUCKET", "test-artifacts-bucket")
os.environ.setdefault("PENDING_PREFIX", "marketplace/pending/")
os.environ.setdefault("APPROVED_PREFIX", "marketplace/approved/")
os.environ.setdefault(
    "HITL_TOPIC", "arn:aws:sns:us-east-1:123456789012:test-hitl-topic"
)
os.environ.setdefault(
    "APPROVAL_STATE_MACHINE", "arn:aws:states:us-east-1:123456789012:stateMachine:test"
)
os.environ.setdefault("PORTFOLIO_ID", "port-test123")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PROJECT_NAME", "aura")
os.environ.setdefault("METRICS_NAMESPACE", "aura/TestEnvironments")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

# Import using importlib (lambda is a reserved keyword)
marketplace_handler = importlib.import_module("src.lambda.marketplace_handler")


class TestValidateTemplate:
    """Tests for validate_template function."""

    def test_validates_complete_template(self):
        """Test validation passes for complete template."""
        template = {
            "name": "Test Template",
            "description": "A test template for testing",
            "category": "backend",
            "cloudformation_template": {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Resources": {},
            },
        }

        # Should not raise
        marketplace_handler.validate_template(template)

    def test_rejects_missing_name(self):
        """Test validation rejects missing name."""
        template = {
            "description": "A test template",
            "category": "backend",
            "cloudformation_template": {"Resources": {}},
        }

        with pytest.raises(marketplace_handler.TemplateValidationError) as exc_info:
            marketplace_handler.validate_template(template)

        assert "name" in str(exc_info.value).lower()

    def test_rejects_missing_category(self):
        """Test validation rejects missing category."""
        template = {
            "name": "Test",
            "description": "A test",
            "cloudformation_template": {"Resources": {}},
        }

        with pytest.raises(marketplace_handler.TemplateValidationError) as exc_info:
            marketplace_handler.validate_template(template)

        assert "category" in str(exc_info.value).lower()

    def test_rejects_invalid_category(self):
        """Test validation rejects invalid category."""
        template = {
            "name": "Test",
            "description": "A test",
            "category": "invalid-category",
            "cloudformation_template": {"Resources": {}},
        }

        with pytest.raises(marketplace_handler.TemplateValidationError) as exc_info:
            marketplace_handler.validate_template(template)

        assert "Invalid category" in str(exc_info.value)

    def test_rejects_long_name(self):
        """Test validation rejects names over 100 characters."""
        template = {
            "name": "A" * 101,
            "description": "A test",
            "category": "backend",
            "cloudformation_template": {"Resources": {}},
        }

        with pytest.raises(marketplace_handler.TemplateValidationError) as exc_info:
            marketplace_handler.validate_template(template)

        assert "100 characters" in str(exc_info.value)

    def test_accepts_all_valid_categories(self):
        """Test validation accepts all valid categories."""
        for category in marketplace_handler.VALID_CATEGORIES:
            template = {
                "name": "Test",
                "description": "A test",
                "category": category,
                "cloudformation_template": {"Resources": {}},
            }
            # Should not raise
            marketplace_handler.validate_template(template)


class TestUploadTemplateToS3:
    """Tests for upload_template_to_s3 function."""

    def test_uploads_template_successfully(self):
        """Test successful template upload."""
        mock_s3 = MagicMock()

        with patch.object(marketplace_handler, "get_s3_client", return_value=mock_s3):
            template_content = {"Resources": {}}
            s3_key = marketplace_handler.upload_template_to_s3(
                "template-123", template_content
            )

            assert "marketplace/pending/template-123" in s3_key
            mock_s3.put_object.assert_called_once()

    def test_uploads_string_content(self):
        """Test upload with string content."""
        mock_s3 = MagicMock()

        with patch.object(marketplace_handler, "get_s3_client", return_value=mock_s3):
            template_content = "AWSTemplateFormatVersion: 2010-09-09"
            s3_key = marketplace_handler.upload_template_to_s3(
                "template-123", template_content
            )

            assert s3_key is not None
            mock_s3.put_object.assert_called_once()


class TestCreateTemplateRecord:
    """Tests for create_template_record function."""

    def test_creates_record_successfully(self):
        """Test successful DynamoDB record creation."""
        mock_table = MagicMock()

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        template_data = {
            "name": "Test Template",
            "description": "A test",
            "category": "backend",
        }

        with patch.object(
            marketplace_handler, "get_dynamodb_resource", return_value=mock_dynamodb
        ):
            marketplace_handler.create_template_record(
                "template-123",
                "user-456",
                template_data,
                "marketplace/pending/template-123/template.yaml",
            )

            mock_table.put_item.assert_called_once()
            call_args = mock_table.put_item.call_args
            item = call_args.kwargs["Item"]

            assert item["template_id"] == "template-123"
            assert item["author_id"] == "user-456"
            assert item["status"] == "pending_approval"


class TestSubmitHandler:
    """Tests for submit_handler Lambda function."""

    @patch.object(marketplace_handler, "upload_template_to_s3")
    @patch.object(marketplace_handler, "create_template_record")
    @patch.object(marketplace_handler, "start_hitl_approval")
    @patch.object(marketplace_handler, "publish_metric")
    def test_submit_handler_success(
        self, mock_metric, mock_hitl, mock_record, mock_upload
    ):
        """Test successful template submission."""
        mock_upload.return_value = "marketplace/pending/123/template.yaml"
        mock_hitl.return_value = "arn:aws:states:execution:123"

        event = {
            "body": json.dumps(
                {
                    "name": "Test Template",
                    "description": "A test template",
                    "category": "backend",
                    "cloudformation_template": {"Resources": {}},
                    "author_id": "user-456",
                }
            )
        }
        context = MagicMock()

        response = marketplace_handler.submit_handler(event, context)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert "template_id" in body
        assert body["status"] == "pending_approval"

    @patch.object(marketplace_handler, "publish_metric")
    def test_submit_handler_validation_error(self, mock_metric):
        """Test submission with validation error."""
        event = {
            "body": json.dumps(
                {"name": "Test", "category": "invalid", "cloudformation_template": {}}
            )
        }
        context = MagicMock()

        response = marketplace_handler.submit_handler(event, context)

        assert response["statusCode"] == 400


class TestApproveHandler:
    """Tests for approve_handler Lambda function."""

    @patch.object(marketplace_handler, "copy_template_to_approved")
    @patch.object(marketplace_handler, "update_template_status")
    @patch.object(marketplace_handler, "create_service_catalog_product")
    @patch.object(marketplace_handler, "publish_metric")
    def test_approve_handler_approves(
        self, mock_metric, mock_catalog, mock_status, mock_copy
    ):
        """Test approval flow."""
        mock_copy.return_value = "marketplace/approved/123/template.yaml"
        mock_catalog.return_value = "prod-123"

        # Mock DynamoDB table for get_item
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "template_id": "template-123",
                "name": "Test",
                "description": "Test",
                "category": "backend",
                "s3_key": "marketplace/pending/template-123/template.yaml",
            }
        }

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        event = {
            "body": json.dumps(
                {
                    "template_id": "template-123",
                    "decision": "approve",
                    "reviewer_id": "admin-789",
                }
            )
        }
        context = MagicMock()

        with patch.object(
            marketplace_handler, "get_dynamodb_resource", return_value=mock_dynamodb
        ):
            response = marketplace_handler.approve_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Template approved"
        mock_status.assert_called_once()

    @patch.object(marketplace_handler, "update_template_status")
    @patch.object(marketplace_handler, "publish_metric")
    def test_approve_handler_rejects(self, mock_metric, mock_status):
        """Test rejection flow."""
        event = {
            "body": json.dumps(
                {
                    "template_id": "template-123",
                    "decision": "reject",
                    "reviewer_id": "admin-789",
                    "rejection_reason": "Does not meet standards",
                }
            )
        }
        context = MagicMock()

        response = marketplace_handler.approve_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Template rejected"
        mock_status.assert_called_with(
            "template-123",
            "rejected",
            reviewer_id="admin-789",
            rejection_reason="Does not meet standards",
        )

    def test_approve_handler_invalid_decision(self):
        """Test handler rejects invalid decision."""
        event = {
            "body": json.dumps({"template_id": "template-123", "decision": "invalid"})
        }
        context = MagicMock()

        response = marketplace_handler.approve_handler(event, context)

        assert response["statusCode"] == 400

    def test_approve_handler_sns_trigger(self):
        """Test handler handles SNS trigger format."""
        with (
            patch.object(marketplace_handler, "update_template_status"),
            patch.object(marketplace_handler, "publish_metric"),
        ):

            event = {
                "Records": [
                    {
                        "Sns": {
                            "Message": json.dumps(
                                {
                                    "template_id": "template-123",
                                    "decision": "reject",
                                    "reviewer_id": "admin",
                                }
                            )
                        }
                    }
                ]
            }
            context = MagicMock()

            response = marketplace_handler.approve_handler(event, context)

            assert response["statusCode"] == 200
