"""
Project Aura - WebSocket Message Handler Tests

Comprehensive tests for the WebSocket message handler Lambda function
that processes chat messages and streams responses via Bedrock.
"""

import json
import os
import platform
import sys
from unittest.mock import MagicMock

import pytest

# Run all tests in separate subprocesses to prevent mock pollution
# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Save original modules before mocking to prevent test pollution
_modules_to_save = [
    "boto3",
    "botocore",
    "botocore.exceptions",
    "tools",
    "src.lambda.chat.tools",
]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock boto3 and tools before imports
mock_dynamodb_resource = MagicMock()
mock_connections_table = MagicMock()
mock_conversations_table = MagicMock()
mock_messages_table = MagicMock()

mock_dynamodb_resource.Table.side_effect = lambda name: {
    "aura-chat-connections-dev": mock_connections_table,
    "aura-chat-conversations-dev": mock_conversations_table,
    "aura-chat-messages-dev": mock_messages_table,
}.get(name, MagicMock())

mock_bedrock_client = MagicMock()
mock_api_gw_client = MagicMock()

mock_boto3 = MagicMock()
mock_boto3.resource.return_value = mock_dynamodb_resource
mock_boto3.client.side_effect = lambda service, **kwargs: {
    "bedrock-runtime": mock_bedrock_client,
    "apigatewaymanagementapi": mock_api_gw_client,
}.get(service, MagicMock())

# Mock tools module
mock_tools = MagicMock()
mock_tools.CHAT_TOOLS = [
    {
        "name": "search_documentation",
        "description": "Search platform documentation",
        "parameters": {"type": "object", "properties": {}},
    }
]
mock_tools.execute_tool = MagicMock(return_value={"result": "test"})

sys.modules["boto3"] = mock_boto3
sys.modules["botocore"] = MagicMock()
sys.modules["botocore.exceptions"] = MagicMock()


# Create a proper ClientError mock
class MockClientError(Exception):
    def __init__(self, error_response=None, operation_name="Unknown"):
        self.response = error_response or {"Error": {"Code": "500", "Message": "Error"}}
        super().__init__(str(error_response))


sys.modules["botocore.exceptions"].ClientError = MockClientError

# Mock the tools module in the chat package
sys.modules["tools"] = mock_tools
sys.modules["src.lambda.chat.tools"] = mock_tools

# Import using importlib
import importlib

ws_message = importlib.import_module("src.lambda.chat.ws_message")

handler = ws_message.handler
handle_send_message = ws_message.handle_send_message
stream_bedrock_response = ws_message.stream_bedrock_response
get_connection_info = ws_message.get_connection_info
create_conversation = ws_message.create_conversation
get_conversation_history = ws_message.get_conversation_history
save_message = ws_message.save_message
send_to_connection = ws_message.send_to_connection

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


class TestHandler:
    """Tests for the main handler function."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_connections_table.reset_mock()
        mock_conversations_table.reset_mock()
        mock_messages_table.reset_mock()
        mock_bedrock_client.reset_mock()
        mock_api_gw_client.reset_mock()

    def test_handler_ping(self):
        """Test ping action returns pong."""
        event = {
            "requestContext": {
                "connectionId": "conn-123",
                "domainName": "api.example.com",
                "stage": "dev",
            },
            "body": json.dumps({"action": "ping"}),
        }

        response = handler(event, None)

        assert response["statusCode"] == 200
        mock_api_gw_client.post_to_connection.assert_called()

    def test_handler_unknown_action(self):
        """Test unknown action returns error."""
        event = {
            "requestContext": {
                "connectionId": "conn-123",
                "domainName": "api.example.com",
                "stage": "dev",
            },
            "body": json.dumps({"action": "unknown_action"}),
        }

        response = handler(event, None)

        assert response["statusCode"] == 400

    def test_handler_empty_body(self):
        """Test handler with empty body defaults to sendMessage."""
        event = {
            "requestContext": {
                "connectionId": "conn-123",
                "domainName": "api.example.com",
                "stage": "dev",
            },
            "body": "{}",
        }

        # Mock connection info
        mock_connections_table.get_item.return_value = {
            "Item": {"user_id": "user-123", "tenant_id": "tenant-abc"}
        }

        response = handler(event, None)

        # Will get 400 because message is empty
        assert response["statusCode"] == 400

    def test_handler_exception(self):
        """Test handler catches exceptions."""
        event = {
            # Missing requestContext to cause exception
            "body": json.dumps({"action": "sendMessage"}),
        }

        response = handler(event, None)

        assert response["statusCode"] == 500


class TestHandleSendMessage:
    """Tests for handle_send_message function."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_connections_table.reset_mock()
        mock_conversations_table.reset_mock()
        mock_messages_table.reset_mock()
        mock_bedrock_client.reset_mock()
        mock_api_gw_client.reset_mock()

    def test_empty_message(self):
        """Test handling empty message."""
        response = handle_send_message(
            api_client=mock_api_gw_client,
            connection_id="conn-123",
            body={"message": ""},
        )

        assert response["statusCode"] == 400

    def test_whitespace_message(self):
        """Test handling whitespace-only message."""
        response = handle_send_message(
            api_client=mock_api_gw_client,
            connection_id="conn-123",
            body={"message": "   "},
        )

        assert response["statusCode"] == 400

    def test_connection_not_found(self):
        """Test handling when connection not found."""
        mock_connections_table.get_item.return_value = {}

        response = handle_send_message(
            api_client=mock_api_gw_client,
            connection_id="conn-unknown",
            body={"message": "Hello"},
        )

        assert response["statusCode"] == 401

    def test_new_conversation(self):
        """Test creating new conversation."""
        mock_connections_table.get_item.return_value = {
            "Item": {"user_id": "user-123", "tenant_id": "tenant-abc"}
        }
        mock_messages_table.query.return_value = {"Items": []}

        # Mock streaming response
        mock_bedrock_client.converse_stream.return_value = {
            "stream": [
                {"contentBlockStart": {"start": {}}},
                {"contentBlockDelta": {"delta": {"text": "Hello"}}},
                {"messageStop": {"stopReason": "end_turn"}},
                {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5}}},
            ]
        }

        response = handle_send_message(
            api_client=mock_api_gw_client,
            connection_id="conn-123",
            body={"message": "Hi there"},
        )

        assert response["statusCode"] == 200
        mock_conversations_table.put_item.assert_called()

    def test_existing_conversation(self):
        """Test using existing conversation."""
        mock_connections_table.get_item.return_value = {
            "Item": {"user_id": "user-123", "tenant_id": "tenant-abc"}
        }
        mock_messages_table.query.return_value = {
            "Items": [
                {"role": "user", "content": "Previous message"},
            ]
        }

        mock_bedrock_client.converse_stream.return_value = {
            "stream": [
                {"contentBlockDelta": {"delta": {"text": "Response"}}},
                {"messageStop": {"stopReason": "end_turn"}},
                {"metadata": {"usage": {"inputTokens": 20, "outputTokens": 10}}},
            ]
        }

        response = handle_send_message(
            api_client=mock_api_gw_client,
            connection_id="conn-123",
            body={"message": "Continue", "conversation_id": "conv-existing"},
        )

        assert response["statusCode"] == 200
        # Should not create new conversation
        mock_conversations_table.put_item.assert_not_called()


class TestStreamBedrockResponse:
    """Tests for stream_bedrock_response function."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_bedrock_client.reset_mock()
        mock_api_gw_client.reset_mock()

    def test_basic_streaming(self):
        """Test basic text streaming."""
        mock_bedrock_client.converse_stream.return_value = {
            "stream": [
                {"contentBlockStart": {"start": {}}},
                {"contentBlockDelta": {"delta": {"text": "Hello "}}},
                {"contentBlockDelta": {"delta": {"text": "world"}}},
                {"contentBlockStop": {}},
                {"messageStop": {"stopReason": "end_turn"}},
                {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5}}},
            ]
        }

        result = stream_bedrock_response(
            api_client=mock_api_gw_client,
            connection_id="conn-123",
            message="Hi",
            history=[],
            user_info={"user_id": "user-1", "tenant_id": "tenant-1"},
            conversation_id="conv-123",
        )

        assert result["content"] == "Hello world"
        assert result["tokens_input"] == 10
        assert result["tokens_output"] == 5
        # Chunks should be sent
        assert mock_api_gw_client.post_to_connection.call_count >= 2

    def test_streaming_with_history(self):
        """Test streaming with conversation history."""
        mock_bedrock_client.converse_stream.return_value = {
            "stream": [
                {"contentBlockDelta": {"delta": {"text": "Response"}}},
                {"messageStop": {"stopReason": "end_turn"}},
                {"metadata": {"usage": {"inputTokens": 30, "outputTokens": 15}}},
            ]
        }

        history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
        ]

        result = stream_bedrock_response(
            api_client=mock_api_gw_client,
            connection_id="conn-123",
            message="Follow-up",
            history=history,
            user_info={"user_id": "user-1", "tenant_id": "tenant-1"},
            conversation_id="conv-123",
        )

        assert result["content"] == "Response"
        # Verify history was included in request
        call_args = mock_bedrock_client.converse_stream.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 3  # 2 history + 1 new


class TestGetConnectionInfo:
    """Tests for get_connection_info function."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_connections_table.reset_mock()

    def test_connection_found(self):
        """Test getting existing connection."""
        mock_connections_table.get_item.return_value = {
            "Item": {
                "connection_id": "conn-123",
                "user_id": "user-abc",
                "tenant_id": "tenant-xyz",
            }
        }

        result = get_connection_info("conn-123")

        assert result is not None
        assert result["user_id"] == "user-abc"
        assert result["tenant_id"] == "tenant-xyz"

    def test_connection_not_found(self):
        """Test getting non-existent connection."""
        mock_connections_table.get_item.return_value = {}

        result = get_connection_info("conn-unknown")

        assert result is None

    def test_connection_error(self):
        """Test handling DynamoDB error."""
        mock_connections_table.get_item.side_effect = Exception("DynamoDB error")

        result = get_connection_info("conn-123")

        assert result is None
        mock_connections_table.get_item.side_effect = None


class TestCreateConversation:
    """Tests for create_conversation function."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_conversations_table.reset_mock()

    def test_create_conversation(self):
        """Test creating a new conversation."""
        user_info = {"user_id": "user-123", "tenant_id": "tenant-abc"}

        create_conversation("conv-123", user_info)

        mock_conversations_table.put_item.assert_called_once()
        call_args = mock_conversations_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert item["PK"] == "USER#user-123"
        assert item["SK"] == "CONV#conv-123"
        assert item["conversation_id"] == "conv-123"
        assert item["tenant_id"] == "tenant-abc"
        assert item["status"] == "active"
        assert "ttl" in item


class TestGetConversationHistory:
    """Tests for get_conversation_history function."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_messages_table.reset_mock()

    def test_get_history(self):
        """Test getting conversation history."""
        mock_messages_table.query.return_value = {
            "Items": [
                {"role": "assistant", "content": "Response 2"},
                {"role": "user", "content": "Message 2"},
                {"role": "assistant", "content": "Response 1"},
                {"role": "user", "content": "Message 1"},
            ]
        }

        history = get_conversation_history("conv-123", limit=10)

        # Should be reversed (oldest first)
        assert len(history) == 4
        assert history[0]["content"] == "Message 1"
        assert history[3]["content"] == "Response 2"

    def test_get_empty_history(self):
        """Test getting empty history."""
        mock_messages_table.query.return_value = {"Items": []}

        history = get_conversation_history("conv-123")

        assert history == []

    def test_get_history_error(self):
        """Test handling query error."""
        mock_messages_table.query.side_effect = Exception("Query error")

        history = get_conversation_history("conv-123")

        assert history == []
        mock_messages_table.query.side_effect = None


class TestSaveMessage:
    """Tests for save_message function."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_messages_table.reset_mock()

    def test_save_user_message(self):
        """Test saving a user message."""
        message_id = save_message(
            conversation_id="conv-123",
            role="user",
            content="Hello!",
            tenant_id="tenant-abc",
        )

        assert message_id is not None
        mock_messages_table.put_item.assert_called_once()

        call_args = mock_messages_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert item["PK"] == "CONV#conv-123"
        assert item["role"] == "user"
        assert item["content"] == "Hello!"
        assert item["tenant_id"] == "tenant-abc"

    def test_save_assistant_message_with_tokens(self):
        """Test saving assistant message with token counts."""
        _message_id = save_message(
            conversation_id="conv-123",
            role="assistant",
            content="Response",
            tenant_id="tenant-abc",
            tokens_input=100,
            tokens_output=50,
            model_id="claude-3-5-sonnet",
        )

        call_args = mock_messages_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert item["tokens_input"] == 100
        assert item["tokens_output"] == 50
        assert item["model_id"] == "claude-3-5-sonnet"

    def test_save_message_with_tool_calls(self):
        """Test saving message with tool calls."""
        tool_calls = [{"name": "search", "input": {}, "output": {"result": "data"}}]

        save_message(
            conversation_id="conv-123",
            role="assistant",
            content="I searched for you",
            tenant_id="tenant-abc",
            tool_calls=tool_calls,
        )

        call_args = mock_messages_table.put_item.call_args
        item = call_args.kwargs["Item"]

        assert item["tool_calls"] == tool_calls


class TestSendToConnection:
    """Tests for send_to_connection function."""

    def setup_method(self):
        """Reset mocks before each test."""
        mock_api_gw_client.reset_mock()
        mock_connections_table.reset_mock()

    def test_send_success(self):
        """Test successful message send."""
        mock_api_gw_client.post_to_connection.return_value = {}

        result = send_to_connection(
            mock_api_gw_client,
            "conn-123",
            {"type": "chunk", "content": "Hello"},
        )

        assert result is True
        mock_api_gw_client.post_to_connection.assert_called_once()

    def test_send_gone_exception(self):
        """Test handling GoneException (stale connection)."""
        error_response = {"Error": {"Code": "GoneException"}}
        mock_api_gw_client.post_to_connection.side_effect = MockClientError(
            error_response, "PostToConnection"
        )

        result = send_to_connection(
            mock_api_gw_client,
            "conn-stale",
            {"type": "chunk", "content": "Hello"},
        )

        assert result is False
        # Should try to clean up the connection
        mock_connections_table.delete_item.assert_called()
        mock_api_gw_client.post_to_connection.side_effect = None

    def test_send_other_error(self):
        """Test handling other errors."""
        error_response = {"Error": {"Code": "InternalError"}}
        mock_api_gw_client.post_to_connection.side_effect = MockClientError(
            error_response, "PostToConnection"
        )

        result = send_to_connection(
            mock_api_gw_client,
            "conn-123",
            {"type": "chunk", "content": "Hello"},
        )

        assert result is False
        mock_api_gw_client.post_to_connection.side_effect = None


class TestSystemPrompt:
    """Tests for system prompt configuration."""

    def test_system_prompt_contains_capabilities(self):
        """Test that system prompt lists key capabilities."""
        prompt = ws_message.SYSTEM_PROMPT

        assert "Aura Assistant" in prompt
        assert "vulnerability" in prompt.lower()
        assert "documentation" in prompt.lower()
        assert "GraphRAG" in prompt


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_default_environment(self):
        """Test default environment values."""
        assert ws_message.ENVIRONMENT == os.environ.get("ENVIRONMENT", "dev")
        assert "aura" in ws_message.CONNECTIONS_TABLE
        assert "aura" in ws_message.CONVERSATIONS_TABLE
        assert "aura" in ws_message.MESSAGES_TABLE

    def test_model_id_configuration(self):
        """Test Bedrock model ID configuration."""
        # Should have a default model ID
        assert ws_message.BEDROCK_MODEL_ID is not None
        assert (
            "claude" in ws_message.BEDROCK_MODEL_ID.lower()
            or "anthropic" in ws_message.BEDROCK_MODEL_ID.lower()
        )
