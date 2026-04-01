"""
Real-Time Event Publisher for WebSocket Streaming.

Manages WebSocket connections and broadcasts execution events
to connected clients for real-time agent intervention (ADR-042).
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set, cast

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """WebSocket connection metadata."""

    connection_id: str
    execution_id: str
    user_id: str
    connected_at: str
    endpoint_url: str


class RealtimeEventPublisher:
    """
    Publishes real-time events to WebSocket connections.

    Manages connection registry and broadcasts checkpoint events
    to all clients subscribed to an execution.
    """

    def __init__(
        self,
        connections_table_name: str,
        api_gateway_endpoint: str,
        region: str = "us-east-1",
    ):
        """
        Initialize event publisher.

        Args:
            connections_table_name: DynamoDB table for connection registry
            api_gateway_endpoint: WebSocket API Gateway endpoint URL
            region: AWS region
        """
        self.connections_table_name = connections_table_name
        self.endpoint_url = api_gateway_endpoint
        self.region = region

        self._dynamodb = boto3.resource("dynamodb", region_name=region)
        self._connections_table = self._dynamodb.Table(connections_table_name)

        # API Gateway Management client for sending messages
        # Endpoint format: https://{api-id}.execute-api.{region}.amazonaws.com/{stage}
        management_endpoint = api_gateway_endpoint.replace("wss://", "https://")
        self._api_client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=management_endpoint,
            region_name=region,
        )

        logger.info(
            f"RealtimeEventPublisher initialized with endpoint {api_gateway_endpoint}"
        )

    async def register_connection(
        self,
        connection_id: str,
        execution_id: str,
        user_id: str,
    ) -> None:
        """
        Register a new WebSocket connection.

        Args:
            connection_id: API Gateway connection ID
            execution_id: Execution to subscribe to
            user_id: User establishing connection
        """
        item: Dict[str, Any] = {
            "connection_id": connection_id,
            "execution_id": execution_id,
            "user_id": user_id,
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "ttl": int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()),
        }

        try:
            self._connections_table.put_item(Item=item)
            logger.info(
                f"Registered connection {connection_id} for execution {execution_id}"
            )
        except ClientError as e:
            logger.error(f"Error registering connection: {e}")
            raise

    async def unregister_connection(self, connection_id: str) -> None:
        """
        Remove a WebSocket connection from registry.

        Args:
            connection_id: Connection to remove
        """
        try:
            self._connections_table.delete_item(Key={"connection_id": connection_id})
            logger.info(f"Unregistered connection {connection_id}")
        except ClientError as e:
            logger.error(f"Error unregistering connection: {e}")

    async def publish(
        self,
        execution_id: str,
        event: Dict[str, Any],
    ) -> int:
        """
        Publish event to all connections subscribed to an execution.

        Args:
            execution_id: Target execution ID
            event: Event payload to broadcast

        Returns:
            Number of connections that received the message
        """
        connections = await self._get_execution_connections(execution_id)

        if not connections:
            logger.debug(f"No connections for execution {execution_id}")
            return 0

        message = json.dumps(event, default=str)
        successful = 0
        stale_connections = []

        for conn in connections:
            try:
                self._api_client.post_to_connection(
                    ConnectionId=conn["connection_id"],
                    Data=message.encode("utf-8"),
                )
                successful += 1
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "GoneException":
                    # Connection is stale, mark for cleanup
                    stale_connections.append(conn["connection_id"])
                else:
                    logger.error(f"Error sending to {conn['connection_id']}: {e}")

        # Cleanup stale connections
        for conn_id in stale_connections:
            await self.unregister_connection(conn_id)

        logger.debug(
            f"Published event to {successful}/{len(connections)} connections "
            f"for execution {execution_id}"
        )

        return successful

    async def publish_to_connection(
        self,
        connection_id: str,
        event: Dict[str, Any],
    ) -> bool:
        """
        Publish event to a specific connection.

        Args:
            connection_id: Target connection
            event: Event payload

        Returns:
            True if successful, False otherwise
        """
        message = json.dumps(event, default=str)

        try:
            self._api_client.post_to_connection(
                ConnectionId=connection_id,
                Data=message.encode("utf-8"),
            )
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "GoneException":
                await self.unregister_connection(connection_id)
            else:
                logger.error(f"Error sending to {connection_id}: {e}")
            return False

    async def broadcast_all(
        self,
        event: Dict[str, Any],
    ) -> int:
        """
        Broadcast event to all active connections.

        Args:
            event: Event payload to broadcast

        Returns:
            Number of connections that received the message
        """
        # Scan all connections (use with caution for large connection counts)
        try:
            response = self._connections_table.scan()
            connections = response.get("Items", [])

            message = json.dumps(event, default=str)
            successful = 0
            stale_connections = []

            for conn in connections:
                try:
                    self._api_client.post_to_connection(
                        ConnectionId=conn["connection_id"],
                        Data=message.encode("utf-8"),
                    )
                    successful += 1
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "")
                    if error_code == "GoneException":
                        stale_connections.append(conn["connection_id"])

            for conn_id in stale_connections:
                await self.unregister_connection(cast(str, conn_id))

            return successful

        except ClientError as e:
            logger.error(f"Error broadcasting: {e}")
            return 0

    async def get_connection_count(self, execution_id: str) -> int:
        """
        Get count of active connections for an execution.

        Args:
            execution_id: Execution to query

        Returns:
            Number of active connections
        """
        connections = await self._get_execution_connections(execution_id)
        return len(connections)

    async def get_all_connections(self, execution_id: str) -> List[ConnectionInfo]:
        """
        Get all connection details for an execution.

        Args:
            execution_id: Execution to query

        Returns:
            List of ConnectionInfo objects
        """
        items = await self._get_execution_connections(execution_id)
        return [
            ConnectionInfo(
                connection_id=item["connection_id"],
                execution_id=item["execution_id"],
                user_id=item["user_id"],
                connected_at=item["connected_at"],
                endpoint_url=self.endpoint_url,
            )
            for item in items
        ]

    async def _get_execution_connections(
        self,
        execution_id: str,
    ) -> List[Dict[str, Any]]:
        """Query connections for an execution."""
        try:
            response = self._connections_table.query(
                IndexName="execution-index",
                KeyConditionExpression="execution_id = :eid",
                ExpressionAttributeValues={":eid": execution_id},
            )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Error querying connections: {e}")
            return []


class LocalEventPublisher:
    """
    Local event publisher for testing and development.

    Uses in-memory queues instead of WebSocket/DynamoDB.
    """

    def __init__(self) -> None:
        """Initialize local publisher."""
        self._connections: Dict[str, Set[str]] = {}  # execution_id -> connection_ids
        self._queues: Dict[str, asyncio.Queue] = {}  # connection_id -> event queue

    async def register_connection(
        self,
        connection_id: str,
        execution_id: str,
        user_id: str,
    ) -> None:
        """Register a connection."""
        if execution_id not in self._connections:
            self._connections[execution_id] = set()
        self._connections[execution_id].add(connection_id)
        self._queues[connection_id] = asyncio.Queue()

    async def unregister_connection(self, connection_id: str) -> None:
        """Unregister a connection."""
        self._queues.pop(connection_id, None)
        for conn_set in self._connections.values():
            conn_set.discard(connection_id)

    async def publish(
        self,
        execution_id: str,
        event: Dict[str, Any],
    ) -> int:
        """Publish event to execution subscribers."""
        connections = self._connections.get(execution_id, set())
        for conn_id in connections:
            if conn_id in self._queues:
                await self._queues[conn_id].put(event)
        return len(connections)

    async def get_events(
        self,
        connection_id: str,
        timeout: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Get pending events for a connection."""
        if connection_id not in self._queues:
            return []

        queue = self._queues[connection_id]
        events = []

        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
                events.append(event)
        except asyncio.TimeoutError:
            pass

        return events
