"""
WebSocket Connect Handler for Real-Time Intervention.

Handles $connect route for API Gateway WebSocket API.
Registers connections in DynamoDB for event broadcasting.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

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
    Handle WebSocket $connect route.

    Query parameters:
        execution_id: Required. Execution to subscribe to.
        token: Required. JWT authentication token.

    Returns:
        200 on success, 400/401 on error
    """
    connection_id = event["requestContext"]["connectionId"]
    query_params = event.get("queryStringParameters") or {}

    logger.info(f"WebSocket connect: {connection_id}")

    # Extract required parameters
    execution_id = query_params.get("execution_id")
    token = query_params.get("token")

    if not execution_id:
        logger.warning(f"Missing execution_id for connection {connection_id}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "execution_id is required"}),
        }

    if not token:
        logger.warning(f"Missing token for connection {connection_id}")
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Authentication token required"}),
        }

    # Validate JWT token (simplified - full validation should use JWT library)
    user_id = validate_token(token)
    if not user_id:
        logger.warning(f"Invalid token for connection {connection_id}")
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Invalid or expired token"}),
        }

    # Check user has access to execution (simplified check)
    if not check_execution_access(user_id, execution_id):
        logger.warning(f"Access denied for {user_id} to execution {execution_id}")
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Access denied to execution"}),
        }

    # Register connection
    try:
        ttl = int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp())

        get_connections_table().put_item(
            Item={
                "connection_id": connection_id,
                "execution_id": execution_id,
                "user_id": user_id,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "ttl": ttl,
            }
        )

        logger.info(
            f"Registered connection {connection_id} for user {user_id} "
            f"on execution {execution_id}"
        )

        return {"statusCode": 200, "body": "Connected"}

    except ClientError as e:
        logger.error(f"Error registering connection: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to register connection"}),
        }


def validate_token(token: str) -> str | None:
    """
    Validate JWT token and extract user ID.

    In production, this should:
    1. Verify JWT signature with Cognito/auth provider public key
    2. Check token expiration
    3. Validate audience/issuer claims

    Args:
        token: JWT token string

    Returns:
        User ID if valid, None otherwise
    """
    try:
        # Simplified: decode without verification for demo
        # Production should use PyJWT or similar
        import base64

        parts = token.split(".")
        if len(parts) != 3:
            return None

        # Decode payload (middle part)
        payload = parts[1]
        # Add padding if needed
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)

        # Check expiration
        exp = claims.get("exp", 0)
        if exp < datetime.now(timezone.utc).timestamp():
            return None

        user_id: str | None = claims.get("sub") or claims.get("user_id")
        return user_id

    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None


def check_execution_access(user_id: str, execution_id: str) -> bool:
    """
    Check if user has access to the execution.

    In production, this should:
    1. Query executions table for ownership
    2. Check team/organization membership
    3. Validate RBAC permissions

    Args:
        user_id: User requesting access
        execution_id: Execution to access

    Returns:
        True if access allowed
    """
    # Simplified: allow all authenticated users
    # Production should implement proper authorization
    return True
