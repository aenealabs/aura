"""
Lambda handlers for template marketplace operations.

Supports:
- submit_handler: Validate template, upload to S3 pending/, create DynamoDB record, trigger HITL
- approve_handler: Move to approved/, update DynamoDB status, create Service Catalog product
- reject_handler: Update DynamoDB status, notify submitter

Part of ADR-039 Phase 4: Advanced Features (Layer 7.10)
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import (
        get_cloudwatch_client,
        get_dynamodb_resource,
        get_s3_client,
        get_servicecatalog_client,
        get_sns_client,
        get_stepfunctions_client,
    )
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_cloudwatch_client = _aws_clients.get_cloudwatch_client
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource
    get_s3_client = _aws_clients.get_s3_client
    get_servicecatalog_client = _aws_clients.get_servicecatalog_client
    get_sns_client = _aws_clients.get_sns_client
    get_stepfunctions_client = _aws_clients.get_stepfunctions_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
TEMPLATES_TABLE = os.environ.get("TEMPLATES_TABLE", "")
ARTIFACTS_BUCKET = os.environ.get("ARTIFACTS_BUCKET", "")
PENDING_PREFIX = os.environ.get("PENDING_PREFIX", "marketplace/pending/")
APPROVED_PREFIX = os.environ.get("APPROVED_PREFIX", "marketplace/approved/")
HITL_TOPIC = os.environ.get("HITL_TOPIC", "")
APPROVAL_STATE_MACHINE = os.environ.get("APPROVAL_STATE_MACHINE", "")
PORTFOLIO_ID = os.environ.get("PORTFOLIO_ID", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")
METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "aura/TestEnvironments")

# Valid template categories
VALID_CATEGORIES = [
    "backend",
    "frontend",
    "full-stack",
    "data-pipeline",
    "ml-inference",
    "testing",
    "other",
]


class TemplateValidationError(Exception):
    """Raised when template validation fails."""


def validate_template(template: dict) -> None:
    """
    Validate template submission data.

    Args:
        template: Template data to validate

    Raises:
        TemplateValidationError: If validation fails
    """
    required_fields = ["name", "description", "category", "cloudformation_template"]

    for field in required_fields:
        if field not in template or not template[field]:
            raise TemplateValidationError(f"Missing required field: {field}")

    # Validate category
    if template["category"] not in VALID_CATEGORIES:
        raise TemplateValidationError(
            f"Invalid category: {template['category']}. "
            f"Valid categories: {', '.join(VALID_CATEGORIES)}"
        )

    # Validate CloudFormation template (basic structure)
    cfn = template["cloudformation_template"]
    if isinstance(cfn, str):
        try:
            cfn = json.loads(cfn)
        except json.JSONDecodeError:
            # Might be YAML, that's okay
            pass

    if isinstance(cfn, dict):
        if "AWSTemplateFormatVersion" not in cfn and "Resources" not in cfn:
            raise TemplateValidationError(
                "CloudFormation template must contain AWSTemplateFormatVersion or Resources"
            )

    # Validate name length
    if len(template["name"]) > 100:
        raise TemplateValidationError("Template name must be 100 characters or less")

    # Validate description length
    if len(template["description"]) > 1000:
        raise TemplateValidationError("Description must be 1000 characters or less")


def upload_template_to_s3(
    template_id: str, template_content: str | dict, prefix: str = PENDING_PREFIX
) -> str:
    """
    Upload template to S3.

    Args:
        template_id: Unique template identifier
        template_content: CloudFormation template content
        prefix: S3 prefix (pending/ or approved/)

    Returns:
        S3 key where template was uploaded
    """
    if isinstance(template_content, dict):
        template_content = json.dumps(template_content, indent=2)

    s3_key = f"{prefix}{template_id}/template.yaml"

    get_s3_client().put_object(
        Bucket=ARTIFACTS_BUCKET,
        Key=s3_key,
        Body=template_content,
        ContentType="application/x-yaml",
        ServerSideEncryption="AES256",
    )

    return s3_key


def copy_template_to_approved(template_id: str) -> str:
    """
    Copy template from pending to approved prefix.

    Args:
        template_id: Template identifier

    Returns:
        New S3 key in approved prefix
    """
    source_key = f"{PENDING_PREFIX}{template_id}/template.yaml"
    dest_key = f"{APPROVED_PREFIX}{template_id}/template.yaml"

    get_s3_client().copy_object(
        Bucket=ARTIFACTS_BUCKET,
        Key=dest_key,
        CopySource={"Bucket": ARTIFACTS_BUCKET, "Key": source_key},
        ServerSideEncryption="AES256",
    )

    return dest_key


def create_template_record(
    template_id: str, author_id: str, template_data: dict, s3_key: str
) -> None:
    """
    Create template record in DynamoDB.

    Args:
        template_id: Unique template identifier
        author_id: User ID of submitter
        template_data: Template metadata
        s3_key: S3 key where template is stored
    """
    if not TEMPLATES_TABLE:
        logger.warning("TEMPLATES_TABLE not configured")
        return

    table = get_dynamodb_resource().Table(TEMPLATES_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "template_id": template_id,
        "author_id": author_id,
        "name": template_data["name"],
        "description": template_data["description"],
        "category": template_data["category"],
        "status": "pending_approval",
        "s3_key": s3_key,
        "created_at": now,
        "updated_at": now,
        "version": "1.0.0",
        "downloads": 0,
        "rating": 0,
        "metadata": {
            "tags": template_data.get("tags", []),
            "estimated_cost": template_data.get("estimated_cost", "unknown"),
            "provisioning_time": template_data.get("provisioning_time", "unknown"),
        },
    }

    table.put_item(Item=item)


def update_template_status(
    template_id: str,
    status: str,
    reviewer_id: str | None = None,
    rejection_reason: str | None = None,
    service_catalog_product_id: str | None = None,
) -> None:
    """
    Update template status in DynamoDB.

    Args:
        template_id: Template identifier
        status: New status
        reviewer_id: ID of approving/rejecting reviewer
        rejection_reason: Reason for rejection (if rejected)
        service_catalog_product_id: Service Catalog product ID (if approved)
    """
    if not TEMPLATES_TABLE:
        return

    table = get_dynamodb_resource().Table(TEMPLATES_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    update_expr = "SET #status = :status, updated_at = :now"
    expr_values: dict[str, Any] = {":status": status, ":now": now}

    if reviewer_id:
        update_expr += ", reviewer_id = :reviewer"
        expr_values[":reviewer"] = reviewer_id

    if rejection_reason:
        update_expr += ", rejection_reason = :reason"
        expr_values[":reason"] = rejection_reason

    if service_catalog_product_id:
        update_expr += ", service_catalog_product_id = :sc_id"
        expr_values[":sc_id"] = service_catalog_product_id

    table.update_item(
        Key={"template_id": template_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues=expr_values,
    )


def start_hitl_approval(
    template_id: str, template_data: dict, author_id: str
) -> str | None:
    """
    Start HITL approval workflow for template.

    Args:
        template_id: Template identifier
        template_data: Template metadata
        author_id: Submitter user ID

    Returns:
        Execution ARN if started, None otherwise
    """
    if not APPROVAL_STATE_MACHINE:
        logger.warning("Step Functions not configured for HITL approval")
        return None

    try:
        response = get_stepfunctions_client().start_execution(
            stateMachineArn=APPROVAL_STATE_MACHINE,
            name=f"template-approval-{template_id[:32]}",
            input=json.dumps(
                {
                    "approval_type": "template_marketplace",
                    "template_id": template_id,
                    "template_name": template_data["name"],
                    "template_description": template_data["description"],
                    "category": template_data["category"],
                    "author_id": author_id,
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
        execution_arn: str | None = response["executionArn"]
        return execution_arn
    except ClientError as e:
        logger.error(f"Failed to start HITL approval: {e}")
        return None


def create_service_catalog_product(
    template_id: str, template_data: dict, s3_key: str
) -> str | None:
    """
    Create Service Catalog product from approved template.

    Args:
        template_id: Template identifier
        template_data: Template metadata
        s3_key: S3 key of approved template

    Returns:
        Product ID if created, None otherwise
    """
    if not PORTFOLIO_ID:
        logger.warning("Service Catalog not configured")
        return None

    try:
        # Create product
        product_response = get_servicecatalog_client().create_product(
            Name=f"User: {template_data['name']}",
            Owner=template_data.get("author_id", "Community"),
            Description=template_data["description"],
            ProductType="CLOUD_FORMATION_TEMPLATE",
            ProvisioningArtifactParameters={
                "Name": "v1.0.0",
                "Description": "Initial version",
                "Info": {
                    "LoadTemplateFromURL": f"https://{ARTIFACTS_BUCKET}.s3.amazonaws.com/{s3_key}"
                },
                "Type": "CLOUD_FORMATION_TEMPLATE",
            },
            Tags=[
                {"Key": "MarketplaceTemplate", "Value": "true"},
                {"Key": "TemplateId", "Value": template_id},
                {"Key": "Category", "Value": template_data["category"]},
            ],
        )

        product_id: str | None = product_response["ProductViewDetail"][
            "ProductViewSummary"
        ]["ProductId"]

        # Associate with portfolio
        get_servicecatalog_client().associate_product_with_portfolio(
            ProductId=product_id, PortfolioId=PORTFOLIO_ID
        )

        logger.info(f"Created Service Catalog product: {product_id}")
        return product_id

    except ClientError as e:
        logger.error(f"Failed to create Service Catalog product: {e}")
        return None


def publish_metric(metric_name: str, value: float = 1.0, unit: str = "Count") -> None:
    """Publish a CloudWatch metric."""
    try:
        get_cloudwatch_client().put_metric_data(
            Namespace=METRICS_NAMESPACE,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": [{"Name": "Environment", "Value": ENVIRONMENT}],
                }
            ],
        )
    except ClientError as e:
        logger.warning(f"Failed to publish metric {metric_name}: {e}")


def send_notification(topic_arn: str, subject: str, message: str) -> None:
    """Send SNS notification."""
    if not topic_arn:
        return

    try:
        get_sns_client().publish(TopicArn=topic_arn, Subject=subject, Message=message)
    except ClientError as e:
        logger.warning(f"Failed to send notification: {e}")


def submit_handler(event: dict, context: Any) -> dict:
    """
    Handle template submission to marketplace.

    Args:
        event: Request with template data
        context: Lambda context

    Returns:
        Response with submission result
    """
    logger.info(f"Template submission request: {json.dumps(event)}")

    # Extract request data
    body = event.get("body", event)
    if isinstance(body, str):
        body = json.loads(body)

    author_id = body.get(
        "author_id",
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
        .get("sub", "unknown"),
    )

    # Validate template
    try:
        validate_template(body)
    except TemplateValidationError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

    # Generate template ID
    template_id = str(uuid.uuid4())

    try:
        # Upload template to S3
        s3_key = upload_template_to_s3(
            template_id, body["cloudformation_template"], PENDING_PREFIX
        )

        # Create DynamoDB record
        create_template_record(template_id, author_id, body, s3_key)

        # Start HITL approval
        execution_arn = start_hitl_approval(template_id, body, author_id)

        publish_metric("TemplateSubmissions")

        return {
            "statusCode": 201,
            "body": json.dumps(
                {
                    "message": "Template submitted for approval",
                    "template_id": template_id,
                    "status": "pending_approval",
                    "approval_execution": execution_arn,
                }
            ),
        }

    except ClientError as e:
        logger.error(f"Template submission failed: {e}")
        publish_metric("TemplateSubmissionFailed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Submission failed: {str(e)}"}),
        }


def approve_handler(event: dict, context: Any) -> dict:
    """
    Handle template approval (HITL callback).

    Args:
        event: Request with approval decision
        context: Lambda context

    Returns:
        Response with approval result
    """
    logger.info(f"Template approval request: {json.dumps(event)}")

    # Extract from SNS message or direct invocation
    if "Records" in event:
        # SNS trigger
        message = json.loads(event["Records"][0]["Sns"]["Message"])
    else:
        message = event.get("body", event)
        if isinstance(message, str):
            message = json.loads(message)

    template_id = message.get("template_id", "")
    decision = message.get("decision", "")  # 'approve' or 'reject'
    reviewer_id = message.get("reviewer_id", "system")
    rejection_reason = message.get("rejection_reason", "")

    if not template_id or decision not in ["approve", "reject"]:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "template_id and valid decision required"}),
        }

    try:
        if decision == "approve":
            # Copy template to approved prefix
            approved_key = copy_template_to_approved(template_id)

            # Get template data from DynamoDB
            if TEMPLATES_TABLE:
                table = get_dynamodb_resource().Table(TEMPLATES_TABLE)
                response = table.get_item(Key={"template_id": template_id})
                template_data = response.get("Item", {})
            else:
                template_data = {}

            # Create Service Catalog product
            product_id = create_service_catalog_product(
                template_id, template_data, approved_key
            )

            # Update status
            update_template_status(
                template_id,
                "approved",
                reviewer_id=reviewer_id,
                service_catalog_product_id=product_id,
            )

            publish_metric("TemplatesApproved")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Template approved",
                        "template_id": template_id,
                        "service_catalog_product_id": product_id,
                    }
                ),
            }
        else:
            # Reject
            update_template_status(
                template_id,
                "rejected",
                reviewer_id=reviewer_id,
                rejection_reason=rejection_reason,
            )

            publish_metric("TemplatesRejected")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Template rejected",
                        "template_id": template_id,
                        "reason": rejection_reason,
                    }
                ),
            }

    except ClientError as e:
        logger.error(f"Template approval processing failed: {e}")
        publish_metric("TemplateApprovalFailed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Approval processing failed: {str(e)}"}),
        }
