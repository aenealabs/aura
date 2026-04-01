"""
Checkpoint Persistence Service for Agent Workflows

Provides DynamoDB-backed checkpoint storage for resumable agent workflows.
Replaces ephemeral /tmp storage with durable distributed storage that
survives pod restarts and supports multi-instance deployments.

Environment Variables:
    CHECKPOINT_TABLE_NAME: DynamoDB table name (default: aura-checkpoints-dev)
    AWS_REGION: AWS region for DynamoDB
    CHECKPOINT_TTL_DAYS: Days to retain checkpoints (default: 7)
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

# Boto3 imports (lazy loading for performance)
if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBServiceResource
    from mypy_boto3_dynamodb.service_resource import Table

_dynamodb_resource: "DynamoDBServiceResource | None" = None
_checkpoints_table: "Table | None" = None


def _get_dynamodb_resource() -> "DynamoDBServiceResource":
    """Get or create DynamoDB resource (lazy initialization)."""
    global _dynamodb_resource
    if _dynamodb_resource is None:
        import boto3

        _dynamodb_resource = boto3.resource(
            "dynamodb",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
    return _dynamodb_resource


def _get_checkpoints_table() -> "Table":
    """Get DynamoDB checkpoints table reference."""
    global _checkpoints_table
    if _checkpoints_table is None:
        resource = _get_dynamodb_resource()
        table_name = os.getenv("CHECKPOINT_TABLE_NAME", "aura-checkpoints-dev")
        _checkpoints_table = resource.Table(table_name)
    return _checkpoints_table


class CheckpointPersistenceService:
    """
    DynamoDB-backed checkpoint persistence for agent workflows.

    Provides durable, distributed storage for workflow checkpoints that:
    - Survives pod/container restarts
    - Supports multi-instance deployments
    - Enables workflow resumption across failures
    - Includes automatic TTL cleanup

    Table Schema (from checkpoint-dynamodb.yaml):
        - checkpoint_id (HASH): Unique checkpoint identifier
        - execution_id (GSI): Workflow execution identifier
        - status (GSI sort key): Checkpoint status

    Example:
        >>> service = CheckpointPersistenceService()
        >>> service.save_checkpoint({
        ...     "checkpoint_id": "cp-123",
        ...     "workflow_id": "wf-456",
        ...     "phase": "context_retrieval",
        ...     "user_prompt": "Fix the security bug",
        ...     "tasks": {"target_entity": "auth.py"},
        ... })
        >>> checkpoint = service.load_checkpoint("cp-123")
    """

    def __init__(
        self,
        table_name: str | None = None,
        ttl_days: int | None = None,
    ):
        """
        Initialize checkpoint persistence service.

        Args:
            table_name: DynamoDB table name (default from env)
            ttl_days: Days to retain checkpoints (default from env or 7)
        """
        self._table_name = table_name or os.getenv(
            "CHECKPOINT_TABLE_NAME", "aura-checkpoints-dev"
        )
        self._ttl_days = ttl_days or int(os.getenv("CHECKPOINT_TTL_DAYS", "7"))
        self._table: "Table | None" = None
        self._mock_storage: dict[str, dict[str, Any]] = {}
        self._use_mock = os.getenv("TESTING", "").lower() == "true"

    def _get_table(self) -> "Table":
        """Get DynamoDB table reference."""
        if self._table is None:
            resource = _get_dynamodb_resource()
            self._table = resource.Table(self._table_name)
        return self._table

    def _calculate_ttl(self) -> int:
        """Calculate TTL timestamp for checkpoint expiration."""
        return int(time.time()) + (self._ttl_days * 24 * 60 * 60)

    def save_checkpoint(self, checkpoint_data: dict[str, Any]) -> str:
        """
        Save checkpoint to DynamoDB.

        Args:
            checkpoint_data: Checkpoint dictionary containing at minimum:
                - checkpoint_id: Unique identifier
                - workflow_id or execution_id: Parent workflow identifier
                - phase: Current workflow phase

        Returns:
            Checkpoint ID

        Raises:
            ValueError: If checkpoint_id is missing
        """
        checkpoint_id = checkpoint_data.get("checkpoint_id")
        if not checkpoint_id:
            raise ValueError("checkpoint_data must contain checkpoint_id")

        # Ensure execution_id is set for GSI
        if "execution_id" not in checkpoint_data:
            checkpoint_data["execution_id"] = checkpoint_data.get(
                "workflow_id", "unknown"
            )

        # Add status for GSI if not present
        if "status" not in checkpoint_data:
            phase = checkpoint_data.get("phase", "unknown")
            if isinstance(phase, str):
                checkpoint_data["status"] = phase
            else:
                checkpoint_data["status"] = getattr(phase, "value", str(phase))

        # Add TTL and timestamps
        checkpoint_data["ttl"] = self._calculate_ttl()
        checkpoint_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "created_at" not in checkpoint_data:
            checkpoint_data["created_at"] = checkpoint_data["updated_at"]

        # Serialize any complex types
        item = self._serialize_item(checkpoint_data)

        if self._use_mock:
            self._mock_storage[checkpoint_id] = item
            logger.info(f"Saved checkpoint {checkpoint_id} to mock storage")
            return checkpoint_id

        try:
            table = self._get_table()
            table.put_item(Item=item)
            logger.info(
                f"Saved checkpoint {checkpoint_id} to DynamoDB "
                f"(phase={checkpoint_data.get('status')}, ttl_days={self._ttl_days})"
            )
            return checkpoint_id
        except Exception as e:
            logger.error(f"Failed to save checkpoint {checkpoint_id}: {e}")
            raise

    def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """
        Load checkpoint from DynamoDB.

        Args:
            checkpoint_id: Checkpoint identifier to load

        Returns:
            Checkpoint data dictionary or None if not found
        """
        if self._use_mock:
            item = self._mock_storage.get(checkpoint_id)
            if item:
                logger.info(f"Loaded checkpoint {checkpoint_id} from mock storage")
                return self._deserialize_item(item)
            logger.warning(f"Checkpoint not found in mock storage: {checkpoint_id}")
            return None

        try:
            table = self._get_table()
            response = table.get_item(Key={"checkpoint_id": checkpoint_id})
            item = response.get("Item")

            if item is None:
                logger.warning(f"Checkpoint not found: {checkpoint_id}")
                return None

            # Check if expired (DynamoDB TTL is eventually consistent)
            if "ttl" in item and item["ttl"] < time.time():
                logger.warning(f"Checkpoint {checkpoint_id} has expired")
                return None

            logger.info(
                f"Loaded checkpoint {checkpoint_id} " f"(phase={item.get('status')})"
            )
            return self._deserialize_item(item)
        except Exception as e:
            logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def list_checkpoints_by_execution(
        self,
        execution_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        List checkpoints for a workflow execution.

        Args:
            execution_id: Workflow execution identifier
            status: Optional status filter
            limit: Maximum checkpoints to return

        Returns:
            List of checkpoint data dictionaries
        """
        if self._use_mock:
            results = [
                self._deserialize_item(cp)
                for cp in self._mock_storage.values()
                if cp.get("execution_id") == execution_id
                and (status is None or cp.get("status") == status)
            ]
            return results[:limit]

        try:
            table = self._get_table()

            key_condition = "execution_id = :eid"
            expr_values: dict[str, Any] = {":eid": execution_id}

            if status:
                key_condition += " AND #status = :status"
                expr_values[":status"] = status
                response = table.query(
                    IndexName="execution-status-index",
                    KeyConditionExpression=key_condition,
                    ExpressionAttributeValues=expr_values,
                    ExpressionAttributeNames={"#status": "status"},
                    Limit=limit,
                )
            else:
                response = table.query(
                    IndexName="execution-status-index",
                    KeyConditionExpression=key_condition,
                    ExpressionAttributeValues=expr_values,
                    Limit=limit,
                )

            return [self._deserialize_item(item) for item in response.get("Items", [])]
        except Exception as e:
            logger.error(f"Failed to list checkpoints for {execution_id}: {e}")
            return []

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint to delete

        Returns:
            True if deleted, False otherwise
        """
        if self._use_mock:
            if checkpoint_id in self._mock_storage:
                del self._mock_storage[checkpoint_id]
                logger.info(f"Deleted checkpoint {checkpoint_id} from mock storage")
                return True
            return False

        try:
            table = self._get_table()
            table.delete_item(Key={"checkpoint_id": checkpoint_id})
            logger.info(f"Deleted checkpoint {checkpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False

    def update_checkpoint_status(
        self,
        checkpoint_id: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update checkpoint status and optionally add metadata.

        Args:
            checkpoint_id: Checkpoint to update
            status: New status value
            metadata: Optional additional data to merge

        Returns:
            True if updated, False otherwise
        """
        if self._use_mock:
            if checkpoint_id in self._mock_storage:
                self._mock_storage[checkpoint_id]["status"] = status
                self._mock_storage[checkpoint_id]["updated_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                if metadata:
                    self._mock_storage[checkpoint_id].update(metadata)
                return True
            return False

        try:
            table = self._get_table()

            update_expr = "SET #status = :status, updated_at = :updated"
            expr_names = {"#status": "status"}
            expr_values: dict[str, Any] = {
                ":status": status,
                ":updated": datetime.now(timezone.utc).isoformat(),
            }

            if metadata:
                for i, (key, value) in enumerate(metadata.items()):
                    update_expr += f", #{key} = :val{i}"
                    expr_names[f"#{key}"] = key
                    expr_values[f":val{i}"] = self._serialize_value(value)

            table.update_item(
                Key={"checkpoint_id": checkpoint_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )
            logger.info(f"Updated checkpoint {checkpoint_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update checkpoint {checkpoint_id}: {e}")
            return False

    def _serialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Serialize item for DynamoDB storage."""
        result = {}
        for key, value in item.items():
            result[key] = self._serialize_value(value)
        return result

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a single value for DynamoDB."""
        if isinstance(value, dict):
            return json.dumps(value)
        if isinstance(value, (list, tuple)):
            return json.dumps(value)
        if hasattr(value, "value"):  # Enum
            return value.value
        return value

    def _deserialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Deserialize item from DynamoDB storage."""
        result = {}
        for key, value in item.items():
            result[key] = self._deserialize_value(key, value)
        return result

    def _deserialize_value(self, key: str, value: Any) -> Any:
        """Deserialize a single value from DynamoDB."""
        # Keys known to be JSON
        json_keys = {
            "tasks",
            "hybrid_context_data",
            "review_result",
            "validation_result",
            "metadata",
        }
        if key in json_keys and isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value


# Singleton instance
_service_instance: CheckpointPersistenceService | None = None


def get_checkpoint_service(
    table_name: str | None = None,
    ttl_days: int | None = None,
) -> CheckpointPersistenceService:
    """
    Get or create singleton checkpoint persistence service.

    Args:
        table_name: Optional table name override
        ttl_days: Optional TTL override

    Returns:
        CheckpointPersistenceService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = CheckpointPersistenceService(table_name, ttl_days)
    return _service_instance


def create_checkpoint_service(
    table_name: str | None = None,
    ttl_days: int | None = None,
) -> CheckpointPersistenceService:
    """
    Create new checkpoint persistence service instance.

    Args:
        table_name: Optional table name override
        ttl_days: Optional TTL override

    Returns:
        New CheckpointPersistenceService instance
    """
    return CheckpointPersistenceService(table_name, ttl_days)
