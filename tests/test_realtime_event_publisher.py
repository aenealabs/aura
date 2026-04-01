"""
Tests for Project Aura - Real-Time Event Publisher

Comprehensive tests for WebSocket connection management and
event broadcasting for real-time agent intervention (ADR-042).
"""

import platform
import sys
from unittest.mock import MagicMock

import pytest

# These tests require pytest-forked for isolation. On Linux CI, mock
# patches don't apply correctly without forked mode, so skip there.
# Use forked mode on non-Linux to prevent state pollution
# On Linux (CI), run normally and rely on conftest.py cleanup
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

# Save original modules before mocking to prevent test pollution
_modules_to_save = ["boto3", "botocore", "botocore.exceptions"]
_original_modules = {m: sys.modules.get(m) for m in _modules_to_save}

# Mock boto3 before importing the module
mock_boto3 = MagicMock()
mock_botocore = MagicMock()
sys.modules["boto3"] = mock_boto3
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore.exceptions


# Create a ClientError class that can be raised
class MockClientError(Exception):
    def __init__(self, error_response=None, operation_name="Unknown"):
        self.response = error_response or {"Error": {"Code": "UnknownError"}}
        self.operation_name = operation_name


mock_botocore.exceptions.ClientError = MockClientError

from src.services.realtime_event_publisher import (
    ConnectionInfo,
    LocalEventPublisher,
    RealtimeEventPublisher,
)

# Restore original modules to prevent pollution of other tests
for mod_name, original in _original_modules.items():
    if original is not None:
        sys.modules[mod_name] = original
    else:
        sys.modules.pop(mod_name, None)


# =============================================================================
# ConnectionInfo Tests
# =============================================================================


class TestConnectionInfo:
    """Tests for ConnectionInfo dataclass."""

    def test_connection_info_creation(self):
        """Test ConnectionInfo creation."""
        info = ConnectionInfo(
            connection_id="conn-123",
            execution_id="exec-456",
            user_id="user-789",
            connected_at="2025-01-01T00:00:00Z",
            endpoint_url="wss://api.example.com",
        )

        assert info.connection_id == "conn-123"
        assert info.execution_id == "exec-456"
        assert info.user_id == "user-789"
        assert info.connected_at == "2025-01-01T00:00:00Z"
        assert info.endpoint_url == "wss://api.example.com"


# =============================================================================
# RealtimeEventPublisher Initialization Tests
# =============================================================================


class TestRealtimeEventPublisherInit:
    """Tests for RealtimeEventPublisher initialization."""

    def test_init(self):
        """Test initialization."""
        mock_boto3.resource.return_value = MagicMock()
        mock_boto3.client.return_value = MagicMock()

        publisher = RealtimeEventPublisher(
            connections_table_name="test-connections",
            api_gateway_endpoint="wss://test.execute-api.us-east-1.amazonaws.com/prod",
            region="us-east-1",
        )

        assert publisher.connections_table_name == "test-connections"
        assert publisher.region == "us-east-1"
        assert "test.execute-api" in publisher.endpoint_url

    def test_init_default_region(self):
        """Test initialization with default region."""
        mock_boto3.resource.return_value = MagicMock()
        mock_boto3.client.return_value = MagicMock()

        publisher = RealtimeEventPublisher(
            connections_table_name="connections",
            api_gateway_endpoint="wss://api.example.com",
        )

        assert publisher.region == "us-east-1"


# =============================================================================
# RealtimeEventPublisher Connection Management Tests
# =============================================================================


class TestRealtimeEventPublisherConnections:
    """Tests for connection management."""

    def setup_method(self):
        """Set up test fixtures."""
        mock_boto3.resource.return_value = MagicMock()
        mock_boto3.client.return_value = MagicMock()

        self.publisher = RealtimeEventPublisher(
            connections_table_name="test-connections",
            api_gateway_endpoint="wss://test.example.com",
        )

        self.mock_table = MagicMock()
        self.publisher._connections_table = self.mock_table

    @pytest.mark.asyncio
    async def test_register_connection(self):
        """Test registering a new connection."""
        await self.publisher.register_connection(
            connection_id="conn-123",
            execution_id="exec-456",
            user_id="user-789",
        )

        self.mock_table.put_item.assert_called_once()
        call_args = self.mock_table.put_item.call_args
        item = call_args[1]["Item"]

        assert item["connection_id"] == "conn-123"
        assert item["execution_id"] == "exec-456"
        assert item["user_id"] == "user-789"
        assert "connected_at" in item
        assert "ttl" in item

    @pytest.mark.asyncio
    async def test_register_connection_error(self):
        """Test registering connection with error."""
        self.mock_table.put_item.side_effect = MockClientError(
            {"Error": {"Code": "ValidationException"}}
        )

        with pytest.raises(MockClientError):
            await self.publisher.register_connection(
                connection_id="conn-123",
                execution_id="exec-456",
                user_id="user-789",
            )

    @pytest.mark.asyncio
    async def test_unregister_connection(self):
        """Test unregistering a connection."""
        await self.publisher.unregister_connection("conn-123")

        self.mock_table.delete_item.assert_called_once()
        call_args = self.mock_table.delete_item.call_args
        assert call_args[1]["Key"]["connection_id"] == "conn-123"

    @pytest.mark.asyncio
    async def test_unregister_connection_error(self):
        """Test unregistering connection with error (should not raise)."""
        self.mock_table.delete_item.side_effect = MockClientError()

        # Should not raise, just log the error
        await self.publisher.unregister_connection("conn-123")


# =============================================================================
# RealtimeEventPublisher Publishing Tests
# =============================================================================


class TestRealtimeEventPublisherPublishing:
    """Tests for event publishing."""

    def setup_method(self):
        """Set up test fixtures."""
        mock_boto3.resource.return_value = MagicMock()
        mock_boto3.client.return_value = MagicMock()

        self.publisher = RealtimeEventPublisher(
            connections_table_name="test-connections",
            api_gateway_endpoint="wss://test.example.com",
        )

        self.mock_table = MagicMock()
        self.mock_api_client = MagicMock()
        self.publisher._connections_table = self.mock_table
        self.publisher._api_client = self.mock_api_client

    @pytest.mark.asyncio
    async def test_publish_no_connections(self):
        """Test publishing with no connections."""
        self.mock_table.query.return_value = {"Items": []}

        result = await self.publisher.publish(
            execution_id="exec-123",
            event={"type": "checkpoint", "data": {}},
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_publish_to_connections(self):
        """Test publishing to multiple connections."""
        self.mock_table.query.return_value = {
            "Items": [
                {"connection_id": "conn-1"},
                {"connection_id": "conn-2"},
                {"connection_id": "conn-3"},
            ]
        }

        result = await self.publisher.publish(
            execution_id="exec-123",
            event={"type": "checkpoint", "data": {"step": 1}},
        )

        assert result == 3
        assert self.mock_api_client.post_to_connection.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_cleans_stale_connections(self):
        """Test that stale connections are cleaned up."""
        self.mock_table.query.return_value = {
            "Items": [
                {"connection_id": "active-conn"},
                {"connection_id": "stale-conn"},
            ]
        }

        # First call succeeds, second raises GoneException
        def post_side_effect(**kwargs):
            if kwargs["ConnectionId"] == "stale-conn":
                raise MockClientError({"Error": {"Code": "GoneException"}})

        self.mock_api_client.post_to_connection.side_effect = post_side_effect

        result = await self.publisher.publish(
            execution_id="exec-123",
            event={"type": "test"},
        )

        assert result == 1
        # Should have called delete for stale connection
        self.mock_table.delete_item.assert_called()

    @pytest.mark.asyncio
    async def test_publish_to_connection_success(self):
        """Test publishing to specific connection."""
        result = await self.publisher.publish_to_connection(
            connection_id="conn-123",
            event={"type": "message", "data": "hello"},
        )

        assert result is True
        self.mock_api_client.post_to_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_to_connection_gone(self):
        """Test publishing to gone connection."""
        self.mock_api_client.post_to_connection.side_effect = MockClientError(
            {"Error": {"Code": "GoneException"}}
        )

        result = await self.publisher.publish_to_connection(
            connection_id="gone-conn",
            event={"type": "test"},
        )

        assert result is False
        # Should clean up the gone connection
        self.mock_table.delete_item.assert_called()

    @pytest.mark.asyncio
    async def test_publish_to_connection_other_error(self):
        """Test publishing with other error."""
        self.mock_api_client.post_to_connection.side_effect = MockClientError(
            {"Error": {"Code": "InternalServerError"}}
        )

        result = await self.publisher.publish_to_connection(
            connection_id="conn-123",
            event={"type": "test"},
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_all(self):
        """Test broadcasting to all connections."""
        self.mock_table.scan.return_value = {
            "Items": [
                {"connection_id": "conn-1"},
                {"connection_id": "conn-2"},
            ]
        }

        result = await self.publisher.broadcast_all(
            event={"type": "system", "message": "maintenance"},
        )

        assert result == 2
        assert self.mock_api_client.post_to_connection.call_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_all_error(self):
        """Test broadcast with scan error."""
        self.mock_table.scan.side_effect = MockClientError()

        result = await self.publisher.broadcast_all(
            event={"type": "test"},
        )

        assert result == 0


# =============================================================================
# RealtimeEventPublisher Connection Count Tests
# =============================================================================


class TestRealtimeEventPublisherConnectionCount:
    """Tests for connection counting."""

    def setup_method(self):
        """Set up test fixtures."""
        mock_boto3.resource.return_value = MagicMock()
        mock_boto3.client.return_value = MagicMock()

        self.publisher = RealtimeEventPublisher(
            connections_table_name="test-connections",
            api_gateway_endpoint="wss://test.example.com",
        )

        self.mock_table = MagicMock()
        self.publisher._connections_table = self.mock_table

    @pytest.mark.asyncio
    async def test_get_connection_count(self):
        """Test getting connection count."""
        self.mock_table.query.return_value = {
            "Items": [
                {"connection_id": "conn-1"},
                {"connection_id": "conn-2"},
                {"connection_id": "conn-3"},
            ]
        }

        count = await self.publisher.get_connection_count("exec-123")

        assert count == 3

    @pytest.mark.asyncio
    async def test_get_connection_count_empty(self):
        """Test getting connection count with no connections."""
        self.mock_table.query.return_value = {"Items": []}

        count = await self.publisher.get_connection_count("exec-123")

        assert count == 0

    @pytest.mark.asyncio
    async def test_get_all_connections(self):
        """Test getting all connection details."""
        self.mock_table.query.return_value = {
            "Items": [
                {
                    "connection_id": "conn-1",
                    "execution_id": "exec-123",
                    "user_id": "user-1",
                    "connected_at": "2025-01-01T00:00:00Z",
                },
                {
                    "connection_id": "conn-2",
                    "execution_id": "exec-123",
                    "user_id": "user-2",
                    "connected_at": "2025-01-01T00:01:00Z",
                },
            ]
        }

        connections = await self.publisher.get_all_connections("exec-123")

        assert len(connections) == 2
        assert all(isinstance(c, ConnectionInfo) for c in connections)
        assert connections[0].connection_id == "conn-1"
        assert connections[1].user_id == "user-2"


# =============================================================================
# LocalEventPublisher Tests
# =============================================================================


class TestLocalEventPublisher:
    """Tests for LocalEventPublisher (testing/development mode)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.publisher = LocalEventPublisher()

    @pytest.mark.asyncio
    async def test_register_connection(self):
        """Test registering connection."""
        await self.publisher.register_connection(
            connection_id="conn-123",
            execution_id="exec-456",
            user_id="user-789",
        )

        assert "exec-456" in self.publisher._connections
        assert "conn-123" in self.publisher._connections["exec-456"]
        assert "conn-123" in self.publisher._queues

    @pytest.mark.asyncio
    async def test_register_multiple_connections(self):
        """Test registering multiple connections to same execution."""
        await self.publisher.register_connection("conn-1", "exec-1", "user-1")
        await self.publisher.register_connection("conn-2", "exec-1", "user-2")
        await self.publisher.register_connection("conn-3", "exec-2", "user-3")

        assert len(self.publisher._connections["exec-1"]) == 2
        assert len(self.publisher._connections["exec-2"]) == 1

    @pytest.mark.asyncio
    async def test_unregister_connection(self):
        """Test unregistering connection."""
        await self.publisher.register_connection("conn-123", "exec-456", "user-789")
        await self.publisher.unregister_connection("conn-123")

        assert "conn-123" not in self.publisher._queues
        assert "conn-123" not in self.publisher._connections.get("exec-456", set())

    @pytest.mark.asyncio
    async def test_publish(self):
        """Test publishing event."""
        await self.publisher.register_connection("conn-1", "exec-1", "user-1")
        await self.publisher.register_connection("conn-2", "exec-1", "user-2")

        result = await self.publisher.publish(
            execution_id="exec-1",
            event={"type": "test", "data": "hello"},
        )

        assert result == 2

    @pytest.mark.asyncio
    async def test_publish_no_connections(self):
        """Test publishing with no connections."""
        result = await self.publisher.publish(
            execution_id="nonexistent",
            event={"type": "test"},
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_events(self):
        """Test getting events from queue."""
        await self.publisher.register_connection("conn-1", "exec-1", "user-1")

        await self.publisher.publish("exec-1", {"type": "event1"})
        await self.publisher.publish("exec-1", {"type": "event2"})

        events = await self.publisher.get_events("conn-1", timeout=0.1)

        assert len(events) == 2
        assert events[0]["type"] == "event1"
        assert events[1]["type"] == "event2"

    @pytest.mark.asyncio
    async def test_get_events_nonexistent_connection(self):
        """Test getting events from nonexistent connection."""
        events = await self.publisher.get_events("nonexistent", timeout=0.1)
        assert events == []

    @pytest.mark.asyncio
    async def test_get_events_empty_queue(self):
        """Test getting events from empty queue."""
        await self.publisher.register_connection("conn-1", "exec-1", "user-1")

        events = await self.publisher.get_events("conn-1", timeout=0.1)

        assert events == []

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow."""
        # Register connections
        await self.publisher.register_connection("conn-a", "exec-1", "user-1")
        await self.publisher.register_connection("conn-b", "exec-1", "user-2")

        # Publish events
        await self.publisher.publish("exec-1", {"step": 1, "status": "started"})
        await self.publisher.publish("exec-1", {"step": 2, "status": "processing"})

        # Get events from first connection
        events_a = await self.publisher.get_events("conn-a", timeout=0.1)
        assert len(events_a) == 2
        assert events_a[0]["step"] == 1

        # Get events from second connection
        events_b = await self.publisher.get_events("conn-b", timeout=0.1)
        assert len(events_b) == 2

        # Unregister one connection
        await self.publisher.unregister_connection("conn-a")

        # Publish more events
        await self.publisher.publish("exec-1", {"step": 3, "status": "completed"})

        # Only conn-b should receive
        events_b2 = await self.publisher.get_events("conn-b", timeout=0.1)
        assert len(events_b2) == 1
        assert events_b2[0]["step"] == 3

        # conn-a should get empty list (not in queues)
        events_a2 = await self.publisher.get_events("conn-a", timeout=0.1)
        assert events_a2 == []


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        mock_boto3.resource.return_value = MagicMock()
        mock_boto3.client.return_value = MagicMock()

        self.publisher = RealtimeEventPublisher(
            connections_table_name="test-connections",
            api_gateway_endpoint="wss://test.example.com",
        )

        self.mock_table = MagicMock()
        self.publisher._connections_table = self.mock_table

    @pytest.mark.asyncio
    async def test_get_execution_connections_error(self):
        """Test querying connections with error."""
        self.mock_table.query.side_effect = MockClientError()

        connections = await self.publisher._get_execution_connections("exec-123")

        assert connections == []

    @pytest.mark.asyncio
    async def test_local_publisher_init(self):
        """Test LocalEventPublisher initialization."""
        publisher = LocalEventPublisher()

        assert publisher._connections == {}
        assert publisher._queues == {}
