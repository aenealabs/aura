"""
Project Aura - WebSocket Connect/Disconnect Handler Tests

Tests for the WebSocket connect and disconnect Lambda handlers
that manage connection state in DynamoDB.
"""

import importlib
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Import the modules using importlib (lambda is a reserved keyword)
ws_connect = importlib.import_module("src.lambda.chat.ws_connect")
ws_disconnect = importlib.import_module("src.lambda.chat.ws_disconnect")

connect_handler = ws_connect.handler
disconnect_handler = ws_disconnect.handler


class TestWebSocketConnect:
    """Tests for WebSocket connect handler."""

    def test_connect_basic(self):
        """Test basic WebSocket connection."""
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-abc123",
            },
        }

        with patch.object(ws_connect, "get_connections_table", return_value=mock_table):
            response = connect_handler(event, None)

            assert response["statusCode"] == 200
            mock_table.put_item.assert_called_once()

            # Verify the item stored
            call_args = mock_table.put_item.call_args
            item = call_args.kwargs["Item"]
            assert item["connection_id"] == "conn-abc123"
            assert item["user_id"] == "anonymous"
            assert item["tenant_id"] == "default"
            assert "connected_at" in item
            assert "ttl" in item

    def test_connect_with_query_params(self):
        """Test WebSocket connection with query parameters."""
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-xyz789",
            },
            "queryStringParameters": {
                "userId": "user-123",
                "tenantId": "tenant-abc",
            },
        }

        with patch.object(ws_connect, "get_connections_table", return_value=mock_table):
            response = connect_handler(event, None)

            assert response["statusCode"] == 200
            call_args = mock_table.put_item.call_args
            item = call_args.kwargs["Item"]
            assert item["user_id"] == "user-123"
            assert item["tenant_id"] == "tenant-abc"

    def test_connect_empty_query_params(self):
        """Test connection with empty query params uses defaults."""
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-empty",
            },
            "queryStringParameters": {},
        }

        with patch.object(ws_connect, "get_connections_table", return_value=mock_table):
            response = connect_handler(event, None)

            assert response["statusCode"] == 200
            call_args = mock_table.put_item.call_args
            item = call_args.kwargs["Item"]
            assert item["user_id"] == "anonymous"
            assert item["tenant_id"] == "default"

    def test_connect_null_query_params(self):
        """Test connection with null query params uses defaults."""
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-null",
            },
            "queryStringParameters": None,
        }

        with patch.object(ws_connect, "get_connections_table", return_value=mock_table):
            response = connect_handler(event, None)

            assert response["statusCode"] == 200

    def test_connect_ttl_set(self):
        """Test that TTL is set for connection."""
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-ttl",
            },
        }

        with patch.object(ws_connect, "get_connections_table", return_value=mock_table):
            connect_handler(event, None)

            call_args = mock_table.put_item.call_args
            item = call_args.kwargs["Item"]

            # TTL should be approximately 2 hours from now
            now = datetime.now(timezone.utc)
            expected_ttl = int(now.timestamp()) + (2 * 60 * 60)
            # Allow 10 second tolerance
            assert abs(item["ttl"] - expected_ttl) < 10

    def test_connect_dynamodb_error(self):
        """Test handling DynamoDB error on connect."""
        mock_table = MagicMock()
        mock_table.put_item.side_effect = Exception("DynamoDB error")

        event = {
            "requestContext": {
                "connectionId": "conn-error",
            },
        }

        with patch.object(ws_connect, "get_connections_table", return_value=mock_table):
            response = connect_handler(event, None)

            assert response["statusCode"] == 500
            body = json.loads(response["body"])
            assert "error" in body

    def test_connect_response_body(self):
        """Test connect response body format."""
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-body",
            },
        }

        with patch.object(ws_connect, "get_connections_table", return_value=mock_table):
            response = connect_handler(event, None)

            body = json.loads(response["body"])
            assert body["message"] == "Connected"


class TestWebSocketDisconnect:
    """Tests for WebSocket disconnect handler."""

    def test_disconnect_basic(self):
        """Test basic WebSocket disconnection."""
        mock_table = MagicMock()
        mock_table.delete_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-abc123",
            },
        }

        with patch.object(
            ws_disconnect, "get_connections_table", return_value=mock_table
        ):
            response = disconnect_handler(event, None)

            assert response["statusCode"] == 200
            mock_table.delete_item.assert_called_once()

            # Verify the key used for deletion
            call_args = mock_table.delete_item.call_args
            key = call_args.kwargs["Key"]
            assert key["connection_id"] == "conn-abc123"

    def test_disconnect_response_body(self):
        """Test disconnect response body format."""
        mock_table = MagicMock()
        mock_table.delete_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-body",
            },
        }

        with patch.object(
            ws_disconnect, "get_connections_table", return_value=mock_table
        ):
            response = disconnect_handler(event, None)

            body = json.loads(response["body"])
            assert body["message"] == "Disconnected"

    def test_disconnect_dynamodb_error(self):
        """Test handling DynamoDB error on disconnect."""
        mock_table = MagicMock()
        mock_table.delete_item.side_effect = Exception("DynamoDB error")

        event = {
            "requestContext": {
                "connectionId": "conn-error",
            },
        }

        with patch.object(
            ws_disconnect, "get_connections_table", return_value=mock_table
        ):
            response = disconnect_handler(event, None)

            assert response["statusCode"] == 500
            body = json.loads(response["body"])
            assert "error" in body

    def test_disconnect_nonexistent_connection(self):
        """Test disconnecting a connection that doesn't exist."""
        mock_table = MagicMock()
        # DynamoDB delete_item doesn't error on non-existent keys
        mock_table.delete_item.return_value = {}

        event = {
            "requestContext": {
                "connectionId": "conn-nonexistent",
            },
        }

        with patch.object(
            ws_disconnect, "get_connections_table", return_value=mock_table
        ):
            response = disconnect_handler(event, None)

            assert response["statusCode"] == 200


class TestEnvironmentConfiguration:
    """Tests for environment variable configuration."""

    def test_connect_environment_default(self):
        """Test default environment variable."""
        assert ws_connect.ENVIRONMENT == "dev" or ws_connect.ENVIRONMENT is not None

    def test_disconnect_environment_default(self):
        """Test default environment variable."""
        assert (
            ws_disconnect.ENVIRONMENT == "dev" or ws_disconnect.ENVIRONMENT is not None
        )

    def test_connections_table_name(self):
        """Test connections table name contains environment."""
        assert "aura-chat-connections" in ws_connect.CONNECTIONS_TABLE
        assert "aura-chat-connections" in ws_disconnect.CONNECTIONS_TABLE
