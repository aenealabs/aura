"""
Aura Chat WebSocket Disconnect Handler

Handles WebSocket disconnection cleanup.
"""

import json
import logging
import os

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
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
CONNECTIONS_TABLE = os.environ.get(
    "CONNECTIONS_TABLE", f"aura-chat-connections-{ENVIRONMENT}"
)


def get_connections_table():
    """Get DynamoDB connections table (lazy initialization)."""
    return get_dynamodb_resource().Table(CONNECTIONS_TABLE)


def handler(event: dict, context) -> dict:
    """
    Handle WebSocket $disconnect route.

    Removes connection from DynamoDB.
    """
    logger.info(f"WebSocket disconnect event: {json.dumps(event)}")

    try:
        connection_id = event["requestContext"]["connectionId"]

        # Remove connection
        get_connections_table().delete_item(Key={"connection_id": connection_id})

        logger.info(f"WebSocket disconnected: {connection_id}")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Disconnected"}),
        }

    except Exception as e:
        logger.exception(f"Error handling WebSocket disconnect: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to disconnect"}),
        }
