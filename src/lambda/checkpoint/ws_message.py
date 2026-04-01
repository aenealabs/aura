"""
WebSocket Message Handler for Real-Time Intervention.

Handles $default route for API Gateway WebSocket API.
Processes client messages for checkpoint approval/denial/modification.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import get_dynamodb_resource, get_events_client
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource
    get_events_client = _aws_clients.get_events_client

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CONNECTIONS_TABLE = os.environ.get("CONNECTIONS_TABLE", "aura-ws-connections-dev")
CHECKPOINTS_TABLE = os.environ.get("CHECKPOINTS_TABLE", "aura-checkpoints-dev")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "aura-checkpoint-events-dev")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def get_connections_table():
    """Get DynamoDB connections table (lazy initialization)."""
    return get_dynamodb_resource(REGION).Table(CONNECTIONS_TABLE)


def get_checkpoints_table():
    """Get DynamoDB checkpoints table (lazy initialization)."""
    return get_dynamodb_resource(REGION).Table(CHECKPOINTS_TABLE)


def handler(event, context):
    """
    Handle WebSocket messages from clients.

    Supported message actions:
        - checkpoint.approve: Approve a pending checkpoint
        - checkpoint.deny: Deny a pending checkpoint
        - checkpoint.modify: Modify parameters and approve
        - execution.pause: Pause execution
        - execution.resume: Resume execution
        - execution.stop: Emergency stop
        - ping: Connection keep-alive

    Message format:
        {
            "action": "checkpoint.approve",
            "checkpoint_id": "uuid",
            "data": { ... optional data ... }
        }

    Returns:
        200 on success, 400 on invalid message
    """
    connection_id = event["requestContext"]["connectionId"]
    domain = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return send_error(domain, stage, connection_id, "Invalid JSON")

    action = body.get("action")
    if not action:
        return send_error(domain, stage, connection_id, "Missing action field")

    logger.info(f"Received action '{action}' from connection {connection_id}")

    # Get connection context
    connection = get_connection(connection_id)
    if not connection:
        return send_error(domain, stage, connection_id, "Connection not found")

    user_id = connection.get("user_id")
    execution_id = connection.get("execution_id")

    # Validate required fields from connection
    if not user_id:
        return send_error(domain, stage, connection_id, "Missing user_id in connection")
    if not execution_id:
        return send_error(
            domain, stage, connection_id, "Missing execution_id in connection"
        )

    # Route to appropriate handler
    handlers = {
        "checkpoint.approve": handle_approve,
        "checkpoint.deny": handle_deny,
        "checkpoint.modify": handle_modify,
        "execution.pause": handle_pause,
        "execution.resume": handle_resume,
        "execution.stop": handle_stop,
        "ping": handle_ping,
    }

    handler_func = handlers.get(action)
    if not handler_func:
        return send_error(domain, stage, connection_id, f"Unknown action: {action}")

    try:
        result = handler_func(
            body=body,
            user_id=str(user_id),
            execution_id=str(execution_id),
            connection_id=connection_id,
        )

        # Send success response
        send_response(
            domain,
            stage,
            connection_id,
            {
                "type": "response",
                "action": action,
                "success": True,
                "data": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {"statusCode": 200, "body": "OK"}

    except Exception as e:
        logger.error(f"Error handling {action}: {e}")
        return send_error(domain, stage, connection_id, str(e))


def handle_approve(
    body: Dict[str, Any],
    user_id: str,
    execution_id: str,
    connection_id: str,
) -> Dict[str, Any]:
    """Handle checkpoint approval."""
    checkpoint_id = body.get("checkpoint_id")
    if not checkpoint_id:
        raise ValueError("checkpoint_id is required")

    # Validate checkpoint belongs to execution
    checkpoint = get_checkpoint(checkpoint_id)
    if not checkpoint:
        raise ValueError(f"Checkpoint {checkpoint_id} not found")

    if checkpoint.get("execution_id") != execution_id:
        raise ValueError("Checkpoint does not belong to this execution")

    if checkpoint.get("status") != "AWAITING_APPROVAL":
        raise ValueError(
            f"Checkpoint is not awaiting approval: {checkpoint.get('status')}"
        )

    # Update checkpoint status
    update_checkpoint(
        checkpoint_id,
        {
            "status": "APPROVED",
            "decided_by": user_id,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Publish event for orchestrator to continue
    publish_checkpoint_event(checkpoint_id, "APPROVED", user_id, execution_id)

    logger.info(f"Checkpoint {checkpoint_id} approved by {user_id}")

    return {"checkpoint_id": checkpoint_id, "status": "APPROVED"}


def handle_deny(
    body: Dict[str, Any],
    user_id: str,
    execution_id: str,
    connection_id: str,
) -> Dict[str, Any]:
    """Handle checkpoint denial."""
    checkpoint_id = body.get("checkpoint_id")
    reason = body.get("reason", "User denied action")

    if not checkpoint_id:
        raise ValueError("checkpoint_id is required")

    checkpoint = get_checkpoint(checkpoint_id)
    if not checkpoint:
        raise ValueError(f"Checkpoint {checkpoint_id} not found")

    if checkpoint.get("execution_id") != execution_id:
        raise ValueError("Checkpoint does not belong to this execution")

    if checkpoint.get("status") != "AWAITING_APPROVAL":
        raise ValueError(
            f"Checkpoint is not awaiting approval: {checkpoint.get('status')}"
        )

    # Update checkpoint status
    update_checkpoint(
        checkpoint_id,
        {
            "status": "DENIED",
            "decided_by": user_id,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        },
    )

    # Publish event for orchestrator to halt
    publish_checkpoint_event(
        checkpoint_id, "DENIED", user_id, execution_id, reason=reason
    )

    logger.info(f"Checkpoint {checkpoint_id} denied by {user_id}: {reason}")

    return {"checkpoint_id": checkpoint_id, "status": "DENIED", "reason": reason}


def handle_modify(
    body: Dict[str, Any],
    user_id: str,
    execution_id: str,
    connection_id: str,
) -> Dict[str, Any]:
    """Handle checkpoint modification and approval."""
    checkpoint_id = body.get("checkpoint_id")
    modifications = body.get("modifications", {})

    if not checkpoint_id:
        raise ValueError("checkpoint_id is required")

    if not modifications:
        raise ValueError("modifications are required")

    checkpoint = get_checkpoint(checkpoint_id)
    if not checkpoint:
        raise ValueError(f"Checkpoint {checkpoint_id} not found")

    if checkpoint.get("execution_id") != execution_id:
        raise ValueError("Checkpoint does not belong to this execution")

    if checkpoint.get("status") != "AWAITING_APPROVAL":
        raise ValueError(
            f"Checkpoint is not awaiting approval: {checkpoint.get('status')}"
        )

    # Update checkpoint with modifications
    update_checkpoint(
        checkpoint_id,
        {
            "status": "MODIFIED",
            "decided_by": user_id,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "modifications": modifications,
        },
    )

    # Publish event with modifications
    publish_checkpoint_event(
        checkpoint_id, "MODIFIED", user_id, execution_id, modifications=modifications
    )

    logger.info(f"Checkpoint {checkpoint_id} modified by {user_id}")

    return {
        "checkpoint_id": checkpoint_id,
        "status": "MODIFIED",
        "modifications": modifications,
    }


def handle_pause(
    body: Dict[str, Any],
    user_id: str,
    execution_id: str,
    connection_id: str,
) -> Dict[str, Any]:
    """Handle execution pause request."""
    publish_execution_event(execution_id, "PAUSE", user_id)
    logger.info(f"Execution {execution_id} paused by {user_id}")
    return {"execution_id": execution_id, "action": "paused"}


def handle_resume(
    body: Dict[str, Any],
    user_id: str,
    execution_id: str,
    connection_id: str,
) -> Dict[str, Any]:
    """Handle execution resume request."""
    publish_execution_event(execution_id, "RESUME", user_id)
    logger.info(f"Execution {execution_id} resumed by {user_id}")
    return {"execution_id": execution_id, "action": "resumed"}


def handle_stop(
    body: Dict[str, Any],
    user_id: str,
    execution_id: str,
    connection_id: str,
) -> Dict[str, Any]:
    """Handle emergency stop request."""
    reason = body.get("reason", "User initiated emergency stop")
    publish_execution_event(execution_id, "STOP", user_id, reason=reason)
    logger.info(f"Execution {execution_id} stopped by {user_id}: {reason}")
    return {"execution_id": execution_id, "action": "stopped", "reason": reason}


def handle_ping(
    body: Dict[str, Any],
    user_id: str,
    execution_id: str,
    connection_id: str,
) -> Dict[str, Any]:
    """Handle ping for keep-alive."""
    return {"pong": True, "timestamp": datetime.now(timezone.utc).isoformat()}


def get_connection(connection_id: str) -> Dict[str, Any] | None:
    """Get connection details from DynamoDB."""
    try:
        response = get_connections_table().get_item(
            Key={"connection_id": connection_id}
        )
        return response.get("Item")
    except ClientError as e:
        logger.error(f"Error getting connection: {e}")
        return None


def get_checkpoint(checkpoint_id: str) -> Dict[str, Any] | None:
    """Get checkpoint details from DynamoDB."""
    try:
        response = get_checkpoints_table().get_item(
            Key={"checkpoint_id": checkpoint_id}
        )
        return response.get("Item")
    except ClientError as e:
        logger.error(f"Error getting checkpoint: {e}")
        return None


def update_checkpoint(checkpoint_id: str, updates: Dict[str, Any]) -> None:
    """Update checkpoint in DynamoDB."""
    update_expr_parts = []
    expr_values = {}

    for key, value in updates.items():
        update_expr_parts.append(f"#{key} = :{key}")
        expr_values[f":{key}"] = value

    update_expr = "SET " + ", ".join(update_expr_parts)
    expr_names = {f"#{k}": k for k in updates.keys()}

    get_checkpoints_table().update_item(
        Key={"checkpoint_id": checkpoint_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def publish_checkpoint_event(
    checkpoint_id: str,
    status: str,
    user_id: str,
    execution_id: str,
    reason: Optional[str] = None,
    modifications: Optional[Dict[str, Any]] = None,
) -> None:
    """Publish checkpoint decision event to EventBridge."""
    detail: Dict[str, Any] = {
        "checkpoint_id": checkpoint_id,
        "status": status,
        "decided_by": user_id,
        "execution_id": execution_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if reason:
        detail["reason"] = reason
    if modifications:
        detail["modifications"] = modifications

    get_events_client(REGION).put_events(
        Entries=[
            {
                "Source": "aura.checkpoint",
                "DetailType": "CheckpointDecision",
                "Detail": json.dumps(detail),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )


def publish_execution_event(
    execution_id: str,
    action: str,
    user_id: str,
    reason: Optional[str] = None,
) -> None:
    """Publish execution control event to EventBridge."""
    detail: Dict[str, Any] = {
        "execution_id": execution_id,
        "action": action,
        "initiated_by": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if reason:
        detail["reason"] = reason

    get_events_client(REGION).put_events(
        Entries=[
            {
                "Source": "aura.execution",
                "DetailType": "ExecutionControl",
                "Detail": json.dumps(detail),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )


def send_response(
    domain: str,
    stage: str,
    connection_id: str,
    message: Dict[str, Any],
) -> None:
    """Send response message to WebSocket client."""
    endpoint = f"https://{domain}/{stage}"
    client = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint)

    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode("utf-8"),
        )
    except ClientError as e:
        logger.error(f"Error sending response: {e}")


def send_error(
    domain: str,
    stage: str,
    connection_id: str,
    error: str,
) -> Dict[str, Any]:
    """Send error response and return HTTP error."""
    send_response(
        domain,
        stage,
        connection_id,
        {
            "type": "error",
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"statusCode": 400, "body": json.dumps({"error": error})}
