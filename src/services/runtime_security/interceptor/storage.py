"""
Project Aura - Traffic Storage Adapter

DynamoDB for traffic event metadata, S3 for full payload storage.
Supports both mock (testing) and real AWS backends.

Based on ADR-083: Runtime Agent Security Platform

Compliance:
- NIST 800-53 AU-4: Audit storage capacity
- NIST 800-53 AU-9: Protection of audit information
- NIST 800-53 AU-11: Audit record retention (90 days)
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from .protocol import TrafficBatch, TrafficEvent, TrafficFilter, TrafficSummary

logger = logging.getLogger(__name__)


class TrafficStorageAdapter:
    """
    Storage adapter for traffic events.

    Writes event metadata to DynamoDB and full payloads to S3.
    Uses mock storage by default for testing; real AWS clients
    are injected for production.
    """

    def __init__(
        self,
        dynamodb_table_name: str = "aura-traffic-events",
        s3_bucket_name: str = "aura-traffic-payloads",
        use_mock: bool = True,
        dynamodb_client: Optional[Any] = None,
        s3_client: Optional[Any] = None,
        batch_size: int = 25,
    ):
        self.dynamodb_table_name = dynamodb_table_name
        self.s3_bucket_name = s3_bucket_name
        self.use_mock = use_mock
        self.batch_size = batch_size
        self._dynamodb = dynamodb_client
        self._s3 = s3_client

        # Mock storage
        self._mock_events: dict[str, dict[str, Any]] = {}
        self._mock_payloads: dict[str, str] = {}
        self._write_count: int = 0
        self._read_count: int = 0

    async def store_event(
        self, event: TrafficEvent, payload: Optional[str] = None
    ) -> bool:
        """
        Store a single traffic event.

        Args:
            event: The traffic event metadata to store.
            payload: Optional full payload to store in S3.

        Returns:
            True if storage succeeded.
        """
        if self.use_mock:
            return self._mock_store_event(event, payload)

        return await self._aws_store_event(event, payload)

    async def store_batch(
        self, batch: TrafficBatch, payloads: Optional[dict[str, str]] = None
    ) -> int:
        """
        Store a batch of traffic events.

        Args:
            batch: Batch of traffic events.
            payloads: Optional map of event_id -> payload for S3 storage.

        Returns:
            Number of events successfully stored.
        """
        if self.use_mock:
            return self._mock_store_batch(batch, payloads)

        return await self._aws_store_batch(batch, payloads)

    async def query_events(self, filter_criteria: TrafficFilter) -> list[TrafficEvent]:
        """
        Query traffic events matching filter criteria.

        Args:
            filter_criteria: Filter to apply.

        Returns:
            List of matching traffic events.
        """
        if self.use_mock:
            return self._mock_query_events(filter_criteria)

        return await self._aws_query_events(filter_criteria)

    async def get_event(self, event_id: str) -> Optional[TrafficEvent]:
        """
        Get a single traffic event by ID.

        Args:
            event_id: The event ID to retrieve.

        Returns:
            The traffic event, or None if not found.
        """
        if self.use_mock:
            return self._mock_get_event(event_id)

        return await self._aws_get_event(event_id)

    async def get_payload(self, event_id: str) -> Optional[str]:
        """
        Get the full payload for a traffic event from S3.

        Args:
            event_id: The event ID whose payload to retrieve.

        Returns:
            The payload string, or None if not found.
        """
        if self.use_mock:
            return self._mock_payloads.get(event_id)

        return await self._aws_get_payload(event_id)

    async def compute_summary(self, filter_criteria: TrafficFilter) -> TrafficSummary:
        """
        Compute summary statistics for matching events.

        Args:
            filter_criteria: Filter to apply before computing summary.

        Returns:
            TrafficSummary with aggregated statistics.
        """
        events = await self.query_events(filter_criteria)
        return self._build_summary(events)

    async def delete_events_before(self, cutoff: datetime) -> int:
        """
        Delete events older than the cutoff date (for retention enforcement).

        Args:
            cutoff: Delete events with timestamp before this datetime.

        Returns:
            Number of events deleted.
        """
        if self.use_mock:
            return self._mock_delete_before(cutoff)

        return await self._aws_delete_before(cutoff)

    @property
    def event_count(self) -> int:
        """Total number of stored events."""
        return len(self._mock_events)

    @property
    def write_count(self) -> int:
        """Total number of write operations."""
        return self._write_count

    @property
    def read_count(self) -> int:
        """Total number of read operations."""
        return self._read_count

    # =========================================================================
    # Mock Storage Implementation
    # =========================================================================

    def _mock_store_event(
        self, event: TrafficEvent, payload: Optional[str] = None
    ) -> bool:
        """Store event in mock storage."""
        self._mock_events[event.event_id] = event.to_dict()
        if payload:
            self._mock_payloads[event.event_id] = payload
        self._write_count += 1
        return True

    def _mock_store_batch(
        self, batch: TrafficBatch, payloads: Optional[dict[str, str]] = None
    ) -> int:
        """Store batch in mock storage."""
        stored = 0
        for event in batch.events:
            payload = payloads.get(event.event_id) if payloads else None
            self._mock_events[event.event_id] = event.to_dict()
            if payload:
                self._mock_payloads[event.event_id] = payload
            stored += 1
            self._write_count += 1
        return stored

    def _mock_query_events(self, filter_criteria: TrafficFilter) -> list[TrafficEvent]:
        """Query events from mock storage."""
        self._read_count += 1
        results: list[TrafficEvent] = []

        for event_dict in self._mock_events.values():
            event = self._dict_to_event(event_dict)
            if filter_criteria.matches(event):
                results.append(event)
                if len(results) >= filter_criteria.max_results:
                    break

        return sorted(results, key=lambda e: e.timestamp, reverse=True)

    def _mock_get_event(self, event_id: str) -> Optional[TrafficEvent]:
        """Get event from mock storage."""
        self._read_count += 1
        event_dict = self._mock_events.get(event_id)
        if event_dict is None:
            return None
        return self._dict_to_event(event_dict)

    def _mock_delete_before(self, cutoff: datetime) -> int:
        """Delete events before cutoff from mock storage."""
        to_delete = []
        for event_id, event_dict in self._mock_events.items():
            ts = datetime.fromisoformat(event_dict["timestamp"])
            if ts < cutoff:
                to_delete.append(event_id)

        for event_id in to_delete:
            del self._mock_events[event_id]
            self._mock_payloads.pop(event_id, None)

        return len(to_delete)

    # =========================================================================
    # AWS Storage Implementation (production)
    # =========================================================================

    async def _aws_store_event(
        self, event: TrafficEvent, payload: Optional[str] = None
    ) -> bool:
        """Store event in DynamoDB + S3."""
        try:
            if self._dynamodb:
                self._dynamodb.put_item(
                    TableName=self.dynamodb_table_name,
                    Item=self._event_to_dynamodb_item(event),
                )

            if payload and self._s3:
                self._s3.put_object(
                    Bucket=self.s3_bucket_name,
                    Key=f"payloads/{event.event_id}.json",
                    Body=payload.encode("utf-8"),
                    ServerSideEncryption="aws:kms",
                )

            self._write_count += 1
            return True
        except Exception:
            logger.exception("Failed to store traffic event %s", event.event_id)
            return False

    async def _aws_store_batch(
        self, batch: TrafficBatch, payloads: Optional[dict[str, str]] = None
    ) -> int:
        """Store batch in DynamoDB + S3."""
        stored = 0
        for event in batch.events:
            payload = payloads.get(event.event_id) if payloads else None
            success = await self._aws_store_event(event, payload)
            if success:
                stored += 1
        return stored

    async def _aws_query_events(
        self, filter_criteria: TrafficFilter
    ) -> list[TrafficEvent]:
        """Query events from DynamoDB."""
        self._read_count += 1
        logger.info("AWS query not implemented for mock-first development")
        return []

    async def _aws_get_event(self, event_id: str) -> Optional[TrafficEvent]:
        """Get event from DynamoDB."""
        self._read_count += 1
        logger.info("AWS get not implemented for mock-first development")
        return None

    async def _aws_get_payload(self, event_id: str) -> Optional[str]:
        """Get payload from S3."""
        try:
            if self._s3:
                response = self._s3.get_object(
                    Bucket=self.s3_bucket_name,
                    Key=f"payloads/{event_id}.json",
                )
                return response["Body"].read().decode("utf-8")
        except Exception:
            logger.debug("Payload not found for event %s", event_id)
        return None

    async def _aws_delete_before(self, cutoff: datetime) -> int:
        """Delete events before cutoff from DynamoDB."""
        logger.info("AWS delete not implemented for mock-first development")
        return 0

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def _dict_to_event(d: dict[str, Any]) -> TrafficEvent:
        """Reconstruct a TrafficEvent from a dictionary."""
        from .protocol import InterceptionPoint, TrafficDirection, TrafficEventType

        return TrafficEvent(
            event_id=d["event_id"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            source_agent_id=d["source_agent_id"],
            target_agent_id=d.get("target_agent_id"),
            interception_point=InterceptionPoint(d["interception_point"]),
            direction=TrafficDirection(d["direction"]),
            event_type=TrafficEventType(d["event_type"]),
            payload_hash=d["payload_hash"],
            latency_ms=d["latency_ms"],
            tool_name=d.get("tool_name"),
            token_count=d.get("token_count"),
            approval_required=d.get("approval_required", False),
            approval_decision=d.get("approval_decision"),
            error_message=d.get("error_message"),
            session_id=d.get("session_id"),
            parent_event_id=d.get("parent_event_id"),
            metadata=tuple((k, v) for k, v in d.get("metadata", {}).items()),
        )

    @staticmethod
    def _event_to_dynamodb_item(event: TrafficEvent) -> dict[str, Any]:
        """Convert TrafficEvent to DynamoDB item format."""
        item: dict[str, Any] = {
            "event_id": {"S": event.event_id},
            "timestamp": {"S": event.timestamp.isoformat()},
            "source_agent_id": {"S": event.source_agent_id},
            "interception_point": {"S": event.interception_point.value},
            "direction": {"S": event.direction.value},
            "event_type": {"S": event.event_type.value},
            "payload_hash": {"S": event.payload_hash},
            "latency_ms": {"N": str(event.latency_ms)},
        }
        if event.target_agent_id:
            item["target_agent_id"] = {"S": event.target_agent_id}
        if event.tool_name:
            item["tool_name"] = {"S": event.tool_name}
        if event.token_count is not None:
            item["token_count"] = {"N": str(event.token_count)}
        if event.session_id:
            item["session_id"] = {"S": event.session_id}
        return item

    @staticmethod
    def _build_summary(events: list[TrafficEvent]) -> TrafficSummary:
        """Build summary statistics from a list of events."""
        if not events:
            return TrafficSummary(
                total_events=0,
                unique_agents=0,
                unique_tools=0,
                events_by_type=(),
                events_by_interception_point=(),
                avg_latency_ms=0.0,
                p95_latency_ms=0.0,
                total_tokens=0,
                error_count=0,
                error_rate=0.0,
            )

        agents: set[str] = set()
        tools: set[str] = set()
        type_counts: dict[str, int] = defaultdict(int)
        point_counts: dict[str, int] = defaultdict(int)
        latencies: list[float] = []
        total_tokens = 0
        error_count = 0

        for event in events:
            agents.add(event.source_agent_id)
            if event.target_agent_id:
                agents.add(event.target_agent_id)
            if event.tool_name:
                tools.add(event.tool_name)
            type_counts[event.event_type.value] += 1
            point_counts[event.interception_point.value] += 1
            latencies.append(event.latency_ms)
            if event.token_count:
                total_tokens += event.token_count
            if event.error_message:
                error_count += 1

        latencies.sort()
        p95_idx = int(len(latencies) * 0.95)
        p95_latency = latencies[min(p95_idx, len(latencies) - 1)]

        timestamps = [e.timestamp for e in events]

        return TrafficSummary(
            total_events=len(events),
            unique_agents=len(agents),
            unique_tools=len(tools),
            events_by_type=tuple(sorted(type_counts.items())),
            events_by_interception_point=tuple(sorted(point_counts.items())),
            avg_latency_ms=sum(latencies) / len(latencies),
            p95_latency_ms=p95_latency,
            total_tokens=total_tokens,
            error_count=error_count,
            error_rate=error_count / len(events) if events else 0.0,
            time_range_start=min(timestamps),
            time_range_end=max(timestamps),
        )


# Singleton instance
_storage_instance: Optional[TrafficStorageAdapter] = None


def get_traffic_storage() -> TrafficStorageAdapter:
    """Get singleton storage adapter instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = TrafficStorageAdapter()
    return _storage_instance


def reset_traffic_storage() -> None:
    """Reset storage singleton (for testing)."""
    global _storage_instance
    _storage_instance = None
