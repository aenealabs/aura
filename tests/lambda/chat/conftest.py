"""
Chat Lambda Tests - Shared Fixtures

Provides common fixtures for testing the chat assistant components:
- Model routing (Phase 1)
- Diagram generation (Phase 2)
- Deep research service (Phase 3)
- Tool execution (Phase 4 integration)
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

# Set mock AWS credentials BEFORE any boto3 imports elsewhere
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Add src/lambda/chat to path for imports
CHAT_LAMBDA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "src",
    "lambda",
    "chat",
)
sys.path.insert(0, os.path.abspath(CHAT_LAMBDA_PATH))

# Test constants
AWS_REGION = "us-east-1"
TEST_TENANT_ID = "test-tenant-001"
TEST_USER_ID = "test-user-001"
TEST_CONVERSATION_ID = "test-conv-001"


@pytest.fixture(scope="function")
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = AWS_REGION
    yield
    # Cleanup handled automatically


@pytest.fixture(scope="function")
def chat_env_vars():
    """Set up environment variables for chat Lambda."""
    env_vars = {
        "ENVIRONMENT": "dev",
        "PROJECT_NAME": "aura",
        "CONVERSATIONS_TABLE": "aura-chat-conversations-dev",
        "MESSAGES_TABLE": "aura-chat-messages-dev",
        "RESEARCH_TASKS_TABLE": "aura-research-tasks-dev",
        "HAIKU_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
        "BEDROCK_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "OPUS_MODEL_ID": "anthropic.claude-3-opus-20240229-v1:0",
        "CONVERSATION_TTL_DAYS": "30",
        "RATE_LIMIT_PER_MINUTE": "30",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture(scope="function")
def mock_user_info():
    """Standard user info for testing."""
    return {
        "user_id": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "email": "test@aenealabs.com",
        "groups": ["admin"],
    }


@pytest.fixture(scope="function")
def mock_dynamodb(aws_credentials):
    """Isolated DynamoDB mock for chat tests."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name=AWS_REGION)
        resource = boto3.resource("dynamodb", region_name=AWS_REGION)
        yield {"client": client, "resource": resource}


@pytest.fixture(scope="function")
def mock_conversations_table(mock_dynamodb):
    """Pre-configured conversations table for testing."""
    client = mock_dynamodb["client"]
    resource = mock_dynamodb["resource"]

    client.create_table(
        TableName="aura-chat-conversations-dev",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "updated_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-conversations-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "updated_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table = resource.Table("aura-chat-conversations-dev")
    yield {"client": client, "resource": resource, "table": table}


@pytest.fixture(scope="function")
def mock_messages_table(mock_dynamodb):
    """Pre-configured messages table for testing."""
    client = mock_dynamodb["client"]
    resource = mock_dynamodb["resource"]

    client.create_table(
        TableName="aura-chat-messages-dev",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table = resource.Table("aura-chat-messages-dev")
    yield {"client": client, "resource": resource, "table": table}


@pytest.fixture(scope="function")
def mock_research_tasks_table(mock_dynamodb):
    """Pre-configured research tasks table for testing."""
    client = mock_dynamodb["client"]
    resource = mock_dynamodb["resource"]

    client.create_table(
        TableName="aura-research-tasks-dev",
        KeySchema=[
            {"AttributeName": "task_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "task_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "tenant_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "user-tasks-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "tenant-tasks-index",
                "KeySchema": [
                    {"AttributeName": "tenant_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    table = resource.Table("aura-research-tasks-dev")
    yield {"client": client, "resource": resource, "table": table}


@pytest.fixture(scope="function")
def mock_bedrock_client():
    """Mock Bedrock runtime client for testing."""
    mock_client = MagicMock()

    # Default successful response
    mock_client.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": "Mock response from Claude"}],
            }
        },
        "usage": {"inputTokens": 100, "outputTokens": 50},
        "stopReason": "end_turn",
    }

    return mock_client


@pytest.fixture(scope="function")
def mock_cloudwatch_client():
    """Mock CloudWatch client for agent status tests."""
    mock_client = MagicMock()

    mock_client.get_metric_data.return_value = {
        "MetricDataResults": [
            {"Values": [100, 150, 200]},  # Invocations
            {"Values": [0, 0, 1]},  # Errors
        ]
    }

    return mock_client


@pytest.fixture(scope="function")
def sample_chat_event(mock_user_info):
    """Sample API Gateway event for chat message."""
    return {
        "httpMethod": "POST",
        "path": "/chat/message",
        "headers": {
            "Content-Type": "application/json",
            "X-Dev-User-Id": mock_user_info["user_id"],
            "X-Dev-Tenant-Id": mock_user_info["tenant_id"],
            "X-Dev-Email": mock_user_info["email"],
        },
        "body": '{"message": "What is the status of the agents?"}',
        "requestContext": {},
    }


@pytest.fixture(scope="function")
def sample_research_task():
    """Sample research task for testing."""
    now = datetime.now(timezone.utc)
    return {
        "task_id": "RSH-TEST123ABC",
        "user_id": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "query": "Analyze security vulnerabilities in authentication module",
        "scope": "repository",
        "urgency": "standard",
        "data_sources": ["code_graph", "security_findings"],
        "status": "pending",
        "progress": 0,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "ttl": int((now + timedelta(days=7)).timestamp()),
    }


@pytest.fixture(scope="function")
def sample_conversation():
    """Sample conversation for testing."""
    now = datetime.now(timezone.utc)
    return {
        "PK": f"USER#{TEST_USER_ID}",
        "SK": f"CONV#{TEST_CONVERSATION_ID}",
        "conversation_id": TEST_CONVERSATION_ID,
        "user_id": TEST_USER_ID,
        "tenant_id": TEST_TENANT_ID,
        "title": "Test Conversation",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "message_count": 0,
        "total_tokens": 0,
        "status": "active",
        "ttl": int((now + timedelta(days=30)).timestamp()),
    }
