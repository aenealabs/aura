"""
Project Aura - Anomaly Persistence Service

DynamoDB persistence layer for anomaly events providing:
- Audit trail for compliance (CMMC, SOX, NIST 800-53)
- Historical analysis and pattern detection
- Deduplication window queries
- TTL-based retention management

Table Design:
- Primary Key: anomaly_id (partition key)
- Sort Key: timestamp#severity (for time-based queries within anomaly)
- GSI: status-created_at-index (query by status with time ordering)
- GSI: severity-created_at-index (query by severity with time ordering)
- GSI: dedup_key-index (deduplication window lookups)
- TTL: Configurable retention (default 90 days)

Integration:
- Subscribes to AnomalyDetectionService via on_anomaly callback
- Can be used standalone for historical queries
- Supports both synchronous and asynchronous operations
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class PersistenceMode(Enum):
    """Operating mode for the persistence service."""

    AWS = "aws"  # Real DynamoDB API calls
    MOCK = "mock"  # Local testing without AWS


@dataclass
class AnomalyRecord:
    """Anomaly record structure for DynamoDB."""

    anomaly_id: str
    timestamp: datetime
    severity: str
    status: str
    type: str
    title: str
    description: str
    source: str
    dedup_key: str
    affected_components: list[str] = field(default_factory=list)
    recommended_action: str | None = None
    cve_id: str | None = None
    orchestrator_task_id: str | None = None
    hitl_approval_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    ttl: int | None = None

    def to_dynamo_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        item: dict[str, Any] = {
            "anomaly_id": self.anomaly_id,
            "sort_key": f"{self.timestamp.isoformat()}#{self.severity}",
            "timestamp": self.timestamp.isoformat(),
            "created_at": self.timestamp.isoformat(),
            "severity": self.severity,
            "status": self.status,
            "type": self.type,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "dedup_key": self.dedup_key,
            "affected_components": self.affected_components,
        }

        # Add optional fields
        if self.recommended_action:
            item["recommended_action"] = self.recommended_action
        if self.cve_id:
            item["cve_id"] = self.cve_id
        if self.orchestrator_task_id:
            item["orchestrator_task_id"] = self.orchestrator_task_id
        if self.hitl_approval_id:
            item["hitl_approval_id"] = self.hitl_approval_id
        if self.metadata:
            item["metadata"] = self.metadata
        if self.resolved_at:
            item["resolved_at"] = self.resolved_at.isoformat()
        if self.resolved_by:
            item["resolved_by"] = self.resolved_by
        if self.ttl:
            item["ttl"] = self.ttl

        return item

    @classmethod
    def from_dynamo_item(cls, item: dict[str, Any]) -> "AnomalyRecord":
        """Create from DynamoDB item."""
        return cls(
            anomaly_id=item["anomaly_id"],
            timestamp=datetime.fromisoformat(item["timestamp"]),
            severity=item["severity"],
            status=item["status"],
            type=item["type"],
            title=item["title"],
            description=item["description"],
            source=item["source"],
            dedup_key=item["dedup_key"],
            affected_components=item.get("affected_components", []),
            recommended_action=item.get("recommended_action"),
            cve_id=item.get("cve_id"),
            orchestrator_task_id=item.get("orchestrator_task_id"),
            hitl_approval_id=item.get("hitl_approval_id"),
            metadata=item.get("metadata", {}),
            resolved_at=(
                datetime.fromisoformat(item["resolved_at"])
                if item.get("resolved_at")
                else None
            ),
            resolved_by=item.get("resolved_by"),
            ttl=item.get("ttl"),
        )


@dataclass
class QueryResult:
    """Result of a query operation."""

    items: list[AnomalyRecord]
    count: int
    last_evaluated_key: dict[str, Any] | None = None
    has_more: bool = False


@dataclass
class PersistenceStats:
    """Statistics for the persistence service."""

    items_written: int = 0
    items_read: int = 0
    items_updated: int = 0
    write_errors: int = 0
    read_errors: int = 0
    last_write_time: datetime | None = None
    last_read_time: datetime | None = None


# =============================================================================
# Anomaly Persistence Service
# =============================================================================


class AnomalyPersistenceService:
    """
    DynamoDB persistence layer for anomaly events.

    Provides:
    - CRUD operations for anomaly records
    - Query by status, severity, time range
    - Deduplication window lookups
    - TTL-based automatic cleanup

    Usage:
        persistence = AnomalyPersistenceService()

        # Store anomaly (as callback)
        detector.on_anomaly(persistence.persist_anomaly)

        # Query anomalies
        active = await persistence.query_by_status("active")
        critical = await persistence.query_by_severity("critical", hours=24)
        duplicates = await persistence.check_dedup_window("key", hours=1)
    """

    # Default table name
    DEFAULT_TABLE_NAME = "aura-anomalies"

    # Default TTL (90 days in seconds)
    DEFAULT_TTL_DAYS = 90

    def __init__(
        self,
        mode: PersistenceMode | None = None,
        region: str | None = None,
        table_name: str | None = None,
        ttl_days: int | None = None,
    ):
        """
        Initialize persistence service.

        Args:
            mode: Operating mode (AWS or MOCK). Auto-detected if not specified.
            region: AWS region. Uses AWS_REGION env var if not specified.
            table_name: DynamoDB table name. Defaults to 'aura-anomalies-{env}'.
            ttl_days: TTL in days for records. Defaults to 90.
        """
        self.mode = mode or self._detect_mode()
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        # Environment-aware table name
        env = os.environ.get("AURA_ENV", "dev")
        self.table_name = table_name or os.environ.get(
            "ANOMALY_TABLE_NAME", f"{self.DEFAULT_TABLE_NAME}-{env}"
        )

        self.ttl_days = ttl_days or int(
            os.environ.get("ANOMALY_TTL_DAYS", str(self.DEFAULT_TTL_DAYS))
        )

        # Statistics
        self.stats = PersistenceStats()

        # DynamoDB client (lazy initialization)
        self._client: Any = None
        self._table: Any = None

        # Mock storage for testing
        self._mock_items: dict[str, dict[str, Any]] = {}

        logger.info(
            f"AnomalyPersistenceService initialized: mode={self.mode.value}, "
            f"region={self.region}, table={self.table_name}, ttl={self.ttl_days} days"
        )

    def _detect_mode(self) -> PersistenceMode:
        """Auto-detect operating mode based on environment."""
        # Check for explicit mode setting
        mode_env = os.environ.get("ANOMALY_PERSISTENCE_MODE", "").lower()
        if mode_env == "mock":
            return PersistenceMode.MOCK
        if mode_env == "aws":
            return PersistenceMode.AWS

        # Check for AWS credentials indicators
        if any(
            [
                os.environ.get("AWS_EXECUTION_ENV"),  # Lambda/ECS
                os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"),  # ECS/EKS
                os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE"),  # IRSA
            ]
        ):
            return PersistenceMode.AWS

        # Default to mock for local development
        return PersistenceMode.MOCK

    @property
    def client(self):
        """Lazy-initialize DynamoDB client."""
        if self._client is None:
            if self.mode == PersistenceMode.AWS:
                self._client = boto3.client("dynamodb", region_name=self.region)
            else:
                self._client = None
        return self._client

    @property
    def table(self):
        """Lazy-initialize DynamoDB table resource."""
        if self._table is None:
            if self.mode == PersistenceMode.AWS:
                dynamodb = boto3.resource("dynamodb", region_name=self.region)
                self._table = dynamodb.Table(self.table_name)
            else:
                self._table = None
        return self._table

    def _calculate_ttl(self) -> int:
        """Calculate TTL epoch timestamp."""
        expiry = datetime.now(timezone.utc) + timedelta(days=self.ttl_days)
        return int(expiry.timestamp())

    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------

    async def persist_anomaly(self, anomaly: Any) -> bool:
        """
        Persist an anomaly event to DynamoDB.

        This method is designed to be used as a callback for AnomalyDetectionService:
            detector.on_anomaly(persistence.persist_anomaly)

        Args:
            anomaly: AnomalyEvent from AnomalyDetectionService

        Returns:
            True if anomaly was persisted successfully
        """
        # Import here to avoid circular imports
        from src.services.anomaly_detection_service import AnomalyEvent

        if not isinstance(anomaly, AnomalyEvent):
            logger.warning(f"Invalid anomaly type: {type(anomaly)}")
            return False

        record = AnomalyRecord(
            anomaly_id=anomaly.id,
            timestamp=anomaly.timestamp,
            severity=anomaly.severity.value,
            status=anomaly.status.value,
            type=anomaly.type.value,
            title=anomaly.title,
            description=anomaly.description,
            source=anomaly.source,
            dedup_key=anomaly.dedup_key or "",
            affected_components=anomaly.affected_components,
            recommended_action=anomaly.recommended_action,
            cve_id=anomaly.cve_id,
            orchestrator_task_id=anomaly.orchestrator_task_id,
            hitl_approval_id=anomaly.hitl_approval_id,
            metadata=anomaly.metadata,
            ttl=self._calculate_ttl(),
        )

        return await self.put_item(record)

    async def put_item(self, record: AnomalyRecord) -> bool:
        """
        Put an anomaly record into DynamoDB.

        Args:
            record: AnomalyRecord to persist

        Returns:
            True if successful
        """
        if self.mode == PersistenceMode.MOCK:
            return self._mock_put_item(record)

        try:
            item = record.to_dynamo_item()

            # Convert floats to Decimal for DynamoDB
            item = self._convert_to_dynamo_types(item)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self.table.put_item(Item=item))

            self.stats.items_written += 1
            self.stats.last_write_time = datetime.now(timezone.utc)

            logger.debug(f"Persisted anomaly: {record.anomaly_id}")
            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"DynamoDB put_item failed ({error_code}): {e}")
            self.stats.write_errors += 1
            return False

    async def update_status(
        self,
        anomaly_id: str,
        new_status: str,
        resolved_by: str | None = None,
    ) -> bool:
        """
        Update anomaly status.

        Args:
            anomaly_id: ID of the anomaly
            new_status: New status value
            resolved_by: Who resolved it (if applicable)

        Returns:
            True if successful
        """
        if self.mode == PersistenceMode.MOCK:
            return self._mock_update_status(anomaly_id, new_status, resolved_by)

        try:
            update_expr = "SET #status = :status, updated_at = :updated_at"
            expr_names = {"#status": "status"}
            expr_values = {
                ":status": new_status,
                ":updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if new_status == "resolved" and resolved_by:
                update_expr += (
                    ", resolved_at = :resolved_at, resolved_by = :resolved_by"
                )
                expr_values[":resolved_at"] = datetime.now(timezone.utc).isoformat()
                expr_values[":resolved_by"] = resolved_by

            # First, get the sort key for this anomaly
            response = await self._query_by_anomaly_id(anomaly_id)
            if not response["items"]:
                logger.warning(f"Anomaly not found for update: {anomaly_id}")
                return False

            sort_key = response["items"][0]["sort_key"]

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.table.update_item(
                    Key={"anomaly_id": anomaly_id, "sort_key": sort_key},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames=expr_names,
                    ExpressionAttributeValues=expr_values,
                ),
            )

            self.stats.items_updated += 1
            logger.debug(f"Updated anomaly status: {anomaly_id} -> {new_status}")
            return True

        except ClientError as e:
            logger.error(f"DynamoDB update_item failed: {e}")
            self.stats.write_errors += 1
            return False

    async def link_orchestrator_task(
        self,
        anomaly_id: str,
        task_id: str,
    ) -> bool:
        """
        Link an orchestrator task to an anomaly.

        Args:
            anomaly_id: ID of the anomaly
            task_id: MetaOrchestrator task ID

        Returns:
            True if successful
        """
        if self.mode == PersistenceMode.MOCK:
            if anomaly_id in self._mock_items:
                self._mock_items[anomaly_id]["orchestrator_task_id"] = task_id
                return True
            return False

        try:
            # Get the sort key for this anomaly
            response = await self._query_by_anomaly_id(anomaly_id)
            if not response["items"]:
                return False

            sort_key = response["items"][0]["sort_key"]

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.table.update_item(
                    Key={"anomaly_id": anomaly_id, "sort_key": sort_key},
                    UpdateExpression="SET orchestrator_task_id = :task_id",
                    ExpressionAttributeValues={":task_id": task_id},
                ),
            )

            self.stats.items_updated += 1
            return True

        except ClientError as e:
            logger.error(f"DynamoDB update_item failed: {e}")
            return False

    async def link_hitl_approval(
        self,
        anomaly_id: str,
        approval_id: str,
    ) -> bool:
        """
        Link a HITL approval to an anomaly.

        Args:
            anomaly_id: ID of the anomaly
            approval_id: HITL approval ID

        Returns:
            True if successful
        """
        if self.mode == PersistenceMode.MOCK:
            if anomaly_id in self._mock_items:
                self._mock_items[anomaly_id]["hitl_approval_id"] = approval_id
                return True
            return False

        try:
            # Get the sort key for this anomaly
            response = await self._query_by_anomaly_id(anomaly_id)
            if not response["items"]:
                return False

            sort_key = response["items"][0]["sort_key"]

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.table.update_item(
                    Key={"anomaly_id": anomaly_id, "sort_key": sort_key},
                    UpdateExpression="SET hitl_approval_id = :approval_id",
                    ExpressionAttributeValues={":approval_id": approval_id},
                ),
            )

            self.stats.items_updated += 1
            return True

        except ClientError as e:
            logger.error(f"DynamoDB update_item failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------

    async def get_anomaly(self, anomaly_id: str) -> AnomalyRecord | None:
        """
        Get an anomaly by ID.

        Args:
            anomaly_id: ID of the anomaly

        Returns:
            AnomalyRecord if found, None otherwise
        """
        if self.mode == PersistenceMode.MOCK:
            item = self._mock_items.get(anomaly_id)
            if item:
                self.stats.items_read += 1
                return AnomalyRecord.from_dynamo_item(item)
            return None

        try:
            response = await self._query_by_anomaly_id(anomaly_id)
            if response["items"]:
                self.stats.items_read += 1
                self.stats.last_read_time = datetime.now(timezone.utc)
                return AnomalyRecord.from_dynamo_item(response["items"][0])
            return None

        except ClientError as e:
            logger.error(f"DynamoDB query failed: {e}")
            self.stats.read_errors += 1
            return None

    async def query_by_status(
        self,
        status: str,
        limit: int = 100,
        start_key: dict[str, Any] | None = None,
    ) -> QueryResult:
        """
        Query anomalies by status.

        Args:
            status: Status to filter by (e.g., "active", "investigating", "resolved")
            limit: Maximum items to return
            start_key: Pagination key from previous query

        Returns:
            QueryResult with matching anomalies
        """
        if self.mode == PersistenceMode.MOCK:
            return self._mock_query_by_status(status, limit)

        try:
            query_params = {
                "IndexName": "status-created_at-index",
                "KeyConditionExpression": "#status = :status",
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {":status": status},
                "Limit": limit,
                "ScanIndexForward": False,  # Most recent first
            }

            if start_key:
                query_params["ExclusiveStartKey"] = start_key

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.table.query(**query_params)
            )

            items = [AnomalyRecord.from_dynamo_item(item) for item in response["Items"]]
            self.stats.items_read += len(items)
            self.stats.last_read_time = datetime.now(timezone.utc)

            return QueryResult(
                items=items,
                count=len(items),
                last_evaluated_key=response.get("LastEvaluatedKey"),
                has_more="LastEvaluatedKey" in response,
            )

        except ClientError as e:
            logger.error(f"DynamoDB query failed: {e}")
            self.stats.read_errors += 1
            return QueryResult(items=[], count=0)

    async def query_by_severity(
        self,
        severity: str,
        hours: int = 24,
        limit: int = 100,
    ) -> QueryResult:
        """
        Query anomalies by severity within a time window.

        Args:
            severity: Severity to filter by (e.g., "critical", "high", "medium", "low")
            hours: Look back window in hours
            limit: Maximum items to return

        Returns:
            QueryResult with matching anomalies
        """
        if self.mode == PersistenceMode.MOCK:
            return self._mock_query_by_severity(severity, hours, limit)

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

            query_params = {
                "IndexName": "severity-created_at-index",
                "KeyConditionExpression": "#severity = :severity AND created_at >= :cutoff",
                "ExpressionAttributeNames": {"#severity": "severity"},
                "ExpressionAttributeValues": {
                    ":severity": severity,
                    ":cutoff": cutoff.isoformat(),
                },
                "Limit": limit,
                "ScanIndexForward": False,  # Most recent first
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.table.query(**query_params)
            )

            items = [AnomalyRecord.from_dynamo_item(item) for item in response["Items"]]
            self.stats.items_read += len(items)
            self.stats.last_read_time = datetime.now(timezone.utc)

            return QueryResult(
                items=items,
                count=len(items),
                last_evaluated_key=response.get("LastEvaluatedKey"),
                has_more="LastEvaluatedKey" in response,
            )

        except ClientError as e:
            logger.error(f"DynamoDB query failed: {e}")
            self.stats.read_errors += 1
            return QueryResult(items=[], count=0)

    async def check_dedup_window(
        self,
        dedup_key: str,
        hours: int = 1,
    ) -> list[AnomalyRecord]:
        """
        Check for duplicate anomalies within a time window.

        Used by AnomalyDetectionService to prevent duplicate alerts.

        Args:
            dedup_key: Deduplication key to search for
            hours: Look back window in hours

        Returns:
            List of matching anomalies within the window
        """
        if self.mode == PersistenceMode.MOCK:
            return self._mock_check_dedup_window(dedup_key, hours)

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

            query_params = {
                "IndexName": "dedup_key-index",
                "KeyConditionExpression": "dedup_key = :dedup_key",
                "FilterExpression": "created_at >= :cutoff",
                "ExpressionAttributeValues": {
                    ":dedup_key": dedup_key,
                    ":cutoff": cutoff.isoformat(),
                },
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.table.query(**query_params)
            )

            items = [AnomalyRecord.from_dynamo_item(item) for item in response["Items"]]
            self.stats.items_read += len(items)

            return items

        except ClientError as e:
            logger.error(f"DynamoDB query failed: {e}")
            self.stats.read_errors += 1
            return []

    async def query_recent(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> QueryResult:
        """
        Query most recent anomalies across all types.

        Args:
            hours: Look back window in hours
            limit: Maximum items to return

        Returns:
            QueryResult with recent anomalies
        """
        if self.mode == PersistenceMode.MOCK:
            return self._mock_query_recent(hours, limit)

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

            # Use scan with filter for cross-partition query
            scan_params = {
                "FilterExpression": "created_at >= :cutoff",
                "ExpressionAttributeValues": {":cutoff": cutoff.isoformat()},
                "Limit": limit,
            }

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self.table.scan(**scan_params)
            )

            items = [AnomalyRecord.from_dynamo_item(item) for item in response["Items"]]
            # Sort by timestamp descending
            items.sort(key=lambda x: x.timestamp, reverse=True)
            self.stats.items_read += len(items)
            self.stats.last_read_time = datetime.now(timezone.utc)

            return QueryResult(
                items=items[:limit],
                count=len(items[:limit]),
                last_evaluated_key=response.get("LastEvaluatedKey"),
                has_more="LastEvaluatedKey" in response,
            )

        except ClientError as e:
            logger.error(f"DynamoDB scan failed: {e}")
            self.stats.read_errors += 1
            return QueryResult(items=[], count=0)

    async def get_anomaly_summary(self, hours: int = 24) -> dict[str, Any]:
        """
        Get summary statistics for anomalies.

        Args:
            hours: Look back window in hours

        Returns:
            Summary with counts by status and severity
        """
        result = await self.query_recent(hours=hours, limit=1000)

        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}

        summary: dict[str, Any] = {
            "total": result.count,
            "time_window_hours": hours,
            "by_status": by_status,
            "by_severity": by_severity,
            "by_type": by_type,
        }

        for item in result.items:
            # Count by status
            by_status[item.status] = by_status.get(item.status, 0) + 1
            # Count by severity
            by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
            # Count by type
            by_type[item.type] = by_type.get(item.type, 0) + 1

        return summary

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def _query_by_anomaly_id(self, anomaly_id: str) -> dict[str, Any]:
        """Query all records for an anomaly ID."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.table.query(
                KeyConditionExpression="anomaly_id = :id",
                ExpressionAttributeValues={":id": anomaly_id},
            ),
        )
        return {"items": response.get("Items", [])}

    def _convert_to_dynamo_types(self, item: dict[str, Any]) -> dict[str, Any]:
        """Convert Python types to DynamoDB-compatible types."""
        converted: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, float):
                converted[key] = Decimal(str(value))
            elif isinstance(value, dict):
                converted[key] = self._convert_to_dynamo_types(value)
            elif isinstance(value, list):
                converted[key] = [
                    self._convert_to_dynamo_types(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                converted[key] = value
        return converted

    # -------------------------------------------------------------------------
    # Mock Operations
    # -------------------------------------------------------------------------

    def _mock_put_item(self, record: AnomalyRecord) -> bool:
        """Mock put item for testing."""
        item = record.to_dynamo_item()
        self._mock_items[record.anomaly_id] = item
        self.stats.items_written += 1
        self.stats.last_write_time = datetime.now(timezone.utc)
        logger.debug(f"[MOCK] Persisted anomaly: {record.anomaly_id}")
        return True

    def _mock_update_status(
        self, anomaly_id: str, new_status: str, resolved_by: str | None
    ) -> bool:
        """Mock update status for testing."""
        if anomaly_id in self._mock_items:
            self._mock_items[anomaly_id]["status"] = new_status
            self._mock_items[anomaly_id]["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            if new_status == "resolved" and resolved_by:
                self._mock_items[anomaly_id]["resolved_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                self._mock_items[anomaly_id]["resolved_by"] = resolved_by
            self.stats.items_updated += 1
            return True
        return False

    def _mock_query_by_status(self, status: str, limit: int) -> QueryResult:
        """Mock query by status for testing."""
        items = [
            AnomalyRecord.from_dynamo_item(item)
            for item in self._mock_items.values()
            if item.get("status") == status
        ]
        items.sort(key=lambda x: x.timestamp, reverse=True)
        self.stats.items_read += len(items[:limit])
        return QueryResult(items=items[:limit], count=len(items[:limit]))

    def _mock_query_by_severity(
        self, severity: str, hours: int, limit: int
    ) -> QueryResult:
        """Mock query by severity for testing."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        items = [
            AnomalyRecord.from_dynamo_item(item)
            for item in self._mock_items.values()
            if item.get("severity") == severity
            and datetime.fromisoformat(item["timestamp"]) >= cutoff
        ]
        items.sort(key=lambda x: x.timestamp, reverse=True)
        self.stats.items_read += len(items[:limit])
        return QueryResult(items=items[:limit], count=len(items[:limit]))

    def _mock_check_dedup_window(
        self, dedup_key: str, hours: int
    ) -> list[AnomalyRecord]:
        """Mock dedup window check for testing."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        items = [
            AnomalyRecord.from_dynamo_item(item)
            for item in self._mock_items.values()
            if item.get("dedup_key") == dedup_key
            and datetime.fromisoformat(item["timestamp"]) >= cutoff
        ]
        self.stats.items_read += len(items)
        return items

    def _mock_query_recent(self, hours: int, limit: int) -> QueryResult:
        """Mock query recent for testing."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        items = [
            AnomalyRecord.from_dynamo_item(item)
            for item in self._mock_items.values()
            if datetime.fromisoformat(item["timestamp"]) >= cutoff
        ]
        items.sort(key=lambda x: x.timestamp, reverse=True)
        self.stats.items_read += len(items[:limit])
        return QueryResult(items=items[:limit], count=len(items[:limit]))

    # -------------------------------------------------------------------------
    # Statistics & Testing
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get persistence statistics."""
        return {
            "mode": self.mode.value,
            "region": self.region,
            "table": self.table_name,
            "ttl_days": self.ttl_days,
            "items_written": self.stats.items_written,
            "items_read": self.stats.items_read,
            "items_updated": self.stats.items_updated,
            "write_errors": self.stats.write_errors,
            "read_errors": self.stats.read_errors,
            "last_write_time": (
                self.stats.last_write_time.isoformat()
                if self.stats.last_write_time
                else None
            ),
            "last_read_time": (
                self.stats.last_read_time.isoformat()
                if self.stats.last_read_time
                else None
            ),
        }

    def get_mock_items(self) -> dict[str, dict[str, Any]]:
        """Get mock items (for testing)."""
        return self._mock_items.copy()

    def clear_mock_items(self) -> None:
        """Clear mock items (for testing)."""
        self._mock_items.clear()


# =============================================================================
# Factory Functions
# =============================================================================


_persistence_instance: AnomalyPersistenceService | None = None


def get_anomaly_persistence_service() -> AnomalyPersistenceService:
    """
    Get singleton anomaly persistence service instance.

    Returns:
        AnomalyPersistenceService instance
    """
    global _persistence_instance
    if _persistence_instance is None:
        _persistence_instance = AnomalyPersistenceService()
    return _persistence_instance


def create_anomaly_persistence_service(
    mode: PersistenceMode | None = None,
    region: str | None = None,
    table_name: str | None = None,
    ttl_days: int | None = None,
) -> AnomalyPersistenceService:
    """
    Create a new anomaly persistence service instance.

    Args:
        mode: Operating mode (AWS or MOCK)
        region: AWS region
        table_name: DynamoDB table name
        ttl_days: TTL in days for records

    Returns:
        New AnomalyPersistenceService instance
    """
    return AnomalyPersistenceService(
        mode=mode,
        region=region,
        table_name=table_name,
        ttl_days=ttl_days,
    )
