"""Tests for CheckpointPersistenceService

Comprehensive tests for DynamoDB-backed checkpoint storage.
"""

import json
import os
import time
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest

from src.services.checkpoint_persistence_service import (
    CheckpointPersistenceService,
    create_checkpoint_service,
    get_checkpoint_service,
)


class TestCheckpointPersistenceServiceInit:
    """Tests for CheckpointPersistenceService initialization."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        with patch.dict(os.environ, {}, clear=True):
            service = CheckpointPersistenceService()
            assert service._table_name == "aura-checkpoints-dev"
            assert service._ttl_days == 7
            assert service._table is None
            assert service._mock_storage == {}

    def test_init_custom_table_name(self):
        """Test initialization with custom table name."""
        service = CheckpointPersistenceService(table_name="custom-checkpoints")
        assert service._table_name == "custom-checkpoints"

    def test_init_custom_ttl(self):
        """Test initialization with custom TTL."""
        service = CheckpointPersistenceService(ttl_days=30)
        assert service._ttl_days == 30

    def test_init_from_env_vars(self):
        """Test initialization reads from environment variables."""
        with patch.dict(
            os.environ,
            {
                "CHECKPOINT_TABLE_NAME": "env-checkpoints-table",
                "CHECKPOINT_TTL_DAYS": "14",
            },
        ):
            service = CheckpointPersistenceService()
            assert service._table_name == "env-checkpoints-table"
            assert service._ttl_days == 14

    def test_init_testing_mode(self):
        """Test initialization in testing mode."""
        with patch.dict(os.environ, {"TESTING": "true"}):
            service = CheckpointPersistenceService()
            assert service._use_mock is True

    def test_init_testing_mode_case_insensitive(self):
        """Test TESTING env var is case-insensitive."""
        with patch.dict(os.environ, {"TESTING": "TRUE"}):
            service = CheckpointPersistenceService()
            assert service._use_mock is True


class TestCheckpointPersistenceServiceMockMode:
    """Tests for CheckpointPersistenceService in mock mode."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CheckpointPersistenceService()
        self.service._use_mock = True

    def test_save_checkpoint_basic(self):
        """Test saving a basic checkpoint."""
        checkpoint_data = {
            "checkpoint_id": "cp-001",
            "workflow_id": "wf-001",
            "phase": "context_retrieval",
            "user_prompt": "Fix the bug",
        }

        result = self.service.save_checkpoint(checkpoint_data)

        assert result == "cp-001"
        assert "cp-001" in self.service._mock_storage
        saved = self.service._mock_storage["cp-001"]
        assert saved["checkpoint_id"] == "cp-001"
        assert saved["execution_id"] == "wf-001"
        assert saved["status"] == "context_retrieval"
        assert "ttl" in saved
        assert "created_at" in saved
        assert "updated_at" in saved

    def test_save_checkpoint_missing_id_raises(self):
        """Test saving checkpoint without ID raises ValueError."""
        with pytest.raises(ValueError, match="must contain checkpoint_id"):
            self.service.save_checkpoint({"workflow_id": "wf-001"})

    def test_save_checkpoint_with_execution_id(self):
        """Test saving checkpoint with explicit execution_id."""
        checkpoint_data = {
            "checkpoint_id": "cp-002",
            "execution_id": "exec-002",
            "phase": "review",
        }

        self.service.save_checkpoint(checkpoint_data)

        saved = self.service._mock_storage["cp-002"]
        assert saved["execution_id"] == "exec-002"

    def test_save_checkpoint_with_status(self):
        """Test saving checkpoint with explicit status."""
        checkpoint_data = {
            "checkpoint_id": "cp-003",
            "workflow_id": "wf-003",
            "phase": "generation",
            "status": "in_progress",
        }

        self.service.save_checkpoint(checkpoint_data)

        saved = self.service._mock_storage["cp-003"]
        assert saved["status"] == "in_progress"

    def test_save_checkpoint_with_enum_phase(self):
        """Test saving checkpoint with enum phase."""

        class WorkflowPhase(Enum):
            GENERATION = "generation"
            REVIEW = "review"

        checkpoint_data = {
            "checkpoint_id": "cp-004",
            "workflow_id": "wf-004",
            "phase": WorkflowPhase.GENERATION,
        }

        self.service.save_checkpoint(checkpoint_data)

        saved = self.service._mock_storage["cp-004"]
        assert saved["status"] == "generation"

    def test_save_checkpoint_preserves_created_at(self):
        """Test saving checkpoint preserves existing created_at."""
        created_time = "2025-01-01T00:00:00+00:00"
        checkpoint_data = {
            "checkpoint_id": "cp-005",
            "workflow_id": "wf-005",
            "phase": "test",
            "created_at": created_time,
        }

        self.service.save_checkpoint(checkpoint_data)

        saved = self.service._mock_storage["cp-005"]
        assert saved["created_at"] == created_time

    def test_load_checkpoint_exists(self):
        """Test loading existing checkpoint."""
        self.service._mock_storage["cp-load-001"] = {
            "checkpoint_id": "cp-load-001",
            "workflow_id": "wf-001",
            "status": "completed",
            "data": "test_data",
        }

        result = self.service.load_checkpoint("cp-load-001")

        assert result is not None
        assert result["checkpoint_id"] == "cp-load-001"
        assert result["data"] == "test_data"

    def test_load_checkpoint_not_found(self):
        """Test loading non-existent checkpoint returns None."""
        result = self.service.load_checkpoint("nonexistent")
        assert result is None

    def test_delete_checkpoint_exists(self):
        """Test deleting existing checkpoint."""
        self.service._mock_storage["cp-delete"] = {"checkpoint_id": "cp-delete"}

        result = self.service.delete_checkpoint("cp-delete")

        assert result is True
        assert "cp-delete" not in self.service._mock_storage

    def test_delete_checkpoint_not_found(self):
        """Test deleting non-existent checkpoint returns False."""
        result = self.service.delete_checkpoint("nonexistent")
        assert result is False

    def test_update_checkpoint_status(self):
        """Test updating checkpoint status."""
        self.service._mock_storage["cp-update"] = {
            "checkpoint_id": "cp-update",
            "status": "pending",
        }

        result = self.service.update_checkpoint_status("cp-update", "completed")

        assert result is True
        assert self.service._mock_storage["cp-update"]["status"] == "completed"
        assert "updated_at" in self.service._mock_storage["cp-update"]

    def test_update_checkpoint_status_with_metadata(self):
        """Test updating checkpoint status with additional metadata."""
        self.service._mock_storage["cp-update-meta"] = {
            "checkpoint_id": "cp-update-meta",
            "status": "pending",
        }

        result = self.service.update_checkpoint_status(
            "cp-update-meta",
            "completed",
            metadata={"result": "success", "score": 95},
        )

        assert result is True
        stored = self.service._mock_storage["cp-update-meta"]
        assert stored["status"] == "completed"
        assert stored["result"] == "success"
        assert stored["score"] == 95

    def test_update_checkpoint_status_not_found(self):
        """Test updating non-existent checkpoint returns False."""
        result = self.service.update_checkpoint_status("nonexistent", "completed")
        assert result is False

    def test_list_checkpoints_by_execution(self):
        """Test listing checkpoints by execution ID."""
        self.service._mock_storage = {
            "cp-1": {
                "checkpoint_id": "cp-1",
                "execution_id": "exec-001",
                "status": "a",
            },
            "cp-2": {
                "checkpoint_id": "cp-2",
                "execution_id": "exec-001",
                "status": "b",
            },
            "cp-3": {
                "checkpoint_id": "cp-3",
                "execution_id": "exec-002",
                "status": "a",
            },
        }

        results = self.service.list_checkpoints_by_execution("exec-001")

        assert len(results) == 2
        assert all(r["execution_id"] == "exec-001" for r in results)

    def test_list_checkpoints_by_execution_with_status_filter(self):
        """Test listing checkpoints with status filter."""
        self.service._mock_storage = {
            "cp-1": {
                "checkpoint_id": "cp-1",
                "execution_id": "exec-001",
                "status": "pending",
            },
            "cp-2": {
                "checkpoint_id": "cp-2",
                "execution_id": "exec-001",
                "status": "completed",
            },
            "cp-3": {
                "checkpoint_id": "cp-3",
                "execution_id": "exec-001",
                "status": "pending",
            },
        }

        results = self.service.list_checkpoints_by_execution(
            "exec-001", status="pending"
        )

        assert len(results) == 2
        assert all(r["status"] == "pending" for r in results)

    def test_list_checkpoints_by_execution_with_limit(self):
        """Test listing checkpoints respects limit."""
        self.service._mock_storage = {
            f"cp-{i}": {
                "checkpoint_id": f"cp-{i}",
                "execution_id": "exec-001",
                "status": "a",
            }
            for i in range(10)
        }

        results = self.service.list_checkpoints_by_execution("exec-001", limit=3)

        assert len(results) == 3

    def test_list_checkpoints_by_execution_empty(self):
        """Test listing checkpoints for non-existent execution."""
        results = self.service.list_checkpoints_by_execution("nonexistent")
        assert results == []


class TestCheckpointPersistenceServiceSerialization:
    """Tests for serialization/deserialization methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CheckpointPersistenceService()
        self.service._use_mock = True

    def test_serialize_value_dict(self):
        """Test serializing dictionary value."""
        value = {"key": "value", "nested": {"a": 1}}
        result = self.service._serialize_value(value)
        assert isinstance(result, str)
        assert json.loads(result) == value

    def test_serialize_value_list(self):
        """Test serializing list value."""
        value = [1, 2, 3, "four"]
        result = self.service._serialize_value(value)
        assert isinstance(result, str)
        assert json.loads(result) == value

    def test_serialize_value_tuple(self):
        """Test serializing tuple value."""
        value = (1, 2, 3)
        result = self.service._serialize_value(value)
        assert isinstance(result, str)
        assert json.loads(result) == [1, 2, 3]  # Tuple becomes list

    def test_serialize_value_enum(self):
        """Test serializing enum value."""

        class Status(Enum):
            PENDING = "pending"
            COMPLETED = "completed"

        result = self.service._serialize_value(Status.PENDING)
        assert result == "pending"

    def test_serialize_value_primitive(self):
        """Test serializing primitive values."""
        assert self.service._serialize_value("string") == "string"
        assert self.service._serialize_value(123) == 123
        assert self.service._serialize_value(3.14) == 3.14
        assert self.service._serialize_value(True) is True

    def test_serialize_item(self):
        """Test serializing entire item."""
        item = {
            "checkpoint_id": "cp-001",
            "tasks": {"task1": "do something"},
            "count": 5,
        }

        result = self.service._serialize_item(item)

        assert result["checkpoint_id"] == "cp-001"
        assert isinstance(result["tasks"], str)
        assert result["count"] == 5

    def test_deserialize_value_json_key(self):
        """Test deserializing known JSON keys."""
        json_str = '{"key": "value"}'
        result = self.service._deserialize_value("tasks", json_str)
        assert result == {"key": "value"}

    def test_deserialize_value_json_key_invalid_json(self):
        """Test deserializing invalid JSON returns original."""
        result = self.service._deserialize_value("tasks", "not-json")
        assert result == "not-json"

    def test_deserialize_value_non_json_key(self):
        """Test deserializing non-JSON key returns as-is."""
        result = self.service._deserialize_value("checkpoint_id", "cp-001")
        assert result == "cp-001"

    def test_deserialize_item(self):
        """Test deserializing entire item."""
        item = {
            "checkpoint_id": "cp-001",
            "tasks": '{"task1": "do something"}',
            "metadata": '{"key": "value"}',
            "status": "completed",
        }

        result = self.service._deserialize_item(item)

        assert result["checkpoint_id"] == "cp-001"
        assert result["tasks"] == {"task1": "do something"}
        assert result["metadata"] == {"key": "value"}
        assert result["status"] == "completed"

    def test_all_json_keys_deserialized(self):
        """Test all known JSON keys are deserialized."""
        json_keys = [
            "tasks",
            "hybrid_context_data",
            "review_result",
            "validation_result",
            "metadata",
        ]

        for key in json_keys:
            result = self.service._deserialize_value(key, '{"test": true}')
            assert result == {"test": True}, f"Key {key} not deserialized"


class TestCheckpointPersistenceServiceTTL:
    """Tests for TTL calculation."""

    def test_calculate_ttl_default(self):
        """Test TTL calculation with default 7 days."""
        service = CheckpointPersistenceService(ttl_days=7)
        expected_min = int(time.time()) + (7 * 24 * 60 * 60) - 1
        expected_max = int(time.time()) + (7 * 24 * 60 * 60) + 1

        ttl = service._calculate_ttl()

        assert expected_min <= ttl <= expected_max

    def test_calculate_ttl_custom(self):
        """Test TTL calculation with custom days."""
        service = CheckpointPersistenceService(ttl_days=30)
        expected_min = int(time.time()) + (30 * 24 * 60 * 60) - 1
        expected_max = int(time.time()) + (30 * 24 * 60 * 60) + 1

        ttl = service._calculate_ttl()

        assert expected_min <= ttl <= expected_max


class TestCheckpointPersistenceServiceDynamoDB:
    """Tests for DynamoDB operations (mocked)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CheckpointPersistenceService()
        self.service._use_mock = False
        self.mock_table = MagicMock()
        self.service._table = self.mock_table

    def test_save_checkpoint_dynamodb(self):
        """Test saving checkpoint to DynamoDB."""
        checkpoint_data = {
            "checkpoint_id": "cp-ddb-001",
            "workflow_id": "wf-001",
            "phase": "test",
        }

        result = self.service.save_checkpoint(checkpoint_data)

        assert result == "cp-ddb-001"
        self.mock_table.put_item.assert_called_once()
        call_args = self.mock_table.put_item.call_args
        item = call_args[1]["Item"]
        assert item["checkpoint_id"] == "cp-ddb-001"

    def test_save_checkpoint_dynamodb_error(self):
        """Test saving checkpoint handles DynamoDB errors."""
        self.mock_table.put_item.side_effect = Exception("DynamoDB error")

        with pytest.raises(Exception, match="DynamoDB error"):
            self.service.save_checkpoint(
                {
                    "checkpoint_id": "cp-error",
                    "workflow_id": "wf-001",
                    "phase": "test",
                }
            )

    def test_load_checkpoint_dynamodb_found(self):
        """Test loading checkpoint from DynamoDB when found."""
        self.mock_table.get_item.return_value = {
            "Item": {
                "checkpoint_id": "cp-ddb-load",
                "status": "completed",
                "ttl": int(time.time()) + 10000,
            }
        }

        result = self.service.load_checkpoint("cp-ddb-load")

        assert result is not None
        assert result["checkpoint_id"] == "cp-ddb-load"
        self.mock_table.get_item.assert_called_once_with(
            Key={"checkpoint_id": "cp-ddb-load"}
        )

    def test_load_checkpoint_dynamodb_not_found(self):
        """Test loading checkpoint from DynamoDB when not found."""
        self.mock_table.get_item.return_value = {}

        result = self.service.load_checkpoint("nonexistent")

        assert result is None

    def test_load_checkpoint_dynamodb_expired(self):
        """Test loading expired checkpoint returns None."""
        self.mock_table.get_item.return_value = {
            "Item": {
                "checkpoint_id": "cp-expired",
                "status": "completed",
                "ttl": int(time.time()) - 1000,  # Expired
            }
        }

        result = self.service.load_checkpoint("cp-expired")

        assert result is None

    def test_load_checkpoint_dynamodb_error(self):
        """Test loading checkpoint handles DynamoDB errors."""
        self.mock_table.get_item.side_effect = Exception("DynamoDB error")

        result = self.service.load_checkpoint("cp-error")

        assert result is None

    def test_delete_checkpoint_dynamodb(self):
        """Test deleting checkpoint from DynamoDB."""
        result = self.service.delete_checkpoint("cp-delete")

        assert result is True
        self.mock_table.delete_item.assert_called_once_with(
            Key={"checkpoint_id": "cp-delete"}
        )

    def test_delete_checkpoint_dynamodb_error(self):
        """Test deleting checkpoint handles DynamoDB errors."""
        self.mock_table.delete_item.side_effect = Exception("DynamoDB error")

        result = self.service.delete_checkpoint("cp-error")

        assert result is False

    def test_update_checkpoint_status_dynamodb(self):
        """Test updating checkpoint status in DynamoDB."""
        result = self.service.update_checkpoint_status("cp-update", "completed")

        assert result is True
        self.mock_table.update_item.assert_called_once()
        call_args = self.mock_table.update_item.call_args
        assert call_args[1]["Key"] == {"checkpoint_id": "cp-update"}

    def test_update_checkpoint_status_with_metadata_dynamodb(self):
        """Test updating checkpoint status with metadata in DynamoDB."""
        result = self.service.update_checkpoint_status(
            "cp-update",
            "completed",
            metadata={"result": "success"},
        )

        assert result is True
        call_args = self.mock_table.update_item.call_args
        assert "#result" in call_args[1]["ExpressionAttributeNames"]

    def test_update_checkpoint_status_dynamodb_error(self):
        """Test updating checkpoint handles DynamoDB errors."""
        self.mock_table.update_item.side_effect = Exception("DynamoDB error")

        result = self.service.update_checkpoint_status("cp-error", "failed")

        assert result is False

    def test_list_checkpoints_dynamodb_without_status(self):
        """Test listing checkpoints from DynamoDB without status filter."""
        self.mock_table.query.return_value = {
            "Items": [
                {"checkpoint_id": "cp-1", "execution_id": "exec-001"},
                {"checkpoint_id": "cp-2", "execution_id": "exec-001"},
            ]
        }

        results = self.service.list_checkpoints_by_execution("exec-001")

        assert len(results) == 2
        self.mock_table.query.assert_called_once()
        call_args = self.mock_table.query.call_args
        assert call_args[1]["IndexName"] == "execution-status-index"

    def test_list_checkpoints_dynamodb_with_status(self):
        """Test listing checkpoints from DynamoDB with status filter."""
        self.mock_table.query.return_value = {
            "Items": [
                {
                    "checkpoint_id": "cp-1",
                    "execution_id": "exec-001",
                    "status": "completed",
                }
            ]
        }

        results = self.service.list_checkpoints_by_execution(
            "exec-001", status="completed"
        )

        assert len(results) == 1
        call_args = self.mock_table.query.call_args
        assert "#status" in call_args[1].get("ExpressionAttributeNames", {})

    def test_list_checkpoints_dynamodb_error(self):
        """Test listing checkpoints handles DynamoDB errors."""
        self.mock_table.query.side_effect = Exception("DynamoDB error")

        results = self.service.list_checkpoints_by_execution("exec-001")

        assert results == []


class TestCheckpointPersistenceServiceGetTable:
    """Tests for _get_table method."""

    def test_get_table_lazy_init(self):
        """Test table is lazily initialized and cached."""
        service = CheckpointPersistenceService(table_name="test-table")
        service._use_mock = True  # Use mock mode to avoid DynamoDB calls

        # Table should not be created yet (lazy initialization)
        assert service._table is None

        # Manually set a mock table to test caching behavior
        mock_table = MagicMock()
        service._table = mock_table

        # Subsequent _get_table calls should return the cached table
        result = service._get_table()
        assert result is mock_table

        # Calling again should return same cached instance
        result2 = service._get_table()
        assert result2 is mock_table
        assert result is result2  # Same object reference


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_checkpoint_service_defaults(self):
        """Test create_checkpoint_service with defaults."""
        service = create_checkpoint_service()

        assert isinstance(service, CheckpointPersistenceService)
        assert service._table_name == "aura-checkpoints-dev"
        assert service._ttl_days == 7

    def test_create_checkpoint_service_custom(self):
        """Test create_checkpoint_service with custom values."""
        service = create_checkpoint_service(
            table_name="custom-table",
            ttl_days=30,
        )

        assert service._table_name == "custom-table"
        assert service._ttl_days == 30

    def test_create_checkpoint_service_always_new(self):
        """Test create_checkpoint_service always returns new instance."""
        service1 = create_checkpoint_service()
        service2 = create_checkpoint_service()

        assert service1 is not service2

    def test_get_checkpoint_service_singleton(self):
        """Test get_checkpoint_service returns singleton."""
        # Reset singleton
        import src.services.checkpoint_persistence_service as module

        module._service_instance = None

        service1 = get_checkpoint_service()
        service2 = get_checkpoint_service()

        assert service1 is service2

        # Clean up
        module._service_instance = None


class TestModuleLevelFunctions:
    """Tests for module-level DynamoDB functions."""

    def test_get_dynamodb_resource_lazy(self):
        """Test _get_dynamodb_resource is lazily initialized."""
        import src.services.checkpoint_persistence_service as module

        # Reset global
        module._dynamodb_resource = None

        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value = MagicMock()

            # First call creates resource
            resource1 = module._get_dynamodb_resource()
            mock_resource.assert_called_once_with("dynamodb", region_name="us-east-1")

            # Second call returns cached
            resource2 = module._get_dynamodb_resource()
            assert resource1 is resource2
            mock_resource.assert_called_once()  # Still only one call

            # Clean up
            module._dynamodb_resource = None

    def test_get_dynamodb_resource_custom_region(self):
        """Test _get_dynamodb_resource uses AWS_REGION env var."""
        import src.services.checkpoint_persistence_service as module

        module._dynamodb_resource = None

        with patch.dict(os.environ, {"AWS_REGION": "us-west-2"}):
            with patch("boto3.resource") as mock_resource:
                mock_resource.return_value = MagicMock()

                module._get_dynamodb_resource()

                mock_resource.assert_called_once_with(
                    "dynamodb", region_name="us-west-2"
                )

        module._dynamodb_resource = None

    def test_get_checkpoints_table_lazy(self):
        """Test _get_checkpoints_table is lazily initialized."""
        import src.services.checkpoint_persistence_service as module

        module._checkpoints_table = None
        module._dynamodb_resource = None

        with patch("boto3.resource") as mock_boto_resource:
            mock_resource = MagicMock()
            mock_table = MagicMock()
            mock_resource.Table.return_value = mock_table
            mock_boto_resource.return_value = mock_resource

            # First call creates table
            table1 = module._get_checkpoints_table()
            assert table1 is mock_table
            mock_resource.Table.assert_called_once_with("aura-checkpoints-dev")

            # Second call returns cached
            table2 = module._get_checkpoints_table()
            assert table2 is mock_table
            mock_resource.Table.assert_called_once()  # Still only one call

            # Clean up
            module._checkpoints_table = None
            module._dynamodb_resource = None


class TestCheckpointPersistenceServiceIntegration:
    """Integration-style tests for full workflows."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = CheckpointPersistenceService()
        self.service._use_mock = True

    def test_full_checkpoint_lifecycle(self):
        """Test complete checkpoint lifecycle: create, load, update, delete."""
        # Create
        checkpoint_data = {
            "checkpoint_id": "cp-lifecycle",
            "workflow_id": "wf-lifecycle",
            "phase": "init",
            "user_prompt": "Test the lifecycle",
            "tasks": {"step1": "do something"},
        }

        cp_id = self.service.save_checkpoint(checkpoint_data)
        assert cp_id == "cp-lifecycle"

        # Load
        loaded = self.service.load_checkpoint("cp-lifecycle")
        assert loaded is not None
        assert loaded["user_prompt"] == "Test the lifecycle"
        assert loaded["tasks"] == {"step1": "do something"}

        # Update
        success = self.service.update_checkpoint_status(
            "cp-lifecycle",
            "completed",
            metadata={"result": "success"},
        )
        assert success is True

        # Load again to verify update
        loaded = self.service.load_checkpoint("cp-lifecycle")
        assert loaded["status"] == "completed"
        assert loaded["result"] == "success"

        # Delete
        deleted = self.service.delete_checkpoint("cp-lifecycle")
        assert deleted is True

        # Verify deleted
        loaded = self.service.load_checkpoint("cp-lifecycle")
        assert loaded is None

    def test_multiple_checkpoints_per_execution(self):
        """Test multiple checkpoints for same execution."""
        execution_id = "exec-multi"

        # Create multiple checkpoints
        for i, phase in enumerate(["init", "context", "generation", "review"]):
            self.service.save_checkpoint(
                {
                    "checkpoint_id": f"cp-multi-{i}",
                    "execution_id": execution_id,
                    "phase": phase,
                    "step": i,
                }
            )

        # List all checkpoints
        all_checkpoints = self.service.list_checkpoints_by_execution(execution_id)
        assert len(all_checkpoints) == 4

        # Filter by status
        init_checkpoints = self.service.list_checkpoints_by_execution(
            execution_id, status="init"
        )
        assert len(init_checkpoints) == 1
        assert init_checkpoints[0]["step"] == 0

    def test_checkpoint_with_complex_data(self):
        """Test checkpoint with complex nested data structures."""
        complex_data = {
            "checkpoint_id": "cp-complex",
            "workflow_id": "wf-complex",
            "phase": "processing",
            "tasks": {
                "main_task": "process data",
                "subtasks": ["step1", "step2", "step3"],
                "config": {"timeout": 300, "retry": True},
            },
            "hybrid_context_data": {
                "graph_results": [{"node": "A", "score": 0.9}],
                "vector_results": [{"id": "vec1", "score": 0.85}],
            },
            "metadata": {
                "agent": "test_agent",
                "version": "1.0",
            },
        }

        self.service.save_checkpoint(complex_data)

        loaded = self.service.load_checkpoint("cp-complex")

        assert loaded["tasks"]["subtasks"] == ["step1", "step2", "step3"]
        assert loaded["hybrid_context_data"]["graph_results"][0]["score"] == 0.9
        assert loaded["metadata"]["agent"] == "test_agent"
