"""
Lambda handler for one-time scheduled environment provisioning.

Triggered by EventBridge every 5 minutes, this handler:
1. Queries DynamoDB for scheduled jobs where scheduled_at <= now AND status = 'pending'
2. For each job: invokes the provisioner Lambda and updates status to 'triggered'
3. Handles errors gracefully, updating status to 'failed' with error message

Part of ADR-039 Phase 4: Advanced Features (Layer 7.8)
"""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import (
        get_cloudwatch_client,
        get_dynamodb_resource,
        get_lambda_client,
        get_sns_client,
    )
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_cloudwatch_client = _aws_clients.get_cloudwatch_client
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource
    get_lambda_client = _aws_clients.get_lambda_client
    get_sns_client = _aws_clients.get_sns_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SCHEDULE_TABLE = os.environ.get("SCHEDULE_TABLE", "")
PROVISIONER_FUNCTION = os.environ.get("PROVISIONER_FUNCTION", "")
SNS_TOPIC = os.environ.get("SNS_TOPIC", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")
METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "aura/TestEnvironments")


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def get_pending_jobs() -> list[dict]:
    """
    Query DynamoDB for pending scheduled jobs that are due.

    Returns:
        List of scheduled job items ready for provisioning
    """
    if not SCHEDULE_TABLE:
        logger.warning("SCHEDULE_TABLE not configured")
        return []

    table = get_dynamodb_resource().Table(SCHEDULE_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    try:
        response = table.query(
            IndexName="status-scheduled_at-index",
            KeyConditionExpression="#status = :pending AND scheduled_at <= :now",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":pending": "pending", ":now": now},
            Limit=10,  # Process up to 10 jobs per invocation
        )
        return response.get("Items", [])
    except ClientError as e:
        logger.error(f"Failed to query pending jobs: {e}")
        return []


def update_job_status(
    schedule_id: str,
    status: str,
    error_message: str | None = None,
    execution_id: str | None = None,
) -> bool:
    """
    Update the status of a scheduled job.

    Args:
        schedule_id: The schedule job ID
        status: New status (triggered, failed, completed)
        error_message: Optional error message for failed status
        execution_id: Optional execution ID from provisioner

    Returns:
        True if update successful, False otherwise
    """
    if not SCHEDULE_TABLE:
        return False

    table = get_dynamodb_resource().Table(SCHEDULE_TABLE)
    now = datetime.now(timezone.utc).isoformat()

    update_expr = "SET #status = :status, updated_at = :updated_at"
    expr_values: dict[str, Any] = {":status": status, ":updated_at": now}

    if error_message:
        update_expr += ", error_message = :error"
        expr_values[":error"] = error_message

    if execution_id:
        update_expr += ", execution_id = :exec_id"
        expr_values[":exec_id"] = execution_id

    try:
        table.update_item(
            Key={"schedule_id": schedule_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=expr_values,
        )
        return True
    except ClientError as e:
        logger.error(f"Failed to update job status: {e}")
        return False


def invoke_provisioner(job: dict) -> tuple[bool, str | None, str | None]:
    """
    Invoke the provisioner Lambda to create the environment.

    Args:
        job: The scheduled job item with provisioning parameters

    Returns:
        Tuple of (success, execution_id, error_message)
    """
    if not PROVISIONER_FUNCTION:
        return False, None, "PROVISIONER_FUNCTION not configured"

    # Build provisioning request from scheduled job
    provision_request = {
        "source": "scheduled_provisioner",
        "schedule_id": job["schedule_id"],
        "user_id": job["user_id"],
        "environment_type": job.get("environment_type", "standard"),
        "template_id": job.get("template_id"),
        "display_name": job.get("display_name", f"Scheduled-{job['schedule_id'][:8]}"),
        "parameters": job.get("parameters", {}),
        "ttl_hours": job.get("ttl_hours", 24),
        "metadata": {
            "scheduled_at": job.get("scheduled_at"),
            "scheduled_by": job.get("user_id"),
        },
    }

    try:
        response = get_lambda_client().invoke(
            FunctionName=PROVISIONER_FUNCTION,
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(provision_request, cls=DecimalEncoder),
        )

        status_code = response.get("StatusCode", 0)
        if status_code in [200, 202]:
            # Extract request ID as execution reference
            request_id = response.get("ResponseMetadata", {}).get("RequestId", "")
            logger.info(
                f"Provisioner invoked successfully for job {job['schedule_id']}"
            )
            return True, request_id, None
        else:
            return False, None, f"Provisioner returned status {status_code}"

    except ClientError as e:
        error_msg = str(e)
        logger.error(f"Failed to invoke provisioner: {error_msg}")
        return False, None, error_msg


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


def send_notification(subject: str, message: str) -> None:
    """Send SNS notification if topic configured."""
    if not SNS_TOPIC:
        return

    try:
        get_sns_client().publish(TopicArn=SNS_TOPIC, Subject=subject, Message=message)
    except ClientError as e:
        logger.warning(f"Failed to send notification: {e}")


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for scheduled provisioning processor.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        Response with processing results
    """
    logger.info(f"Scheduled provisioner invoked: {json.dumps(event)}")

    # Get pending jobs
    pending_jobs = get_pending_jobs()
    logger.info(f"Found {len(pending_jobs)} pending scheduled jobs")

    if not pending_jobs:
        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "No pending jobs to process", "jobs_processed": 0}
            ),
        }

    # Track results
    triggered = 0
    failed = 0
    errors: list[str] = []

    for job in pending_jobs:
        schedule_id = job["schedule_id"]
        logger.info(f"Processing scheduled job: {schedule_id}")

        # Invoke provisioner
        success, execution_id, error_msg = invoke_provisioner(job)

        if success:
            # Update status to triggered
            update_job_status(schedule_id, "triggered", execution_id=execution_id)
            triggered += 1
            publish_metric("ScheduledJobsTriggered")
        else:
            # Update status to failed
            update_job_status(schedule_id, "failed", error_message=error_msg)
            failed += 1
            errors.append(f"{schedule_id}: {error_msg}")
            publish_metric("ScheduledJobsFailed")

    # Log summary
    logger.info(f"Processing complete: {triggered} triggered, {failed} failed")

    # Send notification if failures occurred
    if failed > 0:
        send_notification(
            f"[{ENVIRONMENT}] Scheduled Provisioning Failures",
            f"Failed to trigger {failed} scheduled jobs:\n" + "\n".join(errors),
        )

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Processing complete",
                "jobs_processed": len(pending_jobs),
                "triggered": triggered,
                "failed": failed,
                "errors": errors if errors else None,
            }
        ),
    }
