"""
Aura Chat WebSocket Connect Handler

Handles WebSocket connection establishment for real-time chat streaming.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

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
    Handle WebSocket $connect route.

    Stores connection info in DynamoDB for later message routing.
    """
    logger.info(f"WebSocket connect event: {json.dumps(event)}")

    try:
        connection_id = event["requestContext"]["connectionId"]

        # Extract user info from query string or authorizer
        # Note: For production, use a custom authorizer with JWT
        query_params = event.get("queryStringParameters") or {}
        user_id = query_params.get("userId", "anonymous")
        tenant_id = query_params.get("tenantId", "default")

        # Calculate TTL (connections expire after 2 hours)
        ttl = int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp())

        # Store connection
        get_connections_table().put_item(
            Item={
                "connection_id": connection_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "ttl": ttl,
            }
        )

        logger.info(f"WebSocket connected: {connection_id} for user {user_id}")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Connected"}),
        }

    except Exception as e:
        logger.exception(f"Error handling WebSocket connect: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to connect"}),
        }
