"""
Environment Provisioner Lambda Handler.

Provisions test environments via AWS Service Catalog. Supports both:
1. Direct provisioning for quick/standard templates (no HITL required)
2. Post-approval provisioning called by Step Functions state machine

Environment Variables:
    STATE_TABLE: DynamoDB table name for environment state
    PROJECT_NAME: Project name for resource naming
    ENVIRONMENT: Deployment environment (dev, qa, prod)
    SERVICE_CATALOG_PORTFOLIO_ID: Service Catalog portfolio ID
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Lazy-initialized AWS Clients (created on first use for Lambda cold start optimization)
_sc_client = None
_dynamodb = None
_sns_client = None


def get_sc_client():
    """Get or create Service Catalog client."""
    global _sc_client
    if _sc_client is None:
        _sc_client = boto3.client("servicecatalog")
    return _sc_client


def get_dynamodb():
    """Get or create DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def get_sns_client():
    """Get or create SNS client."""
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client("sns")
    return _sns_client


# Environment variables
STATE_TABLE = os.environ.get("STATE_TABLE", "")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
NOTIFICATIONS_TOPIC_ARN = os.environ.get("NOTIFICATIONS_TOPIC_ARN", "")

# Template ID to Service Catalog Product ID mapping
# This is populated dynamically from the Service Catalog Portfolio
TEMPLATE_PRODUCT_MAP: dict[str, str] = {}


class ProvisioningError(Exception):
    """Exception raised when environment provisioning fails."""


def get_product_id_for_template(template_id: str) -> str | None:
    """
    Look up the Service Catalog Product ID for a given template ID.

    Args:
        template_id: The template identifier (e.g., 'quick-test', 'python-fastapi')

    Returns:
        The Service Catalog Product ID if found, None otherwise
    """
    # Return cached value if available
    if template_id in TEMPLATE_PRODUCT_MAP:
        return TEMPLATE_PRODUCT_MAP[template_id]

    try:
        # Search for products in the portfolio
        portfolio_id = os.environ.get("SERVICE_CATALOG_PORTFOLIO_ID", "")
        if not portfolio_id:
            logger.warning(
                "SERVICE_CATALOG_PORTFOLIO_ID not set, cannot look up products"
            )
            return None

        paginator = get_sc_client().get_paginator("search_products_as_admin")
        for page in paginator.paginate(PortfolioId=portfolio_id):
            for product in page.get("ProductViewDetails", []):
                product_view = product.get("ProductViewSummary", {})
                product_name = product_view.get("Name", "")

                # Match template_id to product name (e.g., 'quick-test' matches 'Quick Test')
                normalized_name = product_name.lower().replace(" ", "-")
                if template_id in normalized_name or normalized_name in template_id:
                    product_id: str | None = product_view.get("ProductId")
                    if product_id is not None:
                        TEMPLATE_PRODUCT_MAP[template_id] = product_id
                        logger.info(
                            f"Found product {product_id} for template {template_id}"
                        )
                        return product_id

        logger.warning(f"No Service Catalog product found for template: {template_id}")
        return None

    except ClientError as e:
        logger.error(f"Error looking up product for template {template_id}: {e}")
        return None


def get_provisioning_artifact_id(product_id: str) -> str | None:
    """
    Get the latest provisioning artifact (version) for a product.

    Args:
        product_id: The Service Catalog Product ID

    Returns:
        The Provisioning Artifact ID for the latest version
    """
    try:
        response = get_sc_client().describe_product_as_admin(Id=product_id)
        artifacts = response.get("ProvisioningArtifactSummaries", [])

        # Find the active/latest artifact
        for artifact in artifacts:
            if artifact.get("Guidance") == "DEFAULT":
                artifact_id: str | None = artifact.get("Id")
                return artifact_id

        # Fall back to first artifact if no DEFAULT
        if artifacts:
            artifact_id = artifacts[0].get("Id")
            return artifact_id

        return None

    except ClientError as e:
        logger.error(
            f"Error getting provisioning artifact for product {product_id}: {e}"
        )
        return None


def build_provisioning_parameters(
    environment_id: str,
    user_id: str,
    display_name: str,
    ttl_hours: int,
    custom_params: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """
    Build the provisioning parameters for Service Catalog.

    Args:
        environment_id: Unique environment identifier
        user_id: User who owns the environment
        display_name: Human-readable name
        ttl_hours: Time-to-live in hours
        custom_params: Additional custom parameters

    Returns:
        List of parameter dictionaries for Service Catalog
    """
    params = [
        {"Key": "EnvironmentId", "Value": environment_id},
        {"Key": "UserId", "Value": user_id},
        {"Key": "DisplayName", "Value": display_name},
        {"Key": "TTLHours", "Value": str(ttl_hours)},
    ]

    if custom_params:
        for key, value in custom_params.items():
            params.append({"Key": key, "Value": str(value)})

    return params


def update_environment_state(
    environment_id: str,
    status: str,
    provisioned_product_id: str | None = None,
    stack_id: str | None = None,
    resources: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """
    Update the environment state in DynamoDB.

    Args:
        environment_id: The environment identifier
        status: New status (provisioning, active, failed, etc.)
        provisioned_product_id: Service Catalog provisioned product ID
        stack_id: CloudFormation stack ID
        resources: Dictionary of provisioned resources
        error_message: Error message if provisioning failed
    """
    if not STATE_TABLE:
        logger.warning("STATE_TABLE not set, skipping state update")
        return

    table = get_dynamodb().Table(STATE_TABLE)

    update_expression_parts = ["#status = :status", "last_updated_at = :ts"]
    expression_names = {"#status": "status"}
    expression_values = {
        ":status": status,
        ":ts": datetime.now(timezone.utc).isoformat(),
    }

    if provisioned_product_id:
        update_expression_parts.append("provisioned_product_id = :ppid")
        expression_values[":ppid"] = provisioned_product_id

    if stack_id:
        update_expression_parts.append("stack_id = :sid")
        expression_values[":sid"] = stack_id

    if resources:
        update_expression_parts.append("resources = :res")
        expression_values[":res"] = json.dumps(resources)

    if error_message:
        update_expression_parts.append("error_message = :err")
        expression_values[":err"] = error_message

    if status == "active":
        update_expression_parts.append("provisioning_completed_at = :pca")
        expression_values[":pca"] = datetime.now(timezone.utc).isoformat()

    try:
        table.update_item(
            Key={"environment_id": environment_id},
            UpdateExpression="SET " + ", ".join(update_expression_parts),
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
        )
        logger.info(f"Updated environment {environment_id} state to {status}")
    except ClientError as e:
        logger.error(f"Failed to update environment state: {e}")
        raise


def send_notification(subject: str, message: str) -> None:
    """Send notification via SNS if topic is configured."""
    if not NOTIFICATIONS_TOPIC_ARN:
        logger.debug("NOTIFICATIONS_TOPIC_ARN not set, skipping notification")
        return

    try:
        get_sns_client().publish(
            TopicArn=NOTIFICATIONS_TOPIC_ARN,
            Subject=subject[:100],  # SNS subject limit
            Message=message,
        )
    except ClientError as e:
        logger.warning(f"Failed to send notification: {e}")


def provision_environment(
    environment_id: str,
    template_id: str,
    user_id: str,
    display_name: str,
    ttl_hours: int = 24,
    provisioning_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Provision an environment via Service Catalog.

    Args:
        environment_id: Unique identifier for the environment
        template_id: Template/product identifier
        user_id: User requesting the environment
        display_name: Human-readable name
        ttl_hours: Time-to-live in hours
        provisioning_params: Additional parameters for the template

    Returns:
        Dictionary with provisioning details

    Raises:
        ProvisioningError: If provisioning fails
    """
    logger.info(
        f"Provisioning environment {environment_id} using template {template_id}"
    )

    # Update state to provisioning
    update_environment_state(environment_id, "provisioning")

    try:
        # Look up the Service Catalog product
        product_id = get_product_id_for_template(template_id)
        if not product_id:
            raise ProvisioningError(
                f"No Service Catalog product found for template: {template_id}"
            )

        # Get the provisioning artifact (version)
        artifact_id = get_provisioning_artifact_id(product_id)
        if not artifact_id:
            raise ProvisioningError(
                f"No provisioning artifact found for product: {product_id}"
            )

        # Build parameters
        params = build_provisioning_parameters(
            environment_id=environment_id,
            user_id=user_id,
            display_name=display_name,
            ttl_hours=ttl_hours,
            custom_params=provisioning_params,
        )

        # Generate unique provisioned product name
        provisioned_name = f"{PROJECT_NAME}-testenv-{environment_id}"

        # Provision the product
        response = get_sc_client().provision_product(
            ProductId=product_id,
            ProvisioningArtifactId=artifact_id,
            ProvisionedProductName=provisioned_name,
            ProvisioningParameters=params,
            Tags=[
                {"Key": "Project", "Value": PROJECT_NAME},
                {"Key": "Environment", "Value": ENVIRONMENT},
                {"Key": "TestEnvId", "Value": environment_id},
                {"Key": "UserId", "Value": user_id},
                {"Key": "CreatedAt", "Value": datetime.now(timezone.utc).isoformat()},
            ],
        )

        record_detail = response.get("RecordDetail", {})
        provisioned_product_id = record_detail.get("ProvisionedProductId")
        record_id = record_detail.get("RecordId")

        logger.info(
            f"Provisioning initiated for {environment_id}: "
            f"product={provisioned_product_id}, record={record_id}"
        )

        # Update state with provisioned product info
        update_environment_state(
            environment_id=environment_id,
            status="provisioning",
            provisioned_product_id=provisioned_product_id,
        )

        # Send notification
        send_notification(
            subject=f"[Aura] Environment Provisioning Started: {display_name}",
            message=(
                f"Test environment '{display_name}' (ID: {environment_id}) "
                f"is now being provisioned.\n\n"
                f"Template: {template_id}\n"
                f"TTL: {ttl_hours} hours\n"
                f"User: {user_id}\n\n"
                f"You will be notified when the environment is ready."
            ),
        )

        return {
            "environment_id": environment_id,
            "provisioned_product_id": provisioned_product_id,
            "record_id": record_id,
            "status": "provisioning",
            "template_id": template_id,
            "display_name": display_name,
        }

    except ClientError as e:
        error_msg = str(e)
        logger.error(f"Provisioning failed for {environment_id}: {error_msg}")

        update_environment_state(
            environment_id=environment_id,
            status="failed",
            error_message=error_msg,
        )

        send_notification(
            subject=f"[Aura] Environment Provisioning Failed: {display_name}",
            message=(
                f"Test environment '{display_name}' (ID: {environment_id}) "
                f"failed to provision.\n\n"
                f"Error: {error_msg}"
            ),
        )

        raise ProvisioningError(f"Service Catalog provisioning failed: {error_msg}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for environment provisioning.

    Event structure:
    {
        "environment_id": "env-abc123",
        "template_id": "python-fastapi",
        "user_id": "user-123",
        "display_name": "My Test Environment",
        "ttl_hours": 24,
        "provisioning_params": {"key": "value"}  # Optional
    }

    Returns:
    {
        "statusCode": 200,
        "body": {
            "environment_id": "env-abc123",
            "provisioned_product_id": "pp-xxx",
            "status": "provisioning"
        }
    }
    """
    logger.info(f"Environment provisioner invoked with event: {json.dumps(event)}")

    try:
        # Extract parameters from event
        environment_id = event.get("environment_id")
        if not environment_id:
            environment_id = f"env-{uuid.uuid4().hex[:12]}"

        template_id = event.get("template_id")
        if not template_id:
            raise ValueError("template_id is required")

        user_id = event.get("user_id", "unknown")
        display_name = event.get("display_name", f"Environment {environment_id}")
        ttl_hours = int(event.get("ttl_hours", 24))
        provisioning_params = event.get("provisioning_params", {})

        # Provision the environment
        result = provision_environment(
            environment_id=environment_id,
            template_id=template_id,
            user_id=user_id,
            display_name=display_name,
            ttl_hours=ttl_hours,
            provisioning_params=provisioning_params,
        )

        return {
            "statusCode": 200,
            "body": result,
        }

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return {
            "statusCode": 400,
            "body": {"error": str(e)},
        }

    except ProvisioningError as e:
        logger.error(f"Provisioning error: {e}")
        return {
            "statusCode": 500,
            "body": {"error": str(e)},
        }

    except Exception as e:
        logger.exception(f"Unexpected error during provisioning: {e}")
        return {
            "statusCode": 500,
            "body": {"error": f"Internal error: {str(e)}"},
        }


def check_provisioning_status(provisioned_product_id: str) -> dict[str, Any]:
    """
    Check the status of a provisioned product.

    Args:
        provisioned_product_id: The Service Catalog provisioned product ID

    Returns:
        Dictionary with status and details
    """
    try:
        response = get_sc_client().describe_provisioned_product(
            Id=provisioned_product_id
        )
        detail = response.get("ProvisionedProductDetail", {})

        status = detail.get("Status")
        status_message = detail.get("StatusMessage", "")
        stack_id = detail.get("PhysicalId")

        return {
            "provisioned_product_id": provisioned_product_id,
            "status": status,
            "status_message": status_message,
            "stack_id": stack_id,
        }

    except ClientError as e:
        logger.error(f"Error checking provisioned product status: {e}")
        return {
            "provisioned_product_id": provisioned_product_id,
            "status": "UNKNOWN",
            "error": str(e),
        }


def status_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for checking provisioning status.

    Can be invoked periodically to update environment state based on
    Service Catalog provisioning progress.

    Event structure:
    {
        "provisioned_product_id": "pp-xxx",
        "environment_id": "env-abc123"
    }
    """
    logger.info(f"Status check invoked with event: {json.dumps(event)}")

    provisioned_product_id = event.get("provisioned_product_id")
    environment_id = event.get("environment_id")

    if not provisioned_product_id:
        return {"statusCode": 400, "body": {"error": "provisioned_product_id required"}}

    status_result = check_provisioning_status(provisioned_product_id)

    # Map Service Catalog status to environment status
    sc_status = status_result.get("status")
    if sc_status == "AVAILABLE":
        env_status = "active"
    elif sc_status in ["UNDER_CHANGE", "PLAN_IN_PROGRESS"]:
        env_status = "provisioning"
    elif sc_status in ["ERROR", "TAINTED"]:
        env_status = "failed"
    else:
        env_status = "unknown"

    # Update environment state if environment_id provided
    if environment_id and env_status in ["active", "failed"]:
        update_environment_state(
            environment_id=environment_id,
            status=env_status,
            provisioned_product_id=provisioned_product_id,
            stack_id=status_result.get("stack_id"),
            error_message=(
                status_result.get("status_message") if env_status == "failed" else None
            ),
        )

    return {
        "statusCode": 200,
        "body": {
            "environment_id": environment_id,
            "provisioned_product_id": provisioned_product_id,
            "sc_status": sc_status,
            "environment_status": env_status,
            "stack_id": status_result.get("stack_id"),
        },
    }
