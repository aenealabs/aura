"""
WebSocket Disconnect Handler for Real-Time Intervention.

Handles $disconnect route for API Gateway WebSocket API.
Removes connections from DynamoDB registry.
"""

import logging
import os

from botocore.exceptions import ClientError

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import get_dynamodb_resource
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CONNECTIONS_TABLE = os.environ.get("CONNECTIONS_TABLE", "aura-ws-connections-dev")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def get_connections_table():
    """Get DynamoDB connections table (lazy initialization)."""
    return get_dynamodb_resource(REGION).Table(CONNECTIONS_TABLE)


def handler(event, context):
    """
    Handle WebSocket $disconnect route.

    Removes the connection from the registry table.
    This is called when the client disconnects or the connection times out.

    Returns:
        200 on success (always returns success for disconnect)
    """
    connection_id = event["requestContext"]["connectionId"]

    logger.info(f"WebSocket disconnect: {connection_id}")

    try:
        # Get connection details before deleting (for logging)
        response = get_connections_table().get_item(
            Key={"connection_id": connection_id}
        )
        item = response.get("Item")

        if item:
            user_id = str(item.get("user_id", "unknown"))
            execution_id = str(item.get("execution_id", "unknown"))
            logger.info(
                f"Disconnecting user {user_id} from " f"execution {execution_id}"
            )

        # Delete the connection
        get_connections_table().delete_item(Key={"connection_id": connection_id})

        logger.info(f"Connection {connection_id} removed from registry")

    except ClientError as e:
        # Log but don't fail - connection is already gone
        logger.error(f"Error removing connection {connection_id}: {e}")

    # Always return success for disconnect
    return {"statusCode": 200, "body": "Disconnected"}
