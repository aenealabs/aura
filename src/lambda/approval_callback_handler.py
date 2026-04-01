"""
Project Aura - Approval Callback Handler Lambda

Lambda function that handles Step Functions task token callbacks for
the HITL approval workflow.

This Lambda serves two purposes:
1. Register task tokens when Step Functions enters WaitForHumanApproval state
2. Process approval decisions and send task success/failure callbacks

Triggered by:
- API Gateway for approval submissions
- Step Functions for task token registration

Author: Project Aura Team
Created: 2025-12-03
Version: 1.0.0
"""

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for approval callback processing.

    Handles two types of events:
    1. Task Token Registration (from Step Functions):
       {"action": "register_token", "workflow_id": "...", "task_token": "..."}

    2. Approval Decision (from API Gateway or Dashboard):
       {"action": "process_approval", "approval_id": "...", "decision": "APPROVED|REJECTED", ...}

    Args:
        event: Event payload (API Gateway or Step Functions)
        context: Lambda context

    Returns:
        Response with status and details
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # Handle API Gateway proxy integration
    if "httpMethod" in event:
        return handle_api_gateway_event(event, context)

    # Handle direct invocation (Step Functions or internal)
    action = event.get("action", "")

    if action == "register_token":
        return handle_register_token(event)
    elif action == "process_approval":
        return handle_process_approval(event)
    else:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Unknown action: {action}"}),
        }


def handle_api_gateway_event(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle API Gateway proxy integration events."""
    http_method = event.get("httpMethod", "")
    path = event.get("path", "")

    logger.info(f"API Gateway: {http_method} {path}")

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return api_response(400, {"error": "Invalid JSON body"})

    # Route based on path
    if path.endswith("/approve") and http_method == "POST":
        return handle_approval_decision(body, decision="APPROVED")
    elif path.endswith("/reject") and http_method == "POST":
        return handle_approval_decision(body, decision="REJECTED")
    elif path.endswith("/register-token") and http_method == "POST":
        return handle_register_token(body)
    else:
        return api_response(404, {"error": f"Route not found: {http_method} {path}"})


def handle_register_token(event: dict[str, Any]) -> dict[str, Any]:
    """
    Register a Step Functions task token for a workflow.

    This is called when Step Functions enters the WaitForHumanApproval state.
    The task token is stored so we can send the callback when approval is received.

    Args:
        event: {
            "workflow_id": "workflow-abc123",
            "approval_id": "approval-xyz789",
            "task_token": "AQCgAAAAKgAAAAMAAAAAAA..."
        }

    Returns:
        Registration result
    """
    workflow_id = event.get("workflow_id")
    approval_id = event.get("approval_id")
    task_token = event.get("task_token")

    if not all([workflow_id, task_token]):
        return api_response(
            400, {"error": "Missing required fields: workflow_id, task_token"}
        )

    logger.info(f"Registering task token for workflow {workflow_id}")

    # Get configuration
    table_name = os.environ.get("WORKFLOW_TABLE_NAME", "aura-patch-workflows-dev")
    region = os.environ.get("AWS_REGION", "us-east-1")

    try:
        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)

        # Update workflow with task token
        table.update_item(
            Key={"workflow_id": workflow_id},
            UpdateExpression="SET task_token = :token, updated_at = :updated",
            ExpressionAttributeValues={
                ":token": task_token,
                ":updated": get_timestamp(),
            },
        )

        # Also store in approval table for faster lookup
        approval_table_name = os.environ.get(
            "APPROVAL_TABLE_NAME", "aura-approval-requests-dev"
        )
        if approval_id:
            approval_table = dynamodb.Table(approval_table_name)
            approval_table.update_item(
                Key={"approvalId": approval_id},
                UpdateExpression="SET task_token = :token, workflow_id = :wid",
                ExpressionAttributeValues={
                    ":token": task_token,
                    ":wid": workflow_id,
                },
            )

        logger.info(f"Task token registered for workflow {workflow_id}")

        return api_response(
            200,
            {
                "status": "registered",
                "workflow_id": workflow_id,
                "approval_id": approval_id,
            },
        )

    except ClientError as e:
        logger.error(f"Failed to register task token: {e}")
        return api_response(500, {"error": str(e)})


def handle_approval_decision(body: dict[str, Any], decision: str) -> dict[str, Any]:
    """
    Handle approval decision from Dashboard or API.

    Args:
        body: {
            "approval_id": "approval-xyz789",
            "approver_email": "senior.engineer@company.com",
            "comments": "Verified patch is correct"
        }
        decision: APPROVED or REJECTED
    """
    approval_id = body.get("approval_id")
    approver_email = body.get("approver_email", "unknown@company.com")
    comments = body.get("comments", "")

    if not approval_id:
        return api_response(400, {"error": "Missing approval_id"})

    logger.info(f"Processing {decision} for approval {approval_id}")

    return handle_process_approval(
        {
            "approval_id": approval_id,
            "decision": decision,
            "approver_email": approver_email,
            "comments": comments,
        }
    )


def handle_process_approval(event: dict[str, Any]) -> dict[str, Any]:
    """
    Process an approval decision and send Step Functions callback.

    Args:
        event: {
            "approval_id": "approval-xyz789",
            "decision": "APPROVED" or "REJECTED",
            "approver_email": "senior.engineer@company.com",
            "comments": "Optional comments"
        }

    Returns:
        Processing result
    """
    approval_id = event.get("approval_id")
    decision = event.get("decision", "").upper()
    approver_email = event.get("approver_email", "unknown")
    comments = event.get("comments", "")

    if not approval_id or decision not in ["APPROVED", "REJECTED"]:
        return api_response(
            400, {"error": "Invalid request: approval_id and valid decision required"}
        )

    # Get configuration
    approval_table_name = os.environ.get(
        "APPROVAL_TABLE_NAME", "aura-approval-requests-dev"
    )
    workflow_table_name = os.environ.get(
        "WORKFLOW_TABLE_NAME", "aura-patch-workflows-dev"
    )
    region = os.environ.get("AWS_REGION", "us-east-1")

    try:
        dynamodb = boto3.resource("dynamodb", region_name=region)
        sfn = boto3.client("stepfunctions", region_name=region)

        # Get approval record to find task token
        approval_table = dynamodb.Table(approval_table_name)
        response = approval_table.get_item(Key={"approvalId": approval_id})
        approval_record = response.get("Item")

        if not approval_record:
            return api_response(404, {"error": f"Approval {approval_id} not found"})

        task_token = approval_record.get("task_token")
        workflow_id = approval_record.get("workflow_id")

        # Update approval status
        approval_table.update_item(
            Key={"approvalId": approval_id},
            UpdateExpression="""
                SET #status = :status,
                    approver_email = :approver,
                    decision_timestamp = :timestamp,
                    approver_comments = :comments
            """,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": decision,
                ":approver": approver_email,
                ":timestamp": get_timestamp(),
                ":comments": comments,
            },
        )

        # Update workflow status if we have workflow_id
        if workflow_id:
            workflow_table = dynamodb.Table(workflow_table_name)
            workflow_status = "approved" if decision == "APPROVED" else "rejected"
            workflow_table.update_item(
                Key={"workflow_id": workflow_id},
                UpdateExpression="""
                    SET #status = :status,
                        updated_at = :updated,
                        completed_at = :completed
                """,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": workflow_status,
                    ":updated": get_timestamp(),
                    ":completed": get_timestamp(),
                },
            )

        # Send Step Functions callback if we have a task token
        callback_result = None
        if task_token:
            try:
                if decision == "APPROVED":
                    sfn.send_task_success(
                        taskToken=task_token,
                        output=json.dumps(
                            {
                                "decision": "APPROVED",
                                "approval_id": approval_id,
                                "approver": approver_email,
                                "comments": comments,
                                "timestamp": get_timestamp(),
                            }
                        ),
                    )
                    callback_result = "success_sent"
                else:
                    sfn.send_task_failure(
                        taskToken=task_token,
                        error="ApprovalRejected",
                        cause=comments or "Patch rejected by reviewer",
                    )
                    callback_result = "failure_sent"

                logger.info(f"Step Functions callback sent: {callback_result}")

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "TaskTimedOut":
                    logger.warning(f"Task token expired for approval {approval_id}")
                    callback_result = "token_expired"
                elif error_code == "TaskDoesNotExist":
                    logger.warning(f"Task no longer exists for approval {approval_id}")
                    callback_result = "task_not_found"
                else:
                    raise
        else:
            callback_result = "no_token"
            logger.info(f"No task token for approval {approval_id}")

        # Send notification about the decision
        await_send_notification(approval_id, decision, approver_email, comments)

        return api_response(
            200,
            {
                "status": "processed",
                "approval_id": approval_id,
                "decision": decision,
                "workflow_id": workflow_id,
                "callback_result": callback_result,
            },
        )

    except ClientError as e:
        logger.error(f"Failed to process approval: {e}")
        return api_response(500, {"error": str(e)})


def await_send_notification(
    approval_id: str, decision: str, approver_email: str, comments: str
) -> None:
    """Send notification about approval decision (async, non-blocking)."""
    try:
        sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")
        if not sns_topic_arn:
            logger.info("No SNS topic configured, skipping notification")
            return

        sns = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "us-east-1"))

        subject = f"[AURA] Patch {decision}: {approval_id}"
        message = f"""
Patch Approval Decision

Approval ID: {approval_id}
Decision: {decision}
Approver: {approver_email}
Timestamp: {get_timestamp()}

Comments:
{comments or '(none)'}

---
Project Aura - Autonomous Code Intelligence Platform
"""

        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=subject[:100],  # SNS subject limit
            Message=message,
        )

        logger.info(f"Notification sent for {approval_id}")

    except Exception as e:
        # Don't fail the whole operation if notification fails
        logger.error(f"Failed to send notification: {e}")


def get_timestamp() -> str:
    """Get current UTC timestamp in ISO format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def api_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """Create API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }
