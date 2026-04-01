"""
Project Aura - Quarantine Manager

Manages quarantined content that failed verification.
Isolates suspicious content, creates review tickets,
and handles HITL review workflow.

Security Rationale:
- Quarantine prevents suspicious content from reaching LLM
- HITL review enables human judgment for edge cases
- Audit trail maintains compliance
- SNS alerts enable rapid incident response

Author: Project Aura Team
Created: 2026-01-25
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .contracts import ProvenanceRecord, QuarantineReason, QuarantineRecord

logger = logging.getLogger(__name__)


class QuarantineManager:
    """
    Manages quarantined content that failed verification.

    Quarantined content is:
    - Removed from active retrieval pool
    - Stored in separate quarantine table
    - Flagged for HITL review
    - Logged to audit trail

    Usage:
        manager = QuarantineManager(dynamodb_client, sns_client)
        record = await manager.quarantine(
            chunk_id="abc123",
            content="suspicious code",
            reason=QuarantineReason.INTEGRITY_FAILURE,
            details="Hash mismatch detected",
            provenance=provenance_record,
        )
    """

    def __init__(
        self,
        dynamodb_client: Optional[Any] = None,
        neptune_client: Optional[Any] = None,
        opensearch_client: Optional[Any] = None,
        sns_client: Optional[Any] = None,
        table_name: str = "aura-context-quarantine",
        alert_topic_arn: Optional[str] = None,
        environment: str = "dev",
    ):
        """
        Initialize quarantine manager.

        Args:
            dynamodb_client: DynamoDB client
            neptune_client: Neptune client for graph updates
            opensearch_client: OpenSearch client for index updates
            sns_client: SNS client for alerts
            table_name: DynamoDB table for quarantine records
            alert_topic_arn: SNS topic for quarantine alerts
            environment: Environment name
        """
        self.dynamodb = dynamodb_client
        self.neptune = neptune_client
        self.opensearch = opensearch_client
        self.sns = sns_client
        self.table_name = f"{table_name}-{environment}"
        self.alert_topic = alert_topic_arn
        self.environment = environment

        # In-memory quarantine for testing/non-persistent mode
        self._in_memory_quarantine: dict[str, QuarantineRecord] = {}

        logger.debug(f"QuarantineManager initialized (table={self.table_name})")

    async def quarantine(
        self,
        chunk_id: str,
        content: str,
        reason: QuarantineReason,
        details: str,
        provenance: ProvenanceRecord,
        quarantined_by: str = "system",
    ) -> QuarantineRecord:
        """
        Quarantine a content chunk.

        Args:
            chunk_id: Unique chunk identifier
            content: Content being quarantined
            reason: Reason for quarantine
            details: Detailed explanation
            provenance: Content provenance
            quarantined_by: Who initiated the quarantine

        Returns:
            QuarantineRecord
        """
        record = QuarantineRecord(
            chunk_id=chunk_id,
            content_hash=self._compute_hash(content),
            reason=reason,
            details=details,
            quarantined_at=datetime.now(timezone.utc),
            quarantined_by=quarantined_by,
            provenance=provenance,
        )

        # Store in quarantine table
        await self._store_quarantine_record(record)

        # Update Neptune vertex status
        if self.neptune:
            await self._update_neptune_status(chunk_id, "QUARANTINED")

        # Update OpenSearch document status
        if self.opensearch:
            await self._update_opensearch_status(chunk_id, "QUARANTINED")

        # Send alert
        if self.alert_topic and self.sns:
            await self._send_alert(record)

        logger.warning(f"Quarantined chunk {chunk_id}: {reason.value} - {details}")

        return record

    async def review(
        self,
        chunk_id: str,
        reviewer_id: str,
        decision: str,  # "release" | "delete"
        notes: Optional[str] = None,
    ) -> bool:
        """
        Review quarantined content.

        Args:
            chunk_id: Quarantined chunk ID
            reviewer_id: Reviewer user ID
            decision: Review decision ("release" or "delete")
            notes: Optional review notes

        Returns:
            True if review processed successfully
        """
        if decision not in ("release", "delete"):
            raise ValueError(f"Invalid decision: {decision}")

        if decision == "release":
            # Restore to active status
            if self.neptune:
                await self._update_neptune_status(chunk_id, "ACTIVE")
            if self.opensearch:
                await self._update_opensearch_status(chunk_id, "ACTIVE")
            review_status = "released"
        else:
            # Mark for deletion
            if self.neptune:
                await self._delete_from_neptune(chunk_id)
            if self.opensearch:
                await self._delete_from_opensearch(chunk_id)
            review_status = "deleted"

        # Update quarantine record
        await self._update_quarantine_record(
            chunk_id,
            review_status=review_status,
            reviewed_by=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
            notes=notes,
        )

        logger.info(
            f"Quarantine review complete for {chunk_id}: {decision} by {reviewer_id}"
        )

        return True

    async def get_pending_reviews(
        self,
        limit: int = 50,
    ) -> list[QuarantineRecord]:
        """Get quarantine records pending review."""
        if self.dynamodb:
            try:
                response = self.dynamodb.query(
                    TableName=self.table_name,
                    IndexName="review-status-index",
                    KeyConditionExpression="review_status = :status",
                    ExpressionAttributeValues={":status": {"S": "pending"}},
                    Limit=limit,
                )

                records = []
                for item in response.get("Items", []):
                    records.append(self._item_to_record(item))

                return records
            except Exception as e:
                logger.error(f"Failed to query pending reviews: {e}")
                return []

        # Fall back to in-memory store
        return [
            r
            for r in self._in_memory_quarantine.values()
            if r.review_status == "pending"
        ][:limit]

    async def get_quarantine_record(
        self,
        chunk_id: str,
    ) -> Optional[QuarantineRecord]:
        """Get a specific quarantine record."""
        if self.dynamodb:
            try:
                response = self.dynamodb.query(
                    TableName=self.table_name,
                    KeyConditionExpression="chunk_id = :chunk_id",
                    ExpressionAttributeValues={":chunk_id": {"S": chunk_id}},
                    Limit=1,
                    ScanIndexForward=False,  # Most recent first
                )

                items = response.get("Items", [])
                if items:
                    return self._item_to_record(items[0])
                return None
            except Exception as e:
                logger.error(f"Failed to get quarantine record: {e}")
                return None

        # Fall back to in-memory store
        return self._in_memory_quarantine.get(chunk_id)

    async def is_quarantined(self, chunk_id: str) -> bool:
        """Check if a chunk is currently quarantined."""
        record = await self.get_quarantine_record(chunk_id)
        if record:
            return record.review_status == "pending"
        return False

    async def get_quarantine_stats(self) -> dict[str, int]:
        """Get quarantine statistics."""
        stats = {
            "pending": 0,
            "released": 0,
            "deleted": 0,
            "total": 0,
        }

        if self.dynamodb:
            for status in ["pending", "released", "deleted"]:
                try:
                    response = self.dynamodb.query(
                        TableName=self.table_name,
                        IndexName="review-status-index",
                        KeyConditionExpression="review_status = :status",
                        ExpressionAttributeValues={":status": {"S": status}},
                        Select="COUNT",
                    )
                    stats[status] = response.get("Count", 0)
                except Exception as e:
                    logger.warning(f"Failed to count {status} records: {e}")

            stats["total"] = stats["pending"] + stats["released"] + stats["deleted"]
        else:
            # In-memory stats
            for record in self._in_memory_quarantine.values():
                stats[record.review_status] = stats.get(record.review_status, 0) + 1
                stats["total"] += 1

        return stats

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def _store_quarantine_record(self, record: QuarantineRecord) -> None:
        """Store record in DynamoDB or in-memory."""
        if self.dynamodb:
            try:
                self.dynamodb.put_item(
                    TableName=self.table_name,
                    Item={
                        "chunk_id": {"S": record.chunk_id},
                        "quarantined_at": {"S": record.quarantined_at.isoformat()},
                        "content_hash": {"S": record.content_hash},
                        "reason": {"S": record.reason.value},
                        "details": {"S": record.details},
                        "quarantined_by": {"S": record.quarantined_by},
                        "review_status": {"S": record.review_status},
                        "provenance": {"S": json.dumps(record.provenance.to_dict())},
                    },
                )
            except Exception as e:
                logger.error(f"Failed to store quarantine record: {e}")
                raise
        else:
            # In-memory storage
            self._in_memory_quarantine[record.chunk_id] = record

    async def _update_quarantine_record(
        self,
        chunk_id: str,
        review_status: str,
        reviewed_by: str,
        reviewed_at: datetime,
        notes: Optional[str] = None,
    ) -> None:
        """Update quarantine record with review result."""
        if self.dynamodb:
            try:
                update_expr = (
                    "SET review_status = :status, reviewed_by = :reviewer, "
                    "reviewed_at = :reviewed_at"
                )
                expr_values: dict[str, Any] = {
                    ":status": {"S": review_status},
                    ":reviewer": {"S": reviewed_by},
                    ":reviewed_at": {"S": reviewed_at.isoformat()},
                }

                if notes:
                    update_expr += ", notes = :notes"
                    expr_values[":notes"] = {"S": notes}

                # We need the sort key - query first
                response = self.dynamodb.query(
                    TableName=self.table_name,
                    KeyConditionExpression="chunk_id = :chunk_id",
                    ExpressionAttributeValues={":chunk_id": {"S": chunk_id}},
                    Limit=1,
                    ScanIndexForward=False,
                )

                items = response.get("Items", [])
                if items:
                    quarantined_at = items[0]["quarantined_at"]["S"]
                    self.dynamodb.update_item(
                        TableName=self.table_name,
                        Key={
                            "chunk_id": {"S": chunk_id},
                            "quarantined_at": {"S": quarantined_at},
                        },
                        UpdateExpression=update_expr,
                        ExpressionAttributeValues=expr_values,
                    )
            except Exception as e:
                logger.error(f"Failed to update quarantine record: {e}")
                raise
        else:
            # In-memory update
            if chunk_id in self._in_memory_quarantine:
                record = self._in_memory_quarantine[chunk_id]
                record.review_status = review_status
                record.reviewed_by = reviewed_by
                record.reviewed_at = reviewed_at

    async def _update_neptune_status(self, chunk_id: str, status: str) -> None:
        """Update vertex status in Neptune."""
        if not self.neptune:
            return

        try:
            query = f"""
            g.V().has('entity_id', '{chunk_id}')
             .property('quarantine_status', '{status}')
            """
            self.neptune.client.submit(query).all().result()
        except Exception as e:
            logger.error(f"Failed to update Neptune status: {e}")

    async def _update_opensearch_status(self, chunk_id: str, status: str) -> None:
        """Update document status in OpenSearch."""
        if not self.opensearch:
            return

        try:
            self.opensearch.update(
                index="aura-code-embeddings",
                id=chunk_id,
                body={"doc": {"status": status}},
            )
        except Exception as e:
            logger.error(f"Failed to update OpenSearch status: {e}")

    async def _delete_from_neptune(self, chunk_id: str) -> None:
        """Delete vertex from Neptune."""
        if not self.neptune:
            return

        try:
            query = f"g.V().has('entity_id', '{chunk_id}').drop()"
            self.neptune.client.submit(query).all().result()
        except Exception as e:
            logger.error(f"Failed to delete from Neptune: {e}")

    async def _delete_from_opensearch(self, chunk_id: str) -> None:
        """Delete document from OpenSearch."""
        if not self.opensearch:
            return

        try:
            self.opensearch.delete(
                index="aura-code-embeddings",
                id=chunk_id,
            )
        except Exception as e:
            logger.error(f"Failed to delete from OpenSearch: {e}")

    async def _send_alert(self, record: QuarantineRecord) -> None:
        """Send SNS alert for quarantine event."""
        if not self.sns or not self.alert_topic:
            return

        try:
            message = {
                "event": "CONTEXT_QUARANTINED",
                "chunk_id": record.chunk_id,
                "reason": record.reason.value,
                "details": record.details,
                "repository": record.provenance.repository_id,
                "commit": record.provenance.commit_sha,
                "timestamp": record.quarantined_at.isoformat(),
                "environment": self.environment,
            }

            self.sns.publish(
                TopicArn=self.alert_topic,
                Message=json.dumps(message),
                Subject="Context Quarantine Alert",
            )
        except Exception as e:
            logger.error(f"Failed to send quarantine alert: {e}")

    def _item_to_record(self, item: dict[str, Any]) -> QuarantineRecord:
        """Convert DynamoDB item to QuarantineRecord."""
        provenance_data = item.get("provenance", {}).get("S", "{}")
        if isinstance(provenance_data, str):
            provenance_data = json.loads(provenance_data)

        reviewed_at = item.get("reviewed_at", {}).get("S")
        if reviewed_at:
            reviewed_at = datetime.fromisoformat(reviewed_at)

        return QuarantineRecord(
            chunk_id=item["chunk_id"]["S"],
            content_hash=item["content_hash"]["S"],
            reason=QuarantineReason(item["reason"]["S"]),
            details=item["details"]["S"],
            quarantined_at=datetime.fromisoformat(item["quarantined_at"]["S"]),
            quarantined_by=item["quarantined_by"]["S"],
            provenance=ProvenanceRecord.from_dict(provenance_data),
            review_status=item.get("review_status", {}).get("S", "pending"),
            reviewed_by=item.get("reviewed_by", {}).get("S"),
            reviewed_at=reviewed_at,
        )


# =============================================================================
# Module-Level Functions
# =============================================================================


_quarantine_manager: Optional[QuarantineManager] = None


def get_quarantine_manager() -> QuarantineManager:
    """Get the global quarantine manager instance."""
    global _quarantine_manager
    if _quarantine_manager is None:
        _quarantine_manager = QuarantineManager()
        logger.info("QuarantineManager initialized with defaults")
    return _quarantine_manager


def configure_quarantine_manager(
    dynamodb_client: Optional[Any] = None,
    neptune_client: Optional[Any] = None,
    opensearch_client: Optional[Any] = None,
    sns_client: Optional[Any] = None,
    table_name: str = "aura-context-quarantine",
    alert_topic_arn: Optional[str] = None,
    environment: str = "dev",
) -> QuarantineManager:
    """Configure the global quarantine manager."""
    global _quarantine_manager
    _quarantine_manager = QuarantineManager(
        dynamodb_client=dynamodb_client,
        neptune_client=neptune_client,
        opensearch_client=opensearch_client,
        sns_client=sns_client,
        table_name=table_name,
        alert_topic_arn=alert_topic_arn,
        environment=environment,
    )
    return _quarantine_manager


def reset_quarantine_manager() -> None:
    """Reset the global quarantine manager (for testing)."""
    global _quarantine_manager
    _quarantine_manager = None
